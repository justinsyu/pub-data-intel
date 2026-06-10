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
