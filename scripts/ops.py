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
from typing import Any, Dict, List, Optional

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


def check_migration_ready(timeout: int = 60, repo_root: Optional[Path] = None) -> bool:
    """Checks whether the database schema matches Alembic head revision."""
    import time
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine
    from backend.config import get_settings

    root = repo_root or REPO_ROOT
    poll_interval = 2.0
    start_time = time.time()

    settings = get_settings()
    sync_url = settings.database_sync_url

    print(f"[MIGRATION-READY] Verifying database schema is at Alembic head (timeout: {timeout}s)...")
    alembic_cfg = Config(str(root / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)
    expected_heads = set(script.get_heads())

    while True:
        try:
            engine = create_engine(sync_url, pool_pre_ping=True)
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
            engine.dispose()

            if current_rev and current_rev in expected_heads:
                print(f"[MIGRATION-READY] OK: Database is at head revision '{current_rev}'.")
                return True
            else:
                print(f"[MIGRATION-READY] Current revision is '{current_rev}', expected head in {expected_heads}.")
        except Exception as exc:
            print(f"[MIGRATION-READY] Database connection check: {exc}")

        elapsed = time.time() - start_time
        if elapsed >= timeout:
            print(f"[MIGRATION-READY] FAIL: Schema readiness check timed out after {timeout}s.", file=sys.stderr)
            return False

        time.sleep(poll_interval)


def cmd_check_migration_ready(args: argparse.Namespace) -> int:
    """CLI handler for checking migration readiness."""
    timeout = getattr(args, "timeout", 60)
    ok = check_migration_ready(timeout=timeout)
    return 0 if ok else 1


def cmd_version(args: argparse.Namespace) -> int:
    """Displays project version and Git commit hash."""
    version = "unknown"
    pyproject_path = REPO_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version ="):
                    version = line.split("=")[1].strip().strip('"').strip("'")
                    break

    git_sha = "unknown"
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            git_sha = result.stdout.strip()
    except Exception:
        pass

    print(f"OpsWingman Version: {version}")
    print(f"Git Commit SHA:    {git_sha}")
    return 0


def cmd_validate_release(args: argparse.Namespace) -> int:
    """Validates repository artifacts and Kubernetes manifests for release readiness."""
    import yaml
    print("[RELEASE] Validating release readiness...")

    # 1. Version check
    pyproject_path = REPO_ROOT / "pyproject.toml"
    if not pyproject_path.exists():
        print("[RELEASE] FAIL: pyproject.toml missing", file=sys.stderr)
        return 1
    print("[RELEASE] OK: pyproject.toml present")

    # 2. Kubernetes manifests check
    k8s_dir = REPO_ROOT / "deploy" / "kubernetes"
    required_manifests = [
        "namespace.yaml",
        "configmap.yaml",
        "secret.yaml",
        "deployment.yaml",
        "service.yaml",
        "ingress.yaml",
        "kustomization.yaml",
    ]
    for filename in required_manifests:
        file_path = k8s_dir / filename
        if not file_path.exists():
            print(f"[RELEASE] FAIL: Manifest missing: {filename}", file=sys.stderr)
            return 1
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as exc:
            print(f"[RELEASE] FAIL: YAML syntax error in {filename}: {exc}", file=sys.stderr)
            return 1
    print("[RELEASE] OK: All Kubernetes manifests exist and parse valid YAML")

    # 3. Kustomize render check
    try:
        import subprocess
        res = subprocess.run(
            ["kubectl", "kustomize", str(k8s_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print("[RELEASE] OK: kubectl kustomize renders successfully")
        else:
            print(f"[RELEASE] WARNING: kubectl kustomize returned non-zero ({res.stderr.strip()})")
    except FileNotFoundError:
        print("[RELEASE] INFO: kubectl not installed on path, skipping kustomize render check")

    print("[RELEASE] Release validation passed successfully!")
    return 0


def run_preflight_checks(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Runs a complete battery of production preflight checks without requiring real credentials."""
    import yaml
    import re
    import subprocess
    root = repo_root or REPO_ROOT

    checks: List[Dict[str, str]] = []

    def record(name: str, status: str, message: str) -> None:
        checks.append({"name": name, "status": status, "message": message})

    # 1. pyproject.toml exists and version is valid
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        version = None
        with open(pyproject_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version ="):
                    version = line.split("=")[1].strip().strip('"').strip("'")
                    break
        if version:
            record("Project Metadata", "PASS", f"pyproject.toml found with version {version}")
        else:
            record("Project Metadata", "FAIL", "pyproject.toml missing version field")
    else:
        record("Project Metadata", "FAIL", "pyproject.toml is missing")

    # 2. Dockerfile exists
    dockerfile_path = root / "docker" / "Dockerfile.backend"
    if dockerfile_path.exists():
        record("Dockerfile", "PASS", "docker/Dockerfile.backend present")
    else:
        record("Dockerfile", "FAIL", "docker/Dockerfile.backend is missing")

    # 3. Kubernetes manifests exist and parse YAML
    k8s_dir = root / "deploy" / "kubernetes"
    required_manifests = [
        "namespace.yaml",
        "configmap.yaml",
        "secret.yaml",
        "deployment.yaml",
        "service.yaml",
        "ingress.yaml",
        "kustomization.yaml",
    ]
    manifests_ok = True
    manifest_data: Dict[str, Any] = {}
    for filename in required_manifests:
        p = k8s_dir / filename
        if not p.exists():
            record(f"Manifest ({filename})", "FAIL", f"File missing in {k8s_dir}")
            manifests_ok = False
        else:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    manifest_data[filename] = yaml.safe_load(f)
            except Exception as exc:
                record(f"Manifest ({filename})", "FAIL", f"YAML parse error: {exc}")
                manifests_ok = False

    if manifests_ok:
        record("Kubernetes Manifests", "PASS", "All 7 required Kubernetes manifests present and valid YAML")

    # 4. Kustomize render
    try:
        res = subprocess.run(
            ["kubectl", "kustomize", str(k8s_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            record("Kustomize Render", "PASS", "kubectl kustomize rendered cleanly")
        else:
            record("Kustomize Render", "FAIL", f"kubectl kustomize error: {res.stderr.strip()}")
    except FileNotFoundError:
        record("Kustomize Render", "WARN", "kubectl not available on PATH; skipping dry-run render")

    # 5. Core Kubernetes resources (Namespace, Deployment, Service)
    if "namespace.yaml" in manifest_data and "deployment.yaml" in manifest_data and "service.yaml" in manifest_data:
        ns = manifest_data["namespace.yaml"].get("metadata", {}).get("name")
        dep = manifest_data["deployment.yaml"].get("metadata", {}).get("name")
        svc = manifest_data["service.yaml"].get("metadata", {}).get("name")
        if ns == "opswingman" and dep == "opswingman-backend" and svc == "opswingman-backend-service":
            record("Core Resources", "PASS", f"Namespace '{ns}', Deployment '{dep}', and Service '{svc}' defined")
        else:
            record("Core Resources", "FAIL", f"Mismatched resource names: ns={ns}, dep={dep}, svc={svc}")

    # 6. Deployment Health Probes
    if "deployment.yaml" in manifest_data:
        dep_spec = manifest_data["deployment.yaml"].get("spec", {}).get("template", {}).get("spec", {})
        containers = dep_spec.get("containers", [])
        if containers:
            backend = containers[0]
            liveness = backend.get("livenessProbe", {}).get("httpGet", {}).get("path")
            readiness = backend.get("readinessProbe", {}).get("httpGet", {}).get("path")
            if liveness == "/health/live" and readiness == "/health/ready":
                record("Health Probes", "PASS", "Liveness (/health/live) and readiness (/health/ready) configured")
            else:
                record("Health Probes", "FAIL", f"Probes incorrect: liveness={liveness}, readiness={readiness}")
        else:
            record("Health Probes", "FAIL", "No containers in deployment spec")

    # 7. Deployment Security Context (non-root)
    if "deployment.yaml" in manifest_data:
        pod_sec = manifest_data["deployment.yaml"].get("spec", {}).get("template", {}).get("spec", {}).get("securityContext", {})
        if pod_sec.get("runAsNonRoot") is True and pod_sec.get("runAsUser") == 1000:
            record("Non-Root Security", "PASS", "Pod securityContext enforces runAsNonRoot=True with UID 1000")
        else:
            record("Non-Root Security", "FAIL", f"Pod securityContext invalid: {pod_sec}")

    # 8. Capabilities Drop
    if "deployment.yaml" in manifest_data:
        containers = manifest_data["deployment.yaml"].get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        if containers:
            drop_caps = containers[0].get("securityContext", {}).get("capabilities", {}).get("drop", [])
            if "ALL" in drop_caps:
                record("Drop Capabilities", "PASS", "Container securityContext drops ALL capabilities")
            else:
                record("Drop Capabilities", "FAIL", f"Capabilities not dropped: {drop_caps}")

    # 9. ConfigMap Production DEBUG & ENVIRONMENT
    if "configmap.yaml" in manifest_data:
        cm_data = manifest_data["configmap.yaml"].get("data", {})
        debug_val = cm_data.get("DEBUG")
        env_val = cm_data.get("ENVIRONMENT")
        if debug_val == "false" and env_val == "production":
            record("Production ConfigMap", "PASS", "ConfigMap specifies DEBUG=false and ENVIRONMENT=production")
        else:
            record("Production ConfigMap", "FAIL", f"ConfigMap values invalid: DEBUG={debug_val}, ENVIRONMENT={env_val}")

    # 10 & 11. Production Configuration Validator
    try:
        from backend.config import Settings
        # Test rejection of insecure secret
        try:
            Settings(
                environment="production",
                debug=False,
                app_secret_key="change-this-insecure-secret-key-for-local-dev-only",
            )
            record("Secret Validation", "FAIL", "Production settings accepted default development secret")
        except ValueError:
            record("Secret Validation", "PASS", "Production settings strictly reject default/short secret keys")

        # Test rejection of debug=True
        try:
            Settings(
                environment="production",
                debug=True,
                app_secret_key="a-long-valid-production-secret-key-12345",
            )
            record("Debug Flag Validation", "FAIL", "Production settings accepted debug=True")
        except ValueError:
            record("Debug Flag Validation", "PASS", "Production settings strictly reject debug=True")
    except Exception as exc:
        record("Settings Module", "FAIL", f"Could not load or test Settings: {exc}")

    # 12. Required production environment variables represented in schema
    try:
        from backend.config import Settings
        fields = Settings.model_fields.keys()
        expected_fields = {"app_secret_key", "database_url", "database_sync_url", "backend_port", "valkey_url", "environment", "debug"}
        missing_fields = expected_fields - set(fields)
        if not missing_fields:
            record("Config Schema", "PASS", "All required operational environment parameters represented")
        else:
            record("Config Schema", "FAIL", f"Missing settings schema fields: {missing_fields}")
    except Exception as exc:
        record("Config Schema", "FAIL", f"Failed to inspect Settings fields: {exc}")

    # 13. Secret Hygiene in Tracked Files
    try:
        tracked_files = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()

        secret_violations = []
        forbidden_patterns = [
            re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            re.compile(r"\bghp_[0-9a-zA-Z]{36}\b"),
            re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b"),
        ]

        for tf in tracked_files:
            if tf == ".env" or tf.endswith(".key") or tf.endswith(".pem"):
                secret_violations.append(f"Forbidden file tracked: {tf}")
            tf_path = root / tf
            if tf_path.is_file() and tf_path.stat().st_size < 1_000_000:
                try:
                    content = tf_path.read_text(encoding="utf-8", errors="ignore")
                    for pattern in forbidden_patterns:
                        if pattern.search(content):
                            secret_violations.append(f"Secret pattern found in tracked file {tf}")
                            break
                except Exception:
                    pass

        if not secret_violations:
            record("Secret Hygiene", "PASS", "No private keys, tokens, or .env files tracked in Git")
        else:
            record("Secret Hygiene", "FAIL", f"Secret leak detected: {secret_violations}")
    except Exception as exc:
        record("Secret Hygiene", "WARN", f"Could not audit git tracked files: {exc}")

    # 14 & 15. Workflows
    ci_wf = root / ".github" / "workflows" / "ci.yml"
    release_wf = root / ".github" / "workflows" / "release.yml"
    if ci_wf.exists():
        record("CI Workflow", "PASS", ".github/workflows/ci.yml present")
    else:
        record("CI Workflow", "FAIL", ".github/workflows/ci.yml missing")

    if release_wf.exists():
        record("Release Workflow", "PASS", ".github/workflows/release.yml present")
    else:
        record("Release Workflow", "FAIL", ".github/workflows/release.yml missing")

    # 16. Alembic configuration
    alembic_ini = root / "alembic.ini"
    if alembic_ini.exists():
        record("Alembic Config", "PASS", "alembic.ini present")
    else:
        record("Alembic Config", "FAIL", "alembic.ini missing")

    # 17. Application health routes exist in backend
    try:
        from backend.main import app
        route_paths = [getattr(r, "path", "") for r in app.routes if getattr(r, "path", None)]
        if "/health" in route_paths and "/health/live" in route_paths and "/health/ready" in route_paths:
            record("Health Endpoints", "PASS", "Routes /health, /health/live, /health/ready verified in application")
        else:
            record("Health Endpoints", "FAIL", f"Missing health routes in backend: {route_paths}")
    except Exception as exc:
        record("Health Endpoints", "FAIL", f"Failed to inspect application routes: {exc}")

    # 18. Kustomize images block for immutable SHA tagging
    if "kustomization.yaml" in manifest_data:
        images_block = manifest_data["kustomization.yaml"].get("images", [])
        if images_block and any(img.get("name") == "opswingman/backend" for img in images_block):
            record("Immutable Image Config", "PASS", "Kustomize 'images' block supports dynamic immutable SHA tagging")
        else:
            record("Immutable Image Config", "FAIL", "Kustomize missing 'images' block for opswingman/backend")

    # 19. Staging Overlay Packaging
    staging_overlay_dir = root / "deploy" / "kubernetes" / "overlays" / "staging"
    staging_kust = staging_overlay_dir / "kustomization.yaml"
    if staging_kust.exists():
        try:
            res_staging = subprocess.run(
                ["kubectl", "kustomize", str(staging_overlay_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            if res_staging.returncode == 0:
                rendered_output = res_staging.stdout
                if "name: opswingman-staging" in rendered_output and "ENVIRONMENT: staging" in rendered_output:
                    record("Staging Overlay", "PASS", "Staging overlay renders cleanly with namespace opswingman-staging and ENVIRONMENT=staging")
                else:
                    record("Staging Overlay", "FAIL", "Staging overlay rendered without expected namespace or environment")
            else:
                record("Staging Overlay", "FAIL", f"Staging kustomize render failed: {res_staging.stderr.strip()}")
        except FileNotFoundError:
            record("Staging Overlay", "WARN", "kubectl not available on PATH; skipping staging overlay render check")
    else:
        record("Staging Overlay", "FAIL", "deploy/kubernetes/overlays/staging/kustomization.yaml missing")

    # 20. Migration Concurrency Strategy
    migration_job_path = root / "deploy" / "kubernetes" / "migration-job.yaml"
    if migration_job_path.exists():
        if "configmap.yaml" in manifest_data:
            cm_data = manifest_data["configmap.yaml"].get("data", {})
            auto_migrate = cm_data.get("AUTO_MIGRATE")
            wait_for_migration = cm_data.get("WAIT_FOR_MIGRATION")
            if auto_migrate == "false" and wait_for_migration == "true":
                record("Migration Strategy", "PASS", "Multi-replica config disables AUTO_MIGRATE and enables WAIT_FOR_MIGRATION with dedicated migration job")
            else:
                record("Migration Strategy", "WARN", f"ConfigMap has AUTO_MIGRATE={auto_migrate}, WAIT_FOR_MIGRATION={wait_for_migration}; recommend AUTO_MIGRATE=false in multi-replica deployments")
        else:
            record("Migration Strategy", "PASS", "deploy/kubernetes/migration-job.yaml present")
    else:
        record("Migration Strategy", "FAIL", "deploy/kubernetes/migration-job.yaml missing")

    # 21. Ingress Modern Specification
    if "ingress.yaml" in manifest_data:
        ing_spec = manifest_data["ingress.yaml"].get("spec", {})
        ing_class = ing_spec.get("ingressClassName")
        if ing_class == "nginx":
            record("Ingress Configuration", "PASS", "Ingress configures standard spec.ingressClassName='nginx'")
        else:
            record("Ingress Configuration", "WARN", f"Ingress missing spec.ingressClassName (got: {ing_class})")

    # 22, 23, 24. Optional Environment Credentials (WARN if absent, PASS if present)
    app_secret_env = os.getenv("APP_SECRET_KEY")
    if app_secret_env and len(app_secret_env.strip()) >= 16 and app_secret_env != "change-this-insecure-secret-key-for-local-dev-only":
        record("Production Secret Key", "PASS", "APP_SECRET_KEY configured in environment")
    else:
        record("Production Secret Key", "WARN", "APP_SECRET_KEY not set in local environment (required in production Secret)")

    kubeconfig_env = os.getenv("KUBECONFIG")
    default_kubeconfig = Path.home() / ".kube" / "config"
    if kubeconfig_env or default_kubeconfig.exists():
        record("Cluster Kubeconfig", "PASS", "Kubeconfig credentials detected")
    else:
        record("Cluster Kubeconfig", "WARN", "Kubeconfig not configured in local environment (required for CD deployment)")

    registry_pass_env = os.getenv("REGISTRY_PASSWORD")
    if registry_pass_env:
        record("Registry Credentials", "PASS", "REGISTRY_PASSWORD detected in environment")
    else:
        record("Registry Credentials", "WARN", "REGISTRY_PASSWORD not set in local environment (required for container push)")

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    warn_count = sum(1 for c in checks if c["status"] == "WARN")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {
        "checks": checks,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
    }


def cmd_preflight(args: argparse.Namespace) -> int:
    """Runs full production preflight checks."""
    result = run_preflight_checks()
    print("=" * 70)
    print("OpsWingman Production Preflight Validation")
    print("=" * 70)
    for c in result["checks"]:
        print(f"[{c['status']}] {c['name']}: {c['message']}")
    print("-" * 70)
    print(f"Summary: {result['pass_count']} PASS, {result['warn_count']} WARN, {result['fail_count']} FAIL")
    if result["fail_count"] > 0:
        print("Result: PREFLIGHT FAILED (Resolve FAIL items before deployment)")
        print("=" * 70)
        return 1
    else:
        print("Result: PREFLIGHT PASSED (Repository is deployment-ready)")
        print("=" * 70)
        return 0


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

    # version
    subparsers.add_parser("version", help="Show application version and Git commit hash")

    # validate-release
    subparsers.add_parser("validate-release", help="Validate repository artifacts and manifests for release")

    # check-migration-ready
    migrate_ready_parser = subparsers.add_parser("check-migration-ready", help="Verify database schema is at head revision")
    migrate_ready_parser.add_argument("--timeout", type=int, default=60, help="Seconds to wait before timing out (default: 60)")

    # preflight
    subparsers.add_parser("preflight", help="Run full production preflight validation")

    args = parser.parse_args()

    handlers = {
        "check-config": cmd_check_config,
        "check-health": cmd_check_health,
        "migrate": cmd_migrate,
        "migration-status": cmd_migration_status,
        "check-migration-ready": cmd_check_migration_ready,
        "version": cmd_version,
        "validate-release": cmd_validate_release,
        "preflight": cmd_preflight,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
