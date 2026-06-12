// Reusable client-side table paginator. Owns a container's <table> + pager
// controls; setRows(rows) resets to page 1 and re-renders. afterRender runs
// after every page render so callers can (re)attach row listeners.
window.Paginate = (() => {
  function create({container, pageSize, headHtml, rowHtml, afterRender, label}) {
    let rows = [], page = 0;
    function render() {
      const total = rows.length;
      const pages = Math.max(1, Math.ceil(total / pageSize));
      if (page > pages - 1) page = pages - 1;
      if (page < 0) page = 0;
      const start = page * pageSize;
      const slice = rows.slice(start, start + pageSize);
      container.innerHTML =
        `<table><thead>${headHtml}</thead><tbody>` +
        slice.map(rowHtml).join("") +
        "</tbody></table>" +
        `<div class="pager">
           <button type="button" data-pg="prev"${page === 0 ? " disabled" : ""}>‹ Prev</button>
           <button type="button" data-pg="next"${page >= pages - 1 ? " disabled" : ""}>Next ›</button>
           <span class="muted">Showing ${total ? Fmt.num(start + 1) : 0} to ${Fmt.num(start + slice.length)} of ${Fmt.num(total)} ${label}</span>
           <span class="muted">Page ${Fmt.num(page + 1)} of ${Fmt.num(pages)}</span>
         </div>`;
      const prev = container.querySelector('[data-pg="prev"]');
      const next = container.querySelector('[data-pg="next"]');
      if (prev) prev.onclick = () => { if (page > 0) { page--; render(); } };
      if (next) next.onclick = () => { if (page < pages - 1) { page++; render(); } };
      if (afterRender) afterRender(container);
    }
    return {
      setRows(r) { rows = r; page = 0; render(); },
      render,
    };
  }
  return {create};
})();
