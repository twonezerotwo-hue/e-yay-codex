"""
FAZ 3 — Agent Thesis Context Service.

Fonksiyonlar:
  load_latest_safe_thesis(limit)  -> dict | None
  build_thesis_trade_context(pair, thesis) -> dict

Amaç:
  Paper trading tick döngüsü pozisyon açarken son güvenli thesis'i okur ve
  open_signal içine audit context olarak yazar.

Güvenlik garantileri (her zaman zorlanır):
  • context_only = True
  • can_open_trade = False
  • Thesis paper trading'e emir vermez.
  • Thesis tek başına trade açtırmaz.
  • safe_for_context=False olan thesis'ler tamamen yok sayılır.
  • Karar motoru (consensus engine) değişmez.
  • Risk gate final kapı olarak kalır.

Kısıtlar:
  • Bu modül paper_trading_service.py'yi import etmez.
  • Bu modül herhangi bir endpoint'i import etmez.
  • Snapshot üretmez, kaydetmez; sadece okur.
  • Mock / fake veri kullanmaz.
"""
from __future__ import annotations

from typing import Any

from app.storage.agent_thesis_store import load_recent_agent_theses


# ── Public API ─────────────────────────────────────────────────────────────────

def load_latest_safe_thesis(limit: int = 24) -> dict[str, Any] | None:
    """
    agent_hourly_theses.jsonl'den son `limit` thesis'i okur.
    thesis_sanity.safe_for_context == True olan en son thesis'i döndürür.
    Hiçbiri uygun değilse None döner (paper trading context yok sayar).

    Hata durumunda (dosya yok, bozuk satır vb.) None döner — trade bloke etmez.
    """
    try:
        theses = load_recent_agent_theses(limit=limit)
    except Exception:  # noqa: BLE001
        return None

    for thesis in reversed(theses):
        sanity = thesis.get("thesis_sanity") or {}
        if sanity.get("safe_for_context") is True:
            return thesis

    return None


def build_thesis_trade_context(pair: str, thesis: dict[str, Any] | None) -> dict[str, Any]:
    """
    Pair + thesis'ten open_signal'a yazılacak audit context dict'i üretir.

    • thesis None ise: available=False, reason="no_safe_thesis"
    • pair asset_bias içindeyse: pair-specific bias + contradictions
    • pair asset_bias içinde değilse: global market_view özeti

    Her iki durumda da:
      context_only = True  (her zaman)
      can_open_trade = False  (her zaman)
    """
    if thesis is None:
        return {
            "available":      False,
            "reason":         "no_safe_thesis",
            "context_only":   True,
            "can_open_trade": False,
        }

    asset_bias  = thesis.get("asset_bias") or {}
    market_view = thesis.get("market_view") or {}
    sanity      = thesis.get("thesis_sanity") or {}

    base: dict[str, Any] = {
        "available":      True,
        "thesis_id":      thesis.get("thesis_id"),
        "created_at":     thesis.get("created_at"),
        "context_only":   True,
        "can_open_trade": False,
        "sanity_score":   sanity.get("score"),
        "sanity_status":  sanity.get("status"),
    }

    if pair in asset_bias:
        pair_data = asset_bias[pair]
        return {
            **base,
            "source":        "pair_specific",
            "pair":          pair,
            "bias":          pair_data.get("bias"),
            "reason":        pair_data.get("reason"),
            "contradictions": pair_data.get("contradictions") or [],
        }

    # Global fallback
    return {
        **base,
        "source":               "global_market_view",
        "pair":                 pair,
        "primary_bias":         market_view.get("primary_bias"),
        "regime_view":          market_view.get("regime_view"),
        "risk_appetite_view":   market_view.get("risk_appetite_view"),
    }
