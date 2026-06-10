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
    pages = {0: [{"a": 1}] * 3, 3: [{"a": 2}]}

    def fake_json(url, params=None):
        return pages[params["offset"]]

    monkeypatch.setattr(api, "cached_json", fake_json)
    rows = api.fetch_all("https://x/data", filters={"HCPCS_Cd": "67028"}, page_size=3)
    assert len(rows) == 4


def test_fetch_all_exact_multiple_terminates(monkeypatch):
    pages = {0: [{"a": 1}] * 3, 3: [{"a": 2}] * 3, 6: []}

    def fake_json(url, params=None):
        return pages[params["offset"]]

    monkeypatch.setattr(api, "cached_json", fake_json)
    rows = api.fetch_all("https://x/data", page_size=3)
    assert len(rows) == 6


def test_dkan_query_paginates(monkeypatch):
    payloads = {0: {"results": [{"npi": "1"}, {"npi": "2"}]}, 2: {"results": [{"npi": "3"}]}}

    def fake_json(url, params=None):
        assert url.endswith("/ds-id/0")
        return payloads[params["offset"]]

    monkeypatch.setattr(api, "cached_json", fake_json)
    rows = api._dkan_query("https://x/query", "ds-id", [("a", "=", "b")], limit=2)
    assert [r["npi"] for r in rows] == ["1", "2", "3"]


def test_pdc_conditions_built_correctly():
    params = api._pdc_params([("pri_spec", "=", "OPHTHALMOLOGY")], limit=10, offset=0)
    assert params["conditions[0][property]"] == "pri_spec"
    assert params["conditions[0][value]"] == "OPHTHALMOLOGY"
    assert params["conditions[0][operator]"] == "="
