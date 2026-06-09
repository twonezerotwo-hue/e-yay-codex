"""
FAZ 11 — Advanced Technical kontrol testleri.

Kapsam:
  1. _ema_stack bullish/bearish/mixed/unavailable
  2. _market_structure_label HH/HL bullish, LH/LL bearish
  3. _vwap_position above/below/unavailable
  4. _volume_confirmation positive/weak/warning
  5. _candle_close_confirmation confirmed/fakeout
  6. build_advanced_technical_context — cache yokken unavailable
  7. open_signal içine advanced_technical enjeksiyonu (paper_trading_service)
  8. thesis_sanity advanced_technical çelişki yakalar
  9. position_recheck advanced_technical warning üretir
  10. learning_candidate yeni label'lar oluşturur
"""
from __future__ import annotations

import numpy as np
import pytest

from app.providers.technical_provider import (
    _ema_stack,
    _market_structure_label,
    _vwap_position,
    _volume_confirmation,
    _candle_close_confirmation,
)


# ── 1) EMA stack ────────────────────────────────────────────────────────────

def test_ema_stack_bullish():
    # 300 bar artan close → EMA20 > EMA50 > EMA200
    close = np.linspace(100.0, 200.0, 300)
    label, score = _ema_stack(close)
    assert label == "bullish"
    assert score == 5


def test_ema_stack_bearish():
    close = np.linspace(200.0, 100.0, 300)
    label, score = _ema_stack(close)
    assert label == "bearish"
    assert score == 5


def test_ema_stack_unavailable_when_insufficient():
    close = np.linspace(100.0, 110.0, 50)  # <200 bar
    label, score = _ema_stack(close)
    assert label == "unavailable"
    assert score == 0


# ── 2) Market structure ─────────────────────────────────────────────────────

def test_market_structure_bullish_hh_hl():
    """Sin-dalga gibi: trendde net swing high/low'lar ve ikincisi daha yüksek."""
    # 60 bar — iki net tepe + iki net dip, ikinciler artan
    x = np.linspace(0, 4 * np.pi, 60)
    base = np.sin(x) * 3.0 + np.linspace(0.0, 4.0, 60)  # genel artan trend
    high = base + 2.0
    low  = base - 2.0
    label, score = _market_structure_label(high, low)
    assert label == "HH_HL", f"got {label}"
    assert score == 5


def test_market_structure_bearish_lh_ll():
    x = np.linspace(0, 4 * np.pi, 60)
    base = np.sin(x) * 3.0 + np.linspace(4.0, 0.0, 60)  # genel azalan trend
    high = base + 2.0
    low  = base - 2.0
    label, score = _market_structure_label(high, low)
    assert label == "LH_LL", f"got {label}"
    assert score == 5


def test_market_structure_unavailable_when_short():
    high = np.array([1.0, 2.0, 3.0])
    low  = np.array([0.5, 1.5, 2.5])
    label, score = _market_structure_label(high, low)
    assert label == "unavailable"


# ── 3) VWAP ─────────────────────────────────────────────────────────────────

def test_vwap_above_when_price_above_avg():
    # 20 bar düşük fiyat + son bar yüksek → fiyat VWAP üstünde
    close = np.array([100.0] * 20 + [120.0])
    high  = close + 1.0
    low   = close - 1.0
    vol   = np.array([1000.0] * 21)
    label, score, val = _vwap_position(high, low, close, vol)
    assert label == "above"
    assert score == 5
    assert val is not None and val < 120.0


def test_vwap_unavailable_when_no_volume():
    close = np.linspace(100.0, 110.0, 30)
    high  = close + 1.0
    low   = close - 1.0
    label, score, val = _vwap_position(high, low, close, None)
    assert label == "unavailable"
    assert score == 0
    assert val is None


# ── 4) Volume confirmation ──────────────────────────────────────────────────

def test_volume_confirmation_positive_when_high_volume():
    close = np.array([100.0] * 21)
    vol   = np.array([1000.0] * 20 + [2000.0])  # son bar 2x ortalama
    label, score = _volume_confirmation(close, vol)
    assert label == "positive"
    assert score == 5


def test_volume_confirmation_warning_low_volume_big_move():
    close = np.array([100.0] * 20 + [102.0])  # +2% hareket
    vol   = np.array([1000.0] * 20 + [500.0])  # düşük hacim
    label, score = _volume_confirmation(close, vol)
    assert label == "warning"
    assert score == 0


def test_volume_confirmation_unavailable_when_no_volume():
    label, score = _volume_confirmation(np.array([100.0, 101.0]), None)
    assert label == "unavailable"


# ── 5) Candle close confirmation ────────────────────────────────────────────

def test_candle_close_confirmed_resistance_breakout():
    # prev_close=100 < resistance=105 < cur_high=110, cur_close=108 (üstünde)
    high  = np.array([102.0, 110.0])
    low   = np.array([99.0, 104.0])
    close = np.array([100.0, 108.0])
    label, score = _candle_close_confirmation(high, low, close, support=95.0, resistance=105.0)
    assert label == "confirmed"
    assert score == 5


def test_candle_close_fakeout_wick_no_close():
    # wick kırdı (cur_high>105) ama cur_close<105 → fakeout
    high  = np.array([102.0, 110.0])
    low   = np.array([99.0,  100.0])
    close = np.array([100.0, 103.0])  # 105 altında kapanış
    label, score = _candle_close_confirmation(high, low, close, support=95.0, resistance=105.0)
    assert label == "fakeout"
    assert score == 0


def test_candle_close_no_breakout():
    high  = np.array([102.0, 104.0])
    low   = np.array([99.0, 101.0])
    close = np.array([100.0, 103.0])
    label, score = _candle_close_confirmation(high, low, close, support=95.0, resistance=105.0)
    assert label == "no_breakout"


# ── 6) build_advanced_technical_context cache yokken ───────────────────────

def test_advanced_context_unavailable_when_no_cache(monkeypatch):
    from app.services import advanced_technical_context as ctx_mod
    monkeypatch.setattr(ctx_mod, "_read_mtf_cache", lambda: {})
    ctx = ctx_mod.build_advanced_technical_context("BTCUSD", "1h")
    assert ctx["available"] is False
    assert ctx["ema_stack"] == "unavailable"
    assert ctx["contradictions"] == []


def test_advanced_context_reads_cache(monkeypatch):
    """Cache'te BTCUSD/1h insight varsa available=True."""
    from app.services import advanced_technical_context as ctx_mod

    class FakeInsight:
        volume_confirmation       = "positive"
        volume_conf_score         = 5
        ema_stack                 = "bullish"
        ema_alignment_score       = 5
        market_structure_label    = "HH_HL"
        market_structure_score    = 5
        vwap_position             = "above"
        vwap_value                = 100.5
        vwap_score                = 5
        candle_close_confirmation = "confirmed"
        candle_close_score        = 5
        advanced_technical_score  = 25

    class FakeBear(FakeInsight):
        ema_stack = "bearish"
        market_structure_label = "LH_LL"

    monkeypatch.setattr(
        ctx_mod, "_read_mtf_cache",
        lambda: {"BTCUSD": {"1h": FakeInsight(), "4h": FakeBear()}},
    )
    ctx = ctx_mod.build_advanced_technical_context("BTCUSD", "1h")
    assert ctx["available"] is True
    assert ctx["ema_stack"] == "bullish"
    assert ctx["primary_tf"] == "1h"
    # 1h bullish vs 4h bearish → çelişki
    assert any("EMA" in c or "Structure" in c for c in ctx["contradictions"])


# ── 7) paper_trading open_signal'a advanced_technical enjekte ──────────────

def test_open_signal_gets_advanced_technical(monkeypatch):
    import app.services.paper_trading_service as pts
    import app.services.agent_thesis_context as atc

    # thesis stub
    monkeypatch.setattr(atc, "load_latest_safe_thesis", lambda: None)
    monkeypatch.setattr(atc, "build_thesis_trade_context", lambda pair, thesis: {})

    # advanced stub
    monkeypatch.setattr(
        "app.services.advanced_technical_context.build_advanced_technical_context",
        lambda pair, primary_tf: {
            "available": True,
            "primary_tf": primary_tf or "1h",
            "ema_stack": "bullish",
            "market_structure": "HH_HL",
            "volume_confirmation": "positive",
            "vwap_position": "above",
            "candle_close_confirmation": "confirmed",
            "advanced_score": 25,
            "tf_view": {},
            "contradictions": [],
            "vwap_value": 100.0,
        },
    )

    captured: list[dict] = []
    monkeypatch.setattr(pts, "_queue_pending_open",
        lambda st, **kw: captured.append(kw["signal_snapshot"]))

    from app.services.paper_trading_service import TradingState
    from datetime import datetime, UTC
    st = TradingState.__new__(TradingState)
    st.pending_orders = {}
    st.manual_ready_trades = {}

    pts._route_new_open_signal(
        st, pair="BTCUSD", side="LONG", price=100.0, size_usd=500.0,
        last_signal="LONG@0.8",
        signal_snapshot={"primary_tf": "1h"},
        fingerprint="fp1", now_dt=datetime.now(UTC), atr_value=1.0,
        primary_tf="1h", is_recurring=False, raw_regime="NEUTRAL",
    )

    assert len(captured) == 1
    snap = captured[0]
    assert "advanced_technical" in snap
    adv = snap["advanced_technical"]
    assert adv["available"] is True
    assert adv["ema_stack"] == "bullish"


# ── 8) thesis_sanity advanced bias çelişkisi ────────────────────────────────

def test_thesis_sanity_advanced_long_bias_vs_bearish_ema():
    from app.services.agent_thesis_sanity import validate_agent_thesis
    thesis = {
        "source_snapshot_ids": ["s1"],
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_SAFE",
        "asset_bias": {
            "BTCUSD": {
                "bias": "cautious_long",
                "advanced_technical": {
                    "ema_stack": "bearish",
                    "market_structure": "LH_LL",
                    "volume_confirmation": "positive",
                    "candle_close_confirmation": "confirmed",
                },
            },
        },
    }
    out = validate_agent_thesis(thesis)
    codes = {i["code"] for i in out["issues"]}
    assert "long_bias_against_ema_and_structure" in codes
    assert out["status"] == "fail"  # critical issue


def test_thesis_sanity_fakeout_warning():
    from app.services.agent_thesis_sanity import validate_agent_thesis
    thesis = {
        "source_snapshot_ids": ["s1"],
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_SAFE",
        "asset_bias": {
            "BTCUSD": {
                "bias": "neutral",
                "advanced_technical": {
                    "ema_stack": "bullish",
                    "market_structure": "HH_HL",
                    "volume_confirmation": "positive",
                    "candle_close_confirmation": "fakeout",
                },
            },
        },
    }
    out = validate_agent_thesis(thesis)
    codes = {i["code"] for i in out["issues"]}
    assert "breakout_candle_close_failed" in codes


# ── 9) position_recheck advanced warnings ────────────────────────────────────

def test_position_recheck_emits_ema_flip_warning():
    from app.services.position_recheck_service import build_position_recheck

    position = {
        "pair": "BTCUSD",
        "side": "LONG",
        "entry_price": 100.0,
        "current_price": 95.0,
        "pnl_pct": -5.0,
        "open_signal": {
            "primary_tf": "1h",
            "advanced_technical": {
                "available": True,
                "ema_stack": "bullish",
                "market_structure": "HH_HL",
                "volume_confirmation": "positive",
                "candle_close_confirmation": "confirmed",
                "vwap_position": "above",
            },
        },
    }
    snapshot = {
        "snapshot_id": "snap1",
        "mtf": {"BTCUSD": {"1h": {"structure": "BEARISH"}}},
        "report": {"asset_signals": [], "macro_layer": {}, "appetite_layer": {}},
    }
    out = build_position_recheck(position, snapshot, None)
    codes = {c["code"] for c in out["checks"]}
    assert "ema_stack_flipped" in codes


# ── 10) learning_candidate yeni label'lar ───────────────────────────────────

def test_learning_candidate_emits_low_volume_breakout(monkeypatch):
    """Açılışta vol_confirmation=weak + pnl<0 → low_volume_breakout label."""
    from app.services.learning_candidate_service import build_learning_candidate

    position = {
        "pair": "BTCUSD",
        "side": "LONG",
        "entry_price": 100.0,
        "current_price": 95.0,
        "pnl_pct": -5.0,
        "open_signal": {
            "primary_tf": "1h",
            "tf_signals": {"1h": {"direction": "long"}},
            "advanced_technical": {
                "available": True,
                "ema_stack": "bearish",
                "market_structure": "LH_LL",
                "volume_confirmation": "weak",
                "candle_close_confirmation": "fakeout",
                "vwap_position": "below",
            },
        },
    }
    out = build_learning_candidate(position, None, None, None)
    codes = {l["code"] for l in (out.get("candidate_labels") or [])}
    assert "low_volume_breakout" in codes
    assert "ema_stack_against_trade" in codes
    assert "vwap_rejection" in codes
    assert "candle_close_failed" in codes
