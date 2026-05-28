from __future__ import annotations



from app.services import SnapshotSourceObservationCadenceDrift
from app.services import SnapshotSourceObservationTimestampIntegrityDrift
from app.services import SnapshotSourceObservationNormalizationModeDrift
from app.services import SnapshotSourceObservationAvailabilityLagDrift
from app.services import SnapshotSourceFreshnessPolicyDrift
from app.services import SnapshotStaleSourceListThresholdReconciliation
from app.services import SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift
from app.services import SnapshotSourceObservationFreshnessSecondsDrift
from app.services import SnapshotMappedAtAlignmentConsistency
from app.services import SnapshotSourceFreshnessSummaryReconciliation
from app.services import SnapshotSourceFreshnessStatusThresholdReconciliation
from app.services import SnapshotSourceFreshnessDecayTimeline

def _serialize_source_freshness_decay_timeline(
    source_freshness_decay_timeline: SnapshotSourceFreshnessDecayTimeline,
) -> dict[str, object]:
    return {
        "decay_classification": source_freshness_decay_timeline.decay_classification,
        "total_snapshots": source_freshness_decay_timeline.total_snapshots,
        "evaluable_snapshots": source_freshness_decay_timeline.evaluable_snapshots,
        "missing_freshness_snapshots": source_freshness_decay_timeline.missing_freshness_snapshots,
        "first_status": source_freshness_decay_timeline.first_status,
        "latest_status": source_freshness_decay_timeline.latest_status,
        "dominant_status": source_freshness_decay_timeline.dominant_status,
        "worst_status": source_freshness_decay_timeline.worst_status,
        "transition_count": source_freshness_decay_timeline.transition_count,
        "decay_score_delta": source_freshness_decay_timeline.decay_score_delta,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "freshness_status": entry.freshness_status,
                "fresh_source_count": entry.fresh_source_count,
                "stale_source_count": entry.stale_source_count,
                "missing_timestamp_source_count": entry.missing_timestamp_source_count,
                "degraded_source_count": entry.degraded_source_count,
                "total_active_sources": entry.total_active_sources,
                "decay_score": entry.decay_score,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_freshness_decay_timeline.entries
        ],
        "failures": list(source_freshness_decay_timeline.failures),
        "total_snapshots_requested": source_freshness_decay_timeline.total_snapshots_requested,
        "diagnostics": list(source_freshness_decay_timeline.diagnostics),
        "paper_safe": source_freshness_decay_timeline.paper_safe,
        "network_calls": source_freshness_decay_timeline.network_calls,
        "execution_side_effects": source_freshness_decay_timeline.execution_side_effects,
    }

def _serialize_source_observation_cadence_drift(
    source_observation_cadence_drift: SnapshotSourceObservationCadenceDrift,
) -> dict[str, object]:
    return {
        "cadence_classification": source_observation_cadence_drift.cadence_classification,
        "cadence_score": source_observation_cadence_drift.cadence_score,
        "severity_bucket": source_observation_cadence_drift.severity_bucket,
        "total_snapshots_requested": source_observation_cadence_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_cadence_drift.snapshots_checked,
        "evaluable_snapshots": source_observation_cadence_drift.evaluable_snapshots,
        "missing_timestamp_snapshots": source_observation_cadence_drift.missing_timestamp_snapshots,
        "transition_count": source_observation_cadence_drift.transition_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "cadence_status": entry.cadence_status,
                "anchor_observed_at": entry.anchor_observed_at,
                "observed_source_count": entry.observed_source_count,
                "missing_timestamp_source_count": entry.missing_timestamp_source_count,
                "interval_seconds_from_previous": entry.interval_seconds_from_previous,
                "cadence_score": entry.cadence_score,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_cadence_drift.entries
        ],
        "failures": list(source_observation_cadence_drift.failures),
        "diagnostics": list(source_observation_cadence_drift.diagnostics),
        "paper_safe": source_observation_cadence_drift.paper_safe,
        "network_calls": source_observation_cadence_drift.network_calls,
        "execution_side_effects": source_observation_cadence_drift.execution_side_effects,
    }

def _serialize_source_observation_timestamp_integrity_drift(
    source_observation_timestamp_integrity_drift: SnapshotSourceObservationTimestampIntegrityDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_observation_timestamp_integrity_drift.drift_classification,
        "average_integrity_score": source_observation_timestamp_integrity_drift.average_integrity_score,
        "severity_score": source_observation_timestamp_integrity_drift.severity_score,
        "total_snapshots_requested": source_observation_timestamp_integrity_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_timestamp_integrity_drift.snapshots_checked,
        "stable_snapshots": source_observation_timestamp_integrity_drift.stable_snapshots,
        "degrading_snapshots": source_observation_timestamp_integrity_drift.degrading_snapshots,
        "improving_snapshots": source_observation_timestamp_integrity_drift.improving_snapshots,
        "mixed_snapshots": source_observation_timestamp_integrity_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_observation_timestamp_integrity_drift.insufficient_data_snapshots,
        "missing_timestamp_source_ids": list(
            source_observation_timestamp_integrity_drift.missing_timestamp_source_ids
        ),
        "sequence_violation_source_ids": list(
            source_observation_timestamp_integrity_drift.sequence_violation_source_ids
        ),
        "mapped_time_regression_source_ids": list(
            source_observation_timestamp_integrity_drift.mapped_time_regression_source_ids
        ),
        "malformed_record_count": source_observation_timestamp_integrity_drift.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "integrity_classification": entry.integrity_classification,
                "integrity_score": entry.integrity_score,
                "total_records": entry.total_records,
                "valid_records": entry.valid_records,
                "missing_timestamp_source_ids": list(entry.missing_timestamp_source_ids),
                "sequence_violation_source_ids": list(entry.sequence_violation_source_ids),
                "mapped_time_regression_source_ids": list(entry.mapped_time_regression_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_timestamp_integrity_drift.entries
        ],
        "failures": list(source_observation_timestamp_integrity_drift.failures),
        "diagnostics": list(source_observation_timestamp_integrity_drift.diagnostics),
        "paper_safe": source_observation_timestamp_integrity_drift.paper_safe,
        "network_calls": source_observation_timestamp_integrity_drift.network_calls,
        "execution_side_effects": source_observation_timestamp_integrity_drift.execution_side_effects,
    }

def _serialize_source_observation_normalization_mode_drift(
    source_observation_normalization_mode_drift: SnapshotSourceObservationNormalizationModeDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_observation_normalization_mode_drift.drift_classification,
        "average_mode_consistency_score": source_observation_normalization_mode_drift.average_mode_consistency_score,
        "severity_score": source_observation_normalization_mode_drift.severity_score,
        "total_snapshots_requested": source_observation_normalization_mode_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_normalization_mode_drift.snapshots_checked,
        "stable_snapshots": source_observation_normalization_mode_drift.stable_snapshots,
        "drifting_snapshots": source_observation_normalization_mode_drift.drifting_snapshots,
        "degraded_snapshots": source_observation_normalization_mode_drift.degraded_snapshots,
        "insufficient_data_snapshots": source_observation_normalization_mode_drift.insufficient_data_snapshots,
        "dominant_normalization_mode": source_observation_normalization_mode_drift.dominant_normalization_mode,
        "latest_normalization_mode": source_observation_normalization_mode_drift.latest_normalization_mode,
        "normalization_mode_counts": source_observation_normalization_mode_drift.normalization_mode_counts,
        "mode_transition_count": source_observation_normalization_mode_drift.mode_transition_count,
        "malformed_summary_count": source_observation_normalization_mode_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "normalization_mode": entry.normalization_mode,
                "previous_normalization_mode": entry.previous_normalization_mode,
                "mode_consistency_score": entry.mode_consistency_score,
                "total_bound_sources": entry.total_bound_sources,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_normalization_mode_drift.entries
        ],
        "failures": list(source_observation_normalization_mode_drift.failures),
        "diagnostics": list(source_observation_normalization_mode_drift.diagnostics),
        "paper_safe": source_observation_normalization_mode_drift.paper_safe,
        "network_calls": source_observation_normalization_mode_drift.network_calls,
        "execution_side_effects": source_observation_normalization_mode_drift.execution_side_effects,
    }

def _serialize_mapped_at_alignment_consistency(
    mapped_at_alignment_consistency: SnapshotMappedAtAlignmentConsistency,
) -> dict[str, object]:
    return {
        "consistency_classification": mapped_at_alignment_consistency.consistency_classification,
        "average_consistency_percentage": mapped_at_alignment_consistency.average_consistency_percentage,
        "total_snapshots_requested": mapped_at_alignment_consistency.total_snapshots_requested,
        "snapshots_checked": mapped_at_alignment_consistency.snapshots_checked,
        "consistent_snapshots": mapped_at_alignment_consistency.consistent_snapshots,
        "partial_snapshots": mapped_at_alignment_consistency.partial_snapshots,
        "degraded_snapshots": mapped_at_alignment_consistency.degraded_snapshots,
        "invalid_snapshots": mapped_at_alignment_consistency.invalid_snapshots,
        "missing_mapped_at_source_ids": list(mapped_at_alignment_consistency.missing_mapped_at_source_ids),
        "batch_anchor_mismatch_source_ids": list(mapped_at_alignment_consistency.batch_anchor_mismatch_source_ids),
        "stored_at_alignment_mismatch_source_ids": list(
            mapped_at_alignment_consistency.stored_at_alignment_mismatch_source_ids
        ),
        "source_observation_alignment_mismatch_source_ids": list(
            mapped_at_alignment_consistency.source_observation_alignment_mismatch_source_ids
        ),
        "malformed_record_count": mapped_at_alignment_consistency.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "consistency_classification": entry.consistency_classification,
                "consistency_percentage": entry.consistency_percentage,
                "normalization_mode": entry.normalization_mode,
                "batch_anchor": entry.batch_anchor,
                "total_records": entry.total_records,
                "aligned_records": entry.aligned_records,
                "missing_mapped_at_source_ids": list(entry.missing_mapped_at_source_ids),
                "batch_anchor_mismatch_source_ids": list(entry.batch_anchor_mismatch_source_ids),
                "stored_at_alignment_mismatch_source_ids": list(entry.stored_at_alignment_mismatch_source_ids),
                "source_observation_alignment_mismatch_source_ids": list(
                    entry.source_observation_alignment_mismatch_source_ids
                ),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in mapped_at_alignment_consistency.entries
        ],
        "failures": list(mapped_at_alignment_consistency.failures),
        "diagnostics": list(mapped_at_alignment_consistency.diagnostics),
        "paper_safe": mapped_at_alignment_consistency.paper_safe,
        "network_calls": mapped_at_alignment_consistency.network_calls,
        "execution_side_effects": mapped_at_alignment_consistency.execution_side_effects,
    }

def _serialize_source_observation_availability_lag_drift(
    source_observation_availability_lag_drift: SnapshotSourceObservationAvailabilityLagDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_observation_availability_lag_drift.drift_classification,
        "average_lag_seconds": source_observation_availability_lag_drift.average_lag_seconds,
        "severity_score": source_observation_availability_lag_drift.severity_score,
        "total_snapshots_requested": source_observation_availability_lag_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_availability_lag_drift.snapshots_checked,
        "stable_snapshots": source_observation_availability_lag_drift.stable_snapshots,
        "degrading_snapshots": source_observation_availability_lag_drift.degrading_snapshots,
        "improving_snapshots": source_observation_availability_lag_drift.improving_snapshots,
        "mixed_snapshots": source_observation_availability_lag_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_observation_availability_lag_drift.insufficient_data_snapshots,
        "degraded_source_ids": list(source_observation_availability_lag_drift.degraded_source_ids),
        "improved_source_ids": list(source_observation_availability_lag_drift.improved_source_ids),
        "missing_timestamp_source_ids": list(
            source_observation_availability_lag_drift.missing_timestamp_source_ids
        ),
        "malformed_record_count": source_observation_availability_lag_drift.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "average_lag_seconds": entry.average_lag_seconds,
                "previous_average_lag_seconds": entry.previous_average_lag_seconds,
                "lag_delta_from_previous_seconds": entry.lag_delta_from_previous_seconds,
                "total_records": entry.total_records,
                "valid_lag_records": entry.valid_lag_records,
                "degraded_source_ids": list(entry.degraded_source_ids),
                "improved_source_ids": list(entry.improved_source_ids),
                "missing_timestamp_source_ids": list(entry.missing_timestamp_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_availability_lag_drift.entries
        ],
        "failures": list(source_observation_availability_lag_drift.failures),
        "diagnostics": list(source_observation_availability_lag_drift.diagnostics),
        "paper_safe": source_observation_availability_lag_drift.paper_safe,
        "network_calls": source_observation_availability_lag_drift.network_calls,
        "execution_side_effects": source_observation_availability_lag_drift.execution_side_effects,
    }

def _serialize_source_freshness_summary_reconciliation(
    source_freshness_summary_reconciliation: SnapshotSourceFreshnessSummaryReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_freshness_summary_reconciliation.consistency_classification,
        "average_consistency_percentage": source_freshness_summary_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_freshness_summary_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_freshness_summary_reconciliation.snapshots_checked,
        "consistent_snapshots": source_freshness_summary_reconciliation.consistent_snapshots,
        "partial_snapshots": source_freshness_summary_reconciliation.partial_snapshots,
        "degraded_snapshots": source_freshness_summary_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_freshness_summary_reconciliation.invalid_snapshots,
        "missing_freshness_source_ids": list(
            source_freshness_summary_reconciliation.missing_freshness_source_ids
        ),
        "record_only_stale_source_ids": list(
            source_freshness_summary_reconciliation.record_only_stale_source_ids
        ),
        "summary_only_stale_source_ids": list(
            source_freshness_summary_reconciliation.summary_only_stale_source_ids
        ),
        "malformed_record_count": source_freshness_summary_reconciliation.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_records": entry.total_records,
                "aligned_records": entry.aligned_records,
                "record_stale_source_count": entry.record_stale_source_count,
                "summary_stale_source_count": entry.summary_stale_source_count,
                "record_degraded_source_count": entry.record_degraded_source_count,
                "record_fresh_source_count": entry.record_fresh_source_count,
                "missing_freshness_source_ids": list(entry.missing_freshness_source_ids),
                "record_only_stale_source_ids": list(entry.record_only_stale_source_ids),
                "summary_only_stale_source_ids": list(entry.summary_only_stale_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_freshness_summary_reconciliation.entries
        ],
        "failures": list(source_freshness_summary_reconciliation.failures),
        "diagnostics": list(source_freshness_summary_reconciliation.diagnostics),
        "paper_safe": source_freshness_summary_reconciliation.paper_safe,
        "network_calls": source_freshness_summary_reconciliation.network_calls,
        "execution_side_effects": source_freshness_summary_reconciliation.execution_side_effects,
    }

def _serialize_source_observation_freshness_seconds_drift(
    source_observation_freshness_seconds_drift: SnapshotSourceObservationFreshnessSecondsDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_observation_freshness_seconds_drift.drift_classification,
        "average_freshness_seconds": source_observation_freshness_seconds_drift.average_freshness_seconds,
        "severity_score": source_observation_freshness_seconds_drift.severity_score,
        "total_snapshots_requested": source_observation_freshness_seconds_drift.total_snapshots_requested,
        "snapshots_checked": source_observation_freshness_seconds_drift.snapshots_checked,
        "stable_snapshots": source_observation_freshness_seconds_drift.stable_snapshots,
        "degrading_snapshots": source_observation_freshness_seconds_drift.degrading_snapshots,
        "improving_snapshots": source_observation_freshness_seconds_drift.improving_snapshots,
        "mixed_snapshots": source_observation_freshness_seconds_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_observation_freshness_seconds_drift.insufficient_data_snapshots,
        "degraded_source_ids": list(source_observation_freshness_seconds_drift.degraded_source_ids),
        "improved_source_ids": list(source_observation_freshness_seconds_drift.improved_source_ids),
        "missing_freshness_source_ids": list(
            source_observation_freshness_seconds_drift.missing_freshness_source_ids
        ),
        "malformed_record_count": source_observation_freshness_seconds_drift.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "average_freshness_seconds": entry.average_freshness_seconds,
                "previous_average_freshness_seconds": entry.previous_average_freshness_seconds,
                "freshness_delta_from_previous_seconds": entry.freshness_delta_from_previous_seconds,
                "total_records": entry.total_records,
                "valid_freshness_records": entry.valid_freshness_records,
                "degraded_source_ids": list(entry.degraded_source_ids),
                "improved_source_ids": list(entry.improved_source_ids),
                "missing_freshness_source_ids": list(entry.missing_freshness_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_observation_freshness_seconds_drift.entries
        ],
        "failures": list(source_observation_freshness_seconds_drift.failures),
        "diagnostics": list(source_observation_freshness_seconds_drift.diagnostics),
        "paper_safe": source_observation_freshness_seconds_drift.paper_safe,
        "network_calls": source_observation_freshness_seconds_drift.network_calls,
        "execution_side_effects": source_observation_freshness_seconds_drift.execution_side_effects,
    }

def _serialize_source_freshness_status_threshold_reconciliation(
    source_freshness_status_threshold_reconciliation: SnapshotSourceFreshnessStatusThresholdReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": source_freshness_status_threshold_reconciliation.consistency_classification,
        "average_consistency_percentage": source_freshness_status_threshold_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": source_freshness_status_threshold_reconciliation.total_snapshots_requested,
        "snapshots_checked": source_freshness_status_threshold_reconciliation.snapshots_checked,
        "consistent_snapshots": source_freshness_status_threshold_reconciliation.consistent_snapshots,
        "partial_snapshots": source_freshness_status_threshold_reconciliation.partial_snapshots,
        "degraded_snapshots": source_freshness_status_threshold_reconciliation.degraded_snapshots,
        "invalid_snapshots": source_freshness_status_threshold_reconciliation.invalid_snapshots,
        "missing_freshness_status_source_ids": list(
            source_freshness_status_threshold_reconciliation.missing_freshness_status_source_ids
        ),
        "threshold_mismatch_source_ids": list(
            source_freshness_status_threshold_reconciliation.threshold_mismatch_source_ids
        ),
        "malformed_record_count": source_freshness_status_threshold_reconciliation.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_records": entry.total_records,
                "aligned_records": entry.aligned_records,
                "fresh_threshold_source_count": entry.fresh_threshold_source_count,
                "degraded_threshold_source_count": entry.degraded_threshold_source_count,
                "stale_threshold_source_count": entry.stale_threshold_source_count,
                "missing_freshness_status_source_ids": list(entry.missing_freshness_status_source_ids),
                "threshold_mismatch_source_ids": list(entry.threshold_mismatch_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_freshness_status_threshold_reconciliation.entries
        ],
        "failures": list(source_freshness_status_threshold_reconciliation.failures),
        "diagnostics": list(source_freshness_status_threshold_reconciliation.diagnostics),
        "paper_safe": source_freshness_status_threshold_reconciliation.paper_safe,
        "network_calls": source_freshness_status_threshold_reconciliation.network_calls,
        "execution_side_effects": source_freshness_status_threshold_reconciliation.execution_side_effects,
    }

def _serialize_source_freshness_policy_drift(
    source_freshness_policy_drift: SnapshotSourceFreshnessPolicyDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_freshness_policy_drift.drift_classification,
        "average_policy_score": source_freshness_policy_drift.average_policy_score,
        "severity_score": source_freshness_policy_drift.severity_score,
        "total_snapshots_requested": source_freshness_policy_drift.total_snapshots_requested,
        "snapshots_checked": source_freshness_policy_drift.snapshots_checked,
        "stable_snapshots": source_freshness_policy_drift.stable_snapshots,
        "degrading_snapshots": source_freshness_policy_drift.degrading_snapshots,
        "improving_snapshots": source_freshness_policy_drift.improving_snapshots,
        "mixed_snapshots": source_freshness_policy_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_freshness_policy_drift.insufficient_data_snapshots,
        "evaluation_mode_changes": source_freshness_policy_drift.evaluation_mode_changes,
        "malformed_summary_count": source_freshness_policy_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "policy_score": entry.policy_score,
                "previous_policy_score": entry.previous_policy_score,
                "policy_score_delta": entry.policy_score_delta,
                "total_active_sources": entry.total_active_sources,
                "fresh_source_count": entry.fresh_source_count,
                "stale_source_count": entry.stale_source_count,
                "missing_timestamp_source_count": entry.missing_timestamp_source_count,
                "not_evaluated_source_count": entry.not_evaluated_source_count,
                "evaluation_mode": entry.evaluation_mode,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_freshness_policy_drift.entries
        ],
        "failures": list(source_freshness_policy_drift.failures),
        "diagnostics": list(source_freshness_policy_drift.diagnostics),
        "paper_safe": source_freshness_policy_drift.paper_safe,
        "network_calls": source_freshness_policy_drift.network_calls,
        "execution_side_effects": source_freshness_policy_drift.execution_side_effects,
    }

def _serialize_stale_source_list_threshold_reconciliation(
    stale_source_list_threshold_reconciliation: SnapshotStaleSourceListThresholdReconciliation,
) -> dict[str, object]:
    return {
        "consistency_classification": stale_source_list_threshold_reconciliation.consistency_classification,
        "average_consistency_percentage": stale_source_list_threshold_reconciliation.average_consistency_percentage,
        "total_snapshots_requested": stale_source_list_threshold_reconciliation.total_snapshots_requested,
        "snapshots_checked": stale_source_list_threshold_reconciliation.snapshots_checked,
        "consistent_snapshots": stale_source_list_threshold_reconciliation.consistent_snapshots,
        "partial_snapshots": stale_source_list_threshold_reconciliation.partial_snapshots,
        "degraded_snapshots": stale_source_list_threshold_reconciliation.degraded_snapshots,
        "invalid_snapshots": stale_source_list_threshold_reconciliation.invalid_snapshots,
        "missing_timestamp_source_ids": list(
            stale_source_list_threshold_reconciliation.missing_timestamp_source_ids
        ),
        "threshold_mismatch_source_ids": list(
            stale_source_list_threshold_reconciliation.threshold_mismatch_source_ids
        ),
        "malformed_field_count": stale_source_list_threshold_reconciliation.malformed_field_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "reconciliation_classification": entry.reconciliation_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_active_sources": entry.total_active_sources,
                "aligned_sources": entry.aligned_sources,
                "threshold_stale_source_count": entry.threshold_stale_source_count,
                "persisted_stale_source_count": entry.persisted_stale_source_count,
                "missing_timestamp_source_ids": list(entry.missing_timestamp_source_ids),
                "threshold_mismatch_source_ids": list(entry.threshold_mismatch_source_ids),
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in stale_source_list_threshold_reconciliation.entries
        ],
        "failures": list(stale_source_list_threshold_reconciliation.failures),
        "diagnostics": list(stale_source_list_threshold_reconciliation.diagnostics),
        "paper_safe": stale_source_list_threshold_reconciliation.paper_safe,
        "network_calls": stale_source_list_threshold_reconciliation.network_calls,
        "execution_side_effects": stale_source_list_threshold_reconciliation.execution_side_effects,
    }

def _serialize_source_diagnostics_freshness_evaluation_mode_drift(
    source_diagnostics_freshness_evaluation_mode_drift: SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_diagnostics_freshness_evaluation_mode_drift.drift_classification,
        "average_mode_consistency_score": source_diagnostics_freshness_evaluation_mode_drift.average_mode_consistency_score,
        "severity_score": source_diagnostics_freshness_evaluation_mode_drift.severity_score,
        "total_snapshots_requested": source_diagnostics_freshness_evaluation_mode_drift.total_snapshots_requested,
        "snapshots_checked": source_diagnostics_freshness_evaluation_mode_drift.snapshots_checked,
        "stable_snapshots": source_diagnostics_freshness_evaluation_mode_drift.stable_snapshots,
        "drifting_snapshots": source_diagnostics_freshness_evaluation_mode_drift.drifting_snapshots,
        "degraded_snapshots": source_diagnostics_freshness_evaluation_mode_drift.degraded_snapshots,
        "insufficient_data_snapshots": source_diagnostics_freshness_evaluation_mode_drift.insufficient_data_snapshots,
        "dominant_freshness_evaluation_mode": source_diagnostics_freshness_evaluation_mode_drift.dominant_freshness_evaluation_mode,
        "latest_freshness_evaluation_mode": source_diagnostics_freshness_evaluation_mode_drift.latest_freshness_evaluation_mode,
        "freshness_evaluation_mode_counts": source_diagnostics_freshness_evaluation_mode_drift.freshness_evaluation_mode_counts,
        "mode_transition_count": source_diagnostics_freshness_evaluation_mode_drift.mode_transition_count,
        "malformed_summary_count": source_diagnostics_freshness_evaluation_mode_drift.malformed_summary_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "freshness_evaluation_mode": entry.freshness_evaluation_mode,
                "previous_freshness_evaluation_mode": entry.previous_freshness_evaluation_mode,
                "mode_consistency_score": entry.mode_consistency_score,
                "total_features": entry.total_features,
                "features_with_stale_sources": entry.features_with_stale_sources,
                "total_stale_assets": entry.total_stale_assets,
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_diagnostics_freshness_evaluation_mode_drift.entries
        ],
        "failures": list(source_diagnostics_freshness_evaluation_mode_drift.failures),
        "diagnostics": list(source_diagnostics_freshness_evaluation_mode_drift.diagnostics),
        "paper_safe": source_diagnostics_freshness_evaluation_mode_drift.paper_safe,
        "network_calls": source_diagnostics_freshness_evaluation_mode_drift.network_calls,
        "execution_side_effects": source_diagnostics_freshness_evaluation_mode_drift.execution_side_effects,
    }

