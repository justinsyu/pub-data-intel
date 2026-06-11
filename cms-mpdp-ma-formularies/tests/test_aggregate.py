import pandas as pd

from mpdp_formulary.aggregate import stats, status_vectors


def fd(rows):
    return pd.DataFrame(rows, columns=[
        "formulary_id", "rxcui", "tier", "tier_min", "tier_max",
        "pa", "st", "ql", "ql_amount", "ql_days", "selected", "ndc_count"])


SAMPLE = fd([
    ("F1", "100", 3, 3, 3, True, False, True, "2", "28", False, 4),
    ("F2", "100", 2, 2, 2, False, False, False, None, None, False, 1),
    ("F2", "200", 5, 5, 5, False, True, False, None, None, True, 2),
])


def test_encode_status():
    assert status_vectors.encode_status(False, False, False) == "1"
    assert status_vectors.encode_status(True, False, False) == "3"
    assert status_vectors.encode_status(False, True, False) == "5"
    assert status_vectors.encode_status(False, False, True) == "9"
    assert status_vectors.encode_status(True, True, True) == "f"


def test_build_vectors():
    out = status_vectors.build_vectors(SAMPLE, ["F1", "F2"])
    v = out.set_index("rxcui")["vector"]
    assert v["100"] == "b1"   # F1: PA+QL -> b; F2: unrestricted -> 1
    assert v["200"] == "-5"   # not on F1; ST on F2


def test_formulary_order_is_sorted_distinct():
    assert stats.formulary_order(SAMPLE) == ["F1", "F2"]


def test_formulary_stats():
    out = stats.formulary_stats(SAMPLE).set_index("formulary_id")
    assert out.loc["F1", "n_drugs"] == 1
    assert out.loc["F2", "n_drugs"] == 2
    assert out.loc["F2", "pa_pct"] == 0.0
    assert out.loc["F2", "st_pct"] == 50.0
    assert out.loc["F1", "ql_pct"] == 100.0


def test_plan_stats_attaches_exclusions_by_contract_plan():
    plan_dim = pd.DataFrame([
        ("H1_001_000", "H1", "001", "000", "F1"),
        ("H1_001_001", "H1", "001", "001", "F1"),
        ("S1_002_000", "S1", "002", "000", "F2"),
    ], columns=["plan_key", "contract_id", "plan_id", "segment_id", "formulary_id"])
    excluded = pd.DataFrame([
        ("H1", "001", "900"), ("H1", "001", "901"),
    ], columns=["CONTRACT_ID", "PLAN_ID", "RXCUI"])
    out = stats.plan_stats(plan_dim, stats.formulary_stats(SAMPLE), excluded)
    m = out.set_index("plan_key")["n_excluded"]
    assert m["H1_001_000"] == 2 and m["H1_001_001"] == 2  # both segments
    assert m["S1_002_000"] == 0
    assert out.set_index("plan_key").loc["S1_002_000", "n_drugs"] == 2
