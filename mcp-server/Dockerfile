# =============================================================================
# AI Browsing MCP Server
# Base: python:3.11-slim — minimal footprint, supports all required libraries
# =============================================================================

FROM python:3.11-slim

# Install system dependencies required by readability-lxml and lxml
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libxml2-dev \
        libxslt-dev \
        wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying source to leverage layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8081

# Run with a single Uvicorn worker.
# Note: the in-memory rate limiter in auth.py is only correct for single-worker
# deployments. Switch to a Redis-backed limiter before adding multiple workers.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8081"]
