"""Census ingests: county gazetteer, NBER CBSA crosswalk, ACS 65+ population, ZCTA-county."""
import io
import json
import os
import zipfile

import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest.http_cache import cached_get

ACS_VARS = [
    "B01001_001E",  # total population
    # male 65+
    "B01001_020E", "B01001_021E", "B01001_022E", "B01001_023E", "B01001_024E", "B01001_025E",
    # female 65+
    "B01001_044E", "B01001_045E", "B01001_046E", "B01001_047E", "B01001_048E", "B01001_049E",
]


def parse_gazetteer(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame({
        "fips": df["GEOID"].str.zfill(5),
        "state": df["USPS"].str.strip(),
        "county_name": df["NAME"].str.strip(),
        "lat": df["INTPTLAT"].astype(float),
        "lon": df["INTPTLONG"].astype(float),
    })
    return out


def load_county_frame() -> pd.DataFrame:
    raw = cached_get(sources.URLS["census_gazetteer_counties"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        inner = zf.read(zf.namelist()[0])
    return parse_gazetteer(inner)


def parse_cbsa_xwalk(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding="latin-1")
    df = df.dropna(subset=["fipsstatecode", "fipscountycode"])
    out = pd.DataFrame({
        "fips": df["fipsstatecode"].str.strip().str.zfill(2) + df["fipscountycode"].str.strip().str.zfill(3),
        "cbsa_code": df["cbsacode"],
        "cbsa_title": df["cbsatitle"],
        "metro_micro": df["metropolitanmicropolitanstatis"],
    })
    return out


def load_cbsa_xwalk() -> pd.DataFrame:
    return parse_cbsa_xwalk(cached_get(sources.URLS["nber_cbsa_xwalk"]))


def parse_acs_pop65(payload: list[list[str]]) -> pd.DataFrame:
    header, *rows = payload
    df = pd.DataFrame(rows, columns=header)
    age_cols = ACS_VARS[1:]
    for c in ACS_VARS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return pd.DataFrame({
        "fips": df["state"] + df["county"],
        "pop_total": df["B01001_001E"],
        "pop65": df[age_cols].sum(axis=1),
    })


def load_pop65() -> pd.DataFrame:
    params = {"get": "NAME," + ",".join(ACS_VARS), "for": "county:*"}
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params["key"] = key
    raw = cached_get(sources.URLS["census_acs5"], params)
    # The Census ACS API returns an HTML error page when no key is provided or the
    # key is invalid. Detect this and surface a clear message rather than a JSON
    # parse error.
    if raw.lstrip()[:1] != b"[":
        raise RuntimeError(
            "Census ACS API returned a non-JSON response (likely missing or invalid key). "
            "Set the CENSUS_API_KEY environment variable. "
            "Register at https://api.census.gov/data/key_signup.html\n"
            f"Response preview: {raw[:200]!r}"
        )
    return parse_acs_pop65(json.loads(raw))


def load_zcta_county() -> pd.DataFrame:
    """ZCTA-to-county mapping; a ZIP maps to the county with the largest overlap."""
    raw = cached_get(sources.URLS["census_zcta_county_rel"])
    df = pd.read_csv(io.BytesIO(raw), sep="|", dtype=str)
    df["AREALAND_PART"] = pd.to_numeric(df["AREALAND_PART"], errors="coerce").fillna(0)
    df = df.dropna(subset=["GEOID_ZCTA5_20", "GEOID_COUNTY_20"])
    df = df.sort_values("AREALAND_PART", kind="mergesort").groupby("GEOID_ZCTA5_20").tail(1)
    return pd.DataFrame({"zcta": df["GEOID_ZCTA5_20"], "fips": df["GEOID_COUNTY_20"]}).reset_index(drop=True)
