from datetime import UTC, datetime
from datetime import timedelta

import pytest

from app.db.models import MarketSnapshotRecord
from app.domain import MarketSnapshot
from app.services import DataQualityDecision
from app.services import MarketSnapshotService


class FakeSession:
    def __init__(self, *, fail_on_commit: bool = False) -> None:
        self.fail_on_commit = fail_on_commit
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def commit(self) -> None:
        self.commit_calls += 1
        if self.fail_on_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollback_calls += 1


def build_snapshot() -> MarketSnapshot:
    observed_at = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
    available_at = observed_at + timedelta(minutes=1)
    stored_at = available_at + timedelta(minutes=1)

    return MarketSnapshot(
        asset_symbol="BTCUSD",
        value=105000.5,
        unit="usd_per_btc",
        source_name="approved_crypto_feed",
        source_tier="primary",
        observed_at=observed_at,
        available_at=available_at,
        stored_at=stored_at,
        is_stale=False,
        fallback_used=False,
        data_quality_score=0.0,
        raw_payload_ref="s3://snapshots/btcusd/latest.json",
    )


def test_snapshot_is_converted_to_db_model() -> None:
    session = FakeSession()
    result = MarketSnapshotService(session).persist_snapshot(build_snapshot())

    assert len(session.added) == 1
    record = session.added[0]
    assert isinstance(record, MarketSnapshotRecord)
    assert record.asset_symbol == "BTCUSD"
    assert record.unit == "usd_per_btc"
    assert record.source_name == "approved_crypto_feed"
    assert record.freshness_seconds == 120
    assert record.data_quality_score == 100.0
    assert result.snapshot.data_quality_score == 100.0


def test_dqs_result_is_calculated_and_applied_to_snapshot() -> None:
    session = FakeSession()
    result = MarketSnapshotService(session).persist_snapshot(
        build_snapshot(),
        cross_provider_agreement_score=70.0,
        anomaly_consistency_score=70.0,
    )

    assert result.dqs_result.total_score == 91.0
    assert result.dqs_result.decision == DataQualityDecision.PASS
    assert result.snapshot.data_quality_score == 91.0
    assert session.added[0].data_quality_score == 91.0


def test_service_adds_and_commits_session() -> None:
    session = FakeSession()

    MarketSnapshotService(session).persist_snapshot(build_snapshot())

    assert len(session.added) == 1
    assert session.commit_calls == 1
    assert session.rollback_calls == 0


def test_failed_session_is_handled_with_rollback() -> None:
    session = FakeSession(fail_on_commit=True)

    with pytest.raises(RuntimeError, match="commit failed"):
        MarketSnapshotService(session).persist_snapshot(build_snapshot())

    assert len(session.added) == 1
    assert session.commit_calls == 1
    assert session.rollback_calls == 1


def test_service_returns_snapshot_and_dqs_result() -> None:
    session = FakeSession()
    result = MarketSnapshotService(session).persist_snapshot(build_snapshot())

    assert result.snapshot.asset_symbol.value == "BTCUSD"
    assert result.dqs_result.component_scores["freshness_score"] == 100.0

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
