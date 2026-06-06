"""
Core Snapshot Cache — Item 3 / snapshot ID contract (puan 97).

Pipeline çıktısı bir snapshot_id ile dondurulur. Agent, critic ve audit
hepsi aynı snapshot'a referans verir.

Faydaları:
  • Tutarlılık — agent ve critic farklı pipeline'lar çalıştırmaz, aynı veriyi okur
  • Cache friendliness — aynı snapshot_id için tekrar hesap yok
  • Reproducibility — audit kaydındaki snapshot_id ile re-replay mümkün
  • Contract — her snapshot contract_version taşır

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import Any

_TTL_SECONDS_DEFAULT = 60
_MAX_SNAPSHOTS = 50
CONTRACT_VERSION = "1.0_revised"

_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_LOCK = threading.Lock()
_CURRENT_ID: str | None = None


def _make_id(evidence: dict[str, Any]) -> str:
    """Evidence'ın stabil hash'i + timestamp → snapshot_id."""
    try:
        s = json.dumps(evidence, sort_keys=True, default=str)[:8000]
    except Exception:
        s = repr(evidence)[:8000]
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"snap_{ts}_{h}"


def _is_expired(entry: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    try:
        return now > datetime.fromisoformat(entry["expires_at"])
    except Exception:
        return False


def create_snapshot(
    evidence: dict[str, Any],
    *,
    ttl_seconds: int = _TTL_SECONDS_DEFAULT,
    source: str = "pipeline",
) -> tuple[str, dict[str, Any]]:
    """Yeni snapshot oluştur, cache'e koy, (snapshot_id, entry) döndür."""
    snapshot_id = _make_id(evidence)
    now = datetime.now(UTC)
    entry: dict[str, Any] = {
        "snapshot_id":      snapshot_id,
        "contract_version": CONTRACT_VERSION,
        "source":           source,
        "evidence":         evidence,
        "created_at":       now.isoformat(),
        "expires_at":       (now + timedelta(seconds=ttl_seconds)).isoformat(),
        "ttl_seconds":      ttl_seconds,
    }
    with _LOCK:
        # Aynı hash daha önce varsa over-write etme — eskisi geçerli sayılır
        if snapshot_id in _CACHE and not _is_expired(_CACHE[snapshot_id], now):
            entry = _CACHE[snapshot_id]
        else:
            _CACHE[snapshot_id] = entry
            while len(_CACHE) > _MAX_SNAPSHOTS:
                _CACHE.popitem(last=False)
        global _CURRENT_ID
        _CURRENT_ID = snapshot_id
    return snapshot_id, entry


def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    """ID ile snapshot al. Expired ise None döner ve cache'den siler."""
    with _LOCK:
        entry = _CACHE.get(snapshot_id)
        if entry is None:
            return None
        if _is_expired(entry):
            _CACHE.pop(snapshot_id, None)
            return None
    return entry


def get_current() -> dict[str, Any] | None:
    """Sistem genelinde mevcut geçerli snapshot."""
    with _LOCK:
        sid = _CURRENT_ID
    if sid is None:
        return None
    return get_snapshot(sid)


def list_recent(limit: int = 20) -> list[dict[str, Any]]:
    """Son N snapshot'ın özetini döndür (evidence dahil değil)."""
    with _LOCK:
        items = list(_CACHE.values())
    items.reverse()
    summary = []
    for it in items[:limit]:
        s = {k: v for k, v in it.items() if k != "evidence"}
        s["evidence_keys"] = sorted(list((it.get("evidence") or {}).keys()))
        summary.append(s)
    return summary


def stats() -> dict[str, Any]:
    with _LOCK:
        n = len(_CACHE)
        cur = _CURRENT_ID
    return {
        "total":          n,
        "max":            _MAX_SNAPSHOTS,
        "current_id":     cur,
        "ttl_default_s":  _TTL_SECONDS_DEFAULT,
        "contract_version": CONTRACT_VERSION,
    }


__all__ = [
    "create_snapshot",
    "get_snapshot",
    "get_current",
    "list_recent",
    "stats",
    "CONTRACT_VERSION",
]
