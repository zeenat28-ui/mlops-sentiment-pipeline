import argparse
from datetime import datetime, timezone
import mlflow, mlflow.sklearn
import pandas as pd
from mlflow.tracking import MlflowClient
from sklearn.metrics import accuracy_score

mlflow.set_registry_uri("databricks-uc")

p = argparse.ArgumentParser(allow_abbrev=False)
p.add_argument("--model", default="project1.mlops_sentiment.sentiment_classifier_test")
p.add_argument("--metric", default="gate_tweet_acc")
p.add_argument("--min-improvement", type=float, default=0.005)
p.add_argument("--dry-run", action="store_true")
args, _ = p.parse_known_args()

client = MlflowClient()
name = args.model


def get_version(alias):
    try:
        return client.get_model_version_by_alias(name, alias)
    except Exception:
        return None


def get_metric(mv):
    mv_full = client.get_model_version(name, mv.version)
    tags = mv_full.tags if isinstance(mv_full.tags, dict) else {}
    run_id = tags.get("source_run_id") or mv.run_id
    if run_id:
        try:
            metrics = client.get_run(run_id).data.metrics
            if args.metric in metrics:
                return metrics[args.metric]
            if "test_tweet_acc" in metrics:
                return metrics["test_tweet_acc"]
        except Exception:
            pass
    m = mlflow.sklearn.load_model(f"models:/{name}/{mv.version}")
    t = spark.table("project1.mlops_sentiment.tweets_test").toPandas()
    return float(accuracy_score(t["label"], m.predict(t[["text"]])))


def smoke_test(alias):
    model = mlflow.pyfunc.load_model(f"models:/{name}@{alias}")
    sample = pd.DataFrame({"text": ["great movie, loved it", "terrible, waste of time"]})
    preds = [int(x) for x in model.predict(sample)]
    assert preds == list((1, 0)), f"unexpected predictions: {preds}"
    return preds


def main():
    challenger = get_version("challenger")
    champion = get_version("champion")
    old_previous = get_version("previous")

    # 1) Pre-checks (No-op & existence)
    if challenger is None:
        raise RuntimeError("FAIL: koi @challenger nahi mila, promote ke liye kuch nahi.")

    if champion is not None and str(champion.version) == str(challenger.version):
        print(f"NO-OP: challenger aur champion dono v{champion.version} hain.")
        return

    # 2) Metric comparison
    c_metric = get_metric(challenger)
    if champion is not None:
        ch_metric = get_metric(champion)
        print(f"{args.metric}: champion v{champion.version}={ch_metric:.4f} | "
              f"challenger v{challenger.version}={c_metric:.4f}")
        if c_metric < ch_metric + args.min_improvement:
            raise RuntimeError("REJECTED: challenger required improvement se behtar nahi, promote nahi hua.")

    if args.dry_run:
        print("DRY-RUN: promote hota, lekin kuch badla nahi gaya.")
        return

    # 3) Alias order: pehle @previous, phir @champion
    old_champion = champion
    if old_champion is not None:
        client.set_registered_model_alias(name, "previous", old_champion.version)
    client.set_registered_model_alias(name, "champion", challenger.version)

    client.set_model_version_tag(
        name, challenger.version, "promoted_at", datetime.now(timezone.utc).isoformat()
    )
    if old_champion is not None:
        client.set_model_version_tag(
            name, challenger.version, "promoted_from", str(old_champion.version)
        )
    print(f"PROMOTED: v{challenger.version} ab @champion hai.")

    # 4) Post-promote smoke test + full auto-rollback (aliases + audit tags)
    try:
        preds = smoke_test("champion")
        print(f"SMOKE TEST PASSED. Sample preds: {preds}")
    except Exception as e:
        print(f"SMOKE TEST FAILED: {e}")
        if old_champion is not None:
            client.set_registered_model_alias(name, "champion", old_champion.version)
            print(f"AUTO-ROLLBACK: @champion wapas v{old_champion.version} par.")
        if old_previous is not None:
            client.set_registered_model_alias(name, "previous", old_previous.version)
            print(f"AUTO-ROLLBACK: @previous wapas v{old_previous.version} par.")
        for t in ("promoted_at", "promoted_from"):
            try:
                client.delete_model_version_tag(name, challenger.version, t)
            except Exception:
                pass
        client.set_model_version_tag(
            name, challenger.version, "rolled_back_at", datetime.now(timezone.utc).isoformat()
        )
        raise RuntimeError("FAIL: promote rollback ho gaya, job red rakhi gayi taake alert chale.")


main()
