"""
FAZ 7.5 — Auto Tune Override Reader.

Paper trading karar motoru için auto_tune_overrides.json'u okur
ve küçük pozisyon boyutu düzeltmeleri uygular.

Bu fazda sadece position_size_multiplier aktif uygulanır.
Diğerleri (stop_distance, entry_bars, news_confirmation, early_exit)
sadece audit/context olarak open_signal'a yazılır.

Güvenlik:
  - Override dosyası bozuksa/yoksa → sessizce yoksay (paper trading crash etmez)
  - Override side/direction değiştirmez
  - Override başlı başına trade açmaz
  - Açık pozisyonlara retroaktif etki yoktur
  - Tüm güvenlik alanları doğrulanır (PAPER_SAFE / NO_EXECUTION)
  - paper_trading_service buraya import edilmez (dairesel import yok)

Koşul eşleştirme:
  "LONG + pattern_bearish"  — LONG açılış + 1h yönü bearish/short/sell
  "SHORT + pattern_bullish" — SHORT açılış + 1h yönü bullish/long/buy
  Eşleşme yoksa → override uygulanmaz, context yazılır

open_signal'a yazılan auto_tune_context (uygulama başarılı):
  {available, applied=True, source, target, condition,
   old_size_pct, new_size_pct, multiplier,
   decision_permission, execution_mode, broker_permission, live_execution_allowed}

open_signal'a yazılan auto_tune_context (eşleşme yok):
  {available, applied=False, reason}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

_OVERRIDES_PATH: Path = (
    Path(__file__).resolve().parents[3] / "data" / "auto_tune_overrides.json"
)

# position_size_multiplier için izin verilen aralık
_PSM_MIN: float = 0.70
_PSM_MAX: float = 1.15

# 1h yön sınıflandırması
_BEARISH_DIR = frozenset({"bearish", "short", "sell"})
_BULLISH_DIR = frozenset({"bullish", "long", "buy"})

# Güvenlik alanları — context dict'e her zaman eklenir
_SECURITY_FIELDS: dict[str, Any] = {
    "decision_permission":    "NO_EXECUTION",
    "execution_mode":         "PAPER_SAFE",
    "broker_permission":      "BROKER_NOT_CONNECTED",
    "live_execution_allowed": False,
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def load_auto_tune_overrides() -> dict[str, Any]:
    """
    auto_tune_overrides.json dosyasını okur.

    Dosya yoksa veya herhangi bir hata oluşursa boş dict döner.
    Paper trading bu fonksiyon yüzünden crash etmez.
    """
    try:
        if not _OVERRIDES_PATH.exists():
            return {}
        with _OVERRIDES_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _validate_security_fields(overrides: dict[str, Any]) -> bool:
    """
    Override dosyasının dört güvenlik alanını doğrular.

    Herhangi biri yanlış veya eksikse False döner →
    apply_auto_tune_modifiers override uygulamaz.
    """
    return (
        overrides.get("decision_permission") == "NO_EXECUTION"
        and overrides.get("execution_mode") == "PAPER_SAFE"
        and overrides.get("broker_permission") == "BROKER_NOT_CONNECTED"
        and overrides.get("live_execution_allowed") is False
    )


def _get_pattern_bias(signal: dict[str, Any]) -> str:
    """
    Sinyalin 1h direction'ını küçük harfle döndürür.

    Önce tf_signals.1h.direction bakılır; bulunamazsa final_direction'a
    düşülür. Hiçbiri yoksa boş string döner.
    """
    tf_signals = signal.get("tf_signals") or {}
    one_h = tf_signals.get("1h") or {}
    direction = one_h.get("direction") or ""
    if direction:
        return direction.lower()
    fd = signal.get("final_direction") or ""
    return fd.lower()


def _match_condition(condition: str, signal: dict[str, Any], side: str) -> bool:
    """
    Override koşul string'ini sinyal + tarafla karşılaştırır.

    Desteklenen koşullar:
      "LONG + pattern_bearish"  — side=="LONG"  AND 1h bias bearish/short/sell
      "SHORT + pattern_bullish" — side=="SHORT" AND 1h bias bullish/long/buy

    Tanınmayan koşul → False.
    """
    cond = (condition or "").strip()
    pattern_bias = _get_pattern_bias(signal)

    if cond == "LONG + pattern_bearish":
        return side == "LONG" and pattern_bias in _BEARISH_DIR
    if cond == "SHORT + pattern_bullish":
        return side == "SHORT" and pattern_bias in _BULLISH_DIR
    return False


# ── Public API ────────────────────────────────────────────────────────────────

def build_auto_tune_context(
    pair: str,
    signal: dict[str, Any],
    side: str,
) -> dict[str, Any]:
    """
    pair için mevcut override context'ini döndürür (audit only).

    Bu fonksiyon hiçbir şey uygulamaz — sadece context dict üretir.
    Sonuç open_signal'a audit alanı olarak yazılabilir.
    """
    overrides = load_auto_tune_overrides()

    if not overrides:
        return {"available": False, "applied": False, "reason": "no_overrides"}

    if not _validate_security_fields(overrides):
        return {
            "available": False,
            "applied":   False,
            "reason":    "security_validation_failed",
        }

    overrides_map = overrides.get("overrides") or {}
    psm_map = overrides_map.get("position_size_multiplier") or {}

    for condition, multiplier in psm_map.items():
        if _match_condition(condition, signal, side):
            return {
                "available":  True,
                "applied":    False,   # context-only; gerçek uygulama apply_auto_tune_modifiers'da
                "source":     "auto_tune_overrides",
                "target":     "position_size_multiplier",
                "condition":  condition,
                "multiplier": float(multiplier),
                **_SECURITY_FIELDS,
            }

    return {"available": True, "applied": False, "reason": "no_matching_override"}


def apply_auto_tune_modifiers(
    signal: dict[str, Any],
    side: str,
    base_size_pct: float,
    risk_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Auto-tune override'larını sinyal üzerine uygular.

    Bu fazda sadece position_size_multiplier aktif olarak uygulanır.
    Diğer override türleri (stop_distance_multiplier, entry_confirmation_bars,
    require_news_confirmation, early_exit_threshold_pct) sadece gelecek
    fazlarda ele alınacak; şu an context/audit alanına bile yazılmaz.

    Override = küçük bir çarpan:
      - Side/direction değiştirmez.
      - Başlı başına trade açmaz.
      - Yalnızca açılış boyutunu (size_pct) küçük ölçüde değiştirir.
      - Açık pozisyonlara retroaktif etkisi yoktur.

    Hata veya eşleşme yoksa → base_size_pct değişmeden döner; paper trading crash etmez.

    Parameters:
        signal        — consensus sinyal snapshot'ı
        side          — "LONG" veya "SHORT"
        base_size_pct — mevcut size multiplier (learning/scoring çıktısı)
        risk_plan     — opsiyonel risk planı (ileride kullanılabilir)

    Returns:
        {
            "size_pct":          float,  # uygulanmış (veya orijinal) size çarpanı
            "auto_tune_context": dict,   # open_signal'a yazılır
        }
    """
    overrides = load_auto_tune_overrides()

    if not overrides:
        return {
            "size_pct":          base_size_pct,
            "auto_tune_context": {
                "available": False,
                "applied":   False,
                "reason":    "no_overrides",
            },
        }

    if not _validate_security_fields(overrides):
        return {
            "size_pct":          base_size_pct,
            "auto_tune_context": {
                "available": False,
                "applied":   False,
                "reason":    "security_validation_failed",
            },
        }

    overrides_map = overrides.get("overrides") or {}
    psm_map = overrides_map.get("position_size_multiplier") or {}

    for condition, multiplier in psm_map.items():
        if _match_condition(condition, signal, side):
            old_size_pct = float(base_size_pct)
            raw_new      = old_size_pct * float(multiplier)
            new_size_pct = round(max(_PSM_MIN, min(_PSM_MAX, raw_new)), 4)

            return {
                "size_pct": new_size_pct,
                "auto_tune_context": {
                    "available":    True,
                    "applied":      True,
                    "source":       "auto_tune_overrides",
                    "target":       "position_size_multiplier",
                    "condition":    condition,
                    "old_size_pct": old_size_pct,
                    "new_size_pct": new_size_pct,
                    "multiplier":   float(multiplier),
                    **_SECURITY_FIELDS,
                },
            }

    return {
        "size_pct":          base_size_pct,
        "auto_tune_context": {
            "available": True,
            "applied":   False,
            "reason":    "no_matching_override",
        },
    }
