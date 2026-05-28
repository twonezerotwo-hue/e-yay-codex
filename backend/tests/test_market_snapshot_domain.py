from datetime import UTC, datetime
from datetime import timedelta

import pytest

from app.domain import AssetCode
from app.domain import MarketSnapshot
from app.domain import SourceTier


def test_market_snapshot_domain_model_accepts_valid_payload() -> None:
    observed_at = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
    available_at = observed_at + timedelta(minutes=5)
    stored_at = available_at + timedelta(minutes=2)

    snapshot = MarketSnapshot(
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
        data_quality_score=88.75,
        raw_payload_ref="s3://snapshots/btcusd/20260519T100000Z.json",
    )

    assert snapshot.asset_symbol == AssetCode.BTCUSD
    assert snapshot.source_tier == SourceTier.PRIMARY
    assert snapshot.freshness_seconds == 420
    assert snapshot.asset.unit == "usd_per_btc"
    assert snapshot.data_quality_score == 88.75


def test_market_snapshot_rejects_invalid_asset_symbol() -> None:
    timestamp = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        MarketSnapshot(
            asset_symbol="INVALID_ASSET",
            value=1.0,
            unit="usd",
            source_name="test_source",
            source_tier="primary",
            observed_at=timestamp,
            available_at=timestamp,
            stored_at=timestamp,
            data_quality_score=50.0,
        )


def test_market_snapshot_enforces_data_quality_score_bounds() -> None:
    timestamp = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        MarketSnapshot(
            asset_symbol="DXY",
            value=100.0,
            unit="index_points",
            source_name="approved_macro_market_feed",
            source_tier="primary",
            observed_at=timestamp,
            available_at=timestamp,
            stored_at=timestamp,
            data_quality_score=101.0,
        )

    valid_snapshot = MarketSnapshot(
        asset_symbol="DXY",
        value=100.0,
        unit="index_points",
        source_name="approved_macro_market_feed",
        source_tier="primary",
        observed_at=timestamp,
        available_at=timestamp,
        stored_at=timestamp,
        data_quality_score=0.0,
    )

    assert valid_snapshot.data_quality_score == 0.0


def test_market_snapshot_normalizes_timezone_aware_timestamps() -> None:
    observed_at = datetime.fromisoformat("2026-05-19T12:00:00+02:00")
    available_at = datetime.fromisoformat("2026-05-19T12:02:00+02:00")
    stored_at = datetime.fromisoformat("2026-05-19T12:04:00+02:00")

    snapshot = MarketSnapshot(
        asset_symbol="USCPI",
        value=3.1,
        unit="year_over_year_percent",
        source_name="approved_macro_feed",
        source_tier="secondary",
        observed_at=observed_at,
        available_at=available_at,
        stored_at=stored_at,
        freshness_seconds=240,
        is_stale=True,
        fallback_used=True,
        data_quality_score=72.5,
        raw_payload_ref=None,
    )

    assert snapshot.observed_at.tzinfo == UTC
    assert snapshot.available_at.tzinfo == UTC
    assert snapshot.stored_at.tzinfo == UTC
    assert snapshot.observed_at.isoformat() == "2026-05-19T10:00:00+00:00"
    assert snapshot.available_at.isoformat() == "2026-05-19T10:02:00+00:00"
    assert snapshot.stored_at.isoformat() == "2026-05-19T10:04:00+00:00"

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
