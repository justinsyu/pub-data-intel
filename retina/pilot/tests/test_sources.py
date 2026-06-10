from retina_pilot import sources


def test_all_sources_are_https():
    for name, url in sources.URLS.items():
        assert url.startswith("https://"), name


def test_expected_sources_present():
    expected = {
        "census_gazetteer_counties", "nber_cbsa_xwalk", "census_acs5",
        "census_zcta_county_rel", "cdc_svi_county", "usda_rucc",
        "cms_data_json", "pdc_metastore", "clinicaltrials_v2",
        "openpayments_metastore", "hrsa_340b_ce",
        "pdc_datastore_query", "openpayments_datastore_query",
    }
    assert set(sources.URLS) == expected
