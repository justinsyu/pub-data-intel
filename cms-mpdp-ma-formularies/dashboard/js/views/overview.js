window.MPDP = window.MPDP || {views: {}};
MPDP.views.overview = {
  async render(root) {
    const [meta, ov] = await Promise.all([Data.meta(), Data.overview()]);
    const card = (v, l) =>
      `<div class="card"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    const typeRows = ov.plan_types.map(t =>
      `<tr><td>${Fmt.esc(meta.plan_type_labels[t.type] || t.type)}</td>` +
      `<td>${Fmt.num(t.n)}</td></tr>`).join("");
    const snpRows = ov.snp.map(s =>
      `<tr><td>${Fmt.esc(meta.snp_labels[s.snp] || s.snp)}</td>` +
      `<td>${Fmt.num(s.n)}</td></tr>`).join("");
    const selRows = ov.selected_drugs.map(d =>
      `<tr class="click" data-rxcui="${Fmt.esc(d.rxcui)}">` +
      `<td><a href="#">${Fmt.esc(d.name)}</a></td><td>${d.rxcui}</td>` +
      `<td>${Fmt.num(d.n_formularies)}</td></tr>`).join("");
    root.innerHTML = `
      <h2>Market overview</h2>
      <div class="cards">
        ${card(Fmt.num(meta.counts.plans), "Plans (contract-plan-segment)")}
        ${card(Fmt.num(meta.counts.contracts), "Contracts")}
        ${card(Fmt.num(meta.counts.formularies), "Formularies")}
        ${card(Fmt.num(meta.counts.drugs), "Distinct drugs (RXCUI)")}
      </div>
      <div class="grid2">
        <div class="panel"><h3>Tier mix (formulary-drug listings)</h3>
          <div id="tierChart" class="chart"></div></div>
        <div class="panel"><h3>Restriction prevalence (share of listings)</h3>
          <div id="restrChart" class="chart"></div></div>
      </div>
      <div class="grid2">
        <div class="panel"><h3>Plans by type</h3>
          <table><thead><tr><th>Type</th><th>Plans</th></tr></thead>
          <tbody>${typeRows}</tbody></table></div>
        <div class="panel"><h3>Plans by special needs status</h3>
          <table><thead><tr><th>SNP type</th><th>Plans</th></tr></thead>
          <tbody>${snpRows}</tbody></table></div>
      </div>
      <div class="panel"><h3>Drugs selected for Medicare price negotiation</h3>
        <table><thead><tr><th>Drug</th><th>RXCUI</th><th>Formularies listing</th>
        </tr></thead><tbody>${selRows}</tbody></table></div>
      <div class="panel"><h3>Exclusions</h3>
        <p>${Fmt.num(ov.exclusions.rows)} exclusion records covering
        ${Fmt.num(ov.exclusions.distinct_rxcuis)} distinct drugs across
        ${Fmt.num(ov.exclusions.n_contract_plans)} contract-plans.
        Browse them per drug or per plan in the explorers.</p></div>`;
    root.querySelectorAll("tr[data-rxcui]").forEach(tr =>
      tr.addEventListener("click", e => {
        e.preventDefault();
        MPDP.show("drugs", tr.dataset.rxcui);
      }));
    echarts.init(document.getElementById("tierChart")).setOption({
      tooltip: {},
      grid: {left: 70, right: 16, top: 16, bottom: 24},
      xAxis: {type: "category",
              data: ov.tier_mix.map(t => "Tier " + t.tier)},
      yAxis: {type: "value"},
      series: [{type: "bar", data: ov.tier_mix.map(t => t.n)}],
    });
    echarts.init(document.getElementById("restrChart")).setOption({
      tooltip: {valueFormatter: v => v + "%"},
      grid: {left: 70, right: 16, top: 16, bottom: 24},
      xAxis: {type: "category",
              data: ["Prior authorization", "Step therapy", "Quantity limit"]},
      yAxis: {type: "value", axisLabel: {formatter: "{value}%"}},
      series: [{type: "bar", data: [ov.restrictions.pa_pct,
                ov.restrictions.st_pct, ov.restrictions.ql_pct]}],
    });
  },
};
