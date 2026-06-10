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


def pdc_query(dataset_id: str, conditions: list[tuple], limit: int = 1500) -> list[dict]:
    # PDC DKAN API enforces limit <= 1500 (HTTP 400 if exceeded).
    return _dkan_query(sources.URLS["pdc_datastore_query"], dataset_id, conditions, limit)


def openpayments_resolve(title_substring: str) -> str:
    """Resolve an Open Payments dataset by title substring.

    When multiple datasets match (e.g. year-prefixed "2023 General Payment Data",
    "2024 General Payment Data"), returns the one with the lexically-latest title
    so callers always get the most recent program year.
    """
    items = cached_json(sources.URLS["openpayments_metastore"])
    matches = [item for item in items
               if title_substring.strip().lower() in item.get("title", "").strip().lower()]
    if not matches:
        raise LookupError(f"Open Payments dataset not found: {title_substring}")
    # Pick the latest by title sort (year prefix makes lexical == chronological)
    best = max(matches, key=lambda item: item.get("title", ""))
    return best["identifier"]


def openpayments_query(dataset_id: str, conditions: list[tuple], limit: int = 2000) -> list[dict]:
    return _dkan_query(sources.URLS["openpayments_datastore_query"], dataset_id, conditions, limit)
