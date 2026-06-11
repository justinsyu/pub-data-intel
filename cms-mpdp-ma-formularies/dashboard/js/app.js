window.MPDP = window.MPDP || {views: {}};
(async function () {
  const nav = document.getElementById("nav");
  const root = document.getElementById("view");
  async function show(name, arg) {
    nav.querySelectorAll("button").forEach(b =>
      b.classList.toggle("active", b.dataset.view === name));
    root.innerHTML = "<p class='muted'>Loading…</p>";
    try {
      await MPDP.views[name].render(root, arg);
    } catch (err) {
      root.innerHTML =
        `<div class="error">Failed to render ${Fmt.esc(name)}: ` +
        `${Fmt.esc(err.message)}</div>`;
      console.error(err);
    }
  }
  MPDP.show = show;
  nav.addEventListener("click", e => {
    if (e.target.dataset.view) show(e.target.dataset.view);
  });
  const meta = await Data.meta();
  document.getElementById("vintage").textContent = `Data: ${meta.vintage}`;
  show("overview");
})();
