"""Paper trading lifecycle classifier testleri.

Mevcut sinyalleri standart lifecycle koduna çevirir. Yeni trade davranışı
eklemez; sadece sınıflandırır.
"""
from __future__ import annotations

from app.market_state.lifecycle import (
    LIFECYCLE_CODES,
    classify_candidate_lifecycle,
    classify_position_lifecycle,
)


def test_kill_switch_wins_over_everything() -> None:
    code = classify_position_lifecycle(
        position={"aggression_level": "low"},
        risk_action="KILL_SWITCH", add_plan_active=True,
        regime_flipped=True, time_stop_hit=True,
    )
    assert code == "KILL_SWITCH_EXIT"


def test_time_stop_before_regime_flip() -> None:
    code = classify_position_lifecycle(
        position={}, time_stop_hit=True, regime_flipped=True, risk_action="HOLD",
    )
    assert code == "TIME_STOP_EXIT"


def test_add_plan_yields_momentum_add() -> None:
    code = classify_position_lifecycle(
        position={"aggression_level": "medium"},
        risk_action="HOLD", add_plan_active=True,
    )
    assert code == "MOMENTUM_ADD"


def test_scout_when_aggression_low() -> None:
    code = classify_position_lifecycle(
        position={"aggression_level": "low"}, risk_action="HOLD",
    )
    assert code == "SCOUT_ENTRY"


def test_confirmation_default() -> None:
    code = classify_position_lifecycle(
        position={"aggression_level": "medium"}, risk_action="HOLD",
    )
    assert code == "CONFIRMATION_ENTRY"


def test_candidate_block_reason_goes_watch_only() -> None:
    code = classify_candidate_lifecycle(
        risk_action="HOLD", block_reason="TF karşıt", should_trade=False,
    )
    assert code == "WATCH_ONLY"


def test_candidate_kill_switch() -> None:
    code = classify_candidate_lifecycle(
        risk_action="KILL_SWITCH", block_reason="", should_trade=False,
    )
    assert code == "KILL_SWITCH_EXIT"


def test_candidate_no_trade_when_should_trade_false() -> None:
    code = classify_candidate_lifecycle(
        risk_action="HOLD", block_reason=None, should_trade=False,
    )
    assert code == "NO_TRADE"


def test_candidate_scout_when_manual_required() -> None:
    code = classify_candidate_lifecycle(
        risk_action="HOLD", block_reason=None, should_trade=True,
        manual_required=True,
    )
    assert code == "SCOUT_ENTRY"


def test_codes_are_canonical() -> None:
    for fn in (
        classify_position_lifecycle({}),
        classify_candidate_lifecycle(risk_action="HOLD", block_reason=None, should_trade=False),
    ):
        assert fn in LIFECYCLE_CODES
