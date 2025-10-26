import csv, os, time
from typing import Dict, Any

AUDIT_PATH = os.getenv("AUDIT_CSV", "audit_log.csv")
FIELDS = [
    "ts","ticker","price","iv_per_share","buy_40pct_MoS",
    "rf","erp","beta","wacc","g0","g_perp","fcff0",
    "flags_json"
]

def append_row(row: Dict[str, Any]):
    exists = os.path.exists(AUDIT_PATH)
    with open(AUDIT_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow({
            "ts": int(time.time()),
            "ticker": row.get("ticker"),
            "price": row.get("price"),
            "iv_per_share": row.get("iv_per_share"),
            "buy_40pct_MoS": row.get("buy_40pct_MoS"),
            "rf": row.get("rf"),
            "erp": row.get("erp"),
            "beta": row.get("beta"),
            "wacc": row.get("wacc"),
            "g0": row.get("g0"),
            "g_perp": row.get("g_perp"),
            "fcff0": row.get("fcff0"),
            "flags_json": str(row.get("provenance_flags", {}))[:4000]
        })
