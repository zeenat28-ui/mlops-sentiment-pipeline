# Production MLOps Sentiment Pipeline — Operations Runbook

## 1. Closed-Loop Architecture (`Train -> Register -> Deploy -> Observe -> Retrain`)
1. **Fail-Closed Model Integrity (`serving/app.py`)**: Container verifies SHA-256 checksums of all artifacts against `model/manifest.json` on startup and exits non-zero on tamper or extra files.
2. **GitOps & Canary Progressive Delivery (`Argo CD` + `Argo Rollouts`)**: `k8s/overlays/kind` syncs via `sentiment-api-gitops`. Releases roll out via `25% -> 50% -> 100%` Canary gates with instant rollback (`kubectl argo rollouts undo`).
3. **Observability & SLOs (`Prometheus` + `Grafana` + `k6`)**: `PodMonitor` scrapes `/metrics` every 15s (`http_requests_total`, `prediction_latency_seconds`, `sentiment_predictions_total`). Verified SLO: `p95 = 113.82ms (<200ms)` at `142.93 req/s` (`0.00%` errors).
4. **Zero-Trust CI/CD (`GitHub Actions OIDC` + `Cosign`)**: `.github/workflows/gitops-cd-oidc.yml` builds immutable `sha-<commit>` images, signs keyless via OIDC (`id-token: write`), and promotes via GitOps without static secrets.
5. **Automated Drift Loop (`monitoring/drift_detector.py`)**: Scheduled 6h PSI check triggers retraining when `PSI >= 0.20`.

## 2. Emergency Commands
- **Check Rollout & Canary Health**: `kubectl argo rollouts get rollout sentiment-api -n mlops`
- **Instant Rollback to Last Stable Revision**: `kubectl argo rollouts abort sentiment-api -n mlops && kubectl argo rollouts undo sentiment-api -n mlops`
- **Verify Live Prometheus Scrape Targets**: `kubectl get podmonitor -n monitoring`
