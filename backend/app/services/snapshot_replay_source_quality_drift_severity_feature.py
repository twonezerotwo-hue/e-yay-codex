from __future__ import annotations

from app.services.snapshot_replay_source_quality_drift_severity_feature_alert import (
    SnapshotReplaySourceQualityDriftSeverityFeatureAlertMixin,
)
from app.services.snapshot_replay_source_quality_drift_severity_feature_info import (
    SnapshotReplaySourceQualityDriftSeverityFeatureInfoMixin,
)
from app.services.snapshot_replay_source_quality_drift_severity_feature_stale import (
    SnapshotReplaySourceQualityDriftSeverityFeatureStaleMixin,
)


class SnapshotReplaySourceQualityDriftSeverityFeatureMixin(
    SnapshotReplaySourceQualityDriftSeverityFeatureStaleMixin,
    SnapshotReplaySourceQualityDriftSeverityFeatureAlertMixin,
    SnapshotReplaySourceQualityDriftSeverityFeatureInfoMixin,
):
    pass


__all__ = ["SnapshotReplaySourceQualityDriftSeverityFeatureMixin"]
