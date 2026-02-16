# ============================================================================
# Hliðskjálf - Odin's High Seat
# The throne from which all Nine Realms are observed
# ============================================================================

FROM python:3.11-slim

LABEL maintainer="Ravenhelm Team"
LABEL description="Hliðskjálf Control Plane API"
LABEL ravenhelm.workload="control-plane"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files needed for installation
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir pip --upgrade && \
    pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/

# Create ravenhelm user (UID/GID 1001) with docker group access
# GID 0 (root group) is needed for Docker socket access on macOS Docker Desktop
RUN groupadd -g 1001 ravenhelm && \
    groupadd -g 999 docker && \
    useradd -m -u 1001 -g ravenhelm -G docker,root ravenhelm && \
    chown -R ravenhelm:ravenhelm /app

USER ravenhelm

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8900/health || exit 1

EXPOSE 8900

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8900"]