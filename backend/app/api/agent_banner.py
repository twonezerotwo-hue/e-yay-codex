"""
FAZ 10.1 — Agent Banner API.

Read-only endpoint:
  GET /agent/banner

Stored data'dan (snapshot/thesis/paper state/learning) dinamik banner döner.
Canlı market/broker çağrısı yapmaz.
30sn TTL cache — her istekte fresh veri değil, son 30sn'nin verisi.

Güvenlik:
  PAPER_SAFE / NO_EXECUTION
  Broker yok, live execution yok.
  Trade açmaz/kapatmaz.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from app.services.agent_banner_service import build_agent_banner

router = APIRouter(prefix="/agent", tags=["agent"])

# 30sn TTL — anlık değil ama her reload'da stale değil
_BANNER_CACHE: tuple[float, dict[str, Any]] | None = None
_BANNER_TTL = 30.0


@router.get("/banner")
def get_agent_banner() -> dict[str, Any]:
    """
    Sistem durumuna göre dinamik agent banner üretir — read-only.

    Kaynaklar: hourly snapshot, agent thesis, paper trading state,
               position recheck, learning candidates, mistake memory,
               weekly calibration, auto tune overrides.

    Canlı market çağrısı yoktur; broker bağlantısı yoktur.
    """
    global _BANNER_CACHE
    now = time.monotonic()
    if _BANNER_CACHE and (now - _BANNER_CACHE[0]) < _BANNER_TTL:
        return _BANNER_CACHE[1]

    result = build_agent_banner()
    _BANNER_CACHE = (now, result)
    return result
