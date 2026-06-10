"""GET /api/v1/snapshots/{snapshot_id}/replay-status — replay durum kontratı.

`snapshot_id` replay'e bağlı DEĞİL; bu endpoint kontrat dürüstlüğü için
açıkça durumu raporlar. SnapshotReplayService.replay(id) → context API'si
implement edilince burası gerçek status'a geçer.

PAPER_SAFE / NO_EXECUTION — sadece okuma.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("/{snapshot_id}/replay-status")
def get_replay_status(snapshot_id: str) -> dict:
    """Snapshot replay'in mevcut implementasyon durumu.

    `status` her zaman "reserved_not_active" döner — gerçek replay(id)→context
    API'si henüz yok. Frontend buna göre "replay" izlenimi vermez.
    """
    return {
        "snapshot_id":   snapshot_id,
        "status":        "reserved_not_active",
        "reason":        "replay(id)->context API not implemented yet",
        "paper_safe":    True,
        "execution_side_effects": "NO_EXECUTION",
        "context_source_if_used": "current",
    }


__all__ = ["router"]
