from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.domain import AssetDefinition
from app.domain import MarketSnapshot
from app.domain import list_main_assets
from app.providers import VerifiedProviderAdapter
from app.providers import VerifiedProviderPayload
from app.services.data_quality_service import DataQualityDecision
from app.services.market_snapshot_service import MarketSnapshotService
from app.services.market_snapshot_service import PersistedMarketSnapshot
from app.services.source_observation_service import SourceObservationService
from app.storage import SnapshotStore


@dataclass(frozen=True)
class ProviderIngestionResult:
    total_assets_processed: int
    successful_snapshots: int
    failed_snapshots: int
    dqs_decision_counts: dict[str, int]
    persisted_snapshots: tuple[PersistedMarketSnapshot, ...]
    provider_payloads: tuple[VerifiedProviderPayload, ...]
    source_observation_persistence_payload: dict[str, object]
    failed_assets: tuple[str, ...]
    stored_snapshot_metadata: dict[str, object] | None = None


class ProviderIngestionService:
    def __init__(
        self,
        snapshot_service: MarketSnapshotService,
        provider: VerifiedProviderAdapter,
        *,
        source_observation_service: SourceObservationService | None = None,
        paper_safe_required: bool = True,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.provider = provider
        self.source_observation_service = source_observation_service or SourceObservationService()
        self.paper_safe_required = paper_safe_required

    def run(
        self,
        assets: tuple[AssetDefinition, ...] | None = None,
        *,
        persist_result: bool = False,
        snapshot_store: SnapshotStore | None = None,
        snapshot_metadata: dict[str, Any] | None = None,
    ) -> ProviderIngestionResult:
        resolved_assets = assets or list_main_assets()
        total_assets_processed = 0
        successful_snapshots = 0
        failed_snapshots = 0
        dqs_decision_counts = {decision.value: 0 for decision in DataQualityDecision}
        persisted_snapshots: list[PersistedMarketSnapshot] = []
        provider_payloads: list[VerifiedProviderPayload] = []
        failed_assets: list[str] = []

        for asset in resolved_assets:
            total_assets_processed += 1

            try:
                payload = self.provider.get_asset_data(asset.code)
                if self.paper_safe_required and not payload.paper_safe:
                    raise ValueError(f"{asset.code.value} provider payload is not paper-safe.")

                snapshot = MarketSnapshot(
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
                )
                persisted = self.snapshot_service.persist_snapshot(snapshot)
            except Exception:
                failed_snapshots += 1
                failed_assets.append(asset.code.value)
                continue

            successful_snapshots += 1
            dqs_decision_counts[persisted.dqs_result.decision.value] += 1
            provider_payloads.append(payload)
            persisted_snapshots.append(persisted)

        source_observation_persistence_payload = self.source_observation_service.build_persistence_payload(
            tuple(provider_payloads),
        )

        result = ProviderIngestionResult(
            total_assets_processed=total_assets_processed,
            successful_snapshots=successful_snapshots,
            failed_snapshots=failed_snapshots,
            dqs_decision_counts=dqs_decision_counts,
            persisted_snapshots=tuple(persisted_snapshots),
            provider_payloads=tuple(provider_payloads),
            source_observation_persistence_payload=source_observation_persistence_payload,
            failed_assets=tuple(failed_assets),
        )

        if not persist_result:
            return result

        stored_snapshot_metadata = self.persist_ingestion_result(
            result,
            snapshot_store=snapshot_store,
            snapshot_metadata=snapshot_metadata,
        )
        return replace(result, stored_snapshot_metadata=stored_snapshot_metadata)

    def persist_ingestion_result(
        self,
        ingestion_result: ProviderIngestionResult,
        *,
        snapshot_store: SnapshotStore | None,
        snapshot_metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        if snapshot_store is None:
            raise ValueError("snapshot_store is required when persistence is enabled.")

        snapshot_payload = self.build_snapshot_payload(
            ingestion_result,
            snapshot_metadata=snapshot_metadata,
        )
        return snapshot_store.save_snapshot(snapshot_payload)

    def build_snapshot_payload(
        self,
        ingestion_result: ProviderIngestionResult,
        *,
        snapshot_metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        metadata = snapshot_metadata or {}
        persistence_payload = ingestion_result.source_observation_persistence_payload
        source_observations = persistence_payload["source_observations"]

        if ingestion_result.persisted_snapshots:
            created_at = max(
                persisted.snapshot.stored_at
                for persisted in ingestion_result.persisted_snapshots
            )
        else:
            created_at = metadata.get("created_at", datetime.now(UTC))

        missing_sources = list(metadata.get("missing_sources", []))
        stale_sources = list(metadata.get("stale_sources", []))
        report_type = str(metadata.get("report_type", "provider_ingestion_paper_snapshot"))
        mode = str(metadata.get("mode", "PAPER_SAFE"))
        execution_mode = str(
            metadata.get(
                "execution_mode",
                "PAPER_ONLY" if mode == "PAPER_SAFE" else "NO_EXECUTION",
            )
        )

        snapshot_payload = {
            "snapshot_id": metadata.get("snapshot_id"),
            "created_at": created_at,
            "mode": mode,
            "source_registry_version": str(metadata.get("source_registry_version", "unknown")),
            "feature_registry_version": metadata.get("feature_registry_version"),
            "source_observations": source_observations,
            "source_observation_records": persistence_payload["records"],
            "source_observation_summary": persistence_payload["summary"],
            "missing_sources": missing_sources,
            "stale_sources": stale_sources,
            "report_type": report_type,
            "decision_permission": "NO_EXECUTION",
            "execution_mode": execution_mode,
            "snapshots": [
                self._serialize_persisted_snapshot(persisted_snapshot)
                for persisted_snapshot in sorted(
                    ingestion_result.persisted_snapshots,
                    key=lambda item: item.snapshot.asset_symbol.value,
                )
            ],
            "pipeline_summary": {
                "total_assets_processed": ingestion_result.total_assets_processed,
                "successful_snapshots": ingestion_result.successful_snapshots,
                "failed_snapshots": ingestion_result.failed_snapshots,
                "failed_assets": list(ingestion_result.failed_assets),
                "dqs_decision_counts": ingestion_result.dqs_decision_counts,
            },
        }

        optional_metadata_fields = (
            "source_binding_summary",
            "source_freshness_summary",
            "source_diagnostics_summary",
            "audit_source_payload",
        )
        for field_name in optional_metadata_fields:
            if field_name in metadata:
                snapshot_payload[field_name] = metadata[field_name]

        return snapshot_payload

    @staticmethod
    def _serialize_persisted_snapshot(
        persisted_snapshot: PersistedMarketSnapshot,
    ) -> dict[str, object]:
        snapshot = persisted_snapshot.snapshot
        dqs_result = persisted_snapshot.dqs_result

        return {
            "asset_symbol": snapshot.asset_symbol.value,
            "value": snapshot.value,
            "unit": snapshot.unit,
            "source_name": snapshot.source_name,
            "source_tier": snapshot.source_tier.value,
            "observed_at": snapshot.observed_at.isoformat(),
            "available_at": snapshot.available_at.isoformat(),
            "stored_at": snapshot.stored_at.isoformat(),
            "freshness_seconds": snapshot.freshness_seconds,
            "is_stale": snapshot.is_stale,
            "fallback_used": snapshot.fallback_used,
            "data_quality_score": snapshot.data_quality_score,
            "raw_payload_ref": snapshot.raw_payload_ref,
            "dqs_result": {
                "total_score": dqs_result.total_score,
                "decision": dqs_result.decision.value,
                "component_scores": dqs_result.component_scores,
            },
        }

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
