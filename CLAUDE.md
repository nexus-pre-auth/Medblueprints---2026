# CLAUDE.md — MedBlueprints 2026

AI assistant reference guide for the MedBlueprints codebase. Read this before making changes.

---

## What This Project Does

MedBlueprints is an **AI-powered regulatory compliance platform for healthcare facility construction**. It takes blueprint images/PDFs and tells you whether they'll pass regulatory approval — before you submit.

**Core value proposition**: A single hospital project is $200M–$2B. One compliance revision cycle costs $500K–$2M. This saves that.

**Customers**:
- General contractors and architects — analyze single projects pre-submission
- Hospital owners/executives — portfolio-level capital-at-risk intelligence

---

## Tech Stack

### Backend
- **FastAPI 0.115** + **Uvicorn** — async Python web framework
- **Python 3.11** — language
- **Pydantic v2** — data validation and settings
- **SQLAlchemy 2.0 async** — ORM (SQLite dev, PostgreSQL prod)
- **SlowAPI** — rate limiting (10 req/min default)

### AI / ML
- **Anthropic Claude API** (`claude-opus-4-6`) — LLM compliance reasoning (Layer 4)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — semantic rule matching
- **FAISS** (CPU) — vector similarity search over regulatory rules
- **XGBoost** — approval probability prediction model
- **OpenCV 4.10** + **Pillow** — blueprint image analysis (Layer 1)
- **NetworkX** — in-memory facility and regulatory graphs
- **Neo4j** — optional production graph database backend

### Frontend
- **Next.js 15** (App Router) + **React 19** + **TypeScript 5.6**
- **Tailwind CSS 3.4** — styling
- **Recharts 2.13** — charts
- **Lucide React** — icons

### Infrastructure
- **Docker** + **Docker Compose v2**
- **Caddy 2** — reverse proxy with auto-TLS (Let's Encrypt)
- **PostgreSQL 16** — production relational database
- **Redis 7** — async job queue
- **SQLite** — local development database (`./medblueprints.db`)

---

## Directory Structure

```
/
├── main.py                         # FastAPI app entry point — lifespan, router registration
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Multi-stage backend build
├── docker-compose.yml              # Local dev: API, frontend, postgres, redis, neo4j
├── docker-compose.prod.yml         # Production: + Caddy, internal networks only
├── Caddyfile                       # Caddy config: medblueprints.com + api.medblueprints.com
├── deploy.sh                       # One-shot provisioning script (Ubuntu 22.04 / Debian 12)
├── demo.py                         # Standalone demo runner
├── .env.example                    # All environment variables with defaults
│
├── src/
│   ├── core/
│   │   ├── config.py               # Pydantic BaseSettings — all env vars loaded here
│   │   └── limiter.py              # SlowAPI rate limiter instance
│   │
│   ├── models/                     # Pure Pydantic data models (no business logic)
│   │   ├── blueprint.py            # RoomType, DetectedRoom, BlueprintParseResult
│   │   ├── compliance.py           # RegulatoryRule, ComplianceViolation, ComplianceReport
│   │   ├── facility.py             # FacilityGraph, FacilityNode, FacilityEdge
│   │   └── prediction.py          # ApprovalPrediction, ProjectOutcome, PredictionFeatures
│   │
│   ├── engines/                    # The 7 intelligence layers (core business logic)
│   │   ├── cv_blueprint_engine.py  # Layer 1: CV image → structured geometry
│   │   ├── facility_graph.py       # Layer 2: Rooms → digital twin graph
│   │   ├── regulatory_knowledge_graph.py  # Layer 3: Rule DB + FAISS vector search
│   │   ├── llm_compliance_engine.py       # Layer 4: Claude violation interpretation
│   │   ├── approval_prediction.py  # Layer 5: XGBoost approval probability
│   │   ├── ar_visualization.py     # Layer 6: WebXR / Vision Pro / SVG overlays
│   │   ├── pipeline.py             # Orchestrator: sequences layers 1–6
│   │   ├── blueprint_ingestion.py  # File upload → image/OCR extraction
│   │   └── state_regulatory_engine.py  # State-specific rule loading (50 states + DC)
│   │
│   ├── api/
│   │   ├── middleware/
│   │   │   └── api_key.py          # Optional API key auth (REQUIRE_API_KEY env)
│   │   └── routes/
│   │       ├── blueprints.py       # POST /blueprints/parse
│   │       ├── compliance.py       # POST /compliance/analyze, GET /compliance/rules
│   │       ├── predictions.py      # POST /predictions/simulate, /outcomes/record
│   │       ├── visualization.py    # POST /visualization/webxr|vision-pro|svg
│   │       ├── jobs.py             # POST /jobs/analyze (async), poll, result
│   │       ├── projects.py         # CRUD, dashboard stats, portfolio risk
│   │       └── states.py           # GET /states/{state}/rules|compliance-stack
│   │
│   └── storage/                    # Persistence layers (all async SQLAlchemy)
│       ├── outcome_dataset.py      # Layer 7: project_outcomes table (the strategic moat)
│       ├── graph_store.py          # NetworkX in-memory / optional Neo4j backend
│       ├── job_store.py            # jobs table — async job tracking
│       └── project_store.py        # projects table — lifecycle and snapshots
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx                    # Landing page
│       │   └── (dashboard)/               # Route group (dashboard layout)
│       │       ├── upload/page.tsx         # Blueprint upload form
│       │       ├── dashboard/page.tsx      # Overview metrics
│       │       ├── projects/page.tsx       # Project list
│       │       ├── projects/[id]/page.tsx  # Project detail
│       │       ├── projects/[id]/result/   # Compliance report viewer
│       │       ├── compliance/page.tsx     # Violation browser
│       │       ├── simulate/page.tsx       # Approval simulator
│       │       ├── portfolio/page.tsx      # Executive risk dashboard
│       │       └── dataset/page.tsx        # Outcome dataset analytics
│       ├── components/                     # Sidebar, compliance viewer, simulator UI
│       ├── lib/api.ts                      # Fetch utilities (NEXT_PUBLIC_API_URL)
│       └── types/                          # TypeScript type definitions
│
├── data/
│   ├── regulatory_rules/
│   │   ├── fgi_rules.json          # FGI (Facility Guidelines Institute)
│   │   ├── nfpa_rules.json         # NFPA fire safety
│   │   ├── ashrae_rules.json       # ASHRAE ventilation / HVAC
│   │   ├── ada_rules.json          # ADA accessibility
│   │   ├── joint_commission_rules.json
│   │   ├── generated_rules.json    # Programmatically expanded rules
│   │   └── states/                 # Per-state rule overrides (24 states populated)
│   ├── sample_blueprints/          # Demo blueprint images
│   ├── ar_outputs/                 # SVG floor plans generated by AR engine
│   └── approval_model.joblib       # Serialized XGBoost model
│
├── scripts/
│   ├── db_init.sql                 # PostgreSQL setup (uuid-ossp, pg_trgm extensions)
│   ├── train_model.py              # Retrain XGBoost approval model
│   ├── expand_rules.py             # Generate rule variations → generated_rules.json
│   ├── seed_training_data.py       # Populate outcome_dataset for model training
│   └── generate_sample_blueprint.py  # Create synthetic blueprint for testing
│
└── tests/
    └── test_pipeline.py            # pytest integration tests for full pipeline
```

---

## Environment Variables

All variables are defined in `src/core/config.py` (Pydantic BaseSettings). Copy `.env.example` to `.env`.

| Variable | Default | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Yes** (Layer 4 LLM engine) |
| `CLAUDE_MODEL` | `claude-opus-4-6` | No |
| `DATABASE_URL` | `sqlite+aiosqlite:///./medblueprints.db` | No |
| `USE_NEO4J` | `false` | No |
| `NEO4J_URI` | — | Only if USE_NEO4J=true |
| `NEO4J_USER` | — | Only if USE_NEO4J=true |
| `NEO4J_PASSWORD` | — | Only if USE_NEO4J=true |
| `EMBEDDINGS_MODEL` | `all-MiniLM-L6-v2` | No |
| `FAISS_INDEX_PATH` | `./data/regulatory_index.faiss` | No |
| `MODEL_PATH` | `./data/approval_model.joblib` | No |
| `AR_OUTPUT_PATH` | `./data/ar_outputs` | No |
| `WEBXR_BASE_URL` | `http://localhost:8000/ar` | No |
| `LOG_LEVEL` | `INFO` | No |
| `REQUIRE_API_KEY` | `false` | No |
| `DEMO_API_KEY` | `demo-medblueprints-2026` | No |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend |

---

## Running Locally

### Backend (without Docker)
```bash
pip install -r requirements.txt
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Full stack (Docker Compose)
```bash
cp .env.example .env
# Edit .env with secrets
docker compose up
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

### With optional Neo4j graph backend
```bash
docker compose --profile graph up
```

### Production deployment
```bash
# On a fresh Ubuntu 22.04 / Debian 12 server:
bash deploy.sh
# Or manually:
docker compose -f docker-compose.prod.yml up -d
```

---

## Development Commands

### Backend
```bash
# Run tests
pytest tests/

# Run a quick demo (no server needed)
python demo.py

# Retrain the approval prediction model
python scripts/train_model.py

# Expand regulatory rule variations
python scripts/expand_rules.py

# Seed outcome dataset with synthetic data
python scripts/seed_training_data.py

# Generate a sample blueprint for testing
python scripts/generate_sample_blueprint.py
```

### Frontend
```bash
cd frontend
npm run dev          # Development server on :3000
npm run build        # Production build
npm run type-check   # TypeScript validation
npm start            # Production server (after build)
```

---

## Intelligence Pipeline (The 7 Layers)

Data flows through these layers in order. Each layer produces output consumed by the next.

```
Upload (jobs.py / blueprints.py)
    ↓
[Layer 1] cv_blueprint_engine.py
    Canny edge detection → Hough wall detection → room segmentation
    → BlueprintParseResult (rooms, objects, corridors with geometry)
    ↓
[Layer 2] facility_graph.py
    Polygon adjacency detection → NetworkX room relationship graph
    → FacilityGraph (digital twin)
    ↓
[Layer 3] regulatory_knowledge_graph.py
    Load JSON rules → FAISS vector index → semantic rule retrieval
    + deterministic constraint evaluation
    ↓
[Layer 4] llm_compliance_engine.py
    Claude interprets violations → human-readable explanations + cost estimates
    → ComplianceReport
    ↓
[Layer 5] approval_prediction.py
    Extract 20+ features → XGBoost classifier → per-regulator probabilities
    → ApprovalPrediction (FGI / AHJ / State / Joint Commission)
    ↓
[Layer 6] ar_visualization.py
    Room geometry + violations → color-coded spatial overlays
    → WebXR JSON | Vision Pro scene | SVG floor plan
    ↓
[Layer 7] outcome_dataset.py (storage)
    Record all results to project_outcomes table
    → Builds the training dataset (the strategic moat)
```

**Key insight**: Layers 1–3 are deterministic. Layer 4 (Claude) adds reasoning and catches false positives. Layer 7 accumulates outcome data that improves Layer 5 over time.

**Orchestrator**: `src/engines/pipeline.py` — `MedBlueprintsPipeline.run()` sequences all layers for a single project.

---

## API Endpoints

Base: `http://localhost:8000/api/v1`

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service info |
| GET | `/health` | Health check |
| POST | `/blueprints/parse` | Parse blueprint image/PDF |
| POST | `/compliance/analyze` | Run compliance analysis |
| GET | `/compliance/rules` | Browse rules (filter by room_type, source) |
| POST | `/predictions/simulate` | Approval probability simulator |
| POST | `/predictions/outcomes/record` | Store approval outcome |
| POST | `/visualization/webxr` | Generate WebXR overlay |
| POST | `/visualization/vision-pro` | Apple Vision Pro scene |
| POST | `/visualization/svg` | SVG floor plan with heatmap |
| POST | `/jobs/analyze` | Start async full-pipeline job |
| GET | `/jobs/{job_id}` | Poll job status + progress |
| GET | `/jobs/{job_id}/result` | Fetch completed result |
| GET | `/jobs/` | List recent jobs |
| POST | `/projects/` | Create project |
| GET | `/projects/` | List projects (paginated) |
| GET | `/projects/dashboard` | Dashboard stats |
| GET | `/projects/portfolio` | Executive portfolio risk view |
| GET | `/projects/{project_id}` | Project detail |
| POST | `/projects/{project_id}/outcome` | Record approval outcome |
| GET | `/states/` | All 50 states + DC feed |
| GET | `/states/available` | States with rule data |
| GET | `/states/{state}/rules` | State-specific rules |
| GET | `/states/{state}/compliance-stack` | Federal + state rules combined |
| POST | `/states/{state}/analyze` | Analyze room against state rules |
| GET | `/graph/stats` | Regulatory design graph stats |
| GET | `/graph/violations/common` | Most common violations |
| GET | `/graph/approval-rates` | Approval rate by violation count |

**Rate limiting**: 10 requests/minute per endpoint (SlowAPI).

**Auth**: Optional. Set `REQUIRE_API_KEY=true` and pass `X-API-Key` header.

---

## Data Models (Key Types)

### `BlueprintParseResult` (`src/models/blueprint.py`)
Output of Layer 1 (CV engine). Contains detected rooms (with polygon geometry, area, `RoomType` enum), objects (doors, HVAC, medical gas), and corridors.

**`RoomType` enum**: `operating_room`, `icu`, `emergency`, `sterile_core`, `nurse_station`, `patient_room`, `corridor`, `mechanical`, `utility`, `waiting`, `pharmacy`, `laboratory`, `imaging`, `unknown`

### `ComplianceReport` (`src/models/compliance.py`)
Output of Layer 4 (LLM engine). Per-room violations with severity, cost estimate, and Claude-generated explanation. Call `.compute_totals()` to aggregate.

**`ViolationSeverity`**: `critical`, `high`, `medium`, `low`, `advisory`

**`RuleSource`**: `FGI`, `NFPA`, `AIA`, `ASHRAE`, `Joint Commission`, `ADA`, `state`, `local`

### `ApprovalPrediction` (`src/models/prediction.py`)
Output of Layer 5 (XGBoost). Contains overall `readiness_score`, `risk_level`, per-regulator probabilities (`FGI`, `AHJ`, `State`, `Joint Commission`), top issues, and recommended actions.

### `ProjectOutcome` (`src/models/prediction.py`)
Stored to the outcome dataset. Includes all project metrics + actual approval result. This is what builds the training moat.

---

## Regulatory Data

Rules are stored as JSON files in `data/regulatory_rules/`:

- **Federal**: FGI, NFPA, ASHRAE, ADA, Joint Commission
- **State-specific**: 24 states populated (`data/regulatory_rules/states/CA.json`, `TX.json`, etc.)
- **Generated**: `generated_rules.json` — programmatic rule expansions via `scripts/expand_rules.py`

To add a new state: create `data/regulatory_rules/states/{STATE_CODE}.json` following the pattern of existing state files (array of rule objects matching the `RegulatoryRule` model).

The `RegulatoryKnowledgeGraph` (Layer 3) loads all rules at startup and builds a FAISS index for semantic search. Re-initialization is required to pick up new rule files.

---

## Database Schema

Tables are created automatically by SQLAlchemy on startup.

| Table | Storage Layer | Purpose |
|---|---|---|
| `project_outcomes` | `outcome_dataset.py` | Every analyzed project (the moat) |
| `projects` | `project_store.py` | Project metadata + analysis snapshots |
| `jobs` | `job_store.py` | Async job tracking (status, progress, result) |

**Dev**: SQLite (`./medblueprints.db`) — zero config, works out of the box.

**Prod**: PostgreSQL 16. Run `scripts/db_init.sql` first to enable uuid-ossp and pg_trgm extensions.

---

## Code Conventions

### Architecture Principles
1. **Models ≠ business logic** — `src/models/` contains only Pydantic data shapes. No computation.
2. **Engines do the work** — All business logic lives in `src/engines/`. Routes call engines.
3. **Singletons in route modules** — Engines (knowledge graphs, compliance engines) are module-level singletons to avoid re-initialization on every request. Don't instantiate them in endpoint functions.
4. **Async throughout** — All database calls use SQLAlchemy async. All FastAPI endpoints are `async def`.
5. **Graceful fallbacks** — Demo parse if OpenCV unavailable. In-memory graphs if Neo4j fails. Baseline heuristics if XGBoost model missing.

### Adding a New API Endpoint
1. Add route function to the appropriate `src/api/routes/` file
2. Apply `@limiter.limit("10/minute")` decorator
3. Input/output types must be Pydantic models from `src/models/`
4. Register router in `main.py` if adding a new router file

### Adding a New Intelligence Layer
1. Create `src/engines/new_layer.py` with a class following the engine pattern
2. Add the layer to `src/engines/pipeline.py` in the correct sequence
3. Update the `PipelineResult` model if it produces new output

### Frontend Conventions
- All pages are in `src/app/(dashboard)/` under the dashboard route group
- API calls go through `src/lib/api.ts` utilities (uses `NEXT_PUBLIC_API_URL`)
- Dynamic routes: `projects/[id]/page.tsx` pattern
- Reusable UI primitives in `src/components/ui/`

### Environment / Config
- Never hardcode secrets or URLs — use `src/core/config.py`
- Add new env vars to `config.py` (Pydantic BaseSettings) AND `.env.example`

---

## Testing

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test
pytest tests/test_pipeline.py::test_name
```

`tests/test_pipeline.py` is a full integration test — it exercises the entire pipeline (Layers 1–6) using demo/sample data. Tests do not require a real ANTHROPIC_API_KEY (demo mode bypasses LLM calls).

---

## Deployment Checklist

For production deployments:

1. Set all required env vars (especially `ANTHROPIC_API_KEY`, `DATABASE_URL` with PostgreSQL, `POSTGRES_PASSWORD`)
2. Run `scripts/db_init.sql` against PostgreSQL to enable required extensions
3. Ensure `data/approval_model.joblib` exists (run `scripts/train_model.py` if not)
4. Update `Caddyfile` with your actual domain names
5. Run `docker compose -f docker-compose.prod.yml up -d`
6. Verify health: `curl https://api.yourdomain.com/health`

---

## Strategic Notes for AI Assistants

- **The outcome dataset is the moat.** Every endpoint that records a `ProjectOutcome` is feeding the ML training pipeline. Don't remove or skip `outcome_dataset.py` calls.
- **Claude is Layer 4 only.** The LLM is used for *interpretation* of already-detected violations — not for primary detection. Deterministic rule evaluation (Layer 3) finds violations; Claude explains them and catches false positives.
- **State rules are seed data.** The 24 state JSON files are manually curated. They need monitoring as regulations change. Don't treat them as authoritative forever.
- **XGBoost model needs real data.** `data/approval_model.joblib` was trained on synthetic data. Real predictive accuracy requires real project outcomes flowing through the system.
- **Demo mode exists for testing.** Pass `use_demo=true` to `/blueprints/parse` for a synthetic result without needing a real blueprint or OpenCV.
