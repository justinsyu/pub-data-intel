# MPDP Formulary Dashboard: Design

Date: 2026-06-11
Status: Approved
Project root: `cms-mpdp-ma-formularies/`

## Purpose

A static dashboard over the CMS Monthly Prescription Drug Plan Formulary and Pharmacy Network Information PUF (May 2026 snapshot, contract year 2026) that lets users understand:

- Drug coverage by plan: which drugs a plan's formulary covers, at which tier, at what cost sharing.
- Excluded drugs: which drugs plans exclude and under what residual terms.
- Restrictions: prevalence and detail of prior authorization (PA), step therapy (ST), and quantity limits (QL) per drug and per plan.

Two primary lenses, both in scope: drug-centric (for a given drug, how restrictive is coverage across the market) and plan-centric (for a given plan, what does its formulary look like). Tier-level beneficiary cost sharing and a county map are in scope for v1.

## Source data

All files are pipe-delimited with a header row, extracted to `cms-mpdp-ma-formularies/extracted/`. Counts are from the 2026-05-31 release.

| File | Rows | Grain | Key facts |
|---|---|---|---|
| Plan information | 112,294 | contract x plan x segment x county | 691 contracts, 329 formulary IDs, premium, deductible, SNP type, PLAN_SUPPRESSED_YN; Latin-1 encoded |
| Basic drugs formulary | 1,123,842 | formulary x RXCUI x NDC | 328 formulary IDs; tier 1 to 7; PA 28.3%, ST 1.1%, QL 38.8% of rows; SELECTED_DRUG_YN flag |
| Excluded drugs formulary | 13,717 | contract x plan x RXCUI | 44 distinct RXCUIs, 270 contracts; tier, QL, PA, ST, capped-benefit flags |
| Beneficiary cost | 172,660 | plan x coverage level x tier x days supply | copay or coinsurance by retail/mail, preferred/standard |
| Insulin beneficiary cost | 43,066 | plan x tier x days supply | insulin copay/coinsurance by channel |
| Indication-based coverage | 367 | contract x plan x RXCUI x disease | 3 contracts, 12 indications |
| Geographic locator | 3,279 | SSA county code | state, county name, MA region, PDP region |
| Pharmacy networks | ~22.5 GB unzipped | plan x pharmacy | out of scope for v1; remains zipped |

Join keys: plan info to basic formulary via FORMULARY_ID; plan info to cost, insulin, excluded, and indication files via CONTRACT_ID + PLAN_ID (+ SEGMENT_ID where present); geography via COUNTY_CODE (H contracts) or MA/PDP region code (R/S contracts) against the geographic locator.

Observed data-versus-PDF discrepancies (data wins, encoded in tests): QUANTITY_LIMIT_YN, PRIOR_AUTHORIZATION_YN, STEP_THERAPY_YN, SELECTED_DRUG_YN carry Y/N values, not 0/1; CONTRACT_NAME and PLAN_NAME are populated, not suppressed. Plan info contains 329 formulary IDs versus 328 in the basic formulary file; the orphan is identified and reported during QA.

## Architecture

Chosen approach: staged Python pipeline producing pre-computed JSON consumed by a fully static dashboard. This follows the `retina/pilot` conventions (uv, staged CLI, DuckDB/parquet, vendored ECharts, `python -m http.server`).

The size constraint that makes both lenses and the map feasible statically: there are only 328 formularies, so any drug's market-wide coverage reduces to a 328-entry status vector, and county aggregation happens client-side from a county-to-plan index instead of pre-computing drug x county matrices.

```
extracted/*.txt + RxNorm + SSA-FIPS crosswalk
        |  ingest (validate layouts, load DuckDB, cache reference data)
        v
data/out/*.parquet (typed dims and facts)
        |  transform (plan dim, plan-county bridge, drug dim at RXCUI grain)
        |  aggregate (status vectors, per-formulary/plan/national stats)
        v
dashboard/data/*.json (+ sharded drugs/, plans/, formularies/)
        |  static fetch
        v
dashboard/index.html + app.js + vendored ECharts (5 views)
```

### Project layout

```
cms-mpdp-ma-formularies/
  pyproject.toml              # uv; pandas, duckdb, pyarrow, requests, pytest (dev)
  .gitignore                  # source zip, extracted/, data/cache/, data/out/, dashboard/data/
  README.md                   # run instructions, data vintage, QA results, limitations
  src/mpdp_formulary/
    cli.py                    # stages: ingest, transform, aggregate, export (run-all default)
    layouts.py                # expected headers and dtypes per file; single source of truth
    ingest/
      raw_files.py            # locate + header-validate + load extracted txt into DuckDB
      rxnorm.py               # RxNorm Prescribable Content download (cached), RxNav fallback
      crosswalk.py            # SSA-to-FIPS county crosswalk (cached download)
    transform/
      plans.py                # plan dim (contract+plan+segment), plan-county bridge
      drugs.py                # RXCUI-grain drug dim; NDC-to-RXCUI aggregation
    aggregate/
      status_vectors.py       # per-drug 328-formulary coded status
      stats.py                # formulary, plan, and national aggregates
    export/
      dashboard_json.py       # all JSON writers
  data/
    cache/                    # RxNorm release, crosswalk, RxNav responses (gitignored)
    out/                      # parquet intermediates (gitignored)
  dashboard/
    index.html
    app.js
    vendor/echarts.min.js
    data/                     # JSON exports (gitignored)
  tests/
    fixtures/                 # small pipe-delimited extracts per file type
    test_*.py
```

## Components

### Ingest

- `layouts.py` declares the exact expected header for each of the seven in-scope files; ingest fails loudly on any mismatch so a future monthly drop with a changed layout cannot silently corrupt outputs.
- Plan information is read as Latin-1; all others as UTF-8.
- RxNorm: download the Current Prescribable Content release (free subset, no UMLS license) to `data/cache/`, build an RXCUI -> {name, TTY} table. TTY maps to a brand/generic flag (SCD, GPCK generic; SBD, BPCK brand). RXCUIs not found (retired/remapped) resolve via the RxNav REST API with disk caching; final name match rate must be >= 99% of distinct RXCUIs or the stage fails with a report of the unmatched residue.
- SSA-to-FIPS: COUNTY_CODE in the plan and geographic files is an SSA code, not FIPS. Ingest a published SSA-to-FIPS crosswalk (cached download; NBER or equivalent). QA reports the match rate; unmatched counties render as no-data on the map and are listed in the QA output.

### Transform

- Plan dim: dedupe the 112k county-level plan info rows to one record per CONTRACT_ID + PLAN_ID + SEGMENT_ID with contract/plan names, type (MA local H, MA regional R, PDP S, derived from contract prefix), SNP type, premium, deductible, FORMULARY_ID, PLAN_SUPPRESSED_YN.
- Plan-county bridge: H contracts map directly from their county rows; R and S contracts expand region codes to member counties via the geographic locator. The bridge drives the map and the county filter.
- Drug dim: aggregate basic formulary NDC rows to RXCUI grain. A restriction flag is set for a (formulary, RXCUI) if any of its NDCs carries the flag; tier is the modal tier across NDCs with min/max retained; NDC count retained. Display names from RxNorm.

### Aggregate

- Status vectors: for each RXCUI, a 328-character string in fixed formulary order. Each character encodes one formulary's status as a hex digit of a 4-bit mask (bit 0 covered, bit 1 PA, bit 2 ST, bit 3 QL), with `-` for not listed. Exclusions are plan-level (CONTRACT_ID + PLAN_ID), not formulary-level, so they are not in the vector; they are carried as a per-drug list of excluding plans.
- Per-formulary stats: drug count, tier histogram, PA/ST/QL rates.
- Per-plan stats: formulary stats joined via FORMULARY_ID, plus exclusion count, cost-sharing table, insulin cost table, indication-based coverage records.
- National overview stats: plan/contract/formulary/drug counts, restriction prevalence, tier mix, selected-drug (negotiation program) list.

### Export (JSON contracts)

| File | Contents | Approx size |
|---|---|---|
| `meta.json` | data vintage, file dates, counts, code labels, formulary order (array of 328 formulary IDs defining vector positions) | small |
| `overview.json` | national stats and chart series | small |
| `drugs_index.json` | one row per RXCUI: name, brand/generic, NDC count, coverage % (share of the 328 formularies listing the RXCUI), PA/ST/QL rates among listing formularies, excluding-plan count, selected-drug flag | ~1-3 MB |
| `drugs/{rxcui}.json` | status vector, per-formulary tier, QL amount/days detail, excluding plans with residual terms, indication-based coverage | ~1-3 KB each |
| `plans_index.json` | one row per plan: ids, names, type, SNP, premium, deductible, formulary ID, suppressed flag, summary stats | ~1-2 MB |
| `plans/{contract}_{plan}_{segment}.json` | cost-sharing table (coverage level x tier x days supply x channel), insulin costs, excluded drugs with names, indication coverage | small each |
| `formularies/{formulary_id}.json` | full drug table for the plan formulary browser: rxcui, name, tier, PA/ST/QL, QL detail | ~330 files, 100-400 KB each |
| `geo.json` | per county: FIPS, name, plan keys serving it (from the bridge) | ~1-3 MB |

Initial dashboard load fetches only `meta.json`, `overview.json`, and the two index files; everything else is lazy.

## Dashboard views

Single-page `index.html` + `app.js` with nav buttons, matching the retina dashboard pattern. Global filters where applicable: plan type (MA local / MA regional / PDP), SNP type, state/county.

1. **Overview**: headline counts (plans, contracts, formularies, distinct drugs); tier mix bar chart; restriction prevalence (PA 28.3%, QL 38.8%, ST 1.1% of formulary rows as the starting frame, recomputed per filter); exclusion summary; selected-drugs panel for the negotiation program.
2. **Drug explorer**: searchable drug table from `drugs_index.json` (name, coverage %, restriction rates, exclusion count); selecting a drug loads its shard and renders: coverage and restriction summary, tier distribution across formularies, county map (share of plans serving each county whose formulary covers the drug without PA/ST/QL; metric toggle: covered at all / unrestricted), and a formulary-level table linking to plans.
3. **Plan explorer**: filterable plan table from `plans_index.json`; selecting a plan loads its shard plus its formulary shard and renders: plan facts (type, SNP, premium, deductible, suppressed badge), formulary stats, tier cost-sharing table (coverage phase x days supply x retail/mail x preferred/standard, copay vs coinsurance formatted correctly), insulin cost panel, excluded drugs list, and a searchable formulary browser.
4. **Compare**: pick 2 to 4 plans; side-by-side columns of formulary breadth, restriction rates, tier costs, premium/deductible, exclusion counts, and exclusion overlap.
5. **Methods**: data vintage and provenance, file definitions, join logic, caveats: proxy NDCs, RXCUI aggregation rule, suppressed plans, SSA-FIPS mapping, exclusion semantics (plan-level), single-month snapshot, pharmacy networks out of scope.

## Error handling

- Every stage carries QA assertions that fail loudly: header mismatches, row-count bounds, join coverage (e.g., every plan FORMULARY_ID resolves or is reported), null-rate ceilings, RxNorm match rate >= 99%, crosswalk match rate reported.
- Suppressed plans (PLAN_SUPPRESSED_YN = Y) remain in indexes with a badge; their cost panels show a suppression notice instead of numbers.
- Client code treats missing shards as a rendered error state, not a blank page.

## Testing

- pytest with small fixtures per source file type exercising ingest validation, NDC-to-RXCUI aggregation logic, status-vector encoding, region-to-county expansion, and JSON export shapes.
- Encoded regression tests for the data-versus-PDF discrepancies (Y/N flags, populated names).
- Final manual verification of all five views in a browser (dev-browser per repo convention), including one drug and one plan spot-checked end to end against the raw files.

## Out of scope (v1)

- Pharmacy network files (phase-2 candidate: preferred pharmacy density, dispensing fees).
- Therapeutic class rollups via RxClass (phase-2 candidate).
- Multi-month trend analysis (single snapshot only).
- Any server-side runtime.
