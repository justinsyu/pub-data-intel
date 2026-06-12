window.MPDP = window.MPDP || {views: {}};
(() => {
  const picked = [];
  let drawEpoch = 0;
  MPDP.views.compare = {
    async render(root) {
      const [meta, plans] = await Promise.all([Data.meta(), Data.plansIndex()]);
      root.innerHTML = `<h2>Compare plans</h2>
        <div class="panel"><div class="controls">
          <input type="text" id="cSearch" placeholder="Search plans to add (2 to 4)">
          <span id="cChips"></span></div>
          <div id="cMatches"></div></div>
        <div id="cTable"></div>`;
      const searchEl = root.querySelector("#cSearch");
      const matches = root.querySelector("#cMatches");

      function drawChips() {
        root.querySelector("#cChips").innerHTML = picked.map((p, i) =>
          `<span class="badge">${Fmt.esc(p.plan_name)}
           <a href="#" data-i="${i}">remove</a></span>`).join(" ");
        root.querySelectorAll("#cChips a").forEach(a =>
          a.addEventListener("click", e => {
            e.preventDefault();
            picked.splice(Number(a.dataset.i), 1);
            drawChips(); drawTable();
          }));
      }

      searchEl.addEventListener("input", () => {
        const q = searchEl.value.trim().toLowerCase();
        if (q.length < 2) { matches.innerHTML = ""; return; }
        const rows = plans.filter(p =>
          (p.plan_name || "").toLowerCase().includes(q) &&
          !picked.some(x => x.plan_key === p.plan_key)).slice(0, 10);
        matches.innerHTML = rows.map(p =>
          `<div class="click" data-key="${Fmt.esc(p.plan_key)}">
           ${Fmt.esc(p.plan_name)} <span class="muted">${p.plan_key}</span></div>`
        ).join("");
        matches.querySelectorAll("[data-key]").forEach(div =>
          div.addEventListener("click", () => {
            if (picked.length >= 4) return;
            picked.push(plans.find(p => p.plan_key === div.dataset.key));
            searchEl.value = "";
            matches.innerHTML = "";
            drawChips(); drawTable();
          }));
      });

      async function drawTable() {
        const el = root.querySelector("#cTable");
        if (picked.length < 2) {
          el.innerHTML = "<p class='muted'>Pick at least two plans to compare.</p>";
          return;
        }
        const epoch = ++drawEpoch;
        const cur = picked.slice();
        const shards = await Promise.all(cur.map(p => Data.plan(p.plan_key)));
        if (epoch !== drawEpoch || !root.isConnected) return;
        const metric = (label, fn) => `<tr><th>${label}</th>` +
          cur.map((p, i) => `<td>${fn(p, shards[i])}</td>`).join("") + "</tr>";
        const tierCost = (shard, tier) => {
          const c = shard.costs.find(c =>
            c.level === 1 && c.days === 1 && c.tier === tier);
          if (!c) return "n/a";
          if (c.channels.pref[0]) return Fmt.cost(c.channels.pref);
          if (c.channels.nonpref[0]) return Fmt.cost(c.channels.nonpref) + " (std)";
          return "n/a";
        };
        const tiers = [...new Set(shards.flatMap(s => s.costs
          .filter(c => c.level === 1 && c.days === 1)
          .map(c => c.tier)))].sort((a, b) => a - b);
        const exSets = shards.map(s => new Set(s.excluded.rows.map(r => r[0])));
        const shared = [...exSets[0]].filter(r => exSets.every(s => s.has(r))).length;
        el.innerHTML = `<div class="panel"><table>
          <thead><tr><th>Metric</th>${cur.map(p =>
            `<th>${Fmt.esc(p.plan_name)}</th>`).join("")}</tr></thead><tbody>` +
          metric("Type", p => meta.plan_type_labels[p.type] || p.type) +
          metric("SNP", p => meta.snp_labels[p.snp] || p.snp) +
          metric("Monthly premium", p => Fmt.money(p.premium)) +
          metric("Annual deductible", p => Fmt.money(p.deductible)) +
          metric("Formulary drugs", p => Fmt.num(p.n_drugs)) +
          metric("Prior authorization share", p => Fmt.pct(p.pa_pct)) +
          metric("Step therapy share", p => Fmt.pct(p.st_pct)) +
          metric("Quantity limit share", p => Fmt.pct(p.ql_pct)) +
          metric("Excluded drugs", p => Fmt.num(p.n_excluded)) +
          tiers.map(t => metric(
            `Tier ${t}, 30-day retail, initial coverage (std = standard network)`,
            (p, s) => tierCost(s, t))).join("") +
          `<tr><th>Excluded drugs shared by all selected</th>
           <td colspan="${cur.length}">${shared}</td></tr>` +
          "</tbody></table></div>";
      }

      drawChips(); drawTable();
    },
  };
})();
