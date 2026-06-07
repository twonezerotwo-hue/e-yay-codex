"""
Agent Chart Reader — multi-timeframe S/R + trend + ATR (Sprint Item 9).

Mevcut `TechnicalProvider` 1D çalışıyor; agent için "şu an aktif TF'de ne
görüyor" sorusuna cevap üretmek için 1h / 4h / 1d katmanlarını ayrı ayrı çeker
ve sade bir karşılaştırma raporu döner.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import logging
import threading
import time as _time
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Cache: (ticker, tf_label) → (df, ts_monotonic)
_CACHE: dict[tuple[str, str], tuple[Any, float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 180.0  # 3 dakika — yfinance soft limit + UI snappy


_TF_PRESETS: dict[str, tuple[str, str]] = {
    # tf_label : (yfinance interval, period — soft limits)
    "1h":  ("1h",  "60d"),     # ~1500 bar
    "4h":  ("1h",  "60d"),     # 4h yok → 1h çek + resample
    "1d":  ("1d",  "200d"),
    "1wk": ("1wk", "5y"),
}


_TICKER_MAP = {
    "BTCUSD": "BTC-USD",
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "XCUUSD": "HG=F",
    "BRENT":  "BZ=F",
    "DXY":    "DX-Y.NYB",
    "VIX":    "^VIX",
    "SP500":  "^GSPC",
    "ETHUSD": "ETH-USD",
    "HYG":    "HYG",
    "QQQ":    "QQQ",
    "IWM":    "IWM",
    "SMH":    "SMH",
    "XLF":    "XLF",
}


@dataclass
class TFView:
    timeframe:   str             # "1h" | "4h" | "1d" | "1wk"
    bars_used:   int
    current:     float
    support:     float
    resistance:  float
    atr:         float
    atr_pct:     float
    trend:       str             # BULLISH | BEARISH | NEUTRAL
    rsi_14:      float | None
    distance_to_support_pct:    float | None
    distance_to_resistance_pct: float | None
    last_close_vs_open_pct:     float | None
    notes:       list[str] = field(default_factory=list)


@dataclass
class ChartReading:
    asset_code:    str
    ticker:        str
    timeframes:    list[TFView]
    primary_tf:    str           # En güvenilir / consensus TF
    alignment:    str            # "STRONG_BULL" | "STRONG_BEAR" | "MIXED" | "NEUTRAL"
    alignment_pct: float
    summary:      str
    error:        str | None = None


def _wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    if len(high) < period + 1:
        return 0.0
    tr_arr = []
    prev_close = close[0]
    for i in range(1, len(close)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - prev_close),
            abs(low[i] - prev_close),
        )
        tr_arr.append(tr)
        prev_close = close[i]
    tr_arr = np.array(tr_arr)
    if len(tr_arr) < period:
        return 0.0
    atr = float(np.mean(tr_arr[:period]))
    for i in range(period, len(tr_arr)):
        atr = (atr * (period - 1) + tr_arr[i]) / period
    return atr


def _rsi(close: np.ndarray, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    deltas = np.diff(close)
    ups = np.maximum(deltas, 0)
    downs = np.maximum(-deltas, 0)
    avg_up = float(np.mean(ups[:period]))
    avg_dn = float(np.mean(downs[:period]))
    for i in range(period, len(deltas)):
        avg_up = (avg_up * (period - 1) + ups[i]) / period
        avg_dn = (avg_dn * (period - 1) + downs[i]) / period
    if avg_dn == 0:
        return 100.0
    rs = avg_up / avg_dn
    return round(100 - (100 / (1 + rs)), 2)


def _resample_to_4h(df):
    """1h df'sini 4h'ya yuvarla."""
    try:
        return df.resample("4h").agg({
            "Open":   "first",
            "High":   "max",
            "Low":    "min",
            "Close":  "last",
            "Volume": "sum",
        }).dropna()
    except Exception as exc:
        logger.warning("4h resample fail: %s", exc)
        return df


def _fetch_ohlcv(ticker: str, tf_label: str):
    """yfinance'tan OHLCV çek, 4h ise resample. None döner hata olursa.

    3 dk'lık in-process cache — peş peşe kart flip'leri tek istek atar.
    """
    if tf_label not in _TF_PRESETS:
        return None
    key = (ticker, tf_label)
    now = _time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None and (now - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

    import yfinance as yf
    interval, period = _TF_PRESETS[tf_label]
    try:
        df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    except Exception as exc:
        logger.warning("yfinance fail %s %s: %s", ticker, tf_label, exc)
        return None
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    if tf_label == "4h":
        df = _resample_to_4h(df)
    with _CACHE_LOCK:
        _CACHE[key] = (df, now)
        # Cache büyüklüğü cap — 100'den fazlaysa en eskiyi at
        if len(_CACHE) > 100:
            oldest = min(_CACHE.items(), key=lambda kv: kv[1][1])[0]
            _CACHE.pop(oldest, None)
    return df


def _trend(close: np.ndarray) -> str:
    """Basit yapı: son 10 bar EMA20 üzerinde mi?"""
    if len(close) < 30:
        return "NEUTRAL"
    ema = float(np.mean(close[-20:]))
    cur = float(close[-1])
    if cur > ema * 1.005:
        return "BULLISH"
    if cur < ema * 0.995:
        return "BEARISH"
    return "NEUTRAL"


def _swing_sr(high: np.ndarray, low: np.ndarray, lookback: int = 30) -> tuple[float, float]:
    seg_h = high[-lookback:] if len(high) >= lookback else high
    seg_l = low[-lookback:] if len(low) >= lookback else low
    return float(np.min(seg_l)), float(np.max(seg_h))


def _build_tf_view(tf_label: str, df) -> TFView | None:
    if df is None or df.empty:
        return None
    try:
        h = df["High"].dropna().to_numpy(dtype=float)
        l = df["Low"].dropna().to_numpy(dtype=float)
        c = df["Close"].dropna().to_numpy(dtype=float)
        o = df["Open"].dropna().to_numpy(dtype=float) if "Open" in df.columns else c
    except Exception:
        return None
    if len(c) < 16:
        return None
    cur = float(c[-1])
    if cur <= 0:
        return None

    sup, res = _swing_sr(h, l, lookback=min(40, len(h)))
    atr = _wilder_atr(h, l, c, period=14)
    atr_pct = (atr / cur * 100) if cur else 0.0
    trend = _trend(c)
    rsi = _rsi(c, 14)

    dist_sup = ((cur - sup) / cur * 100) if cur else None
    dist_res = ((res - cur) / cur * 100) if cur else None
    last_co = ((c[-1] - o[-1]) / o[-1] * 100) if (len(o) > 0 and o[-1]) else None

    notes: list[str] = []
    if rsi is not None and rsi > 70:
        notes.append("RSI aşırı alım bölgesinde")
    elif rsi is not None and rsi < 30:
        notes.append("RSI aşırı satım bölgesinde")
    if dist_sup is not None and dist_sup < 1.0:
        notes.append("Fiyat destek hemen üstünde (~%1)")
    if dist_res is not None and dist_res < 1.0:
        notes.append("Fiyat direnç hemen altında (~%1)")
    if atr_pct > 4.0:
        notes.append(f"Yüksek volatilite (ATR%{atr_pct:.1f})")

    return TFView(
        timeframe=tf_label,
        bars_used=len(c),
        current=round(cur, 6),
        support=round(sup, 6),
        resistance=round(res, 6),
        atr=round(atr, 6),
        atr_pct=round(atr_pct, 3),
        trend=trend,
        rsi_14=rsi,
        distance_to_support_pct=round(dist_sup, 3) if dist_sup is not None else None,
        distance_to_resistance_pct=round(dist_res, 3) if dist_res is not None else None,
        last_close_vs_open_pct=round(last_co, 3) if last_co is not None else None,
        notes=notes,
    )


def _alignment(views: list[TFView]) -> tuple[str, float, str]:
    if not views:
        return "NEUTRAL", 0.0, "TF verisi alınamadı."
    bulls = sum(1 for v in views if v.trend == "BULLISH")
    bears = sum(1 for v in views if v.trend == "BEARISH")
    n = len(views)
    pct = round(100 * max(bulls, bears) / n, 1)
    if bulls == n:
        return "STRONG_BULL", 100.0, "Tüm timeframe'ler yukarı yönlü hizalı."
    if bears == n:
        return "STRONG_BEAR", 100.0, "Tüm timeframe'ler aşağı yönlü hizalı."
    if bulls > bears:
        return "MIXED", pct, f"{bulls}/{n} TF yukarı, {bears}/{n} aşağı — kısa ufuk farklı."
    if bears > bulls:
        return "MIXED", pct, f"{bears}/{n} TF aşağı, {bulls}/{n} yukarı — kısa ufuk farklı."
    return "NEUTRAL", round(100 * (n - bulls - bears) / n, 1), "Yön belirgin değil."


def _pick_primary_tf(views: list[TFView]) -> str:
    """1d öncelikli, sonra 4h, sonra 1h."""
    priority = ["1d", "4h", "1h", "1wk"]
    have = {v.timeframe for v in views}
    for p in priority:
        if p in have:
            return p
    return views[0].timeframe if views else "1d"


def read_chart(
    asset_code: str,
    timeframes: list[str] | None = None,
) -> ChartReading:
    """Bir varlık için belirtilen TF'lerde chart oku, hizalama raporla."""
    tfs = timeframes or ["1h", "4h", "1d"]
    ticker = _TICKER_MAP.get(asset_code.upper())
    if not ticker:
        return ChartReading(
            asset_code=asset_code, ticker="?",
            timeframes=[], primary_tf="?",
            alignment="NEUTRAL", alignment_pct=0.0,
            summary="Sembol için yfinance ticker tanımı yok.",
            error="ticker_not_mapped",
        )

    views: list[TFView] = []
    for tf in tfs:
        if tf not in _TF_PRESETS:
            continue
        df = _fetch_ohlcv(ticker, tf)
        v = _build_tf_view(tf, df) if df is not None else None
        if v is not None:
            views.append(v)

    if not views:
        return ChartReading(
            asset_code=asset_code, ticker=ticker,
            timeframes=[], primary_tf=tfs[0],
            alignment="NEUTRAL", alignment_pct=0.0,
            summary="Veri çekilemedi.",
            error="no_data",
        )

    primary = _pick_primary_tf(views)
    align, align_pct, align_text = _alignment(views)
    return ChartReading(
        asset_code=asset_code,
        ticker=ticker,
        timeframes=views,
        primary_tf=primary,
        alignment=align,
        alignment_pct=align_pct,
        summary=align_text,
    )


def reading_to_dict(r: ChartReading) -> dict[str, Any]:
    out = asdict(r)
    out["timeframes"] = [asdict(v) if not isinstance(v, dict) else v for v in r.timeframes]
    return out


__all__ = [
    "TFView", "ChartReading",
    "read_chart", "reading_to_dict",
    "_TICKER_MAP", "_TF_PRESETS",
]
