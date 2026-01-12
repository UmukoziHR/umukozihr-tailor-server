# ===================================
# UmukoziHR Resume Tailor - Server
# Production Docker build for FastAPI
# Works with: Render, AWS App Runner, ECS
# ===================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create artifacts directory
RUN mkdir -p /app/artifacts

# Make start script executable
RUN chmod +x /app/start.sh

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

# Environment variables (will be overridden by docker-compose or ECS/App Runner)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command - runs migration then starts server
CMD ["/bin/sh", "/app/start.sh"]