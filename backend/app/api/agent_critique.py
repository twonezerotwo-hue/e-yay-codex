"""
GET /api/v1/agent/insight/critiqued
  → Mevcut agent.insight cevabını alır, multi-agent critic katmanından geçirir,
    bull/bear/risk perspektifleriyle birlikte döner.

POST /api/v1/agent/critique
  → Caller'ın verdiği consensus + regime evidence'a critique uygular.
    Frontend zaten elinde olan veriyi göndermek istediğinde kullanır.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.agent_insight import get_agent_insight
from app.services import agent_audit_log, multi_agent_critique
from app.services.agent_output_guard import guard_response

router = APIRouter(prefix="/agent", tags=["agent-critique"])


def _is_weekend(now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    return now.weekday() in (5, 6)


def _gather_evidence_for_critique() -> dict[str, Any]:
    """Critique için yan kanıtları topla — best-effort, hata sessiz."""
    evidence: dict[str, Any] = {}

    # Chart patterns
    try:
        from app.api.chart_patterns import list_chart_patterns
        cp = list_chart_patterns()
        evidence["chart_patterns"] = (cp or {}).get("pairs") or {}
    except Exception:
        evidence["chart_patterns"] = {}

    # Market clock
    evidence["market_clock"] = {
        "weekend": _is_weekend(),
        "now_utc": datetime.now(UTC).isoformat(),
    }

    return evidence


def _consensus_from_insights(agent_response: dict) -> dict[str, Any]:
    """agent.insight çıktısından consensus özetini çıkar."""
    insights = agent_response.get("insights") or []
    scores: list[float] = []
    for ins in insights:
        if isinstance(ins, dict):
            s = ins.get("score")
            if isinstance(s, (int, float)):
                scores.append(float(s))
    if not scores:
        return {"final_score": None, "final_direction": None}
    avg = sum(scores) / len(scores)
    direction = "bullish" if avg > 55 else ("bearish" if avg < 45 else "neutral")
    return {"final_score": avg, "final_direction": direction, "module_count": len(scores)}


@router.get("/insight/critiqued")
def get_insight_critiqued() -> dict:
    """Mevcut /agent/insight cevabını + critique katmanını birlikte döndür."""
    start_t = time.monotonic()

    try:
        agent_response = get_agent_insight()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"agent.insight unavailable: {exc!s:.180}") from exc

    # ABSTAIN durumunda critique gereksiz — sadece orijinali döndür
    if agent_response.get("status") == "abstain":
        result = {
            "status":            "abstain",
            "original":          agent_response,
            "critique":          None,
            "execution_mode":    "OFF / NO_EXECUTION",
            "abstention_reason": agent_response.get("abstention_reason"),
        }
        return guard_response(result, source="agent.insight.critiqued")

    evidence = _gather_evidence_for_critique()
    consensus_summary = _consensus_from_insights(agent_response)

    critique_result = multi_agent_critique.critique(
        agent_response=agent_response,
        consensus=consensus_summary,
        regime={"regime": (agent_response.get("decision") or "").upper()},
        news=None,  # /agent/insight news'i dışarı vermiyor; kontekst zaten kullandı
        chart_patterns=evidence["chart_patterns"],
        data_quality=None,
        validation=agent_response.get("validation"),
        market_clock=evidence["market_clock"],
    )

    result = {
        "status":         "ok",
        "execution_mode": "OFF / NO_EXECUTION",
        "generated_at":   datetime.now(UTC).isoformat(),
        "original":       agent_response,
        "critique":       critique_result.to_dict(),
        "synthesis":      critique_result.synthesis,
        "agreement_with_original": critique_result.agreement_with_original,
        "revised_confidence_pct":  critique_result.revised_confidence_pct,
    }
    result = guard_response(result, source="agent.insight.critiqued")

    # Audit
    try:
        agent_audit_log.record(
            endpoint="agent.insight.critiqued",
            input_payload={"insights_count": len(agent_response.get("insights", []))},
            output_payload={
                "synthesis":   critique_result.synthesis,
                "agreement":   critique_result.agreement_with_original,
                "challenges":  len(critique_result.challenges),
            },
            snapshot_id=agent_response.get("generated_at"),
            contract_version="critique.1.0",
            model="rule-based-critic",
            tool_calls=["agent.insight", "chart_patterns.list"],
            confidence={
                "original_pct": (agent_response.get("confidence") or {}).get("confidence_pct"),
                "revised_pct":  critique_result.revised_confidence_pct,
                "synthesis":    critique_result.synthesis,
            },
            duration_ms=(time.monotonic() - start_t) * 1000.0,
        )
    except Exception:
        pass

    return result


class CritiqueRequest(BaseModel):
    consensus: dict | None = None
    regime: dict | None = None
    chart_patterns: dict | None = None
    data_quality: dict | None = None
    validation: dict | None = None
    agent_response: dict | None = None


@router.post("/critique")
def critique_payload(body: CritiqueRequest) -> dict:
    """Caller'ın verdiği kanıt + agent_response'a critique uygula.

    Frontend elinde olan veriyi göndermek isterse — pipeline tetiklemez.
    """
    start_t = time.monotonic()
    result = multi_agent_critique.critique(
        agent_response=body.agent_response,
        consensus=body.consensus,
        regime=body.regime,
        chart_patterns=body.chart_patterns,
        data_quality=body.data_quality,
        validation=body.validation,
        market_clock={"weekend": _is_weekend(), "now_utc": datetime.now(UTC).isoformat()},
    )

    out = {
        "status":         "ok",
        "execution_mode": "OFF / NO_EXECUTION",
        "generated_at":   datetime.now(UTC).isoformat(),
        "critique":       result.to_dict(),
    }
    out = guard_response(out, source="agent.critique.post")

    try:
        agent_audit_log.record(
            endpoint="agent.critique",
            input_payload={
                "has_consensus":      body.consensus is not None,
                "has_regime":         body.regime is not None,
                "has_chart_patterns": body.chart_patterns is not None,
            },
            output_payload={
                "synthesis": result.synthesis,
                "agreement": result.agreement_with_original,
            },
            model="rule-based-critic",
            duration_ms=(time.monotonic() - start_t) * 1000.0,
        )
    except Exception:
        pass

    return out


__all__ = ["router"]
