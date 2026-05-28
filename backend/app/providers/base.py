from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.domain import AssetCode
from app.domain import SourceTier


@dataclass(frozen=True)
class MarketProviderPayload:
    asset_symbol: AssetCode
    value: float
    unit: str
    source_name: str
    source_tier: SourceTier
    observed_at: datetime
    available_at: datetime
    stored_at: datetime
    fallback_used: bool = False
    raw_payload_ref: str | None = None


class MarketProvider(ABC):
    @abstractmethod
    def get_asset_data(self, asset_symbol: AssetCode | str) -> MarketProviderPayload:
        raise NotImplementedError

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
