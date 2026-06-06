from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from sqlalchemy.orm import Session

from app.db.models import MarketSnapshotRecord
from app.domain import MarketSnapshot
from app.services.data_quality_service import DataQualityScoreResult
from app.services.data_quality_service import DataQualityService


@dataclass(frozen=True)
class PersistedMarketSnapshot:
    snapshot: MarketSnapshot
    dqs_result: DataQualityScoreResult


class MarketSnapshotService:
    def __init__(
        self,
        session: Session,
        *,
        data_quality_service: DataQualityService | None = None,
    ) -> None:
        self.session = session
        self.data_quality_service = data_quality_service or DataQualityService()

    def build_record(self, snapshot: MarketSnapshot) -> MarketSnapshotRecord:
        return MarketSnapshotRecord(
            asset_symbol=snapshot.asset_symbol.value,
            value=snapshot.value,
            unit=snapshot.unit,
            source_name=snapshot.source_name,
            source_tier=snapshot.source_tier.value,
            observed_at=snapshot.observed_at,
            available_at=snapshot.available_at,
            stored_at=snapshot.stored_at,
            freshness_seconds=snapshot.freshness_seconds,
            is_stale=snapshot.is_stale,
            fallback_used=snapshot.fallback_used,
            data_quality_score=snapshot.data_quality_score,
            raw_payload_ref=snapshot.raw_payload_ref,
        )

    def persist_snapshot(
        self,
        snapshot: MarketSnapshot,
        *,
        cross_provider_agreement_score: float = 100.0,
        anomaly_consistency_score: float = 100.0,
    ) -> PersistedMarketSnapshot:
        dqs_result = self.data_quality_service.calculate_snapshot_score(
            snapshot,
            cross_provider_agreement_score=cross_provider_agreement_score,
            anomaly_consistency_score=anomaly_consistency_score,
        )
        scored_snapshot = replace(snapshot, data_quality_score=dqs_result.total_score)
        record = self.build_record(scored_snapshot)

        try:
            self.session.add(record)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        return PersistedMarketSnapshot(
            snapshot=scored_snapshot,
            dqs_result=dqs_result,
        )

__all__ = [name for name in globals() if not name.startswith('_')]
