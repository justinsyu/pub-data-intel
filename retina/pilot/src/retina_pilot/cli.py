"""Pipeline CLI. Stages: screen, select (Stage 1); deepdive, score, actions, export (Stage 2)."""
import argparse
import json
from pathlib import Path

import pandas as pd

from retina_pilot import sources
from retina_pilot.codes import ALL_DRUG_HCPCS, PROCEDURE_HCPCS
from retina_pilot.ingest import area_context, census, deepdive_sources, enrollment, mcd, mupphy, providers
from retina_pilot.score import screen as screen_score_mod
from retina_pilot.transform import geo_frame, select as select_mod

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "out"
# sources.MCD_LOCAL_DIR is relative ("data/cache/mcd"); resolve against the pilot
# root (same parent as OUT_DIR), not the CWD, so the stage works from anywhere.
MCD_DIR = Path(__file__).resolve().parents[2] / sources.MCD_LOCAL_DIR


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

    # CT exclusion: the ZCTA-county relationship file (rel2020) encodes Connecticut using
    # legacy county FIPS (09001-09015), but all other federal files (gazetteer 2024, NBER
    # CBSA crosswalk 2023, PEP cc-est2023, SVI 2022, RUCC 2023, enrollment) use the 2022
    # planning-region FIPS (09110-09190). This vintage mismatch causes every CT provider
    # ZIP to map to a legacy FIPS that joins to nothing in the metrics table, making all
    # CT retina_providers = 0 regardless of actual supply. Excluding CT avoids selecting
    # pilot sites on an artifact. A proper fix requires a ZIP-to-planning-region crosswalk
    # that does not yet exist in this pipeline.
    ct_units = units[units["state"] == "CT"]["unit_id"].unique()
    print(
        f"CT excluded from screen pool: county-equivalent vintage mismatch across federal files "
        f"({len(ct_units)} units, {(units['state'] == 'CT').sum()} counties excluded)"
    )
    units_screen = units[units["state"] != "CT"]

    unit_metrics = geo_frame.aggregate_to_units(units_screen, metrics.dropna(subset=["pop65", "svi", "ma_pct"]))
    rucc_unit = units_screen.merge(rucc, on="fips").groupby("unit_id")["rucc"].max().reset_index()
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


def run_deepdive(outdir: Path = OUT_DIR) -> None:
    selected = json.loads((outdir / "selected_10.json").read_text())
    county_screen = pd.read_parquet(outdir / "county_screen.parquet")
    pilot_units = {s["unit_id"] for s in selected}
    pilot_counties = county_screen[county_screen["unit_id"].isin(pilot_units)][["fips", "unit_id"]]
    pilot_states = sorted({st for s in selected for st in s["state"].split(",")})

    zcta = census.load_zcta_county()
    zip_to_unit = zcta.merge(pilot_counties, on="fips")[["zcta", "unit_id"]]

    all_codes = list(PROCEDURE_HCPCS) + ALL_DRUG_HCPCS
    mup = mupphy.fetch_mupphy_by_hcpcs(all_codes)
    # zip5-to-ZCTA is an approximation (rural ZIP gaps can drop providers; known limitation per spec).
    mup = mup.merge(zip_to_unit, left_on="zip5", right_on="zcta", how="inner").drop(columns=["zcta"])
    mup.to_parquet(outdir / "deepdive_providers.parquet", index=False)

    deepdive_sources.load_qdd().to_parquet(outdir / "deepdive_qdd.parquet", index=False)

    ce = deepdive_sources.load_340b()
    if not ce.empty:  # loader returns an empty frame when no OPAIS export is available
        ce = ce.merge(zip_to_unit, left_on="zip5", right_on="zcta", how="inner").drop(columns=["zcta"])
    ce.to_parquet(outdir / "deepdive_340b.parquet", index=False)

    sites = deepdive_sources.parse_trial_sites(deepdive_sources.fetch_retina_studies())
    if not sites.empty:
        sites = sites.merge(zip_to_unit, left_on="zip5", right_on="zcta", how="inner").drop(columns=["zcta"])
    sites.to_parquet(outdir / "deepdive_trials.parquet", index=False)

    # Per-state pull kept: DKAN count probe (2026-06-10) showed ophthalmology general
    # payment volumes AL 2,677 / AZ 4,092 / LA 4,300 / NC 6,252 / TX 19,809; the max
    # (TX) is well under the ~50k threshold where per-NPI queries would be cheaper.
    pay = deepdive_sources.fetch_ophth_payments(pilot_states)
    pilot_npis = sorted(set(mup["npi"]))
    pay = pay[pay["npi"].isin(pilot_npis)]
    pay.to_parquet(outdir / "deepdive_payments.parquet", index=False)

    aff = deepdive_sources.fetch_affiliations(pilot_npis)
    aff.to_parquet(outdir / "deepdive_affiliations.parquet", index=False)

    mcd_frames = mcd.load_mcd_retina(MCD_DIR, download=True)
    mcd_frames["articles"].to_parquet(outdir / "deepdive_mcd.parquet", index=False)


def run_score(outdir: Path = OUT_DIR) -> pd.DataFrame:
    from retina_pilot.score import dimensions as dim
    selected = json.loads((outdir / "selected_10.json").read_text())
    cards = dim.score_dimensions(
        selected=selected,
        providers=pd.read_parquet(outdir / "deepdive_providers.parquet"),
        ce_340b=pd.read_parquet(outdir / "deepdive_340b.parquet"),
        trials=pd.read_parquet(outdir / "deepdive_trials.parquet"),
        payments=pd.read_parquet(outdir / "deepdive_payments.parquet"),
        affiliations=pd.read_parquet(outdir / "deepdive_affiliations.parquet"),
        mcd_articles=pd.read_parquet(outdir / "deepdive_mcd.parquet"),
    )
    cards.to_parquet(outdir / "scorecards.parquet", index=False)
    return cards


def run_actions(outdir: Path = OUT_DIR) -> None:
    from retina_pilot.actions import engine
    cards = pd.read_parquet(outdir / "scorecards.parquet")
    rules = engine.load_rules()
    all_actions = {row["unit_id"]: engine.generate_actions(row.to_dict(), rules)
                   for _, row in cards.iterrows()}
    (outdir / "actions.json").write_text(json.dumps(all_actions, indent=2))


def run_export(outdir: Path = OUT_DIR) -> None:
    from datetime import date
    from retina_pilot.export import dashboard_json as dj
    dash_data = Path(__file__).resolve().parents[2] / "dashboard" / "data"
    dj.write_dashboard_json(
        dash_data,
        county_screen=pd.read_parquet(outdir / "county_screen.parquet"),
        cards=pd.read_parquet(outdir / "scorecards.parquet"),
        providers=pd.read_parquet(outdir / "deepdive_providers.parquet"),
        trials=pd.read_parquet(outdir / "deepdive_trials.parquet"),
        actions=json.loads((outdir / "actions.json").read_text()),
        meta={"generated": str(date.today()), "acs_vintage": "Census PEP 2023 county age-sex estimates (ACS API fallback)",
              "sources_note": "All data from official public sources; see the project spec for the registry. "
                              "Screen score averages four equal-weighted percentile ranks: population 65 and over, "
                              "SVI, MA penetration, and inverse retina-provider supply. The trials and KOL dimension "
                              "counts active trial sites only; investigator and industry-payment signals are not yet scored."},
    )


def main():
    parser = argparse.ArgumentParser(prog="retina-pilot")
    parser.add_argument("stage", choices=["screen", "select", "deepdive", "score", "actions", "export"])
    args = parser.parse_args()
    stage = {"screen": run_screen, "select": run_select, "deepdive": run_deepdive,
             "score": run_score, "actions": run_actions, "export": run_export}.get(args.stage)
    if stage is None:
        raise SystemExit(f"stage not implemented yet: {args.stage}")
    stage()


if __name__ == "__main__":
    main()
