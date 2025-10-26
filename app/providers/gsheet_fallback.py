from typing import Dict
from ..config import GF_SPREADSHEET_ID, GF_WORKSHEET, GCP_SERVICE_ACCOUNT_JSON

def gf_available() -> bool:
    return bool(GF_SPREADSHEET_ID and GCP_SERVICE_ACCOUNT_JSON)

def fetch_google_finance_via_sheets(ticker: str) -> Dict[str, float]:
    """
    Read fallback values from Google Sheets with GOOGLEFINANCE.
    Expects:
      A1: =GOOGLEFINANCE(A10,"price")
      A2: =GOOGLEFINANCE(A10,"marketcap")
      A3: =GOOGLEFINANCE(A10,"shares")
      A4: =GOOGLEFINANCE(A10,"beta")
      A10: ticker string (we set it)
    """
    if not gf_available():
        return {"google finance not available" : 0}

    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        GCP_SERVICE_ACCOUNT_JSON,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(GF_SPREADSHEET_ID).worksheet(GF_WORKSHEET)

    # Write ticker into A10
    ws.update("A10", ticker)

    vals = ws.get("A1:A4")
    names = ["price","market_cap","shares","beta"]
    out = {}
    for i,v in enumerate(vals):
        if not v:
            continue
        try:
            val = float(str(v[0]).replace(",",""))
            out[names[i]] = val
        except Exception:
            pass
    return out
