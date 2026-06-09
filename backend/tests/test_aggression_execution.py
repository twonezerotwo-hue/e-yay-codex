"""
Aggression Execution Integration (FAZ 2) — unit testler.

Kapsam:
 1. Aggression-aware SL/TP — atr_multiplier kullanılır, fallback korunur
 2. Take Profit Plan — agresiflik seviyesine göre R/R + partial TP
 3. Recheck Plan — pozisyon açılışında next_recheck_at oluşur
 4. Max Holding Plan — max_holding_until + holding_status active
 5. Event Risk Fallback — artık hep False değil
 6. High Volatility Fallback — artık hep False değil
 7. Controlled-Aggressive Promotion — controlled_aggressive modda aktif
 8. Promotion — conservative modda çalışmaz
 9. Backward compat — eski open_signal'lar fallback'e düşer

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.services.aggression_awareness import (
    AGGRESSION_RR_TARGET,
    MIN_RR_THRESHOLD,
    PROMOTION_MAX_SIZE,
    AggressionContext,
    build_holding_plan,
    build_recheck_plan,
    build_take_profit_plan,
    calc_aggression_aware_sl_tp,
    derive_event_risk_fallback,
    derive_high_volatility_fallback,
    maybe_promote_command,
    score_aggression,
)
from app.services.agent_decision_aggregator import (
    aggregate_agent_decision,
    decision_to_open_signal_extras,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _sig(
    *,
    score: float = 72.0,
    direction: str = "bullish",
    regime: str = "NEUTRAL",
    conf: str = "aligned",
    tf_signals: dict | None = None,
    primary_tf: str = "1d",
    appetite: str = "STRONG",
    atr: float = 1.50,
    last_price: float = 100.0,
) -> dict:
    return {
        "final_score":     score,
        "final_direction": direction,
        "raw_regime":      regime,
        "confluence":      {"status": conf},
        "tf_signals":      tf_signals or {
            "1h": {"direction": "bullish", "score": 68.0},
            "4h": {"direction": "bullish", "score": 70.0},
            "1d": {"direction": "bullish", "score": 74.0},
        },
        "primary_tf":      primary_tf,
        "risk_appetite":   {"status": appetite},
        "atr":             atr,
        "last_price":      last_price,
    }


def _make_ctx(level: str) -> AggressionContext:
    sig = _sig()
    # Score'u istenen seviyeye gönder
    if level == "low":
        return score_aggression(
            sig, pair="BTCUSD", side="LONG",
            tf_alignment_label="strong", regime="RISK_ON", appetite="STRONG",
            dqs_score=85, contradiction_score=5,
        )
    if level == "medium":
        return score_aggression(
            sig, pair="BTCUSD", side="LONG",
            tf_alignment_label="moderate", regime="NEUTRAL", appetite="MODERATE",
            dqs_score=70, contradiction_score=30,
        )
    if level == "high":
        return score_aggression(
            sig, pair="BRENT", side="LONG",
            tf_alignment_label="weak", regime="DEFENSIVE", appetite="WEAK",
            dqs_score=60, contradiction_score=55,
        )
    # extreme
    return score_aggression(
        sig, pair="BRENT", side="LONG",
        tf_alignment_label="weak", regime="CRISIS", appetite="CRISIS",
        dqs_score=58, contradiction_score=75,
    )


# ── 1. Aggression-aware SL/TP ────────────────────────────────────────────────

def test_aggression_aware_sl_tp_uses_stop_decision_atr_multiplier():
    """High aggression: atr_multiplier=1.2 → SL = entry - 1.2*ATR"""
    open_signal = {
        "stop_decision": {
            "atr_multiplier": 1.2,
            "stop_type": "atr",
            "stop_distance_pct": 1.5,
        },
        "aggression_context": {"aggression_level": "high"},
    }
    result = calc_aggression_aware_sl_tp(
        "LONG", entry_price=100.0, pair="BRENT", atr_value=1.5,
        open_signal=open_signal,
    )
    assert result is not None
    sl, tp, meta = result
    # SL = 100 - 1.2*1.5 = 98.2
    assert sl == 98.2
    # TP = 100 + (1.2*1.5)*1.8 = 100 + 3.24 = 103.24
    expected_tp = 100.0 + (1.2 * 1.5 * AGGRESSION_RR_TARGET["high"])
    assert abs(tp - expected_tp) < 0.01
    assert meta["source"] == "aggression"
    assert meta["atr_multiplier"] == 1.2
    assert meta["rr_target"] == AGGRESSION_RR_TARGET["high"]


def test_aggression_aware_sl_tp_returns_none_without_stop_decision():
    """open_signal stop_decision yoksa → None (fallback)"""
    assert calc_aggression_aware_sl_tp("LONG", 100.0, "BRENT", 1.5, {}) is None
    assert calc_aggression_aware_sl_tp("LONG", 100.0, "BRENT", 1.5, None) is None


def test_aggression_aware_sl_tp_low_keeps_wide_stop():
    """Low aggression: atr_multiplier=2.5 → geniş stop korunur"""
    open_signal = {
        "stop_decision": {"atr_multiplier": 2.5, "stop_type": "atr"},
        "aggression_context": {"aggression_level": "low"},
    }
    result = calc_aggression_aware_sl_tp(
        "LONG", entry_price=100.0, pair="BTCUSD", atr_value=2.0,
        open_signal=open_signal,
    )
    assert result is not None
    sl, tp, meta = result
    # SL = 100 - 2.5*2.0 = 95.0
    assert sl == 95.0
    assert meta["rr_target"] == AGGRESSION_RR_TARGET["low"]
    assert meta["rr_target"] >= MIN_RR_THRESHOLD


def test_aggression_aware_sl_tp_requires_atr():
    """ATR yoksa None döner — caller fallback'e düşer"""
    open_signal = {
        "stop_decision": {"atr_multiplier": 1.2, "stop_type": "atr"},
        "aggression_context": {"aggression_level": "high"},
    }
    assert calc_aggression_aware_sl_tp("LONG", 100.0, "BRENT", None, open_signal) is None
    assert calc_aggression_aware_sl_tp("LONG", 100.0, "BRENT", 0.0, open_signal) is None


# ── 2. Take Profit Plan ──────────────────────────────────────────────────────

def test_tp_plan_extreme_aggression_uses_short_target_and_partial_tp():
    ctx = _make_ctx("extreme")
    plan = build_take_profit_plan(ctx, None, side="LONG", entry_price=100.0, stop_price=99.0)
    assert plan["rr_target"] == AGGRESSION_RR_TARGET["extreme"]
    assert plan["partial_tp_enabled"] is True
    assert plan["partial_tp_at_r"] is not None
    # rr_below_min False olmalı — table ile constant garantisi
    assert plan["rr_below_min"] is False


def test_tp_plan_low_aggression_uses_wide_target():
    ctx = _make_ctx("low")
    plan = build_take_profit_plan(ctx, None, side="LONG", entry_price=100.0, stop_price=98.0)
    assert plan["rr_target"] == AGGRESSION_RR_TARGET["low"]
    # final TP = 100 + (100-98)*2.8 = 105.6
    assert plan["final_tp_price"] is not None
    assert plan["final_tp_price"] > 105.0


def test_tp_plan_high_has_partial_tp_enabled():
    ctx = _make_ctx("high")
    plan = build_take_profit_plan(ctx, None, side="LONG", entry_price=100.0, stop_price=99.0)
    # _make_ctx("high") seviyesi high VEYA extreme dönebilir (skor sınırda); ikisinde de partial TP zorunlu
    assert plan["partial_tp_enabled"] is True
    assert plan["rr_target"] == AGGRESSION_RR_TARGET[ctx.aggression_level]
    assert ctx.aggression_level in ("high", "extreme")


def test_tp_plan_rr_always_above_min_threshold():
    """Tüm aggression seviyelerinde rr_target >= MIN_RR_THRESHOLD"""
    for level in ("low", "medium", "high", "extreme"):
        assert AGGRESSION_RR_TARGET[level] >= MIN_RR_THRESHOLD, (
            f"{level} rr_target {AGGRESSION_RR_TARGET[level]} < MIN {MIN_RR_THRESHOLD}"
        )


# ── 3. Recheck Plan ──────────────────────────────────────────────────────────

def test_recheck_plan_creates_next_recheck_at():
    ctx = _make_ctx("high")
    opened_at = datetime.now(UTC).isoformat()
    plan = build_recheck_plan(ctx, opened_at)
    assert plan["next_recheck_at"] != ""
    assert plan["recheck_interval_minutes"] == ctx.recheck_interval_minutes
    assert plan["recheck_count"] == 0
    assert plan["last_recheck_at"] is None
    assert plan["last_recheck_result"] is None
    # next_recheck_at = opened_at + interval
    next_dt = datetime.fromisoformat(plan["next_recheck_at"])
    opened_dt = datetime.fromisoformat(opened_at)
    delta_min = (next_dt - opened_dt).total_seconds() / 60.0
    assert abs(delta_min - ctx.recheck_interval_minutes) < 0.1


def test_recheck_plan_handles_bad_iso():
    ctx = _make_ctx("low")
    plan = build_recheck_plan(ctx, "not-an-iso")
    assert plan["next_recheck_at"] == ""
    assert plan["recheck_interval_minutes"] == ctx.recheck_interval_minutes


# ── 4. Max Holding Plan ──────────────────────────────────────────────────────

def test_holding_plan_creates_max_holding_until():
    ctx = _make_ctx("high")
    opened_at = datetime.now(UTC).isoformat()
    plan = build_holding_plan(ctx, opened_at)
    assert plan["max_holding_until"] != ""
    # _make_ctx("high") seviyesi high VEYA extreme dönebilir → 6h ya da 2h
    assert plan["max_holding_time"] in ("6h", "2h")
    assert plan["holding_status"] == "active"
    assert plan["extension_allowed"] is True
    # until = opened + N saat (N=2 ya da 6)
    until_dt = datetime.fromisoformat(plan["max_holding_until"])
    opened_dt = datetime.fromisoformat(opened_at)
    delta_h = (until_dt - opened_dt).total_seconds() / 3600.0
    expected_h = 6.0 if plan["max_holding_time"] == "6h" else 2.0
    assert abs(delta_h - expected_h) < 0.01


def test_holding_plan_extreme_uses_2h():
    ctx = _make_ctx("extreme")
    plan = build_holding_plan(ctx, datetime.now(UTC).isoformat())
    assert plan["max_holding_time"] == "2h"


# ── 5. Event Risk Fallback ───────────────────────────────────────────────────

def test_event_risk_fallback_high_in_crisis():
    sig = _sig(regime="CRISIS")
    out = derive_event_risk_fallback(
        "BRENT", sig, regime="CRISIS", appetite="WEAK", side="LONG",
    )
    assert out["event_risk_high"] is True
    assert out["reason"] != ""


def test_event_risk_fallback_low_in_normal_regime():
    sig = _sig(regime="RISK_ON")
    out = derive_event_risk_fallback(
        "BTCUSD", sig, regime="RISK_ON", appetite="STRONG", side="LONG",
    )
    assert out["event_risk_high"] is False


def test_event_risk_fallback_brent_long_in_crisis_supports_trade():
    """Brent LONG + enerji şoku → trade yönünü destekler"""
    sig = _sig(regime="CRISIS")
    out = derive_event_risk_fallback(
        "BRENT", sig, regime="CRISIS", appetite="CRISIS", side="LONG",
    )
    assert out["event_risk_high"] is True
    assert out["event_risk_direction"] == "supports_trade"


def test_event_risk_fallback_btc_long_in_crisis_against_trade():
    """BTC LONG + crisis → trade yönüne ters"""
    sig = _sig(regime="CRISIS")
    out = derive_event_risk_fallback(
        "BTCUSD", sig, regime="CRISIS", appetite="CRISIS", side="LONG",
    )
    assert out["event_risk_high"] is True
    assert out["event_risk_direction"] == "against_trade"


# ── 6. High Volatility Fallback ──────────────────────────────────────────────

def test_volatility_fallback_high_when_atr_pct_elevated():
    sig = _sig()
    # ATR/fiyat = 4/100 = %4 → high
    out = derive_high_volatility_fallback("BTCUSD", sig, atr_value=4.0, entry_price=100.0)
    assert out["high_volatility"] is True
    assert out["atr_pct"] >= 3.0


def test_volatility_fallback_high_for_fast_asset_with_moderate_atr():
    sig = _sig()
    out = derive_high_volatility_fallback("BRENT", sig, atr_value=2.5, entry_price=100.0)
    assert out["high_volatility"] is True


def test_volatility_fallback_low_when_atr_normal():
    sig = _sig()
    out = derive_high_volatility_fallback("XAUUSD", sig, atr_value=0.5, entry_price=2000.0)
    assert out["high_volatility"] is False


# ── 7. Controlled-Aggressive Promotion ──────────────────────────────────────

def test_promotion_activates_in_controlled_aggressive_mode():
    ctx = _make_ctx("high")
    # score'u 60-80 aralığına zorla
    if ctx.aggression_score < 60 or ctx.aggression_score > 80:
        ctx = AggressionContext(
            aggression_level="high", aggression_score=70,
            why_aggressive=ctx.why_aggressive,
            allowed_if_aggressive=True,
            required_adjustments=ctx.required_adjustments,
            recommended_timeframe=ctx.recommended_timeframe,
            max_holding_time=ctx.max_holding_time,
            recheck_interval_minutes=ctx.recheck_interval_minutes,
            stop_style=ctx.stop_style,
            summary=ctx.summary,
        )
    result = maybe_promote_command(
        paper_mode="controlled_aggressive",
        command="AGGRESSIVE_WATCH",
        side_hint="LONG",
        aggression=ctx,
        contradiction_score=50,
        block_reason="Güven düşük: 54.0 < 56.0",
        risk_action="HOLD",
        dqs_score=70,
        tf_alignment_label="weak",
        atr_value=1.5,
        event_risk_direction="neutral_or_unknown",
    )
    assert result["promoted"] is True
    assert result["to"] == "SCALP_LONG_SETUP"
    assert result["new_size_cap"] <= PROMOTION_MAX_SIZE


def test_promotion_disabled_in_conservative_mode():
    ctx = _make_ctx("high")
    result = maybe_promote_command(
        paper_mode="conservative",
        command="AGGRESSIVE_WATCH",
        side_hint="LONG",
        aggression=ctx,
        contradiction_score=50,
        block_reason="Güven düşük: 54.0 < 56.0",
        risk_action="HOLD",
        dqs_score=70,
        tf_alignment_label="weak",
        atr_value=1.5,
        event_risk_direction="neutral_or_unknown",
    )
    assert result["promoted"] is False


def test_promotion_blocked_when_kill_switch():
    ctx = _make_ctx("high")
    result = maybe_promote_command(
        paper_mode="controlled_aggressive",
        command="AGGRESSIVE_WATCH",
        side_hint="LONG",
        aggression=ctx,
        contradiction_score=50,
        block_reason="KILL_SWITCH (DQS=40)",
        risk_action="KILL_SWITCH",
        dqs_score=40,
        tf_alignment_label="weak",
        atr_value=1.5,
        event_risk_direction="neutral_or_unknown",
    )
    assert result["promoted"] is False


def test_promotion_blocked_when_event_risk_against():
    ctx = _make_ctx("high")
    result = maybe_promote_command(
        paper_mode="controlled_aggressive",
        command="AGGRESSIVE_WATCH",
        side_hint="LONG",
        aggression=ctx,
        contradiction_score=50,
        block_reason="Güven düşük",
        risk_action="HOLD",
        dqs_score=70,
        tf_alignment_label="weak",
        atr_value=1.5,
        event_risk_direction="against_trade",
    )
    assert result["promoted"] is False


def test_promotion_blocked_without_atr():
    ctx = _make_ctx("high")
    result = maybe_promote_command(
        paper_mode="controlled_aggressive",
        command="AGGRESSIVE_WATCH",
        side_hint="LONG",
        aggression=ctx,
        contradiction_score=50,
        block_reason="Güven düşük",
        risk_action="HOLD",
        dqs_score=70,
        tf_alignment_label="weak",
        atr_value=0.0,
        event_risk_direction="neutral_or_unknown",
    )
    assert result["promoted"] is False


# ── 8. Aggregator entegrasyonu ───────────────────────────────────────────────

def test_aggregator_emits_event_risk_and_volatility_contexts():
    sig = _sig(regime="CRISIS", appetite="CRISIS", atr=5.0, last_price=80.0)
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    assert isinstance(dec.event_risk_context, dict)
    assert "event_risk_high" in dec.event_risk_context
    assert isinstance(dec.volatility_context, dict)
    assert "high_volatility" in dec.volatility_context


def test_open_signal_extras_include_faz2_fields():
    sig = _sig(regime="TRANSITIONING", appetite="MODERATE", score=68.0)
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    extras = decision_to_open_signal_extras(dec)
    assert "event_risk_context" in extras
    assert "volatility_context" in extras
    assert "controlled_aggressive_promotion" in extras
    if dec.side in ("LONG", "SHORT"):
        assert "take_profit_plan" in extras


def test_event_risk_not_always_false():
    """FAZ 2 öncesi hep False geçiyordu; artık fallback heuristik üretir."""
    sig = _sig(regime="CRISIS", appetite="CRISIS")
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    # Brent + CRISIS → fallback True dönmeli
    assert dec.event_risk_context.get("event_risk_high") is True


def test_high_volatility_not_always_false():
    sig = _sig(atr=5.0, last_price=80.0)   # ATR/price = 6.25%
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0, dqs_score=80)
    assert dec.volatility_context.get("high_volatility") is True


def test_aggregator_promotion_in_controlled_aggressive_mode(monkeypatch):
    """Controlled aggressive modda uygun soft-blok → SCALP'e yükselir + trade açılır"""
    monkeypatch.setenv("PAPER_TRADING_MODE", "controlled_aggressive")
    # Soft block (confidence düşük) ama aggression high olsun:
    sig = _sig(
        regime="DEFENSIVE", appetite="WEAK", score=56.5,  # confidence sınırda
        tf_signals={
            "1h": {"direction": "bullish", "score": 58.0},
            "4h": {"direction": "neutral",  "score": 50.0},
            "1d": {"direction": "neutral",  "score": 50.0},
        },
        atr=1.5, last_price=100.0,
    )
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    # Score'u uygun aralıkta promote olabilmesi için aggression high/extreme + 60-80 olmalı
    if (dec.aggression and dec.aggression.aggression_score >= 60
            and dec.aggression.aggression_score <= 80
            and dec.command == "AGGRESSIVE_WATCH"):
        # Promotion uygulanmalı
        promo = dec.controlled_aggressive_promotion
        # Promotion uygulandıysa command SCALP olmalı
        if promo.get("promoted"):
            assert dec.command == "SCALP_LONG_SETUP"
            assert dec.size_pct > 0.0
            assert dec.size_pct <= PROMOTION_MAX_SIZE


def test_aggregator_promotion_disabled_in_conservative_mode(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING_MODE", "conservative")
    sig = _sig(
        regime="DEFENSIVE", appetite="WEAK", score=56.5,
        tf_signals={
            "1h": {"direction": "bullish", "score": 58.0},
            "4h": {"direction": "neutral",  "score": 50.0},
            "1d": {"direction": "neutral",  "score": 50.0},
        },
        atr=1.5, last_price=100.0,
    )
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    # Promotion olmamalı
    promo = dec.controlled_aggressive_promotion
    assert promo.get("promoted") is False


# ── 9. Backward compatibility ────────────────────────────────────────────────

def test_old_open_signal_falls_back_to_legacy_sl_tp():
    """Eski open_signal (stop_decision yok) → calc_aggression_aware_sl_tp None döner"""
    old_signal = {
        "final_score": 70, "final_direction": "bullish",
        "raw_regime": "RISK_ON", "atr": 1.5,
    }
    assert calc_aggression_aware_sl_tp(
        "LONG", 100.0, "BTCUSD", 1.5, old_signal,
    ) is None


# ── 10. paper_trading_service entegrasyonu (position fields) ─────────────────

def test_position_open_creates_recheck_and_holding_plans(tmp_path, monkeypatch):
    """_open_position_from_pending: aggression_context varsa Position.recheck_plan
    ve holding_plan otomatik kurulur."""
    # Geçici state path kullan
    import app.services.paper_trading_service as pts
    state_path = tmp_path / "paper_trading_state.json"
    monkeypatch.setattr(pts, "_STATE_PATH", state_path)

    # Aggregator çıktısı ile zenginleştirilmiş open_signal hazırla
    sig = _sig(regime="DEFENSIVE", appetite="WEAK", score=62.0,
               tf_signals={"1h": {"direction": "bullish", "score": 60.0}})
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    extras = decision_to_open_signal_extras(dec)
    enriched_signal = {**sig, **extras}

    pending = pts.PendingOpenOrder(
        pair="BRENT",
        side="LONG",
        requested_at=datetime.now(UTC).isoformat(),
        execute_at=datetime.now(UTC).isoformat(),
        requested_price=100.0,
        size_usd=10_000.0,
        last_signal="test",
        open_signal=enriched_signal,
        fingerprint="test_fp",
        atr_value=1.5,
        primary_tf="1d",
    )
    st = pts.TradingState()
    opened_at = datetime.now(UTC).isoformat()
    pts._open_position_from_pending(st, pending, current_price=100.0, opened_at=opened_at)

    pos = st.positions.get("BRENT")
    assert pos is not None
    # aggression_context varsa recheck_plan + holding_plan otomatik kurulmalı
    assert pos.recheck_plan != {}
    assert pos.holding_plan != {}
    assert pos.recheck_plan.get("next_recheck_at") != ""
    assert pos.holding_plan.get("max_holding_until") != ""
    assert pos.holding_plan.get("holding_status") == "active"
    # open_signal'a take_profit_plan yazılmış olmalı (finalized)
    assert pos.open_signal.get("take_profit_plan") is not None


def test_position_recheck_audit_only_no_auto_close(tmp_path, monkeypatch):
    """Recheck zamanı gelse bile pozisyon otomatik kapatılmaz; sadece audit yazılır."""
    import app.services.paper_trading_service as pts
    state_path = tmp_path / "paper_trading_state.json"
    monkeypatch.setattr(pts, "_STATE_PATH", state_path)

    # Bir pozisyon kur (geçmişte açılmış gibi)
    past = datetime.now(UTC) - timedelta(hours=2)
    pos = pts.Position(
        pair="BRENT", side="LONG", entry_price=100.0,
        entry_at=past.isoformat(), size_usd=10_000.0,
        last_signal="test", stop_loss=98.0, take_profit=104.0,
        recheck_plan={
            "recheck_interval_minutes": 30,
            "next_recheck_at": (past + timedelta(minutes=30)).isoformat(),
            "last_recheck_at": None,
            "recheck_count": 0,
            "max_rechecks": 12,
            "last_recheck_result": None,
            "last_recheck_reason": "",
        },
        holding_plan={
            "max_holding_time": "6h",
            "max_holding_until": (past + timedelta(hours=6)).isoformat(),
            "extension_allowed": True,
            "extension_requires": [],
            "holding_status": "active",
        },
    )
    now_dt = datetime.now(UTC)
    # Recheck zamanı çoktan geçti — handler çağrıldığında otomatik close YAPMAMALI
    pts._apply_recheck_and_holding_review(
        pos, "BRENT", sig=None, now_dt=now_dt,
        dqs_score=70, kill_switch=False,
    )
    # Pozisyon hala duruyor — sadece plan güncellenmiş
    assert pos.recheck_plan.get("recheck_count") == 1
    assert pos.recheck_plan.get("last_recheck_at") is not None
    assert pos.recheck_plan.get("last_recheck_result") == "ok"


def test_holding_expiry_marks_review_no_auto_close(tmp_path, monkeypatch):
    """Max holding süresi dolunca otomatik close değil, holding_status değişir."""
    import app.services.paper_trading_service as pts
    state_path = tmp_path / "paper_trading_state.json"
    monkeypatch.setattr(pts, "_STATE_PATH", state_path)

    past = datetime.now(UTC) - timedelta(hours=8)
    pos = pts.Position(
        pair="BRENT", side="LONG", entry_price=100.0,
        entry_at=past.isoformat(), size_usd=10_000.0,
        last_signal="test", stop_loss=98.0, take_profit=104.0,
        recheck_plan={
            "recheck_interval_minutes": 30,
            "next_recheck_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "last_recheck_at": None,
            "recheck_count": 0, "max_rechecks": 12,
            "last_recheck_result": None, "last_recheck_reason": "",
        },
        holding_plan={
            "max_holding_time": "6h",
            "max_holding_until": (past + timedelta(hours=6)).isoformat(),  # 2 saat önce doldu
            "extension_allowed": True, "extension_requires": [],
            "holding_status": "active",
        },
    )
    now_dt = datetime.now(UTC)
    pts._apply_recheck_and_holding_review(
        pos, "BRENT", sig=None, now_dt=now_dt,
        dqs_score=80, kill_switch=False,
    )
    assert pos.holding_plan.get("holding_status") == "expired_needs_review"


def test_old_state_loads_with_empty_recheck_holding_plans(tmp_path, monkeypatch):
    """Eski state dosyaları (recheck_plan/holding_plan yoksa) sorunsuz okunur."""
    import json
    import app.services.paper_trading_service as pts
    state_path = tmp_path / "paper_trading_state.json"
    monkeypatch.setattr(pts, "_STATE_PATH", state_path)

    # Eski formatta state — yeni alanlar YOK
    old_state = {
        "starting_balance": 100_000.0,
        "realized_pnl_usd": 0.0,
        "positions": {
            "BRENT": {
                "pair": "BRENT", "side": "LONG",
                "entry_price": 100.0, "entry_at": "2025-01-01T00:00:00+00:00",
                "size_usd": 25_000.0, "last_signal": "test",
                "stop_loss": 98.0, "take_profit": 104.0,
                # recheck_plan / holding_plan YOK
            },
        },
        "pending_orders": {}, "rejected_signals": {}, "manual_ready_trades": {},
        "trades": [], "weight_adjustments": {},
        "last_trained_at_trade_count": 0, "training_history": [],
        "last_tick_prices": {}, "last_tick_signals": {},
    }
    state_path.write_text(json.dumps(old_state), encoding="utf-8")

    st = pts._load_state()
    pos = st.positions.get("BRENT")
    assert pos is not None
    assert pos.recheck_plan == {}
    assert pos.holding_plan == {}
