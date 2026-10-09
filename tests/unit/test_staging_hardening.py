"""
Unit tests for Staging Deployment Hardening (Phase 5 Increment 7).

Verifies:
- Staging Kustomize overlay renders cleanly with namespace 'opswingman-staging' and ENVIRONMENT='staging'
- Staging Ingress configuration uses spec.ingressClassName='nginx' and isolated staging hostname
- Migration Job manifest exists, valid YAML, and enforces secure non-root runtime
- Migration concurrency resolution: AUTO_MIGRATE=false, WAIT_FOR_MIGRATION=true
- CLI command check-migration-ready and helper check_migration_ready()
- Entrypoint script includes WAIT_FOR_MIGRATION branch
- Staging workflow exists with environment 'staging' and workflow_dispatch trigger
"""

import argparse
import subprocess
from pathlib import Path
from typing import Any, Dict
import pytest
import yaml

from scripts.ops import (
    REPO_ROOT,
    check_migration_ready,
    cmd_check_migration_ready,
    run_preflight_checks,
)

STAGING_DIR = REPO_ROOT / "deploy" / "kubernetes" / "overlays" / "staging"
K8S_DIR = REPO_ROOT / "deploy" / "kubernetes"


# ==============================================================================
# 1. Staging Kustomize Overlay Rendering Tests
# ==============================================================================

def test_staging_overlay_renders_cleanly():
    """Verifies that kubectl kustomize deploy/kubernetes/overlays/staging/ renders valid YAML."""
    res = subprocess.run(
        ["kubectl", "kustomize", str(STAGING_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"kubectl kustomize failed: {res.stderr}"

    rendered = res.stdout
    docs = list(yaml.safe_load_all(rendered))
    assert len(docs) >= 6

    # 1. Namespace
    ns_doc = next((d for d in docs if d.get("kind") == "Namespace"), None)
    assert ns_doc is not None
    assert ns_doc["metadata"]["name"] == "opswingman-staging"

    # 2. ConfigMap
    cm_doc = next((d for d in docs if d.get("kind") == "ConfigMap"), None)
    assert cm_doc is not None
    assert cm_doc["metadata"]["namespace"] == "opswingman-staging"
    assert cm_doc["data"]["ENVIRONMENT"] == "staging"
    assert cm_doc["data"]["AUTO_MIGRATE"] == "false"
    assert cm_doc["data"]["WAIT_FOR_MIGRATION"] == "true"
    assert "staging.opswingman.io" in cm_doc["data"]["BACKEND_CORS_ORIGINS"]

    # 3. Deployment & Image Override
    dep_doc = next((d for d in docs if d.get("kind") == "Deployment"), None)
    assert dep_doc is not None
    assert dep_doc["metadata"]["namespace"] == "opswingman-staging"
    container = dep_doc["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "ghcr.io/opswingman/backend:staging-latest"

    # 4. Ingress
    ing_doc = next((d for d in docs if d.get("kind") == "Ingress"), None)
    assert ing_doc is not None
    assert ing_doc["metadata"]["namespace"] == "opswingman-staging"
    assert ing_doc["spec"]["ingressClassName"] == "nginx"
    assert ing_doc["spec"]["rules"][0]["host"] == "api-staging.opswingman.example.com"


# ==============================================================================
# 2. Migration Job Manifest Tests
# ==============================================================================

def test_migration_job_manifest_validity():
    """Verifies that deploy/kubernetes/migration-job.yaml exists and enforces secure execution."""
    job_path = K8S_DIR / "migration-job.yaml"
    assert job_path.is_file(), f"Expected {job_path} to exist"

    with open(job_path, "r", encoding="utf-8") as f:
        job = yaml.safe_load(f)

    assert job["apiVersion"] == "batch/v1"
    assert job["kind"] == "Job"
    assert job["metadata"]["name"] == "opswingman-db-migrate"
    assert job["spec"]["template"]["spec"]["restartPolicy"] == "OnFailure"

    pod_sec = job["spec"]["template"]["spec"]["securityContext"]
    assert pod_sec["runAsNonRoot"] is True
    assert pod_sec["runAsUser"] == 1000

    container = job["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["python", "scripts/ops.py", "migrate"]
    assert "ALL" in container["securityContext"]["capabilities"]["drop"]


# ==============================================================================
# 3. Migration Concurrency & Readiness Checks
# ==============================================================================

def test_check_migration_ready_success():
    """Verifies that check_migration_ready() succeeds when database is at head."""
    is_ready = check_migration_ready(timeout=5)
    assert is_ready is True


def test_cmd_check_migration_ready_cli():
    """Verifies that CLI cmd_check_migration_ready() returns 0."""
    args = argparse.Namespace(timeout=5)
    code = cmd_check_migration_ready(args)
    assert code == 0


def test_entrypoint_script_has_wait_for_migration():
    """Verifies that docker/entrypoint.sh handles WAIT_FOR_MIGRATION."""
    entrypoint_path = REPO_ROOT / "docker" / "entrypoint.sh"
    content = entrypoint_path.read_text(encoding="utf-8")

    assert "WAIT_FOR_MIGRATION" in content
    assert "check-migration-ready" in content


# ==============================================================================
# 4. Staging Deployment Workflow Tests
# ==============================================================================

def test_staging_workflow_file_exists_and_configured():
    """Verifies .github/workflows/deploy-staging.yml exists and targets staging environment."""
    wf_path = REPO_ROOT / ".github" / "workflows" / "deploy-staging.yml"
    assert wf_path.is_file()

    with open(wf_path, "r", encoding="utf-8") as f:
        wf = yaml.safe_load(f)

    on_trigger = wf.get("on") or wf.get(True)
    assert on_trigger is not None and "workflow_dispatch" in on_trigger
    jobs = wf["jobs"]
    deploy_job = jobs.get("deploy-staging")
    assert deploy_job is not None
    assert deploy_job["environment"] == "staging"


# ==============================================================================
# 5. Preflight Strategy Verification
# ==============================================================================

def test_preflight_verifies_staging_and_migration_strategy():
    """Verifies that preflight check covers Staging Overlay and Migration Strategy."""
    res = run_preflight_checks()
    assert res["fail_count"] == 0

    staging_check = next((c for c in res["checks"] if c["name"] == "Staging Overlay"), None)
    assert staging_check is not None
    assert staging_check["status"] == "PASS"

    mig_check = next((c for c in res["checks"] if c["name"] == "Migration Strategy"), None)
    assert mig_check is not None
    assert mig_check["status"] == "PASS"

    ing_check = next((c for c in res["checks"] if c["name"] == "Ingress Configuration"), None)
    assert ing_check is not None
    assert ing_check["status"] == "PASS"


# ==============================================================================
# 6. Safety & Consistency Hardening Tests (Phase 5 Increment 7.1)
# ==============================================================================

def test_migration_job_has_no_hardcoded_namespace():
    """Verifies migration-job.yaml does not hardcode namespace, ensuring portability to staging."""
    job_path = K8S_DIR / "migration-job.yaml"
    with open(job_path, "r", encoding="utf-8") as f:
        job = yaml.safe_load(f)
    assert "namespace" not in job.get("metadata", {}), "migration-job.yaml should not hardcode namespace"


def test_staging_workflow_image_synchronization():
    """Verifies that deploy-staging.yml synchronizes target image across build, migration, and deployment."""
    wf_path = REPO_ROOT / ".github" / "workflows" / "deploy-staging.yml"
    with open(wf_path, "r", encoding="utf-8") as f:
        wf = yaml.safe_load(f)

    # 1. build-staging-image job outputs target_image
    build_job = wf["jobs"].get("build-staging-image")
    assert build_job is not None
    assert "target_image" in build_job["outputs"]

    # 2. deploy-staging depends on build-staging-image
    deploy_job = wf["jobs"].get("deploy-staging")
    assert deploy_job is not None
    assert "build-staging-image" in deploy_job.get("needs", [])

    # 3. Read steps to verify image synchronization and failure guard
    steps = deploy_job.get("steps", [])
    step_runs = " ".join(s.get("run", "") for s in steps)
    assert "migration-job.yaml" in step_runs
    assert "TARGET_IMAGE" in step_runs
    assert "wait --for=condition=complete" in step_runs
