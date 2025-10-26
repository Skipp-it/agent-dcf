import pandas as pd

def get_risk_free_dgs10() -> float:
    """
    Pull US 10Y Treasury yield (DGS10) from FRED CSV and return as decimal.
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
    df = pd.read_csv(url)
    df["DGS10"] = pd.to_numeric(df["DGS10"], errors="coerce")
    val = float(df["DGS10"].dropna().iloc[-1]) / 100.0
    return val
