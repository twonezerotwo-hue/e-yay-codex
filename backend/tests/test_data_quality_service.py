from datetime import UTC, datetime
from datetime import timedelta

from app.domain import MarketSnapshot
from app.services import DataQualityDecision
from app.services import DataQualityService


def build_snapshot(
    *,
    asset_symbol: str = "BTCUSD",
    unit: str = "usd_per_btc",
    source_tier: str = "primary",
    is_stale: bool = False,
    raw_payload_ref: str | None = None,
) -> MarketSnapshot:
    observed_at = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
    available_at = observed_at + timedelta(minutes=1)
    stored_at = available_at + timedelta(minutes=1)

    return MarketSnapshot(
        asset_symbol=asset_symbol,
        value=105000.5,
        unit=unit,
        source_name="approved_source",
        source_tier=source_tier,
        observed_at=observed_at,
        available_at=available_at,
        stored_at=stored_at,
        is_stale=is_stale,
        fallback_used=False,
        data_quality_score=100.0,
        raw_payload_ref=raw_payload_ref,
    )


def test_perfect_snapshot_returns_pass() -> None:
    result = DataQualityService().calculate_snapshot_score(build_snapshot(raw_payload_ref=None))

    assert result.total_score == 100.0
    assert result.decision == DataQualityDecision.PASS
    assert result.component_scores == {
        "freshness_score": 100.0,
        "source_tier_score": 100.0,
        "cross_provider_agreement_score": 100.0,
        "completeness_score": 100.0,
        "timestamp_integrity_score": 100.0,
        "anomaly_consistency_score": 100.0,
    }


def test_lower_source_tier_reduces_score() -> None:
    result = DataQualityService().calculate_snapshot_score(build_snapshot(source_tier="reference"))

    assert result.component_scores["source_tier_score"] == 40.0
    assert result.total_score == 88.0
    assert result.decision == DataQualityDecision.DEGRADED_PASS


def test_stale_snapshot_reduces_score() -> None:
    result = DataQualityService().calculate_snapshot_score(build_snapshot(is_stale=True))

    assert result.component_scores["freshness_score"] == 0.0
    assert result.total_score == 75.0
    assert result.decision == DataQualityDecision.DEGRADED_PASS


def test_broken_timestamp_integrity_reduces_score() -> None:
    snapshot = build_snapshot()
    object.__setattr__(snapshot, "stored_at", snapshot.available_at - timedelta(seconds=1))

    result = DataQualityService().calculate_snapshot_score(snapshot)

    assert result.component_scores["timestamp_integrity_score"] == 0.0
    assert result.total_score == 90.0
    assert result.decision == DataQualityDecision.PASS


def test_threshold_decisions_are_correct() -> None:
    service = DataQualityService()

    assert service.determine_decision(100.0) == DataQualityDecision.PASS
    assert service.determine_decision(90.0) == DataQualityDecision.PASS
    assert service.determine_decision(89.99) == DataQualityDecision.DEGRADED_PASS
    assert service.determine_decision(70.0) == DataQualityDecision.DEGRADED_PASS
    assert service.determine_decision(69.99) == DataQualityDecision.LIMITED_ANALYSIS_ONLY
    assert service.determine_decision(50.0) == DataQualityDecision.LIMITED_ANALYSIS_ONLY
    assert service.determine_decision(49.99) == DataQualityDecision.FAIL_NO_DECISION


def test_placeholder_component_scores_are_used_in_total() -> None:
    result = DataQualityService().calculate_snapshot_score(
        build_snapshot(source_tier="fallback", is_stale=True),
        cross_provider_agreement_score=70.0,
        anomaly_consistency_score=70.0,
    )

    assert result.component_scores["cross_provider_agreement_score"] == 70.0
    assert result.component_scores["anomaly_consistency_score"] == 70.0
    assert result.total_score == 60.0
    assert result.decision == DataQualityDecision.LIMITED_ANALYSIS_ONLY

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
