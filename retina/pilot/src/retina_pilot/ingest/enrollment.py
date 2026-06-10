"""Medicare Monthly Enrollment: county Medicare totals and MA penetration."""
import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest import cms_api

# Probe-and-pin: verify these against a live row.
COL_FIPS = "BENE_FIPS_CD"
COL_TOT = "TOT_BENES"
COL_MA = "MA_AND_OTH_BENES"
FILTERS = {"BENE_GEO_LVL": "County", "MONTH": "Year"}


def parse_enrollment(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[df[COL_FIPS].astype(str).str.len() == 5]
    tot = pd.to_numeric(df[COL_TOT], errors="coerce")
    ma = pd.to_numeric(df[COL_MA], errors="coerce")
    out = pd.DataFrame({
        "fips": df[COL_FIPS].astype(str),
        "medicare_benes": tot,
        "ma_benes": ma,
        "ma_pct": (100 * ma / tot).round(1),
    })
    return out.dropna().reset_index(drop=True)


def load_enrollment() -> pd.DataFrame:
    url = cms_api.resolve_data_cms_dataset(sources.CMS_DATASET_TITLES["monthly_enrollment"])
    rows = cms_api.fetch_all(url, filters=FILTERS)
    raw = pd.DataFrame(rows)
    # Dataset spans multiple years; keep only the most recent YEAR.
    if "YEAR" in raw.columns:
        max_year = pd.to_numeric(raw["YEAR"], errors="coerce").max()
        raw = raw[pd.to_numeric(raw["YEAR"], errors="coerce") == max_year]
    return parse_enrollment(raw.to_dict("records"))
