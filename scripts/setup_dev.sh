#!/usr/bin/env bash
set -e

echo "========================================"
echo "  OpsWingman Local Dev Environment Setup"
echo "========================================"

# 1. Check for .env file
if [ ! -f ".env" ]; then
    echo "[1/3] Creating .env from .env.example..."
    cp .env.example .env
    echo "  -> .env created successfully."
else
    echo "[1/3] .env file already exists."
fi

# 2. Check Docker availability
echo "[2/3] Starting local infrastructure..."
if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres valkey mailpit langfuse-db langfuse
    echo "  -> Infrastructure services running."
else
    echo "  -> Docker not found. Please install and start Docker."
fi

# 3. Summary
echo "[3/3] Ready for Phase 0 Development!"
echo "  - Backend:  uvicorn backend.main:app --reload --port 8000"
echo "  - Frontend: cd frontend && npm run dev"
echo "  - Mailpit:  http://localhost:8025"
echo "  - Langfuse: http://localhost:3001"
echo "========================================"
