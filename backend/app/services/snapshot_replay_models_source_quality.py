
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotRawPayloadReferenceCompletenessEntry:
    snapshot_id: str
    created_at: str
    completeness_classification: str
    completeness_percentage: float
    total_records: int
    complete_records: int
    partial_reference_assets: tuple[str, ...]
    missing_reference_assets: tuple[str, ...]
    empty_reference_assets: tuple[str, ...]
    malformed_reference_assets: tuple[str, ...]
    diagnostic: str

@dataclass(frozen=True)
class SnapshotRawPayloadReferenceCompleteness:
    completeness_classification: str
    average_completeness_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    complete_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_reference_assets: tuple[str, ...]
    empty_reference_assets: tuple[str, ...]
    malformed_reference_assets: tuple[str, ...]
    entries: tuple[SnapshotRawPayloadReferenceCompletenessEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceRecordCompletenessEntry:
    snapshot_id: str
    created_at: str
    completeness_classification: str
    completeness_percentage: float
    total_records: int
    complete_records: int
    missing_field_counts: dict[str, int]
    missing_field_diagnostics: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceRecordCompleteness:
    completeness_classification: str
    average_completeness_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    complete_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    aggregate_missing_field_counts: dict[str, int]
    malformed_record_count: int
    missing_field_diagnostics: tuple[str, ...]
    entries: tuple[SnapshotSourceRecordCompletenessEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDecisionUsageConsistencyEntry:
    snapshot_id: str
    created_at: str
    consistency_classification: str
    consistency_percentage: float
    total_records: int
    consistent_records: int
    decision_usage_counts: dict[str, int]
    mismatched_source_ids: tuple[str, ...]
    unsafe_source_ids: tuple[str, ...]
    unknown_registry_source_ids: tuple[str, ...]
    missing_decision_usage_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDecisionUsageConsistency:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    aggregate_decision_usage_counts: dict[str, int]
    mismatched_source_ids: tuple[str, ...]
    unsafe_source_ids: tuple[str, ...]
    unknown_registry_source_ids: tuple[str, ...]
    missing_decision_usage_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceDecisionUsageConsistencyEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationRecordSummaryReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    record_total_bound_sources: int
    summary_total_bound_sources: int | None
    record_verified_sources: int
    summary_verified_sources: int | None
    record_simulation_only_sources: int
    summary_simulation_only_sources: int | None
    record_paper_safe_sources: int
    summary_paper_safe_sources: int | None
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationRecordSummaryReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceObservationRecordSummaryReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotVerifiedSourceCoverageReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    coverage_percentage: float
    expected_verified_source_count: int
    observed_verified_source_count: int
    matched_verified_source_count: int
    missing_verified_source_ids: tuple[str, ...]
    unexpected_verified_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotVerifiedSourceCoverageReconciliation:
    consistency_classification: str
    average_coverage_percentage: float
    expected_verified_source_count: int
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_verified_source_ids: tuple[str, ...]
    unexpected_verified_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotVerifiedSourceCoverageReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_features_with_stale_sources: int
    derived_features_with_stale_sources: int
    summary_total_stale_assets: int
    derived_total_stale_assets: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsStaleAssetCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_minimum_coverage_score: float
    derived_minimum_coverage_score: float | None
    total_features: int
    ready_features: int
    floor_derivation_mode: str | None
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_severity_ranking_feature_count: int
    derived_severity_ranking_feature_count: int
    critical_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_warning_feature_count: int
    derived_warning_feature_count: int
    high_severity_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_info_feature_count: int
    derived_info_feature_count: int
    warning_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_non_actionable_feature_count: int
    derived_non_actionable_feature_count: int
    info_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    checked_feature_count: int
    consistent_rank_label_feature_count: int
    inconsistent_rank_label_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    checked_feature_count: int
    consistent_rank_order_feature_count: int
    reordered_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    checked_gap_count: int
    consistent_rank_gap_count: int
    discontinuous_rank_gap_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    checked_gap_count: int
    consistent_rank_gap_magnitude_count: int
    mismatched_rank_gap_magnitude_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_critical_feature_count: int
    derived_critical_feature_count: int
    high_severity_feature_count: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_features_with_missing_sources: int
    derived_features_with_missing_sources: int
    total_missing_assets: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry:
    snapshot_id: str
    created_at: str
    reconciliation_classification: str
    consistency_percentage: float
    summary_features_with_missing_sources: int
    derived_features_with_missing_sources: int
    summary_total_missing_assets: int
    derived_total_missing_assets: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsMissingAssetCountReconciliation:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_ranking_count: int
    entries: tuple[SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

__all__ = [
    "SnapshotRawPayloadReferenceCompletenessEntry",
    "SnapshotRawPayloadReferenceCompleteness",
    "SnapshotSourceRecordCompletenessEntry",
    "SnapshotSourceRecordCompleteness",
    "SnapshotSourceDecisionUsageConsistencyEntry",
    "SnapshotSourceDecisionUsageConsistency",
    "SnapshotSourceObservationRecordSummaryReconciliationEntry",
    "SnapshotSourceObservationRecordSummaryReconciliation",
    "SnapshotVerifiedSourceCoverageReconciliationEntry",
    "SnapshotVerifiedSourceCoverageReconciliation",
    "SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry",
    "SnapshotSourceDiagnosticsStaleAssetCountReconciliation",
    "SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry",
    "SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation",
    "SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry",
    "SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation",
    "SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry",
    "SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation",
    "SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry",
    "SnapshotSourceDiagnosticsMissingAssetCountReconciliation",
]
