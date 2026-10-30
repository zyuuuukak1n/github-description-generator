# ==============================================================================
# Dockerfile: GitHub Description Generator
# Architecture: Multi-stage build, minimal attack surface, non-root execution
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Runtime (Defensive, Minimal, Non-root)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

# Install curl for healthcheck and setup non-root system user
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 appgroup \
    && useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code with ownership
COPY --chown=appuser:appgroup app /app/app
COPY --chown=appuser:appgroup static /app/static

# Drop root privileges
USER appuser

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8085

EXPOSE 8085

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8085/health || exit 1

# Start Uvicorn ASGI Server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]

