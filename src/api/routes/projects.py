"""
Projects API — Full Project Lifecycle
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.storage.project_store import ProjectStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])

_store = ProjectStore()


class CreateProjectRequest(BaseModel):
    name: str
    facility_type: str = "hospital"
    state: Optional[str] = None
    city: Optional[str] = None
    owner_email: Optional[str] = None
    org_name: Optional[str] = None


class OutcomeRequest(BaseModel):
    approval_result: str  # "approved" | "rejected" | "conditional"
    regulator: Optional[str] = None
    review_duration_days: Optional[int] = None
    actual_rework_cost_usd: Optional[float] = None


@router.on_event("startup")
async def startup():
    await _store.init()


@router.post("", summary="Create a new project")
async def create_project(request: CreateProjectRequest):
    pid = await _store.create_project(
        name=request.name,
        facility_type=request.facility_type,
        state=request.state,
        city=request.city,
        owner_email=request.owner_email,
        org_name=request.org_name,
    )
    return {"project_id": pid, "status": "draft"}


@router.get("", summary="List all projects")
async def list_projects(
    org: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    projects = await _store.list_projects(org_name=org, status=status, limit=limit)
    return {"projects": projects, "count": len(projects)}


@router.get("/dashboard", summary="Dashboard aggregate statistics")
async def dashboard():
    """Stats for the main architect dashboard."""
    return await _store.dashboard_stats()


@router.get("/portfolio", summary="Portfolio-level construction risk intelligence")
async def portfolio_risk():
    """
    Owner / GC executive view: aggregate financial exposure, delay risk,
    and risk tier breakdown across all analyzed projects.

    This is the endpoint for the Construction Risk Intelligence dashboard —
    showing hospital owners and GCs the total capital at risk before submission.
    """
    return await _store.portfolio_risk_stats()


@router.get("/{project_id}", summary="Get project details")
async def get_project(project_id: str):
    project = await _store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@router.post("/{project_id}/submit", summary="Mark project as submitted to regulator")
async def submit_project(project_id: str):
    project = await _store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await _store.record_submission(project_id)
    return {"project_id": project_id, "status": "submitted"}


@router.post("/{project_id}/outcome", summary="Record regulatory approval outcome")
async def record_outcome(project_id: str, request: OutcomeRequest):
    """
    Record the actual regulatory decision.
    This is the data that trains the AI and builds the strategic moat.
    """
    if request.approval_result not in ("approved", "rejected", "conditional"):
        raise HTTPException(
            status_code=400,
            detail="approval_result must be 'approved', 'rejected', or 'conditional'",
        )
    await _store.record_approval_outcome(
        project_id=project_id,
        approval_result=request.approval_result,
        regulator=request.regulator,
        review_duration_days=request.review_duration_days,
        actual_rework_cost_usd=request.actual_rework_cost_usd,
    )
    return {"project_id": project_id, "outcome_recorded": request.approval_result}
