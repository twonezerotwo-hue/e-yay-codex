from __future__ import annotations

from app.services.snapshot_replay_source_quality_drift_severity_basic import (
    SnapshotReplaySourceQualityDriftSeverityBasicMixin,
)
from app.services.snapshot_replay_source_quality_drift_severity_rank import (
    SnapshotReplaySourceQualityDriftSeverityRankMixin,
)


class SnapshotReplaySourceQualityDriftSeverityMixin(
    SnapshotReplaySourceQualityDriftSeverityBasicMixin,
    SnapshotReplaySourceQualityDriftSeverityRankMixin,
):
    pass


__all__ = ["SnapshotReplaySourceQualityDriftSeverityMixin"]
