"""
MedBlueprints Pipeline Tests
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.engines.cv_blueprint_engine import CVBlueprintEngine
from src.engines.facility_graph import FacilityGraphEngine
from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
from src.engines.approval_prediction import ApprovalPredictionEngine, extract_features
from src.engines.ar_visualization import ARVisualizationEngine
from src.engines.llm_compliance_engine import LLMComplianceEngine
from src.models.blueprint import RoomType, BlueprintParseResult, DetectedRoom, Polygon
from src.models.compliance import ComplianceReport, RoomComplianceResult, ComplianceViolation, ViolationSeverity, ConstraintType, RuleSource
from src.models.prediction import ProjectOutcome


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def demo_parse_result():
    return CVBlueprintEngine.create_demo_parse_result("TEST-001")


@pytest.fixture
def knowledge_graph():
    return RegulatoryKnowledgeGraph()


@pytest.fixture
def graph_engine():
    return FacilityGraphEngine()


@pytest.fixture
def prediction_engine():
    return ApprovalPredictionEngine()


@pytest.fixture
def ar_engine(tmp_path):
    return ARVisualizationEngine(output_dir=str(tmp_path))


@pytest.fixture
def demo_compliance_report(demo_parse_result):
    report = ComplianceReport(project_id="TEST-001")
    for room in demo_parse_result.rooms:
        report.room_results.append(RoomComplianceResult(
            room_id=room.id,
            room_label=room.label,
            room_type=room.room_type.value,
        ))
    report.compute_totals()
    return report


@pytest.fixture
def compliance_report_with_violations(demo_parse_result):
    """Report with critical violations for testing."""
    violations = [
        ComplianceViolation(
            violation_id="v001",
            rule_id="FGI_OR_001",
            room_id=demo_parse_result.rooms[0].id,
            room_label="OR 101",
            severity=ViolationSeverity.CRITICAL,
            constraint_type=ConstraintType.MINIMUM_VENTILATION,
            description="Ventilation below 20 ACH",
            actual_value=18,
            required_value=20,
            unit="ACH",
            estimated_correction_cost_usd=280_000,
            source=RuleSource.FGI,
        )
    ]
    report = ComplianceReport(project_id="TEST-001")
    for i, room in enumerate(demo_parse_result.rooms):
        rr = RoomComplianceResult(
            room_id=room.id,
            room_label=room.label,
            room_type=room.room_type.value,
            violations=violations if i == 0 else [],
        )
        report.room_results.append(rr)
    report.compute_totals()
    return report


# ── Layer 1: CV Blueprint Engine ────────────────────────────────────────────

class TestCVBlueprintEngine:
    def test_demo_parse_result_structure(self, demo_parse_result):
        assert demo_parse_result.project_id == "TEST-001"
        assert len(demo_parse_result.rooms) == 5
        assert demo_parse_result.total_area_sqft > 0

    def test_demo_has_correct_room_types(self, demo_parse_result):
        types = [r.room_type for r in demo_parse_result.rooms]
        assert RoomType.OPERATING_ROOM in types
        assert RoomType.STERILE_CORE in types
        assert RoomType.ICU in types
        assert RoomType.NURSE_STATION in types

    def test_demo_or_area(self, demo_parse_result):
        or_rooms = [r for r in demo_parse_result.rooms if r.room_type == RoomType.OPERATING_ROOM]
        assert all(r.area_sqft >= 400 for r in or_rooms)

    def test_polygon_area(self):
        poly = Polygon(points=[(0, 0), (10, 0), (10, 10), (0, 10)])
        assert poly.area == 100.0

    def test_polygon_centroid(self):
        poly = Polygon(points=[(0, 0), (10, 0), (10, 10), (0, 10)])
        cx, cy = poly.centroid
        assert cx == 5.0
        assert cy == 5.0

    def test_room_by_id(self, demo_parse_result):
        first_id = demo_parse_result.rooms[0].id
        found = demo_parse_result.room_by_id(first_id)
        assert found is not None
        assert found.id == first_id


# ── Layer 2: Digital Facility Graph ─────────────────────────────────────────

class TestFacilityGraph:
    def test_graph_builds(self, demo_parse_result, graph_engine):
        graph = graph_engine.build(demo_parse_result)
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

    def test_system_nodes_created(self, demo_parse_result, graph_engine):
        graph = graph_engine.build(demo_parse_result)
        system_nodes = [n for n in graph.nodes if n.node_type.value == "system"]
        assert len(system_nodes) >= 3  # HVAC, electrical, medical gas

    def test_all_rooms_in_graph(self, demo_parse_result, graph_engine):
        graph = graph_engine.build(demo_parse_result)
        room_node_ids = {n.id for n in graph.nodes if n.node_type.value == "room"}
        parse_room_ids = {r.id for r in demo_parse_result.rooms}
        assert parse_room_ids == room_node_ids

    def test_ventilation_edges(self, demo_parse_result, graph_engine):
        graph = graph_engine.build(demo_parse_result)
        vent_edges = [e for e in graph.edges if e.edge_type.value == "ventilated_by"]
        assert len(vent_edges) == len(demo_parse_result.rooms)

    def test_networkx_export(self, demo_parse_result, graph_engine):
        graph = graph_engine.build(demo_parse_result)
        G = graph_engine.to_networkx(graph)
        assert G.number_of_nodes() > 0
        assert G.number_of_edges() > 0


# ── Layer 3: Regulatory Knowledge Graph ─────────────────────────────────────

class TestRegulatoryKnowledgeGraph:
    def test_rules_loaded(self, knowledge_graph):
        assert len(knowledge_graph.get_all_rules()) > 0

    def test_or_rules_present(self, knowledge_graph):
        rules = knowledge_graph.get_rules_for_room_type("operating_room")
        assert len(rules) >= 3

    def test_ventilation_rules(self, knowledge_graph):
        from src.models.compliance import ConstraintType
        rules = knowledge_graph.get_rules_for_room_type(
            "operating_room", ConstraintType.MINIMUM_VENTILATION
        )
        assert len(rules) >= 1
        assert any(r.threshold_value == 20 for r in rules)

    def test_adjacency_rules(self, knowledge_graph):
        rules = knowledge_graph.get_adjacency_rules("operating_room")
        assert any(r.related_room_type == "sterile_core" for r in rules)

    def test_keyword_search(self, knowledge_graph):
        results = knowledge_graph.semantic_search("ventilation operating room", top_k=3)
        assert len(results) >= 1

    def test_graph_export(self, knowledge_graph):
        data = knowledge_graph.export_graph_json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

    def test_stats(self, knowledge_graph):
        stats = knowledge_graph.stats()
        assert stats["total_rules"] > 0
        assert "operating_room" in stats["room_types_covered"]


# ── Layer 5: Approval Prediction ─────────────────────────────────────────────

class TestApprovalPrediction:
    def test_predict_compliant(self, demo_parse_result, demo_compliance_report, prediction_engine):
        features = extract_features(demo_parse_result, demo_compliance_report)
        prediction = prediction_engine.predict(features)
        assert prediction.submission_readiness_score >= 90
        assert prediction.overall_risk_level.value == "low"

    def test_predict_with_violations(
        self, demo_parse_result, compliance_report_with_violations, prediction_engine
    ):
        features = extract_features(demo_parse_result, compliance_report_with_violations)
        prediction = prediction_engine.predict(features)
        # Should show reduced readiness with critical violations
        assert prediction.submission_readiness_score < 100

    def test_prediction_has_all_regulators(
        self, demo_parse_result, demo_compliance_report, prediction_engine
    ):
        features = extract_features(demo_parse_result, demo_compliance_report)
        prediction = prediction_engine.predict(features)
        regulators = {rp.regulator.value for rp in prediction.regulator_predictions}
        assert "FGI" in regulators
        assert "AHJ" in regulators

    def test_feature_extraction(self, demo_parse_result, demo_compliance_report):
        features = extract_features(demo_parse_result, demo_compliance_report)
        assert features.has_operating_rooms is True
        assert features.operating_room_count == 2
        assert features.has_icu is True
        assert features.total_rooms == 5


# ── Layer 6: AR Visualization ─────────────────────────────────────────────────

class TestARVisualization:
    def test_webxr_scene_structure(
        self, demo_parse_result, demo_compliance_report, ar_engine
    ):
        scene = ar_engine.to_webxr_json(demo_parse_result, demo_compliance_report)
        assert "rooms" in scene
        assert "summary" in scene
        assert "legend" in scene
        assert len(scene["rooms"]) == len(demo_parse_result.rooms)

    def test_room_colors_in_scene(
        self, demo_parse_result, demo_compliance_report, ar_engine
    ):
        scene = ar_engine.to_webxr_json(demo_parse_result, demo_compliance_report)
        for room in scene["rooms"]:
            assert "color" in room
            assert "compliance_status" in room

    def test_svg_generation(
        self, demo_parse_result, demo_compliance_report, ar_engine
    ):
        svg = ar_engine.to_svg(demo_parse_result, demo_compliance_report)
        assert svg.startswith("<svg")
        assert "</svg>" in svg
        assert "MedBlueprints" in svg

    def test_vision_pro_scene(
        self, demo_parse_result, demo_compliance_report, ar_engine
    ):
        scene = ar_engine.to_vision_pro(demo_parse_result, demo_compliance_report)
        assert "entities" in scene
        assert scene["coordinate_system"] == "RealityKit"
        assert len(scene["entities"]) == len(demo_parse_result.rooms)

    def test_svg_has_violation_badges(
        self, demo_parse_result, compliance_report_with_violations, ar_engine
    ):
        svg = ar_engine.to_svg(demo_parse_result, compliance_report_with_violations)
        # Should contain circle elements for violation badges
        assert "<circle" in svg

    def test_save_svg(self, demo_parse_result, demo_compliance_report, ar_engine):
        path = ar_engine.save_svg(demo_parse_result, demo_compliance_report)
        assert Path(path).exists()


# ── End-to-End Pipeline ──────────────────────────────────────────────────────

class TestEndToEndPipeline:
    def test_full_pipeline_demo(self):
        from src.engines.pipeline import MedBlueprintsPipeline
        pipeline = MedBlueprintsPipeline(enable_llm=False, enable_ar=True)
        result = pipeline.run(use_demo=True, project_id="PYTEST-001")

        assert result.project_id == "PYTEST-001"
        assert len(result.parse_result.rooms) > 0
        assert result.facility_graph is not None
        assert result.compliance_report is not None
        assert result.prediction is not None
        assert result.prediction.submission_readiness_score >= 0
        assert result.ar_webxr_scene is not None

    def test_pipeline_summary(self):
        from src.engines.pipeline import MedBlueprintsPipeline
        pipeline = MedBlueprintsPipeline(enable_llm=False, enable_ar=False)
        result = pipeline.run(use_demo=True, project_id="PYTEST-002")
        summary = result.summary()

        assert "project_id" in summary
        assert "submission_readiness" in summary
        assert "fgi_approval_probability" in summary
        assert "recommended_actions" in summary
