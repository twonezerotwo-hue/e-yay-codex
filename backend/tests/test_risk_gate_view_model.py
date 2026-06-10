"""RiskGate / AgentVote / PositionCheck ViewModel testleri.

Mevcut risk motoru ÇIKTILARININ doğru standartlaştırıldığını sabitler.
Motoru yeniden yazmaz; sadece map'leme garantisi verir:
  KILL_SWITCH → BLOCK
  RISK_REDUCE/NO_POSITION_INCREASE → CAUTION
  HOLD → PASS
  DQS < 55 → BLOCK (DataQualityAgent + RiskGate hard blocker)
"""
from __future__ import annotations

from app.market_state.risk_gate_view import (
    build_agent_votes,
    build_position_checks,
    build_risk_gate,
)


# ── Risk gate ────────────────────────────────────────────────────────────────


def test_kill_switch_blocks() -> None:
    g = build_risk_gate(risk_action="KILL_SWITCH", kill_switch=True, dqs_score=70)
    assert g.status == "BLOCK"
    assert g.kill_switch_active is True
    assert any("Kill switch" in b for b in g.hard_blockers)
    assert g.source_risk_action == "KILL_SWITCH"


def test_low_dqs_blocks_even_when_action_hold() -> None:
    g = build_risk_gate(risk_action="HOLD", dqs_score=40)
    assert g.status == "BLOCK"
    assert g.dqs_passed is False
    assert any("DQS" in b for b in g.hard_blockers)


def test_hold_passes() -> None:
    g = build_risk_gate(risk_action="HOLD", dqs_score=75)
    assert g.status == "PASS"
    assert g.dqs_passed is True
    assert not g.hard_blockers


def test_no_position_increase_is_caution() -> None:
    g = build_risk_gate(risk_action="NO_POSITION_INCREASE", dqs_score=70, regime="DEFENSIVE")
    assert g.status == "CAUTION"
    assert g.no_position_increase is True


def test_risk_reduce_is_caution() -> None:
    g = build_risk_gate(risk_action="RISK_REDUCE", dqs_score=70, regime="CRISIS")
    assert g.status == "CAUTION"
    assert g.risk_reduce is True


def test_high_contradiction_warns() -> None:
    g = build_risk_gate(risk_action="HOLD", dqs_score=75, contradiction_score=85)
    assert g.status == "CAUTION"
    assert any("Çelişki" in b for b in g.hard_blockers)


def test_block_reason_with_hold_promotes_to_caution() -> None:
    g = build_risk_gate(risk_action="HOLD", dqs_score=75, block_reason="TF karşıt")
    # mevcut block_reason "trade yok" demek → en azından CAUTION
    assert g.status == "CAUTION"
    assert "TF karşıt" in g.reason


# ── Agent votes ──────────────────────────────────────────────────────────────


def test_votes_kill_switch_block() -> None:
    votes = build_agent_votes(risk_action="KILL_SWITCH", kill_switch=True, dqs_score=70)
    risk = next(v for v in votes if v.agent_name == "RiskAgent")
    assert risk.vote == "BLOCK"


def test_votes_dqs_block() -> None:
    votes = build_agent_votes(risk_action="HOLD", dqs_score=30)
    dq = next(v for v in votes if v.agent_name == "DataQualityAgent")
    assert dq.vote == "BLOCK"


def test_votes_dqs_caution_band() -> None:
    votes = build_agent_votes(risk_action="HOLD", dqs_score=60)
    dq = next(v for v in votes if v.agent_name == "DataQualityAgent")
    assert dq.vote == "CAUTION"


def test_votes_dqs_allow() -> None:
    votes = build_agent_votes(risk_action="HOLD", dqs_score=85)
    dq = next(v for v in votes if v.agent_name == "DataQualityAgent")
    assert dq.vote == "ALLOW"


def test_votes_dqs_abstain_when_unknown() -> None:
    votes = build_agent_votes(risk_action="HOLD", dqs_score=None)
    dq = next(v for v in votes if v.agent_name == "DataQualityAgent")
    assert dq.vote == "ABSTAIN"


def test_votes_tf_divergent_blocks_technical() -> None:
    votes = build_agent_votes(
        risk_action="HOLD", dqs_score=80,
        tf_alignment_label="divergent", tf_alignment_detail="0/3 KARŞIT", side="LONG",
    )
    tech = next(v for v in votes if v.agent_name == "TechnicalAgent")
    assert tech.vote == "BLOCK"


def test_votes_tf_strong_allows() -> None:
    votes = build_agent_votes(
        risk_action="HOLD", dqs_score=80,
        tf_alignment_label="strong", side="LONG", confidence=72.0,
    )
    tech = next(v for v in votes if v.agent_name == "TechnicalAgent")
    assert tech.vote == "ALLOW"
    assert tech.direction == "LONG_BIAS"


def test_votes_high_contradiction_blocks() -> None:
    votes = build_agent_votes(risk_action="HOLD", dqs_score=80, contradiction_score=85)
    cont = next(v for v in votes if v.agent_name == "ContradictionAgent")
    assert cont.vote == "BLOCK"


# ── Position checks ──────────────────────────────────────────────────────────


def test_position_checks_hard_failures_are_blockers() -> None:
    checks = build_position_checks({
        "kill_switch_off":           False,
        "dqs_passed":                True,
        "rr_after_add_valid":        False,
        "max_position_size_passed":  True,
        "stop_distance_safe":        False,   # soft → WARNING (hard listede değil)
        "average_entry_valid":       True,
        "not_too_close_to_stop":     True,
        "contradiction_acceptable":  True,
        "paper_mode_allowed":        True,
    })
    by_name = {c.check_name: c for c in checks}
    assert by_name["kill_switch_off"].severity   == "BLOCKER"
    assert by_name["rr_after_add_valid"].severity == "BLOCKER"
    # stop_distance_safe hard listede değil → WARNING
    assert by_name["stop_distance_safe"].severity == "WARNING"
    # geçen check'ler INFO
    assert by_name["dqs_passed"].severity == "INFO"


def test_position_checks_empty_or_none() -> None:
    assert build_position_checks(None) == []
    assert build_position_checks({}) == []
