"""Pipeline CLI. Stages: screen, select (Stage 1); deepdive, score, actions, export (Stage 2)."""
import argparse
import json
from pathlib import Path

import pandas as pd

from retina_pilot.ingest import area_context, census, enrollment, providers
from retina_pilot.score import screen as screen_score_mod
from retina_pilot.transform import geo_frame, select as select_mod

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "out"


def run_screen(outdir: Path = OUT_DIR) -> pd.DataFrame:
    outdir.mkdir(parents=True, exist_ok=True)
    counties = census.load_county_frame()
    xwalk = census.load_cbsa_xwalk()
    pop = census.load_pop65()
    svi = area_context.load_svi()
    rucc = area_context.load_rucc()
    enrl = enrollment.load_enrollment()
    provs = providers.load_ophth_providers()
    zcta = census.load_zcta_county()

    prov_county = provs.merge(zcta, left_on="zip5", right_on="zcta", how="left")
    prov_counts = (prov_county.dropna(subset=["fips"]).groupby("fips").size()
                   .rename("retina_providers").reset_index())

    metrics = (pop.merge(svi, on="fips", how="left")
                  .merge(rucc, on="fips", how="left")
                  .merge(enrl, on="fips", how="left")
                  .merge(prov_counts, on="fips", how="left"))
    metrics["retina_providers"] = metrics["retina_providers"].fillna(0).astype(int)

    # QA assertions (spec: pipeline QA)
    assert len(metrics) > 3000 or len(metrics) < 10, "unexpected county count"
    assert metrics["svi"].notna().mean() > 0.9 or len(metrics) < 10, "SVI join coverage below 90%"

    units = geo_frame.assign_units(counties, xwalk)
    unit_metrics = geo_frame.aggregate_to_units(units, metrics.dropna(subset=["pop65", "svi", "ma_pct"]))
    rucc_unit = units.merge(rucc, on="fips").groupby("unit_id")["rucc"].max().reset_index()
    unit_metrics = unit_metrics.merge(rucc_unit, on="unit_id", how="left")
    scored = screen_score_mod.score_screen(unit_metrics)

    county_screen = units.merge(metrics, on="fips", how="left").merge(
        scored[["unit_id", "screen_score"]], on="unit_id", how="left")
    county_screen.to_parquet(outdir / "county_screen.parquet", index=False)
    scored.to_parquet(outdir / "screen_scores.parquet", index=False)
    return scored


def run_select(outdir: Path = OUT_DIR) -> list[dict]:
    scored = pd.read_parquet(outdir / "screen_scores.parquet")
    picked = select_mod.select_pilot(scored, n=10)
    (outdir / "selected_10.json").write_text(json.dumps(picked, indent=2, default=str))
    return picked


def main():
    parser = argparse.ArgumentParser(prog="retina-pilot")
    parser.add_argument("stage", choices=["screen", "select", "deepdive", "score", "actions", "export"])
    args = parser.parse_args()
    stage = {"screen": run_screen, "select": run_select}.get(args.stage)
    if stage is None:
        raise SystemExit(f"stage not implemented yet: {args.stage}")
    stage()


if __name__ == "__main__":
    main()
