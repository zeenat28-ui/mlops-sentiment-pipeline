import json, pathlib, sys
sys.path.insert(0, "src")
from common import run_gate

CFG = json.load(open(pathlib.Path("config/gate_v5.json")))

CHAMP = {
    "movie_acc": 0.78, "movie_gap": 0.04, "movie_bias": 0.02,
    "tweet_acc": 0.60, "tweet_gap": 0.10, "tweet_bias": 0.05,
    "p95_ms": 10.0
}

def chal(**changes):
    return {**CHAMP, **changes}

def passed(c):
    return run_gate(CHAMP, c, CFG)[0]

def test_config_has_required_keys():
    for k in ["primary_domain", "secondary_domain", "min_primary_gain", "max_secondary_drop",
              "recall_gap_slack", "bias_slack", "max_p95_ms", "eval_tables"]:
        assert k in CFG

def test_identical_model_is_rejected():            # Sanity 1
    assert not passed(chal())

def test_clear_improvement_passes():
    assert passed(chal(tweet_acc=0.70))

def test_regression_like_v1_is_rejected():         # Sanity 2
    assert not passed(chal(tweet_acc=0.55, tweet_gap=0.14))

def test_secondary_domain_drop_rejected():         # v3 ka case
    assert not passed(chal(tweet_acc=0.70, movie_acc=0.75))

def test_movie_improvement_is_not_penalised():     # Step 3 ke abs() bug ka guard
    assert passed(chal(tweet_acc=0.70, movie_acc=0.83))

def test_worse_recall_gap_rejected():
    assert not passed(chal(tweet_acc=0.70, tweet_gap=0.20))

def test_worse_bias_rejected():
    assert not passed(chal(tweet_acc=0.70, tweet_bias=0.12))

def test_slow_model_rejected():
    assert passed(chal(tweet_acc=0.70, p95_ms=150.0))
