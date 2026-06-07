"""
Asset Parameter Profile
─────────────────────────────────────────────────────────────────────────────

Varlık bazlı teknik parametreler. BTC ≠ XAU ≠ XAG ≠ XCU ≠ BRENT — her birinin
volatilite rejimi, mum yapısı, RSI bantları, ATR çarpanları farklıdır.

Bu modül salt **konfigürasyon kaynağı**dır — kendisi bir hesaplama yapmaz.
Mevcut kod tabanında sabit kalan değerlerin yerine aşağıdaki profil okunur.

NOT: Profili tüketenler default fallback'i `get("default")` ile almalıdır,
böylece yeni bir asset eklendiğinde sistem patlamaz.
"""
from __future__ import annotations

from typing import TypedDict


class AssetParams(TypedDict, total=False):
    # RSI bantları — aşırı alım/satım eşikleri
    rsi_overbought:   float
    rsi_oversold:     float
    # ATR çarpanları — SL = X×ATR, TP = Y×ATR
    sl_atr_mult:      float
    tp_atr_mult:      float
    # Pattern kalite minimumu (chart_pattern_provider strength filter)
    min_pattern_strength: float
    # Confluence için: kaç TF aynı yönde olmalı
    min_confluence_tfs: int
    # Beklenen tutuş aralığı (saat)
    horizon_hours_low:  int
    horizon_hours_high: int
    # Pattern confirmation: pattern bardan sonra kaç bar teyit istensin
    confirmation_bars:  int


# Her varlık için kalibrasyon. Default profil "default" anahtarındadır.
# Değerler için kısa gerekçe yorumlar:
ASSET_PROFILES: dict[str, AssetParams] = {

    # ── Default — yeni varlıklar için fallback ─────────────────────────────
    # Konservatif, hiçbir varlığa özel değil.
    "default": {
        "rsi_overbought":       70.0,
        "rsi_oversold":         30.0,
        "sl_atr_mult":          2.0,
        "tp_atr_mult":          3.0,
        "min_pattern_strength": 50.0,
        "min_confluence_tfs":   2,
        "horizon_hours_low":    48,
        "horizon_hours_high":   144,
        "confirmation_bars":    1,
    },

    # ── BTCUSD — 7/24 piyasa, yüksek volatilite ─────────────────────────────
    # RSI bantları daha geniş (60/40 yerine 75/25), zira BTC'de uzun süre
    # extreme zone'da kalabilir. ATR çarpanı sıkı (1.5×) — geniş whipsaw
    # zararını azalt.
    "BTCUSD": {
        "rsi_overbought":       75.0,
        "rsi_oversold":         25.0,
        "sl_atr_mult":          1.5,
        "tp_atr_mult":          2.5,
        "min_pattern_strength": 55.0,
        "min_confluence_tfs":   2,
        "horizon_hours_low":    24,
        "horizon_hours_high":   96,
        "confirmation_bars":    1,
    },

    # ── XAUUSD — Altın, Asya/Londra session belirleyici, gap riski ─────────
    # RSI klasik 70/30, ama gap için ATR çarpanı daha geniş (2.5×).
    "XAUUSD": {
        "rsi_overbought":       70.0,
        "rsi_oversold":         30.0,
        "sl_atr_mult":          2.5,
        "tp_atr_mult":          3.5,
        "min_pattern_strength": 50.0,
        "min_confluence_tfs":   2,
        "horizon_hours_low":    48,
        "horizon_hours_high":   144,
        "confirmation_bars":    1,
    },

    # ── XAGUSD — Gümüş, XAU'dan daha yüksek beta (~3×) ──────────────────────
    # Geniş RSI bantları, sıkı SL — gümüş hızlı reverse eder.
    "XAGUSD": {
        "rsi_overbought":       72.0,
        "rsi_oversold":         28.0,
        "sl_atr_mult":          2.0,
        "tp_atr_mult":          3.5,
        "min_pattern_strength": 55.0,
        "min_confluence_tfs":   2,
        "horizon_hours_low":    36,
        "horizon_hours_high":   120,
        "confirmation_bars":    2,
    },

    # ── XCUUSD — Bakır, makro/Çin verisine duyarlı, görece düşük günlük vol ──
    # Klasik RSI, pattern strength biraz daha sıkı.
    "XCUUSD": {
        "rsi_overbought":       70.0,
        "rsi_oversold":         30.0,
        "sl_atr_mult":          2.5,
        "tp_atr_mult":          3.0,
        "min_pattern_strength": 55.0,
        "min_confluence_tfs":   2,
        "horizon_hours_low":    72,
        "horizon_hours_high":   168,
        "confirmation_bars":    2,
    },

    # ── BRENT — Petrol, OPEC/jeopolitik gap, futures kontrat değişimi ───────
    # En yüksek confirmation_bars (2) — fake breakout sık.
    "BRENT": {
        "rsi_overbought":       72.0,
        "rsi_oversold":         28.0,
        "sl_atr_mult":          2.5,
        "tp_atr_mult":          3.5,
        "min_pattern_strength": 55.0,
        "min_confluence_tfs":   2,
        "horizon_hours_low":    48,
        "horizon_hours_high":   144,
        "confirmation_bars":    2,
    },
}


def get_profile(asset_code: str) -> AssetParams:
    """
    Varlık koduna göre profili döndür. Bulunamazsa default profili döner.

    Hiçbir koşulda KeyError fırlatmaz — sistemin yeni bir asset karşısında
    çökmesini önlemek için sözleşme.
    """
    if not isinstance(asset_code, str):
        return dict(ASSET_PROFILES["default"])     # type: ignore[return-value]
    code = asset_code.upper().strip()
    profile = ASSET_PROFILES.get(code) or ASSET_PROFILES["default"]
    # Default ile birleştir — eksik alanlar fallback'ten doldurulsun
    merged: AssetParams = {**ASSET_PROFILES["default"], **profile}    # type: ignore[misc]
    return merged


def get_param(asset_code: str, key: str, fallback: float | int | None = None):
    """Tek parametre okuma kısayolu, fallback değer destekli."""
    profile = get_profile(asset_code)
    value = profile.get(key)    # type: ignore[call-overload]
    if value is None:
        return fallback
    return value


def list_assets() -> list[str]:
    """Profil tanımlı varlıkların listesi (default hariç)."""
    return [k for k in ASSET_PROFILES if k != "default"]


__all__ = [
    "AssetParams",
    "ASSET_PROFILES",
    "get_profile",
    "get_param",
    "list_assets",
]
