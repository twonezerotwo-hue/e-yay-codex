"""
POST /api/v1/agent/ensemble/run     — multi-persona ensemble çalıştır (async job önerilir)
POST /api/v1/agent/ensemble/jobs    — job submit (uzun süren için)
GET  /api/v1/agent/ensemble/jobs/{id}

Sprint 10 / Item 10. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import sys
import time as _time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import agent_audit_log, agent_ensemble_service, job_runner
from app.services.agent_output_guard import guard_response

REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_repo_root_on_path() -> None:
    s = str(REPO_ROOT)
    if s not in sys.path:
        sys.path.insert(0, s)


router = APIRouter(prefix="/agent/ensemble", tags=["agent-ensemble"])


def _build_ensemble_inputs() -> dict:
    """Pipeline'ı koş, ensemble'a verilecek dict'leri üret. ai_report ile aynı pattern."""
    _ensure_repo_root_on_path()
    import dataclasses

    from registry import build_source_registry_entries, load_source_registry

    from app.api.ai_report import _get_provider
    from app.providers import (
        SourceRegistryBoundProviderAdapter,
        build_provider_source_bindings,
    )
    from app.providers.capital_rotation_provider import CapitalRotationProvider
    from app.providers.geo_news_provider import GeoNewsProvider
    from app.services import MarketSnapshotService, ProviderIngestionService
    from app.services.regime_report_service import RegimeReportService
    from app.providers.real_market_provider import RealMarketProvider

    source_registry = load_source_registry()
    entries = build_source_registry_entries(source_registry)

    base = _get_provider()
    data_mode = "live" if isinstance(base, RealMarketProvider) else "simulation"

    class _FakeSession:
        def add(self, _): pass
        def commit(self): pass
        def rollback(self): pass

    provider = SourceRegistryBoundProviderAdapter(
        base, build_provider_source_bindings(entries),
    )
    ingestion = ProviderIngestionService(MarketSnapshotService(_FakeSession()), provider).run()
    snapshots = tuple(p.snapshot for p in ingestion.persisted_snapshots)
    report = RegimeReportService().generate(snapshots, news_headlines=())

    geo_news = ()
    try:
        geo_news = GeoNewsProvider().fetch(max_total=20)
    except Exception:
        pass

    rotation = None
    try:
        rotation = CapitalRotationProvider().compute()
    except Exception:
        pass

    return {
        "macro":     dataclasses.asdict(report.macro_layer),
        "appetite":  dataclasses.asdict(report.appetite_layer),
        "assets":    [dataclasses.asdict(s) for s in report.asset_signals],
        "checklist": [dataclasses.asdict(c) for c in report.confirmation_checklist],
        "decision":  report.decision,
        "verdict":   report.verdict,
        "geo_news":  geo_news,
        "rotation":  rotation,
        "data_mode": data_mode,
    }


def _run_ensemble_pipeline(personas_csv: str | None) -> dict:
    """Job worker — full pipeline + ensemble + audit + guard."""
    start_t = _time.monotonic()
    try:
        inputs = _build_ensemble_inputs()
    except Exception as exc:
        return {"status": "error", "error": f"pipeline_failed: {exc!s:.220}"}

    personas: list[str] | None = None
    if personas_csv:
        personas = [p.strip() for p in personas_csv.split(",") if p.strip()]

    report = agent_ensemble_service.run_ensemble(
        macro=inputs["macro"],
        appetite=inputs["appetite"],
        assets=inputs["assets"],
        checklist=inputs["checklist"],
        decision=inputs["decision"],
        verdict=inputs["verdict"],
        geo_news=inputs["geo_news"],
        rotation=inputs["rotation"],
        personas=personas,
    )

    payload = guard_response({
        "status":         "ok",
        "execution_mode": "OFF / NO_EXECUTION",
        "data_mode":      inputs["data_mode"],
        "generated_at":   datetime.now(UTC).isoformat(),
        "ensemble":       agent_ensemble_service.report_to_dict(report),
    }, source="agent.ensemble.run")

    try:
        agent_audit_log.record(
            endpoint="agent.ensemble",
            input_payload={
                "personas":   personas or ["analyst","risk_officer","macro_strategist"],
                "data_mode":  inputs["data_mode"],
                "assets":     len(inputs["assets"]),
            },
            output_payload={
                "status":          payload.get("status"),
                "final_label":     report.final_label,
                "agreement_pct":   report.agreement_pct,
                "decision":        report.final_label,
            },
            model="ensemble",
            tool_calls=[f"ai_report.{p}" for p in (personas or ["analyst","risk_officer","macro_strategist"])],
            duration_ms=(_time.monotonic() - start_t) * 1000.0,
        )
    except Exception:
        pass

    return payload


@router.post("/run")
def run_ensemble(
    personas: str | None = Query(default=None, description="CSV: analyst,risk_officer,..."),
) -> dict:
    """Sync ensemble run — küçük testler için. Üretimde /jobs tercih edin."""
    return _run_ensemble_pipeline(personas)


class EnsembleJobRequest(BaseModel):
    personas: str | None = None


@router.post("/jobs")
def submit_ensemble_job(body: EnsembleJobRequest | None = None) -> dict:
    personas_csv = (body.personas if body else None)
    job_id = job_runner.submit(
        _run_ensemble_pipeline,
        personas_csv,
        label="agent.ensemble",
    )
    return {
        "status":         "submitted",
        "job_id":         job_id,
        "poll":           f"/api/v1/agent/ensemble/jobs/{job_id}",
        "execution_mode": "OFF / NO_EXECUTION",
    }


@router.get("/jobs/{job_id}")
def get_ensemble_job(job_id: str) -> dict:
    s = job_runner.get_status(job_id)
    if s is None:
        return {"status": "not_found", "job_id": job_id}
    if s["status"] == "ready":
        s["result"] = job_runner.get_result(job_id)
    return s


@router.get("/jobs")
def list_ensemble_jobs(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    items = [it for it in job_runner.list_recent(limit) if it.get("label") == "agent.ensemble"]
    return {"status": "ok", "count": len(items), "items": items}


__all__ = ["router"]
