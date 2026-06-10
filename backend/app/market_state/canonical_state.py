"""CanonicalMarketState — tüm dashboard panellerinin ortak veri kaynağı.

`RegimeReportService.generate()` regime_report, ai_report ve strategist
endpoint'lerinde ayrı ayrı koşuyordu → aynı an farklı paneller hafif farklı
veri görebiliyordu. Bu modül tek pipeline koşturup ortak `snapshot_id` ile
serialize eder ve `risk_gate / agent_votes / position_checks` ViewModel'lerini
state'e gömer.

PAPER_SAFE / NO_EXECUTION — sadece okuma + birleştirme.
"""
from __future__ import annotations

import dataclasses
import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Canonical dataclass ─────────────────────────────────────────────────────


@dataclass
class CanonicalMarketState:
    """Tek snapshot — paneller bundan beslenir."""
    snapshot_id:            str
    generated_at:           str
    data_mode:              str
    execution_mode:         str

    regime_report:          dict
    macro_layer:            dict
    appetite_layer:         dict
    asset_signals:          list[dict]
    confirmation_checklist: list[dict]
    scenarios:              list[dict]
    asymmetry:              dict | None

    technical_state:        dict | None
    capital_rotation:       dict | None
    geo_news:               list[dict]
    event_calendar:         list[dict]

    # Phase 2 ViewModels
    risk_gate:              dict | None
    agent_votes:            list[dict]
    position_checks:        list[dict]

    paper_trading:          dict | None

    data_quality:           dict
    module_health:          dict
    warnings:               list[str] = field(default_factory=list)


# ── Yardımcılar ──────────────────────────────────────────────────────────────


def _to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _snapshot_id(generated_at: str, data_mode: str, asset_count: int) -> str:
    raw = f"{generated_at}|{data_mode}|{asset_count}"
    return "dash::" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _build_module_health(
    *, data_mode: str, snapshot_count: int, report, rotation, news_count: int,
    catalysts,
) -> dict[str, dict]:
    """regime_report.py:179'daki module_health üretimini birebir tekrar eder.

    Sıfırdan logic yazmaz; UI aynı şekilde sağlık skorlarını okur.
    """
    cal_approx = sum(1 for c in catalysts if isinstance(getattr(c, "name", ""), str) and "[~" in c.name)
    cal_score  = "HIGH" if cal_approx == 0 else ("MEDIUM" if cal_approx < 3 else "LOW")
    price_score = "HIGH" if data_mode == "live" else "LOW"
    news_score = "HIGH" if news_count >= 20 else ("MEDIUM" if news_count >= 8 else "LOW")
    blocking = getattr(report, "blocking_count", 0)
    sig_score = "LOW" if blocking >= 3 else ("MEDIUM" if blocking >= 2 else "HIGH")
    rot_score = "HIGH" if (rotation and not getattr(rotation, "error", None)) else "LOW"

    return {
        "calendar":  {"score": cal_score,   "detail": f"{cal_approx} yaklaşık tarih"},
        "price":     {"score": price_score, "detail": f"{data_mode} · {snapshot_count} varlık"},
        "news":      {"score": news_score,  "detail": f"{news_count} haber"},
        "signals":   {"score": sig_score,   "detail": f"{blocking} blocking · {getattr(report,'confirmed_count',0)} confirmed"},
        "rotation":  {"score": rot_score,   "detail": "rotasyon aktif" if rotation else "rotasyon yok"},
    }


def _data_quality_summary(module_health: dict[str, dict]) -> dict:
    """Module health'ten basit DQS hesabı (0-100)."""
    weights = {"HIGH": 100.0, "MEDIUM": 60.0, "LOW": 20.0}
    scores: list[float] = []
    per_module: dict[str, float] = {}
    for name, info in module_health.items():
        s = weights.get(str(info.get("score", "")).upper(), 0.0)
        per_module[name] = s
        scores.append(s)
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    return {
        "score":  avg,
        "passed": avg >= 55.0,
        "per_module": per_module,
    }


# ── Build orchestrator ──────────────────────────────────────────────────────


def build_canonical_state(
    *,
    include_paper: bool = True,
    include_news: bool = True,
) -> CanonicalMarketState:
    """Tek pipeline koşturup CanonicalMarketState üretir.

    Mevcut sağlayıcıları (provider, ingestion, regime, rotation, news, calendar,
    technical) regime_report.py ile birebir aynı sırada çağırır → veri tutarlı.
    """
    # Lazy import: paket import grafı temiz kalsın
    from app.api.regime_report import _get_provider, _serialize_report
    from app.providers import (
        SourceRegistryBoundProviderAdapter,
        build_provider_source_bindings,
    )
    from app.providers.capital_rotation_provider import CapitalRotationProvider
    from app.providers.geo_news_provider import GeoNewsProvider
    from app.providers.news_provider import NewsProvider
    from app.providers.real_market_provider import RealMarketProvider
    from app.providers.technical_provider import TechnicalProvider
    from app.services import MarketSnapshotService, ProviderIngestionService
    from app.services.event_calendar_service import EventCalendarService
    from app.services.regime_report_service import RegimeReportService
    from registry import build_source_registry_entries, load_source_registry

    from app.market_state.risk_gate_view import (
        build_agent_votes, build_position_checks, build_risk_gate,
    )

    warnings: list[str] = []

    source_registry = load_source_registry()
    source_registry_entries = build_source_registry_entries(source_registry)
    base_provider = _get_provider()
    data_mode = "live" if isinstance(base_provider, RealMarketProvider) else "simulation"

    class _FakeSession:
        def add(self, _): pass
        def commit(self): pass
        def rollback(self): pass

    market_provider = SourceRegistryBoundProviderAdapter(
        base_provider,
        build_provider_source_bindings(source_registry_entries),
    )
    ingestion = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), market_provider
    ).run()
    snapshots = tuple(p.snapshot for p in ingestion.persisted_snapshots)

    # Haber + olay + teknik + rotasyon (her biri opsiyonel, hata olursa warning)
    news_items: tuple = ()
    if include_news:
        try:
            news_items = NewsProvider().fetch_headlines(max_total=30)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"news_fetch:{type(exc).__name__}")

    catalysts: tuple = ()
    try:
        catalysts = EventCalendarService().fetch_upcoming(horizon_days=120, max_events=20)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"event_calendar:{type(exc).__name__}")

    tech_insights: dict = {}
    try:
        tech_insights = TechnicalProvider().compute()
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"technical:{type(exc).__name__}")

    rotation = None
    try:
        rotation = CapitalRotationProvider().compute()
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"rotation:{type(exc).__name__}")

    # Ana regime raporu
    report = RegimeReportService().generate(
        snapshots,
        news_headlines=news_items,
        upcoming_catalysts=catalysts,
        tech_insights=tech_insights,
    )
    serialized_report = _serialize_report(report)

    # Jeopolitik haberler (ayrı kaynak)
    geo_news_list: list[dict] = []
    try:
        geo_news = GeoNewsProvider().fetch(max_total=30)
        for h in geo_news[:20]:
            geo_news_list.append({
                "title":     getattr(h, "title", ""),
                "region":    getattr(h, "region", ""),
                "sentiment": getattr(h, "sentiment", ""),
            })
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"geo_news:{type(exc).__name__}")

    # Paper trading state (opsiyonel)
    paper_state: dict | None = None
    if include_paper:
        try:
            from app.services.paper_trading_service import get_snapshot as get_paper_snapshot
            snap = get_paper_snapshot()
            paper_state = _to_dict(snap) if snap is not None else None
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"paper_state:{type(exc).__name__}")
            paper_state = None

    # Module health + DQS özeti
    module_health = _build_module_health(
        data_mode=data_mode, snapshot_count=len(snapshots),
        report=report, rotation=rotation,
        news_count=len(report.news_headlines), catalysts=report.upcoming_catalysts,
    )
    data_quality = _data_quality_summary(module_health)

    # Risk gate (canonical): mevcut motorun çıkardığı ana risk sinyallerini özetler
    # block_reason yok (her asset için ayrı) — burada portföy düzeyi gate
    risk_gate_vm = build_risk_gate(
        risk_action="HOLD" if report.decision != "KAPAT" else "RISK_REDUCE",
        dqs_score=data_quality["score"],
        kill_switch=(report.decision == "KAPAT"),
        regime=report.macro_layer.regime,
        contradiction_score=None,
    )

    # Portföy düzeyi agent votes: macro/appetite/decision sinyallerinden özet
    agent_votes_vms = build_agent_votes(
        risk_action=risk_gate_vm.source_risk_action,
        kill_switch=risk_gate_vm.kill_switch_active,
        dqs_score=data_quality["score"],
        tf_alignment_label=None, tf_alignment_detail=None,
        regime=report.macro_layer.regime,
    )

    # Generated_at + snapshot_id
    generated_at = datetime.now(UTC).isoformat()
    snap_id = _snapshot_id(generated_at, data_mode, len(snapshots))

    return CanonicalMarketState(
        snapshot_id=snap_id,
        generated_at=generated_at,
        data_mode=data_mode,
        execution_mode="OFF / NO_EXECUTION",
        regime_report=serialized_report,
        macro_layer=_to_dict(report.macro_layer),
        appetite_layer=_to_dict(report.appetite_layer),
        asset_signals=[_to_dict(s) for s in report.asset_signals],
        confirmation_checklist=[_to_dict(c) for c in report.confirmation_checklist],
        scenarios=[_to_dict(s) for s in report.scenarios],
        asymmetry=_to_dict(report.asymmetry) if report.asymmetry else None,
        technical_state=tech_insights or None,
        capital_rotation=_to_dict(rotation) if rotation else None,
        geo_news=geo_news_list,
        event_calendar=[_to_dict(c) for c in report.upcoming_catalysts],
        risk_gate=risk_gate_vm.to_dict(),
        agent_votes=[v.to_dict() for v in agent_votes_vms],
        position_checks=[],  # her açık pozisyon için ayrı; paper_trading altında
        paper_trading=paper_state,
        data_quality=data_quality,
        module_health=module_health,
        warnings=warnings,
    )


# ── Cache (60 sn — yfinance + regime pipeline yükü) ──────────────────────────

_CACHE_TTL = 60.0
_cached: CanonicalMarketState | None = None
_cached_at: float = 0.0


def get_cached_state(
    *,
    force_refresh: bool = False,
    include_paper: bool = True,
    include_news: bool = True,
) -> tuple[CanonicalMarketState, bool]:
    """Tek snapshot_id ile cache'li canonical state — (state, was_cached) döner."""
    global _cached, _cached_at
    now = time.monotonic()
    if (not force_refresh and _cached is not None
            and (now - _cached_at) < _CACHE_TTL):
        return _cached, True
    state = build_canonical_state(include_paper=include_paper, include_news=include_news)
    _cached = state
    _cached_at = now
    return state, False
