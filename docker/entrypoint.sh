#!/usr/bin/env bash
set -e

# ==============================================================================
# OpsWingman Container Entrypoint Script
# ==============================================================================

echo "[ENTRYPOINT] Starting OpsWingman backend container..."

# Run database migrations if AUTO_MIGRATE is enabled (default: true)
if [ "${AUTO_MIGRATE:-true}" = "true" ]; then
    echo "[ENTRYPOINT] Running database migrations (alembic upgrade head)..."
    alembic upgrade head || {
        echo "[ENTRYPOINT] ERROR: Database migration failed. Exiting."
        exit 1
    }
    echo "[ENTRYPOINT] Database migrations completed successfully."
fi

# Execute CMD passed from Dockerfile or docker-compose
echo "[ENTRYPOINT] Launching application command: $@"
exec "$@"
