from sqlalchemy import DateTime, Integer, JSON, String

from app.db.base import Base
from app.db.models import AuditLog


def test_audit_log_model_imports() -> None:
    assert AuditLog.__name__ == "AuditLog"
    assert AuditLog.__tablename__ == "audit_logs"


def test_audit_logs_table_exists_in_metadata() -> None:
    assert "audit_logs" in Base.metadata.tables


def test_audit_log_columns_match_expected_schema() -> None:
    table = Base.metadata.tables["audit_logs"]

    assert isinstance(table.c.id.type, Integer)
    assert table.c.id.primary_key is True
    assert isinstance(table.c.event_type.type, String)
    assert isinstance(table.c.message.type, String)
    assert isinstance(table.c.details_json.type, JSON)
    assert table.c.request_id.nullable is True
    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
