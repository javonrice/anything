"""
State licensing database configs.
Each entry defines how to download + parse a state's bulk licensee file.

url:        Direct download URL for the bulk file (CSV or Excel)
format:     "csv" or "excel"
category:   "insurance" or "real_estate"
sheet:      Excel sheet name or index (for Excel only, optional)
col_map:    Maps source column names → standard schema field names
            Required standard fields: full_name, email, phone, address, city, zip, license_number, license_status, business_name

skip_rows:  Number of header rows to skip (Excel only)
encoding:   File encoding (CSV only, default utf-8)
filter_col: Column to filter active-only records
filter_val: Value(s) in filter_col that mean "active" (list of strings, case-insensitive)
"""

STATES = [

    # -------------------------------------------------------------------------
    # TEXAS — Real Estate (TREC)
    # https://www.trec.texas.gov/agency-information/open-records
    # -------------------------------------------------------------------------
    {
        "state": "TX",
        "category": "real_estate",
        "url": "https://www.trec.texas.gov/sites/default/files/uploads/agency/open-records/active-licensees.xlsx",
        "format": "excel",
        "sheet": 0,
        "skip_rows": 0,
        "col_map": {
            "Name":             "full_name",
            "License Num":      "license_number",
            "License Type":     "license_type",
            "Status":           "license_status",
            "Phone":            "phone",
            "Email":            "email",
            "Mailing Address":  "address",
            "City":             "city",
            "State":            "state_field",
            "Zip":              "zip",
            "Business Name":    "business_name",
        },
        "filter_col": "Status",
        "filter_val": ["active", "active-approved to renew"],
    },

    # -------------------------------------------------------------------------
    # TEXAS — Insurance (TDI)
    # https://www.tdi.texas.gov/agent/agentlicensesearch.html
    # -------------------------------------------------------------------------
    {
        "state": "TX",
        "category": "insurance",
        "url": "https://www.tdi.texas.gov/agent/documents/agntindv.xlsx",
        "format": "excel",
        "sheet": 0,
        "skip_rows": 0,
        "col_map": {
            "Name":                 "full_name",
            "License Number":       "license_number",
            "License Type":         "license_type",
            "Status":               "license_status",
            "Business Phone":       "phone",
            "Business Email":       "email",
            "Business Addr1":       "address",
            "Business City":        "city",
            "Business State":       "state_field",
            "Business Zip":         "zip",
            "Business Name":        "business_name",
        },
        "filter_col": "Status",
        "filter_val": ["active"],
    },

    # -------------------------------------------------------------------------
    # GEORGIA — Real Estate (GREC)
    # https://grec.state.ga.us/information/downloads.html
    # -------------------------------------------------------------------------
    {
        "state": "GA",
        "category": "real_estate",
        "url": "https://grec.state.ga.us/sites/grec.state.ga.us/files/ActiveLicensees.csv",
        "format": "csv",
        "encoding": "latin-1",
        "col_map": {
            "LicenseeFullName":   "full_name",
            "LicenseNumber":      "license_number",
            "LicenseType":        "license_type",
            "LicenseStatus":      "license_status",
            "Phone":              "phone",
            "Email":              "email",
            "Address":            "address",
            "City":               "city",
            "State":              "state_field",
            "Zip":                "zip",
            "BusinessName":       "business_name",
        },
        "filter_col": "LicenseStatus",
        "filter_val": ["active"],
    },

    # -------------------------------------------------------------------------
    # NORTH CAROLINA — Real Estate (NCREC)
    # https://www.ncrec.gov/
    # -------------------------------------------------------------------------
    {
        "state": "NC",
        "category": "real_estate",
        "url": "https://www.ncrec.gov/Portals/0/documents/licensee/ActiveLicensees.csv",
        "format": "csv",
        "col_map": {
            "Full Name":          "full_name",
            "License Number":     "license_number",
            "License Type":       "license_type",
            "License Status":     "license_status",
            "Primary Phone":      "phone",
            "Email":              "email",
            "Address1":           "address",
            "City":               "city",
            "State":              "state_field",
            "Zip":                "zip",
            "Firm Name":          "business_name",
        },
        "filter_col": "License Status",
        "filter_val": ["active"],
    },

    # -------------------------------------------------------------------------
    # ILLINOIS — Real Estate + Insurance (IDFPR)
    # https://idfpr.illinois.gov/profs/profdownload/
    # -------------------------------------------------------------------------
    {
        "state": "IL",
        "category": "real_estate",
        "url": "https://idfpr.illinois.gov/profs/profdownload/Real_Estate_Broker.csv",
        "format": "csv",
        "col_map": {
            "FULL_NAME":        "full_name",
            "LICENSE_NUMBER":   "license_number",
            "LICENSE_TYPE":     "license_type",
            "LICENSE_STATUS":   "license_status",
            "PHONE":            "phone",
            "EMAIL":            "email",
            "ADDRESS":          "address",
            "CITY":             "city",
            "STATE":            "state_field",
            "ZIP":              "zip",
            "BUSINESS_NAME":    "business_name",
        },
        "filter_col": "LICENSE_STATUS",
        "filter_val": ["active", "renewed"],
    },
    {
        "state": "IL",
        "category": "insurance",
        "url": "https://idfpr.illinois.gov/profs/profdownload/Insurance_Producer.csv",
        "format": "csv",
        "col_map": {
            "FULL_NAME":        "full_name",
            "LICENSE_NUMBER":   "license_number",
            "LICENSE_TYPE":     "license_type",
            "LICENSE_STATUS":   "license_status",
            "PHONE":            "phone",
            "EMAIL":            "email",
            "ADDRESS":          "address",
            "CITY":             "city",
            "STATE":            "state_field",
            "ZIP":              "zip",
            "BUSINESS_NAME":    "business_name",
        },
        "filter_col": "LICENSE_STATUS",
        "filter_val": ["active", "renewed"],
    },

    # -------------------------------------------------------------------------
    # OHIO — Real Estate (ODRE)
    # https://com.ohio.gov/divisions/real-estate-and-professional-licensing
    # -------------------------------------------------------------------------
    {
        "state": "OH",
        "category": "real_estate",
        "url": "https://elicense.ohio.gov/oh_lms_licensee/PublicLicenseeSearch/Download?licenseType=REALEST",
        "format": "csv",
        "col_map": {
            "Full Name":          "full_name",
            "License Number":     "license_number",
            "License Type":       "license_type",
            "Status":             "license_status",
            "Business Phone":     "phone",
            "Email":              "email",
            "Address":            "address",
            "City":               "city",
            "State":              "state_field",
            "Zip Code":           "zip",
            "Business Name":      "business_name",
        },
        "filter_col": "Status",
        "filter_val": ["active"],
    },

    # -------------------------------------------------------------------------
    # WASHINGTON — Real Estate (DOL)
    # https://www.dol.wa.gov/business/realestate/
    # -------------------------------------------------------------------------
    {
        "state": "WA",
        "category": "real_estate",
        "url": "https://fortress.wa.gov/dol/dolprod/bpdLicenseQuery/DownloadLicensees?profCode=REBROK",
        "format": "csv",
        "col_map": {
            "Full Name":          "full_name",
            "License Number":     "license_number",
            "License Type":       "license_type",
            "Status":             "license_status",
            "Phone":              "phone",
            "Email":              "email",
            "Address":            "address",
            "City":               "city",
            "State":              "state_field",
            "Zip":                "zip",
            "Business Name":      "business_name",
        },
        "filter_col": "Status",
        "filter_val": ["active"],
    },

    # -------------------------------------------------------------------------
    # ARIZONA — Real Estate (ADRE)
    # https://azre.gov/public/licensee-lookup
    # -------------------------------------------------------------------------
    {
        "state": "AZ",
        "category": "real_estate",
        "url": "https://azre.gov/sites/default/files/public/data/LicenseeExport.csv",
        "format": "csv",
        "col_map": {
            "Name":               "full_name",
            "License Number":     "license_number",
            "License Type":       "license_type",
            "License Status":     "license_status",
            "Business Phone":     "phone",
            "Email":              "email",
            "Address":            "address",
            "City":               "city",
            "State":              "state_field",
            "Zip":                "zip",
            "Company Name":       "business_name",
        },
        "filter_col": "License Status",
        "filter_val": ["active", "current"],
    },

    # -------------------------------------------------------------------------
    # NORTH CAROLINA — Insurance (NCDOI)
    # https://www.ncdoi.gov/licensing/
    # -------------------------------------------------------------------------
    {
        "state": "NC",
        "category": "insurance",
        "url": "https://www.ncdoi.gov/Portals/0/Files/Licensing/ActiveAgents.csv",
        "format": "csv",
        "col_map": {
            "Name":               "full_name",
            "License Number":     "license_number",
            "License Type":       "license_type",
            "Status":             "license_status",
            "Phone":              "phone",
            "Email":              "email",
            "Address":            "address",
            "City":               "city",
            "State":              "state_field",
            "Zip":                "zip",
            "Business Name":      "business_name",
        },
        "filter_col": "Status",
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
