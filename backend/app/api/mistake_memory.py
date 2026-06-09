"""
FAZ 5B — Mistake Memory (Final) API.

Endpoints:
  POST /mistake-memory/finalize   → Kapanmış trade'ler için final memory üretir.
  GET  /mistake-memory/recent     → Son N memory'yi döndürür (read-only).

Güvenlik:
  PAPER_SAFE guard aktif.
  Paper trading state'ini mutate ETMEZ.
  is_final = True — pozisyon kapanmadan kesin öğrenme yazılmaz.
  Duplicate önleme: aynı trade tekrar finalize edilmez.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.execution_boundary import require_paper_safe
from app.services import paper_trading_service as pts
from app.services.mistake_memory_service import (
    build_mistake_memory,
    _trade_fingerprint,
)
from app.storage.learning_candidate_store import load_recent_learning_candidates
from app.storage.mistake_memory_store import (
    load_finalized_fingerprints,
    load_recent_mistake_memory,
    save_mistake_memory,
)
from app.storage.position_recheck_store import load_recent_position_rechecks

router = APIRouter(prefix="/mistake-memory", tags=["mistake-memory"])

# ── Yardımcı: eşleştirme ─────────────────────────────────────────────────────

def _match_candidates(trade: dict, candidates: list[dict]) -> list[dict]:
    """Pair + entry_price yakınlığı (veya position_id) ile candidate eşleştirir."""
    pair     = str(trade.get("pair") or "")
    entry    = float(trade.get("entry_price") or 0)
    trade_id = trade.get("trade_id") or trade.get("id")

    matched: list[dict] = []
    for c in candidates:
        if c.get("pair") != pair:
            continue
        # position_id / trade_id eşleşmesi
        if trade_id and c.get("position_id") == str(trade_id):
            matched.append(c)
            continue
        # entry_price yakınlığı (±0.5%)
        c_entry = float(c.get("entry_price") or 0)
        if entry > 0 and c_entry > 0:
            pct_diff = abs(entry - c_entry) / entry * 100
            if pct_diff < 0.5:
                matched.append(c)
    return matched


def _match_rechecks(trade: dict, rechecks: list[dict]) -> list[dict]:
    """Pair ile recheck eşleştirir (entry_price da biliniyorsa filtreler)."""
    pair  = str(trade.get("pair") or "")
    entry = float(trade.get("entry_price") or 0)

    matched: list[dict] = []
    for r in rechecks:
        if r.get("pair") != pair:
            continue
        r_entry = float(r.get("entry_price") or 0)
        if entry > 0 and r_entry > 0:
            pct_diff = abs(entry - r_entry) / entry * 100
            if pct_diff < 0.5:
                matched.append(r)
        else:
            # entry bilinmiyorsa sadece pair eşleşmesi yeterli
            matched.append(r)
    return matched


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/finalize", dependencies=[Depends(require_paper_safe)])
def finalize_mistake_memory() -> dict:
    """
    Daha önce finalize edilmemiş kapanmış trade'ler için final memory üretir.

    • Paper trading state'ini değiştirmez.
    • Karar motorunu etkilemez.
    • Duplicate: aynı trade_fingerprint için tekrar kayıt açılmaz.
    """
    snap_state    = pts.get_snapshot()
    closed_trades = (
        snap_state.get("closed_trades")
        or snap_state.get("trade_history")
        or snap_state.get("trades")   # paper_trading_service → state["trades"]
        or []
    )

    if not closed_trades:
        return {
            "status":              "not_created",
            "reason":              "no_closed_trades",
            "decision_permission": "NO_EXECUTION",
            "execution_mode":      "PAPER_SAFE",
        }

    # Daha önce finalize edilmiş fingerprint'ler
    finalized_fps = load_finalized_fingerprints()

    # Gerçek veri kaynakları
    all_candidates = load_recent_learning_candidates(limit=500)
    all_rechecks   = load_recent_position_rechecks(limit=500)

    memory_ids:  list[str]  = []
    results:     list[dict] = []
    skipped:     int        = 0

    for trade in closed_trades:
        fp = _trade_fingerprint(trade)

        # Duplicate önleme
        if fp in finalized_fps:
            skipped += 1
            results.append({
                "pair":   trade.get("pair"),
                "status": "already_finalized",
                "source_trade_fingerprint": fp,
            })
            continue

        candidates = _match_candidates(trade, all_candidates)
        rechecks   = _match_rechecks(trade, all_rechecks)

        memory = build_mistake_memory(trade, candidates, rechecks)

        if memory.get("status") == "not_created":
            results.append({
                "pair":   memory.get("pair"),
                "status": "not_created",
                "reason": memory.get("reason"),
            })
            continue

        memory_id = save_mistake_memory(memory)
        finalized_fps.add(fp)      # bellek içi duplicate önleme (aynı batch)
        memory_ids.append(memory_id)
        results.append({
            "pair":              trade.get("pair"),
            "side":              trade.get("side"),
            "memory_id":         memory_id,
            "result":            memory["final_summary"]["result"],
            "label_codes":       [l["code"] for l in memory.get("final_labels") or []],
            "recommended_review": memory["final_summary"]["recommended_review"],
            "evidence_quality":  (memory.get("candidate_evidence") or {}).get(
                "evidence_quality", "limited"
            ),
        })

    status = "created" if memory_ids else "not_created"
    reason = "no_new_closed_trades" if not memory_ids and closed_trades else None

    response: dict = {
        "status":              status,
        "count":               len(memory_ids),
        "memory_ids":          memory_ids,
        "skipped_count":       skipped,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "is_final":            True,
        "results":             results,
    }
    if reason:
        response["reason"] = reason
    return response


@router.get("/recent")
def get_recent_mistake_memory(limit: int = 50) -> dict:
    """Son N final mistake memory'yi döndürür (read-only)."""
    safe_limit = max(1, min(limit, 500))
    records = load_recent_mistake_memory(limit=safe_limit)
    return {
        "status":   "ok",
        "count":    len(records),
        "memories": records,
    }
