INTEGRATION_JOB_KEY ?= retrain_sentiment

ci:
	ruff check src tests scripts serving
	PYTHONPATH=src pytest -q
	databricks bundle validate -t integration_test

# Same steps as .github/workflows/deploy-test.yml, run from a laptop.
# Needs DATABRICKS_HOST and DATABRICKS_TOKEN (or a configured CLI profile).
deploy-test-local:
	python scripts/assert_prod_untouched.py snapshot before.json
	databricks bundle validate -t integration_test
	databricks bundle deploy -t integration_test
	databricks bundle run $(INTEGRATION_JOB_KEY) -t integration_test
	python scripts/assert_prod_untouched.py snapshot after.json
	python scripts/assert_prod_untouched.py compare before.json after.json

# Model serving commands
pull-model:
	DATABRICKS_HOST="https://dbc-21cd347b-ad51.cloud.databricks.com" \
	DATABRICKS_TOKEN="$$DATABRICKS_TOKEN" \
	python serving/pull_model.py project1.mlops_sentiment.sentiment_classifier

docker-build:
	docker build -f serving/Dockerfile -t mlops-sentiment-api:latest .

docker-run:
	docker run --rm -p 8000:8000 mlops-sentiment-api:latest

.PHONY: ci deploy-test-local pull-model docker-build docker-run
