import pandas as pd
import pytest

from mpdp_formulary.ingest import rxnorm


def conso(rows):
    return pd.DataFrame(rows, columns=["RXCUI", "SAB", "TTY", "STR", "SUPPRESS"])


def test_build_names_prefers_primary_tty():
    df = conso([
        ("100", "RXNORM", "IN", "drug ingredient", "N"),
        ("100", "RXNORM", "SCD", "drug 10 MG Tablet", "N"),
    ])
    out, rate = rxnorm.build_name_table(["100"], df, rxnav=None)
    assert rate == 1.0
    row = out.set_index("rxcui").loc["100"]
    assert row["name"] == "drug 10 MG Tablet"
    assert row["tty"] == "SCD"
    assert row["brand_generic"] == "generic"


def test_build_names_brand_flag():
    df = conso([("200", "RXNORM", "SBD", "Brandy 5 MG Tablet", "N")])
    out, _ = rxnorm.build_name_table(["200"], df, rxnav=None)
    assert out.set_index("rxcui").loc["200"]["brand_generic"] == "brand"


def test_build_names_ignores_suppressed_and_other_sab():
    df = conso([
        ("300", "RXNORM", "SCD", "suppressed name", "Y"),
        ("300", "MTHSPL", "SCD", "wrong source", "N"),
        ("300", "RXNORM", "IN", "fallback tty name", "N"),
    ])
    out, _ = rxnorm.build_name_table(["300"], df, rxnav=None)
    assert out.set_index("rxcui").loc["300"]["name"] == "fallback tty name"


def test_build_names_uses_rxnav_for_missing():
    df = conso([("100", "RXNORM", "SCD", "known", "N")])
    out, rate = rxnorm.build_name_table(
        ["100", "999"], df, rxnav=lambda rxcui: ("remapped name", "SCD")
    )
    assert rate == 1.0
    assert out.set_index("rxcui").loc["999"]["name"] == "remapped name"


def test_build_names_low_match_rate_raises():
    df = conso([("100", "RXNORM", "SCD", "known", "N")])
    with pytest.raises(ValueError, match="match rate"):
        rxnorm.build_name_table(
            [str(i) for i in range(100, 300)], df, rxnav=lambda rxcui: (None, "")
        )
