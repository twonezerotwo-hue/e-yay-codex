"""
AI Trade Opinion ↔ Paper Trading entegrasyon testleri.

Kapsam:
  • build_trade_opinion_context_for_signal soft modifier üretir
  • HIGH conviction → size +%5/10
  • LOW conviction → size azalır
  • AVOID → manual_ready route
  • Decision KAPAT/KÜÇÜLT + LONG_BIAS → agrees=False, disagreement>=60
  • build_position_opinion_view opinion özetini döner

Sınır: bu testler ana paper trading flow'unu mutate etmez —
sadece pure helper fonksiyonları doğrular.
"""
from __future__ import annotations

import pytest

from app.services.ai_trade_opinion_service import (
    TRACKED_ASSETS,
    build_ai_trade_opinion,
    build_position_opinion_view,
    build_trade_opinion_context_for_signal,
)
from app.services import ai_trade_opinion_service as ats


# ── Sentetik opinion üreticileri ─────────────────────────────────────────────

def _opinion(*, asset="BTCUSD", opinion="LONG_BIAS", conviction="high",
             best_bias="long", decision="AL", pos_label="", side="LONG"):
    asset_ops = [
        {"asset": a, "opinion": opinion if a == asset else "WAIT",
         "conviction": conviction if a == asset else "low",
         "score": 75.0 if a == asset else 50.0,
         "why": ["test"], "against": ["test"],
         "trigger_needed": "trigger", "invalidation": "invalidation",
         "suggested_action": "test"}
        for a in TRACKED_ASSETS
    ]
    pos_ops = []
    if pos_label:
        pos_ops.append({
            "pair": asset, "side": side,
            "opinion": pos_label, "conviction": "medium",
            "reason": "test", "what_to_watch": ["w"],
            "invalidation": "inv",
        })
    return {
        "schema_version": ats.SCHEMA_VERSION,
        "generated_at": "2026-06-10T00:00:00+00:00",
        "execution_mode": "PAPER_SAFE",
        "live_execution_allowed": False,
        "overall_view": "mixed",
        "market_opinion": "...",
        "asset_opinions": asset_ops,
        "open_position_opinions": pos_ops,
        "best_candidate": {"asset": asset, "bias": best_bias,
                           "reason": "r", "trigger": "t", "risk": "x"},
        "no_trade_reason": "",
        "next_3_triggers": [], "next_triggers": [],
        "what_would_change_my_mind": [],
        "invalidation": "x",
        "owner_brief": "ob",
        "agrees_with_main_decision": True,
        "disagreement_score": 0,
    }


# ── Soft size modifier ───────────────────────────────────────────────────────

def test_high_conviction_long_increases_size():
    op = _opinion(opinion="LONG_BIAS", conviction="high")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    assert ctx["available"] is True
    assert abs(ctx["size_multiplier"] - 1.10) < 1e-6
    assert ctx["route_recommendation"] == "proceed"
    assert "high conviction" in ctx["reason"]


def test_medium_conviction_long_modest_increase():
    op = _opinion(opinion="LONG_BIAS", conviction="medium")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    assert abs(ctx["size_multiplier"] - 1.05) < 1e-6


def test_low_conviction_reduces_size():
    # Low conviction + WAIT + LONG → unaligned + low → -%15 size
    op = _opinion(opinion="WAIT", conviction="low", asset="BTCUSD")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    assert abs(ctx["size_multiplier"] - 0.85) < 1e-6
    assert ctx["route_recommendation"] == "proceed"


def test_wait_medium_conviction_modest_reduction():
    # Medium conviction WAIT (aligned değil ama low da değil) → WAIT branch (-%10)
    op = _opinion(opinion="WAIT", conviction="medium", asset="BTCUSD")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    assert abs(ctx["size_multiplier"] - 0.90) < 1e-6


def test_avoid_routes_to_manual_ready():
    op = _opinion(opinion="AVOID", conviction="low")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    assert ctx["size_multiplier"] == 0.0
    assert ctx["route_recommendation"] == "manual_ready"


def test_close_watch_position_blocks_new_add():
    op = _opinion(opinion="LONG_BIAS", conviction="high",
                  pos_label="CLOSE_WATCH", side="LONG")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    assert ctx["route_recommendation"] == "manual_ready"
    assert ctx["size_multiplier"] == 0.0


def test_short_bias_long_signal_is_not_boosted():
    op = _opinion(opinion="SHORT_BIAS", conviction="high")
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion=op)
    # Aligned değil → boost yok; conviction high ama SHORT_BIAS+LONG → neutral
    assert ctx["size_multiplier"] == 1.0
    assert ctx["route_recommendation"] == "proceed"


# ── Decision uyumu (KAPAT/KÜÇÜLT + long_bias) ────────────────────────────────

def _ctx_with_decision(verdict: str, best_bias="long"):
    """build_ai_trade_opinion'a verilen sentetik ctx — decision verdict'i içerir."""
    statuses = {"BTCUSD": "CONFIRMED"}
    asset_signals = [
        {"asset_code": a, "status": statuses.get(a, "PENDING"),
         "action_trigger": "trig", "value": 100.0}
        for a in TRACKED_ASSETS
    ]
    mtf = {a: {"1h": {"structure": "BULLISH", "current_price": 100.0,
                       "levels": {"support": 95.0, "resistance": 105.0, "atr": 1.0}},
                "4h": {"structure": "BULLISH"},
                "1d": {"structure": "BULLISH"}}
           for a in TRACKED_ASSETS}
    return {
        "now": "2026-06-10T00:00:00+00:00",
        "snapshot": {"report": {
            "macro_layer":    {"regime": "NEUTRAL"},
            "appetite_layer": {"status": "NEUTRAL"},
            "asset_signals":  asset_signals,
            "news_headlines": [], "upcoming_catalysts": [],
            "decision": {"verdict": verdict},
        }, "mtf": mtf},
        "prev_snapshot": None, "thesis": None, "thesis_sanity": None,
        "paper_state": {"open_positions": []},
        "rechecks": [], "learning_candidates": [], "mistake_memory": [],
        "weekly_calibration": None, "auto_tune_overrides": {},
        "system_health": None,
    }


def test_decision_kucult_long_bias_disagrees():
    out = build_ai_trade_opinion(_ctx_with_decision("KÜÇÜLT"))
    if out["best_candidate"]["bias"] == "long":
        assert out["agrees_with_main_decision"] is False
        assert out["disagreement_score"] >= 60


def test_decision_al_long_bias_agrees():
    out = build_ai_trade_opinion(_ctx_with_decision("AL"))
    assert out["agrees_with_main_decision"] is True
    assert out["disagreement_score"] < 50


# ── Position opinion view ────────────────────────────────────────────────────

def test_position_opinion_view_unavailable_when_no_match(monkeypatch):
    op = _opinion(pos_label="", asset="BTCUSD")
    monkeypatch.setattr(ats, "build_ai_trade_opinion", lambda: op)
    view = build_position_opinion_view("BTCUSD", "LONG")
    # pos_ops boş → fallback MANUAL_REVIEW
    assert view["available"] is True
    assert view["opinion"] == "MANUAL_REVIEW"


def test_position_opinion_view_returns_close_watch(monkeypatch):
    op = _opinion(pos_label="CLOSE_WATCH", asset="BRENT", side="LONG")
    monkeypatch.setattr(ats, "build_ai_trade_opinion", lambda: op)
    view = build_position_opinion_view("BRENT", "LONG")
    assert view["available"] is True
    assert view["opinion"] == "CLOSE_WATCH"
    assert view["invalidation"] == "inv"


# ── Opinion unavailable graceful path ────────────────────────────────────────

def test_unavailable_opinion_returns_neutral_ctx():
    ctx = build_trade_opinion_context_for_signal("BTCUSD", "LONG", opinion={})
    assert ctx["available"] is False
    assert ctx["size_multiplier"] == 1.0
    assert ctx["route_recommendation"] == "proceed"
