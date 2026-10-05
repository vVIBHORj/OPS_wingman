"""
Unit tests for Kubernetes Deployment Manifests (Phase 5 Increment 3).

Verifies:
- All required manifest files exist and parse valid YAML
- Deployment configuration, port 8000, probes (/health/live, /health/ready)
- ClusterIP Service and label selectors
- Ingress routing to backend Service
- Production environment variables (DEBUG=false, ENVIRONMENT=production)
- Secret templates contain only placeholders without real credentials
- SecurityContext (non-root, drop capabilities)
- RollingUpdate deployment strategy and resource limits
"""

from pathlib import Path
from typing import Any, Dict
import pytest
import yaml

MANIFEST_DIR = Path(__file__).parent.parent.parent / "deploy" / "kubernetes"


def load_yaml(filename: str) -> Dict[str, Any]:
    """Helper to load and parse a YAML manifest file."""
    path = MANIFEST_DIR / filename
    assert path.exists(), f"Manifest file missing: {path}"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"Expected dict from YAML file {filename}, got {type(data)}"
    return data


# ==============================================================================
# 1. File Structure & Manifest Existence
# ==============================================================================

def test_manifest_files_exist():
    """Verifies that all required Kubernetes manifest files exist."""
    required_files = [
        "namespace.yaml",
        "configmap.yaml",
        "secret.yaml",
        "deployment.yaml",
        "service.yaml",
        "ingress.yaml",
        "kustomization.yaml",
    ]
    for filename in required_files:
        path = MANIFEST_DIR / filename
        assert path.is_file(), f"Expected file {filename} to exist in deploy/kubernetes/"


# ==============================================================================
# 2. Namespace & Metadata Tests
# ==============================================================================

def test_namespace_manifest():
    """Verifies namespace specification."""
    data = load_yaml("namespace.yaml")
    assert data["apiVersion"] == "v1"
    assert data["kind"] == "Namespace"
    assert data["metadata"]["name"] == "opswingman"


# ==============================================================================
# 3. ConfigMap & Secret Separation Tests
# ==============================================================================

def test_configmap_production_settings():
    """Verifies ConfigMap has safe production defaults (DEBUG=false, ENVIRONMENT=production)."""
    cm = load_yaml("configmap.yaml")
    assert cm["apiVersion"] == "v1"
    assert cm["kind"] == "ConfigMap"
    assert cm["metadata"]["name"] == "opswingman-backend-config"
    assert cm["metadata"]["namespace"] == "opswingman"

    data = cm["data"]
    assert data["ENVIRONMENT"] == "production"
    assert data["DEBUG"] == "false"
    assert data["BACKEND_PORT"] == "8000"
    assert data["VALKEY_HOST"] == "opswingman-valkey"
    assert data["AUTO_MIGRATE"] == "true"


def test_secret_template_no_real_credentials():
    """Ensures Secret manifest contains only placeholders and no hardcoded credentials."""
    secret = load_yaml("secret.yaml")
    assert secret["apiVersion"] == "v1"
    assert secret["kind"] == "Secret"
    assert secret["metadata"]["name"] == "opswingman-backend-secrets"
    assert secret["type"] == "Opaque"

    string_data = secret.get("stringData", {})
    assert "APP_SECRET_KEY" in string_data
    assert "DATABASE_URL" in string_data
    assert "DATABASE_SYNC_URL" in string_data

    # Verify placeholder patterns
    for key, val in string_data.items():
        assert any(
            placeholder in val
            for placeholder in ["CHANGE_ME", "placeholder", "replace-in-production"]
        ), f"Secret '{key}' does not appear to be a placeholder value: {val}"


# ==============================================================================
# 4. Deployment, Probes & Security Tests
# ==============================================================================

def test_deployment_structure_and_ports():
    """Verifies Deployment metadata, replicas, rolling update strategy, and port 8000."""
    deploy = load_yaml("deployment.yaml")
    assert deploy["apiVersion"] == "apps/v1"
    assert deploy["kind"] == "Deployment"
    assert deploy["metadata"]["name"] == "opswingman-backend"
    assert deploy["spec"]["replicas"] == 2

    # Strategy
    strategy = deploy["spec"]["strategy"]
    assert strategy["type"] == "RollingUpdate"
    assert strategy["rollingUpdate"]["maxUnavailable"] == 0
    assert strategy["rollingUpdate"]["maxSurge"] == 1

    # Container definition
    containers = deploy["spec"]["template"]["spec"]["containers"]
    assert len(containers) >= 1
    backend = containers[0]
    assert backend["name"] == "backend"

    # Ports
    ports = backend["ports"]
    http_port = next((p for p in ports if p["name"] == "http"), None)
    assert http_port is not None
    assert http_port["containerPort"] == 8000


def test_deployment_health_probes():
    """Verifies liveness and readiness probe configurations."""
    deploy = load_yaml("deployment.yaml")
    backend = deploy["spec"]["template"]["spec"]["containers"][0]

    # Liveness probe -> /health/live
    liveness = backend["livenessProbe"]
    assert liveness["httpGet"]["path"] == "/health/live"
    assert liveness["httpGet"]["port"] == "http"
    assert liveness["initialDelaySeconds"] >= 10
    assert liveness["periodSeconds"] >= 5

    # Readiness probe -> /health/ready
    readiness = backend["readinessProbe"]
    assert readiness["httpGet"]["path"] == "/health/ready"
    assert readiness["httpGet"]["port"] == "http"
    assert readiness["initialDelaySeconds"] >= 5
    assert readiness["periodSeconds"] >= 3


def test_deployment_security_context_and_resources():
    """Verifies non-root execution, privilege escalation disabled, and resource limits."""
    deploy = load_yaml("deployment.yaml")
    pod_security = deploy["spec"]["template"]["spec"]["securityContext"]
    assert pod_security["runAsNonRoot"] is True
    assert pod_security["runAsUser"] == 1000

    backend = deploy["spec"]["template"]["spec"]["containers"][0]
    container_security = backend["securityContext"]
    assert container_security["allowPrivilegeEscalation"] is False
    assert "ALL" in container_security["capabilities"]["drop"]

    # Resources
    resources = backend["resources"]
    assert "requests" in resources and "limits" in resources
    assert resources["requests"]["cpu"] == "100m"
    assert resources["requests"]["memory"] == "256Mi"
    assert resources["limits"]["memory"] == "1Gi"


def test_deployment_config_and_secret_references():
    """Verifies that Deployment correctly references ConfigMap and Secret."""
    deploy = load_yaml("deployment.yaml")
    backend = deploy["spec"]["template"]["spec"]["containers"][0]
    env_from = backend["envFrom"]

    cm_ref = next((e["configMapRef"]["name"] for e in env_from if "configMapRef" in e), None)
    sec_ref = next((e["secretRef"]["name"] for e in env_from if "secretRef" in e), None)

    assert cm_ref == "opswingman-backend-config"
    assert sec_ref == "opswingman-backend-secrets"


# ==============================================================================
# 5. Service & Ingress Tests
# ==============================================================================

def test_service_cluster_ip_and_selector():
    """Verifies ClusterIP Service definition and label selector match Deployment."""
    svc = load_yaml("service.yaml")
    assert svc["apiVersion"] == "v1"
    assert svc["kind"] == "Service"
    assert svc["metadata"]["name"] == "opswingman-backend-service"
    assert svc["spec"]["type"] == "ClusterIP"

    # Ports
    ports = svc["spec"]["ports"]
    http_port = next((p for p in ports if p["name"] == "http"), None)
    assert http_port is not None
    assert http_port["port"] == 8000
    assert http_port["targetPort"] == "http"

    # Selector
    deploy = load_yaml("deployment.yaml")
    deploy_labels = deploy["spec"]["selector"]["matchLabels"]
    assert svc["spec"]["selector"] == deploy_labels


def test_ingress_routing():
    """Verifies Ingress routes to opswingman-backend-service on port 8000."""
    ingress = load_yaml("ingress.yaml")
    assert ingress["apiVersion"] == "networking.k8s.io/v1"
    assert ingress["kind"] == "Ingress"
    assert ingress["metadata"]["name"] == "opswingman-backend-ingress"

    rules = ingress["spec"]["rules"]
    assert len(rules) >= 1
    http_paths = rules[0]["http"]["paths"]
    assert len(http_paths) >= 1

    rule_path = http_paths[0]
    assert rule_path["path"] == "/"
    assert rule_path["pathType"] == "Prefix"
    backend_svc = rule_path["backend"]["service"]
    assert backend_svc["name"] == "opswingman-backend-service"
    assert backend_svc["port"]["number"] == 8000
