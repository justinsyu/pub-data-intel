# Retina Access Pilot

## Purpose

A six-stage pipeline that screens all US counties and CBSAs on public federal data, selects 10 pilot geographies for retina (anti-VEGF) market access work under diversity constraints, deep-dives each selection across supply, utilization, drug mix, site of care, policy, trials, and access risk, and renders the results as a static dashboard with rule-generated role actions. Design spec: [docs/superpowers/specs/2026-06-10-retina-access-pilot-design.md](../../docs/superpowers/specs/2026-06-10-retina-access-pilot-design.md). Implementation plan: [docs/superpowers/plans/2026-06-10-retina-access-pilot.md](../../docs/superpowers/plans/2026-06-10-retina-access-pilot.md).

## How to run

From `retina/pilot/`:

```
uv sync
uv run python -m retina_pilot.cli screen    # national county/CBSA screen
uv run python -m retina_pilot.cli select    # constrained selection of 10
uv run python -m retina_pilot.cli deepdive  # per-geography source pulls
uv run python -m retina_pilot.cli score     # 7 dimension scores + composite
uv run python -m retina_pilot.cli actions   # rule engine -> actions.json
uv run python -m retina_pilot.cli export    # dashboard JSON exports
uv run pytest -q                            # test suite (56 tests)
```

All HTTP responses are disk-cached under `data/cache/`, so reruns are incremental and fast (the full pipeline replays from cache in under 15 seconds). Outputs land in `data/out/` (parquet + JSON) and `dashboard/data/` (JSON).

The `duckdb` dependency is included for output inspection (querying the parquet files in `data/out/`); it is not used by the pipeline stages themselves.

To view the dashboard:

```
cd dashboard
python -m http.server 8765
```

Then open http://localhost:8765. The dashboard is fully static (no backend); it has 4 views: national map, scorecards, geography detail, and methods.

## Data sources and vintages

| Source | Provides | Access path | Vintage observed in this run |
|---|---|---|---|
| CMS Provider Data Catalog: DAC National Downloadable File and Facility Affiliations (NPPES-derived) | Provider specialty, location, hospital affiliations | PDC metastore + datastore query API | Current snapshot at run date (2026-06-10) |
| Medicare Physician & Other Practitioners by Provider and Service (MUPPHY) | Per-provider retina procedure and drug service volumes | data.cms.gov data-api, filtered by HCPCS | Latest version (dataset modified 2026-05-21; temporal coverage through 2024-12-31) |
| Medicare Monthly Enrollment | County Medicare beneficiary totals and MA penetration | data.cms.gov data-api, county-level annual rows | Latest release (modified 2026-05-21), most recent year retained |
| Medicare Part B Spending by Drug (QDD) | National spending and claims per HCPCS drug code | data.cms.gov data-api | 2023 (temporal 2023-01-01 to 2023-12-31) |
| Census population estimates | County population age 65+ | PEP 2023 county age-sex file (the ACS API requires a key; the keyless PEP fallback was used in this run) | Vintage 2023 estimates |
| NBER CBSA-county crosswalk | County to CBSA assignment | Static CSV | 2023 |
| CDC/ATSDR SVI | County social vulnerability index | Static CSV | 2022 |
| USDA ERS RUCC | Rural-urban continuum codes | Static CSV | 2023 |
| ClinicalTrials.gov API v2 | Active retina trial sites | REST API | Queried 2026-06-10 |
| Open Payments | Industry general payments to ophthalmologists | DKAN API, resolved by title to latest program year | 2024 General Payment Data |
| Medicare Coverage Database (MCD) | Retina-relevant LCDs and articles per MAC | Weekly current_article export (direct download) | Retrieved 2026-06-10; latest article update observed 2026-05-29 |
| HRSA 340B OPAIS | Covered entities (site-of-care signal) | Manual download required | Gap in this run (see below) |

Note: quarterly ASP drug pricing (the CMS Part B drug ASP files) was descoped from this phase; price context comes only from QDD spending. See known limitations.

## Manual-download notes

- **MCD**: the MCD website gates downloads behind a license click-through, but the weekly export zips on downloads.cms.gov respond without a session, so the pipeline now self-fetches the current article export. Operator override: place manually downloaded `current_article.zip` / `current_lcd.zip` into `data/cache/mcd/` and the loader uses them first.
- **HRSA 340B**: the OPAIS daily covered-entity export has no static URL (the report is generated per browser session). Download the covered-entity daily report from https://340bopais.hrsa.gov/reports into `data/cache/hrsa/` before the next deepdive run. In this run the loader returned an empty frame and the gap is recorded in each geography's data-gaps list.

## QA results (run of 2026-06-10)

1. **Selection constraints**: satisfied. The 10 selections contain 4 CBSAs, 6 rural counties (RUCC >= 4), 4 MAC jurisdictions (JF, JH, JJ, JM), and 10 unique unit ids. Selected geographies with screen scores: Talladega County, AL (83.6); Starr County, TX (83.2); Eagle Pass, TX CBSA (82.4); Santa Cruz County, AZ (82.2); Dallas County, AL (81.2); Lenoir County, NC (80.4); St. Mary Parish, LA (80.0); Brownsville-Harlingen, TX CBSA (78.3); McAllen-Edinburg-Mission, TX CBSA (78.3); El Paso, TX CBSA (77.8).
2. **Composite spread**: non-degenerate. Min 42.1 (St. Mary Parish, LA), max 81.4 (McAllen-Edinburg-Mission, TX), range 39.3 points (> 20).
3. **Rule coverage**: every geography fires at least one rule; minimum 2 (El Paso, TX), maximum 4 (Starr County, Eagle Pass, Lenoir County) of the 8 rules. Two rules never fire pool-wide: `ma_340b_concentration` requires ce_340b >= 3, but the HRSA 340B export was unavailable in this run, so ce_340b is 0 everywhere; `msl_no_trials_high_volume` requires trial_count == 0 and utilization >= 60, but in this pool every zero-trial geography has utilization 40 (no Medicare-visible injection volume) and every geography with utilization >= 60 has at least one trial site (firing `msl_trial_sites` instead).
4. **Biosimilar shares**: plausible; all values within 0-60. One nonzero value: El Paso, TX at 13.0 percent. The other nine geographies are 0.0 (seven have no Medicare-visible drug claims at all; Brownsville and McAllen have originator-only visible claims).
5. **Dashboard size**: under 5 MB. `dashboard/data/` totals 0.19 MB (map.json 165 KB, details.json 29 KB, scorecards.json 2.4 KB, meta.json 1.3 KB); the whole `dashboard/` directory including vendored ECharts (1.0 MB) and the US counties GeoJSON (3.2 MB) totals 4.25 MB.
6. **Stage notes**: both printed. Screen printed "CT excluded from screen pool: county-equivalent vintage mismatch across federal files (7 units, 9 counties excluded)". Deepdive printed "340B: no data; download the covered-entity daily report from https://340bopais.hrsa.gov/reports into data/cache/hrsa/".

## Known limitations

- **Connecticut excluded**: the 2020 ZCTA-county relationship file uses legacy CT county FIPS while the other federal files (gazetteer 2024, NBER crosswalk 2023, PEP 2023, SVI 2022, RUCC 2023, enrollment) use the 2022 planning-region FIPS, so CT provider counts cannot be joined correctly and CT is removed from the screen pool.
- **ZIP-to-ZCTA approximation**: provider ZIP codes are matched to ZCTAs by 5-digit equality; rural ZIPs without a same-numbered ZCTA can drop providers.
- **MUPPHY small-cell suppression**: rows with 10 or fewer beneficiaries are suppressed, which undercounts rural volumes; several selected counties show zero Medicare-visible injection services for this reason.
- **Data lag**: MUPPHY and Open Payments lag the present by 1-2 years.
- **Ecological measures**: SVI, MA penetration, and other area-level measures describe geographies, not individual providers or patients.
- **Commercial economics deferred**: payer machine-readable-file (MRF) processing is out of scope for this phase; commercial procedure economics appear as a recorded data gap.
- **ASP pricing deferred**: quarterly ASP drug pricing (the CMS Part B drug ASP files) was descoped from this phase; price context comes only from QDD national spending per HCPCS code. Ingesting the quarterly ASP files is an explicit deferred item.
- **Trials/KOL dimension is site-count only**: the trials_kol dimension currently uses trial-site counts only; investigator names are not extracted from ClinicalTrials.gov records, and Open Payments amounts are collected but not scored. Both are future enhancements.
- **Policy dimension is pool-constant**: all 10 geographies share the same MCD article counts at the jurisdiction level in this run (policy score 75.0 for all), pending per-MAC contractor-level differentiation.
