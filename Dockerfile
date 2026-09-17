# =============================================================================
# ClassFellow Web - Multi-Stage Production Dockerfile (Category 17)
# Multi-stage build running on python:3.12-slim with non-root security isolation
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder (Compiles C-extensions and prepares isolated virtualenv)
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn whitenoise

# -----------------------------------------------------------------------------
# Stage 2: Final Minimal Runtime Image
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings_prod \
    PYTHONPATH="/app:/app/classfellow_web"

# Install minimal runtime dependencies (libpq5 for PostgreSQL, netcat & curl for probes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-traditional \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Run as non-root system user (UID 1001)
RUN groupadd -g 1001 classfellow && \
    useradd -u 1001 -g classfellow -s /bin/bash -m classfellow

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY . /app

# Ensure directories exist and grant ownership to non-root user
RUN mkdir -p /app/classfellow_web/staticfiles \
             /app/classfellow_web/media \
             /app/data/backups && \
    chmod +x /app/docker/entrypoint.sh && \
    chown -R classfellow:classfellow /app /opt/venv

USER classfellow

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]
