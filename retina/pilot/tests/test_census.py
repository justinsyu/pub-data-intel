from pathlib import Path

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
