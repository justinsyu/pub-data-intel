window.MPDP = window.MPDP || {views: {}};
MPDP.views.overview = {
  async render(root) {
    root.innerHTML = "<h2>Overview</h2><p class='muted'>Implemented in a later task.</p>";
  },
};
