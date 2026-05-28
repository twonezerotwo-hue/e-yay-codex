from __future__ import annotations

from app.services.snapshot_replay_source_registry_contracts import (
    SnapshotReplaySourceRegistryContractsMixin,
)
from app.services.snapshot_replay_source_registry_rolling import (
    SnapshotReplaySourceRegistryRollingMixin,
)
from app.services.snapshot_replay_source_registry_verification import (
    SnapshotReplaySourceRegistryVerificationMixin,
)


class SnapshotReplaySourceRegistryMixin(
    SnapshotReplaySourceRegistryVerificationMixin,
    SnapshotReplaySourceRegistryContractsMixin,
    SnapshotReplaySourceRegistryRollingMixin,
):
    pass


__all__ = ["SnapshotReplaySourceRegistryMixin"]
