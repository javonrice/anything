"""
State licensing database configs.

Strategies:
  "direct"    - url points straight to a CSV/Excel file
  "discover"  - visit discover_url, find a link matching discover_pattern, download it

col_map: source column names (lowercase) → standard schema fields
filter_col / filter_val: keep only rows where that col matches one of the values (case-insensitive)
"""

STATES = [

    # =========================================================================
    # ILLINOIS — IDFPR
    # https://idfpr.illinois.gov/profs/profdownload/
    # Lists profession-specific CSV files; we match by text/href keyword.
    # =========================================================================
    {
        "state": "IL",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://idfpr.illinois.gov/profs/profdownload/",
        "discover_pattern": ["real estate broker", "realestate", "real_estate"],
        "format": "csv",
        "col_map": {
            "license number":  "license_number",
            "license type":    "license_type",
            "status":          "license_status",
            "last name":       "_last",
            "first name":      "_first",
            "middle name":     "_mid",
            "business name":   "business_name",
            "address 1":       "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "phone":           "phone",
            "email":           "email",
        },
        "filter_col": "status",
        "filter_val": ["active", "active-approved to renew"],
    },
    {
        "state": "IL",
        "category": "insurance",
        "strategy": "discover",
        "discover_url": "https://idfpr.illinois.gov/profs/profdownload/",
        "discover_pattern": ["insurance producer", "insurance_producer"],
        "format": "csv",
        "col_map": {
            "license number":  "license_number",
            "license type":    "license_type",
            "status":          "license_status",
            "last name":       "_last",
            "first name":      "_first",
            "middle name":     "_mid",
            "business name":   "business_name",
            "address 1":       "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "phone":           "phone",
            "email":           "email",
        },
        "filter_col": "status",
        "filter_val": ["active", "active-approved to renew"],
    },

    # =========================================================================
    # NORTH CAROLINA — NCREC (Real Estate)
    # =========================================================================
    {
        "state": "NC",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://www.ncrec.gov/PublicRecords",
        "discover_pattern": [".csv", ".xlsx", "licensee", "active", "download"],
        "format": "csv",
        "col_map": {
            "full name":       "full_name",
            "name":            "full_name",
            "license number":  "license_number",
            "license type":    "license_type",
            "license status":  "license_status",
            "status":          "license_status",
            "primary phone":   "phone",
            "phone":           "phone",
            "email":           "email",
            "address1":        "address",
            "address":         "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "firm name":       "business_name",
            "company":         "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active"],
    },

    # =========================================================================
    # NORTH CAROLINA — NCDOI (Insurance)
    # =========================================================================
    {
        "state": "NC",
        "category": "insurance",
        "strategy": "discover",
        "discover_url": "https://www.ncdoi.gov/Licensing/Agent-Licensee-Data-Download",
        "discover_pattern": [".csv", ".xlsx", ".zip", "download", "agent", "licensee"],
        "format": "csv",
        "col_map": {
            "full name":       "full_name",
            "name":            "full_name",
            "license number":  "license_number",
            "license type":    "license_type",
            "status":          "license_status",
            "phone":           "phone",
            "email":           "email",
            "address":         "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "business name":   "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active"],
    },

    # =========================================================================
    # MINNESOTA — Commerce (Real Estate + Insurance)
    # =========================================================================
    {
        "state": "MN",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://mn.gov/commerce/licensees/",
        "discover_pattern": ["real estate", "salesperson", "broker", ".csv", ".xlsx"],
        "format": "csv",
        "col_map": {
            "full name":       "full_name",
            "name":            "full_name",
            "license number":  "license_number",
            "license type":    "license_type",
            "status":          "license_status",
            "phone":           "phone",
            "email":           "email",
            "address":         "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "company":         "business_name",
            "firm":            "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active"],
    },
    {
        "state": "MN",
        "category": "insurance",
        "strategy": "discover",
        "discover_url": "https://mn.gov/commerce/licensees/",
        "discover_pattern": ["insurance", "producer", "agent", ".csv", ".xlsx"],
        "format": "csv",
        "col_map": {
            "full name":       "full_name",
            "name":            "full_name",
            "license number":  "license_number",
            "license type":    "license_type",
            "status":          "license_status",
            "phone":           "phone",
            "email":           "email",
            "address":         "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "company":         "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active"],
    },

    # =========================================================================
    # OHIO — eLicense (Real Estate)
    # =========================================================================
    {
        "state": "OH",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://elicense.ohio.gov/oh_lms_licensee/PublicLicenseeSearch/",
        "discover_pattern": [".csv", "download", "export", "real estate"],
        "format": "csv",
        "col_map": {
            "full name":      "full_name",
            "name":           "full_name",
            "license number": "license_number",
            "license type":   "license_type",
            "status":         "license_status",
            "phone":          "phone",
            "email":          "email",
            "address":        "address",
            "city":           "city",
            "state":          "state_field",
            "zip code":       "zip",
            "zip":            "zip",
            "business name":  "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active"],
    },

]

# Standard output column order
OUTPUT_FIELDS = [
    "category",
    "state",
    "full_name",
    "business_name",
    "email",
    "phone",
    "address",
    "city",
    "zip",
    "license_number",
    "license_type",
    "license_status",
    "source_url",
]
