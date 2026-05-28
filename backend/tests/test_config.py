from app.core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "E-yAy BrainChain"
    assert settings.app_env == "development"
    assert settings.debug is True
    assert settings.api_prefix == "/api/v1"
    assert settings.execution_mode == "OFF"
    assert settings.log_level == "INFO"
    assert settings.database_url is None
    assert settings.redis_url is None


def test_settings_read_database_and_redis_urls(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://eyay_user:test@postgres:5432/eyay")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://eyay_user:test@postgres:5432/eyay"
    assert settings.redis_url == "redis://redis:6379/0"

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
