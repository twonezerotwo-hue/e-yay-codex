"""
GET /api/v1/agent/chart/{symbol}    — multi-TF chart okuma raporu

Sprint 9+ / agent chart reader. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import agent_chart_reader_service as cr

router = APIRouter(prefix="/agent/chart", tags=["agent-chart"])


@router.get("/{symbol}")
def read_chart(
    symbol: str,
    timeframes: str = Query(default="1h,4h,1d", description="CSV TF listesi (1h, 4h, 1d, 1wk)"),
) -> dict:
    tfs = [t.strip() for t in timeframes.split(",") if t.strip()]
    reading = cr.read_chart(symbol.upper(), timeframes=tfs)
    if reading.error == "ticker_not_mapped":
        raise HTTPException(status_code=404, detail=f"Sembol bilinmiyor: {symbol}")
    return {
        "status":         "ok" if reading.error is None else "partial",
        "execution_mode": "OFF / NO_EXECUTION",
        "reading":        cr.reading_to_dict(reading),
    }


__all__ = ["router"]
