"""
TechnicalProvider — OHLCV bazlı dinamik eşik hesaplama modülü.

Hedef varlıklar (yfinance OHLCV'ye sahip):
  BTC, XAU, XAG, XCU, BRENT, DXY, VIX, SP500, HYG,
  QQQ, IWM, LQD, SMH, XLF

Hesaplamalar:
  1. Wilder ATR(14)     — Ortalama Gerçek Aralık → volatilite ölçüsü
  2. Swing H/L tespiti  — Son 60 barda lokal zirve/dip → destek/direnç
  3. RSI(14)            — Momentum göstergesi
  4. MACD(12,26,9)      — Trend/momentum sinyali
  5. Piyasa yapısı      — HH/HL (BULLISH) vs LH/LL (BEARISH)
  6. Hacim oranı        — Mevcut hacim / 20-bar ortalaması

Çıktı: TechnicalInsight per asset — DynamicLevels + skor (0-100)
Cache : 3 dakika TTL (aynı süreçte) — _CACHE_TTL ile senkron
Execution: OFF / NO_EXECUTION / PAPER_SAFE
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Çıktı dataclass'ları
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DynamicLevels:
    """ATR + swing point bazlı dinamik destek/direnç seviyeleri."""
    support:     float   # Swing low (son N bar)
    resistance:  float   # Swing high (son N bar)
    atr:         float   # Wilder ATR(14) — mutlak volatilite
    stop_loss:   float   # support - 0.5 × ATR
    take_profit: float   # resistance + 0.5 × ATR
    atr_pct:     float   # ATR / current_price × 100 — göreli volatilite %


@dataclass(frozen=True)
class TechnicalInsight:
    """Tek bir varlık için teknik analiz özeti."""
    asset_code:     str
    timeframe:      str          # "1D" (şimdilik)
    current_price:  float

    # Piyasa yapısı
    structure:      str          # "BULLISH" | "BEARISH" | "NEUTRAL"

    # Dinamik seviyeler
    levels:         DynamicLevels

    # Momentum
    rsi_14:        float | None
    macd_signal:   str           # "BULLISH" | "BEARISH" | "NEUTRAL"

    # Hacim
    volume_ratio:  float | None  # mevcut hacim / 20-bar ortalama

    # Bileşik skor 0-100
    structure_score: int   # 0-25
    momentum_score:  int   # 0-25
    zone_score:      int   # 0-25 (fiyatın destek/direnç aralığındaki konumu)
    volume_score:    int   # 0-25
    technical_score: int   # 0-100 toplamı

    # ── İleri seviye teknik kontroller (FAZ 11) ─────────────────────────────
    # Defaults: "unavailable" / 0 → veri yetersizse downstream güvenli
    volume_confirmation:       str = "unavailable"  # positive | weak | warning | unavailable
    volume_conf_score:         int = 0              # 0-5

    ema_stack:                 str = "unavailable"  # bullish | bearish | mixed | unavailable
    ema_alignment_score:       int = 0              # 0-5

    market_structure_label:    str = "unavailable"  # HH_HL | LH_LL | MIXED | unavailable
    market_structure_score:    int = 0              # 0-5

    vwap_position:             str = "unavailable"  # above | below | at | unavailable
    vwap_score:                int = 0              # 0-5
    vwap_value:                float | None = None

    candle_close_confirmation: str = "unavailable"  # confirmed | fakeout | no_breakout | unavailable
    candle_close_score:        int = 0              # 0-5

    advanced_technical_score:  int = 0              # 0-25 (toplam ileri skor; technical_score'a karışmaz)


# ---------------------------------------------------------------------------
# OHLCV yapılandırması
# ---------------------------------------------------------------------------

#   ticker  : yfinance sembolü
#   period  : geçmiş veri uzunluğu
#   interval: çubuk aralığı
#   mult    : fiyat çarpanı (HG=F $/lb → $/tonne için 2204.623)

_OHLCV_ASSETS: dict[str, dict] = {
    "BTCUSD": {"ticker": "BTC-USD",   "period": "90d", "interval": "1d", "mult": 1.0},
    "XAUUSD": {"ticker": "GC=F",      "period": "90d", "interval": "1d", "mult": 1.0},
    "XAGUSD": {"ticker": "SI=F",      "period": "90d", "interval": "1d", "mult": 1.0},
    "XCUUSD": {"ticker": "HG=F",      "period": "90d", "interval": "1d", "mult": 2204.623},
    "BRENT":  {"ticker": "BZ=F",      "period": "90d", "interval": "1d", "mult": 1.0},
    "DXY":    {"ticker": "DX-Y.NYB",  "period": "90d", "interval": "1d", "mult": 1.0},
    "VIX":    {"ticker": "^VIX",      "period": "90d", "interval": "1d", "mult": 1.0},
    "SP500":  {"ticker": "^GSPC",     "period": "90d", "interval": "1d", "mult": 1.0},
    "HYG":    {"ticker": "HYG",       "period": "90d", "interval": "1d", "mult": 1.0},
    "QQQ":    {"ticker": "QQQ",       "period": "90d", "interval": "1d", "mult": 1.0},
    "IWM":    {"ticker": "IWM",       "period": "90d", "interval": "1d", "mult": 1.0},
    "LQD":    {"ticker": "LQD",       "period": "90d", "interval": "1d", "mult": 1.0},
    "SMH":    {"ticker": "SMH",       "period": "90d", "interval": "1d", "mult": 1.0},
    "XLF":    {"ticker": "XLF",       "period": "90d", "interval": "1d", "mult": 1.0},
}

# ---------------------------------------------------------------------------
# Asset bazlı fiyat aralıkları — yfinance / paralel indirme bazen yanlış
# ticker'a ait DataFrame iade edebiliyor (ör: BTC'ye XAG'ın bar'ları geliyor).
# Bu durumda current_price/support/resistance asset için olası aralık dışında
# kalır. _process_ticker çıkışında bu sanity guard çalışır ve yanlış mapping
# olan insight'ı discard eder (None döner). Böylece downstream (asset_signals,
# owner_actions, flip_conditions, paper trading) fallback sabit eşiği kullanır.
# ---------------------------------------------------------------------------
_ASSET_PRICE_BOUNDS: dict[str, tuple[float, float]] = {
    "BTCUSD": (10_000.0,   1_000_000.0),
    "XAUUSD": (1_000.0,    10_000.0),
    "XAGUSD": (5.0,        300.0),
    "XCUUSD": (2_000.0,    20_000.0),   # USD/MT — mult sonrası
    "BRENT":  (10.0,       250.0),
    "DXY":    (50.0,       200.0),
    "VIX":    (5.0,        150.0),
    "SP500":  (1_500.0,    10_000.0),
    "HYG":    (20.0,       200.0),
    "QQQ":    (100.0,      2_000.0),
    "IWM":    (50.0,       500.0),
    "LQD":    (50.0,       200.0),
    "SMH":    (50.0,       500.0),
    "XLF":    (15.0,       200.0),
}


def _is_insight_sane(asset_code: str, current_price: float, support: float, resistance: float) -> bool:
    """current_price + S/R hepsi asset'in olası aralığında mı?"""
    bounds = _ASSET_PRICE_BOUNDS.get(asset_code)
    if not bounds:
        return True
    lo, hi = bounds
    for label, v in (("current", current_price), ("support", support), ("resistance", resistance)):
        if not (lo <= v <= hi):
            logger.warning(
                "TechnicalProvider: %s %s=%.4f aralık dışı [%.0f, %.0f] — insight discard",
                asset_code, label, v, lo, hi,
            )
            return False
    return True

# ---------------------------------------------------------------------------
# Süreç-içi önbellek
# ---------------------------------------------------------------------------

_CACHE:    dict[str, TechnicalInsight] = {}
_CACHE_TS: float = 0.0
_CACHE_TTL = 180.0  # 3 dakika — yfinance soft limit (~2k/gün) ile uyumlu
                    # (480 çağrı/gün × 14 varlık paralel = makul)


# ---------------------------------------------------------------------------
# Matematiksel yardımcılar
# ---------------------------------------------------------------------------


def _wilder_atr(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> float:
    """
    Wilder smoothed ATR(period).
    Başlangıç: ilk `period` TR'nin SMA'sı.
    Sonraki : ATR = (ATR_prev × (period-1) + TR_curr) / period
    """
    n = len(high)
    if n < period + 2:
        # Yeterli veri yoksa basit aralığın ortalaması
        return float(np.mean(high[-min(period, n):] - low[-min(period, n):]))

    # True Range dizisi
    tr = np.empty(n - 1, dtype=float)
    for i in range(1, n):
        tr[i - 1] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # İlk ATR: SMA
    atr = float(np.mean(tr[:period]))

    # Wilder smoothing
    for i in range(period, len(tr)):
        atr = (atr * (period - 1) + tr[i]) / period

    return round(atr, 8)


def _find_swing_levels(
    high: np.ndarray,
    low: np.ndarray,
    lookback: int = 60,
    window: int = 5,
    current_price: float | None = None,
    atr: float | None = None,
) -> tuple[float, float]:
    """
    Son `lookback` barda lokal swing high/low noktalarını tespit eder.

    KIRILIM mantığı (klasik teknik prensip):
      • Eğer fiyat tespit edilen support'un ALTINA inmişse:
          - eski support artık DİRENÇ olur (rol değişimi)
          - yeni support = max(periyot dibi, fiyat − 1×ATR)
      • Eğer fiyat tespit edilen resistance'ın ÜSTÜNE çıkmışsa:
          - eski resistance artık DESTEK olur
          - yeni resistance = max(periyot tavanı, fiyat + 1×ATR)

    Böylece fiyat seviyeleri kırdığında destek/direnç otomatik güncellenir.

    window: Her iki yanda bakılacak bar sayısı.
    Döner: (support, resistance)
    """
    h = high[-lookback:]
    l = low[-lookback:]
    m = len(h)

    swing_highs: list[float] = []
    swing_lows:  list[float] = []

    for i in range(window, m - window):
        if h[i] >= np.max(h[max(0, i - window):i + window + 1]):
            swing_highs.append(float(h[i]))
        if l[i] <= np.min(l[max(0, i - window):i + window + 1]):
            swing_lows.append(float(l[i]))

    resistance = max(swing_highs) if swing_highs else float(np.max(h))
    support    = min(swing_lows)  if swing_lows  else float(np.min(l))

    if support >= resistance:
        support    = float(np.min(l))
        resistance = float(np.max(h))

    # ── KIRILIM tespiti — fiyat bilgisi verilmişse rolleri çevir ──────────────
    if current_price is not None:
        period_low  = float(np.min(l))
        period_high = float(np.max(h))
        atr_buf     = float(atr) if (atr is not None and atr > 0) else max(
            (period_high - period_low) * 0.02, current_price * 0.01
        )

        # Destek kırıldı → eski destek direnç olur, yeni destek aşağıda
        if current_price < support:
            new_resistance = support                                   # rol değişimi
            new_support    = min(period_low, current_price - atr_buf)  # fiyatın altı
            support, resistance = new_support, new_resistance

        # Direnç kırıldı → eski direnç destek olur, yeni direnç yukarıda
        elif current_price > resistance:
            new_support    = resistance                                # rol değişimi
            new_resistance = max(period_high, current_price + atr_buf) # fiyatın üstü
            support, resistance = new_support, new_resistance

        # Sağlık: support < current < resistance her zaman olsun
        if support >= current_price:
            support = current_price - atr_buf
        if resistance <= current_price:
            resistance = current_price + atr_buf

    return support, resistance


def _rsi(close: np.ndarray, period: int = 14) -> float | None:
    """Wilder smoothed RSI(period)."""
    n = len(close)
    if n < period + 2:
        return None

    deltas = np.diff(close)
    gains  = np.where(deltas > 0,  deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Üstel Hareketli Ortalama."""
    k = 2.0 / (period + 1)
    result = np.empty_like(data, dtype=float)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = data[i] * k + result[i - 1] * (1.0 - k)
    return result


def _macd_signal(close: np.ndarray) -> str:
    """
    MACD(12,26,9) → histogram pozisyonu + son kesişim.
    Döner: "BULLISH" | "BEARISH" | "NEUTRAL"
    """
    if len(close) < 35:
        return "NEUTRAL"

    macd_line   = _ema(close, 12) - _ema(close, 26)
    signal_line = _ema(macd_line, 9)
    hist        = macd_line - signal_line

    if len(hist) < 2:
        return "NEUTRAL"

    # Kesişim kontrolü (son iki bar)
    if hist[-2] < 0 and hist[-1] >= 0:
        return "BULLISH"
    if hist[-2] > 0 and hist[-1] <= 0:
        return "BEARISH"

    # Histogram konumu
    return "BULLISH" if hist[-1] > 0 else "BEARISH"


def _market_structure(
    high: np.ndarray, low: np.ndarray, close: np.ndarray
) -> str:
    """
    Swing noktalarına dayalı piyasa yapısı tespiti.
    HH + HL → BULLISH | LH + LL → BEARISH | diğer → NEUTRAL
    """
    n = len(high)
    if n < 20:
        return "NEUTRAL"

    lookback = min(60, n)
    h = high[-lookback:]
    l = low[-lookback:]
    window = 4

    sh_vals: list[float] = []
    sl_vals: list[float] = []

    for i in range(window, len(h) - window):
        if h[i] >= np.max(h[max(0, i - window):i + window + 1]):
            sh_vals.append(float(h[i]))
        if l[i] <= np.min(l[max(0, i - window):i + window + 1]):
            sl_vals.append(float(l[i]))

    if len(sh_vals) >= 2 and len(sl_vals) >= 2:
        hh = sh_vals[-1] > sh_vals[-2]  # Higher High
        hl = sl_vals[-1] > sl_vals[-2]  # Higher Low
        lh = sh_vals[-1] < sh_vals[-2]  # Lower High
        ll = sl_vals[-1] < sl_vals[-2]  # Lower Low

        if hh and hl:
            return "BULLISH"
        if lh and ll:
            return "BEARISH"
        # Expanding veya contracting range → NEUTRAL

    # Yedek: eğim + yüzde değişim
    pct = (close[-1] - close[-20]) / close[-20] * 100
    if pct > 4.0:
        return "BULLISH"
    if pct < -4.0:
        return "BEARISH"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Skorlama
# ---------------------------------------------------------------------------


def _score_structure(structure: str) -> int:
    return {"BULLISH": 25, "NEUTRAL": 12, "BEARISH": 0}[structure]


def _score_momentum(rsi: float | None, macd: str) -> int:
    """0-25 arası momentum skoru."""
    rsi_score = 12  # default
    if rsi is not None:
        if 55 <= rsi <= 75:
            rsi_score = 20
        elif 45 <= rsi < 55:
            rsi_score = 14
        elif 35 <= rsi < 45:
            rsi_score = 8
        elif rsi > 75:
            rsi_score = 15  # aşırı alım — düşür
        else:  # < 35 — aşırı satım
            rsi_score = 5

    macd_bonus = 5 if macd == "BULLISH" else (-3 if macd == "BEARISH" else 0)
    return max(0, min(25, rsi_score + macd_bonus))


def _score_zone(current: float, support: float, resistance: float) -> int:
    """
    Fiyatın destek-direnç aralığındaki konumu (0-25).
    Desteğe yakın = düşük skor (alım fırsatı) — ancak yön de önemli.
    Burada skor: fiyatın range ortasında olması nötr (12),
    desteği test ediyor ama kırmıyorsa = 20 (sıçrama beklentisi),
    direnci kırıyorsa = 23.
    """
    if resistance <= support:
        return 12

    rng = resistance - support
    ratio = (current - support) / rng  # 0 = destek, 1 = direnç

    # Yaklaşık direnç kırılımı — momentum
    if ratio > 0.90:
        return 23
    if 0.65 <= ratio <= 0.90:
        return 18   # direnç bölgesine yakın
    if 0.35 <= ratio < 0.65:
        return 12   # orta bölge
    if 0.10 <= ratio < 0.35:
        return 20   # destek bölgesine yakın (potansiyel sıçrama)
    # < 0.10 — desteğin altında
    return 4


def _score_volume(vol_ratio: float | None) -> int:
    """0-25 arası hacim skoru."""
    if vol_ratio is None:
        return 12
    if vol_ratio >= 2.0:
        return 25
    if vol_ratio >= 1.5:
        return 20
    if vol_ratio >= 1.0:
        return 15
    if vol_ratio >= 0.5:
        return 8
    return 3


# ---------------------------------------------------------------------------
# FAZ 11 — İleri seviye teknik kontroller (audit; technical_score değişmez)
# ---------------------------------------------------------------------------


def _ema_stack(close: np.ndarray) -> tuple[str, int]:
    """
    EMA20 > EMA50 > EMA200 → bullish
    EMA20 < EMA50 < EMA200 → bearish
    Diğer durumlar              → mixed
    Yetersiz veri (<200 bar)    → unavailable
    """
    if close is None or len(close) < 200:
        return ("unavailable", 0)
    try:
        e20  = float(_ema(close, 20)[-1])
        e50  = float(_ema(close, 50)[-1])
        e200 = float(_ema(close, 200)[-1])
    except Exception:  # noqa: BLE001
        return ("unavailable", 0)
    if e20 > e50 > e200:
        return ("bullish", 5)
    if e20 < e50 < e200:
        return ("bearish", 5)
    return ("mixed", 1)


def _market_structure_label(
    high: np.ndarray, low: np.ndarray
) -> tuple[str, int]:
    """
    Swing noktalarına göre yapı:
      HH + HL → "HH_HL"  (bullish)
      LH + LL → "LH_LL"  (bearish)
      diğer  → "MIXED"
    Yetersiz veri → "unavailable".
    """
    n = len(high)
    if n < 20:
        return ("unavailable", 0)
    lookback = min(60, n)
    h = high[-lookback:]
    l = low[-lookback:]
    window = 4
    sh: list[float] = []
    sl: list[float] = []
    for i in range(window, len(h) - window):
        if h[i] >= np.max(h[max(0, i - window):i + window + 1]):
            sh.append(float(h[i]))
        if l[i] <= np.min(l[max(0, i - window):i + window + 1]):
            sl.append(float(l[i]))
    if len(sh) < 2 or len(sl) < 2:
        return ("unavailable", 0)
    hh = sh[-1] > sh[-2]
    hl = sl[-1] > sl[-2]
    lh = sh[-1] < sh[-2]
    ll_ = sl[-1] < sl[-2]
    if hh and hl:
        return ("HH_HL", 5)
    if lh and ll_:
        return ("LH_LL", 5)
    return ("MIXED", 1)


def _vwap_position(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray | None,
    window: int = 20,
) -> tuple[str, int, float | None]:
    """
    Son `window` bardan rolling VWAP. Fiyat VWAP üstünde/altında/yakın:
      above | below | at | unavailable
    """
    if volume is None or len(volume) < 5 or len(close) < 5:
        return ("unavailable", 0, None)
    n = min(window, len(close), len(volume))
    h = high[-n:]
    l = low[-n:]
    c = close[-n:]
    v = volume[-n:]
    vol_sum = float(np.sum(v))
    if vol_sum <= 0:
        return ("unavailable", 0, None)
    tp = (h + l + c) / 3.0
    vwap_val = float(np.sum(tp * v) / vol_sum)
    cur = float(close[-1])
    if vwap_val <= 0:
        return ("unavailable", 0, None)
    if cur > vwap_val * 1.001:
        return ("above", 5, round(vwap_val, 4))
    if cur < vwap_val * 0.999:
        return ("below", 5, round(vwap_val, 4))
    return ("at", 2, round(vwap_val, 4))


def _volume_confirmation(
    close: np.ndarray, volume: np.ndarray | None
) -> tuple[str, int]:
    """
    Son bar hacmi 20-bar ortalamasına göre:
      ratio >= 1.5     → positive (güçlü)
      ratio >= 1.0     → positive
      büyük hareket + düşük hacim → warning (fakeout şüphesi)
      diğer            → weak
    Veri yoksa unavailable.
    """
    if volume is None or len(volume) < 21 or len(close) < 2:
        return ("unavailable", 0)
    avg20 = float(np.mean(volume[-21:-1]))
    if avg20 <= 0:
        return ("unavailable", 0)
    ratio = float(volume[-1]) / avg20
    move_pct = abs((close[-1] - close[-2]) / close[-2] * 100.0) if close[-2] != 0 else 0.0
    if ratio >= 1.5:
        return ("positive", 5)
    if ratio >= 1.0:
        return ("positive", 3)
    if move_pct > 1.0 and ratio < 0.7:
        return ("warning", 0)
    return ("weak", 1)


def _candle_close_confirmation(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    support: float,
    resistance: float,
) -> tuple[str, int]:
    """
    Son bar bir destek/direnç kırılımıyla close ile teyitlendi mi?
      confirmed   → close kırılım yönünde
      fakeout     → wick kırdı ama close geri döndü
      no_breakout → kırılım yok (normal bar)
    """
    if len(close) < 2:
        return ("unavailable", 0)
    cur_close  = float(close[-1])
    cur_high   = float(high[-1])
    cur_low    = float(low[-1])
    prev_close = float(close[-2])

    # Direnç kırılımı denemesi
    if cur_high > resistance > prev_close:
        if cur_close > resistance:
            return ("confirmed", 5)
        return ("fakeout", 0)

    # Destek kırılımı denemesi
    if cur_low < support < prev_close:
        if cur_close < support:
            return ("confirmed", 5)
        return ("fakeout", 0)

    return ("no_breakout", 2)


# ---------------------------------------------------------------------------
# Tek varlık işleme
# ---------------------------------------------------------------------------


def _process_ticker(
    asset_code: str, cfg: dict
) -> TechnicalInsight | None:
    """
    Bir varlık için yfinance'dan OHLCV çeker, teknik hesaplamalar yapar.
    Başarısızlık durumunda None döner — çağıran bunu yakalar.
    """
    import yfinance as yf  # geç import — sadece burada gerekli

    try:
        df = yf.download(
            cfg["ticker"],
            period=cfg["period"],
            interval=cfg["interval"],
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.warning("yfinance indirme hatası %s: %s", cfg["ticker"], exc)
        return None

    if df is None or df.empty or len(df) < 16:
        logger.debug("Yetersiz veri: %s (%d bar)", cfg["ticker"], len(df) if df is not None else 0)
        return None

    # MultiIndex sütun varsa düzleştir
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # Gerekli sütunları kontrol et
    required = {"High", "Low", "Close"}
    if not required.issubset(set(df.columns)):
        logger.debug("Eksik sütun %s: %s", cfg["ticker"], df.columns.tolist())
        return None

    mult = cfg.get("mult", 1.0)

    high  = df["High"].dropna().to_numpy(dtype=float)  * mult
    low   = df["Low"].dropna().to_numpy(dtype=float)   * mult
    close = df["Close"].dropna().to_numpy(dtype=float) * mult

    # Hacim (bazı futures'larda olmayabilir)
    vol: np.ndarray | None = None
    if "Volume" in df.columns:
        v = df["Volume"].dropna().to_numpy(dtype=float)
        if len(v) >= 20 and v[-1] > 0:
            vol = v

    # Yeterli bar mı?
    if len(close) < 16:
        return None

    current = float(close[-1])
    if current <= 0:
        return None

    # ── Teknik hesaplamalar ──────────────────────────────────────────────────

    atr       = _wilder_atr(high, low, close)
    support, resistance = _find_swing_levels(
        high, low,
        current_price=current,   # fiyat kırılan seviyeyi otomatik döndürsün
        atr=atr,
    )

    # Asset-specific sanity guard — yfinance bazen yanlış ticker'ı dönüyor;
    # bound dışı current/S/R varsa discard et (downstream fallback kullanır).
    if not _is_insight_sane(asset_code, current, support, resistance):
        return None

    rsi       = _rsi(close)
    macd      = _macd_signal(close)
    structure = _market_structure(high, low, close)

    # Hacim oranı
    vol_ratio: float | None = None
    if vol is not None and len(vol) >= 21:
        avg20 = float(np.mean(vol[-21:-1]))
        if avg20 > 0:
            vol_ratio = round(float(vol[-1]) / avg20, 2)

    # Dinamik seviyeler
    stop_loss   = round(support    - 0.5 * atr, 6)
    take_profit = round(resistance + 0.5 * atr, 6)
    atr_pct     = round(atr / current * 100, 2)

    levels = DynamicLevels(
        support=round(support, 4),
        resistance=round(resistance, 4),
        atr=round(atr, 4),
        stop_loss=stop_loss,
        take_profit=take_profit,
        atr_pct=atr_pct,
    )

    # ── Skorlama ────────────────────────────────────────────────────────────
    s_score = _score_structure(structure)
    m_score = _score_momentum(rsi, macd)
    z_score = _score_zone(current, support, resistance)
    v_score = _score_volume(vol_ratio)
    total   = s_score + m_score + z_score + v_score

    # ── FAZ 11 — İleri seviye teknik kontroller ──────────────────────────────
    ema_lbl,   ema_sc   = _ema_stack(close)
    ms_lbl,    ms_sc    = _market_structure_label(high, low)
    vwap_lbl,  vwap_sc, vwap_val = _vwap_position(high, low, close, vol)
    vc_lbl,    vc_sc    = _volume_confirmation(close, vol)
    cc_lbl,    cc_sc    = _candle_close_confirmation(high, low, close, support, resistance)
    adv_score           = ema_sc + ms_sc + vwap_sc + vc_sc + cc_sc

    return TechnicalInsight(
        asset_code    = asset_code,
        timeframe     = "1D",
        current_price = current,
        structure     = structure,
        levels        = levels,
        rsi_14        = rsi,
        macd_signal   = macd,
        volume_ratio  = vol_ratio,
        structure_score = s_score,
        momentum_score  = m_score,
        zone_score      = z_score,
        volume_score    = v_score,
        technical_score = total,
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


# ---------------------------------------------------------------------------
# Ana provider sınıfı
# ---------------------------------------------------------------------------


class TechnicalProvider:
    """
    Tüm yapılandırılmış varlıklar için OHLCV bazlı teknik analiz üretir.
    Önbellekleme: 3 dk TTL (yfinance soft-limit dostu).
    """

    def compute(
        self, max_workers: int = 1, force_refresh: bool = False
    ) -> dict[str, TechnicalInsight]:
        """
        Tüm desteklenen varlıklar için TechnicalInsight sözlüğü döner.
        Önbellek geçerliyse hızlı döner; değilse yfinance'dan paralel çeker.
        """
        global _CACHE, _CACHE_TS

        now = time.monotonic()
        if not force_refresh and _CACHE and (now - _CACHE_TS) < _CACHE_TTL:
            logger.debug("TechnicalProvider: önbellekten döndürüldü.")
            return dict(_CACHE)

        results: dict[str, TechnicalInsight] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_process_ticker, code, cfg): code
                for code, cfg in _OHLCV_ASSETS.items()
                if cfg is not None
            }
            for fut in as_completed(futures):
                code = futures[fut]
                try:
                    insight = fut.result()
                    if insight is not None:
                        results[code] = insight
                except Exception as exc:
                    logger.warning("TechnicalProvider %s hatası: %s", code, exc)

        _CACHE    = results
        _CACHE_TS = now
        logger.info(
            "TechnicalProvider: %d/%d varlık için teknik analiz tamamlandı.",
            len(results),
            len(_OHLCV_ASSETS),
        )
        return results

    def get_levels(self, asset_code: str) -> DynamicLevels | None:
        """Önbellekten tek bir varlığın DynamicLevels'ını döner."""
        insight = _CACHE.get(asset_code)
        return insight.levels if insight else None


__all__ = ["TechnicalProvider", "TechnicalInsight", "DynamicLevels"]
