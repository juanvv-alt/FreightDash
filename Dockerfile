# syntax=docker/dockerfile:1
# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies.
# The cache mount persists downloaded wheels between builds on Render,
# so unchanged requirements cost near-zero on subsequent deploys.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Final production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure startup script can be executed by non-root user.
RUN chmod +x /app/entrypoint.sh

# Ensure static root is pre-created and owned by appuser so collectstatic
# can write to it at runtime. collectstatic runs via entrypoint.sh when
# DATABASE_URL is available, not here during the build.
RUN mkdir -p /app/staticfiles && chown -R appuser:appuser /app/staticfiles

# Stamp the build version into the image (set by CI via --build-arg). Kept near
# the end so it never busts the dependency/code layers above. The running app
# reports these on the Software Updates admin page and the /health endpoint.
ARG GIT_SHA=unknown
ARG BUILD_TIME=unknown
ENV APP_GIT_SHA=$GIT_SHA \
    APP_BUILD_TIME=$BUILD_TIME

# Switch to non-root user
USER appuser

# Run startup orchestration script.
CMD ["/app/entrypoint.sh"]
