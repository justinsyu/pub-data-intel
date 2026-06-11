window.MPDP = window.MPDP || {views: {}};
MPDP.views.methods = {
  async render(root) {
    const meta = await Data.meta();
    root.innerHTML = `
      <h2>Methods and caveats</h2>
      <div class="panel"><h3>Source</h3>
        <p>CMS Monthly Prescription Drug Plan Formulary and Pharmacy Network
        Information PUF, snapshot dated ${Fmt.esc(meta.vintage)}, contract year
        ${Fmt.esc(meta.contract_year)}. Drug names resolve through the RxNorm
        Current Prescribable Content release with an RxNav fallback for retired
        identifiers.</p></div>
      <div class="panel"><h3>Grain and aggregation rules</h3><ul>
        <li>The basic formulary file carries one row per formulary and RXCUI
        with a single representative NDC; this dashboard reports at RXCUI
        grain. If a future vintage shipped multiple NDC rows per drug, a
        restriction would be shown when any NDC carries it and the tier shown
        would be the modal tier.</li>
        <li>A "plan" is one CONTRACT_ID + PLAN_ID + SEGMENT_ID combination.
        Plans reference one of ${Fmt.num(meta.counts.formularies)} formularies;
        coverage statistics are computed at the formulary level.</li>
        <li>Excluded drugs are reported per contract-plan (the source file has
        no segment), so exclusions apply to every segment of that plan.</li></ul>
      </div>
      <div class="panel"><h3>Caveats</h3><ul>
        <li>NDCs in the source are proxy codes for drug products, not complete
        package-level listings.</li>
        <li>Plans flagged as suppressed by CMS keep their identity rows but
        their cost data is hidden here.</li>
        <li>County mapping crosses SSA county codes to FIPS by state and county
        name; 54 SSA codes (mostly Guam and American Samoa villages and
        dissolved jurisdictions) do not map and render as no-data.</li>
        <li>The county map outlines use a 2010-vintage boundary file; a small
        number of renamed or reorganized counties (for example Kusilvak AK and
        Oglala Lakota SD) and the territories render as no-data on the map even
        when plan data exists for them.</li>
        <li>Local MA plans (H contracts) list exact service-area counties;
        regional MA (R) and PDP (S) contracts are expanded from their CMS
        regions, so county-level precision differs by plan type.</li>
        <li>This is a single monthly snapshot; no trend analysis.</li>
        <li>Pharmacy network data (preferred pharmacies, dispensing fees) is
        not included in this version.</li></ul></div>`;
  },
};
