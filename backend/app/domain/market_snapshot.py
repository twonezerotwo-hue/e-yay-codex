from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.domain.assets import AssetCode
from app.domain.assets import AssetDefinition
from app.domain.assets import get_asset_definition


class SourceTier(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    FALLBACK = "fallback"
    REFERENCE = "reference"


def _normalize_datetime(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class MarketSnapshot:
    asset_symbol: AssetCode | str
    value: float
    unit: str
    source_name: str
    source_tier: SourceTier | str
    observed_at: datetime
    available_at: datetime
    stored_at: datetime
    freshness_seconds: int | None = None
    is_stale: bool = False
    fallback_used: bool = False
    data_quality_score: float = 100.0
    raw_payload_ref: str | None = None

    def __post_init__(self) -> None:
        asset_code = self.asset_symbol if isinstance(self.asset_symbol, AssetCode) else AssetCode(self.asset_symbol)
        asset_definition = get_asset_definition(asset_code)
        source_tier = self.source_tier if isinstance(self.source_tier, SourceTier) else SourceTier(self.source_tier)

        observed_at = _normalize_datetime(self.observed_at, "observed_at")
        available_at = _normalize_datetime(self.available_at, "available_at")
        stored_at = _normalize_datetime(self.stored_at, "stored_at")

        if not self.source_name.strip():
            raise ValueError("source_name must not be empty.")

        if self.unit != asset_definition.unit:
            raise ValueError(
                f"unit mismatch for {asset_code.value}: expected {asset_definition.unit}, got {self.unit}"
            )

        if available_at < observed_at:
            raise ValueError("available_at cannot be earlier than observed_at.")

        if stored_at < available_at:
            raise ValueError("stored_at cannot be earlier than available_at.")

        freshness_seconds = self.freshness_seconds
        if freshness_seconds is None:
            freshness_seconds = int((stored_at - observed_at).total_seconds())

        if freshness_seconds < 0:
            raise ValueError("freshness_seconds must be greater than or equal to 0.")

        data_quality_score = float(self.data_quality_score)
        if not 0.0 <= data_quality_score <= 100.0:
            raise ValueError("data_quality_score must be between 0 and 100.")

        object.__setattr__(self, "asset_symbol", asset_code)
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "source_tier", source_tier)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "available_at", available_at)
        object.__setattr__(self, "stored_at", stored_at)
        object.__setattr__(self, "freshness_seconds", int(freshness_seconds))
        object.__setattr__(self, "data_quality_score", round(data_quality_score, 2))

    @property
    def asset(self) -> AssetDefinition:
        return get_asset_definition(self.asset_symbol)

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
