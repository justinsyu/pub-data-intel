// Client-side column sorting for table views. Columns are {label, get, type}
// where label is trusted HTML, get is (row)=>value, type is "num" or "text".
// A column with sortable:false renders an inert header (no caret, not clickable)
// and is skipped when wiring; use it for columns that mix units (e.g. cost cells
// that are copay dollars on some rows and coinsurance percent on others).
// Sort state is {col, dir}; col is a column index or null (natural order).
// Blanks (null/undefined/"") always sort last, in both directions.
window.Sort = (() => {
  function state() {
    return {col: null, dir: "asc"};
  }
  function cmp(col, dir) {
    const sign = dir === "desc" ? -1 : 1;
    return (x, y) => {
      const a = col.get(x), b = col.get(y);
      const ab = a === null || a === undefined || a === "";
      const bb = b === null || b === undefined || b === "";
      if (ab && bb) return 0;
      if (ab) return 1;
      if (bb) return -1;
      if (col.type === "num") return sign * (Number(a) - Number(b));
      return sign * String(a).localeCompare(String(b), undefined, {numeric: true, sensitivity: "base"});
    };
  }
  function apply(rows, columns, state) {
    if (state.col == null) return rows;
    return rows.slice().sort(cmp(columns[state.col], state.dir));
  }
  function headHtml(columns, state) {
    return "<tr>" + columns.map((c, i) => {
      if (c.sortable === false) return `<th>${c.label}</th>`;
      const active = state.col === i;
      const caret = active
        ? `<span class="sort-caret">${state.dir === "desc" ? "▼" : "▲"}</span>`
        : "";
      return `<th class="th-sort${active ? " active" : ""}" data-ci="${i}">${c.label}${caret}</th>`;
    }).join("") + "</tr>";
  }
  function wire(scopeEl, columns, state, redraw) {
    scopeEl.querySelectorAll("th.th-sort").forEach(th => {
      th.addEventListener("click", () => {
        const ci = Number(th.dataset.ci);
        if (state.col === ci) {
          state.dir = state.dir === "asc" ? "desc" : "asc";
        } else {
          state.col = ci;
          state.dir = columns[ci].type === "num" ? "desc" : "asc";
        }
        redraw();
      });
    });
  }
  function table(container, columns, rows, rowHtml, opts) {
    const state = (opts && opts.state) || Sort.state();
    function render() {
      container.innerHTML =
        "<table><thead>" + headHtml(columns, state) + "</thead><tbody>" +
        apply(rows, columns, state).map(rowHtml).join("") +
        "</tbody></table>";
      wire(container, columns, state, render);
      if (opts && opts.afterRender) opts.afterRender(container);
    }
    render();
    return {render};
  }
  return {state, cmp, apply, headHtml, wire, table};
})();
