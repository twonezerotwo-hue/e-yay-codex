"""
Paper trading deney (sandbox) konfigürasyonu — salt env okuma, yan etki yok.

PAPER_SAFE / NO_EXECUTION korunur: bu bayraklar YALNIZCA paper (simülasyon)
state'i üzerindeki davranışı ayarlar. Gerçek emir / broker / live execution YOK.
Tüm varsayılanlar mevcut davranışı korur (experiment kapalı, schema additive).

Bu modül leaf'tir (yalnız stdlib import eder) — backend import'unu kıramaz.
"""
from __future__ import annotations

import os
from typing import Any


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _intval(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ── Env bayrakları (varsayılanlar = mevcut davranış; experiment kapalı) ───────
PAPER_EXPERIMENT_MODE: bool          = _flag("PAPER_EXPERIMENT_MODE", False)
PAPER_ALLOW_AUTO_TEST_TRADES: bool   = _flag("PAPER_ALLOW_AUTO_TEST_TRADES", False)
PAPER_LEARNING_ENABLED: bool         = _flag("PAPER_LEARNING_ENABLED", True)
PAPER_STALE_EXPERIMENT_ALLOWED: bool = _flag("PAPER_STALE_EXPERIMENT_ALLOWED", True)
PAPER_MAX_OPEN_POSITIONS: int        = _intval("PAPER_MAX_OPEN_POSITIONS", 0)   # 0 = mevcut limiti kullan
PAPER_MAX_TICK_AGE_SECONDS: int      = _intval("PAPER_MAX_TICK_AGE_SECONDS", 300)
PAPER_HARD_STALE_SECONDS: int        = _intval("PAPER_HARD_STALE_SECONDS", 900)


def experiment_view() -> dict[str, Any]:
    """get_snapshot içine additive gömülen salt-okunur görünüm.
    Mevcut alanları değiştirmez; UI bunu opsiyonel okur."""
    return {
        "mode":                     "experiment" if PAPER_EXPERIMENT_MODE else "standard",
        "experiment_mode":          PAPER_EXPERIMENT_MODE,
        "allow_auto_test_trades":   PAPER_ALLOW_AUTO_TEST_TRADES,
        "learning_enabled":         PAPER_LEARNING_ENABLED,
        "stale_experiment_allowed": PAPER_STALE_EXPERIMENT_ALLOWED,
        "max_open_positions":       PAPER_MAX_OPEN_POSITIONS or None,
        "max_tick_age_seconds":     PAPER_MAX_TICK_AGE_SECONDS,
        "hard_stale_seconds":       PAPER_HARD_STALE_SECONDS,
        "paper_safe":               True,
        "no_execution":             True,
    }


__all__ = [n for n in globals() if not n.startswith("_")]
