"""
FAZ 14 — Capital Rotation Visual API.

Read-only endpoint:
  GET /capital-rotation/visual?timeframe=1d|7d|30d

Mevcut CapitalRotationProvider çıktısını visual layer modeline çevirir.
  • 30d (varsayılan): tam rotasyon analizi (provider.compute()).
  • 1d / 7d: aynı günlük kapanış serilerinden pencere-bazlı momentum
    (compute_window_rotation) → aynı build_visual_payload ile node/flow.

Veri yoksa fake üretmez: timeframe_available=False + reason döner; panel
çökmez, kullanıcıya "veri yok" gösterir. Karar üretmez. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Query

from app.services.capital_rotation_visual_adapter import (
    SCHEMA_VERSION,
    build_visual_payload,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/capital-rotation", tags=["capital-rotation-visual"])

# Timeframe başına 30sn TTL cache — provider'a yük bindirmez.
_CACHE: dict[str, tuple[float, dict[str, Any]]] | None = {}
_TTL   = 30.0
_VALID_TIMEFRAMES = ("1d", "7d", "30d")


def _base_meta(extra: dict[str, Any]) -> dict[str, Any]:
    base = {
        "schema_version":      SCHEMA_VERSION,
        "source":              "capital_rotation_provider",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "visual_mode":         "animated_flow",
    }
    base.update(extra)
    return base


def _provider_unavailable(exc: Exception, timeframe: str) -> dict[str, Any]:
    """Sağlayıcı tamamen erişilemez → degraded (frontend klasik görünüme döner)."""
    return _base_meta({
        "status":              "degraded",
        "conviction":          0,
        "primary_flow":        "",
        "nodes":               [],
        "flows":               [],
        "fallback_reason":     f"provider_unavailable: {type(exc).__name__}",
        "timeframe":           timeframe,
        "timeframe_available": False,
    })


def _timeframe_unavailable(timeframe: str, reason: str) -> dict[str, Any]:
    """Bu pencere için veri hesaplanamıyor → status=ok ama timeframe_available=False.

    status'u 'ok' tutuyoruz ki frontend klasik görünüme DÜŞMESİN; bunun yerine
    'X veri yok' mesajı gösterip kullanıcı başka timeframe'e geçebilsin.
    """
    return _base_meta({
        "status":              "ok",
        "conviction":          0,
        "primary_flow":        "",
        "nodes":               [],
        "flows":               [],
        "fallback_reason":     reason,
        "timeframe":           timeframe,
        "timeframe_available": False,
    })


def _build_for_timeframe(timeframe: str) -> dict[str, Any]:
    if timeframe == "30d":
        try:
            from app.providers.capital_rotation_provider import (  # noqa: PLC0415
                CapitalRotationProvider,
            )
            rotation = CapitalRotationProvider().compute()
        except Exception as exc:  # noqa: BLE001
            _log.warning("capital_rotation_visual: provider unavailable: %s", exc)
            return _provider_unavailable(exc, timeframe)
        payload = build_visual_payload(rotation)
        payload["timeframe"] = "30d"
        payload["timeframe_available"] = payload.get("status") == "ok"
        return payload

    # 1d / 7d — pencere-bazlı momentum (aynı ham serilerden, ekstra ağ çağrısı yok)
    try:
        from app.providers.capital_rotation_provider import (  # noqa: PLC0415
            compute_window_rotation,
        )
        wr = compute_window_rotation(timeframe)
    except Exception as exc:  # noqa: BLE001
        _log.warning("capital_rotation_visual: window compute failed: %s", exc)
        return _provider_unavailable(exc, timeframe)

    if not wr.get("window_available"):
        return _timeframe_unavailable(timeframe, str(wr.get("reason") or "insufficient_history"))

    payload = build_visual_payload(wr)
    if payload.get("status") != "ok":
        # Adapter degraded döndüyse (örn. identical_returns) klasik görünüme
        # düşmek yerine bu pencereyi "veri yok" olarak işaretle.
        return _timeframe_unavailable(timeframe, str(payload.get("fallback_reason") or "insufficient_history"))
    payload["timeframe"] = timeframe
    payload["timeframe_available"] = True
    return payload


@router.get("/visual")
def get_visual(timeframe: str = Query("30d")) -> dict[str, Any]:
    """
    Read-only visual layer payload (timeframe-aware).
    Timeframe başına 30sn TTL cache.
    """
    global _CACHE
    tf = timeframe if timeframe in _VALID_TIMEFRAMES else "30d"
    if _CACHE is None:  # test'ler cache'i None'a set edebilir
        _CACHE = {}

    now = time.monotonic()
    cached = _CACHE.get(tf)
    if cached is not None and (now - cached[0]) < _TTL:
        return cached[1]

    payload = _build_for_timeframe(tf)
    _CACHE[tf] = (now, payload)
    return payload
