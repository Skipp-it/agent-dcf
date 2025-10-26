from pydantic import BaseModel
from typing import Dict, Any, Optional, List

class ValueRequest(BaseModel):
    ticker: str
    erp_override: Optional[float] = None

class ValueResponse(BaseModel):
    ticker: str
    price: float
    iv_per_share: float
    buy_40pct_MoS: float
    rf: float
    erp: float
    beta: float
    wacc: float
    g0: float
    g_perp: float
    fcff0: float
    provenance_flags: Dict[str, Any]
    summary: str

class SensRequest(BaseModel):
    ticker: str
    erp_override: Optional[float] = None

class SensPoint(BaseModel):
    d_wacc: float
    d_g_perp: float
    iv_per_share: float

class SensResponse(BaseModel):
    ticker: str
    base_iv_per_share: float
    price: float
    wacc: float
    g0: float
    g_perp: float
    table: List[SensPoint]