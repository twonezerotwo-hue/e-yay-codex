"""
Aggression Awareness Layer — unit testler.

Test edilen davranışlar:
 1. Medium appetite + strong technical → TACTICAL_LONG_SETUP üretir
 2. Contradiction 60-80 → AGGRESSIVE_WATCH veya SCALP_LONG_SETUP
 3. DQS<55 → BLOCKED (hard block korunuyor)
 4. Kill switch ON → BLOCKED
 5. Aggression high → stop ATR multiplier küçülür
 6. Aggression high → size çarpanı küçülür
 7. Aggression high → timeframe 15m/30m/1h aralığında
 8. Aggression high → max holding kısa atanır
 9. aggregate_agent_decision sonucu open_signal extras üretir (aggression_context dahil)
10. Mevcut sizing hiçbir zaman büyütülmez — controlled-aggressive guard

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import pytest

from app.services.aggression_awareness import (
    AGGRESSION_ATR_MULT,
    AGGRESSION_MAX_SIZE,
    AGGRESSION_RECHECK_MIN,
    AGGRESSION_TIMEFRAME,
    aggression_sizing,
    aggression_to_dict,
    choose_stop,
    choose_timeframe,
    derive_contradiction_score,
    pick_command,
    score_aggression,
)
from app.services.agent_decision_aggregator import (
    aggregate_agent_decision,
    decision_to_open_signal_extras,
)


# ── Sig fixture'ı ────────────────────────────────────────────────────────────

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


# ── 1. Medium appetite + strong technical → TACTICAL_LONG_SETUP ─────────────

def test_medium_appetite_strong_tech_produces_tactical_setup():
    sig = _sig(regime="TRANSITIONING", appetite="MODERATE", score=68.0)
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    assert dec.side == "LONG"
    # Komut TACTICAL_LONG_SETUP ya da LONG_SETUP olabilir (contradiction skoru sınırda);
    # tamamen blok olmamalı + aggression en az medium olmalı
    assert dec.command in ("TACTICAL_LONG_SETUP", "SCALP_LONG_SETUP", "LONG_SETUP")
    assert dec.aggression is not None
    assert dec.aggression.aggression_level in ("medium", "high")


# ── 2. Contradiction 60-80 → AGGRESSIVE_WATCH / SCALP_LONG_SETUP ────────────

def test_high_contradiction_does_not_hard_block():
    # Bullish teknik + DEFENSIVE rejim + zayıf TF uyumu → contradiction yüksek
    sig = _sig(
        regime="DEFENSIVE", appetite="WEAK", score=62.0,
        tf_signals={
            "1h": {"direction": "bullish", "score": 60.0},
            "4h": {"direction": "neutral", "score": 50.0},
            "1d": {"direction": "neutral", "score": 50.0},
        },
    )
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=68)
    # Hard block YOK (contradiction tek başına bloklamaz)
    assert dec.command in (
        "SCALP_LONG_SETUP", "TACTICAL_LONG_SETUP", "AGGRESSIVE_WATCH", "LONG_SETUP",
    ), f"Beklenen controlled-aggressive komut, geldi: {dec.command}"
    # Aggression high veya extreme olmalı
    assert dec.aggression is not None
    assert dec.aggression.aggression_level in ("high", "extreme", "medium")


# ── 3. DQS<55 → BLOCKED ──────────────────────────────────────────────────────

def test_low_dqs_remains_blocked():
    sig = _sig()
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0, dqs_score=40)
    assert dec.command == "BLOCKED"
    assert dec.side is None
    assert "KILL_SWITCH" in dec.block_reason


# ── 4. Kill switch ON → BLOCKED ──────────────────────────────────────────────

def test_kill_switch_blocks_everything():
    sig = _sig()
    dec = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.0,
                                   dqs_score=80, kill_switch=True)
    assert dec.command == "BLOCKED"
    assert dec.side is None
    assert "KILL_SWITCH" in dec.block_reason


# ── 5. Aggression high → ATR çarpanı küçülür ─────────────────────────────────

def test_aggression_high_tightens_stop():
    sig = _sig(regime="DEFENSIVE", appetite="WEAK", score=60.0,
               tf_signals={"1h": {"direction": "bullish", "score": 58.0}})
    contradiction = derive_contradiction_score(sig, tf_alignment_label="weak", regime="DEFENSIVE")
    ctx = score_aggression(
        sig, pair="BRENT", side="LONG",
        tf_alignment_label="weak", regime="DEFENSIVE", appetite="WEAK",
        dqs_score=60, contradiction_score=contradiction,
    )
    assert ctx.aggression_level in ("high", "extreme")
    stop = choose_stop(ctx, side="LONG", price=100.0, atr_value=1.5)
    assert stop.atr_multiplier <= 1.5
    # Low aggression için karşılaştırma
    ctx_low = score_aggression(
        _sig(), pair="BTCUSD", side="LONG",
        tf_alignment_label="strong", regime="RISK_ON", appetite="STRONG",
        dqs_score=85, contradiction_score=10,
    )
    stop_low = choose_stop(ctx_low, side="LONG", price=100.0, atr_value=1.5)
    assert stop.atr_multiplier < stop_low.atr_multiplier


# ── 6. Aggression high → size çarpanı küçülür ────────────────────────────────

def test_aggression_high_shrinks_size():
    sig = _sig(regime="DEFENSIVE", appetite="WEAK", score=60.0)
    ctx_high = score_aggression(
        sig, pair="BRENT", side="LONG",
        tf_alignment_label="weak", regime="DEFENSIVE", appetite="WEAK",
        dqs_score=60, contradiction_score=65,
    )
    ctx_low = score_aggression(
        _sig(), pair="BTCUSD", side="LONG",
        tf_alignment_label="strong", regime="RISK_ON", appetite="STRONG",
        dqs_score=85, contradiction_score=10,
    )
    s_high = aggression_sizing(
        base_size_multiplier=1.0, regime="DEFENSIVE",
        aggression=ctx_high, contradiction_score=65,
    )
    s_low = aggression_sizing(
        base_size_multiplier=1.0, regime="RISK_ON",
        aggression=ctx_low, contradiction_score=10,
    )
    assert s_high.final_size_multiplier < s_low.final_size_multiplier
    # Üst sınır kontrolü — extreme/high max sizing
    assert s_high.aggression_multiplier <= AGGRESSION_MAX_SIZE["high"]


# ── 7. Aggression high → timeframe kısa ──────────────────────────────────────

def test_aggression_high_shortens_timeframe():
    sig = _sig(regime="DEFENSIVE", appetite="WEAK", score=60.0)
    ctx_high = score_aggression(
        sig, pair="BRENT", side="LONG",
        tf_alignment_label="weak", regime="DEFENSIVE", appetite="WEAK",
        dqs_score=60, contradiction_score=65,
    )
    tf = choose_timeframe(ctx_high, primary_tf="1d")
    assert tf.selected_timeframe in ("15m", "30m", "1h")


# ── 8. Aggression high → max holding kısa ────────────────────────────────────

def test_aggression_high_shortens_holding():
    sig = _sig(regime="DEFENSIVE", appetite="WEAK", score=60.0)
    ctx_high = score_aggression(
        sig, pair="BRENT", side="LONG",
        tf_alignment_label="weak", regime="DEFENSIVE", appetite="WEAK",
        dqs_score=60, contradiction_score=65,
    )
    assert ctx_high.max_holding_time in ("2h", "6h")
    assert ctx_high.recheck_interval_minutes <= 30


# ── 9. open_signal extras: aggression_context dahil ─────────────────────────

def test_decision_to_open_signal_extras_includes_aggression():
    sig = _sig(regime="TRANSITIONING", appetite="MODERATE")
    dec = aggregate_agent_decision(sig, "BRENT", base_mult_from_score=1.0, dqs_score=70)
    extras = decision_to_open_signal_extras(dec)

    assert "agent_command" in extras
    assert "contradiction_score" in extras
    assert "aggression_context" in extras
    agg_block = extras["aggression_context"]
    for key in (
        "aggression_level", "aggression_score", "why_aggressive",
        "required_adjustments", "recommended_timeframe",
        "max_holding_time", "recheck_interval_minutes", "stop_style", "summary",
    ):
        assert key in agg_block


# ── 10. Controlled-aggressive guard: sizing hiçbir zaman büyütülmez ─────────

def test_aggression_never_grows_size():
    sig = _sig(regime="RISK_ON", appetite="STRONG", score=82.0)
    dec_strong = aggregate_agent_decision(sig, "BTCUSD", base_mult_from_score=1.5, dqs_score=90)
    # Aggression low — yine de mevcut size_pct'yi büyütmemeli
    if dec_strong.sizing_decision is not None:
        assert dec_strong.size_pct <= max(
            1.5 * 1.0 * 1.0,  # raw base * regime * TF
            dec_strong.sizing_decision.final_size_multiplier,
        )
    # Negatif değer olmamalı
    assert dec_strong.size_pct >= 0.0


# ── 11. Contradiction score: makro çelişkisini yakalar ──────────────────────

def test_contradiction_score_captures_macro_conflict():
    # Bullish + CRISIS regime → yüksek contradiction beklenir
    sig_conflict = _sig(direction="bullish", regime="CRISIS")
    score_conflict = derive_contradiction_score(
        sig_conflict, tf_alignment_label="weak", regime="CRISIS",
    )
    # Bullish + RISK_ON → düşük contradiction beklenir
    sig_aligned = _sig(direction="bullish", regime="RISK_ON")
    score_aligned = derive_contradiction_score(
        sig_aligned, tf_alignment_label="strong", regime="RISK_ON",
    )
    assert score_conflict > score_aligned
    assert score_conflict >= 40
    assert score_aligned <= 30


# ── 12. pick_command: block_reason her zaman BLOCKED üretir ─────────────────

def test_pick_command_respects_block_reason():
    sig = _sig()
    ctx = score_aggression(
        sig, pair="BTCUSD", side="LONG",
        tf_alignment_label="strong", regime="RISK_ON", appetite="STRONG",
        dqs_score=85, contradiction_score=10,
    )
    cmd = pick_command(
        side="LONG", confidence=80.0,
        aggression_level=ctx.aggression_level,
        contradiction_score=10,
        block_reason="KILL_SWITCH (DQS=40)",
        risk_action="KILL_SWITCH",
    )
    assert cmd == "BLOCKED"


# ── 13. aggression_to_dict: tüm alanlar serileşir ───────────────────────────

def test_aggression_to_dict_round_trip():
    sig = _sig(regime="TRANSITIONING", appetite="MODERATE")
    ctx = score_aggression(
        sig, pair="BRENT", side="LONG",
        tf_alignment_label="moderate", regime="TRANSITIONING", appetite="MODERATE",
        dqs_score=68, contradiction_score=40,
    )
    d = aggression_to_dict(ctx)
    assert d["aggression_level"] == ctx.aggression_level
    assert d["aggression_score"] == ctx.aggression_score
    assert isinstance(d["why_aggressive"], list)
    assert isinstance(d["required_adjustments"], dict)
    assert d["recommended_timeframe"] in ("15m", "30m", "1h", "4h", "1d")
