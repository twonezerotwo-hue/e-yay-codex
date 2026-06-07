"""
Agent Decision Aggregator — unit testler.

Her katman (TF alignment, regime sizing, DQS gate, trigger auto-close)
bağımsız test edilir. Mevcut paper_trading_service testleri bozulmaz.

PAPER_SAFE / NO_EXECUTION
"""
from __future__ import annotations

import pytest

from app.services.agent_decision_aggregator import (
    AgentTradeDecision,
    MIN_DQS,
    MIN_TRADE_CONFIDENCE,
    TFAlignment,
    _check_trigger_auto_close,
    _compute_tf_alignment,
    _get_risk_action,
    aggregate_agent_decision,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sig(
    *,
    score: float = 72.0,
    direction: str = "bullish",
    regime: str = "OFFENSIVE",
    conf: str = "aligned",
    tf_signals: dict | None = None,
    primary_tf: str = "1d",
) -> dict:
    return {
        "final_score":     score,
        "final_direction": direction,
        "raw_regime":      regime,
        "confluence":      {"status": conf},
        "primary_tf":      primary_tf,
        "tf_signals":      tf_signals or {},
    }


def _tf(dir_: str, score: float) -> dict:
    return {"direction": dir_, "score": score}


# ── 1. TF Alignment: strong ───────────────────────────────────────────────────

def test_strong_tf_alignment_3_bullish():
    tfs = {"1h": _tf("bullish", 72), "4h": _tf("bullish", 68), "1d": _tf("bullish", 70)}
    result = _compute_tf_alignment(tfs, "LONG")
    assert result.label == "strong"
    assert result.bullish_count == 3
    assert result.avg_score >= 68


def test_moderate_tf_alignment_2_bullish():
    tfs = {"1h": _tf("bullish", 65), "4h": _tf("bullish", 63), "1d": _tf("neutral", 52)}
    result = _compute_tf_alignment(tfs, "LONG")
    assert result.label == "moderate"
    assert result.bullish_count == 2


def test_weak_tf_alignment_1_bullish():
    tfs = {"1h": _tf("bullish", 68), "4h": _tf("neutral", 50), "1d": _tf("neutral", 48)}
    result = _compute_tf_alignment(tfs, "LONG")
    assert result.label == "weak"


def test_divergent_tf_alignment_bearish_majority():
    tfs = {"1h": _tf("bullish", 62), "4h": _tf("bearish", 38), "1d": _tf("bearish", 35)}
    result = _compute_tf_alignment(tfs, "LONG")
    assert result.label == "divergent"


def test_empty_tf_signals_returns_none():
    result = _compute_tf_alignment({}, "LONG")
    assert result.label == "none"


# ── 2. Risk action kuralları ──────────────────────────────────────────────────

def test_kill_switch_overrides_everything():
    assert _get_risk_action("OFFENSIVE", dqs_score=99, kill_switch=True) == "KILL_SWITCH"


def test_low_dqs_triggers_kill_switch():
    assert _get_risk_action("OFFENSIVE", dqs_score=MIN_DQS - 1, kill_switch=False) == "KILL_SWITCH"


def test_crisis_regime_maps_to_risk_reduce():
    assert _get_risk_action("CRISIS", dqs_score=90, kill_switch=False) == "RISK_REDUCE"


def test_defensive_maps_to_no_position_increase():
    assert _get_risk_action("DEFENSIVE", dqs_score=80, kill_switch=False) == "NO_POSITION_INCREASE"


def test_offensive_maps_to_hold():
    assert _get_risk_action("OFFENSIVE", dqs_score=85, kill_switch=False) == "HOLD"


# ── 3. Trigger auto-close ─────────────────────────────────────────────────────

def test_red_critical_trigger_sets_auto_close():
    te = {
        "trigger_severity": "RED",
        "confirmed_triggers": [{"trigger_code": "RED_ENERGY_SHOCK", "asset": "BRENT"}],
    }
    fired, reason = _check_trigger_auto_close(te)
    assert fired is True
    assert "RED_ENERGY_SHOCK" in reason


def test_orange_trigger_does_not_auto_close():
    te = {
        "trigger_severity": "ORANGE",
        "confirmed_triggers": [{"trigger_code": "RED_ENERGY_SHOCK", "asset": "BRENT"}],
    }
    fired, _ = _check_trigger_auto_close(te)
    assert fired is False


def test_none_trigger_engine_safe():
    fired, _ = _check_trigger_auto_close(None)
    assert fired is False


# ── 4. Aggregator — OFFENSIVE + strong TF → büyük size ───────────────────────

def test_strong_alignment_offensive_full_size():
    tfs = {"1h": _tf("bullish", 73), "4h": _tf("bullish", 70), "1d": _tf("bullish", 68)}
    sig = _sig(score=74, regime="OFFENSIVE", tf_signals=tfs)
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    assert dec.side == "LONG"
    assert dec.should_trade is True
    # OFFENSIVE × strong → size_pct = 1.0 × 1.0 × 1.0 = 1.0
    assert dec.size_pct >= 0.95
    assert dec.confidence >= 74  # strong alignment bonus


def test_defensive_regime_reduces_size():
    sig = _sig(score=70, regime="DEFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    assert dec.side == "LONG"
    # DEFENSIVE mult=0.65, none TF mult=0.75 → 0.65 × 0.75 ≈ 0.49
    assert dec.size_pct < 0.55, f"DEFENSIVE pozisyonu küçük olmalı, got {dec.size_pct}"


# ── 5. Divergent TF → trade bloke ────────────────────────────────────────────

def test_divergent_tf_blocks_trade():
    tfs = {"1h": _tf("bullish", 62), "4h": _tf("bearish", 38), "1d": _tf("bearish", 35)}
    sig = _sig(score=72, regime="OFFENSIVE", tf_signals=tfs)
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    assert dec.should_trade is False
    assert dec.side is None
    assert "karşıt" in dec.block_reason.lower() or "divergent" in dec.block_reason.lower()


# ── 6. DQS gate → trade bloke ────────────────────────────────────────────────

def test_low_dqs_blocks_trade():
    sig = _sig(score=75, regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0, dqs_score=40)
    assert dec.should_trade is False
    assert dec.side is None
    assert "KILL_SWITCH" in dec.block_reason


def test_acceptable_dqs_allows_trade():
    sig = _sig(score=72, regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0, dqs_score=80)
    assert dec.should_trade is True


# ── 7. Düşük skor → bloke / yok ──────────────────────────────────────────────

def test_below_min_score_returns_none_side():
    sig = _sig(score=50, direction="bullish", regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=0.6)
    # score=50 < MIN_SCORE_THRESHOLD=58 → side=None
    assert dec.side is None


def test_score_at_threshold_allows_weak_trade():
    sig = _sig(score=60, direction="bullish", regime="NEUTRAL")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    # 60 >= 58 threshold, NEUTRAL, no TF data → check confidence
    if dec.side == "LONG":
        assert dec.confidence >= MIN_TRADE_CONFIDENCE


# ── 8. Kill_switch flag ───────────────────────────────────────────────────────

def test_kill_switch_flag_blocks_even_with_good_signal():
    tfs = {"1h": _tf("bullish", 75), "4h": _tf("bullish", 72), "1d": _tf("bullish", 70)}
    sig = _sig(score=80, regime="OFFENSIVE", tf_signals=tfs)
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.5, kill_switch=True)
    assert dec.should_trade is False
    assert dec.side is None
    assert dec.size_pct == 0.0


# ── 9. Bearish sinyal destekli ────────────────────────────────────────────────

def test_bearish_signal_returns_short():
    sig = _sig(score=38, direction="bearish", regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "XAUUSD", base_mult_from_score=1.0)
    # 38 <= 100-58=42 → SHORT
    assert dec.side == "SHORT"


# ── 10. Auto_close içeren trigger entegrasyonu ────────────────────────────────

def test_aggregator_with_red_trigger_sets_auto_close():
    te = {
        "trigger_severity": "RED",
        "confirmed_triggers": [{"trigger_code": "SYSTEMIC_RISK_RED", "asset": "ALL"}],
    }
    sig = _sig(score=75, regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0, trigger_engine=te)
    assert dec.auto_close is True
    assert "SYSTEMIC_RISK_RED" in dec.auto_close_reason


# ── 11. CRISIS rejimine bakılmaksızın iyi sinyal küçük lot ile geçer ─────────

def test_crisis_regime_allows_small_trade():
    sig = _sig(score=72, regime="CRISIS")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    # CRISIS → RISK_REDUCE, küçük lot ama BLOKE değil
    assert dec.side == "LONG"
    # size_pct = 1.0 × 0.35 (CRISIS) × 0.75 (none TF) ≈ 0.26
    assert 0.0 < dec.size_pct < 0.45, f"CRISIS lot küçük olmalı, got {dec.size_pct}"


# ── 12. Reasoning listesi dolu ────────────────────────────────────────────────

def test_reasons_non_empty_for_trade():
    sig = _sig(score=72, regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    assert len(dec.reasons) >= 1


def test_reasons_contains_pass_for_blocked():
    sig = _sig(score=50, direction="bullish", regime="OFFENSIVE")
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0)
    assert any("PASS" in r for r in dec.reasons)
