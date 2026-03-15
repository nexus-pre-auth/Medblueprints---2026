"""
Async Job Store
================
Blueprint analysis is CPU-heavy.  Instead of making architects wait for
a synchronous HTTP response, we:
  1. Accept the file upload → return a job_id immediately (< 200ms)
  2. Process the full pipeline in a FastAPI BackgroundTask (or Celery worker)
  3. Store status + results in the job store
  4. Architect polls GET /jobs/{job_id} or connects via WebSocket

Job lifecycle:
  pending → processing → completed | failed

Architecture note:
  This module uses SQLite/SQLAlchemy for simplicity.
  For production, Redis (via Celery) is recommended for distributed workers.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict

from sqlalchemy import Column, String, Text, DateTime, Float
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import select

from src.core.config import settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class JobRecord(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, default=JobStatus.PENDING.value)
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # current pipeline stage
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    facility_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, default="hospital")
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "stage": self.stage,
            "filename": self.filename,
            "facility_type": self.facility_type,
            "progress_pct": self.progress_pct,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error_message,
            "has_result": self.result_json is not None,
        }


class JobStore:
    """Async job status store for blueprint analysis pipeline jobs."""

    def __init__(self, database_url: Optional[str] = None):
        db_url = database_url or settings.database_url
        self._engine = create_async_engine(db_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def create_job(
        self,
        filename: str,
        facility_type: str = "hospital",
        project_id: Optional[str] = None,
    ) -> str:
        """Create a new pending job. Returns job_id."""
        job_id = str(uuid.uuid4())
        pid = project_id or job_id[:12]
        record = JobRecord(
            id=job_id,
            project_id=pid,
            filename=filename,
            facility_type=facility_type,
            status=JobStatus.PENDING.value,
        )
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()
        logger.info("Created job %s for file '%s'", job_id, filename)
        return job_id

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        stage: Optional[str] = None,
        progress_pct: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        async with self._session_factory() as session:
            result = await session.execute(select(JobRecord).where(JobRecord.id == job_id))
            record = result.scalar_one_or_none()
            if record:
                record.status = status.value
                record.updated_at = datetime.now(timezone.utc)
                if stage:
                    record.stage = stage
                record.progress_pct = progress_pct
                if error:
                    record.error_message = error
                if status == JobStatus.COMPLETED:
                    record.completed_at = datetime.now(timezone.utc)
                    record.progress_pct = 100.0
                await session.commit()

    async def save_result(self, job_id: str, result: Dict[str, Any]) -> None:
        async with self._session_factory() as session:
            res = await session.execute(select(JobRecord).where(JobRecord.id == job_id))
            record = res.scalar_one_or_none()
            if record:
                record.result_json = json.dumps(result)
                record.status = JobStatus.COMPLETED.value
                record.progress_pct = 100.0
                record.completed_at = datetime.now(timezone.utc)
                record.updated_at = datetime.now(timezone.utc)
                await session.commit()
        logger.info("Saved result for job %s", job_id)

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(select(JobRecord).where(JobRecord.id == job_id))
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return record.to_dict()

    async def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(select(JobRecord).where(JobRecord.id == job_id))
            record = result.scalar_one_or_none()
            if record is None or record.result_json is None:
                return None
            return json.loads(record.result_json)

    async def list_jobs(self, limit: int = 50) -> list:
        async with self._session_factory() as session:
            result = await session.execute(
                select(JobRecord)
                .order_by(JobRecord.created_at.desc())
                .limit(limit)
            )
            return [r.to_dict() for r in result.scalars().all()]
