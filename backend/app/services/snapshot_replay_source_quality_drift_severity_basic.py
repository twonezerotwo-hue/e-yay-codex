from __future__ import annotations

from app.services.snapshot_replay_source_quality_drift_severity_feature import (
    SnapshotReplaySourceQualityDriftSeverityFeatureMixin,
)
from app.services.snapshot_replay_source_quality_drift_severity_rank_basic import (
    SnapshotReplaySourceQualityDriftSeverityRankBasicMixin,
)


class SnapshotReplaySourceQualityDriftSeverityBasicMixin(
    SnapshotReplaySourceQualityDriftSeverityFeatureMixin,
    SnapshotReplaySourceQualityDriftSeverityRankBasicMixin,
):
    pass


__all__ = ["SnapshotReplaySourceQualityDriftSeverityBasicMixin"]
