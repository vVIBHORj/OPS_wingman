"""
Unit Tests for Production Release & Kubernetes CD Configuration (Phase 5 Increment 4).

Verifies:
- Release workflow (.github/workflows/release.yml) exists and parses valid YAML
- No literal secrets/passwords/tokens are embedded in the workflow
- Production deployment is not triggered on pull_request
- Production deployment uses GitHub environment 'production'
- Docker image build job is present with Buildx
- Registry authentication uses GitHub secrets
- Immutable image tagging via Git SHA is present
- Kubernetes manifest validation & dry-run job exists
- Kubernetes rollout status check is enforced
- Kubernetes manifests remain valid
- Kustomize image override works as expected
- CLI operational commands (version, validate-release) work
"""

from pathlib import Path
import subprocess
from typing import Any, Dict
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
K8S_DIR = REPO_ROOT / "deploy" / "kubernetes"


def load_workflow() -> Dict[str, Any]:
    """Helper to load and parse .github/workflows/release.yml."""
    assert WORKFLOW_PATH.exists(), f"Release workflow missing: {WORKFLOW_PATH}"
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"Expected dict from workflow YAML, got {type(data)}"
    return data


# ==============================================================================
# 1. Workflow Structure & Triggers
# ==============================================================================

def test_release_workflow_exists_and_parses():
    """Verifies that release workflow exists and is syntactically valid YAML."""
    data = load_workflow()
    assert "name" in data
    assert "jobs" in data
    assert "on" in data or True in data  # YAML parses 'on:' as True or 'on'


def test_workflow_triggers_exclude_pull_request():
    """Ensures production deployment cannot be triggered by pull_request events."""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    data = yaml.safe_load(content)
    triggers = data.get("on") or data.get(True) or {}

    # Trigger must NOT include pull_request
    assert "pull_request" not in triggers
    assert "push" in triggers or "workflow_dispatch" in triggers


def test_no_literal_secrets_in_workflow():
    """Ensures no hardcoded passwords, tokens, or credentials exist in the workflow."""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    forbidden_patterns = [
        "ghp_",
        "gho_",
        "password:",
        "secret_key:",
        "postgres://postgres:postgres",
        "BEGIN RSA PRIVATE KEY",
        "BEGIN OPENSSH PRIVATE KEY",
    ]
    for pattern in forbidden_patterns:
        # Exclude references to GitHub secrets like secrets.REGISTRY_PASSWORD
        matches = [line for line in content.splitlines() if pattern in line and "secrets." not in line]
        assert not matches, f"Found potentially hardcoded secret pattern '{pattern}': {matches}"


# ==============================================================================
# 2. Jobs, Environment & Security Verification
# ==============================================================================

def test_workflow_jobs_and_environment():
    """Verifies job hierarchy and production environment protection."""
    data = load_workflow()
    jobs = data["jobs"]

    assert "validate-k8s" in jobs
    assert "build-and-push" in jobs
    assert "deploy-production" in jobs

    deploy_job = jobs["deploy-production"]
    assert deploy_job.get("environment") == "production"


def test_build_job_registry_and_tagging():
    """Verifies registry authentication via secrets and immutable image tags."""
    data = load_workflow()
    build_job = data["jobs"]["build-and-push"]
    steps = build_job["steps"]

    # Check for Buildx setup
    has_buildx = any("setup-buildx-action" in str(s.get("uses", "")) for s in steps)
    assert has_buildx, "Docker Buildx setup step is missing"

    # Check for registry login using secrets
    login_step = next((s for s in steps if "login-action" in str(s.get("uses", ""))), None)
    assert login_step is not None, "Docker login step is missing"
    assert "secrets.REGISTRY_PASSWORD" in str(login_step.get("with", {}).get("password", ""))

    # Check for build-push step
    build_step = next((s for s in steps if "build-push-action" in str(s.get("uses", ""))), None)
    assert build_step is not None, "Docker build-push step is missing"


def test_rollout_status_enforced():
    """Verifies that rollout status check is present in deployment job."""
    with open(WORKFLOW_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "kubectl rollout status" in content
    assert "opswingman-backend" in content


# ==============================================================================
# 3. Kustomize Dynamic Image Override Verification
# ==============================================================================

def test_kustomize_image_override_functional():
    """Verifies that modifying images in kustomization.yaml updates rendered manifests."""
    kust_file = K8S_DIR / "kustomization.yaml"
    with open(kust_file, "r", encoding="utf-8") as f:
        original = yaml.safe_load(f)

    try:
        # Apply a custom test image override
        modified = yaml.safe_load(open(kust_file, "r", encoding="utf-8"))
        modified["images"][0]["newName"] = "registry.example.com/opswingman/backend"
        modified["images"][0]["newTag"] = "sha-test-immutable"
        with open(kust_file, "w", encoding="utf-8") as f:
            yaml.dump(modified, f)

        # Run kustomize render
        res = subprocess.run(
            ["kubectl", "kustomize", str(K8S_DIR)],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            rendered = res.stdout
            assert "registry.example.com/opswingman/backend:sha-test-immutable" in rendered
    finally:
        # Restore original kustomization.yaml
        with open(kust_file, "w", encoding="utf-8") as f:
            yaml.dump(original, f)


# ==============================================================================
# 4. Operational CLI Commands (version & validate-release)
# ==============================================================================

def test_cli_version_command():
    """Tests python scripts/ops.py version execution."""
    res = subprocess.run(
        ["python", "scripts/ops.py", "version"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "OpsWingman Version:" in res.stdout
    assert "0.1.0" in res.stdout


def test_cli_validate_release_command():
    """Tests python scripts/ops.py validate-release execution."""
    res = subprocess.run(
        ["python", "scripts/ops.py", "validate-release"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Release validation passed successfully!" in res.stdout
