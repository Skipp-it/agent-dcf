import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .models import ValueRequest, ValueResponse
from .dcf import run_valuation
import traceback, sys

app = FastAPI(title="DCF Agent API")

# comma-separated list in env; default to local only
_allowed = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080")
ALLOWED_ORIGINS = [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,     # no wildcard
    allow_credentials=False,           # tighten unless you need cookies
    allow_methods=["POST", "GET"],     # minimal verbs
    allow_headers=["content-type"],    # minimal headers
)

@app.get("/")
def root():
    return {"ok": True, "use": "/docs"}

@app.post("/value", response_model=ValueResponse)
def value(req: ValueRequest):
    try:
        out = run_valuation(req.ticker, erp_override=req.erp_override)
        return ValueResponse(**out)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=400, detail=str(e))
