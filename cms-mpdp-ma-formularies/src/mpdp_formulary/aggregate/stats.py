"""Formulary-level and plan-level statistics."""
import pandas as pd


def formulary_order(formulary_drug: pd.DataFrame) -> list[str]:
    return sorted(formulary_drug["formulary_id"].unique())


def formulary_stats(formulary_drug: pd.DataFrame) -> pd.DataFrame:
    g = formulary_drug.groupby("formulary_id")
    out = pd.DataFrame({
        "n_drugs": g.size(),
        "pa_pct": g["pa"].mean() * 100,
        "st_pct": g["st"].mean() * 100,
        "ql_pct": g["ql"].mean() * 100,
    }).round(1)
    return out.reset_index()


def plan_stats(plan_dim: pd.DataFrame, form_stats: pd.DataFrame,
               excluded_raw: pd.DataFrame) -> pd.DataFrame:
    """plan_dim joined to its formulary's stats plus exclusion counts.

    Exclusions are keyed by contract+plan (no segment in the excluded file),
    so the count applies to every segment of that contract+plan.
    """
    excl = (
        excluded_raw.groupby(["CONTRACT_ID", "PLAN_ID"]).size()
        .rename("n_excluded").reset_index()
        .rename(columns={"CONTRACT_ID": "contract_id", "PLAN_ID": "plan_id"})
    )
    out = plan_dim.merge(form_stats, on="formulary_id", how="left")
    out = out.merge(excl, on=["contract_id", "plan_id"], how="left")
    out["n_excluded"] = out["n_excluded"].fillna(0).astype(int)
    return out
