import json, time, numpy as np
from sklearn.metrics import accuracy_score, recall_score

CATALOG, SCHEMA = "project1", "mlops_sentiment"
MODEL = f"{CATALOG}.{SCHEMA}.sentiment_classifier"
CFG_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/config/gate_v5.json"

def load_cfg():
    return json.load(open(CFG_PATH))

def load_tests(spark, cfg):
    return {d: spark.table(f"{CATALOG}.{SCHEMA}.{t}").toPandas()
            for d, t in cfg["eval_tables"].items()}

def evaluate(m, tests):
    r = {}
    for dom, t in tests.items():
        p = m.predict(t[["text"]])
        r[f"{dom}_acc"] = accuracy_score(t["label"], p)
        r[f"{dom}_gap"] = abs(recall_score(t["label"], p, pos_label=0)
                              - recall_score(t["label"], p, pos_label=1))
        r[f"{dom}_bias"] = abs(float(p.mean()) - float(t["label"].mean()))
    s = tests["movie"][["text"]].sample(200, random_state=0)
    lat = []
    for i in range(len(s)):
        t0 = time.perf_counter(); m.predict(s.iloc[[i]])
        lat.append((time.perf_counter() - t0) * 1000)
    r["p95_ms"] = float(np.percentile(lat, 95))
    return r

def run_gate(champ, chal, cfg):
    P, S = cfg["primary_domain"], cfg["secondary_domain"]
    checks = {
        f"{P} acc gain >= {cfg['min_primary_gain']}":
            chal[f"{P}_acc"] - champ[f"{P}_acc"] >= cfg["min_primary_gain"],
        f"{S} acc drop <= {cfg['max_secondary_drop']}":
            champ[f"{S}_acc"] - chal[f"{S}_acc"] <= cfg["max_secondary_drop"],
        "recall gap <= champion + slack (both)":
            all(chal[f"{d}_gap"] <= champ[f"{d}_gap"] + cfg["recall_gap_slack"] for d in (P, S)),
        "pred-share bias <= champion + slack (both)":
            all(chal[f"{d}_bias"] <= champ[f"{d}_bias"] + cfg["bias_slack"] for d in (P, S)),
        f"p95 latency <= {cfg['max_p95_ms']} ms": chal["p95_ms"] <= cfg["max_p95_ms"],
    }
    return all(checks.values()), checks
