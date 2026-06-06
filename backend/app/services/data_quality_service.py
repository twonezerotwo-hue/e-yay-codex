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
    fallback_used: bool = False


# DÜZELTİLDİ: Çapraz doğrulama yapılmadıysa default UNVERIFIED (60), 100 değil.
# 100 vermek "gerçek doğrulama yapıldı" anlamına gelir — bu yanlış güven üretir.
_UNVERIFIED_SCORE = 60.0  # cross-provider check yapılmadı ama makul bir kaynak


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
        SourceTier.PRIMARY:   100.0,
        SourceTier.SECONDARY:  90.0,
        SourceTier.FALLBACK:   70.0,
        SourceTier.REFERENCE:  40.0,
    }
    # Fallback kullanıldığında cross-provider score cezası
    FALLBACK_CROSS_PROVIDER_SCORE = 35.0

    def calculate_snapshot_score(
        self,
        snapshot: MarketSnapshot,
        *,
        cross_provider_agreement_score: float = _UNVERIFIED_SCORE,
        anomaly_consistency_score: float = _UNVERIFIED_SCORE,
    ) -> DataQualityScoreResult:
        # Fallback kullanıldıysa cross-provider score otomatik düşür
        if snapshot.fallback_used:
            cross_provider_agreement_score = min(
                cross_provider_agreement_score, self.FALLBACK_CROSS_PROVIDER_SCORE
            )

        component_scores = {
            "freshness_score":               self._calculate_freshness_score(snapshot),
            "source_tier_score":             self._calculate_source_tier_score(snapshot),
            "cross_provider_agreement_score": self._clamp_score(cross_provider_agreement_score),
            "completeness_score":            self._calculate_completeness_score(snapshot),
            "timestamp_integrity_score":     self._calculate_timestamp_integrity_score(snapshot),
            "anomaly_consistency_score":     self._clamp_score(anomaly_consistency_score),
        }
        total_score = round(
            sum(
                component_scores[k] * w
                for k, w in self.COMPONENT_WEIGHTS.items()
            ),
            2,
        )
        return DataQualityScoreResult(
            total_score=total_score,
            decision=self.determine_decision(total_score),
            component_scores=component_scores,
            fallback_used=snapshot.fallback_used,
        )

    def calculate_from_snapshot(self, snapshot: MarketSnapshot) -> DataQualityScoreResult:
        """Convenience: snapshot'un kendi data_quality_score'unu kullanarak DQS hesapla."""
        return self.calculate_snapshot_score(snapshot)

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
        """Kademeli freshness — binary 0/100 yerine yaş bazlı bant."""
        if snapshot.is_stale:
            return 0.0
        secs = getattr(snapshot, "freshness_seconds", None)
        if secs is None:
            return 70.0   # bilinmiyor, ihtiyatlı
        if secs <= 180:    # ≤ 3 dk
            return 100.0
        if secs <= 600:    # 3–10 dk
            return 85.0
        if secs <= 1800:   # 10–30 dk
            return 70.0
        if secs <= 7200:   # 30 dk – 2 saat
            return 50.0
        return 20.0        # 2 saatten eski ama stale sayılmamış

    def _calculate_source_tier_score(self, snapshot: MarketSnapshot) -> float:
        return self.SOURCE_TIER_SCORES.get(snapshot.source_tier, 50.0)

    def _calculate_completeness_score(self, snapshot: MarketSnapshot) -> float:
        required = all(
            field is not None
            for field in (
                snapshot.asset_symbol, snapshot.unit, snapshot.source_tier,
                snapshot.observed_at, snapshot.available_at, snapshot.stored_at,
                snapshot.freshness_seconds, snapshot.value,
            )
        )
        required = required and bool(snapshot.source_name.strip()) and bool(snapshot.unit)
        return 100.0 if required else 0.0

    def _calculate_timestamp_integrity_score(self, snapshot: MarketSnapshot) -> float:
        if snapshot.observed_at <= snapshot.available_at <= snapshot.stored_at:
            return 100.0
        return 0.0

    @staticmethod
    def _clamp_score(score: float) -> float:
        return round(max(0.0, min(100.0, float(score))), 2)


# ── Live path entegrasyonu — kaynak kalite özeti ──────────────────────────

def get_data_quality_summary(snapshots: dict) -> dict:
    """
    Canlı yolda çağrılabilir: snapshot dict'inden kalite özeti üret.
    regime_report, consensus veya paper_trading response'una eklenebilir.

    Returns:
        {
            "total": int,
            "fallback_count": int,
            "fallback_assets": [...],
            "quality_score": float,    # ortalama (0-100)
            "decision": str,           # PASS / DEGRADED_PASS / ...
        }
    """
    svc = DataQualityService()
    results = []
    fallback_assets = []

    for asset, snap in snapshots.items():
        if not hasattr(snap, "fallback_used"):
            continue
        r = svc.calculate_snapshot_score(snap)
        results.append(r.total_score)
        if snap.fallback_used:
            fallback_assets.append(str(asset))

    if not results:
        return {"total": 0, "fallback_count": 0, "fallback_assets": [],
                "quality_score": 0.0, "decision": "NO_DATA"}

    avg = round(sum(results) / len(results), 1)
    return {
        "total": len(results),
        "fallback_count": len(fallback_assets),
        "fallback_assets": fallback_assets,
        "quality_score": avg,
        "decision": DataQualityService.determine_decision(avg).value,
    }


__all__ = [name for name in globals() if not name.startswith("_")]
