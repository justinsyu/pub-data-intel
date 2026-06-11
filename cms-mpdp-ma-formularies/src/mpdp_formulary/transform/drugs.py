"""formulary_drug (formulary x RXCUI grain) and drug_dim (per-RXCUI counts)."""

FORMULARY_DRUG_SQL = """
CREATE OR REPLACE TABLE formulary_drug AS
SELECT
    FORMULARY_ID AS formulary_id,
    RXCUI AS rxcui,
    mode(try_cast(TIER_LEVEL_VALUE AS INTEGER)) AS tier,
    min(try_cast(TIER_LEVEL_VALUE AS INTEGER)) AS tier_min,
    max(try_cast(TIER_LEVEL_VALUE AS INTEGER)) AS tier_max,
    bool_or(PRIOR_AUTHORIZATION_YN = 'Y') AS pa,
    bool_or(STEP_THERAPY_YN = 'Y') AS st,
    bool_or(QUANTITY_LIMIT_YN = 'Y') AS ql,
    max(CASE WHEN QUANTITY_LIMIT_YN = 'Y'
             THEN nullif(trim(QUANTITY_LIMIT_AMOUNT), '') END) AS ql_amount,
    max(CASE WHEN QUANTITY_LIMIT_YN = 'Y'
             THEN nullif(trim(QUANTITY_LIMIT_DAYS), '') END) AS ql_days,
    bool_or(SELECTED_DRUG_YN = 'Y') AS selected,
    count(DISTINCT NDC) AS ndc_count
FROM raw_basic
GROUP BY 1, 2
"""

DRUG_DIM_SQL = """
CREATE OR REPLACE TABLE drug_dim AS
SELECT
    rxcui,
    count(*) AS n_formularies,
    sum(pa::INT) AS n_pa,
    sum(st::INT) AS n_st,
    sum(ql::INT) AS n_ql,
    bool_or(selected) AS selected,
    sum(ndc_count) AS ndc_total
FROM formulary_drug
GROUP BY 1
"""


def build(con) -> dict:
    con.execute(FORMULARY_DRUG_SQL)
    con.execute(DRUG_DIM_SQL)
    n_fd = con.execute("SELECT count(*) FROM formulary_drug").fetchone()[0]
    n_form = con.execute(
        "SELECT count(DISTINCT formulary_id) FROM formulary_drug").fetchone()[0]
    n_drugs = con.execute("SELECT count(*) FROM drug_dim").fetchone()[0]
    stats = {"n_formulary_drug": n_fd, "n_formularies": n_form, "n_drugs": n_drugs}
    print(f"transform: formulary_drug {n_fd:,} rows, "
          f"{n_form} formularies, {n_drugs:,} distinct RXCUIs")
    return stats
