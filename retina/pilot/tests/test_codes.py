from retina_pilot import codes


def test_drug_codes_cover_verified_products():
    assert {"J0178", "J0177", "J2778", "J2777", "J0179"} <= set(codes.ANTIVEGF_ORIGINATOR_HCPCS)
    assert {"Q5124", "Q5128", "Q5147"} <= set(codes.ANTIVEGF_BIOSIMILAR_HCPCS)
    assert {"J2781", "J2782"} <= set(codes.GA_COMPLEMENT_HCPCS)


def test_all_drug_codes_have_labels():
    for code in codes.ALL_DRUG_HCPCS:
        assert code in codes.DRUG_LABELS


def test_procedure_codes():
    assert "67028" in codes.PROCEDURE_HCPCS
    assert "92134" in codes.PROCEDURE_HCPCS


def test_taxonomy_codes():
    assert codes.TAXONOMY_OPHTHALMOLOGY == "207W00000X"
    assert codes.TAXONOMY_RETINA_SPECIALIST == "207WX0107X"


def test_mac_map_covers_50_states_plus_dc():
    states = {s for sts in codes.MAC_JURISDICTIONS.values() for s in sts}
    assert len(states & set(codes.ALL_STATES)) == 51


def test_state_to_mac_lookup():
    assert codes.state_to_mac("CA") == "JE"
    assert codes.state_to_mac("FL") == "JN"
    assert codes.state_to_mac("NY") == "JK"
