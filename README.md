# Agent DCF API — README

US-listed stocks only. SEC CompanyFacts for fundamentals. FRED DGS10 for risk-free. Yahoo Finance for market fields with Google Finance (Sheets) fallback. Python 3.9+ compatible.

---

## 1) What this does

- Computes intrinsic value per share via FCFF DCF.
- Uses diluted shares.
- WACC from CAPM + after-tax cost of debt.
- Growth = ROIC × reinvestment, faded to a capped terminal growth.
- Sensitivity table for ±100 bps WACC and ±50 bps terminal growth.
- Provenance flags show any fallback or assumption.

US-only: non-US tickers or exchange suffixes are rejected. Ambiguous tickers return suggestions.

---

## 2) Project structure

