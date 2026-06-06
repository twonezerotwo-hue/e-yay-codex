from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.redis_client import get_redis_client
from app.db.session import get_engine


def ensure_dependency_configuration(settings: Settings) -> None:
    missing_settings: list[str] = []

    if not settings.database_url:
        missing_settings.append("database_url")

    if not settings.redis_url:
        missing_settings.append("redis_url")

    if missing_settings:
        raise AppError(
            error_code="READINESS_CONFIGURATION_MISSING",
            message="Required readiness configuration is missing.",
            details={"missing_settings": missing_settings},
            status_code=503,
        )


def check_database_connection(settings: Settings) -> str:
    if not settings.database_url:
        raise AppError(
            error_code="READINESS_CONFIGURATION_MISSING",
            message="Required readiness configuration is missing.",
            details={"missing_settings": ["database_url"]},
            status_code=503,
        )

    try:
        engine = get_engine(settings.database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise AppError(
            error_code="READINESS_DATABASE_UNAVAILABLE",
            message="Database readiness check failed.",
            details={"dependency": "database"},
            status_code=503,
        ) from exc

    return "ok"


def check_redis_connection(settings: Settings) -> str:
    if not settings.redis_url:
        raise AppError(
            error_code="READINESS_CONFIGURATION_MISSING",
            message="Required readiness configuration is missing.",
            details={"missing_settings": ["redis_url"]},
            status_code=503,
        )

    try:
        client = get_redis_client(settings.redis_url)
        client.ping()
    except RedisError as exc:
        raise AppError(
            error_code="READINESS_REDIS_UNAVAILABLE",
            message="Redis readiness check failed.",
            details={"dependency": "redis"},
            status_code=503,
        ) from exc

    return "ok"


def build_readiness_payload(settings: Settings) -> dict[str, object]:
    ensure_dependency_configuration(settings)
    database_status = check_database_connection(settings)
    redis_status = check_redis_connection(settings)

    return {
        "status": "ready",
        "dependencies": {
            "database": database_status,
            "redis": redis_status,
        },
    }

__all__ = [name for name in globals() if not name.startswith('_')]
