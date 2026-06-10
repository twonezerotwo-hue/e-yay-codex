"""Owner feedback ve rebalance proposal — JSON-based MVP.

Sen grafik başındasın; sistemin hatalarını engelliyorsun. Bu modül senin
müdahalelerini standart formatta JSONL'e yazar ve learning rebalance için
hammadde oluşturur.

KRİTİK: Bu modül weights/threshold'ları OTOMATİK değiştirmez. Sadece
RebalanceProposal üretir; owner approve etmedikçe weights dosyası
güncellenmez. Mevcut risk kuralları olduğu gibi kalır.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Storage paths ────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "learning"
_FEEDBACK_FILE   = _DATA_DIR / "owner_feedback.jsonl"
_PROPOSALS_FILE  = _DATA_DIR / "rebalance_proposals.jsonl"
_WEIGHTS_FILE    = _DATA_DIR / "weights_active.json"

VALID_ACTIONS = (
    "APPROVE", "REJECT", "FORCE_WATCH", "REDUCE",
    "INCREASE_AGGRESSION", "MARK_SIGNAL_WRONG",
)


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class OwnerFeedback:
    feedback_id:   str
    created_at:    str
    trade_id:      str | None
    snapshot_id:   str | None
    asset_code:    str | None
    action:        str
    reason:        str
    later_outcome: str | None = None
    lesson:        str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RebalanceProposal:
    proposal_id:                str
    generated_at:               str
    based_on_period:            str
    agent_weight_changes:       dict[str, float] = field(default_factory=dict)
    feature_weight_changes:     dict[str, float] = field(default_factory=dict)
    threshold_suggestions:      dict[str, float] = field(default_factory=dict)
    reasons:                    list[str]        = field(default_factory=list)
    risk_notes:                 list[str]        = field(default_factory=list)
    requires_owner_approval:    bool             = True
    approved:                   bool             = False
    approved_at:                str | None       = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _gen_id(prefix: str) -> str:
    raw = f"{prefix}|{time.time_ns()}"
    return f"{prefix}_{hashlib.sha1(raw.encode()).hexdigest()[:10]}"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit is not None:
        return out[-limit:]
    return out


# ── Public API ───────────────────────────────────────────────────────────────


def record_owner_feedback(
    *,
    action: str,
    reason: str,
    trade_id: str | None = None,
    snapshot_id: str | None = None,
    asset_code: str | None = None,
    later_outcome: str | None = None,
    lesson: str | None = None,
) -> OwnerFeedback:
    """Owner müdahalesini kaydet."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"invalid action: {action} (valid: {VALID_ACTIONS})")
    fb = OwnerFeedback(
        feedback_id=_gen_id("fb"),
        created_at=datetime.now(UTC).isoformat(),
        trade_id=trade_id, snapshot_id=snapshot_id, asset_code=asset_code,
        action=action, reason=reason,
        later_outcome=later_outcome, lesson=lesson,
    )
    _append_jsonl(_FEEDBACK_FILE, fb.to_dict())
    return fb


def get_recent_feedback(limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl(_FEEDBACK_FILE, limit=limit)


def propose_rebalance(
    *,
    based_on_period: str = "daily",
    agent_weight_changes: dict[str, float] | None = None,
    feature_weight_changes: dict[str, float] | None = None,
    threshold_suggestions: dict[str, float] | None = None,
    reasons: list[str] | None = None,
    risk_notes: list[str] | None = None,
) -> RebalanceProposal:
    """Rebalance proposal üret — owner approve etmedikçe aktive olmaz."""
    proposal = RebalanceProposal(
        proposal_id=_gen_id("rp"),
        generated_at=datetime.now(UTC).isoformat(),
        based_on_period=based_on_period,
        agent_weight_changes=dict(agent_weight_changes or {}),
        feature_weight_changes=dict(feature_weight_changes or {}),
        threshold_suggestions=dict(threshold_suggestions or {}),
        reasons=list(reasons or []),
        risk_notes=list(risk_notes or []),
        requires_owner_approval=True,
        approved=False,
    )
    _append_jsonl(_PROPOSALS_FILE, proposal.to_dict())
    return proposal


def get_recent_proposals(limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl(_PROPOSALS_FILE, limit=limit)


def approve_proposal(proposal_id: str) -> dict[str, Any]:
    """Bir proposal'ı owner approval ile aktif weights'a yaz.

    Mevcut weights'a UYGULAR (versiyonlu); risk kurallarını DEĞİŞTİRMEZ.
    Sadece agent/feature weight + threshold önerilerini sabitler. Eski
    weights JSON arşivlenir (yeni dosyada `previous_id` referansı kalır).
    """
    _ensure_dir()
    items = _read_jsonl(_PROPOSALS_FILE)
    matching = [p for p in items if p.get("proposal_id") == proposal_id]
    if not matching:
        raise KeyError(f"proposal not found: {proposal_id}")
    # En son satır approval event ise zaten onaylanmıştır
    if any(p.get("approved") or p.get("_event") == "approval" for p in matching):
        return {"status": "already_approved", "proposal_id": proposal_id}
    target = matching[0]

    # Mevcut weights'i oku (yoksa boş başla)
    current = {}
    if _WEIGHTS_FILE.exists():
        try:
            current = json.loads(_WEIGHTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}

    prev_id = current.get("active_proposal_id")
    new_weights = {
        "active_proposal_id":    proposal_id,
        "previous_id":           prev_id,
        "approved_at":           datetime.now(UTC).isoformat(),
        "agent_weights":         {
            **(current.get("agent_weights")    or {}),
            **(target.get("agent_weight_changes")    or {}),
        },
        "feature_weights":       {
            **(current.get("feature_weights")  or {}),
            **(target.get("feature_weight_changes")  or {}),
        },
        "threshold_suggestions": {
            **(current.get("threshold_suggestions") or {}),
            **(target.get("threshold_suggestions")  or {}),
        },
    }

    # Versiyonlu kopyaya yedek + yeni aktif yaz
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = _DATA_DIR / f"weights_v_{ts}_{proposal_id}.json"
    archive.write_text(json.dumps(new_weights, ensure_ascii=False, indent=2), encoding="utf-8")
    _WEIGHTS_FILE.write_text(json.dumps(new_weights, ensure_ascii=False, indent=2), encoding="utf-8")

    # Proposal'ı approved işaretle (yeni satır)
    target["approved"]    = True
    target["approved_at"] = datetime.now(UTC).isoformat()
    _append_jsonl(_PROPOSALS_FILE, {"_event": "approval", **target})

    return {
        "status":           "approved",
        "proposal_id":      proposal_id,
        "previous_id":      prev_id,
        "weights_file":     str(_WEIGHTS_FILE),
        "archive":          str(archive),
    }


def get_active_weights() -> dict[str, Any] | None:
    if not _WEIGHTS_FILE.exists():
        return None
    try:
        return json.loads(_WEIGHTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ── Daily report ─────────────────────────────────────────────────────────────


def build_daily_report() -> dict[str, Any]:
    """Bugünkü owner feedback + son proposal'lardan kısa rapor üret."""
    feedbacks = get_recent_feedback(limit=100)
    proposals = get_recent_proposals(limit=10)
    today = datetime.now(UTC).date().isoformat()
    today_feedbacks = [f for f in feedbacks if (f.get("created_at") or "").startswith(today)]
    action_counts: dict[str, int] = {}
    for f in today_feedbacks:
        action_counts[f["action"]] = action_counts.get(f["action"], 0) + 1
    return {
        "date":                 today,
        "total_feedback_today": len(today_feedbacks),
        "action_counts":        action_counts,
        "pending_proposals":    [p for p in proposals if not p.get("approved")],
        "active_weights":       get_active_weights(),
    }
