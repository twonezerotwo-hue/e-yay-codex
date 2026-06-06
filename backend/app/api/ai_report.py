"""
AI Analyst Report API
GET /api/v1/ai-report/current

Claude claude-opus-4-7 ile Katman 1+2+3 + jeopolitik haber analizi.
Önbellek: 15 dakika (pahalı istek — sık yenileme yok).
Execution: OFF / NO_EXECUTION
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.agent_output_guard import guard_response

router = APIRouter(prefix="/ai-report", tags=["ai-report"])

REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_repo_root_on_path() -> None:
    s = str(REPO_ROOT)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Regime report provider (paylaşılan önbellek — regime_report.py ile aynı)
# ---------------------------------------------------------------------------

import time as _time
from app.providers import MockMarketProvider
from app.providers.real_market_provider import RealMarketProvider

_PROVIDER_CACHE_TTL = 180  # yfinance ile uyumlu
_cached_provider: "RealMarketProvider | None" = None
_cached_provider_ts: float = 0.0


def _get_provider():
    global _cached_provider, _cached_provider_ts
    now = _time.monotonic()
    if _cached_provider is None or (now - _cached_provider_ts) > _PROVIDER_CACHE_TTL:
        try:
            _cached_provider = RealMarketProvider()
            _cached_provider_ts = now
        except Exception:  # noqa: BLE001
            return MockMarketProvider()
    return _cached_provider


# ---------------------------------------------------------------------------
# Serialize yardımcısı
# ---------------------------------------------------------------------------

def _to_dict(obj: object) -> object:
    import dataclasses
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(i) for i in obj]
    return obj


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/current")
def get_ai_report(
    force_refresh: bool = Query(default=False, description="Önbelleği yoksay, yeni rapor üret"),
) -> JSONResponse:
    """
    Piyasa katmanları + jeopolitik haberleri okuyup Claude ile Türkçe analiz üretir.
    Sonuç 15 dakika önbellekte tutulur.
    """
    _ensure_repo_root_on_path()

    from registry import build_source_registry_entries, load_source_registry

    from app.providers import SourceRegistryBoundProviderAdapter, build_provider_source_bindings
    from app.services import MarketSnapshotService, ProviderIngestionService
    from app.services.regime_report_service import RegimeReportService
    from app.providers.geo_news_provider import GeoNewsProvider
    from app.providers.capital_rotation_provider import CapitalRotationProvider
    from app.services.ai_analyst_service import generate_ai_report

    # ── Piyasa verisi al ──────────────────────────────────────────────────
    source_registry = load_source_registry()
    source_registry_entries = build_source_registry_entries(source_registry)

    base_provider = _get_provider()
    data_mode = "live" if isinstance(base_provider, RealMarketProvider) else "simulation"

    class _FakeSession:
        def add(self, _): pass
        def commit(self): pass
        def rollback(self): pass

    provider = SourceRegistryBoundProviderAdapter(
        base_provider,
        build_provider_source_bindings(source_registry_entries),
    )
    ingestion_result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), provider
    ).run()

    snapshots = tuple(p.snapshot for p in ingestion_result.persisted_snapshots)
    report = RegimeReportService().generate(snapshots, news_headlines=())

    # ── Jeopolitik haberler ───────────────────────────────────────────────
    geo_news = ()
    try:
        geo_news = GeoNewsProvider().fetch(max_total=30)
    except Exception:  # noqa: BLE001
        pass

    # ── Sermaye rotasyonu ────────────────────────────────────────────────
    rotation = None
    try:
        rotation = CapitalRotationProvider().compute()
    except Exception:  # noqa: BLE001
        pass

    # ── Veriyi dict'e çevir (AI servisine geç) ────────────────────────────
    import dataclasses
    macro_dict = dataclasses.asdict(report.macro_layer)
    appetite_dict = dataclasses.asdict(report.appetite_layer)
    assets_list = [dataclasses.asdict(s) for s in report.asset_signals]
    checklist_list = [dataclasses.asdict(c) for c in report.confirmation_checklist]

    # ── AI raporu üret ────────────────────────────────────────────────────
    ai_report = generate_ai_report(
        macro=macro_dict,
        appetite=appetite_dict,
        assets=assets_list,
        checklist=checklist_list,
        decision=report.decision,
        verdict=report.verdict,
        geo_news=geo_news,
        rotation=rotation,
        force_refresh=force_refresh,
    )

    payload = guard_response({
        "status": "ok",
        "data_mode": data_mode,
        "execution_mode": "OFF / NO_EXECUTION",
        "ai_report": _to_dict(ai_report),
        "geo_news_count": len(geo_news),
        "capital_rotation": _to_dict(rotation) if rotation else None,
    }, source="ai_report.current")
    return JSONResponse(content=payload)


__all__ = [name for name in globals() if not name.startswith("_")]
