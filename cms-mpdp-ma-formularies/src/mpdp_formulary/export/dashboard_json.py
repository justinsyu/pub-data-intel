"""Writers for all dashboard/data JSON artifacts. Shapes documented in the plan
and consumed by dashboard/js. Index files are {"cols": [...], "rows": [[...]]}.
"""
import json
import math
from pathlib import Path

import pandas as pd

DRUGS_INDEX_COLS = ["rxcui", "name", "bg", "ndc_count", "n_form", "cov_pct",
                    "pa_pct", "st_pct", "ql_pct", "excl_plans", "selected"]
PLANS_INDEX_COLS = ["plan_key", "contract_name", "plan_name", "type", "snp",
                    "premium", "deductible", "formulary_idx", "suppressed",
                    "n_drugs", "pa_pct", "st_pct", "ql_pct", "n_excluded",
                    "states"]
EXCLUDED_COLS = ["rxcui", "name", "tier", "pa", "st", "ql", "ql_amount",
                 "ql_days", "capped"]
EXCLUDED_BY_COLS = ["contract_plan", "plan_name", "tier", "pa", "st", "ql",
                    "ql_amount", "ql_days", "capped"]
FORMULARY_COLS = ["rxcui", "name", "bg", "tier", "pa", "st", "ql", "ql_amount",
                  "ql_days", "selected"]
GEO_COLS = ["fips", "name", "state", "plans"]
CHANNELS = ["PREF", "NONPREF", "MAIL_PREF", "MAIL_NONPREF"]
CHANNEL_KEYS = ["pref", "nonpref", "mail_pref", "mail_nonpref"]


def _clean(v):
    if v is None or v is pd.NA:
        return None
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (pd.Timestamp,)):
        return str(v)
    if hasattr(v, "item"):  # numpy scalar
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False),
                    encoding="utf-8")


def _rows(df: pd.DataFrame, cols: list[str]) -> list[list]:
    return [[_clean(v) for v in row] for row in df[cols].itertuples(index=False)]


def write_meta(out_dir: Path, meta: dict) -> None:
    _write(out_dir / "meta.json", meta)


def write_overview(out_dir: Path, overview: dict) -> None:
    _write(out_dir / "overview.json", overview)


def write_drugs_index(out_dir: Path, df: pd.DataFrame) -> None:
    _write(out_dir / "drugs_index.json",
           {"cols": DRUGS_INDEX_COLS, "rows": _rows(df, DRUGS_INDEX_COLS)})


def write_plans_index(out_dir: Path, df: pd.DataFrame) -> None:
    _write(out_dir / "plans_index.json",
           {"cols": PLANS_INDEX_COLS, "rows": _rows(df, PLANS_INDEX_COLS)})


def write_drug_shards(out_dir: Path, drugs: pd.DataFrame, vectors: pd.DataFrame,
                      formulary_drug: pd.DataFrame, excluded: pd.DataFrame,
                      indications: pd.DataFrame) -> int:
    """drugs: rxcui, name, bg, selected. vectors: rxcui, vector.
    formulary_drug: formulary_id, rxcui, tier, ql_amount, ql_days.
    excluded: contract_plan, plan_name, rxcui, tier, pa, st, ql, ql_amount,
    ql_days, capped. indications: contract_plan, rxcui, disease.
    """
    vec = vectors.set_index("rxcui")["vector"]
    fd_g = {k: g for k, g in formulary_drug.groupby("rxcui")}
    ex_g = {k: g for k, g in excluded.groupby("rxcui")} if len(excluded) else {}
    in_g = {k: g for k, g in indications.groupby("rxcui")} if len(indications) else {}
    n = 0
    for row in drugs.itertuples():
        fid_map = {}
        for f in fd_g.get(row.rxcui, pd.DataFrame()).itertuples():
            fid_map[f.formulary_id] = [_clean(f.tier), _clean(f.ql_amount),
                                       _clean(f.ql_days)]
        ex = ex_g.get(row.rxcui)
        ind = in_g.get(row.rxcui)
        obj = {
            "rxcui": row.rxcui,
            "name": row.name,
            "bg": row.bg,
            "selected": bool(row.selected),
            "vector": vec.get(row.rxcui, ""),
            "formularies": fid_map,
            "excluded_by": {
                "cols": EXCLUDED_BY_COLS,
                "rows": _rows(ex, EXCLUDED_BY_COLS) if ex is not None else [],
            },
            "indications": (
                [{"contract_plan": r.contract_plan, "disease": r.disease}
                 for r in ind.itertuples()] if ind is not None else []
            ),
        }
        _write(out_dir / "drugs" / f"{row.rxcui}.json", obj)
        n += 1
    return n


def write_plan_shards(out_dir: Path, plan_keys: list[str], costs: pd.DataFrame,
                      insulin: pd.DataFrame, excluded: pd.DataFrame,
                      indications: pd.DataFrame) -> int:
    """costs/insulin carry a plan_key column plus the raw uppercase PUF columns
    (VARCHAR; numeric parsing happens here). excluded must carry contract_plan,
    plan_name, AND name plus the drug columns: plan shards emit name via
    EXCLUDED_COLS while drug shards emit plan_name via EXCLUDED_BY_COLS.
    indications carry contract_plan, rxcui, name, disease.
    """
    def num(v):
        if isinstance(v, float) and math.isnan(v):
            return None
        v = (v or "").strip() if isinstance(v, str) else v
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    cost_g = {k: g for k, g in costs.groupby("plan_key")}
    ins_g = {k: g for k, g in insulin.groupby("plan_key")}
    ex_g = {k: g for k, g in excluded.groupby("contract_plan")} if len(excluded) else {}
    in_g = {k: g for k, g in indications.groupby("contract_plan")} if len(indications) else {}
    n = 0
    for pk in plan_keys:
        cp = "_".join(pk.split("_")[:2])  # contract_plan prefix
        cost_rows = []
        for r in cost_g.get(pk, pd.DataFrame()).itertuples():
            channels = {}
            for ch_key, ch in zip(CHANNEL_KEYS, CHANNELS):
                channels[ch_key] = [
                    num(getattr(r, f"COST_TYPE_{ch}")),
                    num(getattr(r, f"COST_AMT_{ch}")),
                    num(getattr(r, f"COST_MIN_AMT_{ch}")),
                    num(getattr(r, f"COST_MAX_AMT_{ch}")),
                ]
            cost_rows.append({
                "level": num(r.COVERAGE_LEVEL), "tier": num(r.TIER),
                "days": num(r.DAYS_SUPPLY),
                "specialty": _clean(r.TIER_SPECIALTY_YN),
                "ded_applies": _clean(r.DED_APPLIES_YN), "channels": channels,
            })
        ins_rows = []
        for r in ins_g.get(pk, pd.DataFrame()).itertuples():
            ins_rows.append({
                "tier": num(r.TIER), "days": num(r.DAYS_SUPPLY),
                "copay": [num(getattr(r, f"COPAY_AMT_{ch}_INSLN")) for ch in CHANNELS],
                "coin": [num(getattr(r, f"COIN_AMT_{ch}_INSLN")) for ch in CHANNELS],
            })
        ex = ex_g.get(cp)
        ind = in_g.get(cp)
        obj = {
            "plan_key": pk,
            "costs": cost_rows,
            "insulin": ins_rows,
            "excluded": {"cols": EXCLUDED_COLS,
                         "rows": _rows(ex, EXCLUDED_COLS) if ex is not None else []},
            "indications": (
                [{"rxcui": r.rxcui, "name": r.name, "disease": r.disease}
                 for r in ind.itertuples()] if ind is not None else []
            ),
        }
        _write(out_dir / "plans" / f"{pk}.json", obj)
        n += 1
    return n


def write_formulary_shards(out_dir: Path, formulary_drug_named: pd.DataFrame) -> int:
    n = 0
    for fid, g in formulary_drug_named.groupby("formulary_id"):
        _write(out_dir / "formularies" / f"{fid}.json",
               {"formulary_id": fid, "cols": FORMULARY_COLS,
                "rows": _rows(g.sort_values("name"), FORMULARY_COLS)})
        n += 1
    return n


def write_geo(out_dir: Path, geo: pd.DataFrame) -> None:
    _write(out_dir / "geo.json",
           {"cols": GEO_COLS, "rows": _rows(geo, GEO_COLS)})
