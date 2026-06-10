"""Learning + Owner Feedback API.

POST /api/v1/learning/owner-feedback         — owner müdahalesini kaydet
GET  /api/v1/learning/owner-feedback/recent  — son müdahaleler
GET  /api/v1/learning/daily-report           — bugünkü özet
POST /api/v1/learning/rebalance/propose      — proposal üret (otomatik aktivasyon YOK)
POST /api/v1/learning/rebalance/approve      — owner onayı + versionlu yaz
GET  /api/v1/learning/rebalance/proposals    — son proposal'lar
GET  /api/v1/learning/active-weights         — aktif weights

PAPER_SAFE / NO_EXECUTION — risk kuralları değişmez.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.owner_feedback_service import (
    VALID_ACTIONS,
    approve_proposal,
    build_daily_report,
    get_active_weights,
    get_recent_feedback,
    get_recent_proposals,
    propose_rebalance,
    record_owner_feedback,
)

router = APIRouter(prefix="/learning", tags=["learning"])


# ── Request schemas ─────────────────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    action:        str = Field(..., description=f"One of {VALID_ACTIONS}")
    reason:        str = Field(..., min_length=1, max_length=2000)
    trade_id:      str | None = None
    snapshot_id:   str | None = None
    asset_code:    str | None = None
    later_outcome: str | None = None
    lesson:        str | None = None


class RebalanceProposeRequest(BaseModel):
    based_on_period:        str = "daily"
    agent_weight_changes:   dict[str, float] = Field(default_factory=dict)
    feature_weight_changes: dict[str, float] = Field(default_factory=dict)
    threshold_suggestions:  dict[str, float] = Field(default_factory=dict)
    reasons:                list[str] = Field(default_factory=list)
    risk_notes:             list[str] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    proposal_id: str = Field(..., min_length=3)


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/owner-feedback")
def post_owner_feedback(body: FeedbackRequest) -> dict:
    try:
        fb = record_owner_feedback(
            action=body.action, reason=body.reason,
            trade_id=body.trade_id, snapshot_id=body.snapshot_id,
            asset_code=body.asset_code,
            later_outcome=body.later_outcome, lesson=body.lesson,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "feedback": fb.to_dict(), "paper_safe": True}


@router.get("/owner-feedback/recent")
def get_owner_feedback_recent(limit: int = 20) -> dict:
    return {
        "status":     "ok",
        "items":      get_recent_feedback(limit=max(1, min(limit, 200))),
        "paper_safe": True,
    }


@router.get("/daily-report")
def get_daily_report() -> dict:
    return {"status": "ok", "report": build_daily_report(), "paper_safe": True}


@router.post("/rebalance/propose")
def post_rebalance_propose(body: RebalanceProposeRequest) -> dict:
    proposal = propose_rebalance(
        based_on_period=body.based_on_period,
        agent_weight_changes=body.agent_weight_changes,
        feature_weight_changes=body.feature_weight_changes,
        threshold_suggestions=body.threshold_suggestions,
        reasons=body.reasons,
        risk_notes=body.risk_notes,
    )
    return {
        "status":     "proposed",
        "proposal":   proposal.to_dict(),
        "paper_safe": True,
        "execution_side_effects": "NO_EXECUTION",
        "note":       "Owner approval gereklidir; otomatik aktivasyon YOK.",
    }


@router.post("/rebalance/approve")
def post_rebalance_approve(body: ApproveRequest) -> dict:
    try:
        result = approve_proposal(body.proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok", "result": result, "paper_safe": True}


@router.get("/rebalance/proposals")
def get_proposals_recent(limit: int = 20) -> dict:
    return {
        "status":     "ok",
        "proposals":  get_recent_proposals(limit=max(1, min(limit, 200))),
        "paper_safe": True,
    }


@router.get("/active-weights")
def get_active_weights_endpoint() -> dict:
    return {"status": "ok", "weights": get_active_weights(), "paper_safe": True}


__all__ = ["router"]
