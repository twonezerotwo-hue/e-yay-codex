"""
GET /api/v1/paper/decision/latest

Paper Trading Karar Merkezi — tek uçtan tüm karar zinciri.

Döner:
  - market_interpretation
  - data_quality_status
  - trigger_engine_output
  - risk_engine_verdict
  - paper_trading_decision
  - entry_plan
  - exit_plan
  - active_paper_positions
  - news_to_decision_mapping
  - learning_layer
  - owner_action
  - execution_status        ← her zaman PAPER_SAFE / NO_EXECUTION

PAPER_SAFE · NO_EXECUTION. Read-only, side-effect yok.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.services import paper_decision_service as pds

router = APIRouter(prefix="/paper/decision", tags=["paper-decision"])


@router.get("/latest")
def get_latest_paper_decision() -> dict:
    """Karar merkezinin en güncel durumu — pipeline okur, mutate etmez."""
    try:
        payload = pds.build_latest_decision()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    body = asdict(payload)
    body["status"] = "ok"
    return body


__all__ = ["router"]
