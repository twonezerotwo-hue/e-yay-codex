"""
Similar Trade Memory — Geçmiş mistake_memory kayıtlarından benzer trade arama.

find_similar_trade_memories(signal, pair, side, limit=5) -> dict

Benzerlik kriterleri (AND değil puanlama):
  pair eşleşmesi     → +3
  side eşleşmesi     → +2
  primary_tf eşleşme → +1
  confluence_status  → +1
  pattern_bias       → +1
  pattern_score bucket (same ±1 tier) → +1
  asset_bias eşleşme → +1
  herhangi final_label overlap        → +1

Eşik: toplam puan >= 4 ise "benzer" kabul edilir.

Çıktı:
{
  "available": bool,
  "matches": int,
  "wins": int,
  "losses": int,
  "avg_pnl_pct": float | None,
  "common_labels": list[str],
  "summary": str
}

Sadece audit/context — karar motorunu, side/size/score'u değiştirmez.
PAPER_SAFE · NO_EXECUTION.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

_MIN_SCORE = 4          # benzer sayılmak için minimum puan
_PATTERN_BUCKETS = [(0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.01)]


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _pattern_bucket(score: float | None) -> int:
    if score is None:
        return -1
    for i, (lo, hi) in enumerate(_PATTERN_BUCKETS):
        if lo <= score < hi:
            return i
    return len(_PATTERN_BUCKETS) - 1


def _similarity_score(sig: dict[str, Any], pair: str, side: str, mem: dict) -> int:
    """Sinyal ile bellek kaydı arasındaki benzerlik puanını döndürür."""
    trade     = mem.get("trade") or {}
    opening   = mem.get("opening_context") or {}
    cand      = mem.get("candidate_evidence") or {}

    score = 0

    # pair
    mem_pair = trade.get("pair") or opening.get("pair") or ""
    if mem_pair and mem_pair.upper() == pair.upper():
        score += 3

    # side
    mem_side = trade.get("side") or opening.get("side") or ""
    if mem_side and mem_side.upper() == side.upper():
        score += 2

    # primary_tf
    sig_tf  = sig.get("primary_tf") or sig.get("tf") or ""
    mem_tf  = opening.get("primary_tf") or cand.get("primary_tf") or ""
    if sig_tf and mem_tf and sig_tf == mem_tf:
        score += 1

    # confluence_status
    sig_conf = sig.get("confluence_status") or ""
    mem_conf = opening.get("confluence_status") or cand.get("confluence_status") or ""
    if sig_conf and mem_conf and sig_conf == mem_conf:
        score += 1

    # pattern_bias
    sig_pb  = sig.get("pattern_bias") or sig.get("bias") or ""
    mem_pb  = opening.get("pattern_bias") or cand.get("pattern_bias") or ""
    if sig_pb and mem_pb and sig_pb == mem_pb:
        score += 1

    # pattern_score bucket
    sig_ps  = sig.get("pattern_score")
    mem_ps  = opening.get("pattern_score") or cand.get("pattern_score")
    sb, mb  = _pattern_bucket(sig_ps), _pattern_bucket(mem_ps)
    if sb >= 0 and mb >= 0 and abs(sb - mb) <= 1:
        score += 1

    # asset_bias (agent_thesis_context içinden)
    sig_thesis = sig.get("agent_thesis_context") or {}
    sig_bias   = (sig_thesis.get("asset_bias") or {}).get(pair.upper()) or ""
    mem_thesis = opening.get("agent_thesis_context") or {}
    mem_bias   = (mem_thesis.get("asset_bias") or {}).get(pair.upper()) or ""
    if sig_bias and mem_bias and sig_bias == mem_bias:
        score += 1

    # final_labels overlap
    sig_labels = set(sig.get("final_labels") or [])
    mem_labels = set(mem.get("final_labels") or [])
    if sig_labels & mem_labels:
        score += 1

    return score


def _build_summary(wins: int, losses: int, avg_pnl: float | None, common_labels: list[str]) -> str:
    total = wins + losses
    if total == 0:
        return "Benzer geçmiş trade bulunamadı."
    outcome = "kâr ağırlıklı" if wins >= losses else "loss ağırlıklı"
    pnl_str = f"; ort. PnL {avg_pnl:+.1f}%" if avg_pnl is not None else ""
    label_str = f"; tekrar eden etiket: {common_labels[0]}" if common_labels else ""
    return f"Benzer geçmiş trade'lerde {outcome} ({wins}K/{losses}L){pnl_str}{label_str}."


# ── Public API ────────────────────────────────────────────────────────────────

def find_similar_trade_memories(
    signal: dict[str, Any],
    pair: str,
    side: str,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Geçmiş mistake_memory kayıtlarından benzer trade'leri bulur.

    Döndürülen dict sadece audit/context içindir —
    karar motoru, side/size/score değiştirilmez.
    """
    try:
        from app.storage.mistake_memory_store import load_recent_mistake_memory  # noqa: PLC0415
        records = load_recent_mistake_memory(limit=200)
    except Exception:  # noqa: BLE001
        return _empty()

    if not records:
        return _empty()

    matches_raw: list[dict] = []
    for mem in records:
        # Pair hard filter — farklı asset'ler benzer sayılmaz
        trade   = mem.get("trade") or {}
        opening = mem.get("opening_context") or {}
        mem_pair = (trade.get("pair") or opening.get("pair") or "").upper()
        if mem_pair and mem_pair != pair.upper():
            continue
        s = _similarity_score(signal, pair, side, mem)
        if s >= _MIN_SCORE:
            matches_raw.append(mem)
        if len(matches_raw) >= limit:
            break

    if not matches_raw:
        return _empty()

    wins, losses, pnl_sum, pnl_count = 0, 0, 0.0, 0
    label_counter: Counter[str] = Counter()

    for mem in matches_raw:
        trade = mem.get("trade") or {}
        pnl   = trade.get("pnl_pct")
        if pnl is not None:
            if pnl > 0:
                wins += 1
            else:
                losses += 1
            pnl_sum   += pnl
            pnl_count += 1
        for lbl in mem.get("final_labels") or []:
            label_counter[lbl] += 1

    avg_pnl    = round(pnl_sum / pnl_count, 2) if pnl_count > 0 else None
    top_labels = [lbl for lbl, _ in label_counter.most_common(3)]

    return {
        "available":     True,
        "matches":       len(matches_raw),
        "wins":          wins,
        "losses":        losses,
        "avg_pnl_pct":   avg_pnl,
        "common_labels": top_labels,
        "summary":       _build_summary(wins, losses, avg_pnl, top_labels),
    }


def _empty() -> dict[str, Any]:
    return {
        "available":     False,
        "matches":       0,
        "wins":          0,
        "losses":        0,
        "avg_pnl_pct":   None,
        "common_labels": [],
        "summary":       "Benzer geçmiş trade bulunamadı.",
    }
