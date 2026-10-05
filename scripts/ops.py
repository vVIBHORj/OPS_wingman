"""
OpsWingman Unified Operational Management CLI (Phase 5).

Provides lightweight CLI commands for configuration validation, health checks,
and database migration management without heavy external frameworks.
"""

import argparse
import os
import sys
from pathlib import Path
import urllib.request
import urllib.error
import json

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alembic.config import Config
from alembic import command


def cmd_check_config(args: argparse.Namespace) -> int:
    """Validates configuration settings against development or production requirements."""
    from backend.config import Settings

    env_target = args.env or os.getenv("ENVIRONMENT", "development")
    print(f"[CONFIG] Validating configuration for target environment: '{env_target}'...")

    try:
        settings = Settings(environment=env_target)
        print("[CONFIG] Validation succeeded!")
        print(f"  App Name:     {settings.app_name}")
        print(f"  Environment:  {settings.environment}")
        print(f"  Debug Mode:   {settings.debug}")
        print(f"  Log Level:    {settings.log_level}")
        print(f"  API Bind:     {settings.backend_host}:{settings.backend_port}")
        print(f"  CORS Origins: {settings.backend_cors_origins}")
        print(f"  DB Sync URL:  {settings.database_sync_url.split('@')[-1] if '@' in settings.database_sync_url else 'configured'}")
        print(f"  Docs Enabled: {settings.docs_enabled}")
        return 0
    except Exception as exc:
        print(f"[CONFIG] Validation failed: {exc}", file=sys.stderr)
        return 1


def cmd_check_health(args: argparse.Namespace) -> int:
    """Queries application liveness and readiness endpoints."""
    base_url = args.url.rstrip("/")
    live_url = f"{base_url}/health"
    ready_url = f"{base_url}/health/ready"

    print(f"[HEALTH] Checking liveness at {live_url}...")
    try:
        req = urllib.request.Request(live_url, headers={"User-Agent": "OpsWingman-CLI"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            print(f"[HEALTH] Liveness: OK ({res.status}) -> {data}")
    except Exception as exc:
        print(f"[HEALTH] Liveness check failed: {exc}", file=sys.stderr)
        return 1

    print(f"[HEALTH] Checking readiness at {ready_url}...")
    try:
        req = urllib.request.Request(ready_url, headers={"User-Agent": "OpsWingman-CLI"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            print(f"[HEALTH] Readiness: OK ({res.status}) -> {data}")
            return 0
    except urllib.error.HTTPError as exc:
        print(f"[HEALTH] Readiness check returned error status {exc.code}: {exc.read().decode()}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[HEALTH] Readiness check failed: {exc}", file=sys.stderr)
        return 1


def cmd_migrate(args: argparse.Namespace) -> int:
    """Applies all pending database migrations up to head."""
    print("[MIGRATION] Running Alembic upgrade head...")
    try:
        alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        print("[MIGRATION] Successfully upgraded to head.")
        return 0
    except Exception as exc:
        print(f"[MIGRATION] Upgrade failed: {exc}", file=sys.stderr)
        return 1


def cmd_migration_status(args: argparse.Namespace) -> int:
    """Reports current migration revision and available heads."""
    print("[MIGRATION] Inspecting Alembic revision status...")
    try:
        alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
        print("--- Current Revision ---")
        command.current(alembic_cfg)
        print("--- Migration Heads ---")
        command.heads(alembic_cfg)
        return 0
    except Exception as exc:
        print(f"[MIGRATION] Status check failed: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ops",
        description="OpsWingman Operational Management CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-config
    cfg_parser = subparsers.add_parser("check-config", help="Validate environment configuration")
    cfg_parser.add_argument("--env", choices=["development", "staging", "production"], help="Override environment to test")

    # check-health
    health_parser = subparsers.add_parser("check-health", help="Check application liveness and readiness")
    health_parser.add_argument("--url", default="http://localhost:8000", help="Base URL of OpsWingman API")

    # migrate
    subparsers.add_parser("migrate", help="Run database migrations (alembic upgrade head)")

    # migration-status
    subparsers.add_parser("migration-status", help="Show current Alembic revision and heads")

    args = parser.parse_args()

    handlers = {
        "check-config": cmd_check_config,
        "check-health": cmd_check_health,
        "migrate": cmd_migrate,
        "migration-status": cmd_migration_status,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
