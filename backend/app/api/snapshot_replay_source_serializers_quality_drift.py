from __future__ import annotations

from app.services import SnapshotSourceObservationSummaryDrift
from app.services import SnapshotSourceObservationConfidenceDrift
from app.services import SnapshotSourceDiagnosticsAverageCoverageDrift
from app.services import SnapshotSourceDiagnosticsReadyFeatureDrift
from app.services import SnapshotSourceDiagnosticsStaleFeatureDrift
from app.services import SnapshotSourceDiagnosticsCriticalFeatureDrift
from app.services import SnapshotSourceDiagnosticsHighSeverityDrift
from app.services import SnapshotSourceDiagnosticsWarningFeatureDrift
from app.services import SnapshotSourceDiagnosticsInfoFeatureDrift
from app.services import SnapshotSourceDiagnosticsZeroRankDrift
from app.services import SnapshotSourceDiagnosticsSeverityLabelDrift
from app.services import SnapshotSourceDiagnosticsSeverityRankDrift
from app.services import SnapshotSourceDiagnosticsSeverityRankDensityDrift
from app.services import SnapshotSourceDiagnosticsSeverityRankSpreadDrift



def _serialize_source_observation_summary_drift(
    source_observation_summary_drift: SnapshotSourceObservationSummaryDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_observation_summary_drift.drift_classification,
        "average_summary_score": source_observation_summary_drift.average_summary_score,
        "severity_score": source_observation_summary_drift.severity_score,
        "total_snapshots_requested": source_observation_summary_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_summary_drift.snapshots_checked,
        "stable_snapshots": source_observation_summary_drift.stable_snapshots,
        "degrading_snapshots": source_observation_summary_drift.degrading_snapshots,
        "improving_snapshots": source_observation_summary_drift.improving_snapshots,
        "mixed_snapshots": source_observation_summary_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_observation_summary_drift.insufficient_data_snapshots,
        "expected_total_bound_sources": source_observation_summary_drift.expected_total_bound_sources,
        "expected_verified_sources": source_observation_summary_drift.expected_verified_sources,
        "expected_simulation_only_sources": source_observation_summary_drift.expected_simulation_only_sources,
        "expected_paper_safe_sources": source_observation_summary_drift.expected_paper_safe_sources,
        "normalization_mode_changes": source_observation_summary_drift.normalization_mode_changes,
        "malformed_summary_count": source_observation_summary_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "summary_score": entry.summary_score,
                "contract": entry.contract,
                "normalization_mode": entry.normalization_mode,
                "total_bound_sources": entry.total_bound_sources,
                "verified_sources": entry.verified_sources,
                "simulation_only_sources": entry.simulation_only_sources,
                "paper_safe_sources": entry.paper_safe_sources,
                "total_bound_source_delta": entry.total_bound_source_delta,
                "verified_source_delta": entry.verified_source_delta,
                "paper_safe_source_delta": entry.paper_safe_source_delta,
                "simulation_only_source_delta": entry.simulation_only_source_delta,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_summary_drift.entries
        ],
        "failures": list(source_observation_summary_drift.failures),
        "diagnostics": list(source_observation_summary_drift.diagnostics),
        "paper_safe": source_observation_summary_drift.paper_safe,
        "network_calls": source_observation_summary_drift.network_calls,
        "execution_side_effects": source_observation_summary_drift.execution_side_effects,
    }

def _serialize_source_observation_confidence_drift(
    source_observation_confidence_drift: SnapshotSourceObservationConfidenceDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_observation_confidence_drift.drift_classification,
        "average_confidence_score": source_observation_confidence_drift.average_confidence_score,
        "severity_score": source_observation_confidence_drift.severity_score,
        "total_snapshots_requested": source_observation_confidence_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_confidence_drift.snapshots_checked,
        "stable_snapshots": source_observation_confidence_drift.stable_snapshots,
        "degrading_snapshots": source_observation_confidence_drift.degrading_snapshots,
        "improving_snapshots": source_observation_confidence_drift.improving_snapshots,
        "mixed_snapshots": source_observation_confidence_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_observation_confidence_drift.insufficient_data_snapshots,
        "degraded_source_ids": list(source_observation_confidence_drift.degraded_source_ids),
        "improved_source_ids": list(source_observation_confidence_drift.improved_source_ids),
        "missing_confidence_source_ids": list(
            source_observation_confidence_drift.missing_confidence_source_ids
        ),
        "malformed_record_count": source_observation_confidence_drift.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "average_confidence_score": entry.average_confidence_score,
                "previous_average_confidence_score": entry.previous_average_confidence_score,
                "confidence_delta_from_previous": entry.confidence_delta_from_previous,
                "total_records": entry.total_records,
                "valid_confidence_records": entry.valid_confidence_records,
                "degraded_source_ids": list(entry.degraded_source_ids),
                "improved_source_ids": list(entry.improved_source_ids),
                "missing_confidence_source_ids": list(entry.missing_confidence_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_confidence_drift.entries
        ],
        "failures": list(source_observation_confidence_drift.failures),
        "diagnostics": list(source_observation_confidence_drift.diagnostics),
        "paper_safe": source_observation_confidence_drift.paper_safe,
        "network_calls": source_observation_confidence_drift.network_calls,
        "execution_side_effects": source_observation_confidence_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_average_coverage_drift(
    source_diagnostics_average_coverage_drift: SnapshotSourceDiagnosticsAverageCoverageDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_average_coverage_drift.drift_classification,
        "average_coverage_score": source_diagnostics_average_coverage_drift.average_coverage_score,
        "severity_score": source_diagnostics_average_coverage_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_average_coverage_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_average_coverage_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_average_coverage_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_average_coverage_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_average_coverage_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_average_coverage_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_average_coverage_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_average_coverage_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "average_coverage_score": entry.average_coverage_score,
                "previous_average_coverage_score": entry.previous_average_coverage_score,
                "coverage_score_delta": entry.coverage_score_delta,
                "minimum_coverage_score": entry.minimum_coverage_score,
                "total_features": entry.total_features,
                "ready_features": entry.ready_features,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_average_coverage_drift.entries
        ],
        "failures": list(source_diagnostics_average_coverage_drift.failures),
        "diagnostics": list(source_diagnostics_average_coverage_drift.diagnostics),
        "paper_safe": source_diagnostics_average_coverage_drift.paper_safe,
        "network_calls": source_diagnostics_average_coverage_drift.network_calls,
        "execution_side_effects": source_diagnostics_average_coverage_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_ready_feature_drift(
    source_diagnostics_ready_feature_drift: SnapshotSourceDiagnosticsReadyFeatureDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_ready_feature_drift.drift_classification,
        "average_ready_features": source_diagnostics_ready_feature_drift.average_ready_features,
        "severity_score": source_diagnostics_ready_feature_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_ready_feature_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_ready_feature_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_ready_feature_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_ready_feature_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_ready_feature_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_ready_feature_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_ready_feature_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_ready_feature_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "ready_features": entry.ready_features,
                "previous_ready_features": entry.previous_ready_features,
                "ready_feature_delta": entry.ready_feature_delta,
                "total_features": entry.total_features,
                "total_missing_assets": entry.total_missing_assets,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_ready_feature_drift.entries
        ],
        "failures": list(source_diagnostics_ready_feature_drift.failures),
        "diagnostics": list(source_diagnostics_ready_feature_drift.diagnostics),
        "paper_safe": source_diagnostics_ready_feature_drift.paper_safe,
        "network_calls": source_diagnostics_ready_feature_drift.network_calls,
        "execution_side_effects": source_diagnostics_ready_feature_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_stale_feature_drift(
    source_diagnostics_stale_feature_drift: SnapshotSourceDiagnosticsStaleFeatureDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_stale_feature_drift.drift_classification,
        "average_stale_features": source_diagnostics_stale_feature_drift.average_stale_features,
        "severity_score": source_diagnostics_stale_feature_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_stale_feature_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_stale_feature_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_stale_feature_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_stale_feature_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_stale_feature_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_stale_feature_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_stale_feature_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_stale_feature_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "features_with_stale_sources": entry.features_with_stale_sources,
                "previous_features_with_stale_sources": entry.previous_features_with_stale_sources,
                "stale_feature_delta": entry.stale_feature_delta,
                "total_features": entry.total_features,
                "total_stale_assets": entry.total_stale_assets,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_stale_feature_drift.entries
        ],
        "failures": list(source_diagnostics_stale_feature_drift.failures),
        "diagnostics": list(source_diagnostics_stale_feature_drift.diagnostics),
        "paper_safe": source_diagnostics_stale_feature_drift.paper_safe,
        "network_calls": source_diagnostics_stale_feature_drift.network_calls,
        "execution_side_effects": source_diagnostics_stale_feature_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_critical_feature_drift(
    source_diagnostics_critical_feature_drift: SnapshotSourceDiagnosticsCriticalFeatureDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_critical_feature_drift.drift_classification,
        "average_critical_feature_count": source_diagnostics_critical_feature_drift.average_critical_feature_count,
        "severity_score": source_diagnostics_critical_feature_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_critical_feature_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_critical_feature_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_critical_feature_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_critical_feature_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_critical_feature_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_critical_feature_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_critical_feature_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_critical_feature_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "critical_feature_count": entry.critical_feature_count,
                "previous_critical_feature_count": entry.previous_critical_feature_count,
                "critical_feature_delta": entry.critical_feature_delta,
                "severity_ranking_feature_count": entry.severity_ranking_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_critical_feature_drift.entries
        ],
        "failures": list(source_diagnostics_critical_feature_drift.failures),
        "diagnostics": list(source_diagnostics_critical_feature_drift.diagnostics),
        "paper_safe": source_diagnostics_critical_feature_drift.paper_safe,
        "network_calls": source_diagnostics_critical_feature_drift.network_calls,
        "execution_side_effects": source_diagnostics_critical_feature_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_high_severity_drift(
    source_diagnostics_high_severity_drift: SnapshotSourceDiagnosticsHighSeverityDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_high_severity_drift.drift_classification,
        "average_high_severity_feature_count": source_diagnostics_high_severity_drift.average_high_severity_feature_count,
        "severity_score": source_diagnostics_high_severity_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_high_severity_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_high_severity_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_high_severity_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_high_severity_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_high_severity_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_high_severity_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_high_severity_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_high_severity_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "high_severity_feature_count": entry.high_severity_feature_count,
                "previous_high_severity_feature_count": entry.previous_high_severity_feature_count,
                "high_severity_feature_delta": entry.high_severity_feature_delta,
                "critical_severity_feature_count": entry.critical_severity_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_high_severity_drift.entries
        ],
        "failures": list(source_diagnostics_high_severity_drift.failures),
        "diagnostics": list(source_diagnostics_high_severity_drift.diagnostics),
        "paper_safe": source_diagnostics_high_severity_drift.paper_safe,
        "network_calls": source_diagnostics_high_severity_drift.network_calls,
        "execution_side_effects": source_diagnostics_high_severity_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_warning_feature_drift(
    source_diagnostics_warning_feature_drift: SnapshotSourceDiagnosticsWarningFeatureDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_warning_feature_drift.drift_classification,
        "average_warning_feature_count": source_diagnostics_warning_feature_drift.average_warning_feature_count,
        "severity_score": source_diagnostics_warning_feature_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_warning_feature_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_warning_feature_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_warning_feature_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_warning_feature_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_warning_feature_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_warning_feature_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_warning_feature_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_warning_feature_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "warning_feature_count": entry.warning_feature_count,
                "previous_warning_feature_count": entry.previous_warning_feature_count,
                "warning_feature_delta": entry.warning_feature_delta,
                "high_severity_feature_count": entry.high_severity_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_warning_feature_drift.entries
        ],
        "failures": list(source_diagnostics_warning_feature_drift.failures),
        "diagnostics": list(source_diagnostics_warning_feature_drift.diagnostics),
        "paper_safe": source_diagnostics_warning_feature_drift.paper_safe,
        "network_calls": source_diagnostics_warning_feature_drift.network_calls,
        "execution_side_effects": source_diagnostics_warning_feature_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_info_feature_drift(
    source_diagnostics_info_feature_drift: SnapshotSourceDiagnosticsInfoFeatureDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_info_feature_drift.drift_classification,
        "average_info_feature_count": source_diagnostics_info_feature_drift.average_info_feature_count,
        "severity_score": source_diagnostics_info_feature_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_info_feature_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_info_feature_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_info_feature_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_info_feature_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_info_feature_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_info_feature_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_info_feature_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_info_feature_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "info_feature_count": entry.info_feature_count,
                "previous_info_feature_count": entry.previous_info_feature_count,
                "info_feature_delta": entry.info_feature_delta,
                "warning_feature_count": entry.warning_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_info_feature_drift.entries
        ],
        "failures": list(source_diagnostics_info_feature_drift.failures),
        "diagnostics": list(source_diagnostics_info_feature_drift.diagnostics),
        "paper_safe": source_diagnostics_info_feature_drift.paper_safe,
        "network_calls": source_diagnostics_info_feature_drift.network_calls,
        "execution_side_effects": source_diagnostics_info_feature_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_zero_rank_drift(
    source_diagnostics_zero_rank_drift: SnapshotSourceDiagnosticsZeroRankDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_zero_rank_drift.drift_classification,
        "average_zero_rank_feature_count": source_diagnostics_zero_rank_drift.average_zero_rank_feature_count,
        "severity_score": source_diagnostics_zero_rank_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_zero_rank_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_zero_rank_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_zero_rank_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_zero_rank_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_zero_rank_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_zero_rank_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_zero_rank_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_zero_rank_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "zero_rank_feature_count": entry.zero_rank_feature_count,
                "previous_zero_rank_feature_count": entry.previous_zero_rank_feature_count,
                "zero_rank_feature_delta": entry.zero_rank_feature_delta,
                "info_feature_count": entry.info_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_zero_rank_drift.entries
        ],
        "failures": list(source_diagnostics_zero_rank_drift.failures),
        "diagnostics": list(source_diagnostics_zero_rank_drift.diagnostics),
        "paper_safe": source_diagnostics_zero_rank_drift.paper_safe,
        "network_calls": source_diagnostics_zero_rank_drift.network_calls,
        "execution_side_effects": source_diagnostics_zero_rank_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_label_drift(
    source_diagnostics_severity_label_drift: SnapshotSourceDiagnosticsSeverityLabelDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_severity_label_drift.drift_classification,
        "average_severity_label_score": source_diagnostics_severity_label_drift.average_severity_label_score,
        "severity_score": source_diagnostics_severity_label_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_severity_label_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_label_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_severity_label_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_severity_label_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_severity_label_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_severity_label_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_severity_label_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_severity_label_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "severity_label_score": entry.severity_label_score,
                "previous_severity_label_score": entry.previous_severity_label_score,
                "severity_label_score_delta": entry.severity_label_score_delta,
                "severity_ranking_feature_count": entry.severity_ranking_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_label_drift.entries
        ],
        "failures": list(source_diagnostics_severity_label_drift.failures),
        "diagnostics": list(source_diagnostics_severity_label_drift.diagnostics),
        "paper_safe": source_diagnostics_severity_label_drift.paper_safe,
        "network_calls": source_diagnostics_severity_label_drift.network_calls,
        "execution_side_effects": source_diagnostics_severity_label_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_rank_drift(
    source_diagnostics_severity_rank_drift: SnapshotSourceDiagnosticsSeverityRankDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_severity_rank_drift.drift_classification,
        "average_severity_rank_total": source_diagnostics_severity_rank_drift.average_severity_rank_total,
        "severity_score": source_diagnostics_severity_rank_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_severity_rank_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_rank_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_severity_rank_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_severity_rank_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_severity_rank_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_severity_rank_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_severity_rank_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_severity_rank_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "severity_rank_total": entry.severity_rank_total,
                "previous_severity_rank_total": entry.previous_severity_rank_total,
                "severity_rank_total_delta": entry.severity_rank_total_delta,
                "severity_ranking_feature_count": entry.severity_ranking_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_rank_drift.entries
        ],
        "failures": list(source_diagnostics_severity_rank_drift.failures),
        "diagnostics": list(source_diagnostics_severity_rank_drift.diagnostics),
        "paper_safe": source_diagnostics_severity_rank_drift.paper_safe,
        "network_calls": source_diagnostics_severity_rank_drift.network_calls,
        "execution_side_effects": source_diagnostics_severity_rank_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_rank_density_drift(
    source_diagnostics_severity_rank_density_drift: SnapshotSourceDiagnosticsSeverityRankDensityDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_severity_rank_density_drift.drift_classification,
        "average_severity_rank_density": source_diagnostics_severity_rank_density_drift.average_severity_rank_density,
        "severity_score": source_diagnostics_severity_rank_density_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_severity_rank_density_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_rank_density_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_severity_rank_density_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_severity_rank_density_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_severity_rank_density_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_severity_rank_density_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_severity_rank_density_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_severity_rank_density_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "severity_rank_density": entry.severity_rank_density,
                "previous_severity_rank_density": entry.previous_severity_rank_density,
                "severity_rank_density_delta": entry.severity_rank_density_delta,
                "severity_ranking_feature_count": entry.severity_ranking_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_rank_density_drift.entries
        ],
        "failures": list(source_diagnostics_severity_rank_density_drift.failures),
        "diagnostics": list(source_diagnostics_severity_rank_density_drift.diagnostics),
        "paper_safe": source_diagnostics_severity_rank_density_drift.paper_safe,
        "network_calls": source_diagnostics_severity_rank_density_drift.network_calls,
        "execution_side_effects": source_diagnostics_severity_rank_density_drift.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_rank_spread_drift(
    source_diagnostics_severity_rank_spread_drift: SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_severity_rank_spread_drift.drift_classification,
        "average_severity_rank_spread": source_diagnostics_severity_rank_spread_drift.average_severity_rank_spread,
        "severity_score": source_diagnostics_severity_rank_spread_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_severity_rank_spread_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_rank_spread_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_severity_rank_spread_drift.stable_snapshots,
        "degrading_snapshots": source_diagnostics_severity_rank_spread_drift.degrading_snapshots,
        "improving_snapshots": source_diagnostics_severity_rank_spread_drift.improving_snapshots,
        "mixed_snapshots": source_diagnostics_severity_rank_spread_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_diagnostics_severity_rank_spread_drift.insufficient_data_snapshots,
        "malformed_summary_count": source_diagnostics_severity_rank_spread_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "severity_rank_spread": entry.severity_rank_spread,
                "previous_severity_rank_spread": entry.previous_severity_rank_spread,
                "severity_rank_spread_delta": entry.severity_rank_spread_delta,
                "severity_ranking_feature_count": entry.severity_ranking_feature_count,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_rank_spread_drift.entries
        ],
        "failures": list(source_diagnostics_severity_rank_spread_drift.failures),
        "diagnostics": list(source_diagnostics_severity_rank_spread_drift.diagnostics),
        "paper_safe": source_diagnostics_severity_rank_spread_drift.paper_safe,
        "network_calls": source_diagnostics_severity_rank_spread_drift.network_calls,
        "execution_side_effects": source_diagnostics_severity_rank_spread_drift.execution_side_effects,
    }
