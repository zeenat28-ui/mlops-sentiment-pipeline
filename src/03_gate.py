# Databricks notebook source
import mlflow, mlflow.sklearn
from common import *

mlflow.set_registry_uri("databricks-uc")
cfg = load_cfg()
tests = load_tests(spark, cfg)
uri = dbutils.jobs.taskValues.get(taskKey="train", key="model_uri", debugValue="")
run_id = dbutils.jobs.taskValues.get(taskKey="train", key="run_id", debugValue="")
assert uri and run_id, "train task ki values nahi mili"

champ = evaluate(mlflow.sklearn.load_model(f"models:/{MODEL}@champion"), tests)
chal = evaluate(mlflow.sklearn.load_model(uri), tests)
passed, checks = run_gate(champ, chal, cfg)

print("champion  :", {k: round(v, 3) for k, v in champ.items()})
print("challenger:", {k: round(v, 3) for k, v in chal.items()})
for k, v in checks.items(): print("PASS" if v else "FAIL", "-", k)
print("GATE PASSED" if passed else "GATE FAILED")

with mlflow.start_run(run_id=run_id):
    mlflow.log_metrics({f"gate_{k}": v for k, v in chal.items()})
    mlflow.set_tag("gate_version", cfg["gate_version"])
    mlflow.set_tag("gate_passed", str(passed))
dbutils.jobs.taskValues.set(key="gate_passed", value=str(passed).lower())
