# MLOps Sentiment Pipeline

A governed model lifecycle for a sentiment classifier on Databricks: registry, serving, drift monitoring, gated retraining, canary release, controlled promotion, and automatic rollback. The model itself is deliberately simple (TF-IDF with logistic regression). The project is about what happens around the model.

## Problem

A sentiment classifier in production degrades when live data differs from training data. Retraining alone does not solve this. The harder questions are operational:

- How do we stop a worse model from reaching production?
- How do we release a new model without exposing all traffic to it?
- If something breaks after release, how fast can we return to the last good model?
- How do we test the whole pipeline without touching production?

This repository answers those four questions with a pipeline that was tested against each failure path, not only the happy path.

## Scope and environment

- Platform: Databricks Free Edition (serverless compute)
- Tracking and registry: MLflow with Unity Catalog
- Registered models: `project1.mlops_sentiment.sentiment_classifier` (production) and `project1.mlops_sentiment.sentiment_classifier_test` (integration testing)
- Serving: Databricks model serving endpoint `sentiment-classifier`
- Orchestration: Databricks Workflows (Jobs)

## Architecture

```
            retrain job (Workflows)
  unit_tests -> validate_data -> train -> gate -> gate_check -> register
                                             |            |
                                       fail: stop     pass: new version
                                                      gets @challenger
                                                            |
                         promote job (separate, manual trigger)
                                                            |
            compare metric -> set @previous -> set @champion
                                                            |
                                  smoke test on @champion
                                     |                 |
                                   pass          fail: restore old
                                                 @champion, fail job
```

Aliases used in the registry:

| Alias | Meaning |
|---|---|
| `@challenger` | Newest registered candidate. Not serving traffic through promotion yet. |
| `@champion` | The version considered the production standard. |
| `@previous` | The prior champion, kept as the rollback target. |

Aliases are pointers. Promotion and rollback move a pointer and do not copy or rebuild a model.

## Repository layout

```
config/
  gate_v5.json          gate threshold used for real retraining
  gate_test.json        gate threshold used for integration tests
src/
  00_unit_tests.py      unit test runner for pipeline
  common.py             shared helpers
  01_validate_data.py   input data checks
  02_train.py           training and metric logging
  03_gate.py            quality gate on the evaluation metric
  04_register.py        registers a version and sets @challenger
  05_promote.py         challenger to champion, with rollback logic
tests/
  test_gate.py          unit tests (9 test cases)
databricks.yml          multi-target pipeline (dev + integration_test)
.github/workflows/
  ci.yml                GitHub Actions CI (pytest on push/PR)
```

## Pipeline stages

### 1. Registry and versioning
Every trained model is logged to MLflow and registered in Unity Catalog, so each version has a run, metrics, and lineage back to the code that produced it.

### 2. Serving and drift monitoring
The champion is served from the `sentiment-classifier` endpoint. Predictions on tweet-style text are monitored to detect drift from the original training distribution. Drift is the trigger for retraining.

### 3. Canary release and rollback drill
A retrained version was released with a 90/10 traffic split before full rollout. A rollback drill moved the endpoint from v3 to v1 in 62 seconds and back to v3 in 158 seconds. This established a measured recovery time instead of an assumed one.

### 4. Automated retraining job
A Workflows job runs `unit_tests`, `validate_data`, `train`, `gate`, `gate_check`, and `register` in order. Unit tests run first to catch logic errors, then data checks run before training so bad input fails early.

### 5. Quality gate
`gate_check` compares the evaluation metric (`gate_tweet_acc`) against a threshold stored in a config file. If the gate fails, the register task is skipped and no new version is created. Thresholds live in config so tests can change them without editing code.

### 6. Register does not mean promote
`04_register.py` only registers the version and sets `@challenger`. It never touches `@champion`. Registering and promoting are separate decisions with different risk, so they are separate tasks.

### 7. Controlled promotion
`05_promote.py` runs as a separate Databricks job (`promote_sentiment`), triggered manually. Its logic:

1. If there is no challenger, fail.
2. If challenger and champion are the same version, exit without changes (idempotent).
3. Compare the chosen metric. Reject unless the challenger beats the champion by at least `--min-improvement`.
4. Set `@previous` to the current champion first, then set `@champion` to the challenger. This order means a crash between the two steps still leaves a rollback target.
5. Tag the promoted version with `promoted_at` and `promoted_from`.
6. Load `models:/<name>@champion` and run a smoke test prediction.
7. If the smoke test fails, restore the old champion and exit with an error so job failure notifications fire.

Flags: `--model` (defaults to the `_test` model so production is never targeted by accident), `--metric`, `--min-improvement`, `--dry-run`.

## Verification

Each guarantee was tested with an explicit scenario. Registry state was captured before and after each run.

| Scenario | Setup | Observed result |
|---|---|---|
| Happy path | Integration job on the `_test` model, gate passes | Version 2 registered, `@challenger` set, `@champion` unchanged |
| Gate failure | Gate threshold raised above achievable accuracy | Register task skipped, `_test` versions unchanged, aliases unchanged |
| Production isolation | Snapshot of production model before and after both runs | Aliases (`champion=3`, `challenger=3`, `previous=1`) and versions `[1, 2, 3]` identical |
| Promotion | Promote job on `_test` | `champion=2`, `previous=1`, `challenger=2`; smoke test returned `[1, 0]` for one positive and one negative sample |
| Automatic rollback | Smoke test forced to fail after promotion | Log shows `PROMOTED`, `SMOKE TEST FAILED`, `AUTO-ROLLBACK`; `@champion` returned to v1; job ended red |

Integration tests use a separate registered model (`_test` suffix) so that pipeline experiments cannot change production aliases.

## Tech Stack
- **Platform:** Databricks (Unity Catalog, MLflow, Model Serving, Serverless Jobs)
- **ML:** scikit-learn (TF-IDF + Logistic Regression)
- **Data:** Delta Lake, PySpark
- **CI/CD:** GitHub Actions, pytest, Databricks Asset Bundles
- **Monitoring:** Population Stability Index (PSI), Out-of-Vocabulary (OOV) tracking

## Key Metrics
- **Test Accuracy:** 78.6% (movies), 78.4% (tweets)
- **Latency:** p50 = 31ms, p95 = 78ms
- **Deployment:** Zero-downtime canary rollout (90/10 → 100%)
- **Rollback Time:** 62 seconds (live)
- **Test Coverage:** 9 gate scenarios with GitHub Actions CI

## Findings worth noting

- In the rollback drill, champion and challenger had identical metrics (0.7838) and the promote still ran. The comparison uses a strict less-than, so equal metrics pass when `--min-improvement` is `0.0`. For production, use a small positive value so a retrain with no real gain does not change the champion.
- After a rollback, the tags `promoted_at` and `promoted_from` remain on the version that was rolled back. They should be removed or replaced with a `rolled_back_at` tag so the audit trail is accurate.
- If `@previous` already pointed at an older version before a promote, a rollback currently leaves `@previous` pointing at the rolled-back champion. The previous value of `@previous` should be saved and restored.

## Known limitations

- Runs on Databricks Free Edition. Features such as service principals and fine-grained permission controls may be limited and were not part of this work.
- The model is a classical TF-IDF and logistic regression pipeline. No deep learning or GPU serving is included.
- Promotion is manually triggered via the `promote_sentiment` Databricks job. There is no automated approval workflow.
- CI/CD is limited to unit tests via GitHub Actions; deployment automation to Databricks is not yet implemented.

## Planned work

1. Extended CI/CD pipeline: Deploy bundles to `_test` via GitHub Actions on PR merge, with production deployment behind manual approval.
2. Serving outside Databricks: pull `@champion` from the registry and serve it with FastAPI in a Docker container.
3. Security controls: Unity Catalog grants on alias changes, secret scopes, image scanning, and an audit view built from promotion tags.
4. Monitoring: latency, error rate, and prediction distribution metrics with a dashboard.
5. Shadow deployment: send mirrored traffic to the challenger and compare its outputs against the champion before promotion.

## How to run

Replace the placeholders with your workspace values.

```bash
# Authenticate with Databricks
databricks auth login --host https://dbc-<your-workspace>.cloud.databricks.com

# Validate bundle
databricks bundle validate -t dev

# Deploy integration test environment
databricks bundle deploy -t integration_test

# Run integration test
databricks bundle run retrain_sentiment -t integration_test

# Run promote job (manual)
databricks bundle run promote_sentiment -t integration_test

# Or promote via Python script directly
python src/05_promote.py --dry-run

# Promote the test model
python src/05_promote.py --metric gate_tweet_acc --min-improvement 0.0

# Promote production (only after test drills pass)
python src/05_promote.py --model project1.mlops_sentiment.sentiment_classifier \
  --metric gate_tweet_acc --min-improvement 0.005 --dry-run
```

## Author

Zeenat Riaz
- GitHub: https://github.com/zeenat28-ui
- LinkedIn: https://www.linkedin.com/in/zeenat-riaz-16339b3ab/

## License
MIT
