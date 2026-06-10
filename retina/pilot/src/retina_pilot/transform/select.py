"""Greedy diverse selection of the 10 pilot geographies (spec: selection constraints)."""
import pandas as pd

MIN_CBSA = 4
MIN_RURAL = 3
MIN_MACS = 4


def select_pilot(scored: pd.DataFrame, n: int = 10) -> list[dict]:
    pool = scored.sort_values("screen_score", ascending=False, kind="mergesort").to_dict("records")
    picked: list[dict] = []

    def counts():
        types = [p["unit_type"] for p in picked]
        return types.count("cbsa"), types.count("county"), {p["mac"] for p in picked if p["mac"] is not None}

    for row in pool:
        if len(picked) == n:
            break
        n_cbsa, n_rural, macs = counts()
        remaining = n - len(picked)
        need_cbsa = max(0, MIN_CBSA - n_cbsa)
        need_rural = max(0, MIN_RURAL - n_rural)
        need_macs = max(0, MIN_MACS - len(macs))
        if row["unit_type"] == "cbsa" and remaining - need_rural <= 0:
            continue  # must save room for rural counties
        if row["unit_type"] == "county" and remaining - need_cbsa <= 0:
            continue  # must save room for CBSAs
        if need_macs >= remaining and row["mac"] in macs:
            continue  # must save room for new MAC jurisdictions
        picked.append(row)

    n_cbsa, n_rural, macs = counts()
    assert len(picked) == n, f"selection incomplete: {len(picked)}"
    assert n_cbsa >= MIN_CBSA and n_rural >= MIN_RURAL and len(macs) >= MIN_MACS, (
        f"constraints unmet: cbsa={n_cbsa} rural={n_rural} macs={len(macs)}"
    )
    return picked
