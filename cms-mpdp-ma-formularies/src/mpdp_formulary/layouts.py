"""File locations, expected headers, encodings, and row bounds for the MPDP PUF.

Single source of truth. The real files have inconsistent double spaces in their
names, so files are located by lowercase prefix, never by exact name. Header
columns are compared case-insensitively because the insulin file's cost columns
are lowercase in the shipped header.
"""
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "extracted"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
OUT_DIR = PROJECT_ROOT / "data" / "out"
DASH_DATA_DIR = PROJECT_ROOT / "dashboard" / "data"

VINTAGE = "2026-05-31"
CONTRACT_YEAR = "2026"


@dataclass(frozen=True)
class Layout:
    key: str
    prefix: str            # lowercase filename prefix
    encoding: str
    columns: tuple


LAYOUTS = {
    "plan_info": Layout(
        key="plan_info",
        prefix="plan information",
        encoding="latin-1",
        columns=(
            "CONTRACT_ID", "PLAN_ID", "SEGMENT_ID", "CONTRACT_NAME", "PLAN_NAME",
            "FORMULARY_ID", "PREMIUM", "DEDUCTIBLE", "MA_REGION_CODE",
            "PDP_REGION_CODE", "STATE", "COUNTY_CODE", "SNP", "PLAN_SUPPRESSED_YN",
        ),
    ),
    "basic": Layout(
        key="basic",
        prefix="basic drugs formulary file",
        encoding="utf-8",
        columns=(
            "FORMULARY_ID", "FORMULARY_VERSION", "CONTRACT_YEAR", "RXCUI", "NDC",
            "TIER_LEVEL_VALUE", "QUANTITY_LIMIT_YN", "QUANTITY_LIMIT_AMOUNT",
            "QUANTITY_LIMIT_DAYS", "PRIOR_AUTHORIZATION_YN", "STEP_THERAPY_YN",
            "SELECTED_DRUG_YN",
        ),
    ),
    "excluded": Layout(
        key="excluded",
        prefix="excluded drugs formulary file",
        encoding="utf-8",
        columns=(
            "CONTRACT_ID", "PLAN_ID", "RXCUI", "TIER", "QUANTITY_LIMIT_YN",
            "QUANTITY_LIMIT_AMOUNT", "QUANTITY_LIMIT_DAYS", "PRIOR_AUTH_YN",
            "STEP_THERAPY_YN", "CAPPED_BENEFIT_YN",
        ),
    ),
    "bene_cost": Layout(
        key="bene_cost",
        prefix="beneficiary cost file",
        encoding="utf-8",
        columns=(
            "CONTRACT_ID", "PLAN_ID", "SEGMENT_ID", "COVERAGE_LEVEL", "TIER",
            "DAYS_SUPPLY",
            "COST_TYPE_PREF", "COST_AMT_PREF", "COST_MIN_AMT_PREF", "COST_MAX_AMT_PREF",
            "COST_TYPE_NONPREF", "COST_AMT_NONPREF", "COST_MIN_AMT_NONPREF",
            "COST_MAX_AMT_NONPREF",
            "COST_TYPE_MAIL_PREF", "COST_AMT_MAIL_PREF", "COST_MIN_AMT_MAIL_PREF",
            "COST_MAX_AMT_MAIL_PREF",
            "COST_TYPE_MAIL_NONPREF", "COST_AMT_MAIL_NONPREF",
            "COST_MIN_AMT_MAIL_NONPREF", "COST_MAX_AMT_MAIL_NONPREF",
            "TIER_SPECIALTY_YN", "DED_APPLIES_YN",
        ),
    ),
    "insulin": Layout(
        key="insulin",
        prefix="insulin beneficiary cost file",
        encoding="utf-8",
        columns=(
            "CONTRACT_ID", "PLAN_ID", "SEGMENT_ID", "TIER", "DAYS_SUPPLY",
            "COPAY_AMT_PREF_INSLN", "COPAY_AMT_NONPREF_INSLN",
            "COPAY_AMT_MAIL_PREF_INSLN", "COPAY_AMT_MAIL_NONPREF_INSLN",
            "COIN_AMT_PREF_INSLN", "COIN_AMT_NONPREF_INSLN",
            "COIN_AMT_MAIL_PREF_INSLN", "COIN_AMT_MAIL_NONPREF_INSLN",
        ),
    ),
    "indication": Layout(
        key="indication",
        prefix="indication based coverage formulary file",
        encoding="utf-8",
        columns=("CONTRACT_ID", "PLAN_ID", "RXCUI", "DISEASE"),
    ),
    "geo": Layout(
        key="geo",
        prefix="geographic locator file",
        encoding="utf-8",
        columns=(
            "COUNTY_CODE", "STATENAME", "COUNTY", "MA_REGION_CODE", "MA_REGION",
            "PDP_REGION_CODE", "PDP_REGION",
        ),
    ),
}

# Loose sanity bounds on data row counts (excluding header) for the full files.
ROW_BOUNDS = {
    "plan_info": (50_000, 500_000),
    "basic": (500_000, 5_000_000),
    "excluded": (1_000, 200_000),
    "bene_cost": (50_000, 1_000_000),
    "insulin": (5_000, 500_000),
    "indication": (50, 50_000),
    "geo": (3_000, 4_000),
}


def find_raw_file(layout: Layout, raw_dir: Path = RAW_DIR) -> Path:
    matches = [
        p for p in sorted(raw_dir.iterdir())
        if p.suffix.lower() == ".txt"
        and p.name.lower().startswith(layout.prefix)
        and "sample" not in p.name.lower()
    ]
    if len(matches) != 1:
        raise FileNotFoundError(
            f"{layout.key}: expected exactly 1 file with prefix {layout.prefix!r} "
            f"in {raw_dir}, found {[p.name for p in matches]}"
        )
    return matches[0]


def validate_header(layout: Layout, path: Path) -> None:
    with open(path, encoding=layout.encoding) as f:
        header = f.readline().rstrip("\r\n").split("|")
    got = [h.strip().upper() for h in header]
    want = [c.upper() for c in layout.columns]
    if got != want:
        raise ValueError(
            f"{layout.key}: header mismatch in {path.name}\n got: {got}\nwant: {want}"
        )
