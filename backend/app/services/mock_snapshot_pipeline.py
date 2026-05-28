from __future__ import annotations

from dataclasses import dataclass

from app.domain import MarketSnapshot
from app.domain import list_main_assets
from app.providers import MarketProvider
from app.providers import MockMarketProvider
from app.services.data_quality_service import DataQualityDecision
from app.services.market_snapshot_service import MarketSnapshotService
from app.services.market_snapshot_service import PersistedMarketSnapshot


@dataclass(frozen=True)
class MockSnapshotPipelineResult:
    total_assets_processed: int
    successful_snapshots: int
    failed_snapshots: int
    dqs_decision_counts: dict[str, int]
    persisted_snapshots: tuple[PersistedMarketSnapshot, ...] = ()


class MockSnapshotPipeline:
    def __init__(
        self,
        snapshot_service: MarketSnapshotService,
        *,
        provider: MarketProvider | None = None,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.provider = provider or MockMarketProvider()

    def run(self) -> MockSnapshotPipelineResult:
        total_assets_processed = 0
        successful_snapshots = 0
        failed_snapshots = 0
        dqs_decision_counts = {decision.value: 0 for decision in DataQualityDecision}
        persisted_snapshots: list[PersistedMarketSnapshot] = []

        for asset in list_main_assets():
            total_assets_processed += 1
            try:
                payload = self.provider.get_asset_data(asset.code)
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
                continue

            successful_snapshots += 1
            dqs_decision_counts[persisted.dqs_result.decision.value] += 1
            persisted_snapshots.append(persisted)

        return MockSnapshotPipelineResult(
            total_assets_processed=total_assets_processed,
            successful_snapshots=successful_snapshots,
            failed_snapshots=failed_snapshots,
            dqs_decision_counts=dqs_decision_counts,
            persisted_snapshots=tuple(persisted_snapshots),
        )

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
