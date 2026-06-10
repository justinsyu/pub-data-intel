"""Compact JSON exports consumed by dashboard/app.js."""
import json
from pathlib import Path

import pandas as pd

from retina_pilot import codes
from retina_pilot.score.dimensions import DIMENSIONS, WEIGHTS

STANDING_DATA_GAPS = [
    "Commercial procedure economics deferred (payer MRF not processed in this phase).",
    "Patient-level laterality, visual acuity, OCT outcomes, persistence, and switching require claims/EHR/registry data.",
    "Net price, rebates, and acquisition cost are not observable in public files.",
    "MUPPHY suppresses provider rows with 10 or fewer beneficiaries; rural volumes are undercounted.",
    "340B covered-entity data unavailable by script (HRSA OPAIS has no static export URL); download manually for the next refresh.",
]


def write_dashboard_json(outdir: Path, county_screen: pd.DataFrame, cards: pd.DataFrame,
                         providers: pd.DataFrame, trials: pd.DataFrame, actions: dict,
                         meta: dict) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    map_rows = county_screen[["fips", "unit_id", "screen_score"]].dropna()
    selected_units = set(cards["unit_id"])
    map_payload = [
        {"fips": r.fips, "score": round(float(r.screen_score), 1),
         "selected": r.unit_id in selected_units}
        for r in map_rows.itertuples()
    ]
    (outdir / "map.json").write_text(json.dumps(map_payload))

    score_payload = [
        {"unit_id": r["unit_id"], "name": r["unit_name"], "mac": r["mac"],
         "composite": float(r["composite"]), "dims": {d: float(r[d]) for d in DIMENSIONS}}
        for _, r in cards.iterrows()
    ]
    (outdir / "scorecards.json").write_text(json.dumps(score_payload))

    details = {}
    for _, r in cards.iterrows():
        uid = r["unit_id"]
        prov = providers[providers["unit_id"] == uid]
        top = (prov.groupby(["npi", "last_name"])["services"].sum()
               .sort_values(ascending=False).head(15).reset_index())
        top["services"] = top["services"].astype(float)  # numpy scalars are not JSON-safe
        drug_mix = (prov[prov["hcpcs"].isin(codes.ALL_DRUG_HCPCS)]
                    .groupby("hcpcs")["services"].sum().to_dict())
        tr = trials[trials["unit_id"] == uid] if not trials.empty else trials
        unit_actions = [
            {**a, "action": str(a.get("action", "")).strip()}
            for a in actions.get(uid, [])
        ]
        details[uid] = {
            "name": r["unit_name"], "mac": r["mac"],
            "facts": {"pop65": int(r["pop65"]), "ma_pct": float(r["ma_pct"]),
                      "svi": float(r["svi"]), "rucc": int(r["rucc"]),
                      "injectors": int(r["injectors"]), "inj_services": float(r["inj_services"]),
                      "biosimilar_share_pct": float(r["biosimilar_share_pct"]),
                      "ce_340b": int(r["ce_340b"]), "trial_count": int(r["trial_count"])},
            "top_providers": top.to_dict("records"),
            "drug_mix": {codes.DRUG_LABELS.get(k, k): float(v) for k, v in drug_mix.items()},
            "trials": tr[["nct_id", "title", "facility", "city"]].to_dict("records") if not tr.empty else [],
            "actions": unit_actions,
            "data_gaps": list(STANDING_DATA_GAPS),
        }
    (outdir / "details.json").write_text(json.dumps(details))

    meta_payload = dict(meta, weights=WEIGHTS, dimensions=DIMENSIONS,
                        drug_codes=codes.DRUG_LABELS,
                        procedure_codes=codes.PROCEDURE_HCPCS)
    (outdir / "meta.json").write_text(json.dumps(meta_payload, indent=2))
