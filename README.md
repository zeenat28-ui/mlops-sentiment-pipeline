# End-to-End MLOps Sentiment Pipeline on Databricks

A production-grade MLOps pipeline built on **Databricks (Unity Catalog, MLflow, Model Serving, Serverless Jobs)** and **GitHub Actions**, demonstrating the full lifecycle of a multi-domain sentiment classifier (Movie Reviews + Social Media Tweets).

## Architecture
`Delta Tables (Unity Catalog)` → `Data Validation` → `MLflow Experiment Tracking` → `Config-Driven Quality Gate` → `Unity Catalog Model Registry (@champion / @challenger / @previous)` → `Model Serving REST API (Canary 90/10 & Rollback)` → `Drift Monitoring (PSI & OOV)` → `Automated Retraining DAG`

## Key Milestones & Engineering Decisions

### 1. Data Ingestion & Lineage (Unity Catalog)
- Stored raw datasets in Unity Catalog Volumes and curated into Delta tables (`reviews_train`, `reviews_validation`, `reviews_test`, `tweets_train`, `tweets_validation`, `tweets_test`, `train_combined`).
- Enforced automated schema, null, duplicate rate (`<= 0.5%`), and zero train/test leakage checks.
- Logged Delta table versions into MLflow parameters for full reproducibility.

### 2. Experiment Tracking & Evaluation Gates (v1 → v5.1)
- **Baseline (`tfidf_bigram_C4`):** Achieved `74.86%` validation accuracy and `78.52%` test accuracy (`p95 latency = 9.7 ms`).
- **Gate v1 → v2 Fix:** Discovered a two-sided `abs(val - test) <= 0.03` bug that penalized better test performance (`78.52% > 74.86%`). Fixed to a one-sided overfitting check (`val - test <= 0.03`).
- **Gate v3 Fail (Domain Imbalance):** Retraining on unweighted combined data (`24,942` tweets vs `8,530` movies) improved tweet accuracy (`+17.4%`) but caused a `2.4%` drop on movie reviews (`> 2.0%` limit).
- **Challenger v2 (`v2_mf50k_dw`):** Solved domain regression using `max_features=50,000` and domain-balanced sample weights (`~2.9x` weight on movie reviews), restoring movie test accuracy to `78.6%` while achieving `78.4%` on tweets.
- **Gate v4 Waiver & Audit Trail:** `v2_mf50k_dw` narrowly missed the absolute `recall_gap <= 0.10` bar (`0.110` due to tweet class-prior shift: `71.6%` positive in train vs `37.4%` in test), whereas the existing champion itself had a `0.137` gap. Issued a documented human waiver (`waiver_approved_by`) paired with a 10% canary rollout. Lesson learned: always sanity-check new gates against the current champion first.
- **Gate v5.1 Config & Unit Tests:** Extracted relative champion-vs-challenger thresholds into `config/gate_v5.json` and covered 9 edge cases with `pytest` in GitHub Actions CI.

### 3. Production Serving, Canary Rollout & Rollback Drill
- **Live REST API (`sentiment-classifier`):** Deployed on Databricks Model Serving (`p50 = 31 ms`, `p95 = 78 ms`).
- **Environment Rebuild (`v2 → v3`):** Resolved a `pyarrow` container build conflict by pinning clean `pip_requirements` on the exact `v2_mf50k_dw` artifact (`rebuilt_from_version: 2`).
- **Canary Rollout (90/10 Split):** Verified `0 / 300` errors, `100%` local-vs-endpoint prediction parity, and `32.2 ms` challenger p95 latency before promoting `v3` to `100%` (`@champion`) and tagging `v1` as `@previous`.
- **Rollback Drill:** Measured live rollback (`v3 → v1` in **62s**) and re-promotion (`v1 → v3` in **158s**) with zero downtime.

### 4. Drift Monitoring & Automated Retraining Pipeline
- **Drift Detection:** Calibrated Population Stability Index (`PSI`) against a no-drift permutation baseline (`95th percentile = 0.224` for word count, `0.162` for OOV rate). Out-of-domain tweet traffic spiked OOV rate from `9.4%` to `38.8%` and dropped accuracy by `18%` (`79% → 61%`), triggering automated drift alerts.
- **Serverless Workflows DAG:** Built a 5-task pipeline (`validate_data` → `train` → `gate` → `gate_check` → `register`) using Databricks `taskValues` and `condition_task` to automatically block non-improving models from registry promotion.

## Repository Structure
```
mlops-sentiment-pipeline/
├── .github/workflows/ci.yml    # GitHub Actions CI (pytest)
├── config/gate_v5.json         # Quality gate thresholds
├── src/
│   ├── common.py               # Shared utilities
│   ├── 01_validate_data.py     # Data quality checks
│   ├── 02_train.py             # Model training
│   ├── 03_gate.py              # Quality gate evaluation
│   └── 04_register.py          # Model registry promotion
├── tests/test_gate.py          # Unit tests (9 test cases)
├── databricks.yml              # Serverless job DAG
└── README.md
```

## Tech Stack
- **Platform:** Databricks (Unity Catalog, MLflow, Model Serving, Serverless Jobs)
- **ML:** scikit-learn (TF-IDF + Logistic Regression)
- **Data:** Delta Lake, PySpark
- **CI/CD:** GitHub Actions, pytest
- **Monitoring:** Population Stability Index (PSI), Out-of-Vocabulary (OOV) tracking

## Key Metrics
- **Test Accuracy:** 78.6% (movies), 78.4% (tweets)
- **Latency:** p50 = 31ms, p95 = 78ms
- **Deployment:** Zero-downtime canary rollout (90/10 → 100%)
- **Rollback Time:** 62 seconds (live)
- **Test Coverage:** 9 gate scenarios

## License
MIT
