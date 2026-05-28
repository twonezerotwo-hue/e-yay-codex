from __future__ import annotations

from app.services.snapshot_replay_source_registry_contract_coverage import (
    SnapshotReplaySourceRegistryContractCoverageMixin,
)
from app.services.snapshot_replay_source_registry_group_coverage import (
    SnapshotReplaySourceRegistryGroupCoverageMixin,
)
from app.services.snapshot_replay_source_registry_naming import (
    SnapshotReplaySourceRegistryNamingMixin,
)
from app.services.snapshot_replay_source_registry_metadata import (
    SnapshotReplaySourceRegistryMetadataMixin,
)
from app.services.snapshot_replay_source_registry_signatures import (
    SnapshotReplaySourceRegistrySignaturesMixin,
)
from app.services.snapshot_replay_source_registry_surface_counts import (
    SnapshotReplaySourceRegistrySurfaceCountsMixin,
)
from app.services.snapshot_replay_source_registry_field_sets import (
    SnapshotReplaySourceRegistryFieldSetsMixin,
)


class SnapshotReplaySourceRegistryContractsMixin(
    SnapshotReplaySourceRegistryContractCoverageMixin,
    SnapshotReplaySourceRegistryGroupCoverageMixin,
    SnapshotReplaySourceRegistryNamingMixin,
    SnapshotReplaySourceRegistrySignaturesMixin,
    SnapshotReplaySourceRegistrySurfaceCountsMixin,
    SnapshotReplaySourceRegistryMetadataMixin,
    SnapshotReplaySourceRegistryFieldSetsMixin,
):
    pass


__all__ = ["SnapshotReplaySourceRegistryContractsMixin"]
