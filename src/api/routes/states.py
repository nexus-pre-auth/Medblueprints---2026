"""
State Regulatory Data Feed Routes
====================================
Powers the "one feed per state" vision for Medblueprints.com.

Every endpoint here feeds real state regulatory data back to the platform,
enabling per-state compliance analysis, national dashboards, and the eventual
goal of all 50 states + DC feeding Medblueprints.com.

Endpoints:
  GET  /states/                      — national feed summary (all states)
  GET  /states/available             — states with live data files
  GET  /states/{state}/              — per-state feed summary
  GET  /states/{state}/rules         — all rules for a state
  GET  /states/{state}/compliance-stack — full stack (federal + state)
  POST /states/{state}/analyze        — run compliance analysis for a state
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.engines.state_regulatory_engine import StateRegulatoryEngine, ALL_STATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/states", tags=["State Regulatory Feeds"])

# Module-level singleton (initialized once on first import)
_state_engine: Optional[StateRegulatoryEngine] = None


def get_state_engine() -> StateRegulatoryEngine:
    global _state_engine
    if _state_engine is None:
        _state_engine = StateRegulatoryEngine()
    return _state_engine


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StateAnalysisRequest(BaseModel):
    state: str
    room_type: str
    actual_area_sq_ft: Optional[float] = None
    actual_ventilation_ach: Optional[float] = None
    corridor_width_ft: Optional[float] = None
    has_equipment_list: Optional[List[str]] = None


class StateAnalysisResult(BaseModel):
    state: str
    state_name: str
    room_type: str
    rules_evaluated: int
    violations: List[dict]
    passed: List[str]
    compliance_score: float
    authority: Optional[dict] = None
    powered_by: str = "MedBlueprints.com + Claude AI"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/",
    summary="National Feed Summary — All States",
    description=(
        "Master dashboard view for Medblueprints.com: shows all 50 states + DC, "
        "which are live with state-specific rules, and overall national coverage."
    ),
)
async def national_feed_summary():
    """
    The big picture: one feed per state, all feeding Medblueprints.com.
    Use this to power the national compliance intelligence dashboard.
    """
    engine = get_state_engine()
    return engine.get_national_feed_summary()


@router.get(
    "/available",
    summary="States With Live Data",
    description="Returns list of state abbreviations that have regulatory rule files loaded.",
)
async def available_states():
    engine = get_state_engine()
    available = engine.available_states()
    return {
        "available_states": available,
        "count": len(available),
        "total_possible": len(ALL_STATES),
        "coverage_pct": round(len(available) / len(ALL_STATES) * 100, 1),
        "message": f"{len(available)} of {len(ALL_STATES)} state feeds live on Medblueprints.com",
    }


@router.get(
    "/{state}",
    summary="State Feed Summary",
    description="Feed summary for a specific state: authority, rule counts, coverage breakdown.",
)
async def state_feed_summary(state: str):
    state = state.upper()
    if state not in ALL_STATES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown state code '{state}'. Use a 2-letter US state abbreviation.",
        )
    engine = get_state_engine()
    return engine.get_state_feed_summary(state)


@router.get(
    "/{state}/rules",
    summary="State Regulatory Rules",
    description="All healthcare construction rules for a specific state, optionally filtered.",
)
async def state_rules(
    state: str,
    room_type: Optional[str] = Query(None, description="Filter by room type (e.g. operating_room)"),
    constraint_type: Optional[str] = Query(None, description="Filter by constraint type"),
):
    state = state.upper()
    if state not in ALL_STATES:
        raise HTTPException(status_code=404, detail=f"Unknown state '{state}'")

    engine = get_state_engine()

    if room_type or constraint_type:
        rules = engine.search_rules(state, room_type=room_type, constraint_type=constraint_type)
    else:
        rules = engine.get_rules_for_state(state)

    if not rules:
        return {
            "state": state,
            "state_name": ALL_STATES[state],
            "rules": [],
            "count": 0,
            "status": "pending_integration",
            "message": (
                f"State rules for {ALL_STATES[state]} are being integrated. "
                "Federal rules (FGI, NFPA, ASHRAE, ADA) apply in the meantime."
            ),
        }

    return {
        "state": state,
        "state_name": ALL_STATES[state],
        "authority": engine.get_state_authority(state),
        "rules": [r.model_dump() for r in rules],
        "count": len(rules),
        "status": "live",
        "powered_by": "MedBlueprints.com",
    }


@router.get(
    "/{state}/compliance-stack",
    summary="Full Compliance Stack",
    description=(
        "Returns the complete regulatory compliance stack for a state: "
        "federal baseline rules + state-specific rules merged together."
    ),
)
async def state_compliance_stack(state: str, request: Request):
    state = state.upper()
    if state not in ALL_STATES:
        raise HTTPException(status_code=404, detail=f"Unknown state '{state}'")

    engine = get_state_engine()

    # Try to pull federal rules from the regulatory knowledge graph if available
    federal_rules = []
    try:
        from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
        rkg = RegulatoryKnowledgeGraph(enable_vector_search=False)
        federal_rules = list(rkg._rules.values())
    except Exception as exc:
        logger.warning("Could not load federal rules for stack: %s", exc)

    stack = engine.get_full_compliance_stack(state, federal_rules=federal_rules)
    stack["powered_by"] = "MedBlueprints.com — AI Regulatory Intelligence"
    return stack


@router.post(
    "/{state}/analyze",
    response_model=StateAnalysisResult,
    summary="Run State-Specific Compliance Check",
    description=(
        "Quick compliance check against a specific state's regulations. "
        "Evaluates room dimensions, ventilation, and equipment against state rules. "
        "For full AI-powered analysis use POST /api/v1/compliance/analyze."
    ),
)
async def analyze_for_state(state: str, req: StateAnalysisRequest):
    state_code = state.upper()
    if state_code not in ALL_STATES:
        raise HTTPException(status_code=404, detail=f"Unknown state '{state}'")

    engine = get_state_engine()
    rules = engine.get_rules_for_state(state_code)

    if not rules:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No state-specific rules loaded for {ALL_STATES[state_code]} yet. "
                "Use /api/v1/compliance/analyze for federal rule-based analysis."
            ),
        )

    violations = []
    passed = []

    for rule in rules:
        # Only evaluate rules for the requested room type (or "all" rules)
        if rule.room_type not in (req.room_type, "all"):
            continue

        from src.models.compliance import ConstraintType

        if rule.constraint_type == ConstraintType.MINIMUM_AREA and req.actual_area_sq_ft is not None:
            if rule.threshold_value and req.actual_area_sq_ft < rule.threshold_value:
                violations.append({
                    "rule_id": rule.rule_id,
                    "description": rule.description,
                    "required": f"{rule.threshold_value} {rule.threshold_unit}",
                    "actual": f"{req.actual_area_sq_ft} sq_ft",
                    "severity": "critical",
                    "citation": rule.citation,
                })
            else:
                passed.append(rule.rule_id)

        elif rule.constraint_type == ConstraintType.MINIMUM_VENTILATION and req.actual_ventilation_ach is not None:
            if rule.threshold_value and req.actual_ventilation_ach < rule.threshold_value:
                violations.append({
                    "rule_id": rule.rule_id,
                    "description": rule.description,
                    "required": f"{rule.threshold_value} ACH",
                    "actual": f"{req.actual_ventilation_ach} ACH",
                    "severity": "critical",
                    "citation": rule.citation,
                })
            else:
                passed.append(rule.rule_id)

        elif rule.constraint_type == ConstraintType.MINIMUM_CORRIDOR_WIDTH and req.corridor_width_ft is not None:
            if rule.threshold_value and req.corridor_width_ft < rule.threshold_value:
                violations.append({
                    "rule_id": rule.rule_id,
                    "description": rule.description,
                    "required": f"{rule.threshold_value} ft",
                    "actual": f"{req.corridor_width_ft} ft",
                    "severity": "high",
                    "citation": rule.citation,
                })
            else:
                passed.append(rule.rule_id)

        elif rule.constraint_type == ConstraintType.EQUIPMENT_REQUIRED:
            violations.append({
                "rule_id": rule.rule_id,
                "description": rule.description,
                "severity": "advisory",
                "citation": rule.citation,
                "note": "Verify manually — process/documentation requirement",
            })

    rules_evaluated = len(violations) + len(passed)
    compliance_score = round(len(passed) / rules_evaluated * 100, 1) if rules_evaluated > 0 else 100.0

    return StateAnalysisResult(
        state=state_code,
        state_name=ALL_STATES[state_code],
        room_type=req.room_type,
        rules_evaluated=rules_evaluated,
        violations=violations,
        passed=passed,
        compliance_score=compliance_score,
        authority=engine.get_state_authority(state_code),
    )
