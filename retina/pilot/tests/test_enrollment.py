import retina_pilot.ingest.enrollment as enr


def test_parse_enrollment_rows():
    rows = [
        {"BENE_FIPS_CD": "01001", "BENE_STATE_ABRVTN": "AL", "BENE_COUNTY_DESC": "Autauga",
         "TOT_BENES": "12000", "ORGNL_MDCR_BENES": "7000", "MA_AND_OTH_BENES": "5000",
         "MONTH": "Year", "YEAR": "2024", "BENE_GEO_LVL": "County"},
        {"BENE_FIPS_CD": "", "BENE_STATE_ABRVTN": "AL", "BENE_COUNTY_DESC": "Unknown",
         "TOT_BENES": "10", "ORGNL_MDCR_BENES": "5", "MA_AND_OTH_BENES": "5",
         "MONTH": "Year", "YEAR": "2024", "BENE_GEO_LVL": "County"},
    ]
    df = enr.parse_enrollment(rows)
    assert len(df) == 1  # blank-FIPS row dropped
    row = df.iloc[0]
    assert row["fips"] == "01001"
    assert row["ma_pct"] == 41.7


def test_parse_enrollment_zero_total_dropped():
    rows = [
        {"BENE_FIPS_CD": "01001", "TOT_BENES": "0", "MA_AND_OTH_BENES": "500",
         "BENE_GEO_LVL": "County", "MONTH": "Year", "YEAR": "2024"},
    ]
    df = enr.parse_enrollment(rows)
    assert df.empty
