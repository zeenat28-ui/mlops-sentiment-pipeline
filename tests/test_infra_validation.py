import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_kubernetes_manifests_syntax_and_structure():
    k8s_dir = REPO_ROOT / "k8s"
    assert k8s_dir.exists(), "k8s directory must exist"

    manifest_files = [
        "deployment.yaml",
        "service.yaml",
        "hpa.yaml",
        "ingress.yaml",
        "kustomization.yaml",
    ]

    for fname in manifest_files:
        fpath = k8s_dir / fname
        assert fpath.exists(), f"Missing manifest: {fname}"
        with open(fpath, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) > 0, f"Empty manifest: {fname}"
            for doc in docs:
                assert "apiVersion" in doc
                assert "kind" in doc

    # Deep verification on Deployment
    with open(k8s_dir / "deployment.yaml", "r", encoding="utf-8") as f:
        deploy = yaml.safe_load(f)
    assert deploy["kind"] == "Deployment"
    assert deploy["metadata"]["namespace"] == "mlops"
    pod_spec = deploy["spec"]["template"]["spec"]
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    container = pod_spec["containers"][0]
    assert "resources" in container
    assert "requests" in container["resources"]
    assert "limits" in container["resources"]
    assert "livenessProbe" in container
    assert "readinessProbe" in container

def test_terraform_structure():
    tf_dir = REPO_ROOT / "terraform"
    assert tf_dir.exists(), "terraform directory must exist"

    for fname in ["main.tf", "variables.tf", "outputs.tf", "terraform.tfvars.example"]:
        fpath = tf_dir / fname
        assert fpath.exists(), f"Missing terraform file: {fname}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content.strip()) > 50

    main_tf = (tf_dir / "main.tf").read_text(encoding="utf-8")
    assert "module \"eks\"" in main_tf
    assert "resource \"aws_ecr_repository\"" in main_tf

def test_monitoring_prometheus_and_grafana():
    mon_dir = REPO_ROOT / "monitoring"
    assert mon_dir.exists(), "monitoring directory must exist"

    # Validate prometheus.yml
    prom_path = mon_dir / "prometheus.yml"
    assert prom_path.exists()
    with open(prom_path, "r", encoding="utf-8") as f:
        prom = yaml.safe_load(f)
    assert "scrape_configs" in prom
    job_names = [sc["job_name"] for sc in prom["scrape_configs"]]
    assert "sentiment-api" in job_names
    assert "databricks-serving" in job_names

    # Validate alerts.yml
    alerts_path = mon_dir / "alerts.yml"
    assert alerts_path.exists()
    with open(alerts_path, "r", encoding="utf-8") as f:
        alerts = yaml.safe_load(f)
    assert "groups" in alerts
    alert_names = [r["alert"] for r in alerts["groups"][0]["rules"]]
    assert "ModelServingHighLatency" in alert_names
    assert "DataDriftAlertThresholdExceeded" in alert_names

    # Validate grafana-dashboard.json
    grafana_path = mon_dir / "grafana-dashboard.json"
    assert grafana_path.exists()
    with open(grafana_path, "r", encoding="utf-8") as f:
        dash = json.load(f)
    assert dash["title"] == "MLOps Sentiment Serving - Production Health & Drift"
    assert len(dash["panels"]) >= 5
