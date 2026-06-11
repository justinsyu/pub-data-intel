import pytest

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


def test_fetch_http_error_is_not_cached(tmp_path, monkeypatch):
    class ErrorResponse:
        content = b"server error page"

        def raise_for_status(self):
            raise RuntimeError("HTTP 500")

    monkeypatch.setattr(
        http_cache.requests, "get", lambda url, timeout: ErrorResponse()
    )
    with pytest.raises(RuntimeError):
        http_cache.fetch("https://example.org/err", tmp_path)
    assert list(tmp_path.iterdir()) == [], "failed response must not be cached"
