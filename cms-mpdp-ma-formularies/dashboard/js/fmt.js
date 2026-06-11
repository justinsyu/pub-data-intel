const Fmt = {
  money: v => v == null ? "n/a" : "$" + Number(v).toFixed(2),
  pct: v => v == null ? "n/a" : Number(v).toFixed(1) + "%",
  num: v => v == null ? "n/a" : Number(v).toLocaleString("en-US"),
  flag: b => b ? "Yes" : "No",
  esc: s => String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c])),
  // Channel cell from [type, amt, min, max]: type 0/null = not offered,
  // 1 = copay in dollars, 2 = coinsurance as a fraction of drug cost.
  cost(ch) {
    if (!ch || !ch[0]) return "n/a";
    const [type, amt, min, max] = ch;
    if (type === 1) return Fmt.money(amt);
    let s = Math.round((amt || 0) * 100) + "%";
    if (min) s += `, min ${Fmt.money(min)}`;
    if (max) s += `, max ${Fmt.money(max)}`;
    return s;
  },
  // Decode one status-vector character: null = not listed, else PA/ST/QL bits.
  status(ch) {
    if (!ch || ch === "-") return null;
    const m = parseInt(ch, 16);
    return {pa: !!(m & 2), st: !!(m & 4), ql: !!(m & 8)};
  },
  restr(ch) {
    const s = Fmt.status(ch);
    if (!s) return "not listed";
    const parts = [];
    if (s.pa) parts.push("PA");
    if (s.st) parts.push("ST");
    if (s.ql) parts.push("QL");
    return parts.length ? parts.join(" + ") : "unrestricted";
  },
};
