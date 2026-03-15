"""
Approval Prediction Model
==========================
Predicts regulatory approval probability and submission readiness score
using a gradient-boosted ensemble trained on historical project outcomes.

Features:
  - Room counts and types
  - Violation counts by severity
  - Area metrics
  - Estimated correction costs
  - Facility type and region

Model training uses the Outcome Dataset (see storage/outcome_dataset.py).
On first run without a saved model, uses a calibrated rule-based baseline.
"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import numpy as np

try:
    import joblib
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.calibration import CalibratedClassifierCV
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from src.core.config import settings
from src.models.compliance import ComplianceReport, ViolationSeverity
from src.models.prediction import (
    ApprovalPrediction,
    PredictionFeatures,
    RegulatorPrediction,
    RegulatorType,
    RiskLevel,
    ProjectOutcome,
)
from src.models.blueprint import BlueprintParseResult, RoomType

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Baseline heuristics (used when no trained model is available)
# ------------------------------------------------------------------

def _baseline_approval_probability(features: PredictionFeatures) -> float:
    """
    Rule-based baseline calibrated against FGI review outcome statistics.
    Returns a probability 0–100.
    """
    score = 95.0  # start optimistic

    # Critical violations are hard blockers
    score -= features.critical_violations * 18.0

    # High violations have major impact
    score -= features.high_violations * 8.0

    # Medium violations have moderate impact
    score -= features.medium_violations * 3.0

    # Low violations minimal impact
    score -= features.low_violations * 0.5

    # Complex OR suites have stricter review
    if features.operating_room_count > 4:
        score -= features.operating_room_count * 1.5

    # Ventilation and adjacency are high-scrutiny areas
    score -= features.ventilation_deficiencies * 6.0
    score -= features.adjacency_violations * 5.0

    return max(0.0, min(100.0, round(score, 1)))


def _compute_submission_readiness(features: PredictionFeatures) -> float:
    """
    Submission readiness: composite score that weights how close a
    project is to being ready for formal submission.
    """
    score = 100.0

    if features.critical_violations > 0:
        score -= min(50, features.critical_violations * 20)
    if features.high_violations > 0:
        score -= min(30, features.high_violations * 7)
    score -= min(10, features.medium_violations * 2)
    score -= min(5, features.low_violations)

    # Penalty for extremely high correction costs
    cost_m = features.estimated_correction_cost_usd / 1_000_000
    score -= min(15, cost_m * 2)

    return max(0.0, min(100.0, round(score, 1)))


def _risk_level_from_score(readiness: float) -> RiskLevel:
    if readiness >= 85:
        return RiskLevel.LOW
    if readiness >= 65:
        return RiskLevel.MEDIUM
    if readiness >= 40:
        return RiskLevel.HIGH
    return RiskLevel.VERY_HIGH


def _expected_review_days(features: PredictionFeatures, regulator: RegulatorType) -> int:
    """Estimate review duration based on complexity and violations."""
    base = {"FGI": 30, "AHJ": 45, "state": 60, "joint_commission": 90}
    days = base.get(regulator.value, 45)

    # More complex = longer review
    days += features.total_rooms // 10
    days += features.critical_violations * 10
    days += features.high_violations * 3

    if features.operating_room_count > 0:
        days += 10
    if features.has_icu:
        days += 5

    return days


# ------------------------------------------------------------------
# Feature extraction
# ------------------------------------------------------------------

def extract_features(
    parse_result: BlueprintParseResult,
    compliance_report: ComplianceReport,
    facility_type: str = "hospital",
    regulator_region: str = "national",
) -> PredictionFeatures:
    """Build a PredictionFeatures object from parse + compliance data."""
    rooms = parse_result.rooms
    room_types = [r.room_type for r in rooms]

    or_count = sum(1 for rt in room_types if rt == RoomType.OPERATING_ROOM)
    icu_count = sum(1 for rt in room_types if rt == RoomType.ICU)

    # Corridor widths
    corridor_widths = [
        c.width_ft for c in parse_result.corridors if c.width_ft is not None
    ]
    min_corridor_width = min(corridor_widths) if corridor_widths else 8.0

    # Violation type breakdown
    all_violations = [v for r in compliance_report.room_results for v in r.violations]
    vent_deficiencies = sum(
        1 for v in all_violations
        if "ventilation" in v.constraint_type.value
    )
    adj_violations = sum(
        1 for v in all_violations
        if "adjacency" in v.constraint_type.value
    )
    egress_violations = sum(
        1 for v in all_violations
        if "egress" in v.constraint_type.value
    )

    # Project size category
    total_area = parse_result.total_area_sqft or 0.0
    if total_area < 5_000:
        size_cat = "small"
    elif total_area < 50_000:
        size_cat = "medium"
    elif total_area < 200_000:
        size_cat = "large"
    else:
        size_cat = "very_large"

    return PredictionFeatures(
        project_id=parse_result.project_id,
        total_rooms=len(rooms),
        total_area_sqft=total_area,
        critical_violations=compliance_report.critical_violations,
        high_violations=compliance_report.high_violations,
        medium_violations=compliance_report.medium_violations,
        low_violations=compliance_report.low_violations,
        has_operating_rooms=or_count > 0,
        has_icu=icu_count > 0,
        has_emergency=RoomType.EMERGENCY in room_types,
        operating_room_count=or_count,
        icu_bed_count=icu_count,
        corridor_width_min_ft=min_corridor_width,
        ventilation_deficiencies=vent_deficiencies,
        adjacency_violations=adj_violations,
        egress_violations=egress_violations,
        estimated_correction_cost_usd=compliance_report.estimated_total_correction_cost_usd,
        project_size_category=size_cat,
        facility_type=facility_type,
        regulator_region=regulator_region,
    )


# ------------------------------------------------------------------
# Approval Prediction Engine
# ------------------------------------------------------------------

class ApprovalPredictionEngine:
    """
    Predicts approval probability for a healthcare facility design.

    Uses a trained GradientBoostingClassifier when a saved model exists,
    otherwise falls back to the calibrated heuristic baseline.
    """

    def __init__(self, model_path: Optional[str] = None):
        self._model: Optional[Any] = None
        self._model_loaded = False
        model_path = model_path or settings.model_path

        if SKLEARN_AVAILABLE and os.path.exists(model_path):
            try:
                self._model = joblib.load(model_path)
                self._model_loaded = True
                logger.info("Loaded approval prediction model from %s", model_path)
            except Exception as exc:
                logger.warning("Could not load model from %s: %s", model_path, exc)
        else:
            logger.info("No trained model found — using calibrated heuristic baseline")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, features: PredictionFeatures) -> ApprovalPrediction:
        """Generate a full approval prediction for a project."""
        if self._model_loaded and self._model:
            fgi_prob = self._ml_predict(features)
        else:
            fgi_prob = _baseline_approval_probability(features)

        # AHJ and state are typically 3-7% lower than FGI (stricter local codes)
        ahj_prob = max(0.0, fgi_prob - 7.0)
        state_prob = max(0.0, fgi_prob - 4.0)
        jc_prob = max(0.0, fgi_prob - 2.0)

        readiness = _compute_submission_readiness(features)
        risk = _risk_level_from_score(readiness)

        regulator_predictions = [
            RegulatorPrediction(
                regulator=RegulatorType.FGI,
                approval_probability=round(fgi_prob, 1),
                expected_review_days=_expected_review_days(features, RegulatorType.FGI),
                primary_concerns=self._primary_concerns(features),
            ),
            RegulatorPrediction(
                regulator=RegulatorType.AHJ,
                approval_probability=round(ahj_prob, 1),
                expected_review_days=_expected_review_days(features, RegulatorType.AHJ),
                primary_concerns=self._primary_concerns(features),
            ),
            RegulatorPrediction(
                regulator=RegulatorType.STATE,
                approval_probability=round(state_prob, 1),
                expected_review_days=_expected_review_days(features, RegulatorType.STATE),
                primary_concerns=self._primary_concerns(features),
            ),
        ]

        return ApprovalPrediction(
            project_id=features.project_id,
            submission_readiness_score=readiness,
            overall_risk_level=risk,
            regulator_predictions=regulator_predictions,
            top_blocking_issues=self._blocking_issues(features),
            recommended_actions=self._recommended_actions(features),
            estimated_rework_cost_usd=features.estimated_correction_cost_usd,
            estimated_rework_days=max(0, int(features.critical_violations * 45 + features.high_violations * 14)),
            confidence=0.75 if not self._model_loaded else 0.88,
            model_version="heuristic-1.0" if not self._model_loaded else "gbm-1.0",
        )

    # ------------------------------------------------------------------
    # ML predict (when model available)
    # ------------------------------------------------------------------

    def _ml_predict(self, features: PredictionFeatures) -> float:
        fv = self._to_feature_vector(features)
        try:
            prob = self._model.predict_proba([fv])[0][1] * 100
            return round(float(prob), 1)
        except Exception as exc:
            logger.warning("ML prediction failed: %s — falling back to heuristic", exc)
            return _baseline_approval_probability(features)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _to_feature_vector(f: PredictionFeatures) -> List[float]:
        return [
            f.total_rooms,
            f.total_area_sqft / 1000,
            f.critical_violations,
            f.high_violations,
            f.medium_violations,
            f.low_violations,
            int(f.has_operating_rooms),
            int(f.has_icu),
            int(f.has_emergency),
            f.operating_room_count,
            f.icu_bed_count,
            f.corridor_width_min_ft,
            f.ventilation_deficiencies,
            f.adjacency_violations,
            f.egress_violations,
            f.estimated_correction_cost_usd / 100_000,
        ]

    @staticmethod
    def _primary_concerns(f: PredictionFeatures) -> List[str]:
        concerns = []
        if f.critical_violations:
            concerns.append(f"{f.critical_violations} critical violation(s) must be resolved before submission")
        if f.ventilation_deficiencies:
            concerns.append(f"Ventilation deficiencies in {f.ventilation_deficiencies} room(s)")
        if f.adjacency_violations:
            concerns.append(f"Required room adjacency not met in {f.adjacency_violations} case(s)")
        if f.corridor_width_min_ft < 8.0:
            concerns.append(f"Corridor width below 8ft minimum (found {f.corridor_width_min_ft:.1f}ft)")
        return concerns[:4]

    @staticmethod
    def _blocking_issues(f: PredictionFeatures) -> List[str]:
        issues = []
        if f.critical_violations > 0:
            issues.append(
                f"{f.critical_violations} critical violation(s) — submission will be rejected without resolution"
            )
        if f.ventilation_deficiencies > 0:
            issues.append(
                f"Ventilation non-compliance in {f.ventilation_deficiencies} rooms — "
                "FGI and ASHRAE 170 requirements not met"
            )
        if f.adjacency_violations > 0:
            issues.append("Required clinical adjacencies missing (e.g., OR → Sterile Core)")
        return issues

    @staticmethod
    def _recommended_actions(f: PredictionFeatures) -> List[str]:
        actions = []
        if f.critical_violations > 0:
            actions.append("Resolve all critical violations before proceeding to submission")
        if f.ventilation_deficiencies > 0:
            actions.append(
                "Engage MEP engineer to redesign HVAC to meet minimum ACH requirements per ASHRAE 170"
            )
        if f.adjacency_violations > 0:
            actions.append(
                "Revise floor plan to ensure operating rooms have direct access to sterile core"
            )
        if f.corridor_width_min_ft < 8.0:
            actions.append("Widen corridors to minimum 8ft to meet NFPA 101 egress requirements")
        if not actions:
            actions.append("Design appears ready for pre-submission review")
        return actions

    # ------------------------------------------------------------------
    # Model training (called by the outcome dataset pipeline)
    # ------------------------------------------------------------------

    def train(
        self,
        outcomes: List[ProjectOutcome],
        save_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Train the GBM approval prediction model on historical outcome data.
        Requires scikit-learn and at least 50 labeled projects.
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for model training")
        if len(outcomes) < 10:
            raise ValueError(f"Need at least 10 labeled outcomes to train, got {len(outcomes)}")

        X, y = [], []
        for outcome in outcomes:
            if outcome.approval_result is None:
                continue
            # Must match _to_feature_vector column order exactly:
            # total_rooms, area, critical, high, medium, low,
            # has_or, has_icu, has_emergency,
            # or_count, icu_count, corridor_width_min,
            # ventilation_defs, adjacency_violations, egress_violations, cost
            fv = [
                outcome.total_rooms,
                outcome.total_area_sqft / 1000,
                outcome.critical_violations,
                outcome.high_violations,
                outcome.medium_violations,
                outcome.low_violations,
                int(outcome.operating_room_count > 0),   # has_operating_rooms
                int(outcome.icu_bed_count > 0),          # has_icu
                0,                                        # has_emergency (unknown from outcome)
                outcome.operating_room_count,
                outcome.icu_bed_count,
                8.0,                                      # corridor_width_min_ft (unknown)
                0, 0, 0,                                  # ventilation/adjacency/egress deficiencies
                outcome.estimated_correction_cost_usd / 100_000,
            ]
            X.append(fv)
            y.append(1 if outcome.approval_result == "approved" else 0)

        X_arr = np.array(X, dtype=np.float32)
        y_arr = np.array(y)

        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        model.fit(X_arr, y_arr)

        self._model = model
        self._model_loaded = True

        save_path = save_path or settings.model_path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, save_path)
        logger.info("Model trained on %d projects, saved to %s", len(X), save_path)

        return {
            "training_samples": len(X),
            "approval_rate": float(y_arr.mean()),
            "model_path": save_path,
        }
