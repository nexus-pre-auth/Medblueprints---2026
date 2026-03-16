"""
Blueprint API Routes
Upload blueprints and trigger the full AI pipeline.
"""
import io
import logging
import uuid
from typing import Optional, Annotated

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
import numpy as np
from src.core.limiter import limiter

from src.engines.cv_blueprint_engine import CVBlueprintEngine
from src.engines.facility_graph import FacilityGraphEngine
from src.models.blueprint import BlueprintParseResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/blueprints", tags=["blueprints"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".pdf"}
ALLOWED_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/bmp", "image/tiff",
    "application/pdf",
}


def get_cv_engine() -> CVBlueprintEngine:
    try:
        return CVBlueprintEngine()
    except ImportError:
        return None  # Returns None; routes handle gracefully


def get_graph_engine() -> FacilityGraphEngine:
    return FacilityGraphEngine()


@router.post("/parse", summary="Parse a blueprint image/PDF")
@limiter.limit("10/minute")
async def parse_blueprint(
    request: Request,
    file: UploadFile = File(None),
    project_id: Optional[str] = Form(None),
    use_demo: bool = Form(False),
    facility_type: str = Form("hospital"),
):
    """
    Upload a blueprint image (PNG/JPG/PDF) to extract:
    - Room geometry and types
    - Detected objects (doors, HVAC vents, etc.)
    - Corridors and widths

    Returns a BlueprintParseResult JSON.
    Set `use_demo=true` to get a sample parse result without uploading a file.
    """
    pid = project_id or str(uuid.uuid4())[:12]

    if use_demo:
        result = CVBlueprintEngine.create_demo_parse_result(pid)
        return result.model_dump()

    if not file:
        raise HTTPException(status_code=400, detail="Provide a file or set use_demo=true")

    # Validate file type
    filename_lower = (file.filename or "").lower()
    ext = "." + filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else ""
    content_type = (file.content_type or "").split(";")[0].strip()
    if ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext or content_type}'. Allowed: PNG, JPG, BMP, TIFF, PDF",
        )

    cv_engine = get_cv_engine()
    if cv_engine is None:
        # Fallback to demo if OpenCV not available
        logger.warning("OpenCV not available — returning demo parse result")
        result = CVBlueprintEngine.create_demo_parse_result(pid)
        return result.model_dump()

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // (1024*1024)} MB). Maximum allowed: 50 MB",
        )

    try:
        arr = np.frombuffer(content, dtype=np.uint8)
        import cv2
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=422, detail="Could not decode image. Supported formats: PNG, JPG, BMP")

        result = cv_engine.parse_image(
            image_array=img,
            project_id=pid,
            filename=file.filename or "blueprint.png",
        )
        return result.model_dump()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Blueprint parsing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Blueprint parsing error: {str(exc)}")


@router.post("/facility-graph", summary="Build digital facility graph from parse result")
async def build_facility_graph(
    parse_result: BlueprintParseResult,
):
    """
    Convert a BlueprintParseResult into a Digital Facility Graph.
    Returns nodes (rooms, systems) and edges (adjacencies, ventilation, etc.).
    """
    engine = get_graph_engine()
    graph = engine.build(parse_result)

    # Include missing adjacency analysis
    missing = engine.find_missing_required_adjacencies(graph, parse_result)
    missing_serializable = [
        {"required_room_type": a.value, "must_be_adjacent_to": b.value}
        for a, b in missing
    ]

    return {
        "project_id": graph.project_id,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "nodes": [n.model_dump() for n in graph.nodes],
        "edges": [e.model_dump() for e in graph.edges],
        "missing_required_adjacencies": missing_serializable,
    }
