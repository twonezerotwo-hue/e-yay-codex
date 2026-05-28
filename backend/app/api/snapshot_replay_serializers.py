from __future__ import annotations

from collections import Counter


from app.services import SnapshotAnomalyWatchlistDiagnostics
from app.services import RollingBacktestDiagnostics
from app.services import SnapshotBacktestResult
from app.services import SnapshotComparisonResult
from app.services import SnapshotDriftClassification
from app.services import SnapshotDriftTrendLeaderboard
from app.services import SnapshotDriftTrendScore
from app.services import SnapshotDqsStability
from app.services import SnapshotReplayRegimeTimeline
from app.services import SnapshotReplayRegimeSummary
from app.services import SnapshotRiskActionStability
from app.services import SnapshotReplayResult
from app.services import SnapshotTriggerPersistenceLeaderboard
from app.api.snapshot_replay_source_serializers import (
    _serialize_fallback_usage_recurrence,
    _serialize_mapped_at_alignment_consistency,
    _serialize_no_execution_guardrail_consistency,
    _serialize_paper_safe_source_flag_consistency,
    _serialize_provider_adapter_contract_consistency,
    _serialize_raw_payload_reference_completeness,
    _serialize_source_decision_usage_consistency,
    _serialize_source_diagnostics_average_coverage_drift,
    _serialize_source_diagnostics_critical_feature_drift,
    _serialize_source_diagnostics_freshness_evaluation_mode_drift,
    _serialize_source_diagnostics_high_severity_drift,
    _serialize_source_diagnostics_info_feature_drift,
    _serialize_source_diagnostics_minimum_coverage_floor_reconciliation,
    _serialize_source_diagnostics_missing_asset_count_reconciliation,
    _serialize_source_diagnostics_missing_source_feature_count_reconciliation,
    _serialize_source_diagnostics_ready_feature_drift,
    _serialize_source_diagnostics_severity_label_drift,
    _serialize_source_diagnostics_severity_rank_density_drift,
    _serialize_source_diagnostics_severity_rank_drift,
    _serialize_source_diagnostics_severity_rank_spread_drift,
    _serialize_source_diagnostics_severity_ranking_critical_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_feature_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_info_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_non_actionable_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation,
    _serialize_source_diagnostics_severity_ranking_warning_count_reconciliation,
    _serialize_source_diagnostics_stale_asset_count_reconciliation,
    _serialize_source_diagnostics_stale_feature_drift,
    _serialize_source_diagnostics_warning_feature_drift,
    _serialize_source_diagnostics_zero_rank_drift,
    _serialize_source_freshness_decay_timeline,
    _serialize_source_freshness_policy_drift,
    _serialize_source_freshness_status_threshold_reconciliation,
    _serialize_source_freshness_summary_reconciliation,
    _serialize_source_gap_recurrence_leaderboard,
    _serialize_source_observation_availability_lag_drift,
    _serialize_source_observation_cadence_drift,
    _serialize_source_observation_confidence_drift,
    _serialize_source_observation_freshness_seconds_drift,
    _serialize_source_observation_normalization_mode_drift,
    _serialize_source_observation_record_summary_reconciliation,
    _serialize_source_observation_summary_drift,
    _serialize_source_observation_timestamp_integrity_drift,
    _serialize_source_record_completeness,
    _serialize_source_registry_binding_drift,
    _serialize_source_verification_drift,
    _serialize_stale_source_list_threshold_reconciliation,
    _serialize_verified_source_coverage_reconciliation,
)

def _serialize_trigger_results(replay_result: SnapshotReplayResult) -> list[dict[str, object]]:
    return [
        {
            "trigger_code": trigger.trigger_code,
            "severity": trigger.severity.value,
            "asset_symbol": trigger.asset_symbol,
            "is_triggered": trigger.is_triggered,
            "confirmation_status": trigger.confirmation_status.value,
            "message": trigger.message,
        }
        for trigger in replay_result.trigger_results
    ]


def _serialize_risk_engine_result(replay_result: SnapshotReplayResult) -> dict[str, object]:
    return {
        "risk_action": replay_result.risk_engine_result.risk_action.value,
        "reason_codes": list(replay_result.risk_engine_result.reason_codes),
        "summary": replay_result.risk_engine_result.summary,
        "kill_switch_active": replay_result.risk_engine_result.kill_switch_active,
    }


def _serialize_report(replay_result: SnapshotReplayResult) -> dict[str, object]:
    return {
        "report_title": replay_result.ceo_report.report_title,
        "regime_summary": replay_result.ceo_report.regime_summary,
        "key_triggers": list(replay_result.ceo_report.key_triggers),
        "risk_action": replay_result.ceo_report.risk_action.value,
        "owner_action": replay_result.ceo_report.owner_action,
        "execution_status": replay_result.ceo_report.execution_status,
        "short_report_sentences": list(replay_result.ceo_report.short_report_sentences),
    }


def _serialize_replay_result(replay_result: SnapshotReplayResult) -> dict[str, object]:
    return {
        "snapshot_id": replay_result.snapshot_id,
        "created_at": replay_result.created_at,
        "report_type": replay_result.report_type,
        "mode": replay_result.mode,
        "paper_safe": True,
        "execution_mode": replay_result.execution_mode,
        "decision_permission": replay_result.decision_permission,
        "source_registry_version": replay_result.source_registry_version,
        "feature_registry_version": replay_result.feature_registry_version,
        "snapshot_count": len(replay_result.snapshots),
        "source_observation_count": len(replay_result.source_observations),
        "missing_sources": list(replay_result.missing_sources),
        "stale_sources": list(replay_result.stale_sources),
        "pipeline_summary": replay_result.pipeline_summary,
        "trigger_results": _serialize_trigger_results(replay_result),
        "risk_engine_result": _serialize_risk_engine_result(replay_result),
        "report": _serialize_report(replay_result),
        "audit_source_payload": replay_result.audit_source_payload,
    }


def _serialize_drift_classification(
    drift_classification: SnapshotDriftClassification,
) -> dict[str, object]:
    return {
        "baseline_snapshot_id": drift_classification.baseline_snapshot_id,
        "candidate_snapshot_id": drift_classification.candidate_snapshot_id,
        "drift_code": drift_classification.drift_code,
        "severity": drift_classification.severity.value,
        "summary": drift_classification.summary,
        "anomaly_flags": list(drift_classification.anomaly_flags),
        "paper_safe": drift_classification.paper_safe,
        "execution_status_consistent": drift_classification.execution_status_consistent,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def _serialize_comparison_result(comparison_result: SnapshotComparisonResult) -> dict[str, object]:
    return {
        "baseline_snapshot_id": comparison_result.baseline_snapshot_id,
        "candidate_snapshot_id": comparison_result.candidate_snapshot_id,
        "baseline_created_at": comparison_result.baseline_created_at,
        "candidate_created_at": comparison_result.candidate_created_at,
        "baseline_report_type": comparison_result.baseline_report_type,
        "candidate_report_type": comparison_result.candidate_report_type,
        "risk_action_changed": comparison_result.risk_action_changed,
        "risk_action_from": comparison_result.risk_action_from,
        "risk_action_to": comparison_result.risk_action_to,
        "kill_switch_changed": comparison_result.kill_switch_changed,
        "kill_switch_from": comparison_result.kill_switch_from,
        "kill_switch_to": comparison_result.kill_switch_to,
        "new_trigger_codes": list(comparison_result.new_trigger_codes),
        "cleared_trigger_codes": list(comparison_result.cleared_trigger_codes),
        "unchanged_trigger_codes": list(comparison_result.unchanged_trigger_codes),
        "new_reason_codes": list(comparison_result.new_reason_codes),
        "cleared_reason_codes": list(comparison_result.cleared_reason_codes),
        "missing_sources_added": list(comparison_result.missing_sources_added),
        "missing_sources_cleared": list(comparison_result.missing_sources_cleared),
        "stale_sources_added": list(comparison_result.stale_sources_added),
        "stale_sources_cleared": list(comparison_result.stale_sources_cleared),
        "execution_status_consistent": comparison_result.execution_status_consistent,
        "paper_safe": comparison_result.paper_safe,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def _serialize_anomaly_watchlist(
    anomaly_watchlist: SnapshotAnomalyWatchlistDiagnostics,
) -> dict[str, object]:
    return {
        "summary": {
            "total_items": anomaly_watchlist.total_items,
            "stable_transitions": anomaly_watchlist.stable_transitions,
            "improving_transitions": anomaly_watchlist.improving_transitions,
            "anomalous_transitions": anomaly_watchlist.anomalous_transitions,
            "paper_safe": anomaly_watchlist.paper_safe,
            "network_calls": anomaly_watchlist.network_calls,
            "execution_side_effects": anomaly_watchlist.execution_side_effects,
        },
        "watchlist_items": [
            {
                "watchlist_code": watchlist_item.watchlist_code,
                "severity": watchlist_item.severity.value,
                "occurrence_count": watchlist_item.occurrence_count,
                "first_snapshot_id": watchlist_item.first_snapshot_id,
                "latest_snapshot_id": watchlist_item.latest_snapshot_id,
                "related_snapshot_pairs": list(watchlist_item.related_snapshot_pairs),
                "trigger_codes": list(watchlist_item.trigger_codes),
                "reason_codes": list(watchlist_item.reason_codes),
                "source_ids": list(watchlist_item.source_ids),
                "latest_summary": watchlist_item.latest_summary,
            }
            for watchlist_item in anomaly_watchlist.watchlist_items
        ],
    }


def _serialize_drift_trend_score(
    drift_trend_score: SnapshotDriftTrendScore,
) -> dict[str, object]:
    return {
        "trend_classification": drift_trend_score.trend_classification,
        "trend_score": drift_trend_score.trend_score,
        "severity_bucket": drift_trend_score.severity_bucket,
        "comparison_count": drift_trend_score.comparison_count,
        "improving_transitions": drift_trend_score.improving_transitions,
        "deteriorating_transitions": drift_trend_score.deteriorating_transitions,
        "stable_transitions": drift_trend_score.stable_transitions,
        "diagnostics": list(drift_trend_score.diagnostics),
        "paper_safe": drift_trend_score.paper_safe,
        "network_calls": drift_trend_score.network_calls,
        "execution_side_effects": drift_trend_score.execution_side_effects,
    }


def _serialize_drift_trend_leaderboard(
    drift_trend_leaderboard: SnapshotDriftTrendLeaderboard,
) -> dict[str, object]:
    return {
        "total_entries": drift_trend_leaderboard.total_entries,
        "entries": [
            {
                "rank": entry.rank,
                "drift_code": entry.drift_code,
                "direction": entry.direction,
                "severity": entry.severity.value,
                "occurrence_count": entry.occurrence_count,
                "total_weight": entry.total_weight,
                "related_snapshot_pairs": list(entry.related_snapshot_pairs),
                "latest_summary": entry.latest_summary,
            }
            for entry in drift_trend_leaderboard.entries
        ],
        "paper_safe": drift_trend_leaderboard.paper_safe,
        "network_calls": drift_trend_leaderboard.network_calls,
        "execution_side_effects": drift_trend_leaderboard.execution_side_effects,
    }


def _serialize_trigger_persistence_leaderboard(
    trigger_persistence_leaderboard: SnapshotTriggerPersistenceLeaderboard,
) -> dict[str, object]:
    return {
        "total_entries": trigger_persistence_leaderboard.total_entries,
        "total_snapshots": trigger_persistence_leaderboard.total_snapshots,
        "entries": [
            {
                "rank": entry.rank,
                "trigger_code": entry.trigger_code,
                "asset_symbol": entry.asset_symbol,
                "severity": entry.severity.value,
                "persistence_classification": entry.persistence_classification,
                "active_snapshot_count": entry.active_snapshot_count,
                "persistence_ratio": entry.persistence_ratio,
                "longest_streak": entry.longest_streak,
                "first_snapshot_id": entry.first_snapshot_id,
                "latest_snapshot_id": entry.latest_snapshot_id,
                "active_snapshot_ids": list(entry.active_snapshot_ids),
                "latest_message": entry.latest_message,
            }
            for entry in trigger_persistence_leaderboard.entries
        ],
        "diagnostics": list(trigger_persistence_leaderboard.diagnostics),
        "paper_safe": trigger_persistence_leaderboard.paper_safe,
        "network_calls": trigger_persistence_leaderboard.network_calls,
        "execution_side_effects": trigger_persistence_leaderboard.execution_side_effects,
    }



def _serialize_regime_summary(
    regime_summary: SnapshotReplayRegimeSummary,
) -> dict[str, object]:
    return {
        "status": regime_summary.status,
        "distribution_classification": regime_summary.distribution_classification,
        "dominant_regime": regime_summary.dominant_regime,
        "regime_distribution": regime_summary.regime_distribution,
        "transition_count": regime_summary.transition_count,
        "mixed_or_unstable": regime_summary.mixed_or_unstable,
        "available_regime_count": regime_summary.available_regime_count,
        "missing_regime_count": regime_summary.missing_regime_count,
        "diagnostics": list(regime_summary.diagnostics),
        "paper_safe": regime_summary.paper_safe,
        "network_calls": regime_summary.network_calls,
        "execution_side_effects": regime_summary.execution_side_effects,
    }


def _serialize_regime_timeline(
    regime_timeline: SnapshotReplayRegimeTimeline,
) -> dict[str, object]:
    return {
        "status": regime_timeline.status,
        "total_snapshots": regime_timeline.total_snapshots,
        "dominant_regime": regime_timeline.dominant_regime,
        "transition_count": regime_timeline.transition_count,
        "mixed_or_unstable": regime_timeline.mixed_or_unstable,
        "available_regime_count": regime_timeline.available_regime_count,
        "missing_regime_count": regime_timeline.missing_regime_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "replay_regime": entry.replay_regime,
                "status": entry.status,
                "diagnostic": entry.diagnostic,
                "transition_from_previous": entry.transition_from_previous,
                "dominant_regime_match": entry.dominant_regime_match,
            }
            for entry in regime_timeline.entries
        ],
        "diagnostics": list(regime_timeline.diagnostics),
        "paper_safe": regime_timeline.paper_safe,
        "network_calls": regime_timeline.network_calls,
        "execution_side_effects": regime_timeline.execution_side_effects,
    }


def _serialize_dqs_stability(
    dqs_stability: SnapshotDqsStability,
) -> dict[str, object]:
    return {
        "stability_classification": dqs_stability.stability_classification,
        "dominant_decision": dqs_stability.dominant_decision,
        "first_decision": dqs_stability.first_decision,
        "latest_decision": dqs_stability.latest_decision,
        "transition_count": dqs_stability.transition_count,
        "unique_decision_count": dqs_stability.unique_decision_count,
        "lowest_minimum_score": dqs_stability.lowest_minimum_score,
        "highest_minimum_score": dqs_stability.highest_minimum_score,
        "average_score_delta": dqs_stability.average_score_delta,
        "decision_counts": dqs_stability.decision_counts,
        "path": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "aggregate_decision": entry.aggregate_decision.value,
                "minimum_score": entry.minimum_score,
                "average_score": entry.average_score,
                "core_snapshot_count": entry.core_snapshot_count,
            }
            for entry in dqs_stability.path
        ],
        "diagnostics": list(dqs_stability.diagnostics),
        "paper_safe": dqs_stability.paper_safe,
        "network_calls": dqs_stability.network_calls,
        "execution_side_effects": dqs_stability.execution_side_effects,
    }


def _serialize_risk_action_stability(
    risk_action_stability: SnapshotRiskActionStability,
) -> dict[str, object]:
    return {
        "stability_classification": risk_action_stability.stability_classification,
        "dominant_risk_action": risk_action_stability.dominant_risk_action,
        "first_risk_action": risk_action_stability.first_risk_action,
        "latest_risk_action": risk_action_stability.latest_risk_action,
        "transition_count": risk_action_stability.transition_count,
        "longest_stable_run": risk_action_stability.longest_stable_run,
        "unique_action_count": risk_action_stability.unique_action_count,
        "risk_action_counts": risk_action_stability.risk_action_counts,
        "diagnostics": list(risk_action_stability.diagnostics),
        "paper_safe": risk_action_stability.paper_safe,
        "network_calls": risk_action_stability.network_calls,
        "execution_side_effects": risk_action_stability.execution_side_effects,
    }


def _summarize_backtest_result(backtest_result: SnapshotBacktestResult) -> dict[str, object]:
    risk_action_counts = Counter(
        replay_result.risk_engine_result.risk_action.value
        for replay_result in backtest_result.replay_results
    )
    trigger_hit_counts = Counter()
    report_type_counts = Counter()
    execution_statuses: set[str] = set()
    missing_source_snapshots = 0
    stale_source_snapshots = 0

    for replay_result in backtest_result.replay_results:
        report_type_counts[replay_result.report_type] += 1
        execution_statuses.add(replay_result.ceo_report.execution_status)
        if replay_result.missing_sources:
            missing_source_snapshots += 1
        if replay_result.stale_sources:
            stale_source_snapshots += 1

        for trigger in replay_result.trigger_results:
            if trigger.is_triggered:
                trigger_hit_counts[trigger.trigger_code] += 1

    return {
        "total_snapshots_requested": backtest_result.total_snapshots_requested,
        "successful_replays": backtest_result.successful_replays,
        "failed_replays": backtest_result.failed_replays,
        "successful_snapshot_ids": [
            replay_result.snapshot_id
            for replay_result in backtest_result.replay_results
        ],
        "failed_snapshot_ids": [
            failure["snapshot_id"]
            for failure in backtest_result.failures
        ],
        "report_type_counts": dict(sorted(report_type_counts.items())),
        "risk_action_counts": dict(sorted(risk_action_counts.items())),
        "trigger_hit_counts": dict(sorted(trigger_hit_counts.items())),
        "kill_switch_count": sum(
            1
            for replay_result in backtest_result.replay_results
            if replay_result.risk_engine_result.kill_switch_active
        ),
        "missing_source_snapshots": missing_source_snapshots,
        "stale_source_snapshots": stale_source_snapshots,
        "execution_statuses": sorted(execution_statuses),
        "failures": list(backtest_result.failures),
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def _serialize_rolling_backtest_diagnostics(
    rolling_diagnostics: RollingBacktestDiagnostics,
) -> dict[str, object]:
    return {
        "total_snapshots_requested": rolling_diagnostics.total_snapshots_requested,
        "successful_replays": rolling_diagnostics.successful_replays,
        "failed_replays": rolling_diagnostics.failed_replays,
        "ordered_snapshot_ids": list(rolling_diagnostics.ordered_snapshot_ids),
        "risk_action_path": list(rolling_diagnostics.risk_action_path),
        "comparisons_generated": rolling_diagnostics.comparisons_generated,
        "risk_action_changes": rolling_diagnostics.risk_action_changes,
        "kill_switch_count": rolling_diagnostics.kill_switch_count,
        "risk_action_counts": rolling_diagnostics.risk_action_counts,
        "trigger_transition_counts": rolling_diagnostics.trigger_transition_counts,
        "comparison_results": [
            _serialize_comparison_result(comparison_result)
            for comparison_result in rolling_diagnostics.comparison_results
        ],
        "drift_classifications": [
            _serialize_drift_classification(drift_classification)
            for drift_classification in rolling_diagnostics.drift_classifications
        ],
        "drift_trend_score": _serialize_drift_trend_score(rolling_diagnostics.drift_trend_score),
        "drift_trend_leaderboard": _serialize_drift_trend_leaderboard(
            rolling_diagnostics.drift_trend_leaderboard
        ),
        "trigger_persistence_leaderboard": _serialize_trigger_persistence_leaderboard(
            rolling_diagnostics.trigger_persistence_leaderboard
        ),
        "source_gap_recurrence_leaderboard": _serialize_source_gap_recurrence_leaderboard(
            rolling_diagnostics.source_gap_recurrence_leaderboard
        ),
        "source_freshness_decay_timeline": _serialize_source_freshness_decay_timeline(
            rolling_diagnostics.source_freshness_decay_timeline
        ),
        "fallback_usage_recurrence": _serialize_fallback_usage_recurrence(
            rolling_diagnostics.fallback_usage_recurrence
        ),
        "raw_payload_reference_completeness": _serialize_raw_payload_reference_completeness(
            rolling_diagnostics.raw_payload_reference_completeness
        ),
        "source_observation_cadence_drift": _serialize_source_observation_cadence_drift(
            rolling_diagnostics.source_observation_cadence_drift
        ),
        "source_record_completeness": _serialize_source_record_completeness(
            rolling_diagnostics.source_record_completeness
        ),
        "source_registry_binding_drift": _serialize_source_registry_binding_drift(
            rolling_diagnostics.source_registry_binding_drift
        ),
        "source_decision_usage_consistency": _serialize_source_decision_usage_consistency(
            rolling_diagnostics.source_decision_usage_consistency
        ),
        "source_verification_drift": _serialize_source_verification_drift(
            rolling_diagnostics.source_verification_drift
        ),
        "paper_safe_source_flag_consistency": _serialize_paper_safe_source_flag_consistency(
            rolling_diagnostics.paper_safe_source_flag_consistency
        ),
        "source_observation_summary_drift": _serialize_source_observation_summary_drift(
            rolling_diagnostics.source_observation_summary_drift
        ),
        "provider_adapter_contract_consistency": _serialize_provider_adapter_contract_consistency(
            rolling_diagnostics.provider_adapter_contract_consistency
        ),
        "source_observation_timestamp_integrity_drift": _serialize_source_observation_timestamp_integrity_drift(
            rolling_diagnostics.source_observation_timestamp_integrity_drift
        ),
        "source_observation_record_summary_reconciliation": _serialize_source_observation_record_summary_reconciliation(
            rolling_diagnostics.source_observation_record_summary_reconciliation
        ),
        "source_observation_normalization_mode_drift": _serialize_source_observation_normalization_mode_drift(
            rolling_diagnostics.source_observation_normalization_mode_drift
        ),
        "mapped_at_alignment_consistency": _serialize_mapped_at_alignment_consistency(
            rolling_diagnostics.mapped_at_alignment_consistency
        ),
        "source_observation_confidence_drift": _serialize_source_observation_confidence_drift(
            rolling_diagnostics.source_observation_confidence_drift
        ),
        "verified_source_coverage_reconciliation": _serialize_verified_source_coverage_reconciliation(
            rolling_diagnostics.verified_source_coverage_reconciliation
        ),
        "source_observation_availability_lag_drift": _serialize_source_observation_availability_lag_drift(
            rolling_diagnostics.source_observation_availability_lag_drift
        ),
        "source_freshness_summary_reconciliation": _serialize_source_freshness_summary_reconciliation(
            rolling_diagnostics.source_freshness_summary_reconciliation
        ),
        "source_freshness_policy_drift": _serialize_source_freshness_policy_drift(
            rolling_diagnostics.source_freshness_policy_drift
        ),
        "stale_source_list_threshold_reconciliation": _serialize_stale_source_list_threshold_reconciliation(
            rolling_diagnostics.stale_source_list_threshold_reconciliation
        ),
        "source_diagnostics_freshness_evaluation_mode_drift": _serialize_source_diagnostics_freshness_evaluation_mode_drift(
            rolling_diagnostics.source_diagnostics_freshness_evaluation_mode_drift
        ),
        "source_diagnostics_stale_asset_count_reconciliation": _serialize_source_diagnostics_stale_asset_count_reconciliation(
            rolling_diagnostics.source_diagnostics_stale_asset_count_reconciliation
        ),
        "source_diagnostics_average_coverage_drift": _serialize_source_diagnostics_average_coverage_drift(
            rolling_diagnostics.source_diagnostics_average_coverage_drift
        ),
        "source_diagnostics_minimum_coverage_floor_reconciliation": _serialize_source_diagnostics_minimum_coverage_floor_reconciliation(
            rolling_diagnostics.source_diagnostics_minimum_coverage_floor_reconciliation
        ),
        "source_diagnostics_ready_feature_drift": _serialize_source_diagnostics_ready_feature_drift(
            rolling_diagnostics.source_diagnostics_ready_feature_drift
        ),
        "source_diagnostics_stale_feature_drift": _serialize_source_diagnostics_stale_feature_drift(
            rolling_diagnostics.source_diagnostics_stale_feature_drift
        ),
        "source_diagnostics_critical_feature_drift": _serialize_source_diagnostics_critical_feature_drift(
            rolling_diagnostics.source_diagnostics_critical_feature_drift
        ),
        "source_diagnostics_high_severity_drift": _serialize_source_diagnostics_high_severity_drift(
            rolling_diagnostics.source_diagnostics_high_severity_drift
        ),
        "source_diagnostics_warning_feature_drift": _serialize_source_diagnostics_warning_feature_drift(
            rolling_diagnostics.source_diagnostics_warning_feature_drift
        ),
        "source_diagnostics_info_feature_drift": _serialize_source_diagnostics_info_feature_drift(
            rolling_diagnostics.source_diagnostics_info_feature_drift
        ),
        "source_diagnostics_zero_rank_drift": _serialize_source_diagnostics_zero_rank_drift(
            rolling_diagnostics.source_diagnostics_zero_rank_drift
        ),
        "source_diagnostics_severity_label_drift": _serialize_source_diagnostics_severity_label_drift(
            rolling_diagnostics.source_diagnostics_severity_label_drift
        ),
        "source_diagnostics_severity_rank_drift": _serialize_source_diagnostics_severity_rank_drift(
            rolling_diagnostics.source_diagnostics_severity_rank_drift
        ),
        "source_diagnostics_severity_rank_density_drift": _serialize_source_diagnostics_severity_rank_density_drift(
            rolling_diagnostics.source_diagnostics_severity_rank_density_drift
        ),
        "source_diagnostics_severity_rank_spread_drift": _serialize_source_diagnostics_severity_rank_spread_drift(
            rolling_diagnostics.source_diagnostics_severity_rank_spread_drift
        ),
        "source_diagnostics_severity_ranking_feature_count_reconciliation": _serialize_source_diagnostics_severity_ranking_feature_count_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_feature_count_reconciliation
        ),
        "source_diagnostics_severity_ranking_warning_count_reconciliation": _serialize_source_diagnostics_severity_ranking_warning_count_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_warning_count_reconciliation
        ),
        "source_diagnostics_severity_ranking_info_count_reconciliation": _serialize_source_diagnostics_severity_ranking_info_count_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_info_count_reconciliation
        ),
        "source_diagnostics_severity_ranking_non_actionable_count_reconciliation": _serialize_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_non_actionable_count_reconciliation
        ),
        "source_diagnostics_severity_ranking_rank_label_consistency_reconciliation": _serialize_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_rank_label_consistency_reconciliation
        ),
        "source_diagnostics_severity_ranking_rank_order_continuity_reconciliation": _serialize_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_rank_order_continuity_reconciliation
        ),
        "source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation": _serialize_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation
        ),
        "source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation": _serialize_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation
        ),
        "source_diagnostics_severity_ranking_critical_count_reconciliation": _serialize_source_diagnostics_severity_ranking_critical_count_reconciliation(
            rolling_diagnostics.source_diagnostics_severity_ranking_critical_count_reconciliation
        ),
        "source_diagnostics_missing_source_feature_count_reconciliation": _serialize_source_diagnostics_missing_source_feature_count_reconciliation(
            rolling_diagnostics.source_diagnostics_missing_source_feature_count_reconciliation
        ),
        "source_diagnostics_missing_asset_count_reconciliation": _serialize_source_diagnostics_missing_asset_count_reconciliation(
            rolling_diagnostics.source_diagnostics_missing_asset_count_reconciliation
        ),
        "source_observation_freshness_seconds_drift": _serialize_source_observation_freshness_seconds_drift(
            rolling_diagnostics.source_observation_freshness_seconds_drift
        ),
        "source_freshness_status_threshold_reconciliation": _serialize_source_freshness_status_threshold_reconciliation(
            rolling_diagnostics.source_freshness_status_threshold_reconciliation
        ),
        "regime_summary": _serialize_regime_summary(rolling_diagnostics.regime_summary),
        "regime_timeline": _serialize_regime_timeline(rolling_diagnostics.regime_timeline),
        "dqs_stability": _serialize_dqs_stability(rolling_diagnostics.dqs_stability),
        "risk_action_stability": _serialize_risk_action_stability(
            rolling_diagnostics.risk_action_stability
        ),
        "no_execution_guardrail_consistency": _serialize_no_execution_guardrail_consistency(
            rolling_diagnostics.no_execution_guardrail_consistency
        ),
        "anomaly_watchlist": _serialize_anomaly_watchlist(rolling_diagnostics.anomaly_watchlist),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }


