"""
Unit tests for Production Deployment Preflight Validation (Phase 5 Increment 5).

Verifies:
- Standard preflight execution returns PASS with 0 FAIL items
- Missing optional runtime credentials produce WARN, not FAIL
- Missing or invalid Kubernetes manifests trigger FAIL
- Missing CI or release workflows produce FAIL
- Secret hygiene scanner detects absence of tracked credentials
- Immutable image configuration, health probes, and security contexts are verified
"""

import argparse
from pathlib import Path
import shutil
from typing import Any, Dict
import pytest
import yaml

from scripts.ops import cmd_preflight, run_preflight_checks, REPO_ROOT


# ==============================================================================
# 1. Base Preflight & CLI Command Execution
# ==============================================================================

def test_preflight_success_baseline():
    """Verifies that running preflight on the current repository succeeds with 0 FAIL items."""
    res = run_preflight_checks()
    assert res["fail_count"] == 0, f"Expected 0 failures, got {res['fail_count']}: {res['checks']}"
    assert res["pass_count"] >= 15
    assert any(c["name"] == "Core Resources" and c["status"] == "PASS" for c in res["checks"])


def test_preflight_cli_returns_zero():
    """Verifies that cmd_preflight() exits with returncode 0."""
    args = argparse.Namespace()
    ret = cmd_preflight(args)
    assert ret == 0


def test_missing_optional_credentials_produce_warn(monkeypatch):
    """Verifies that missing environment credentials trigger WARN, not FAIL."""
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    monkeypatch.delenv("KUBECONFIG", raising=False)
    monkeypatch.delenv("REGISTRY_PASSWORD", raising=False)

    res = run_preflight_checks()
    assert res["fail_count"] == 0

    secret_check = next((c for c in res["checks"] if c["name"] == "Production Secret Key"), None)
    assert secret_check is not None
    assert secret_check["status"] == "WARN"

    reg_check = next((c for c in res["checks"] if c["name"] == "Registry Credentials"), None)
    assert reg_check is not None
    assert reg_check["status"] == "WARN"


# ==============================================================================
# 2. Failure Detection Scenarios (Isolated Test Environments)
# ==============================================================================

def test_invalid_manifest_produces_fail(tmp_path):
    """Verifies that a missing or corrupted manifest causes preflight to FAIL."""
    # Copy essential structure to tmp_path
    shutil.copy(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    k8s_dir = tmp_path / "deploy" / "kubernetes"
    k8s_dir.mkdir(parents=True)

    # Missing deployment.yaml
    shutil.copy(REPO_ROOT / "deploy" / "kubernetes" / "namespace.yaml", k8s_dir / "namespace.yaml")
    shutil.copy(REPO_ROOT / "deploy" / "kubernetes" / "configmap.yaml", k8s_dir / "configmap.yaml")

    res = run_preflight_checks(repo_root=tmp_path)
    assert res["fail_count"] > 0
    assert any(c["status"] == "FAIL" and "Manifest (deployment.yaml)" in c["name"] for c in res["checks"])


def test_corrupt_yaml_manifest_produces_fail(tmp_path):
    """Verifies that YAML syntax error triggers FAIL."""
    shutil.copy(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    k8s_dir = tmp_path / "deploy" / "kubernetes"
    shutil.copytree(REPO_ROOT / "deploy" / "kubernetes", k8s_dir)

    # Corrupt deployment.yaml
    with open(k8s_dir / "deployment.yaml", "w", encoding="utf-8") as f:
        f.write("invalid: yaml: syntax: [unclosed_bracket")

    res = run_preflight_checks(repo_root=tmp_path)
    assert res["fail_count"] > 0
    corrupt_check = next((c for c in res["checks"] if "deployment.yaml" in c["name"]), None)
    assert corrupt_check is not None
    assert corrupt_check["status"] == "FAIL"


def test_missing_release_workflow_produces_fail(tmp_path):
    """Verifies that missing release workflow causes preflight to FAIL."""
    shutil.copy(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    # Only copy ci.yml
    shutil.copy(REPO_ROOT / ".github" / "workflows" / "ci.yml", workflows_dir / "ci.yml")

    res = run_preflight_checks(repo_root=tmp_path)
    assert res["fail_count"] > 0
    rel_check = next((c for c in res["checks"] if c["name"] == "Release Workflow"), None)
    assert rel_check is not None
    assert rel_check["status"] == "FAIL"


def test_missing_ci_workflow_produces_fail(tmp_path):
    """Verifies that missing CI workflow causes preflight to FAIL."""
    shutil.copy(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    # Only copy release.yml
    shutil.copy(REPO_ROOT / ".github" / "workflows" / "release.yml", workflows_dir / "release.yml")

    res = run_preflight_checks(repo_root=tmp_path)
    assert res["fail_count"] > 0
    ci_check = next((c for c in res["checks"] if c["name"] == "CI Workflow"), None)
    assert ci_check is not None
    assert ci_check["status"] == "FAIL"


# ==============================================================================
# 3. Security, Probes & Image Checks
# ==============================================================================

def test_secret_hygiene_scanner_passes():
    """Verifies that current repository has clean secret hygiene with no tracked private keys."""
    res = run_preflight_checks()
    sec_check = next((c for c in res["checks"] if c["name"] == "Secret Hygiene"), None)
    assert sec_check is not None
    assert sec_check["status"] == "PASS"


def test_immutable_image_configuration_check():
    """Verifies that Kustomize images configuration check passes."""
    res = run_preflight_checks()
    img_check = next((c for c in res["checks"] if c["name"] == "Immutable Image Config"), None)
    assert img_check is not None
    assert img_check["status"] == "PASS"


def test_health_probe_validation_check():
    """Verifies that liveness and readiness probe configuration passes."""
    res = run_preflight_checks()
    probe_check = next((c for c in res["checks"] if c["name"] == "Health Probes"), None)
    assert probe_check is not None
    assert probe_check["status"] == "PASS"


def test_security_context_validation_checks():
    """Verifies that non-root and capability dropping checks pass."""
    res = run_preflight_checks()
    non_root_check = next((c for c in res["checks"] if c["name"] == "Non-Root Security"), None)
    drop_caps_check = next((c for c in res["checks"] if c["name"] == "Drop Capabilities"), None)

    assert non_root_check is not None and non_root_check["status"] == "PASS"
    assert drop_caps_check is not None and drop_caps_check["status"] == "PASS"
