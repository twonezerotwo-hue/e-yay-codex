"""GET /api/v1/dashboard/state — Canonical Market State endpoint.

Tüm dashboard panellerinin ortak veri kaynağı. Mevcut pipeline'ı (regime
report, capital rotation, technical, news, paper trading) tek snapshot_id
altında birleştirir; risk_gate / agent_votes / position_checks ViewModel'leri
panellere kanıt zinciri olarak sunulur.

PAPER_SAFE / NO_EXECUTION — sadece okuma.
"""
from __future__ import annotations

import dataclasses
import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.market_state.canonical_state import get_cached_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/state")
def get_dashboard_state(
    force_refresh: bool = Query(default=False, description="Cache'i atla, taze pipeline koş"),
    include_paper: bool = Query(default=True),
    include_news:  bool = Query(default=True),
) -> JSONResponse:
    """Tek canonical state — paneller buradan beslenir.

    Cache 60sn (yfinance + regime pipeline yükü). Aynı request içinde tüm
    paneller aynı `snapshot_id` görür → tutarsızlık tamamen kapanır.
    """
    try:
        state, was_cached = get_cached_state(
            force_refresh=force_refresh,
            include_paper=include_paper,
            include_news=include_news,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("dashboard_state pipeline başarısız")
        return JSONResponse(
            status_code=200,
            content={
                "status":               "error",
                "paper_safe":           True,
                "execution_side_effects": "NO_EXECUTION",
                "error":                f"{type(exc).__name__}: {exc}",
            },
        )

    return JSONResponse(content={
        "status":                "ok",
        "paper_safe":            True,
        "execution_side_effects": "NO_EXECUTION",
        "snapshot_id":           state.snapshot_id,
        "generated_at":          state.generated_at,
        "cached":                was_cached,
        "state":                 dataclasses.asdict(state),
        "warnings":              list(state.warnings),
    })


__all__ = ["router"]
