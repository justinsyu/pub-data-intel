/* Static dashboard: loads JSON exports, renders 4 views. No backend. */
const state = {};

// Escape API-derived strings before interpolating into innerHTML.
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
// Integer counts (services, population) with thousands separators.
const fmtCount = v => Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });
// Scores and percentages keep one decimal.
const fmtScore = v => Number(v).toFixed(1);
const COUNT_FACTS = new Set(["pop65", "injectors", "inj_services", "ce_340b", "trial_count"]);
const PCT_FACTS = new Set(["ma_pct", "biosimilar_share_pct"]);
const fmtFact = (k, v) => {
  if (typeof v !== "number") return esc(v);
  if (COUNT_FACTS.has(k)) return fmtCount(v);
  if (PCT_FACTS.has(k)) return fmtScore(v);
  return v;
};

async function loadAll() {
  const [mapData, cards, details, meta, geo] = await Promise.all([
    fetch("data/map.json").then(r => r.json()),
    fetch("data/scorecards.json").then(r => r.json()),
    fetch("data/details.json").then(r => r.json()),
    fetch("data/meta.json").then(r => r.json()),
    fetch("vendor/us-counties.geo.json").then(r => r.json()),
  ]);
  // The plotly counties geojson keys fips on feature.id (top level), but
  // ECharts nameProperty only reads feature.properties. Copy it across.
  geo.features.forEach(f => { f.properties.id = f.id; });
  Object.assign(state, { mapData, cards, details, meta, geo });
}

function renderMap() {
  echarts.registerMap("USCounties", state.geo);
  const el = document.getElementById("map-chart");
  const chart = echarts.getInstanceByDom(el) || echarts.init(el);
  chart.setOption({
    title: { text: "National screen score (selected geographies outlined)", left: "center" },
    tooltip: { formatter: p => `${p.data?.fips ?? p.name}: ${p.value ?? "n/a"}` },
    visualMap: { min: 0, max: 100, left: 16, bottom: 16, text: ["high need", "low need"],
                 inRange: { color: ["#eaf3f2", "#245f65"] } },
    series: [{
      type: "map", map: "USCounties", nameProperty: "id",
      // Aleutian features cross the antimeridian, stretching the default
      // bounding box; center/zoom focus the continental US. roam allows pan/zoom.
      roam: true, center: [-96, 38], zoom: 5,
      data: state.mapData.map(d => ({
        name: d.fips, fips: d.fips, value: d.score,
        itemStyle: d.selected ? { borderColor: "#a85f36", borderWidth: 2 } : undefined,
      })),
    }],
  });
}

function renderScorecards() {
  const dims = state.meta.dimensions;
  const el = document.getElementById("radar-chart");
  const chart = echarts.getInstanceByDom(el) || echarts.init(el);
  chart.setOption({
    title: { text: "Dimension scores across the 10 pilot geographies", left: "center" },
    legend: { type: "scroll", bottom: 0 },
    radar: { indicator: dims.map(d => ({ name: d, max: 100 })) },
    series: [{ type: "radar",
      data: state.cards.map(c => ({ name: c.name, value: dims.map(d => c.dims[d]) })) }],
  });
  const rows = state.cards.map(c =>
    `<tr><td>${esc(c.name)}</td><td>${esc(c.mac)}</td><td>${fmtScore(c.composite)}</td>` +
    dims.map(d => `<td>${fmtScore(c.dims[d])}</td>`).join("") + "</tr>").join("");
  document.getElementById("score-table").innerHTML =
    `<table><tr><th>Geography</th><th>MAC</th><th>Composite</th>` +
    dims.map(d => `<th>${d}</th>`).join("") + `</tr>${rows}</table>`;
}

function renderDetail(unitId) {
  const d = state.details[unitId];
  if (!d) return;
  const facts = Object.entries(d.facts).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${fmtFact(k, v)}</td></tr>`).join("");
  const provs = d.top_providers.map(p =>
    `<tr><td>${esc(p.last_name)}</td><td>${esc(p.npi)}</td><td>${fmtCount(p.services)}</td></tr>`).join("");
  const drugs = Object.entries(d.drug_mix).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${fmtCount(v)}</td></tr>`).join("");
  const trials = d.trials.map(t => `<tr><td>${esc(t.nct_id)}</td><td>${esc(t.title)}</td><td>${esc(t.facility)}, ${esc(t.city)}</td></tr>`).join("");
  const actions = d.actions.map(a =>
    `<div class="panel"><span class="role">${esc(a.role.replace("_", " "))}</span><p>${esc(a.action)}</p>` +
    `<p class="muted">Evidence: ${a.evidence.map(e => `${esc(e.metric)}=${esc(e.value)}`).join(", ")}</p></div>`).join("");
  const gaps = d.data_gaps.map(g => `<li>${esc(g)}</li>`).join("");
  document.getElementById("detail-content").innerHTML = `
    <div class="panel"><h2>${esc(d.name)} <span class="muted">(MAC ${esc(d.mac)})</span></h2>
      <table>${facts}</table></div>
    <div class="panel"><h3>Top providers by retina services (Medicare-visible)</h3>
      <table><tr><th>Name</th><th>NPI</th><th>Services</th></tr>${provs || "<tr><td colspan=3>None visible (small-cell suppression)</td></tr>"}</table></div>
    <div class="panel"><h3>Drug mix (services by product)</h3>
      <table><tr><th>Product</th><th>Services</th></tr>${drugs || "<tr><td colspan=2>None visible</td></tr>"}</table></div>
    <div class="panel"><h3>Active trials</h3>
      <table><tr><th>NCT</th><th>Title</th><th>Site</th></tr>${trials || "<tr><td colspan=3>None found</td></tr>"}</table></div>
    <h3>Role actions</h3>${actions || "<p>No rules fired.</p>"}
    <div class="panel"><h3>Data gaps (require private data)</h3><ul>${gaps}</ul></div>`;
}

function renderMethods() {
  const m = state.meta;
  document.getElementById("methods-content").innerHTML = `
    <h2>Methods</h2>
    <p>Generated: ${m.generated}. Population source: ${m.acs_vintage}.</p>
    <p>Dimension weights: ${Object.entries(m.weights).map(([k, v]) => `${k}=${v.toFixed(3)}`).join(", ")}</p>
    <p>Drug codes: ${Object.entries(m.drug_codes).map(([k, v]) => `${k} (${v})`).join("; ")}</p>
    <p>Procedure codes: ${Object.entries(m.procedure_codes).map(([k, v]) => `${k} (${v})`).join("; ")}</p>
    <p class="muted">${m.sources_note} CPT codes shown with neutral functional labels;
    descriptors are AMA-licensed. MUPPHY and Open Payments lag 1-2 years.
    Area-level measures are not individual patient attributes.</p>`;
}

function wireNav() {
  document.querySelectorAll("nav button").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("nav button").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("view-" + btn.dataset.view).classList.add("active");
      if (btn.dataset.view === "scorecards") renderScorecards();
      if (btn.dataset.view === "methods") renderMethods();
    });
  });
  const sel = document.getElementById("geo-select");
  sel.addEventListener("change", () => renderDetail(sel.value));
}

loadAll().then(() => {
  wireNav();
  renderMap();
  const sel = document.getElementById("geo-select");
  sel.innerHTML = state.cards.map(c => `<option value="${esc(c.unit_id)}">${esc(c.name)}</option>`).join("");
  if (state.cards.length) renderDetail(state.cards[0].unit_id);
});

window.addEventListener("resize", () => {
  ["map-chart", "radar-chart"].forEach(id => {
    const el = document.getElementById(id);
    const chart = el && echarts.getInstanceByDom(el);
    if (chart) chart.resize();
  });
});
