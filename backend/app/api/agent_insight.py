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
from app.services import (
    agent_audit_log,
    agent_confidence,
    agent_self_validator,
    core_snapshot_cache,
)
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

    generated_at = datetime.now(UTC).isoformat()

    # ── Core snapshot contract (Item 3) ──────────────────────────────────
    # Pipeline çıktısını dondur; agent/critic/audit aynı snapshot'a referans verir.
    # Eval anchor: karar anı fiyatları snapshot'a koy → ileride
    # agent_eval_service realized delta'yı hesaplayabilsin.
    anchor_prices: dict[str, float] = {}
    for s in snapshots:
        try:
            sym = getattr(s, "asset_symbol", None) or getattr(s, "symbol", None)
            val = getattr(s, "value", None) or getattr(s, "price", None)
            if sym and val is not None:
                anchor_prices[str(sym)] = float(val)
        except Exception:
            continue

    evidence_payload: dict = {
        "snapshots":  [getattr(s, "asset_symbol", None) for s in snapshots],
        "prices":     anchor_prices,
        "news_count": len(news),
        "tech_keys":  sorted(list(tech_insights.keys())) if isinstance(tech_insights, dict) else [],
        "decision":   getattr(report, "decision", None),
        "macro": {
            "regime":         getattr(getattr(report, "macro_layer", None), "regime", None),
            "confidence_pct": getattr(getattr(report, "macro_layer", None), "confidence_pct", None),
        },
        "rotation_primary": (getattr(rotation, "primary_flow", None) if rotation else None),
        "generated_at":     generated_at,
    }
    snapshot_id, snapshot_entry = core_snapshot_cache.create_snapshot(
        evidence_payload, source="agent.insight", ttl_seconds=90,
    )

    # ── Self-validation (Item 4) ─────────────────────────────────────────
    macro = getattr(report, "macro_layer", None)
    dq_pct: float | None = float(getattr(macro, "confidence_pct", 0)) if macro else None
    consensus_status = "OK" if insights else "INSUFFICIENT_DATA"
    validation = agent_self_validator.validate(
        snapshot_at=generated_at,
        required_fields={
            "snapshots":     snapshots,
            "tech_insights": tech_insights,
            "insights":      insights,
        },
        data_quality_score=dq_pct,
        consensus_status=consensus_status,
        max_snapshot_age_s=900,  # /insight 60s cache + biraz tolerans
    )

    # ── Confidence + abstention (Item 15) ─────────────────────────────────
    consensus_score_avg: float | None = None
    if insights:
        try:
            scores = [getattr(i, "score", None) for i in insights]
            scores = [float(s) for s in scores if s is not None]
            if scores:
                consensus_score_avg = sum(scores) / len(scores)
        except Exception:
            consensus_score_avg = None

    confidence = agent_confidence.compute(
        data_quality_score=dq_pct,
        consensus_score=consensus_score_avg,
        consensus_status=consensus_status,
        module_count=len(insights) if insights else 0,
        snapshot_age_seconds=validation.snapshot_age_seconds,
        expected_module_count=4,
    )

    # ABSTAIN durumunda response'u sadeleştir — agent görüş bildirmez
    if confidence.abstain or not validation.is_valid:
        response = {
            "status":         "abstain",
            "execution_mode": "OFF / NO_EXECUTION",
            "generated_at":   generated_at,
            "snapshot_id":    snapshot_id,
            "contract_version": snapshot_entry["contract_version"],
            "abstention_reason": (
                confidence.abstention_reason
                or "; ".join(validation.reasons)
                or "insufficient_evidence"
            ),
            "validation":  validation.to_dict(),
            "confidence":  confidence.to_dict(),
            "insights":    [],
            "decision":    None,
        }
    else:
        response = {
            "status": "ok",
            "execution_mode": "OFF / NO_EXECUTION",
            "generated_at": generated_at,
            "snapshot_id":  snapshot_id,
            "contract_version": snapshot_entry["contract_version"],
            "decision":   report.decision,
            # Karar hangi TF'lerde okunmuş bir kanıt setiyle alındı?
            "decision_timeframe": {
                "primary":     "1D",
                "secondary":   ["4H (in-day swing)", "1H (kısa ufuk teyit)"],
                "indicators":  ["ATR(14)", "swing high/low", "RSI(14)", "EMA(20)"],
                "explanation": (
                    "Karar deterministik regime motorundan; teknik kanıtlar 1D mumlardan, "
                    "agent isterse 1H/4H'i `read_chart` aracıyla ek olarak okur."
                ),
            },
            "insights":   [dataclasses.asdict(i) for i in insights],
            "validation": validation.to_dict(),
            "confidence": confidence.to_dict(),
        }
    response = guard_response(response, source="agent.insight")

    # ── Memory write (Sprint 7) ──────────────────────────────────────────
    try:
        from app.services import agent_memory_service
        if response.get("status") == "ok":
            agent_memory_service.remember(
                category="decision",
                text=f"{response.get('decision') or '?'} · {len(response.get('insights', []))} insight",
                regime=getattr(getattr(report, "macro_layer", None), "regime", None),
                snapshot_id=snapshot_id,
                confidence_pct=confidence.confidence_pct if hasattr(confidence, "confidence_pct") else None,
                tags=["agent.insight"],
            )
    except Exception:
        pass

    # ── Audit trail (Item 12) ────────────────────────────────────────────
    try:
        agent_audit_log.record(
            endpoint="agent.insight",
            input_payload={
                "snapshots_count": len(snapshots),
                "news_count":      len(news),
                "tech_count":      len(tech_insights) if isinstance(tech_insights, (list, dict)) else 0,
            },
            output_payload={
                "status":    response.get("status"),
                "insights":  len(response.get("insights", [])),
                "decision":  response.get("decision"),
            },
            snapshot_id=snapshot_id,
            contract_version=snapshot_entry["contract_version"],
            model="rule-based",
            validation=validation.to_dict(),
            confidence=confidence.to_dict(),
            duration_ms=(time.monotonic() - now) * 1000.0,
        )
    except Exception:
        pass

    _INSIGHT_RESPONSE_CACHE = (now, response)
    return response


__all__ = [name for name in globals() if not name.startswith("_")]
