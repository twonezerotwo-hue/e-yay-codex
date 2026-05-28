"""
Regime Report API — 4-katmanlı piyasa analizi endpoint'i.
GET /api/v1/regime-report/current

Döner: RegimeReport JSON (macro, appetite, signals, decision, news, verdict)
Execution: OFF / NO_EXECUTION — hiçbir zaman işlem açmaz.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.providers import MockMarketProvider
from app.providers import SourceRegistryBoundProviderAdapter
from app.providers import build_provider_source_bindings
from app.providers.news_provider import NewsProvider
from app.providers.real_market_provider import RealMarketProvider
from app.services import MarketSnapshotService
from app.services import ProviderIngestionService
from app.services.regime_report_service import RegimeReportService

router = APIRouter(prefix="/regime-report", tags=["regime-report"])
REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Provider önbelleği — 300 saniye (5 dk) geçerli, ardından yeniden çekilir
# ---------------------------------------------------------------------------
import time as _time
_PROVIDER_CACHE_TTL = 300   # saniye
_cached_provider: "RealMarketProvider | None" = None
_cached_provider_ts: float = 0.0


def _get_provider() -> "RealMarketProvider | MockMarketProvider":
    global _cached_provider, _cached_provider_ts
    now = _time.monotonic()
    if _cached_provider is None or (now - _cached_provider_ts) > _PROVIDER_CACHE_TTL:
        try:
            _cached_provider = RealMarketProvider()
            _cached_provider_ts = now
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "RealMarketProvider önbelleklenemedi, mock kullanılıyor: %s", exc
            )
            return MockMarketProvider()
    return _cached_provider


def _ensure_repo_root_on_path() -> None:
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


class _FakeSession:
    def add(self, _: object) -> None: pass
    def commit(self) -> None: pass
    def rollback(self) -> None: pass


def _serialize_report(report: object) -> dict:
    from dataclasses import asdict
    import dataclasses

    def _convert(obj: object) -> object:
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, tuple):
            return [_convert(i) for i in obj]
        if isinstance(obj, list):
            return [_convert(i) for i in obj]
        return obj

    return _convert(report)  # type: ignore[return-value]


@router.get("/current")
def get_current_regime_report(
    include_news: bool = Query(default=True, description="Haber başlıklarını dahil et"),
) -> JSONResponse:
    """
    Mevcut piyasa verilerinden 4-katmanlı regime raporu üretir.
    Veri: simulation/mock (paper-safe). Execution: OFF.
    """
    _ensure_repo_root_on_path()

    from registry import build_source_registry_entries, load_source_registry

    source_registry = load_source_registry()
    source_registry_entries = build_source_registry_entries(source_registry)

    base_provider = _get_provider()
    data_mode = "live" if isinstance(base_provider, RealMarketProvider) else "simulation"

    provider = SourceRegistryBoundProviderAdapter(
        base_provider,
        build_provider_source_bindings(source_registry_entries),
    )
    ingestion_result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), provider
    ).run()

    snapshots = tuple(
        persisted.snapshot for persisted in ingestion_result.persisted_snapshots
    )

    # Haber çekimi
    news = ()
    if include_news:
        try:
            news = NewsProvider().fetch_headlines(max_total=15)
        except Exception:  # noqa: BLE001
            news = ()

    report = RegimeReportService().generate(snapshots, news_headlines=news)
    serialized = _serialize_report(report)

    return JSONResponse(content={
        "status": "ok",
        "data_mode": data_mode,
        "execution_mode": "OFF / NO_EXECUTION",
        "report": serialized,
        "meta": {
            "total_snapshots": len(snapshots),
            "blocking_signals": report.blocking_count,
            "confirmed_signals": report.confirmed_count,
            "news_fetched": len(report.news_headlines),
        },
    })


__all__ = [name for name in globals() if not name.startswith("_")]
