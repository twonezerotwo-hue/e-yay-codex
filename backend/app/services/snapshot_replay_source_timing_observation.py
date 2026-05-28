from __future__ import annotations

from app.services.snapshot_replay_source_timing_observation_cadence import (
    SnapshotReplaySourceTimingObservationCadenceMixin,
)
from app.services.snapshot_replay_source_timing_observation_integrity import (
    SnapshotReplaySourceTimingObservationIntegrityMixin,
)


class SnapshotReplaySourceTimingObservationMixin(
    SnapshotReplaySourceTimingObservationCadenceMixin,
    SnapshotReplaySourceTimingObservationIntegrityMixin,
):
    pass


__all__ = ["SnapshotReplaySourceTimingObservationMixin"]
