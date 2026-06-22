"""
State licensing database configs.

Two download strategies:
  "direct"    - url points straight to a CSV/Excel file
  "socrata"   - state uses a Socrata open-data portal; we paginate via their API
  "discover"  - visit discover_url, find a link matching discover_pattern, download that

col_map: source column names → standard schema fields
  Standard fields: full_name, email, phone, address, city, zip,
                   license_number, license_type, license_status, business_name

filter_col / filter_val: keep only rows where filter_col (after mapping) is in filter_val
                          (case-insensitive). Omit to keep all rows.
"""

STATES = [

    # =========================================================================
    # ILLINOIS — IDFPR
    # https://idfpr.illinois.gov/profs/profdownload/
    # Well-documented public download page; files named by profession code.
    # =========================================================================
    {
        "state": "IL",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://idfpr.illinois.gov/profs/profdownload/",
        # Match any link whose text or href contains these keywords
        "discover_pattern": ["real estate broker", "realestate", "real_estate_broker"],
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
    # TEXAS — TREC (Real Estate)
    # Socrata open-data portal: data.texas.gov
    # Dataset 4x4 IDs confirmed from Texas open data catalog.
    # =========================================================================
    {
        "state": "TX",
        "category": "real_estate",
        "strategy": "socrata",
        "socrata_domain": "data.texas.gov",
        # Try multiple known dataset IDs; first one to respond wins
        "socrata_ids": ["vhub-c3bv", "jrnr-wy3v", "g4qm-6fci"],
        "col_map": {
            "name":                "full_name",
            "licensee_name":       "full_name",
            "full_name":           "full_name",
            "license_num":         "license_number",
            "license_number":      "license_number",
            "license_type":        "license_type",
            "status":              "license_status",
            "license_status":      "license_status",
            "phone":               "phone",
            "business_phone":      "phone",
            "email":               "email",
            "business_email":      "email",
            "mailing_address":     "address",
            "address":             "address",
            "city":                "city",
            "mailing_city":        "city",
            "state":               "state_field",
            "zip":                 "zip",
            "mailing_zip":         "zip",
            "business_name":       "business_name",
            "firm_name":           "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active", "active-approved to renew"],
    },

    # =========================================================================
    # TEXAS — TDI (Insurance)
    # Socrata: data.texas.gov
    # =========================================================================
    {
        "state": "TX",
        "category": "insurance",
        "strategy": "socrata",
        "socrata_domain": "data.texas.gov",
        "socrata_ids": ["mhpf-5rhz", "qk8j-7r5v", "psh4-yr8r"],
        "col_map": {
            "name":                "full_name",
            "licensee_name":       "full_name",
            "full_name":           "full_name",
            "license_number":      "license_number",
            "license_type":        "license_type",
            "status":              "license_status",
            "license_status":      "license_status",
            "phone":               "phone",
            "business_phone":      "phone",
            "email":               "email",
            "business_email":      "email",
            "address":             "address",
            "mailing_address":     "address",
            "city":                "city",
            "state":               "state_field",
            "zip":                 "zip",
            "business_name":       "business_name",
        },
        "filter_col": "status",
        "filter_val": ["active"],
    },

    # =========================================================================
    # MINNESOTA — COMMERCE (Real Estate + Insurance)
    # MN uses a public data portal with direct CSV downloads.
    # https://mn.gov/commerce/licensees/
    # =========================================================================
    {
        "state": "MN",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://mn.gov/commerce/licensees/",
        "discover_pattern": ["real estate", "salesperson", "broker"],
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
        "discover_pattern": ["insurance", "producer", "agent"],
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
    # NORTH CAROLINA — NCREC (Real Estate)
    # Direct download page; file served as zip or CSV
    # =========================================================================
    {
        "state": "NC",
        "category": "real_estate",
        "strategy": "discover",
        "discover_url": "https://www.ncrec.gov/PublicRecords",
        "discover_pattern": [".csv", ".xlsx", "download", "licensee", "active"],
        "format": "csv",
        "col_map": {
            "full name":       "full_name",
            "name":            "full_name",
            "license number":  "license_number",
            "license type":    "license_type",
            "license status":  "license_status",
            "primary phone":   "phone",
            "phone":           "phone",
            "email":           "email",
            "address1":        "address",
            "address":         "address",
            "city":            "city",
            "state":           "state_field",
            "zip":             "zip",
            "firm name":       "business_name",
        },
        "filter_col": "license status",
        "filter_val": ["active"],
    },

    # =========================================================================
    # OHIO — eLicense (Real Estate)
    # https://elicense.ohio.gov/
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
