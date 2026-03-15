"""
Outcome Dataset — The Strategic Moat
======================================
Every project that runs through MedBlueprints is stored as a structured
outcome record.  Over time this becomes the largest dataset of healthcare
facility design decisions and regulatory approval outcomes in the world.

This dataset:
  1. Trains the approval prediction model
  2. Answers design intelligence questions (e.g., "what OR layouts have the
     highest approval rate in California?")
  3. Powers the Regulatory Design Graph (see graph_store.py)
  4. Is the primary defensible competitive moat

Storage: SQLite (dev) → PostgreSQL (prod) via SQLAlchemy async
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    create_engine, select, func,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

from src.core.config import settings
from src.models.prediction import ProjectOutcome

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class ProjectOutcomeRecord(Base):
    __tablename__ = "project_outcomes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String, index=True)
    facility_type: Mapped[str] = mapped_column(String)
    total_rooms: Mapped[int] = mapped_column(Integer)
    total_area_sqft: Mapped[float] = mapped_column(Float)
    critical_violations: Mapped[int] = mapped_column(Integer)
    high_violations: Mapped[int] = mapped_column(Integer)
    medium_violations: Mapped[int] = mapped_column(Integer)
    low_violations: Mapped[int] = mapped_column(Integer)
    operating_room_count: Mapped[int] = mapped_column(Integer)
    icu_bed_count: Mapped[int] = mapped_column(Integer)
    estimated_correction_cost_usd: Mapped[float] = mapped_column(Float)
    approval_result: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    regulator: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_rework_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rework_changes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    submitted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extra_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_outcome(self) -> ProjectOutcome:
        return ProjectOutcome(
            project_id=self.project_id,
            facility_type=self.facility_type,
            total_rooms=self.total_rooms,
            total_area_sqft=self.total_area_sqft,
            critical_violations=self.critical_violations,
            high_violations=self.high_violations,
            medium_violations=self.medium_violations,
            low_violations=self.low_violations,
            operating_room_count=self.operating_room_count,
            icu_bed_count=self.icu_bed_count,
            estimated_correction_cost_usd=self.estimated_correction_cost_usd,
            approval_result=self.approval_result,
            regulator=self.regulator,
            review_duration_days=self.review_duration_days,
            actual_rework_cost_usd=self.actual_rework_cost_usd,
            rework_changes=json.loads(self.rework_changes) if self.rework_changes else None,
            submitted_at=self.submitted_at,
            reviewed_at=self.reviewed_at,
            metadata=json.loads(self.extra_metadata) if self.extra_metadata else {},
        )


class OutcomeDataset:
    """
    Async data access layer for the project outcome dataset.

    Usage (in FastAPI):
        dataset = OutcomeDataset()
        await dataset.init()
        await dataset.save_outcome(outcome)
        outcomes = await dataset.load_all()
    """

    def __init__(self, database_url: Optional[str] = None):
        db_url = database_url or settings.database_url
        self._engine = create_async_engine(db_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("OutcomeDataset using database: %s", db_url)

    async def init(self) -> None:
        """Create tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("OutcomeDataset tables ready")

    async def save_outcome(self, outcome: ProjectOutcome) -> str:
        """Store a project outcome. Returns the record ID."""
        record = ProjectOutcomeRecord(
            project_id=outcome.project_id,
            facility_type=outcome.facility_type,
            total_rooms=outcome.total_rooms,
            total_area_sqft=outcome.total_area_sqft,
            critical_violations=outcome.critical_violations,
            high_violations=outcome.high_violations,
            medium_violations=outcome.medium_violations,
            low_violations=outcome.low_violations,
            operating_room_count=outcome.operating_room_count,
            icu_bed_count=outcome.icu_bed_count,
            estimated_correction_cost_usd=outcome.estimated_correction_cost_usd,
            approval_result=outcome.approval_result,
            regulator=outcome.regulator,
            review_duration_days=outcome.review_duration_days,
            actual_rework_cost_usd=outcome.actual_rework_cost_usd,
            rework_changes=json.dumps(outcome.rework_changes) if outcome.rework_changes else None,
            submitted_at=outcome.submitted_at,
            reviewed_at=outcome.reviewed_at,
            extra_metadata=json.dumps(outcome.metadata) if outcome.metadata else None,
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
            logger.debug("Saved outcome for project %s", outcome.project_id)
            return record.id

    async def update_approval_result(
        self,
        project_id: str,
        approval_result: str,
        regulator: Optional[str] = None,
        review_duration_days: Optional[int] = None,
        actual_rework_cost_usd: Optional[float] = None,
        rework_changes: Optional[List[str]] = None,
    ) -> None:
        """Record the actual regulatory decision when received."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ProjectOutcomeRecord)
                .where(ProjectOutcomeRecord.project_id == project_id)
                .order_by(ProjectOutcomeRecord.created_at.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()
            if record:
                record.approval_result = approval_result
                record.reviewed_at = datetime.now(timezone.utc).isoformat()
                if regulator:
                    record.regulator = regulator
                if review_duration_days is not None:
                    record.review_duration_days = review_duration_days
                if actual_rework_cost_usd is not None:
                    record.actual_rework_cost_usd = actual_rework_cost_usd
                if rework_changes is not None:
                    record.rework_changes = json.dumps(rework_changes)
                await session.commit()
                logger.info("Updated approval result for project %s: %s", project_id, approval_result)

    async def load_all(self) -> List[ProjectOutcome]:
        async with self._session_factory() as session:
            result = await session.execute(select(ProjectOutcomeRecord))
            return [r.to_outcome() for r in result.scalars().all()]

    async def load_labeled(self) -> List[ProjectOutcome]:
        """Return only outcomes with a confirmed approval_result (for model training)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ProjectOutcomeRecord)
                .where(ProjectOutcomeRecord.approval_result.is_not(None))
            )
            return [r.to_outcome() for r in result.scalars().all()]

    async def get_dataset_stats(self) -> Dict[str, Any]:
        """High-level stats about the outcome dataset."""
        async with self._session_factory() as session:
            total = await session.scalar(select(func.count(ProjectOutcomeRecord.id)))
            labeled = await session.scalar(
                select(func.count(ProjectOutcomeRecord.id))
                .where(ProjectOutcomeRecord.approval_result.is_not(None))
            )
            approved = await session.scalar(
                select(func.count(ProjectOutcomeRecord.id))
                .where(ProjectOutcomeRecord.approval_result == "approved")
            )
            rejected = await session.scalar(
                select(func.count(ProjectOutcomeRecord.id))
                .where(ProjectOutcomeRecord.approval_result == "rejected")
            )
            avg_cost = await session.scalar(
                select(func.avg(ProjectOutcomeRecord.actual_rework_cost_usd))
                .where(ProjectOutcomeRecord.actual_rework_cost_usd.is_not(None))
            )

        return {
            "total_projects": total or 0,
            "labeled_projects": labeled or 0,
            "approved_projects": approved or 0,
            "rejected_projects": rejected or 0,
            "approval_rate": round((approved or 0) / max(labeled or 1, 1) * 100, 1),
            "avg_rework_cost_usd": round(float(avg_cost or 0), 2),
            "model_training_ready": (labeled or 0) >= 50,
        }

    async def design_intelligence_query(
        self,
        facility_type: Optional[str] = None,
        room_type_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Answer design intelligence questions from the outcome dataset.
        Powers queries like:
          - "What OR configurations have the highest approval rate?"
          - "Average rework cost for ICU violations?"
        """
        async with self._session_factory() as session:
            base_query = select(ProjectOutcomeRecord).where(
                ProjectOutcomeRecord.approval_result.is_not(None)
            )
            if facility_type:
                base_query = base_query.where(
                    ProjectOutcomeRecord.facility_type == facility_type
                )
            result = await session.execute(base_query)
            records = result.scalars().all()

        if not records:
            return {"message": "Insufficient data for analysis", "projects_analyzed": 0}

        approved = [r for r in records if r.approval_result == "approved"]
        rejected = [r for r in records if r.approval_result == "rejected"]

        def avg(lst, attr):
            vals = [getattr(r, attr) for r in lst if getattr(r, attr) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        return {
            "projects_analyzed": len(records),
            "approval_rate_pct": round(len(approved) / len(records) * 100, 1),
            "approved": {
                "count": len(approved),
                "avg_critical_violations": avg(approved, "critical_violations"),
                "avg_rework_cost_usd": avg(approved, "actual_rework_cost_usd"),
                "avg_review_days": avg(approved, "review_duration_days"),
            },
            "rejected": {
                "count": len(rejected),
                "avg_critical_violations": avg(rejected, "critical_violations"),
                "avg_rework_cost_usd": avg(rejected, "actual_rework_cost_usd"),
                "avg_review_days": avg(rejected, "review_duration_days"),
            },
            "facility_type": facility_type or "all",
        }
