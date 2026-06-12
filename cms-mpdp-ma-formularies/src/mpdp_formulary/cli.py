"""Stage orchestrator. Usage: python -m mpdp_formulary.cli [stage]

Stages: ingest, transform, aggregate, export, all (default).
"""
import argparse

import duckdb
import pandas as pd

from . import layouts
from .aggregate import stats, status_vectors
from .export import dashboard_json
from .ingest import crosswalk, raw_files, rxnorm
from .transform import drugs as drugs_mod
from .transform import plans as plans_mod

TRANSFORM_BOUNDS = {"n_formularies": (200, 500), "n_drugs": (2_000, 50_000)}


def _pq(name: str) -> str:
    return (layouts.OUT_DIR / f"{name}.parquet").as_posix()


def _con_with_raw() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for key in layouts.LAYOUTS:
        con.execute(
            f"CREATE VIEW raw_{key} AS SELECT * FROM read_parquet('{_pq('raw_' + key)}')"
        )
    return con


def stage_ingest() -> None:
    raw_files.load_all(layouts.RAW_DIR, layouts.OUT_DIR)
    con = _con_with_raw()
    rxcuis = [r[0] for r in con.execute(
        """
        SELECT DISTINCT RXCUI FROM raw_basic
        UNION SELECT DISTINCT RXCUI FROM raw_excluded
        UNION SELECT DISTINCT RXCUI FROM raw_indication
        """
    ).fetchall()]
    conso = rxnorm.load_rxnconso(layouts.CACHE_DIR)
    names, rate = rxnorm.build_name_table(
        rxcuis, conso, rxnav=lambda r: rxnorm.rxnav_lookup(r, layouts.CACHE_DIR))
    names.to_parquet(layouts.OUT_DIR / "rxcui_names.parquet", index=False)
    print(f"ingest: rxnorm names for {len(names):,} RXCUIs, match rate {rate:.4f}")
    geo = con.execute("SELECT COUNTY_CODE, STATENAME, COUNTY FROM raw_geo").df()
    xwalk, xrate = crosswalk.build(
        geo, crosswalk.fetch_census_counties(layouts.CACHE_DIR))
    xwalk.to_parquet(layouts.OUT_DIR / "ssa_fips.parquet", index=False)
    print(f"ingest: ssa-fips crosswalk match rate {xrate:.4f}")


def stage_transform() -> None:
    con = _con_with_raw()
    plans_mod.build(con)
    dstats = drugs_mod.build(con)
    for metric, (lo, hi) in TRANSFORM_BOUNDS.items():
        if not lo <= dstats[metric] <= hi:
            raise ValueError(
                f"transform: {metric}={dstats[metric]} outside [{lo}, {hi}]")
    for t in ("plan_dim", "plan_county", "formulary_drug", "drug_dim"):
        con.execute(f"COPY {t} TO '{_pq(t)}' (FORMAT PARQUET)")
    orphans = con.execute(
        """
        SELECT DISTINCT formulary_id FROM plan_dim
        WHERE formulary_id NOT IN (SELECT formulary_id FROM formulary_drug)
        """
    ).fetchall()
    print(f"transform: {len(orphans)} formulary id(s) in plan info absent "
          f"from basic file: {[o[0] for o in orphans]}")


def stage_aggregate() -> None:
    con = duckdb.connect()
    fd = con.execute(f"SELECT * FROM read_parquet('{_pq('formulary_drug')}')").df()
    order = stats.formulary_order(fd)
    vectors = status_vectors.build_vectors(fd, order)
    vectors.to_parquet(layouts.OUT_DIR / "vectors.parquet", index=False)
    fs = stats.formulary_stats(fd)
    fs.to_parquet(layouts.OUT_DIR / "formulary_stats.parquet", index=False)
    plan_dim = con.execute(f"SELECT * FROM read_parquet('{_pq('plan_dim')}')").df()
    excluded = con.execute(
        f"SELECT * FROM read_parquet('{_pq('raw_excluded')}')").df()
    ps = stats.plan_stats(plan_dim, fs, excluded)
    ps.to_parquet(layouts.OUT_DIR / "plan_stats.parquet", index=False)
    pd.DataFrame({"formulary_id": order}).to_parquet(
        layouts.OUT_DIR / "formulary_order.parquet", index=False)
    print(f"aggregate: {len(vectors):,} vectors of length {len(order)}, "
          f"{len(ps):,} plan stats rows")


def stage_export() -> None:
    out = layouts.DASH_DATA_DIR
    con = duckdb.connect()

    def rd(name: str) -> pd.DataFrame:
        return con.execute(f"SELECT * FROM read_parquet('{_pq(name)}')").df()

    names = rd("rxcui_names")
    fd = rd("formulary_drug")
    drug_dim = rd("drug_dim")
    order = list(rd("formulary_order")["formulary_id"])
    vectors = rd("vectors")
    bridge = rd("plan_county")
    xwalk = rd("ssa_fips")
    raw = {k: rd(f"raw_{k}")
           for k in ("excluded", "indication", "bene_cost", "insulin", "geo")}

    # Plans index, sorted by plan_key; row position is the index used by geo.json.
    plans_sorted = rd("plan_stats").sort_values("plan_key").reset_index(drop=True)
    fidx = {fid: i for i, fid in enumerate(order)}
    plans_sorted["formulary_idx"] = plans_sorted["formulary_id"].map(
        lambda f: fidx.get(f, -1))
    geo_states = raw["geo"][["COUNTY_CODE", "STATENAME"]].copy()
    geo_states["state"] = geo_states["STATENAME"].map(crosswalk.state_abbrev)
    cs = bridge.merge(geo_states, left_on="county_code", right_on="COUNTY_CODE")
    states_map = (cs.dropna(subset=["state"]).groupby("plan_key")["state"]
                  .agg(lambda s: sorted(set(s))))
    plans_sorted["states"] = plans_sorted["plan_key"].map(states_map).apply(
        lambda v: v if isinstance(v, list) else [])
    pidx_df = plans_sorted.rename(columns={
        "plan_type": "type", "suppressed_yn": "suppressed"})
    dashboard_json.write_plans_index(out, pidx_df)

    # Drugs index. Excluded-only RXCUIs (absent from the basic file) still get
    # rows so the explorer can surface them; their vectors are all '-'.
    excl = raw["excluded"].copy()
    excl["contract_plan"] = excl["CONTRACT_ID"] + "_" + excl["PLAN_ID"]
    excl_counts = excl.groupby("RXCUI")["contract_plan"].nunique()
    di = drug_dim.merge(names, on="rxcui", how="left")
    di["name"] = di["name"].fillna("(unnamed) " + di["rxcui"])
    di["bg"] = di["brand_generic"].fillna("")
    di["cov_pct"] = (di["n_formularies"] / len(order) * 100).round(1)
    for c in ("pa", "st", "ql"):
        di[f"{c}_pct"] = (di[f"n_{c}"] / di["n_formularies"] * 100).round(1)
    di["excl_plans"] = di["rxcui"].map(excl_counts).fillna(0).astype(int)
    di["ndc_count"] = di["ndc_total"]
    di["n_form"] = di["n_formularies"]
    extra_ids = sorted(set(excl_counts.index) - set(di["rxcui"]))
    if extra_ids:
        extra = pd.DataFrame({"rxcui": extra_ids}).merge(names, "left", "rxcui")
        extra["name"] = extra["name"].fillna("(unnamed) " + extra["rxcui"])
        extra["bg"] = extra["brand_generic"].fillna("")
        extra = extra.assign(ndc_count=0, n_form=0, cov_pct=0.0, pa_pct=None,
                             st_pct=None, ql_pct=None, selected=False)
        extra["excl_plans"] = extra["rxcui"].map(excl_counts).astype(int)
        di = pd.concat([di[dashboard_json.DRUGS_INDEX_COLS],
                        extra[dashboard_json.DRUGS_INDEX_COLS]])
    di = di.sort_values("name").reset_index(drop=True)
    dashboard_json.write_drugs_index(out, di)
    missing_vec = sorted(set(di["rxcui"]) - set(vectors["rxcui"]))
    if missing_vec:
        vectors = pd.concat([vectors, pd.DataFrame(
            {"rxcui": missing_vec, "vector": ["-" * len(order)] * len(missing_vec)})])

    # Named exclusion and indication frames shared by drug and plan shards.
    cp_names = (plans_sorted
                .assign(cp=plans_sorted["contract_id"] + "_" + plans_sorted["plan_id"])
                .drop_duplicates("cp").set_index("cp")["plan_name"])
    ex = excl.merge(names[["rxcui", "name"]], left_on="RXCUI",
                    right_on="rxcui", how="left")
    ex["plan_name"] = ex["contract_plan"].map(cp_names)
    ex["tier"] = pd.to_numeric(ex["TIER"], errors="coerce")
    # The excluded file mixes flag conventions: QL is 0/1, PA/ST/capped are Y/N.
    ex["pa"] = ex["PRIOR_AUTH_YN"].isin(["Y", "1"])
    ex["st"] = ex["STEP_THERAPY_YN"].isin(["Y", "1"])
    ex["ql"] = ex["QUANTITY_LIMIT_YN"].isin(["Y", "1"])
    ex["capped"] = ex["CAPPED_BENEFIT_YN"].isin(["Y", "1"])
    ex["ql_amount"] = ex["QUANTITY_LIMIT_AMOUNT"].str.strip().replace("", None)
    ex["ql_days"] = ex["QUANTITY_LIMIT_DAYS"].str.strip().replace("", None)
    ind = raw["indication"].copy()
    ind["contract_plan"] = ind["CONTRACT_ID"] + "_" + ind["PLAN_ID"]
    ind = ind.merge(names[["rxcui", "name"]], left_on="RXCUI",
                    right_on="rxcui", how="left")
    ind["disease"] = ind["DISEASE"]

    n = dashboard_json.write_drug_shards(
        out, di[["rxcui", "name", "bg", "selected"]], vectors,
        fd[["formulary_id", "rxcui", "tier", "ql_amount", "ql_days"]], ex, ind)
    print(f"export: {n:,} drug shards")

    costs = raw["bene_cost"].copy()
    costs["plan_key"] = (costs["CONTRACT_ID"] + "_" + costs["PLAN_ID"]
                         + "_" + costs["SEGMENT_ID"])
    ins = raw["insulin"].copy()
    ins["plan_key"] = (ins["CONTRACT_ID"] + "_" + ins["PLAN_ID"]
                       + "_" + ins["SEGMENT_ID"])
    n = dashboard_json.write_plan_shards(
        out, list(plans_sorted["plan_key"]), costs, ins, ex, ind)
    print(f"export: {n:,} plan shards")

    fdn = fd.merge(names[["rxcui", "name", "brand_generic"]], on="rxcui", how="left")
    fdn["bg"] = fdn["brand_generic"].fillna("")
    fdn["name"] = fdn["name"].fillna("(unnamed) " + fdn["rxcui"])
    n = dashboard_json.write_formulary_shards(out, fdn)
    print(f"export: {n} formulary shards")

    g = (raw["geo"][["COUNTY_CODE", "STATENAME", "COUNTY"]]
         .merge(xwalk, left_on="COUNTY_CODE", right_on="county_code"))
    n_unmapped = int(g["fips"].isna().sum())
    g = g.dropna(subset=["fips"]).copy()
    g["state"] = g["STATENAME"].map(crosswalk.state_abbrev)
    pix = {pk: i for i, pk in enumerate(plans_sorted["plan_key"])}
    bplans = bridge.groupby("county_code")["plan_key"].agg(
        lambda s: sorted(pix[k] for k in set(s) if k in pix))
    g["plans"] = g["COUNTY_CODE"].map(bplans).apply(
        lambda v: v if isinstance(v, list) else [])
    g = g.rename(columns={"COUNTY": "name"})
    g = (g.groupby("fips", as_index=False)
         .agg(name=("name", "first"), state=("state", "first"),
              plans=("plans", lambda s: sorted(set().union(*s)))))
    dashboard_json.write_geo(out, g[["fips", "name", "state", "plans"]])
    print(f"export: geo.json with {len(g):,} counties "
          f"({n_unmapped} SSA codes unmapped to FIPS)")

    tier_mix = fd.groupby("tier").size().reset_index(name="n").dropna()
    sel = di[di["selected"].astype(bool)]
    overview = {
        "tier_mix": [{"tier": int(t), "n": int(c)}
                     for t, c in tier_mix.sort_values("tier").values],
        "restrictions": {f"{c}_pct": round(float(fd[c].mean() * 100), 1)
                         for c in ("pa", "st", "ql")},
        "exclusions": {"rows": int(len(raw["excluded"])),
                       "distinct_rxcuis": int(raw["excluded"]["RXCUI"].nunique()),
                       "n_contract_plans": int(excl["contract_plan"].nunique())},
        "plan_types": [{"type": t, "n": int(c)} for t, c in
                       plans_sorted.groupby("plan_type").size().items()],
        "snp": [{"snp": s, "n": int(c)} for s, c in
                plans_sorted.groupby("snp").size().items()],
        "selected_drugs": [{"rxcui": r.rxcui, "name": r.name,
                            "n_formularies": int(r.n_form)}
                           for r in sel.itertuples()],
    }
    dashboard_json.write_overview(out, overview)
    meta = {
        "vintage": layouts.VINTAGE,
        "contract_year": layouts.CONTRACT_YEAR,
        "formulary_order": order,
        "counts": {"plans": int(len(plans_sorted)),
                   "contracts": int(plans_sorted["contract_id"].nunique()),
                   "formularies": len(order),
                   "drugs": int(len(di))},
        "snp_labels": {"0": "Not a SNP",
                       "1": "Chronic or disabling condition SNP",
                       "2": "Dual-eligible SNP", "3": "Institutional SNP"},
        "coverage_level_labels": {"0": "Pre-deductible", "1": "Initial coverage",
                                  "3": "Catastrophic"},
        "days_supply_labels": {"1": "30-day", "2": "90-day", "3": "Other",
                               "4": "60-day"},
        "plan_type_labels": {"MA": "Medicare Advantage (local)",
                             "MA_REGIONAL": "Medicare Advantage (regional)",
                             "PDP": "Stand-alone PDP", "OTHER": "Other"},
    }
    dashboard_json.write_meta(out, meta)
    n_files = sum(1 for _ in out.rglob("*.json"))
    total = sum(f.stat().st_size for f in out.rglob("*.json"))
    print(f"export: {n_files:,} JSON files, {total / 1e6:.1f} MB total")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=["ingest", "transform", "aggregate", "export", "all"])
    args = parser.parse_args(argv)
    stages = {"ingest": stage_ingest, "transform": stage_transform,
              "aggregate": stage_aggregate, "export": stage_export}
    for name in (list(stages) if args.stage == "all" else [args.stage]):
        print(f"=== {name} ===")
        stages[name]()


if __name__ == "__main__":
    main()
