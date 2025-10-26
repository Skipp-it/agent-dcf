import requests
import yfinance as yf
from functools import lru_cache
from ..config import SEC_USER_EMAIL, HTTP_TIMEOUT
import re

UA = {"User-Agent": SEC_USER_EMAIL}

def fetch_yahoo_core(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    out = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}
    try:
        fast = getattr(t, "fast_info", {}) or {}
    except Exception:
        fast = {}

    p = fast.get("lastPrice") or info.get("currentPrice")
    if p is not None:
        out["price"] = float(p)

    mc = info.get("marketCap")
    if mc is not None:
        out["market_cap"] = float(mc)

    sh = info.get("sharesOutstanding") or info.get("floatShares")
    if sh is not None:
        out["shares"] = float(sh)

    b = info.get("beta")
    if b is not None:
        out["beta"] = float(b)

    td = info.get("totalDebt")
    if td is not None:
        out["total_debt"] = float(td)

    c = info.get("totalCash")
    if c is not None:
        out["cash"] = float(c)

    return out

@lru_cache(maxsize=1)
def _sec_ticker_map():
    url = "https://www.sec.gov/files/company_tickers.json"
    r = requests.get(url, headers=UA, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    mapping = {}
    for _, rec in data.items():
        t = str(rec.get("ticker", "")).upper()
        cik_str = str(rec.get("cik_str", "")).strip()
        if t and cik_str.isdigit():
            mapping[t] = int(cik_str)
    return mapping

def get_cik(ticker: str) -> int:
    try:
        t = yf.Ticker(ticker)
        if hasattr(t, "get_cik"):
            cik_val = t.get_cik()
            if cik_val:
                return int(cik_val)
    except Exception:
        pass

    # Fallback to SEC map
    mapping = _sec_ticker_map()
    tkr = ticker.upper()
    if tkr in mapping:
        return mapping[tkr]
    # last resort: browse atom
    url = "https://www.sec.gov/cgi-bin/browse-edgar?CIK={}&owner=exclude&action=getcompany&output=atom".format(tkr)
    r = requests.get(url, headers=UA, timeout=HTTP_TIMEOUT)
    r.raise_for_status()

    m = re.search(r"CIK0*([0-9]+)", r.text)
    if m:
        return int(m.group(1))
    raise RuntimeError("CIK not found for '{}'".format(ticker))

def suggest_symbols(prefix: str):
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        r = requests.get(url, params={"q": prefix, "quotesCount": 6}, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        out = []
        for s in r.json().get("quotes", []):
            out.append({"symbol": s.get("symbol"), "shortname": s.get("shortname")})
        return out
    except Exception:
        return []
