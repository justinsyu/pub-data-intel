"""Verified retina code sets. Single source of truth (spec section: Verified code sets)."""

# ICD-10-CM families (prefix match against dotted codes)
ICD10_WET_AMD_PREFIX = "H35.32"
ICD10_DRY_AMD_PREFIX = "H35.31"
ICD10_CRVO_PREFIX = "H34.81"
ICD10_RETINA_PREFIXES = [ICD10_WET_AMD_PREFIX, ICD10_DRY_AMD_PREFIX, "H34.8", "E08.3", "E09.3", "E10.3", "E11.3", "E13.3"]

# Procedures (codes only; neutral labels, no licensed AMA descriptors)
PROCEDURE_HCPCS = {
    "67028": "intravitreal injection",
    "92134": "OCT retina imaging",
    "92133": "OCT optic nerve imaging",
    "92235": "fluorescein angiography",
    "92250": "fundus photography",
}

ANTIVEGF_ORIGINATOR_HCPCS = ["J0178", "J0177", "J2778", "J2777", "J0179"]
ANTIVEGF_BIOSIMILAR_HCPCS = ["Q5124", "Q5128", "Q5147", "Q5149"]
GA_COMPLEMENT_HCPCS = ["J2781", "J2782"]
ALL_DRUG_HCPCS = ANTIVEGF_ORIGINATOR_HCPCS + ANTIVEGF_BIOSIMILAR_HCPCS + GA_COMPLEMENT_HCPCS

DRUG_LABELS = {
    "J0178": "aflibercept (Eylea)",
    "J0177": "aflibercept HD (Eylea HD)",
    "J2778": "ranibizumab (Lucentis)",
    "J2777": "faricimab-svoa (Vabysmo)",
    "J0179": "brolucizumab-dbll (Beovu)",
    "Q5124": "ranibizumab-nuna (Byooviz)",
    "Q5128": "ranibizumab-eqrn (Cimerli)",
    "Q5147": "aflibercept-ayyh (Pavblu)",
    "Q5149": "aflibercept-abzv (Enzeevu)",
    "J2781": "pegcetacoplan (Syfovre)",
    "J2782": "avacincaptad pegol (Izervay)",
}

TAXONOMY_OPHTHALMOLOGY = "207W00000X"
TAXONOMY_RETINA_SPECIALIST = "207WX0107X"

POLICY_ANCHOR_ARTICLE = "A52451"  # CMS billing-and-coding article family for anti-VEGF
# Display form with "A" prefix; the MCD export's article_id is the bare number
# ("52451"), so comparisons against export data must strip the prefix.

ALL_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

# Medicare A/B MAC jurisdictions (states and DC only)
MAC_JURISDICTIONS = {
    "JE": ["CA", "HI", "NV"],
    "JF": ["AK", "AZ", "ID", "MT", "ND", "OR", "SD", "UT", "WA", "WY"],
    "J5": ["IA", "KS", "MO", "NE"],
    "J6": ["IL", "MN", "WI"],
    "J8": ["IN", "MI"],
    "J15": ["KY", "OH"],
    "JH": ["AR", "CO", "LA", "MS", "NM", "OK", "TX"],
    "JL": ["DE", "DC", "MD", "NJ", "PA"],
    "JJ": ["AL", "GA", "TN"],
    "JM": ["NC", "SC", "VA", "WV"],
    "JN": ["FL"],
    "JK": ["CT", "ME", "MA", "NH", "NY", "RI", "VT"],
}

_STATE_TO_MAC = {s: j for j, sts in MAC_JURISDICTIONS.items() for s in sts}


def state_to_mac(state: str) -> str:
    return _STATE_TO_MAC[state.upper()]
