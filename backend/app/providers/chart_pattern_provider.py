"""
Chart Pattern Provider — Mum + Trend + Destek/Direnç pattern okuyucu.

OHLCV ham veri alır → candlestick patterns, trend structure, S/R proximity tespit eder.
Sonuçta her varlık için -100..+100 arası pattern_score üretir.

PAPER_SAFE / NO_EXECUTION. Pure pandas/numpy — extra dependency YOK.

Mevcut sisteme zarar vermez:
  • Standalone fonksiyonlar (input: OHLCV, output: insight)
  • Hata olursa None döner, mevcut akış etkilenmez
  • Yeni yfinance çağrısı yapmaz
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np

logger = logging.getLogger(__name__)

PatternBias = Literal["bullish", "bearish", "neutral"]
TrendStructure = Literal["uptrend", "downtrend", "neutral"]


# ─────────────────────────────────────────────────────────────────────────────
# Output modelleri
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CandlestickPattern:
    name: str               # "hammer", "engulfing_bullish", ...
    bias: PatternBias
    strength: float         # 0-100, pattern netliği
    bar_offset: int         # 0 = son bar, -1 = önceki, ...
    note: str = ""          # açıklama


@dataclass(frozen=True)
class ChartPatternInsight:
    asset_code: str
    timeframe: str
    patterns: tuple[CandlestickPattern, ...]
    trend_structure: TrendStructure
    trend_strength: float          # 0-100
    near_support: bool
    near_resistance: bool
    distance_to_support_atr: float   # kaç ATR uzakta
    distance_to_resistance_atr: float
    pattern_score: float           # -100 (strong bearish) ... +100 (strong bullish)
    reason: str                    # insan-okur özet


# ─────────────────────────────────────────────────────────────────────────────
# Candlestick pattern detektörleri — saf numpy
# ─────────────────────────────────────────────────────────────────────────────

def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0 or not np.isfinite(b):
        return default
    return a / b


def _bar_metrics(o: float, h: float, l: float, c: float) -> dict[str, float]:
    """Bar metriklerini tek seferde üret."""
    rng = h - l
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    is_green = c > o
    return {
        "range": rng,
        "body": body,
        "upper_wick": upper,
        "lower_wick": lower,
        "body_pct": _safe_div(body, rng, 0.0),
        "upper_pct": _safe_div(upper, rng, 0.0),
        "lower_pct": _safe_div(lower, rng, 0.0),
        "is_green": is_green,
    }


def _detect_doji(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> CandlestickPattern | None:
    """Doji — açılış≈kapanış, kararsızlık."""
    if len(c) < 1:
        return None
    m = _bar_metrics(o[-1], h[-1], l[-1], c[-1])
    if m["range"] == 0:
        return None
    if m["body_pct"] < 0.1:    # body < %10 of range
        return CandlestickPattern(
            name="doji",
            bias="neutral",
            strength=80.0 - m["body_pct"] * 500,  # daha küçük body → daha güçlü doji
            bar_offset=0,
            note=f"body %{m['body_pct']*100:.1f}",
        )
    return None


def _detect_hammer(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> CandlestickPattern | None:
    """Hammer / Pin Bar — uzun alt fitil, küçük gövde, kısa üst fitil → bullish reversal."""
    if len(c) < 1:
        return None
    m = _bar_metrics(o[-1], h[-1], l[-1], c[-1])
    if m["range"] == 0 or m["body"] == 0:
        return None
    lower_to_body = _safe_div(m["lower_wick"], m["body"], 0)
    upper_to_body = _safe_div(m["upper_wick"], m["body"], 0)
    if lower_to_body >= 2.0 and upper_to_body < 0.5 and m["body_pct"] < 0.4:
        return CandlestickPattern(
            name="hammer",
            bias="bullish",
            strength=min(100.0, 50.0 + lower_to_body * 10),
            bar_offset=0,
            note=f"alt fitil {lower_to_body:.1f}× body",
        )
    return None


def _detect_shooting_star(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> CandlestickPattern | None:
    """Shooting Star — uzun üst fitil, küçük gövde, kısa alt fitil → bearish reversal."""
    if len(c) < 1:
        return None
    m = _bar_metrics(o[-1], h[-1], l[-1], c[-1])
    if m["range"] == 0 or m["body"] == 0:
        return None
    upper_to_body = _safe_div(m["upper_wick"], m["body"], 0)
    lower_to_body = _safe_div(m["lower_wick"], m["body"], 0)
    if upper_to_body >= 2.0 and lower_to_body < 0.5 and m["body_pct"] < 0.4:
        return CandlestickPattern(
            name="shooting_star",
            bias="bearish",
            strength=min(100.0, 50.0 + upper_to_body * 10),
            bar_offset=0,
            note=f"üst fitil {upper_to_body:.1f}× body",
        )
    return None


def _detect_engulfing(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> CandlestickPattern | None:
    """Engulfing — önceki bar tersi yön, mevcut bar gövdesi öncekini tamamen sarar."""
    if len(c) < 2:
        return None
    prev = _bar_metrics(o[-2], h[-2], l[-2], c[-2])
    curr = _bar_metrics(o[-1], h[-1], l[-1], c[-1])
    if prev["body"] == 0 or curr["body"] == 0:
        return None

    # Bullish engulfing: prev kırmızı, curr yeşil, curr gövdesi prev'i sarar
    if not prev["is_green"] and curr["is_green"]:
        if c[-1] > o[-2] and o[-1] < c[-2]:    # curr açılış prev kapanışın altında, curr kapanış prev açılışın üstünde
            body_ratio = _safe_div(curr["body"], prev["body"], 0)
            if body_ratio >= 1.2:
                return CandlestickPattern(
                    name="engulfing_bullish",
                    bias="bullish",
                    strength=min(100.0, 60.0 + body_ratio * 10),
                    bar_offset=0,
                    note=f"gövde {body_ratio:.1f}× önceki",
                )

    # Bearish engulfing: prev yeşil, curr kırmızı, curr gövdesi prev'i sarar
    if prev["is_green"] and not curr["is_green"]:
        if c[-1] < o[-2] and o[-1] > c[-2]:
            body_ratio = _safe_div(curr["body"], prev["body"], 0)
            if body_ratio >= 1.2:
                return CandlestickPattern(
                    name="engulfing_bearish",
                    bias="bearish",
                    strength=min(100.0, 60.0 + body_ratio * 10),
                    bar_offset=0,
                    note=f"gövde {body_ratio:.1f}× önceki",
                )
    return None


def _detect_inside_bar(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> CandlestickPattern | None:
    """Inside Bar — mevcut bar tamamen önceki barın içinde, sıkışma/kırılım hazırlığı."""
    if len(c) < 2:
        return None
    if h[-1] < h[-2] and l[-1] > l[-2]:
        # Range küçüldü mü?
        prev_range = h[-2] - l[-2]
        curr_range = h[-1] - l[-1]
        compression = _safe_div(curr_range, prev_range, 1.0)
        return CandlestickPattern(
            name="inside_bar",
            bias="neutral",
            strength=max(40.0, 100.0 - compression * 50),
            bar_offset=0,
            note=f"sıkışma %{compression*100:.0f}",
        )
    return None


def _detect_marubozu(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> CandlestickPattern | None:
    """Marubozu — gövde tüm bar, fitil minimal → güçlü trend devam."""
    if len(c) < 1:
        return None
    m = _bar_metrics(o[-1], h[-1], l[-1], c[-1])
    if m["range"] == 0:
        return None
    if m["body_pct"] >= 0.85:    # body %85+ of range
        bias: PatternBias = "bullish" if m["is_green"] else "bearish"
        return CandlestickPattern(
            name="marubozu",
            bias=bias,
            strength=60.0 + m["body_pct"] * 30,
            bar_offset=0,
            note=f"body %{m['body_pct']*100:.0f}",
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Trend yapısı — HH/HL veya LL/LH (son N bar üzerinden swing tespiti)
# ─────────────────────────────────────────────────────────────────────────────

def _find_swing_points(
    high: np.ndarray, low: np.ndarray, lookback: int = 30, window: int = 3,
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Son `lookback` bar içinde local swing high/low noktalarını bul.

    Bir bar swing high'tır eğer kendisinden ± `window` kadarındaki tüm barlardan yüksekse.
    Returns: (swing_highs, swing_lows) — her biri (index, price) listesi.
    """
    n = len(high)
    start = max(window, n - lookback)
    swing_highs: list[tuple[int, float]] = []
    swing_lows: list[tuple[int, float]] = []

    for i in range(start, n - window):
        left_h = high[i - window:i]
        right_h = high[i + 1:i + window + 1]
        if high[i] > left_h.max() and high[i] > right_h.max():
            swing_highs.append((i, float(high[i])))

        left_l = low[i - window:i]
        right_l = low[i + 1:i + window + 1]
        if low[i] < left_l.min() and low[i] < right_l.min():
            swing_lows.append((i, float(low[i])))

    return swing_highs, swing_lows


def _classify_trend(
    high: np.ndarray, low: np.ndarray, lookback: int = 30,
) -> tuple[TrendStructure, float]:
    """Son `lookback` bar swing yapısına göre trend kararı + güç skoru (0-100)."""
    swing_h, swing_l = _find_swing_points(high, low, lookback=lookback)
    if len(swing_h) < 2 or len(swing_l) < 2:
        return "neutral", 30.0

    # Son 2 swing high, son 2 swing low
    last_h, prev_h = swing_h[-1][1], swing_h[-2][1]
    last_l, prev_l = swing_l[-1][1], swing_l[-2][1]

    hh = last_h > prev_h     # Higher High
    hl = last_l > prev_l     # Higher Low
    lh = last_h < prev_h     # Lower High
    ll = last_l < prev_l     # Lower Low

    # HH + HL = uptrend
    if hh and hl:
        pct_up = ((last_h - prev_h) / prev_h + (last_l - prev_l) / prev_l) / 2 * 100
        strength = min(100.0, 50.0 + abs(pct_up) * 20)
        return "uptrend", strength

    # LL + LH = downtrend
    if ll and lh:
        pct_dn = ((prev_h - last_h) / prev_h + (prev_l - last_l) / prev_l) / 2 * 100
        strength = min(100.0, 50.0 + abs(pct_dn) * 20)
        return "downtrend", strength

    # Karışık — nötr
    return "neutral", 40.0


# ─────────────────────────────────────────────────────────────────────────────
# Destek/Direnç yakınlığı (verilen support/resistance + ATR ile)
# ─────────────────────────────────────────────────────────────────────────────

def _proximity_to_levels(
    current: float, support: float, resistance: float, atr: float,
) -> tuple[bool, bool, float, float]:
    """Fiyatın S/R'a kaç ATR uzakta olduğunu hesapla."""
    if atr <= 0:
        return False, False, 999.0, 999.0
    dist_sup = (current - support) / atr if support > 0 else 999.0
    dist_res = (resistance - current) / atr if resistance > 0 else 999.0
    near_sup = 0 < dist_sup <= 1.0    # 1 ATR içinde
    near_res = 0 < dist_res <= 1.0
    return near_sup, near_res, dist_sup, dist_res


# ─────────────────────────────────────────────────────────────────────────────
# Pattern skoru — tüm sinyalleri tek bir -100..+100 skoruna birleştir
# ─────────────────────────────────────────────────────────────────────────────

def _aggregate_pattern_score(
    patterns: list[CandlestickPattern],
    trend: TrendStructure,
    trend_strength: float,
    near_support: bool,
    near_resistance: bool,
) -> tuple[float, str]:
    """Patterns + trend + S/R yakınlığını -100..+100 arası tek skor + açıklama yap."""
    score = 0.0
    reasons: list[str] = []

    # Trend baz katkısı
    if trend == "uptrend":
        score += trend_strength * 0.3
        reasons.append(f"Uptrend HH/HL (güç {trend_strength:.0f})")
    elif trend == "downtrend":
        score -= trend_strength * 0.3
        reasons.append(f"Downtrend LL/LH (güç {trend_strength:.0f})")

    # Pattern katkıları — destek/direnç bağlamına göre ödüllendir/cezalandır
    for p in patterns:
        if p.bias == "bullish":
            mult = 1.0
            ctx = ""
            if near_support:
                mult = 1.5    # bullish pattern + destek = güçlü teyit
                ctx = " (destekte)"
            elif near_resistance:
                mult = 0.5    # bullish pattern + direnç = zayıf
                ctx = " (dirençte zayıf)"
            score += p.strength * 0.5 * mult
            reasons.append(f"{p.name}{ctx} +{p.strength*0.5*mult:.0f}")
        elif p.bias == "bearish":
            mult = 1.0
            ctx = ""
            if near_resistance:
                mult = 1.5
                ctx = " (dirençte)"
            elif near_support:
                mult = 0.5
                ctx = " (destekte zayıf)"
            score -= p.strength * 0.5 * mult
            reasons.append(f"{p.name}{ctx} -{p.strength*0.5*mult:.0f}")
        else:    # neutral
            reasons.append(f"{p.name} (nötr)")

    # Clamp -100..+100
    score = max(-100.0, min(100.0, score))
    reason = " · ".join(reasons) if reasons else "belirgin pattern yok"
    return round(score, 1), reason


# ─────────────────────────────────────────────────────────────────────────────
# Ana entry point — OHLCV input alır, ChartPatternInsight üretir
# ─────────────────────────────────────────────────────────────────────────────

def analyze_chart_patterns(
    asset_code: str,
    timeframe: str,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    *,
    support: float = 0.0,
    resistance: float = 0.0,
    atr: float = 0.0,
) -> ChartPatternInsight | None:
    """
    OHLCV array'lerinden chart pattern analizi yap.

    Args:
        asset_code: Varlık kodu (BTCUSD, XAUUSD, ...)
        timeframe: Zaman dilimi ("1h", "4h", "1d")
        open_, high, low, close: numpy array (en az 30 bar)
        support, resistance, atr: Mevcut TechnicalInsight'tan alınan seviyeler

    Returns:
        ChartPatternInsight | None (yeterli veri yoksa None)
    """
    if len(close) < 30:
        return None
    if not (len(open_) == len(high) == len(low) == len(close)):
        return None

    try:
        # 1. Candlestick pattern tarama
        detectors = [
            _detect_doji,
            _detect_hammer,
            _detect_shooting_star,
            _detect_engulfing,
            _detect_inside_bar,
            _detect_marubozu,
        ]
        patterns: list[CandlestickPattern] = []
        for detector in detectors:
            p = detector(open_, high, low, close)
            if p is not None:
                patterns.append(p)

        # 2. Trend yapısı
        trend, trend_strength = _classify_trend(high, low, lookback=30)

        # 3. Destek/Direnç yakınlığı
        current = float(close[-1])
        near_sup, near_res, dist_sup, dist_res = _proximity_to_levels(
            current, support, resistance, atr
        )

        # 4. Birleşik skor
        score, reason = _aggregate_pattern_score(
            patterns, trend, trend_strength, near_sup, near_res
        )

        return ChartPatternInsight(
            asset_code=asset_code,
            timeframe=timeframe,
            patterns=tuple(patterns),
            trend_structure=trend,
            trend_strength=round(trend_strength, 1),
            near_support=near_sup,
            near_resistance=near_res,
            distance_to_support_atr=round(dist_sup, 2),
            distance_to_resistance_atr=round(dist_res, 2),
            pattern_score=score,
            reason=reason,
        )
    except Exception as exc:
        logger.warning("Chart pattern analizi hatası %s [%s]: %s", asset_code, timeframe, exc)
        return None


__all__ = [
    "CandlestickPattern",
    "ChartPatternInsight",
    "analyze_chart_patterns",
]
