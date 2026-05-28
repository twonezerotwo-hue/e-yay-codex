
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotSourceFreshnessDecayTimelineEntry:
    snapshot_id: str
    created_at: str
    freshness_status: str
    fresh_source_count: int
    stale_source_count: int
    missing_timestamp_source_count: int
    degraded_source_count: int
    total_active_sources: int
    decay_score: int | None
    diagnostic: str | None

@dataclass(frozen=True)
class SnapshotSourceFreshnessDecayTimeline:
    decay_classification: str
    total_snapshots: int
    evaluable_snapshots: int
    missing_freshness_snapshots: int
    first_status: str | None
    latest_status: str | None
    dominant_status: str | None
    worst_status: str | None
    transition_count: int
    decay_score_delta: int
    entries: tuple[SnapshotSourceFreshnessDecayTimelineEntry, ...]
    failures: tuple[dict[str, str], ...]
    total_snapshots_requested: int
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationCadenceEntry:
    snapshot_id: str
    created_at: str
    cadence_status: str
    anchor_observed_at: str | None
    observed_source_count: int
    missing_timestamp_source_count: int
    interval_seconds_from_previous: int | None
    cadence_score: int | None
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationCadenceDrift:
    cadence_classification: str
    cadence_score: int
    severity_bucket: str
    total_snapshots_requested: int
    snapshots_checked: int
    evaluable_snapshots: int
    missing_timestamp_snapshots: int
    transition_count: int
    entries: tuple[SnapshotSourceObservationCadenceEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationTimestampIntegrityDriftEntry:
    snapshot_id: str
    created_at: str
    integrity_classification: str
    integrity_score: float
    total_records: int
    valid_records: int
    missing_timestamp_source_ids: tuple[str, ...]
    sequence_violation_source_ids: tuple[str, ...]
    mapped_time_regression_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationTimestampIntegrityDrift:
    drift_classification: str
    average_integrity_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    missing_timestamp_source_ids: tuple[str, ...]
    sequence_violation_source_ids: tuple[str, ...]
    mapped_time_regression_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceObservationTimestampIntegrityDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationNormalizationModeDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    normalization_mode: str | None
    previous_normalization_mode: str | None
    mode_consistency_score: float
    total_bound_sources: int | None
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationNormalizationModeDrift:
    drift_classification: str
    average_mode_consistency_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    dominant_normalization_mode: str | None
    latest_normalization_mode: str | None
    normalization_mode_counts: dict[str, int]
    mode_transition_count: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceObservationNormalizationModeDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotMappedAtAlignmentConsistencyEntry:
    snapshot_id: str
    created_at: str
    consistency_classification: str
    consistency_percentage: float
    normalization_mode: str | None
    batch_anchor: str | None
    total_records: int
    aligned_records: int
    missing_mapped_at_source_ids: tuple[str, ...]
    batch_anchor_mismatch_source_ids: tuple[str, ...]
    stored_at_alignment_mismatch_source_ids: tuple[str, ...]
    source_observation_alignment_mismatch_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotMappedAtAlignmentConsistency:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_mapped_at_source_ids: tuple[str, ...]
    batch_anchor_mismatch_source_ids: tuple[str, ...]
    stored_at_alignment_mismatch_source_ids: tuple[str, ...]
    source_observation_alignment_mismatch_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotMappedAtAlignmentConsistencyEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationAvailabilityLagDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    average_lag_seconds: float
    previous_average_lag_seconds: float | None
    lag_delta_from_previous_seconds: float | None
    total_records: int
    valid_lag_records: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_timestamp_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationAvailabilityLagDrift:
    drift_classification: str
    average_lag_seconds: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_timestamp_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceObservationAvailabilityLagDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceFreshnessSummaryReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    total_records: int
    aligned_records: int
    record_stale_source_count: int
    summary_stale_source_count: int
    record_degraded_source_count: int
    record_fresh_source_count: int
    missing_freshness_source_ids: tuple[str, ...]
    record_only_stale_source_ids: tuple[str, ...]
    summary_only_stale_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceFreshnessSummaryReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_freshness_source_ids: tuple[str, ...]
    record_only_stale_source_ids: tuple[str, ...]
    summary_only_stale_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceFreshnessSummaryReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceFreshnessPolicyDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    policy_score: float
    previous_policy_score: float | None
    policy_score_delta: float | None
    total_active_sources: int
    fresh_source_count: int
    stale_source_count: int
    missing_timestamp_source_count: int
    not_evaluated_source_count: int
    evaluation_mode: str | None
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceFreshnessPolicyDrift:
    drift_classification: str
    average_policy_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    evaluation_mode_changes: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceFreshnessPolicyDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotStaleSourceListThresholdReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    total_active_sources: int
    aligned_sources: int
    threshold_stale_source_count: int
    persisted_stale_source_count: int
    missing_timestamp_source_ids: tuple[str, ...]
    threshold_mismatch_source_ids: tuple[str, ...]
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotStaleSourceListThresholdReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_timestamp_source_ids: tuple[str, ...]
    threshold_mismatch_source_ids: tuple[str, ...]
    malformed_field_count: int
    entries: tuple[SnapshotStaleSourceListThresholdReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    freshness_evaluation_mode: str | None
    previous_freshness_evaluation_mode: str | None
    mode_consistency_score: float
    total_features: int
    features_with_stale_sources: int
    total_stale_assets: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift:
    drift_classification: str
    average_mode_consistency_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    dominant_freshness_evaluation_mode: str | None
    latest_freshness_evaluation_mode: str | None
    freshness_evaluation_mode_counts: dict[str, int]
    mode_transition_count: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationFreshnessSecondsDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    average_freshness_seconds: float
    previous_average_freshness_seconds: float | None
    freshness_delta_from_previous_seconds: float | None
    total_records: int
    valid_freshness_records: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_freshness_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationFreshnessSecondsDrift:
    drift_classification: str
    average_freshness_seconds: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_freshness_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceObservationFreshnessSecondsDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceFreshnessStatusThresholdReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    total_records: int
    aligned_records: int
    fresh_threshold_source_count: int
    degraded_threshold_source_count: int
    stale_threshold_source_count: int
    missing_freshness_status_source_ids: tuple[str, ...]
    threshold_mismatch_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceFreshnessStatusThresholdReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_freshness_status_source_ids: tuple[str, ...]
    threshold_mismatch_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceFreshnessStatusThresholdReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

__all__ = [
    "SnapshotSourceFreshnessDecayTimelineEntry",
    "SnapshotSourceFreshnessDecayTimeline",
    "SnapshotSourceObservationCadenceEntry",
    "SnapshotSourceObservationCadenceDrift",
    "SnapshotSourceObservationTimestampIntegrityDriftEntry",
    "SnapshotSourceObservationTimestampIntegrityDrift",
    "SnapshotSourceObservationNormalizationModeDriftEntry",
    "SnapshotSourceObservationNormalizationModeDrift",
    "SnapshotMappedAtAlignmentConsistencyEntry",
    "SnapshotMappedAtAlignmentConsistency",
    "SnapshotSourceObservationAvailabilityLagDriftEntry",
    "SnapshotSourceObservationAvailabilityLagDrift",
    "SnapshotSourceFreshnessSummaryReconciliationEntry",
    "SnapshotSourceFreshnessSummaryReconciliation",
    "SnapshotSourceFreshnessPolicyDriftEntry",
    "SnapshotSourceFreshnessPolicyDrift",
    "SnapshotStaleSourceListThresholdReconciliationEntry",
    "SnapshotStaleSourceListThresholdReconciliation",
    "SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry",
    "SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift",
    "SnapshotSourceObservationFreshnessSecondsDriftEntry",
    "SnapshotSourceObservationFreshnessSecondsDrift",
    "SnapshotSourceFreshnessStatusThresholdReconciliationEntry",
    "SnapshotSourceFreshnessStatusThresholdReconciliation",
]
