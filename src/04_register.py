# Databricks notebook source
import mlflow
from mlflow.tracking import MlflowClient
from common import *

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()
uri = dbutils.jobs.taskValues.get(taskKey="train", key="model_uri", debugValue="")
run_id = dbutils.jobs.taskValues.get(taskKey="train", key="run_id", debugValue="")
dv = dbutils.jobs.taskValues.get(taskKey="validate_data", key="data_version", debugValue=0)

mv = mlflow.register_model(uri, MODEL)
client.set_registered_model_alias(MODEL, "challenger", mv.version)
for k, v in {
    "source_run_id": run_id,
    "train_table_version": str(dv),
    "gate_version": load_cfg()["gate_version"],
    "gate_passed": "True"
}.items():
    client.set_model_version_tag(MODEL, mv.version, k, v)
print("registered v", mv.version, "as challenger; champion unchanged")
