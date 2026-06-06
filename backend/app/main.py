from pathlib import Path

from dotenv import load_dotenv

# .env dosyasını os.environ'a yükle (ANTHROPIC_API_KEY dahil tüm değişkenler)
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_FILE, override=True)

from fastapi import FastAPI

from app.api.agent_insight import router as agent_insight_router
from app.api.ai_report import router as ai_report_router
from app.api.ceo_report import router as ceo_report_router
from app.api.chat import router as chat_router
from app.api.consensus import router as consensus_router
from app.api.health import router as health_router
from app.api.paper_trading import router as paper_trading_router
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
app.include_router(ai_report_router, prefix=settings.api_prefix)
app.include_router(chat_router, prefix=settings.api_prefix)
app.include_router(agent_insight_router, prefix=settings.api_prefix)
app.include_router(paper_trading_router, prefix=settings.api_prefix)
app.include_router(consensus_router, prefix=settings.api_prefix)
app.include_router(snapshot_replay_router, prefix=settings.api_prefix)

__all__ = [name for name in globals() if not name.startswith('_')]
