const Data = (() => {
  const cache = new Map();
  function json(path) {
    if (!cache.has(path)) {
      cache.set(path, fetch(path).then(r => {
        if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
        return r.json();
      }));
    }
    return cache.get(path);
  }
  function table(obj) {
    return obj.rows.map(r =>
      Object.fromEntries(obj.cols.map((c, i) => [c, r[i]])));
  }
  return {
    json, table,
    meta: () => json("data/meta.json"),
    overview: () => json("data/overview.json"),
    drugsIndex: () => json("data/drugs_index.json").then(table),
    plansIndex: () => json("data/plans_index.json").then(table),
    geo: () => json("data/geo.json").then(table),
    drug: rxcui => json(`data/drugs/${rxcui}.json`),
    plan: key => json(`data/plans/${key}.json`),
    formulary: fid => json(`data/formularies/${fid}.json`),
  };
})();
