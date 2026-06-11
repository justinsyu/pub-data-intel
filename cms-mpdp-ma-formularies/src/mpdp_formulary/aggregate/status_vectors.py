"""Per-drug formulary status vectors.

One character per formulary at its formulary_order position: '-' = not listed,
else lowercase hex of (1 | 2*PA | 4*ST | 8*QL). '1' is covered unrestricted.
"""
import pandas as pd


def encode_status(pa: bool, st: bool, ql: bool) -> str:
    return format(1 | (2 if pa else 0) | (4 if st else 0) | (8 if ql else 0), "x")


def build_vectors(formulary_drug: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    idx = {fid: i for i, fid in enumerate(order)}
    chars: dict[str, list[str]] = {}
    for row in formulary_drug.itertuples():
        vec = chars.setdefault(row.rxcui, ["-"] * len(order))
        vec[idx[row.formulary_id]] = encode_status(
            bool(row.pa), bool(row.st), bool(row.ql))
    return pd.DataFrame(
        {"rxcui": list(chars), "vector": ["".join(v) for v in chars.values()]}
    )
