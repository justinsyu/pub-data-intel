"""All external URLs live here and only here.

If a URL 404s, locate the current one on the agency page in the comment
and update it here. Do not embed URLs anywhere else in the codebase.
"""

URLS = {
    # Census gazetteer (counties): https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
    # Directory is 2024_Gazetteer (no trailing 's'); confirmed via www2.census.gov index
    "census_gazetteer_counties": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip",
    # NBER CBSA-county crosswalk: https://www.nber.org/research/data/census-core-based-statistical-area-cbsa-federal-information-processing-series-fips-county-crosswalk
    # File moved to versioned subdirectory; cbsa2fipsxw.csv (unversioned) no longer exists
    "nber_cbsa_xwalk": "https://data.nber.org/cbsa-csa-fips-county-crosswalk/2023/cbsa2fipsxw_2023.csv",
    # Census ACS 5-year API: https://www.census.gov/data/developers/data-sets/acs-5year.html
    # Base URL returns 404 without query params (?get=...&for=...); reachable with params
    "census_acs5": "https://api.census.gov/data/2023/acs/acs5",
    # Census ZCTA-county relationship: https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html
    "census_zcta_county_rel": "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt",
    # CDC/ATSDR SVI: https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html
    # Filename is SVI_2022_US_county (underscore after SVI); confirmed via svi.cdc.gov/js/loadXML.js URL template
    "cdc_svi_county": "https://svi.cdc.gov/Documents/Data/2022/csv/states_counties/SVI_2022_US_county.csv",
    # USDA ERS RUCC: https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/
    "usda_rucc": "https://ers.usda.gov/sites/default/files/_laserfiche/DataFiles/53251/Ruralurbancontinuumcodes2023.csv",
    # CMS open data catalog: https://data.cms.gov/api-docs
    "cms_data_json": "https://data.cms.gov/data.json",
    # CMS Provider Data Catalog metastore: https://data.cms.gov/provider-data/docs
    "pdc_metastore": "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items",
    "pdc_datastore_query": "https://data.cms.gov/provider-data/api/1/datastore/query",
    # ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/api
    "clinicaltrials_v2": "https://clinicaltrials.gov/api/v2/studies",
    # Open Payments DKAN API: https://openpaymentsdata.cms.gov/about/api
    "openpayments_metastore": "https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items",
    "openpayments_datastore_query": "https://openpaymentsdata.cms.gov/api/1/datastore/query",
    # HRSA 340B OPAIS daily covered-entity export: https://340bopais.hrsa.gov/Reports
    # KNOWN-FAILING: OPAIS migrated to Blazor; daily export is now session-generated via
    # downloadFileFromStream (no static URL). Access requires browser session at
    # https://340bopais.hrsa.gov/Reports or UI automation. Placeholder URL retained for
    # registry completeness; ingest task (P14) must handle this via browser automation.
    "hrsa_340b_ce": "https://340bopais.hrsa.gov/dailyreports/OPA_CE_DAILY_REPORT.csv",
}

# Datasets resolved by title from the CMS data.json catalog (titles, not UUIDs,
# because UUIDs change with versions).
CMS_DATASET_TITLES = {
    "mupphy": "Medicare Physician & Other Practitioners - by Provider and Service",
    "monthly_enrollment": "Medicare Monthly Enrollment",
    "qdd": "Medicare Part B Spending by Drug",
}

PDC_DATASET_TITLES = {
    "dac_ndf": "National Downloadable File",
    "dac_fa": "Facility Affiliation Data",
}

# Manual-download fallback (license click-through): Medicare Coverage Database
# https://www.cms.gov/medicare-coverage-database/downloads/downloadable-databases.aspx
# Download current LCD and Article zips into retina/pilot/data/cache/mcd/ by hand
# if scripted retrieval is blocked.
MCD_LOCAL_DIR = "data/cache/mcd"
