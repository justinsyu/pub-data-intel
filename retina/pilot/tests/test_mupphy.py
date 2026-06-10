import retina_pilot.ingest.mupphy as mup


def test_parse_mupphy_rows():
    rows = [
        {"Rndrng_NPI": "111", "Rndrng_Prvdr_Last_Org_Name": "JONES",
         "Rndrng_Prvdr_State_Abrvtn": "CA", "Rndrng_Prvdr_Zip5": "90001",
         "HCPCS_Cd": "67028", "Tot_Srvcs": "250.0", "Tot_Benes": "60",
         "Avg_Mdcr_Pymt_Amt": "98.5", "Place_Of_Srvc": "O"},
    ]
    df = mup.parse_mupphy(rows)
    r = df.iloc[0]
    assert r["npi"] == "111"
    assert r["hcpcs"] == "67028"
    assert r["services"] == 250.0
    assert r["state"] == "CA"


def test_fetch_uses_one_filter_per_code(monkeypatch):
    seen = []

    def fake_fetch_all(url, filters=None, page_size=5000):
        seen.append(filters["HCPCS_Cd"])
        return []

    monkeypatch.setattr(mup.cms_api, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(mup.cms_api, "resolve_data_cms_dataset", lambda t: "https://x/data")
    mup.fetch_mupphy_by_hcpcs(["67028", "J0178"])
    assert seen == ["67028", "J0178"]
