from pathlib import Path

path = Path(r"C:\Users\twone\Desktop\E_YAY CODEX\backend\app\services\snapshot_replay_models_core.py")
text = path.read_text(encoding="utf-8")

needed_block = '''from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.snapshot_replay_models_source_quality import (
        SnapshotRawPayloadReferenceCompleteness,
        SnapshotSourceRecordCompleteness,
        SnapshotSourceDecisionUsageConsistency,
        SnapshotSourceObservationRecordSummaryReconciliation,
        SnapshotVerifiedSourceCoverageReconciliation,
        SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
        SnapshotSourceDiagnosticsStaleAssetCountReconciliation,
        SnapshotSourceDiagnosticsAverageCoverageDrift,
        SnapshotSourceDiagnosticsReadyFeatureDrift,
        SnapshotSourceDiagnosticsStaleFeatureDrift,
        SnapshotSourceDiagnosticsCriticalFeatureDrift,
        SnapshotSourceDiagnosticsHighSeverityDrift,
        SnapshotSourceDiagnosticsWarningFeatureDrift,
        SnapshotSourceDiagnosticsInfoFeatureDrift,
        SnapshotSourceDiagnosticsZeroRankDrift,
        SnapshotSourceDiagnosticsSeverityLabelDrift,
        SnapshotSourceDiagnosticsSeverityRankDrift,
        SnapshotSourceDiagnosticsSeverityRankDensityDrift,
        SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
        SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation,
        SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation,
        SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
        SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
    )
    from app.services.snapshot_replay_models_source_timing import (
        SnapshotSourceFreshnessDecayTimeline,
        SnapshotFallbackUsageRecurrence,
        SnapshotSourceObservationCadenceDrift,
        SnapshotSourceObservationFreshnessSecondsDrift,
        SnapshotSourceFreshnessStatusThresholdReconciliation,
        SnapshotSourceFreshnessSummaryReconciliation,
        SnapshotSourceFreshnessPolicyDrift,
        SnapshotStaleSourceListThresholdReconciliation,
        SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
        SnapshotSourceObservationTimestampIntegrityDrift,
        SnapshotSourceObservationNormalizationModeDrift,
        SnapshotSourceObservationConfidenceDrift,
        SnapshotSourceObservationAvailabilityLagDrift,
    )
    from app.services.snapshot_replay_models_source_registry import (
        SnapshotSourceGapRecurrenceLeaderboard,
        SnapshotSourceRegistryBindingDrift,
        SnapshotSourceVerificationDrift,
        SnapshotPaperSafeSourceFlagConsistency,
        SnapshotProviderAdapterContractConsistency,
        SnapshotNoExecutionGuardrailConsistency,
        SnapshotReplaySourceDiagnosticsContractCoverageDrift,
        SnapshotReplayDiagnosticEndpointCoverageConsistency,
        SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift,
        SnapshotReplayDedicatedRollingDiagnosticConsistency,
        SnapshotReplaySourceDiagnosticGroupCoverageDrift,
        SnapshotReplayRouteSerializerGroupAlignmentConsistency,
        SnapshotReplaySourceDiagnosticSurfaceCountDrift,
        SnapshotReplayContractSurfaceCountConsistency,
        SnapshotReplaySourceDiagnosticMetadataCompletenessDrift,
        SnapshotReplayContractMetadataNormalizationConsistency,
        SnapshotReplaySourceDiagnosticNamingContractDrift,
        SnapshotReplayBuilderSerializerRouteNamingConsistency,
        SnapshotReplaySourceDiagnosticContractSignatureDrift,
        SnapshotReplayFullSurfaceContractSignatureConsistency,
    )
'''

if "from typing import TYPE_CHECKING" not in text:
    lines = text.splitlines()
    insert_at = 0

    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__")
        or lines[insert_at].strip() == ""
    ):
        insert_at += 1

    lines.insert(insert_at, needed_block.rstrip())
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    print("patched snapshot_replay_models_core.py")
else:
    print("TYPE_CHECKING block already exists; skipped")

print("done")
