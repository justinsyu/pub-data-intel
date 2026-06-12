# MPDP Formulary Dashboard

Pipeline and static dashboard over the CMS Monthly Prescription Drug Plan
Formulary and Pharmacy Network Information PUF (snapshot 2026-05-31, contract
year 2026). Covers drug coverage by plan, excluded drugs, restrictions
(prior authorization, step therapy, quantity limits), tier cost sharing, and a
county coverage map. Pharmacy network files are out of scope in this version.

Design spec: ../docs/superpowers/specs/2026-06-11-mpdp-formulary-dashboard-design.md
Implementation plan: ../docs/superpowers/plans/2026-06-11-mpdp-formulary-dashboard.md

## How to run

    uv sync
    uv run pytest -q
    uv run python -m mpdp_formulary.cli all     # or: ingest|transform|aggregate|export
    uv run python -m http.server 8765 --directory dashboard
    # open http://localhost:8765

Source text files are expected in extracted/ (unzipped from the CMS release).
First ingest downloads the RxNorm Prescribable Content release and the Census
county file into data/cache/; reruns are offline and fast.

## Dashboard views

- Overview: market totals, tier mix, restriction prevalence, negotiation-
  selected drugs, exclusion summary.
- Drug explorer: search 6,156 drugs; per-drug coverage and restriction rates,
  tier placement, county map (share of plans covering, with or without
  restrictions), excluding plans, indication-based coverage.
- Plan explorer: filter 5,518 plans by type, SNP status, and state; per-plan
  premiums, deductibles, phase-by-phase tier cost sharing, insulin cost
  sharing (lesser of copay and coinsurance), excluded drugs, and a searchable
  formulary browser.
- Compare: 2 to 4 plans side by side, including tier costs (standard-network
  fallback) and shared exclusions.
- Methods: provenance, grain rules, caveats.

## Data sources

| Source | Vintage | Access |
|---|---|---|
| CMS MPDP Formulary PUF | 2026-05-31 | manual download, extracted/ |
| RxNorm Current Prescribable Content | current at first run | cached download |
| Census national_county2020.txt | 2020 | cached download |
| Plotly counties GeoJSON | 2010 boundaries | vendored, dashboard/vendor/ |

## QA results (2026-06-11 run)

- Tests: 48 passed.
- Ingest row counts: plan_info 112,294; basic 1,123,842; excluded 13,717;
  bene_cost 172,660; insulin 43,066; indication 367; geo 3,279.
- RxNorm name match rate: 1.0000 across 6,156 distinct RXCUIs.
- SSA-to-FIPS crosswalk match rate: 0.9835 (54 SSA codes unmapped, mostly
  Guam and American Samoa villages and dissolved jurisdictions).
- Plans: 5,518 (contracts: 691); plan-county bridge: 150,940 rows; 0 plans
  without counties.
- Formularies: 328; distinct RXCUIs in the basic file: 6,115; orphan
  formulary ID in plan info: 00026194 (one suppressed plan).
- Export: 6,156 drug shards (41 excluded-only drugs), 5,518 plan shards,
  328 formulary shards, geo.json with 3,223 FIPS-deduplicated counties;
  12,007 JSON files, 203.5 MB total; initial dashboard load ~1.0 MB.
- Spot checks: RXCUI 2392142 formulary count matches raw (328);
  plan H0028_007_000 tier 1 initial-coverage cost cells match the raw
  bene_cost row.
- Browser QA: all five views verified in Chromium; console free of
  application errors.

## Known limitations

- Single monthly snapshot; no trends.
- The basic formulary file carries one row per formulary and RXCUI with a
  single representative (proxy) NDC; restriction and tier displays are at
  RXCUI grain.
- Exclusions are contract-plan grain (no segment in the source file), so
  exclusion lists apply to every segment of a plan.
- County map: SSA-to-FIPS by state and county name; 54 SSA codes do not map.
  The vendored boundary file uses 2010 county definitions, so a few renamed
  or reorganized counties (e.g., Kusilvak AK, Oglala Lakota SD) and the
  territories render as no-data.
- Insulin cost panel shows the copay cap and coinsurance together; the
  beneficiary pays the lesser at point of sale.
- Suppressed plans (19) keep identity rows; cost data is hidden.
- Pharmacy networks (~22.5 GB) deferred; phase-2 candidates: preferred
  pharmacy density, dispensing fees, RxClass therapeutic class rollups.
