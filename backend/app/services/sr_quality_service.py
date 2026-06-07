"""
Support/Resistance Quality Service
─────────────────────────────────────────────────────────────────────────────

Bir destek/direnç seviyesinin kalitesini ölçer:

  • touch_count : seviye kaç kere test edildi
  • recency     : son test ne kadar önce (bar cinsinden, yeni → yüksek skor)
  • reaction    : seviye ne kadar güçlü reaksiyon gösterdi (wick yüzdesi)
  • avg_rejection_strength : ortalama reddetme gücü (0-100)

Tüm bileşenler 0-100 arası tek bir `quality_score` oluşturur.
Bu skor consumer'lar tarafından "bu seviyeye güveneyim mi?" sorusuna kullanılır.

PAPER_SAFE / NO_EXECUTION — sadece istatistik.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import numpy as np
except ImportError:    # test ortamında numpy stub olabilir
    np = None    # type: ignore[assignment]


@dataclass(frozen=True)
class SRQuality:
    level:                    float
    side:                     str       # "support" | "resistance"
    touch_count:              int
    last_touch_bars_ago:      int       # -1 = hiç dokunulmadı
    avg_rejection_strength:   float     # 0-100, wick reaction ortalaması
    body_violations:          int       # kaç kere body ile seviye kırıldı (kötüye işaret)
    quality_score:            float     # 0-100 birleşik
    rating:                   str       # "STRONG" | "MEDIUM" | "WEAK" | "UNTESTED"


def _safe_abs(x: float) -> float:
    return abs(float(x)) if x is not None else 0.0


def evaluate_level(
    level: float,
    side: str,                    # "support" | "resistance"
    open_arr: Any,
    high_arr: Any,
    low_arr: Any,
    close_arr: Any,
    *,
    atr: float = 0.0,
    proximity_atr: float = 0.5,   # kaç ATR yakına dokunma sayılsın
    lookback_bars: int = 60,
) -> SRQuality:
    """
    Tek bir seviye için kalite skoru üret.

    Touch tanımı:
      • Support  → low_arr[i] seviye ± proximity_atr*atr içinde
      • Resistance → high_arr[i] aynı şekilde

    Body violation: close seviyenin yanlış tarafında kapanırsa (support için
    close < level − proximity, resistance için close > level + proximity).
    """
    if level <= 0 or side not in ("support", "resistance"):
        return SRQuality(level=level, side=side, touch_count=0,
                         last_touch_bars_ago=-1, avg_rejection_strength=0.0,
                         body_violations=0, quality_score=0.0, rating="UNTESTED")

    if np is None or not hasattr(close_arr, "__len__"):
        return SRQuality(level=level, side=side, touch_count=0,
                         last_touch_bars_ago=-1, avg_rejection_strength=0.0,
                         body_violations=0, quality_score=0.0, rating="UNTESTED")

    n = len(close_arr)
    if n < 10:
        return SRQuality(level=level, side=side, touch_count=0,
                         last_touch_bars_ago=-1, avg_rejection_strength=0.0,
                         body_violations=0, quality_score=0.0, rating="UNTESTED")

    start = max(0, n - lookback_bars)
    tolerance = max(level * 0.001, _safe_abs(atr) * proximity_atr)

    touch_count = 0
    body_violations = 0
    rejection_strengths: list[float] = []
    last_touch_idx = -1

    for i in range(start, n):
        h = float(high_arr[i])
        l = float(low_arr[i])
        c = float(close_arr[i])
        # open_arr[i] şu an aktif kullanılmıyor — gelecek genişleme için tutuluyor

        if side == "support":
            # Wick seviyeyi yokladı mı?
            if l <= level + tolerance and l >= level - tolerance:
                touch_count += 1
                last_touch_idx = i
                # Reaction strength: close > low ne kadar üstüne çıktı → seviyeden ne kadar uzaklaştı
                rebound = c - l
                bar_range = max(h - l, tolerance)
                strength = min(100.0, max(0.0, (rebound / bar_range) * 100))
                rejection_strengths.append(strength)
            # Body violation: close seviyenin tolerance kadar altında kapandı mı?
            if c < level - tolerance:
                body_violations += 1
        else:   # resistance
            if h >= level - tolerance and h <= level + tolerance:
                touch_count += 1
                last_touch_idx = i
                rebound = h - c
                bar_range = max(h - l, tolerance)
                strength = min(100.0, max(0.0, (rebound / bar_range) * 100))
                rejection_strengths.append(strength)
            if c > level + tolerance:
                body_violations += 1

    last_touch_bars_ago = (n - 1 - last_touch_idx) if last_touch_idx >= 0 else -1
    avg_strength = (sum(rejection_strengths) / len(rejection_strengths)
                    if rejection_strengths else 0.0)

    # ── Quality score (0-100) ────────────────────────────────────────────────
    # 1) Touch component (max 40): 3+ touch → tam puan
    touch_component = min(40.0, touch_count * 13.3)
    # 2) Recency component (max 25): son 10 bar içinde dokunulmuş → yüksek
    if last_touch_bars_ago < 0:
        recency_component = 0.0
    elif last_touch_bars_ago <= 5:
        recency_component = 25.0
    elif last_touch_bars_ago <= 15:
        recency_component = 18.0
    elif last_touch_bars_ago <= 30:
        recency_component = 10.0
    else:
        recency_component = 5.0
    # 3) Rejection strength component (max 25): wick reaksiyonu güçlü → yüksek
    rejection_component = min(25.0, avg_strength * 0.25)
    # 4) Body violation penalty (max −20): seviye gerçekten kırıldıysa zayıf
    violation_penalty = -min(20.0, body_violations * 8.0)

    quality_score = max(0.0, min(100.0,
        touch_component + recency_component + rejection_component + violation_penalty
    ))

    # Rating
    if touch_count == 0:
        rating = "UNTESTED"
    elif quality_score >= 70:
        rating = "STRONG"
    elif quality_score >= 45:
        rating = "MEDIUM"
    else:
        rating = "WEAK"

    return SRQuality(
        level                   = round(level, 6),
        side                    = side,
        touch_count             = touch_count,
        last_touch_bars_ago     = last_touch_bars_ago,
        avg_rejection_strength  = round(avg_strength, 2),
        body_violations         = body_violations,
        quality_score           = round(quality_score, 2),
        rating                  = rating,
    )


def evaluate_pair(
    support: float, resistance: float,
    open_arr: Any, high_arr: Any, low_arr: Any, close_arr: Any,
    *, atr: float = 0.0, proximity_atr: float = 0.5, lookback_bars: int = 60,
) -> dict[str, Any]:
    """Bir varlığın hem destek hem direnç seviyesini değerlendir."""
    sup = evaluate_level(support, "support",
                         open_arr, high_arr, low_arr, close_arr,
                         atr=atr, proximity_atr=proximity_atr, lookback_bars=lookback_bars)
    res = evaluate_level(resistance, "resistance",
                         open_arr, high_arr, low_arr, close_arr,
                         atr=atr, proximity_atr=proximity_atr, lookback_bars=lookback_bars)
    return {
        "support":    {
            "level":                 sup.level,
            "touch_count":           sup.touch_count,
            "last_touch_bars_ago":   sup.last_touch_bars_ago,
            "avg_rejection_strength": sup.avg_rejection_strength,
            "body_violations":       sup.body_violations,
            "quality_score":         sup.quality_score,
            "rating":                sup.rating,
        },
        "resistance": {
            "level":                 res.level,
            "touch_count":           res.touch_count,
            "last_touch_bars_ago":   res.last_touch_bars_ago,
            "avg_rejection_strength": res.avg_rejection_strength,
            "body_violations":       res.body_violations,
            "quality_score":         res.quality_score,
            "rating":                res.rating,
        },
    }


__all__ = ["SRQuality", "evaluate_level", "evaluate_pair"]
