"""
AR Visualization Engine
========================
Generates spatial compliance overlays for augmented reality viewers.

Supported output formats:
  - WebXR / WebAR JSON  (browser-based AR, tablets, phones)
  - Apple Vision Pro scene descriptor (visionOS / RealityKit)
  - 2D SVG floor plan with violation heatmap (fallback for any device)
  - Plotly 3D figure (development / preview)

Each room is color-coded by its worst violation severity:
  RED    = critical
  ORANGE = high
  YELLOW = medium
  BLUE   = low / passing
  GREEN  = fully compliant
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from src.core.config import settings
from src.models.blueprint import BlueprintParseResult, DetectedRoom
from src.models.compliance import (
    ComplianceReport,
    ComplianceViolation,
    ViolationSeverity,
    RoomComplianceResult,
)

logger = logging.getLogger(__name__)

# Color map: severity → RGBA hex
SEVERITY_COLORS = {
    "critical":  "#FF2D2D",   # red
    "high":      "#FF8C00",   # orange
    "medium":    "#FFD700",   # yellow
    "low":       "#4FC3F7",   # light blue
    "compliant": "#2ECC71",   # green
}

SEVERITY_OPACITY = {
    "critical": 0.85,
    "high": 0.70,
    "medium": 0.55,
    "low": 0.40,
    "compliant": 0.25,
}


def _worst_severity(violations: List[ComplianceViolation]) -> str:
    order = [
        ViolationSeverity.CRITICAL,
        ViolationSeverity.HIGH,
        ViolationSeverity.MEDIUM,
        ViolationSeverity.LOW,
    ]
    for sev in order:
        if any(v.severity == sev for v in violations):
            return sev.value
    return "compliant"


def _room_annotation(
    room: DetectedRoom,
    result: RoomComplianceResult,
) -> Dict[str, Any]:
    """Build a room annotation object for AR overlay."""
    worst = _worst_severity(result.violations)
    total_cost = sum(v.estimated_correction_cost_usd or 0 for v in result.violations)
    cx, cy = room.polygon.centroid

    violations_summary = []
    for v in result.violations[:3]:  # top 3 for display
        violations_summary.append({
            "severity": v.severity.value,
            "constraint": v.constraint_type.value,
            "description": v.description[:80] + "..." if len(v.description) > 80 else v.description,
            "actual": v.actual_value,
            "required": v.required_value,
            "unit": v.unit,
            "cost_usd": v.estimated_correction_cost_usd,
        })

    return {
        "room_id": room.id,
        "label": room.label,
        "room_type": room.room_type.value,
        "centroid": {"x": round(cx, 2), "y": round(cy, 2)},
        "polygon": room.polygon.points,
        "area_sqft": room.area_sqft,
        "floor": room.floor,
        "compliance_status": worst,
        "color": SEVERITY_COLORS.get(worst, SEVERITY_COLORS["compliant"]),
        "opacity": SEVERITY_OPACITY.get(worst, 0.25),
        "violation_count": len(result.violations),
        "violations": violations_summary,
        "total_correction_cost_usd": round(total_cost, 0),
        "llm_summary": result.llm_interpretation,
    }


class ARVisualizationEngine:
    """
    Generates AR-ready output from compliance analysis results.

    Three export methods:
      to_webxr_json    → JSON consumed by a WebXR/A-Frame frontend
      to_vision_pro    → JSON scene descriptor for Apple Vision Pro / RealityKit
      to_svg           → SVG floor plan with compliance heat map
    """

    def __init__(self, output_dir: Optional[str] = None):
        self._output_dir = Path(output_dir or settings.ar_output_path)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # WebXR / WebAR JSON
    # ------------------------------------------------------------------

    def to_webxr_json(
        self,
        parse_result: BlueprintParseResult,
        report: ComplianceReport,
    ) -> Dict[str, Any]:
        """
        Produce a WebXR scene descriptor.

        Compatible with Three.js / A-Frame AR viewers.
        Each room becomes a transparent 3D volume with a compliance overlay.
        """
        result_by_room: Dict[str, RoomComplianceResult] = {
            r.room_id: r for r in report.room_results
        }

        rooms_ar = []
        for room in parse_result.rooms:
            result = result_by_room.get(room.id)
            if result is None:
                # No compliance data → treat as compliant
                result = RoomComplianceResult(
                    room_id=room.id,
                    room_label=room.label,
                    room_type=room.room_type.value,
                )
            rooms_ar.append(_room_annotation(room, result))

        corridor_annotations = []
        for corridor in parse_result.corridors:
            cx, cy = corridor.polygon.centroid
            width_ok = (corridor.width_ft or 8.0) >= 8.0
            corridor_annotations.append({
                "corridor_id": corridor.id,
                "centroid": {"x": round(cx, 2), "y": round(cy, 2)},
                "polygon": corridor.polygon.points,
                "width_ft": corridor.width_ft,
                "compliant": width_ok,
                "color": SEVERITY_COLORS["compliant"] if width_ok else SEVERITY_COLORS["critical"],
                "opacity": 0.3,
            })

        scene = {
            "schema_version": "medblueprints-ar-v1",
            "project_id": parse_result.project_id,
            "canvas": {
                "width_px": parse_result.image_width,
                "height_px": parse_result.image_height,
                "scale_ft_per_px": parse_result.scale_ft_per_pixel,
                "floors": parse_result.floors,
            },
            "summary": {
                "total_rooms": len(parse_result.rooms),
                "critical_violations": report.critical_violations,
                "high_violations": report.high_violations,
                "medium_violations": report.medium_violations,
                "low_violations": report.low_violations,
                "submission_ready": report.overall_compliant,
                "estimated_correction_cost_usd": report.estimated_total_correction_cost_usd,
            },
            "legend": {
                "critical": {"color": SEVERITY_COLORS["critical"], "label": "Critical Violation"},
                "high": {"color": SEVERITY_COLORS["high"], "label": "High Violation"},
                "medium": {"color": SEVERITY_COLORS["medium"], "label": "Medium Violation"},
                "low": {"color": SEVERITY_COLORS["low"], "label": "Low / Advisory"},
                "compliant": {"color": SEVERITY_COLORS["compliant"], "label": "Compliant"},
            },
            "rooms": rooms_ar,
            "corridors": corridor_annotations,
        }
        return scene

    # ------------------------------------------------------------------
    # Apple Vision Pro
    # ------------------------------------------------------------------

    def to_vision_pro(
        self,
        parse_result: BlueprintParseResult,
        report: ComplianceReport,
    ) -> Dict[str, Any]:
        """
        Produce a visionOS / RealityKit scene descriptor.
        Rooms become 3D mesh volumes with shader-based compliance coloring.
        """
        webxr = self.to_webxr_json(parse_result, report)

        entities = []
        for room in webxr["rooms"]:
            pts = room["polygon"]
            # Extrude to 3D: room height 9ft (standard hospital)
            floor_height = (room.get("floor", 1) - 1) * 10.0  # 10ft per floor
            entities.append({
                "entity_type": "RoomVolume",
                "id": room["room_id"],
                "label": room["label"],
                "floor_polygon_2d": pts,
                "extrusion_height_ft": 9.0,
                "base_elevation_ft": floor_height,
                "material": {
                    "type": "PhysicallyBased",
                    "base_color": room["color"],
                    "opacity": room["opacity"],
                    "metallic": 0.0,
                    "roughness": 0.8,
                },
                "annotations": [
                    {
                        "type": "floating_label",
                        "position": {"x": room["centroid"]["x"], "y": 8.5, "z": room["centroid"]["y"]},
                        "text": room["label"],
                        "sub_text": f"{room['violation_count']} violation(s)" if room["violation_count"] else "Compliant",
                        "color": room["color"],
                    }
                ],
                "violations": room["violations"],
            })

        return {
            "schema_version": "medblueprints-visionpro-v1",
            "project_id": parse_result.project_id,
            "coordinate_system": "RealityKit",
            "units": "feet",
            "scene_summary": webxr["summary"],
            "entities": entities,
        }

    # ------------------------------------------------------------------
    # SVG floor plan (universal fallback)
    # ------------------------------------------------------------------

    def to_svg(
        self,
        parse_result: BlueprintParseResult,
        report: ComplianceReport,
        scale: float = 4.0,
    ) -> str:
        """
        Generate an SVG compliance heatmap floor plan.
        scale: pixels per unit (default 4x for readability)
        """
        W = parse_result.image_width * scale
        H = parse_result.image_height * scale

        result_by_room: Dict[str, RoomComplianceResult] = {
            r.room_id: r for r in report.room_results
        }

        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" style="background:#1a1a2e;">',
            # Background grid
            '<defs>',
            '  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">',
            '    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#2a2a4a" stroke-width="0.5"/>',
            '  </pattern>',
            '</defs>',
            f'<rect width="{W}" height="{H}" fill="url(#grid)"/>',
        ]

        # Draw rooms
        for room in parse_result.rooms:
            result = result_by_room.get(room.id)
            worst = _worst_severity(result.violations) if result else "compliant"
            color = SEVERITY_COLORS[worst]
            opacity = SEVERITY_OPACITY[worst]

            pts_str = " ".join(f"{x * scale},{y * scale}" for x, y in room.polygon.points)
            cx, cy = room.polygon.centroid
            cx_s, cy_s = cx * scale, cy * scale

            total_cost = sum(
                v.estimated_correction_cost_usd or 0
                for v in (result.violations if result else [])
            )
            tooltip_lines = [
                f"{room.label}",
                f"Type: {room.room_type.value}",
                f"Area: {room.area_sqft:.0f} sqft" if room.area_sqft else "",
                f"Violations: {len(result.violations) if result else 0}",
                f"Est. Cost: ${total_cost:,.0f}" if total_cost else "",
            ]
            tooltip = "&#xa;".join(l for l in tooltip_lines if l)

            svg_parts.append(
                f'<polygon points="{pts_str}" '
                f'fill="{color}" fill-opacity="{opacity}" '
                f'stroke="{color}" stroke-width="2" stroke-opacity="0.9">'
                f'<title>{tooltip}</title>'
                f'</polygon>'
            )

            # Room label
            font_size = min(12, max(6, (room.area_sqft or 100) / 50))
            svg_parts.append(
                f'<text x="{cx_s}" y="{cy_s}" '
                f'text-anchor="middle" dominant-baseline="middle" '
                f'font-family="Arial, sans-serif" font-size="{font_size}" '
                f'fill="white" fill-opacity="0.9">'
                f'{room.label}</text>'
            )

            # Violation count badge
            if result and result.violations:
                badge_r = 8
                badge_x = cx_s + 20
                badge_y = cy_s - 20
                svg_parts.extend([
                    f'<circle cx="{badge_x}" cy="{badge_y}" r="{badge_r}" fill="{color}" fill-opacity="0.9"/>',
                    f'<text x="{badge_x}" y="{badge_y}" text-anchor="middle" dominant-baseline="middle" '
                    f'font-size="8" fill="white">{len(result.violations)}</text>',
                ])

        # Draw corridors
        for corridor in parse_result.corridors:
            pts_str = " ".join(f"{x * scale},{y * scale}" for x, y in corridor.polygon.points)
            width_ok = (corridor.width_ft or 8.0) >= 8.0
            cor_color = SEVERITY_COLORS["compliant"] if width_ok else SEVERITY_COLORS["critical"]
            svg_parts.append(
                f'<polygon points="{pts_str}" fill="{cor_color}" fill-opacity="0.15" '
                f'stroke="{cor_color}" stroke-width="1" stroke-opacity="0.5"/>'
            )

        # Legend
        legend_items = [
            ("critical", "Critical"),
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low/Advisory"),
            ("compliant", "Compliant"),
        ]
        lx, ly = 10, H - 120
        svg_parts.append(f'<rect x="{lx-5}" y="{ly-15}" width="150" height="110" fill="black" fill-opacity="0.6" rx="4"/>')
        for i, (sev, label) in enumerate(legend_items):
            color = SEVERITY_COLORS[sev]
            y_pos = ly + i * 18
            svg_parts.extend([
                f'<rect x="{lx}" y="{y_pos}" width="12" height="12" fill="{color}" rx="2"/>',
                f'<text x="{lx+16}" y="{y_pos+10}" font-family="Arial" font-size="10" fill="white">{label}</text>',
            ])

        # Title
        svg_parts.append(
            f'<text x="10" y="20" font-family="Arial" font-size="14" font-weight="bold" fill="white">'
            f'MedBlueprints Compliance Map — {parse_result.project_id}</text>'
        )

        svg_parts.append("</svg>")
        return "\n".join(svg_parts)

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------

    def save_webxr(self, parse_result: BlueprintParseResult, report: ComplianceReport) -> str:
        scene = self.to_webxr_json(parse_result, report)
        path = self._output_dir / f"{parse_result.project_id}_ar.json"
        path.write_text(json.dumps(scene, indent=2))
        logger.info("WebXR scene saved: %s", path)
        return str(path)

    def save_svg(self, parse_result: BlueprintParseResult, report: ComplianceReport) -> str:
        svg = self.to_svg(parse_result, report)
        path = self._output_dir / f"{parse_result.project_id}_floorplan.svg"
        path.write_text(svg)
        logger.info("SVG floor plan saved: %s", path)
        return str(path)

    def save_vision_pro(self, parse_result: BlueprintParseResult, report: ComplianceReport) -> str:
        scene = self.to_vision_pro(parse_result, report)
        path = self._output_dir / f"{parse_result.project_id}_visionpro.json"
        path.write_text(json.dumps(scene, indent=2))
        logger.info("Vision Pro scene saved: %s", path)
        return str(path)
