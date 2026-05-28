from pathlib import Path

from app.storage import SnapshotStore


def build_snapshot_payload(*, created_at: str, source_suffix: str, report_type: str = "paper_ingestion") -> dict[str, object]:
    return {
        "created_at": created_at,
        "mode": "PAPER_SAFE",
        "source_registry_version": "1.0",
        "feature_registry_version": "1.0",
        "source_observations": {
            f"approved_btcusd_feed_{source_suffix}": created_at,
            f"approved_brent_feed_{source_suffix}": created_at,
        },
        "missing_sources": [],
        "stale_sources": [],
        "report_type": report_type,
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_ONLY",
    }


def test_snapshot_store_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    payload = build_snapshot_payload(
        created_at="2026-05-19T09:28:00+00:00",
        source_suffix="a",
    )

    stored_snapshot = store.save_snapshot(payload)
    loaded_snapshot = store.load_snapshot(stored_snapshot["snapshot_id"])

    assert stored_snapshot == loaded_snapshot
    assert store.snapshot_exists(stored_snapshot["snapshot_id"]) is True


def test_snapshot_store_lists_snapshots_in_descending_order(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    first = store.save_snapshot(
        build_snapshot_payload(
            created_at="2026-05-19T09:28:00+00:00",
            source_suffix="a",
        )
    )
    second = store.save_snapshot(
        build_snapshot_payload(
            created_at="2026-05-19T09:29:00+00:00",
            source_suffix="b",
        )
    )

    listed_snapshots = store.list_snapshots(limit=2)

    assert listed_snapshots == [second, first]


def test_snapshot_store_builds_deterministic_ids_and_respects_explicit_id(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")

    first_id = store.build_snapshot_id(
        created_at="2026-05-19T09:28:00+00:00",
        source_set=["approved_brent_feed", "approved_btcusd_feed"],
        report_type="paper_ingestion",
    )
    second_id = store.build_snapshot_id(
        created_at="2026-05-19T09:28:00+00:00",
        source_set=["approved_btcusd_feed", "approved_brent_feed"],
        report_type="paper_ingestion",
    )
    explicit_id = store.build_snapshot_id(
        created_at="2026-05-19T09:28:00+00:00",
        source_set=["approved_btcusd_feed"],
        report_type="paper_ingestion",
        explicit_snapshot_id="manual_snapshot_id",
    )

    assert first_id == second_id
    assert explicit_id == "manual_snapshot_id"


def test_snapshot_store_rejects_live_execution_metadata(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    payload = build_snapshot_payload(
        created_at="2026-05-19T09:28:00+00:00",
        source_suffix="a",
    )
    payload["execution_mode"] = "LIVE"

    try:
        store.save_snapshot(payload)
    except ValueError as exc:
        assert str(exc) == "snapshot execution_mode must remain PAPER_ONLY or NO_EXECUTION."
    else:
        raise AssertionError("SnapshotStore should reject live execution metadata.")

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
