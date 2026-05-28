from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.domain import AssetCode
from app.domain import SourceTier
from app.providers.base import MarketProvider


@dataclass(frozen=True)
class ProviderSourceBinding:
    asset_symbol: AssetCode | str
    source_id: str
    registry_provider: str
    verified: bool
    decision_usage: str
    active: bool
    paper_safe: bool = True

    def __post_init__(self) -> None:
        asset_code = self.asset_symbol if isinstance(self.asset_symbol, AssetCode) else AssetCode(self.asset_symbol)

        if not self.source_id.strip():
            raise ValueError("source_id must not be empty.")

        if not self.registry_provider.strip():
            raise ValueError("registry_provider must not be empty.")

        object.__setattr__(self, "asset_symbol", asset_code)


@dataclass(frozen=True)
class VerifiedProviderPayload:
    asset_symbol: AssetCode
    value: float
    unit: str
    source_name: str
    source_tier: SourceTier
    observed_at: datetime
    available_at: datetime
    stored_at: datetime
    source_id: str
    registry_provider: str
    verified: bool
    decision_usage: str
    paper_safe: bool
    fallback_used: bool = False
    raw_payload_ref: str | None = None


class VerifiedProviderAdapter(MarketProvider, ABC):
    @abstractmethod
    def list_bindings(self) -> tuple[ProviderSourceBinding, ...]:
        raise NotImplementedError

    @abstractmethod
    def get_asset_data(self, asset_symbol: AssetCode | str) -> VerifiedProviderPayload:
        raise NotImplementedError


class SourceRegistryBoundProviderAdapter(VerifiedProviderAdapter):
    def __init__(
        self,
        provider: MarketProvider,
        source_bindings: dict[AssetCode | str, ProviderSourceBinding],
    ) -> None:
        self.provider = provider
        self._source_bindings = {
            binding.asset_symbol if isinstance(binding.asset_symbol, AssetCode) else AssetCode(binding.asset_symbol): binding
            for binding in source_bindings.values()
        }

    def list_bindings(self) -> tuple[ProviderSourceBinding, ...]:
        return tuple(self._source_bindings[asset_code] for asset_code in sorted(self._source_bindings, key=lambda item: item.value))

    def get_asset_data(self, asset_symbol: AssetCode | str) -> VerifiedProviderPayload:
        asset_code = asset_symbol if isinstance(asset_symbol, AssetCode) else AssetCode(asset_symbol)
        binding = self._source_bindings.get(asset_code)

        if binding is None:
            raise ValueError(f"No source binding configured for {asset_code.value}.")

        if not binding.active:
            raise ValueError(f"Source binding for {asset_code.value} is inactive.")

        payload = self.provider.get_asset_data(asset_code)
        return VerifiedProviderPayload(
            asset_symbol=payload.asset_symbol,
            value=payload.value,
            unit=payload.unit,
            source_name=payload.source_name,
            source_tier=payload.source_tier,
            observed_at=payload.observed_at,
            available_at=payload.available_at,
            stored_at=payload.stored_at,
            fallback_used=payload.fallback_used,
            raw_payload_ref=payload.raw_payload_ref,
            source_id=binding.source_id,
            registry_provider=binding.registry_provider,
            verified=binding.verified,
            decision_usage=binding.decision_usage,
            paper_safe=binding.paper_safe,
        )


def build_provider_source_bindings(source_registry_entries: Iterable[object]) -> dict[str, ProviderSourceBinding]:
    bindings: dict[str, ProviderSourceBinding] = {}

    for entry in source_registry_entries:
        bindings[entry.asset.code.value] = ProviderSourceBinding(
            asset_symbol=entry.asset.code,
            source_id=entry.source_id,
            registry_provider=entry.provider,
            verified=entry.verified,
            decision_usage=entry.decision_usage,
            active=entry.active,
            paper_safe=entry.active and (entry.verified or entry.decision_usage == "simulation_only"),
        )

    return bindings

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
