"""
Prediction API Routes
Pre-submission approval simulator and outcome tracking.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body

from src.engines.approval_prediction import ApprovalPredictionEngine, extract_features
from src.models.blueprint import BlueprintParseResult
from src.models.compliance import ComplianceReport
from src.models.prediction import ApprovalPrediction, PredictionFeatures, ProjectOutcome
from src.storage.outcome_dataset import OutcomeDataset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])

_prediction_engine = ApprovalPredictionEngine()
_outcome_dataset: Optional[OutcomeDataset] = None


def get_outcome_dataset() -> OutcomeDataset:
    global _outcome_dataset
    if _outcome_dataset is None:
        _outcome_dataset = OutcomeDataset()
    return _outcome_dataset


# -----------------------------------------------------------------------
# Pre-submission Approval Simulator
# -----------------------------------------------------------------------

class FullAnalysisRequest:
    """Combined blueprint + compliance for prediction."""
    pass


from pydantic import BaseModel


class PredictionRequest(BaseModel):
    parse_result: BlueprintParseResult
    compliance_report: ComplianceReport
    facility_type: str = "hospital"
    regulator_region: str = "national"


@router.post("/simulate", summary="Pre-Submission Approval Simulator")
async def simulate_approval(request: PredictionRequest):
    """
    The flagship feature: upload a parsed blueprint + compliance report
    and receive:
    - Submission readiness score (0-100)
    - Approval probability per regulator (FGI, AHJ, State)
    - Expected review duration
    - Top blocking issues
    - Recommended actions
    - Estimated rework cost and timeline

    This is the feature that prevents million-dollar redesign mistakes.
    """
    try:
        features = extract_features(
            request.parse_result,
            request.compliance_report,
            facility_type=request.facility_type,
            regulator_region=request.regulator_region,
        )
        prediction = _prediction_engine.predict(features)

        # Auto-record this project to the outcome dataset (without approval result yet)
        dataset = get_outcome_dataset()
        await dataset.init()
        outcome = ProjectOutcome(
            project_id=request.parse_result.project_id,
            facility_type=request.facility_type,
            total_rooms=features.total_rooms,
            total_area_sqft=features.total_area_sqft,
            critical_violations=features.critical_violations,
            high_violations=features.high_violations,
            medium_violations=features.medium_violations,
            low_violations=features.low_violations,
            operating_room_count=features.operating_room_count,
            icu_bed_count=features.icu_bed_count,
            estimated_correction_cost_usd=features.estimated_correction_cost_usd,
        )
        await dataset.save_outcome(outcome)

        return prediction.model_dump()

    except Exception as exc:
        logger.error("Approval simulation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(exc)}")


@router.post("/features", summary="Extract prediction features from blueprint + compliance")
async def extract_prediction_features(request: PredictionRequest):
    """Extract and inspect the feature vector used by the approval prediction model."""
    features = extract_features(
        request.parse_result,
        request.compliance_report,
        facility_type=request.facility_type,
        regulator_region=request.regulator_region,
    )
    return features.model_dump()


# -----------------------------------------------------------------------
# Outcome Tracking (The Moat)
# -----------------------------------------------------------------------

class OutcomeUpdateRequest(BaseModel):
    project_id: str
    approval_result: str  # "approved" | "rejected" | "conditional"
    regulator: Optional[str] = None
    review_duration_days: Optional[int] = None
    actual_rework_cost_usd: Optional[float] = None
    rework_changes: Optional[list[str]] = None


@router.post("/outcomes/record", summary="Record regulatory approval outcome")
async def record_outcome(request: OutcomeUpdateRequest):
    """
    Record the actual regulatory decision for a submitted project.
    This data trains the approval prediction model and builds the moat.
    """
    if request.approval_result not in ("approved", "rejected", "conditional"):
        raise HTTPException(
            status_code=400,
            detail="approval_result must be 'approved', 'rejected', or 'conditional'"
        )

    dataset = get_outcome_dataset()
    await dataset.init()
    await dataset.update_approval_result(
        project_id=request.project_id,
        approval_result=request.approval_result,
        regulator=request.regulator,
        review_duration_days=request.review_duration_days,
        actual_rework_cost_usd=request.actual_rework_cost_usd,
        rework_changes=request.rework_changes,
    )
    return {"status": "recorded", "project_id": request.project_id}


@router.get("/outcomes/stats", summary="Outcome dataset statistics")
async def outcome_stats():
    """
    Show dataset size, approval rate, and model training readiness.
    Tracks the growth of the strategic moat.
    """
    dataset = get_outcome_dataset()
    await dataset.init()
    return await dataset.get_dataset_stats()


@router.get("/outcomes/intelligence", summary="Design intelligence query")
async def design_intelligence(
    facility_type: Optional[str] = Query(None),
):
    """
    Query the outcome dataset for design intelligence.
    Example: "What is the approval rate for hospital projects?"
    """
    dataset = get_outcome_dataset()
    await dataset.init()
    return await dataset.design_intelligence_query(facility_type=facility_type)


@router.post("/model/train", summary="Retrain approval prediction model")
async def retrain_model():
    """
    Retrain the GBM approval prediction model on all labeled outcomes.
    Requires at least 50 labeled projects (see /outcomes/stats for readiness).
    """
    dataset = get_outcome_dataset()
    await dataset.init()
    labeled = await dataset.load_labeled()

    if len(labeled) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 10 labeled outcomes to train. Currently have {len(labeled)}."
        )

    try:
        result = _prediction_engine.train(labeled)
        return {"status": "trained", **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(exc)}")
