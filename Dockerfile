# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

# Switch to non-root user
USER appuser

# Collect static files (required for production)
RUN python manage.py collectstatic --noinput --clear || true

# Run Gunicorn - PORT variable is set by Render/Heroku, defaults to 8000
CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --worker-class sync --worker-tmp-dir /dev/shm --max-requests 1000 --max-requests-jitter 50 --timeout 600 --access-logfile - --error-logfile - --log-level info config.wsgi:application"
