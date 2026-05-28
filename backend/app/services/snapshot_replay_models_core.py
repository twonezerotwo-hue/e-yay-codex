
from __future__ import annotations

from app.services.snapshot_replay_models_source_quality import SnapshotRawPayloadReferenceCompleteness
from app.services.snapshot_replay_models_source_quality import SnapshotSourceRecordCompleteness
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDecisionUsageConsistency
from app.services.snapshot_replay_models_source_quality import SnapshotSourceObservationRecordSummaryReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotVerifiedSourceCoverageReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsStaleAssetCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsMissingAssetCountReconciliation
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsAverageCoverageDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsReadyFeatureDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsStaleFeatureDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsCriticalFeatureDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsHighSeverityDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsWarningFeatureDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsInfoFeatureDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsZeroRankDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsSeverityLabelDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsSeverityRankDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsSeverityRankDensityDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceDiagnosticsSeverityRankSpreadDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceObservationConfidenceDrift
from app.services.snapshot_replay_models_source_drift import SnapshotSourceObservationSummaryDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessDecayTimeline
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationCadenceDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationFreshnessSecondsDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessStatusThresholdReconciliation
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessSummaryReconciliation
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessPolicyDrift
from app.services.snapshot_replay_models_source_timing import SnapshotStaleSourceListThresholdReconciliation
from app.services.snapshot_replay_models_source_timing import SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationTimestampIntegrityDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationNormalizationModeDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationAvailabilityLagDrift
from app.services.snapshot_replay_models_source_timing import SnapshotMappedAtAlignmentConsistency
from app.services.snapshot_replay_models_source_registry import SnapshotFallbackUsageRecurrence
from app.services.snapshot_replay_models_source_registry import SnapshotSourceGapRecurrenceLeaderboard
from app.services.snapshot_replay_models_source_registry import SnapshotSourceRegistryBindingDrift
from app.services.snapshot_replay_models_source_registry import SnapshotSourceVerificationDrift
from app.services.snapshot_replay_models_source_registry import SnapshotPaperSafeSourceFlagConsistency
from app.services.snapshot_replay_models_source_registry import SnapshotProviderAdapterContractConsistency
from app.services.snapshot_replay_models_source_registry import SnapshotNoExecutionGuardrailConsistency
from dataclasses import dataclass

from app.domain import MarketSnapshot
from app.services.ceo_report_service import CEOReport
from app.services.data_quality_service import DataQualityDecision
from app.services.risk_engine import RiskEngineResult
from app.services.risk_engine import SnapshotRiskInput
from app.services.trigger_engine import TriggerResult
from app.services.trigger_engine import TriggerSeverity

@dataclass(frozen=True)
class SnapshotReplayResult:
    snapshot_id: str
    created_at: str
    report_type: str
    mode: str
    execution_mode: str
    decision_permission: str
    source_registry_version: str
    feature_registry_version: str | None
    source_observations: dict[str, str]
    missing_sources: tuple[str, ...]
    stale_sources: tuple[str, ...]
    snapshots: tuple[MarketSnapshot, ...]
    snapshot_quality_results: tuple[SnapshotRiskInput, ...]
    trigger_results: tuple[TriggerResult, ...]
    risk_engine_result: RiskEngineResult
    ceo_report: CEOReport
    pipeline_summary: dict[str, object]
    audit_source_payload: dict[str, object] | None
    replay_regime: str | None
    replay_regime_diagnostic: str | None

@dataclass(frozen=True)
class SnapshotBacktestResult:
    total_snapshots_requested: int
    successful_replays: int
    failed_replays: int
    replay_results: tuple[SnapshotReplayResult, ...]
    failures: tuple[dict[str, str], ...]

@dataclass(frozen=True)
class SnapshotComparisonResult:
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    baseline_created_at: str
    candidate_created_at: str
    baseline_report_type: str
    candidate_report_type: str
    risk_action_changed: bool
    risk_action_from: str
    risk_action_to: str
    kill_switch_changed: bool
    kill_switch_from: bool
    kill_switch_to: bool
    new_trigger_codes: tuple[str, ...]
    cleared_trigger_codes: tuple[str, ...]
    unchanged_trigger_codes: tuple[str, ...]
    new_reason_codes: tuple[str, ...]
    cleared_reason_codes: tuple[str, ...]
    missing_sources_added: tuple[str, ...]
    missing_sources_cleared: tuple[str, ...]
    stale_sources_added: tuple[str, ...]
    stale_sources_cleared: tuple[str, ...]
    execution_status_consistent: bool
    paper_safe: bool

@dataclass(frozen=True)
class SnapshotDriftClassification:
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    drift_code: str
    severity: TriggerSeverity
    summary: str
    anomaly_flags: tuple[str, ...]
    paper_safe: bool
    execution_status_consistent: bool

@dataclass(frozen=True)
class SnapshotAnomalyWatchlistItem:
    watchlist_code: str
    severity: TriggerSeverity
    occurrence_count: int
    first_snapshot_id: str
    latest_snapshot_id: str
    related_snapshot_pairs: tuple[str, ...]
    trigger_codes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    latest_summary: str

@dataclass(frozen=True)
class SnapshotAnomalyWatchlistDiagnostics:
    total_items: int
    stable_transitions: int
    improving_transitions: int
    anomalous_transitions: int
    watchlist_items: tuple[SnapshotAnomalyWatchlistItem, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotDriftTrendScore:
    trend_classification: str
    trend_score: int
    severity_bucket: str
    comparison_count: int
    improving_transitions: int
    deteriorating_transitions: int
    stable_transitions: int
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotDriftTrendLeaderboardEntry:
    rank: int
    drift_code: str
    direction: str
    severity: TriggerSeverity
    occurrence_count: int
    total_weight: int
    related_snapshot_pairs: tuple[str, ...]
    latest_summary: str

@dataclass(frozen=True)
class SnapshotDriftTrendLeaderboard:
    total_entries: int
    entries: tuple[SnapshotDriftTrendLeaderboardEntry, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotReplayRegimeSummary:
    status: str
    distribution_classification: str
    dominant_regime: str | None
    regime_distribution: dict[str, int]
    transition_count: int
    mixed_or_unstable: bool
    available_regime_count: int
    missing_regime_count: int
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotReplayRegimeTimelineEntry:
    snapshot_id: str
    created_at: str
    replay_regime: str | None
    status: str
    diagnostic: str | None
    transition_from_previous: bool
    dominant_regime_match: bool

@dataclass(frozen=True)
class SnapshotReplayRegimeTimeline:
    status: str
    total_snapshots: int
    dominant_regime: str | None
    transition_count: int
    mixed_or_unstable: bool
    available_regime_count: int
    missing_regime_count: int
    entries: tuple[SnapshotReplayRegimeTimelineEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotTriggerPersistenceLeaderboardEntry:
    rank: int
    trigger_code: str
    asset_symbol: str
    severity: TriggerSeverity
    persistence_classification: str
    active_snapshot_count: int
    persistence_ratio: float
    longest_streak: int
    first_snapshot_id: str
    latest_snapshot_id: str
    active_snapshot_ids: tuple[str, ...]
    latest_message: str

@dataclass(frozen=True)
class SnapshotTriggerPersistenceLeaderboard:
    total_entries: int
    total_snapshots: int
    entries: tuple[SnapshotTriggerPersistenceLeaderboardEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotRiskActionStability:
    stability_classification: str
    dominant_risk_action: str | None
    first_risk_action: str | None
    latest_risk_action: str | None
    transition_count: int
    longest_stable_run: int
    unique_action_count: int
    risk_action_counts: dict[str, int]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotDqsStabilityPathEntry:
    snapshot_id: str
    created_at: str
    aggregate_decision: DataQualityDecision
    minimum_score: float
    average_score: float
    core_snapshot_count: int

@dataclass(frozen=True)
class SnapshotDqsStability:
    stability_classification: str
    dominant_decision: str | None
    first_decision: str | None
    latest_decision: str | None
    transition_count: int
    unique_decision_count: int
    lowest_minimum_score: float | None
    highest_minimum_score: float | None
    average_score_delta: float
    decision_counts: dict[str, int]
    path: tuple[SnapshotDqsStabilityPathEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class RollingBacktestDiagnostics:
    total_snapshots_requested: int
    successful_replays: int
    failed_replays: int
    ordered_snapshot_ids: tuple[str, ...]
    risk_action_path: tuple[dict[str, object], ...]
    comparisons_generated: int
    risk_action_changes: int
    kill_switch_count: int
    risk_action_counts: dict[str, int]
    trigger_transition_counts: dict[str, int]
    comparison_results: tuple[SnapshotComparisonResult, ...]
    drift_classifications: tuple[SnapshotDriftClassification, ...]
    drift_trend_score: SnapshotDriftTrendScore
    drift_trend_leaderboard: SnapshotDriftTrendLeaderboard
    trigger_persistence_leaderboard: SnapshotTriggerPersistenceLeaderboard
    source_gap_recurrence_leaderboard: SnapshotSourceGapRecurrenceLeaderboard
    source_freshness_decay_timeline: SnapshotSourceFreshnessDecayTimeline
    fallback_usage_recurrence: SnapshotFallbackUsageRecurrence
    raw_payload_reference_completeness: SnapshotRawPayloadReferenceCompleteness
    source_observation_cadence_drift: SnapshotSourceObservationCadenceDrift
    source_record_completeness: SnapshotSourceRecordCompleteness
    source_registry_binding_drift: SnapshotSourceRegistryBindingDrift
    source_decision_usage_consistency: SnapshotSourceDecisionUsageConsistency
    source_verification_drift: SnapshotSourceVerificationDrift
    paper_safe_source_flag_consistency: SnapshotPaperSafeSourceFlagConsistency
    source_observation_summary_drift: SnapshotSourceObservationSummaryDrift
    provider_adapter_contract_consistency: SnapshotProviderAdapterContractConsistency
    source_observation_timestamp_integrity_drift: SnapshotSourceObservationTimestampIntegrityDrift
    source_observation_record_summary_reconciliation: SnapshotSourceObservationRecordSummaryReconciliation
    source_observation_normalization_mode_drift: SnapshotSourceObservationNormalizationModeDrift
    mapped_at_alignment_consistency: SnapshotMappedAtAlignmentConsistency
    source_observation_confidence_drift: SnapshotSourceObservationConfidenceDrift
    verified_source_coverage_reconciliation: SnapshotVerifiedSourceCoverageReconciliation
    source_observation_availability_lag_drift: SnapshotSourceObservationAvailabilityLagDrift
    source_freshness_summary_reconciliation: SnapshotSourceFreshnessSummaryReconciliation
    source_freshness_policy_drift: SnapshotSourceFreshnessPolicyDrift
    stale_source_list_threshold_reconciliation: SnapshotStaleSourceListThresholdReconciliation
    source_diagnostics_freshness_evaluation_mode_drift: SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift
    source_diagnostics_stale_asset_count_reconciliation: SnapshotSourceDiagnosticsStaleAssetCountReconciliation
    source_diagnostics_average_coverage_drift: SnapshotSourceDiagnosticsAverageCoverageDrift
    source_diagnostics_minimum_coverage_floor_reconciliation: SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation
    source_diagnostics_ready_feature_drift: SnapshotSourceDiagnosticsReadyFeatureDrift
    source_diagnostics_stale_feature_drift: SnapshotSourceDiagnosticsStaleFeatureDrift
    source_diagnostics_critical_feature_drift: SnapshotSourceDiagnosticsCriticalFeatureDrift
    source_diagnostics_high_severity_drift: SnapshotSourceDiagnosticsHighSeverityDrift
    source_diagnostics_warning_feature_drift: SnapshotSourceDiagnosticsWarningFeatureDrift
    source_diagnostics_info_feature_drift: SnapshotSourceDiagnosticsInfoFeatureDrift
    source_diagnostics_zero_rank_drift: SnapshotSourceDiagnosticsZeroRankDrift
    source_diagnostics_severity_label_drift: SnapshotSourceDiagnosticsSeverityLabelDrift
    source_diagnostics_severity_rank_drift: SnapshotSourceDiagnosticsSeverityRankDrift
    source_diagnostics_severity_rank_density_drift: SnapshotSourceDiagnosticsSeverityRankDensityDrift
    source_diagnostics_severity_rank_spread_drift: SnapshotSourceDiagnosticsSeverityRankSpreadDrift
    source_diagnostics_severity_ranking_feature_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation
    source_diagnostics_severity_ranking_warning_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation
    source_diagnostics_severity_ranking_info_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation
    source_diagnostics_severity_ranking_non_actionable_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation
    source_diagnostics_severity_ranking_rank_label_consistency_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation
    source_diagnostics_severity_ranking_rank_order_continuity_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation
    source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation
    source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation: SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation
    source_diagnostics_severity_ranking_critical_count_reconciliation: SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation
    source_diagnostics_missing_source_feature_count_reconciliation: SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation
    source_diagnostics_missing_asset_count_reconciliation: SnapshotSourceDiagnosticsMissingAssetCountReconciliation
    source_observation_freshness_seconds_drift: SnapshotSourceObservationFreshnessSecondsDrift
    source_freshness_status_threshold_reconciliation: SnapshotSourceFreshnessStatusThresholdReconciliation
    regime_summary: SnapshotReplayRegimeSummary
    regime_timeline: SnapshotReplayRegimeTimeline
    dqs_stability: SnapshotDqsStability
    risk_action_stability: SnapshotRiskActionStability
    no_execution_guardrail_consistency: SnapshotNoExecutionGuardrailConsistency
    anomaly_watchlist: SnapshotAnomalyWatchlistDiagnostics
    failures: tuple[dict[str, str], ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

__all__ = [
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
    "SnapshotDqsStabilityPathEntry",
    "SnapshotDqsStability",
    "RollingBacktestDiagnostics",
]
