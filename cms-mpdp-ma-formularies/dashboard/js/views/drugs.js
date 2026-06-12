window.MPDP = window.MPDP || {views: {}};
(() => {
  let mapRegistered = false;
  // Recursively apply fn to every [lon, lat] pair in a GeoJSON coordinates tree.
  function mapCoords(coords, fn) {
    return typeof coords[0] === "number"
      ? fn(coords) : coords.map(c => mapCoords(c, fn));
  }
  // Reposition Alaska and Hawaii as shrunken bottom-left insets (Albers-USA
  // style) so the contiguous US fills most of the panel instead of Alaska's
  // true, huge geographic extent dominating it.
  const akInset = ([lon, lat]) => {
    if (lon > 0) lon -= 360;           // unwrap Aleutian Islands past the antimeridian
    return [(lon + 152) * 0.38 - 117, (lat - 62) * 0.38 + 25];
  };
  const hiInset = ([lon, lat]) => [(lon + 157) - 104, (lat - 20.5) + 23];
  // Puerto Rico and the US Virgin Islands are tiny at true scale; enlarge them
  // ~2.5x in the bottom-right (still well smaller than the Alaska inset).
  const prInset = ([lon, lat]) => [(lon + 66) * 2.5 - 68, (lat - 18) * 2.5 + 20];
  async function ensureCountyMap() {
    if (mapRegistered) return;
    const gj = await Data.json("vendor/counties-fips.json");
    gj.features.forEach(f => {
      f.properties.fips = f.id;
      const st = String(f.id).slice(0, 2);
      if (!f.geometry) return;
      if (st === "02") f.geometry.coordinates = mapCoords(f.geometry.coordinates, akInset);
      else if (st === "15") f.geometry.coordinates = mapCoords(f.geometry.coordinates, hiInset);
      else if (st === "72" || st === "78") f.geometry.coordinates = mapCoords(f.geometry.coordinates, prInset);
    });
    echarts.registerMap("US_COUNTIES", gj);
    mapRegistered = true;
  }

  function countyValues(vector, plans, geo, metric, types) {
    const vals = [];
    for (const c of geo) {
      let tot = 0, hit = 0;
      for (const i of c.plans) {
        const p = plans[i];
        if (!types.has(p.type) || p.formulary_idx < 0) continue;
        tot++;
        const ch = vector[p.formulary_idx];
        if (!ch || ch === "-") continue;
        if (metric === "covered" || ch === "1") hit++;
      }
      if (tot) vals.push({name: c.fips, value: Math.round(1000 * hit / tot) / 10});
    }
    return vals;
  }

  MPDP.views.drugs = {
    async render(root, rxcui) {
      const drugs = await Data.drugsIndex();
      root.innerHTML = `
        <h2>Drug explorer</h2>
        <div class="panel">
          <div class="controls">
            <input type="text" id="dSearch" placeholder="Search drug name or RXCUI">
            <select id="dBg"><option value="">Brand + generic</option>
              <option value="brand">Brand</option>
              <option value="generic">Generic</option></select>
            <label><input type="checkbox" id="dExcl"> Excluded somewhere</label>
            <label><input type="checkbox" id="dSel"> Negotiation-selected</label>
            <span class="muted" id="dCount"></span>
          </div>
          <div id="dTable"></div>
        </div>
        <div id="dDetail"></div>`;

      const pager = Paginate.create({
        container: root.querySelector("#dTable"),
        pageSize: 50,
        label: "drugs",
        columns: [
          {label: "Drug", get: d => d.name, type: "text"},
          {label: "Type", get: d => d.bg, type: "text"},
          {label: "Coverage", get: d => d.cov_pct, type: "num"},
          {label: Defs.abbr("PA"), get: d => d.pa_pct, type: "num"},
          {label: Defs.abbr("ST"), get: d => d.st_pct, type: "num"},
          {label: Defs.abbr("QL"), get: d => d.ql_pct, type: "num"},
          {label: "Excluding plans", get: d => d.excl_plans, type: "num"},
        ],
        rowHtml: d => `<tr class="click" data-rxcui="${Fmt.esc(d.rxcui)}">
            <td>${Fmt.esc(d.name)}${d.selected
              ? `<span class="badge sel" title="${Fmt.esc(Defs.tip("Negotiation-selected"))}">negotiation</span>` : ""}</td>
            <td>${d.bg || ""}</td><td>${Fmt.pct(d.cov_pct)}</td>
            <td>${Fmt.pct(d.pa_pct)}</td><td>${Fmt.pct(d.st_pct)}</td>
            <td>${Fmt.pct(d.ql_pct)}</td><td>${Fmt.num(d.excl_plans)}</td></tr>`,
        afterRender: container => container.querySelectorAll("tr[data-rxcui]").forEach(tr =>
          tr.addEventListener("click", () => showDetail(tr.dataset.rxcui))),
      });

      function draw() {
        const q = root.querySelector("#dSearch").value.trim().toLowerCase();
        const bg = root.querySelector("#dBg").value;
        let rows = drugs;
        if (q) rows = rows.filter(d =>
          d.name.toLowerCase().includes(q) || d.rxcui.startsWith(q));
        if (bg) rows = rows.filter(d => d.bg === bg);
        if (root.querySelector("#dExcl").checked)
          rows = rows.filter(d => d.excl_plans > 0);
        if (root.querySelector("#dSel").checked)
          rows = rows.filter(d => d.selected);
        root.querySelector("#dCount").textContent = `${Fmt.num(rows.length)} drugs match`;
        pager.setRows(rows);
      }
      ["#dSearch", "#dBg", "#dExcl", "#dSel"].forEach(sel =>
        root.querySelector(sel).addEventListener("input", draw));
      draw();

      async function showDetail(id) {
        const el = root.querySelector("#dDetail");
        el.querySelectorAll("[_echarts_instance_]").forEach(n => {
          const c = echarts.getInstanceByDom(n);
          if (c) c.dispose();
        });
        el.innerHTML = "<p class='muted'>Loading drug detail…</p>";
        el.scrollIntoView({behavior: "smooth", block: "start"});
        const [d, meta, plans] = await Promise.all(
          [Data.drug(id), Data.meta(), Data.plansIndex()]);
        const planByFidx = new Map();
        plans.forEach(p => {
          if (!planByFidx.has(p.formulary_idx)) planByFidx.set(p.formulary_idx, []);
          planByFidx.get(p.formulary_idx).push(p);
        });
        const fRows = meta.formulary_order.map((fid, i) => {
          const ch = d.vector[i];
          if (!ch || ch === "-") return null;
          const det = d.formularies[fid] || [null, null, null];
          const ps = planByFidx.get(i) || [];
          const orgs = [...new Set(ps.map(p => p.contract_name).filter(Boolean))].sort();
          return {fid, tier: det[0], qla: det[1], qld: det[2],
                  restr: Fmt.restr(ch),
                  nPlans: ps.length, orgs};
        }).filter(Boolean).sort((a, b) => (a.tier || 99) - (b.tier || 99));
        // CMS formularies have no name; label them by the organization(s) whose
        // plans use the formulary, with the numeric ID shown underneath.
        const formularyLabel = r => {
          const id = `<span class="muted">${Fmt.esc(r.fid)}</span>`;
          if (!r.orgs.length) return id;
          const extra = r.orgs.length > 1
            ? ` <span class="muted">(+${r.orgs.length - 1} more)</span>` : "";
          const title = r.orgs.length > 1
            ? ` title="${Fmt.esc(r.orgs.join("; "))}"` : "";
          return `<div${title}>${Fmt.esc(r.orgs[0])}${extra}</div>${id}`;
        };
        const exRows = Data.table(d.excluded_by);
        el.innerHTML = `
          <h2>${Fmt.esc(d.name)}
            <span class="muted">RXCUI ${Fmt.esc(d.rxcui)}</span>
            ${d.selected ? `<span class="badge sel" title="${Fmt.esc(Defs.tip("Negotiation-selected"))}">negotiation-selected</span>` : ""}
          </h2>
          <div class="grid2" style="grid-template-columns: 2fr 3fr;">
            <div class="panel"><h3>Tier placement across formularies</h3>
              <div id="dTier" class="chart"></div></div>
            <div class="panel"><h3>County coverage map</h3>
              <div class="controls">
                <select id="dMetric">
                  <option value="unrestricted">% of plans covering without PA/ST/QL</option>
                  <option value="covered">% of plans covering at all</option>
                </select>
                <label><input type="checkbox" class="dType" value="MA" checked> MA</label>
                <label><input type="checkbox" class="dType" value="MA_REGIONAL" checked> MA regional</label>
                <label><input type="checkbox" class="dType" value="PDP" checked> PDP</label>
              </div>
              <div id="dMap" class="map"></div></div>
          </div>
          <div class="panel">
            <h3>Formularies listing this drug (${fRows.length})</h3>
            <div id="dFormList"></div></div>
          <div class="panel"><h3>Plans excluding this drug (${exRows.length})</h3>` +
          (exRows.length ? `<div id="dExclList"></div>` : "<p class='muted'>None.</p>") + "</div>" +
          (d.indications.length ? `<div class="panel">
            <h3>Indication-based coverage</h3><ul>` +
            d.indications.map(i =>
              `<li>${Fmt.esc(i.contract_plan)}: ${Fmt.esc(i.disease)}</li>`).join("") +
            "</ul></div>" : "");
        el.scrollIntoView({behavior: "smooth", block: "start"});

        Sort.table(el.querySelector("#dFormList"), [
          {label: "Formulary", get: r => (r.orgs && r.orgs.length ? r.orgs[0] : r.fid), type: "text"},
          {label: Defs.abbr("Tier"), get: r => r.tier, type: "num"},
          {label: "Restrictions", get: r => r.restr, type: "text"},
          {label: "QL amount / days", get: r => r.qla, type: "num"},
          {label: "Plans using", get: r => r.nPlans, type: "num"},
        ], fRows, r => `<tr><td>${formularyLabel(r)}</td><td>${r.tier ?? "n/a"}</td>
            <td>${r.restr}</td>
            <td>${r.qla ? `${Fmt.esc(r.qla)} / ${Fmt.esc(r.qld)}d` : ""}</td>
            <td>${Fmt.num(r.nPlans)}</td></tr>`);

        if (exRows.length) Sort.table(el.querySelector("#dExclList"), [
          {label: "Plan", get: r => r.plan_name || r.contract_plan, type: "text"},
          {label: Defs.abbr("Tier"), get: r => r.tier, type: "num"},
          {label: Defs.abbr("PA"), get: r => r.pa ? 1 : 0, type: "num"},
          {label: Defs.abbr("ST"), get: r => r.st ? 1 : 0, type: "num"},
          {label: Defs.abbr("QL"), get: r => r.ql ? 1 : 0, type: "num"},
          {label: Defs.abbr("Capped"), get: r => r.capped ? 1 : 0, type: "num"},
        ], exRows, r => `<tr>
            <td>${Fmt.esc(r.plan_name || r.contract_plan)}</td>
            <td>${r.tier ?? ""}</td><td>${Fmt.flag(r.pa)}</td>
            <td>${Fmt.flag(r.st)}</td>
            <td>${r.ql ? `${Fmt.esc(r.ql_amount || "?")} / ${Fmt.esc(r.ql_days || "?")}d` : "No"}</td>
            <td>${Fmt.flag(r.capped)}</td></tr>`);

        const tierCounts = {};
        fRows.forEach(r => {
          if (r.tier) tierCounts[r.tier] = (tierCounts[r.tier] || 0) + 1;
        });
        const tiers = Object.keys(tierCounts).sort((a, b) => a - b);
        echarts.init(el.querySelector("#dTier")).setOption({
          tooltip: {},
          grid: {left: 50, right: 16, top: 16, bottom: 24},
          xAxis: {type: "category", data: tiers.map(t => "Tier " + t)},
          yAxis: {type: "value"},
          series: [{type: "bar", barMaxWidth: 56, data: tiers.map(t => tierCounts[t])}],
        });

        await ensureCountyMap();
        const geo = await Data.geo();
        const countyName = new Map(geo.map(c => [c.fips, `${c.name}, ${c.state}`]));
        const mapChart = echarts.init(el.querySelector("#dMap"));
        function drawMap() {
          const metric = el.querySelector("#dMetric").value;
          const types = new Set(
            [...el.querySelectorAll(".dType:checked")].map(c => c.value));
          mapChart.setOption({
            tooltip: {formatter: p =>
              `${countyName.get(p.name) || p.name}: ` +
              (p.value == null || isNaN(p.value) ? "no data" : p.value + "%")},
            visualMap: {min: 0, max: 100, calculable: true,
                        inRange: {color: ["#f7fbff", "#08519c"]}},
            series: [{type: "map", map: "US_COUNTIES", nameProperty: "fips",
                      boundingCoords: [[-132, 50], [-64, 17.5]],
                      data: countyValues(d.vector, plans, geo, metric, types),
                      emphasis: {label: {show: false}}}],
          }, true);
        }
        el.querySelector("#dMetric").addEventListener("input", drawMap);
        el.querySelectorAll(".dType").forEach(c =>
          c.addEventListener("input", drawMap));
        drawMap();
      }

      if (rxcui) showDetail(rxcui);
    },
  };
})();
