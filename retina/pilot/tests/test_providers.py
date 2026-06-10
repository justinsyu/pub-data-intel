import retina_pilot.ingest.providers as prov


def test_parse_dac_rows():
    rows = [
        {"npi": "1234567890", "provider_last_name": "SMITH", "provider_first_name": "ANN",
         "pri_spec": "OPHTHALMOLOGY", "state": "CA", "zip_code": "900011234",
         "facility_name": "RETINA MEDICAL GROUP"},
        {"npi": "1234567890", "provider_last_name": "SMITH", "provider_first_name": "ANN",
         "pri_spec": "OPHTHALMOLOGY", "state": "CA", "zip_code": "900011234",
         "facility_name": "SECOND LOCATION"},  # duplicate NPI collapses
    ]
    df = prov.parse_dac(rows)
    assert len(df) == 1
    assert df.iloc[0]["zip5"] == "90001"
    assert df.iloc[0]["npi"] == "1234567890"
