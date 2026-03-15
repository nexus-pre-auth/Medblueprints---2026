"""
MedBlueprints Demo
==================
Demonstrates the full AI pipeline using synthetic demo data.

Run:
  python demo.py
"""
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.engines.pipeline import MedBlueprintsPipeline


def main():
    print("\n" + "=" * 65)
    print("  MedBlueprints Advanced AI Architecture — Demo")
    print("=" * 65)

    print("\n[1/6] Initializing AI Pipeline...")
    # Disable LLM for demo (no API key needed)
    pipeline = MedBlueprintsPipeline(enable_llm=False, enable_ar=True)

    print("[2/6] Running full pipeline on demo hospital blueprint...")
    result = pipeline.run(use_demo=True, project_id="DEMO-HOSP-001")

    print("\n" + "─" * 65)
    print("  BLUEPRINT PARSE RESULTS")
    print("─" * 65)
    pr = result.parse_result
    print(f"  Project ID    : {pr.project_id}")
    print(f"  Rooms detected: {len(pr.rooms)}")
    print(f"  Total area    : {pr.total_area_sqft:,.0f} sqft")
    print(f"  Parse confidence: {pr.parse_confidence:.0%}")
    print("\n  Rooms:")
    for room in pr.rooms:
        print(f"    • {room.label:<25} {room.room_type.value:<20} {room.area_sqft:.0f} sqft")

    print("\n" + "─" * 65)
    print("  DIGITAL FACILITY GRAPH")
    print("─" * 65)
    fg = result.facility_graph
    print(f"  Graph nodes: {len(fg.nodes)}")
    print(f"  Graph edges: {len(fg.edges)}")
    adjacency_edges = [e for e in fg.edges if e.edge_type.value == "adjacent_to"]
    print(f"  Adjacency pairs: {len(adjacency_edges)}")

    print("\n" + "─" * 65)
    print("  COMPLIANCE ANALYSIS")
    print("─" * 65)
    report = result.compliance_report
    print(f"  Critical violations : {report.critical_violations}")
    print(f"  High violations     : {report.high_violations}")
    print(f"  Medium violations   : {report.medium_violations}")
    print(f"  Low violations      : {report.low_violations}")
    print(f"  Est. correction cost: ${report.estimated_total_correction_cost_usd:>12,.0f}")
    print(f"  Overall compliant   : {'YES ✓' if report.overall_compliant else 'NO ✗'}")

    if report.room_results:
        print("\n  Room-level results:")
        for rr in report.room_results:
            status = "✓" if rr.is_compliant else f"✗ ({len(rr.violations)} violations)"
            print(f"    • {rr.room_label:<25} {status}")

    print("\n" + "─" * 65)
    print("  PRE-SUBMISSION APPROVAL PREDICTION")
    print("─" * 65)
    pred = result.prediction
    print(f"  Submission Readiness Score : {pred.submission_readiness_score:.1f} / 100")
    print(f"  Overall Risk Level         : {pred.overall_risk_level.value.upper()}")
    print(f"  Estimated Rework Cost      : ${pred.estimated_rework_cost_usd:>12,.0f}")
    print(f"  Estimated Rework Days      : {pred.estimated_rework_days}")
    print(f"  Model Confidence           : {pred.confidence:.0%}")
    print(f"  Model Version              : {pred.model_version}")
    print("\n  Regulator Predictions:")
    for rp in pred.regulator_predictions:
        bar_len = int(rp.approval_probability / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"    {rp.regulator.value:<18} {bar} {rp.approval_probability:5.1f}%  (~{rp.expected_review_days}d)")

    if pred.top_blocking_issues:
        print("\n  Blocking Issues:")
        for issue in pred.top_blocking_issues:
            print(f"    ⚠  {issue}")

    if pred.recommended_actions:
        print("\n  Recommended Actions:")
        for action in pred.recommended_actions:
            print(f"    →  {action}")

    print("\n" + "─" * 65)
    print("  AR VISUALIZATION")
    print("─" * 65)
    if result.ar_webxr_scene:
        scene = result.ar_webxr_scene
        print(f"  WebXR scene generated: {len(scene.get('rooms', []))} room overlays")
        print("  Supported targets: WebXR browser, A-Frame, Three.js")
    if result.ar_svg_path:
        print(f"  SVG floor plan saved: {result.ar_svg_path}")
    print("  Additional: Apple Vision Pro scene descriptor available via /api/v1/visualization/vision-pro")

    print("\n" + "─" * 65)
    print("  STRATEGIC MOAT: REGULATORY DESIGN GRAPH")
    print("─" * 65)
    print("  Every project run through MedBlueprints contributes to:")
    print("  • The Outcome Dataset (approval results + rework costs)")
    print("  • The Regulatory Design Graph (room ↔ rule relationships)")
    print("  • The Approval Prediction Model (improves with each project)")
    print()
    print("  Data advantages this creates:")
    print("  • Largest healthcare facility design + outcome dataset")
    print("  • Predictive accuracy competitors cannot match")
    print("  • Network effects: more architects → better predictions")

    print("\n" + "=" * 65)
    print("  Full API available at http://localhost:8000/docs")
    print("  Run: uvicorn main:app --reload")
    print("=" * 65 + "\n")

    if result.errors:
        print("Warnings during pipeline run:")
        for err in result.errors:
            print(f"  ! {err}")


if __name__ == "__main__":
    main()
