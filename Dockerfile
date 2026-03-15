# MedBlueprints API — Production Docker Image
# Multi-stage build for minimal final image size

# ── Stage 1: builder ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for OpenCV, Tesseract, and scientific libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenCV runtime
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1-mesa-glx \
    # Tesseract OCR
    tesseract-ocr \
    tesseract-ocr-eng \
    # PDF rendering
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/ar_outputs data/regulatory_rules data/sample_blueprints

# Non-root user for security
RUN useradd --create-home --shell /bin/bash medblueprints && \
    chown -R medblueprints:medblueprints /app
USER medblueprints

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
