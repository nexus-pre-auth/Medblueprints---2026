# MedBlueprints 2026: AI for Healthcare Construction Compliance

MedBlueprints is an advanced AI-powered platform designed to streamline the regulatory compliance process for healthcare construction projects. It leverages a sophisticated 7-layer intelligence system to analyze architectural blueprints, identify compliance issues, predict approval outcomes, and visualize potential rework, ensuring that healthcare facilities are built to the highest standards of safety and compliance.

This repository contains the full source code for the MedBlueprints backend services, frontend application, and machine learning models.

## Key Features

- **Automated Compliance Analysis:** Parses blueprint files (PDF, DWG, IFC) to identify violations against a comprehensive knowledge graph of regulatory codes (FGI, NFPA, ASHRAE, ADA).
- **Predictive Analytics:** Utilizes machine learning to predict the probability of blueprint approval from regulatory bodies, estimate potential rework costs, and identify high-risk design elements.
- **Digital Twin & Graph Technology:** Creates a digital representation of the facility to understand spatial relationships and dependencies, enabling complex compliance checks.
- **LLM-Powered Reasoning:** Employs Large Language Models (LLMs) to interpret complex regulatory text and provide clear, actionable remediation advice.
- **Augmented Reality Visualization:** Generates spatial overlays of compliance issues that can be viewed on-site with AR devices like WebXR and Vision Pro.
- **Strategic Outcome Dataset:** Continuously learns from every project's design and its real-world regulatory outcome to improve the accuracy of its predictive models.

## Tech Stack

The platform is built with a modern, scalable architecture:

| Component | Technology |
|---|---|
| **Backend** | FastAPI, Python 3.11, Uvicorn |
| **Frontend** | Next.js, React, TypeScript, Tailwind CSS |
| **Databases** | PostgreSQL (via Neon), Redis, FAISS, Neo4j |
| **AI/ML** | Anthropic Claude, scikit-learn, XGBoost, OpenCV, NetworkX |
| **Deployment** | Docker, Docker Compose, Caddy |

## Project Structure

```
/Medblueprints---2026
├── frontend/         # Next.js frontend application
├── src/              # FastAPI backend source code
│   ├── api/          # API routes and middleware
│   ├── core/         # Core application settings and configuration
│   ├── engines/      # The 7 core AI/ML intelligence engines
│   ├── models/       # Pydantic data models
│   └── storage/      # Database interaction and storage layers
├── data/             # Sample blueprints and regulatory rule data
├── scripts/          # Helper scripts for DB initialization and data generation
├── main.py           # FastAPI application entry point
├── Dockerfile        # Dockerfile for the backend service
├── docker-compose.yml # Docker Compose for local development
└── README.md         # This file
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An environment file (`.env`) with necessary API keys and configurations (see `src/core/config.py`).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/nexus-pre-auth/Medblueprints---2026.git
    cd Medblueprints---2026
    ```

2.  **Build and run the services using Docker Compose:**
    ```bash
    docker-compose up --build
    ```

This will start the FastAPI backend, the Next.js frontend, and all required database services.

-   **Backend API:** `http://localhost:8000`
-   **API Docs (Swagger UI):** `http://localhost:8000/docs`
-   **Frontend Application:** `http://localhost:3000`

## API Endpoints

The backend exposes a RESTful API for interacting with the MedBlueprints system. Key endpoints include:

-   `POST /api/v1/jobs/analyze`: Upload and initiate a full analysis of a blueprint.
-   `GET /api/v1/jobs/{job_id}`: Poll for the status of an analysis job.
-   `GET /api/v1/jobs/{job_id}/result`: Retrieve the final analysis results.
-   `POST /api/v1/compliance/analyze`: Run a compliance analysis on uploaded blueprint data.
-   `POST /api/v1/predictions/simulate`: Simulate the regulatory approval outcome for a project.
-   `POST /api/v1/visualization/webxr`: Generate AR visualization data for a project.

For a complete list of endpoints and their parameters, please refer to the auto-generated OpenAPI documentation at `/docs`.

## License

This project is licensed under the terms of the [MIT License](LICENSE).
