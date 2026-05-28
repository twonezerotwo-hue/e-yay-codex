"""create market snapshots

Revision ID: 20260519_0002
Revises: 20260518_0001
Create Date: 2026-05-19 11:27:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260519_0002"
down_revision: str | None = "20260518_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_symbol", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_tier", sa.String(length=50), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_seconds", sa.Integer(), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("data_quality_score", sa.Float(), nullable=False),
        sa.Column("raw_payload_ref", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "data_quality_score >= 0 AND data_quality_score <= 100",
            name="ck_market_snapshots_data_quality_score",
        ),
        sa.CheckConstraint(
            "freshness_seconds >= 0",
            name="ck_market_snapshots_freshness_seconds",
        ),
    )


def downgrade() -> None:
    op.drop_table("market_snapshots")

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
