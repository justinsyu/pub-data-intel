"""plan_dim (one row per contract+plan+segment) and plan_county bridge."""

PLAN_DIM_SQL = """
CREATE OR REPLACE TABLE plan_dim AS
SELECT
    CONTRACT_ID || '_' || PLAN_ID || '_' || SEGMENT_ID AS plan_key,
    CONTRACT_ID AS contract_id,
    PLAN_ID AS plan_id,
    SEGMENT_ID AS segment_id,
    any_value(CONTRACT_NAME) AS contract_name,
    any_value(PLAN_NAME) AS plan_name,
    any_value(FORMULARY_ID) AS formulary_id,
    CASE substr(CONTRACT_ID, 1, 1)
        WHEN 'H' THEN 'MA' WHEN 'R' THEN 'MA_REGIONAL' WHEN 'S' THEN 'PDP'
        ELSE 'OTHER' END AS plan_type,
    any_value(SNP) AS snp,
    max(PLAN_SUPPRESSED_YN) AS suppressed_yn,
    try_cast(nullif(trim(any_value(PREMIUM)), '') AS DOUBLE) AS premium,
    try_cast(nullif(trim(any_value(DEDUCTIBLE)), '') AS DOUBLE) AS deductible
FROM raw_plan_info
GROUP BY 1, 2, 3, 4
"""

MULTI_FORMULARY_SQL = """
SELECT CONTRACT_ID, PLAN_ID, SEGMENT_ID
FROM raw_plan_info
GROUP BY 1, 2, 3
HAVING count(DISTINCT FORMULARY_ID) > 1
"""

PLAN_COUNTY_SQL = """
CREATE OR REPLACE TABLE plan_county AS
SELECT DISTINCT plan_key, county_code FROM (
    SELECT CONTRACT_ID || '_' || PLAN_ID || '_' || SEGMENT_ID AS plan_key,
           COUNTY_CODE AS county_code
    FROM raw_plan_info
    WHERE substr(CONTRACT_ID, 1, 1) = 'H'
      AND nullif(trim(COUNTY_CODE), '') IS NOT NULL
    UNION ALL
    SELECT p.CONTRACT_ID || '_' || p.PLAN_ID || '_' || p.SEGMENT_ID,
           g.COUNTY_CODE
    FROM raw_plan_info p
    JOIN raw_geo g
      ON trim(p.MA_REGION_CODE) = trim(g.MA_REGION_CODE)
    WHERE substr(p.CONTRACT_ID, 1, 1) = 'R'
      AND nullif(trim(p.MA_REGION_CODE), '') IS NOT NULL
    UNION ALL
    SELECT p.CONTRACT_ID || '_' || p.PLAN_ID || '_' || p.SEGMENT_ID,
           g.COUNTY_CODE
    FROM raw_plan_info p
    JOIN raw_geo g
      ON trim(p.PDP_REGION_CODE) = trim(g.PDP_REGION_CODE)
    WHERE substr(p.CONTRACT_ID, 1, 1) = 'S'
      AND nullif(trim(p.PDP_REGION_CODE), '') IS NOT NULL
)
"""


def build(con) -> dict:
    multi = con.execute(MULTI_FORMULARY_SQL).fetchall()
    if multi:
        raise ValueError(
            f"plans: {len(multi)} plan(s) carry more than one formulary ID, "
            f"first: {multi[:5]}"
        )
    con.execute(PLAN_DIM_SQL)
    con.execute(PLAN_COUNTY_SQL)
    n_plans = con.execute("SELECT count(*) FROM plan_dim").fetchone()[0]
    n_bridge = con.execute("SELECT count(*) FROM plan_county").fetchone()[0]
    n_orphan = con.execute(
        """
        SELECT count(*) FROM plan_dim d
        WHERE NOT EXISTS (
            SELECT 1 FROM plan_county c WHERE c.plan_key = d.plan_key)
        """
    ).fetchone()[0]
    stats = {"n_plans": n_plans, "n_bridge_rows": n_bridge,
             "n_plans_without_counties": n_orphan}
    print(f"transform: plan_dim {n_plans:,} plans, bridge {n_bridge:,} rows, "
          f"{n_orphan} plans without counties")
    return stats
