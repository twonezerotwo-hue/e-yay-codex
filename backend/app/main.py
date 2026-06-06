from pathlib import Path

from dotenv import load_dotenv

# .env dosyasını os.environ'a yükle (ANTHROPIC_API_KEY dahil tüm değişkenler)
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_FILE, override=True)

import asyncio
import logging

from fastapi import FastAPI

from app.api.agent_audit import router as agent_audit_router
from app.api.agent_critique import router as agent_critique_router
from app.api.agent_insight import router as agent_insight_router
from app.api.ai_report import router as ai_report_router
from app.api.alerts import router as alerts_router
from app.api.ceo_report import router as ceo_report_router
from app.api.chart_patterns import router as chart_patterns_router
from app.api.chat import router as chat_router
from app.api.consensus import router as consensus_router
from app.api.core_snapshots import jobs_router as core_jobs_router
from app.api.core_snapshots import router as core_snapshots_router
from app.api.health import router as health_router
from app.api.paper_trading import router as paper_trading_router
from app.api.regime_report import router as regime_report_router
from app.api.snapshot_replay import router as snapshot_replay_router
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.execution_boundary import log_startup_boundary
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware


settings = get_settings()
configure_logging(settings.log_level)
_log = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(alerts_router, prefix=settings.api_prefix)
app.include_router(ceo_report_router, prefix=settings.api_prefix)
app.include_router(regime_report_router, prefix=settings.api_prefix)
app.include_router(ai_report_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(agent_insight_router, prefix=settings.api_prefix)
app.include_router(agent_audit_router, prefix=settings.api_prefix)
app.include_router(agent_critique_router, prefix=settings.api_prefix)
app.include_router(paper_trading_router, prefix=settings.api_prefix)
app.include_router(consensus_router, prefix=settings.api_prefix)
app.include_router(core_snapshots_router, prefix=settings.api_prefix)
app.include_router(core_jobs_router, prefix=settings.api_prefix)
app.include_router(chart_patterns_router, prefix=settings.api_prefix)
app.include_router(snapshot_replay_router, prefix=settings.api_prefix)


# ── Background tick scheduler — Sprint 1 / Item 1 ────────────────────────────
# GET /trading/state read-only oldu; tick'i bu background task tutuyor.

_TICK_INTERVAL_SECONDS = 30
_tick_task: asyncio.Task | None = None


async def _periodic_tick_loop() -> None:
    """Her 30 sn'de bir consensus tick'i çalıştır (off-thread, blocking-safe)."""
    from app.api.paper_trading import _run_tick_pipeline
    loop = asyncio.get_running_loop()
    # Startup'tan hemen sonra 5 sn bekle — uygulama tam yerleşsin.
    await asyncio.sleep(5)
    while True:
        try:
            result = await loop.run_in_executor(None, _run_tick_pipeline)
            _log.info("background_tick · status=%s · signals=%s · prices=%s",
                      result.get("status"),
                      result.get("signals_count"),
                      result.get("prices_count"))
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("background_tick failed (loop devam ediyor)")
        try:
            await asyncio.sleep(_TICK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise


@app.on_event("startup")
async def _startup() -> None:
    log_startup_boundary()
    global _tick_task
    _tick_task = asyncio.create_task(_periodic_tick_loop())
    _log.info("background_tick scheduler started · interval=%ss", _TICK_INTERVAL_SECONDS)


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _tick_task
    if _tick_task is not None:
        _tick_task.cancel()
        try:
            await _tick_task
        except (asyncio.CancelledError, Exception):
            pass
        _tick_task = None
        _log.info("background_tick scheduler stopped")


__all__ = [name for name in globals() if not name.startswith('_')]
