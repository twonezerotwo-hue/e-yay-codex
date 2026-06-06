"""
Multi-Timeframe Confluence Engine — E-YAY × Aegis (REVİZE).

Aegis kaynak: aegis_core/engine/confluence.py

REVİZELER (Aegis'in 4 hatasını düzeltir):
  1. Direction band (45-55 nötr zone) — tek 50.0 eşik bug'ı yok
  2. Multiplier asimetrisi açık parametre (config'den okunur)
  3. Nötr TF "vote yok" sayılır — Aegis "mixed" sayıyordu (BUG)
  4. Boş higher TF → 'skipped' status (anlamsız call'ı engelle)
"""
from __future__ import annotations

from typing import Literal

from app.services.regime_weights_engine import get_consensus_config


ConfluenceStatus = Literal["aligned", "opposing", "mixed", "neutral_base", "skipped"]


def _direction(score: float, bull_thr: float, bear_thr: float) -> Literal["bullish", "bearish", "neutral"]:
    if score > bull_thr:
        return "bullish"
    if score < bear_thr:
        return "bearish"
    return "neutral"


def apply_multi_tf_confluence(
    base_score: float,
    higher_tf_scores: dict[str, float],
    config: dict | None = None,
) -> dict:
    """
    Multi-timeframe confluence — base skor + higher TF konfirmasyon multiplier'ı.

    Kurallar (REVİZE):
      • Base nötr (45-55 band) → multiplier 1.0, status='neutral_base'
      • Higher TF yok → multiplier 1.0, status='skipped' (Aegis'in 'no data' uyarısı yerine)
      • Nötr higher TF'ler oylama SAYILMAZ (Aegis'in 'mixed' bug'ı düzeltildi)
      • Sadece non-neutral TF'ler:
          - Hepsi base ile aynı yön → aligned → multiplier=aligned_boost (default 1.20)
          - Hepsi karşı yön        → opposing → multiplier=opposing_penalty (default 0.65)
          - Karışık                → mixed → multiplier=1.0
    """
    cfg = config or get_consensus_config().get("confluence", {})
    aligned_boost     = float(cfg.get("aligned_boost",    1.20))
    opposing_penalty  = float(cfg.get("opposing_penalty", 0.65))
    mixed_multiplier  = float(cfg.get("mixed_multiplier", 1.00))

    direction_cfg = get_consensus_config().get("direction_band", {})
    bull_thr = float(direction_cfg.get("bullish_threshold", 55.0))
    bear_thr = float(direction_cfg.get("bearish_threshold", 45.0))

    warnings: list[str] = []

    # Base skoru clamp
    base_score = max(0.0, min(100.0, float(base_score)))
    base_dir = _direction(base_score, bull_thr, bear_thr)

    # ── REVİZE 4: nötr base veya boş higher → 'skipped' ─
    if base_dir == "neutral":
        warnings.append("Base skor nötr bantta (direction band) — confluence skip.")
        return {
            "original_score": round(base_score, 4),
            "adjusted_score": round(base_score, 4),
            "multiplier":     1.0,
            "status":         "neutral_base",
            "vote_count":     {"aligned": 0, "opposing": 0, "neutral_ignored": 0},
            "warnings":       warnings,
        }

    if not higher_tf_scores:
        warnings.append("Higher timeframe verisi yok — confluence skip.")
        return {
            "original_score": round(base_score, 4),
            "adjusted_score": round(base_score, 4),
            "multiplier":     1.0,
            "status":         "skipped",
            "vote_count":     {"aligned": 0, "opposing": 0, "neutral_ignored": 0},
            "warnings":       warnings,
        }

    # ── Higher TF normalize + oy say ─
    aligned        = 0
    opposing       = 0
    neutral_ignored = 0
    tf_directions: dict[str, str] = {}

    for tf, score in higher_tf_scores.items():
        try:
            s = max(0.0, min(100.0, float(score)))
        except (TypeError, ValueError):
            warnings.append(f"Higher TF '{tf}' skoru sayı değil — yok sayıldı.")
            continue

        d = _direction(s, bull_thr, bear_thr)
        tf_directions[tf] = d

        # ── REVİZE 3: nötr TF oylama sayılmaz (Aegis'in bug'ı) ─
        if d == "neutral":
            neutral_ignored += 1
            continue
        if d == base_dir:
            aligned += 1
        else:
            opposing += 1

    # ── Multiplier kararı ─
    if aligned + opposing == 0:
        # Tüm higher TF'ler nötr → bilgi yok
        status     = "skipped"
        multiplier = 1.0
        warnings.append("Tüm higher TF'ler nötr bantta — confluence skip.")
    elif aligned > 0 and opposing == 0:
        status     = "aligned"
        multiplier = aligned_boost
    elif opposing > 0 and aligned == 0:
        status     = "opposing"
        multiplier = opposing_penalty
    else:
        status     = "mixed"
        multiplier = mixed_multiplier

    # Güvenlik clamp (Aegis ile aynı)
    multiplier = max(0.3, min(1.5, float(multiplier)))
    adjusted = max(0.0, min(100.0, base_score * multiplier))

    return {
        "original_score":  round(base_score, 4),
        "adjusted_score":  round(adjusted, 4),
        "multiplier":      round(multiplier, 4),
        "status":          status,
        "vote_count":      {
            "aligned":         aligned,
            "opposing":        opposing,
            "neutral_ignored": neutral_ignored,
        },
        "tf_directions":   tf_directions,
        "base_direction":  base_dir,
        "warnings":        warnings,
    }


__all__ = ["apply_multi_tf_confluence", "ConfluenceStatus"]
