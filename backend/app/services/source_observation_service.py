from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.providers.verified_adapter import VerifiedProviderPayload


@dataclass(frozen=True)
class SourceObservationRecord:
    source_id: str
    asset_symbol: str
    registry_provider: str
    observed_at: datetime
    available_at: datetime
    stored_at: datetime
    mapped_at: datetime
    verified: bool
    decision_usage: str
    paper_safe: bool


class SourceObservationService:
    def build_records(
        self,
        provider_payloads: list[VerifiedProviderPayload] | tuple[VerifiedProviderPayload, ...],
        *,
        normalize_to_batch_time: bool = True,
    ) -> tuple[SourceObservationRecord, ...]:
        if not provider_payloads:
            return ()

        batch_time = max(payload.stored_at for payload in provider_payloads)
        records: list[SourceObservationRecord] = []

        for payload in provider_payloads:
            mapped_at = batch_time if normalize_to_batch_time else payload.stored_at
            records.append(
                SourceObservationRecord(
                    source_id=payload.source_id,
                    asset_symbol=payload.asset_symbol.value,
                    registry_provider=payload.registry_provider,
                    observed_at=payload.observed_at,
                    available_at=payload.available_at,
                    stored_at=payload.stored_at,
                    mapped_at=mapped_at,
                    verified=payload.verified,
                    decision_usage=payload.decision_usage,
                    paper_safe=payload.paper_safe,
                )
            )

        return tuple(records)

    def build_source_observations(
        self,
        provider_payloads: list[VerifiedProviderPayload] | tuple[VerifiedProviderPayload, ...],
        *,
        normalize_to_batch_time: bool = True,
    ) -> dict[str, datetime]:
        source_observations: dict[str, datetime] = {}

        for record in self.build_records(provider_payloads, normalize_to_batch_time=normalize_to_batch_time):
            current_value = source_observations.get(record.source_id)
            if current_value is None or record.mapped_at > current_value:
                source_observations[record.source_id] = record.mapped_at

        return source_observations

    def build_mapping_summary(
        self,
        records: list[SourceObservationRecord] | tuple[SourceObservationRecord, ...],
        *,
        normalize_to_batch_time: bool = True,
    ) -> dict[str, object]:
        return {
            "contract": "verified_provider_adapter_v1",
            "normalization_mode": "batch_stored_at" if normalize_to_batch_time else "per_source_stored_at",
            "total_bound_sources": len(records),
            "verified_sources": sum(1 for record in records if record.verified),
            "simulation_only_sources": sum(1 for record in records if record.decision_usage == "simulation_only"),
            "paper_safe_sources": sum(1 for record in records if record.paper_safe),
        }

    def build_persistence_payload(
        self,
        provider_payloads: list[VerifiedProviderPayload] | tuple[VerifiedProviderPayload, ...],
        *,
        normalize_to_batch_time: bool = True,
    ) -> dict[str, object]:
        records = self.build_records(
            provider_payloads,
            normalize_to_batch_time=normalize_to_batch_time,
        )
        source_observations = self.build_source_observations(
            provider_payloads,
            normalize_to_batch_time=normalize_to_batch_time,
        )

        return {
            "summary": self.build_mapping_summary(
                records,
                normalize_to_batch_time=normalize_to_batch_time,
            ),
            "records": [
                {
                    "source_id": record.source_id,
                    "asset_symbol": record.asset_symbol,
                    "registry_provider": record.registry_provider,
                    "observed_at": record.observed_at.isoformat(),
                    "available_at": record.available_at.isoformat(),
                    "stored_at": record.stored_at.isoformat(),
                    "mapped_at": record.mapped_at.isoformat(),
                    "verified": record.verified,
                    "decision_usage": record.decision_usage,
                    "paper_safe": record.paper_safe,
                }
                for record in records
            ],
            "source_observations": {
                source_id: observed_at.isoformat()
                for source_id, observed_at in source_observations.items()
            },
        }

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
