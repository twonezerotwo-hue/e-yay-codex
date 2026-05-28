from __future__ import annotations

from typing import Any
from app.services.snapshot_replay_core import SnapshotReplayCore
from .snapshot_replay_models import (
    SnapshotReplaySourceDiagnosticContractSignatureDrift,
    SnapshotReplaySourceDiagnosticNamingContractDrift,
    SnapshotReplaySourceDiagnosticMetadataCompletenessDrift,
    SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift,
    SnapshotReplaySourceDiagnosticGroupCoverageDrift,
    SnapshotReplaySourceDiagnosticSurfaceCountDrift,
    SnapshotReplaySourceDiagnosticsContractCoverageDrift,
)
from app.services.snapshot_replay_source_common import (
        Mapping,
    SnapshotFallbackUsageRecurrence,
    SnapshotMappedAtAlignmentConsistency,
    SnapshotNoExecutionGuardrailConsistency,
    SnapshotNoExecutionGuardrailEntry,
    SnapshotPaperSafeSourceFlagConsistency,
    SnapshotProviderAdapterContractConsistency,
    SnapshotRawPayloadReferenceCompleteness,
    SnapshotSourceDecisionUsageConsistency,
    SnapshotSourceDiagnosticsAverageCoverageDrift,
    SnapshotSourceDiagnosticsCriticalFeatureDrift,
    SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
    SnapshotSourceDiagnosticsHighSeverityDrift,
    SnapshotSourceDiagnosticsInfoFeatureDrift,
    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
    SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
    SnapshotSourceDiagnosticsReadyFeatureDrift,
    SnapshotSourceDiagnosticsSeverityLabelDrift,
    SnapshotSourceDiagnosticsSeverityRankDensityDrift,
    SnapshotSourceDiagnosticsSeverityRankDrift,
    SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
    SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation,
    SnapshotSourceDiagnosticsStaleAssetCountReconciliation,
    SnapshotSourceDiagnosticsStaleFeatureDrift,
    SnapshotSourceDiagnosticsWarningFeatureDrift,
    SnapshotSourceDiagnosticsZeroRankDrift,
    SnapshotSourceFreshnessDecayTimeline,
    SnapshotSourceFreshnessPolicyDrift,
    SnapshotSourceFreshnessStatusThresholdReconciliation,
    SnapshotSourceFreshnessSummaryReconciliation,
    SnapshotSourceObservationAvailabilityLagDrift,
    SnapshotSourceObservationCadenceDrift,
    SnapshotSourceObservationConfidenceDrift,
    SnapshotSourceObservationFreshnessSecondsDrift,
    SnapshotSourceObservationNormalizationModeDrift,
    SnapshotSourceObservationRecordSummaryReconciliation,
    SnapshotSourceObservationSummaryDrift,
    SnapshotSourceObservationTimestampIntegrityDrift,
    SnapshotSourceRecordCompleteness,
    SnapshotSourceRegistryBindingDrift,
    SnapshotSourceVerificationDrift,
    SnapshotStaleSourceListThresholdReconciliation,
    SnapshotStore,
    SnapshotVerifiedSourceCoverageReconciliation,
    UTC,
    datetime,
)
from app.services.snapshot_replay_source_quality import SnapshotReplaySourceQualityMixin
from app.services.snapshot_replay_source_timing import SnapshotReplaySourceTimingMixin
from app.services.snapshot_replay_source_registry import SnapshotReplaySourceRegistryMixin
from app.services.snapshot_replay_source_recurrence import SnapshotReplaySourceRecurrenceMixin


class SnapshotReplaySourceDiagnostics(
    SnapshotReplaySourceQualityMixin,
    SnapshotReplaySourceTimingMixin,
    SnapshotReplaySourceRegistryMixin,
    SnapshotReplaySourceRecurrenceMixin,
    SnapshotReplayCore,
):
    def build_source_freshness_decay_timeline(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceFreshnessDecayTimeline:
        backtest_result, ordered_replay_results = self._run_ordered_backtest(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_freshness_decay_timeline(
            ordered_replay_results,
            failure_count=backtest_result.failed_replays,
            failures=backtest_result.failures,
            total_snapshots_requested=backtest_result.total_snapshots_requested,
        )
    def build_fallback_usage_recurrence(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotFallbackUsageRecurrence:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_fallback_usage_recurrence(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_raw_payload_reference_completeness(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotRawPayloadReferenceCompleteness:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_raw_payload_reference_completeness(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_cadence_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationCadenceDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_cadence_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_record_completeness(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceRecordCompleteness:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_record_completeness(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_registry_binding_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceRegistryBindingDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_registry_binding_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_decision_usage_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDecisionUsageConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_decision_usage_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_verification_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceVerificationDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_verification_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_paper_safe_source_flag_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotPaperSafeSourceFlagConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_paper_safe_source_flag_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_summary_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationSummaryDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_summary_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_provider_adapter_contract_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotProviderAdapterContractConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_provider_adapter_contract_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_contract_coverage_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplaySourceDiagnosticsContractCoverageDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_contract_coverage_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostic_group_coverage_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplaySourceDiagnosticGroupCoverageDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostic_group_coverage_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostic_surface_count_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplaySourceDiagnosticSurfaceCountDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostic_surface_count_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostic_metadata_completeness_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplaySourceDiagnosticMetadataCompletenessDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostic_metadata_completeness_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostic_naming_contract_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplaySourceDiagnosticNamingContractDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostic_naming_contract_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostic_contract_signature_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplaySourceDiagnosticContractSignatureDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostic_contract_signature_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_rolling_source_diagnostic_bundle_coverage_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_rolling_source_diagnostic_bundle_coverage_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_timestamp_integrity_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationTimestampIntegrityDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_timestamp_integrity_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_record_summary_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationRecordSummaryReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_record_summary_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_normalization_mode_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationNormalizationModeDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_normalization_mode_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_mapped_at_alignment_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotMappedAtAlignmentConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_mapped_at_alignment_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_confidence_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationConfidenceDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_confidence_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_verified_source_coverage_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotVerifiedSourceCoverageReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_verified_source_coverage_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_availability_lag_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationAvailabilityLagDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_availability_lag_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_freshness_summary_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceFreshnessSummaryReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_freshness_summary_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_observation_freshness_seconds_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationFreshnessSecondsDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_freshness_seconds_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_freshness_status_threshold_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceFreshnessStatusThresholdReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_freshness_status_threshold_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_freshness_policy_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceFreshnessPolicyDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_freshness_policy_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_stale_source_list_threshold_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotStaleSourceListThresholdReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_stale_source_list_threshold_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_freshness_evaluation_mode_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_freshness_evaluation_mode_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_stale_asset_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsStaleAssetCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_stale_asset_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_average_coverage_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsAverageCoverageDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_average_coverage_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_minimum_coverage_floor_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_minimum_coverage_floor_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_ready_feature_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsReadyFeatureDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_ready_feature_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_stale_feature_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsStaleFeatureDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_stale_feature_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_critical_feature_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsCriticalFeatureDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_critical_feature_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_high_severity_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsHighSeverityDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_high_severity_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_warning_feature_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsWarningFeatureDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_warning_feature_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_info_feature_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsInfoFeatureDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_info_feature_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_zero_rank_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsZeroRankDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_zero_rank_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_label_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityLabelDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_label_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_rank_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_rank_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_rank_density_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankDensityDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_rank_density_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_rank_spread_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankSpreadDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_rank_spread_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_feature_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_feature_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_critical_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_critical_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_warning_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_warning_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_info_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_info_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_missing_source_feature_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_missing_source_feature_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_source_diagnostics_missing_asset_count_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDiagnosticsMissingAssetCountReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_diagnostics_missing_asset_count_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def build_no_execution_guardrail_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotNoExecutionGuardrailConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_no_execution_guardrail_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )
    def _build_no_execution_guardrail_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotNoExecutionGuardrailConsistency:
        diagnostics: list[str] = []
        entries: list[SnapshotNoExecutionGuardrailEntry] = []
        violations: list[SnapshotNoExecutionGuardrailEntry] = []

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)
            report_type = str(snapshot_payload.get("report_type", "unknown"))
            mode = str(snapshot_payload.get("mode", "unknown"))
            execution_mode = str(snapshot_payload.get("execution_mode", "unknown"))
            decision_permission = str(snapshot_payload.get("decision_permission", "unknown"))

            violation_codes: list[str] = []
            if decision_permission != "NO_EXECUTION":
                violation_codes.append("DECISION_PERMISSION_BREACH")
            if execution_mode not in SnapshotStore.ALLOWED_EXECUTION_MODES:
                violation_codes.append("UNSAFE_EXECUTION_MODE")
            if mode not in SnapshotStore.ALLOWED_MODES:
                violation_codes.append("UNSAFE_MODE")

            if violation_codes:
                diagnostic = (
                    "Snapshot violated the paper-safe NO_EXECUTION guardrail: "
                    + ", ".join(violation_codes)
                    + "."
                )
            else:
                diagnostic = "Snapshot preserved the NO_EXECUTION guardrail."

            entry = SnapshotNoExecutionGuardrailEntry(
                snapshot_id=snapshot_id,
                created_at=created_at,
                report_type=report_type,
                mode=mode,
                execution_mode=execution_mode,
                decision_permission=decision_permission,
                consistent=not violation_codes,
                violation_codes=tuple(violation_codes),
                diagnostic=diagnostic,
            )
            entries.append(entry)
            if violation_codes:
                violations.append(entry)

        if not entries:
            diagnostics.append("No saved snapshots were available for NO_EXECUTION guardrail consistency analysis.")
        elif violations:
            diagnostics.append(
                f"Detected {len(violations)} NO_EXECUTION guardrail violation(s) across {len(entries)} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                f"All {len(entries)} saved snapshot(s) preserved the NO_EXECUTION guardrail."
            )

        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during NO_EXECUTION guardrail analysis."
            )

        if not entries:
            consistency_status = "insufficient_data"
        elif violations:
            consistency_status = "violations_detected"
        else:
            consistency_status = "consistent"

        return SnapshotNoExecutionGuardrailConsistency(
            consistency_status=consistency_status,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=len(entries),
            consistent_snapshots=sum(1 for entry in entries if entry.consistent),
            violation_count=len(violations),
            entries=tuple(entries),
            violations=tuple(violations),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = ["SnapshotReplaySourceDiagnostics"]
