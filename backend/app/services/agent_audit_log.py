"""
Agent Audit Trail — Sprint 2 / Item 12.

"Neden böyle dedi?" sorusunun cevaplanabilmesi için her agent çağrısı kaydedilir.

Kayıt alanları:
  • timestamp, endpoint
  • input_hash, output_hash    — re-replay edilebilirlik için
  • snapshot_id, contract_version
  • model, tool_calls          — agent hangi araçları kullandı
  • validation, confidence     — self-validation + confidence sonuçları
  • duration_ms                — performans gözlemi

Saklama:
  • In-memory ring buffer (500 event) — hızlı erişim
  • Opsiyonel dosya append (data/agent_audit.log) — kalıcı iz
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RING: deque[dict[str, Any]] = deque(maxlen=500)
_LOCK = threading.Lock()
_COUNTER = 0

_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "agent_audit.log"


def _hash(payload: Any) -> str:
    """Stabil JSON hash — payload'un kimliğini sabitler."""
    try:
        s = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        s = repr(payload)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def record(
    *,
    endpoint: str,
    input_payload: Any = None,
    output_payload: Any = None,
    snapshot_id: str | None = None,
    contract_version: str | None = None,
    model: str | None = None,
    tool_calls: list[str] | None = None,
    validation: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
    duration_ms: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit entry oluştur, ring buffer'a ve opsiyonel olarak dosyaya yaz.

    Hata olursa sessiz geçer — audit asla ana akışı kırmaz.
    """
    global _COUNTER
    try:
        entry = {
            "id":               None,  # set below under lock
            "uid":              str(uuid.uuid4()),
            "timestamp":        datetime.now(UTC).isoformat(),
            "endpoint":         endpoint,
            "input_hash":       _hash(input_payload) if input_payload is not None else None,
            "output_hash":      _hash(output_payload) if output_payload is not None else None,
            "snapshot_id":      snapshot_id,
            "contract_version": contract_version,
            "model":            model,
            "tool_calls":       tool_calls or [],
            "validation":       validation,
            "confidence":       confidence,
            "duration_ms":      round(duration_ms, 1) if duration_ms is not None else None,
            "extra":            extra or {},
        }
        with _LOCK:
            _COUNTER += 1
            entry["id"] = _COUNTER
            _RING.append(entry)

        # Dosyaya append — best-effort
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_PATH.open("a", encoding="utf-8") as h:
                h.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

        return entry
    except Exception:
        return {"id": None, "endpoint": endpoint, "error": "audit_failed_silent"}


def get_recent(limit: int = 50, endpoint: str | None = None) -> list[dict[str, Any]]:
    """En son audit kayıtlarını yeni → eski döndür."""
    with _LOCK:
        items = list(_RING)
    items.reverse()
    if endpoint:
        items = [i for i in items if i.get("endpoint") == endpoint]
    return items[:max(1, min(limit, 500))]


def stats() -> dict[str, Any]:
    """Kayıt sayısı + endpoint dağılımı."""
    with _LOCK:
        items = list(_RING)
    endpoints: dict[str, int] = {}
    abstentions = 0
    for it in items:
        endpoints[it["endpoint"]] = endpoints.get(it["endpoint"], 0) + 1
        c = it.get("confidence") or {}
        if c.get("abstain"):
            abstentions += 1
    return {
        "total":       len(items),
        "by_endpoint": endpoints,
        "abstentions": abstentions,
        "ring_max":    _RING.maxlen,
        "log_file":    str(_LOG_PATH),
    }


__all__ = ["record", "get_recent", "stats"]
