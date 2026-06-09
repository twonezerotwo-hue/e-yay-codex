"""
FAZ 11 — Advanced Technical Context.

build_advanced_technical_context(pair, primary_tf) -> dict

Mevcut MTF cache'inden 5 ileri seviye teknik göstergeyi okur:
  volume_confirmation, ema_stack, market_structure,
  vwap_position, candle_close_confirmation

ve ek alanları (skor, vwap_value, tf-cross çelişkileri) audit-only dict
olarak döndürür. open_signal["advanced_technical"] içine yazılır.

Garantiler:
  • Sadece mevcut cache okunur — yeni network call yapılmaz.
  • Veri yoksa "unavailable" yazılır (uydurma yok).
  • Karar motoru, side, size, score değişmez.
PAPER_SAFE · NO_EXECUTION.
"""
from __future__ import annotations

from typing import Any


_UNAVAILABLE: dict[str, Any] = {
    "available":                 False,
    "primary_tf":                "",
    "volume_confirmation":       "unavailable",
    "ema_stack":                 "unavailable",
    "market_structure":          "unavailable",
    "vwap_position":             "unavailable",
    "vwap_value":                None,
    "candle_close_confirmation": "unavailable",
    "advanced_score":            0,
    "tf_view":                   {},
    "contradictions":            [],
}


def _read_mtf_cache() -> dict[str, dict[str, Any]]:
    """Mevcut MultiTimeframeTechnicalProvider cache'ini okur (yeni indirme yok)."""
    try:
        from app.providers import multi_tf_technical_provider as mtf  # noqa: PLC0415
        cache = getattr(mtf, "_MTF_CACHE", None)
        if cache is None:
            return {}
        return cache[1] if isinstance(cache, tuple) and len(cache) >= 2 else {}
    except Exception:  # noqa: BLE001
        return {}


def _insight_to_dict(insight: Any) -> dict[str, Any]:
    """TechnicalInsight dataclass'ından ilgili alanları çıkar."""
    return {
        "volume_confirmation":       getattr(insight, "volume_confirmation", "unavailable"),
        "volume_conf_score":         getattr(insight, "volume_conf_score", 0),
        "ema_stack":                 getattr(insight, "ema_stack", "unavailable"),
        "ema_alignment_score":       getattr(insight, "ema_alignment_score", 0),
        "market_structure":          getattr(insight, "market_structure_label", "unavailable"),
        "market_structure_score":    getattr(insight, "market_structure_score", 0),
        "vwap_position":             getattr(insight, "vwap_position", "unavailable"),
        "vwap_value":                getattr(insight, "vwap_value", None),
        "vwap_score":                getattr(insight, "vwap_score", 0),
        "candle_close_confirmation": getattr(insight, "candle_close_confirmation", "unavailable"),
        "candle_close_score":        getattr(insight, "candle_close_score", 0),
        "advanced_technical_score":  getattr(insight, "advanced_technical_score", 0),
    }


def _detect_contradictions(tf_view: dict[str, dict]) -> list[str]:
    """1H vs 4H EMA/structure uyumsuzluklarını yakalar."""
    out: list[str] = []
    one = tf_view.get("1h") or {}
    four = tf_view.get("4h") or {}
    day  = tf_view.get("1d") or {}

    # EMA yön çelişkisi
    ema_1h = one.get("ema_stack")
    ema_4h = four.get("ema_stack")
    if ema_1h and ema_4h and ema_1h in ("bullish", "bearish") and ema_4h in ("bullish", "bearish"):
        if ema_1h != ema_4h:
            out.append(f"EMA çelişkisi: 1h={ema_1h}, 4h={ema_4h}")

    # Structure çelişkisi
    ms_1h = one.get("market_structure")
    ms_4h = four.get("market_structure")
    if ms_1h == "HH_HL" and ms_4h == "LH_LL":
        out.append("Structure çelişkisi: 1h bullish, 4h bearish")
    if ms_1h == "LH_LL" and ms_4h == "HH_HL":
        out.append("Structure çelişkisi: 1h bearish, 4h bullish")

    # 1D'ye karşı 1H
    ema_1d = day.get("ema_stack")
    if ema_1h and ema_1d and ema_1h in ("bullish", "bearish") and ema_1d in ("bullish", "bearish"):
        if ema_1h != ema_1d:
            out.append(f"EMA çelişkisi: 1h={ema_1h}, 1d={ema_1d}")

    return out


def build_advanced_technical_context(pair: str, primary_tf: str = "") -> dict[str, Any]:
    """
    open_signal["advanced_technical"] içine yazılacak audit dict.

    Args:
        pair       : "BTCUSD" vb.
        primary_tf : "1h" / "4h" / "1d" — yoksa "1h" varsayılır.
    """
    cache = _read_mtf_cache()
    if not cache:
        return dict(_UNAVAILABLE)

    pair_data = cache.get(pair.upper()) or {}
    if not pair_data:
        return dict(_UNAVAILABLE)

    # Her TF için özet
    tf_view: dict[str, dict[str, Any]] = {}
    for tf_key, insight in pair_data.items():
        try:
            tf_view[tf_key] = _insight_to_dict(insight)
        except Exception:  # noqa: BLE001
            continue

    if not tf_view:
        return dict(_UNAVAILABLE)

    # Primary TF: ilk eşleşen, yoksa 1h, yoksa mevcut ilk TF
    ptf = primary_tf or "1h"
    if ptf not in tf_view:
        ptf = "1h" if "1h" in tf_view else next(iter(tf_view.keys()))

    primary = tf_view.get(ptf) or {}

    return {
        "available":                 True,
        "primary_tf":                ptf,
        "volume_confirmation":       primary.get("volume_confirmation", "unavailable"),
        "ema_stack":                 primary.get("ema_stack", "unavailable"),
        "market_structure":          primary.get("market_structure", "unavailable"),
        "vwap_position":             primary.get("vwap_position", "unavailable"),
        "vwap_value":                primary.get("vwap_value"),
        "candle_close_confirmation": primary.get("candle_close_confirmation", "unavailable"),
        "advanced_score":            primary.get("advanced_technical_score", 0),
        "tf_view":                   tf_view,
        "contradictions":            _detect_contradictions(tf_view),
    }
