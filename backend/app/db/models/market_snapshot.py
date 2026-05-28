from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketSnapshotRecord(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        CheckConstraint(
            "data_quality_score >= 0 AND data_quality_score <= 100",
            name="ck_market_snapshots_data_quality_score",
        ),
        CheckConstraint(
            "freshness_seconds >= 0",
            name="ck_market_snapshots_freshness_seconds",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_tier: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    raw_payload_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
