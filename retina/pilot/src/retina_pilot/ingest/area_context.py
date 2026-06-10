"""CDC SVI and USDA RUCC county files."""
import io

import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest.http_cache import cached_get


def parse_svi(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), dtype={"FIPS": str})
    df["svi"] = pd.to_numeric(df["RPL_THEMES"], errors="coerce")
    df = df[df["svi"] >= 0]  # -999 flags missing
    return pd.DataFrame({"fips": df["FIPS"].str.zfill(5), "svi": df["svi"]}).reset_index(drop=True)


def load_svi() -> pd.DataFrame:
    return parse_svi(cached_get(sources.URLS["cdc_svi_county"]))


def parse_rucc(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), dtype=str, encoding="latin-1")
    df = df[df["Attribute"].str.startswith("RUCC")]
    return pd.DataFrame({
        "fips": df["FIPS"].str.zfill(5),
        "rucc": pd.to_numeric(df["Value"], errors="coerce").astype("Int64"),
    }).dropna().reset_index(drop=True)


def load_rucc() -> pd.DataFrame:
    return parse_rucc(cached_get(sources.URLS["usda_rucc"]))
