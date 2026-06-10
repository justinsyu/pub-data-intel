"""Stage 2 ingests: QDD drug spend, HRSA 340B, ClinicalTrials.gov v2, Open Payments, DAC affiliations."""
import io
from pathlib import Path

import pandas as pd

from retina_pilot import codes, sources
from retina_pilot.ingest import cms_api
from retina_pilot.ingest.http_cache import cached_get, cached_json

# ---- QDD (Medicare Part B Spending by Drug) ----
# Real API columns (2025-06 probe): year-suffixed format, e.g. Tot_Spndng_2023, Tot_Clms_2023.
# parse_qdd auto-detects the latest year suffix; falls back to bare column names for tests.

def _latest_year_col(cols: list[str], prefix: str) -> str:
    """Return the column with the highest year suffix matching prefix, or prefix if not found."""
    candidates = [c for c in cols if c.startswith(prefix + "_") and c[len(prefix)+1:].isdigit()]
    if candidates:
        return max(candidates, key=lambda c: int(c.rsplit("_", 1)[-1]))
    return prefix  # bare column (test fixtures)


def parse_qdd(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[df["HCPCS_Cd"].isin(codes.ALL_DRUG_HCPCS)]
    cols = list(df.columns)
    spndng_col = _latest_year_col(cols, "Tot_Spndng")
    clms_col = _latest_year_col(cols, "Tot_Clms")
    return pd.DataFrame({
        "hcpcs": df["HCPCS_Cd"],
        "spending": pd.to_numeric(df[spndng_col], errors="coerce"),
        "claims": pd.to_numeric(df[clms_col], errors="coerce"),
    }).reset_index(drop=True)


def load_qdd() -> pd.DataFrame:
    url = cms_api.resolve_data_cms_dataset(sources.CMS_DATASET_TITLES["qdd"])
    return parse_qdd(cms_api.fetch_all(url))


# ---- HRSA 340B covered entities ----
# The OPAIS daily export has no static URL (Blazor session download). Fallback chain:
# 1) try the registry URL; 2) read a manually-downloaded CSV from data/cache/hrsa/;
# 3) return an empty frame (site-of-care dimension degrades; data gap recorded downstream).

HRSA_LOCAL_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "hrsa"


def parse_340b(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), dtype=str)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df[df["participating"].str.upper().eq("TRUE")]
    return pd.DataFrame({
        "ce_id": df["340b_id"],
        "entity_name": df["entity_name"],
        "state": df["state"],
        "zip5": df["zip_code"].astype(str).str[:5],
    }).reset_index(drop=True)


def load_340b() -> pd.DataFrame:
    empty = pd.DataFrame(columns=["ce_id", "entity_name", "state", "zip5"])
    try:
        return parse_340b(cached_get(sources.URLS["hrsa_340b_ce"]))
    except Exception:
        pass
    local = sorted(HRSA_LOCAL_DIR.glob("*.csv"))
    if local:
        return parse_340b(local[-1].read_bytes())
    print("340B: no data — download the covered-entity daily report from https://340bopais.hrsa.gov/reports into data/cache/hrsa/")
    return empty


# ---- ClinicalTrials.gov v2 ----

RETINA_CONDITIONS = [
    "wet age-related macular degeneration",
    "geographic atrophy",
    "diabetic macular edema",
    "retinal vein occlusion",
]


def fetch_retina_studies(statuses=("RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION")) -> list[dict]:
    studies, seen = [], set()
    for cond in RETINA_CONDITIONS:
        token = None
        while True:
            params = {"query.cond": cond, "filter.overallStatus": "|".join(statuses),
                      "pageSize": 100}
            if token:
                params["pageToken"] = token
            payload = cached_json(sources.URLS["clinicaltrials_v2"], params)
            for s in payload.get("studies", []):
                nct = s["protocolSection"]["identificationModule"]["nctId"]
                if nct not in seen:
                    seen.add(nct)
                    studies.append(s)
            token = payload.get("nextPageToken")
            if not token:
                break
    return studies


def parse_trial_sites(studies: list[dict]) -> pd.DataFrame:
    rows = []
    for s in studies:
        ps = s["protocolSection"]
        nct = ps["identificationModule"]["nctId"]
        title = ps["identificationModule"].get("briefTitle", "")
        for loc in ps.get("contactsLocationsModule", {}).get("locations", []):
            if loc.get("country") != "United States":
                continue
            rows.append({
                "nct_id": nct, "title": title,
                "facility": loc.get("facility", ""), "city": loc.get("city", ""),
                "state": loc.get("state", ""), "zip5": str(loc.get("zip", ""))[:5],
            })
    return pd.DataFrame(rows, columns=["nct_id", "title", "facility", "city", "state", "zip5"])


# ---- Open Payments (general payments, ophthalmology) ----

OP_DATASET_TITLE = "General Payment Data"  # latest program year; resolved by title


def parse_open_payments(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return pd.DataFrame({
        "npi": df["covered_recipient_npi"],
        "specialty": df["covered_recipient_specialty_1"],
        "state": df["recipient_state"],
        "amount": pd.to_numeric(df["total_amount_of_payment_usdollars"], errors="coerce"),
    }).reset_index(drop=True)


def fetch_ophth_payments(states: list[str]) -> pd.DataFrame:
    ds = cms_api.openpayments_resolve(OP_DATASET_TITLE)
    frames = []
    for st in states:
        # limit=500 probed safe against the DKAN cap for this endpoint
        rows = cms_api.openpayments_query(ds, [
            ("covered_recipient_specialty_1", "contains", "Ophthalmology"),
            ("recipient_state", "=", st),
        ], limit=500)
        if rows:
            frames.append(parse_open_payments(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["npi", "specialty", "state", "amount"])


# ---- DAC facility affiliations ----

def fetch_affiliations(npis: list[str]) -> pd.DataFrame:
    ds = cms_api.pdc_resolve(sources.PDC_DATASET_TITLES["dac_fa"])
    frames = []
    for npi in npis:
        rows = cms_api.pdc_query(ds, [("npi", "LIKE", npi)], limit=50)
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        return pd.DataFrame(columns=["npi", "facility_type"])
    df = pd.concat(frames, ignore_index=True)
    return df[["npi", "facility_type"]]
