"""Disk-cached HTTP GET. All network access in this package goes through fetch()."""
import hashlib
import os
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
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(resp.content)
    os.replace(tmp, path)
    return resp.content
