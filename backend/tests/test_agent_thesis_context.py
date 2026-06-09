"""
FAZ 3 — Agent Thesis Context testleri.

Kapsam:
  load_latest_safe_thesis  : boş store, hepsi unsafe, en son safe, karışık liste
  build_thesis_trade_context : None thesis, pair-specific, global, context_only, can_open_trade
  paper_trading integration  : _route_new_open_signal → open_signal["agent_thesis_context"]
                               orijinal sinyal alanları (side/final_score/vb.) korunur
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.agent_thesis_context import (
    build_thesis_trade_context,
    load_latest_safe_thesis,
)


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _thesis(
    thesis_id: str = "t1",
    safe_for_context: bool = True,
    pair: str | None = None,
    pair_bias: str = "cautious_long",
    primary_bias: str = "mixed",
) -> dict:
    """Minimal thesis dict üretir."""
    t: dict = {
        "thesis_id":           thesis_id,
        "created_at":          "2026-06-09T00:00:00+00:00",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "source_snapshot_ids": ["snap1"],
        "market_view": {
            "primary_bias":       primary_bias,
            "regime_view":        "TRANSITIONING",
            "risk_appetite_view": "MODERATE",
        },
        "asset_bias": {},
        "paper_trading_context": {"permission": "context_only", "can_open_trade": False},
        "thesis_sanity": {
            "status":           "pass" if safe_for_context else "fail",
            "score":            100 if safe_for_context else 0,
            "issues":           [],
            "safe_for_context": safe_for_context,
        },
    }
    if pair is not None:
        t["asset_bias"][pair] = {
            "bias":            pair_bias,
            "reason":          f"{pair} sinyali aktif",
            "contradictions":  [],
            "mtf_structures":  {"1h": "BULLISH", "4h": "BULLISH"},
        }
    return t


# ── load_latest_safe_thesis ───────────────────────────────────────────────────

def test_load_latest_safe_returns_none_when_store_empty(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: [],
    )
    assert load_latest_safe_thesis() is None


def test_load_latest_safe_returns_none_when_all_unsafe(monkeypatch):
    unsafe = [_thesis("t1", safe_for_context=False), _thesis("t2", safe_for_context=False)]
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: unsafe,
    )
    assert load_latest_safe_thesis() is None


def test_load_latest_safe_returns_single_safe(monkeypatch):
    safe = _thesis("t1", safe_for_context=True)
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: [safe],
    )
    result = load_latest_safe_thesis()
    assert result is not None
    assert result["thesis_id"] == "t1"


def test_load_latest_safe_returns_most_recent_safe(monkeypatch):
    """Listede birden fazla safe thesis varsa sonuncusu (en yeni) döner."""
    theses = [_thesis("old", safe_for_context=True), _thesis("new", safe_for_context=True)]
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: theses,
    )
    result = load_latest_safe_thesis()
    assert result is not None
    assert result["thesis_id"] == "new"


def test_load_latest_safe_skips_unsafe_at_end_returns_prior_safe(monkeypatch):
    """En son thesis unsafe ise, ondan önceki safe olan döner."""
    theses = [
        _thesis("safe_old", safe_for_context=True),
        _thesis("unsafe_new", safe_for_context=False),
    ]
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: theses,
    )
    result = load_latest_safe_thesis()
    assert result is not None
    assert result["thesis_id"] == "safe_old"


def test_xagusd_critical_sanity_excluded(monkeypatch):
    """safe_for_context=False olan thesis (örn. XAGUSD critical) yok sayılır."""
    xagusd_fail = _thesis("xag_fail", safe_for_context=False, pair="XAGUSD", pair_bias="cautious_long")
    # sanity'de critical issue simülasyonu
    xagusd_fail["thesis_sanity"]["issues"] = [{
        "severity": "critical",
        "code":     "long_bias_against_all_bearish_mtf",
        "asset":    "XAGUSD",
        "message":  "cautious_long ama tüm MTF bearish",
    }]
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: [xagusd_fail],
    )
    assert load_latest_safe_thesis() is None


def test_load_latest_safe_tolerates_store_exception(monkeypatch):
    """load_recent_agent_theses istisna atarsa None döner — trade bloke etmez."""
    def _raise(limit=24):
        raise OSError("disk error")

    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        _raise,
    )
    assert load_latest_safe_thesis() is None


# ── build_thesis_trade_context ────────────────────────────────────────────────

def test_build_context_no_thesis_available_false():
    ctx = build_thesis_trade_context("BTCUSD", None)
    assert ctx["available"] is False


def test_build_context_no_thesis_reason_no_safe_thesis():
    ctx = build_thesis_trade_context("BTCUSD", None)
    assert ctx["reason"] == "no_safe_thesis"


def test_build_context_always_context_only_true_when_no_thesis():
    ctx = build_thesis_trade_context("BTCUSD", None)
    assert ctx["context_only"] is True


def test_build_context_always_can_open_trade_false_when_no_thesis():
    ctx = build_thesis_trade_context("BTCUSD", None)
    assert ctx["can_open_trade"] is False


def test_build_context_pair_specific_when_pair_in_asset_bias():
    t = _thesis(pair="BTCUSD", pair_bias="cautious_long")
    ctx = build_thesis_trade_context("BTCUSD", t)
    assert ctx["source"] == "pair_specific"


def test_build_context_pair_specific_includes_bias():
    t = _thesis(pair="BTCUSD", pair_bias="avoid")
    ctx = build_thesis_trade_context("BTCUSD", t)
    assert ctx["bias"] == "avoid"


def test_build_context_pair_specific_includes_pair():
    t = _thesis(pair="XAGUSD", pair_bias="watch")
    ctx = build_thesis_trade_context("XAGUSD", t)
    assert ctx["pair"] == "XAGUSD"


def test_build_context_global_when_pair_not_in_asset_bias():
    t = _thesis(pair="XAGUSD")  # only XAGUSD in asset_bias
    ctx = build_thesis_trade_context("EURUSD", t)  # EURUSD not present
    assert ctx["source"] == "global_market_view"


def test_build_context_global_includes_primary_bias():
    t = _thesis(pair="XAGUSD", primary_bias="risk_off")
    ctx = build_thesis_trade_context("EURUSD", t)
    assert ctx["primary_bias"] == "risk_off"


def test_build_context_always_context_only_true_with_thesis():
    t = _thesis(pair="BTCUSD")
    for pair in ("BTCUSD", "EURUSD"):
        ctx = build_thesis_trade_context(pair, t)
        assert ctx["context_only"] is True


def test_build_context_always_can_open_trade_false_with_thesis():
    t = _thesis(pair="BTCUSD")
    for pair in ("BTCUSD", "EURUSD"):
        ctx = build_thesis_trade_context(pair, t)
        assert ctx["can_open_trade"] is False


def test_build_context_includes_thesis_id():
    t = _thesis(thesis_id="unique-abc", pair="BTCUSD")
    ctx = build_thesis_trade_context("BTCUSD", t)
    assert ctx["thesis_id"] == "unique-abc"


def test_build_context_includes_sanity_score():
    t = _thesis(safe_for_context=True)
    t["thesis_sanity"]["score"] = 85
    ctx = build_thesis_trade_context("EURUSD", t)
    assert ctx["sanity_score"] == 85


# ── Paper trading integration ─────────────────────────────────────────────────

def test_open_signal_gets_agent_thesis_context(monkeypatch):
    """_route_new_open_signal open_signal'a agent_thesis_context ekler."""
    from app.services.paper_trading_service import (  # noqa: PLC0415
        TradingState,
        _route_new_open_signal,
    )

    safe = _thesis("t_live", safe_for_context=True, pair="BTCUSD")
    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: [safe],
    )

    st = TradingState()
    _route_new_open_signal(
        st,
        pair="BTCUSD",
        side="LONG",
        price=61_000.0,
        size_usd=100.0,
        last_signal="LONG",
        signal_snapshot={"primary_tf": "1h", "final_score": 0.7, "final_direction": "LONG"},
        fingerprint="fp1",
        now_dt=datetime.now(UTC),
        atr_value=100.0,
        primary_tf="1h",
        is_recurring=False,
        raw_regime="NEUTRAL",
    )

    assert "BTCUSD" in st.pending_orders
    enriched = st.pending_orders["BTCUSD"].open_signal
    assert "agent_thesis_context" in enriched
    ctx = enriched["agent_thesis_context"]
    assert ctx["context_only"] is True
    assert ctx["can_open_trade"] is False


def test_original_signal_fields_unchanged_after_enrichment(monkeypatch):
    """agent_thesis_context enjeksiyonu side/final_score/final_direction'ı değiştirmez."""
    from app.services.paper_trading_service import (  # noqa: PLC0415
        TradingState,
        _route_new_open_signal,
    )

    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: [],
    )

    st = TradingState()
    original_signal = {
        "primary_tf":      "4h",
        "final_score":     0.82,
        "final_direction": "SHORT",
        "confluence":      {"count": 3},
    }
    _route_new_open_signal(
        st,
        pair="EURUSD",
        side="SHORT",
        price=1.08,
        size_usd=200.0,
        last_signal="SHORT",
        signal_snapshot=original_signal,
        fingerprint="fp2",
        now_dt=datetime.now(UTC),
        atr_value=0.002,
        primary_tf="4h",
        is_recurring=False,
        raw_regime="NEUTRAL",
    )

    assert "EURUSD" in st.pending_orders
    enriched = st.pending_orders["EURUSD"].open_signal
    # Orijinal alanlar korunmuş olmalı
    assert enriched["primary_tf"] == "4h"
    assert enriched["final_score"] == 0.82
    assert enriched["final_direction"] == "SHORT"
    assert enriched["confluence"] == {"count": 3}
    # Yeni alan eklenmiş
    assert "agent_thesis_context" in enriched


def test_open_signal_context_available_false_when_no_safe_thesis(monkeypatch):
    """Güvenli thesis yoksa context available=False olarak yazılır."""
    from app.services.paper_trading_service import (  # noqa: PLC0415
        TradingState,
        _route_new_open_signal,
    )

    monkeypatch.setattr(
        "app.services.agent_thesis_context.load_recent_agent_theses",
        lambda limit=24: [],
    )

    st = TradingState()
    _route_new_open_signal(
        st,
        pair="XAUUSD",
        side="LONG",
        price=2300.0,
        size_usd=100.0,
        last_signal="LONG",
        signal_snapshot={"primary_tf": "1h"},
        fingerprint="fp3",
        now_dt=datetime.now(UTC),
        atr_value=5.0,
        primary_tf="1h",
        is_recurring=False,
        raw_regime="NEUTRAL",
    )

    assert "XAUUSD" in st.pending_orders
    ctx = st.pending_orders["XAUUSD"].open_signal.get("agent_thesis_context", {})
    assert ctx.get("available") is False
    assert ctx.get("can_open_trade") is False
