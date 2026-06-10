"""Medicare Physician & Other Practitioners by Provider and Service, filtered to retina codes."""
import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest import cms_api

# Column names verified live against the data-api in a prior task.
COLS = {
    "Rndrng_NPI": "npi",
    "Rndrng_Prvdr_Last_Org_Name": "last_name",
    "Rndrng_Prvdr_State_Abrvtn": "state",
    "Rndrng_Prvdr_Zip5": "zip5",
    "HCPCS_Cd": "hcpcs",
    "Tot_Srvcs": "services",
    "Tot_Benes": "benes",
    "Avg_Mdcr_Pymt_Amt": "avg_payment",
    "Place_Of_Srvc": "place_of_service",
}
NUMERIC = ["services", "benes", "avg_payment"]


def parse_mupphy(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)[list(COLS)].rename(columns=COLS)
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def fetch_mupphy_by_hcpcs(hcpcs_codes: list[str]) -> pd.DataFrame:
    url = cms_api.resolve_data_cms_dataset(sources.CMS_DATASET_TITLES["mupphy"])
    frames = []
    for code in hcpcs_codes:
        rows = cms_api.fetch_all(url, filters={"HCPCS_Cd": code})
        if rows:
            frames.append(parse_mupphy(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=list(COLS.values()))
