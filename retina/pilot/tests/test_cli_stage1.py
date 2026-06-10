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


def test_run_screen_excludes_ct(tmp_path, monkeypatch, capsys):
    """CT counties must be excluded from screen_scores due to ZCTA-rel vintage mismatch."""
    counties = pd.DataFrame({
        "fips": ["06037", "09170", "09150"],
        "state": ["CA", "CT", "CT"],
        "county_name": ["Los Angeles County", "New Haven Planning Region", "Northeastern CT"],
        "lat": [34.0, 41.3, 41.9], "lon": [-118.0, -72.9, -72.0],
    })
    xwalk = pd.DataFrame({"fips": ["06037"], "cbsa_code": ["31080"],
                          "cbsa_title": ["LA, CA"], "metro_micro": ["Metropolitan Statistical Area"]})
    pop = pd.DataFrame({"fips": ["06037", "09170", "09150"],
                        "pop_total": [1000000, 570000, 97000], "pop65": [150000, 109000, 20000]})
    svi = pd.DataFrame({"fips": ["06037", "09170", "09150"], "svi": [0.8, 0.66, 0.24]})
    rucc = pd.DataFrame({"fips": ["06037", "09170", "09150"], "rucc": [1, 2, 4]})
    enrl = pd.DataFrame({"fips": ["06037", "09170", "09150"],
                         "medicare_benes": [90000, 122000, 23000],
                         "ma_benes": [45000, 73000, 13000], "ma_pct": [50.0, 60.0, 59.0]})
    provs = pd.DataFrame({"npi": ["1"], "state": ["CA"], "zip5": ["90001"]})
    zcta = pd.DataFrame({"zcta": ["90001"], "fips": ["06037"]})

    monkeypatch.setattr(cli.census, "load_county_frame", lambda: counties)
    monkeypatch.setattr(cli.census, "load_cbsa_xwalk", lambda: xwalk)
    monkeypatch.setattr(cli.census, "load_pop65", lambda: pop)
    monkeypatch.setattr(cli.census, "load_zcta_county", lambda: zcta)
    monkeypatch.setattr(cli.area_context, "load_svi", lambda: svi)
    monkeypatch.setattr(cli.area_context, "load_rucc", lambda: rucc)
    monkeypatch.setattr(cli.enrollment, "load_enrollment", lambda: enrl)
    monkeypatch.setattr(cli.providers, "load_ophth_providers", lambda: provs)

    out = cli.run_screen(outdir=tmp_path)
    # CT units must not appear in screen_scores
    ct_in_scores = [r for r in out.to_dict("records") if r.get("state") == "CT"]
    assert len(ct_in_scores) == 0, f"CT units leaked into screen_scores: {ct_in_scores}"
    # CT rows ARE still present in county_screen (for reference), but not scored for selection
    county_screen = pd.read_parquet(tmp_path / "county_screen.parquet")
    ct_rows = county_screen[county_screen["state"] == "CT"]
    assert len(ct_rows) == 2  # CT counties present but not scored
    # Exclusion notice must be printed
    captured = capsys.readouterr()
    assert "CT excluded" in captured.out
