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
    monkeypatch.setattr(cli.mcd, "load_mcd_retina", lambda d, download=False: {"articles": pd.DataFrame(
        {"article_id": ["52451"], "title": ["Anti-VEGF"], "contractor": ["Noridian JF"],
         "last_updated": ["2026-01-15"]})})

    cli.run_deepdive(outdir=tmp_path)
    assert (tmp_path / "deepdive_providers.parquet").exists()
    provs = pd.read_parquet(tmp_path / "deepdive_providers.parquet")
    assert provs.iloc[0]["unit_id"] == "county:30033"
