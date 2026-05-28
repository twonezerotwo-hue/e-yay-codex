from app.db.models import AuditLog
from app.services import AuditService


class FakeSession:
    def __init__(self) -> None:
        self.added: list[AuditLog] = []
        self.flush_called = False

    def add(self, instance: AuditLog) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_called = True


def test_build_audit_log_sets_expected_fields() -> None:
    service = AuditService(FakeSession())  # type: ignore[arg-type]

    audit_log = service.build_audit_log(
        event_type="health.check",
        message="Health endpoint called.",
        details_json={"status": "ok"},
        request_id="req-123",
    )

    assert isinstance(audit_log, AuditLog)
    assert audit_log.event_type == "health.check"
    assert audit_log.message == "Health endpoint called."
    assert audit_log.details_json == {"status": "ok"}
    assert audit_log.request_id == "req-123"


def test_create_log_adds_audit_log_to_session() -> None:
    session = FakeSession()
    service = AuditService(session)  # type: ignore[arg-type]

    audit_log = service.create_log(
        event_type="pipeline.event",
        message="Pipeline event recorded.",
        details_json={"source": "test"},
        request_id="req-456",
    )

    assert session.added == [audit_log]
    assert session.flush_called is True


def test_create_log_allows_null_request_id() -> None:
    service = AuditService(FakeSession())  # type: ignore[arg-type]

    audit_log = service.create_log(
        event_type="owner.brief",
        message="Owner brief generated.",
        details_json={"length": "short"},
        request_id=None,
    )

    assert audit_log.request_id is None

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
