from __future__ import annotations

from app.services import SnapshotSourceDecisionUsageConsistency
from app.services import SnapshotSourceObservationRecordSummaryReconciliation
from app.services import SnapshotVerifiedSourceCoverageReconciliation
from app.services import SnapshotSourceDiagnosticsStaleAssetCountReconciliation
from app.services import SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation
from app.services import SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation
from app.services import SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation
from app.services import SnapshotSourceDiagnosticsMissingAssetCountReconciliation



def _serialize_source_decision_usage_consistency(
    source_decision_usage_consistency: SnapshotSourceDecisionUsageConsistency,
) -> dict[str, object]:
    return {
        "consistency_classification": source_decision_usage_consistency.consistency_classification,
        "average_consistency_percentage": source_decision_usage_consistency.average_consistency_percentage,
        "total_snapshots_requested": source_decision_usage_consistency.total_snapshots_requested,
        "snapshots_checked": source_decision_usage_consistency.snapshots_checked,
        "consistent_snapshots": source_decision_usage_consistency.consistent_snapshots,
        "partial_snapshots": source_decision_usage_consistency.partial_snapshots,
        "degraded_snapshots": source_decision_usage_consistency.degraded_snapshots,
        "invalid_snapshots": source_decision_usage_consistency.invalid_snapshots,
        "aggregate_decision_usage_counts": source_decision_usage_consistency.aggregate_decision_usage_counts,
        "mismatched_source_ids": list(source_decision_usage_consistency.mismatched_source_ids),
        "unsafe_source_ids": list(source_decision_usage_consistency.unsafe_source_ids),
        "unknown_registry_source_ids": list(source_decision_usage_consistency.unknown_registry_source_ids),
        "missing_decision_usage_source_ids": list(
            source_decision_usage_consistency.missing_decision_usage_source_ids
        ),
        "malformed_record_count": source_decision_usage_consistency.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "consistency_classification": entry.consistency_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_records": entry.total_records,
                "consistent_records": entry.consistent_records,
                "decision_usage_counts": entry.decision_usage_counts,
                "mismatched_source_ids": list(entry.mismatched_source_ids),
                "unsafe_source_ids": list(entry.unsafe_source_ids),
                "unknown_registry_source_ids": list(entry.unknown_registry_source_ids),
                "missing_decision_usage_source_ids": list(entry.missing_decision_usage_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_decision_usage_consistency.entries
        ],
        "failures": list(source_decision_usage_consistency.failures),
        "diagnostics": list(source_decision_usage_consistency.diagnostics),
        "paper_safe": source_decision_usage_consistency.paper_safe,
        "network_calls": source_decision_usage_consistency.network_calls,
        "execution_side_effects": source_decision_usage_consistency.execution_side_effects,
    }

def _serialize_source_observation_record_summary_reconciliation(
    source_observation_record_summary_reconciliation: SnapshotSourceObservationRecordSummaryReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_observation_record_summary_reconciliation.consistency_classification,
        "average_consistency_percentage": source_observation_record_summary_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_observation_record_summary_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_observation_record_summary_reconciliation.snapshots_checked,
        "consistent_snapshots": source_observation_record_summary_reconciliation.consistent_snapshots,
        "partial_snapshots": source_observation_record_summary_reconciliation.partial_snapshots,
        "degraded_snapshots": source_observation_record_summary_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_observation_record_summary_reconciliation.invalid_snapshots,
        "missing_fields": list(source_observation_record_summary_reconciliation.missing_fields),
        "mismatched_fields": list(source_observation_record_summary_reconciliation.mismatched_fields),
        "malformed_record_count": source_observation_record_summary_reconciliation.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "record_total_bound_sources": entry.record_total_bound_sources,
                "summary_total_bound_sources": entry.summary_total_bound_sources,
                "record_verified_sources": entry.record_verified_sources,
                "summary_verified_sources": entry.summary_verified_sources,
                "record_simulation_only_sources": entry.record_simulation_only_sources,
                "summary_simulation_only_sources": entry.summary_simulation_only_sources,
                "record_paper_safe_sources": entry.record_paper_safe_sources,
                "summary_paper_safe_sources": entry.summary_paper_safe_sources,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_record_summary_reconciliation.entries
        ],
        "failures": list(source_observation_record_summary_reconciliation.failures),
        "diagnostics": list(source_observation_record_summary_reconciliation.diagnostics),
        "paper_safe": source_observation_record_summary_reconciliation.paper_safe,
        "network_calls": source_observation_record_summary_reconciliation.network_calls,
        "execution_side_effects": source_observation_record_summary_reconciliation.execution_side_effects,
    }

def _serialize_verified_source_coverage_reconciliation(
    verified_source_coverage_reconciliation: SnapshotVerifiedSourceCoverageReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": verified_source_coverage_reconciliation.consistency_classification,
        "average_coverage_percentage": verified_source_coverage_reconciliation.average_coverage_percentage,
        "expected_verified_source_count": verified_source_coverage_reconciliation.expected_verified_source_count,
        "total_snapshots_requested": verified_source_coverage_reconciliation.total_snapshots_requested,
        "snapshots_checked": verified_source_coverage_reconciliation.snapshots_checked,
        "consistent_snapshots": verified_source_coverage_reconciliation.consistent_snapshots,
        "partial_snapshots": verified_source_coverage_reconciliation.partial_snapshots,
        "degraded_snapshots": verified_source_coverage_reconciliation.degraded_snapshots,
        "invalid_snapshots": verified_source_coverage_reconciliation.invalid_snapshots,
        "missing_verified_source_ids": list(
            verified_source_coverage_reconciliation.missing_verified_source_ids
        ),
        "unexpected_verified_source_ids": list(
            verified_source_coverage_reconciliation.unexpected_verified_source_ids
        ),
        "malformed_record_count": verified_source_coverage_reconciliation.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "coverage_percentage": entry.coverage_percentage,
                "expected_verified_source_count": entry.expected_verified_source_count,
                "observed_verified_source_count": entry.observed_verified_source_count,
                "matched_verified_source_count": entry.matched_verified_source_count,
                "missing_verified_source_ids": list(entry.missing_verified_source_ids),
                "unexpected_verified_source_ids": list(entry.unexpected_verified_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in verified_source_coverage_reconciliation.entries
        ],
        "failures": list(verified_source_coverage_reconciliation.failures),
        "diagnostics": list(verified_source_coverage_reconciliation.diagnostics),
        "paper_safe": verified_source_coverage_reconciliation.paper_safe,
        "network_calls": verified_source_coverage_reconciliation.network_calls,
        "execution_side_effects": verified_source_coverage_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_stale_asset_count_reconciliation(
    source_diagnostics_stale_asset_count_reconciliation: SnapshotSourceDiagnosticsStaleAssetCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_stale_asset_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_stale_asset_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_stale_asset_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_stale_asset_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_stale_asset_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_stale_asset_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_stale_asset_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_stale_asset_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_stale_asset_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_stale_asset_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_stale_asset_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_features_with_stale_sources": entry.summary_features_with_stale_sources,
                "derived_features_with_stale_sources": entry.derived_features_with_stale_sources,
                "summary_total_stale_assets": entry.summary_total_stale_assets,
                "derived_total_stale_assets": entry.derived_total_stale_assets,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_stale_asset_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_stale_asset_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_stale_asset_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_stale_asset_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_stale_asset_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_stale_asset_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_minimum_coverage_floor_reconciliation(
    source_diagnostics_minimum_coverage_floor_reconciliation: SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_minimum_coverage_floor_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_minimum_coverage_floor_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_minimum_coverage_floor_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_minimum_coverage_floor_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_minimum_coverage_floor_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_minimum_coverage_floor_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_minimum_coverage_floor_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_minimum_coverage_floor_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_minimum_coverage_floor_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_minimum_coverage_floor_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_minimum_coverage_floor_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_minimum_coverage_score": entry.summary_minimum_coverage_score,
                "derived_minimum_coverage_score": entry.derived_minimum_coverage_score,
                "total_features": entry.total_features,
                "ready_features": entry.ready_features,
                "floor_derivation_mode": entry.floor_derivation_mode,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_minimum_coverage_floor_reconciliation.entries
        ],
        "failures": list(source_diagnostics_minimum_coverage_floor_reconciliation.failures),
        "diagnostics": list(source_diagnostics_minimum_coverage_floor_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_minimum_coverage_floor_reconciliation.paper_safe,
        "network_calls": source_diagnostics_minimum_coverage_floor_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_minimum_coverage_floor_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_feature_count_reconciliation(
    source_diagnostics_severity_ranking_feature_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_feature_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_feature_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_feature_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_feature_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_feature_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_feature_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_feature_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_feature_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_feature_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_feature_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_feature_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_severity_ranking_feature_count": entry.summary_severity_ranking_feature_count,
                "derived_severity_ranking_feature_count": entry.derived_severity_ranking_feature_count,
                "critical_feature_count": entry.critical_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_feature_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_feature_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_feature_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_feature_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_feature_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_feature_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_warning_count_reconciliation(
    source_diagnostics_severity_ranking_warning_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_warning_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_warning_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_warning_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_warning_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_warning_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_warning_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_warning_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_warning_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_warning_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_warning_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_warning_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_warning_feature_count": entry.summary_warning_feature_count,
                "derived_warning_feature_count": entry.derived_warning_feature_count,
                "high_severity_feature_count": entry.high_severity_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_warning_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_warning_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_warning_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_warning_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_warning_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_warning_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_info_count_reconciliation(
    source_diagnostics_severity_ranking_info_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_info_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_info_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_info_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_info_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_info_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_info_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_info_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_info_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_info_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_info_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_info_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_info_feature_count": entry.summary_info_feature_count,
                "derived_info_feature_count": entry.derived_info_feature_count,
                "warning_feature_count": entry.warning_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_info_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_info_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_info_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_info_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_info_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_info_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
    source_diagnostics_severity_ranking_non_actionable_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_non_actionable_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_non_actionable_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_non_actionable_feature_count": entry.summary_non_actionable_feature_count,
                "derived_non_actionable_feature_count": entry.derived_non_actionable_feature_count,
                "info_feature_count": entry.info_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_non_actionable_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_non_actionable_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_non_actionable_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
    source_diagnostics_severity_ranking_rank_label_consistency_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "checked_feature_count": entry.checked_feature_count,
                "consistent_rank_label_feature_count": entry.consistent_rank_label_feature_count,
                "inconsistent_rank_label_feature_count": entry.inconsistent_rank_label_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
    source_diagnostics_severity_ranking_rank_order_continuity_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "checked_feature_count": entry.checked_feature_count,
                "consistent_rank_order_feature_count": entry.consistent_rank_order_feature_count,
                "reordered_feature_count": entry.reordered_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
    source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "checked_gap_count": entry.checked_gap_count,
                "consistent_rank_gap_count": entry.consistent_rank_gap_count,
                "discontinuous_rank_gap_count": entry.discontinuous_rank_gap_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
    source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "checked_gap_count": entry.checked_gap_count,
                "consistent_rank_gap_magnitude_count": entry.consistent_rank_gap_magnitude_count,
                "mismatched_rank_gap_magnitude_count": entry.mismatched_rank_gap_magnitude_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_severity_ranking_critical_count_reconciliation(
    source_diagnostics_severity_ranking_critical_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_severity_ranking_critical_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_severity_ranking_critical_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_severity_ranking_critical_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_severity_ranking_critical_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_severity_ranking_critical_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_severity_ranking_critical_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_severity_ranking_critical_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_severity_ranking_critical_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_severity_ranking_critical_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_severity_ranking_critical_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_severity_ranking_critical_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_critical_feature_count": entry.summary_critical_feature_count,
                "derived_critical_feature_count": entry.derived_critical_feature_count,
                "high_severity_feature_count": entry.high_severity_feature_count,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_severity_ranking_critical_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_severity_ranking_critical_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_severity_ranking_critical_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_severity_ranking_critical_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_severity_ranking_critical_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_severity_ranking_critical_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_missing_source_feature_count_reconciliation(
    source_diagnostics_missing_source_feature_count_reconciliation: SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_missing_source_feature_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_missing_source_feature_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_missing_source_feature_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_missing_source_feature_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_missing_source_feature_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_missing_source_feature_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_missing_source_feature_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_missing_source_feature_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_missing_source_feature_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_missing_source_feature_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_missing_source_feature_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_features_with_missing_sources": entry.summary_features_with_missing_sources,
                "derived_features_with_missing_sources": entry.derived_features_with_missing_sources,
                "total_missing_assets": entry.total_missing_assets,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_missing_source_feature_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_missing_source_feature_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_missing_source_feature_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_missing_source_feature_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_missing_source_feature_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_missing_source_feature_count_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_missing_asset_count_reconciliation(
    source_diagnostics_missing_asset_count_reconciliation: SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_diagnostics_missing_asset_count_reconciliation.consistency_classification,
        "average_consistency_percentage": source_diagnostics_missing_asset_count_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_diagnostics_missing_asset_count_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_missing_asset_count_reconciliation.snapshots_checked,
        "consistent_snapshots": source_diagnostics_missing_asset_count_reconciliation.consistent_snapshots,
        "partial_snapshots": source_diagnostics_missing_asset_count_reconciliation.partial_snapshots,
        "degraded_snapshots": source_diagnostics_missing_asset_count_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_diagnostics_missing_asset_count_reconciliation.invalid_snapshots,
        "missing_fields": list(source_diagnostics_missing_asset_count_reconciliation.missing_fields),
        "mismatched_fields": list(source_diagnostics_missing_asset_count_reconciliation.mismatched_fields),
        "malformed_ranking_count": source_diagnostics_missing_asset_count_reconciliation.malformed_ranking_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "summary_features_with_missing_sources": entry.summary_features_with_missing_sources,
                "derived_features_with_missing_sources": entry.derived_features_with_missing_sources,
                "summary_total_missing_assets": entry.summary_total_missing_assets,
                "derived_total_missing_assets": entry.derived_total_missing_assets,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_ranking_count": entry.malformed_ranking_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_missing_asset_count_reconciliation.entries
        ],
        "failures": list(source_diagnostics_missing_asset_count_reconciliation.failures),
        "diagnostics": list(source_diagnostics_missing_asset_count_reconciliation.diagnostics),
        "paper_safe": source_diagnostics_missing_asset_count_reconciliation.paper_safe,
        "network_calls": source_diagnostics_missing_asset_count_reconciliation.network_calls,
        "execution_side_effects": source_diagnostics_missing_asset_count_reconciliation.execution_side_effects,
    }

