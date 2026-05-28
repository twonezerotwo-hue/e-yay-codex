
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotSourceObservationSummaryDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    summary_score: float
    contract: str | None
    normalization_mode: str | None
    total_bound_sources: int | None
    verified_sources: int | None
    simulation_only_sources: int | None
    paper_safe_sources: int | None
    total_bound_source_delta: int | None
    verified_source_delta: int | None
    paper_safe_source_delta: int | None
    simulation_only_source_delta: int | None
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationSummaryDrift:
    drift_classification: str
    average_summary_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    expected_total_bound_sources: int
    expected_verified_sources: int
    expected_simulation_only_sources: int
    expected_paper_safe_sources: int
    normalization_mode_changes: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceObservationSummaryDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceObservationConfidenceDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    average_confidence_score: float
    previous_average_confidence_score: float | None
    confidence_delta_from_previous: float | None
    total_records: int
    valid_confidence_records: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_confidence_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceObservationConfidenceDrift:
    drift_classification: str
    average_confidence_score: float
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
    missing_confidence_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceObservationConfidenceDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsAverageCoverageDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    average_coverage_score: float
    previous_average_coverage_score: float | None
    coverage_score_delta: float | None
    minimum_coverage_score: float
    total_features: int
    ready_features: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsAverageCoverageDrift:
    drift_classification: str
    average_coverage_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsAverageCoverageDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsReadyFeatureDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    ready_features: int
    previous_ready_features: int | None
    ready_feature_delta: int | None
    total_features: int
    total_missing_assets: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsReadyFeatureDrift:
    drift_classification: str
    average_ready_features: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsReadyFeatureDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsStaleFeatureDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    features_with_stale_sources: int
    previous_features_with_stale_sources: int | None
    stale_feature_delta: int | None
    total_features: int
    total_stale_assets: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsStaleFeatureDrift:
    drift_classification: str
    average_stale_features: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsStaleFeatureDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsCriticalFeatureDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    critical_feature_count: int
    previous_critical_feature_count: int | None
    critical_feature_delta: int | None
    severity_ranking_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsCriticalFeatureDrift:
    drift_classification: str
    average_critical_feature_count: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsCriticalFeatureDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsHighSeverityDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    high_severity_feature_count: int
    previous_high_severity_feature_count: int | None
    high_severity_feature_delta: int | None
    critical_severity_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsHighSeverityDrift:
    drift_classification: str
    average_high_severity_feature_count: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsHighSeverityDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsWarningFeatureDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    warning_feature_count: int
    previous_warning_feature_count: int | None
    warning_feature_delta: int | None
    high_severity_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsWarningFeatureDrift:
    drift_classification: str
    average_warning_feature_count: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsWarningFeatureDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsInfoFeatureDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    info_feature_count: int
    previous_info_feature_count: int | None
    info_feature_delta: int | None
    warning_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsInfoFeatureDrift:
    drift_classification: str
    average_info_feature_count: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsInfoFeatureDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsZeroRankDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    zero_rank_feature_count: int
    previous_zero_rank_feature_count: int | None
    zero_rank_feature_delta: int | None
    info_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsZeroRankDrift:
    drift_classification: str
    average_zero_rank_feature_count: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsZeroRankDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityLabelDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    severity_label_score: int
    previous_severity_label_score: int | None
    severity_label_score_delta: int | None
    severity_ranking_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityLabelDrift:
    drift_classification: str
    average_severity_label_score: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityLabelDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    severity_rank_total: int
    previous_severity_rank_total: int | None
    severity_rank_total_delta: int | None
    severity_ranking_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankDrift:
    drift_classification: str
    average_severity_rank_total: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    severity_rank_density: float
    previous_severity_rank_density: float | None
    severity_rank_density_delta: float | None
    severity_ranking_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankDensityDrift:
    drift_classification: str
    average_severity_rank_density: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    severity_rank_spread: int
    previous_severity_rank_spread: int | None
    severity_rank_spread_delta: int | None
    severity_ranking_feature_count: int
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceDiagnosticsSeverityRankSpreadDrift:
    drift_classification: str
    average_severity_rank_spread: float
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    malformed_summary_count: int
    entries: tuple[SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

__all__ = [
    "SnapshotSourceObservationSummaryDriftEntry",
    "SnapshotSourceObservationSummaryDrift",
    "SnapshotSourceObservationConfidenceDriftEntry",
    "SnapshotSourceObservationConfidenceDrift",
    "SnapshotSourceDiagnosticsAverageCoverageDriftEntry",
    "SnapshotSourceDiagnosticsAverageCoverageDrift",
    "SnapshotSourceDiagnosticsReadyFeatureDriftEntry",
    "SnapshotSourceDiagnosticsReadyFeatureDrift",
    "SnapshotSourceDiagnosticsStaleFeatureDriftEntry",
    "SnapshotSourceDiagnosticsStaleFeatureDrift",
    "SnapshotSourceDiagnosticsCriticalFeatureDriftEntry",
    "SnapshotSourceDiagnosticsCriticalFeatureDrift",
    "SnapshotSourceDiagnosticsHighSeverityDriftEntry",
    "SnapshotSourceDiagnosticsHighSeverityDrift",
    "SnapshotSourceDiagnosticsWarningFeatureDriftEntry",
    "SnapshotSourceDiagnosticsWarningFeatureDrift",
    "SnapshotSourceDiagnosticsInfoFeatureDriftEntry",
    "SnapshotSourceDiagnosticsInfoFeatureDrift",
    "SnapshotSourceDiagnosticsZeroRankDriftEntry",
    "SnapshotSourceDiagnosticsZeroRankDrift",
    "SnapshotSourceDiagnosticsSeverityLabelDriftEntry",
    "SnapshotSourceDiagnosticsSeverityLabelDrift",
    "SnapshotSourceDiagnosticsSeverityRankDriftEntry",
    "SnapshotSourceDiagnosticsSeverityRankDrift",
    "SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry",
    "SnapshotSourceDiagnosticsSeverityRankDensityDrift",
    "SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry",
    "SnapshotSourceDiagnosticsSeverityRankSpreadDrift",
]
