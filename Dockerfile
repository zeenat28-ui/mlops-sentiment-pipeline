# Multi-stage build for security and minimal size
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY serving/requirements-api.txt .
COPY model/requirements.txt model-requirements.txt

# Combine and install dependencies
RUN pip --default-timeout=120 --retries=10 install --no-cache-dir --upgrade pip && \
    pip --default-timeout=120 --retries=10 install --no-cache-dir -r requirements-api.txt && \
    if [ -f model-requirements.txt ]; then \
        pip --default-timeout=120 --retries=10 install --no-cache-dir -r model-requirements.txt; \
    fi

# Production stage
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 10001 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application
COPY serving/app.py .
COPY model/ model/

# Set permissions
RUN chown -R appuser:appuser /app && \
    chmod -R 755 /app && \
    chmod -R 444 /app/model/*

USER appuser

ENV PORT=8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

# Run the application with dynamic PORT support for Render/Cloud
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
