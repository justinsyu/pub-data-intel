window.MPDP = window.MPDP || {views: {}};
(() => {
  MPDP.views.plans = {
    async render(root, planKey) {
      const [meta, plans] = await Promise.all([Data.meta(), Data.plansIndex()]);
      const states = [...new Set(plans.flatMap(p => p.states))].sort();
      root.innerHTML = `
        <h2>Plan explorer</h2>
        <div class="panel"><div class="controls">
          <input type="text" id="pSearch" placeholder="Search plan, contract, or key">
          <select id="pType"><option value="">All types</option>
            ${Object.entries(meta.plan_type_labels).map(([k, v]) =>
              `<option value="${k}">${Fmt.esc(v)}</option>`).join("")}</select>
          <select id="pSnp"><option value="">All SNP statuses</option>
            ${Object.entries(meta.snp_labels).map(([k, v]) =>
              `<option value="${k}">${Fmt.esc(v)}</option>`).join("")}</select>
          <select id="pState"><option value="">All states</option>
            ${states.map(s => `<option>${s}</option>`).join("")}</select>
          <span class="muted" id="pCount"></span></div>
          <div id="pTable"></div></div>
        <div id="pDetail"></div>`;

      const pager = Paginate.create({
        container: root.querySelector("#pTable"),
        pageSize: 50,
        label: "plans",
        headHtml: `<tr>
          <th>Plan</th><th>Type</th><th>Premium</th><th>Deductible</th>
          <th>Drugs</th><th>${Defs.abbr("PA")}</th><th>${Defs.abbr("QL")}</th><th>Excluded</th></tr>`,
        rowHtml: p => `<tr class="click" data-key="${Fmt.esc(p.plan_key)}">
            <td>${Fmt.esc(p.plan_name)}
              ${p.suppressed === "Y"
                ? `<span class="badge warn" title="${Fmt.esc(Defs.tip("Suppressed"))}">suppressed</span>` : ""}
              ${p.snp !== "0" ? `<span class="badge" title="${Fmt.esc(meta.snp_labels[p.snp] || Defs.tip("SNP"))}">SNP</span>` : ""}</td>
            <td title="${Fmt.esc(meta.plan_type_labels[p.type] || p.type)}">${Fmt.esc(p.type)}</td>
            <td>${Fmt.money(p.premium)}</td>
            <td>${Fmt.money(p.deductible)}</td><td>${Fmt.num(p.n_drugs)}</td>
            <td>${Fmt.pct(p.pa_pct)}</td><td>${Fmt.pct(p.ql_pct)}</td>
            <td>${Fmt.num(p.n_excluded)}</td></tr>`,
        afterRender: container => container.querySelectorAll("tr[data-key]").forEach(tr =>
          tr.addEventListener("click", () => showDetail(tr.dataset.key))),
      });

      function draw() {
        const q = root.querySelector("#pSearch").value.trim().toLowerCase();
        const ty = root.querySelector("#pType").value;
        const sn = root.querySelector("#pSnp").value;
        const st = root.querySelector("#pState").value;
        let rows = plans;
        if (q) rows = rows.filter(p =>
          (p.plan_name || "").toLowerCase().includes(q) ||
          (p.contract_name || "").toLowerCase().includes(q) ||
          p.plan_key.toLowerCase().startsWith(q));
        if (ty) rows = rows.filter(p => p.type === ty);
        if (sn) rows = rows.filter(p => p.snp === sn);
        if (st) rows = rows.filter(p => p.states.includes(st));
        root.querySelector("#pCount").textContent = `${Fmt.num(rows.length)} plans match`;
        pager.setRows(rows);
      }
      ["#pSearch", "#pType", "#pSnp", "#pState"].forEach(sel =>
        root.querySelector(sel).addEventListener("input", draw));
      draw();

      async function showDetail(key) {
        const el = root.querySelector("#pDetail");
        el.querySelectorAll("[_echarts_instance_]").forEach(n => {
          const c = echarts.getInstanceByDom(n);
          if (c) c.dispose();
        });
        el.innerHTML = "<p class='muted'>Loading plan detail…</p>";
        el.scrollIntoView({behavior: "smooth", block: "start"});
        const p = plans.find(x => x.plan_key === key);
        const shard = await Data.plan(key);
        const suppressed = p.suppressed === "Y";

        const costsByLevel = {};
        shard.costs.forEach(c => {
          (costsByLevel[c.level] = costsByLevel[c.level] || []).push(c);
        });
        const costTables = suppressed
          ? "<p class='muted'>Cost data suppressed by CMS for this plan.</p>"
          : Object.keys(costsByLevel).sort().map(level => {
              const rows = costsByLevel[level].sort((a, b) =>
                (a.tier - b.tier) || (a.days - b.days));
              return `<h4>${Fmt.esc(meta.coverage_level_labels[level] ||
                  ("Level " + level))}</h4>
                <table><thead><tr><th>${Defs.abbr("Tier")}</th><th>Supply</th>
                  <th>${Defs.abbr("Preferred", "Preferred retail")}</th><th>Standard retail</th>
                  <th>Preferred mail</th><th>Standard mail</th>
                  <th>Deductible applies</th></tr></thead><tbody>` +
                rows.map(c => `<tr>
                  <td>${c.tier}${c.specialty === "Y"
                    ? ` <span class="badge" title="${Fmt.esc(Defs.tip("Specialty"))}">specialty</span>` : ""}</td>
                  <td>${Fmt.esc(meta.days_supply_labels[c.days] || c.days)}</td>
                  <td>${Fmt.cost(c.channels.pref)}</td>
                  <td>${Fmt.cost(c.channels.nonpref)}</td>
                  <td>${Fmt.cost(c.channels.mail_pref)}</td>
                  <td>${Fmt.cost(c.channels.mail_nonpref)}</td>
                  <td>${c.ded_applies}</td></tr>`).join("") +
                "</tbody></table>";
            }).join("");

        const insCell = (cp, cn) => {
          if (cp == null && cn == null) return "n/a";
          if (cp != null && cn != null && cn > 0)
            return `${Fmt.money(cp)} / ${Math.round(cn * 100)}%, lesser applies`;
          if (cp != null) return Fmt.money(cp);
          return Math.round(cn * 100) + "%";
        };
        const insTable = suppressed || !shard.insulin.length ? "" :
          `<div class="panel"><h3>Insulin cost sharing (lesser of copay and coinsurance applies)</h3>
            <table><thead><tr><th>${Defs.abbr("Tier")}</th><th>Supply</th>
              <th>Preferred retail</th><th>Standard retail</th>
              <th>Preferred mail</th><th>Standard mail</th></tr></thead><tbody>` +
          shard.insulin.map(i => `<tr>
            <td>${i.tier ?? "std"}</td>
            <td>${Fmt.esc(meta.days_supply_labels[i.days] || i.days)}</td>
            ${[0, 1, 2, 3].map(k => `<td>${insCell(i.copay[k], i.coin[k])}</td>`).join("")}</tr>`).join("") +
          "</tbody></table></div>";

        const ex = Data.table(shard.excluded);
        const exTable = ex.length ? `<div class="panel">
            <h3>Excluded drugs (${ex.length})</h3>
            <table><thead><tr><th>Drug</th><th>${Defs.abbr("Tier")}</th><th>${Defs.abbr("PA")}</th><th>${Defs.abbr("ST")}</th>
              <th>${Defs.abbr("QL")}</th><th>${Defs.abbr("Capped")}</th></tr></thead><tbody>` +
          ex.map(r => `<tr>
            <td><a href="#" data-rxcui="${Fmt.esc(r.rxcui)}">
              ${Fmt.esc(r.name || r.rxcui)}</a></td>
            <td>${r.tier ?? ""}</td><td>${Fmt.flag(r.pa)}</td>
            <td>${Fmt.flag(r.st)}</td>
            <td>${r.ql ? `${Fmt.esc(r.ql_amount || "?")} / ${Fmt.esc(r.ql_days || "?")}d` : "No"}</td>
            <td>${Fmt.flag(r.capped)}</td></tr>`).join("") +
          "</tbody></table></div>"
          : "<div class='panel'><h3>Excluded drugs</h3><p class='muted'>None reported.</p></div>";

        const indList = shard.indications.length ? `<div class="panel">
            <h3>Indication-based coverage</h3><ul>` +
          shard.indications.map(i =>
            `<li>${Fmt.esc(i.name || i.rxcui)}: ${Fmt.esc(i.disease)}</li>`).join("") +
          "</ul></div>" : "";

        el.innerHTML = `
          <h2>${Fmt.esc(p.plan_name)}
            ${suppressed ? `<span class="badge warn" title="${Fmt.esc(Defs.tip("Suppressed"))}">suppressed</span>` : ""}</h2>
          <div class="cards">
            <div class="card"><div class="v">${Fmt.esc(p.plan_key)}</div>
              <div class="l">${Fmt.esc(meta.plan_type_labels[p.type] || p.type)},
              ${Fmt.esc(meta.snp_labels[p.snp] || p.snp)}</div></div>
            <div class="card"><div class="v">${Fmt.money(p.premium)}</div>
              <div class="l">Monthly premium</div></div>
            <div class="card"><div class="v">${Fmt.money(p.deductible)}</div>
              <div class="l">Annual deductible</div></div>
            <div class="card"><div class="v">${Fmt.num(p.n_drugs)}</div>
              <div class="l">Formulary drugs (PA ${Fmt.pct(p.pa_pct)},
              QL ${Fmt.pct(p.ql_pct)})</div></div>
          </div>
          <div class="panel"><h3>Tier cost sharing</h3>${costTables}</div>
          ${insTable}${exTable}${indList}
          <div class="panel"><h3>Formulary browser</h3>
            <div class="controls">
              <input type="text" id="fSearch" placeholder="Search this formulary">
              <span class="muted" id="fCount"></span></div>
            <div id="fTable"><p class="muted">Loading formulary…</p></div></div>`;
        el.scrollIntoView({behavior: "smooth", block: "start"});
        el.querySelectorAll("a[data-rxcui]").forEach(a =>
          a.addEventListener("click", e => {
            e.preventDefault();
            MPDP.show("drugs", a.dataset.rxcui);
          }));

        const fid = p.formulary_idx >= 0
          ? meta.formulary_order[p.formulary_idx] : null;
        if (!fid) {
          el.querySelector("#fTable").innerHTML =
            "<p class='muted'>This plan's formulary is not present in the basic drugs file.</p>";
          return;
        }
        const form = await Data.formulary(fid);
        const fRows = Data.table(form);
        const formPager = Paginate.create({
          container: el.querySelector("#fTable"),
          pageSize: 50,
          label: `drugs on formulary ${fid}`,
          headHtml: `<tr><th>Drug</th><th>Type</th><th>${Defs.abbr("Tier")}</th>
            <th>${Defs.abbr("PA")}</th><th>${Defs.abbr("ST")}</th><th>${Defs.abbr("QL")}</th></tr>`,
          rowHtml: r => `<tr>
            <td><a href="#" data-rxcui="${Fmt.esc(r.rxcui)}">${Fmt.esc(r.name)}</a></td>
            <td>${r.bg || ""}</td><td>${r.tier ?? ""}</td>
            <td>${Fmt.flag(r.pa)}</td><td>${Fmt.flag(r.st)}</td>
            <td>${r.ql ? `${Fmt.esc(r.ql_amount || "?")} / ${Fmt.esc(r.ql_days || "?")}d` : "No"}</td>
            </tr>`,
          afterRender: container => container.querySelectorAll("a[data-rxcui]").forEach(a =>
            a.addEventListener("click", e => {
              e.preventDefault();
              MPDP.show("drugs", a.dataset.rxcui);
            })),
        });
        function drawForm() {
          const q = el.querySelector("#fSearch").value.trim().toLowerCase();
          const rows = q
            ? fRows.filter(r => r.name.toLowerCase().includes(q)
                                || r.rxcui.startsWith(q))
            : fRows;
          el.querySelector("#fCount").textContent = `${Fmt.num(rows.length)} drugs match`;
          formPager.setRows(rows);
        }
        el.querySelector("#fSearch").addEventListener("input", drawForm);
        drawForm();
      }

      if (planKey) showDetail(planKey);
    },
  };
})();
