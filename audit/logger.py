from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def create_audit_record(
    *,
    event_type: str,
    message: str,
    details_json: dict[str, Any] | list[Any] | str | None = None,
    request_id: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    return {
        "timestamp_utc": timestamp,
        "event_type": event_type,
        "message": message,
        "details_json": details_json,
        "request_id": request_id,
    }
