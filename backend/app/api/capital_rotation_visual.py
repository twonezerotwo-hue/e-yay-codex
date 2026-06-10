"""
FAZ 14 — Capital Rotation Visual API.

Read-only endpoint:
  GET /capital-rotation/visual

Mevcut CapitalRotationProvider çıktısını visual layer modeline çevirir.
Karar üretmez. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter

from app.services.capital_rotation_visual_adapter import build_visual_payload

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/capital-rotation", tags=["capital-rotation-visual"])

_CACHE: tuple[float, dict[str, Any]] | None = None
_TTL   = 30.0


@router.get("/visual")
def get_visual() -> dict[str, Any]:
    """
    Read-only visual layer payload.
    30sn TTL cache — provider'a yük bindirmez.
    """
    global _CACHE
    now = time.monotonic()
    if _CACHE is not None and (now - _CACHE[0]) < _TTL:
        return _CACHE[1]

    try:
        from app.providers.capital_rotation_provider import (  # noqa: PLC0415
            CapitalRotationProvider,
        )
        rotation = CapitalRotationProvider().compute()
    except Exception as exc:  # noqa: BLE001
        _log.warning("capital_rotation_visual: provider unavailable: %s", exc)
        payload = {
            "status":              "degraded",
            "schema_version":      "capital_rotation_visual_v1",
            "source":              "capital_rotation_provider",
            "decision_permission": "NO_EXECUTION",
            "execution_mode":      "PAPER_SAFE",
            "visual_mode":         "animated_flow",
            "conviction":          0,
            "primary_flow":        "",
            "nodes":               [],
            "flows":               [],
            "fallback_reason":     f"provider_unavailable: {type(exc).__name__}",
        }
        _CACHE = (now, payload)
        return payload

    payload = build_visual_payload(rotation)
    _CACHE = (now, payload)
    return payload
