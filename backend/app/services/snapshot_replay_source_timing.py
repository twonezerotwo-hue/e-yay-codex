from __future__ import annotations

from app.services.snapshot_replay_source_timing_freshness import (
    SnapshotReplaySourceTimingFreshnessMixin,
)
from app.services.snapshot_replay_source_timing_observation import (
    SnapshotReplaySourceTimingObservationMixin,
)


class SnapshotReplaySourceTimingMixin(
    SnapshotReplaySourceTimingObservationMixin,
    SnapshotReplaySourceTimingFreshnessMixin,
):
    pass


__all__ = ["SnapshotReplaySourceTimingMixin"]
