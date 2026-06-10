# Design: Retina Access and Evidence Action Pilot (Wet AMD)

Date: 2026-06-10
Status: Approved
Source requirement: "Best First Deliverable" section of `retina/mimilabs_data_catalog_opportunity_map.html`

## Purpose

Build a 10-geography "retina access and evidence action" pilot for wet AMD and adjacent retinal diseases. The pilot tests whether public data alone can generate account-level hypotheses worth validating with claims, registry, EHR, hub, or payer-policy data. Outputs serve three roles: MSL, Medical Affairs, and Market Access.

## Decisions (confirmed with user)

1. Data access: raw public downloads and public APIs only. No Mimilabs subscription; every source is an official government file or established public dataset.
2. Geographic unit: mixed. Urban geographies are CBSAs (metro areas); rural geographies are counties.
3. Geography selection: data-driven national screen with diversity constraints selects the 10 geographies.
4. Output: interactive dashboard (static, no backend) plus the scored datasets.
5. Scope: 7 scoring dimensions. Commercial payer MRF rates are deferred to a later phase and recorded as an explicit data gap per geography. Coverage-policy friction stays in scope via the Medicare Coverage Database.
6. Stack: Python + DuckDB pipeline; static-hosted JS dashboard (vendored ECharts, no CDN, no server).
7. Role-specific actions: deterministic rule-based generation. Every generated statement cites the metrics that triggered it.
8. Architecture: API-filtered staged pipeline (Approach A). Stage 1 screens nationally with small files and filtered API pulls; Stage 2 deep-dives only the 10 selected geographies. All API responses cached to disk.

## Architecture

New project directory: `retina/pilot/`

```
retina/pilot/
  pyproject.toml              # uv-managed Python project
  src/retina_pilot/
    cli.py                    # stages: screen, select, deepdive, score, actions, export
    codes.py                  # verified retina code sets (single source of truth)
    ingest/                   # one module per source; disk-cached HTTP
    transform/                # joins, geography frame, metric builders
    score/                    # dimension scorers + composite
    actions/                  # rule engine + rules.yaml
    export/                   # dashboard JSON writers
  data/
    cache/                    # raw API responses and downloads (gitignored)
    out/                      # versioned pipeline outputs (parquet/csv)
  dashboard/
    index.html
    app.js
    vendor/echarts.min.js     # vendored, no CDN
    data/*.json               # compact exports, written by export stage
  tests/
    fixtures/                 # small static source extracts
    test_*.py
  docs/
```

Pipeline principles:

- Each stage reads only prior-stage outputs plus cache; stages are re-runnable and idempotent.
- Every HTTP response is cached to `data/cache/` keyed by URL + query; re-runs hit cache.
- Every output records source vintage metadata (file release date, HCPCS quarter, ICD-10 year, ACS vintage).
- Data QA assertions (row counts, null rates, join coverage thresholds) run inside the pipeline and fail loudly.

## Verified code sets (from the opportunity map review, 2026-06-10)

- Wet AMD diagnosis: ICD-10-CM `H35.32-` family (laterality + activity staging). Adjacent: `H35.31-` (dry AMD; advanced atrophic stages identify geographic atrophy), `H34.81-` (central RVO), DR/DME families under E08-E13.
- Procedures: CPT 67028 (intravitreal injection administration), 92134 (OCT, retina), plus imaging codes 92133, 92235, 92250 as secondary.
- Drugs (HCPCS): J0178, J0177 (aflibercept, aflibercept HD), J2778 (ranibizumab), J2777 (faricimab-svoa), J0179 (brolucizumab-dbll), Q5124, Q5128 (ranibizumab biosimilars), Q5147 plus newer aflibercept biosimilar Q-codes, J2781, J2782 (geographic atrophy complement inhibitors).
- Provider taxonomy: 207W00000X (Ophthalmology), 207WX0107X (Retina Specialist; effective April 2017, undercounts subspecialists, so confirm with procedure volume).
- Policy anchor: CMS billing-and-coding article A52451 and its MAC-jurisdiction LCD/article family.

`codes.py` is the single source of truth for these lists; all stages import from it.

## Stage 1: National screen

County frame:

- Census Gazetteer county file + OMB CBSA delineation file (county-to-CBSA membership).
- Unit handling: metro counties roll up to their CBSA; non-metro counties stand alone. Screen scores compute at county level first, then aggregate (population-weighted) for CBSAs.

Screen inputs (all small files or filtered API pulls):

| Input | Source | Access |
|---|---|---|
| Population 65+ | Census ACS 5-year | Census API |
| Medicare enrollment, MA penetration | Medicare Monthly Enrollment | data.cms.gov API |
| Ophthalmology/retina provider counts | CMS Doctors and Clinicians national file (specialty filter), NPPES taxonomy | data.cms.gov provider data API |
| Social vulnerability | CDC SVI county file | CDC download |
| Rurality | USDA Rural-Urban Continuum Codes (county) | USDA download |

Screen score: need-versus-supply vulnerability index. High older-adult population, high deprivation, high MA penetration, and low retina provider supply raise the score. Weights documented in code and on the dashboard.

Selection: top-ranked geographies subject to diversity constraints:

- At least 4 metro CBSAs and at least 3 rural counties (RUCC 6-9 or non-CBSA).
- Spanning at least 4 MAC jurisdictions (state-to-MAC mapping from CMS).
- No two geographies from the same CBSA.

Output: `data/out/screen_scores.parquet` (all geographies) and `data/out/selected_10.json`.

## Stage 2: Deep dive (10 geographies only)

| Metric family | Source | Access |
|---|---|---|
| Provider-level injection (67028), OCT (92134), and J-code volume | Medicare Physician & Other Practitioners (MUPPHY) | data.cms.gov API, HCPCS-filtered |
| Part B drug spend and product mix | Medicare Quarterly Part B Spending by Drug (QDD) | data.cms.gov download |
| Quarterly ASP price context | CMS ASP pricing files | cms.gov download |
| 340B covered entities and contract pharmacies | HRSA OPAIS | HRSA download/API |
| Coverage-policy friction | Medicare Coverage Database quarterly download (LCD/article, code crosswalks, revision history), anchored on A52451 family | CMS MCD download |
| Trials, sites, investigators | ClinicalTrials.gov API v2 (wet AMD, GA, DME, RVO conditions) | NIH API |
| Industry engagement context | Open Payments, filtered to ophthalmology | openpaymentsdata.cms.gov API |
| Hospital/system affiliation | CMS Doctors and Clinicians facility affiliations | data.cms.gov API |

## Scoring (7 dimensions)

Each dimension scores 0-100 as a percentile against the national screen pool (or candidate pool where the metric only exists for the 10). Composite = documented weighted sum; the starting point is equal weights across the 7 dimensions, adjustable in one configuration location and displayed on the dashboard methods panel. Dimensions:

1. Retina supply and capacity (providers, injectors, OCT volume per 10k residents 65+)
2. Injection and imaging utilization intensity
3. Part B drug mix (originator vs biosimilar vs GA-drug share)
4. 340B / site-of-care context (covered-entity density, hospital affiliation share)
5. Policy friction (LCD/article restrictiveness signals: covered-diagnosis breadth, documentation language, revision recency)
6. Trial and KOL activity (active trial sites, investigators, publication-adjacent payment signals)
7. Older-adult access risk (SVI, rurality, MA penetration)

Deferred dimension recorded per geography as a data gap: commercial procedure economics (payer MRF). Each geography also gets an explicit "requires private data" list (laterality, visual acuity, OCT outcomes, persistence, switching, PA outcomes, net price).

## Rule-based role actions

- `actions/rules.yaml`: declarative conditions over dimension scores and facts; templated action text per role.
- Example rules: low injector density + high MA penetration triggers a Market Access action about network adequacy and site-of-care economics; active trial sites + named investigators generate MSL engagement targets; high biosimilar share divergence triggers a Medical Affairs evidence-narrative action.
- The rule engine is pure-function, unit-tested, and each emitted action carries the triggering metric values for auditability.

## Dashboard

Static folder, vendored ECharts, no CDN, no backend. Views:

1. National screen choropleth (county/CBSA screen score) with the 10 selected geographies highlighted.
2. Scorecard comparison: 7-dimension radar/bar comparison across the 10 geographies.
3. Geography detail: provider table, drug mix, policy summary, trials and investigators, generated role actions, and the data-gap panel.
4. Methods panel: sources, vintages, weights, verified code sets, and limitations.

Data ships as compact JSON in `dashboard/data/` (target under 5 MB total). Viewable via `python -m http.server` or `file://`.

CPT licensing constraint: the dashboard displays CPT codes with short neutral functional labels (for example "67028 intravitreal injection") rather than reproducing licensed AMA descriptors.

## Testing

- TDD throughout (superpowers test-driven-development skill): pytest, small fixture extracts per source in `tests/fixtures/`.
- Unit tests for every transform, scorer, and rule; golden-file tests for dashboard JSON exports.
- Pipeline QA assertions: row counts, null rates, join coverage (for example, share of providers geocoded to a county must exceed a threshold).
- Dashboard smoke tests with dev-browser (per project CLAUDE.md): each view renders with the real pilot data, no console errors.

## Limitations stated on the dashboard

- MUPPHY and Open Payments lag one to two years; QDD lags quarters.
- Taxonomy undercounts retina subspecialists; procedure volume is the corrective signal.
- Area-level measures are not individual patient attributes; the pilot shows access proxies, not prevalence.
- MUPPHY suppresses rows with 10 or fewer beneficiaries, which can hide low-volume providers in rural counties; suppression handling is documented per metric.

## Out of scope (this phase)

- Commercial payer MRF economics (deferred; documented as a gap).
- MA Plan Benefit Package supplemental-benefit parsing (transportation/vision benefits) beyond MA penetration.
- Any claims, EHR, registry, hub, or chart data.
- Automated geocoding beyond county/ZIP assignment from source files (no Placekey reproduction in this phase).
