from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain import MarketSnapshot
from app.domain import SourceTier


class DataQualityDecision(str, Enum):
    PASS = "PASS"
    DEGRADED_PASS = "DEGRADED_PASS"
    LIMITED_ANALYSIS_ONLY = "LIMITED_ANALYSIS_ONLY"
    FAIL_NO_DECISION = "FAIL_NO_DECISION"


@dataclass(frozen=True)
class DataQualityScoreResult:
    total_score: float
    decision: DataQualityDecision
    component_scores: dict[str, float]


class DataQualityService:
    COMPONENT_WEIGHTS = {
        "freshness_score": 0.25,
        "source_tier_score": 0.20,
        "cross_provider_agreement_score": 0.20,
        "completeness_score": 0.15,
        "timestamp_integrity_score": 0.10,
        "anomaly_consistency_score": 0.10,
    }
    SOURCE_TIER_SCORES = {
        SourceTier.PRIMARY: 100.0,
        SourceTier.SECONDARY: 90.0,
        SourceTier.FALLBACK: 70.0,
        SourceTier.REFERENCE: 40.0,
    }

    def calculate_snapshot_score(
        self,
        snapshot: MarketSnapshot,
        *,
        cross_provider_agreement_score: float = 100.0,
        anomaly_consistency_score: float = 100.0,
    ) -> DataQualityScoreResult:
        component_scores = {
            "freshness_score": self._calculate_freshness_score(snapshot),
            "source_tier_score": self._calculate_source_tier_score(snapshot),
            "cross_provider_agreement_score": self._clamp_score(cross_provider_agreement_score),
            "completeness_score": self._calculate_completeness_score(snapshot),
            "timestamp_integrity_score": self._calculate_timestamp_integrity_score(snapshot),
            "anomaly_consistency_score": self._clamp_score(anomaly_consistency_score),
        }
        total_score = round(
            sum(
                component_scores[component_name] * weight
                for component_name, weight in self.COMPONENT_WEIGHTS.items()
            ),
            2,
        )
        return DataQualityScoreResult(
            total_score=total_score,
            decision=self.determine_decision(total_score),
            component_scores=component_scores,
        )

    @staticmethod
    def determine_decision(total_score: float) -> DataQualityDecision:
        if total_score >= 90.0:
            return DataQualityDecision.PASS
        if total_score >= 70.0:
            return DataQualityDecision.DEGRADED_PASS
        if total_score >= 50.0:
            return DataQualityDecision.LIMITED_ANALYSIS_ONLY
        return DataQualityDecision.FAIL_NO_DECISION

    def _calculate_freshness_score(self, snapshot: MarketSnapshot) -> float:
        return 0.0 if snapshot.is_stale else 100.0

    def _calculate_source_tier_score(self, snapshot: MarketSnapshot) -> float:
        return self.SOURCE_TIER_SCORES[snapshot.source_tier]

    def _calculate_completeness_score(self, snapshot: MarketSnapshot) -> float:
        required_fields_present = all(
            field is not None
            for field in (
                snapshot.asset_symbol,
                snapshot.unit,
                snapshot.source_tier,
                snapshot.observed_at,
                snapshot.available_at,
                snapshot.stored_at,
                snapshot.freshness_seconds,
                snapshot.value,
            )
        )
        required_fields_present = required_fields_present and bool(snapshot.source_name.strip()) and bool(snapshot.unit)
        return 100.0 if required_fields_present else 0.0

    def _calculate_timestamp_integrity_score(self, snapshot: MarketSnapshot) -> float:
        if snapshot.observed_at <= snapshot.available_at <= snapshot.stored_at:
            return 100.0
        return 0.0

    @staticmethod
    def _clamp_score(score: float) -> float:
        return round(max(0.0, min(100.0, float(score))), 2)

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
