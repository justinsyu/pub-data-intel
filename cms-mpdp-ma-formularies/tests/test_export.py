import json

import pandas as pd

from mpdp_formulary.export import dashboard_json as dj


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_index_and_table_roundtrip(tmp_path):
    df = pd.DataFrame([{"rxcui": "100", "name": "drug", "bg": "generic",
                        "ndc_count": 2, "n_form": 1, "cov_pct": 50.0,
                        "pa_pct": 0.0, "st_pct": 0.0, "ql_pct": 100.0,
                        "excl_plans": 0, "selected": False}])
    dj.write_drugs_index(tmp_path, df)
    obj = read(tmp_path / "drugs_index.json")
    assert obj["cols"] == dj.DRUGS_INDEX_COLS
    assert obj["rows"][0][0] == "100"


def test_write_drug_shards(tmp_path):
    drugs = pd.DataFrame([{"rxcui": "100", "name": "drug", "bg": "generic",
                           "selected": False}])
    vectors = pd.DataFrame([{"rxcui": "100", "vector": "b1"}])
    fd = pd.DataFrame([
        {"formulary_id": "F1", "rxcui": "100", "tier": 3,
         "ql_amount": "2", "ql_days": "28"},
        {"formulary_id": "F2", "rxcui": "100", "tier": 2,
         "ql_amount": None, "ql_days": None},
    ])
    excl = pd.DataFrame([{"contract_plan": "H1_001", "plan_name": "Plan",
                          "rxcui": "100", "tier": 1, "pa": False, "st": False,
                          "ql": True, "ql_amount": "6", "ql_days": "30",
                          "capped": False}])
    ind = pd.DataFrame([{"contract_plan": "H1_001", "rxcui": "100",
                         "disease": "ASTHMA"}])
    dj.write_drug_shards(tmp_path, drugs, vectors, fd, excl, ind)
    obj = read(tmp_path / "drugs" / "100.json")
    assert obj["vector"] == "b1"
    assert obj["formularies"]["F1"] == [3, "2", "28"]
    assert obj["formularies"]["F2"] == [2, None, None]
    assert obj["excluded_by"]["rows"][0][0] == "H1_001"
    assert obj["indications"] == [{"contract_plan": "H1_001", "disease": "ASTHMA"}]


def test_write_geo_uses_plan_indexes(tmp_path):
    geo = pd.DataFrame([{"fips": "01001", "name": "Autauga", "state": "AL",
                         "plans": [0, 2]}])
    dj.write_geo(tmp_path, geo)
    obj = read(tmp_path / "geo.json")
    assert obj["rows"][0] == ["01001", "Autauga", "AL", [0, 2]]


def test_nan_becomes_null(tmp_path):
    df = pd.DataFrame([{"plan_key": "H1_001_000", "contract_name": "C",
                        "plan_name": "P", "type": "MA", "snp": "0",
                        "premium": float("nan"), "deductible": 0.0,
                        "formulary_idx": 0, "suppressed": "N", "n_drugs": 10,
                        "pa_pct": 1.0, "st_pct": 0.0, "ql_pct": 2.0,
                        "n_excluded": 0, "states": ["NE"]}])
    dj.write_plans_index(tmp_path, df)
    obj = read(tmp_path / "plans_index.json")
    row = dict(zip(obj["cols"], obj["rows"][0]))
    assert row["premium"] is None


def test_write_plan_shards_parses_costs_and_handles_blanks(tmp_path):
    costs = pd.DataFrame([{
        "plan_key": "H1_001_000", "CONTRACT_ID": "H1", "PLAN_ID": "001",
        "SEGMENT_ID": "000", "COVERAGE_LEVEL": "1", "TIER": "1",
        "DAYS_SUPPLY": "1",
        "COST_TYPE_PREF": "1", "COST_AMT_PREF": "5", "COST_MIN_AMT_PREF": " ",
        "COST_MAX_AMT_PREF": float("nan"),
        "COST_TYPE_NONPREF": "2", "COST_AMT_NONPREF": "0.25",
        "COST_MIN_AMT_NONPREF": "1", "COST_MAX_AMT_NONPREF": "50",
        "COST_TYPE_MAIL_PREF": "0", "COST_AMT_MAIL_PREF": "0",
        "COST_MIN_AMT_MAIL_PREF": "0", "COST_MAX_AMT_MAIL_PREF": "0",
        "COST_TYPE_MAIL_NONPREF": "0", "COST_AMT_MAIL_NONPREF": "0",
        "COST_MIN_AMT_MAIL_NONPREF": "0", "COST_MAX_AMT_MAIL_NONPREF": "0",
        "TIER_SPECIALTY_YN": "N", "DED_APPLIES_YN": "Y",
    }])
    ins = pd.DataFrame([{
        "plan_key": "H1_001_000", "TIER": " ", "DAYS_SUPPLY": "1",
        "COPAY_AMT_PREF_INSLN": " ", "COPAY_AMT_NONPREF_INSLN": "0.00",
        "COPAY_AMT_MAIL_PREF_INSLN": "0.00", "COPAY_AMT_MAIL_NONPREF_INSLN": "10.00",
        "COIN_AMT_PREF_INSLN": " ", "COIN_AMT_NONPREF_INSLN": "0.00",
        "COIN_AMT_MAIL_PREF_INSLN": "0.00", "COIN_AMT_MAIL_NONPREF_INSLN": "0.25",
    }])
    excl = pd.DataFrame([{"contract_plan": "H1_001", "plan_name": "Plan",
                          "name": "drugname", "rxcui": "100", "tier": 1,
                          "pa": False, "st": False, "ql": True,
                          "ql_amount": "6", "ql_days": "30", "capped": False}])
    ind = pd.DataFrame([{"contract_plan": "H1_001", "rxcui": "100",
                         "name": "drugname", "disease": "ASTHMA"}])
    n = dj.write_plan_shards(tmp_path, ["H1_001_000", "S9_009_000"],
                             costs, ins, excl, ind)
    assert n == 2
    # strict parse: reject NaN/Infinity literals the way browsers do
    def reject(_):
        raise ValueError("invalid JSON literal")
    text = (tmp_path / "plans" / "H1_001_000.json").read_text(encoding="utf-8")
    obj = json.loads(text, parse_constant=reject)
    c = obj["costs"][0]
    assert c["level"] == 1.0 and c["tier"] == 1.0 and c["days"] == 1.0
    assert c["specialty"] == "N" and c["ded_applies"] == "Y"
    assert c["channels"]["pref"] == [1.0, 5.0, None, None]   # blank and NaN -> null
    assert c["channels"]["nonpref"] == [2.0, 0.25, 1.0, 50.0]
    assert obj["insulin"][0]["tier"] is None
    assert obj["insulin"][0]["copay"] == [None, 0.0, 0.0, 10.0]
    assert obj["excluded"]["rows"][0][0] == "100"
    assert obj["indications"] == [{"rxcui": "100", "name": "drugname",
                                   "disease": "ASTHMA"}]
    # empty shard for the plan with no rows keeps a consistent shape
    empty = json.loads((tmp_path / "plans" / "S9_009_000.json")
                       .read_text(encoding="utf-8"), parse_constant=reject)
    assert empty["costs"] == [] and empty["insulin"] == []
    assert empty["excluded"]["rows"] == [] and empty["indications"] == []


def test_clean_handles_pd_na_and_lists(tmp_path):
    import numpy as np
    df = pd.DataFrame([{"fips": "01001", "name": "Autauga", "state": "AL",
                        "plans": [np.int64(0), np.int64(2)]}])
    dj.write_geo(tmp_path, df)
    obj = read(tmp_path / "geo.json")
    assert obj["rows"][0][3] == [0, 2]
    assert dj._clean(pd.NA) is None
