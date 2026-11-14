"""Snapshot the production model's aliases and versions, and compare two snapshots.

Usage:
    python scripts/assert_prod_untouched.py snapshot <out.json>
    python scripts/assert_prod_untouched.py compare <before.json> <after.json>

Authentication comes from DATABRICKS_HOST and DATABRICKS_TOKEN in the environment.
"""
import json
import os
import sys

PROD = os.environ.get("PROD_MODEL", "project1.mlops_sentiment.sentiment_classifier")


def take_snapshot() -> dict:
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_registry_uri("databricks-uc")
    client = MlflowClient()
    model = client.get_registered_model(PROD)
    aliases = dict(model.aliases) if model.aliases else {}
    versions = sorted(int(v.version) for v in client.search_model_versions(f"name='{PROD}'"))
    return {"model": PROD, "aliases": aliases, "versions": versions}


def compare(before_path: str, after_path: str) -> int:
    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)
    if before == after:
        print(f"PROD UNTOUCHED: aliases={after['aliases']} versions={after['versions']}")
        return 0
    print("PROD CHANGED")
    print("before:", json.dumps(before, sort_keys=True))
    print("after: ", json.dumps(after, sort_keys=True))
    return 1


def main(argv: list) -> int:
    if len(argv) == 3 and argv[1] == "snapshot":
        with open(argv[2], "w") as f:
            json.dump(take_snapshot(), f, indent=2, sort_keys=True)
        print(f"snapshot written to {argv[2]}")
        return 0
    if len(argv) == 4 and argv[1] == "compare":
        return compare(argv[2], argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
