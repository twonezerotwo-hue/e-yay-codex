"""
Multi-Timeframe TechnicalProvider — E-YAY × Aegis.

Mevcut TechnicalProvider'ın 1D'sini 3 zaman dilimine genişletir:
  • 1h  — gün-içi swing (yfinance 1h native, 60g geçmiş)
  • 4h  — 1h bar'ından agregat (yfinance 4h vermez, biz toplarız)
  • 1d  — mevcut günlük (90g geçmiş)

Cache: 3 dakika TTL (yfinance soft IP limit ile uyumlu).
PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from app.providers.technical_provider import (
    TechnicalInsight,
    DynamicLevels,
    _wilder_atr,
    _find_swing_levels,
    _rsi,
    _macd_signal,
    _market_structure,
    _score_structure,
    _score_momentum,
    _score_zone,
    _score_volume,
    _is_insight_sane,
    # FAZ 11 — ileri seviye teknik kontroller
    _ema_stack,
    _market_structure_label,
    _vwap_position,
    _volume_confirmation,
    _candle_close_confirmation,
)

logger = logging.getLogger(__name__)

# ── Timeframe konfigürasyonu ─────────────────────────────────────────────────
# (asset_ticker, period, interval, mult, aggregate_factor)
# aggregate_factor None → ham veri kullan
# aggregate_factor N    → her N bar'ı tek bar'a topla (OHLCV agg)

TIMEFRAMES: dict[str, dict] = {
    "1h": {"period": "60d",  "interval": "1h", "aggregate": None},
    "4h": {"period": "60d",  "interval": "1h", "aggregate": 4},     # 1h → 4h agg
    "1d": {"period": "90d",  "interval": "1d", "aggregate": None},
}

# Hangi varlıklar için multi-TF çekilecek?
MTF_ASSETS: dict[str, dict] = {
    "BTCUSD":  {"ticker": "BTC-USD", "mult": 1.0},
    "XAUUSD":  {"ticker": "GC=F",    "mult": 1.0},
    "XAGUSD":  {"ticker": "SI=F",    "mult": 1.0},
    "XCUUSD":  {"ticker": "HG=F",    "mult": 2204.623},  # USD/lb → USD/MT
    "BRENT":   {"ticker": "BZ=F",    "mult": 1.0},
}

# Cache — (now, {asset_code: {tf: TechnicalInsight}})
_MTF_CACHE: tuple[float, dict[str, dict[str, TechnicalInsight]]] | None = None
_MTF_CACHE_TTL = 180  # 3 dk


# ─────────────────────────────────────────────────────────────────────────────
# OHLCV agregat — 1H bardan 4H bar üret
# ─────────────────────────────────────────────────────────────────────────────

def _aggregate_ohlcv(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    volume: np.ndarray | None, factor: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """N bar'ı tek bar'a topla. Open=ilk, High=max, Low=min, Close=son, Vol=sum."""
    n = len(close)
    if n == 0 or factor <= 1:
        return high, low, close, volume

    # Tam dolmayan son grubu at — sadece tam N'lik gruplar
    full_groups = n // factor
    if full_groups == 0:
        return high, low, close, volume

    trimmed = full_groups * factor
    h = high[-trimmed:].reshape(full_groups, factor)
    l = low[-trimmed:].reshape(full_groups, factor)
    c = close[-trimmed:].reshape(full_groups, factor)

    agg_high  = h.max(axis=1)
    agg_low   = l.min(axis=1)
    agg_close = c[:, -1]

    agg_vol: np.ndarray | None = None
    if volume is not None and len(volume) >= trimmed:
        v = volume[-trimmed:].reshape(full_groups, factor)
        agg_vol = v.sum(axis=1)

    return agg_high, agg_low, agg_close, agg_vol


# ─────────────────────────────────────────────────────────────────────────────
# Tek varlık + tek TF için technical insight hesapla
# ─────────────────────────────────────────────────────────────────────────────

def _compute_one(
    asset_code: str, ticker_cfg: dict, tf: str, tf_cfg: dict
) -> TechnicalInsight | None:
    """yfinance'tan veri çek, aggregate yap (4H için), TechnicalInsight üret."""
    import yfinance as yf

    try:
        df = yf.download(
            ticker_cfg["ticker"],
            period=tf_cfg["period"],
            interval=tf_cfg["interval"],
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.warning("yfinance %s [%s] hatası: %s", ticker_cfg["ticker"], tf, exc)
        return None

    if df is None or df.empty:
        return None
    if len(df) < 20:
        return None

    # MultiIndex sütun düzleştir
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    required = {"High", "Low", "Close"}
    if not required.issubset(set(df.columns)):
        return None

    mult = ticker_cfg.get("mult", 1.0)
    high  = df["High"].dropna().to_numpy(dtype=float)  * mult
    low   = df["Low"].dropna().to_numpy(dtype=float)   * mult
    close = df["Close"].dropna().to_numpy(dtype=float) * mult

    volume: np.ndarray | None = None
    if "Volume" in df.columns:
        v = df["Volume"].dropna().to_numpy(dtype=float)
        if len(v) >= 20 and v[-1] > 0:
            volume = v

    # ── 4H için agregat yap ──
    agg_factor = tf_cfg.get("aggregate")
    if agg_factor:
        high, low, close, volume = _aggregate_ohlcv(high, low, close, volume, agg_factor)

    if len(close) < 16:
        return None

    current = float(close[-1])
    if current <= 0:
        return None

    # ── Aynı teknik hesaplamalar ─
    atr       = _wilder_atr(high, low, close)
    support, resistance = _find_swing_levels(
        high, low,
        current_price=current,
        atr=atr,
    )

    # Asset-specific sanity guard — yfinance asset-asset kontaminasyonunu engelle
    if not _is_insight_sane(asset_code, current, support, resistance):
        return None

    rsi       = _rsi(close)
    macd      = _macd_signal(close)
    structure = _market_structure(high, low, close)

    # Hacim oranı
    vol_ratio: float | None = None
    if volume is not None and len(volume) >= 21:
        avg20 = float(np.mean(volume[-21:-1]))
        if avg20 > 0:
            vol_ratio = round(float(volume[-1]) / avg20, 2)

    # Dinamik seviyeler
    stop_loss   = round(support    - 0.5 * atr, 6)
    take_profit = round(resistance + 0.5 * atr, 6)
    atr_pct     = round(atr / current * 100, 2) if current > 0 else 0.0

    levels = DynamicLevels(
        support=round(support, 4),
        resistance=round(resistance, 4),
        atr=round(atr, 4),
        stop_loss=stop_loss,
        take_profit=take_profit,
        atr_pct=atr_pct,
    )

    # ── Skorlama (aynı algoritma) ─
    s_score = _score_structure(structure)
    m_score = _score_momentum(rsi, macd)
    z_score = _score_zone(current, support, resistance)
    v_score = _score_volume(vol_ratio)
    total   = s_score + m_score + z_score + v_score

    # ── FAZ 11 — İleri seviye teknik kontroller ──────────────────────────────
    ema_lbl,  ema_sc  = _ema_stack(close)
    ms_lbl,   ms_sc   = _market_structure_label(high, low)
    vwap_lbl, vwap_sc, vwap_val = _vwap_position(high, low, close, volume)
    vc_lbl,   vc_sc   = _volume_confirmation(close, volume)
    cc_lbl,   cc_sc   = _candle_close_confirmation(high, low, close, support, resistance)
    adv_score         = ema_sc + ms_sc + vwap_sc + vc_sc + cc_sc

    return TechnicalInsight(
        asset_code=asset_code,
        timeframe=tf,
        current_price=round(current, 4),
        structure=structure,
        levels=levels,
        rsi_14=rsi,
        macd_signal=macd,
        volume_ratio=vol_ratio,
        structure_score=s_score,
        momentum_score=m_score,
        zone_score=z_score,
        volume_score=v_score,
        technical_score=total,
        # ── İleri seviye
        volume_confirmation       = vc_lbl,
        volume_conf_score         = vc_sc,
        ema_stack                 = ema_lbl,
        ema_alignment_score       = ema_sc,
        market_structure_label    = ms_lbl,
        market_structure_score    = ms_sc,
        vwap_position             = vwap_lbl,
        vwap_score                = vwap_sc,
        vwap_value                = vwap_val,
        candle_close_confirmation = cc_lbl,
        candle_close_score        = cc_sc,
        advanced_technical_score  = adv_score,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public — multi-TF compute
# ─────────────────────────────────────────────────────────────────────────────

class MultiTimeframeTechnicalProvider:
    """4 parite × 3 timeframe = 12 TechnicalInsight üretir."""

    def compute(
        self,
        max_workers: int = 1,
        force_refresh: bool = False,
    ) -> dict[str, dict[str, TechnicalInsight]]:
        """Tüm asset × tf kombinasyonları için technical insight üret.

        Dönüş: {"BTCUSD": {"1h": insight, "4h": insight, "1d": insight}, ...}
        """
        global _MTF_CACHE
        now = time.monotonic()
        if not force_refresh and _MTF_CACHE and (now - _MTF_CACHE[0]) < _MTF_CACHE_TTL:
            return _MTF_CACHE[1]

        results: dict[str, dict[str, TechnicalInsight]] = {}

        # 4H için 1H verisi paylaşılabilir — ama basitlik için ayrı çek
        jobs = [
            (asset, ticker_cfg, tf, tf_cfg)
            for asset, ticker_cfg in MTF_ASSETS.items()
            for tf, tf_cfg in TIMEFRAMES.items()
        ]

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_compute_one, asset, ticker_cfg, tf, tf_cfg): (asset, tf)
                for asset, ticker_cfg, tf, tf_cfg in jobs
            }
            for fut in as_completed(futures):
                asset, tf = futures[fut]
                try:
                    insight = fut.result()
                    if insight is not None:
                        results.setdefault(asset, {})[tf] = insight
                except Exception as exc:
                    logger.warning("MTF %s/%s hatası: %s", asset, tf, exc)

        _MTF_CACHE = (now, results)
        logger.info(
            "MultiTimeframeTechnicalProvider: %d asset / %d insight üretildi",
            len(results), sum(len(v) for v in results.values()),
        )
        return results


__all__ = ["MultiTimeframeTechnicalProvider", "TIMEFRAMES", "MTF_ASSETS"]
