"""
AR Visualization API Routes
Generate AR overlays and compliance floor plan maps.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src.engines.ar_visualization import ARVisualizationEngine
from src.models.blueprint import BlueprintParseResult
from src.models.compliance import ComplianceReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/visualization", tags=["visualization"])

_ar_engine = ARVisualizationEngine()


class VisualizationRequest(BaseModel):
    parse_result: BlueprintParseResult
    compliance_report: ComplianceReport


@router.post("/webxr", summary="Generate WebXR/WebAR compliance overlay")
async def generate_webxr(request: VisualizationRequest):
    """
    Generate a WebXR scene descriptor for browser-based AR visualization.
    Compatible with Three.js, A-Frame, and WebXR-capable browsers.

    Room colors:
    - Red = critical violations
    - Orange = high violations
    - Yellow = medium violations
    - Blue = low/advisory
    - Green = fully compliant
    """
    try:
        scene = _ar_engine.to_webxr_json(request.parse_result, request.compliance_report)
        return scene
    except Exception as exc:
        logger.error("WebXR generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/vision-pro", summary="Generate Apple Vision Pro scene descriptor")
async def generate_vision_pro(request: VisualizationRequest):
    """
    Generate a visionOS / RealityKit scene descriptor for Apple Vision Pro.
    Returns 3D room volumes with compliance color coding and floating labels.
    """
    try:
        scene = _ar_engine.to_vision_pro(request.parse_result, request.compliance_report)
        return scene
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/svg", summary="Generate SVG compliance floor plan")
async def generate_svg(request: VisualizationRequest):
    """
    Generate an SVG compliance heatmap floor plan.
    Universal fallback that works on any device or browser.
    Returns SVG as text/svg+xml.
    """
    try:
        svg = _ar_engine.to_svg(request.parse_result, request.compliance_report)
        return Response(content=svg, media_type="image/svg+xml")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
