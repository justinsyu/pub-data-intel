import json

import numpy as np

from retina_pilot.actions import engine

RULES = [
    {"id": "ma_low_supply", "role": "market_access",
     "when": [{"metric": "supply", "op": "<=", "value": 35},
              {"metric": "ma_pct", "op": ">=", "value": 45}],
     "action": "High MA penetration with thin retina supply: assess network adequacy and site-of-care economics."},
    {"id": "msl_trials", "role": "msl",
     "when": [{"metric": "trial_count", "op": ">=", "value": 1}],
     "action": "Active retina trial sites present: prioritize investigator engagement."},
]


def test_rule_fires_with_citation():
    geo = {"unit_id": "county:30033", "supply": 10.0, "ma_pct": 50.0, "trial_count": 0}
    actions = engine.generate_actions(geo, RULES)
    assert len(actions) == 1
    a = actions[0]
    assert a["role"] == "market_access"
    assert a["rule_id"] == "ma_low_supply"
    assert {"metric": "supply", "value": 10.0} in a["evidence"]


def test_rule_does_not_fire():
    geo = {"unit_id": "x", "supply": 90.0, "ma_pct": 50.0, "trial_count": 0}
    assert engine.generate_actions(geo, RULES) == []


def test_default_rules_load_and_evaluate():
    rules = engine.load_rules()
    assert len(rules) >= 6
    roles = {r["role"] for r in rules}
    assert roles == {"msl", "medical_affairs", "market_access"}
    geo = {"supply": 10.0, "ma_pct": 60.0, "trial_count": 3, "biosimilar_share_pct": 2.0,
           "ce_340b": 4, "access_risk": 90.0, "utilization": 20.0, "policy_articles": 1,
           "injectors": 1, "unit_id": "x"}
    assert engine.generate_actions(geo, rules)  # at least one rule fires


def test_numpy_values_compare_and_serialize():
    # Parquet rows yield numpy scalars; OPS must compare them and evidence must be JSON-safe.
    geo = {"unit_id": "x", "supply": np.float64(10.0), "ma_pct": np.float64(50.0),
           "trial_count": np.int64(0)}
    actions = engine.generate_actions(geo, RULES)
    assert len(actions) == 1
    evidence = actions[0]["evidence"]
    assert all(type(e["value"]) in (int, float) for e in evidence)
    assert json.loads(json.dumps(actions)) == actions
