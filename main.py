"""
MedBlueprints Advanced AI Architecture
========================================
FastAPI application entry point.

Intelligence layers:
  1. Computer Vision Blueprint Engine   — geometry extraction
  2. Digital Facility Graph             — room relationship graph
  3. Regulatory Knowledge Graph         — structured rule database
  4. LLM Compliance Reasoning (Claude)  — violation interpretation
  5. Approval Prediction Model          — submission readiness score
  6. AR Visualization Engine            — spatial compliance overlays
  7. Outcome Dataset                    — the strategic moat

Run:
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from src.core.limiter import limiter

from src.core.config import settings
from src.api.routes import blueprints, compliance, predictions, visualization
from src.api.routes import jobs, projects
from src.api.middleware.api_key import APIKeyMiddleware, load_api_keys
from src.storage.outcome_dataset import OutcomeDataset
from src.storage.graph_store import RegulatoryDesignGraphStore
from src.storage.job_store import JobStore
from src.storage.project_store import ProjectStore

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Shared singletons
outcome_dataset = OutcomeDataset()
design_graph = RegulatoryDesignGraphStore()
job_store = JobStore()
project_store = ProjectStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, clean up on shutdown."""
    logger.info("MedBlueprints AI Architecture starting up...")

    # Initialize all database tables
    await outcome_dataset.init()
    await job_store.init()
    await project_store.init()
    logger.info("All storage layers ready")

    # Attach singletons to app state for access in routes
    app.state.outcome_dataset = outcome_dataset
    app.state.design_graph = design_graph

    logger.info("MedBlueprints AI Architecture ready")
    yield
    logger.info("MedBlueprints shutting down")


app = FastAPI(
    title="MedBlueprints AI Architecture",
    description="""
## MedBlueprints — AI Regulatory Infrastructure for Healthcare Construction

### Intelligence Layers

| Layer | Engine | Purpose |
|-------|--------|---------|
| 1 | Computer Vision Blueprint Engine | Extract room geometry from images/PDFs |
| 2 | Digital Facility Graph | Model room relationships and system connections |
| 3 | Regulatory Knowledge Graph | FGI, NFPA, ASHRAE, ADA rules as queryable graph |
| 4 | LLM Compliance Engine (Claude) | Interpret violations, suggest remediation |
| 5 | Approval Prediction Model | Estimate submission readiness and approval probability |
| 6 | AR Visualization Engine | Spatial compliance overlays for WebXR/Vision Pro |
| 7 | Outcome Dataset | Strategic moat: every project's design + outcome |

### Quick Start

1. **Parse a blueprint**: `POST /blueprints/parse` (or `use_demo=true`)
2. **Run compliance analysis**: `POST /compliance/analyze`
3. **Simulate approval**: `POST /predictions/simulate`
4. **Generate AR overlay**: `POST /visualization/webxr`
5. **Record outcome**: `POST /predictions/outcomes/record` (builds the moat)
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth (off by default for local dev; set REQUIRE_API_KEY=true in prod)
_require_auth = os.environ.get("REQUIRE_API_KEY", "false").lower() == "true"
app.add_middleware(
    APIKeyMiddleware,
    require_auth=_require_auth,
    valid_keys=load_api_keys(),
)

# Register routers
app.include_router(blueprints.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(visualization.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "MedBlueprints AI Architecture",
        "version": "1.0.0",
        "status": "operational",
        "intelligence_layers": [
            "Computer Vision Blueprint Engine",
            "Digital Facility Graph",
            "Regulatory Knowledge Graph (FGI + NFPA + ASHRAE + ADA)",
            "LLM Compliance Reasoning Engine (Claude)",
            "Approval Prediction Model",
            "AR Visualization Engine (WebXR + Vision Pro + SVG)",
            "Outcome Dataset + Regulatory Design Graph",
        ],
        "docs": "/docs",
        "openapi": "/openapi.json",
        "key_endpoints": {
            "upload_and_analyze": "POST /api/v1/jobs/analyze",
            "poll_job_status": "GET  /api/v1/jobs/{job_id}",
            "get_result": "GET  /api/v1/jobs/{job_id}/result",
            "compliance_analysis": "POST /api/v1/compliance/analyze",
            "approval_simulation": "POST /api/v1/predictions/simulate",
            "record_outcome": "POST /api/v1/projects/{id}/outcome",
            "ar_overlay": "POST /api/v1/visualization/webxr",
        },
    }


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/graph/stats", tags=["graph"])
async def design_graph_stats():
    """Statistics for the Regulatory Design Graph (the strategic moat)."""
    return design_graph.graph_stats()


@app.get("/api/v1/graph/violations/common", tags=["graph"])
async def common_violations(
    room_type: str = None,
    top_k: int = 10,
):
    """Most frequently violated rules across all ingested projects."""
    return {
        "most_common_violations": design_graph.most_common_violations(room_type, top_k),
        "description": "Rule IDs ranked by frequency of violation across all projects",
    }


@app.get("/api/v1/graph/approval-rates", tags=["graph"])
async def approval_rates_by_violations():
    """Approval rate by critical violation count — powered by the outcome dataset."""
    return design_graph.approval_rate_by_violation_count()
