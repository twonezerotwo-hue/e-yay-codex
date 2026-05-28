from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core import readiness
from app.main import app


client = TestClient(app)


def test_health_returns_expected_body() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "E-yAy BrainChain",
        "environment": "development",
        "execution_mode": "OFF",
    }


def test_health_response_includes_request_id_header() -> None:
    response = client.get("/health")
    request_id = response.headers.get("X-Request-ID")

    assert request_id is not None
    assert request_id != ""


def test_health_live_returns_alive() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_health_ready_returns_expected_body(monkeypatch) -> None:
    database_checked = False
    redis_checked = False

    def mock_database_check(settings: Settings) -> str:
        nonlocal database_checked
        database_checked = True
        return "ok"

    def mock_redis_check(settings: Settings) -> str:
        nonlocal redis_checked
        redis_checked = True
        return "ok"

    monkeypatch.setattr(readiness, "check_database_connection", mock_database_check)
    monkeypatch.setattr(readiness, "check_redis_connection", mock_redis_check)
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_name="E-yAy BrainChain",
        app_env="development",
        debug=True,
        api_prefix="/api/v1",
        execution_mode="OFF",
        log_level="INFO",
        database_url="postgresql://eyay_user:test@postgres:5432/eyay",
        redis_url="redis://redis:6379/0",
    )
    response = client.get("/health/ready")

    try:
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "dependencies": {
                "database": "ok",
                "redis": "ok",
            },
        }
        assert database_checked is True
        assert redis_checked is True
    finally:
        app.dependency_overrides.clear()


def test_health_ready_returns_controlled_503_when_dependency_fails(monkeypatch) -> None:
    database_checked = False
    redis_checked = False

    def mock_database_check(settings: Settings) -> str:
        nonlocal database_checked
        database_checked = True
        return "ok"

    def mock_redis_check(settings: Settings) -> str:
        nonlocal redis_checked
        redis_checked = True
        raise AppError(
            error_code="READINESS_REDIS_UNAVAILABLE",
            message="Redis readiness check failed.",
            details={"dependency": "redis"},
            status_code=503,
        )

    monkeypatch.setattr(readiness, "check_database_connection", mock_database_check)
    monkeypatch.setattr(readiness, "check_redis_connection", mock_redis_check)
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_name="E-yAy BrainChain",
        app_env="development",
        debug=True,
        api_prefix="/api/v1",
        execution_mode="OFF",
        log_level="INFO",
        database_url="postgresql+psycopg://eyay_user:test@postgres:5432/eyay",
        redis_url="redis://redis:6379/0",
    )
    response = client.get("/health/ready")
    body = response.json()

    try:
        assert response.status_code == 503
        assert body == {
            "error_code": "READINESS_REDIS_UNAVAILABLE",
            "message": "Redis readiness check failed.",
            "details": {"dependency": "redis"},
            "request_id": body["request_id"],
        }
        assert body["request_id"] != ""
        assert response.headers.get("X-Request-ID") == body["request_id"]
        assert database_checked is True
        assert redis_checked is True
    finally:
        app.dependency_overrides.clear()


def test_health_error_endpoint_returns_standard_error_response() -> None:
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
