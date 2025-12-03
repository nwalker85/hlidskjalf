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

# Create non-root user
RUN useradd -m -u 1000 odin && \
    chown -R odin:odin /app

USER odin

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8900/health || exit 1

EXPOSE 8900

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8900"]