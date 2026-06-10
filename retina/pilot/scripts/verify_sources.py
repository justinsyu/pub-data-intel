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
