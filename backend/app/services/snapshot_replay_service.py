
from __future__ import annotations

from collections import Counter

from app.services.snapshot_replay_models import (
    RollingBacktestDiagnostics,
    SnapshotReplayResult,
    SnapshotBacktestResult,
    SnapshotComparisonResult,
    SnapshotDriftClassification,
    SnapshotAnomalyWatchlistItem,
    SnapshotAnomalyWatchlistDiagnostics,
    SnapshotDriftTrendScore,
    SnapshotDriftTrendLeaderboardEntry,
    SnapshotDriftTrendLeaderboard,
    SnapshotReplayRegimeSummary,
    SnapshotReplayRegimeTimelineEntry,
    SnapshotReplayRegimeTimeline,
    SnapshotTriggerPersistenceLeaderboardEntry,
    SnapshotTriggerPersistenceLeaderboard,
    SnapshotRiskActionStability,
    SnapshotSourceGapRecurrenceEntry,
    SnapshotSourceGapRecurrenceLeaderboard,
    SnapshotSourceFreshnessDecayTimelineEntry,
    SnapshotSourceFreshnessDecayTimeline,
    SnapshotNoExecutionGuardrailEntry,
    SnapshotNoExecutionGuardrailConsistency,
    SnapshotFallbackUsageTimelineEntry,
    SnapshotFallbackUsageRecurrenceEntry,
    SnapshotFallbackUsageRecurrence,
    SnapshotRawPayloadReferenceCompletenessEntry,
    SnapshotRawPayloadReferenceCompleteness,
    SnapshotSourceObservationCadenceEntry,
    SnapshotSourceObservationCadenceDrift,
    SnapshotSourceRecordCompletenessEntry,
    SnapshotSourceRecordCompleteness,
    SnapshotSourceRegistryBindingDriftEntry,
    SnapshotSourceRegistryBindingDrift,
    SnapshotSourceDecisionUsageConsistencyEntry,
    SnapshotSourceDecisionUsageConsistency,
    SnapshotSourceVerificationDriftEntry,
    SnapshotSourceVerificationDrift,
    SnapshotPaperSafeSourceFlagConsistencyEntry,
    SnapshotPaperSafeSourceFlagConsistency,
    SnapshotSourceObservationSummaryDriftEntry,
    SnapshotSourceObservationSummaryDrift,
    SnapshotProviderAdapterContractConsistencyEntry,
    SnapshotProviderAdapterContractConsistency,
    SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry,
    SnapshotReplayRouteSerializerGroupAlignmentConsistency,
    SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry,
    SnapshotReplaySourceDiagnosticGroupCoverageDrift,
    SnapshotReplayContractSurfaceCountConsistencyEntry,
    SnapshotReplayContractSurfaceCountConsistency,
    SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry,
    SnapshotReplaySourceDiagnosticSurfaceCountDrift,
    SnapshotReplayContractMetadataNormalizationConsistencyEntry,
    SnapshotReplayContractMetadataNormalizationConsistency,
    SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry,
    SnapshotReplaySourceDiagnosticMetadataCompletenessDrift,
    SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry,
    SnapshotReplayBuilderSerializerRouteNamingConsistency,
    SnapshotReplaySourceDiagnosticNamingContractDriftEntry,
    SnapshotReplaySourceDiagnosticNamingContractDrift,
    SnapshotReplayFullSurfaceContractSignatureConsistencyEntry,
    SnapshotReplayFullSurfaceContractSignatureConsistency,
    SnapshotReplaySourceDiagnosticContractSignatureDriftEntry,
    SnapshotReplaySourceDiagnosticContractSignatureDrift,
    SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry,
    SnapshotReplayDiagnosticEndpointCoverageConsistency,
    SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry,
    SnapshotReplaySourceDiagnosticsContractCoverageDrift,
    SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry,
    SnapshotReplayDedicatedRollingDiagnosticConsistency,
    SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry,
    SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift,
    SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry,
    SnapshotReplaySourceDiagnosticContractFieldSetDrift,
    SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry,
    SnapshotReplayFullSurfaceResponseFieldSetConsistency,
    SnapshotSourceObservationTimestampIntegrityDriftEntry,
    SnapshotSourceObservationTimestampIntegrityDrift,
    SnapshotSourceObservationRecordSummaryReconciliationEntry,
    SnapshotSourceObservationRecordSummaryReconciliation,
    SnapshotSourceObservationNormalizationModeDriftEntry,
    SnapshotSourceObservationNormalizationModeDrift,
    SnapshotMappedAtAlignmentConsistencyEntry,
    SnapshotMappedAtAlignmentConsistency,
    SnapshotSourceObservationConfidenceDriftEntry,
    SnapshotSourceObservationConfidenceDrift,
    SnapshotVerifiedSourceCoverageReconciliationEntry,
    SnapshotVerifiedSourceCoverageReconciliation,
    SnapshotSourceObservationAvailabilityLagDriftEntry,
    SnapshotSourceObservationAvailabilityLagDrift,
    SnapshotSourceFreshnessSummaryReconciliationEntry,
    SnapshotSourceFreshnessSummaryReconciliation,
    SnapshotSourceFreshnessPolicyDriftEntry,
    SnapshotSourceFreshnessPolicyDrift,
    SnapshotStaleSourceListThresholdReconciliationEntry,
    SnapshotStaleSourceListThresholdReconciliation,
    SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry,
    SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
    SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry,
    SnapshotSourceDiagnosticsStaleAssetCountReconciliation,
    SnapshotSourceDiagnosticsAverageCoverageDriftEntry,
    SnapshotSourceDiagnosticsAverageCoverageDrift,
    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry,
    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
    SnapshotSourceDiagnosticsReadyFeatureDriftEntry,
    SnapshotSourceDiagnosticsReadyFeatureDrift,
    SnapshotSourceDiagnosticsStaleFeatureDriftEntry,
    SnapshotSourceDiagnosticsStaleFeatureDrift,
    SnapshotSourceDiagnosticsCriticalFeatureDriftEntry,
    SnapshotSourceDiagnosticsCriticalFeatureDrift,
    SnapshotSourceDiagnosticsHighSeverityDriftEntry,
    SnapshotSourceDiagnosticsHighSeverityDrift,
    SnapshotSourceDiagnosticsWarningFeatureDriftEntry,
    SnapshotSourceDiagnosticsWarningFeatureDrift,
    SnapshotSourceDiagnosticsInfoFeatureDriftEntry,
    SnapshotSourceDiagnosticsInfoFeatureDrift,
    SnapshotSourceDiagnosticsZeroRankDriftEntry,
    SnapshotSourceDiagnosticsZeroRankDrift,
    SnapshotSourceDiagnosticsSeverityLabelDriftEntry,
    SnapshotSourceDiagnosticsSeverityLabelDrift,
    SnapshotSourceDiagnosticsSeverityRankDriftEntry,
    SnapshotSourceDiagnosticsSeverityRankDrift,
    SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry,
    SnapshotSourceDiagnosticsSeverityRankDensityDrift,
    SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry,
    SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
    SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation,
    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry,
    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
    SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry,
    SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
    SnapshotSourceObservationFreshnessSecondsDriftEntry,
    SnapshotSourceObservationFreshnessSecondsDrift,
    SnapshotSourceFreshnessStatusThresholdReconciliationEntry,
    SnapshotSourceFreshnessStatusThresholdReconciliation,
    SnapshotDqsStabilityPathEntry,
    SnapshotDqsStability,
)
from app.services.snapshot_replay_regime_diagnostics import SnapshotReplayRegimeDiagnostics
from app.services.snapshot_replay_source_diagnostics import SnapshotReplaySourceDiagnostics
from app.services.snapshot_replay_transition_diagnostics import SnapshotReplayTransitionDiagnostics


class SnapshotReplayService(
    SnapshotReplaySourceDiagnostics,
    SnapshotReplayRegimeDiagnostics,
    SnapshotReplayTransitionDiagnostics,
):
    def build_rolling_backtest_diagnostics(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> RollingBacktestDiagnostics:
        backtest_result, ordered_replay_results = self._run_ordered_backtest(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        comparison_results = tuple(
            self.compare_replay_results(
                ordered_replay_results[index - 1],
                ordered_replay_results[index],
            )
            for index in range(1, len(ordered_replay_results))
        )
        drift_classifications = tuple(
            self.classify_comparison_result(comparison_result)
            for comparison_result in comparison_results
        )

        risk_action_counts = Counter(
            replay_result.risk_engine_result.risk_action.value
            for replay_result in ordered_replay_results
        )
        trigger_transition_counts = Counter()
        for comparison_result in comparison_results:
            trigger_transition_counts.update(comparison_result.new_trigger_codes)

        anomaly_watchlist = self._build_anomaly_watchlist(drift_classifications, comparison_results)
        drift_trend_score = self._build_drift_trend_score(
            drift_classifications,
            failure_count=backtest_result.failed_replays,
        )
        drift_trend_leaderboard = self._build_drift_trend_leaderboard(drift_classifications)
        trigger_persistence_leaderboard = self._build_trigger_persistence_leaderboard(
            ordered_replay_results,
        )
        source_gap_recurrence_leaderboard = self._build_source_gap_recurrence_leaderboard(
            ordered_replay_results,
        )
        source_freshness_decay_timeline = self._build_source_freshness_decay_timeline(
            ordered_replay_results,
            failure_count=backtest_result.failed_replays,
            failures=backtest_result.failures,
            total_snapshots_requested=backtest_result.total_snapshots_requested,
        )
        snapshot_payloads, payload_failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        fallback_usage_recurrence = self._build_fallback_usage_recurrence(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        raw_payload_reference_completeness = self._build_raw_payload_reference_completeness(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_observation_cadence_drift = self._build_source_observation_cadence_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_record_completeness = self._build_source_record_completeness(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_registry_binding_drift = self._build_source_registry_binding_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_decision_usage_consistency = self._build_source_decision_usage_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_verification_drift = self._build_source_verification_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        paper_safe_source_flag_consistency = self._build_paper_safe_source_flag_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_observation_summary_drift = self._build_source_observation_summary_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        provider_adapter_contract_consistency = self._build_provider_adapter_contract_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_observation_timestamp_integrity_drift = (
            self._build_source_observation_timestamp_integrity_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_observation_record_summary_reconciliation = (
            self._build_source_observation_record_summary_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_observation_normalization_mode_drift = (
            self._build_source_observation_normalization_mode_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        mapped_at_alignment_consistency = self._build_mapped_at_alignment_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        source_observation_confidence_drift = self._build_source_observation_confidence_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        verified_source_coverage_reconciliation = (
            self._build_verified_source_coverage_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_observation_availability_lag_drift = (
            self._build_source_observation_availability_lag_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_freshness_summary_reconciliation = (
            self._build_source_freshness_summary_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_freshness_policy_drift = self._build_source_freshness_policy_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )
        stale_source_list_threshold_reconciliation = (
            self._build_stale_source_list_threshold_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_freshness_evaluation_mode_drift = (
            self._build_source_diagnostics_freshness_evaluation_mode_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_stale_asset_count_reconciliation = (
            self._build_source_diagnostics_stale_asset_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_average_coverage_drift = (
            self._build_source_diagnostics_average_coverage_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_minimum_coverage_floor_reconciliation = (
            self._build_source_diagnostics_minimum_coverage_floor_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_ready_feature_drift = (
            self._build_source_diagnostics_ready_feature_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_stale_feature_drift = (
            self._build_source_diagnostics_stale_feature_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_critical_feature_drift = (
            self._build_source_diagnostics_critical_feature_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_high_severity_drift = (
            self._build_source_diagnostics_high_severity_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_warning_feature_drift = (
            self._build_source_diagnostics_warning_feature_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_info_feature_drift = (
            self._build_source_diagnostics_info_feature_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_zero_rank_drift = (
            self._build_source_diagnostics_zero_rank_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_label_drift = (
            self._build_source_diagnostics_severity_label_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_rank_drift = (
            self._build_source_diagnostics_severity_rank_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_rank_density_drift = (
            self._build_source_diagnostics_severity_rank_density_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_rank_spread_drift = (
            self._build_source_diagnostics_severity_rank_spread_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_feature_count_reconciliation = (
            self._build_source_diagnostics_severity_ranking_feature_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_warning_count_reconciliation = (
            self._build_source_diagnostics_severity_ranking_warning_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_info_count_reconciliation = (
            self._build_source_diagnostics_severity_ranking_info_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_non_actionable_count_reconciliation = (
            self._build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_rank_label_consistency_reconciliation = (
            self._build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_rank_order_continuity_reconciliation = (
            self._build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation = (
            self._build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation = (
            self._build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_severity_ranking_critical_count_reconciliation = (
            self._build_source_diagnostics_severity_ranking_critical_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_missing_source_feature_count_reconciliation = (
            self._build_source_diagnostics_missing_source_feature_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_diagnostics_missing_asset_count_reconciliation = (
            self._build_source_diagnostics_missing_asset_count_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_observation_freshness_seconds_drift = (
            self._build_source_observation_freshness_seconds_drift(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        source_freshness_status_threshold_reconciliation = (
            self._build_source_freshness_status_threshold_reconciliation(
                snapshot_payloads,
                total_snapshots_requested=total_requested,
                failures=payload_failures,
            )
        )
        regime_summary = self._build_replay_regime_summary(ordered_replay_results)
        regime_timeline = self._build_replay_regime_timeline(
            ordered_replay_results,
            regime_summary=regime_summary,
        )
        dqs_stability = self._build_dqs_stability(
            ordered_replay_results,
            failure_count=backtest_result.failed_replays,
        )
        risk_action_stability = self._build_risk_action_stability(
            ordered_replay_results,
            failure_count=backtest_result.failed_replays,
        )
        no_execution_guardrail_consistency = self._build_no_execution_guardrail_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=payload_failures,
        )

        return RollingBacktestDiagnostics(
            total_snapshots_requested=backtest_result.total_snapshots_requested,
            successful_replays=backtest_result.successful_replays,
            failed_replays=backtest_result.failed_replays,
            ordered_snapshot_ids=tuple(
                replay_result.snapshot_id
                for replay_result in ordered_replay_results
            ),
            risk_action_path=tuple(
                {
                    "snapshot_id": replay_result.snapshot_id,
                    "created_at": replay_result.created_at,
                    "risk_action": replay_result.risk_engine_result.risk_action.value,
                    "kill_switch_active": replay_result.risk_engine_result.kill_switch_active,
                }
                for replay_result in ordered_replay_results
            ),
            comparisons_generated=len(comparison_results),
            risk_action_changes=sum(
                1
                for comparison_result in comparison_results
                if comparison_result.risk_action_changed
            ),
            kill_switch_count=sum(
                1
                for replay_result in ordered_replay_results
                if replay_result.risk_engine_result.kill_switch_active
            ),
            risk_action_counts=dict(sorted(risk_action_counts.items())),
            trigger_transition_counts=dict(sorted(trigger_transition_counts.items())),
            comparison_results=comparison_results,
            drift_classifications=drift_classifications,
            drift_trend_score=drift_trend_score,
            drift_trend_leaderboard=drift_trend_leaderboard,
            trigger_persistence_leaderboard=trigger_persistence_leaderboard,
            source_gap_recurrence_leaderboard=source_gap_recurrence_leaderboard,
            source_freshness_decay_timeline=source_freshness_decay_timeline,
            fallback_usage_recurrence=fallback_usage_recurrence,
            raw_payload_reference_completeness=raw_payload_reference_completeness,
            source_observation_cadence_drift=source_observation_cadence_drift,
            source_record_completeness=source_record_completeness,
            source_registry_binding_drift=source_registry_binding_drift,
            source_decision_usage_consistency=source_decision_usage_consistency,
            source_verification_drift=source_verification_drift,
            paper_safe_source_flag_consistency=paper_safe_source_flag_consistency,
            source_observation_summary_drift=source_observation_summary_drift,
            provider_adapter_contract_consistency=provider_adapter_contract_consistency,
            source_observation_timestamp_integrity_drift=source_observation_timestamp_integrity_drift,
            source_observation_record_summary_reconciliation=source_observation_record_summary_reconciliation,
            source_observation_normalization_mode_drift=source_observation_normalization_mode_drift,
            mapped_at_alignment_consistency=mapped_at_alignment_consistency,
            source_observation_confidence_drift=source_observation_confidence_drift,
            verified_source_coverage_reconciliation=verified_source_coverage_reconciliation,
            source_observation_availability_lag_drift=source_observation_availability_lag_drift,
            source_freshness_summary_reconciliation=source_freshness_summary_reconciliation,
            source_freshness_policy_drift=source_freshness_policy_drift,
            stale_source_list_threshold_reconciliation=stale_source_list_threshold_reconciliation,
            source_diagnostics_freshness_evaluation_mode_drift=source_diagnostics_freshness_evaluation_mode_drift,
            source_diagnostics_stale_asset_count_reconciliation=source_diagnostics_stale_asset_count_reconciliation,
            source_diagnostics_average_coverage_drift=source_diagnostics_average_coverage_drift,
            source_diagnostics_minimum_coverage_floor_reconciliation=source_diagnostics_minimum_coverage_floor_reconciliation,
            source_diagnostics_ready_feature_drift=source_diagnostics_ready_feature_drift,
            source_diagnostics_stale_feature_drift=source_diagnostics_stale_feature_drift,
            source_diagnostics_critical_feature_drift=source_diagnostics_critical_feature_drift,
            source_diagnostics_high_severity_drift=source_diagnostics_high_severity_drift,
            source_diagnostics_warning_feature_drift=source_diagnostics_warning_feature_drift,
            source_diagnostics_info_feature_drift=source_diagnostics_info_feature_drift,
            source_diagnostics_zero_rank_drift=source_diagnostics_zero_rank_drift,
            source_diagnostics_severity_label_drift=source_diagnostics_severity_label_drift,
            source_diagnostics_severity_rank_drift=source_diagnostics_severity_rank_drift,
            source_diagnostics_severity_rank_density_drift=source_diagnostics_severity_rank_density_drift,
            source_diagnostics_severity_rank_spread_drift=source_diagnostics_severity_rank_spread_drift,
            source_diagnostics_severity_ranking_feature_count_reconciliation=source_diagnostics_severity_ranking_feature_count_reconciliation,
            source_diagnostics_severity_ranking_warning_count_reconciliation=source_diagnostics_severity_ranking_warning_count_reconciliation,
            source_diagnostics_severity_ranking_info_count_reconciliation=source_diagnostics_severity_ranking_info_count_reconciliation,
            source_diagnostics_severity_ranking_non_actionable_count_reconciliation=source_diagnostics_severity_ranking_non_actionable_count_reconciliation,
            source_diagnostics_severity_ranking_rank_label_consistency_reconciliation=source_diagnostics_severity_ranking_rank_label_consistency_reconciliation,
            source_diagnostics_severity_ranking_rank_order_continuity_reconciliation=source_diagnostics_severity_ranking_rank_order_continuity_reconciliation,
            source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation=source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation,
            source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation=source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation,
            source_diagnostics_severity_ranking_critical_count_reconciliation=source_diagnostics_severity_ranking_critical_count_reconciliation,
            source_diagnostics_missing_source_feature_count_reconciliation=source_diagnostics_missing_source_feature_count_reconciliation,
            source_diagnostics_missing_asset_count_reconciliation=source_diagnostics_missing_asset_count_reconciliation,
            source_observation_freshness_seconds_drift=source_observation_freshness_seconds_drift,
            source_freshness_status_threshold_reconciliation=source_freshness_status_threshold_reconciliation,
            regime_summary=regime_summary,
            regime_timeline=regime_timeline,
            dqs_stability=dqs_stability,
            risk_action_stability=risk_action_stability,
            no_execution_guardrail_consistency=no_execution_guardrail_consistency,
            anomaly_watchlist=anomaly_watchlist,
            failures=backtest_result.failures,
            paper_safe=all(
                self._is_paper_safe_replay_result(replay_result)
                for replay_result in ordered_replay_results
            ),
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = [
    "SnapshotReplayService",
    "RollingBacktestDiagnostics",
    "SnapshotReplayResult",
    "SnapshotBacktestResult",
    "SnapshotComparisonResult",
    "SnapshotDriftClassification",
    "SnapshotAnomalyWatchlistItem",
    "SnapshotAnomalyWatchlistDiagnostics",
    "SnapshotDriftTrendScore",
    "SnapshotDriftTrendLeaderboardEntry",
    "SnapshotDriftTrendLeaderboard",
    "SnapshotReplayRegimeSummary",
    "SnapshotReplayRegimeTimelineEntry",
    "SnapshotReplayRegimeTimeline",
    "SnapshotTriggerPersistenceLeaderboardEntry",
    "SnapshotTriggerPersistenceLeaderboard",
    "SnapshotRiskActionStability",
    "SnapshotSourceGapRecurrenceEntry",
    "SnapshotSourceGapRecurrenceLeaderboard",
    "SnapshotSourceFreshnessDecayTimelineEntry",
    "SnapshotSourceFreshnessDecayTimeline",
    "SnapshotNoExecutionGuardrailEntry",
    "SnapshotNoExecutionGuardrailConsistency",
    "SnapshotFallbackUsageTimelineEntry",
    "SnapshotFallbackUsageRecurrenceEntry",
    "SnapshotFallbackUsageRecurrence",
    "SnapshotRawPayloadReferenceCompletenessEntry",
    "SnapshotRawPayloadReferenceCompleteness",
    "SnapshotSourceObservationCadenceEntry",
    "SnapshotSourceObservationCadenceDrift",
    "SnapshotSourceRecordCompletenessEntry",
    "SnapshotSourceRecordCompleteness",
    "SnapshotSourceRegistryBindingDriftEntry",
    "SnapshotSourceRegistryBindingDrift",
    "SnapshotSourceDecisionUsageConsistencyEntry",
    "SnapshotSourceDecisionUsageConsistency",
    "SnapshotSourceVerificationDriftEntry",
    "SnapshotSourceVerificationDrift",
    "SnapshotPaperSafeSourceFlagConsistencyEntry",
    "SnapshotPaperSafeSourceFlagConsistency",
    "SnapshotSourceObservationSummaryDriftEntry",
    "SnapshotSourceObservationSummaryDrift",
    "SnapshotProviderAdapterContractConsistencyEntry",
    "SnapshotProviderAdapterContractConsistency",
    "SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry",
    "SnapshotReplayRouteSerializerGroupAlignmentConsistency",
    "SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry",
    "SnapshotReplaySourceDiagnosticGroupCoverageDrift",
    "SnapshotReplayContractSurfaceCountConsistencyEntry",
    "SnapshotReplayContractSurfaceCountConsistency",
    "SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry",
    "SnapshotReplaySourceDiagnosticSurfaceCountDrift",
    "SnapshotReplayContractMetadataNormalizationConsistencyEntry",
    "SnapshotReplayContractMetadataNormalizationConsistency",
    "SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry",
    "SnapshotReplaySourceDiagnosticMetadataCompletenessDrift",
    "SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry",
    "SnapshotReplayBuilderSerializerRouteNamingConsistency",
    "SnapshotReplaySourceDiagnosticNamingContractDriftEntry",
    "SnapshotReplaySourceDiagnosticNamingContractDrift",
    "SnapshotReplayFullSurfaceContractSignatureConsistencyEntry",
    "SnapshotReplayFullSurfaceContractSignatureConsistency",
    "SnapshotReplaySourceDiagnosticContractSignatureDriftEntry",
    "SnapshotReplaySourceDiagnosticContractSignatureDrift",
    "SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry",
    "SnapshotReplayDiagnosticEndpointCoverageConsistency",
    "SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry",
    "SnapshotReplaySourceDiagnosticsContractCoverageDrift",
    "SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry",
    "SnapshotReplayDedicatedRollingDiagnosticConsistency",
    "SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry",
    "SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift",
    "SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry",
    "SnapshotReplaySourceDiagnosticContractFieldSetDrift",
    "SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry",
    "SnapshotReplayFullSurfaceResponseFieldSetConsistency",
    "SnapshotSourceObservationTimestampIntegrityDriftEntry",
    "SnapshotSourceObservationTimestampIntegrityDrift",
    "SnapshotSourceObservationRecordSummaryReconciliationEntry",
    "SnapshotSourceObservationRecordSummaryReconciliation",
    "SnapshotSourceObservationNormalizationModeDriftEntry",
    "SnapshotSourceObservationNormalizationModeDrift",
    "SnapshotMappedAtAlignmentConsistencyEntry",
    "SnapshotMappedAtAlignmentConsistency",
    "SnapshotSourceObservationConfidenceDriftEntry",
    "SnapshotSourceObservationConfidenceDrift",
    "SnapshotVerifiedSourceCoverageReconciliationEntry",
    "SnapshotVerifiedSourceCoverageReconciliation",
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
    "SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry",
    "SnapshotSourceDiagnosticsStaleAssetCountReconciliation",
    "SnapshotSourceDiagnosticsAverageCoverageDriftEntry",
    "SnapshotSourceDiagnosticsAverageCoverageDrift",
    "SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry",
    "SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation",
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
    "SnapshotSourceObservationFreshnessSecondsDriftEntry",
    "SnapshotSourceObservationFreshnessSecondsDrift",
    "SnapshotSourceFreshnessStatusThresholdReconciliationEntry",
    "SnapshotSourceFreshnessStatusThresholdReconciliation",
    "SnapshotDqsStabilityPathEntry",
    "SnapshotDqsStability",
]
