from __future__ import annotations

from app.services.snapshot_replay_source_quality_drift_severity import (
    SnapshotReplaySourceQualityDriftSeverityMixin,
)
from app.services.snapshot_replay_source_quality_drift_summary import (
    SnapshotReplaySourceQualityDriftSummaryMixin,
)


class SnapshotReplaySourceQualityDriftMixin(
    SnapshotReplaySourceQualityDriftSummaryMixin,
    SnapshotReplaySourceQualityDriftSeverityMixin,
):
    pass


__all__ = ["SnapshotReplaySourceQualityDriftMixin"]
