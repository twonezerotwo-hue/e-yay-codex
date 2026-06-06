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

from app.services import agent_audit_log, agent_confidence, agent_self_validator, job_runner
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

    # ── Self-validation + confidence + audit ─────────────────────────────
    from datetime import UTC, datetime as _dt
    start_t = _time.monotonic()
    generated_at = _dt.now(UTC).isoformat()

    dq_pct: float | None = float(report.macro_layer.confidence_pct) if report.macro_layer else None
    consensus_status = "OK" if assets_list else "INSUFFICIENT_DATA"

    validation = agent_self_validator.validate(
        snapshot_at=generated_at,
        required_fields={
            "snapshots": snapshots,
            "assets":    assets_list,
            "macro":     macro_dict,
        },
        data_quality_score=dq_pct,
        consensus_status=consensus_status,
        max_snapshot_age_s=1200,
    )

    # Asset signal'lardan ortalama skor → consensus_score temsilcisi
    consensus_score_avg: float | None = None
    try:
        vals = [a.get("score") for a in assets_list if isinstance(a, dict)]
        vals = [float(v) for v in vals if v is not None]
        if vals:
            consensus_score_avg = sum(vals) / len(vals)
    except Exception:
        consensus_score_avg = None

    confidence = agent_confidence.compute(
        data_quality_score=dq_pct,
        consensus_score=consensus_score_avg,
        consensus_status=consensus_status,
        module_count=len(assets_list),
        snapshot_age_seconds=validation.snapshot_age_seconds,
        expected_module_count=8,
    )

    if confidence.abstain or not validation.is_valid:
        payload = guard_response({
            "status": "abstain",
            "data_mode": data_mode,
            "execution_mode": "OFF / NO_EXECUTION",
            "abstention_reason": (
                confidence.abstention_reason
                or "; ".join(validation.reasons)
                or "insufficient_evidence"
            ),
            "validation": validation.to_dict(),
            "confidence": confidence.to_dict(),
            "ai_report":  None,
        }, source="ai_report.current")
    else:
        payload = guard_response({
            "status": "ok",
            "data_mode": data_mode,
            "execution_mode": "OFF / NO_EXECUTION",
            "ai_report": _to_dict(ai_report),
            "geo_news_count": len(geo_news),
            "capital_rotation": _to_dict(rotation) if rotation else None,
            "validation": validation.to_dict(),
            "confidence": confidence.to_dict(),
        }, source="ai_report.current")

    # Audit trail
    try:
        agent_audit_log.record(
            endpoint="ai_report.current",
            input_payload={
                "data_mode":      data_mode,
                "assets":         len(assets_list),
                "geo_news":       len(geo_news),
                "force_refresh":  force_refresh,
            },
            output_payload={
                "status":     payload.get("status"),
                "has_report": payload.get("ai_report") is not None,
            },
            snapshot_id=f"ai_report::{generated_at}",
            contract_version=agent_self_validator.DEFAULT_CONTRACT_VERSION,
            model="claude-opus-4-7",
            validation=validation.to_dict(),
            confidence=confidence.to_dict(),
            duration_ms=(_time.monotonic() - start_t) * 1000.0,
        )
    except Exception:
        pass

    return JSONResponse(content=payload)


# ---------------------------------------------------------------------------
# Async job pattern — LLM çağrısını request'ten çıkarır
# ---------------------------------------------------------------------------

def _run_ai_report_job(force_refresh: bool) -> dict:
    """Job worker — get_ai_report'u sync çağırır, JSONResponse'tan dict çıkarır."""
    resp = get_ai_report(force_refresh=force_refresh)
    # JSONResponse içeriği — body'den dict üret
    try:
        import json as _json
        return _json.loads(bytes(resp.body).decode("utf-8"))
    except Exception:
        return {"status": "error", "error": "job_decode_failed"}


@router.post("/jobs")
def submit_ai_report_job(
    force_refresh: bool = Query(default=False, description="Önbelleği yoksay"),
) -> dict:
    """Async job submit — anında job_id döner, frontend polling yapar."""
    job_id = job_runner.submit(
        _run_ai_report_job,
        force_refresh,
        label="ai-report.current",
    )
    return {
        "status": "submitted",
        "job_id": job_id,
        "poll":   f"/api/v1/ai-report/jobs/{job_id}",
        "execution_mode": "OFF / NO_EXECUTION",
    }


@router.get("/jobs/{job_id}")
def get_ai_report_job(job_id: str) -> dict:
    """Job durumunu sorgula. status: pending|running|ready|failed."""
    s = job_runner.get_status(job_id)
    if s is None:
        return {"status": "not_found", "job_id": job_id}
    if s["status"] == "ready":
        s["result"] = job_runner.get_result(job_id)
    return s


@router.get("/jobs")
def list_ai_report_jobs(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    items = [it for it in job_runner.list_recent(limit) if it.get("label") == "ai-report.current"]
    return {"status": "ok", "count": len(items), "items": items}


__all__ = [name for name in globals() if not name.startswith("_")]
