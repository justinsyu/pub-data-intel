import retina_pilot.ingest.deepdive_sources as dd


def test_parse_qdd_keeps_retina_drugs():
    rows = [
        {"HCPCS_Cd": "J0178", "HCPCS_Desc": "x", "Tot_Spndng": "3000000000", "Tot_Clms": "1000"},
        {"HCPCS_Cd": "J9999", "HCPCS_Desc": "y", "Tot_Spndng": "1", "Tot_Clms": "1"},
    ]
    df = dd.parse_qdd(rows)
    assert list(df["hcpcs"]) == ["J0178"]


def test_parse_340b(tmp_path):
    raw = (b"Entity Type,340B ID,Entity Name,Participating,State,Zip Code\n"
           b"HOSP,ABC123,GENERAL HOSPITAL,TRUE,CA,90001\n"
           b"HOSP,DEF456,PAST HOSPITAL,FALSE,CA,90002\n")
    df = dd.parse_340b(raw)
    assert len(df) == 1  # non-participating dropped
    assert df.iloc[0]["zip5"] == "90001"


def test_parse_trials_extracts_us_sites():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT01", "briefTitle": "Wet AMD study"},
            "statusModule": {"overallStatus": "RECRUITING"},
            "contactsLocationsModule": {"locations": [
                {"facility": "Retina Inst", "city": "Los Angeles", "state": "California",
                 "country": "United States", "zip": "90001"},
                {"facility": "EU Site", "city": "Paris", "country": "France"},
            ]},
        }
    }
    sites = dd.parse_trial_sites([study])
    assert len(sites) == 1
    assert sites.iloc[0]["nct_id"] == "NCT01"
    assert sites.iloc[0]["zip5"] == "90001"


def test_parse_open_payments():
    rows = [{"covered_recipient_npi": "111", "covered_recipient_specialty_1":
             "Allopathic & Osteopathic Physicians|Ophthalmology|Retina Specialist",
             "total_amount_of_payment_usdollars": "150.25",
             "recipient_state": "CA"}]
    df = dd.parse_open_payments(rows)
    assert df.iloc[0]["amount"] == 150.25
