from pathlib import Path

from dotenv import load_dotenv

# .env dosyasını os.environ'a yükle (ANTHROPIC_API_KEY dahil tüm değişkenler)
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_FILE, override=True)

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agent_banner import router as agent_banner_router
from app.api.ai_trade_opinion import router as ai_trade_opinion_router
from app.api.breaking_news_visual import router as breaking_news_visual_router
from app.api.capital_rotation_visual import router as capital_rotation_visual_router
from app.api.agent_audit import router as agent_audit_router
from app.api.agent_chart import router as agent_chart_router
from app.api.agent_critique import router as agent_critique_router
from app.api.agent_ensemble import router as agent_ensemble_router
from app.api.agent_eval import router as agent_eval_router
from app.api.agent_insight import router as agent_insight_router
from app.api.agent_memory import router as agent_memory_router
from app.api.agent_persona import router as agent_persona_router
from app.api.agent_stream import router as agent_stream_router
from app.api.agent_tools import router as agent_tools_router
from app.api.ai_report import router as ai_report_router
from app.api.alerts import router as alerts_router
from app.api.ceo_report import router as ceo_report_router
from app.api.chart_patterns import router as chart_patterns_router
from app.api.chat import router as chat_router
from app.api.consensus import router as consensus_router
from app.api.core_snapshots import jobs_router as core_jobs_router
from app.api.core_snapshots import router as core_snapshots_router
from app.api.health import router as health_router
from app.api.hourly_snapshots import router as hourly_snapshots_router
from app.api.learning_candidates import router as learning_candidates_router
from app.api.mistake_memory import router as mistake_memory_router
from app.api.auto_tune import router as auto_tune_router
from app.api.weekly_calibration import router as weekly_calibration_router
from app.api.learning_summary import router as learning_summary_router
from app.api.scheduler import router as scheduler_router
from app.api.system_health import router as system_health_router
from app.api.position_rechecks import router as position_rechecks_router
from app.api.paper_trading import router as paper_trading_router
from app.api.market_strategist import router as market_strategist_router
from app.api.paper_decision import router as paper_decision_router
from app.api.signal_attribution import router as signal_attribution_router
from app.api.dashboard_state import router as dashboard_state_router
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


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Startup
    log_startup_boundary()
    global _tick_task
    _tick_task = asyncio.create_task(_periodic_tick_loop())
    _log.info("background_tick scheduler started · interval=%ss", _TICK_INTERVAL_SECONDS)
    try:
        yield
    finally:
        # Shutdown
        if _tick_task is not None:
            _tick_task.cancel()
            try:
                await _tick_task
            except (asyncio.CancelledError, Exception):
                pass
            _tick_task = None
            _log.info("background_tick scheduler stopped")


app = FastAPI(title=settings.app_name, lifespan=_lifespan)
app.add_middleware(RequestIDMiddleware)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(alerts_router, prefix=settings.api_prefix)
app.include_router(ceo_report_router, prefix=settings.api_prefix)
app.include_router(regime_report_router, prefix=settings.api_prefix)
app.include_router(dashboard_state_router, prefix=settings.api_prefix)
app.include_router(ai_report_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(agent_insight_router, prefix=settings.api_prefix)
app.include_router(agent_audit_router, prefix=settings.api_prefix)
app.include_router(agent_chart_router, prefix=settings.api_prefix)
app.include_router(agent_critique_router, prefix=settings.api_prefix)
app.include_router(agent_eval_router, prefix=settings.api_prefix)
app.include_router(agent_tools_router, prefix=settings.api_prefix)
app.include_router(agent_memory_router, prefix=settings.api_prefix)
app.include_router(agent_stream_router, prefix=settings.api_prefix)
app.include_router(agent_persona_router, prefix=settings.api_prefix)
app.include_router(agent_ensemble_router, prefix=settings.api_prefix)
app.include_router(paper_trading_router, prefix=settings.api_prefix)
app.include_router(signal_attribution_router, prefix=settings.api_prefix)
app.include_router(market_strategist_router, prefix=settings.api_prefix)
app.include_router(paper_decision_router, prefix=settings.api_prefix)
app.include_router(consensus_router, prefix=settings.api_prefix)
app.include_router(core_snapshots_router, prefix=settings.api_prefix)
app.include_router(core_jobs_router, prefix=settings.api_prefix)
app.include_router(chart_patterns_router, prefix=settings.api_prefix)
app.include_router(snapshot_replay_router, prefix=settings.api_prefix)
app.include_router(hourly_snapshots_router, prefix=settings.api_prefix)
app.include_router(position_rechecks_router, prefix=settings.api_prefix)
app.include_router(learning_candidates_router, prefix=settings.api_prefix)
app.include_router(mistake_memory_router, prefix=settings.api_prefix)
app.include_router(auto_tune_router, prefix=settings.api_prefix)
app.include_router(weekly_calibration_router, prefix=settings.api_prefix)
app.include_router(learning_summary_router, prefix=settings.api_prefix)
app.include_router(scheduler_router, prefix=settings.api_prefix)
app.include_router(system_health_router, prefix=settings.api_prefix)
app.include_router(agent_banner_router, prefix=settings.api_prefix)
app.include_router(ai_trade_opinion_router, prefix=settings.api_prefix)
app.include_router(capital_rotation_visual_router, prefix=settings.api_prefix)
app.include_router(breaking_news_visual_router, prefix=settings.api_prefix)


__all__ = [name for name in globals() if not name.startswith('_')]
