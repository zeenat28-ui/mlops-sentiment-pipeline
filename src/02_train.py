# Databricks notebook source
import mlflow, mlflow.sklearn, numpy as np, pandas as pd
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, balanced_accuracy_score
from common import *

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experiment_id="2867098470618006")

cfg = load_cfg()
ld = lambda t: spark.table(f"{CATALOG}.{SCHEMA}.{t}").toPandas()
comb, vm, vt = ld(cfg["train_table"]), ld("reviews_validation"), ld("tweets_validation")
data_version = dbutils.jobs.taskValues.get(taskKey="validate_data", key="data_version", debugValue=0)

n_m, n_t = (comb["domain"] == "movie").sum(), (comb["domain"] == "tweet").sum()
w = np.where(comb["domain"] == "movie", n_t / n_m, 1.0)

PIP_REQS = ["scikit-learn", "pandas", "numpy"]

with mlflow.start_run(run_name="pipeline_challenger") as run:
    mlflow.log_params({
        "max_features": 50000,
        "ngram_range": "(1, 2)",
        "C": 4.0,
        "domain_weighted": True,
        "train_table": cfg["train_table"],
        "train_table_version": data_version
    })
    mlflow.set_tag("role", "pipeline_challenger")
    model = Pipeline([
        ("prep", ColumnTransformer([("tfidf", TfidfVectorizer(
            max_features=50000, ngram_range=(1, 2)), "text")])),
        ("clf", LogisticRegression(C=4.0, max_iter=1000))
    ])
    model.fit(comb[["text"]], comb["label"], clf__sample_weight=w)
    mlflow.log_metrics({
        "val_acc_movie": accuracy_score(vm["label"], model.predict(vm[["text"]])),
        "val_bal_acc_tweet": balanced_accuracy_score(vt["label"], model.predict(vt[["text"]]))
    })
    info = mlflow.sklearn.log_model(
        model, name="model", pip_requirements=PIP_REQS,
        signature=infer_signature(vm[["text"]], model.predict(vm[["text"]])),
        input_example=vm[["text"]].head(3)
    )

dbutils.jobs.taskValues.set(key="model_uri", value=info.model_uri)
dbutils.jobs.taskValues.set(key="run_id", value=run.info.run_id)
print("trained:", info.model_uri)
