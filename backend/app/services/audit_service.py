from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.db.session import get_session


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def build_audit_log(
        self,
        *,
        event_type: str,
        message: str,
        details_json: dict[str, Any] | list[Any] | str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        return AuditLog(
            event_type=event_type,
            message=message,
            details_json=details_json,
            request_id=request_id,
        )

    def create_log(
        self,
        *,
        event_type: str,
        message: str,
        details_json: dict[str, Any] | list[Any] | str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        audit_log = self.build_audit_log(
            event_type=event_type,
            message=message,
            details_json=details_json,
            request_id=request_id,
        )
        self.session.add(audit_log)
        self.session.flush()
        return audit_log


def persist_audit_log(
    *,
    database_url: str,
    event_type: str,
    message: str,
    details_json: dict[str, Any] | list[Any] | str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    session = get_session(database_url)

    try:
        audit_log = AuditService(session).create_log(
            event_type=event_type,
            message=message,
            details_json=details_json,
            request_id=request_id,
        )
        session.commit()
        return audit_log
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

__all__ = [name for name in globals() if not name.startswith('_')]
