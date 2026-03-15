"""
MedBlueprints Full AI Pipeline
================================
Orchestrates all five intelligence layers in sequence for a single project.

Usage:
    pipeline = MedBlueprintsPipeline()
    result = pipeline.run(image_path="hospital_floor.png", project_id="HOSP_001")
    print(result.prediction.submission_readiness_score)
"""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from src.engines.cv_blueprint_engine import CVBlueprintEngine
from src.engines.facility_graph import FacilityGraphEngine
from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
from src.engines.llm_compliance_engine import LLMComplianceEngine
from src.engines.approval_prediction import ApprovalPredictionEngine, extract_features
from src.engines.ar_visualization import ARVisualizationEngine
from src.models.blueprint import BlueprintParseResult
from src.models.facility import FacilityGraph
from src.models.compliance import ComplianceReport
from src.models.prediction import ApprovalPrediction, ProjectOutcome

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete output of the MedBlueprints AI pipeline."""
    project_id: str
    parse_result: BlueprintParseResult
    facility_graph: FacilityGraph
    compliance_report: ComplianceReport
    prediction: ApprovalPrediction
    ar_webxr_scene: Optional[Dict[str, Any]] = None
    ar_svg_path: Optional[str] = None
    errors: list = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "rooms_detected": len(self.parse_result.rooms),
            "total_area_sqft": self.parse_result.total_area_sqft,
            "critical_violations": self.compliance_report.critical_violations,
            "high_violations": self.compliance_report.high_violations,
            "submission_readiness": self.prediction.submission_readiness_score,
            "fgi_approval_probability": next(
                (p.approval_probability for p in self.prediction.regulator_predictions
                 if p.regulator.value == "FGI"), None
            ),
            "ahj_approval_probability": next(
                (p.approval_probability for p in self.prediction.regulator_predictions
                 if p.regulator.value == "AHJ"), None
            ),
            "estimated_rework_cost_usd": self.prediction.estimated_rework_cost_usd,
            "estimated_rework_days": self.prediction.estimated_rework_days,
            "overall_risk": self.prediction.overall_risk_level.value,
            "top_blocking_issues": self.prediction.top_blocking_issues,
            "recommended_actions": self.prediction.recommended_actions,
            "compliance_summary": self.compliance_report.summary,
        }


class MedBlueprintsPipeline:
    """
    Single entry point for the full MedBlueprints AI stack.

    Layers executed in order:
      1. CV Blueprint Engine     → BlueprintParseResult
      2. Facility Graph Engine   → FacilityGraph
      3. Regulatory Knowledge Graph (loaded once, shared)
      4. LLM Compliance Engine   → ComplianceReport
      5. Approval Prediction     → ApprovalPrediction
      6. AR Visualization        → WebXR JSON + SVG

    The pipeline also records each project in the Outcome Dataset.
    """

    def __init__(
        self,
        enable_ar: bool = True,
        enable_llm: bool = True,
    ):
        self._kg = RegulatoryKnowledgeGraph()
        self._graph_engine = FacilityGraphEngine()
        self._prediction_engine = ApprovalPredictionEngine()
        self._ar_engine = ARVisualizationEngine() if enable_ar else None
        self._compliance_engine = (
            LLMComplianceEngine(knowledge_graph=self._kg) if enable_llm else None
        )
        logger.info(
            "MedBlueprintsPipeline ready (LLM=%s, AR=%s)",
            enable_llm,
            enable_ar,
        )

    def run(
        self,
        image_path: Optional[str] = None,
        project_id: Optional[str] = None,
        use_demo: bool = False,
        facility_type: str = "hospital",
        regulator_region: str = "national",
    ) -> PipelineResult:
        """
        Run the complete pipeline.

        Args:
            image_path: path to blueprint image (PNG/JPG/BMP)
            project_id: optional project identifier
            use_demo: if True, use synthetic demo data instead of real image
            facility_type: type of facility (hospital, clinic, etc.)
            regulator_region: regulatory region for prediction context
        """
        pid = project_id or str(uuid.uuid4())[:12]
        errors = []

        # ── Layer 1: Computer Vision Blueprint Engine ─────────────────
        logger.info("[%s] Layer 1: CV Blueprint Engine", pid)
        try:
            if use_demo or not image_path:
                parse_result = CVBlueprintEngine.create_demo_parse_result(pid)
            else:
                cv_engine = CVBlueprintEngine()
                parse_result = cv_engine.parse_image(image_path=image_path, project_id=pid)
        except Exception as exc:
            logger.error("CV engine failed: %s — using demo", exc)
            parse_result = CVBlueprintEngine.create_demo_parse_result(pid)
            errors.append(f"CV engine fallback: {exc}")

        # ── Layer 2: Digital Facility Graph ───────────────────────────
        logger.info("[%s] Layer 2: Digital Facility Graph", pid)
        facility_graph = self._graph_engine.build(parse_result)

        # Build adjacency map for compliance engine
        adjacencies: Dict[str, list] = {}
        for room in parse_result.rooms:
            neighbor_ids = self._graph_engine.get_adjacent_rooms(facility_graph, room.id)
            adjacencies[room.id] = [
                r.room_type.value
                for nid in neighbor_ids
                if (r := parse_result.room_by_id(nid)) is not None
            ]

        # ── Layer 3 + 4: Knowledge Graph + LLM Compliance Engine ─────
        logger.info("[%s] Layer 4: LLM Compliance Engine", pid)
        try:
            if self._compliance_engine:
                report = self._compliance_engine.generate_report(parse_result, adjacencies)
            else:
                # Lightweight compliance without LLM
                from src.models.compliance import ComplianceReport, RoomComplianceResult
                report = ComplianceReport(
                    project_id=pid,
                    room_results=[
                        RoomComplianceResult(
                            room_id=r.id,
                            room_label=r.label,
                            room_type=r.room_type.value,
                        )
                        for r in parse_result.rooms
                    ],
                )
                report.compute_totals()
        except Exception as exc:
            logger.error("Compliance engine failed: %s", exc)
            errors.append(f"Compliance engine error: {exc}")
            from src.models.compliance import ComplianceReport
            report = ComplianceReport(project_id=pid)

        # ── Layer 5: Approval Prediction Model ───────────────────────
        logger.info("[%s] Layer 5: Approval Prediction", pid)
        features = extract_features(parse_result, report, facility_type, regulator_region)
        prediction = self._prediction_engine.predict(features)

        # ── Layer 6: AR Visualization ─────────────────────────────────
        ar_scene = None
        ar_svg_path = None
        if self._ar_engine:
            logger.info("[%s] Layer 6: AR Visualization", pid)
            try:
                ar_scene = self._ar_engine.to_webxr_json(parse_result, report)
                ar_svg_path = self._ar_engine.save_svg(parse_result, report)
            except Exception as exc:
                logger.warning("AR visualization failed: %s", exc)
                errors.append(f"AR visualization: {exc}")

        logger.info(
            "[%s] Pipeline complete — readiness: %.1f, critical violations: %d",
            pid,
            prediction.submission_readiness_score,
            report.critical_violations,
        )

        return PipelineResult(
            project_id=pid,
            parse_result=parse_result,
            facility_graph=facility_graph,
            compliance_report=report,
            prediction=prediction,
            ar_webxr_scene=ar_scene,
            ar_svg_path=ar_svg_path,
            errors=errors,
        )
