"""
Job Runner — Async job pattern for slow operations.

ThreadPoolExecutor tabanlı, in-memory job queue. Redis/Celery YOK.
LLM çağrıları gibi uzun işler için: POST job → job_id, GET poll.

Tipik kullanım:
  job_id = job_runner.submit(func, *args, label="ai-report.current")
  status = job_runner.get_status(job_id)   # pending|running|ready|failed
  result = job_runner.get_result(job_id)   # ready ise dict, değilse None

TTL: 30 dk — job sonuçları belleğe kazınır, sonra GC.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Callable

_MAX_WORKERS = 2
_TTL_SECONDS = 1800

_EXECUTOR = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="eyay-job")
_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def submit(
    func: Callable[..., Any],
    *args: Any,
    label: str = "job",
    snapshot_id: str | None = None,
    **kwargs: Any,
) -> str:
    """Job submit et, job_id döner. Func arka planda çalışır."""
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    future = _EXECUTOR.submit(_run, job_id, func, args, kwargs)

    with _LOCK:
        _JOBS[job_id] = {
            "id":           job_id,
            "label":        label,
            "snapshot_id":  snapshot_id,
            "status":       "pending",
            "created_at":   now_iso,
            "started_at":   None,
            "completed_at": None,
            "result":       None,
            "error":        None,
            "_future":      future,
        }
        _cleanup_expired_locked()
    return job_id


def _run(job_id: str, func: Callable[..., Any], args: tuple, kwargs: dict) -> Any:
    """Job'u çalıştır + status güncelle (worker thread)."""
    with _LOCK:
        entry = _JOBS.get(job_id)
        if entry is not None:
            entry["status"]     = "running"
            entry["started_at"] = datetime.now(UTC).isoformat()
    try:
        result = func(*args, **kwargs)
        with _LOCK:
            entry = _JOBS.get(job_id)
            if entry is not None:
                entry["status"]       = "ready"
                entry["completed_at"] = datetime.now(UTC).isoformat()
                entry["result"]       = result
        return result
    except Exception as exc:
        with _LOCK:
            entry = _JOBS.get(job_id)
            if entry is not None:
                entry["status"]       = "failed"
                entry["completed_at"] = datetime.now(UTC).isoformat()
                entry["error"]        = repr(exc)[:500]
        raise


def get_status(job_id: str) -> dict[str, Any] | None:
    """Job durumu (future hariç) — yoksa None."""
    with _LOCK:
        entry = _JOBS.get(job_id)
    if entry is None:
        return None
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def get_result(job_id: str, *, wait_seconds: float = 0.0) -> Any | None:
    """Sonucu döndür. wait_seconds > 0 ise o süre kadar bekler (sync fallback)."""
    with _LOCK:
        entry = _JOBS.get(job_id)
    if entry is None:
        return None
    future: Future | None = entry.get("_future")  # type: ignore
    if future is None:
        return entry.get("result")
    if wait_seconds > 0:
        try:
            future.result(timeout=wait_seconds)
        except Exception:
            pass
    if future.done():
        return entry.get("result")
    return None


def _cleanup_expired_locked() -> None:
    """TTL geçmiş job'ları temizle (LOCK çağıran tarafça tutulur)."""
    now = datetime.now(UTC)
    drop: list[str] = []
    for job_id, entry in _JOBS.items():
        ts = entry.get("completed_at") or entry.get("created_at")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts)
            if (now - t).total_seconds() > _TTL_SECONDS:
                drop.append(job_id)
        except Exception:
            pass
    for j in drop:
        _JOBS.pop(j, None)


def list_recent(limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        items = [
            {k: v for k, v in e.items() if not k.startswith("_")}
            for e in _JOBS.values()
        ]
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[:limit]


def stats() -> dict[str, Any]:
    with _LOCK:
        counts: dict[str, int] = {}
        for e in _JOBS.values():
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        total = len(_JOBS)
    return {
        "total":       total,
        "by_status":   counts,
        "max_workers": _MAX_WORKERS,
        "ttl_seconds": _TTL_SECONDS,
    }


__all__ = [
    "submit",
    "get_status",
    "get_result",
    "list_recent",
    "stats",
]
