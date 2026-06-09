"""
FAZ 10 — System Health Summary API.

Read-only endpoint:
  GET /system-health/summary

Beş sağlık kontrolü:
  scheduler     — arka plan döngüsü çalışıyor mu + son run başarılı mı?
  snapshot      — son hourly pipeline snapshot yaşı
  thesis        — son agent thesis veri kalitesi
  paper_trading — state anomaly flag + açık pozisyon sayısı
  auto_tune     — aktif override sayısı

Yanıt şeması:
  {
    "status": "ok" | "degraded" | "fail",
    "checks": [{"name", "status", "message"}, ...],
    "safety": { güvenlik sabitleri }
  }

Güvenlik:
  Read-only — hiçbir şey yazılmaz/değiştirilmez.
  Broker yok, live execution yok.
  Trade açmaz/kapatmaz.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from app.storage.agent_thesis_store import load_recent_agent_theses
from app.storage.auto_tune_store import read_overrides
from app.storage.hourly_snapshot_store import load_recent_hourly_snapshots
from app.storage.scheduler_run_store import load_recent_scheduler_runs

router = APIRouter(prefix="/system-health", tags=["system-health"])

# ── Güvenlik sabitleri ────────────────────────────────────────────────────────

_SAFETY: dict[str, Any] = {
    "decision_permission":    "NO_EXECUTION",
    "execution_mode":         "PAPER_SAFE",
    "broker_permission":      "BROKER_NOT_CONNECTED",
    "live_execution_allowed": False,
}

# Snapshot yaşı eşiği — üstündeyse "degraded"
_SNAPSHOT_STALE_SECONDS: float = 7_200.0   # 2 saat


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _age_seconds(iso_str: str | None) -> float | None:
    """ISO timestamp'ten şimdiye kadar kaç saniye? Parse başarısızsa None döner."""
    if not iso_str:
        return None
    try:
        ts = datetime.fromisoformat(iso_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(UTC) - ts).total_seconds())
    except Exception:
        return None


def _fmt_age(seconds: float) -> str:
    """Saniyeyi okunabilir kısa form'a çevir: "5m", "2h 5m"."""
    seconds = max(0.0, seconds)
    minutes = int(seconds / 60)
    hours, mins = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    return f"{minutes}m"


def _check(name: str, status: str, message: str) -> dict[str, str]:
    """Tek check kaydı oluştur."""
    return {"name": name, "status": status, "message": message}


# ── Beş health check ──────────────────────────────────────────────────────────

def _check_scheduler() -> dict[str, str]:
    """
    Scheduler durumu: çalışıyor mu + son run başarılı mı?

    Durdurulmuşsa → degraded (fail değil).
    Son run fail ise → degraded.
    """
    try:
        from app.services.scheduler_service import get_scheduler_status  # lazy
        status_dict = get_scheduler_status()
        running: bool = bool(status_dict.get("running", False))

        recent = load_recent_scheduler_runs(limit=1)

        if not running:
            if not recent:
                return _check("scheduler", "degraded", "Scheduler stopped, no runs yet")
            last = recent[-1]
            summary = last.get("summary") or {}
            last_status = summary.get("status", "unknown")
            age = _age_seconds(last.get("created_at"))
            age_str = f", last run {_fmt_age(age)} ago" if age is not None else ""
            return _check(
                "scheduler", "degraded",
                f"Scheduler stopped{age_str}, last status: {last_status}",
            )

        # Çalışıyor
        if not recent:
            return _check("scheduler", "ok", "Running, no completed runs yet")

        last = recent[-1]
        summary = last.get("summary") or {}
        last_status = summary.get("status", "unknown")
        age = _age_seconds(last.get("created_at"))
        age_str = f"{_fmt_age(age)} ago" if age is not None else "unknown"

        if last_status == "fail":
            return _check("scheduler", "degraded", f"Running, last run failed ({age_str})")
        return _check("scheduler", "ok", f"Running, last run {last_status} ({age_str})")

    except Exception as exc:
        return _check("scheduler", "degraded", f"Status check error: {type(exc).__name__}")


def _check_snapshot() -> dict[str, str]:
    """Son hourly snapshot yaşı. Hiç yoksa → degraded. 2 saatten eskiyse → degraded."""
    try:
        snapshots = load_recent_hourly_snapshots(limit=1)
        if not snapshots:
            return _check("snapshot", "degraded", "No snapshots yet")

        last = snapshots[-1]
        age = _age_seconds(last.get("created_at"))
        if age is None:
            return _check("snapshot", "degraded", "Snapshot timestamp unreadable")

        age_str = _fmt_age(age)
        if age > _SNAPSHOT_STALE_SECONDS:
            return _check("snapshot", "degraded", f"Last snapshot {age_str} ago (stale)")
        return _check("snapshot", "ok", f"Last snapshot {age_str} ago")

    except Exception as exc:
        return _check("snapshot", "degraded", f"Snapshot check error: {type(exc).__name__}")


def _check_thesis() -> dict[str, str]:
    """Son agent thesis veri kalitesi. Hiç yoksa → degraded."""
    try:
        theses = load_recent_agent_theses(limit=1)
        if not theses:
            return _check("thesis", "degraded", "No theses yet")

        last = theses[-1]
        dq = last.get("data_quality") or {}
        dq_status = (dq.get("status") or "unknown").lower()

        age = _age_seconds(last.get("created_at"))
        age_str = f"{_fmt_age(age)} ago" if age is not None else "unknown"

        if dq_status in ("error", "fail", "failed"):
            return _check("thesis", "fail", f"Last thesis data quality: {dq_status} ({age_str})")
        if dq_status in ("degraded", "partial", "warning"):
            return _check(
                "thesis", "degraded",
                f"Last thesis data quality: {dq_status} ({age_str})",
            )
        return _check("thesis", "ok", f"Last thesis {age_str}, data quality: {dq_status}")

    except Exception as exc:
        return _check("thesis", "degraded", f"Thesis check error: {type(exc).__name__}")


def _check_paper_trading() -> dict[str, str]:
    """
    Paper trading anomaly flag + açık pozisyon sayısı.

    Anomaly aktifse → fail (kırmızı).
    """
    try:
        from app.services.paper_trading_service import get_snapshot  # lazy
        snap = get_snapshot()
        anomaly = snap.get("state_anomaly") or {}
        active: bool = bool(anomaly.get("active", False))
        reasons: list[str] = anomaly.get("reasons") or []
        open_count: int = len(snap.get("open_positions") or [])

        if active:
            reason_str = reasons[0] if reasons else "unknown"
            return _check(
                "paper_trading", "fail",
                f"Anomaly active ({reason_str}), open positions: {open_count}",
            )
        return _check(
            "paper_trading", "ok",
            f"Anomaly: false, open positions: {open_count}",
        )

    except Exception as exc:
        return _check(
            "paper_trading", "degraded",
            f"Paper trading check error: {type(exc).__name__}",
        )


def _check_auto_tune() -> dict[str, str]:
    """Auto-tune aktif override sayısı."""
    try:
        overrides = read_overrides()
        overrides_map = overrides.get("overrides") or {}
        count = sum(
            len(conditions) if isinstance(conditions, dict) else 1
            for conditions in overrides_map.values()
        )
        return _check("auto_tune", "ok", f"{count} active override(s)")

    except Exception as exc:
        return _check("auto_tune", "degraded", f"Auto-tune check error: {type(exc).__name__}")


# ── Genel durum ───────────────────────────────────────────────────────────────

def _overall_status(checks: list[dict[str, str]]) -> str:
    """Tüm check'lerden en kötü durumu al: fail > degraded > ok."""
    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        return "fail"
    if "degraded" in statuses:
        return "degraded"
    return "ok"


# ── Public endpoint ───────────────────────────────────────────────────────────

@router.get("/summary")
def get_system_health_summary() -> dict[str, Any]:
    """
    Sistem sağlık özeti — read-only.

    Beş modülün durumunu tek payload'da döndürür.
    Hiçbir şeyi değiştirmez; trade açmaz/kapatmaz.
    """
    checks: list[dict[str, str]] = [
        _check_scheduler(),
        _check_snapshot(),
        _check_thesis(),
        _check_paper_trading(),
        _check_auto_tune(),
    ]

    return {
        "status": _overall_status(checks),
        "checks": checks,
        "safety": _SAFETY,
    }
