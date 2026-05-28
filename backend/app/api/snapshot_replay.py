from __future__ import annotations

from fastapi import APIRouter

from app.api.snapshot_replay_routes_core import router as core_router
from app.api.snapshot_replay_routes_source_quality import router as source_quality_router
from app.api.snapshot_replay_routes_source_registry import router as source_registry_router
from app.api.snapshot_replay_routes_source_timing import router as source_timing_router
from app.services.snapshot_replay_service import SnapshotReplayService
from app.storage import build_local_snapshot_store

router = APIRouter(prefix="/snapshots", tags=["snapshot-replay"])

router.include_router(core_router)
router.include_router(source_quality_router)
router.include_router(source_registry_router)
router.include_router(source_timing_router)


def build_snapshot_replay_store():
    return build_local_snapshot_store()


def build_snapshot_replay_service() -> SnapshotReplayService:
    return SnapshotReplayService(snapshot_store=build_snapshot_replay_store())


__all__ = ["router", "build_snapshot_replay_store", "build_snapshot_replay_service"]
