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
