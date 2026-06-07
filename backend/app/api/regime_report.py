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
from app.providers.technical_provider import TechnicalProvider
from app.providers.capital_rotation_provider import CapitalRotationProvider
from app.providers.real_market_provider import RealMarketProvider
from app.services import MarketSnapshotService
from app.services import ProviderIngestionService
from app.services.regime_report_service import RegimeReportService
from app.services.event_calendar_service import EventCalendarService

router = APIRouter(prefix="/regime-report", tags=["regime-report"])
REPO_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Provider önbelleği — 180 saniye (3 dk) yfinance soft limitiyle uyumlu
# ---------------------------------------------------------------------------
import time as _time
_PROVIDER_CACHE_TTL = 180   # saniye
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

    # 7 günlük delta — sadece gerçek provider'da mevcut
    delta_map: dict = {}
    if isinstance(base_provider, RealMarketProvider):
        try:
            delta_map = base_provider.delta_map_by_code
        except Exception:  # noqa: BLE001
            delta_map = {}

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
            news = NewsProvider().fetch_headlines(max_total=30)
        except Exception:  # noqa: BLE001
            news = ()

    # Olay takvimi
    try:
        catalysts = EventCalendarService().fetch_upcoming(horizon_days=120, max_events=20)
    except Exception:  # noqa: BLE001
        catalysts = ()

    # Teknik analiz (OHLCV bazlı dinamik eşikler)
    tech_insights = {}
    try:
        tech_insights = TechnicalProvider().compute()
    except Exception:  # noqa: BLE001
        tech_insights = {}

    # Sermaye rotasyonu (çapraz varlık korelasyon + para akış yönü)
    rotation = None
    try:
        rotation = CapitalRotationProvider().compute()
    except Exception:  # noqa: BLE001
        rotation = None

    report = RegimeReportService().generate(
        snapshots,
        news_headlines=news,
        upcoming_catalysts=catalysts,
        delta_map=delta_map,
        tech_insights=tech_insights,
    )
    serialized = _serialize_report(report)

    # ── Modül sağlık skorları ──────────────────────────────────────────────
    from datetime import date as _date
    _today_str = _date.today().isoformat()
    # Takvim: yaklaşık tarih içeriyorsa MEDIUM, yoksa HIGH
    _cal_approx = sum(1 for c in report.upcoming_catalysts if "[~" in c.name)
    _cal_score  = "HIGH" if _cal_approx == 0 else ("MEDIUM" if _cal_approx < 3 else "LOW")

    # Fiyat verisi: simülasyon modunda LOW, live ise HIGH
    _price_score = "HIGH" if data_mode == "live" else "LOW"

    # Haber: kaç kaynak başarılı döndü (news_fetched / beklenen)
    _news_count = len(report.news_headlines)
    _news_score = "HIGH" if _news_count >= 20 else ("MEDIUM" if _news_count >= 8 else "LOW")

    # Sinyal: blocking sayısına göre güven
    _blocking = report.blocking_count
    _sig_score = "LOW" if _blocking >= 3 else ("MEDIUM" if _blocking >= 2 else "HIGH")

    # Rotasyon: veri var mı?
    _rot_score = "HIGH" if (rotation and not rotation.error) else "LOW"

    module_health = {
        "calendar":  {"score": _cal_score,   "detail": f"BLS 2026 hardcoded · {_cal_approx} yaklaşık tarih"},
        "price":     {"score": _price_score,  "detail": f"{data_mode} · {len(snapshots)} varlık"},
        "news":      {"score": _news_score,   "detail": f"{_news_count} haber · çok kaynak"},
        "signals":   {"score": _sig_score,    "detail": f"{_blocking} blocking · {report.confirmed_count} confirmed"},
        "rotation":  {"score": _rot_score,    "detail": "sermaye rotasyonu aktif" if rotation else "rotasyon verisi yok"},
    }

    return JSONResponse(content={
        "status": "ok",
        "data_mode": data_mode,
        "execution_mode": "OFF / NO_EXECUTION",
        "report": serialized,
        "capital_rotation": _serialize_report(rotation) if rotation else None,
        "module_health": module_health,
        "meta": {
            "total_snapshots": len(snapshots),
            "blocking_signals": report.blocking_count,
            "confirmed_signals": report.confirmed_count,
            "news_fetched": len(report.news_headlines),
            "catalysts_fetched": len(report.upcoming_catalysts),
            "tech_insights": len(report.tech_insights),
            "rotation_ratios": len(rotation.ratios) if rotation else 0,
        },
    })


__all__ = [name for name in globals() if not name.startswith("_")]
