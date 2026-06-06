"""
Agent Self-Validator — Sprint 2 / Item 4.

Agent cevap dönmeden önce kanıtın geçerli olduğunu kendi kendine kontrol eder.

Kontroller:
  1. Snapshot freshness — verinin yaşı kabul edilebilir mi?
  2. Required fields — beklenen alanlar mevcut mu?
  3. Contract version — schema/kontrat sürümü uyumlu mu?
  4. Data quality — DQS skoru asgari eşiği geçiyor mu?
  5. Consensus status — INSUFFICIENT_DATA değil mi?

Sonuç:
  • is_valid=True  → agent serbest cevap üretebilir
  • is_valid=False → endpoint INSUFFICIENT_DATA / abstain döner

Bu modül asla cevap üretmez — sadece "geçerli mi?" sorusunu yanıtlar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Default eşikler — YAML/env'e taşınabilir ileride
DEFAULT_MAX_SNAPSHOT_AGE_S = 600     # 10 dk
DEFAULT_MIN_DATA_QUALITY   = 40.0    # DQS 0-100
DEFAULT_CONTRACT_VERSION   = "1.0_revised"


@dataclass
class ValidationResult:
    is_valid: bool
    reasons: list[str] = field(default_factory=list)
    snapshot_age_seconds: float | None = None
    data_quality_score: float | None = None
    contract_version: str | None = None
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid":              self.is_valid,
            "reasons":               list(self.reasons),
            "snapshot_age_seconds":  self.snapshot_age_seconds,
            "data_quality_score":    self.data_quality_score,
            "contract_version":      self.contract_version,
            "missing_fields":        list(self.missing_fields),
        }


def _snapshot_age_seconds(snapshot_at: str | None) -> float | None:
    if not snapshot_at:
        return None
    try:
        ts = datetime.fromisoformat(snapshot_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return (datetime.now(UTC) - ts).total_seconds()
    except Exception:
        return None


def validate(
    *,
    snapshot_at: str | None = None,
    required_fields: dict[str, Any] | None = None,
    contract_version: str | None = None,
    data_quality_score: float | None = None,
    consensus_status: str | None = None,
    max_snapshot_age_s: int = DEFAULT_MAX_SNAPSHOT_AGE_S,
    min_data_quality: float = DEFAULT_MIN_DATA_QUALITY,
    expected_contract_version: str = DEFAULT_CONTRACT_VERSION,
) -> ValidationResult:
    """Tüm kontrolleri tek seferde yürüt, agg result döndür."""
    reasons: list[str] = []
    missing: list[str] = []

    # 1) Freshness
    age = _snapshot_age_seconds(snapshot_at)
    if age is None and snapshot_at is not None:
        reasons.append("snapshot_at parse edilemedi")
    elif age is not None and age > max_snapshot_age_s:
        reasons.append(
            f"snapshot stale: {age:.0f}s > limit {max_snapshot_age_s}s"
        )

    # 2) Required fields — None veya boş kabul edilmez
    if required_fields:
        for key, value in required_fields.items():
            if value is None or (isinstance(value, (list, dict, str)) and len(value) == 0):
                missing.append(key)
        if missing:
            reasons.append(f"eksik alanlar: {missing}")

    # 3) Contract version
    if contract_version is not None and contract_version != expected_contract_version:
        reasons.append(
            f"contract_version mismatch: got '{contract_version}', expected '{expected_contract_version}'"
        )

    # 4) Data quality threshold
    if data_quality_score is not None and data_quality_score < min_data_quality:
        reasons.append(
            f"data_quality {data_quality_score:.1f} < min {min_data_quality:.1f}"
        )

    # 5) Consensus status
    if consensus_status == "INSUFFICIENT_DATA":
        reasons.append("consensus status INSUFFICIENT_DATA")

    return ValidationResult(
        is_valid=(len(reasons) == 0),
        reasons=reasons,
        snapshot_age_seconds=age,
        data_quality_score=data_quality_score,
        contract_version=contract_version,
        missing_fields=missing,
    )


__all__ = [
    "ValidationResult",
    "validate",
    "DEFAULT_MAX_SNAPSHOT_AGE_S",
    "DEFAULT_MIN_DATA_QUALITY",
    "DEFAULT_CONTRACT_VERSION",
]
