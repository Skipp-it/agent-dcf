from typing import Dict, Any, Optional

from .config import YEARS, PERP_G_CAP, ERP_OVERRIDE
from .providers.yahoo import fetch_yahoo_core, get_cik
from .providers.gsheet_fallback import fetch_google_finance_via_sheets, gf_available
from .providers.fred import get_risk_free_dgs10
from .providers.sec import companyfacts, compute_fcff_block

def run_valuation(ticker: str, erp_override: Optional[float] = None) -> Dict[str, Any]:
    flags: Dict[str, Any] = {}

    # -------- Market fields (Yahoo first, Sheets fallback) --------
    y = fetch_yahoo_core(ticker)
    for k in y:
        flags[k] = {"source": "Yahoo Finance", "flag": "OK"}

    # Fallback to Google Sheets for missing core fields
    needed = {"price", "market_cap", "shares", "beta"}
    if not needed.issubset(y.keys()) and gf_available():
        g = fetch_google_finance_via_sheets(ticker)
        for k, v in g.items():
            if k not in y:
                y[k] = v
                flags[k] = {"source": "Google Finance via Sheets", "flag": "CHECK"}

    # Validate presence
    for key in ("price", "market_cap", "shares"):
        if key not in y:
            raise RuntimeError(f"Missing {key} even after fallback.")

    # Risk-free and ERP
    rf = get_risk_free_dgs10()
    flags["rf"] = {"source": "FRED DGS10", "flag": "OK"}

    if erp_override is not None:
        erp = float(erp_override)
        flags["erp"] = {"source": "override", "flag": "OK"}
    elif ERP_OVERRIDE is not None:
        erp = float(ERP_OVERRIDE)
        flags["erp"] = {"source": "env override", "flag": "OK"}
    else:
        erp = 0.05  # default
        flags["erp"] = {"source": "default 5%", "flag": "CHECK"}

    beta = y.get("beta", 1.0)
    if "beta" not in y:
        flags["beta"] = {"source": "default 1.0", "flag": "CHECK"}

    # -------- Fundamentals (SEC) --------
    cik = get_cik(ticker)
    facts = companyfacts(cik)
    sec = compute_fcff_block(facts)
    flags["sec"] = {"source": "SEC CompanyFacts", "flag": "OK"}

    if sec["fcff0"] <= 0:
        raise RuntimeError("Base FCFF <= 0. Normalize or adjust before DCF.")

    # -------- Balance sheet and cash --------
    total_debt = y.get("total_debt", 0.0) or sec.get("total_debt_book", 0.0)
    if "total_debt" not in y:
        flags["total_debt"] = {"source": "SEC book proxy", "flag": "CHECK"}
    cash = y.get("cash", 0.0)
    if "cash" not in y:
        flags["cash"] = {"source": "missing, set 0", "flag": "CHECK"}

    # Costs of capital
    re = rf + beta * erp
    rd = (sec["interest_expense"] / total_debt) if total_debt > 0 and sec["interest_expense"] > 0 else rf
    after_tax_rd = rd * (1 - sec["tax_rate"])

    E = float(y["market_cap"])
    D = float(total_debt)
    V = max(E + D, 1.0)
    wacc = (E / V) * re + (D / V) * after_tax_rd

    # Growth model: ROIC * reinvestment with fade to min(rf, cap)
    nopat = sec["ebit"] * (1 - sec["tax_rate"])
    roic = min(max(nopat / V, 0.0), 0.5)
    if nopat > 1e-6:
        reinvestment = min(max(sec["capex"] + sec["delta_nwc"] - sec["da"], 0.0) / nopat, 1.0)
    else:
        reinvestment = 0.0
    g0 = min(roic * reinvestment, 0.20)
    g_perp = min(rf, PERP_G_CAP)

    # Build growth path (linear fade)
    g_path = [g0 - (g0 - g_perp) * (i / YEARS) for i in range(1, YEARS + 1)]

    # Project FCFF
    fcff = []
    cf = sec["fcff0"]
    for g in g_path:
        cf *= (1 + g)
        fcff.append(cf)

    # -------- Terminal and valuation (with gentle soften) --------
    EPS = 1e-4  # tiny nudge to avoid equality due to rounding
    if wacc <= g_perp:
        old_gp = g_perp
        g_perp = max(0.0, g_perp - EPS)
        flags["g_perp_adjust"] = {"old": float(old_gp), "new": float(g_perp), "eps": EPS, "reason": "soften WACC>g_perp"}

    if wacc <= g_perp:
        raise RuntimeError("WACC <= terminal growth; invalid terminal math.")

    disc = [fcff[i] / ((1 + wacc) ** (i + 1)) for i in range(YEARS)]
    tv = fcff[-1] * (1 + g_perp) / (wacc - g_perp)
    tv_disc = tv / ((1 + wacc) ** YEARS)

    ev = sum(disc) + tv_disc
    equity_value = ev - (D - cash)
    iv_per_share = equity_value / float(y["shares"])

    out: Dict[str, Any] = {"ticker": ticker.upper(), "price": float(y["price"]), "iv_per_share": float(iv_per_share),
                           "buy_40pct_MoS": float(iv_per_share * 0.60), "rf": float(rf), "erp": float(erp),
                           "beta": float(beta), "wacc": float(wacc), "g0": float(g0), "g_perp": float(g_perp),
                           "fcff0": float(sec["fcff0"]), "provenance_flags": flags, "_internals": {
            "wacc": float(wacc),
            "g_perp": float(g_perp),
            "fcff_path": [float(x) for x in fcff],
            "D": float(D),
            "cash": float(cash),
            "shares": float(y["shares"]),
            "years": int(YEARS),
        }}

    # Internals for /sensitivities endpoint

    out["summary"] = (
        f"{out['ticker']}: price {out['price']:.2f}, IV {out['iv_per_share']:.2f}, "
        f"40% MoS buy {out['buy_40pct_MoS']:.2f}. WACC {out['wacc']:.3f}, "
        f"g0 {out['g0']:.3f} → g∞ {out['g_perp']:.3f}."
    )
    return out
