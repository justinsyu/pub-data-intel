import pandas as pd

from retina_pilot.score import dimensions as dim


def _selected():
    return [
        {"unit_id": "county:30033", "unit_name": "Garfield County, MT", "mac": "JF",
         "pop65": 300, "medicare_benes": 200, "ma_pct": 10.0, "svi": 0.3, "rucc": 9,
         "retina_providers": 0, "screen_score": 88.0, "unit_type": "county", "state": "MT"},
        {"unit_id": "cbsa:31080", "unit_name": "LA, CA", "mac": "JE",
         "pop65": 150000, "medicare_benes": 90000, "ma_pct": 55.0, "svi": 0.8, "rucc": 1,
         "retina_providers": 40, "screen_score": 72.0, "unit_type": "cbsa", "state": "CA"},
    ]


def _providers():
    return pd.DataFrame({
        "unit_id": ["cbsa:31080"] * 3,
        "npi": ["1", "1", "2"],
        "hcpcs": ["67028", "J0178", "Q5147"],
        "services": [500.0, 400.0, 100.0],
        "benes": [120.0, 100.0, 30.0],
        "avg_payment": [95.0, 900.0, 500.0],
        "place_of_service": ["O", "O", "O"],
    })


def test_scorecards_have_all_dimensions():
    cards = dim.score_dimensions(
        selected=_selected(),
        providers=_providers(),
        ce_340b=pd.DataFrame({"unit_id": ["cbsa:31080"], "ce_id": ["X"]}),
        trials=pd.DataFrame({"unit_id": ["cbsa:31080"], "nct_id": ["NCT01"], "facility": ["F"]}),
        payments=pd.DataFrame({"npi": ["1"], "amount": [5000.0]}),
        affiliations=pd.DataFrame({"npi": ["1"], "facility_type": ["Hospital"]}),
        mcd_articles=pd.DataFrame({"article_id": ["52451"], "contractor": ["Noridian JE"],
                                   "last_updated": ["2026-01-15"]}),
    )
    assert set(dim.DIMENSIONS) <= set(cards.columns)
    assert cards["composite"].between(0, 100).all()
    la = cards[cards.unit_id == "cbsa:31080"].iloc[0]
    mt = cards[cards.unit_id == "county:30033"].iloc[0]
    assert la["supply"] > mt["supply"]          # LA has providers, MT has none
    assert la["biosimilar_share_pct"] == 20.0   # 100 of 500 drug services
    # Real MCD exports carry no per-MAC contractor column; retina articles apply
    # pool-wide, so a non-empty article set scores 75.0 for every unit.
    assert (cards["policy"] == 75.0).all()
    assert cards["policy_anchor_present"].all()  # bare "52451" matches anchor "A52451"


def test_no_mcd_data_scores_neutral():
    cards = dim.score_dimensions(
        selected=_selected(), providers=_providers(),
        ce_340b=pd.DataFrame(columns=["unit_id", "ce_id"]),
        trials=pd.DataFrame(columns=["unit_id", "nct_id", "facility"]),
        payments=pd.DataFrame(columns=["npi", "amount"]),
        affiliations=pd.DataFrame(columns=["npi", "facility_type"]),
        mcd_articles=pd.DataFrame(columns=["article_id", "contractor", "last_updated"]),
    )
    assert (cards["policy"] == 50.0).all()
