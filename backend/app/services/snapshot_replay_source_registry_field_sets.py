from __future__ import annotations

import dataclasses

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models_source_registry import (
    SnapshotFallbackUsageRecurrence,
    SnapshotPaperSafeSourceFlagConsistency,
    SnapshotProviderAdapterContractConsistency,
    SnapshotSourceRegistryBindingDrift,
    SnapshotSourceVerificationDrift,
    SnapshotReplayFullSurfaceResponseFieldSetConsistency,
    SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry,
    SnapshotReplaySourceDiagnosticContractFieldSetDrift,
    SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry,
)
from app.services.snapshot_replay_models_source_quality import (
    SnapshotRawPayloadReferenceCompleteness,
    SnapshotSourceDecisionUsageConsistency,
    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
    SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
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
    SnapshotSourceObservationRecordSummaryReconciliation,
    SnapshotSourceRecordCompleteness,
    SnapshotVerifiedSourceCoverageReconciliation,
)
from app.services.snapshot_replay_models_source_timing import (
    SnapshotMappedAtAlignmentConsistency,
    SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
    SnapshotSourceFreshnessDecayTimeline,
    SnapshotSourceFreshnessPolicyDrift,
    SnapshotSourceFreshnessStatusThresholdReconciliation,
    SnapshotSourceFreshnessSummaryReconciliation,
    SnapshotSourceObservationAvailabilityLagDrift,
    SnapshotSourceObservationCadenceDrift,
    SnapshotSourceObservationFreshnessSecondsDrift,
    SnapshotSourceObservationNormalizationModeDrift,
    SnapshotSourceObservationTimestampIntegrityDrift,
    SnapshotStaleSourceListThresholdReconciliation,
)
from app.services.snapshot_replay_models_source_drift import (
    SnapshotSourceDiagnosticsAverageCoverageDrift,
    SnapshotSourceDiagnosticsCriticalFeatureDrift,
    SnapshotSourceDiagnosticsHighSeverityDrift,
    SnapshotSourceDiagnosticsInfoFeatureDrift,
    SnapshotSourceDiagnosticsReadyFeatureDrift,
    SnapshotSourceDiagnosticsSeverityLabelDrift,
    SnapshotSourceDiagnosticsSeverityRankDensityDrift,
    SnapshotSourceDiagnosticsSeverityRankDrift,
    SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
    SnapshotSourceDiagnosticsStaleFeatureDrift,
    SnapshotSourceDiagnosticsWarningFeatureDrift,
    SnapshotSourceDiagnosticsZeroRankDrift,
    SnapshotSourceObservationConfidenceDrift,
    SnapshotSourceObservationSummaryDrift,
)

_SLUG_TO_MODEL_CLASS: dict[str, type] = {
    "fallback-usage-recurrence": SnapshotFallbackUsageRecurrence,
    "raw-payload-reference-completeness": SnapshotRawPayloadReferenceCompleteness,
    "source-record-completeness": SnapshotSourceRecordCompleteness,
    "source-registry-binding-drift": SnapshotSourceRegistryBindingDrift,
    "source-decision-usage-consistency": SnapshotSourceDecisionUsageConsistency,
    "source-verification-drift": SnapshotSourceVerificationDrift,
    "paper-safe-source-flag-consistency": SnapshotPaperSafeSourceFlagConsistency,
    "source-observation-summary-drift": SnapshotSourceObservationSummaryDrift,
    "provider-adapter-contract-consistency": SnapshotProviderAdapterContractConsistency,
    "source-freshness-decay-timeline": SnapshotSourceFreshnessDecayTimeline,
    "source-observation-cadence-drift": SnapshotSourceObservationCadenceDrift,
    "source-observation-timestamp-integrity-drift": SnapshotSourceObservationTimestampIntegrityDrift,
    "source-observation-record-summary-reconciliation": SnapshotSourceObservationRecordSummaryReconciliation,
    "source-observation-normalization-mode-drift": SnapshotSourceObservationNormalizationModeDrift,
    "mapped-at-alignment-consistency": SnapshotMappedAtAlignmentConsistency,
    "source-observation-confidence-drift": SnapshotSourceObservationConfidenceDrift,
    "verified-source-coverage-reconciliation": SnapshotVerifiedSourceCoverageReconciliation,
    "source-observation-availability-lag-drift": SnapshotSourceObservationAvailabilityLagDrift,
    "source-freshness-summary-reconciliation": SnapshotSourceFreshnessSummaryReconciliation,
    "source-observation-freshness-seconds-drift": SnapshotSourceObservationFreshnessSecondsDrift,
    "source-freshness-status-threshold-reconciliation": SnapshotSourceFreshnessStatusThresholdReconciliation,
    "source-freshness-policy-drift": SnapshotSourceFreshnessPolicyDrift,
    "stale-source-list-threshold-reconciliation": SnapshotStaleSourceListThresholdReconciliation,
    "source-diagnostics-freshness-evaluation-mode-drift": SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
    "source-diagnostics-stale-asset-count-reconciliation": SnapshotSourceDiagnosticsStaleAssetCountReconciliation,
    "source-diagnostics-average-coverage-drift": SnapshotSourceDiagnosticsAverageCoverageDrift,
    "source-diagnostics-minimum-coverage-floor-reconciliation": SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
    "source-diagnostics-ready-feature-drift": SnapshotSourceDiagnosticsReadyFeatureDrift,
    "source-diagnostics-stale-feature-drift": SnapshotSourceDiagnosticsStaleFeatureDrift,
    "source-diagnostics-critical-feature-drift": SnapshotSourceDiagnosticsCriticalFeatureDrift,
    "source-diagnostics-high-severity-drift": SnapshotSourceDiagnosticsHighSeverityDrift,
    "source-diagnostics-warning-feature-drift": SnapshotSourceDiagnosticsWarningFeatureDrift,
    "source-diagnostics-info-feature-drift": SnapshotSourceDiagnosticsInfoFeatureDrift,
    "source-diagnostics-zero-rank-drift": SnapshotSourceDiagnosticsZeroRankDrift,
    "source-diagnostics-severity-label-drift": SnapshotSourceDiagnosticsSeverityLabelDrift,
    "source-diagnostics-severity-rank-drift": SnapshotSourceDiagnosticsSeverityRankDrift,
    "source-diagnostics-severity-rank-density-drift": SnapshotSourceDiagnosticsSeverityRankDensityDrift,
    "source-diagnostics-severity-rank-spread-drift": SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
    "source-diagnostics-severity-ranking-feature-count-reconciliation": SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation,
    "source-diagnostics-severity-ranking-warning-count-reconciliation": SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation,
    "source-diagnostics-severity-ranking-info-count-reconciliation": SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation,
    "source-diagnostics-severity-ranking-non-actionable-count-reconciliation": SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation,
    "source-diagnostics-severity-ranking-rank-label-consistency-reconciliation": SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation,
    "source-diagnostics-severity-ranking-rank-order-continuity-reconciliation": SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation,
    "source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation": SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation,
    "source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation": SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation,
    "source-diagnostics-severity-ranking-critical-count-reconciliation": SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation,
    "source-diagnostics-missing-source-feature-count-reconciliation": SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
    "source-diagnostics-missing-asset-count-reconciliation": SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
}

_STANDARD_FIELD_SET: frozenset[str] = frozenset(
    source_diagnostic_contracts.SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET
)


def _inspect_model_class(
    slug: str,
    model_cls: type | None,
) -> tuple[bool, tuple[str, ...], tuple[str, ...], tuple[str, ...], int]:
    if model_cls is None:
        return False, (), tuple(sorted(_STANDARD_FIELD_SET)), (), 0
    all_field_names = frozenset(f.name for f in dataclasses.fields(model_cls))
    present = tuple(sorted(_STANDARD_FIELD_SET & all_field_names))
    missing = tuple(sorted(_STANDARD_FIELD_SET - all_field_names))
    extra = tuple(sorted(all_field_names - _STANDARD_FIELD_SET))
    has_all = len(missing) == 0
    return has_all, present, missing, extra, len(all_field_names)


class SnapshotReplaySourceRegistryFieldSetsMixin:
    def build_source_diagnostic_contract_field_set_drift(
        self,
        *,
        snapshot_ids: list[str] | None = None,  # noqa: ARG002 — static inspection, no snapshot data needed
    ) -> SnapshotReplaySourceDiagnosticContractFieldSetDrift:
        slugs = source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
        entries: list[SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry] = []
        fully_consistent = 0
        partially_consistent = 0

        for slug in slugs:
            key = source_diagnostic_contracts.snapshot_replay_source_diagnostic_key(slug)
            group = source_diagnostic_contracts.snapshot_replay_source_diagnostic_group(slug)
            model_cls = _SLUG_TO_MODEL_CLASS.get(slug)
            has_all, present, missing, extra, total_fields = _inspect_model_class(slug, model_cls)
            class_name = model_cls.__name__ if model_cls is not None else "UNKNOWN"

            if model_cls is None:
                drift_cls = "degraded"
                diag = f"No model class registered for slug {slug!r}."
                partially_consistent += 1
            elif has_all:
                drift_cls = "stable"
                diag = f"All standard fields present in {class_name}."
                fully_consistent += 1
            else:
                drift_cls = "drifting"
                diag = f"Missing {len(missing)} standard field(s) in {class_name}: {missing}."
                partially_consistent += 1

            entries.append(
                SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry(
                    slug=slug,
                    diagnostic_key=key,
                    diagnostic_group=group,
                    model_class_name=class_name,
                    has_all_standard_fields=has_all,
                    present_standard_fields=present,
                    missing_standard_fields=missing,
                    extra_fields=extra,
                    total_fields=total_fields,
                    drift_classification=drift_cls,
                    diagnostic=diag,
                )
            )

        total = len(slugs)
        consistency_pct = round(fully_consistent / total * 100.0, 2) if total > 0 else 0.0
        missing_field_count = sum(len(e.missing_standard_fields) for e in entries)

        if consistency_pct == 100.0:
            overall_drift = "stable"
        elif consistency_pct >= 80.0:
            overall_drift = "drifting"
        else:
            overall_drift = "degraded"

        severity_score = partially_consistent * 2

        if partially_consistent == 0:
            diag_msg = "All source diagnostic models have the full standard field set."
        else:
            diag_msg = (
                f"{partially_consistent} of {total} source diagnostic models "
                "are missing one or more standard fields."
            )

        return SnapshotReplaySourceDiagnosticContractFieldSetDrift(
            drift_classification=overall_drift,
            consistency_percentage=consistency_pct,
            severity_score=severity_score,
            total_diagnostics_registered=total,
            fully_consistent_count=fully_consistent,
            partially_consistent_count=partially_consistent,
            missing_standard_field_count=missing_field_count,
            standard_field_set=tuple(sorted(_STANDARD_FIELD_SET)),
            entries=tuple(entries),
            diagnostics=(diag_msg,),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def build_full_surface_response_field_set_consistency(
        self,
        *,
        snapshot_ids: list[str] | None = None,  # noqa: ARG002 — static inspection, no snapshot data needed
    ) -> SnapshotReplayFullSurfaceResponseFieldSetConsistency:
        slugs = source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
        entries: list[SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry] = []
        fully_consistent = 0
        partially_consistent = 0
        degraded = 0

        for slug in slugs:
            key = source_diagnostic_contracts.snapshot_replay_source_diagnostic_key(slug)
            group = source_diagnostic_contracts.snapshot_replay_source_diagnostic_group(slug)
            model_cls = _SLUG_TO_MODEL_CLASS.get(slug)
            has_all, present, missing, _extra, total_fields = _inspect_model_class(slug, model_cls)
            class_name = model_cls.__name__ if model_cls is not None else "UNKNOWN"

            if model_cls is None:
                consistency_cls = "degraded"
                diag = f"No model class registered for slug {slug!r}."
                degraded += 1
            elif has_all:
                consistency_cls = "consistent"
                diag = f"{class_name} has all standard response fields."
                fully_consistent += 1
            elif len(missing) <= 2:
                consistency_cls = "partial"
                diag = f"{class_name} is missing {len(missing)} standard field(s): {missing}."
                partially_consistent += 1
            else:
                consistency_cls = "degraded"
                diag = f"{class_name} is missing {len(missing)} standard field(s): {missing}."
                degraded += 1

            entries.append(
                SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry(
                    slug=slug,
                    diagnostic_key=key,
                    diagnostic_group=group,
                    model_class_name=class_name,
                    has_all_standard_fields=has_all,
                    present_standard_fields=present,
                    missing_standard_fields=missing,
                    total_fields=total_fields,
                    consistency_classification=consistency_cls,
                    diagnostic=diag,
                )
            )

        total = len(slugs)
        consistency_pct = round(fully_consistent / total * 100.0, 2) if total > 0 else 0.0

        if consistency_pct == 100.0:
            overall = "consistent"
        elif consistency_pct >= 80.0:
            overall = "partial"
        else:
            overall = "degraded"

        if fully_consistent == total:
            diag_msg = "All source diagnostic response models have the full standard field set."
        else:
            diag_msg = (
                f"{fully_consistent} of {total} source diagnostic models "
                "are fully field-set consistent."
            )

        return SnapshotReplayFullSurfaceResponseFieldSetConsistency(
            consistency_classification=overall,
            consistency_percentage=consistency_pct,
            total_diagnostics_registered=total,
            fully_consistent_count=fully_consistent,
            partially_consistent_count=partially_consistent,
            degraded_count=degraded,
            standard_field_set=tuple(sorted(_STANDARD_FIELD_SET)),
            entries=tuple(entries),
            diagnostics=(diag_msg,),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryFieldSetsMixin"]
