import duckdb
import pytest

from mpdp_formulary import layouts
from mpdp_formulary.ingest import raw_files

TEST_BOUNDS = {k: (1, 100) for k in layouts.LAYOUTS}


def make_raw_dir(tmp_path):
    """Minimal valid versions of all seven files, 2 data rows each."""
    rows = {
        "plan information  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|SEGMENT_ID|CONTRACT_NAME|PLAN_NAME|FORMULARY_ID|PREMIUM|DEDUCTIBLE|MA_REGION_CODE|PDP_REGION_CODE|STATE|COUNTY_CODE|SNP|PLAN_SUPPRESSED_YN\n"
            "H0028|007|000|CHA HMO, INC.|Humana Gold Plus \xe9|00026408|35.60|615| | |NE|28100|2|N\n"
            "S5601|001|000|PDP ORG|Some PDP|00026409|12.30|0| |22| | |0|N\n"
        ),
        "basic drugs formulary file  20260531.txt": (
            "FORMULARY_ID|FORMULARY_VERSION|CONTRACT_YEAR|RXCUI|NDC|TIER_LEVEL_VALUE|QUANTITY_LIMIT_YN|QUANTITY_LIMIT_AMOUNT|QUANTITY_LIMIT_DAYS|PRIOR_AUTHORIZATION_YN|STEP_THERAPY_YN|SELECTED_DRUG_YN\n"
            "00026408|17|2026|1551300|00002143380|3|Y|2|28|Y|N|N\n"
            "00026409|17|2026|1551300|00002143380|2|N| | |N|N|N\n"
        ),
        "excluded drugs formulary file  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|RXCUI|TIER|QUANTITY_LIMIT_YN|QUANTITY_LIMIT_AMOUNT|QUANTITY_LIMIT_DAYS|PRIOR_AUTH_YN|STEP_THERAPY_YN|CAPPED_BENEFIT_YN\n"
            "H0028|007|312950|1|1|6|30|N|N|N\n"
            "H0028|007|1367410|1|0| | |N|N|N\n"
        ),
        "beneficiary cost file  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|SEGMENT_ID|COVERAGE_LEVEL|TIER|DAYS_SUPPLY|COST_TYPE_PREF|COST_AMT_PREF|COST_MIN_AMT_PREF|COST_MAX_AMT_PREF|COST_TYPE_NONPREF|COST_AMT_NONPREF|COST_MIN_AMT_NONPREF|COST_MAX_AMT_NONPREF|COST_TYPE_MAIL_PREF|COST_AMT_MAIL_PREF|COST_MIN_AMT_MAIL_PREF|COST_MAX_AMT_MAIL_PREF|COST_TYPE_MAIL_NONPREF|COST_AMT_MAIL_NONPREF|COST_MIN_AMT_MAIL_NONPREF|COST_MAX_AMT_MAIL_NONPREF|TIER_SPECIALTY_YN|DED_APPLIES_YN\n"
            "H0028|007|000|0|1|1|0|0|0|0|1|0|0|0|1|0|0|0|1|10|0|0|N|N\n"
            "H0028|007|000|1|1|1|1|5|0|0|2|0.25|1|50|1|0|0|0|1|10|0|0|N|Y\n"
        ),
        "insulin beneficiary cost file  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|SEGMENT_ID|TIER|DAYS_SUPPLY|copay_amt_pref_insln|copay_amt_nonpref_insln|copay_amt_mail_pref_insln|copay_amt_mail_nonpref_insln|coin_amt_pref_insln|coin_amt_nonpref_insln|coin_amt_mail_pref_insln|coin_amt_mail_nonpref_insln\n"
            "H0028|007|000|1|1| |0.00|0.00|10.00| |0.00|0.00|0.25\n"
            "H0028|007|000|1|2| |0.00|0.00|30.00| |0.00|0.00|0.25\n"
        ),
        "Indication Based Coverage Formulary File  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|RXCUI|DISEASE\n"
            "H1994|001|1745108|SPONDYLITIS, ANKYLOSING\n"
            "H1994|001|1876406|ASTHMA\n"
        ),
        "geographic locator file 20260531.txt": (
            "COUNTY_CODE|STATENAME|COUNTY|MA_REGION_CODE|MA_REGION|PDP_REGION_CODE|PDP_REGION\n"
            "01000|Alabama|Autauga|10|Alabama and Tennessee|12|Alabama, Tennessee\n"
            "28100|Nebraska|Douglas|19|Upper Midwest|25|Upper Midwest\n"
        ),
    }
    raw = tmp_path / "extracted"
    raw.mkdir()
    for name, text in rows.items():
        enc = "latin-1" if name.startswith("plan information") else "utf-8"
        (raw / name).write_text(text, encoding=enc)
    return raw


def test_load_all_writes_seven_parquets(tmp_path):
    raw = make_raw_dir(tmp_path)
    out = tmp_path / "out"
    counts = raw_files.load_all(raw, out, bounds=TEST_BOUNDS)
    assert set(counts) == set(layouts.LAYOUTS)
    assert all(n == 2 for n in counts.values())
    con = duckdb.connect()
    df = con.execute(
        f"SELECT * FROM read_parquet('{(out / 'raw_plan_info.parquet').as_posix()}')"
    ).df()
    assert list(df.columns) == list(layouts.LAYOUTS["plan_info"].columns)
    assert "\xe9" in df["PLAN_NAME"][0], "latin-1 byte must round-trip"


def test_load_all_bounds_violation_raises(tmp_path):
    raw = make_raw_dir(tmp_path)
    bad = dict(TEST_BOUNDS)
    bad["basic"] = (10, 100)
    with pytest.raises(ValueError, match="basic"):
        raw_files.load_all(raw, tmp_path / "out", bounds=bad)
