"""
FAZ 1.6 — Manual Snapshot Capture Endpoint.

Endpointler:
  POST /api/v1/hourly-snapshots/capture  — gerçek pipeline çalıştır → kaydet
  GET  /api/v1/hourly-snapshots/recent   — son snapshot'ları oku

Politika:
  • MOCK VERİ YOK. Gerçek pipeline başarısız olursa kayıt yapılmaz.
  • report + rotation + mtf üçü birden gerekli; biri eksikse → not_saved.
  • Paper trading state sadece READ; pozisyon açma/kapama yok.
  • decision_permission = NO_EXECUTION, execution_mode = PAPER_SAFE.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.consensus import _build_pipeline
from app.core.execution_boundary import require_paper_safe
from app.services import paper_trading_service as pts
from app.services.hourly_snapshot_builder import build_hourly_snapshot_payload
from app.storage.hourly_snapshot_store import (
    load_recent_hourly_snapshots,
    save_hourly_snapshot,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/hourly-snapshots", tags=["hourly-snapshots"])

_SCHEMA_VERSION = "hourly_snapshot_v1"
_MAX_LIMIT = 200


# ── POST /capture ─────────────────────────────────────────────────────────────

@router.post("/capture")
def capture_snapshot(
    _boundary: dict = Depends(require_paper_safe),
) -> dict[str, Any]:
    """
    Gerçek backend pipeline çıktısını hourly snapshot store'a yazar.

    report + rotation + mtf üçü de alınamazsa kayıt YOK; not_saved döner.
    Bu endpoint hiçbir trade açmaz; paper_trading_state sadece okunur.
    """
    # ── 1. Gerçek pipeline ─────────────────────────────────────────────────
    try:
        report, rotation, mtf, raw_snapshots = _build_pipeline()
    except Exception as exc:
        _log.warning("hourly_snapshot capture: pipeline failed — not_saved | %s", exc)
        return {
            "status":  "not_saved",
            "reason":  "real_pipeline_data_unavailable",
            "detail":  "pipeline exception",
        }

    # ── 2. Zorunlu alan kontrolü ───────────────────────────────────────────
    missing: list[str] = []
    if report is None:
        missing.append("report")
    if rotation is None:
        missing.append("rotation")
    if not mtf:           # None veya boş dict → MTF provider başarısız
        missing.append("mtf")

    if missing:
        _log.warning(
            "hourly_snapshot capture: incomplete pipeline output %s — not_saved", missing
        )
        return {
            "status":  "not_saved",
            "reason":  "real_pipeline_data_unavailable",
            "missing": missing,
        }

    # ── 3. Paper trading state (read-only) ────────────────────────────────
    pt_state: dict | None = None
    try:
        pt_state = pts.get_snapshot()
    except Exception as exc:
        _log.debug("hourly_snapshot capture: get_snapshot failed (non-critical): %s", exc)

    # ── 4. Data quality ───────────────────────────────────────────────────
    dq: dict = {"status": "unknown", "notes": []}
    try:
        from app.services.data_quality_service import get_data_quality_summary

        asset_snapshots = {
            str(snap.asset_symbol): snap
            for snap in raw_snapshots
            if hasattr(snap, "fallback_used")
        }
        dq = get_data_quality_summary(asset_snapshots) or dq
    except Exception as exc:
        _log.debug("hourly_snapshot capture: data_quality failed (non-critical): %s", exc)

    # ── 5. Payload üret + kaydet ──────────────────────────────────────────
    payload = build_hourly_snapshot_payload(
        report=report,
        rotation=rotation,
        mtf=mtf,
        paper_trading_state=pt_state,
        data_quality=dq,
    )
    snapshot_id = save_hourly_snapshot(payload)

    _log.info("hourly_snapshot saved | id=%s", snapshot_id)
    return {
        "status":             "saved",
        "snapshot_id":        snapshot_id,
        "schema_version":     _SCHEMA_VERSION,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":     "PAPER_SAFE",
    }


# ── GET /recent ───────────────────────────────────────────────────────────────

@router.get("/recent")
def get_recent_snapshots(limit: int = 24) -> dict[str, Any]:
    """
    Kayıtlı son N saatlik snapshot'ı döndürür (read-only).
    Dosya yoksa boş liste döner; crash olmaz.
    """
    safe_limit = max(1, min(limit, _MAX_LIMIT))
    records = load_recent_hourly_snapshots(limit=safe_limit)
    return {
        "status":    "ok",
        "count":     len(records),
        "snapshots": records,
    }
