"""
Project Store — Full Project Lifecycle
========================================
Tracks every project from upload through approval outcome.

Project states:
  draft → analyzing → reviewed → submitted → approved | rejected | conditional

Each project links to:
  - Source files (stored references)
  - Analysis jobs (job_ids from job_store)
  - Compliance reports
  - Approval prediction results
  - Regulatory outcome (when received)

This is the primary business object — the "deal" in the sales pipeline.
"""
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, DateTime, Integer, Float, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String)
    facility_type: Mapped[str] = mapped_column(String, default="hospital")
    status: Mapped[str] = mapped_column(String, default="draft")

    # Location / regulatory context
    state: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    regulator_region: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="national")

    # File references (paths or cloud storage URLs)
    blueprint_filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blueprint_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Analysis link
    latest_job_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Snapshot of latest analysis results (JSON)
    parse_summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compliance_summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prediction_summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Key metrics (indexed for fast queries)
    total_rooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_area_sqft: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    critical_violations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    high_violations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    submission_readiness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fgi_approval_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_correction_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Regulatory outcome
    approval_result: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approval_regulator: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_rework_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Shareable report link
    share_token: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True, unique=True)

    # Team / org
    owner_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    org_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.id,
            "name": self.name,
            "facility_type": self.facility_type,
            "status": self.status,
            "state": self.state,
            "city": self.city,
            "regulator_region": self.regulator_region,
            "blueprint_filename": self.blueprint_filename,
            "latest_job_id": self.latest_job_id,
            "metrics": {
                "total_rooms": self.total_rooms,
                "total_area_sqft": self.total_area_sqft,
                "critical_violations": self.critical_violations,
                "high_violations": self.high_violations,
                "submission_readiness_score": self.submission_readiness_score,
                "fgi_approval_probability": self.fgi_approval_probability,
                "estimated_correction_cost_usd": self.estimated_correction_cost_usd,
            },
            "compliance_summary": json.loads(self.compliance_summary_json) if self.compliance_summary_json else None,
            "prediction_summary": json.loads(self.prediction_summary_json) if self.prediction_summary_json else None,
            "outcome": {
                "approval_result": self.approval_result,
                "regulator": self.approval_regulator,
                "review_duration_days": self.review_duration_days,
                "actual_rework_cost_usd": self.actual_rework_cost_usd,
            } if self.approval_result else None,
            "owner_email": self.owner_email,
            "org_name": self.org_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


class ProjectStore:
    """Async data access for the project lifecycle."""

    def __init__(self, database_url: Optional[str] = None):
        db_url = database_url or settings.database_url
        self._engine = create_async_engine(db_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("ProjectStore tables ready")

    async def create_project(
        self,
        name: str,
        facility_type: str = "hospital",
        state: Optional[str] = None,
        city: Optional[str] = None,
        owner_email: Optional[str] = None,
        org_name: Optional[str] = None,
    ) -> str:
        """Create a new project. Returns project_id."""
        pid = str(uuid.uuid4())[:12]
        record = ProjectRecord(
            id=pid,
            name=name,
            facility_type=facility_type,
            state=state,
            city=city,
            owner_email=owner_email,
            org_name=org_name,
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
        logger.info("Created project %s: %s", pid, name)
        return pid

    async def attach_job(
        self,
        project_id: str,
        job_id: str,
        blueprint_filename: Optional[str] = None,
    ) -> None:
        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
            record = res.scalar_one_or_none()
            if record:
                record.latest_job_id = job_id
                if blueprint_filename:
                    record.blueprint_filename = blueprint_filename
                record.status = "analyzing"
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def update_from_analysis(
        self,
        project_id: str,
        analysis_result: Dict[str, Any],
    ) -> None:
        """Update project metrics from a completed analysis job result."""
        parse = analysis_result.get("parse_result", {})
        compliance = analysis_result.get("compliance_report", {})
        prediction = analysis_result.get("prediction", {})

        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
            record = res.scalar_one_or_none()
            if record:
                record.total_rooms = len(parse.get("rooms", []))
                record.total_area_sqft = parse.get("total_area_sqft")
                record.critical_violations = compliance.get("critical_violations", 0)
                record.high_violations = compliance.get("high_violations", 0)
                record.estimated_correction_cost_usd = compliance.get("estimated_total_correction_cost_usd", 0)
                record.submission_readiness_score = prediction.get("submission_readiness_score")

                # Extract FGI approval probability
                for rp in prediction.get("regulator_predictions", []):
                    if rp.get("regulator") == "FGI":
                        record.fgi_approval_probability = rp.get("approval_probability")
                        break

                record.compliance_summary_json = json.dumps({
                    "critical": compliance.get("critical_violations", 0),
                    "high": compliance.get("high_violations", 0),
                    "medium": compliance.get("medium_violations", 0),
                    "low": compliance.get("low_violations", 0),
                    "total_cost_usd": compliance.get("estimated_total_correction_cost_usd", 0),
                    "summary": compliance.get("summary"),
                })
                record.prediction_summary_json = json.dumps({
                    "readiness_score": prediction.get("submission_readiness_score"),
                    "risk_level": prediction.get("overall_risk_level"),
                    "blocking_issues": prediction.get("top_blocking_issues", []),
                    "recommended_actions": prediction.get("recommended_actions", []),
                    "estimated_rework_cost_usd": prediction.get("estimated_rework_cost_usd"),
                    "estimated_rework_days": prediction.get("estimated_rework_days"),
                })
                record.status = "reviewed"
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()
        logger.info("Updated project %s from analysis", project_id)

    async def record_submission(self, project_id: str) -> None:
        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
            record = res.scalar_one_or_none()
            if record:
                record.status = "submitted"
                record.submitted_at = datetime.now(timezone.utc)
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()

    async def record_approval_outcome(
        self,
        project_id: str,
        approval_result: str,
        regulator: Optional[str] = None,
        review_duration_days: Optional[int] = None,
        actual_rework_cost_usd: Optional[float] = None,
    ) -> None:
        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
            record = res.scalar_one_or_none()
            if record:
                record.approval_result = approval_result
                record.approval_regulator = regulator
                record.review_duration_days = review_duration_days
                record.actual_rework_cost_usd = actual_rework_cost_usd
                record.status = approval_result  # "approved" | "rejected" | "conditional"
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()
        logger.info("Recorded outcome for project %s: %s", project_id, approval_result)

    async def generate_share_token(self, project_id: str) -> str:
        """Generate (or return existing) share token for a project."""
        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
            record = res.scalar_one_or_none()
            if not record:
                raise ValueError(f"Project {project_id} not found")
            if not record.share_token:
                record.share_token = secrets.token_urlsafe(16)
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()
            return record.share_token

    async def get_project_by_share_token(self, token: str) -> Optional[Dict[str, Any]]:
        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.share_token == token))
            record = res.scalar_one_or_none()
            return record.to_dict() if record else None

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        async with self._session_factory() as session:
            res = await session.execute(select(ProjectRecord).where(ProjectRecord.id == project_id))
            record = res.scalar_one_or_none()
            return record.to_dict() if record else None

    async def list_projects(
        self,
        org_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        async with self._session_factory() as session:
            query = select(ProjectRecord).order_by(ProjectRecord.created_at.desc()).limit(limit)
            if org_name:
                query = query.where(ProjectRecord.org_name == org_name)
            if status:
                query = query.where(ProjectRecord.status == status)
            res = await session.execute(query)
            return [r.to_dict() for r in res.scalars().all()]

    async def portfolio_risk_stats(self) -> Dict[str, Any]:
        """
        Aggregate portfolio-level risk intelligence for owners and GCs.
        Returns financial exposure, delay risk, and project breakdowns by risk tier.
        """
        async with self._session_factory() as session:
            projects_res = await session.execute(
                select(ProjectRecord).where(
                    ProjectRecord.submission_readiness_score.is_not(None)
                ).order_by(ProjectRecord.estimated_correction_cost_usd.desc())
            )
            projects = list(projects_res.scalars().all())

        total_cost_exposure = sum(
            (p.estimated_correction_cost_usd or 0.0) for p in projects
        )

        # Delay risk: critical violations → ~1.5 weeks each, high → ~0.5 weeks each
        total_delay_weeks = sum(
            (p.critical_violations or 0) * 1.5 + (p.high_violations or 0) * 0.5
            for p in projects
        )

        # Risk tier from readiness score
        def risk_tier(score: Optional[float]) -> str:
            if score is None:
                return "unknown"
            if score >= 85:
                return "low"
            if score >= 65:
                return "medium"
            if score >= 40:
                return "high"
            return "very_high"

        tier_counts: Dict[str, int] = {"very_high": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        tier_exposure: Dict[str, float] = {"very_high": 0.0, "high": 0.0, "medium": 0.0, "low": 0.0, "unknown": 0.0}

        top_risk_projects = []
        for p in projects:
            tier = risk_tier(p.submission_readiness_score)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            tier_exposure[tier] = tier_exposure.get(tier, 0.0) + (p.estimated_correction_cost_usd or 0.0)
            if tier in ("very_high", "high") and len(top_risk_projects) < 5:
                top_risk_projects.append({
                    "project_id": p.id,
                    "name": p.name,
                    "facility_type": p.facility_type,
                    "risk_tier": tier,
                    "readiness_score": p.submission_readiness_score,
                    "cost_exposure_usd": p.estimated_correction_cost_usd or 0.0,
                    "critical_violations": p.critical_violations or 0,
                    "high_violations": p.high_violations or 0,
                    "fgi_approval_probability": p.fgi_approval_probability,
                    "delay_risk_weeks": (p.critical_violations or 0) * 1.5 + (p.high_violations or 0) * 0.5,
                    "status": p.status,
                })

        return {
            "total_projects_analyzed": len(projects),
            "total_cost_exposure_usd": round(total_cost_exposure, 2),
            "total_delay_risk_weeks": round(total_delay_weeks, 1),
            "high_risk_count": tier_counts["very_high"] + tier_counts["high"],
            "risk_tier_counts": tier_counts,
            "risk_tier_exposure_usd": {k: round(v, 2) for k, v in tier_exposure.items()},
            "top_risk_projects": top_risk_projects,
        }

    async def dashboard_stats(self) -> Dict[str, Any]:
        """Aggregate stats for the main dashboard."""
        async with self._session_factory() as session:
            total = await session.scalar(select(func.count(ProjectRecord.id)))
            analyzed = await session.scalar(
                select(func.count(ProjectRecord.id))
                .where(ProjectRecord.status.in_(["reviewed", "submitted", "approved", "rejected"]))
            )
            approved = await session.scalar(
                select(func.count(ProjectRecord.id))
                .where(ProjectRecord.approval_result == "approved")
            )
            avg_readiness = await session.scalar(
                select(func.avg(ProjectRecord.submission_readiness_score))
                .where(ProjectRecord.submission_readiness_score.is_not(None))
            )
            avg_critical = await session.scalar(
                select(func.avg(ProjectRecord.critical_violations))
                .where(ProjectRecord.critical_violations.is_not(None))
            )

        return {
            "total_projects": total or 0,
            "analyzed_projects": analyzed or 0,
            "approved_projects": approved or 0,
            "avg_submission_readiness": round(float(avg_readiness or 0), 1),
            "avg_critical_violations": round(float(avg_critical or 0), 2),
        }
