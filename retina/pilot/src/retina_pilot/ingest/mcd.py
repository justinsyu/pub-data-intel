"""Medicare Coverage Database: retina LCD/article extraction from operator-downloaded zips.

Manual step (primary path): download the current Article and LCD CSV archives from
https://www.cms.gov/medicare-coverage-database/downloads/downloadable-databases.aspx
(license click-through) into retina/pilot/data/cache/mcd/.

Scripted fallback: the direct downloads.cms.gov export URLs in sources.py currently
respond 200 without a browser session (verified 2026-06-10). load_mcd_retina can
fetch the article archive itself when called with download=True; the default is
False so tests and offline runs stay network-free. If the direct URL stops working,
the function falls back to the documented empty-frame path.

Real export layout (verified 2026-06-10): the outer zip nests the CSV tables in an
inner *_csv.zip (plus a .mdb and PDFs); CSVs are latin-1 encoded. Key tables:
article.csv (article_id, title, last_updated, ...) and article_x_hcpc_code.csv
(article_id, hcpc_code_id, ...).
"""
import csv
import io
import zipfile
from pathlib import Path

import pandas as pd

from retina_pilot import codes, sources
from retina_pilot.ingest import http_cache

RETINA_HCPCS = set(codes.ALL_DRUG_HCPCS) | set(codes.PROCEDURE_HCPCS)

_EMPTY_COLUMNS = ["article_id", "title", "contractor", "last_updated"]


def _candidate_zips(outer: zipfile.ZipFile):
    """Yield the archive itself plus any nested zips (real export nests *_csv.zip)."""
    yield outer
    for name in outer.namelist():
        if name.lower().endswith(".zip"):
            yield zipfile.ZipFile(io.BytesIO(outer.read(name)))


def _read_table(zf: zipfile.ZipFile, name_contains: str) -> pd.DataFrame:
    matches = [
        n for n in zf.namelist()
        if name_contains in n.lower() and n.lower().endswith(".csv")
    ]
    if not matches:
        return pd.DataFrame()
    # Shortest name is the base table (article.csv, article_x_hcpc_code.csv)
    # rather than satellites (article_x_..., ..._group.csv).
    name = min(matches, key=lambda n: (len(n), n))
    # Real article.csv carries HTML description blobs above the csv module's
    # default 128 KiB field limit; 2**31 - 1 is the max C long on Windows.
    csv.field_size_limit(2**31 - 1)
    return pd.read_csv(
        io.BytesIO(zf.read(name)), dtype=str, sep=None, engine="python",
        encoding="latin-1",
    )


def filter_retina(articles: pd.DataFrame, hcpc_xwalk: pd.DataFrame) -> pd.DataFrame:
    hits = hcpc_xwalk[hcpc_xwalk["hcpc_code_id"].isin(RETINA_HCPCS)]["article_id"].unique()
    return articles[articles["article_id"].isin(hits)].reset_index(drop=True)


def _download_article_zip(mcd_dir: Path) -> list[Path]:
    """Fetch the current article export via the direct URL; empty list on failure."""
    try:
        payload = http_cache.cached_get(sources.URLS["mcd_current_article"])
    except Exception:
        return []
    mcd_dir.mkdir(parents=True, exist_ok=True)
    path = mcd_dir / "current_article.zip"
    path.write_bytes(payload)
    return [path]


def load_mcd_retina(mcd_dir: Path, download: bool = False) -> dict:
    mcd_dir = Path(mcd_dir)
    zips = sorted(mcd_dir.glob("*.zip"))
    if not zips and download:
        zips = _download_article_zip(mcd_dir)
    if not zips:
        return {"articles": pd.DataFrame(columns=_EMPTY_COLUMNS)}
    articles_frames, xwalk_frames = [], []
    for zp in zips:
        with zipfile.ZipFile(zp) as outer:
            for zf in _candidate_zips(outer):
                art = _read_table(zf, "article")
                xw = _read_table(zf, "hcpc")
                if not art.empty:
                    articles_frames.append(art)
                if not xw.empty:
                    xwalk_frames.append(xw)
    if not articles_frames or not xwalk_frames:
        return {"articles": pd.DataFrame(columns=_EMPTY_COLUMNS)}
    articles = pd.concat(articles_frames, ignore_index=True)
    xwalk = pd.concat(xwalk_frames, ignore_index=True)
    articles.columns = [c.strip().lower() for c in articles.columns]
    xwalk.columns = [c.strip().lower() for c in xwalk.columns]
    return {"articles": filter_retina(articles, xwalk)}
