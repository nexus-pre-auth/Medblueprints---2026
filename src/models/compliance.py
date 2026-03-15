"""
Compliance models — rules, violations, and analysis results.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class RuleSource(str, Enum):
    FGI = "FGI"           # Facility Guidelines Institute
    NFPA = "NFPA"         # National Fire Protection Association
    AIA = "AIA"           # American Institute of Architects
    ASHRAE = "ASHRAE"     # ASHRAE ventilation standards
    JOINT_COMMISSION = "joint_commission"
    ADA = "ADA"           # Americans with Disabilities Act
    STATE = "state_code"
    LOCAL = "local_ahj"   # Authority Having Jurisdiction


class ConstraintType(str, Enum):
    MINIMUM_AREA = "minimum_area"
    MAXIMUM_AREA = "maximum_area"
    MINIMUM_VENTILATION = "minimum_ventilation"
    ADJACENCY_REQUIRED = "adjacency_required"
    ADJACENCY_PROHIBITED = "adjacency_prohibited"
    MINIMUM_CORRIDOR_WIDTH = "minimum_corridor_width"
    EQUIPMENT_REQUIRED = "equipment_required"
    SEPARATION_REQUIRED = "separation_required"
    EGRESS_REQUIRED = "egress_required"
    LIGHTING_REQUIRED = "lighting_required"


class RegulatoryRule(BaseModel):
    rule_id: str
    source: RuleSource
    room_type: str
    constraint_type: ConstraintType
    description: str
    threshold_value: Optional[float] = None
    threshold_unit: Optional[str] = None
    related_room_type: Optional[str] = None
    mandatory: bool = True
    citation: Optional[str] = None
    embedding: Optional[List[float]] = None  # For vector search


class ViolationSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ADVISORY = "advisory"


class ComplianceViolation(BaseModel):
    violation_id: str
    rule_id: str
    room_id: str
    room_label: str
    severity: ViolationSeverity
    constraint_type: ConstraintType
    description: str
    actual_value: Optional[float] = None
    required_value: Optional[float] = None
    unit: Optional[str] = None
    estimated_correction_cost_usd: Optional[float] = None
    remediation_suggestion: Optional[str] = None
    source: RuleSource


class RoomComplianceResult(BaseModel):
    room_id: str
    room_label: str
    room_type: str
    violations: List[ComplianceViolation] = Field(default_factory=list)
    passed_rules: List[str] = Field(default_factory=list)
    llm_interpretation: Optional[str] = None

    @property
    def is_compliant(self) -> bool:
        return len([v for v in self.violations if v.severity in (
            ViolationSeverity.CRITICAL, ViolationSeverity.HIGH
        )]) == 0


class ComplianceReport(BaseModel):
    """Full compliance report for a project."""
    project_id: str
    room_results: List[RoomComplianceResult] = Field(default_factory=list)
    total_violations: int = 0
    critical_violations: int = 0
    high_violations: int = 0
    medium_violations: int = 0
    low_violations: int = 0
    estimated_total_correction_cost_usd: float = 0.0
    overall_compliant: bool = False
    summary: Optional[str] = None

    def compute_totals(self) -> None:
        all_violations = [v for r in self.room_results for v in r.violations]
        self.total_violations = len(all_violations)
        self.critical_violations = sum(1 for v in all_violations if v.severity == ViolationSeverity.CRITICAL)
        self.high_violations = sum(1 for v in all_violations if v.severity == ViolationSeverity.HIGH)
        self.medium_violations = sum(1 for v in all_violations if v.severity == ViolationSeverity.MEDIUM)
        self.low_violations = sum(1 for v in all_violations if v.severity == ViolationSeverity.LOW)
        self.estimated_total_correction_cost_usd = sum(
            v.estimated_correction_cost_usd or 0
            for v in all_violations
        )
        self.overall_compliant = self.critical_violations == 0 and self.high_violations == 0
