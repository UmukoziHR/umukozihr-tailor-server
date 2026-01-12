#!/bin/sh
# ===================================
# UmukoziHR Resume Tailor - Startup Script
# Runs database migrations then starts the server
# ===================================

set -e

echo "==================================="
echo "UmukoziHR Tailor Server Starting..."
echo "==================================="

# Run database migrations
echo "Running database migrations..."
python migrate.py

# Start the server
# Use PORT env var (set by App Runner/Render) or default to 8000
PORT=${PORT:-8000}
WORKERS=${WORKERS:-4}

echo "Starting uvicorn on port $PORT with $WORKERS workers..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers $WORKERS
