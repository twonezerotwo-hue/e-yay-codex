"""
Agent Confidence + Abstention — Sprint 2 / Item 15.

Agent'ın emin olmadığı yerde fazla kesin konuşmasını engeller.

Hesap (0-100):
  confidence = 0.40 * data_quality
             + 0.35 * consensus_strength    # 50'den ne kadar uzaklaştığı
             + 0.15 * module_completeness   # kaç modül skor sağladı
             + 0.10 * freshness_score       # snapshot ne kadar yeni

Eşikler:
  >= 65  → HIGH        — net görüş
  50-65  → MODERATE    — temkinli görüş
  35-50  → LOW         — uyarı + alternatif senaryo zorunlu
  < 35   → ABSTAIN     — agent görüş bildirmez; INSUFFICIENT_CONFIDENCE
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ConfidenceBand = Literal["HIGH", "MODERATE", "LOW", "ABSTAIN"]

# Eşikler
THR_HIGH     = 65.0
THR_MODERATE = 50.0
THR_LOW      = 35.0


@dataclass
class ConfidenceResult:
    confidence_pct: float
    band: ConfidenceBand
    abstain: bool
    abstention_reason: str | None
    components: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_pct":    round(self.confidence_pct, 1),
            "band":              self.band,
            "abstain":           self.abstain,
            "abstention_reason": self.abstention_reason,
            "components":        {k: round(v, 1) for k, v in self.components.items()},
        }


def _consensus_strength(consensus_score: float | None) -> float:
    """50'den uzaklık → güç. 50 → 0; 100 veya 0 → 100."""
    if consensus_score is None:
        return 0.0
    return min(100.0, abs(consensus_score - 50.0) * 2.0)


def _freshness_score(snapshot_age_seconds: float | None) -> float:
    """Snapshot ne kadar taze? (kademeli düşüş)."""
    if snapshot_age_seconds is None:
        return 50.0   # bilinmiyorsa nötr
    s = snapshot_age_seconds
    if s <= 180:    return 100.0   # ≤3 dk
    if s <= 600:    return 85.0    # ≤10 dk
    if s <= 1800:   return 60.0    # ≤30 dk
    if s <= 7200:   return 30.0    # ≤2 sa
    return 10.0


def _module_completeness(module_count: int | None, expected: int = 6) -> float:
    """Beklenen N modülden kaç tanesi skor sağladı?"""
    if not module_count or module_count <= 0:
        return 0.0
    return min(100.0, (module_count / expected) * 100.0)


def _band(score: float) -> ConfidenceBand:
    if score >= THR_HIGH:     return "HIGH"
    if score >= THR_MODERATE: return "MODERATE"
    if score >= THR_LOW:      return "LOW"
    return "ABSTAIN"


def compute(
    *,
    data_quality_score: float | None,
    consensus_score: float | None,
    consensus_status: str | None,
    module_count: int | None,
    snapshot_age_seconds: float | None,
    expected_module_count: int = 6,
) -> ConfidenceResult:
    """Confidence skorunu hesapla + ABSTAIN gerekiyorsa işaretle."""
    # INSUFFICIENT_DATA → otomatik ABSTAIN
    if consensus_status == "INSUFFICIENT_DATA":
        return ConfidenceResult(
            confidence_pct=0.0,
            band="ABSTAIN",
            abstain=True,
            abstention_reason="consensus INSUFFICIENT_DATA",
            components={
                "data_quality":       float(data_quality_score or 0.0),
                "consensus_strength": 0.0,
                "module_completeness": 0.0,
                "freshness":          _freshness_score(snapshot_age_seconds),
            },
        )

    dq        = float(data_quality_score) if data_quality_score is not None else 50.0
    cs        = _consensus_strength(consensus_score)
    mc        = _module_completeness(module_count, expected_module_count)
    fresh     = _freshness_score(snapshot_age_seconds)

    confidence = 0.40 * dq + 0.35 * cs + 0.15 * mc + 0.10 * fresh
    band = _band(confidence)

    abstain = (band == "ABSTAIN")
    reason: str | None = None
    if abstain:
        weakest = min(
            ("data_quality", dq),
            ("consensus_strength", cs),
            ("module_completeness", mc),
            ("freshness", fresh),
            key=lambda kv: kv[1],
        )
        reason = f"confidence {confidence:.1f} < {THR_LOW} (zayıf bileşen: {weakest[0]}={weakest[1]:.1f})"

    return ConfidenceResult(
        confidence_pct=confidence,
        band=band,
        abstain=abstain,
        abstention_reason=reason,
        components={
            "data_quality":        dq,
            "consensus_strength":  cs,
            "module_completeness": mc,
            "freshness":           fresh,
        },
    )


__all__ = [
    "ConfidenceResult",
    "ConfidenceBand",
    "compute",
    "THR_HIGH",
    "THR_MODERATE",
    "THR_LOW",
]
