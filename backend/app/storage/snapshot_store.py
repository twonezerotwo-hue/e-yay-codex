from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT_STORE_FILENAME = "ceo_report_demo_snapshots.jsonl"


class SnapshotStore:
    REQUIRED_FIELDS = (
        "created_at",
        "mode",
        "source_registry_version",
        "source_observations",
        "missing_sources",
        "stale_sources",
        "report_type",
        "decision_permission",
        "execution_mode",
    )
    ALLOWED_MODES = {"PAPER_SAFE", "SIMULATION"}
    ALLOWED_EXECUTION_MODES = {"PAPER_ONLY", "NO_EXECUTION"}

    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)

    def save_snapshot(self, snapshot_payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = self._normalize_value(deepcopy(snapshot_payload))

        snapshot_id = normalized_payload.get("snapshot_id")
        created_at = normalized_payload.get("created_at")
        report_type = normalized_payload.get("report_type")
        source_observations = normalized_payload.get("source_observations", {})
        source_set = sorted(source_observations.keys()) if isinstance(source_observations, dict) else ()

        normalized_payload["snapshot_id"] = self.build_snapshot_id(
            created_at=created_at,
            source_set=source_set,
            report_type=report_type,
            explicit_snapshot_id=snapshot_id,
        )
        self._validate_snapshot_payload(normalized_payload)

        entries = self._read_entries()
        replaced = False

        for index, entry in enumerate(entries):
            if entry["snapshot_id"] == normalized_payload["snapshot_id"]:
                entries[index] = normalized_payload
                replaced = True
                break

        if not replaced:
            entries.append(normalized_payload)

        self._write_entries(entries)
        return normalized_payload

    def load_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        for entry in self._read_entries():
            if entry["snapshot_id"] == snapshot_id:
                return entry
        raise KeyError(snapshot_id)

    def list_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        entries = self._read_entries()
        sorted_entries = sorted(
            entries,
            key=lambda item: (
                item.get("created_at", ""),
                item.get("snapshot_id", ""),
            ),
            reverse=True,
        )
        return sorted_entries[:limit]

    def snapshot_exists(self, snapshot_id: str) -> bool:
        return any(entry["snapshot_id"] == snapshot_id for entry in self._read_entries())

    def build_snapshot_id(
        self,
        *,
        created_at: datetime | str | None,
        source_set: list[str] | tuple[str, ...],
        report_type: str | None,
        explicit_snapshot_id: str | None = None,
    ) -> str:
        if explicit_snapshot_id:
            return explicit_snapshot_id

        if created_at is None or report_type is None:
            raise ValueError("created_at and report_type are required when snapshot_id is not explicit.")

        created_at_iso = self._normalize_datetime_value(created_at)
        normalized_source_set = sorted(set(source_set))
        seed_payload = {
            "created_at": created_at_iso,
            "report_type": report_type,
            "source_set": normalized_source_set,
        }
        seed = json.dumps(seed_payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        report_slug = re.sub(r"[^a-z0-9]+", "_", report_type.lower()).strip("_")
        timestamp_slug = created_at_iso.replace("-", "").replace(":", "").replace("+00:00", "Z")
        return f"{report_slug}_{timestamp_slug}_{digest}"

    def _read_entries(self) -> list[dict[str, Any]]:
        if not self.storage_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        with self.storage_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
        return entries

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=True, sort_keys=True))
                handle.write("\n")

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return self._normalize_datetime_value(value)
        if isinstance(value, dict):
            return {str(key): self._normalize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._normalize_value(item) for item in value]
        return value

    def _normalize_datetime_value(self, value: datetime | str) -> str:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            parsed = value

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(UTC).isoformat()

    def _validate_snapshot_payload(self, snapshot_payload: dict[str, Any]) -> None:
        missing_fields = [
            field_name
            for field_name in self.REQUIRED_FIELDS
            if field_name not in snapshot_payload or snapshot_payload[field_name] is None
        ]
        if missing_fields:
            raise ValueError(
                "snapshot_payload is missing required fields: "
                + ", ".join(sorted(missing_fields))
            )

        if snapshot_payload["mode"] not in self.ALLOWED_MODES:
            raise ValueError("snapshot mode must be PAPER_SAFE or SIMULATION.")

        if snapshot_payload["decision_permission"] != "NO_EXECUTION":
            raise ValueError("snapshot decision_permission must remain NO_EXECUTION.")

        if snapshot_payload["execution_mode"] not in self.ALLOWED_EXECUTION_MODES:
            raise ValueError("snapshot execution_mode must remain PAPER_ONLY or NO_EXECUTION.")

        if not isinstance(snapshot_payload["source_observations"], dict):
            raise TypeError("source_observations must be a mapping of source ids to timestamps.")

        if not isinstance(snapshot_payload["missing_sources"], list):
            raise TypeError("missing_sources must be a list.")

        if not isinstance(snapshot_payload["stale_sources"], list):
            raise TypeError("stale_sources must be a list.")

        if "snapshots" in snapshot_payload and not isinstance(snapshot_payload["snapshots"], list):
            raise TypeError("snapshots must be a list when provided.")


def build_local_snapshot_store(
    storage_name: str = DEFAULT_SNAPSHOT_STORE_FILENAME,
) -> SnapshotStore:
    repo_root = Path(__file__).resolve().parents[3]
    return SnapshotStore(repo_root / "backend" / "storage_data" / storage_name)

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
