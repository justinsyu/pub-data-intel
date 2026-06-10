import io
import zipfile

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


def _make_article_zip() -> bytes:
    """Mimic the real MCD export: CSV tables nested in an inner *_csv.zip, latin-1 encoded."""
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr(
            "article.csv",
            "article_id,title,last_updated\n"
            "52451,Billing and Coding: Ranibizumab \x96 J0178,2026-01-15\n"
            "52369,Arthroscopy,2025-12-22\n".encode("latin-1"),
        )
        zf.writestr(
            "article_x_hcpc_code.csv",
            b"article_id,hcpc_code_id\n52451,J0178\n52369,29877\n",
        )
        zf.writestr(
            "article_x_hcpc_code_group.csv",
            b"article_id,hcpc_code_group\n52451,1\n",
        )
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as zf:
        zf.writestr("current_article_csv.zip", inner.getvalue())
        zf.writestr("readme_first.txt", b"see data dictionary")
    return outer.getvalue()


def test_load_parses_nested_csv_zip_latin1(tmp_path):
    (tmp_path / "current_article.zip").write_bytes(_make_article_zip())
    frames = mcd.load_mcd_retina(tmp_path)
    assert list(frames["articles"]["article_id"]) == ["52451"]


def test_load_handles_oversized_description_fields(tmp_path):
    """Real article.csv rows carry HTML blobs above the csv module's 128 KiB field limit."""
    big_field = "x" * 200_000
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr(
            "article.csv",
            "article_id,title,description,last_updated\n"
            f'52451,Billing and Coding: Ranibizumab,"{big_field}",2026-01-15\n'.encode("latin-1"),
        )
        zf.writestr("article_x_hcpc_code.csv", b"article_id,hcpc_code_id\n52451,J0178\n")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as zf:
        zf.writestr("current_article_csv.zip", inner.getvalue())
    (tmp_path / "current_article.zip").write_bytes(outer.getvalue())
    frames = mcd.load_mcd_retina(tmp_path)
    assert list(frames["articles"]["article_id"]) == ["52451"]


def test_load_downloads_when_requested(tmp_path, monkeypatch):
    payload = _make_article_zip()
    monkeypatch.setattr(mcd.http_cache, "cached_get", lambda url, params=None: payload)
    frames = mcd.load_mcd_retina(tmp_path, download=True)
    assert (tmp_path / "current_article.zip").exists()
    assert list(frames["articles"]["article_id"]) == ["52451"]
