INTEGRATION_JOB_KEY ?= retrain_sentiment

ci:
	ruff check src tests scripts
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

.PHONY: ci deploy-test-local
