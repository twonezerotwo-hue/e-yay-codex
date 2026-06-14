"""PHASE 3 — AI opinion ASLA paper trade size'ı artıramaz (PAPER_SAFE).

AI opinion yalnızca: size azaltabilir, manual-review'a alabilir, açıklayabilir.
Boost (size artırma) yok. Bu testler invariant'ı kilitler.

NOT: backend/tests/conftest.py autouse fixture'ı modül attribute'ünü no-op'a
patch'liyor; gerçek fonksiyonu import anında (fixture koşmadan önce) bağlayarak
bypass ediyoruz.
"""
from __future__ import annotations

from app.services.ai_trade_opinion_service import (
    build_trade_opinion_context_for_signal as _ctx,
)


def _op(asset_opinion: str, conviction: str = "high", *, pair: str = "BTCUSD",
        pos: list | None = None) -> dict:
    return {
        "asset_opinions": [
            {"asset": pair, "opinion": asset_opinion, "conviction": conviction},
        ],
        "open_position_opinions": pos or [],
    }


# ── Boost yok: aligned + high/medium conviction → çarpan ≤ 1.0 ────────────────

def test_high_conviction_aligned_does_not_increase_size():
    ctx = _ctx("BTCUSD", "LONG", opinion=_op("LONG_BIAS", "high"))
    assert ctx["size_multiplier"] == 1.0          # eskiden 1.10 idi
    assert ctx["size_multiplier"] <= 1.0


def test_medium_conviction_aligned_does_not_increase_size():
    ctx = _ctx("BTCUSD", "LONG", opinion=_op("LONG_BIAS", "medium"))
    assert ctx["size_multiplier"] == 1.0          # eskiden 1.05 idi
    assert ctx["size_multiplier"] <= 1.0


def test_short_bias_aligned_short_does_not_increase_size():
    ctx = _ctx("BTCUSD", "SHORT", opinion=_op("SHORT_BIAS", "high"))
    assert ctx["size_multiplier"] <= 1.0


# ── Azaltma / manual-review yolları KORUNUR ───────────────────────────────────

def test_avoid_reduces_and_routes_manual_ready():
    ctx = _ctx("BTCUSD", "LONG", opinion=_op("AVOID"))
    assert ctx["size_multiplier"] == 0.0
    assert ctx["route_recommendation"] == "manual_ready"


def test_wait_reduces_size():
    ctx = _ctx("BTCUSD", "LONG", opinion=_op("WAIT", "high"))
    assert ctx["size_multiplier"] <= 0.90


def test_low_conviction_not_aligned_reduces_size():
    ctx = _ctx("BTCUSD", "LONG", opinion=_op("SHORT_BIAS", "low"))  # LONG side ≠ short bias
    assert ctx["size_multiplier"] <= 0.85


def test_position_reduce_watch_routes_manual_ready():
    op = _op("LONG_BIAS", "high", pos=[{"pair": "BTCUSD", "opinion": "REDUCE_WATCH"}])
    ctx = _ctx("BTCUSD", "LONG", opinion=op)
    assert ctx["route_recommendation"] == "manual_ready"
    assert ctx["size_multiplier"] <= 1.0


# ── Opinion yok → deterministik mevcut davranış (1.0, proceed) ────────────────

def test_no_opinion_is_neutral_passthrough():
    ctx = _ctx("BTCUSD", "LONG", opinion={})   # falsy → unavailable
    assert ctx["available"] is False
    assert ctx["size_multiplier"] == 1.0
    assert ctx["route_recommendation"] == "proceed"


# ── Genel invariant: hiçbir opinion kombinasyonu çarpanı 1.0 üstüne çıkaramaz ──

def test_no_opinion_combo_ever_exceeds_one():
    for op_label in ("LONG_BIAS", "SHORT_BIAS", "HOLD", "AVOID", "WAIT", "REDUCE"):
        for conv in ("high", "medium", "low"):
            for side in ("LONG", "SHORT"):
                ctx = _ctx("BTCUSD", side, opinion=_op(op_label, conv))
                assert ctx["size_multiplier"] <= 1.0, f"{op_label}/{conv}/{side} boosted!"
