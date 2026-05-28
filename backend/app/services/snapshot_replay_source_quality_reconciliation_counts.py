from __future__ import annotations

from app.services.snapshot_replay_source_quality_reconciliation_counts_basic import (
    SnapshotReplaySourceQualityReconciliationCountsBasicMixin,
)
from app.services.snapshot_replay_source_quality_reconciliation_counts_severity import (
    SnapshotReplaySourceQualityReconciliationCountsSeverityMixin,
)


class SnapshotReplaySourceQualityReconciliationCountsMixin(
    SnapshotReplaySourceQualityReconciliationCountsBasicMixin,
    SnapshotReplaySourceQualityReconciliationCountsSeverityMixin,
):
    pass


__all__ = ["SnapshotReplaySourceQualityReconciliationCountsMixin"]
