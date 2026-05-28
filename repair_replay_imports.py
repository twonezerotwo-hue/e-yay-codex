from pathlib import Path
import re

root = Path(r"C:\Users\twone\Desktop\E_YAY CODEX")

# 1) Fix snapshot_replay.py E402 by rewriting clean aggregator router
snapshot_api = root / "backend/app/api/snapshot_replay.py"
snapshot_api.write_text(
'''from __future__ import annotations

from fastapi import APIRouter

from app.api.snapshot_replay_routes_core import router as core_router
from app.api.snapshot_replay_routes_source_quality import router as source_quality_router
from app.api.snapshot_replay_routes_source_registry import router as source_registry_router
from app.api.snapshot_replay_routes_source_timing import router as source_timing_router

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshot-replay"])

router.include_router(core_router)
router.include_router(source_quality_router)
router.include_router(source_registry_router)
router.include_router(source_timing_router)

__all__ = ["router"]
''',
encoding="utf-8",
)
print("patched snapshot_replay.py")

# 2) Fix wrong Any import in snapshot_replay_source_diagnostics.py
diag = root / "backend/app/services/snapshot_replay_source_diagnostics.py"
text = diag.read_text(encoding="utf-8")

if "from typing import Any" not in text:
    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__") or lines[insert_at].strip() == ""
    ):
        insert_at += 1
    lines.insert(insert_at, "from typing import Any")
    text = "\n".join(lines) + "\n"

# remove Any from import block coming from snapshot_replay_source_common
text = re.sub(r"(\n\s*)Any,\n", r"\1", text)
diag.write_text(text, encoding="utf-8")
print("patched snapshot_replay_source_diagnostics.py Any import")

# 3) Fix snapshot_replay_models_core.py annotation visibility
core = root / "backend/app/services/snapshot_replay_models_core.py"
text = core.read_text(encoding="utf-8")

# remove previous TYPE_CHECKING block if inserted
text = re.sub(
    r"\nfrom typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n(?:    .+\n|        .+\n|\s*\)\n)*",
    "\n",
    text,
    flags=re.MULTILINE,
)

needed_imports = '''from app.services.snapshot_replay_models_source_quality import SnapshotRawPayloadReferenceCompleteness
from app.services.snapshot_replay_models_source_quality import SnapshotSourceRecordCompleteness
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDecisionUsageConsistency
from app.services.snapshot_replay_models_source_quality import SnapshotSourceObservationRecordSummaryReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotVerifiedSourceCoverageReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsStaleAssetCountReconciliation
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsAverageCoverageDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsReadyFeatureDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsStaleFeatureDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsCriticalFeatureDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsHighSeverityDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsWarningFeatureDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsInfoFeatureDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsZeroRankDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityLabelDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankDensityDrift
from app.services.snapshot_replay_models_source_quality import SnapshotSourceDiagnosticsSeverityRankSpreadDrift
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
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessDecayTimeline
from app.services.snapshot_replay_models_source_timing import SnapshotFallbackUsageRecurrence
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationCadenceDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationFreshnessSecondsDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessStatusThresholdReconciliation
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessSummaryReconciliation
from app.services.snapshot_replay_models_source_timing import SnapshotSourceFreshnessPolicyDrift
from app.services.snapshot_replay_models_source_timing import SnapshotStaleSourceListThresholdReconciliation
from app.services.snapshot_replay_models_source_timing import SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationTimestampIntegrityDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationNormalizationModeDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationConfidenceDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationAvailabilityLagDrift
from app.services.snapshot_replay_models_source_timing import SnapshotSourceObservationSummaryDrift
from app.services.snapshot_replay_models_source_timing import SnapshotMappedAtAlignmentConsistency
from app.services.snapshot_replay_models_source_registry import SnapshotSourceGapRecurrenceLeaderboard
from app.services.snapshot_replay_models_source_registry import SnapshotSourceRegistryBindingDrift
from app.services.snapshot_replay_models_source_registry import SnapshotSourceVerificationDrift
from app.services.snapshot_replay_models_source_registry import SnapshotPaperSafeSourceFlagConsistency
from app.services.snapshot_replay_models_source_registry import SnapshotProviderAdapterContractConsistency
from app.services.snapshot_replay_models_source_registry import SnapshotNoExecutionGuardrailConsistency
'''

if "SnapshotSourceGapRecurrenceLeaderboard" not in text.split("@dataclass", 1)[0]:
    lines = text.splitlines()
    insert_at = 0
    while insert_at < len(lines) and (
        lines[insert_at].startswith("from __future__") or lines[insert_at].strip() == ""
    ):
        insert_at += 1
    lines.insert(insert_at, needed_imports.rstrip())
    text = "\n".join(lines) + "\n"

core.write_text(text, encoding="utf-8")
print("patched snapshot_replay_models_core.py imports")

# 4) Fix wrong __all__ in contract coverage module
coverage = root / "backend/app/services/snapshot_replay_source_registry_contract_coverage.py"
text = coverage.read_text(encoding="utf-8")
text = text.replace(
    '__all__ = ["SnapshotReplaySourceRegistryContractsMixin"]',
    '__all__ = ["SnapshotReplaySourceRegistryContractCoverageMixin"]',
)
coverage.write_text(text, encoding="utf-8")
print("patched contract coverage __all__")

# 5) Fix unused local variable severity_rank
rank_basic = root / "backend/app/services/snapshot_replay_source_quality_drift_severity_rank_basic.py"
text = rank_basic.read_text(encoding="utf-8")
text = text.replace("severity_rank = int(raw_severity_rank)", "int(raw_severity_rank)")
rank_basic.write_text(text, encoding="utf-8")
print("patched unused severity_rank")

# 6) Add __all__ to services/__init__.py so re-export imports are intentional
init_file = root / "backend/app/services/__init__.py"
text = init_file.read_text(encoding="utf-8")
if "__all__ =" not in text:
    text = text.rstrip() + "\n\n__all__ = [name for name in globals() if not name.startswith('_')]\n"
    init_file.write_text(text, encoding="utf-8")
    print("added __all__ to services/__init__.py")
else:
    print("services/__init__.py already has __all__")

print("patch phase done")
