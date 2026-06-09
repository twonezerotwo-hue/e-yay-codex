"""
FAZ 9 — Scheduler API.

Endpointler:
  POST /scheduler/run-once   → 7 adımı bir kez sırayla çalıştırır
  POST /scheduler/start      → arka plan döngüsünü başlatır
  POST /scheduler/stop       → arka plan döngüsünü durdurur
  GET  /scheduler/status     → mevcut scheduler durumu
  GET  /scheduler/recent     → son N run kaydını döndürür

Güvenlik:
  PAPER_SAFE guard aktif (POST endpointlerinde).
  Hiçbir endpoint trade açmaz/kapatmaz.
  Broker bağlantısı yoktur — BROKER_NOT_CONNECTED.
  Live execution yoktur — live_execution_allowed = False.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.execution_boundary import require_paper_safe
from app.services.scheduler_service import (
    get_scheduler_status,
    run_once,
    scheduler_start,
    scheduler_stop,
)
from app.storage.scheduler_run_store import load_recent_scheduler_runs

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/run-once", dependencies=[Depends(require_paper_safe)])
def run_once_endpoint() -> dict:
    """
    7 adımı bir kez sırayla çalıştırır.

    Bir adım fail olursa sonraki adımlar çalışmaya devam eder.
    Sonuç JSONL'e kaydedilir ve dönüş değeri olarak döndürülür.
    """
    return run_once()


@router.post("/start", dependencies=[Depends(require_paper_safe)])
def start_scheduler(interval_seconds: int = 3600) -> dict:
    """
    Arka plan döngüsünü başlatır.

    interval_seconds: çalıştırmalar arası bekleme (60–86400, varsayılan 3600).
    Zaten çalışıyorsa "already_running" döner.
    """
    return scheduler_start(interval_seconds=interval_seconds)


@router.post("/stop", dependencies=[Depends(require_paper_safe)])
def stop_scheduler() -> dict:
    """
    Arka plan döngüsünü durdurur.

    Çalışmıyorsa "already_stopped" döner.
    """
    return scheduler_stop()


@router.get("/status")
def get_status() -> dict:
    """
    Mevcut scheduler durumunu döndürür (read-only).
    """
    return get_scheduler_status()


@router.get("/recent")
def get_recent_runs(limit: int = 20) -> dict:
    """Son N scheduler run kaydını döndürür (read-only)."""
    safe_limit = max(1, min(limit, 200))
    runs = load_recent_scheduler_runs(limit=safe_limit)
    return {
        "status": "ok",
        "count":  len(runs),
        "runs":   runs,
    }
