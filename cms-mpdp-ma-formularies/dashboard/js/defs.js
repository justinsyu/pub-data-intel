// Definitions for the abbreviations and Medicare terms used across the views.
// Defs.abbr(key) wraps a term in an <abbr> with a hover tooltip; Defs.tip(key)
// returns the tooltip text for a title attribute; Defs.glossaryHtml() renders
// the full reference list shown in the Methods view.
window.Defs = (() => {
  const map = {
    PA: ["Prior authorization", "The plan must approve coverage before the drug is dispensed."],
    ST: ["Step therapy", "The plan requires trying one or more alternative drugs first."],
    QL: ["Quantity limit", "The plan limits the amount dispensed per fill or time period (shown as amount / days)."],
    SNP: ["Special Needs Plan", "A Medicare Advantage plan limited to specific beneficiaries: dual-eligible, chronic-condition, or institutional."],
    "D-SNP": ["Dual-eligible Special Needs Plan", "For people enrolled in both Medicare and Medicaid."],
    "C-SNP": ["Chronic-condition Special Needs Plan", "For people with specific severe or disabling chronic conditions."],
    "I-SNP": ["Institutional Special Needs Plan", "For people who live in an institution such as a nursing home."],
    MA: ["Medicare Advantage (local)", "A local HMO or PPO Medicare Advantage plan that includes Part D drug coverage."],
    "MA regional": ["Medicare Advantage (regional)", "A regional PPO Medicare Advantage plan covering a multi-state CMS region."],
    PDP: ["Stand-alone Prescription Drug Plan", "Medicare Part D drug coverage purchased separately from medical coverage."],
    Tier: ["Cost-sharing tier", "Cost-sharing level; lower tiers usually cost less. Conventionally 1 generic, 2 preferred brand, 3 non-preferred brand, 4 specialty, with plan-defined higher tiers."],
    Specialty: ["Specialty tier", "A tier for high-cost drugs, typically charged as coinsurance rather than a flat copay."],
    Copay: ["Copay", "A fixed dollar amount the beneficiary pays per fill."],
    Coinsurance: ["Coinsurance", "A percentage of the drug cost the beneficiary pays."],
    Preferred: ["Preferred pharmacy", "An in-network pharmacy with lower negotiated cost sharing than a standard pharmacy."],
    "Coverage phase": ["Coverage phase", "The Part D benefit stage: pre-deductible, initial coverage, or catastrophic."],
    "Negotiation-selected": ["Negotiation-selected drug", "A drug selected for the Medicare Drug Price Negotiation Program."],
    Suppressed: ["Suppressed plan", "CMS withheld this plan's cost-sharing data from the public file."],
    Capped: ["Capped benefit", "The drug has a capped (limited) benefit under the plan."],
    Excluded: ["Excluded drug", "A drug the plan reports as not on its formulary; residual terms may still apply."],
  };
  function tip(key) {
    const e = map[key];
    return e ? `${e[0]}: ${e[1]}` : "";
  }
  function abbr(key, text) {
    const label = text == null ? key : text;
    const e = map[key];
    return e
      ? `<abbr title="${Fmt.esc(tip(key))}">${Fmt.esc(label)}</abbr>`
      : Fmt.esc(label);
  }
  function glossaryHtml() {
    return `<dl class="glossary">` +
      Object.values(map).map(([t, d]) =>
        `<dt>${Fmt.esc(t)}</dt><dd>${Fmt.esc(d)}</dd>`).join("") +
      `</dl>`;
  }
  return {map, tip, abbr, glossaryHtml};
})();
