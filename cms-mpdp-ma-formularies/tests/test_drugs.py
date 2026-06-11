import duckdb
import pandas as pd

from mpdp_formulary.transform import drugs

BASIC_COLS = ["FORMULARY_ID", "FORMULARY_VERSION", "CONTRACT_YEAR", "RXCUI", "NDC",
              "TIER_LEVEL_VALUE", "QUANTITY_LIMIT_YN", "QUANTITY_LIMIT_AMOUNT",
              "QUANTITY_LIMIT_DAYS", "PRIOR_AUTHORIZATION_YN", "STEP_THERAPY_YN",
              "SELECTED_DRUG_YN"]


def make_con(rows):
    con = duckdb.connect()
    con.register("basic_df", pd.DataFrame(rows, columns=BASIC_COLS))
    con.execute("CREATE TABLE raw_basic AS SELECT * FROM basic_df")
    return con


def test_ndc_rows_aggregate_to_rxcui_with_any_logic():
    con = make_con([
        ("F1", "17", "2026", "100", "00001", "3", "Y", "2", "28", "N", "N", "N"),
        ("F1", "17", "2026", "100", "00002", "3", "N", " ", " ", "Y", "N", "N"),
        ("F1", "17", "2026", "100", "00003", "2", "N", " ", " ", "N", "Y", "Y"),
    ])
    drugs.build(con)
    row = con.execute("SELECT * FROM formulary_drug").df().iloc[0]
    assert row["tier"] == 3            # modal tier of [3, 3, 2]
    assert row["tier_min"] == 2 and row["tier_max"] == 3
    assert bool(row["pa"]) and bool(row["st"]) and bool(row["ql"])
    assert bool(row["selected"])
    assert row["ql_amount"] == "2" and row["ql_days"] == "28"
    assert row["ndc_count"] == 3


def test_drug_dim_counts_across_formularies():
    con = make_con([
        ("F1", "17", "2026", "100", "00001", "1", "N", " ", " ", "N", "N", "N"),
        ("F2", "17", "2026", "100", "00001", "2", "N", " ", " ", "Y", "N", "N"),
        ("F2", "17", "2026", "200", "00009", "4", "Y", "30", "30", "N", "N", "N"),
    ])
    drugs.build(con)
    dim = con.execute("SELECT * FROM drug_dim ORDER BY rxcui").df()
    d100 = dim[dim["rxcui"] == "100"].iloc[0]
    assert d100["n_formularies"] == 2
    assert d100["n_pa"] == 1 and d100["n_ql"] == 0
    d200 = dim[dim["rxcui"] == "200"].iloc[0]
    assert d200["n_formularies"] == 1 and d200["n_ql"] == 1
