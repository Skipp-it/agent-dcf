# app/providers/sec.py
from typing import List, Dict, Optional
import requests
from ..config import SEC_USER_EMAIL, HTTP_TIMEOUT

UA = {"User-Agent": SEC_USER_EMAIL}

def companyfacts(cik: int) -> dict:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    r = requests.get(url, headers=UA, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()

def _annual_usd(facts: dict, tag: str) -> List[dict]:
    try:
        units = facts["facts"]["us-gaap"][tag]["units"]
    except KeyError:
        return []
    if "USD" not in units:
        return []
    rows = [x for x in units["USD"] if x.get("fy") and x.get("fp") in ("FY", "Y")]
    rows = sorted(rows, key=lambda x: (x.get("fy", 0), x.get("end", "")))
    return rows

def _val(item: Optional[dict]) -> float:
    try:
        return float(item.get("val", 0.0))
    except Exception:
        return 0.0

def _last(facts: dict, tag: str) -> float:
    arr = _annual_usd(facts, tag)
    return _val(arr[-1]) if arr else 0.0

def _last2(facts: dict, tag: str) -> List[float]:
    arr = _annual_usd(facts, tag)
    if not arr:
        return []
    if len(arr) == 1:
        return [_val(arr[-1])]
    return [_val(arr[-2]), _val(arr[-1])]

def compute_fcff_block(facts: dict) -> Dict[str, float]:
    # EBIT (try OperatingIncomeLoss, then EBIT)
    ebit_series = _annual_usd(facts, "OperatingIncomeLoss")
    if not ebit_series:
        ebit_series = _annual_usd(facts, "EarningsBeforeInterestAndTaxes")
    ebit = _val(ebit_series[-1]) if ebit_series else 0.0

    # Taxes
    tax_exp = _last(facts, "IncomeTaxExpenseBenefit")
    pretax  = _last(facts, "IncomeLossFromContinuingOperationsBeforeIncomeTaxes")
    tax_rate = 0.21
    if pretax != 0:
        tr = tax_exp / pretax
        if tr < 0: tr = 0.0
        if tr > 0.35: tr = 0.35
        tax_rate = tr

    # D&A and CapEx
    da    = _last(facts, "DepreciationDepletionAndAmortization")
    capex = _last(facts, "PaymentsToAcquirePropertyPlantAndEquipment")

    # ΔNWC = (CA - Cash - (CL - ST debt)) YoY, fully safe
    ca2 = _last2(facts, "AssetsCurrent")
    cl2 = _last2(facts, "LiabilitiesCurrent")
    sd2 = _last2(facts, "DebtCurrent")
    cs2 = _last2(facts, "CashAndCashEquivalentsAtCarryingValue")

    def nwc_at(i: int) -> float:
        # use last available, default 0
        ca  = ca2[i] if len(ca2)  > i else (ca2[-1] if ca2 else 0.0)
        cl  = cl2[i] if len(cl2)  > i else (cl2[-1] if cl2 else 0.0)
        sd  = sd2[i] if len(sd2)  > i else (sd2[-1] if sd2 else 0.0)
        cs  = cs2[i] if len(cs2)  > i else (cs2[-1] if cs2 else 0.0)
        return max(ca - cs - max(cl - sd, 0.0), 0.0)

    if ca2 and cl2 and cs2:
        # if we have at least one period, form Δ with itself → 0; with two → proper Δ
        if len(ca2) >= 2 and len(cl2) >= 2 and len(cs2) >= 2:
            delta_nwc = nwc_at(1) - nwc_at(0)
        else:
            delta_nwc = 0.0
    else:
        delta_nwc = 0.0

    # Interest and Debt (book)
    int_exp = _last(facts, "InterestExpense")
    debt_book = _last(facts, "DebtInstrumentCarryingAmount")
    if debt_book == 0.0:
        debt_book = _last(facts, "LongTermDebtAndCapitalLeaseObligations")

    nopat = ebit * (1 - tax_rate)
    fcff0 = nopat + da - capex - delta_nwc

    return {
        "ebit": ebit,
        "tax_rate": tax_rate,
        "da": da,
        "capex": capex,
        "delta_nwc": delta_nwc,
        "fcff0": fcff0,
        "interest_expense": int_exp,
        "total_debt_book": debt_book
    }
