"""
GET /api/v1/trading/attribution/recent   — son N trade'in modül bazlı PnL dağılımı
GET /api/v1/trading/attribution/modules  — modül bazlı toplam istatistik
GET /api/v1/trading/attribution/summary  — üst düzey özet (best/worst module)

P1 — Signal Attribution Engine. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import signal_attribution_service as sas

router = APIRouter(prefix="/trading/attribution", tags=["signal-attribution"])


@router.get("/recent")
def recent_attributions(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    items = sas.get_recent(limit=limit)
    return {
        "status":         "ok",
        "execution_mode": "PAPER_SAFE / NO_EXECUTION",
        "count":          len(items),
        "items":          items,
    }


@router.get("/modules")
def module_stats(
    pair:    str | None = Query(default=None, description="Pair filter, örn: BTCUSD"),
    side:    str | None = Query(default=None, description="LONG | SHORT"),
    last_n:  int | None = Query(default=None, ge=1, le=2000),
) -> dict:
    modules = sas.get_module_stats(pair_filter=pair, side_filter=side, last_n=last_n)
    return {
        "status":         "ok",
        "execution_mode": "PAPER_SAFE / NO_EXECUTION",
        "filters":        {"pair": pair, "side": side, "last_n": last_n},
        "modules":        modules,
    }


@router.get("/summary")
def attribution_summary() -> dict:
    return {"status": "ok", **sas.summary()}


__all__ = ["router"]
