import pandas as pd

from retina_pilot.transform import geo_frame


def _counties():
    return pd.DataFrame({
        "fips": ["06037", "01001", "30033"],
        "state": ["CA", "AL", "MT"],
        "county_name": ["Los Angeles County", "Autauga County", "Garfield County"],
    })


def _xwalk():
    return pd.DataFrame({
        "fips": ["06037", "01001"],
        "cbsa_code": ["31080", "33860"],
        "cbsa_title": ["Los Angeles-Long Beach-Anaheim, CA", "Montgomery, AL"],
        "metro_micro": ["Metropolitan Statistical Area", "Metropolitan Statistical Area"],
    })


def test_units_metro_county_rolls_to_cbsa():
    units = geo_frame.assign_units(_counties(), _xwalk())
    la = units[units.fips == "06037"].iloc[0]
    assert la["unit_id"] == "cbsa:31080"
    assert la["unit_type"] == "cbsa"


def test_units_nonmetro_county_stands_alone():
    units = geo_frame.assign_units(_counties(), _xwalk())
    garfield = units[units.fips == "30033"].iloc[0]
    assert garfield["unit_id"] == "county:30033"
    assert garfield["unit_type"] == "county"


def test_aggregate_to_units_weights_by_population():
    units = geo_frame.assign_units(_counties(), _xwalk())
    metrics = pd.DataFrame({
        "fips": ["06037", "01001", "30033"],
        "pop65": [1000, 100, 50],
        "svi": [0.9, 0.5, 0.2],
        "ma_pct": [50.0, 40.0, 10.0],
        "medicare_benes": [2000, 200, 80],
        "retina_providers": [30, 2, 0],
    })
    agg = geo_frame.aggregate_to_units(units, metrics)
    g = agg[agg.unit_id == "county:30033"].iloc[0]
    assert g["pop65"] == 50
    assert g["svi"] == 0.2


def test_aggregate_zero_pop65_guard():
    """Units with pop65==0 must not produce NaN or ZeroDivisionError for weighted cols."""
    units = geo_frame.assign_units(_counties(), _xwalk())
    metrics = pd.DataFrame({
        "fips": ["06037", "01001", "30033"],
        "pop65": [0, 0, 0],
        "svi": [0.9, 0.5, 0.2],
        "ma_pct": [50.0, 40.0, 10.0],
        "medicare_benes": [0, 0, 0],
        "retina_providers": [0, 0, 0],
    })
    agg = geo_frame.aggregate_to_units(units, metrics)
    # Both CBSA unit and county unit should exist; weighted cols should be NaN, not raise
    assert len(agg) > 0
    for col in ["svi", "ma_pct"]:
        assert agg[col].isna().all(), f"Expected NaN for {col} when pop65==0"


def test_assign_units_dedupes_duplicate_xwalk_rows():
    counties = _counties()
    xwalk = pd.concat([_xwalk(), _xwalk()], ignore_index=True)  # duplicated rows
    units = geo_frame.assign_units(counties, xwalk)
    assert len(units) == len(counties)
