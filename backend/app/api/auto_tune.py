"""
FAZ 7 — Auto Tune API.

Endpoints:
  POST /auto-tune/evaluate  → Eligible proposal'ları listeler (state değişmez).
  POST /auto-tune/apply     → Eligible proposal'ları overrides.json'a uygular.
  POST /auto-tune/rollback  → Son applied adjustment'ı geri alır.
  GET  /auto-tune/recent    → Son N adjustment kaydını döndürür.
  GET  /auto-tune/overrides → Mevcut override dosyasını döndürür.

Güvenlik:
  PAPER_SAFE guard aktif (POST endpoints).
  Paper trading state mutate edilmez.
  Broker bağlantısı yoktur — BROKER_NOT_CONNECTED.
  Live execution yoktur — live_execution_allowed = False.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.execution_boundary import require_paper_safe
from app.services.auto_tune_service import (
    apply_proposals,
    evaluate_proposals,
    rollback_last_adjustment,
)
from app.storage.auto_tune_store import load_recent_adjustments, read_overrides

router = APIRouter(prefix="/auto-tune", tags=["auto-tune"])


@router.post("/evaluate", dependencies=[Depends(require_paper_safe)])
def evaluate_endpoint() -> dict:
    """
    En son calibration'dan uygulanabilir proposal'ları değerlendirir.

    Hiçbir şeyi değiştirmez — sadece okur ve analiz eder.
    """
    return evaluate_proposals()


@router.post("/apply", dependencies=[Depends(require_paper_safe)])
def apply_endpoint() -> dict:
    """
    Eligible proposal'ları auto_tune_overrides.json'a uygular.

    • Paper trading state'ini değiştirmez.
    • Broker bağlantısı gerektirmez.
    • auto_tune_overrides.json dosyasını günceller.
    • Her uygulama için JSONL log yazılır.
    """
    return apply_proposals()


@router.post("/rollback", dependencies=[Depends(require_paper_safe)])
def rollback_endpoint() -> dict:
    """
    Son applied adjustment'ı geri alır.

    Override dosyasını eski değere döndürür.
    JSONL'e rolled_back kaydı yazar.
    """
    return rollback_last_adjustment()


@router.get("/recent")
def get_recent_adjustments(limit: int = 50) -> dict:
    """Son N adjustment kaydını döndürür (read-only)."""
    safe_limit = max(1, min(limit, 500))
    records = load_recent_adjustments(limit=safe_limit)
    return {
        "status":      "ok",
        "count":       len(records),
        "adjustments": records,
    }


@router.get("/overrides")
def get_overrides() -> dict:
    """Mevcut auto_tune_overrides.json içeriğini döndürür (read-only)."""
    return read_overrides()
