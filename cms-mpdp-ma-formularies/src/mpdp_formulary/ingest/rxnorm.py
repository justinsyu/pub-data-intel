"""Resolve RXCUIs to names via RxNorm Prescribable Content, RxNav fallback."""
import csv
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from . import http_cache

RXNORM_URL = "https://download.nlm.nih.gov/rxnorm/RxNorm_full_prescribe_current.zip"
RXNAV_URL = "https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/historystatus.json"

RXNCONSO_COLS = [
    "RXCUI", "LAT", "TS", "LUI", "STT", "SUI", "ISPREF", "RXAUI", "SAUI",
    "SCUI", "SDUI", "SAB", "TTY", "CODE", "STR", "SRL", "SUPPRESS", "CVF",
    "_trail",
]
PRIMARY_TTYS = ("SCD", "SBD", "GPCK", "BPCK")
FALLBACK_TTYS = ("SCDG", "SBDG", "SCDC", "SBDC", "SCDF", "SBDF", "MIN", "PIN",
                 "IN", "BN", "DF")
GENERIC_TTYS = {"SCD", "GPCK", "SCDG", "SCDC", "SCDF", "IN", "MIN", "PIN"}
BRAND_TTYS = {"SBD", "BPCK", "SBDG", "SBDC", "SBDF", "BN"}
MIN_MATCH_RATE = 0.99
# More misses than this means the conso table is broken; the match-rate gate
# will raise anyway, so do not spend one HTTP call per missing RXCUI.
MAX_RXNAV_LOOKUPS = 500


def _read_rrf(f) -> pd.DataFrame:
    return pd.read_csv(
        f, sep="|", header=None, names=RXNCONSO_COLS, dtype=str,
        usecols=["RXCUI", "SAB", "TTY", "STR", "SUPPRESS"],
        quoting=csv.QUOTE_NONE, keep_default_na=False,
    )


def load_rxnconso(cache_dir: Path) -> pd.DataFrame:
    """Download (cached) the prescribable release and parse RXNCONSO.RRF."""
    raw = http_cache.fetch(RXNORM_URL, cache_dir)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        member = next(n for n in zf.namelist() if n.upper().endswith("RXNCONSO.RRF"))
        with zf.open(member) as f:
            df = _read_rrf(f)
    return df


def rxnav_lookup(rxcui: str, cache_dir: Path) -> tuple[str | None, str]:
    """Return (name, tty) from RxNav history status, or (None, '')."""
    data = json.loads(http_cache.fetch(RXNAV_URL.format(rxcui=rxcui), cache_dir))
    attrs = data.get("rxcuiStatusHistory", {}).get("attributes", {})
    return (attrs.get("name") or None), (attrs.get("tty") or "")


def _brand_generic(tty: str) -> str:
    if tty in GENERIC_TTYS:
        return "generic"
    if tty in BRAND_TTYS:
        return "brand"
    return ""


def build_name_table(rxcuis, conso: pd.DataFrame, rxnav) -> tuple[pd.DataFrame, float]:
    """rxcuis: iterable of distinct RXCUI strings appearing in the PUF.

    rxnav: callable rxcui -> (name, tty), or None to skip the API fallback
    (tests pass a stub; the CLI passes a cache-backed rxnav_lookup closure).
    """
    wanted = pd.Index(sorted({str(r) for r in rxcuis}), name="rxcui")
    usable = conso[(conso["SAB"] == "RXNORM") & (conso["SUPPRESS"] == "N")]

    resolved: dict[str, tuple[str, str]] = {}
    for ttys in (PRIMARY_TTYS, FALLBACK_TTYS):
        tier = usable[usable["TTY"].isin(ttys)]
        tier = tier.set_index("TTY").loc[[t for t in ttys if t in set(tier["TTY"])]]
        for row in tier.reset_index().itertuples():
            if row.RXCUI in wanted and row.RXCUI not in resolved:
                resolved[row.RXCUI] = (row.STR, row.TTY)

    missing = [r for r in wanted if r not in resolved]
    if rxnav is not None and len(missing) <= MAX_RXNAV_LOOKUPS:
        for rxcui in missing:
            name, tty = rxnav(rxcui)
            if name:
                resolved[rxcui] = (name, tty)

    rate = len(resolved) / len(wanted) if len(wanted) else 1.0
    if rate < MIN_MATCH_RATE:
        unmatched = [r for r in wanted if r not in resolved][:20]
        raise ValueError(
            f"rxnorm: match rate {rate:.4f} below {MIN_MATCH_RATE}; "
            f"first unmatched: {unmatched}"
        )

    out = pd.DataFrame(
        {
            "rxcui": list(wanted),
            "name": [resolved.get(r, ("(unknown)", ""))[0] for r in wanted],
            "tty": [resolved.get(r, ("", ""))[1] for r in wanted],
        }
    )
    out["brand_generic"] = out["tty"].map(_brand_generic)
    return out, rate
