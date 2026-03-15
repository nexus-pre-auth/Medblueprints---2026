"""
Compliance API Routes
Run the full compliance engine on a parsed blueprint.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from src.engines.facility_graph import FacilityGraphEngine
from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
from src.engines.llm_compliance_engine import LLMComplianceEngine
from src.models.blueprint import BlueprintParseResult
from src.models.compliance import ComplianceReport, RegulatoryRule

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/compliance", tags=["compliance"])

# Shared engine instances (lightweight singletons for the process)
_kg: Optional[RegulatoryKnowledgeGraph] = None
_compliance_engine: Optional[LLMComplianceEngine] = None
_graph_engine = FacilityGraphEngine()


def get_knowledge_graph() -> RegulatoryKnowledgeGraph:
    global _kg
    if _kg is None:
        _kg = RegulatoryKnowledgeGraph()
    return _kg


def get_compliance_engine() -> LLMComplianceEngine:
    global _compliance_engine
    if _compliance_engine is None:
        _compliance_engine = LLMComplianceEngine(knowledge_graph=get_knowledge_graph())
    return _compliance_engine


@router.post("/analyze", summary="Run full compliance analysis on a blueprint")
async def analyze_compliance(parse_result: BlueprintParseResult):
    """
    Run the full compliance pipeline:
    1. Build facility graph (adjacency detection)
    2. Match regulatory rules from knowledge graph
    3. Deterministic rule evaluation
    4. LLM interpretation & remediation suggestions
    5. Return ComplianceReport with room-level and project-level results
    """
    # Build facility graph to get adjacencies
    facility_graph = _graph_engine.build(parse_result)

    # Build adjacency map: room_id → [adjacent room types]
    adjacencies: dict[str, list[str]] = {}
    for room in parse_result.rooms:
        neighbor_ids = _graph_engine.get_adjacent_rooms(facility_graph, room.id)
        neighbor_types = []
        for nid in neighbor_ids:
            neighbor_room = parse_result.room_by_id(nid)
            if neighbor_room:
                neighbor_types.append(neighbor_room.room_type.value)
        adjacencies[room.id] = neighbor_types

    engine = get_compliance_engine()
    try:
        report = engine.generate_report(parse_result, adjacencies)
    except Exception as exc:
        logger.error("Compliance analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compliance analysis error: {str(exc)}")

    return report.model_dump()


@router.get("/rules", summary="List all regulatory rules")
async def list_rules(
    room_type: Optional[str] = Query(None, description="Filter by room type"),
    source: Optional[str] = Query(None, description="Filter by source (FGI, NFPA, ASHRAE, ADA)"),
):
    """Browse the regulatory knowledge graph rules."""
    kg = get_knowledge_graph()
    rules = kg.get_rules_for_room_type(room_type) if room_type else kg.get_all_rules()

    if source:
        rules = [r for r in rules if r.source.value.upper() == source.upper()]

    return {
        "count": len(rules),
        "rules": [r.model_dump(exclude={"embedding"}) for r in rules],
    }


@router.get("/rules/search", summary="Semantic search over regulatory rules")
async def search_rules(
    q: str = Query(..., description="Natural language query"),
    top_k: int = Query(5, ge=1, le=20),
):
    """
    Semantically search the regulatory knowledge graph.
    Example: "operating room ventilation requirements"
    """
    kg = get_knowledge_graph()
    results = kg.semantic_search(q, top_k=top_k)
    return {
        "query": q,
        "count": len(results),
        "rules": [r.model_dump(exclude={"embedding"}) for r in results],
    }


@router.get("/rules/graph", summary="Export the regulatory knowledge graph")
async def export_rule_graph():
    """Export the full regulatory knowledge graph as nodes + edges JSON."""
    kg = get_knowledge_graph()
    return kg.export_graph_json()


@router.get("/rules/stats", summary="Regulatory knowledge graph statistics")
async def rule_graph_stats():
    kg = get_knowledge_graph()
    return kg.stats()
