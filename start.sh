#!/bin/sh
# ===================================
# UmukoziHR Resume Tailor - Startup Script
# Runs database migrations then starts the server
# ===================================

set -e

echo "==================================="
echo "UmukoziHR Tailor Server Starting..."
echo "==================================="

# Verify TeX Live / latexmk is installed
echo "Checking PDF compilation tools..."
if command -v latexmk > /dev/null 2>&1; then
    echo "  latexmk: $(which latexmk)"
    latexmk --version | head -1
else
    echo "  WARNING: latexmk not found! PDF compilation will fail."
fi

if command -v pdflatex > /dev/null 2>&1; then
    echo "  pdflatex: $(which pdflatex)"
else
    echo "  WARNING: pdflatex not found!"
fi

# Ensure artifacts directory exists and is writable
ARTIFACTS_DIR=${ARTIFACTS_DIR:-/tmp/artifacts}
mkdir -p "$ARTIFACTS_DIR"
echo "Artifacts directory: $ARTIFACTS_DIR"

# Run database migrations
echo "Running database migrations..."
python migrate.py

# Start the server
# Use PORT env var (set by App Runner/Render) or default to 8000
PORT=${PORT:-8000}
WORKERS=${WORKERS:-4}

echo "Starting uvicorn on port $PORT with $WORKERS workers..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers $WORKERS
