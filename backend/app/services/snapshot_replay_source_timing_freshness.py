from __future__ import annotations

from app.services.snapshot_replay_source_timing_freshness_decay import (
    SnapshotReplaySourceTimingFreshnessDecayMixin,
)
from app.services.snapshot_replay_source_timing_freshness_status import (
    SnapshotReplaySourceTimingFreshnessStatusMixin,
)


class SnapshotReplaySourceTimingFreshnessMixin(
    SnapshotReplaySourceTimingFreshnessStatusMixin,
    SnapshotReplaySourceTimingFreshnessDecayMixin,
):
    pass


__all__ = ["SnapshotReplaySourceTimingFreshnessMixin"]
