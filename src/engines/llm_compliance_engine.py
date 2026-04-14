"""
LLM Compliance Reasoning Engine
=================================
Uses Claude (Anthropic) to interpret structured compliance check results
and produce human-readable, actionable violation explanations.

Design principle:
  The LLM does NOT parse blueprints.
  Geometry and rule evaluation happen in the deterministic engines.
  Claude receives pre-computed room data + matched rules and is asked
  to reason about severity, remediation, and cost — preventing hallucinations.

Flow:
  1. Deterministic rule evaluation → list of candidate violations
  2. Claude interprets each violation:
       - Confirms severity
       - Suggests remediation
       - Estimates correction cost
       - Generates human-readable explanation
  3. Claude produces a project-level compliance summary
"""
import json
import logging
import uuid
from typing import List, Optional, Dict, Any

import anthropic

from src.core.config import settings
from src.models.blueprint import DetectedRoom, RoomType
from src.models.compliance import (
    ComplianceViolation,
    ComplianceReport,
    RegulatoryRule,
    RoomComplianceResult,
    ViolationSeverity,
    ConstraintType,
)
from src.engines.regulatory_knowledge_graph import RegulatoryKnowledgeGraph
from src.models.blueprint import BlueprintParseResult

logger = logging.getLogger(__name__)

# Correction cost estimates (USD) by constraint type and severity.
# Derived from RSMeans construction cost data and healthcare facility cost studies.
# Critical = complete redesign or structural rebuild; High = significant rework;
# Medium = targeted modification within existing scope.
COST_ESTIMATES: Dict[str, Dict[str, float]] = {
    ConstraintType.MINIMUM_VENTILATION.value: {
        # HVAC duct redesign + commissioning; critical = full AHU replacement/rerouting
        ViolationSeverity.CRITICAL.value: 95_000,
        ViolationSeverity.HIGH.value: 45_000,
        ViolationSeverity.MEDIUM.value: 18_000,
    },
    ConstraintType.MINIMUM_AREA.value: {
        # Room expansion requires demolition + reconstruction; highly dependent on project stage
        ViolationSeverity.CRITICAL.value: 180_000,
        ViolationSeverity.HIGH.value: 85_000,
        ViolationSeverity.MEDIUM.value: 30_000,
    },
    ConstraintType.ADJACENCY_REQUIRED.value: {
        # Corridor rerouting or department relocation; critical = major floor plan revision
        ViolationSeverity.CRITICAL.value: 120_000,
        ViolationSeverity.HIGH.value: 55_000,
        ViolationSeverity.MEDIUM.value: 20_000,
    },
    ConstraintType.MINIMUM_CORRIDOR_WIDTH.value: {
        # Wall relocation + finish work; critical = structural wall involvement
        ViolationSeverity.CRITICAL.value: 65_000,
        ViolationSeverity.HIGH.value: 28_000,
        ViolationSeverity.MEDIUM.value: 10_000,
    },
    ConstraintType.EQUIPMENT_REQUIRED.value: {
        # Equipment procurement + installation + commissioning
        ViolationSeverity.CRITICAL.value: 85_000,
        ViolationSeverity.HIGH.value: 38_000,
        ViolationSeverity.MEDIUM.value: 12_000,
    },
}


class LLMComplianceEngine:
    """
    Wraps the Anthropic Claude API to provide LLM-powered compliance reasoning.

    Two primary methods:
      evaluate_room  - check a single room against applicable rules
      generate_report - full project compliance report with LLM summary
    """

    def __init__(self, knowledge_graph: Optional[RegulatoryKnowledgeGraph] = None):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_model
        self._kg = knowledge_graph or RegulatoryKnowledgeGraph()
        logger.info("LLMComplianceEngine initialized with model: %s", self._model)

    # ------------------------------------------------------------------
    # Single-room evaluation
    # ------------------------------------------------------------------

    def evaluate_room(self, room: DetectedRoom, adjacent_room_types: List[str]) -> RoomComplianceResult:
        """
        Deterministic rule check + LLM interpretation for one room.
        """
        # 1. Retrieve applicable rules from knowledge graph
        applicable_rules = self._kg.get_rules_for_room_type(room.room_type.value)
        if not applicable_rules:
            return RoomComplianceResult(
                room_id=room.id,
                room_label=room.label,
                room_type=room.room_type.value,
                llm_interpretation="No specific regulatory rules found for this room type.",
            )

        # 2. Deterministic checks
        raw_violations, passed = self._deterministic_check(room, applicable_rules, adjacent_room_types)

        # 3. LLM interpretation of violations (only if violations exist)
        llm_text = None
        enriched_violations = raw_violations
        if raw_violations:
            enriched_violations, llm_text = self._llm_interpret_violations(
                room, raw_violations, applicable_rules
            )

        return RoomComplianceResult(
            room_id=room.id,
            room_label=room.label,
            room_type=room.room_type.value,
            violations=enriched_violations,
            passed_rules=passed,
            llm_interpretation=llm_text,
        )

    def _deterministic_check(
        self,
        room: DetectedRoom,
        rules: List[RegulatoryRule],
        adjacent_room_types: List[str],
    ) -> tuple[List[ComplianceViolation], List[str]]:
        violations: List[ComplianceViolation] = []
        passed: List[str] = []

        for rule in rules:
            violation = self._check_rule(room, rule, adjacent_room_types)
            if violation:
                violations.append(violation)
            else:
                passed.append(rule.rule_id)

        return violations, passed

    def _check_rule(
        self,
        room: DetectedRoom,
        rule: RegulatoryRule,
        adjacent_room_types: List[str],
    ) -> Optional[ComplianceViolation]:
        """Return a ComplianceViolation if the room fails the rule, else None."""
        ct = rule.constraint_type

        # --- Area checks ---
        if ct == ConstraintType.MINIMUM_AREA:
            actual = room.area_sqft or 0.0
            required = rule.threshold_value or 0.0
            if actual < required:
                severity = ViolationSeverity.CRITICAL if actual < required * 0.85 else ViolationSeverity.HIGH
                return self._make_violation(rule, room, severity, actual, required, "sqft")

        # --- Ventilation checks ---
        elif ct == ConstraintType.MINIMUM_VENTILATION:
            actual = float(room.attributes.get("ventilation_ach", 0))
            required = rule.threshold_value or 0.0
            if actual > 0 and actual < required:
                severity = ViolationSeverity.CRITICAL if actual < required * 0.8 else ViolationSeverity.HIGH
                return self._make_violation(rule, room, severity, actual, required, "ACH")

        # --- Adjacency checks ---
        elif ct == ConstraintType.ADJACENCY_REQUIRED:
            required_neighbor = rule.related_room_type
            if required_neighbor and required_neighbor not in adjacent_room_types:
                return self._make_violation(rule, room, ViolationSeverity.HIGH)

        # --- Corridor width ---
        elif ct == ConstraintType.MINIMUM_CORRIDOR_WIDTH:
            actual = float(room.attributes.get("width_ft", 0))
            required = rule.threshold_value or 0.0
            if actual > 0 and actual < required:
                severity = ViolationSeverity.CRITICAL if actual < required * 0.75 else ViolationSeverity.MEDIUM
                return self._make_violation(rule, room, severity, actual, required, "ft")

        return None

    @staticmethod
    def _make_violation(
        rule: RegulatoryRule,
        room: DetectedRoom,
        severity: ViolationSeverity,
        actual: Optional[float] = None,
        required: Optional[float] = None,
        unit: Optional[str] = None,
    ) -> ComplianceViolation:
        cost = COST_ESTIMATES.get(rule.constraint_type.value, {}).get(
            severity.value, 50_000
        )
        return ComplianceViolation(
            violation_id=str(uuid.uuid4())[:8],
            rule_id=rule.rule_id,
            room_id=room.id,
            room_label=room.label,
            severity=severity,
            constraint_type=rule.constraint_type,
            description=rule.description,
            actual_value=actual,
            required_value=required,
            unit=unit,
            estimated_correction_cost_usd=cost,
            source=rule.source,
        )

    # ------------------------------------------------------------------
    # LLM enrichment
    # ------------------------------------------------------------------

    def _llm_interpret_violations(
        self,
        room: DetectedRoom,
        violations: List[ComplianceViolation],
        applicable_rules: List[RegulatoryRule],
    ) -> tuple[List[ComplianceViolation], str]:
        """
        Send room + violations to Claude for enriched reasoning.
        Returns enriched violations and a room-level explanation string.
        """
        prompt = self._build_violation_prompt(room, violations, applicable_rules)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            return self._parse_llm_response(raw, violations)
        except Exception as exc:
            logger.warning("LLM call failed for room %s: %s", room.id, exc)
            return violations, "LLM analysis unavailable; violations detected by deterministic engine."

    @staticmethod
    def _build_violation_prompt(
        room: DetectedRoom,
        violations: List[ComplianceViolation],
        rules: List[RegulatoryRule],
    ) -> str:
        room_data = {
            "room_id": room.id,
            "label": room.label,
            "room_type": room.room_type.value,
            "area_sqft": room.area_sqft,
            "attributes": room.attributes,
        }
        violation_data = [
            {
                "rule_id": v.rule_id,
                "constraint": v.constraint_type.value,
                "severity": v.severity.value,
                "actual": v.actual_value,
                "required": v.required_value,
                "unit": v.unit,
            }
            for v in violations
        ]
        rule_texts = [f"- [{r.rule_id}] {r.description} (citation: {r.citation})" for r in rules]

        return f"""You are a healthcare facility compliance expert reviewing a blueprint analysis.

ROOM DATA:
{json.dumps(room_data, indent=2)}

DETECTED VIOLATIONS:
{json.dumps(violation_data, indent=2)}

APPLICABLE REGULATIONS:
{chr(10).join(rule_texts)}

For each violation, provide:
1. A plain-English explanation of why this is a problem
2. Specific remediation steps an architect can take
3. Estimated correction cost (USD) — use realistic construction cost estimates
4. Whether your confidence in the severity rating is high/medium/low

Then provide a one-paragraph summary of the room's overall compliance status.

Respond in this exact JSON format:
{{
  "violations": [
    {{
      "rule_id": "<rule_id>",
      "explanation": "<plain English explanation>",
      "remediation": "<specific steps>",
      "estimated_cost_usd": <number>,
      "severity_confidence": "high|medium|low"
    }}
  ],
  "room_summary": "<one paragraph summary>"
}}"""

    @staticmethod
    def _parse_llm_response(
        raw: str,
        violations: List[ComplianceViolation],
    ) -> tuple[List[ComplianceViolation], str]:
        try:
            # Extract JSON from response (may have surrounding text)
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                return violations, raw

            data = json.loads(raw[start:end])
            summary = data.get("room_summary", "")

            # Enrich violations with LLM insights
            llm_by_rule: Dict[str, Dict] = {
                v["rule_id"]: v for v in data.get("violations", [])
            }
            enriched = []
            for v in violations:
                llm_data = llm_by_rule.get(v.rule_id)
                if llm_data:
                    enriched.append(v.model_copy(update={
                        "remediation_suggestion": llm_data.get("remediation"),
                        "estimated_correction_cost_usd": llm_data.get(
                            "estimated_cost_usd", v.estimated_correction_cost_usd
                        ),
                    }))
                else:
                    enriched.append(v)
            return enriched, summary

        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse LLM response: %s", exc)
            return violations, raw

    # ------------------------------------------------------------------
    # Full project report
    # ------------------------------------------------------------------

    def generate_report(
        self,
        parse_result: BlueprintParseResult,
        facility_graph_adjacencies: Optional[Dict[str, List[str]]] = None,
    ) -> ComplianceReport:
        """
        Run compliance evaluation on all rooms and generate a full report
        with a project-level LLM summary.
        """
        logger.info("Generating compliance report for project %s", parse_result.project_id)
        adjacencies = facility_graph_adjacencies or {}
        room_results: List[RoomComplianceResult] = []

        for room in parse_result.rooms:
            adjacent_types = adjacencies.get(room.id, [])
            result = self.evaluate_room(room, adjacent_types)
            room_results.append(result)

        report = ComplianceReport(
            project_id=parse_result.project_id,
            room_results=room_results,
        )
        report.compute_totals()

        # Project-level summary from LLM
        report.summary = self._generate_project_summary(report)
        return report

    def _generate_project_summary(self, report: ComplianceReport) -> str:
        all_violations = [v for r in report.room_results for v in r.violations]
        if not all_violations:
            return (
                f"Project {report.project_id} passed all regulatory checks across "
                f"{len(report.room_results)} rooms. The facility appears ready for submission."
            )

        prompt = f"""You are a senior healthcare facility compliance reviewer.

PROJECT COMPLIANCE SUMMARY:
- Total rooms reviewed: {len(report.room_results)}
- Critical violations: {report.critical_violations}
- High violations: {report.high_violations}
- Medium violations: {report.medium_violations}
- Low violations: {report.low_violations}
- Estimated total correction cost: ${report.estimated_total_correction_cost_usd:,.0f}

TOP VIOLATIONS:
{self._format_top_violations(all_violations[:5])}

Write a concise (3-4 sentence) executive summary that:
1. States the overall compliance status
2. Highlights the most critical issues
3. Provides a clear recommendation (ready to submit / needs revision / major redesign required)

Be direct and professional. Do not use bullet points."""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            logger.warning("Project summary LLM call failed: %s", exc)
            return (
                f"Project {report.project_id}: {report.total_violations} violations found "
                f"({report.critical_violations} critical, {report.high_violations} high). "
                f"Estimated correction cost: ${report.estimated_total_correction_cost_usd:,.0f}."
            )

    @staticmethod
    def _format_top_violations(violations: List[ComplianceViolation]) -> str:
        lines = []
        for v in violations:
            lines.append(
                f"- [{v.severity.value.upper()}] {v.room_label}: {v.description[:100]}"
            )
        return "\n".join(lines)
