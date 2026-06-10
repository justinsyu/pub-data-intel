"""Ophthalmology providers from the CMS Doctors and Clinicians national file (PDC)."""
import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest import cms_api

# Pinned against live PDC NDF (dataset id mj5m-pzi6): columns npi, pri_spec, state, zip_code.
COL_NPI = "npi"
COL_SPEC = "pri_spec"
COL_STATE = "state"
COL_ZIP = "zip_code"
SPECIALTY_VALUE = "OPHTHALMOLOGY"
# The PDC DKAN datastore rejects the "=" operator with HTTP 400;
# "LIKE" with an exact value (no wildcards) returns identical results.
SPECIALTY_OPERATOR = "LIKE"


def parse_dac(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["zip5"] = df[COL_ZIP].astype(str).str[:5]
    out = df.rename(columns={COL_NPI: "npi", COL_STATE: "state"})[
        ["npi", "state", "zip5"]
    ].drop_duplicates(subset=["npi"])
    return out.reset_index(drop=True)


def load_ophth_providers() -> pd.DataFrame:
    ds = cms_api.pdc_resolve(sources.PDC_DATASET_TITLES["dac_ndf"])
    rows = cms_api.pdc_query(ds, [(COL_SPEC, SPECIALTY_OPERATOR, SPECIALTY_VALUE)])
    return parse_dac(rows)
