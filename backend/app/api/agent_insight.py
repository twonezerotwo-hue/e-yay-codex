"""
GET /api/v1/agent/insight

Agent'ın "şu an dikkat çeken" gözlemlerini döndürür.
Tam pipeline (haberler + teknik + sermaye rotasyonu) ile sentez yapar.
Saf analiz katmanı — Groq'a istek YOK.
PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import dataclasses
import time
from datetime import UTC, datetime
from fastapi import APIRouter

from app.api.regime_report import (
    _FakeSession,
    _ensure_repo_root_on_path,
    _get_provider,
)
from app.providers import (
    SourceRegistryBoundProviderAdapter,
    build_provider_source_bindings,
)
from app.providers.capital_rotation_provider import CapitalRotationProvider
from app.providers.news_provider import NewsProvider
from app.providers.real_market_provider import RealMarketProvider
from app.providers.technical_provider import TechnicalProvider
from app.services.agent_output_guard import guard_response
from app.services.market_snapshot_service import MarketSnapshotService
from app.services.provider_ingestion_service import ProviderIngestionService
from app.services.regime_report_service import RegimeReportService
from app.services.agent_insight_service import generate_insights

router = APIRouter(prefix="/agent", tags=["agent"])

_INSIGHT_RESPONSE_CACHE: tuple[float, dict] | None = None
_INSIGHT_RESPONSE_TTL = 60


@router.get("/insight")
def get_agent_insight() -> dict:
    global _INSIGHT_RESPONSE_CACHE
    now = time.monotonic()
    if _INSIGHT_RESPONSE_CACHE and (now - _INSIGHT_RESPONSE_CACHE[0]) < _INSIGHT_RESPONSE_TTL:
        return _INSIGHT_RESPONSE_CACHE[1]

    _ensure_repo_root_on_path()
    from registry import build_source_registry_entries, load_source_registry

    source_registry = load_source_registry()
    entries = build_source_registry_entries(source_registry)

    base_provider = _get_provider()

    # 7g delta — gerçek provider'da var
    delta_map: dict = {}
    if isinstance(base_provider, RealMarketProvider):
        try:
            delta_map = base_provider.delta_map_by_code
        except Exception:
            delta_map = {}

    provider = SourceRegistryBoundProviderAdapter(
        base_provider, build_provider_source_bindings(entries),
    )
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), provider
    ).run()
    snapshots = tuple(p.snapshot for p in result.persisted_snapshots)

    # Haberler — agent sentezi için kritik
    news: tuple = ()
    try:
        news = NewsProvider().fetch_headlines(max_total=30)
    except Exception:
        news = ()

    # Teknik analiz — destek/direnç yakınlık tespiti için kritik
    tech_insights: dict = {}
    try:
        tech_insights = TechnicalProvider().compute()
    except Exception:
        tech_insights = {}

    # Tam rapor — haber + teknik dahil
    report = RegimeReportService().generate(
        snapshots,
        news_headlines=news,
        delta_map=delta_map,
        tech_insights=tech_insights,
    )

    try:
        rotation = CapitalRotationProvider().compute()
    except Exception:
        rotation = None

    insights = generate_insights(report, rotation)

    response = {
        "status": "ok",
        "execution_mode": "OFF / NO_EXECUTION",
        "generated_at": datetime.now(UTC).isoformat(),
        "decision": report.decision,
        "insights": [dataclasses.asdict(i) for i in insights],
    }
    response = guard_response(response, source="agent.insight")
    _INSIGHT_RESPONSE_CACHE = (now, response)
    return response


__all__ = [name for name in globals() if not name.startswith("_")]
