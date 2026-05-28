from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Integer, String

from app.db.base import Base
from app.db.models import MarketSnapshotRecord


def test_market_snapshot_model_imports() -> None:
    assert MarketSnapshotRecord.__name__ == "MarketSnapshotRecord"
    assert MarketSnapshotRecord.__tablename__ == "market_snapshots"


def test_market_snapshots_table_exists_in_metadata() -> None:
    assert "market_snapshots" in Base.metadata.tables


def test_market_snapshot_columns_match_expected_schema() -> None:
    table = Base.metadata.tables["market_snapshots"]

    assert isinstance(table.c.id.type, Integer)
    assert table.c.id.primary_key is True
    assert isinstance(table.c.asset_symbol.type, String)
    assert isinstance(table.c.value.type, Float)
    assert isinstance(table.c.unit.type, String)
    assert isinstance(table.c.source_name.type, String)
    assert isinstance(table.c.source_tier.type, String)
    assert isinstance(table.c.observed_at.type, DateTime)
    assert table.c.observed_at.type.timezone is True
    assert isinstance(table.c.available_at.type, DateTime)
    assert table.c.available_at.type.timezone is True
    assert isinstance(table.c.stored_at.type, DateTime)
    assert table.c.stored_at.type.timezone is True
    assert isinstance(table.c.freshness_seconds.type, Integer)
    assert isinstance(table.c.is_stale.type, Boolean)
    assert isinstance(table.c.fallback_used.type, Boolean)
    assert isinstance(table.c.data_quality_score.type, Float)
    assert table.c.raw_payload_ref.nullable is True


def test_market_snapshot_constraints_are_registered() -> None:
    table = Base.metadata.tables["market_snapshots"]
    check_constraint_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert check_constraint_names == {
        "ck_market_snapshots_data_quality_score",
        "ck_market_snapshots_freshness_seconds",
    }

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
