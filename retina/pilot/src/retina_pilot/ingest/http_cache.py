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
