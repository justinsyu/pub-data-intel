# MPDP Formulary Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a staged Python pipeline and fully static dashboard over the CMS Monthly Prescription Drug Plan Formulary PUF (May 2026) covering drug coverage by plan, excluded drugs, restrictions (PA/ST/QL), tier cost sharing, and a county map.

**Architecture:** Four-stage CLI (ingest, transform, aggregate, export) using DuckDB over the extracted pipe-delimited files, parquet intermediates in `data/out/`, JSON shards in `dashboard/data/`, consumed by a vanilla-JS + vendored-ECharts single-page dashboard served with `python -m http.server`. Drug-level market coverage is encoded as 328-character formulary status vectors; county aggregation happens client-side from a county-to-plan index.

**Tech Stack:** Python 3.11+, uv, duckdb, pandas, pyarrow, requests, pytest; vanilla JS, ECharts (vendored), Plotly counties GeoJSON (vendored).

**Spec:** `docs/superpowers/specs/2026-06-11-mpdp-formulary-dashboard-design.md` (read it first).

**Prerequisites (already true on this machine):** `cms-mpdp-ma-formularies/extracted/` contains the seven unzipped `.txt` files; `uv` is installed; the repo root is `C:\Users\Justin\Desktop\pub-data-intel` and all commands below run from `C:\Users\Justin\Desktop\pub-data-intel\cms-mpdp-ma-formularies` unless stated otherwise.

**Verified data facts the code relies on (do not re-derive):**
- All seven files are pipe-delimited with a header row. `plan information  20260531.txt` is Latin-1; all others are UTF-8.
- Flag columns carry `Y`/`N` (not `0`/`1` as the PDF record layout claims).
- File names contain inconsistent double spaces; locate files by lowercase prefix, never by exact name.
- Row counts (2026-05-31): plan info 112,294; basic formulary 1,123,842; excluded 13,717; beneficiary cost 172,660; insulin cost 43,066; indication 367; geo locator 3,279.
- Plan info has 329 distinct FORMULARY_IDs; basic formulary has 328. The orphan is reported, not fatal.
- COUNTY_CODE is an SSA code, not FIPS. The excluded/indication files have no SEGMENT_ID.

## File map

```
cms-mpdp-ma-formularies/
  pyproject.toml                          Task 1
  .gitignore                              Task 1
  README.md                               Task 17
  src/mpdp_formulary/
    __init__.py                           Task 1
    layouts.py                            Task 2   file locations, headers, row bounds
    cli.py                                Task 11  stage orchestrator
    ingest/__init__.py                    Task 1
    ingest/http_cache.py                  Task 3   disk-cached HTTP GET
    ingest/raw_files.py                   Task 4   txt -> raw_*.parquet with validation
    ingest/rxnorm.py                      Task 5   RXCUI -> name/TTY/brand-generic
    ingest/crosswalk.py                   Task 6   SSA county code -> FIPS
    transform/__init__.py                 Task 1
    transform/plans.py                    Task 7   plan_dim, plan_county bridge
    transform/drugs.py                    Task 8   formulary_drug (RXCUI grain), drug_dim
    aggregate/__init__.py                 Task 1
    aggregate/status_vectors.py           Task 9   per-drug 328-char vectors
    aggregate/stats.py                    Task 9   formulary/plan/national stats
    export/__init__.py                    Task 1
    export/dashboard_json.py              Task 10  all JSON writers
  tests/
    test_smoke.py                         Task 1
    test_layouts.py                       Task 2
    test_http_cache.py                    Task 3
    test_raw_files.py                     Task 4
    test_rxnorm.py                        Task 5
    test_crosswalk.py                     Task 6
    test_plans.py                         Task 7
    test_drugs.py                         Task 8
    test_aggregate.py                     Task 9
    test_export.py                        Task 10
  dashboard/
    index.html                            Task 12
    styles.css                            Task 12
    js/data.js                            Task 12
    js/fmt.js                             Task 12
    js/app.js                             Task 12
    js/views/overview.js                  Task 12 stub, Task 13 full
    js/views/methods.js                   Task 12 stub, Task 13 full
    js/views/drugs.js                     Task 12 stub, Task 14 full
    js/views/plans.js                     Task 12 stub, Task 15 full
    js/views/compare.js                   Task 12 stub, Task 16 full
    vendor/echarts.min.js                 Task 12  copied from retina/pilot
    vendor/counties-fips.json             Task 12  downloaded once, committed
```

JSON contracts (written by Task 10, read by Tasks 13-16) are specified inside Task 10. Index files use a compact `{"cols": [...], "rows": [[...], ...]}` shape; `Data.table()` in `js/data.js` rehydrates them to objects.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/mpdp_formulary/__init__.py`, `src/mpdp_formulary/ingest/__init__.py`, `src/mpdp_formulary/transform/__init__.py`, `src/mpdp_formulary/aggregate/__init__.py`, `src/mpdp_formulary/export/__init__.py`, `tests/test_smoke.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "mpdp-formulary"
version = "0.1.0"
description = "Pipeline and static dashboard for the CMS Monthly Prescription Drug Plan Formulary PUF"
requires-python = ">=3.11"
dependencies = [
    "duckdb>=1.0",
    "pandas>=2.2",
    "pyarrow>=15.0",
    "requests>=2.32",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mpdp_formulary"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
*.zip
extracted/
data/cache/
data/out/
dashboard/data/
__pycache__/
.venv/
*.duckdb
*.log
```

This keeps the 2.2 GB source zip, the unzipped text files, all caches, parquet outputs, and generated dashboard JSON out of git.

- [ ] **Step 3: Create package skeleton and smoke test**

Create the five empty `__init__.py` files listed above. Create `tests/test_smoke.py`:

```python
def test_package_imports():
    import mpdp_formulary  # noqa: F401
```

- [ ] **Step 4: Install and run the test**

Run: `uv sync` then `uv run pytest -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore uv.lock src tests
git commit -m "feat: scaffold mpdp formulary dashboard project"
```

---

### Task 2: Layouts and header validation

**Files:**
- Create: `src/mpdp_formulary/layouts.py`
- Test: `tests/test_layouts.py`

`layouts.py` is the single source of truth for file locations, expected headers, encodings, and row bounds. Header comparison is case-insensitive because the insulin file's cost columns are lowercase in the real header.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from mpdp_formulary import layouts


def _touch(d: Path, name: str, text: str = "X|Y\n1|2\n", encoding: str = "utf-8"):
    (d / name).write_text(text, encoding=encoding)


def test_find_raw_file_picks_full_file_not_sample(tmp_path):
    _touch(tmp_path, "basic drugs formulary file  20260531.txt")
    _touch(tmp_path, "basic drugs formulary file sample 20260531.txt")
    layout = layouts.LAYOUTS["basic"]
    assert layouts.find_raw_file(layout, tmp_path).name == "basic drugs formulary file  20260531.txt"


def test_find_raw_file_no_prefix_collision(tmp_path):
    _touch(tmp_path, "beneficiary cost file  20260531.txt")
    _touch(tmp_path, "insulin beneficiary cost file  20260531.txt")
    assert "insulin" not in layouts.find_raw_file(layouts.LAYOUTS["bene_cost"], tmp_path).name
    assert "insulin" in layouts.find_raw_file(layouts.LAYOUTS["insulin"], tmp_path).name


def test_find_raw_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        layouts.find_raw_file(layouts.LAYOUTS["geo"], tmp_path)


def test_validate_header_accepts_case_insensitive(tmp_path):
    layout = layouts.LAYOUTS["indication"]
    _touch(tmp_path, "indication based coverage formulary file  20260531.txt",
           "contract_id|plan_id|rxcui|disease\nH1|001|123|ASTHMA\n")
    path = layouts.find_raw_file(layout, tmp_path)
    layouts.validate_header(layout, path)  # must not raise


def test_validate_header_rejects_wrong_columns(tmp_path):
    layout = layouts.LAYOUTS["indication"]
    _touch(tmp_path, "indication based coverage formulary file  20260531.txt",
           "CONTRACT_ID|PLAN_ID|BAD\nH1|001|x\n")
    path = layouts.find_raw_file(layout, tmp_path)
    with pytest.raises(ValueError, match="header mismatch"):
        layouts.validate_header(layout, path)


def test_all_layouts_have_bounds():
    assert set(layouts.ROW_BOUNDS) == set(layouts.LAYOUTS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_layouts.py -q`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError` (layouts does not exist yet)

- [ ] **Step 3: Write `src/mpdp_formulary/layouts.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_layouts.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/layouts.py tests/test_layouts.py
git commit -m "feat: add PUF file layouts and header validation"
```

---

### Task 3: Disk-cached HTTP

**Files:**
- Create: `src/mpdp_formulary/ingest/http_cache.py`
- Test: `tests/test_http_cache.py`

All network access (RxNorm release, RxNav API, Census county file) goes through `fetch()` so reruns are offline-fast and tests never hit the network.

- [ ] **Step 1: Write the failing tests**

```python
from mpdp_formulary.ingest import http_cache


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def test_fetch_caches_to_disk(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return FakeResponse(b"payload")

    monkeypatch.setattr(http_cache.requests, "get", fake_get)
    out1 = http_cache.fetch("https://example.org/a", tmp_path)
    out2 = http_cache.fetch("https://example.org/a", tmp_path)
    assert out1 == out2 == b"payload"
    assert len(calls) == 1, "second call must be served from disk"
    assert len(list(tmp_path.iterdir())) == 1


def test_fetch_distinct_urls_distinct_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        http_cache.requests, "get", lambda url, timeout: FakeResponse(url.encode())
    )
    a = http_cache.fetch("https://example.org/a", tmp_path)
    b = http_cache.fetch("https://example.org/b", tmp_path)
    assert a != b
    assert len(list(tmp_path.iterdir())) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_http_cache.py -q`
Expected: FAIL with `ImportError` (module does not exist)

- [ ] **Step 3: Write `src/mpdp_formulary/ingest/http_cache.py`**

```python
"""Disk-cached HTTP GET. All network access in this package goes through fetch()."""
import hashlib
from pathlib import Path

import requests


def fetch(url: str, cache_dir: Path, timeout: int = 300) -> bytes:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    path = cache_dir / key
    if path.exists():
        return path.read_bytes()
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return resp.content
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_http_cache.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/ingest/http_cache.py tests/test_http_cache.py
git commit -m "feat: add disk-cached HTTP fetch"
```

---

### Task 4: Raw file ingest to parquet

**Files:**
- Create: `src/mpdp_formulary/ingest/raw_files.py`
- Test: `tests/test_raw_files.py`

Loads each of the seven text files into `data/out/raw_<key>.parquet` after validating the header. Everything is read as VARCHAR (typing happens downstream) so a malformed numeric cell cannot abort a 1.1M-row load.

- [ ] **Step 1: Write the failing tests**

```python
import duckdb
import pytest

from mpdp_formulary import layouts
from mpdp_formulary.ingest import raw_files

TEST_BOUNDS = {k: (1, 100) for k in layouts.LAYOUTS}


def make_raw_dir(tmp_path):
    """Minimal valid versions of all seven files, 2 data rows each."""
    rows = {
        "plan information  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|SEGMENT_ID|CONTRACT_NAME|PLAN_NAME|FORMULARY_ID|PREMIUM|DEDUCTIBLE|MA_REGION_CODE|PDP_REGION_CODE|STATE|COUNTY_CODE|SNP|PLAN_SUPPRESSED_YN\n"
            "H0028|007|000|CHA HMO, INC.|Humana Gold Plus \xe9|00026408|35.60|615| | |NE|28100|2|N\n"
            "S5601|001|000|PDP ORG|Some PDP|00026409|12.30|0| |22| | |0|N\n"
        ),
        "basic drugs formulary file  20260531.txt": (
            "FORMULARY_ID|FORMULARY_VERSION|CONTRACT_YEAR|RXCUI|NDC|TIER_LEVEL_VALUE|QUANTITY_LIMIT_YN|QUANTITY_LIMIT_AMOUNT|QUANTITY_LIMIT_DAYS|PRIOR_AUTHORIZATION_YN|STEP_THERAPY_YN|SELECTED_DRUG_YN\n"
            "00026408|17|2026|1551300|00002143380|3|Y|2|28|Y|N|N\n"
            "00026409|17|2026|1551300|00002143380|2|N| | |N|N|N\n"
        ),
        "excluded drugs formulary file  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|RXCUI|TIER|QUANTITY_LIMIT_YN|QUANTITY_LIMIT_AMOUNT|QUANTITY_LIMIT_DAYS|PRIOR_AUTH_YN|STEP_THERAPY_YN|CAPPED_BENEFIT_YN\n"
            "H0028|007|312950|1|1|6|30|N|N|N\n"
            "H0028|007|1367410|1|0| | |N|N|N\n"
        ),
        "beneficiary cost file  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|SEGMENT_ID|COVERAGE_LEVEL|TIER|DAYS_SUPPLY|COST_TYPE_PREF|COST_AMT_PREF|COST_MIN_AMT_PREF|COST_MAX_AMT_PREF|COST_TYPE_NONPREF|COST_AMT_NONPREF|COST_MIN_AMT_NONPREF|COST_MAX_AMT_NONPREF|COST_TYPE_MAIL_PREF|COST_AMT_MAIL_PREF|COST_MIN_AMT_MAIL_PREF|COST_MAX_AMT_MAIL_PREF|COST_TYPE_MAIL_NONPREF|COST_AMT_MAIL_NONPREF|COST_MIN_AMT_MAIL_NONPREF|COST_MAX_AMT_MAIL_NONPREF|TIER_SPECIALTY_YN|DED_APPLIES_YN\n"
            "H0028|007|000|0|1|1|0|0|0|0|1|0|0|0|1|0|0|0|1|10|0|0|N|N\n"
            "H0028|007|000|1|1|1|1|5|0|0|2|0.25|1|50|1|0|0|0|1|10|0|0|N|Y\n"
        ),
        "insulin beneficiary cost file  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|SEGMENT_ID|TIER|DAYS_SUPPLY|copay_amt_pref_insln|copay_amt_nonpref_insln|copay_amt_mail_pref_insln|copay_amt_mail_nonpref_insln|coin_amt_pref_insln|coin_amt_nonpref_insln|coin_amt_mail_pref_insln|coin_amt_mail_nonpref_insln\n"
            "H0028|007|000|1|1| |0.00|0.00|10.00| |0.00|0.00|0.25\n"
            "H0028|007|000|1|2| |0.00|0.00|30.00| |0.00|0.00|0.25\n"
        ),
        "Indication Based Coverage Formulary File  20260531.txt": (
            "CONTRACT_ID|PLAN_ID|RXCUI|DISEASE\n"
            "H1994|001|1745108|SPONDYLITIS, ANKYLOSING\n"
            "H1994|001|1876406|ASTHMA\n"
        ),
        "geographic locator file 20260531.txt": (
            "COUNTY_CODE|STATENAME|COUNTY|MA_REGION_CODE|MA_REGION|PDP_REGION_CODE|PDP_REGION\n"
            "01000|Alabama|Autauga|10|Alabama and Tennessee|12|Alabama, Tennessee\n"
            "28100|Nebraska|Douglas|19|Upper Midwest|25|Upper Midwest\n"
        ),
    }
    raw = tmp_path / "extracted"
    raw.mkdir()
    for name, text in rows.items():
        enc = "latin-1" if name.startswith("plan information") else "utf-8"
        (raw / name).write_text(text, encoding=enc)
    return raw


def test_load_all_writes_seven_parquets(tmp_path):
    raw = make_raw_dir(tmp_path)
    out = tmp_path / "out"
    counts = raw_files.load_all(raw, out, bounds=TEST_BOUNDS)
    assert set(counts) == set(layouts.LAYOUTS)
    assert all(n == 2 for n in counts.values())
    con = duckdb.connect()
    df = con.execute(
        f"SELECT * FROM read_parquet('{(out / 'raw_plan_info.parquet').as_posix()}')"
    ).df()
    assert list(df.columns) == list(layouts.LAYOUTS["plan_info"].columns)
    assert "\xe9" in df["PLAN_NAME"][0], "latin-1 byte must round-trip"


def test_load_all_bounds_violation_raises(tmp_path):
    raw = make_raw_dir(tmp_path)
    bad = dict(TEST_BOUNDS)
    bad["basic"] = (10, 100)
    with pytest.raises(ValueError, match="basic"):
        raw_files.load_all(raw, tmp_path / "out", bounds=bad)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_raw_files.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/ingest/raw_files.py`**

```python
"""Load the seven extracted PUF text files into raw_*.parquet with validation."""
from pathlib import Path

import duckdb

from .. import layouts


def load_all(raw_dir: Path, out_dir: Path, bounds: dict | None = None) -> dict[str, int]:
    bounds = bounds if bounds is not None else layouts.ROW_BOUNDS
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    counts: dict[str, int] = {}
    for layout in layouts.LAYOUTS.values():
        path = layouts.find_raw_file(layout, raw_dir)
        layouts.validate_header(layout, path)
        cols = ", ".join(f"'{c}': 'VARCHAR'" for c in layout.columns)
        out = out_dir / f"raw_{layout.key}.parquet"
        con.execute(
            f"""
            COPY (
                SELECT * FROM read_csv(
                    '{path.as_posix()}', delim='|', header=true,
                    columns={{{cols}}}, encoding='{layout.encoding}',
                    all_varchar=true
                )
            ) TO '{out.as_posix()}' (FORMAT PARQUET)
            """
        )
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{out.as_posix()}')"
        ).fetchone()[0]
        lo, hi = bounds[layout.key]
        if not lo <= n <= hi:
            raise ValueError(
                f"{layout.key}: {n} rows outside expected bounds [{lo}, {hi}]"
            )
        counts[layout.key] = n
        print(f"ingest: {layout.key:<10} {n:>9,} rows -> {out.name}")
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_raw_files.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/ingest/raw_files.py tests/test_raw_files.py
git commit -m "feat: ingest PUF text files to parquet with validation"
```

---

### Task 5: RxNorm drug names

**Files:**
- Create: `src/mpdp_formulary/ingest/rxnorm.py`
- Test: `tests/test_rxnorm.py`

Resolves every RXCUI appearing in the data to a display name, TTY, and brand/generic flag. Primary source: the RxNorm Current Prescribable Content release (free, no UMLS license). Fallback for retired or remapped RXCUIs: the RxNav `historystatus` endpoint, disk-cached. The stage fails if fewer than 99% of distinct RXCUIs resolve.

- [ ] **Step 1: Write the failing tests**

```python
import pandas as pd
import pytest

from mpdp_formulary.ingest import rxnorm


def conso(rows):
    return pd.DataFrame(rows, columns=["RXCUI", "SAB", "TTY", "STR", "SUPPRESS"])


def test_build_names_prefers_primary_tty():
    df = conso([
        ("100", "RXNORM", "IN", "drug ingredient", "N"),
        ("100", "RXNORM", "SCD", "drug 10 MG Tablet", "N"),
    ])
    out, rate = rxnorm.build_name_table(["100"], df, rxnav=None)
    assert rate == 1.0
    row = out.set_index("rxcui").loc["100"]
    assert row["name"] == "drug 10 MG Tablet"
    assert row["tty"] == "SCD"
    assert row["brand_generic"] == "generic"


def test_build_names_brand_flag():
    df = conso([("200", "RXNORM", "SBD", "Brandy 5 MG Tablet", "N")])
    out, _ = rxnorm.build_name_table(["200"], df, rxnav=None)
    assert out.set_index("rxcui").loc["200"]["brand_generic"] == "brand"


def test_build_names_ignores_suppressed_and_other_sab():
    df = conso([
        ("300", "RXNORM", "SCD", "suppressed name", "Y"),
        ("300", "MTHSPL", "SCD", "wrong source", "N"),
        ("300", "RXNORM", "IN", "fallback tty name", "N"),
    ])
    out, _ = rxnorm.build_name_table(["300"], df, rxnav=None)
    assert out.set_index("rxcui").loc["300"]["name"] == "fallback tty name"


def test_build_names_uses_rxnav_for_missing():
    df = conso([("100", "RXNORM", "SCD", "known", "N")])
    out, rate = rxnorm.build_name_table(
        ["100", "999"], df, rxnav=lambda rxcui: ("remapped name", "SCD")
    )
    assert rate == 1.0
    assert out.set_index("rxcui").loc["999"]["name"] == "remapped name"


def test_build_names_low_match_rate_raises():
    df = conso([("100", "RXNORM", "SCD", "known", "N")])
    with pytest.raises(ValueError, match="match rate"):
        rxnorm.build_name_table(
            [str(i) for i in range(100, 300)], df, rxnav=lambda rxcui: (None, "")
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rxnorm.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/ingest/rxnorm.py`**

```python
"""Resolve RXCUIs to names via RxNorm Prescribable Content, RxNav fallback."""
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


def load_rxnconso(cache_dir: Path) -> pd.DataFrame:
    """Download (cached) the prescribable release and parse RXNCONSO.RRF."""
    raw = http_cache.fetch(RXNORM_URL, cache_dir)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        member = next(n for n in zf.namelist() if n.upper().endswith("RXNCONSO.RRF"))
        with zf.open(member) as f:
            df = pd.read_csv(
                f, sep="|", header=None, names=RXNCONSO_COLS, dtype=str,
                usecols=["RXCUI", "SAB", "TTY", "STR", "SUPPRESS"],
            )
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
    if rxnav is not None:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_rxnorm.py -q`
Expected: `5 passed`

Note: the TTY-priority loop iterates tiers in order, so an SCD name wins over an IN name for the same RXCUI; the tests pin this.

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/ingest/rxnorm.py tests/test_rxnorm.py
git commit -m "feat: resolve RXCUIs to names via RxNorm with RxNav fallback"
```

---

### Task 6: SSA-to-FIPS county crosswalk

**Files:**
- Create: `src/mpdp_formulary/ingest/crosswalk.py`
- Test: `tests/test_crosswalk.py`

COUNTY_CODE in the PUF is an SSA code; the map needs FIPS. The geographic locator gives (state name, bare county name) per SSA code; the Census `national_county2020.txt` file gives (state abbrev, designated county name like "Autauga County") per FIPS. Matching is two-pass within state: pass 1 exact normalized name, pass 2 with the Census designator suffix stripped, preferring the "County" row when stripping creates duplicates (e.g., Richmond County vs Richmond city in VA). Unmatched counties get a null FIPS and render as no-data on the map; the build fails below a 97% match rate.

- [ ] **Step 1: Write the failing tests**

```python
import pandas as pd
import pytest

from mpdp_formulary.ingest import crosswalk

CENSUS_TEXT = """STATE|STATEFP|COUNTYFP|COUNTYNS|COUNTYNAME|CLASSFP|FUNCSTAT
AL|01|001|00161526|Autauga County|H1|A
LA|22|001|00558389|Acadia Parish|H1|A
VA|51|159|01480139|Richmond County|H1|A
VA|51|760|01498434|Richmond city|C7|F
NE|31|055|00835880|Douglas County|H1|A
"""


def geo(rows):
    return pd.DataFrame(rows, columns=["COUNTY_CODE", "STATENAME", "COUNTY"])


def test_exact_and_designator_stripped_matching():
    g = geo([
        ("01000", "Alabama", "Autauga"),
        ("19450", "Louisiana", "Acadia"),
        ("28100", "Nebraska", "Douglas"),
    ])
    out, rate = crosswalk.build(g, CENSUS_TEXT)
    m = out.set_index("county_code")["fips"]
    assert m["01000"] == "01001"
    assert m["19450"] == "22001"
    assert m["28100"] == "31055"
    assert rate == 1.0


def test_designator_collision_prefers_county():
    g = geo([("52280", "Virginia", "Richmond")])
    out, _ = crosswalk.build(g, CENSUS_TEXT)
    assert out.set_index("county_code")["fips"]["52280"] == "51159"


def test_city_matches_exact_before_stripping():
    g = geo([("52760", "Virginia", "Richmond City")])
    out, _ = crosswalk.build(g, CENSUS_TEXT)
    assert out.set_index("county_code")["fips"]["52760"] == "51760"


def test_unmatched_gets_null_and_rate_drops():
    g = geo([("01000", "Alabama", "Autauga"), ("99999", "Alabama", "Nonesuch")])
    out, rate = crosswalk.build(g, CENSUS_TEXT, min_rate=0.0)
    m = out.set_index("county_code")["fips"]
    assert pd.isna(m["99999"])
    assert rate == 0.5


def test_low_match_rate_raises():
    g = geo([("99999", "Alabama", "Nonesuch")])
    with pytest.raises(ValueError, match="match rate"):
        crosswalk.build(g, CENSUS_TEXT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_crosswalk.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/ingest/crosswalk.py`**

```python
"""Map SSA county codes to FIPS by state + county-name matching.

The PUF geographic locator carries bare county names ("Autauga"); the Census
county file carries designated names ("Autauga County"). Pass 1 matches full
normalized names (catches Virginia independent cities like "Richmond City");
pass 2 strips the Census designator suffix and, on duplicates within a state,
prefers the row whose raw name ends in "County".
"""
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
    census = pd.read_csv(io.StringIO(census_text), sep="|", dtype=str)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_crosswalk.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/ingest/crosswalk.py tests/test_crosswalk.py
git commit -m "feat: add SSA-to-FIPS county crosswalk via Census names"
```

---

### Task 7: Plan dimension and plan-county bridge

**Files:**
- Create: `src/mpdp_formulary/transform/plans.py`
- Test: `tests/test_plans.py`

Collapses the 112k county-grain plan info rows to one row per CONTRACT_ID + PLAN_ID + SEGMENT_ID, and builds the plan-to-county bridge: H contracts from their own county rows, R and S contracts by expanding region codes through the geographic locator. Functions operate on a DuckDB connection where `raw_plan_info` and `raw_geo` relations already exist (the CLI registers parquet views; tests register pandas frames).

- [ ] **Step 1: Write the failing tests**

```python
import duckdb
import pandas as pd
import pytest

from mpdp_formulary.transform import plans

PLAN_COLS = ["CONTRACT_ID", "PLAN_ID", "SEGMENT_ID", "CONTRACT_NAME", "PLAN_NAME",
             "FORMULARY_ID", "PREMIUM", "DEDUCTIBLE", "MA_REGION_CODE",
             "PDP_REGION_CODE", "STATE", "COUNTY_CODE", "SNP", "PLAN_SUPPRESSED_YN"]
GEO_COLS = ["COUNTY_CODE", "STATENAME", "COUNTY", "MA_REGION_CODE", "MA_REGION",
            "PDP_REGION_CODE", "PDP_REGION"]


def make_con(plan_rows, geo_rows):
    con = duckdb.connect()
    con.register("plan_df", pd.DataFrame(plan_rows, columns=PLAN_COLS))
    con.register("geo_df", pd.DataFrame(geo_rows, columns=GEO_COLS))
    con.execute("CREATE TABLE raw_plan_info AS SELECT * FROM plan_df")
    con.execute("CREATE TABLE raw_geo AS SELECT * FROM geo_df")
    return con


GEO = [
    ("01000", "Alabama", "Autauga", "10", "AL and TN", "12", "AL, TN"),
    ("01010", "Alabama", "Baldwin", "10", "AL and TN", "12", "AL, TN"),
    ("28100", "Nebraska", "Douglas", "19", "Upper Midwest", "25", "Upper Midwest"),
]


def h_plan(county, name="Plan H"):
    return ("H0028", "007", "000", "CHA HMO", name, "00026408", "35.60", "615",
            " ", " ", "NE", county, "2", "N")


def test_plan_dim_dedupes_county_rows():
    con = make_con([h_plan("28100"), h_plan("28100")], GEO)
    stats = plans.build(con)
    dim = con.execute("SELECT * FROM plan_dim").df()
    assert len(dim) == 1
    row = dim.iloc[0]
    assert row["plan_key"] == "H0028_007_000"
    assert row["plan_type"] == "MA"
    assert row["premium"] == pytest.approx(35.60)
    assert stats["n_plans"] == 1


def test_bridge_h_uses_own_counties_r_and_s_expand_regions():
    r_plan = ("R5826", "001", "000", "ORG R", "Plan R", "00026500", "0", "0",
              "10", " ", " ", " ", "0", "N")
    s_plan = ("S5601", "001", "000", "ORG S", "Plan S", "00026501", "0", "0",
              " ", "25", " ", " ", "0", "N")
    con = make_con([h_plan("28100"), r_plan, s_plan], GEO)
    plans.build(con)
    bridge = con.execute(
        "SELECT plan_key, county_code FROM plan_county ORDER BY 1, 2"
    ).df()
    got = set(map(tuple, bridge.values))
    assert got == {
        ("H0028_007_000", "28100"),
        ("R5826_001_000", "01000"),   # MA region 10 has two counties
        ("R5826_001_000", "01010"),
        ("S5601_001_000", "28100"),   # PDP region 25
    }


def test_multiple_formularies_per_plan_raises():
    bad = list(h_plan("28100"))
    bad2 = list(h_plan("01000"))
    bad2[5] = "99999999"
    con = make_con([tuple(bad), tuple(bad2)], GEO)
    with pytest.raises(ValueError, match="formulary"):
        plans.build(con)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plans.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/transform/plans.py`**

```python
"""plan_dim (one row per contract+plan+segment) and plan_county bridge."""

PLAN_DIM_SQL = """
CREATE OR REPLACE TABLE plan_dim AS
SELECT
    CONTRACT_ID || '_' || PLAN_ID || '_' || SEGMENT_ID AS plan_key,
    CONTRACT_ID AS contract_id,
    PLAN_ID AS plan_id,
    SEGMENT_ID AS segment_id,
    any_value(CONTRACT_NAME) AS contract_name,
    any_value(PLAN_NAME) AS plan_name,
    any_value(FORMULARY_ID) AS formulary_id,
    CASE substr(CONTRACT_ID, 1, 1)
        WHEN 'H' THEN 'MA' WHEN 'R' THEN 'MA_REGIONAL' WHEN 'S' THEN 'PDP'
        ELSE 'OTHER' END AS plan_type,
    any_value(SNP) AS snp,
    max(PLAN_SUPPRESSED_YN) AS suppressed_yn,
    try_cast(nullif(trim(any_value(PREMIUM)), '') AS DOUBLE) AS premium,
    try_cast(nullif(trim(any_value(DEDUCTIBLE)), '') AS DOUBLE) AS deductible
FROM raw_plan_info
GROUP BY 1, 2, 3, 4
"""

MULTI_FORMULARY_SQL = """
SELECT CONTRACT_ID, PLAN_ID, SEGMENT_ID
FROM raw_plan_info
GROUP BY 1, 2, 3
HAVING count(DISTINCT FORMULARY_ID) > 1
"""

PLAN_COUNTY_SQL = """
CREATE OR REPLACE TABLE plan_county AS
SELECT DISTINCT plan_key, county_code FROM (
    SELECT CONTRACT_ID || '_' || PLAN_ID || '_' || SEGMENT_ID AS plan_key,
           COUNTY_CODE AS county_code
    FROM raw_plan_info
    WHERE substr(CONTRACT_ID, 1, 1) = 'H'
      AND nullif(trim(COUNTY_CODE), '') IS NOT NULL
    UNION ALL
    SELECT p.CONTRACT_ID || '_' || p.PLAN_ID || '_' || p.SEGMENT_ID,
           g.COUNTY_CODE
    FROM raw_plan_info p
    JOIN raw_geo g
      ON trim(p.MA_REGION_CODE) = trim(g.MA_REGION_CODE)
    WHERE substr(p.CONTRACT_ID, 1, 1) = 'R'
      AND nullif(trim(p.MA_REGION_CODE), '') IS NOT NULL
    UNION ALL
    SELECT p.CONTRACT_ID || '_' || p.PLAN_ID || '_' || p.SEGMENT_ID,
           g.COUNTY_CODE
    FROM raw_plan_info p
    JOIN raw_geo g
      ON trim(p.PDP_REGION_CODE) = trim(g.PDP_REGION_CODE)
    WHERE substr(p.CONTRACT_ID, 1, 1) = 'S'
      AND nullif(trim(p.PDP_REGION_CODE), '') IS NOT NULL
)
"""


def build(con) -> dict:
    multi = con.execute(MULTI_FORMULARY_SQL).fetchall()
    if multi:
        raise ValueError(
            f"plans: {len(multi)} plan(s) carry more than one formulary ID, "
            f"first: {multi[:5]}"
        )
    con.execute(PLAN_DIM_SQL)
    con.execute(PLAN_COUNTY_SQL)
    n_plans = con.execute("SELECT count(*) FROM plan_dim").fetchone()[0]
    n_bridge = con.execute("SELECT count(*) FROM plan_county").fetchone()[0]
    n_orphan = con.execute(
        """
        SELECT count(*) FROM plan_dim d
        WHERE NOT EXISTS (
            SELECT 1 FROM plan_county c WHERE c.plan_key = d.plan_key)
        """
    ).fetchone()[0]
    stats = {"n_plans": n_plans, "n_bridge_rows": n_bridge,
             "n_plans_without_counties": n_orphan}
    print(f"transform: plan_dim {n_plans:,} plans, bridge {n_bridge:,} rows, "
          f"{n_orphan} plans without counties")
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_plans.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/transform/plans.py tests/test_plans.py
git commit -m "feat: build plan dimension and plan-county bridge"
```

---

### Task 8: Formulary drugs at RXCUI grain

**Files:**
- Create: `src/mpdp_formulary/transform/drugs.py`
- Test: `tests/test_drugs.py`

Aggregates the NDC-grain basic formulary file to (formulary, RXCUI) grain. Restriction flags use any-NDC logic; tier is the modal tier with min/max retained; QL detail keeps the max amount/days among QL rows. Also builds `drug_dim` (per-RXCUI market counts). Operates on a connection where `raw_basic` exists.

- [ ] **Step 1: Write the failing tests**

```python
import duckdb
import pandas as pd

from mpdp_formulary.transform import drugs

BASIC_COLS = ["FORMULARY_ID", "FORMULARY_VERSION", "CONTRACT_YEAR", "RXCUI", "NDC",
              "TIER_LEVEL_VALUE", "QUANTITY_LIMIT_YN", "QUANTITY_LIMIT_AMOUNT",
              "QUANTITY_LIMIT_DAYS", "PRIOR_AUTHORIZATION_YN", "STEP_THERAPY_YN",
              "SELECTED_DRUG_YN"]


def make_con(rows):
    con = duckdb.connect()
    con.register("basic_df", pd.DataFrame(rows, columns=BASIC_COLS))
    con.execute("CREATE TABLE raw_basic AS SELECT * FROM basic_df")
    return con


def test_ndc_rows_aggregate_to_rxcui_with_any_logic():
    con = make_con([
        ("F1", "17", "2026", "100", "00001", "3", "Y", "2", "28", "N", "N", "N"),
        ("F1", "17", "2026", "100", "00002", "3", "N", " ", " ", "Y", "N", "N"),
        ("F1", "17", "2026", "100", "00003", "2", "N", " ", " ", "N", "Y", "Y"),
    ])
    drugs.build(con)
    row = con.execute("SELECT * FROM formulary_drug").df().iloc[0]
    assert row["tier"] == 3            # modal tier of [3, 3, 2]
    assert row["tier_min"] == 2 and row["tier_max"] == 3
    assert bool(row["pa"]) and bool(row["st"]) and bool(row["ql"])
    assert bool(row["selected"])
    assert row["ql_amount"] == "2" and row["ql_days"] == "28"
    assert row["ndc_count"] == 3


def test_drug_dim_counts_across_formularies():
    con = make_con([
        ("F1", "17", "2026", "100", "00001", "1", "N", " ", " ", "N", "N", "N"),
        ("F2", "17", "2026", "100", "00001", "2", "N", " ", " ", "Y", "N", "N"),
        ("F2", "17", "2026", "200", "00009", "4", "Y", "30", "30", "N", "N", "N"),
    ])
    drugs.build(con)
    dim = con.execute("SELECT * FROM drug_dim ORDER BY rxcui").df()
    d100 = dim[dim["rxcui"] == "100"].iloc[0]
    assert d100["n_formularies"] == 2
    assert d100["n_pa"] == 1 and d100["n_ql"] == 0
    d200 = dim[dim["rxcui"] == "200"].iloc[0]
    assert d200["n_formularies"] == 1 and d200["n_ql"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_drugs.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/transform/drugs.py`**

```python
"""formulary_drug (formulary x RXCUI grain) and drug_dim (per-RXCUI counts)."""

FORMULARY_DRUG_SQL = """
CREATE OR REPLACE TABLE formulary_drug AS
SELECT
    FORMULARY_ID AS formulary_id,
    RXCUI AS rxcui,
    mode(try_cast(TIER_LEVEL_VALUE AS INTEGER)) AS tier,
    min(try_cast(TIER_LEVEL_VALUE AS INTEGER)) AS tier_min,
    max(try_cast(TIER_LEVEL_VALUE AS INTEGER)) AS tier_max,
    bool_or(PRIOR_AUTHORIZATION_YN = 'Y') AS pa,
    bool_or(STEP_THERAPY_YN = 'Y') AS st,
    bool_or(QUANTITY_LIMIT_YN = 'Y') AS ql,
    max(CASE WHEN QUANTITY_LIMIT_YN = 'Y'
             THEN nullif(trim(QUANTITY_LIMIT_AMOUNT), '') END) AS ql_amount,
    max(CASE WHEN QUANTITY_LIMIT_YN = 'Y'
             THEN nullif(trim(QUANTITY_LIMIT_DAYS), '') END) AS ql_days,
    bool_or(SELECTED_DRUG_YN = 'Y') AS selected,
    count(DISTINCT NDC) AS ndc_count
FROM raw_basic
GROUP BY 1, 2
"""

DRUG_DIM_SQL = """
CREATE OR REPLACE TABLE drug_dim AS
SELECT
    rxcui,
    count(*) AS n_formularies,
    sum(pa::INT) AS n_pa,
    sum(st::INT) AS n_st,
    sum(ql::INT) AS n_ql,
    bool_or(selected) AS selected,
    sum(ndc_count) AS ndc_total
FROM formulary_drug
GROUP BY 1
"""


def build(con) -> dict:
    con.execute(FORMULARY_DRUG_SQL)
    con.execute(DRUG_DIM_SQL)
    n_fd = con.execute("SELECT count(*) FROM formulary_drug").fetchone()[0]
    n_form = con.execute(
        "SELECT count(DISTINCT formulary_id) FROM formulary_drug").fetchone()[0]
    n_drugs = con.execute("SELECT count(*) FROM drug_dim").fetchone()[0]
    stats = {"n_formulary_drug": n_fd, "n_formularies": n_form, "n_drugs": n_drugs}
    print(f"transform: formulary_drug {n_fd:,} rows, "
          f"{n_form} formularies, {n_drugs:,} distinct RXCUIs")
    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_drugs.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/transform/drugs.py tests/test_drugs.py
git commit -m "feat: aggregate formulary drugs to RXCUI grain"
```

---

### Task 9: Status vectors and statistics

**Files:**
- Create: `src/mpdp_formulary/aggregate/status_vectors.py`, `src/mpdp_formulary/aggregate/stats.py`
- Test: `tests/test_aggregate.py`

Status vector encoding (one character per formulary, in `formulary_order` position): `-` means not listed; otherwise the lowercase hex digit of a 4-bit mask where bit 0 is always set (covered), bit 1 = PA, bit 2 = ST, bit 3 = QL. So `1` = covered unrestricted, `3` = PA only, `9` = QL only, `b` = PA + QL, `f` = all three. The dashboard JS decodes with `parseInt(ch, 16)`.

- [ ] **Step 1: Write the failing tests**

```python
import pandas as pd

from mpdp_formulary.aggregate import stats, status_vectors


def fd(rows):
    return pd.DataFrame(rows, columns=[
        "formulary_id", "rxcui", "tier", "tier_min", "tier_max",
        "pa", "st", "ql", "ql_amount", "ql_days", "selected", "ndc_count"])


SAMPLE = fd([
    ("F1", "100", 3, 3, 3, True, False, True, "2", "28", False, 4),
    ("F2", "100", 2, 2, 2, False, False, False, None, None, False, 1),
    ("F2", "200", 5, 5, 5, False, True, False, None, None, True, 2),
])


def test_encode_status():
    assert status_vectors.encode_status(False, False, False) == "1"
    assert status_vectors.encode_status(True, False, False) == "3"
    assert status_vectors.encode_status(False, True, False) == "5"
    assert status_vectors.encode_status(False, False, True) == "9"
    assert status_vectors.encode_status(True, True, True) == "f"


def test_build_vectors():
    out = status_vectors.build_vectors(SAMPLE, ["F1", "F2"])
    v = out.set_index("rxcui")["vector"]
    assert v["100"] == "b1"   # F1: PA+QL -> b; F2: unrestricted -> 1
    assert v["200"] == "-5"   # not on F1; ST on F2


def test_formulary_order_is_sorted_distinct():
    assert stats.formulary_order(SAMPLE) == ["F1", "F2"]


def test_formulary_stats():
    out = stats.formulary_stats(SAMPLE).set_index("formulary_id")
    assert out.loc["F1", "n_drugs"] == 1
    assert out.loc["F2", "n_drugs"] == 2
    assert out.loc["F2", "pa_pct"] == 0.0
    assert out.loc["F2", "st_pct"] == 50.0
    assert out.loc["F1", "ql_pct"] == 100.0


def test_plan_stats_attaches_exclusions_by_contract_plan():
    plan_dim = pd.DataFrame([
        ("H1_001_000", "H1", "001", "000", "F1"),
        ("H1_001_001", "H1", "001", "001", "F1"),
        ("S1_002_000", "S1", "002", "000", "F2"),
    ], columns=["plan_key", "contract_id", "plan_id", "segment_id", "formulary_id"])
    excluded = pd.DataFrame([
        ("H1", "001", "900"), ("H1", "001", "901"),
    ], columns=["CONTRACT_ID", "PLAN_ID", "RXCUI"])
    out = stats.plan_stats(plan_dim, stats.formulary_stats(SAMPLE), excluded)
    m = out.set_index("plan_key")["n_excluded"]
    assert m["H1_001_000"] == 2 and m["H1_001_001"] == 2  # both segments
    assert m["S1_002_000"] == 0
    assert out.set_index("plan_key").loc["S1_002_000", "n_drugs"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_aggregate.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/aggregate/status_vectors.py`**

```python
"""Per-drug formulary status vectors.

One character per formulary at its formulary_order position: '-' = not listed,
else lowercase hex of (1 | 2*PA | 4*ST | 8*QL). '1' is covered unrestricted.
"""
import pandas as pd


def encode_status(pa: bool, st: bool, ql: bool) -> str:
    return format(1 | (2 if pa else 0) | (4 if st else 0) | (8 if ql else 0), "x")


def build_vectors(formulary_drug: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    idx = {fid: i for i, fid in enumerate(order)}
    chars: dict[str, list[str]] = {}
    for row in formulary_drug.itertuples():
        vec = chars.setdefault(row.rxcui, ["-"] * len(order))
        vec[idx[row.formulary_id]] = encode_status(
            bool(row.pa), bool(row.st), bool(row.ql))
    return pd.DataFrame(
        {"rxcui": list(chars), "vector": ["".join(v) for v in chars.values()]}
    )
```

- [ ] **Step 4: Write `src/mpdp_formulary/aggregate/stats.py`**

```python
"""Formulary-level and plan-level statistics."""
import pandas as pd


def formulary_order(formulary_drug: pd.DataFrame) -> list[str]:
    return sorted(formulary_drug["formulary_id"].unique())


def formulary_stats(formulary_drug: pd.DataFrame) -> pd.DataFrame:
    g = formulary_drug.groupby("formulary_id")
    out = pd.DataFrame({
        "n_drugs": g.size(),
        "pa_pct": g["pa"].mean() * 100,
        "st_pct": g["st"].mean() * 100,
        "ql_pct": g["ql"].mean() * 100,
    }).round(1)
    return out.reset_index()


def plan_stats(plan_dim: pd.DataFrame, form_stats: pd.DataFrame,
               excluded_raw: pd.DataFrame) -> pd.DataFrame:
    """plan_dim joined to its formulary's stats plus exclusion counts.

    Exclusions are keyed by contract+plan (no segment in the excluded file),
    so the count applies to every segment of that contract+plan.
    """
    excl = (
        excluded_raw.groupby(["CONTRACT_ID", "PLAN_ID"]).size()
        .rename("n_excluded").reset_index()
        .rename(columns={"CONTRACT_ID": "contract_id", "PLAN_ID": "plan_id"})
    )
    out = plan_dim.merge(form_stats, on="formulary_id", how="left")
    out = out.merge(excl, on=["contract_id", "plan_id"], how="left")
    out["n_excluded"] = out["n_excluded"].fillna(0).astype(int)
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_aggregate.py -q`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add src/mpdp_formulary/aggregate tests/test_aggregate.py
git commit -m "feat: add status vectors and formulary/plan statistics"
```

---

### Task 10: JSON export

**Files:**
- Create: `src/mpdp_formulary/export/dashboard_json.py`
- Test: `tests/test_export.py`

Writes everything under `dashboard/data/`. Index files use `{"cols": [...], "rows": [[...]]}`. These exact shapes are the contract with the JS in Tasks 12-16.

**JSON contracts:**

- `meta.json`: `{"vintage", "contract_year", "formulary_order": [328 ids], "counts": {...}, "snp_labels", "coverage_level_labels", "days_supply_labels", "plan_type_labels"}`
- `overview.json`: `{"tier_mix": [{"tier", "n"}], "restrictions": {"pa_pct", "st_pct", "ql_pct"}, "exclusions": {"rows", "distinct_rxcuis", "n_contract_plans"}, "plan_types": [{"type", "n"}], "snp": [{"snp", "n"}], "selected_drugs": [{"rxcui", "name", "n_formularies"}]}`
- `drugs_index.json`: cols `["rxcui","name","bg","ndc_count","n_form","cov_pct","pa_pct","st_pct","ql_pct","excl_plans","selected"]`
- `drugs/{rxcui}.json`: `{"rxcui", "name", "bg", "selected", "vector", "formularies": {fid: [tier, ql_amount, ql_days]}, "excluded_by": {"cols": ["contract_plan","plan_name","tier","pa","st","ql","ql_amount","ql_days","capped"], "rows": [...]}, "indications": [{"contract_plan", "disease"}]}`
- `plans_index.json`: cols `["plan_key","contract_name","plan_name","type","snp","premium","deductible","formulary_idx","suppressed","n_drugs","pa_pct","st_pct","ql_pct","n_excluded","states"]` (`formulary_idx` indexes `meta.formulary_order`, `-1` if absent; `states` is an array of USPS abbrevs)
- `plans/{plan_key}.json`: `{"plan_key", "costs": [{"level","tier","days","specialty","ded_applies","channels": {"pref": [type, amt, min, max], "nonpref": [...], "mail_pref": [...], "mail_nonpref": [...]}}], "insulin": [{"tier","days","copay": [pref, nonpref, mail_pref, mail_nonpref], "coin": [...]}], "excluded": {"cols": ["rxcui","name","tier","pa","st","ql","ql_amount","ql_days","capped"], "rows": [...]}, "indications": [{"rxcui","name","disease"}]}`
- `formularies/{fid}.json`: cols `["rxcui","name","bg","tier","pa","st","ql","ql_amount","ql_days","selected"]`
- `geo.json`: cols `["fips","name","state","plans"]` where `plans` is an array of integer indexes into `plans_index.rows`.

- [ ] **Step 1: Write the failing tests**

```python
import json

import pandas as pd

from mpdp_formulary.export import dashboard_json as dj


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_index_and_table_roundtrip(tmp_path):
    df = pd.DataFrame([{"rxcui": "100", "name": "drug", "bg": "generic",
                        "ndc_count": 2, "n_form": 1, "cov_pct": 50.0,
                        "pa_pct": 0.0, "st_pct": 0.0, "ql_pct": 100.0,
                        "excl_plans": 0, "selected": False}])
    dj.write_drugs_index(tmp_path, df)
    obj = read(tmp_path / "drugs_index.json")
    assert obj["cols"] == dj.DRUGS_INDEX_COLS
    assert obj["rows"][0][0] == "100"


def test_write_drug_shards(tmp_path):
    drugs = pd.DataFrame([{"rxcui": "100", "name": "drug", "bg": "generic",
                           "selected": False}])
    vectors = pd.DataFrame([{"rxcui": "100", "vector": "b1"}])
    fd = pd.DataFrame([
        {"formulary_id": "F1", "rxcui": "100", "tier": 3,
         "ql_amount": "2", "ql_days": "28"},
        {"formulary_id": "F2", "rxcui": "100", "tier": 2,
         "ql_amount": None, "ql_days": None},
    ])
    excl = pd.DataFrame([{"contract_plan": "H1_001", "plan_name": "Plan",
                          "rxcui": "100", "tier": 1, "pa": False, "st": False,
                          "ql": True, "ql_amount": "6", "ql_days": "30",
                          "capped": False}])
    ind = pd.DataFrame([{"contract_plan": "H1_001", "rxcui": "100",
                         "disease": "ASTHMA"}])
    dj.write_drug_shards(tmp_path, drugs, vectors, fd, excl, ind)
    obj = read(tmp_path / "drugs" / "100.json")
    assert obj["vector"] == "b1"
    assert obj["formularies"]["F1"] == [3, "2", "28"]
    assert obj["formularies"]["F2"] == [2, None, None]
    assert obj["excluded_by"]["rows"][0][0] == "H1_001"
    assert obj["indications"] == [{"contract_plan": "H1_001", "disease": "ASTHMA"}]


def test_write_geo_uses_plan_indexes(tmp_path):
    geo = pd.DataFrame([{"fips": "01001", "name": "Autauga", "state": "AL",
                         "plans": [0, 2]}])
    dj.write_geo(tmp_path, geo)
    obj = read(tmp_path / "geo.json")
    assert obj["rows"][0] == ["01001", "Autauga", "AL", [0, 2]]


def test_nan_becomes_null(tmp_path):
    df = pd.DataFrame([{"plan_key": "H1_001_000", "contract_name": "C",
                        "plan_name": "P", "type": "MA", "snp": "0",
                        "premium": float("nan"), "deductible": 0.0,
                        "formulary_idx": 0, "suppressed": "N", "n_drugs": 10,
                        "pa_pct": 1.0, "st_pct": 0.0, "ql_pct": 2.0,
                        "n_excluded": 0, "states": ["NE"]}])
    dj.write_plans_index(tmp_path, df)
    obj = read(tmp_path / "plans_index.json")
    row = dict(zip(obj["cols"], obj["rows"][0]))
    assert row["premium"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_export.py -q`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Write `src/mpdp_formulary/export/dashboard_json.py`**

```python
"""Writers for all dashboard/data JSON artifacts. Shapes documented in the plan
and consumed by dashboard/js. Index files are {"cols": [...], "rows": [[...]]}.
"""
import json
import math
from pathlib import Path

import pandas as pd

DRUGS_INDEX_COLS = ["rxcui", "name", "bg", "ndc_count", "n_form", "cov_pct",
                    "pa_pct", "st_pct", "ql_pct", "excl_plans", "selected"]
PLANS_INDEX_COLS = ["plan_key", "contract_name", "plan_name", "type", "snp",
                    "premium", "deductible", "formulary_idx", "suppressed",
                    "n_drugs", "pa_pct", "st_pct", "ql_pct", "n_excluded",
                    "states"]
EXCLUDED_COLS = ["rxcui", "name", "tier", "pa", "st", "ql", "ql_amount",
                 "ql_days", "capped"]
EXCLUDED_BY_COLS = ["contract_plan", "plan_name", "tier", "pa", "st", "ql",
                    "ql_amount", "ql_days", "capped"]
FORMULARY_COLS = ["rxcui", "name", "bg", "tier", "pa", "st", "ql", "ql_amount",
                  "ql_days", "selected"]
GEO_COLS = ["fips", "name", "state", "plans"]
CHANNELS = ["PREF", "NONPREF", "MAIL_PREF", "MAIL_NONPREF"]
CHANNEL_KEYS = ["pref", "nonpref", "mail_pref", "mail_nonpref"]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return str(v)
    if hasattr(v, "item"):  # numpy scalar
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False),
                    encoding="utf-8")


def _rows(df: pd.DataFrame, cols: list[str]) -> list[list]:
    return [[_clean(v) for v in row] for row in df[cols].itertuples(index=False)]


def write_meta(out_dir: Path, meta: dict) -> None:
    _write(out_dir / "meta.json", meta)


def write_overview(out_dir: Path, overview: dict) -> None:
    _write(out_dir / "overview.json", overview)


def write_drugs_index(out_dir: Path, df: pd.DataFrame) -> None:
    _write(out_dir / "drugs_index.json",
           {"cols": DRUGS_INDEX_COLS, "rows": _rows(df, DRUGS_INDEX_COLS)})


def write_plans_index(out_dir: Path, df: pd.DataFrame) -> None:
    _write(out_dir / "plans_index.json",
           {"cols": PLANS_INDEX_COLS, "rows": _rows(df, PLANS_INDEX_COLS)})


def write_drug_shards(out_dir: Path, drugs: pd.DataFrame, vectors: pd.DataFrame,
                      formulary_drug: pd.DataFrame, excluded: pd.DataFrame,
                      indications: pd.DataFrame) -> int:
    """drugs: rxcui, name, bg, selected. vectors: rxcui, vector.
    formulary_drug: formulary_id, rxcui, tier, ql_amount, ql_days.
    excluded: contract_plan, plan_name, rxcui, tier, pa, st, ql, ql_amount,
    ql_days, capped. indications: contract_plan, rxcui, disease.
    """
    vec = vectors.set_index("rxcui")["vector"]
    fd_g = {k: g for k, g in formulary_drug.groupby("rxcui")}
    ex_g = {k: g for k, g in excluded.groupby("rxcui")} if len(excluded) else {}
    in_g = {k: g for k, g in indications.groupby("rxcui")} if len(indications) else {}
    n = 0
    for row in drugs.itertuples():
        fid_map = {}
        for f in fd_g.get(row.rxcui, pd.DataFrame()).itertuples():
            fid_map[f.formulary_id] = [_clean(f.tier), _clean(f.ql_amount),
                                       _clean(f.ql_days)]
        ex = ex_g.get(row.rxcui)
        ind = in_g.get(row.rxcui)
        obj = {
            "rxcui": row.rxcui,
            "name": row.name,
            "bg": row.bg,
            "selected": bool(row.selected),
            "vector": vec.get(row.rxcui, ""),
            "formularies": fid_map,
            "excluded_by": {
                "cols": EXCLUDED_BY_COLS,
                "rows": _rows(ex, EXCLUDED_BY_COLS) if ex is not None else [],
            },
            "indications": (
                [{"contract_plan": r.contract_plan, "disease": r.disease}
                 for r in ind.itertuples()] if ind is not None else []
            ),
        }
        _write(out_dir / "drugs" / f"{row.rxcui}.json", obj)
        n += 1
    return n


def write_plan_shards(out_dir: Path, plan_keys: list[str], costs: pd.DataFrame,
                      insulin: pd.DataFrame, excluded: pd.DataFrame,
                      indications: pd.DataFrame) -> int:
    """costs/insulin carry a plan_key column plus the raw uppercase PUF columns
    (already parquet-typed VARCHAR; numeric parsing happens here). excluded and
    indications carry contract_plan plus named drug columns (see write_drug_shards).
    """
    def num(v):
        v = (v or "").strip() if isinstance(v, str) else v
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    cost_g = {k: g for k, g in costs.groupby("plan_key")}
    ins_g = {k: g for k, g in insulin.groupby("plan_key")}
    ex_g = {k: g for k, g in excluded.groupby("contract_plan")} if len(excluded) else {}
    in_g = {k: g for k, g in indications.groupby("contract_plan")} if len(indications) else {}
    n = 0
    for pk in plan_keys:
        cp = "_".join(pk.split("_")[:2])  # contract_plan prefix
        cost_rows = []
        for r in cost_g.get(pk, pd.DataFrame()).itertuples():
            channels = {}
            for ch_key, ch in zip(CHANNEL_KEYS, CHANNELS):
                channels[ch_key] = [
                    num(getattr(r, f"COST_TYPE_{ch}")),
                    num(getattr(r, f"COST_AMT_{ch}")),
                    num(getattr(r, f"COST_MIN_AMT_{ch}")),
                    num(getattr(r, f"COST_MAX_AMT_{ch}")),
                ]
            cost_rows.append({
                "level": num(r.COVERAGE_LEVEL), "tier": num(r.TIER),
                "days": num(r.DAYS_SUPPLY), "specialty": r.TIER_SPECIALTY_YN,
                "ded_applies": r.DED_APPLIES_YN, "channels": channels,
            })
        ins_rows = []
        for r in ins_g.get(pk, pd.DataFrame()).itertuples():
            ins_rows.append({
                "tier": num(r.TIER), "days": num(r.DAYS_SUPPLY),
                "copay": [num(getattr(r, f"COPAY_AMT_{ch}_INSLN")) for ch in CHANNELS],
                "coin": [num(getattr(r, f"COIN_AMT_{ch}_INSLN")) for ch in CHANNELS],
            })
        ex = ex_g.get(cp)
        ind = in_g.get(cp)
        obj = {
            "plan_key": pk,
            "costs": cost_rows,
            "insulin": ins_rows,
            "excluded": {"cols": EXCLUDED_COLS,
                         "rows": _rows(ex, EXCLUDED_COLS) if ex is not None else []},
            "indications": (
                [{"rxcui": r.rxcui, "name": r.name, "disease": r.disease}
                 for r in ind.itertuples()] if ind is not None else []
            ),
        }
        _write(out_dir / "plans" / f"{pk}.json", obj)
        n += 1
    return n


def write_formulary_shards(out_dir: Path, formulary_drug_named: pd.DataFrame) -> int:
    n = 0
    for fid, g in formulary_drug_named.groupby("formulary_id"):
        _write(out_dir / "formularies" / f"{fid}.json",
               {"formulary_id": fid, "cols": FORMULARY_COLS,
                "rows": _rows(g.sort_values("name"), FORMULARY_COLS)})
        n += 1
    return n


def write_geo(out_dir: Path, geo: pd.DataFrame) -> None:
    _write(out_dir / "geo.json",
           {"cols": GEO_COLS, "rows": _rows(geo, GEO_COLS)})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_export.py -q`
Expected: `4 passed`

Note: `drugs.itertuples()` exposes the `name` column as `row.name`; pandas reserves `Index.name` only for `iterrows`, so `itertuples` is safe here, and the tests cover it.

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/export/dashboard_json.py tests/test_export.py
git commit -m "feat: add dashboard JSON export writers"
```

---

### Task 11: CLI orchestrator and full pipeline run

**Files:**
- Create: `src/mpdp_formulary/cli.py`

No new unit tests: every component is already covered; this task wires them and verifies against the real data (an integration run with exact expected row counts).

- [ ] **Step 1: Write `src/mpdp_formulary/cli.py`**

```python
"""Stage orchestrator. Usage: python -m mpdp_formulary.cli [stage]

Stages: ingest, transform, aggregate, export, all (default).
"""
import argparse

import duckdb
import pandas as pd

from . import layouts
from .aggregate import stats, status_vectors
from .export import dashboard_json
from .ingest import crosswalk, raw_files, rxnorm
from .transform import drugs as drugs_mod
from .transform import plans as plans_mod

TRANSFORM_BOUNDS = {"n_formularies": (200, 500), "n_drugs": (2_000, 50_000)}


def _pq(name: str) -> str:
    return (layouts.OUT_DIR / f"{name}.parquet").as_posix()


def _con_with_raw() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for key in layouts.LAYOUTS:
        con.execute(
            f"CREATE VIEW raw_{key} AS SELECT * FROM read_parquet('{_pq('raw_' + key)}')"
        )
    return con


def stage_ingest() -> None:
    raw_files.load_all(layouts.RAW_DIR, layouts.OUT_DIR)
    con = _con_with_raw()
    rxcuis = [r[0] for r in con.execute(
        """
        SELECT DISTINCT RXCUI FROM raw_basic
        UNION SELECT DISTINCT RXCUI FROM raw_excluded
        UNION SELECT DISTINCT RXCUI FROM raw_indication
        """
    ).fetchall()]
    conso = rxnorm.load_rxnconso(layouts.CACHE_DIR)
    names, rate = rxnorm.build_name_table(
        rxcuis, conso, rxnav=lambda r: rxnorm.rxnav_lookup(r, layouts.CACHE_DIR))
    names.to_parquet(layouts.OUT_DIR / "rxcui_names.parquet", index=False)
    print(f"ingest: rxnorm names for {len(names):,} RXCUIs, match rate {rate:.4f}")
    geo = con.execute("SELECT COUNTY_CODE, STATENAME, COUNTY FROM raw_geo").df()
    xwalk, xrate = crosswalk.build(
        geo, crosswalk.fetch_census_counties(layouts.CACHE_DIR))
    xwalk.to_parquet(layouts.OUT_DIR / "ssa_fips.parquet", index=False)
    print(f"ingest: ssa-fips crosswalk match rate {xrate:.4f}")


def stage_transform() -> None:
    con = _con_with_raw()
    plans_mod.build(con)
    dstats = drugs_mod.build(con)
    for metric, (lo, hi) in TRANSFORM_BOUNDS.items():
        if not lo <= dstats[metric] <= hi:
            raise ValueError(
                f"transform: {metric}={dstats[metric]} outside [{lo}, {hi}]")
    for t in ("plan_dim", "plan_county", "formulary_drug", "drug_dim"):
        con.execute(f"COPY {t} TO '{_pq(t)}' (FORMAT PARQUET)")
    orphans = con.execute(
        """
        SELECT DISTINCT formulary_id FROM plan_dim
        WHERE formulary_id NOT IN (SELECT formulary_id FROM formulary_drug)
        """
    ).fetchall()
    print(f"transform: {len(orphans)} formulary id(s) in plan info absent "
          f"from basic file: {[o[0] for o in orphans]}")


def stage_aggregate() -> None:
    con = duckdb.connect()
    fd = con.execute(f"SELECT * FROM read_parquet('{_pq('formulary_drug')}')").df()
    order = stats.formulary_order(fd)
    vectors = status_vectors.build_vectors(fd, order)
    vectors.to_parquet(layouts.OUT_DIR / "vectors.parquet", index=False)
    fs = stats.formulary_stats(fd)
    fs.to_parquet(layouts.OUT_DIR / "formulary_stats.parquet", index=False)
    plan_dim = con.execute(f"SELECT * FROM read_parquet('{_pq('plan_dim')}')").df()
    excluded = con.execute(
        f"SELECT * FROM read_parquet('{_pq('raw_excluded')}')").df()
    ps = stats.plan_stats(plan_dim, fs, excluded)
    ps.to_parquet(layouts.OUT_DIR / "plan_stats.parquet", index=False)
    pd.DataFrame({"formulary_id": order}).to_parquet(
        layouts.OUT_DIR / "formulary_order.parquet", index=False)
    print(f"aggregate: {len(vectors):,} vectors of length {len(order)}, "
          f"{len(ps):,} plan stats rows")


def stage_export() -> None:
    out = layouts.DASH_DATA_DIR
    con = duckdb.connect()

    def rd(name: str) -> pd.DataFrame:
        return con.execute(f"SELECT * FROM read_parquet('{_pq(name)}')").df()

    names = rd("rxcui_names")
    fd = rd("formulary_drug")
    drug_dim = rd("drug_dim")
    order = list(rd("formulary_order")["formulary_id"])
    vectors = rd("vectors")
    bridge = rd("plan_county")
    xwalk = rd("ssa_fips")
    raw = {k: rd(f"raw_{k}")
           for k in ("excluded", "indication", "bene_cost", "insulin", "geo")}

    # Plans index, sorted by plan_key; row position is the index used by geo.json.
    plans_sorted = rd("plan_stats").sort_values("plan_key").reset_index(drop=True)
    fidx = {fid: i for i, fid in enumerate(order)}
    plans_sorted["formulary_idx"] = plans_sorted["formulary_id"].map(
        lambda f: fidx.get(f, -1))
    geo_states = raw["geo"][["COUNTY_CODE", "STATENAME"]].copy()
    geo_states["state"] = geo_states["STATENAME"].str.upper().map(
        crosswalk.STATE_ABBREV)
    cs = bridge.merge(geo_states, left_on="county_code", right_on="COUNTY_CODE")
    states_map = (cs.dropna(subset=["state"]).groupby("plan_key")["state"]
                  .agg(lambda s: sorted(set(s))))
    plans_sorted["states"] = plans_sorted["plan_key"].map(states_map).apply(
        lambda v: v if isinstance(v, list) else [])
    pidx_df = plans_sorted.rename(columns={
        "plan_type": "type", "suppressed_yn": "suppressed"})
    dashboard_json.write_plans_index(out, pidx_df)

    # Drugs index. Excluded-only RXCUIs (absent from the basic file) still get
    # rows so the explorer can surface them; their vectors are all '-'.
    excl = raw["excluded"].copy()
    excl["contract_plan"] = excl["CONTRACT_ID"] + "_" + excl["PLAN_ID"]
    excl_counts = excl.groupby("RXCUI")["contract_plan"].nunique()
    di = drug_dim.merge(names, on="rxcui", how="left")
    di["name"] = di["name"].fillna("(unnamed) " + di["rxcui"])
    di["bg"] = di["brand_generic"].fillna("")
    di["cov_pct"] = (di["n_formularies"] / len(order) * 100).round(1)
    for c in ("pa", "st", "ql"):
        di[f"{c}_pct"] = (di[f"n_{c}"] / di["n_formularies"] * 100).round(1)
    di["excl_plans"] = di["rxcui"].map(excl_counts).fillna(0).astype(int)
    di["ndc_count"] = di["ndc_total"]
    di["n_form"] = di["n_formularies"]
    extra_ids = sorted(set(excl_counts.index) - set(di["rxcui"]))
    if extra_ids:
        extra = pd.DataFrame({"rxcui": extra_ids}).merge(names, "left", "rxcui")
        extra["name"] = extra["name"].fillna("(unnamed) " + extra["rxcui"])
        extra["bg"] = extra["brand_generic"].fillna("")
        extra = extra.assign(ndc_count=0, n_form=0, cov_pct=0.0, pa_pct=None,
                             st_pct=None, ql_pct=None, selected=False)
        extra["excl_plans"] = extra["rxcui"].map(excl_counts).astype(int)
        di = pd.concat([di[dashboard_json.DRUGS_INDEX_COLS],
                        extra[dashboard_json.DRUGS_INDEX_COLS]])
    di = di.sort_values("name").reset_index(drop=True)
    dashboard_json.write_drugs_index(out, di)
    missing_vec = sorted(set(di["rxcui"]) - set(vectors["rxcui"]))
    if missing_vec:
        vectors = pd.concat([vectors, pd.DataFrame(
            {"rxcui": missing_vec, "vector": ["-" * len(order)] * len(missing_vec)})])

    # Named exclusion and indication frames shared by drug and plan shards.
    cp_names = (plans_sorted
                .assign(cp=plans_sorted["contract_id"] + "_" + plans_sorted["plan_id"])
                .drop_duplicates("cp").set_index("cp")["plan_name"])
    ex = excl.merge(names[["rxcui", "name"]], left_on="RXCUI",
                    right_on="rxcui", how="left")
    ex["plan_name"] = ex["contract_plan"].map(cp_names)
    ex["tier"] = pd.to_numeric(ex["TIER"], errors="coerce")
    # The excluded file mixes flag conventions: QL is 0/1, PA/ST/capped are Y/N.
    ex["pa"] = ex["PRIOR_AUTH_YN"].isin(["Y", "1"])
    ex["st"] = ex["STEP_THERAPY_YN"].isin(["Y", "1"])
    ex["ql"] = ex["QUANTITY_LIMIT_YN"].isin(["Y", "1"])
    ex["capped"] = ex["CAPPED_BENEFIT_YN"].isin(["Y", "1"])
    ex["ql_amount"] = ex["QUANTITY_LIMIT_AMOUNT"].str.strip().replace("", None)
    ex["ql_days"] = ex["QUANTITY_LIMIT_DAYS"].str.strip().replace("", None)
    ind = raw["indication"].copy()
    ind["contract_plan"] = ind["CONTRACT_ID"] + "_" + ind["PLAN_ID"]
    ind = ind.merge(names[["rxcui", "name"]], left_on="RXCUI",
                    right_on="rxcui", how="left")
    ind["disease"] = ind["DISEASE"]

    n = dashboard_json.write_drug_shards(
        out, di[["rxcui", "name", "bg", "selected"]], vectors,
        fd[["formulary_id", "rxcui", "tier", "ql_amount", "ql_days"]], ex, ind)
    print(f"export: {n:,} drug shards")

    costs = raw["bene_cost"].copy()
    costs["plan_key"] = (costs["CONTRACT_ID"] + "_" + costs["PLAN_ID"]
                         + "_" + costs["SEGMENT_ID"])
    ins = raw["insulin"].copy()
    ins["plan_key"] = (ins["CONTRACT_ID"] + "_" + ins["PLAN_ID"]
                       + "_" + ins["SEGMENT_ID"])
    n = dashboard_json.write_plan_shards(
        out, list(plans_sorted["plan_key"]), costs, ins, ex, ind)
    print(f"export: {n:,} plan shards")

    fdn = fd.merge(names[["rxcui", "name", "brand_generic"]], on="rxcui", how="left")
    fdn["bg"] = fdn["brand_generic"].fillna("")
    fdn["name"] = fdn["name"].fillna("(unnamed) " + fdn["rxcui"])
    n = dashboard_json.write_formulary_shards(out, fdn)
    print(f"export: {n} formulary shards")

    g = (raw["geo"][["COUNTY_CODE", "STATENAME", "COUNTY"]]
         .merge(xwalk, left_on="COUNTY_CODE", right_on="county_code"))
    n_unmapped = int(g["fips"].isna().sum())
    g = g.dropna(subset=["fips"]).copy()
    g["state"] = g["STATENAME"].str.upper().map(crosswalk.STATE_ABBREV)
    pix = {pk: i for i, pk in enumerate(plans_sorted["plan_key"])}
    bplans = bridge.groupby("county_code")["plan_key"].agg(
        lambda s: sorted(pix[k] for k in set(s) if k in pix))
    g["plans"] = g["COUNTY_CODE"].map(bplans).apply(
        lambda v: v if isinstance(v, list) else [])
    g = g.rename(columns={"COUNTY": "name"})
    dashboard_json.write_geo(out, g[["fips", "name", "state", "plans"]])
    print(f"export: geo.json with {len(g):,} counties "
          f"({n_unmapped} SSA codes unmapped to FIPS)")

    tier_mix = fd.groupby("tier").size().reset_index(name="n").dropna()
    sel = di[di["selected"].astype(bool)]
    overview = {
        "tier_mix": [{"tier": int(t), "n": int(c)}
                     for t, c in tier_mix.sort_values("tier").values],
        "restrictions": {f"{c}_pct": round(float(fd[c].mean() * 100), 1)
                         for c in ("pa", "st", "ql")},
        "exclusions": {"rows": int(len(raw["excluded"])),
                       "distinct_rxcuis": int(raw["excluded"]["RXCUI"].nunique()),
                       "n_contract_plans": int(excl["contract_plan"].nunique())},
        "plan_types": [{"type": t, "n": int(c)} for t, c in
                       plans_sorted.groupby("plan_type").size().items()],
        "snp": [{"snp": s, "n": int(c)} for s, c in
                plans_sorted.groupby("snp").size().items()],
        "selected_drugs": [{"rxcui": r.rxcui, "name": r.name,
                            "n_formularies": int(r.n_form)}
                           for r in sel.itertuples()],
    }
    dashboard_json.write_overview(out, overview)
    meta = {
        "vintage": layouts.VINTAGE,
        "contract_year": layouts.CONTRACT_YEAR,
        "formulary_order": order,
        "counts": {"plans": int(len(plans_sorted)),
                   "contracts": int(plans_sorted["contract_id"].nunique()),
                   "formularies": len(order),
                   "drugs": int(len(di))},
        "snp_labels": {"0": "Not a SNP",
                       "1": "Chronic or disabling condition SNP",
                       "2": "Dual-eligible SNP", "3": "Institutional SNP"},
        "coverage_level_labels": {"0": "Pre-deductible", "1": "Initial coverage",
                                  "3": "Catastrophic"},
        "days_supply_labels": {"1": "30-day", "2": "90-day", "3": "Other",
                               "4": "60-day"},
        "plan_type_labels": {"MA": "Medicare Advantage (local)",
                             "MA_REGIONAL": "Medicare Advantage (regional)",
                             "PDP": "Stand-alone PDP", "OTHER": "Other"},
    }
    dashboard_json.write_meta(out, meta)
    n_files = sum(1 for _ in out.rglob("*.json"))
    total = sum(f.stat().st_size for f in out.rglob("*.json"))
    print(f"export: {n_files:,} JSON files, {total / 1e6:.1f} MB total")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=["ingest", "transform", "aggregate", "export", "all"])
    args = parser.parse_args(argv)
    stages = {"ingest": stage_ingest, "transform": stage_transform,
              "aggregate": stage_aggregate, "export": stage_export}
    for name in (list(stages) if args.stage == "all" else [args.stage]):
        print(f"=== {name} ===")
        stages[name]()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass (35 from Tasks 1-10)

- [ ] **Step 3: Run the full pipeline on real data**

Run: `uv run python -m mpdp_formulary.cli all`

First run downloads the RxNorm prescribable release (a few hundred MB, several minutes) and the Census county file; both are cached under `data/cache/` so reruns are fast. Expected ingest row counts must match exactly:

```
ingest: plan_info    112,294 rows -> raw_plan_info.parquet
ingest: basic      1,123,842 rows -> raw_basic.parquet
ingest: excluded      13,717 rows -> raw_excluded.parquet
ingest: bene_cost    172,660 rows -> raw_bene_cost.parquet
ingest: insulin       43,066 rows -> raw_insulin.parquet
ingest: indication       367 rows -> raw_indication.parquet
ingest: geo            3,279 rows -> raw_geo.parquet
```

Then expect: rxnorm match rate >= 0.99; crosswalk match rate >= 0.97; transform reporting 328 formularies and exactly 1 orphan formulary ID; aggregate and export completing with file counts. If the RxNav fallback loop appears to process hundreds of RXCUIs, stop and investigate (the prescribable release should cover nearly all of them).

Record the printed match rates, the orphan formulary ID, the unmapped-SSA-county count, and the total export size; Task 17 puts them in the README.

- [ ] **Step 4: Sanity-check the export output**

Run: `uv run python -c "import json; m = json.load(open('dashboard/data/meta.json', encoding='utf-8')); print(m['counts']); print(len(m['formulary_order']))"`
Expected: plausible counts (formularies = 328) and no exception.

- [ ] **Step 5: Commit**

```bash
git add src/mpdp_formulary/cli.py
git commit -m "feat: add pipeline CLI and verify full run on May 2026 data"
```

---

### Task 12: Dashboard shell

**Files:**
- Create: `dashboard/index.html`, `dashboard/styles.css`, `dashboard/js/app.js`, `dashboard/js/data.js`, `dashboard/js/fmt.js`, `dashboard/js/views/overview.js`, `dashboard/js/views/methods.js`, `dashboard/js/views/drugs.js`, `dashboard/js/views/plans.js`, `dashboard/js/views/compare.js`
- Vendor: `dashboard/vendor/echarts.min.js` (copy), `dashboard/vendor/counties-fips.json` (download once)

- [ ] **Step 1: Vendor the static assets**

```powershell
New-Item -ItemType Directory -Force dashboard\vendor | Out-Null
Copy-Item "..\retina\pilot\dashboard\vendor\echarts.min.js" dashboard\vendor\
curl.exe -L -o dashboard\vendor\counties-fips.json https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json
```

Verify `counties-fips.json` is ~2.4 MB and starts with `{"type":"FeatureCollection"`.

- [ ] **Step 2: Write `dashboard/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MPDP Formulary Dashboard (2026-05)</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<header>
  <h1>Medicare Part D Formulary Explorer</h1>
  <nav id="nav">
    <button data-view="overview" class="active">Overview</button>
    <button data-view="drugs">Drug explorer</button>
    <button data-view="plans">Plan explorer</button>
    <button data-view="compare">Compare</button>
    <button data-view="methods">Methods</button>
  </nav>
  <span id="vintage"></span>
</header>
<main id="view"></main>
<script src="vendor/echarts.min.js"></script>
<script src="js/fmt.js"></script>
<script src="js/data.js"></script>
<script src="js/views/overview.js"></script>
<script src="js/views/drugs.js"></script>
<script src="js/views/plans.js"></script>
<script src="js/views/compare.js"></script>
<script src="js/views/methods.js"></script>
<script src="js/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `dashboard/styles.css`**

```css
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif;
       color: #1a1d23; background: #f5f6f8; }
header { display: flex; align-items: center; gap: 16px; padding: 10px 20px;
         background: #102a43; color: #fff; flex-wrap: wrap; }
header h1 { font-size: 16px; margin: 0 12px 0 0; font-weight: 600; }
#nav button { background: transparent; border: 1px solid #486581; color: #d9e2ec;
              padding: 5px 12px; margin-right: 6px; border-radius: 4px;
              cursor: pointer; font-size: 13px; }
#nav button.active { background: #2680c2; border-color: #2680c2; color: #fff; }
#vintage { margin-left: auto; font-size: 12px; color: #9fb3c8; }
main { padding: 18px 20px; max-width: 1280px; margin: 0 auto; }
h2 { font-size: 18px; margin: 4px 0 12px; }
h3 { font-size: 14px; margin: 0 0 8px; }
.cards { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.card { background: #fff; border: 1px solid #d9e2ec; border-radius: 6px;
        padding: 12px 16px; min-width: 150px; }
.card .v { font-size: 22px; font-weight: 700; }
.card .l { font-size: 12px; color: #627d98; }
.panel { background: #fff; border: 1px solid #d9e2ec; border-radius: 6px;
         padding: 14px; margin-bottom: 14px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.chart { height: 280px; }
.map { height: 430px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid #e4e9f0; }
th { color: #627d98; font-weight: 600; white-space: nowrap; }
tr.click { cursor: pointer; }
tr.click:hover { background: #f0f6fc; }
.muted { color: #627d98; }
.error { background: #ffe3e3; border: 1px solid #ffb3b3; padding: 10px 14px;
         border-radius: 6px; }
.badge { display: inline-block; padding: 1px 7px; border-radius: 10px;
         font-size: 11px; background: #e4e9f0; margin-left: 6px; }
.badge.warn { background: #ffe9b3; }
.controls { display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
            margin-bottom: 10px; }
.controls input[type=text] { padding: 6px 9px; border: 1px solid #bcccdc;
                             border-radius: 4px; min-width: 260px; }
.controls select { padding: 5px 8px; border: 1px solid #bcccdc;
                   border-radius: 4px; }
a { color: #2680c2; }
@media (max-width: 900px) { .grid2 { grid-template-columns: 1fr; } }
```

- [ ] **Step 4: Write `dashboard/js/fmt.js`**

```js
const Fmt = {
  money: v => v == null ? "n/a" : "$" + Number(v).toFixed(2),
  pct: v => v == null ? "n/a" : Number(v).toFixed(1) + "%",
  num: v => v == null ? "n/a" : Number(v).toLocaleString("en-US"),
  flag: b => b ? "Yes" : "No",
  esc: s => String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])),
  // Channel cell from [type, amt, min, max]: type 0/null = not offered,
  // 1 = copay in dollars, 2 = coinsurance as a fraction of drug cost.
  cost(ch) {
    if (!ch || !ch[0]) return "n/a";
    const [type, amt, min, max] = ch;
    if (type === 1) return Fmt.money(amt);
    let s = Math.round((amt || 0) * 100) + "%";
    if (min) s += `, min ${Fmt.money(min)}`;
    if (max) s += `, max ${Fmt.money(max)}`;
    return s;
  },
  // Decode one status-vector character: null = not listed, else PA/ST/QL bits.
  status(ch) {
    if (!ch || ch === "-") return null;
    const m = parseInt(ch, 16);
    return {pa: !!(m & 2), st: !!(m & 4), ql: !!(m & 8)};
  },
  restr(ch) {
    const s = Fmt.status(ch);
    if (!s) return "not listed";
    const parts = [];
    if (s.pa) parts.push("PA");
    if (s.st) parts.push("ST");
    if (s.ql) parts.push("QL");
    return parts.length ? parts.join(" + ") : "unrestricted";
  },
};
```

- [ ] **Step 5: Write `dashboard/js/data.js`**

```js
const Data = (() => {
  const cache = new Map();
  function json(path) {
    if (!cache.has(path)) {
      cache.set(path, fetch(path).then(r => {
        if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
        return r.json();
      }));
    }
    return cache.get(path);
  }
  function table(obj) {
    return obj.rows.map(r =>
      Object.fromEntries(obj.cols.map((c, i) => [c, r[i]])));
  }
  return {
    json, table,
    meta: () => json("data/meta.json"),
    overview: () => json("data/overview.json"),
    drugsIndex: () => json("data/drugs_index.json").then(table),
    plansIndex: () => json("data/plans_index.json").then(table),
    geo: () => json("data/geo.json").then(table),
    drug: rxcui => json(`data/drugs/${rxcui}.json`),
    plan: key => json(`data/plans/${key}.json`),
    formulary: fid => json(`data/formularies/${fid}.json`),
  };
})();
```

- [ ] **Step 6: Write `dashboard/js/app.js` and the five stub views**

`dashboard/js/app.js`:

```js
window.MPDP = window.MPDP || {views: {}};
(async function () {
  const nav = document.getElementById("nav");
  const root = document.getElementById("view");
  async function show(name, arg) {
    nav.querySelectorAll("button").forEach(b =>
      b.classList.toggle("active", b.dataset.view === name));
    root.innerHTML = "<p class='muted'>Loading…</p>";
    try {
      await MPDP.views[name].render(root, arg);
    } catch (err) {
      root.innerHTML =
        `<div class="error">Failed to render ${Fmt.esc(name)}: ` +
        `${Fmt.esc(err.message)}</div>`;
      console.error(err);
    }
  }
  MPDP.show = show;
  nav.addEventListener("click", e => {
    if (e.target.dataset.view) show(e.target.dataset.view);
  });
  const meta = await Data.meta();
  document.getElementById("vintage").textContent = `Data: ${meta.vintage}`;
  show("overview");
})();
```

Each of the five files `dashboard/js/views/{overview,drugs,plans,compare,methods}.js` gets the same stub with its own name (shown here for overview):

```js
window.MPDP = window.MPDP || {views: {}};
MPDP.views.overview = {
  async render(root) {
    root.innerHTML = "<h2>Overview</h2><p class='muted'>Implemented in a later task.</p>";
  },
};
```

- [ ] **Step 7: Serve and verify**

Run (background): `uv run python -m http.server 8765 --directory dashboard`
Open `http://localhost:8765` with the dev-browser skill (repo convention). Verify: header shows `Data: 2026-05-31`; all five nav buttons switch the stub content; the browser console shows no errors (vendor scripts and `data/meta.json` all load).

- [ ] **Step 8: Commit**

```bash
git add dashboard/index.html dashboard/styles.css dashboard/js dashboard/vendor
git commit -m "feat: add static dashboard shell with vendored assets"
```

---

### Task 13: Overview and Methods views

**Files:**
- Modify: `dashboard/js/views/overview.js`, `dashboard/js/views/methods.js` (replace the stubs entirely)

- [ ] **Step 1: Write `dashboard/js/views/overview.js`**

```js
window.MPDP = window.MPDP || {views: {}};
MPDP.views.overview = {
  async render(root) {
    const [meta, ov] = await Promise.all([Data.meta(), Data.overview()]);
    const card = (v, l) =>
      `<div class="card"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    const typeRows = ov.plan_types.map(t =>
      `<tr><td>${Fmt.esc(meta.plan_type_labels[t.type] || t.type)}</td>` +
      `<td>${Fmt.num(t.n)}</td></tr>`).join("");
    const snpRows = ov.snp.map(s =>
      `<tr><td>${Fmt.esc(meta.snp_labels[s.snp] || s.snp)}</td>` +
      `<td>${Fmt.num(s.n)}</td></tr>`).join("");
    const selRows = ov.selected_drugs.map(d =>
      `<tr class="click" data-rxcui="${Fmt.esc(d.rxcui)}">` +
      `<td><a href="#">${Fmt.esc(d.name)}</a></td><td>${d.rxcui}</td>` +
      `<td>${Fmt.num(d.n_formularies)}</td></tr>`).join("");
    root.innerHTML = `
      <h2>Market overview</h2>
      <div class="cards">
        ${card(Fmt.num(meta.counts.plans), "Plans (contract-plan-segment)")}
        ${card(Fmt.num(meta.counts.contracts), "Contracts")}
        ${card(Fmt.num(meta.counts.formularies), "Formularies")}
        ${card(Fmt.num(meta.counts.drugs), "Distinct drugs (RXCUI)")}
      </div>
      <div class="grid2">
        <div class="panel"><h3>Tier mix (formulary-drug listings)</h3>
          <div id="tierChart" class="chart"></div></div>
        <div class="panel"><h3>Restriction prevalence (share of listings)</h3>
          <div id="restrChart" class="chart"></div></div>
      </div>
      <div class="grid2">
        <div class="panel"><h3>Plans by type</h3>
          <table><thead><tr><th>Type</th><th>Plans</th></tr></thead>
          <tbody>${typeRows}</tbody></table></div>
        <div class="panel"><h3>Plans by special needs status</h3>
          <table><thead><tr><th>SNP type</th><th>Plans</th></tr></thead>
          <tbody>${snpRows}</tbody></table></div>
      </div>
      <div class="panel"><h3>Drugs selected for Medicare price negotiation</h3>
        <table><thead><tr><th>Drug</th><th>RXCUI</th><th>Formularies listing</th>
        </tr></thead><tbody>${selRows}</tbody></table></div>
      <div class="panel"><h3>Exclusions</h3>
        <p>${Fmt.num(ov.exclusions.rows)} exclusion records covering
        ${Fmt.num(ov.exclusions.distinct_rxcuis)} distinct drugs across
        ${Fmt.num(ov.exclusions.n_contract_plans)} contract-plans.
        Browse them per drug or per plan in the explorers.</p></div>`;
    root.querySelectorAll("tr[data-rxcui]").forEach(tr =>
      tr.addEventListener("click", e => {
        e.preventDefault();
        MPDP.show("drugs", tr.dataset.rxcui);
      }));
    echarts.init(document.getElementById("tierChart")).setOption({
      tooltip: {},
      grid: {left: 70, right: 16, top: 16, bottom: 24},
      xAxis: {type: "category",
              data: ov.tier_mix.map(t => "Tier " + t.tier)},
      yAxis: {type: "value"},
      series: [{type: "bar", data: ov.tier_mix.map(t => t.n)}],
    });
    echarts.init(document.getElementById("restrChart")).setOption({
      tooltip: {valueFormatter: v => v + "%"},
      grid: {left: 70, right: 16, top: 16, bottom: 24},
      xAxis: {type: "category",
              data: ["Prior authorization", "Step therapy", "Quantity limit"]},
      yAxis: {type: "value", axisLabel: {formatter: "{value}%"}},
      series: [{type: "bar", data: [ov.restrictions.pa_pct,
                ov.restrictions.st_pct, ov.restrictions.ql_pct]}],
    });
  },
};
```

- [ ] **Step 2: Write `dashboard/js/views/methods.js`**

```js
window.MPDP = window.MPDP || {views: {}};
MPDP.views.methods = {
  async render(root) {
    const meta = await Data.meta();
    root.innerHTML = `
      <h2>Methods and caveats</h2>
      <div class="panel"><h3>Source</h3>
        <p>CMS Monthly Prescription Drug Plan Formulary and Pharmacy Network
        Information PUF, snapshot dated ${Fmt.esc(meta.vintage)}, contract year
        ${Fmt.esc(meta.contract_year)}. Drug names resolve through the RxNorm
        Current Prescribable Content release with an RxNav fallback for retired
        identifiers.</p></div>
      <div class="panel"><h3>Grain and aggregation rules</h3><ul>
        <li>The basic formulary file is NDC-grain; this dashboard aggregates to
        RXCUI grain. A restriction flag is shown if any NDC of the drug carries
        it; the tier shown is the modal tier across the drug's NDCs.</li>
        <li>A "plan" is one CONTRACT_ID + PLAN_ID + SEGMENT_ID combination.
        Plans reference one of ${Fmt.num(meta.counts.formularies)} formularies;
        coverage statistics are computed at the formulary level.</li>
        <li>Excluded drugs are reported per contract-plan (the source file has
        no segment), so exclusions apply to every segment of that plan.</li></ul>
      </div>
      <div class="panel"><h3>Caveats</h3><ul>
        <li>NDCs in the source are proxy codes for drug products, not complete
        package-level listings.</li>
        <li>Plans flagged as suppressed by CMS keep their identity rows but
        their cost data is hidden here.</li>
        <li>County mapping crosses SSA county codes to FIPS by state and county
        name; a small number of counties may not map and render as no-data.</li>
        <li>Local MA plans (H contracts) list exact service-area counties;
        regional MA (R) and PDP (S) contracts are expanded from their CMS
        regions, so county-level precision differs by plan type.</li>
        <li>This is a single monthly snapshot; no trend analysis.</li>
        <li>Pharmacy network data (preferred pharmacies, dispensing fees) is
        not included in this version.</li></ul></div>`;
  },
};
```

- [ ] **Step 3: Verify in the browser**

With the server from Task 12 still running, reload `http://localhost:8765`. Verify: four stat cards show real counts; both charts render; clicking a selected-drug row switches to the (still stubbed) drug explorer without console errors; Methods renders the text.

- [ ] **Step 4: Commit**

```bash
git add dashboard/js/views/overview.js dashboard/js/views/methods.js
git commit -m "feat: implement overview and methods views"
```

---

### Task 14: Drug explorer view with county map

**Files:**
- Modify: `dashboard/js/views/drugs.js` (replace the stub entirely)

The county metric is computed client-side: for each county, over its plans (filtered by plan type, skipping `formulary_idx < 0`), the share whose formulary status character indicates coverage (`covered` metric: any non-`-`; `unrestricted` metric: exactly `"1"`).

- [ ] **Step 1: Write `dashboard/js/views/drugs.js`**

```js
window.MPDP = window.MPDP || {views: {}};
(() => {
  let mapRegistered = false;
  async function ensureCountyMap() {
    if (mapRegistered) return;
    const gj = await Data.json("vendor/counties-fips.json");
    gj.features.forEach(f => { f.properties.fips = f.id; });
    echarts.registerMap("US_COUNTIES", gj);
    mapRegistered = true;
  }

  function countyValues(vector, plans, geo, metric, types) {
    const vals = [];
    for (const c of geo) {
      let tot = 0, hit = 0;
      for (const i of c.plans) {
        const p = plans[i];
        if (!types.has(p.type) || p.formulary_idx < 0) continue;
        tot++;
        const ch = vector[p.formulary_idx];
        if (!ch || ch === "-") continue;
        if (metric === "covered" || ch === "1") hit++;
      }
      if (tot) vals.push({name: c.fips, value: Math.round(1000 * hit / tot) / 10});
    }
    return vals;
  }

  MPDP.views.drugs = {
    async render(root, rxcui) {
      const drugs = await Data.drugsIndex();
      root.innerHTML = `
        <h2>Drug explorer</h2>
        <div class="panel">
          <div class="controls">
            <input type="text" id="dSearch" placeholder="Search drug name or RXCUI">
            <select id="dBg"><option value="">Brand + generic</option>
              <option value="brand">Brand</option>
              <option value="generic">Generic</option></select>
            <label><input type="checkbox" id="dExcl"> Excluded somewhere</label>
            <label><input type="checkbox" id="dSel"> Negotiation-selected</label>
            <span class="muted" id="dCount"></span>
          </div>
          <div id="dTable"></div>
        </div>
        <div id="dDetail"></div>`;
      const tableEl = root.querySelector("#dTable");

      function draw() {
        const q = root.querySelector("#dSearch").value.trim().toLowerCase();
        const bg = root.querySelector("#dBg").value;
        let rows = drugs;
        if (q) rows = rows.filter(d =>
          d.name.toLowerCase().includes(q) || d.rxcui.startsWith(q));
        if (bg) rows = rows.filter(d => d.bg === bg);
        if (root.querySelector("#dExcl").checked)
          rows = rows.filter(d => d.excl_plans > 0);
        if (root.querySelector("#dSel").checked)
          rows = rows.filter(d => d.selected);
        root.querySelector("#dCount").textContent =
          `${Fmt.num(rows.length)} drugs` +
          (rows.length > 200 ? ", showing first 200" : "");
        tableEl.innerHTML = `<table><thead><tr>
          <th>Drug</th><th>Type</th><th>Coverage</th><th>PA</th><th>ST</th>
          <th>QL</th><th>Excluding plans</th></tr></thead><tbody>` +
          rows.slice(0, 200).map(d =>
            `<tr class="click" data-rxcui="${Fmt.esc(d.rxcui)}">
              <td>${Fmt.esc(d.name)}${d.selected
                ? '<span class="badge">negotiation</span>' : ""}</td>
              <td>${d.bg || ""}</td><td>${Fmt.pct(d.cov_pct)}</td>
              <td>${Fmt.pct(d.pa_pct)}</td><td>${Fmt.pct(d.st_pct)}</td>
              <td>${Fmt.pct(d.ql_pct)}</td><td>${Fmt.num(d.excl_plans)}</td></tr>`
          ).join("") + "</tbody></table>";
        tableEl.querySelectorAll("tr[data-rxcui]").forEach(tr =>
          tr.addEventListener("click", () => showDetail(tr.dataset.rxcui)));
      }
      ["#dSearch", "#dBg", "#dExcl", "#dSel"].forEach(sel =>
        root.querySelector(sel).addEventListener("input", draw));
      draw();

      async function showDetail(id) {
        const el = root.querySelector("#dDetail");
        el.innerHTML = "<p class='muted'>Loading drug detail…</p>";
        const [d, meta, plans] = await Promise.all(
          [Data.drug(id), Data.meta(), Data.plansIndex()]);
        const planByFidx = new Map();
        plans.forEach(p => {
          if (!planByFidx.has(p.formulary_idx)) planByFidx.set(p.formulary_idx, []);
          planByFidx.get(p.formulary_idx).push(p);
        });
        const fRows = meta.formulary_order.map((fid, i) => {
          const ch = d.vector[i];
          if (!ch || ch === "-") return null;
          const det = d.formularies[fid] || [null, null, null];
          return {fid, tier: det[0], qla: det[1], qld: det[2],
                  restr: Fmt.restr(ch),
                  nPlans: (planByFidx.get(i) || []).length};
        }).filter(Boolean).sort((a, b) => (a.tier || 99) - (b.tier || 99));
        const exRows = Data.table(d.excluded_by);
        el.innerHTML = `
          <h2>${Fmt.esc(d.name)}
            <span class="muted">RXCUI ${Fmt.esc(d.rxcui)}</span>
            ${d.selected ? '<span class="badge">negotiation-selected</span>' : ""}
          </h2>
          <div class="grid2">
            <div class="panel"><h3>Tier placement across formularies</h3>
              <div id="dTier" class="chart"></div></div>
            <div class="panel"><h3>County coverage map</h3>
              <div class="controls">
                <select id="dMetric">
                  <option value="unrestricted">% of plans covering without PA/ST/QL</option>
                  <option value="covered">% of plans covering at all</option>
                </select>
                <label><input type="checkbox" class="dType" value="MA" checked> MA</label>
                <label><input type="checkbox" class="dType" value="MA_REGIONAL" checked> MA regional</label>
                <label><input type="checkbox" class="dType" value="PDP" checked> PDP</label>
              </div>
              <div id="dMap" class="map"></div></div>
          </div>
          <div class="panel">
            <h3>Formularies listing this drug (${fRows.length})</h3>
            <table><thead><tr><th>Formulary</th><th>Tier</th><th>Restrictions</th>
              <th>QL amount / days</th><th>Plans using</th></tr></thead><tbody>` +
          fRows.map(r => `<tr><td>${r.fid}</td><td>${r.tier ?? "n/a"}</td>
              <td>${r.restr}</td>
              <td>${r.qla ? `${Fmt.esc(r.qla)} / ${Fmt.esc(r.qld)}d` : ""}</td>
              <td>${Fmt.num(r.nPlans)}</td></tr>`).join("") +
          `</tbody></table></div>
          <div class="panel"><h3>Plans excluding this drug (${exRows.length})</h3>` +
          (exRows.length ? `<table><thead><tr><th>Plan</th><th>Tier</th>
              <th>PA</th><th>ST</th><th>QL</th><th>Capped</th></tr></thead><tbody>` +
            exRows.map(r => `<tr>
              <td>${Fmt.esc(r.plan_name || r.contract_plan)}</td>
              <td>${r.tier ?? ""}</td><td>${Fmt.flag(r.pa)}</td>
              <td>${Fmt.flag(r.st)}</td>
              <td>${r.ql ? `${Fmt.esc(r.ql_amount || "?")} / ${Fmt.esc(r.ql_days || "?")}d` : "No"}</td>
              <td>${Fmt.flag(r.capped)}</td></tr>`).join("") +
            "</tbody></table>" : "<p class='muted'>None.</p>") + "</div>" +
          (d.indications.length ? `<div class="panel">
            <h3>Indication-based coverage</h3><ul>` +
            d.indications.map(i =>
              `<li>${Fmt.esc(i.contract_plan)}: ${Fmt.esc(i.disease)}</li>`).join("") +
            "</ul></div>" : "");
        el.scrollIntoView({behavior: "smooth"});

        const tierCounts = {};
        fRows.forEach(r => {
          if (r.tier) tierCounts[r.tier] = (tierCounts[r.tier] || 0) + 1;
        });
        const tiers = Object.keys(tierCounts).sort((a, b) => a - b);
        echarts.init(el.querySelector("#dTier")).setOption({
          tooltip: {},
          grid: {left: 50, right: 16, top: 16, bottom: 24},
          xAxis: {type: "category", data: tiers.map(t => "Tier " + t)},
          yAxis: {type: "value"},
          series: [{type: "bar", data: tiers.map(t => tierCounts[t])}],
        });

        await ensureCountyMap();
        const geo = await Data.geo();
        const countyName = new Map(geo.map(c => [c.fips, `${c.name}, ${c.state}`]));
        const mapChart = echarts.init(el.querySelector("#dMap"));
        function drawMap() {
          const metric = el.querySelector("#dMetric").value;
          const types = new Set(
            [...el.querySelectorAll(".dType:checked")].map(c => c.value));
          mapChart.setOption({
            tooltip: {formatter: p =>
              `${countyName.get(p.name) || p.name}: ` +
              (p.value == null || isNaN(p.value) ? "no data" : p.value + "%")},
            visualMap: {min: 0, max: 100, calculable: true,
                        inRange: {color: ["#f7fbff", "#08519c"]}},
            series: [{type: "map", map: "US_COUNTIES", nameProperty: "fips",
                      data: countyValues(d.vector, plans, geo, metric, types),
                      emphasis: {label: {show: false}}}],
          }, true);
        }
        el.querySelector("#dMetric").addEventListener("input", drawMap);
        el.querySelectorAll(".dType").forEach(c =>
          c.addEventListener("input", drawMap));
        drawMap();
      }

      if (rxcui) showDetail(rxcui);
    },
  };
})();
```

- [ ] **Step 2: Verify in the browser**

Reload `http://localhost:8765`, open Drug explorer. Verify: search narrows the table; clicking a drug renders the detail; the tier chart and county map draw (map colors vary by county; toggling metric and plan-type checkboxes redraws); the negotiation-selected filter works; a drug with exclusions (use the "Excluded somewhere" filter) shows its excluding-plans table; no console errors. Also verify the Overview selected-drug click-through now lands on a rendered detail.

- [ ] **Step 3: Commit**

```bash
git add dashboard/js/views/drugs.js
git commit -m "feat: implement drug explorer with county coverage map"
```

---

### Task 15: Plan explorer view

**Files:**
- Modify: `dashboard/js/views/plans.js` (replace the stub entirely)

- [ ] **Step 1: Write `dashboard/js/views/plans.js`**

```js
window.MPDP = window.MPDP || {views: {}};
(() => {
  MPDP.views.plans = {
    async render(root, planKey) {
      const [meta, plans] = await Promise.all([Data.meta(), Data.plansIndex()]);
      const states = [...new Set(plans.flatMap(p => p.states))].sort();
      root.innerHTML = `
        <h2>Plan explorer</h2>
        <div class="panel"><div class="controls">
          <input type="text" id="pSearch" placeholder="Search plan, contract, or key">
          <select id="pType"><option value="">All types</option>
            ${Object.entries(meta.plan_type_labels).map(([k, v]) =>
              `<option value="${k}">${Fmt.esc(v)}</option>`).join("")}</select>
          <select id="pSnp"><option value="">All SNP statuses</option>
            ${Object.entries(meta.snp_labels).map(([k, v]) =>
              `<option value="${k}">${Fmt.esc(v)}</option>`).join("")}</select>
          <select id="pState"><option value="">All states</option>
            ${states.map(s => `<option>${s}</option>`).join("")}</select>
          <span class="muted" id="pCount"></span></div>
          <div id="pTable"></div></div>
        <div id="pDetail"></div>`;

      function draw() {
        const q = root.querySelector("#pSearch").value.trim().toLowerCase();
        const ty = root.querySelector("#pType").value;
        const sn = root.querySelector("#pSnp").value;
        const st = root.querySelector("#pState").value;
        let rows = plans;
        if (q) rows = rows.filter(p =>
          (p.plan_name || "").toLowerCase().includes(q) ||
          (p.contract_name || "").toLowerCase().includes(q) ||
          p.plan_key.toLowerCase().startsWith(q));
        if (ty) rows = rows.filter(p => p.type === ty);
        if (sn) rows = rows.filter(p => p.snp === sn);
        if (st) rows = rows.filter(p => p.states.includes(st));
        root.querySelector("#pCount").textContent =
          `${Fmt.num(rows.length)} plans` +
          (rows.length > 200 ? ", showing first 200" : "");
        root.querySelector("#pTable").innerHTML = `<table><thead><tr>
          <th>Plan</th><th>Type</th><th>Premium</th><th>Deductible</th>
          <th>Drugs</th><th>PA</th><th>QL</th><th>Excluded</th></tr></thead><tbody>` +
          rows.slice(0, 200).map(p =>
            `<tr class="click" data-key="${Fmt.esc(p.plan_key)}">
              <td>${Fmt.esc(p.plan_name)}
                ${p.suppressed === "Y"
                  ? '<span class="badge warn">suppressed</span>' : ""}
                ${p.snp !== "0" ? '<span class="badge">SNP</span>' : ""}</td>
              <td>${p.type}</td><td>${Fmt.money(p.premium)}</td>
              <td>${Fmt.money(p.deductible)}</td><td>${Fmt.num(p.n_drugs)}</td>
              <td>${Fmt.pct(p.pa_pct)}</td><td>${Fmt.pct(p.ql_pct)}</td>
              <td>${Fmt.num(p.n_excluded)}</td></tr>`).join("") +
          "</tbody></table>";
        root.querySelectorAll("tr[data-key]").forEach(tr =>
          tr.addEventListener("click", () => showDetail(tr.dataset.key)));
      }
      ["#pSearch", "#pType", "#pSnp", "#pState"].forEach(sel =>
        root.querySelector(sel).addEventListener("input", draw));
      draw();

      async function showDetail(key) {
        const el = root.querySelector("#pDetail");
        el.innerHTML = "<p class='muted'>Loading plan detail…</p>";
        const p = plans.find(x => x.plan_key === key);
        const shard = await Data.plan(key);
        const suppressed = p.suppressed === "Y";

        const costsByLevel = {};
        shard.costs.forEach(c => {
          (costsByLevel[c.level] = costsByLevel[c.level] || []).push(c);
        });
        const costTables = suppressed
          ? "<p class='muted'>Cost data suppressed by CMS for this plan.</p>"
          : Object.keys(costsByLevel).sort().map(level => {
              const rows = costsByLevel[level].sort((a, b) =>
                (a.tier - b.tier) || (a.days - b.days));
              return `<h4>${Fmt.esc(meta.coverage_level_labels[level] ||
                  ("Level " + level))}</h4>
                <table><thead><tr><th>Tier</th><th>Supply</th>
                  <th>Preferred retail</th><th>Standard retail</th>
                  <th>Preferred mail</th><th>Standard mail</th>
                  <th>Deductible applies</th></tr></thead><tbody>` +
                rows.map(c => `<tr>
                  <td>${c.tier}${c.specialty === "Y"
                    ? ' <span class="badge">specialty</span>' : ""}</td>
                  <td>${Fmt.esc(meta.days_supply_labels[c.days] || c.days)}</td>
                  <td>${Fmt.cost(c.channels.pref)}</td>
                  <td>${Fmt.cost(c.channels.nonpref)}</td>
                  <td>${Fmt.cost(c.channels.mail_pref)}</td>
                  <td>${Fmt.cost(c.channels.mail_nonpref)}</td>
                  <td>${c.ded_applies}</td></tr>`).join("") +
                "</tbody></table>";
            }).join("");

        const insTable = suppressed || !shard.insulin.length ? "" :
          `<div class="panel"><h3>Insulin cost sharing</h3>
            <table><thead><tr><th>Tier</th><th>Supply</th>
              <th>Preferred retail</th><th>Standard retail</th>
              <th>Preferred mail</th><th>Standard mail</th></tr></thead><tbody>` +
          shard.insulin.map(i => `<tr>
            <td>${i.tier ?? "std"}</td>
            <td>${Fmt.esc(meta.days_supply_labels[i.days] || i.days)}</td>
            ${[0, 1, 2, 3].map(k => `<td>${
              i.copay[k] != null ? Fmt.money(i.copay[k])
              : i.coin[k] != null ? Math.round(i.coin[k] * 100) + "%"
              : "n/a"}</td>`).join("")}</tr>`).join("") +
          "</tbody></table></div>";

        const ex = Data.table(shard.excluded);
        const exTable = ex.length ? `<div class="panel">
            <h3>Excluded drugs (${ex.length})</h3>
            <table><thead><tr><th>Drug</th><th>Tier</th><th>PA</th><th>ST</th>
              <th>QL</th><th>Capped</th></tr></thead><tbody>` +
          ex.map(r => `<tr>
            <td><a href="#" data-rxcui="${Fmt.esc(r.rxcui)}">
              ${Fmt.esc(r.name || r.rxcui)}</a></td>
            <td>${r.tier ?? ""}</td><td>${Fmt.flag(r.pa)}</td>
            <td>${Fmt.flag(r.st)}</td>
            <td>${r.ql ? `${Fmt.esc(r.ql_amount || "?")} / ${Fmt.esc(r.ql_days || "?")}d` : "No"}</td>
            <td>${Fmt.flag(r.capped)}</td></tr>`).join("") +
          "</tbody></table></div>"
          : "<div class='panel'><h3>Excluded drugs</h3><p class='muted'>None reported.</p></div>";

        const indList = shard.indications.length ? `<div class="panel">
            <h3>Indication-based coverage</h3><ul>` +
          shard.indications.map(i =>
            `<li>${Fmt.esc(i.name || i.rxcui)}: ${Fmt.esc(i.disease)}</li>`).join("") +
          "</ul></div>" : "";

        el.innerHTML = `
          <h2>${Fmt.esc(p.plan_name)}
            ${suppressed ? '<span class="badge warn">suppressed</span>' : ""}</h2>
          <div class="cards">
            <div class="card"><div class="v">${Fmt.esc(p.plan_key)}</div>
              <div class="l">${Fmt.esc(meta.plan_type_labels[p.type] || p.type)},
              ${Fmt.esc(meta.snp_labels[p.snp] || p.snp)}</div></div>
            <div class="card"><div class="v">${Fmt.money(p.premium)}</div>
              <div class="l">Monthly premium</div></div>
            <div class="card"><div class="v">${Fmt.money(p.deductible)}</div>
              <div class="l">Annual deductible</div></div>
            <div class="card"><div class="v">${Fmt.num(p.n_drugs)}</div>
              <div class="l">Formulary drugs (PA ${Fmt.pct(p.pa_pct)},
              QL ${Fmt.pct(p.ql_pct)})</div></div>
          </div>
          <div class="panel"><h3>Tier cost sharing</h3>${costTables}</div>
          ${insTable}${exTable}${indList}
          <div class="panel"><h3>Formulary browser</h3>
            <div class="controls">
              <input type="text" id="fSearch" placeholder="Search this formulary">
              <span class="muted" id="fCount"></span></div>
            <div id="fTable"><p class="muted">Loading formulary…</p></div></div>`;
        el.scrollIntoView({behavior: "smooth"});
        el.querySelectorAll("a[data-rxcui]").forEach(a =>
          a.addEventListener("click", e => {
            e.preventDefault();
            MPDP.show("drugs", a.dataset.rxcui);
          }));

        const fid = p.formulary_idx >= 0
          ? meta.formulary_order[p.formulary_idx] : null;
        if (!fid) {
          el.querySelector("#fTable").innerHTML =
            "<p class='muted'>This plan's formulary is not present in the basic drugs file.</p>";
          return;
        }
        const form = await Data.formulary(fid);
        const fRows = Data.table(form);
        function drawForm() {
          const q = el.querySelector("#fSearch").value.trim().toLowerCase();
          const rows = q
            ? fRows.filter(r => r.name.toLowerCase().includes(q)
                                || r.rxcui.startsWith(q))
            : fRows;
          el.querySelector("#fCount").textContent =
            `${Fmt.num(rows.length)} drugs on formulary ${fid}` +
            (rows.length > 100 ? ", showing first 100" : "");
          el.querySelector("#fTable").innerHTML = `<table><thead><tr>
            <th>Drug</th><th>Type</th><th>Tier</th><th>PA</th><th>ST</th>
            <th>QL</th></tr></thead><tbody>` +
            rows.slice(0, 100).map(r => `<tr>
              <td><a href="#" data-rxcui="${Fmt.esc(r.rxcui)}">${Fmt.esc(r.name)}</a></td>
              <td>${r.bg || ""}</td><td>${r.tier ?? ""}</td>
              <td>${Fmt.flag(r.pa)}</td><td>${Fmt.flag(r.st)}</td>
              <td>${r.ql ? `${Fmt.esc(r.ql_amount || "?")} / ${Fmt.esc(r.ql_days || "?")}d` : "No"}</td>
              </tr>`).join("") + "</tbody></table>";
          el.querySelectorAll("#fTable a[data-rxcui]").forEach(a =>
            a.addEventListener("click", e => {
              e.preventDefault();
              MPDP.show("drugs", a.dataset.rxcui);
            }));
        }
        el.querySelector("#fSearch").addEventListener("input", drawForm);
        drawForm();
      }

      if (planKey) showDetail(planKey);
    },
  };
})();
```

- [ ] **Step 2: Verify in the browser**

Reload, open Plan explorer. Verify: the four filters narrow the table (state filter includes territories for PDP regional rows); clicking a plan renders facts, cost tables grouped by coverage phase with copay dollars and coinsurance percentages formatted differently, the insulin panel, the excluded-drugs table (find a plan with `Excluded > 0`), and the lazy-loaded formulary browser with working search; excluded-drug and formulary drug names link through to the drug explorer; a suppressed plan shows the suppression notice instead of cost tables; no console errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/js/views/plans.js
git commit -m "feat: implement plan explorer with costs and formulary browser"
```

---

### Task 16: Compare view

**Files:**
- Modify: `dashboard/js/views/compare.js` (replace the stub entirely)

- [ ] **Step 1: Write `dashboard/js/views/compare.js`**

```js
window.MPDP = window.MPDP || {views: {}};
(() => {
  const picked = [];
  MPDP.views.compare = {
    async render(root) {
      const [meta, plans] = await Promise.all([Data.meta(), Data.plansIndex()]);
      root.innerHTML = `<h2>Compare plans</h2>
        <div class="panel"><div class="controls">
          <input type="text" id="cSearch" placeholder="Search plans to add (2 to 4)">
          <span id="cChips"></span></div>
          <div id="cMatches"></div></div>
        <div id="cTable"></div>`;
      const searchEl = root.querySelector("#cSearch");
      const matches = root.querySelector("#cMatches");

      function drawChips() {
        root.querySelector("#cChips").innerHTML = picked.map((p, i) =>
          `<span class="badge">${Fmt.esc(p.plan_name)}
           <a href="#" data-i="${i}">remove</a></span>`).join(" ");
        root.querySelectorAll("#cChips a").forEach(a =>
          a.addEventListener("click", e => {
            e.preventDefault();
            picked.splice(Number(a.dataset.i), 1);
            drawChips(); drawTable();
          }));
      }

      searchEl.addEventListener("input", () => {
        const q = searchEl.value.trim().toLowerCase();
        if (q.length < 2) { matches.innerHTML = ""; return; }
        const rows = plans.filter(p =>
          (p.plan_name || "").toLowerCase().includes(q) &&
          !picked.some(x => x.plan_key === p.plan_key)).slice(0, 10);
        matches.innerHTML = rows.map(p =>
          `<div class="click" data-key="${Fmt.esc(p.plan_key)}">
           ${Fmt.esc(p.plan_name)} <span class="muted">${p.plan_key}</span></div>`
        ).join("");
        matches.querySelectorAll("[data-key]").forEach(div =>
          div.addEventListener("click", () => {
            if (picked.length >= 4) return;
            picked.push(plans.find(p => p.plan_key === div.dataset.key));
            searchEl.value = "";
            matches.innerHTML = "";
            drawChips(); drawTable();
          }));
      });

      async function drawTable() {
        const el = root.querySelector("#cTable");
        if (picked.length < 2) {
          el.innerHTML = "<p class='muted'>Pick at least two plans to compare.</p>";
          return;
        }
        const shards = await Promise.all(picked.map(p => Data.plan(p.plan_key)));
        const metric = (label, fn) => `<tr><th>${label}</th>` +
          picked.map((p, i) => `<td>${fn(p, shards[i])}</td>`).join("") + "</tr>";
        const tierCost = (shard, tier) => {
          const c = shard.costs.find(c =>
            c.level === 1 && c.days === 1 && c.tier === tier);
          return c ? Fmt.cost(c.channels.pref) : "n/a";
        };
        const exSets = shards.map(s => new Set(s.excluded.rows.map(r => r[0])));
        const shared = [...exSets[0]].filter(r => exSets.every(s => s.has(r))).length;
        el.innerHTML = `<div class="panel"><table>
          <thead><tr><th>Metric</th>${picked.map(p =>
            `<th>${Fmt.esc(p.plan_name)}</th>`).join("")}</tr></thead><tbody>` +
          metric("Type", p => meta.plan_type_labels[p.type] || p.type) +
          metric("SNP", p => meta.snp_labels[p.snp] || p.snp) +
          metric("Monthly premium", p => Fmt.money(p.premium)) +
          metric("Annual deductible", p => Fmt.money(p.deductible)) +
          metric("Formulary drugs", p => Fmt.num(p.n_drugs)) +
          metric("Prior authorization share", p => Fmt.pct(p.pa_pct)) +
          metric("Step therapy share", p => Fmt.pct(p.st_pct)) +
          metric("Quantity limit share", p => Fmt.pct(p.ql_pct)) +
          metric("Excluded drugs", p => Fmt.num(p.n_excluded)) +
          [1, 2, 3, 4, 5].map(t => metric(
            `Tier ${t}, 30-day preferred retail (initial coverage)`,
            (p, s) => tierCost(s, t))).join("") +
          `<tr><th>Excluded drugs shared by all selected</th>
           <td colspan="${picked.length}">${shared}</td></tr>` +
          "</tbody></table></div>";
      }

      drawChips(); drawTable();
    },
  };
})();
```

- [ ] **Step 2: Verify in the browser**

Reload, open Compare. Add two PDPs and one MA plan. Verify: chips add and remove; the table fills with per-plan columns; tier cost rows show copays or coinsurance; the shared-exclusions row shows a number; selecting four plans blocks a fifth; no console errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/js/views/compare.js
git commit -m "feat: implement plan compare view"
```

---

### Task 17: End-to-end QA and README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Full clean verification run**

```bash
uv run pytest -q
uv run python -m mpdp_formulary.cli all
```

Expected: all tests pass; the pipeline completes from cache in well under a minute with the same QA lines as Task 11.

- [ ] **Step 2: Spot-check one drug end to end**

Pick the first drug on the Overview negotiation panel; note its RXCUI and the dashboard's "Formularies listing" count, then verify against the raw data:

```bash
uv run python -c "import duckdb; rx = '<RXCUI>'; con = duckdb.connect(); print(con.execute(\"SELECT count(DISTINCT FORMULARY_ID) FROM read_parquet('data/out/raw_basic.parquet') WHERE RXCUI = ?\", [rx]).fetchone())"
```

The count must equal the dashboard number. Repeat the idea for one plan: open any plan's detail, pick its tier 1 initial-coverage 30-day preferred retail cell, and confirm it matches the raw row:

```bash
uv run python -c "import duckdb; con = duckdb.connect(); print(con.execute(\"SELECT TIER, DAYS_SUPPLY, COST_TYPE_PREF, COST_AMT_PREF FROM read_parquet('data/out/raw_bene_cost.parquet') WHERE CONTRACT_ID = ? AND PLAN_ID = ? AND SEGMENT_ID = ? AND COVERAGE_LEVEL = '1' AND TIER = '1' AND DAYS_SUPPLY = '1'\", ['<CONTRACT>', '<PLAN>', '<SEGMENT>']).df())"
```

If either check disagrees, stop and use the systematic-debugging skill before proceeding.

- [ ] **Step 3: Verify all five views once more in the browser**

With the server running, walk Overview, Drug explorer (search, detail, map, metric toggle), Plan explorer (filters, detail, formulary search), Compare (3 plans), Methods. Console must be free of errors.

- [ ] **Step 4: Write `README.md`**

Use this structure, replacing each angle-bracket token with the actual values observed in Steps 1-3 (numbers come from the pipeline's printed QA lines):

```markdown
# MPDP Formulary Dashboard

Pipeline and static dashboard over the CMS Monthly Prescription Drug Plan
Formulary and Pharmacy Network Information PUF (snapshot 2026-05-31, contract
year 2026). Covers drug coverage by plan, excluded drugs, restrictions
(prior authorization, step therapy, quantity limits), tier cost sharing, and a
county coverage map. Pharmacy network files are out of scope in this version.

Design spec: ../docs/superpowers/specs/2026-06-11-mpdp-formulary-dashboard-design.md
Implementation plan: ../docs/superpowers/plans/2026-06-11-mpdp-formulary-dashboard.md

## How to run

    uv sync
    uv run pytest -q
    uv run python -m mpdp_formulary.cli all     # or: ingest|transform|aggregate|export
    uv run python -m http.server 8765 --directory dashboard
    # open http://localhost:8765

Source text files are expected in extracted/ (unzipped from the CMS release).
First ingest downloads the RxNorm Prescribable Content release and the Census
county file into data/cache/; reruns are offline and fast.

## Data sources

| Source | Vintage | Access |
|---|---|---|
| CMS MPDP Formulary PUF | 2026-05-31 | manual download, extracted/ |
| RxNorm Current Prescribable Content | current at first run | cached download |
| Census national_county2020.txt | 2020 | cached download |
| Plotly counties GeoJSON | vendored | dashboard/vendor/ |

## QA results (<date of run>)

- Ingest row counts: plan_info 112,294; basic 1,123,842; excluded 13,717;
  bene_cost 172,660; insulin 43,066; indication 367; geo 3,279.
- RxNorm name match rate: <rate> across <n> distinct RXCUIs.
- SSA-to-FIPS crosswalk match rate: <rate> (<n> counties unmapped).
- Formularies: 328; orphan formulary ID in plan info: <id>.
- Plans exported: <n>; drug shards: <n>; export total: <size> MB.
- Spot check: RXCUI <rxcui> formulary count matches raw (<n>); plan
  <plan_key> tier 1 cost cell matches raw bene_cost row.

## Known limitations

- Single monthly snapshot; no trends.
- RXCUI-grain aggregation: a restriction is shown if any NDC of the drug
  carries it; tier is the modal tier across NDCs.
- Exclusions are contract-plan grain (no segment in the source file).
- County map: SSA-to-FIPS by name matching; unmapped counties render as
  no-data. R and S contracts are expanded from CMS regions, so county
  precision differs by plan type.
- Pharmacy networks (~22.5 GB) deferred; phase-2 candidates: preferred
  pharmacy density, dispensing fees, RxClass therapeutic class rollups.
```

- [ ] **Step 5: Final commit**

```bash
git add README.md
git commit -m "docs: add README with run instructions and QA results"
```

Then use the superpowers:verification-before-completion skill checklist and report results to the user.




