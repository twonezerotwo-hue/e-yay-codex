"""
GET /api/v1/chart-patterns         → 4 parite × 3 TF chart pattern özeti
GET /api/v1/chart-patterns/{pair}  → tek parite detay

Bağımsız çalışır — consensus/regime pipeline'ından etkilenmez.
Kendi 3 dk cache'i var (yfinance soft limit).

PAPER_SAFE / NO_EXECUTION — sadece bilgi.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

import numpy as np
from fastapi import APIRouter, HTTPException

from app.providers.chart_pattern_provider import (
    ChartPatternInsight,
    analyze_chart_patterns,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chart-patterns", tags=["chart-patterns"])

# Hangi parite + ticker?
_PAIRS: dict[str, str] = {
    "BTCUSD": "BTC-USD",
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "BRENT":  "BZ=F",
}

# Hangi timeframe'ler?
_TIMEFRAMES: dict[str, dict] = {
    "1h": {"period": "30d", "interval": "1h", "aggregate": None},
    "4h": {"period": "60d", "interval": "1h", "aggregate": 4},
    "1d": {"period": "90d", "interval": "1d", "aggregate": None},
}

# Bağımsız cache
_CACHE: tuple[float, dict] | None = None
_CACHE_TTL = 180   # 3 dk


def _aggregate_ohlcv(
    o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, factor: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """N bar'ı tek bar'a topla."""
    n = len(c)
    if factor <= 1 or n < factor:
        return o, h, l, c
    full = n // factor
    trimmed = full * factor
    o2 = o[-trimmed:].reshape(full, factor)[:, 0]
    h2 = h[-trimmed:].reshape(full, factor).max(axis=1)
    l2 = l[-trimmed:].reshape(full, factor).min(axis=1)
    c2 = c[-trimmed:].reshape(full, factor)[:, -1]
    return o2, h2, l2, c2


def _fetch_ohlcv(ticker: str, period: str, interval: str
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """yfinance'tan OHLCV çek."""
    try:
        import yfinance as yf
        df = yf.download(ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        if df is None or df.empty or len(df) < 30:
            return None
        if hasattr(df.columns, "levels"):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
            return None
        o = df["Open"].dropna().to_numpy(dtype=float)
        h = df["High"].dropna().to_numpy(dtype=float)
        l = df["Low"].dropna().to_numpy(dtype=float)
        c = df["Close"].dropna().to_numpy(dtype=float)
        # Sürelerin eşit olduğundan emin ol
        n = min(len(o), len(h), len(l), len(c))
        return o[-n:], h[-n:], l[-n:], c[-n:]
    except Exception as exc:
        logger.warning("Chart pattern fetch %s [%s] hatası: %s", ticker, interval, exc)
        return None


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Basit ATR — yeterli."""
    if len(close) < period + 1:
        return 0.0
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(np.abs(high[1:] - close[:-1]),
                               np.abs(low[1:] - close[:-1])))
    return float(np.mean(tr[-period:]))


def _swing_sr(close: np.ndarray, lookback: int = 30) -> tuple[float, float]:
    """Son N bar swing high/low → basit destek/direnç."""
    recent = close[-lookback:]
    return float(recent.min()), float(recent.max())


def _analyze_pair_tf(pair: str, ticker: str, tf: str, cfg: dict
                     ) -> tuple[str, str, ChartPatternInsight | None]:
    """Tek pair × tf için fetch + analyze."""
    fetched = _fetch_ohlcv(ticker, cfg["period"], cfg["interval"])
    if fetched is None:
        return pair, tf, None
    o, h, l, c = fetched
    agg = cfg.get("aggregate")
    if agg:
        o, h, l, c = _aggregate_ohlcv(o, h, l, c, agg)
    if len(c) < 30:
        return pair, tf, None
    support, resistance = _swing_sr(c, lookback=30)
    atr = _atr(h, l, c)
    insight = analyze_chart_patterns(
        pair, tf, o, h, l, c,
        support=support, resistance=resistance, atr=atr,
    )
    return pair, tf, insight


def _insight_to_dict(ins: ChartPatternInsight | None) -> dict | None:
    if ins is None:
        return None
    d = asdict(ins)
    # tuple → list (JSON serializable)
    d["patterns"] = [asdict(p) for p in ins.patterns]
    return d


def _build_all_patterns() -> dict:
    """4 pair × 3 TF — toplam 12 analiz. Paralel fetch."""
    results: dict[str, dict[str, dict | None]] = {p: {} for p in _PAIRS}

    tasks = [
        (pair, ticker, tf, cfg)
        for pair, ticker in _PAIRS.items()
        for tf, cfg in _TIMEFRAMES.items()
    ]

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [
            ex.submit(_analyze_pair_tf, pair, ticker, tf, cfg)
            for pair, ticker, tf, cfg in tasks
        ]
        for fut in as_completed(futures):
            try:
                pair, tf, insight = fut.result(timeout=20)
                results[pair][tf] = _insight_to_dict(insight)
            except Exception as exc:
                logger.warning("Chart pattern task hatası: %s", exc)

    # Her pair için consolidated skor (TF-ağırlıklı: 1h 30%, 4h 40%, 1d 30%)
    weights = {"1h": 0.30, "4h": 0.40, "1d": 0.30}
    summary = {}
    for pair, tf_dict in results.items():
        weighted = 0.0
        weight_total = 0.0
        active_patterns = []
        for tf, d in tf_dict.items():
            if d is None:
                continue
            weighted += d["pattern_score"] * weights[tf]
            weight_total += weights[tf]
            for p in d["patterns"]:
                active_patterns.append(f"{tf}: {p['name']} ({p['bias']})")
        consolidated = round(weighted / weight_total, 1) if weight_total > 0 else 0.0
        if consolidated >= 25.0:
            bias = "BULLISH"
        elif consolidated <= -25.0:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        summary[pair] = {
            "consolidated_score": consolidated,
            "score_range": "signed_neg100_pos100",  # consensus 0..100 ile karıştırma uyarısı
            "bias_thresholds": {"bullish_at": 25.0, "bearish_at": -25.0},
            "bias": bias,
            "active_patterns": active_patterns,
            "per_tf": tf_dict,
        }
    return summary


@router.get("")
def list_chart_patterns() -> dict:
    """4 parite × 3 TF chart pattern analizi."""
    global _CACHE
    now = time.monotonic()
    if _CACHE and (now - _CACHE[0]) < _CACHE_TTL:
        return _CACHE[1]

    try:
        summary = _build_all_patterns()
        response = {
            "status": "ok",
            "execution_mode": "INFO_ONLY / NO_EXECUTION",
            "cache_ttl_seconds": _CACHE_TTL,
            "pairs": summary,
        }
        _CACHE = (now, response)
        return response
    except Exception as exc:
        logger.exception("chart-patterns endpoint hatası")
        return {"status": "stale", "error": str(exc)[:200], "pairs": {}}


@router.get("/{pair}")
def get_chart_pattern(pair: str) -> dict:
    """Tek parite × 3 TF detayı."""
    pair_upper = pair.upper()
    if pair_upper not in _PAIRS:
        raise HTTPException(status_code=400,
                            detail=f"Bilinmeyen parite: {pair_upper}. Geçerli: {list(_PAIRS)}")

    # Toplu cache'ten çek
    all_data = list_chart_patterns()
    pair_data = all_data.get("pairs", {}).get(pair_upper)
    if pair_data is None:
        raise HTTPException(status_code=503, detail=f"{pair_upper} verisi henüz hazır değil")
    return {
        "status": "ok",
        "execution_mode": "INFO_ONLY / NO_EXECUTION",
        "pair": pair_upper,
        "data": pair_data,
    }


__all__ = [name for name in globals() if not name.startswith("_")]
