"""Map SSA county codes to FIPS by state + county-name matching.

The PUF geographic locator carries bare county names ("Autauga"); the Census
county file carries designated names ("Autauga County"). Pass 1 matches full
normalized names (catches Virginia independent cities like "Richmond City");
pass 2 strips the Census designator suffix and, on duplicates within a state,
prefers the row whose raw name ends in "County".
"""
import csv
import io
import re
from pathlib import Path

import pandas as pd

from . import http_cache

CENSUS_COUNTY_URL = (
    "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"
)
MIN_MATCH_RATE = 0.97

STATE_ABBREV = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN",
    "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA",
    "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
    "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR",
    "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
    "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
    "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "PUERTO RICO": "PR", "GUAM": "GU", "VIRGIN ISLANDS": "VI",
    "U.S. VIRGIN ISLANDS": "VI", "AMERICAN SAMOA": "AS",
    "NORTHERN MARIANA ISLANDS": "MP",
}

_DESIGNATORS = (
    " CITY AND BOROUGH", " CENSUS AREA", " MUNICIPALITY", " MUNICIPIO",
    " BOROUGH", " COUNTY", " PARISH", " DISTRICT", " ISLAND",
)


def _norm(name: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper())
    return re.sub(r"\s+", " ", s).strip()


def _strip_designator(norm_name: str) -> str:
    for d in _DESIGNATORS:
        if norm_name.endswith(d):
            return norm_name[: -len(d)].strip()
    return norm_name


def fetch_census_counties(cache_dir: Path) -> str:
    return http_cache.fetch(CENSUS_COUNTY_URL, cache_dir).decode("utf-8")


def build(geo_df: pd.DataFrame, census_text: str,
          min_rate: float = MIN_MATCH_RATE) -> tuple[pd.DataFrame, float]:
    """geo_df: columns COUNTY_CODE, STATENAME, COUNTY (from the geo locator).

    Returns (df[county_code, fips], match_rate). fips is None when unmatched.
    """
    census = pd.read_csv(io.StringIO(census_text), sep="|", dtype=str,
                         quoting=csv.QUOTE_NONE, keep_default_na=False)
    census["fips"] = census["STATEFP"] + census["COUNTYFP"]
    census["norm"] = census["COUNTYNAME"].map(_norm)
    census["stripped"] = census["norm"].map(_strip_designator)
    census["is_county"] = census["norm"].str.endswith(" COUNTY")

    exact = {}      # (state_abbrev, norm_name) -> fips
    stripped = {}   # (state_abbrev, stripped_name) -> fips, county-designated wins
    for row in census.itertuples():
        exact[(row.STATE, row.norm)] = row.fips
        key = (row.STATE, row.stripped)
        if key not in stripped or row.is_county:
            stripped[key] = row.fips

    records, matched = [], 0
    for row in geo_df.itertuples():
        ab = STATE_ABBREV.get(_norm(row.STATENAME))
        name = _norm(row.COUNTY)
        fips = None
        if ab:
            fips = exact.get((ab, name)) or stripped.get((ab, _strip_designator(name)))
        if fips:
            matched += 1
        records.append({"county_code": row.COUNTY_CODE, "fips": fips})

    rate = matched / len(records) if records else 1.0
    if rate < min_rate:
        misses = [r["county_code"] for r in records if r["fips"] is None][:20]
        raise ValueError(
            f"crosswalk: match rate {rate:.4f} below {min_rate}; "
            f"first unmatched SSA codes: {misses}"
        )
    return pd.DataFrame(records), rate
