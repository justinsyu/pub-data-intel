from pathlib import Path

import pandas as pd

import retina_pilot.ingest.census as census

FIX = Path(__file__).parent / "fixtures"


def test_parse_gazetteer():
    df = census.parse_gazetteer((FIX / "gaz_counties_sample.txt").read_bytes())
    assert list(df.columns) == ["fips", "state", "county_name", "lat", "lon"]
    assert df.loc[df.fips == "06037", "county_name"].iloc[0] == "Los Angeles County"


def test_parse_cbsa_xwalk():
    df = census.parse_cbsa_xwalk((FIX / "cbsa_xwalk_sample.csv").read_bytes())
    assert list(df.columns) == ["fips", "cbsa_code", "cbsa_title", "metro_micro"]
    assert df.loc[df.fips == "06037", "cbsa_code"].iloc[0] == "31080"


def test_parse_acs_pop65():
    payload = [
        ["NAME", "B01001_001E", "B01001_020E", "B01001_021E", "B01001_022E",
         "B01001_023E", "B01001_024E", "B01001_025E", "B01001_044E", "B01001_045E",
         "B01001_046E", "B01001_047E", "B01001_048E", "B01001_049E", "state", "county"],
        ["Autauga County, Alabama", "58761", "1000", "900", "800", "700", "600",
         "500", "1100", "950", "850", "750", "650", "550", "01", "001"],
    ]
    df = census.parse_acs_pop65(payload)
    assert df.iloc[0]["fips"] == "01001"
    assert df.iloc[0]["pop_total"] == 58761
    assert df.iloc[0]["pop65"] == 9350


def test_parse_popest_agesex():
    # Minimal inline fixture with two YEAR values to prove max-YEAR filtering.
    # Only columns used by parse_popest_agesex are needed: SUMLEV, STATE, COUNTY,
    # STNAME, CTYNAME, YEAR, POPESTIMATE, AGE65PLUS_TOT (plus padding to match count).
    # YEAR 4 = 7/1/2022, YEAR 5 = 7/1/2023 (max); only YEAR==5 rows should survive.
    header = "SUMLEV,STATE,COUNTY,STNAME,CTYNAME,YEAR,POPESTIMATE,AGE65PLUS_TOT"
    # older year row (YEAR=4) for county 06037 - should be filtered out
    row_old  = "050,06,037,California,Los Angeles County,4,9800000,1400000"
    # latest year row (YEAR=5) for county 06037 - should be kept
    row_new  = "050,06,037,California,Los Angeles County,5,9850000,1450000"
    # latest year row (YEAR=5) for county 30033 - should be kept
    row_new2 = "050,30,033,Montana,Garfield County,5,1000,300"
    csv_bytes = (header + "\n" + row_old + "\n" + row_new + "\n" + row_new2 + "\n").encode("latin-1")
    df = census.parse_popest_agesex(csv_bytes)
    # Only max-YEAR (5) rows should survive
    assert len(df) == 2
    assert set(df["fips"]) == {"06037", "30033"}
    la = df[df["fips"] == "06037"].iloc[0]
    assert int(la["pop_total"]) == 9850000
    assert int(la["pop65"]) == 1450000
    garfield = df[df["fips"] == "30033"].iloc[0]
    assert int(garfield["pop65"]) == 300
