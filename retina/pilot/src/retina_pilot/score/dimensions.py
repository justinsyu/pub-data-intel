"""Seven dimension scorers (spec: Scoring). Percentile-ranked within the pilot pool, 0-100.

Equal weights across dimensions (spec decision); change WEIGHTS only.
"""
import pandas as pd

from retina_pilot import codes

DIMENSIONS = ["supply", "utilization", "drug_mix", "site_of_care", "policy", "trials_kol", "access_risk"]
WEIGHTS = {d: 1 / len(DIMENSIONS) for d in DIMENSIONS}

DRUG_CODES = set(codes.ALL_DRUG_HCPCS)
BIOSIM = set(codes.ANTIVEGF_BIOSIMILAR_HCPCS)
# MCD export article_id is the bare number ("52451"); codes.POLICY_ANCHOR_ARTICLE
# carries the display "A" prefix, so strip it before any anchor comparison.
_ANCHOR_BARE = codes.POLICY_ANCHOR_ARTICLE.removeprefix("A")


def _pct(series: pd.Series) -> pd.Series:
    if series.nunique() <= 1:
        return pd.Series(50.0, index=series.index)
    return (100 * series.rank(pct=True)).round(1)


def score_dimensions(selected, providers, ce_340b, trials, payments, affiliations, mcd_articles) -> pd.DataFrame:
    """Build per-unit scorecards: fact columns plus 7 dimension scores and a composite.

    `payments` is accepted but unused in scoring: Open Payments context is pulled at
    pool level (one specialty query across all pilot states), so it is effectively a
    constant that adds no between-unit signal. The parameter is kept in the signature
    for future per-NPI KOL weighting.
    """
    df = pd.DataFrame(selected)

    inj = providers[providers["hcpcs"] == "67028"].groupby("unit_id")["services"].sum()
    oct_ = providers[providers["hcpcs"] == "92134"].groupby("unit_id")["services"].sum()
    injectors = providers[providers["hcpcs"] == "67028"].groupby("unit_id")["npi"].nunique()
    drug = providers[providers["hcpcs"].isin(DRUG_CODES)]
    drug_services = drug.groupby("unit_id")["services"].sum()
    biosim_services = drug[drug["hcpcs"].isin(BIOSIM)].groupby("unit_id")["services"].sum()

    df["inj_services"] = df["unit_id"].map(inj).fillna(0)
    df["oct_services"] = df["unit_id"].map(oct_).fillna(0)
    df["injectors"] = df["unit_id"].map(injectors).fillna(0).astype(int)
    df["inj_per_1k_benes"] = (1000 * df["inj_services"] / df["medicare_benes"]).round(1)
    df["biosimilar_share_pct"] = (
        100 * df["unit_id"].map(biosim_services).fillna(0) / df["unit_id"].map(drug_services)
    ).fillna(0).round(1)

    # OPAIS daily export may be unavailable (loader returns an empty, unit-less frame).
    if ce_340b.empty or "unit_id" not in ce_340b.columns:
        df["ce_340b"] = 0
    else:
        ce_counts = ce_340b.groupby("unit_id").size()
        df["ce_340b"] = df["unit_id"].map(ce_counts).fillna(0).astype(int)

    hosp_npis = set(affiliations.loc[affiliations["facility_type"].str.contains(
        "Hospital", case=False, na=False), "npi"]) if not affiliations.empty else set()
    inj_by_unit = providers[providers["hcpcs"] == "67028"].groupby("unit_id")["npi"].agg(set)
    df["hosp_affil_share"] = df["unit_id"].map(
        lambda u: (len(inj_by_unit.get(u, set()) & hosp_npis) / len(inj_by_unit.get(u, set())))
        if len(inj_by_unit.get(u, set())) else 0.0)

    trial_counts = trials.groupby("unit_id")["nct_id"].nunique() if not trials.empty else pd.Series(dtype=int)
    df["trial_count"] = df["unit_id"].map(trial_counts).fillna(0).astype(int)

    # Dimension scores
    df["supply"] = _pct(df["injectors"] / df["pop65"] * 10000)
    df["utilization"] = _pct(df["inj_per_1k_benes"])
    df["drug_mix"] = _pct(df["biosimilar_share_pct"])
    df["site_of_care"] = _pct(df["ce_340b"].astype(float) + df["hosp_affil_share"])
    # Policy: the real MCD export carries no contractor/jurisdiction column (verified
    # against deepdive_mcd.parquet, 2026-06-10), so per-MAC attribution is not possible
    # from this data. Simplification: retina billing-and-coding articles (the A52451
    # anti-VEGF family) are adopted across MACs, so when retina articles exist
    # pool-wide every unit scores 75.0 (explicit billing guidance in place, not
    # unit-differentiating); 50.0 neutral when MCD data is not loaded.
    # policy_articles / policy_anchor_present / policy_last_update are kept as facts.
    if mcd_articles.empty:
        df["policy"] = 50.0  # neutral when MCD not loaded; data gap noted downstream
        df["policy_articles"] = 0
        df["policy_anchor_present"] = False
        df["policy_last_update"] = None
    else:
        df["policy_articles"] = len(mcd_articles)
        ids = mcd_articles["article_id"].astype(str).str.removeprefix("A")
        df["policy_anchor_present"] = bool((ids == _ANCHOR_BARE).any())
        df["policy"] = 75.0
        recency = pd.to_datetime(mcd_articles["last_updated"], errors="coerce").max()
        df["policy_last_update"] = str(recency.date()) if pd.notna(recency) else None
    df["trials_kol"] = _pct(df["trial_count"])
    df["access_risk"] = _pct(df["svi"].rank(pct=True) + df["ma_pct"].rank(pct=True) + df["rucc"].rank(pct=True))

    df["composite"] = sum(df[d] * w for d, w in WEIGHTS.items()).round(1)
    return df
