"""
AI Analyst Report API
GET /api/v1/ai-report/current

Groq llama-3.3-70b (primary) → Claude haiku (fallback) ile Katman 1+2+3 +
jeopolitik haber analizi.
Önbellek: 2 saat, stale fallback: 4 saat (pahalı istek + günlük token bütçesi).
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
# Consensus skoru — asset status dağılımından türetilir
# ---------------------------------------------------------------------------

def _derive_consensus_score_from_assets(assets: list[dict]) -> float | None:
    """Asset signal status'larından 0-100 / 50-merkezli consensus skoru üretir.

    `agent_confidence._consensus_strength()` skoru "50'den uzaklık = güç" olarak
    okur (50→0 güç, 0/100→100 güç). Bu yüzden skoru DİREKT yön (CONFIRMED=1.0,
    BLOCKING=0.0) olarak vermek YANLIŞ olur: tek taraflı BLOCKING 0'a gider →
    50'den uzak → confidence YAPAY yükselir. Oysa blocking güçlü ama NEGATİF
    sinyaldir; confidence'ı şişirmemeli.

    Tasarım: yalnızca DESTEKLEYİCİ (confirmable) consensus 50'nin üstüne taşır.
      • CONFIRMED → tam pozitif kanıt
      • PENDING   → zayıf pozitif kanıt
      • NEUTRAL   → nötr (50 civarı)
      • BLOCKING  → karşıt kanıt, skoru 50'ye geri çeker (yukarı taşımaz)
      • VERİ_YOK  → consensus'a dahil edilmez ama veri kapsamını (coverage)
                    düşürür → düşük kapsam = düşük güven.

    Dönüş: 0-100 skor; hiç değerlendirilebilir status yoksa None.
    """
    statuses = [a.get("status") for a in assets if isinstance(a, dict)]
    statuses = [s for s in statuses if s]
    if not statuses:
        return None

    total = len(statuses)
    known = [s for s in statuses if s != "VERİ_YOK"]
    if not known:
        return None  # tamamen veri yok → consensus hesaplanamaz

    n_confirmed = known.count("CONFIRMED")
    n_pending   = known.count("PENDING")
    n_blocking  = known.count("BLOCKING")
    denom = len(known)  # CONFIRMED + PENDING + BLOCKING + NEUTRAL

    pos = n_confirmed * 1.0 + n_pending * 0.4   # destekleyici kanıt
    neg = n_blocking * 1.0                       # karşıt kanıt
    agreement = (pos - neg) / denom              # [-1, +1]
    directional = max(0.0, agreement)            # BLOCKING confidence'ı şişirmesin

    coverage = len(known) / total                # VERİ_YOK oranı arttıkça düşer
    return round(50.0 + 50.0 * directional * coverage, 1)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/current")
def get_ai_report(
    force_refresh: bool = Query(default=False, description="Önbelleği yoksay, yeni rapor üret"),
    persona: str | None = Query(default=None, description="Persona key (analyst|risk_officer|macro_strategist|narrator)"),
    provider: str | None = Query(default=None, description="Manuel sağlayıcı seçimi: auto (varsayılan, Groq→Claude) | groq | claude"),
) -> JSONResponse:
    """
    Piyasa katmanları + jeopolitik haberleri okuyup LLM ile Türkçe analiz üretir.
    Sonuç 2 saat önbellekte tutulur (stale fallback 4 saat).
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

    # NOT: `provider` query param'ı LLM sağlayıcı seçimidir (auto|groq|claude).
    # Market adapter'ı AYRI bir isimle (`market_provider`) tutulur; aksi halde
    # `provider` shadow'lanır ve generate_ai_report'a string yerine adapter objesi
    # gider → manuel sağlayıcı seçimi sessizce "auto"ya düşerdi.
    market_provider = SourceRegistryBoundProviderAdapter(
        base_provider,
        build_provider_source_bindings(source_registry_entries),
    )
    ingestion_result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), market_provider
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
        persona_key=persona,
        provider=provider,
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

    # Asset signal status'larından consensus skoru türet.
    # NOT: AssetSignal'da `score` alanı yok; eski `a.get("score")` hep None
    # döndürdüğü için consensus boyutu ölüydü. _derive_consensus_score_from_assets
    # status dağılımından 0-100 / 50-merkezli (agent_confidence._consensus_strength
    # sözleşmesi) bir skor üretir. BLOCKING confidence'ı şişirmez (aşağı çeker).
    consensus_score_avg = _derive_consensus_score_from_assets(assets_list)

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
                "provider":       provider or "auto",
            },
            output_payload={
                "status":     payload.get("status"),
                "has_report": payload.get("ai_report") is not None,
            },
            snapshot_id=f"ai_report::{generated_at}",
            contract_version=agent_self_validator.DEFAULT_CONTRACT_VERSION,
            # Gerçek kullanılan modeli kaydet (Groq llama / claude-haiku / stale)
            # — sabit "claude-opus-4-7" yanıltıcıydı.
            model=getattr(ai_report, "model", None) or "(unknown)",
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
