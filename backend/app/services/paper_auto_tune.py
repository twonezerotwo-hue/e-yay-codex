"""
Aşama 4 — Paper trade learning auto-tune (küçük, clamp'li).

Mevcut learning store'larından (positive_memory / mistake_memory) son N kaydı
okur ve asset|side bazında KÜÇÜK bir ayarlama üretir:

  Kaybeden pattern (net <= -2) → label "learning_penalty"
      threshold_delta +2..+5 (bar yükselir), size_multiplier 0.80..0.95
  Kazanan pattern (net >= +2) → label "learning_boost"
      threshold_delta -2..-5 (bar düşer),  size_multiplier 1.05..1.20

Clamp: |threshold_delta| <= 5, size_multiplier in [0.80, 1.20].

Salt-okuma + best-effort: store okunamazsa boş döner, paper trading'i ASLA
crash ettirmez. Hiçbir state yazmaz. Etki uygulaması çağıran tarafta ve
yalnızca PAPER_EXPERIMENT_MODE açıkken yapılır (bu modül sadece hesaplar).
PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import time
from typing import Any

_RECENT_N = 20
_MIN_SAMPLES = 2

# Küçük TTL cache — state her okunduğunda dosyayı tekrar taramasın
_CACHE: tuple[float, dict[str, dict[str, Any]]] | None = None
_TTL = 15.0


def _key(asset: str, side: str) -> str:
    return f"{asset}|{side}"


def _tally(recent_n: int) -> tuple[dict[str, int], dict[str, int]]:
    """positive_memory (win) ve mistake_memory (loss) sayımını asset|side'a göre döner."""
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}

    try:
        from app.storage.learning_candidate_store import (  # noqa: PLC0415
            load_recent_learning_candidates,
        )
        for r in load_recent_learning_candidates(limit=recent_n):
            if "positive_memory" not in (r.get("candidate_labels") or []):
                continue
            a, s = str(r.get("pair", "")), str(r.get("side", ""))
            if a and s:
                wins[_key(a, s)] = wins.get(_key(a, s), 0) + 1
    except Exception:  # noqa: BLE001
        pass

    try:
        from app.storage.mistake_memory_store import (  # noqa: PLC0415
            load_recent_mistake_memory,
        )
        for r in load_recent_mistake_memory(limit=recent_n):
            if "mistake_memory" not in (r.get("final_labels") or []):
                continue
            tr = r.get("trade") or {}
            a, s = str(tr.get("pair", "")), str(tr.get("side", ""))
            if a and s:
                losses[_key(a, s)] = losses.get(_key(a, s), 0) + 1
    except Exception:  # noqa: BLE001
        pass

    return wins, losses


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_adjustments(recent_n: int = _RECENT_N, use_cache: bool = True) -> dict[str, dict[str, Any]]:
    """asset|side → {label, threshold_delta, size_multiplier, wins, losses, net}.

    Yeterli örnek (>= _MIN_SAMPLES) yoksa o anahtar atlanır → memory boşken {} döner.
    """
    global _CACHE
    now = time.monotonic()
    if use_cache and _CACHE is not None and (now - _CACHE[0]) < _TTL:
        return _CACHE[1]

    wins, losses = _tally(recent_n)
    out: dict[str, dict[str, Any]] = {}
    for k in set(wins) | set(losses):
        w, l = wins.get(k, 0), losses.get(k, 0)
        if w + l < _MIN_SAMPLES:
            continue
        net = w - l
        if net <= -2:
            td = int(_clamp(abs(net) + 1, 2, 5))
            sm = round(_clamp(0.97 - 0.03 * abs(net), 0.80, 0.95), 3)
            out[k] = {"label": "learning_penalty", "threshold_delta": td,
                      "size_multiplier": sm, "wins": w, "losses": l, "net": net}
        elif net >= 2:
            td = -int(_clamp(net + 1, 2, 5))
            sm = round(_clamp(1.03 + 0.03 * net, 1.05, 1.20), 3)
            out[k] = {"label": "learning_boost", "threshold_delta": td,
                      "size_multiplier": sm, "wins": w, "losses": l, "net": net}

    _CACHE = (now, out)
    return out


def adjustment_for(asset: str, side: str, recent_n: int = _RECENT_N) -> dict[str, Any] | None:
    """Tek asset|side için ayarlama (yoksa None). Best-effort."""
    try:
        return compute_adjustments(recent_n).get(_key(asset, side))
    except Exception:  # noqa: BLE001
        return None


__all__ = ["compute_adjustments", "adjustment_for"]
