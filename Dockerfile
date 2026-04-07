# ===================================
# UmukoziHR Resume Tailor - Server
# Production Docker build for FastAPI
# Full LaTeX support for PDF generation
# Works with: AWS App Runner, ECS
# ===================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies + TeX Live for native PDF compilation
# This makes the image ~2GB but enables fast, reliable PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    # TeX Live for native LaTeX compilation (no external API needed)
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-xetex \
    latexmk \
    # Latin Modern fonts (required for modern resume templates)
    fonts-lmodern \
    lmodern \
    # Playwright / Chromium system dependencies (for portal scanning & JD fetch)
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser (for portal scanning & form analysis)
RUN python -m playwright install chromium --with-deps 2>/dev/null || python -m playwright install chromium

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
ENV ARTIFACTS_DIR=/tmp/artifacts

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command - runs migration then starts server
CMD ["/bin/sh", "/app/start.sh"]