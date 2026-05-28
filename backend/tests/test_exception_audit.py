from app.core.config import Settings
from app.core import exception_handlers
from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_health_error_endpoint_triggers_audit_service(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        exception_handlers,
        "get_settings",
        lambda: Settings(
            app_name="E-yAy BrainChain",
            app_env="development",
            debug=True,
            api_prefix="/api/v1",
            execution_mode="OFF",
            log_level="INFO",
            database_url="postgresql+psycopg://eyay_user:test@postgres:5432/eyay",
            redis_url="redis://redis:6379/0",
        ),
    )

    def mock_persist_audit_log(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        exception_handlers.audit_service_module,
        "persist_audit_log",
        mock_persist_audit_log,
    )

    response = client.get("/health/error-test")
    body = response.json()

    assert response.status_code == 400
    assert len(calls) == 1
    assert calls[0] == {
        "database_url": "postgresql+psycopg://eyay_user:test@postgres:5432/eyay",
        "event_type": "app_error",
        "message": "Controlled health error for testing.",
        "details_json": {
            "error_code": "HEALTH_ERROR_TEST",
            "details": {"reason": "controlled_test"},
            "path": "/health/error-test",
            "method": "GET",
            "status_code": 400,
        },
        "request_id": body["request_id"],
    }


def test_health_error_endpoint_still_returns_standard_error_when_audit_write_fails(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        exception_handlers,
        "get_settings",
        lambda: Settings(
            app_name="E-yAy BrainChain",
            app_env="development",
            debug=True,
            api_prefix="/api/v1",
            execution_mode="OFF",
            log_level="INFO",
            database_url="postgresql+psycopg://eyay_user:test@postgres:5432/eyay",
            redis_url="redis://redis:6379/0",
        ),
    )
    monkeypatch.setattr(
        exception_handlers.audit_service_module,
        "persist_audit_log",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit failed")),
    )

    response = client.get("/health/error-test")
    body = response.json()

    assert response.status_code == 400
    assert body == {
        "error_code": "HEALTH_ERROR_TEST",
        "message": "Controlled health error for testing.",
        "details": {"reason": "controlled_test"},
        "request_id": body["request_id"],
    }
    assert body["request_id"] != ""
    assert response.headers.get("X-Request-ID") == body["request_id"]

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
