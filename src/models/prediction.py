"""
Prediction models — approval probability and submission readiness.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class RegulatorType(str, Enum):
    FGI = "FGI"
    AHJ = "AHJ"       # Authority Having Jurisdiction
    STATE = "state"
    JOINT_COMMISSION = "joint_commission"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class PredictionFeatures(BaseModel):
    """Feature vector used by the approval prediction model."""
    project_id: str
    total_rooms: int
    total_area_sqft: float
    critical_violations: int
    high_violations: int
    medium_violations: int
    low_violations: int
    has_operating_rooms: bool
    has_icu: bool
    has_emergency: bool
    operating_room_count: int
    icu_bed_count: int
    corridor_width_min_ft: float
    ventilation_deficiencies: int
    adjacency_violations: int
    egress_violations: int
    estimated_correction_cost_usd: float
    project_size_category: str  # small / medium / large / very_large
    facility_type: str
    regulator_region: str = "national"


class RegulatorPrediction(BaseModel):
    regulator: RegulatorType
    approval_probability: float = Field(ge=0.0, le=100.0)
    expected_review_days: int
    primary_concerns: List[str] = Field(default_factory=list)


class ApprovalPrediction(BaseModel):
    """Full approval prediction result."""
    project_id: str
    submission_readiness_score: float = Field(ge=0.0, le=100.0)
    overall_risk_level: RiskLevel
    regulator_predictions: List[RegulatorPrediction] = Field(default_factory=list)
    top_blocking_issues: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    estimated_rework_cost_usd: float = 0.0
    estimated_rework_days: int = 0
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    model_version: str = "1.0.0"


class ProjectOutcome(BaseModel):
    """Stored approval outcome — the dataset that builds the moat."""
    project_id: str
    facility_type: str
    total_rooms: int
    total_area_sqft: float
    critical_violations: int
    high_violations: int
    medium_violations: int
    low_violations: int
    operating_room_count: int
    icu_bed_count: int
    estimated_correction_cost_usd: float
    approval_result: Optional[str] = None   # "approved" | "rejected" | "conditional"
    regulator: Optional[str] = None
    review_duration_days: Optional[int] = None
    actual_rework_cost_usd: Optional[float] = None
    rework_changes: Optional[List[str]] = None
    submitted_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
