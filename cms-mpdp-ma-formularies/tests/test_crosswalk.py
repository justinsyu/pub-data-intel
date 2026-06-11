import pandas as pd
import pytest

from mpdp_formulary.ingest import crosswalk

CENSUS_TEXT = """STATE|STATEFP|COUNTYFP|COUNTYNS|COUNTYNAME|CLASSFP|FUNCSTAT
AL|01|001|00161526|Autauga County|H1|A
LA|22|001|00558389|Acadia Parish|H1|A
VA|51|159|01480139|Richmond County|H1|A
VA|51|760|01498434|Richmond city|C7|F
NE|31|055|00835880|Douglas County|H1|A
"""


def geo(rows):
    return pd.DataFrame(rows, columns=["COUNTY_CODE", "STATENAME", "COUNTY"])


def test_exact_and_designator_stripped_matching():
    g = geo([
        ("01000", "Alabama", "Autauga"),
        ("19450", "Louisiana", "Acadia"),
        ("28100", "Nebraska", "Douglas"),
    ])
    out, rate = crosswalk.build(g, CENSUS_TEXT)
    m = out.set_index("county_code")["fips"]
    assert m["01000"] == "01001"
    assert m["19450"] == "22001"
    assert m["28100"] == "31055"
    assert rate == 1.0


def test_designator_collision_prefers_county():
    g = geo([("52280", "Virginia", "Richmond")])
    out, _ = crosswalk.build(g, CENSUS_TEXT)
    assert out.set_index("county_code")["fips"]["52280"] == "51159"


def test_city_matches_exact_before_stripping():
    g = geo([("52760", "Virginia", "Richmond City")])
    out, _ = crosswalk.build(g, CENSUS_TEXT)
    assert out.set_index("county_code")["fips"]["52760"] == "51760"


def test_unmatched_gets_null_and_rate_drops():
    g = geo([("01000", "Alabama", "Autauga"), ("99999", "Alabama", "Nonesuch")])
    out, rate = crosswalk.build(g, CENSUS_TEXT, min_rate=0.0)
    m = out.set_index("county_code")["fips"]
    assert pd.isna(m["99999"])
    assert rate == 0.5


def test_low_match_rate_raises():
    g = geo([("99999", "Alabama", "Nonesuch")])
    with pytest.raises(ValueError, match="match rate"):
        crosswalk.build(g, CENSUS_TEXT)
