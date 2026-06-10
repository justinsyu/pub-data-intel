import retina_pilot.ingest.area_context as ac


def test_parse_svi():
    raw = b"FIPS,LOCATION,RPL_THEMES\n01001,\"Autauga, AL\",0.5432\n06037,\"LA, CA\",0.9211\n"
    df = ac.parse_svi(raw)
    assert list(df.columns) == ["fips", "svi"]
    assert df.loc[df.fips == "06037", "svi"].iloc[0] == 0.9211


def test_parse_svi_ignores_missing_flag():
    raw = b"FIPS,LOCATION,RPL_THEMES\n01001,X,-999\n"
    df = ac.parse_svi(raw)
    assert df.empty


def test_parse_rucc():
    raw = b'FIPS,State,County_Name,Attribute,Value\n01001,AL,Autauga,RUCC_2023,2\n01001,AL,Autauga,Population_2020,58805\n'
    df = ac.parse_rucc(raw)
    assert list(df.columns) == ["fips", "rucc"]
    assert df.iloc[0]["rucc"] == 2
