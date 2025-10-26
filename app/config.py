import os

# --- External services ---
SEC_USER_EMAIL: str = os.getenv("SEC_USER_EMAIL", "email@example.com")  # required by SEC for CompanyFacts
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "30"))                 # seconds for HTTP requests

# --- Google Sheets fallback (for Google Finance) ---
GF_SPREADSHEET_ID: str = os.getenv("GF_SPREADSHEET_ID", "")             # Sheet ID; leave empty to disable fallback
GF_WORKSHEET: str = os.getenv("GF_WORKSHEET", "Sheet1")
GCP_SERVICE_ACCOUNT_JSON: str = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")  # path to service account JSON

# --- Valuation parameters ---
# Override Damodaran ERP if desired. Example: export ERP=0.049
ERP_OVERRIDE: str = os.getenv("ERP", None)  # keep as str; cast to float where used

YEARS: int = int(os.getenv("YEARS", "10"))                     # projection horizon
PERP_G_CAP: float = float(os.getenv("PERP_G_CAP", "0.025"))    # terminal growth cap (e.g., 2.5%)
