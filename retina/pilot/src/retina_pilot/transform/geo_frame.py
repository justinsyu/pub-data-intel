"""Mixed geography units: metro counties roll up to CBSAs, non-metro counties stand alone."""
import pandas as pd

from retina_pilot import codes

METRO = "Metropolitan Statistical Area"


def assign_units(counties: pd.DataFrame, xwalk: pd.DataFrame) -> pd.DataFrame:
    df = counties.merge(xwalk, on="fips", how="left")
    is_metro = df["metro_micro"].eq(METRO)
    df["unit_id"] = "county:" + df["fips"]
    df.loc[is_metro, "unit_id"] = "cbsa:" + df.loc[is_metro, "cbsa_code"]
    df["unit_type"] = "county"
    df.loc[is_metro, "unit_type"] = "cbsa"
    df["unit_name"] = df["county_name"] + ", " + df["state"]
    df.loc[is_metro, "unit_name"] = df.loc[is_metro, "cbsa_title"]
    df["mac"] = df["state"].map(lambda s: codes.state_to_mac(s) if s in codes.ALL_STATES else None)
    return df[["fips", "state", "unit_id", "unit_type", "unit_name", "mac"]]


SUM_COLS = ["pop65", "medicare_benes", "retina_providers"]
WEIGHTED_COLS = ["svi", "ma_pct"]  # population-weighted by pop65


def aggregate_to_units(units: pd.DataFrame, county_metrics: pd.DataFrame) -> pd.DataFrame:
    df = units.merge(county_metrics, on="fips", how="inner")
    for c in WEIGHTED_COLS:
        df[f"_w_{c}"] = df[c] * df["pop65"]
    g = df.groupby(["unit_id", "unit_type", "unit_name"], as_index=False).agg(
        {**{c: "sum" for c in SUM_COLS}, **{f"_w_{c}": "sum" for c in WEIGHTED_COLS},
         "mac": lambda s: sorted(set(s.dropna()))[0] if s.notna().any() else None,
         "state": lambda s: ",".join(sorted(set(s)))}
    )
    for c in WEIGHTED_COLS:
        # Guard: replace 0 with NaN before dividing to avoid spurious zeros
        # (mirrors the pattern in enrollment.py: tot.replace(0, float("nan")))
        pop65_safe = g["pop65"].replace(0, float("nan"))
        g[c] = (g[f"_w_{c}"] / pop65_safe).round(4)
        g = g.drop(columns=f"_w_{c}")
    return g
