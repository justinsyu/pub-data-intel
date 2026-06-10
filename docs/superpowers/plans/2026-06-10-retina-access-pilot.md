# Retina Access and Evidence Action Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 10-geography wet AMD "retina access and evidence action" pilot: a Python + DuckDB pipeline over raw public data that screens all US geographies, deep-dives 10 selected ones across 7 scoring dimensions, generates rule-based role actions, and ships a static ECharts dashboard.

**Architecture:** API-filtered staged pipeline (spec Approach A). Stage 1 screens nationally using small files and filtered API pulls; Stage 2 deep-dives only the 10 selected geographies. Every HTTP response is disk-cached. A static dashboard reads compact JSON exports; no backend.

**Tech Stack:** Python 3.11+ (uv-managed), pandas, DuckDB, requests, PyYAML, openpyxl, pytest; vanilla JS + vendored ECharts for the dashboard.

**Spec:** `docs/superpowers/specs/2026-06-10-retina-access-pilot-design.md`

---

## Conventions used by every task

- Working directory for all commands: `retina/pilot/` (created in Task 1). All `git` commands run from the repo root `C:\Users\Justin\Desktop\pub-data-intel`.
- Run tests with `uv run pytest <path> -v`.
- **Probe-and-pin pattern:** CMS API column names below are best-known values and must be verified at execution time. Each ingest task includes a probe step (fetch 1 row, print columns). If a real column name differs from the constant in the code, update the constant, not the logic. Never guess silently.
- All network access goes through `http_cache.cached_get`/`cached_json` so re-runs are offline-reproducible.
- Source URLs may drift. They live only in `src/retina_pilot/sources.py`. If a URL 404s at execution time, find the current URL on the agency page listed in the comment beside it and update `sources.py` only.

---

### Task 1: Project scaffold

**Files:**
- Create: `retina/pilot/pyproject.toml`
- Create: `retina/pilot/.gitignore`
- Create: `retina/pilot/src/retina_pilot/__init__.py`
- Create: `retina/pilot/tests/__init__.py`

- [ ] **Step 1: Create the project skeleton**

`retina/pilot/pyproject.toml`:

```toml
[project]
name = "retina-pilot"
version = "0.1.0"
description = "10-geography retina access and evidence action pilot (wet AMD)"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.2",
    "duckdb>=1.0",
    "requests>=2.32",
    "pyyaml>=6.0",
    "openpyxl>=3.1",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/retina_pilot"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`retina/pilot/.gitignore`:

```
data/cache/
data/out/
__pycache__/
.venv/
*.duckdb
```

`src/retina_pilot/__init__.py` and `tests/__init__.py`: empty files.

- [ ] **Step 2: Verify the environment resolves**

Run (in `retina/pilot/`): `uv sync`
Expected: dependencies install without error.

Run: `uv run pytest`
Expected: `no tests ran` (exit code 5 is fine at this point).

- [ ] **Step 3: Commit**

```bash
git add retina/pilot/pyproject.toml retina/pilot/.gitignore retina/pilot/src retina/pilot/tests retina/pilot/uv.lock
git commit -m "chore: scaffold retina pilot project"
```

---

### Task 2: Verified code sets and MAC jurisdiction map (`codes.py`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/codes.py`
- Test: `retina/pilot/tests/test_codes.py`

- [ ] **Step 1: Write the failing test**

`tests/test_codes.py`:

```python
from retina_pilot import codes


def test_drug_codes_cover_verified_products():
    assert {"J0178", "J0177", "J2778", "J2777", "J0179"} <= set(codes.ANTIVEGF_ORIGINATOR_HCPCS)
    assert {"Q5124", "Q5128", "Q5147"} <= set(codes.ANTIVEGF_BIOSIMILAR_HCPCS)
    assert {"J2781", "J2782"} <= set(codes.GA_COMPLEMENT_HCPCS)


def test_all_drug_codes_have_labels():
    for code in codes.ALL_DRUG_HCPCS:
        assert code in codes.DRUG_LABELS


def test_procedure_codes():
    assert "67028" in codes.PROCEDURE_HCPCS
    assert "92134" in codes.PROCEDURE_HCPCS


def test_taxonomy_codes():
    assert codes.TAXONOMY_OPHTHALMOLOGY == "207W00000X"
    assert codes.TAXONOMY_RETINA_SPECIALIST == "207WX0107X"


def test_mac_map_covers_50_states_plus_dc():
    states = {s for sts in codes.MAC_JURISDICTIONS.values() for s in sts}
    assert len(states & set(codes.ALL_STATES)) == 51


def test_state_to_mac_lookup():
    assert codes.state_to_mac("CA") == "JE"
    assert codes.state_to_mac("FL") == "JN"
    assert codes.state_to_mac("NY") == "JK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_codes.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/codes.py`:

```python
"""Verified retina code sets. Single source of truth (spec section: Verified code sets)."""

# ICD-10-CM families (prefix match against dotted codes)
ICD10_WET_AMD_PREFIX = "H35.32"
ICD10_DRY_AMD_PREFIX = "H35.31"
ICD10_CRVO_PREFIX = "H34.81"
ICD10_RETINA_PREFIXES = [ICD10_WET_AMD_PREFIX, ICD10_DRY_AMD_PREFIX, "H34.8", "E08.3", "E09.3", "E10.3", "E11.3", "E13.3"]

# Procedures (codes only; neutral labels, no licensed AMA descriptors)
PROCEDURE_HCPCS = {
    "67028": "intravitreal injection",
    "92134": "OCT retina imaging",
    "92133": "OCT optic nerve imaging",
    "92235": "fluorescein angiography",
    "92250": "fundus photography",
}

ANTIVEGF_ORIGINATOR_HCPCS = ["J0178", "J0177", "J2778", "J2777", "J0179"]
ANTIVEGF_BIOSIMILAR_HCPCS = ["Q5124", "Q5128", "Q5147"]
GA_COMPLEMENT_HCPCS = ["J2781", "J2782"]
ALL_DRUG_HCPCS = ANTIVEGF_ORIGINATOR_HCPCS + ANTIVEGF_BIOSIMILAR_HCPCS + GA_COMPLEMENT_HCPCS

DRUG_LABELS = {
    "J0178": "aflibercept (Eylea)",
    "J0177": "aflibercept HD (Eylea HD)",
    "J2778": "ranibizumab (Lucentis)",
    "J2777": "faricimab-svoa (Vabysmo)",
    "J0179": "brolucizumab-dbll (Beovu)",
    "Q5124": "ranibizumab-nuna (Byooviz)",
    "Q5128": "ranibizumab-eqrn (Cimerli)",
    "Q5147": "aflibercept-ayyh (Pavblu)",
    "J2781": "pegcetacoplan (Syfovre)",
    "J2782": "avacincaptad pegol (Izervay)",
}

TAXONOMY_OPHTHALMOLOGY = "207W00000X"
TAXONOMY_RETINA_SPECIALIST = "207WX0107X"

POLICY_ANCHOR_ARTICLE = "A52451"  # CMS billing-and-coding article family for anti-VEGF

ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

# Medicare A/B MAC jurisdictions (states and DC only)
MAC_JURISDICTIONS = {
    "JE": ["CA", "HI", "NV"],
    "JF": ["AK", "AZ", "ID", "MT", "ND", "OR", "SD", "UT", "WA", "WY"],
    "J5": ["IA", "KS", "MO", "NE"],
    "J6": ["IL", "MN", "WI"],
    "J8": ["IN", "MI"],
    "J15": ["KY", "OH"],
    "JH": ["AR", "CO", "LA", "MS", "NM", "OK", "TX"],
    "JL": ["DE", "DC", "MD", "NJ", "PA"],
    "JJ": ["AL", "GA", "TN"],
    "JM": ["NC", "SC", "VA", "WV"],
    "JN": ["FL"],
    "JK": ["CT", "ME", "MA", "NH", "NY", "RI", "VT"],
}

_STATE_TO_MAC = {s: j for j, sts in MAC_JURISDICTIONS.items() for s in sts}


def state_to_mac(state: str) -> str:
    return _STATE_TO_MAC[state.upper()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_codes.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/codes.py retina/pilot/tests/test_codes.py
git commit -m "feat: add verified retina code sets and MAC jurisdiction map"
```

---

### Task 3: Disk-cached HTTP layer (`ingest/http_cache.py`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/__init__.py` (empty)
- Create: `retina/pilot/src/retina_pilot/ingest/http_cache.py`
- Test: `retina/pilot/tests/test_http_cache.py`

- [ ] **Step 1: Write the failing test**

`tests/test_http_cache.py`:

```python
import retina_pilot.ingest.http_cache as hc


class FakeResponse:
    def __init__(self, content):
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        pass


def test_cached_get_hits_network_once(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        return FakeResponse(b'{"ok": 1}')

    monkeypatch.setattr(hc.requests, "get", fake_get)
    monkeypatch.setattr(hc, "CACHE_DIR", tmp_path)

    first = hc.cached_get("https://example.gov/x", params={"a": "1"})
    second = hc.cached_get("https://example.gov/x", params={"a": "1"})
    assert first == second == b'{"ok": 1}'
    assert len(calls) == 1  # second call served from disk


def test_different_params_different_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        hc.requests, "get",
        lambda url, params=None, headers=None, timeout=None: FakeResponse(
            str(params).encode()
        ),
    )
    assert hc.cached_get("https://e.gov/x", {"a": "1"}) != hc.cached_get("https://e.gov/x", {"a": "2"})


def test_cached_json(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        hc.requests, "get",
        lambda url, params=None, headers=None, timeout=None: FakeResponse(b'[{"k": "v"}]'),
    )
    assert hc.cached_json("https://e.gov/j") == [{"k": "v"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_http_cache.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/ingest/http_cache.py`:

```python
"""Disk-cached HTTP. Every network call in the pipeline goes through this module."""
import hashlib
import json
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
TIMEOUT = 120
HEADERS = {"User-Agent": "retina-pilot/0.1 (public data research)"}


def _key(url: str, params: dict | None) -> str:
    canonical = url + "|" + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def cached_get(url: str, params: dict | None = None) -> bytes:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / _key(url, params)
    if path.exists():
        return path.read_bytes()
    resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return resp.content


def cached_json(url: str, params: dict | None = None):
    return json.loads(cached_get(url, params))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_http_cache.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest retina/pilot/tests/test_http_cache.py
git commit -m "feat: add disk-cached HTTP layer"
```

---

### Task 4: Source URL registry and reachability script

**Files:**
- Create: `retina/pilot/src/retina_pilot/sources.py`
- Create: `retina/pilot/scripts/verify_sources.py`
- Test: `retina/pilot/tests/test_sources.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sources.py`:

```python
from retina_pilot import sources


def test_all_sources_are_https():
    for name, url in sources.URLS.items():
        assert url.startswith("https://"), name


def test_expected_sources_present():
    expected = {
        "census_gazetteer_counties", "nber_cbsa_xwalk", "census_acs5",
        "census_zcta_county_rel", "cdc_svi_county", "usda_rucc",
        "cms_data_json", "pdc_metastore", "clinicaltrials_v2",
        "openpayments_metastore", "hrsa_340b_ce",
    }
    assert expected <= set(sources.URLS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sources.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/sources.py`:

```python
"""All external URLs live here and only here.

If a URL 404s, locate the current one on the agency page in the comment
and update it here. Do not embed URLs anywhere else in the codebase.
"""

URLS = {
    # Census gazetteer (counties): https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
    "census_gazetteer_counties": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteers/2024_Gaz_counties_national.zip",
    # NBER CBSA-county crosswalk: https://www.nber.org/research/data/census-core-based-statistical-area-cbsa-federal-information-processing-series-fips-county-crosswalk
    "nber_cbsa_xwalk": "https://data.nber.org/cbsa-csa-fips-county-crosswalk/cbsa2fipsxw.csv",
    # Census ACS 5-year API: https://www.census.gov/data/developers/data-sets/acs-5year.html
    "census_acs5": "https://api.census.gov/data/2023/acs/acs5",
    # Census ZCTA-county relationship: https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html
    "census_zcta_county_rel": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
    # CDC/ATSDR SVI: https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html
    "cdc_svi_county": "https://svi.cdc.gov/Documents/Data/2022/csv/states_counties/SVI2022_US_county.csv",
    # USDA ERS RUCC: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/
    "usda_rucc": "https://ers.usda.gov/sites/default/files/_laserfiche/DataFiles/53251/Ruralurbancontinuumcodes2023.csv",
    # CMS open data catalog: https://data.cms.gov/api-docs
    "cms_data_json": "https://data.cms.gov/data.json",
    # CMS Provider Data Catalog metastore: https://data.cms.gov/provider-data/docs
    "pdc_metastore": "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items",
    "pdc_datastore_query": "https://data.cms.gov/provider-data/api/1/datastore/query",
    # ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/api
    "clinicaltrials_v2": "https://clinicaltrials.gov/api/v2/studies",
    # Open Payments DKAN API: https://openpaymentsdata.cms.gov/about/api
    "openpayments_metastore": "https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items",
    "openpayments_datastore_query": "https://openpaymentsdata.cms.gov/api/1/datastore/query",
    # HRSA 340B OPAIS daily covered-entity export: https://340bopais.hrsa.gov/reports
    "hrsa_340b_ce": "https://340bopais.hrsa.gov/dailyreports/OPA_CE_DAILY_REPORT.csv",
}

# Datasets resolved by title from the CMS data.json catalog (titles, not UUIDs,
# because UUIDs change with versions).
CMS_DATASET_TITLES = {
    "mupphy": "Medicare Physician & Other Practitioners - by Provider and Service",
    "monthly_enrollment": "Medicare Monthly Enrollment",
    "qdd": "Medicare Part B Spending by Drug",
}

PDC_DATASET_TITLES = {
    "dac_ndf": "National Downloadable File",
    "dac_fa": "Facility Affiliation Data",
}

# Manual-download fallback (license click-through): Medicare Coverage Database
# https://www.cms.gov/medicare-coverage-database/downloads/downloadable-databases.aspx
# Download current LCD and Article zips into retina/pilot/data/cache/mcd/ by hand
# if scripted retrieval is blocked.
MCD_LOCAL_DIR = "data/cache/mcd"
```

`scripts/verify_sources.py`:

```python
"""HEAD/GET-probe every registered source URL and print status. Run before first pipeline run."""
import requests

from retina_pilot import sources

for name, url in sources.URLS.items():
    try:
        r = requests.head(url, timeout=30, allow_redirects=True,
                          headers={"User-Agent": "retina-pilot/0.1"})
        if r.status_code >= 400:  # some servers reject HEAD; retry small GET
            r = requests.get(url, timeout=30, stream=True,
                             headers={"User-Agent": "retina-pilot/0.1"})
        print(f"{r.status_code}  {name}  {url}")
    except Exception as exc:
        print(f"ERR  {name}  {url}  {exc}")
```

- [ ] **Step 4: Run test, then probe the real URLs**

Run: `uv run pytest tests/test_sources.py -v`
Expected: 2 passed.

Run: `uv run python scripts/verify_sources.py`
Expected: mostly `200`. For any 4xx/ERR line, find the current URL via the agency page in the `sources.py` comment and update `sources.py`. Re-run until each source resolves or is documented as manual-download (MCD, possibly 340B).

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/sources.py retina/pilot/scripts/verify_sources.py retina/pilot/tests/test_sources.py
git commit -m "feat: add source URL registry and reachability probe"
```

---

### Task 5: CMS API clients (`ingest/cms_api.py`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/cms_api.py`
- Test: `retina/pilot/tests/test_cms_api.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cms_api.py`:

```python
import retina_pilot.ingest.cms_api as api


def test_resolve_data_cms_dataset(monkeypatch):
    catalog = {
        "dataset": [
            {
                "title": "Medicare Physician & Other Practitioners - by Provider and Service",
                "distribution": [
                    {"format": "API", "accessURL": "https://data.cms.gov/data-api/v1/dataset/abc-123/data"},
                    {"format": "csv", "downloadURL": "https://x/file.csv"},
                ],
            }
        ]
    }
    monkeypatch.setattr(api, "cached_json", lambda url, params=None: catalog)
    url = api.resolve_data_cms_dataset("Medicare Physician & Other Practitioners - by Provider and Service")
    assert url == "https://data.cms.gov/data-api/v1/dataset/abc-123/data"


def test_fetch_all_paginates(monkeypatch):
    pages = {0: [{"a": 1}] * 3, 3: [{"a": 2}], 4: []}

    def fake_json(url, params=None):
        return pages[params["offset"]]

    monkeypatch.setattr(api, "cached_json", fake_json)
    rows = api.fetch_all("https://x/data", filters={"HCPCS_Cd": "67028"}, page_size=3)
    assert len(rows) == 4


def test_pdc_conditions_built_correctly():
    params = api._pdc_params([("pri_spec", "=", "OPHTHALMOLOGY")], limit=10, offset=0)
    assert params["conditions[0][property]"] == "pri_spec"
    assert params["conditions[0][value]"] == "OPHTHALMOLOGY"
    assert params["conditions[0][operator]"] == "="
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cms_api.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/ingest/cms_api.py`:

```python
"""Clients for data.cms.gov (data-api), Provider Data Catalog (DKAN), and Open Payments (DKAN)."""
from retina_pilot import sources
from retina_pilot.ingest.http_cache import cached_json


def resolve_data_cms_dataset(title: str) -> str:
    """Resolve a dataset title to its current data-api URL via the data.json catalog."""
    catalog = cached_json(sources.URLS["cms_data_json"])
    for ds in catalog["dataset"]:
        if ds.get("title", "").strip().lower() == title.strip().lower():
            for dist in ds.get("distribution", []):
                if dist.get("format") == "API" and "accessURL" in dist:
                    return dist["accessURL"]
    raise LookupError(f"dataset not found in data.json: {title}")


def fetch_all(api_url: str, filters: dict | None = None, page_size: int = 5000) -> list[dict]:
    """Fetch every row matching simple equality filters, paginating by offset."""
    params_base = {f"filter[{k}]": v for k, v in (filters or {}).items()}
    rows, offset = [], 0
    while True:
        params = dict(params_base, size=page_size, offset=offset)
        page = cached_json(api_url, params)
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += len(page)


def _pdc_params(conditions: list[tuple], limit: int, offset: int) -> dict:
    params = {"limit": limit, "offset": offset}
    for i, (prop, op, value) in enumerate(conditions):
        params[f"conditions[{i}][property]"] = prop
        params[f"conditions[{i}][operator]"] = op
        params[f"conditions[{i}][value]"] = value
    return params


def _dkan_query(base_url: str, dataset_id: str, conditions: list[tuple], limit: int = 2000) -> list[dict]:
    rows, offset = [], 0
    while True:
        params = _pdc_params(conditions, limit, offset)
        payload = cached_json(f"{base_url}/{dataset_id}/0", params)
        page = payload.get("results", [])
        rows.extend(page)
        if len(page) < limit:
            return rows
        offset += len(page)


def pdc_resolve(title: str) -> str:
    items = cached_json(sources.URLS["pdc_metastore"])
    for item in items:
        if title.strip().lower() in item.get("title", "").strip().lower():
            return item["identifier"]
    raise LookupError(f"PDC dataset not found: {title}")


def pdc_query(dataset_id: str, conditions: list[tuple], limit: int = 2000) -> list[dict]:
    return _dkan_query(sources.URLS["pdc_datastore_query"], dataset_id, conditions, limit)


def openpayments_resolve(title_substring: str) -> str:
    items = cached_json(sources.URLS["openpayments_metastore"])
    for item in items:
        if title_substring.strip().lower() in item.get("title", "").strip().lower():
            return item["identifier"]
    raise LookupError(f"Open Payments dataset not found: {title_substring}")


def openpayments_query(dataset_id: str, conditions: list[tuple], limit: int = 2000) -> list[dict]:
    return _dkan_query(sources.URLS["openpayments_datastore_query"], dataset_id, conditions, limit)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cms_api.py -v`
Expected: 3 passed.

- [ ] **Step 5: Live probe (no test code; verifies real API shape)**

Run: `uv run python -c "from retina_pilot.ingest import cms_api; u = cms_api.resolve_data_cms_dataset('Medicare Physician & Other Practitioners - by Provider and Service'); import json; print(u); print(json.dumps(cms_api.cached_json(u, {'size': 1, 'offset': 0})[0], indent=2))"`
Expected: one MUPPHY row printed. Note the exact column names (`Rndrng_NPI`, `HCPCS_Cd`, `Tot_Srvcs`, `Tot_Benes`, `Rndrng_Prvdr_State_Abrvtn`, `Rndrng_Prvdr_Zip5`, or as actually returned). Pin any differing names into the constants used in Task 11.

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/cms_api.py retina/pilot/tests/test_cms_api.py
git commit -m "feat: add CMS data-api and DKAN clients"
```

---

### Task 6: Census ingests (gazetteer, CBSA crosswalk, ACS 65+, ZCTA-county)

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/census.py`
- Test: `retina/pilot/tests/test_census.py`
- Create: `retina/pilot/tests/fixtures/gaz_counties_sample.txt`
- Create: `retina/pilot/tests/fixtures/cbsa_xwalk_sample.csv`

- [ ] **Step 1: Create fixtures**

`tests/fixtures/gaz_counties_sample.txt` (tab-separated; mirror real gazetteer header):

```
USPS	GEOID	ANSICODE	NAME	ALAND	AWATER	ALAND_SQMI	AWATER_SQMI	INTPTLAT	INTPTLONG
AL	01001	00161526	Autauga County	1539602123	25706961	594.44	9.93	32.532237	-86.646440
CA	06037	00277283	Los Angeles County	10515988166	1785003207	4060.87	689.19	34.196398	-118.261862
```

`tests/fixtures/cbsa_xwalk_sample.csv`:

```
cbsacode,metrodivisioncode,csacode,cbsatitle,metropolitanmicropolitanstatis,metropolitandivisiontitle,csatitle,countycountyequivalent,statename,fipsstatecode,fipscountycode,centraloutlyingcounty
31080,31084,348,"Los Angeles-Long Beach-Anaheim, CA",Metropolitan Statistical Area,"Los Angeles-Long Beach-Glendale, CA","Los Angeles-Long Beach, CA",Los Angeles County,California,06,037,Central
33860,,,"Montgomery, AL",Metropolitan Statistical Area,,,Autauga County,Alabama,01,001,Outlying
```

- [ ] **Step 2: Write the failing test**

`tests/test_census.py`:

```python
from pathlib import Path

import retina_pilot.ingest.census as census

FIX = Path(__file__).parent / "fixtures"


def test_parse_gazetteer():
    df = census.parse_gazetteer((FIX / "gaz_counties_sample.txt").read_bytes())
    assert list(df.columns) == ["fips", "state", "county_name", "lat", "lon"]
    assert df.loc[df.fips == "06037", "county_name"].iloc[0] == "Los Angeles County"


def test_parse_cbsa_xwalk():
    df = census.parse_cbsa_xwalk((FIX / "cbsa_xwalk_sample.csv").read_bytes())
    assert list(df.columns) == ["fips", "cbsa_code", "cbsa_title", "metro_micro"]
    assert df.loc[df.fips == "06037", "cbsa_code"].iloc[0] == "31080"


def test_parse_acs_pop65():
    payload = [
        ["NAME", "B01001_001E", "B01001_020E", "B01001_021E", "B01001_022E",
         "B01001_023E", "B01001_024E", "B01001_025E", "B01001_044E", "B01001_045E",
         "B01001_046E", "B01001_047E", "B01001_048E", "B01001_049E", "state", "county"],
        ["Autauga County, Alabama", "58761", "1000", "900", "800", "700", "600",
         "500", "1100", "950", "850", "750", "650", "550", "01", "001"],
    ]
    df = census.parse_acs_pop65(payload)
    assert df.iloc[0]["fips"] == "01001"
    assert df.iloc[0]["pop_total"] == 58761
    assert df.iloc[0]["pop65"] == 9350
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_census.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write the implementation**

`src/retina_pilot/ingest/census.py`:

```python
"""Census ingests: county gazetteer, NBER CBSA crosswalk, ACS 65+ population, ZCTA-county."""
import io
import os
import zipfile

import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest.http_cache import cached_get, cached_json

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
        "fips": df["fipsstatecode"].str.zfill(2) + df["fipscountycode"].str.zfill(3),
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
    return parse_acs_pop65(cached_json(sources.URLS["census_acs5"], params))


def load_zcta_county() -> pd.DataFrame:
    """ZCTA-to-county mapping; a ZIP maps to the county with the largest overlap."""
    raw = cached_get(sources.URLS["census_zcta_county_rel"])
    df = pd.read_csv(io.BytesIO(raw), sep="|", dtype=str)
    df["AREALAND_PART"] = pd.to_numeric(df["AREALAND_PART"], errors="coerce").fillna(0)
    df = df.dropna(subset=["GEOID_ZCTA5_20", "GEOID_COUNTY_20"])
    df = df.sort_values("AREALAND_PART").groupby("GEOID_ZCTA5_20").tail(1)
    return pd.DataFrame({"zcta": df["GEOID_ZCTA5_20"], "fips": df["GEOID_COUNTY_20"]})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_census.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/census.py retina/pilot/tests/test_census.py retina/pilot/tests/fixtures
git commit -m "feat: add census ingests (gazetteer, CBSA, ACS 65+, ZCTA-county)"
```

---

### Task 7: SVI, RUCC, and Medicare/MA enrollment ingests

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/area_context.py`
- Create: `retina/pilot/src/retina_pilot/ingest/enrollment.py`
- Test: `retina/pilot/tests/test_area_context.py`
- Test: `retina/pilot/tests/test_enrollment.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_area_context.py`:

```python
import retina_pilot.ingest.area_context as ac


def test_parse_svi():
    raw = b"FIPS,LOCATION,RPL_THEMES\n01001,\"Autauga, AL\",0.5432\n06037,\"LA, CA\",0.9211\n"
    df = ac.parse_svi(raw)
    assert list(df.columns) == ["fips", "svi"]
    assert df.loc[df.fips == "06037", "svi"].iloc[0] == 0.9211


def test_parse_svi_ignores_missing_flag():
    raw = b"FIPS,LOCATION,RPL_THEMES\n01001,X,-999\n"
    df = ac.parse_svi(raw)
    assert df.empty


def test_parse_rucc():
    raw = b'FIPS,State,County_Name,Attribute,Value\n01001,AL,Autauga,RUCC_2023,2\n01001,AL,Autauga,Population_2020,58805\n'
    df = ac.parse_rucc(raw)
    assert list(df.columns) == ["fips", "rucc"]
    assert df.iloc[0]["rucc"] == 2
```

`tests/test_enrollment.py`:

```python
import retina_pilot.ingest.enrollment as enr


def test_parse_enrollment_rows():
    rows = [
        {"BENE_FIPS_CD": "01001", "BENE_STATE_ABRVTN": "AL", "BENE_COUNTY_DESC": "Autauga",
         "TOT_BENES": "12000", "ORGNL_MDCR_BENES": "7000", "MA_AND_OTH_BENES": "5000",
         "MONTH": "Year", "YEAR": "2024", "BENE_GEO_LVL": "County"},
        {"BENE_FIPS_CD": "", "BENE_STATE_ABRVTN": "AL", "BENE_COUNTY_DESC": "Unknown",
         "TOT_BENES": "10", "ORGNL_MDCR_BENES": "5", "MA_AND_OTH_BENES": "5",
         "MONTH": "Year", "YEAR": "2024", "BENE_GEO_LVL": "County"},
    ]
    df = enr.parse_enrollment(rows)
    assert len(df) == 1  # blank-FIPS row dropped
    row = df.iloc[0]
    assert row["fips"] == "01001"
    assert row["ma_pct"] == 41.7
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_area_context.py tests/test_enrollment.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementations**

`src/retina_pilot/ingest/area_context.py`:

```python
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
```

`src/retina_pilot/ingest/enrollment.py`:

```python
"""Medicare Monthly Enrollment: county Medicare totals and MA penetration."""
import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest import cms_api

# Probe-and-pin: verify these against a live row (Task 5 step 5 pattern).
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
    return parse_enrollment(cms_api.fetch_all(url, filters=FILTERS))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_area_context.py tests/test_enrollment.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/area_context.py retina/pilot/src/retina_pilot/ingest/enrollment.py retina/pilot/tests/test_area_context.py retina/pilot/tests/test_enrollment.py
git commit -m "feat: add SVI, RUCC, and Medicare enrollment ingests"
```

---

### Task 8: Ophthalmology provider ingest (DAC national file)

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/providers.py`
- Test: `retina/pilot/tests/test_providers.py`

- [ ] **Step 1: Write the failing test**

`tests/test_providers.py`:

```python
import retina_pilot.ingest.providers as prov


def test_parse_dac_rows():
    rows = [
        {"npi": "1234567890", "provider_last_name": "SMITH", "provider_first_name": "ANN",
         "pri_spec": "OPHTHALMOLOGY", "state": "CA", "zip_code": "900011234",
         "facility_name": "RETINA MEDICAL GROUP"},
        {"npi": "1234567890", "provider_last_name": "SMITH", "provider_first_name": "ANN",
         "pri_spec": "OPHTHALMOLOGY", "state": "CA", "zip_code": "900011234",
         "facility_name": "SECOND LOCATION"},  # duplicate NPI collapses
    ]
    df = prov.parse_dac(rows)
    assert len(df) == 1
    assert df.iloc[0]["zip5"] == "90001"
    assert df.iloc[0]["npi"] == "1234567890"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_providers.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/ingest/providers.py`:

```python
"""Ophthalmology providers from the CMS Doctors and Clinicians national file (PDC)."""
import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest import cms_api

# Probe-and-pin: PDC column names are lowercase snake in the datastore API;
# verify with a 1-row query and adjust here only.
COL_NPI = "npi"
COL_SPEC = "pri_spec"
COL_STATE = "state"
COL_ZIP = "zip_code"
SPECIALTY_VALUE = "OPHTHALMOLOGY"


def parse_dac(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["zip5"] = df[COL_ZIP].astype(str).str[:5]
    out = df.rename(columns={COL_NPI: "npi", COL_STATE: "state"})[
        ["npi", "state", "zip5"]
    ].drop_duplicates(subset=["npi"])
    return out.reset_index(drop=True)


def load_ophth_providers() -> pd.DataFrame:
    ds = cms_api.pdc_resolve(sources.PDC_DATASET_TITLES["dac_ndf"])
    rows = cms_api.pdc_query(ds, [(COL_SPEC, "=", SPECIALTY_VALUE)])
    return parse_dac(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_providers.py -v`
Expected: 1 passed.

- [ ] **Step 5: Live probe**

Run: `uv run python -c "from retina_pilot.ingest import cms_api, providers; ds = cms_api.pdc_resolve('National Downloadable File'); rows = cms_api.pdc_query(ds, [('pri_spec', '=', 'OPHTHALMOLOGY')], limit=1); print(rows[0].keys() if rows else 'EMPTY')"`
Expected: a row with keys including `npi`, `pri_spec`, `zip_code` (or actual names). Pin differing names into the module constants.

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/providers.py retina/pilot/tests/test_providers.py
git commit -m "feat: add DAC ophthalmology provider ingest"
```

---

### Task 9: Geography frame and screen table (`transform/`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/transform/__init__.py` (empty)
- Create: `retina/pilot/src/retina_pilot/transform/geo_frame.py`
- Test: `retina/pilot/tests/test_geo_frame.py`

- [ ] **Step 1: Write the failing test**

`tests/test_geo_frame.py`:

```python
import pandas as pd

from retina_pilot.transform import geo_frame


def _counties():
    return pd.DataFrame({
        "fips": ["06037", "01001", "30033"],
        "state": ["CA", "AL", "MT"],
        "county_name": ["Los Angeles County", "Autauga County", "Garfield County"],
    })


def _xwalk():
    return pd.DataFrame({
        "fips": ["06037", "01001"],
        "cbsa_code": ["31080", "33860"],
        "cbsa_title": ["Los Angeles-Long Beach-Anaheim, CA", "Montgomery, AL"],
        "metro_micro": ["Metropolitan Statistical Area", "Metropolitan Statistical Area"],
    })


def test_units_metro_county_rolls_to_cbsa():
    units = geo_frame.assign_units(_counties(), _xwalk())
    la = units[units.fips == "06037"].iloc[0]
    assert la["unit_id"] == "cbsa:31080"
    assert la["unit_type"] == "cbsa"


def test_units_nonmetro_county_stands_alone():
    units = geo_frame.assign_units(_counties(), _xwalk())
    garfield = units[units.fips == "30033"].iloc[0]
    assert garfield["unit_id"] == "county:30033"
    assert garfield["unit_type"] == "county"


def test_aggregate_to_units_weights_by_population():
    units = geo_frame.assign_units(_counties(), _xwalk())
    metrics = pd.DataFrame({
        "fips": ["06037", "01001", "30033"],
        "pop65": [1000, 100, 50],
        "svi": [0.9, 0.5, 0.2],
        "ma_pct": [50.0, 40.0, 10.0],
        "medicare_benes": [2000, 200, 80],
        "retina_providers": [30, 2, 0],
    })
    agg = geo_frame.aggregate_to_units(units, metrics)
    g = agg[agg.unit_id == "county:30033"].iloc[0]
    assert g["pop65"] == 50
    assert g["svi"] == 0.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_geo_frame.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/transform/geo_frame.py`:

```python
"""Mixed geography units: metro counties roll up to CBSAs, non-metro counties stand alone."""
import pandas as pd

from retina_pilot import codes

METRO = "Metropolitan Statistical Area"


def assign_units(counties: pd.DataFrame, xwalk: pd.DataFrame) -> pd.DataFrame:
    df = counties.merge(xwalk, on="fips", how="left")
    is_metro = df["metro_micro"].eq(METRO)
    df["unit_id"] = "county:" + df["fips"]
    df.loc[is_metro, "unit_id"] = "cbsa:" + df.loc[is_metro, "cbsa_code"]
    df["unit_type"] = "county"
    df.loc[is_metro, "unit_type"] = "cbsa"
    df["unit_name"] = df["county_name"] + ", " + df["state"]
    df.loc[is_metro, "unit_name"] = df.loc[is_metro, "cbsa_title"]
    df["mac"] = df["state"].map(lambda s: codes.state_to_mac(s) if s in codes.ALL_STATES else None)
    return df[["fips", "state", "unit_id", "unit_type", "unit_name", "mac"]]


SUM_COLS = ["pop65", "medicare_benes", "retina_providers"]
WEIGHTED_COLS = ["svi", "ma_pct"]  # population-weighted by pop65


def aggregate_to_units(units: pd.DataFrame, county_metrics: pd.DataFrame) -> pd.DataFrame:
    df = units.merge(county_metrics, on="fips", how="inner")
    for c in WEIGHTED_COLS:
        df[f"_w_{c}"] = df[c] * df["pop65"]
    g = df.groupby(["unit_id", "unit_type", "unit_name"], as_index=False).agg(
        {**{c: "sum" for c in SUM_COLS}, **{f"_w_{c}": "sum" for c in WEIGHTED_COLS},
         "mac": lambda s: sorted(set(s.dropna()))[0] if s.notna().any() else None,
         "state": lambda s: ",".join(sorted(set(s)))}
    )
    for c in WEIGHTED_COLS:
        g[c] = (g[f"_w_{c}"] / g["pop65"]).round(4)
        g = g.drop(columns=f"_w_{c}")
    return g
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_geo_frame.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/transform retina/pilot/tests/test_geo_frame.py
git commit -m "feat: add mixed county/CBSA geography frame"
```

---

### Task 10: Screen score and diverse selection (`score/screen.py`, `transform/select.py`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/score/__init__.py` (empty)
- Create: `retina/pilot/src/retina_pilot/score/screen.py`
- Create: `retina/pilot/src/retina_pilot/transform/select.py`
- Test: `retina/pilot/tests/test_screen_select.py`

- [ ] **Step 1: Write the failing test**

`tests/test_screen_select.py`:

```python
import pandas as pd

from retina_pilot.score import screen
from retina_pilot.transform import select


def _pool(n=40):
    rows = []
    for i in range(n):
        rows.append({
            "unit_id": f"cbsa:{10000 + i}" if i % 2 == 0 else f"county:{20000 + i}",
            "unit_type": "cbsa" if i % 2 == 0 else "county",
            "unit_name": f"Unit {i}",
            "state": ["CA", "TX", "FL", "NY", "MT", "AL", "OH", "GA"][i % 8],
            "mac": ["JE", "JH", "JN", "JK", "JF", "JJ", "J15", "JJ"][i % 8],
            "pop65": 10000 + 500 * i,
            "medicare_benes": 8000 + 400 * i,
            "ma_pct": 30 + i,
            "svi": (i % 10) / 10,
            "retina_providers": i % 7,
            "rucc": 8 if i % 2 else 2,
        })
    return pd.DataFrame(rows)


def test_screen_score_range_and_direction():
    scored = screen.score_screen(_pool())
    assert scored["screen_score"].between(0, 100).all()
    # lowest-supply, highest-need unit should outrank highest-supply, lowest-need
    top = scored.sort_values("screen_score", ascending=False).iloc[0]
    assert top["retina_per_10k_65"] <= scored["retina_per_10k_65"].median()


def test_select_pilot_constraints():
    scored = screen.score_screen(_pool())
    picked = select.select_pilot(scored, n=10)
    assert len(picked) == 10
    types = [p["unit_type"] for p in picked]
    assert types.count("cbsa") >= 4
    assert types.count("county") >= 3
    assert len({p["mac"] for p in picked}) >= 4
    assert len({p["unit_id"] for p in picked}) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_screen_select.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementations**

`src/retina_pilot/score/screen.py`:

```python
"""National screen score: need-versus-supply vulnerability (0-100)."""
import pandas as pd


def score_screen(units: pd.DataFrame) -> pd.DataFrame:
    df = units.copy()
    df["retina_per_10k_65"] = (10000 * df["retina_providers"] / df["pop65"]).round(3)
    need_up = ["pop65", "svi", "ma_pct"]      # higher value = higher need
    supply_down = ["retina_per_10k_65"]        # higher value = lower need
    parts = [df[c].rank(pct=True) for c in need_up]
    parts += [1 - df[c].rank(pct=True) for c in supply_down]
    df["screen_score"] = (100 * sum(parts) / len(parts)).round(1)
    return df
```

`src/retina_pilot/transform/select.py`:

```python
"""Greedy diverse selection of the 10 pilot geographies (spec: selection constraints)."""
import pandas as pd

MIN_CBSA = 4
MIN_RURAL = 3
MIN_MACS = 4


def select_pilot(scored: pd.DataFrame, n: int = 10) -> list[dict]:
    pool = scored.sort_values("screen_score", ascending=False).to_dict("records")
    picked: list[dict] = []

    def counts():
        types = [p["unit_type"] for p in picked]
        return types.count("cbsa"), types.count("county"), {p["mac"] for p in picked}

    for row in pool:
        if len(picked) == n:
            break
        n_cbsa, n_rural, macs = counts()
        remaining = n - len(picked)
        need_cbsa = max(0, MIN_CBSA - n_cbsa)
        need_rural = max(0, MIN_RURAL - n_rural)
        need_macs = max(0, MIN_MACS - len(macs))
        if row["unit_type"] == "cbsa" and remaining - need_rural <= 0:
            continue  # must save room for rural counties
        if row["unit_type"] == "county" and remaining - need_cbsa <= 0:
            continue  # must save room for CBSAs
        if need_macs >= remaining and row["mac"] in macs:
            continue  # must save room for new MAC jurisdictions
        picked.append(row)

    n_cbsa, n_rural, macs = counts()
    assert len(picked) == n, f"selection incomplete: {len(picked)}"
    assert n_cbsa >= MIN_CBSA and n_rural >= MIN_RURAL and len(macs) >= MIN_MACS, (
        f"constraints unmet: cbsa={n_cbsa} rural={n_rural} macs={len(macs)}"
    )
    return picked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_screen_select.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/score retina/pilot/src/retina_pilot/transform/select.py retina/pilot/tests/test_screen_select.py
git commit -m "feat: add screen score and constrained pilot selection"
```

---

### Task 11: Stage 1 CLI (`screen` + `select`) and first real run

**Files:**
- Create: `retina/pilot/src/retina_pilot/cli.py`
- Test: `retina/pilot/tests/test_cli_stage1.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli_stage1.py`:

```python
import json

import pandas as pd

from retina_pilot import cli


def test_run_screen_assembles_and_writes(tmp_path, monkeypatch):
    counties = pd.DataFrame({"fips": ["06037", "30033"], "state": ["CA", "MT"],
                             "county_name": ["Los Angeles County", "Garfield County"],
                             "lat": [34.0, 47.0], "lon": [-118.0, -106.0]})
    xwalk = pd.DataFrame({"fips": ["06037"], "cbsa_code": ["31080"],
                          "cbsa_title": ["LA, CA"], "metro_micro": ["Metropolitan Statistical Area"]})
    pop = pd.DataFrame({"fips": ["06037", "30033"], "pop_total": [1000000, 1000], "pop65": [150000, 300]})
    svi = pd.DataFrame({"fips": ["06037", "30033"], "svi": [0.8, 0.3]})
    rucc = pd.DataFrame({"fips": ["06037", "30033"], "rucc": [1, 9]})
    enrl = pd.DataFrame({"fips": ["06037", "30033"], "medicare_benes": [90000, 200],
                         "ma_benes": [45000, 20], "ma_pct": [50.0, 10.0]})
    provs = pd.DataFrame({"npi": ["1", "2"], "state": ["CA", "CA"], "zip5": ["90001", "90002"]})
    zcta = pd.DataFrame({"zcta": ["90001", "90002"], "fips": ["06037", "06037"]})

    monkeypatch.setattr(cli.census, "load_county_frame", lambda: counties)
    monkeypatch.setattr(cli.census, "load_cbsa_xwalk", lambda: xwalk)
    monkeypatch.setattr(cli.census, "load_pop65", lambda: pop)
    monkeypatch.setattr(cli.census, "load_zcta_county", lambda: zcta)
    monkeypatch.setattr(cli.area_context, "load_svi", lambda: svi)
    monkeypatch.setattr(cli.area_context, "load_rucc", lambda: rucc)
    monkeypatch.setattr(cli.enrollment, "load_enrollment", lambda: enrl)
    monkeypatch.setattr(cli.providers, "load_ophth_providers", lambda: provs)

    out = cli.run_screen(outdir=tmp_path)
    assert (tmp_path / "screen_scores.parquet").exists()
    assert (tmp_path / "county_screen.parquet").exists()
    assert "screen_score" in out.columns
    assert len(out) == 2  # one CBSA unit + one rural county unit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_stage1.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/cli.py`:

```python
"""Pipeline CLI. Stages: screen, select (Stage 1); deepdive, score, actions, export (Stage 2)."""
import argparse
import json
from pathlib import Path

import pandas as pd

from retina_pilot.ingest import area_context, census, enrollment, providers
from retina_pilot.score import screen as screen_score_mod
from retina_pilot.transform import geo_frame, select as select_mod

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "out"


def run_screen(outdir: Path = OUT_DIR) -> pd.DataFrame:
    outdir.mkdir(parents=True, exist_ok=True)
    counties = census.load_county_frame()
    xwalk = census.load_cbsa_xwalk()
    pop = census.load_pop65()
    svi = area_context.load_svi()
    rucc = area_context.load_rucc()
    enrl = enrollment.load_enrollment()
    provs = providers.load_ophth_providers()
    zcta = census.load_zcta_county()

    prov_county = provs.merge(zcta, left_on="zip5", right_on="zcta", how="left")
    prov_counts = (prov_county.dropna(subset=["fips"]).groupby("fips").size()
                   .rename("retina_providers").reset_index())

    metrics = (pop.merge(svi, on="fips", how="left")
                  .merge(rucc, on="fips", how="left")
                  .merge(enrl, on="fips", how="left")
                  .merge(prov_counts, on="fips", how="left"))
    metrics["retina_providers"] = metrics["retina_providers"].fillna(0).astype(int)

    # QA assertions (spec: pipeline QA)
    assert len(metrics) > 3000 or len(metrics) < 10, "unexpected county count"
    assert metrics["svi"].notna().mean() > 0.9 or len(metrics) < 10, "SVI join coverage below 90%"

    units = geo_frame.assign_units(counties, xwalk)
    unit_metrics = geo_frame.aggregate_to_units(units, metrics.dropna(subset=["pop65", "svi", "ma_pct"]))
    rucc_unit = units.merge(rucc, on="fips").groupby("unit_id")["rucc"].max().reset_index()
    unit_metrics = unit_metrics.merge(rucc_unit, on="unit_id", how="left")
    scored = screen_score_mod.score_screen(unit_metrics)

    county_screen = units.merge(metrics, on="fips", how="left").merge(
        scored[["unit_id", "screen_score"]], on="unit_id", how="left")
    county_screen.to_parquet(outdir / "county_screen.parquet", index=False)
    scored.to_parquet(outdir / "screen_scores.parquet", index=False)
    return scored


def run_select(outdir: Path = OUT_DIR) -> list[dict]:
    scored = pd.read_parquet(outdir / "screen_scores.parquet")
    picked = select_mod.select_pilot(scored, n=10)
    (outdir / "selected_10.json").write_text(json.dumps(picked, indent=2, default=str))
    return picked


def main():
    parser = argparse.ArgumentParser(prog="retina-pilot")
    parser.add_argument("stage", choices=["screen", "select", "deepdive", "score", "actions", "export"])
    args = parser.parse_args()
    stage = {"screen": run_screen, "select": run_select}.get(args.stage)
    if stage is None:
        raise SystemExit(f"stage not implemented yet: {args.stage}")
    stage()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_stage1.py -v`
Expected: 1 passed.

- [ ] **Step 5: First real Stage 1 run**

Run: `uv run python -m retina_pilot.cli screen` then `uv run python -m retina_pilot.cli select`
Expected: `data/out/screen_scores.parquet`, `county_screen.parquet`, and `selected_10.json` created. Inspect: `uv run python -c "import json, pathlib; print(json.dumps(json.loads(pathlib.Path('data/out/selected_10.json').read_text()), indent=2)[:2000])"`. Sanity-check the 10 picks (mix of CBSAs and rural counties, several MACs). If an ingest fails on live data (column drift, URL drift), fix the pinned constant or `sources.py` and re-run; cached responses make re-runs fast.

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/cli.py retina/pilot/tests/test_cli_stage1.py
git commit -m "feat: add stage 1 CLI (screen + select) and run national screen"
```

---

### Task 12: MUPPHY deep-dive ingest (HCPCS-filtered provider volumes)

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/mupphy.py`
- Test: `retina/pilot/tests/test_mupphy.py`

- [ ] **Step 1: Write the failing test**

`tests/test_mupphy.py`:

```python
import retina_pilot.ingest.mupphy as mup


def test_parse_mupphy_rows():
    rows = [
        {"Rndrng_NPI": "111", "Rndrng_Prvdr_Last_Org_Name": "JONES",
         "Rndrng_Prvdr_State_Abrvtn": "CA", "Rndrng_Prvdr_Zip5": "90001",
         "HCPCS_Cd": "67028", "Tot_Srvcs": "250.0", "Tot_Benes": "60",
         "Avg_Mdcr_Pymt_Amt": "98.5", "Place_Of_Srvc": "O"},
    ]
    df = mup.parse_mupphy(rows)
    r = df.iloc[0]
    assert r["npi"] == "111"
    assert r["hcpcs"] == "67028"
    assert r["services"] == 250.0
    assert r["state"] == "CA"


def test_fetch_uses_one_filter_per_code(monkeypatch):
    seen = []

    def fake_fetch_all(url, filters=None, page_size=5000):
        seen.append(filters["HCPCS_Cd"])
        return []

    monkeypatch.setattr(mup.cms_api, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(mup.cms_api, "resolve_data_cms_dataset", lambda t: "https://x/data")
    mup.fetch_mupphy_by_hcpcs(["67028", "J0178"])
    assert seen == ["67028", "J0178"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mupphy.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/ingest/mupphy.py`:

```python
"""Medicare Physician & Other Practitioners by Provider and Service, filtered to retina codes."""
import pandas as pd

from retina_pilot import sources
from retina_pilot.ingest import cms_api

# Probe-and-pin (verified pattern in Task 5 step 5)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mupphy.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/mupphy.py retina/pilot/tests/test_mupphy.py
git commit -m "feat: add HCPCS-filtered MUPPHY ingest"
```

---

### Task 13: QDD, 340B, ClinicalTrials.gov, Open Payments, facility-affiliation ingests

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/deepdive_sources.py`
- Test: `retina/pilot/tests/test_deepdive_sources.py`

- [ ] **Step 1: Write the failing test**

`tests/test_deepdive_sources.py`:

```python
import retina_pilot.ingest.deepdive_sources as dd


def test_parse_qdd_keeps_retina_drugs():
    rows = [
        {"HCPCS_Cd": "J0178", "HCPCS_Desc": "x", "Tot_Spndng": "3000000000", "Tot_Clms": "1000"},
        {"HCPCS_Cd": "J9999", "HCPCS_Desc": "y", "Tot_Spndng": "1", "Tot_Clms": "1"},
    ]
    df = dd.parse_qdd(rows)
    assert list(df["hcpcs"]) == ["J0178"]


def test_parse_340b(tmp_path):
    raw = (b"Entity Type,340B ID,Entity Name,Participating,State,Zip Code\n"
           b"HOSP,ABC123,GENERAL HOSPITAL,TRUE,CA,90001\n"
           b"HOSP,DEF456,PAST HOSPITAL,FALSE,CA,90002\n")
    df = dd.parse_340b(raw)
    assert len(df) == 1  # non-participating dropped
    assert df.iloc[0]["zip5"] == "90001"


def test_parse_trials_extracts_us_sites():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT01", "briefTitle": "Wet AMD study"},
            "statusModule": {"overallStatus": "RECRUITING"},
            "contactsLocationsModule": {"locations": [
                {"facility": "Retina Inst", "city": "Los Angeles", "state": "California",
                 "country": "United States", "zip": "90001"},
                {"facility": "EU Site", "city": "Paris", "country": "France"},
            ]},
        }
    }
    sites = dd.parse_trial_sites([study])
    assert len(sites) == 1
    assert sites.iloc[0]["nct_id"] == "NCT01"
    assert sites.iloc[0]["zip5"] == "90001"


def test_parse_open_payments():
    rows = [{"covered_recipient_npi": "111", "covered_recipient_specialty_1":
             "Allopathic & Osteopathic Physicians|Ophthalmology|Retina Specialist",
             "total_amount_of_payment_usdollars": "150.25",
             "recipient_state": "CA"}]
    df = dd.parse_open_payments(rows)
    assert df.iloc[0]["amount"] == 150.25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_deepdive_sources.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/ingest/deepdive_sources.py`:

```python
"""Stage 2 ingests: QDD drug spend, HRSA 340B, ClinicalTrials.gov v2, Open Payments, DAC affiliations."""
import io

import pandas as pd

from retina_pilot import codes, sources
from retina_pilot.ingest import cms_api
from retina_pilot.ingest.http_cache import cached_get, cached_json

# ---- QDD (Medicare Part B Spending by Drug) ----

def parse_qdd(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[df["HCPCS_Cd"].isin(codes.ALL_DRUG_HCPCS)]
    return pd.DataFrame({
        "hcpcs": df["HCPCS_Cd"],
        "spending": pd.to_numeric(df["Tot_Spndng"], errors="coerce"),
        "claims": pd.to_numeric(df["Tot_Clms"], errors="coerce"),
    }).reset_index(drop=True)


def load_qdd() -> pd.DataFrame:
    url = cms_api.resolve_data_cms_dataset(sources.CMS_DATASET_TITLES["qdd"])
    return parse_qdd(cms_api.fetch_all(url))


# ---- HRSA 340B covered entities ----

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
    return parse_340b(cached_get(sources.URLS["hrsa_340b_ce"]))


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
    return pd.DataFrame(rows)


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
        rows = cms_api.openpayments_query(ds, [
            ("covered_recipient_specialty_1", "contains", "Ophthalmology"),
            ("recipient_state", "=", st),
        ])
        if rows:
            frames.append(parse_open_payments(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["npi", "specialty", "state", "amount"])


# ---- DAC facility affiliations ----

def fetch_affiliations(npis: list[str]) -> pd.DataFrame:
    ds = cms_api.pdc_resolve(sources.PDC_DATASET_TITLES["dac_fa"])
    frames = []
    for chunk_start in range(0, len(npis), 500):
        chunk = npis[chunk_start:chunk_start + 500]
        for npi in chunk:
            rows = cms_api.pdc_query(ds, [("npi", "=", npi)], limit=50)
            if rows:
                frames.append(pd.DataFrame(rows))
    if not frames:
        return pd.DataFrame(columns=["npi", "facility_type"])
    df = pd.concat(frames, ignore_index=True)
    return df.rename(columns={"facility_type": "facility_type"})[["npi", "facility_type"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_deepdive_sources.py -v`
Expected: 4 passed.

- [ ] **Step 5: Live probes (one row each; pin any drifted column names)**

Run: `uv run python -c "from retina_pilot.ingest.deepdive_sources import load_qdd; print(load_qdd())"`
Expected: a small frame with the retina J/Q codes present.

Run: `uv run python -c "from retina_pilot.ingest import cms_api; ds = cms_api.openpayments_resolve('General Payment Data'); rows = cms_api.openpayments_query(ds, [('recipient_state', '=', 'MT')], limit=1); print(sorted(rows[0].keys()) if rows else 'EMPTY')"`
Expected: keys including `covered_recipient_npi`, `covered_recipient_specialty_1`. Pin drifts.

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/deepdive_sources.py retina/pilot/tests/test_deepdive_sources.py
git commit -m "feat: add QDD, 340B, trials, Open Payments, affiliation ingests"
```

---

### Task 14: MCD policy ingest (local zip, retina filter)

**Files:**
- Create: `retina/pilot/src/retina_pilot/ingest/mcd.py`
- Test: `retina/pilot/tests/test_mcd.py`

**Context:** The Medicare Coverage Database download requires a license click-through, so this ingest reads zips that the operator downloads by hand into `data/cache/mcd/` (`current_lcds.zip` style archives containing pipe- or comma-delimited tables, including an article/LCD table and `*_x_hcpc_code` crosswalks). If the operator has not placed the files, the loader returns empty frames and the policy dimension scores neutral (50) with an explicit data-gap note.

- [ ] **Step 1: Write the failing test**

`tests/test_mcd.py`:

```python
import pandas as pd

import retina_pilot.ingest.mcd as mcd


def test_filter_retina_policies():
    articles = pd.DataFrame({
        "article_id": ["52451", "99999"],
        "title": ["Billing and Coding: Ranibizumab ...", "Cardiac pacing"],
        "contractor": ["Noridian", "X"],
        "last_updated": ["2026-01-15", "2020-01-01"],
    })
    hcpc_xwalk = pd.DataFrame({
        "article_id": ["52451", "99999"],
        "hcpc_code_id": ["J0178", "33208"],
    })
    out = mcd.filter_retina(articles, hcpc_xwalk)
    assert list(out["article_id"]) == ["52451"]


def test_load_returns_empty_when_no_files(tmp_path):
    frames = mcd.load_mcd_retina(tmp_path)
    assert frames["articles"].empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcd.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/ingest/mcd.py`:

```python
"""Medicare Coverage Database: retina LCD/article extraction from operator-downloaded zips.

Manual step: download the current Article and LCD CSV archives from
https://www.cms.gov/medicare-coverage-database/downloads/downloadable-databases.aspx
(license click-through) into retina/pilot/data/cache/mcd/.
"""
import io
import zipfile
from pathlib import Path

import pandas as pd

from retina_pilot import codes

RETINA_HCPCS = set(codes.ALL_DRUG_HCPCS) | set(codes.PROCEDURE_HCPCS)


def _read_table(zf: zipfile.ZipFile, name_contains: str) -> pd.DataFrame:
    for name in zf.namelist():
        if name_contains in name.lower() and name.lower().endswith(".csv"):
            return pd.read_csv(io.BytesIO(zf.read(name)), dtype=str, sep=None, engine="python")
    return pd.DataFrame()


def filter_retina(articles: pd.DataFrame, hcpc_xwalk: pd.DataFrame) -> pd.DataFrame:
    hits = hcpc_xwalk[hcpc_xwalk["hcpc_code_id"].isin(RETINA_HCPCS)]["article_id"].unique()
    return articles[articles["article_id"].isin(hits)].reset_index(drop=True)


def load_mcd_retina(mcd_dir: Path) -> dict:
    zips = sorted(Path(mcd_dir).glob("*.zip"))
    if not zips:
        return {"articles": pd.DataFrame(columns=["article_id", "title", "contractor", "last_updated"])}
    articles_frames, xwalk_frames = [], []
    for zp in zips:
        with zipfile.ZipFile(zp) as zf:
            art = _read_table(zf, "article")
            xw = _read_table(zf, "hcpc")
            if not art.empty:
                articles_frames.append(art)
            if not xw.empty:
                xwalk_frames.append(xw)
    if not articles_frames or not xwalk_frames:
        return {"articles": pd.DataFrame(columns=["article_id", "title", "contractor", "last_updated"])}
    articles = pd.concat(articles_frames, ignore_index=True)
    xwalk = pd.concat(xwalk_frames, ignore_index=True)
    articles.columns = [c.strip().lower() for c in articles.columns]
    xwalk.columns = [c.strip().lower() for c in xwalk.columns]
    return {"articles": filter_retina(articles, xwalk)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcd.py -v`
Expected: 2 passed.

**Execution note:** When running the real pipeline, download the MCD archives and inspect actual inner file/column names; adapt `_read_table` name fragments and the `article_id`/`hcpc_code_id` column names to the real schema (probe-and-pin), keeping `filter_retina` logic unchanged.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/src/retina_pilot/ingest/mcd.py retina/pilot/tests/test_mcd.py
git commit -m "feat: add MCD retina policy ingest with manual-download fallback"
```

---

### Task 15: Deep-dive stage (`run_deepdive`) joining sources to the 10 geographies

**Files:**
- Modify: `retina/pilot/src/retina_pilot/cli.py` (add `run_deepdive`, register stage)
- Test: `retina/pilot/tests/test_cli_deepdive.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli_deepdive.py`:

```python
import json

import pandas as pd

from retina_pilot import cli


def test_run_deepdive_builds_geo_tables(tmp_path, monkeypatch):
    (tmp_path / "selected_10.json").write_text(json.dumps([
        {"unit_id": "county:30033", "unit_type": "county", "unit_name": "Garfield County, MT",
         "state": "MT", "mac": "JF", "pop65": 300, "medicare_benes": 200, "ma_pct": 10.0,
         "svi": 0.3, "rucc": 9, "retina_providers": 0, "screen_score": 88.0},
    ]))
    county_screen = pd.DataFrame({
        "fips": ["30033"], "unit_id": ["county:30033"], "state": ["MT"], "zcta": [None],
    })
    county_screen.to_parquet(tmp_path / "county_screen.parquet", index=False)

    mup = pd.DataFrame({"npi": ["1"], "last_name": ["A"], "state": ["MT"], "zip5": ["59032"],
                        "hcpcs": ["67028"], "services": [100.0], "benes": [40.0],
                        "avg_payment": [95.0], "place_of_service": ["O"]})
    zcta = pd.DataFrame({"zcta": ["59032"], "fips": ["30033"]})

    monkeypatch.setattr(cli.mupphy, "fetch_mupphy_by_hcpcs", lambda c: mup)
    monkeypatch.setattr(cli.census, "load_zcta_county", lambda: zcta)
    monkeypatch.setattr(cli.deepdive_sources, "load_qdd", lambda: pd.DataFrame(
        {"hcpcs": ["J0178"], "spending": [1.0], "claims": [1.0]}))
    monkeypatch.setattr(cli.deepdive_sources, "load_340b", lambda: pd.DataFrame(
        {"ce_id": ["X"], "entity_name": ["H"], "state": ["MT"], "zip5": ["59032"]}))
    monkeypatch.setattr(cli.deepdive_sources, "fetch_retina_studies", lambda: [])
    monkeypatch.setattr(cli.deepdive_sources, "parse_trial_sites", lambda s: pd.DataFrame(
        columns=["nct_id", "title", "facility", "city", "state", "zip5"]))
    monkeypatch.setattr(cli.deepdive_sources, "fetch_ophth_payments", lambda states: pd.DataFrame(
        {"npi": ["1"], "specialty": ["Ophthalmology"], "state": ["MT"], "amount": [100.0]}))
    monkeypatch.setattr(cli.deepdive_sources, "fetch_affiliations", lambda npis: pd.DataFrame(
        {"npi": ["1"], "facility_type": ["Hospital"]}))
    monkeypatch.setattr(cli.mcd, "load_mcd_retina", lambda d: {"articles": pd.DataFrame(
        {"article_id": ["52451"], "title": ["Anti-VEGF"], "contractor": ["Noridian JF"],
         "last_updated": ["2026-01-15"]})})

    cli.run_deepdive(outdir=tmp_path)
    assert (tmp_path / "deepdive_providers.parquet").exists()
    provs = pd.read_parquet(tmp_path / "deepdive_providers.parquet")
    assert provs.iloc[0]["unit_id"] == "county:30033"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_deepdive.py -v`
Expected: FAIL with `AttributeError: ... no attribute 'run_deepdive'`.

- [ ] **Step 3: Add the implementation to `cli.py`**

Add imports at the top of `cli.py`:

```python
from retina_pilot import sources
from retina_pilot.ingest import deepdive_sources, mcd, mupphy
from retina_pilot.codes import ALL_DRUG_HCPCS, PROCEDURE_HCPCS
```

Add the function:

```python
def run_deepdive(outdir: Path = OUT_DIR) -> None:
    selected = json.loads((outdir / "selected_10.json").read_text())
    county_screen = pd.read_parquet(outdir / "county_screen.parquet")
    pilot_units = {s["unit_id"] for s in selected}
    pilot_counties = county_screen[county_screen["unit_id"].isin(pilot_units)][["fips", "unit_id"]]
    pilot_states = sorted({s["state"].split(",")[0] for s in selected})

    zcta = census.load_zcta_county()
    zip_to_unit = zcta.merge(pilot_counties, on="fips")[["zcta", "unit_id"]]

    all_codes = list(PROCEDURE_HCPCS) + ALL_DRUG_HCPCS
    mup = mupphy.fetch_mupphy_by_hcpcs(all_codes)
    mup = mup.merge(zip_to_unit, left_on="zip5", right_on="zcta", how="inner")
    mup.to_parquet(outdir / "deepdive_providers.parquet", index=False)

    deepdive_sources.load_qdd().to_parquet(outdir / "deepdive_qdd.parquet", index=False)

    ce = deepdive_sources.load_340b()
    ce = ce.merge(zip_to_unit, left_on="zip5", right_on="zcta", how="inner")
    ce.to_parquet(outdir / "deepdive_340b.parquet", index=False)

    sites = deepdive_sources.parse_trial_sites(deepdive_sources.fetch_retina_studies())
    if not sites.empty:
        sites = sites.merge(zip_to_unit, left_on="zip5", right_on="zcta", how="inner")
    sites.to_parquet(outdir / "deepdive_trials.parquet", index=False)

    pay = deepdive_sources.fetch_ophth_payments(pilot_states)
    pilot_npis = sorted(set(mup["npi"]))
    pay = pay[pay["npi"].isin(pilot_npis)]
    pay.to_parquet(outdir / "deepdive_payments.parquet", index=False)

    aff = deepdive_sources.fetch_affiliations(pilot_npis)
    aff.to_parquet(outdir / "deepdive_affiliations.parquet", index=False)

    mcd_frames = mcd.load_mcd_retina(Path(sources.MCD_LOCAL_DIR))
    mcd_frames["articles"].to_parquet(outdir / "deepdive_mcd.parquet", index=False)
```

Register it in `main()`’s stage dict: `"deepdive": run_deepdive`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli_deepdive.py -v`
Expected: 1 passed. Also run the full suite: `uv run pytest -q` — all green.

- [ ] **Step 5: Real deep-dive run**

Run: `uv run python -m retina_pilot.cli deepdive`
Expected: six `deepdive_*.parquet` files in `data/out/`. Spot-check row counts (`duckdb` one-liner: `uv run python -c "import duckdb; [print(f, duckdb.sql(f\"select count(*) from 'data/out/{f}'\").fetchone()[0]) for f in ['deepdive_providers.parquet','deepdive_qdd.parquet','deepdive_340b.parquet','deepdive_trials.parquet','deepdive_payments.parquet','deepdive_affiliations.parquet']]"`). Investigate any zero-row file before continuing (usually a pinned column name or a geography with genuinely no data; document which).

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/cli.py retina/pilot/tests/test_cli_deepdive.py
git commit -m "feat: add deep-dive stage joining all sources to pilot geographies"
```

---

### Task 16: Seven dimension scorers and composite (`score/dimensions.py`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/score/dimensions.py`
- Test: `retina/pilot/tests/test_dimensions.py`

- [ ] **Step 1: Write the failing test**

`tests/test_dimensions.py`:

```python
import pandas as pd

from retina_pilot.score import dimensions as dim


def _selected():
    return [
        {"unit_id": "county:30033", "unit_name": "Garfield County, MT", "mac": "JF",
         "pop65": 300, "medicare_benes": 200, "ma_pct": 10.0, "svi": 0.3, "rucc": 9,
         "retina_providers": 0, "screen_score": 88.0, "unit_type": "county", "state": "MT"},
        {"unit_id": "cbsa:31080", "unit_name": "LA, CA", "mac": "JE",
         "pop65": 150000, "medicare_benes": 90000, "ma_pct": 55.0, "svi": 0.8, "rucc": 1,
         "retina_providers": 40, "screen_score": 72.0, "unit_type": "cbsa", "state": "CA"},
    ]


def _providers():
    return pd.DataFrame({
        "unit_id": ["cbsa:31080"] * 3,
        "npi": ["1", "1", "2"],
        "hcpcs": ["67028", "J0178", "Q5147"],
        "services": [500.0, 400.0, 100.0],
        "benes": [120.0, 100.0, 30.0],
        "avg_payment": [95.0, 900.0, 500.0],
        "place_of_service": ["O", "O", "O"],
    })


def test_scorecards_have_all_dimensions():
    cards = dim.score_dimensions(
        selected=_selected(),
        providers=_providers(),
        ce_340b=pd.DataFrame({"unit_id": ["cbsa:31080"], "ce_id": ["X"]}),
        trials=pd.DataFrame({"unit_id": ["cbsa:31080"], "nct_id": ["NCT01"], "facility": ["F"]}),
        payments=pd.DataFrame({"npi": ["1"], "amount": [5000.0]}),
        affiliations=pd.DataFrame({"npi": ["1"], "facility_type": ["Hospital"]}),
        mcd_articles=pd.DataFrame({"article_id": ["52451"], "contractor": ["Noridian JE"],
                                   "last_updated": ["2026-01-15"]}),
    )
    assert set(dim.DIMENSIONS) <= set(cards.columns)
    assert cards["composite"].between(0, 100).all()
    la = cards[cards.unit_id == "cbsa:31080"].iloc[0]
    mt = cards[cards.unit_id == "county:30033"].iloc[0]
    assert la["supply"] > mt["supply"]          # LA has providers, MT has none
    assert la["biosimilar_share_pct"] == 20.0   # 100 of 500 drug services


def test_no_mcd_data_scores_neutral():
    cards = dim.score_dimensions(
        selected=_selected(), providers=_providers(),
        ce_340b=pd.DataFrame(columns=["unit_id", "ce_id"]),
        trials=pd.DataFrame(columns=["unit_id", "nct_id", "facility"]),
        payments=pd.DataFrame(columns=["npi", "amount"]),
        affiliations=pd.DataFrame(columns=["npi", "facility_type"]),
        mcd_articles=pd.DataFrame(columns=["article_id", "contractor", "last_updated"]),
    )
    assert (cards["policy"] == 50.0).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dimensions.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/score/dimensions.py`:

```python
"""Seven dimension scorers (spec: Scoring). Percentile-ranked within the pilot pool, 0-100.

Equal weights across dimensions (spec decision); change WEIGHTS only.
"""
import pandas as pd

from retina_pilot import codes

DIMENSIONS = ["supply", "utilization", "drug_mix", "site_of_care", "policy", "trials_kol", "access_risk"]
WEIGHTS = {d: 1 / len(DIMENSIONS) for d in DIMENSIONS}

DRUG_CODES = set(codes.ALL_DRUG_HCPCS)
BIOSIM = set(codes.ANTIVEGF_BIOSIMILAR_HCPCS)


def _pct(series: pd.Series) -> pd.Series:
    if series.nunique() <= 1:
        return pd.Series(50.0, index=series.index)
    return (100 * series.rank(pct=True)).round(1)


def score_dimensions(selected, providers, ce_340b, trials, payments, affiliations, mcd_articles) -> pd.DataFrame:
    df = pd.DataFrame(selected)

    inj = providers[providers["hcpcs"] == "67028"].groupby("unit_id")["services"].sum()
    oct_ = providers[providers["hcpcs"] == "92134"].groupby("unit_id")["services"].sum()
    injectors = providers[providers["hcpcs"] == "67028"].groupby("unit_id")["npi"].nunique()
    drug = providers[providers["hcpcs"].isin(DRUG_CODES)]
    drug_services = drug.groupby("unit_id")["services"].sum()
    biosim_services = drug[drug["hcpcs"].isin(BIOSIM)].groupby("unit_id")["services"].sum()

    df["inj_services"] = df["unit_id"].map(inj).fillna(0)
    df["oct_services"] = df["unit_id"].map(oct_).fillna(0)
    df["injectors"] = df["unit_id"].map(injectors).fillna(0).astype(int)
    df["inj_per_1k_benes"] = (1000 * df["inj_services"] / df["medicare_benes"]).round(1)
    df["biosimilar_share_pct"] = (
        100 * df["unit_id"].map(biosim_services).fillna(0) / df["unit_id"].map(drug_services)
    ).fillna(0).round(1)

    ce_counts = ce_340b.groupby("unit_id").size()
    df["ce_340b"] = df["unit_id"].map(ce_counts).fillna(0).astype(int)

    hosp_npis = set(affiliations.loc[affiliations["facility_type"].str.contains(
        "Hospital", case=False, na=False), "npi"]) if not affiliations.empty else set()
    inj_by_unit = providers[providers["hcpcs"] == "67028"].groupby("unit_id")["npi"].agg(set)
    df["hosp_affil_share"] = df["unit_id"].map(
        lambda u: (len(inj_by_unit.get(u, set()) & hosp_npis) / len(inj_by_unit.get(u, set())))
        if len(inj_by_unit.get(u, set())) else 0.0)

    trial_counts = trials.groupby("unit_id")["nct_id"].nunique() if not trials.empty else pd.Series(dtype=int)
    df["trial_count"] = df["unit_id"].map(trial_counts).fillna(0).astype(int)
    pay_total = payments["amount"].sum() if not payments.empty else 0.0
    df["payments_context"] = pay_total  # pool-level context, equal across units

    # Dimension scores
    df["supply"] = _pct(df["injectors"] / df["pop65"] * 10000)
    df["utilization"] = _pct(df["inj_per_1k_benes"])
    df["drug_mix"] = _pct(df["biosimilar_share_pct"])
    df["site_of_care"] = _pct(df["ce_340b"].astype(float) + df["hosp_affil_share"])
    if mcd_articles.empty:
        df["policy"] = 50.0  # neutral when MCD not loaded; data gap noted downstream
        df["policy_articles"] = 0
    else:
        df["policy_articles"] = len(mcd_articles)
        recency = pd.to_datetime(mcd_articles["last_updated"], errors="coerce").max()
        df["policy"] = _pct(pd.Series([1.0] * len(df), index=df.index))  # same MAC-level baseline
        df.loc[df["mac"].isin(
            mcd_articles["contractor"].astype(str).str.extract(r"(J[A-Z0-9]+)", expand=False).dropna().unique()
        ), "policy"] = 75.0
        df["policy_last_update"] = str(recency.date()) if pd.notna(recency) else None
    df["trials_kol"] = _pct(df["trial_count"])
    df["access_risk"] = _pct(df["svi"].rank(pct=True) + df["ma_pct"].rank(pct=True) + df["rucc"].rank(pct=True))

    df["composite"] = sum(df[d] * w for d, w in WEIGHTS.items()).round(1)
    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dimensions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Wire the `score` stage into `cli.py`**

Add to `cli.py`:

```python
def run_score(outdir: Path = OUT_DIR) -> pd.DataFrame:
    from retina_pilot.score import dimensions as dim
    selected = json.loads((outdir / "selected_10.json").read_text())
    cards = dim.score_dimensions(
        selected=selected,
        providers=pd.read_parquet(outdir / "deepdive_providers.parquet"),
        ce_340b=pd.read_parquet(outdir / "deepdive_340b.parquet"),
        trials=pd.read_parquet(outdir / "deepdive_trials.parquet"),
        payments=pd.read_parquet(outdir / "deepdive_payments.parquet"),
        affiliations=pd.read_parquet(outdir / "deepdive_affiliations.parquet"),
        mcd_articles=pd.read_parquet(outdir / "deepdive_mcd.parquet"),
    )
    cards.to_parquet(outdir / "scorecards.parquet", index=False)
    return cards
```

Register `"score": run_score` in `main()`. Run the real stage: `uv run python -m retina_pilot.cli score`. Inspect: composite spread should be non-degenerate (not all 50).

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/score/dimensions.py retina/pilot/tests/test_dimensions.py retina/pilot/src/retina_pilot/cli.py
git commit -m "feat: add 7-dimension scorers and composite"
```

---

### Task 17: Rule engine and rules (`actions/`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/actions/__init__.py` (empty)
- Create: `retina/pilot/src/retina_pilot/actions/engine.py`
- Create: `retina/pilot/src/retina_pilot/actions/rules.yaml`
- Test: `retina/pilot/tests/test_actions.py`

- [ ] **Step 1: Write the failing test**

`tests/test_actions.py`:

```python
from retina_pilot.actions import engine

RULES = [
    {"id": "ma_low_supply", "role": "market_access",
     "when": [{"metric": "supply", "op": "<=", "value": 35},
              {"metric": "ma_pct", "op": ">=", "value": 45}],
     "action": "High MA penetration with thin retina supply: assess network adequacy and site-of-care economics."},
    {"id": "msl_trials", "role": "msl",
     "when": [{"metric": "trial_count", "op": ">=", "value": 1}],
     "action": "Active retina trial sites present: prioritize investigator engagement."},
]


def test_rule_fires_with_citation():
    geo = {"unit_id": "county:30033", "supply": 10.0, "ma_pct": 50.0, "trial_count": 0}
    actions = engine.generate_actions(geo, RULES)
    assert len(actions) == 1
    a = actions[0]
    assert a["role"] == "market_access"
    assert a["rule_id"] == "ma_low_supply"
    assert {"metric": "supply", "value": 10.0} in a["evidence"]


def test_rule_does_not_fire():
    geo = {"unit_id": "x", "supply": 90.0, "ma_pct": 50.0, "trial_count": 0}
    assert engine.generate_actions(geo, RULES) == []


def test_default_rules_load_and_evaluate():
    rules = engine.load_rules()
    assert len(rules) >= 6
    roles = {r["role"] for r in rules}
    assert roles == {"msl", "medical_affairs", "market_access"}
    geo = {"supply": 10.0, "ma_pct": 60.0, "trial_count": 3, "biosimilar_share_pct": 2.0,
           "ce_340b": 4, "access_risk": 90.0, "utilization": 20.0, "policy_articles": 1,
           "injectors": 1, "unit_id": "x"}
    assert engine.generate_actions(geo, rules)  # at least one rule fires
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_actions.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/actions/engine.py`:

```python
"""Deterministic rule engine: dimension scores and facts in, cited role actions out."""
import operator
from pathlib import Path

import yaml

OPS = {"<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt, "==": operator.eq}
RULES_PATH = Path(__file__).parent / "rules.yaml"


def load_rules(path: Path = RULES_PATH) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def generate_actions(geo: dict, rules: list[dict]) -> list[dict]:
    out = []
    for rule in rules:
        evidence = []
        for cond in rule["when"]:
            value = geo.get(cond["metric"])
            if value is None or not OPS[cond["op"]](value, cond["value"]):
                evidence = None
                break
            evidence.append({"metric": cond["metric"], "value": value})
        if evidence is not None:
            out.append({"rule_id": rule["id"], "role": rule["role"],
                        "action": rule["action"], "evidence": evidence})
    return out
```

`src/retina_pilot/actions/rules.yaml`:

```yaml
- id: ma_low_supply_high_ma
  role: market_access
  when:
    - {metric: supply, op: "<=", value: 35}
    - {metric: ma_pct, op: ">=", value: 45}
  action: >
    High Medicare Advantage penetration combined with thin retina supply. Assess MA
    network adequacy, site-of-care economics, and plan-level medical policy for
    anti-VEGF agents in this geography.

- id: ma_policy_watch
  role: market_access
  when:
    - {metric: policy_articles, op: ">=", value: 1}
  action: >
    Retina-relevant LCD/article activity exists for this MAC jurisdiction. Review
    covered-diagnosis lists and documentation language against current billing
    practice; track revision history for early policy-drift signals.

- id: ma_340b_concentration
  role: market_access
  when:
    - {metric: ce_340b, op: ">=", value: 3}
  action: >
    Multiple 340B covered entities operate here. Account strategy should model
    site-of-care incentive differences between hospital outpatient and
    community-office settings before interpreting product mix.

- id: msl_trial_sites
  role: msl
  when:
    - {metric: trial_count, op: ">=", value: 1}
  action: >
    Active retina trial sites are recruiting in this geography. Prioritize
    investigator engagement and align scientific exchange with locally active
    protocols and endpoints.

- id: msl_no_trials_high_volume
  role: msl
  when:
    - {metric: trial_count, op: "==", value: 0}
    - {metric: utilization, op: ">=", value: 60}
  action: >
    High injection utilization but no active trial presence. Identify high-volume
    treaters as potential real-world-evidence partners or future site candidates.

- id: medaff_low_biosimilar
  role: medical_affairs
  when:
    - {metric: biosimilar_share_pct, op: "<=", value: 10}
  action: >
    Biosimilar share of anti-VEGF services is low relative to the pilot pool.
    Evidence needs around comparative effectiveness, switching, and payer policy
    may explain adoption friction; validate with local accounts.

- id: medaff_access_equity
  role: medical_affairs
  when:
    - {metric: access_risk, op: ">=", value: 70}
  action: >
    Elevated access-risk context (deprivation, rurality, MA mix). Treatment-burden
    and adherence-support evidence is most relevant here; consider geography for
    health-equity-focused evidence generation.

- id: medaff_supply_desert
  role: medical_affairs
  when:
    - {metric: injectors, op: "<=", value: 2}
  action: >
    Two or fewer Medicare-visible injectors serve this geography. Document as a
    capacity-constrained market; durability-focused evidence (longer intervals,
    fewer visits) carries outsized local relevance.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_actions.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire the `actions` stage into `cli.py`**

Add to `cli.py`:

```python
def run_actions(outdir: Path = OUT_DIR) -> None:
    from retina_pilot.actions import engine
    cards = pd.read_parquet(outdir / "scorecards.parquet")
    rules = engine.load_rules()
    all_actions = {row["unit_id"]: engine.generate_actions(row.to_dict(), rules)
                   for _, row in cards.iterrows()}
    (outdir / "actions.json").write_text(json.dumps(all_actions, indent=2))
```

Register `"actions": run_actions` in `main()`. Run: `uv run python -m retina_pilot.cli actions` and skim `data/out/actions.json` for sane output.

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/actions retina/pilot/tests/test_actions.py retina/pilot/src/retina_pilot/cli.py
git commit -m "feat: add rule engine and role action rules"
```

---

### Task 18: Dashboard JSON export (`export/dashboard_json.py`)

**Files:**
- Create: `retina/pilot/src/retina_pilot/export/__init__.py` (empty)
- Create: `retina/pilot/src/retina_pilot/export/dashboard_json.py`
- Test: `retina/pilot/tests/test_export.py`

- [ ] **Step 1: Write the failing test**

`tests/test_export.py`:

```python
import json

import pandas as pd

from retina_pilot.export import dashboard_json as dj


def test_export_writes_four_files(tmp_path):
    county_screen = pd.DataFrame({"fips": ["30033"], "unit_id": ["county:30033"],
                                  "screen_score": [88.0]})
    cards = pd.DataFrame([{"unit_id": "county:30033", "unit_name": "Garfield County, MT",
                           "mac": "JF", "composite": 71.0, "supply": 10.0, "utilization": 20.0,
                           "drug_mix": 50.0, "site_of_care": 50.0, "policy": 50.0,
                           "trials_kol": 50.0, "access_risk": 95.0, "injectors": 1,
                           "inj_services": 100.0, "biosimilar_share_pct": 0.0, "ce_340b": 0,
                           "trial_count": 0, "pop65": 300, "ma_pct": 10.0, "svi": 0.3, "rucc": 9}])
    providers = pd.DataFrame({"unit_id": ["county:30033"], "npi": ["1"], "last_name": ["A"],
                              "hcpcs": ["67028"], "services": [100.0], "benes": [40.0],
                              "avg_payment": [95.0], "state": ["MT"], "zip5": ["59032"],
                              "place_of_service": ["O"], "zcta": ["59032"]})
    actions = {"county:30033": [{"rule_id": "x", "role": "msl", "action": "Do a thing.",
                                 "evidence": [{"metric": "trial_count", "value": 0}]}]}
    trials = pd.DataFrame(columns=["unit_id", "nct_id", "title", "facility", "city", "state", "zip5"])

    dj.write_dashboard_json(tmp_path, county_screen, cards, providers, trials, actions,
                            meta={"acs_vintage": "2023"})

    for f in ["map.json", "scorecards.json", "details.json", "meta.json"]:
        assert (tmp_path / f).exists(), f
    details = json.loads((tmp_path / "details.json").read_text())
    geo = details["county:30033"]
    assert geo["actions"][0]["role"] == "msl"
    assert "data_gaps" in geo and any("MRF" in g for g in geo["data_gaps"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

`src/retina_pilot/export/dashboard_json.py`:

```python
"""Compact JSON exports consumed by dashboard/app.js."""
import json
from pathlib import Path

import pandas as pd

from retina_pilot import codes
from retina_pilot.score.dimensions import DIMENSIONS, WEIGHTS

STANDING_DATA_GAPS = [
    "Commercial procedure economics deferred (payer MRF not processed in this phase).",
    "Patient-level laterality, visual acuity, OCT outcomes, persistence, and switching require claims/EHR/registry data.",
    "Net price, rebates, and acquisition cost are not observable in public files.",
    "MUPPHY suppresses provider rows with 10 or fewer beneficiaries; rural volumes are undercounted.",
]


def write_dashboard_json(outdir: Path, county_screen: pd.DataFrame, cards: pd.DataFrame,
                         providers: pd.DataFrame, trials: pd.DataFrame, actions: dict,
                         meta: dict) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    map_rows = county_screen[["fips", "unit_id", "screen_score"]].dropna()
    selected_units = set(cards["unit_id"])
    map_payload = [
        {"fips": r.fips, "score": round(float(r.screen_score), 1),
         "selected": r.unit_id in selected_units}
        for r in map_rows.itertuples()
    ]
    (outdir / "map.json").write_text(json.dumps(map_payload))

    score_payload = [
        {"unit_id": r["unit_id"], "name": r["unit_name"], "mac": r["mac"],
         "composite": r["composite"], "dims": {d: r[d] for d in DIMENSIONS}}
        for _, r in cards.iterrows()
    ]
    (outdir / "scorecards.json").write_text(json.dumps(score_payload))

    details = {}
    for _, r in cards.iterrows():
        uid = r["unit_id"]
        prov = providers[providers["unit_id"] == uid]
        top = (prov.groupby(["npi", "last_name"])["services"].sum()
               .sort_values(ascending=False).head(15).reset_index())
        drug_mix = (prov[prov["hcpcs"].isin(codes.ALL_DRUG_HCPCS)]
                    .groupby("hcpcs")["services"].sum().to_dict())
        tr = trials[trials["unit_id"] == uid] if not trials.empty else trials
        details[uid] = {
            "name": r["unit_name"], "mac": r["mac"],
            "facts": {"pop65": int(r["pop65"]), "ma_pct": float(r["ma_pct"]),
                      "svi": float(r["svi"]), "rucc": int(r["rucc"]),
                      "injectors": int(r["injectors"]), "inj_services": float(r["inj_services"]),
                      "biosimilar_share_pct": float(r["biosimilar_share_pct"]),
                      "ce_340b": int(r["ce_340b"]), "trial_count": int(r["trial_count"])},
            "top_providers": top.to_dict("records"),
            "drug_mix": {codes.DRUG_LABELS.get(k, k): v for k, v in drug_mix.items()},
            "trials": tr[["nct_id", "title", "facility", "city"]].to_dict("records") if not tr.empty else [],
            "actions": actions.get(uid, []),
            "data_gaps": list(STANDING_DATA_GAPS),
        }
    (outdir / "details.json").write_text(json.dumps(details))

    meta_payload = dict(meta, weights=WEIGHTS, dimensions=DIMENSIONS,
                        drug_codes=codes.DRUG_LABELS,
                        procedure_codes=codes.PROCEDURE_HCPCS)
    (outdir / "meta.json").write_text(json.dumps(meta_payload, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_export.py -v`
Expected: 1 passed.

- [ ] **Step 5: Wire the `export` stage into `cli.py` and run it**

Add to `cli.py`:

```python
def run_export(outdir: Path = OUT_DIR) -> None:
    from datetime import date
    from retina_pilot.export import dashboard_json as dj
    dash_data = Path(__file__).resolve().parents[2] / "dashboard" / "data"
    dj.write_dashboard_json(
        dash_data,
        county_screen=pd.read_parquet(outdir / "county_screen.parquet"),
        cards=pd.read_parquet(outdir / "scorecards.parquet"),
        providers=pd.read_parquet(outdir / "deepdive_providers.parquet"),
        trials=pd.read_parquet(outdir / "deepdive_trials.parquet"),
        actions=json.loads((outdir / "actions.json").read_text()),
        meta={"generated": str(date.today()), "acs_vintage": "2023 ACS 5-year",
              "sources_note": "All data from official public sources; see spec."},
    )
```

Register `"export": run_export`. Run: `uv run python -m retina_pilot.cli export`. Check `dashboard/data/` JSON sizes (target under 5 MB total per spec; if `map.json` is large, round scores and drop nulls).

- [ ] **Step 6: Commit**

```bash
git add retina/pilot/src/retina_pilot/export retina/pilot/tests/test_export.py retina/pilot/src/retina_pilot/cli.py retina/pilot/dashboard/data
git commit -m "feat: add dashboard JSON export stage"
```

---

### Task 19: Dashboard shell, vendored libraries, national map view

**Files:**
- Create: `retina/pilot/dashboard/index.html`
- Create: `retina/pilot/dashboard/app.js`
- Create: `retina/pilot/dashboard/vendor/echarts.min.js` (vendored)
- Create: `retina/pilot/dashboard/vendor/us-counties.geo.json` (vendored)

- [ ] **Step 1: Vendor the libraries**

Run (in `retina/pilot/`):

```bash
mkdir -p dashboard/vendor
curl -L -o dashboard/vendor/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js
curl -L -o dashboard/vendor/us-counties.geo.json https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json
```

Expected: both files download (echarts ~1 MB, counties geojson ~3 MB). These are vendored once and committed; the dashboard never loads from a CDN at runtime.

- [ ] **Step 2: Write the dashboard shell**

`dashboard/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Retina Access and Evidence Action Pilot</title>
  <style>
    :root { --ink: #17201b; --muted: #59655e; --paper: #fbfaf4; --line: #d9ded5; --accent: #245f65; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, "Segoe UI", Arial, sans-serif; background: var(--paper); color: var(--ink); }
    header { padding: 18px 24px; border-bottom: 1px solid var(--line); }
    h1 { margin: 0; font-size: 1.3rem; }
    nav { display: flex; gap: 8px; padding: 10px 24px; border-bottom: 1px solid var(--line); }
    nav button { padding: 8px 14px; border: 1px solid var(--line); background: #fff; border-radius: 6px; cursor: pointer; font-weight: 600; }
    nav button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
    main { padding: 18px 24px; }
    .view { display: none; }
    .view.active { display: block; }
    #map-chart { width: 100%; height: 640px; }
    #radar-chart { width: 100%; height: 520px; }
    select { padding: 6px 10px; font-size: 1rem; margin-bottom: 12px; }
    table { border-collapse: collapse; width: 100%; font-size: 0.9rem; background: #fff; }
    th, td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; }
    .panel { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; }
    .role { font-weight: 700; color: var(--accent); text-transform: uppercase; font-size: 0.75rem; }
    .muted { color: var(--muted); font-size: 0.85rem; }
  </style>
</head>
<body>
  <header><h1>Retina Access and Evidence Action Pilot (Wet AMD)</h1></header>
  <nav>
    <button data-view="map" class="active">National Screen</button>
    <button data-view="scorecards">Scorecards</button>
    <button data-view="detail">Geography Detail</button>
    <button data-view="methods">Methods</button>
  </nav>
  <main>
    <div id="view-map" class="view active"><div id="map-chart"></div></div>
    <div id="view-scorecards" class="view"><div id="radar-chart"></div><div id="score-table"></div></div>
    <div id="view-detail" class="view">
      <select id="geo-select"></select>
      <div id="detail-content"></div>
    </div>
    <div id="view-methods" class="view"><div id="methods-content" class="panel"></div></div>
  </main>
  <script src="vendor/echarts.min.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write the app with the map view working**

`dashboard/app.js`:

```javascript
/* Static dashboard: loads JSON exports, renders 4 views. No backend. */
const state = {};

async function loadAll() {
  const [mapData, cards, details, meta, geo] = await Promise.all([
    fetch("data/map.json").then(r => r.json()),
    fetch("data/scorecards.json").then(r => r.json()),
    fetch("data/details.json").then(r => r.json()),
    fetch("data/meta.json").then(r => r.json()),
    fetch("vendor/us-counties.geo.json").then(r => r.json()),
  ]);
  Object.assign(state, { mapData, cards, details, meta, geo });
}

function renderMap() {
  echarts.registerMap("USCounties", state.geo);
  const chart = echarts.init(document.getElementById("map-chart"));
  chart.setOption({
    title: { text: "National screen score (selected geographies outlined)", left: "center" },
    tooltip: { formatter: p => `${p.name || p.data?.fips}: ${p.value ?? "n/a"}` },
    visualMap: { min: 0, max: 100, left: 16, bottom: 16, text: ["high need", "low need"],
                 inRange: { color: ["#eaf3f2", "#245f65"] } },
    series: [{
      type: "map", map: "USCounties", nameProperty: "id",
      data: state.mapData.map(d => ({
        name: d.fips, fips: d.fips, value: d.score, selected: false,
        itemStyle: d.selected ? { borderColor: "#a85f36", borderWidth: 2 } : undefined,
      })),
    }],
  });
}

function renderScorecards() {
  const dims = state.meta.dimensions;
  const chart = echarts.init(document.getElementById("radar-chart"));
  chart.setOption({
    title: { text: "Dimension scores across the 10 pilot geographies", left: "center" },
    legend: { type: "scroll", bottom: 0 },
    radar: { indicator: dims.map(d => ({ name: d, max: 100 })) },
    series: [{ type: "radar",
      data: state.cards.map(c => ({ name: c.name, value: dims.map(d => c.dims[d]) })) }],
  });
  const rows = state.cards.map(c =>
    `<tr><td>${c.name}</td><td>${c.mac}</td><td>${c.composite}</td>` +
    dims.map(d => `<td>${c.dims[d]}</td>`).join("") + "</tr>").join("");
  document.getElementById("score-table").innerHTML =
    `<table><tr><th>Geography</th><th>MAC</th><th>Composite</th>` +
    dims.map(d => `<th>${d}</th>`).join("") + `</tr>${rows}</table>`;
}

function renderDetail(unitId) {
  const d = state.details[unitId];
  if (!d) return;
  const facts = Object.entries(d.facts).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
  const provs = d.top_providers.map(p =>
    `<tr><td>${p.last_name}</td><td>${p.npi}</td><td>${p.services}</td></tr>`).join("");
  const drugs = Object.entries(d.drug_mix).map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
  const trials = d.trials.map(t => `<tr><td>${t.nct_id}</td><td>${t.title}</td><td>${t.facility}, ${t.city}</td></tr>`).join("");
  const actions = d.actions.map(a =>
    `<div class="panel"><span class="role">${a.role.replace("_", " ")}</span><p>${a.action}</p>` +
    `<p class="muted">Evidence: ${a.evidence.map(e => `${e.metric}=${e.value}`).join(", ")}</p></div>`).join("");
  const gaps = d.data_gaps.map(g => `<li>${g}</li>`).join("");
  document.getElementById("detail-content").innerHTML = `
    <div class="panel"><h2>${d.name} <span class="muted">(MAC ${d.mac})</span></h2>
      <table>${facts}</table></div>
    <div class="panel"><h3>Top providers by retina services (Medicare-visible)</h3>
      <table><tr><th>Name</th><th>NPI</th><th>Services</th></tr>${provs}</table></div>
    <div class="panel"><h3>Drug mix (services by product)</h3>
      <table><tr><th>Product</th><th>Services</th></tr>${drugs}</table></div>
    <div class="panel"><h3>Active trials</h3>
      <table><tr><th>NCT</th><th>Title</th><th>Site</th></tr>${trials || "<tr><td colspan=3>None found</td></tr>"}</table></div>
    <h3>Role actions</h3>${actions || "<p>No rules fired.</p>"}
    <div class="panel"><h3>Data gaps (require private data)</h3><ul>${gaps}</ul></div>`;
}

function renderMethods() {
  const m = state.meta;
  document.getElementById("methods-content").innerHTML = `
    <h2>Methods</h2>
    <p>Generated: ${m.generated}. ACS vintage: ${m.acs_vintage}.</p>
    <p>Dimension weights: ${Object.entries(m.weights).map(([k, v]) => `${k}=${v.toFixed(3)}`).join(", ")}</p>
    <p>Drug codes: ${Object.entries(m.drug_codes).map(([k, v]) => `${k} (${v})`).join("; ")}</p>
    <p>Procedure codes: ${Object.entries(m.procedure_codes).map(([k, v]) => `${k} (${v})`).join("; ")}</p>
    <p class="muted">${m.sources_note} CPT codes shown with neutral functional labels;
    descriptors are AMA-licensed. MUPPHY and Open Payments lag 1-2 years.
    Area-level measures are not individual patient attributes.</p>`;
}

function wireNav() {
  document.querySelectorAll("nav button").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("view-" + btn.dataset.view).classList.add("active");
      if (btn.dataset.view === "scorecards") renderScorecards();
      if (btn.dataset.view === "methods") renderMethods();
    });
  });
  const sel = document.getElementById("geo-select");
  sel.addEventListener("change", () => renderDetail(sel.value));
}

loadAll().then(() => {
  wireNav();
  renderMap();
  const sel = document.getElementById("geo-select");
  sel.innerHTML = state.cards.map(c => `<option value="${c.unit_id}">${c.name}</option>`).join("");
  if (state.cards.length) renderDetail(state.cards[0].unit_id);
});
```

- [ ] **Step 4: Serve and smoke-test with dev-browser**

Run (in `retina/pilot/dashboard/`): `python -m http.server 8765` (background).
Start the dev-browser server, then run a dev-browser script that:
1. Navigates to `http://localhost:8765`.
2. Asserts the page title and that `#map-chart` contains a rendered canvas.
3. Clicks each nav button and screenshots each view to `tmp/`.
4. Captures console messages; the run fails if any console errors appear.

Expected: all 4 views render with the real pilot data and zero console errors. The geojson `nameProperty`/fips join is the most likely breakage; if counties render gray, check that `map.json` fips values match the geojson feature `id` values (5-digit, zero-padded).

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/dashboard
git commit -m "feat: add static dashboard with map, scorecards, detail, methods views"
```

---

### Task 20: End-to-end run, QA review, and wrap-up

**Files:**
- Create: `retina/pilot/README.md`

- [ ] **Step 1: Full pipeline rerun from cache**

Run, in order:

```bash
uv run python -m retina_pilot.cli screen
uv run python -m retina_pilot.cli select
uv run python -m retina_pilot.cli deepdive
uv run python -m retina_pilot.cli score
uv run python -m retina_pilot.cli actions
uv run python -m retina_pilot.cli export
uv run pytest -q
```

Expected: all stages complete from cache in minutes; full test suite green.

- [ ] **Step 2: Substantive QA of the real outputs**

Check and record answers in the README (next step):
- Do the 10 selected geographies satisfy all constraints (4+ CBSAs, 3+ rural, 4+ MACs)?
- Is composite score spread non-degenerate (range > 20 points)?
- Does at least one rule fire for every geography? If a geography fires zero rules, tune one threshold in `rules.yaml` (commit the change with reasoning).
- Are biosimilar shares plausible (0-60% range, not all 0 or all 100)?
- Is `dashboard/data/` under 5 MB total?

- [ ] **Step 3: Write the README**

`retina/pilot/README.md`: short sections for purpose (link the spec), how to run (the 6 CLI stages + `pytest`), data sources with vintages observed in the run, MCD manual-download instructions, the QA answers from Step 2, and known limitations (copy the dashboard methods list).

- [ ] **Step 4: Final verification with dev-browser**

Re-run the Task 19 dev-browser smoke against the final data. Expected: 4 views, no console errors.

- [ ] **Step 5: Commit**

```bash
git add retina/pilot/README.md retina/pilot/src retina/pilot/dashboard
git commit -m "docs: add pilot README with run instructions and QA results"
```

---

## Self-review (completed at plan-writing time)

- **Spec coverage:** decisions 1-8 all map to tasks (raw public sources: Tasks 4-8, 12-14; mixed units: Task 9; national screen + constrained selection: Tasks 10-11; 7 dimensions + neutral policy fallback + equal weights: Task 16; rule-based actions with evidence citations: Task 17; static vendored dashboard with 4 views including methods panel: Tasks 18-19; QA assertions: Tasks 11, 20; dev-browser smoke per CLAUDE.md: Tasks 19-20; CPT licensing handling: codes.py neutral labels + methods note; MUPPHY suppression and lag limitations: export data gaps + methods).
- **Placeholders:** none; every code step contains full code.
- **Type consistency:** `unit_id`/`unit_type`/`unit_name`/`mac` flow from `geo_frame.assign_units` through `select_pilot`, `score_dimensions`, `write_dashboard_json`, and `app.js`; `fips`/`zip5`/`zcta` join keys consistent across ingest modules; `DIMENSIONS`/`WEIGHTS` defined once in `score/dimensions.py` and imported by the exporter.
