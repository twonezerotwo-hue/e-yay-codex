"""
Core Snapshots API — Item 3 inspection.

GET /api/v1/core/snapshots          — son snapshot özetleri (evidence dahil değil)
GET /api/v1/core/snapshots/{id}     — tek snapshot tam içerik
GET /api/v1/core/snapshots/_stats   — sayım + current_id

GET /api/v1/jobs                    — aktif/biten job listesi
GET /api/v1/jobs/_stats             — by_status

PAPER_SAFE / NO_EXECUTION (read-only).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import core_snapshot_cache, job_runner

router = APIRouter(prefix="/core", tags=["core"])


@router.get("/snapshots")
def list_snapshots(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    items = core_snapshot_cache.list_recent(limit=limit)
    return {"status": "ok", "count": len(items), "items": items}


@router.get("/snapshots/_stats")
def snapshot_stats() -> dict:
    return {"status": "ok", **core_snapshot_cache.stats()}


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> dict:
    entry = core_snapshot_cache.get_snapshot(snapshot_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Snapshot bulunamadı veya expired: {snapshot_id}")
    return {"status": "ok", "snapshot": entry}


# ── Job runner inspection ───────────────────────────────────────────────────

jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])


@jobs_router.get("")
def list_jobs(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    items = job_runner.list_recent(limit=limit)
    return {"status": "ok", "count": len(items), "items": items}


@jobs_router.get("/_stats")
def job_stats() -> dict:
    return {"status": "ok", **job_runner.stats()}


__all__ = ["router", "jobs_router"]
