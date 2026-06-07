"""
Agent Memory — Sprint 7 / Item 7 (puan 88).

Agent'in önceki kararlarını, gözlemlerini ve "öğrendiklerini" hatırlayabildiği
hafif persistent katman. Embedding/vector DB değil — appendable JSONL +
in-memory ring + basit kategori indeksi.

İçerik:
  • decisions   — önceki agent kararları (özet)
  • observations— "fark ettim" notları (regime değişti vb)
  • lessons     — eval sonuçlarından çıkan dersler (ör: HIGH band kötü kalibre)
  • pinned      — kullanıcı/sistem tarafından sabitlenmiş not

Kullanım:
  • LLM prompt context'ine en alakalı son N anı (kategori veya regime ile filtrele)
  • Eval pass'ları otomatik "lesson" yazar (puanı çok kötü kararlar)
  • Insight pipeline her run'da son kararı "decision" olarak yazar

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import json
import threading
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MEM_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "agent_memory.jsonl"
_RING: deque[dict[str, Any]] = deque(maxlen=1000)
_LOCK = threading.Lock()
_LOADED = False

_VALID_CATEGORIES = {"decision", "observation", "lesson", "pinned"}


@dataclass
class MemoryEntry:
    id: str
    category: str
    timestamp: str
    text: str
    regime: str | None = None
    snapshot_id: str | None = None
    confidence_pct: float | None = None
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    with _LOCK:
        if _LOADED:
            return
        try:
            if _MEM_LOG_PATH.exists():
                with _MEM_LOG_PATH.open("r", encoding="utf-8") as h:
                    lines = h.readlines()[-1000:]
                for ln in lines:
                    try:
                        obj = json.loads(ln)
                        _RING.append(obj)
                    except Exception:
                        continue
        except Exception:
            pass
        _LOADED = True


def remember(
    *,
    category: str,
    text: str,
    regime: str | None = None,
    snapshot_id: str | None = None,
    confidence_pct: float | None = None,
    tags: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Belleğe yeni kayıt ekle. Hata olursa sessiz."""
    if category not in _VALID_CATEGORIES:
        category = "observation"
    entry = MemoryEntry(
        id=f"mem_{uuid.uuid4().hex[:10]}",
        category=category,
        timestamp=datetime.now(UTC).isoformat(),
        text=str(text)[:1000],
        regime=regime,
        snapshot_id=snapshot_id,
        confidence_pct=confidence_pct,
        tags=tags or [],
        extra=extra or {},
    )
    obj = asdict(entry)
    _ensure_loaded()
    with _LOCK:
        _RING.append(obj)
    try:
        _MEM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _MEM_LOG_PATH.open("a", encoding="utf-8") as h:
            h.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass
    return obj


def recall(
    *,
    limit: int = 20,
    category: str | None = None,
    regime: str | None = None,
    tags: list[str] | None = None,
    contains: str | None = None,
) -> list[dict[str, Any]]:
    """Belleği filtreli oku. Yeni → eski sıralama."""
    _ensure_loaded()
    with _LOCK:
        items = list(_RING)
    items.reverse()
    if category:
        items = [i for i in items if i.get("category") == category]
    if regime:
        items = [i for i in items if (i.get("regime") or "").lower() == regime.lower()]
    if tags:
        wanted = {t.lower() for t in tags}
        items = [i for i in items if any(t.lower() in wanted for t in (i.get("tags") or []))]
    if contains:
        c = contains.lower()
        items = [i for i in items if c in (i.get("text") or "").lower()]
    return items[:max(1, min(limit, 200))]


def context_for_prompt(
    *,
    regime: str | None = None,
    max_chars: int = 1200,
    max_items: int = 8,
) -> str:
    """LLM prompt'a sığacak özetli bellek bloğu — pinned + son lessons + son decisions."""
    pinned = recall(limit=3, category="pinned")
    lessons = recall(limit=3, category="lesson", regime=regime)
    decisions = recall(limit=4, category="decision", regime=regime)
    blocks = pinned + lessons + decisions
    blocks = blocks[:max_items]
    if not blocks:
        return ""
    lines = ["[BELLEK · son notlar]"]
    for b in blocks:
        tag = b.get("category", "").upper()
        ts = (b.get("timestamp") or "")[:19]
        reg = b.get("regime") or "-"
        txt = (b.get("text") or "").replace("\n", " ")
        ln = f"• [{tag}·{ts}·{reg}] {txt}"
        lines.append(ln)
    out = "\n".join(lines)
    if len(out) > max_chars:
        out = out[: max_chars - 1] + "…"
    return out


def forget(entry_id: str) -> bool:
    _ensure_loaded()
    with _LOCK:
        before = len(_RING)
        kept = [i for i in _RING if i.get("id") != entry_id]
        _RING.clear()
        _RING.extend(kept)
        return len(_RING) < before


def stats() -> dict[str, Any]:
    _ensure_loaded()
    with _LOCK:
        items = list(_RING)
    by_cat: dict[str, int] = {}
    for it in items:
        c = it.get("category", "?")
        by_cat[c] = by_cat.get(c, 0) + 1
    return {
        "total":      len(items),
        "by_category": by_cat,
        "ring_max":   _RING.maxlen,
        "log_file":   str(_MEM_LOG_PATH),
    }


# ────────────────────────────────────────────────────────────────────────────
# Otomatik ders çıkar — eval'den çağrılır
# ────────────────────────────────────────────────────────────────────────────

def auto_lesson_from_eval(eval_result: dict[str, Any]) -> dict[str, Any] | None:
    """Çok kötü puan veya yanlış kalibre durumu için otomatik ders yaz."""
    score = eval_result.get("score")
    band = eval_result.get("calibration_bucket") or eval_result.get("confidence_band")
    correct = eval_result.get("direction_correct")
    decision = eval_result.get("decision")
    realized = eval_result.get("realized_delta_pct")

    text: str | None = None
    if score is not None and score <= -0.75:
        text = (
            f"Yön tahmini ters çıktı (decision={decision}, realized_delta={realized}%). "
            f"Bu rejimde benzer sinyallere daha temkinli yaklaş."
        )
    elif band == "HIGH" and correct is False:
        text = (
            f"HIGH güvenle verilen karar ({decision}) yanlış çıktı. "
            f"HIGH band kalibrasyonunu sıkılaştır."
        )
    if not text:
        return None
    return remember(
        category="lesson",
        text=text,
        snapshot_id=eval_result.get("snapshot_id"),
        confidence_pct=eval_result.get("confidence_pct"),
        tags=["auto", "eval"],
        extra={"score": score, "band": band},
    )


__all__ = [
    "MemoryEntry",
    "remember",
    "recall",
    "context_for_prompt",
    "forget",
    "stats",
    "auto_lesson_from_eval",
]
