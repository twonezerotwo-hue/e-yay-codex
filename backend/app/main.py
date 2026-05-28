from fastapi import FastAPI

from app.api.ceo_report import router as ceo_report_router
from app.api.health import router as health_router
from app.api.regime_report import router as regime_report_router
from app.api.snapshot_replay import router as snapshot_replay_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware


settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(title=settings.app_name)
app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(ceo_report_router, prefix=settings.api_prefix)
app.include_router(regime_report_router, prefix=settings.api_prefix)
app.include_router(snapshot_replay_router, prefix=settings.api_prefix)

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
