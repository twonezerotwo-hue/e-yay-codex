"""Owner feedback + rebalance proposal MVP testleri.

KRİTİK: Rebalance proposal otomatik aktivasyon YAPMAZ; owner approve etmeden
weights dosyası değişmez. Bu testler bu invariant'ı sabitler.
"""
from __future__ import annotations

import pytest

from app.services import owner_feedback_service as ofs


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    """Her test izole bir data dizini kullansın."""
    monkeypatch.setattr(ofs, "_DATA_DIR", tmp_path)
    monkeypatch.setattr(ofs, "_FEEDBACK_FILE",  tmp_path / "owner_feedback.jsonl")
    monkeypatch.setattr(ofs, "_PROPOSALS_FILE", tmp_path / "rebalance_proposals.jsonl")
    monkeypatch.setattr(ofs, "_WEIGHTS_FILE",   tmp_path / "weights_active.json")


def test_record_and_read_feedback() -> None:
    fb = ofs.record_owner_feedback(
        action="REJECT", reason="Dirence çok yakın",
        trade_id="t_1", asset_code="BTCUSD",
    )
    assert fb.action == "REJECT"
    assert fb.feedback_id.startswith("fb_")
    items = ofs.get_recent_feedback()
    assert len(items) == 1
    assert items[0]["asset_code"] == "BTCUSD"


def test_invalid_action_rejected() -> None:
    with pytest.raises(ValueError):
        ofs.record_owner_feedback(action="BOGUS", reason="x")


def test_proposal_requires_approval_and_does_not_change_weights() -> None:
    p = ofs.propose_rebalance(
        agent_weight_changes={"TechnicalAgent": 0.1},
        reasons=["TF strong hit-rate 72% son 30 günde"],
    )
    assert p.requires_owner_approval is True
    assert p.approved is False
    # KRİTİK: weights dosyası YOK
    assert ofs.get_active_weights() is None


def test_approve_writes_versioned_weights() -> None:
    p = ofs.propose_rebalance(
        agent_weight_changes={"TechnicalAgent": 0.1, "RiskAgent": -0.05},
        threshold_suggestions={"MIN_DQS": 60.0},
    )
    res = ofs.approve_proposal(p.proposal_id)
    assert res["status"] == "approved"
    active = ofs.get_active_weights()
    assert active is not None
    assert active["agent_weights"]["TechnicalAgent"] == 0.1
    assert active["threshold_suggestions"]["MIN_DQS"] == 60.0
    # Versionlu arşiv yazıldı mı?
    archives = list(ofs._DATA_DIR.glob("weights_v_*.json"))
    assert len(archives) == 1


def test_approve_unknown_proposal_raises() -> None:
    with pytest.raises(KeyError):
        ofs.approve_proposal("rp_does_not_exist")


def test_approve_twice_is_noop() -> None:
    p = ofs.propose_rebalance(agent_weight_changes={"X": 0.5})
    ofs.approve_proposal(p.proposal_id)
    res2 = ofs.approve_proposal(p.proposal_id)
    assert res2["status"] == "already_approved"


def test_daily_report_shape() -> None:
    ofs.record_owner_feedback(action="APPROVE", reason="iyi setup")
    ofs.record_owner_feedback(action="REJECT", reason="erken")
    ofs.propose_rebalance(reasons=["test"])
    rep = ofs.build_daily_report()
    assert "date" in rep and "action_counts" in rep
    assert rep["total_feedback_today"] >= 2
    assert "pending_proposals" in rep
    assert rep["pending_proposals"], "pending proposal görünmeli"
