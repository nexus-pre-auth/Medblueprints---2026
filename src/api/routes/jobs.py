"""
Jobs API — Async Blueprint Analysis
=====================================
Architects upload a blueprint → get a job_id → poll for results.

POST /api/v1/jobs/analyze        Upload file + start analysis
GET  /api/v1/jobs/{job_id}       Poll status and progress
GET  /api/v1/jobs/{job_id}/result Get full analysis result
GET  /api/v1/jobs                List recent jobs
"""
import asyncio
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks

from src.storage.job_store import JobStore, JobStatus
from src.engines.blueprint_ingestion import BlueprintIngestionPipeline
from src.engines.pipeline import MedBlueprintsPipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Shared singletons
_job_store = JobStore()
_ingestion_pipeline = BlueprintIngestionPipeline()
_analysis_pipeline: Optional[MedBlueprintsPipeline] = None


def get_analysis_pipeline() -> MedBlueprintsPipeline:
    global _analysis_pipeline
    if _analysis_pipeline is None:
        _analysis_pipeline = MedBlueprintsPipeline(enable_llm=True, enable_ar=True)
    return _analysis_pipeline


async def _run_analysis(
    job_id: str,
    file_bytes: bytes,
    filename: str,
    facility_type: str,
    project_id: str,
) -> None:
    """
    Background task: runs the full MedBlueprints pipeline.
    Progress is reported to the job store so the frontend can poll.
    """
    store = _job_store

    try:
        await store.update_status(job_id, JobStatus.PROCESSING, stage="ingestion", progress_pct=5)

        # Layer 0: File ingestion + OCR
        ingestion = _ingestion_pipeline.ingest(file_bytes, filename, project_id)
        await store.update_status(job_id, JobStatus.PROCESSING, stage="cv_parsing", progress_pct=20)

        # Layer 1-6: Full AI pipeline
        pipeline = get_analysis_pipeline()

        if ingestion.primary_image() is not None:
            import numpy as np
            from src.engines.cv_blueprint_engine import CVBlueprintEngine
            cv_engine = CVBlueprintEngine()
            parse_result = cv_engine.parse_image(
                image_array=ingestion.primary_image(),
                project_id=project_id,
                filename=filename,
                room_labels=ingestion.primary_labels(),
            )
        else:
            # Fallback to demo parse if image extraction failed
            from src.engines.cv_blueprint_engine import CVBlueprintEngine
            parse_result = CVBlueprintEngine.create_demo_parse_result(project_id)

        await store.update_status(job_id, JobStatus.PROCESSING, stage="facility_graph", progress_pct=40)

        from src.engines.facility_graph import FacilityGraphEngine
        graph_engine = FacilityGraphEngine()
        facility_graph = graph_engine.build(parse_result)

        adjacencies = {}
        for room in parse_result.rooms:
            neighbor_ids = graph_engine.get_adjacent_rooms(facility_graph, room.id)
            adjacencies[room.id] = [
                r.room_type.value
                for nid in neighbor_ids
                if (r := parse_result.room_by_id(nid)) is not None
            ]

        await store.update_status(job_id, JobStatus.PROCESSING, stage="compliance_analysis", progress_pct=60)

        from src.engines.llm_compliance_engine import LLMComplianceEngine
        from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
        kg = RegulatoryKnowledgeGraph()
        compliance_engine = LLMComplianceEngine(knowledge_graph=kg)
        compliance_report = compliance_engine.generate_report(parse_result, adjacencies)

        await store.update_status(job_id, JobStatus.PROCESSING, stage="approval_prediction", progress_pct=80)

        from src.engines.approval_prediction import ApprovalPredictionEngine, extract_features
        features = extract_features(parse_result, compliance_report, facility_type)
        prediction = ApprovalPredictionEngine().predict(features)

        await store.update_status(job_id, JobStatus.PROCESSING, stage="ar_visualization", progress_pct=90)

        from src.engines.ar_visualization import ARVisualizationEngine
        ar_engine = ARVisualizationEngine()
        ar_scene = ar_engine.to_webxr_json(parse_result, compliance_report)

        # Store full result
        result = {
            "project_id": project_id,
            "parse_result": parse_result.model_dump(),
            "facility_graph": {
                "node_count": len(facility_graph.nodes),
                "edge_count": len(facility_graph.edges),
            },
            "compliance_report": compliance_report.model_dump(),
            "prediction": prediction.model_dump(),
            "ar_scene": ar_scene,
            "ingestion_warnings": ingestion.warnings,
        }
        await store.save_result(job_id, result)
        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
        await store.update_status(
            job_id, JobStatus.FAILED,
            stage="error",
            error=str(exc),
        )


@router.on_event("startup")
async def startup():
    await _job_store.init()


@router.post("/analyze", summary="Upload blueprint and start async analysis")
async def submit_blueprint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    facility_type: str = Form("hospital"),
    project_id: Optional[str] = Form(None),
    use_demo: bool = Form(False),
):
    """
    **The main workflow endpoint.**

    Upload a blueprint file (PNG/JPG/PDF/DXF) and receive a job_id.
    The full AI pipeline runs asynchronously in the background.

    Poll `GET /api/v1/jobs/{job_id}` to check status and progress.
    When status = "completed", fetch results from `GET /api/v1/jobs/{job_id}/result`.

    Supported file formats: PNG, JPG, BMP, TIFF, PDF, DXF
    """
    pid = project_id or str(uuid.uuid4())[:12]

    if use_demo:
        # Demo mode: use synthetic data, no file needed
        filename = "demo_hospital.png"
        file_bytes = b""
    elif file:
        filename = file.filename or "blueprint.png"
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
    else:
        raise HTTPException(status_code=400, detail="Provide a file or set use_demo=true")

    job_id = await _job_store.create_job(filename, facility_type, pid)

    if use_demo:
        # Run a faster demo pipeline path
        background_tasks.add_task(_run_demo_analysis, job_id, pid, facility_type)
    else:
        background_tasks.add_task(_run_analysis, job_id, file_bytes, filename, facility_type, pid)

    return {
        "job_id": job_id,
        "project_id": pid,
        "status": "pending",
        "message": "Analysis started. Poll /api/v1/jobs/{job_id} for progress.",
        "poll_url": f"/api/v1/jobs/{job_id}",
        "result_url": f"/api/v1/jobs/{job_id}/result",
    }


async def _run_demo_analysis(job_id: str, project_id: str, facility_type: str) -> None:
    """Fast demo pipeline (no file I/O, no LLM calls)."""
    store = _job_store
    try:
        from src.engines.cv_blueprint_engine import CVBlueprintEngine
        from src.engines.facility_graph import FacilityGraphEngine
        from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
        from src.engines.llm_compliance_engine import LLMComplianceEngine
        from src.engines.approval_prediction import ApprovalPredictionEngine, extract_features
        from src.engines.ar_visualization import ARVisualizationEngine
        from src.models.compliance import ComplianceReport, RoomComplianceResult

        await store.update_status(job_id, JobStatus.PROCESSING, stage="cv_parsing", progress_pct=20)
        parse_result = CVBlueprintEngine.create_demo_parse_result(project_id)

        await store.update_status(job_id, JobStatus.PROCESSING, stage="facility_graph", progress_pct=40)
        graph_engine = FacilityGraphEngine()
        facility_graph = graph_engine.build(parse_result)

        await store.update_status(job_id, JobStatus.PROCESSING, stage="compliance_analysis", progress_pct=60)
        # Lightweight compliance without LLM for demo speed
        report = ComplianceReport(project_id=project_id)
        for room in parse_result.rooms:
            report.room_results.append(RoomComplianceResult(
                room_id=room.id,
                room_label=room.label,
                room_type=room.room_type.value,
            ))
        report.compute_totals()

        await store.update_status(job_id, JobStatus.PROCESSING, stage="approval_prediction", progress_pct=80)
        features = extract_features(parse_result, report, facility_type)
        prediction = ApprovalPredictionEngine().predict(features)

        await store.update_status(job_id, JobStatus.PROCESSING, stage="ar_visualization", progress_pct=90)
        ar_scene = ARVisualizationEngine().to_webxr_json(parse_result, report)

        result = {
            "project_id": project_id,
            "parse_result": parse_result.model_dump(),
            "facility_graph": {"node_count": len(facility_graph.nodes), "edge_count": len(facility_graph.edges)},
            "compliance_report": report.model_dump(),
            "prediction": prediction.model_dump(),
            "ar_scene": ar_scene,
            "ingestion_warnings": [],
            "demo_mode": True,
        }
        await store.save_result(job_id, result)

    except Exception as exc:
        logger.error("Demo job %s failed: %s", job_id, exc, exc_info=True)
        await store.update_status(job_id, JobStatus.FAILED, error=str(exc))


@router.get("/{job_id}", summary="Poll job status and progress")
async def get_job_status(job_id: str):
    """
    Poll the status of an analysis job.

    Response includes:
    - `status`: pending | processing | completed | failed
    - `stage`: which pipeline stage is currently running
    - `progress_pct`: 0–100 completion percentage
    """
    job = await _job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("/{job_id}/result", summary="Get full analysis result")
async def get_job_result(job_id: str):
    """
    Get the complete analysis result for a completed job.

    Includes:
    - `parse_result`: detected rooms, objects, corridors
    - `compliance_report`: all violations with severity and cost estimates
    - `prediction`: approval probabilities and readiness score
    - `ar_scene`: WebXR scene for AR visualization
    """
    job = await _job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    if job["status"] == "failed":
        raise HTTPException(status_code=422, detail=f"Job failed: {job.get('error')}")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Job not yet complete. Status: {job['status']}, progress: {job['progress_pct']:.0f}%",
        )

    result = await _job_store.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found for completed job")

    return result


@router.get("", summary="List recent jobs")
async def list_jobs(limit: int = 20):
    """List the most recent analysis jobs."""
    jobs = await _job_store.list_jobs(limit=limit)
    return {"jobs": jobs, "count": len(jobs)}
