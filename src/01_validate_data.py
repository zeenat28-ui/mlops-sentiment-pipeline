# Databricks notebook source
from common import *

cfg = load_cfg()
tr = spark.table(f"{CATALOG}.{SCHEMA}.{cfg['train_table']}").toPandas()
tests = load_tests(spark, cfg)

problems = []
if set(tr.columns) != {"text", "label", "domain"}: problems.append(f"columns: {list(tr.columns)}")
if not set(tr["label"].unique()) <= {0, 1}: problems.append("labels 0/1 ke ilawa kuch hai")
if tr["text"].isna().any() or (tr["text"].str.strip().str.len() == 0).any(): problems.append("khali text")
if set(tr["domain"].unique()) != {"movie", "tweet"}: problems.append("koi domain missing")
dup = tr.duplicated("text").mean()
if dup > cfg["max_duplicate_rate"]: problems.append(f"duplicate rate {dup:.4f}")
for d, t in tests.items():
    ov = len(set(tr["text"]) & set(t["text"]))
    if ov: problems.append(f"leakage: {ov} texts train/{d}_test mein common")

ver = spark.sql(f"DESCRIBE HISTORY {CATALOG}.{SCHEMA}.{cfg['train_table']} LIMIT 1").first()["version"]
print("rows:", len(tr), "| dup rate:", round(dup, 5), "| data version:", ver)
assert not problems, f"DATA VALIDATION FAILED: {problems}"
dbutils.jobs.taskValues.set(key="data_version", value=int(ver))
