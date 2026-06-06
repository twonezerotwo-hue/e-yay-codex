"""
Execution Boundary Guard — Sprint 1 / Item 2.

PAPER_SAFE / NO_EXECUTION kuralını kod seviyesinde kilitler.

Kural:
  • EXECUTION_MODE = "OFF" → tüm paper sim aksiyonları serbest.
  • EXECUTION_MODE ≠ "OFF" → tüm mutasyon endpoint'leri 403.

Bu, prompt veya doc ile değil, FastAPI dependency ile zorlanır.
Live execution için ayrı bir build path gerekir — yanlışlıkla açılamaz.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status

from app.core.config import get_settings

_log = logging.getLogger(__name__)


def is_paper_safe() -> bool:
    """EXECUTION_MODE değerini oku, paper-safe ise True döner."""
    mode = (get_settings().execution_mode or "").strip().upper()
    return mode == "OFF"


def assert_paper_safe() -> None:
    """Paper-safe değilse HTTP 403 fırlat — POST mutasyon endpoint'leri için."""
    if not is_paper_safe():
        mode = get_settings().execution_mode
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"PAPER_SAFE boundary violation: EXECUTION_MODE='{mode}' (beklenen 'OFF'). "
                "Bu sürüm yalnızca simülasyon yapar; gerçek emir yetkisi YOK."
            ),
        )


def require_paper_safe() -> dict[str, Any]:
    """FastAPI dependency. Mutasyon endpoint'lerine `Depends(require_paper_safe)` ekle."""
    assert_paper_safe()
    return {"mode": "PAPER_SAFE", "execution": "OFF"}


def boundary_status() -> dict[str, Any]:
    """GET endpoint'leri ve health-check için durum özeti."""
    settings = get_settings()
    return {
        "paper_safe":     is_paper_safe(),
        "execution_mode": settings.execution_mode,
        "guard":          "code-level (require_paper_safe dependency)",
        "violation_action": "HTTP 403 + log",
    }


def log_startup_boundary() -> None:
    """Uygulama startup'ında EXECUTION_MODE'u logla — çalışırken kayıt kalsın."""
    settings = get_settings()
    if is_paper_safe():
        _log.info("execution_boundary OK · EXECUTION_MODE=%s · PAPER_SAFE / NO_EXECUTION",
                  settings.execution_mode)
    else:
        _log.error(
            "execution_boundary WARNING · EXECUTION_MODE=%s · POST mutasyonları bloklanacak.",
            settings.execution_mode,
        )


__all__ = [
    "is_paper_safe",
    "assert_paper_safe",
    "require_paper_safe",
    "boundary_status",
    "log_startup_boundary",
]
