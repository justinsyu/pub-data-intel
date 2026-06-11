import duckdb
import pandas as pd
import pytest

from mpdp_formulary.transform import plans

PLAN_COLS = ["CONTRACT_ID", "PLAN_ID", "SEGMENT_ID", "CONTRACT_NAME", "PLAN_NAME",
             "FORMULARY_ID", "PREMIUM", "DEDUCTIBLE", "MA_REGION_CODE",
             "PDP_REGION_CODE", "STATE", "COUNTY_CODE", "SNP", "PLAN_SUPPRESSED_YN"]
GEO_COLS = ["COUNTY_CODE", "STATENAME", "COUNTY", "MA_REGION_CODE", "MA_REGION",
            "PDP_REGION_CODE", "PDP_REGION"]


def make_con(plan_rows, geo_rows):
    con = duckdb.connect()
    con.register("plan_df", pd.DataFrame(plan_rows, columns=PLAN_COLS))
    con.register("geo_df", pd.DataFrame(geo_rows, columns=GEO_COLS))
    con.execute("CREATE TABLE raw_plan_info AS SELECT * FROM plan_df")
    con.execute("CREATE TABLE raw_geo AS SELECT * FROM geo_df")
    return con


GEO = [
    ("01000", "Alabama", "Autauga", "10", "AL and TN", "12", "AL, TN"),
    ("01010", "Alabama", "Baldwin", "10", "AL and TN", "12", "AL, TN"),
    ("28100", "Nebraska", "Douglas", "19", "Upper Midwest", "25", "Upper Midwest"),
]


def h_plan(county, name="Plan H"):
    return ("H0028", "007", "000", "CHA HMO", name, "00026408", "35.60", "615",
            " ", " ", "NE", county, "2", "N")


def test_plan_dim_dedupes_county_rows():
    con = make_con([h_plan("28100"), h_plan("28100")], GEO)
    stats = plans.build(con)
    dim = con.execute("SELECT * FROM plan_dim").df()
    assert len(dim) == 1
    row = dim.iloc[0]
    assert row["plan_key"] == "H0028_007_000"
    assert row["plan_type"] == "MA"
    assert row["premium"] == pytest.approx(35.60)
    assert stats["n_plans"] == 1


def test_bridge_h_uses_own_counties_r_and_s_expand_regions():
    r_plan = ("R5826", "001", "000", "ORG R", "Plan R", "00026500", "0", "0",
              "10", " ", " ", " ", "0", "N")
    s_plan = ("S5601", "001", "000", "ORG S", "Plan S", "00026501", "0", "0",
              " ", "25", " ", " ", "0", "N")
    con = make_con([h_plan("28100"), r_plan, s_plan], GEO)
    plans.build(con)
    bridge = con.execute(
        "SELECT plan_key, county_code FROM plan_county ORDER BY 1, 2"
    ).df()
    got = set(map(tuple, bridge.values))
    assert got == {
        ("H0028_007_000", "28100"),
        ("R5826_001_000", "01000"),   # MA region 10 has two counties
        ("R5826_001_000", "01010"),
        ("S5601_001_000", "28100"),   # PDP region 25
    }


def test_multiple_formularies_per_plan_raises():
    bad = list(h_plan("28100"))
    bad2 = list(h_plan("01000"))
    bad2[5] = "99999999"
    con = make_con([tuple(bad), tuple(bad2)], GEO)
    with pytest.raises(ValueError, match="formulary"):
        plans.build(con)
