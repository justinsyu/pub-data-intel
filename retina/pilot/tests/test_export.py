import json

import pandas as pd

from retina_pilot.export import dashboard_json as dj


def test_export_writes_four_files(tmp_path):
    county_screen = pd.DataFrame({"fips": ["30033"], "unit_id": ["county:30033"],
                                  "screen_score": [88.0]})
    cards = pd.DataFrame([{"unit_id": "county:30033", "unit_name": "Garfield County, MT",
                           "mac": "JF", "composite": 71.0, "supply": 10.0, "utilization": 20.0,
                           "drug_mix": 50.0, "site_of_care": 50.0, "policy": 50.0,
                           "trials_kol": 50.0, "access_risk": 95.0, "injectors": 1,
                           "inj_services": 100.0, "biosimilar_share_pct": 0.0, "ce_340b": 0,
                           "trial_count": 0, "pop65": 300, "ma_pct": 10.0, "svi": 0.3, "rucc": 9}])
    providers = pd.DataFrame({"unit_id": ["county:30033"], "npi": ["1"], "last_name": ["A"],
                              "hcpcs": ["67028"], "services": [100.0], "benes": [40.0],
                              "avg_payment": [95.0], "state": ["MT"], "zip5": ["59032"],
                              "place_of_service": ["O"]})
    actions = {"county:30033": [{"rule_id": "x", "role": "msl", "action": "Do a thing.\n",
                                 "evidence": [{"metric": "trial_count", "value": 0}]}]}
    trials = pd.DataFrame(columns=["unit_id", "nct_id", "title", "facility", "city", "state", "zip5"])

    dj.write_dashboard_json(tmp_path, county_screen, cards, providers, trials, actions,
                            meta={"acs_vintage": "2023"})

    for f in ["map.json", "scorecards.json", "details.json", "meta.json"]:
        assert (tmp_path / f).exists(), f
    details = json.loads((tmp_path / "details.json").read_text())
    geo = details["county:30033"]
    assert geo["actions"][0]["role"] == "msl"
    assert geo["actions"][0]["action"] == "Do a thing."  # trailing newline stripped
    assert "data_gaps" in geo and any("MRF" in g for g in geo["data_gaps"])
