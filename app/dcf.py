from typing import Dict, Any, Optional

from .config import YEARS, PERP_G_CAP, ERP_OVERRIDE
from .providers.yahoo import fetch_yahoo_core, get_cik, suggest_symbols
from .providers.gsheet_fallback import fetch_google_finance_via_sheets, gf_available
from .providers.fred import get_risk_free_dgs10
from .providers.sec import companyfacts, compute_fcff_block

def run_valuation(ticker: str, erp_override: Optional[float] = None) -> Dict[str, Any]:
    flags: Dict[str, Any] = {}

    # Market fields from Yahoo
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

    # ----- US-only path + ambiguity guard -----
    # Reject tickers with exchange suffixes (e.g., ".TO", ".L") up front
    if "." in ticker and ticker.split(".")[-1].upper() != "US":
        raise RuntimeError("Non-US ticker '{}'. Use a US-listed symbol or ADR (e.g., CNI for Canadian National Railway).".format(ticker))

    # Resolve CIK via SEC. On failure, suggest likely symbols and stop.
    try:
        cik = get_cik(ticker)
    except Exception:
        options = suggest_symbols(ticker)
        syms = [o.get("symbol") for o in options] if options else []
        raise RuntimeError("Ambiguous or non-US ticker '{}'. Try one of: {}".format(ticker, syms))

    # SEC fundamentals
    facts = companyfacts(cik)
    sec = compute_fcff_block(facts)
    flags["sec"] = {"source": "SEC CompanyFacts", "flag": "OK"}

    if sec["fcff0"] <= 0:
        # Optional normalization for testing; remove for hard fail if desired
        sec["fcff0"] = max(sec["ebit"] * (1 - sec["tax_rate"]) + sec["da"] - sec["capex"], 1e-6)
        flags["fcff0_norm"] = {"reason": "ΔNWC override to 0 for test", "flag": "CHECK"}

    # Debt and cash
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

    # Terminal checks; soften tiny equalities
    EPS = 1e-4
    if wacc <= g_perp:
        g_perp = max(0.0, g_perp - EPS)
        flags["g_perp_adjust"] = {"eps": EPS, "flag": "CHECK"}
    if wacc <= g_perp:
        raise RuntimeError("WACC ({:.4f}) <= g_perp ({:.4f})".format(wacc, g_perp))

    # Discount and TV
    disc = [fcff[i] / ((1 + wacc) ** (i + 1)) for i in range(YEARS)]
    tv = fcff[-1] * (1 + g_perp) / (wacc - g_perp)
    tv_disc = tv / ((1 + wacc) ** YEARS)

    ev = sum(disc) + tv_disc
    equity_value = ev - (D - cash)
    iv_per_share = equity_value / float(y["shares"])
    year_high = float(y.get("year_high", 0.0))
    market_cap = float(y["market_cap"])
    cash_val = float(cash)
    total_debt_val = float(total_debt)
    mos_required = 0.40

    out: Dict[str, Any] = {
        "ticker": ticker,
        "price": float(y["price"]),
        "iv_per_share": float(iv_per_share),
        "buy_40pct_MoS": float(iv_per_share * 0.60),
        "rf": float(rf),
        "erp": float(erp),
        "beta": float(beta),
        "wacc": float(wacc),
        "g0": float(g0),
        "g_perp": float(g_perp),
        "fcff0": float(sec["fcff0"]),
        "market_cap": market_cap,
        "cash": cash_val,
        "total_debt": total_debt_val,
        "year_high": year_high,
        "mos_required": mos_required,
        "provenance_flags": flags,
    }

    out["summary"] = (
        f"{ticker}: price {out['price']:.2f}, IV {out['iv_per_share']:.2f}, "
        f"40% MoS buy {out['buy_40pct_MoS']:.2f}. WACC {out['wacc']:.3f}, "
        f"g0 {out['g0']:.3f} → g∞ {out['g_perp']:.3f}."
    )

    # Internals for sensitivities
    out["_internals"] = {
        "wacc": wacc,
        "g_perp": g_perp,
        "fcff_path": fcff,
        "D": D,
        "cash": cash,
        "shares": float(y["shares"]),
        "years": YEARS,
    }

    return out

def build_sensitivities(internals: Dict[str, Any]) -> list:
    """
    Returns a grid of IV/share for dWACC in {-100bps,0,+100bps} and d g_perp in {-50bps,0,+50bps}.
    """
    wacc = internals["wacc"]
    g_perp = internals["g_perp"]
    fcff = internals["fcff_path"]
    D = internals["D"]
    cash = internals["cash"]
    shares = internals["shares"]
    years = internals["years"]

    def price_at(W, Gp):
        if W <= Gp:
            return float("nan")
        disc = [fcff[i] / ((1 + W) ** (i + 1)) for i in range(years)]
        tv = fcff[-1] * (1 + Gp) / (W - Gp)
        ev = sum(disc) + tv / ((1 + W) ** years)
        eq = ev - (D - cash)
        return eq / shares

    grid = []
    for dW in (-0.01, 0.0, 0.01):        # ±100 bps WACC
        for dG in (-0.005, 0.0, 0.005):  # ±50 bps terminal growth
            iv = price_at(wacc + dW, max(g_perp + dG, 0.0))
            grid.append({"d_wacc": dW, "d_g_perp": dG, "iv_per_share": iv})
    return grid
