"""
FAZ 9 — Scheduler Service.

Paper-safe otomatik döngü. 7 adımı sırayla çalıştırır ve her birinin
sonucunu scheduler_runs.jsonl dosyasına kaydeder.

Adımlar:
  1. snapshot_capture      — hourly snapshot yaz
  2. agent_thesis          — agent tezi üret
  3. position_recheck      — açık pozisyon audit
  4. learning_candidate    — açık pozisyon için öğrenme adayı
  5. mistake_memory        — kapanmış trade'ler için final memory
  6. weekly_calibration    — kalibrasyon raporu
  7. auto_tune             — override proposal'larını değerlendir/uygula

Kural:
  • Bir adım hata verse diğerleri çalışmaya devam eder.
  • Hiçbir adım trade açmaz/kapatmaz.
  • broker_permission = BROKER_NOT_CONNECTED
  • live_execution_allowed = False
  • Scheduler varsayılan olarak kapalıdır.
  • run-once her zaman çalışır.
  • start/stop memory flag ile kontrol edilir.

Nota: snapshot_capture adımı, pipeline verisini API katmanındaki
  _build_pipeline'dan lazy import ile alır. Bu import adım fonksiyonu
  içinde (module düzeyinde değil) yapılır — API modülüne modül seviyesi
  bağımlılık oluşturmamak için. Diğer adımlar sadece servis/storage
  katmanından import eder.
"""
from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from app.storage.scheduler_run_store import save_scheduler_run

_log = logging.getLogger(__name__)

# ── Module-level durum (single-process / single-worker) ───────────────────────

_scheduler_lock  = threading.Lock()
_scheduler_thread: threading.Thread | None = None
_stop_event      = threading.Event()
_is_running      = False
_interval_seconds = 3600  # varsayılan: saatlik
_last_run_id: str | None = None
_last_run_at: str | None = None

# Güvenlik sabitleri
_SECURITY: dict[str, Any] = {
    "decision_permission":    "NO_EXECUTION",
    "execution_mode":         "PAPER_SAFE",
    "broker_permission":      "BROKER_NOT_CONNECTED",
    "live_execution_allowed": False,
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Step sonuç objesi üretir."""
    return {"name": name, "status": status, "result": result or {}}


def _summary(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Adım listesinden özet üretir."""
    failed = [s["name"] for s in steps if s["status"] == "fail"]
    non_skipped = [s for s in steps if s["status"] != "skipped"]
    if not non_skipped:
        overall = "skipped"
    elif not failed:
        overall = "success"
    elif len(failed) == len(non_skipped):
        overall = "fail"
    else:
        overall = "partial"
    return {"status": overall, "failed_steps": failed}


# ── Adım implementasyonları ───────────────────────────────────────────────────

def _run_step_snapshot_capture() -> dict[str, Any]:
    """
    Adım 1: Hourly snapshot yaz.

    snapshot_capture: gerçek market pipeline verisi gerektirir.
    Pipeline başarısız olursa adım 'fail' döner; sonraki adımlar çalışır.

    Not: _build_pipeline lazy import ile yüklenir — API modülü bu
    servisin MODULE düzeyinde bağımlılığı değildir.
    """
    name = "snapshot_capture"
    try:
        # Lazy import — module-level API bağımlılığı yok
        from app.api.consensus import _build_pipeline  # noqa: PLC0415
        from app.services import paper_trading_service as pts  # noqa: PLC0415
        from app.services.hourly_snapshot_builder import (  # noqa: PLC0415
            build_hourly_snapshot_payload,
        )
        from app.storage.hourly_snapshot_store import save_hourly_snapshot  # noqa: PLC0415

        report, rotation, mtf, raw_snapshots = _build_pipeline()

        if not report and not rotation and not mtf:
            return _step(name, "skipped", {"reason": "pipeline_data_unavailable"})

        pt_state: dict | None = None
        try:
            pt_state = pts.get_snapshot()
        except Exception:
            pass

        dq: dict[str, Any] = {"status": "unknown"}
        try:
            from app.services.data_quality_service import (  # noqa: PLC0415
                get_data_quality_summary,
            )
            asset_snaps = {
                str(s.asset_symbol): s
                for s in raw_snapshots
                if hasattr(s, "fallback_used")
            }
            dq = get_data_quality_summary(asset_snaps) or dq
        except Exception:
            pass

        payload = build_hourly_snapshot_payload(
            report=report,
            rotation=rotation,
            mtf=mtf,
            paper_trading_state=pt_state,
            data_quality=dq,
        )
        snapshot_id = save_hourly_snapshot(payload)
        return _step(name, "success", {"snapshot_id": snapshot_id})

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


def _run_step_agent_thesis() -> dict[str, Any]:
    """Adım 2: Agent tezi üret ve kaydet."""
    name = "agent_thesis"
    try:
        from app.services.agent_hourly_thesis_service import (  # noqa: PLC0415
            build_agent_hourly_thesis,
        )
        from app.storage.agent_thesis_store import save_agent_thesis  # noqa: PLC0415
        from app.storage.hourly_snapshot_store import (  # noqa: PLC0415
            load_recent_hourly_snapshots,
        )

        snapshots = load_recent_hourly_snapshots(limit=3)
        if not snapshots:
            return _step(name, "skipped", {"reason": "no_hourly_snapshots"})

        thesis = build_agent_hourly_thesis(snapshots)
        if thesis.get("status") == "not_created":
            return _step(name, "skipped", {"reason": thesis.get("reason")})

        thesis_id = save_agent_thesis(thesis)
        return _step(name, "success", {"thesis_id": thesis_id})

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


def _run_step_position_recheck() -> dict[str, Any]:
    """Adım 3: Açık pozisyonlar için audit recheck."""
    name = "position_recheck"
    try:
        from app.services import paper_trading_service as pts  # noqa: PLC0415
        from app.services.agent_thesis_context import (  # noqa: PLC0415
            load_latest_safe_thesis,
        )
        from app.services.position_recheck_service import (  # noqa: PLC0415
            build_position_recheck,
        )
        from app.storage.hourly_snapshot_store import (  # noqa: PLC0415
            load_recent_hourly_snapshots,
        )
        from app.storage.position_recheck_store import (  # noqa: PLC0415
            save_position_recheck,
        )

        snap_state = pts.get_snapshot()
        open_positions = snap_state.get("open_positions") or []
        if not open_positions:
            return _step(name, "skipped", {"reason": "no_open_positions"})

        hourly_snaps = load_recent_hourly_snapshots(limit=1)
        latest_snapshot = hourly_snaps[-1] if hourly_snaps else None
        latest_thesis = load_latest_safe_thesis()

        saved = 0
        for pos in open_positions:
            recheck = build_position_recheck(pos, latest_snapshot, latest_thesis)
            if recheck.get("status") != "not_created":
                save_position_recheck(recheck)
                saved += 1

        return _step(name, "success", {
            "positions_checked": len(open_positions),
            "saved_count":       saved,
        })

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


def _run_step_learning_candidate() -> dict[str, Any]:
    """Adım 4: Açık pozisyonlar için öğrenme adayı."""
    name = "learning_candidate"
    try:
        from app.services import paper_trading_service as pts  # noqa: PLC0415
        from app.services.agent_thesis_context import (  # noqa: PLC0415
            load_latest_safe_thesis,
        )
        from app.services.learning_candidate_service import (  # noqa: PLC0415
            build_learning_candidate,
        )
        from app.storage.hourly_snapshot_store import (  # noqa: PLC0415
            load_recent_hourly_snapshots,
        )
        from app.storage.learning_candidate_store import (  # noqa: PLC0415
            save_learning_candidate,
        )
        from app.storage.position_recheck_store import (  # noqa: PLC0415
            load_recent_position_rechecks,
        )

        snap_state = pts.get_snapshot()
        open_positions = snap_state.get("open_positions") or []
        if not open_positions:
            return _step(name, "skipped", {"reason": "no_open_positions"})

        hourly_snaps = load_recent_hourly_snapshots(limit=1)
        latest_snapshot = hourly_snaps[-1] if hourly_snaps else None
        latest_thesis = load_latest_safe_thesis()
        all_rechecks = load_recent_position_rechecks(limit=200)

        def _latest_recheck(pair: str) -> dict | None:
            matches = [r for r in all_rechecks if r.get("pair") == pair]
            return matches[-1] if matches else None

        saved = 0
        for pos in open_positions:
            pair = str(pos.get("pair") or "").strip()
            candidate = build_learning_candidate(
                pos,
                _latest_recheck(pair),
                latest_snapshot,
                latest_thesis,
            )
            if candidate.get("status") != "not_created":
                save_learning_candidate(candidate)
                saved += 1

        return _step(name, "success", {
            "positions_checked": len(open_positions),
            "saved_count":       saved,
        })

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


def _run_step_mistake_memory() -> dict[str, Any]:
    """Adım 5: Kapanmış trade'ler için final memory finalize."""
    name = "mistake_memory_finalize"
    try:
        from app.services import paper_trading_service as pts  # noqa: PLC0415
        from app.services.mistake_memory_service import (  # noqa: PLC0415
            _trade_fingerprint,
            build_mistake_memory,
        )
        from app.storage.learning_candidate_store import (  # noqa: PLC0415
            load_recent_learning_candidates,
        )
        from app.storage.mistake_memory_store import (  # noqa: PLC0415
            load_finalized_fingerprints,
            save_mistake_memory,
        )
        from app.storage.position_recheck_store import (  # noqa: PLC0415
            load_recent_position_rechecks,
        )

        snap_state = pts.get_snapshot()
        closed_trades = (
            snap_state.get("closed_trades")
            or snap_state.get("trade_history")
            or snap_state.get("trades")
            or []
        )
        if not closed_trades:
            return _step(name, "skipped", {"reason": "no_closed_trades"})

        finalized_fps = load_finalized_fingerprints()
        all_candidates = load_recent_learning_candidates(limit=500)
        all_rechecks   = load_recent_position_rechecks(limit=500)

        def _match_candidates(trade: dict) -> list[dict]:
            pair  = str(trade.get("pair") or "")
            entry = float(trade.get("entry_price") or 0)
            tid   = trade.get("trade_id") or trade.get("id")
            out: list[dict] = []
            for c in all_candidates:
                if c.get("pair") != pair:
                    continue
                if tid and c.get("position_id") == str(tid):
                    out.append(c)
                    continue
                ce = float(c.get("entry_price") or 0)
                if entry > 0 and ce > 0 and abs(entry - ce) / entry * 100 < 0.5:
                    out.append(c)
            return out

        def _match_rechecks(trade: dict) -> list[dict]:
            pair  = str(trade.get("pair") or "")
            entry = float(trade.get("entry_price") or 0)
            out: list[dict] = []
            for r in all_rechecks:
                if r.get("pair") != pair:
                    continue
                re = float(r.get("entry_price") or 0)
                if entry > 0 and re > 0:
                    if abs(entry - re) / entry * 100 < 0.5:
                        out.append(r)
                else:
                    out.append(r)
            return out

        memory_ids: list[str] = []
        for trade in closed_trades:
            fp = _trade_fingerprint(trade)
            if fp in finalized_fps:
                continue
            memory = build_mistake_memory(
                trade, _match_candidates(trade), _match_rechecks(trade)
            )
            if memory.get("status") == "not_created":
                continue
            mid = save_mistake_memory(memory)
            finalized_fps.add(fp)
            memory_ids.append(mid)

        return _step(name, "success", {
            "trades_checked": len(closed_trades),
            "memories_saved": len(memory_ids),
        })

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


def _run_step_weekly_calibration() -> dict[str, Any]:
    """Adım 6: Haftalık kalibrasyon raporu üret."""
    name = "weekly_calibration"
    try:
        from app.services.weekly_calibration_service import (  # noqa: PLC0415
            build_weekly_calibration,
        )
        from app.storage.learning_candidate_store import (  # noqa: PLC0415
            load_recent_learning_candidates,
        )
        from app.storage.mistake_memory_store import (  # noqa: PLC0415
            load_recent_mistake_memory,
        )
        from app.storage.position_recheck_store import (  # noqa: PLC0415
            load_recent_position_rechecks,
        )
        from app.storage.weekly_calibration_store import (  # noqa: PLC0415
            save_weekly_calibration,
        )

        memories   = load_recent_mistake_memory(limit=0)
        candidates = load_recent_learning_candidates(limit=0)
        rechecks   = load_recent_position_rechecks(limit=500)

        calibration = build_weekly_calibration(
            memories=memories, candidates=candidates, rechecks=rechecks,
        )

        if calibration.get("status") == "not_created":
            return _step(name, "skipped", {
                "reason": calibration.get("reason", "insufficient_data"),
            })

        cal_id = save_weekly_calibration(calibration)
        return _step(name, "success", {"calibration_id": cal_id})

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


def _run_step_auto_tune() -> dict[str, Any]:
    """Adım 7: Auto-tune proposal'larını değerlendir ve uygula."""
    name = "auto_tune"
    try:
        from app.services.auto_tune_service import (  # noqa: PLC0415
            apply_proposals,
            evaluate_proposals,
        )

        eval_result = evaluate_proposals()
        if eval_result.get("status") != "eligible":
            return _step(name, "skipped", {
                "reason":  eval_result.get("reason", "not_eligible"),
                "status":  eval_result.get("status"),
            })

        apply_result = apply_proposals()
        return _step(name, "success", {
            "applied_count": apply_result.get("count", 0),
            "status":        apply_result.get("status"),
        })

    except Exception as exc:
        _log.warning("scheduler step %s failed: %s", name, exc)
        return _step(name, "fail", {"error": str(exc)[:200]})


# ── Public: run-once ──────────────────────────────────────────────────────────

def run_once() -> dict[str, Any]:
    """
    7 adımın tamamını sırayla çalıştırır.

    Bir adım fail olursa sonraki adımlar çalışmaya devam eder.
    Sonuç scheduler_runs.jsonl dosyasına kaydedilir.

    Returns: run kaydı (run_id, steps, summary dahil)
    """
    global _last_run_id, _last_run_at

    created_at = _utc_now_iso()
    _log.info("scheduler run_once started")

    steps = [
        _run_step_snapshot_capture(),
        _run_step_agent_thesis(),
        _run_step_position_recheck(),
        _run_step_learning_candidate(),
        _run_step_mistake_memory(),
        _run_step_weekly_calibration(),
        _run_step_auto_tune(),
    ]

    summary = _summary(steps)
    _log.info(
        "scheduler run_once done | status=%s | failed=%s",
        summary["status"], summary["failed_steps"],
    )

    run: dict[str, Any] = {
        **_SECURITY,
        "created_at": created_at,
        "steps":      steps,
        "summary":    summary,
    }
    run_id = save_scheduler_run(run)
    run["run_id"] = run_id

    with _scheduler_lock:
        _last_run_id = run_id
        _last_run_at = created_at

    return run


# ── Background loop ───────────────────────────────────────────────────────────

def _background_loop(interval: int) -> None:
    """Arka planda `interval` saniyede bir run_once çalıştırır."""
    global _is_running
    while not _stop_event.wait(timeout=interval):
        if not _is_running:
            break
        try:
            run_once()
        except Exception:
            _log.exception("scheduler background_loop: run_once failed (loop continues)")
    _log.info("scheduler background_loop stopped")


# ── Public: start / stop / status ────────────────────────────────────────────

def scheduler_start(interval_seconds: int = 3600) -> dict[str, Any]:
    """
    Arka plan scheduler'ı başlatır.

    interval_seconds: çalıştırmalar arası bekleme süresi (60–86400).
    Zaten çalışıyorsa "already_running" döner.
    """
    global _scheduler_thread, _is_running, _stop_event, _interval_seconds

    safe_interval = max(60, min(interval_seconds, 86_400))

    with _scheduler_lock:
        if _is_running and _scheduler_thread is not None and _scheduler_thread.is_alive():
            return {
                **_SECURITY,
                "status":            "already_running",
                "interval_seconds":  _interval_seconds,
            }

        _stop_event.clear()
        _is_running = True
        _interval_seconds = safe_interval

        _scheduler_thread = threading.Thread(
            target=_background_loop,
            args=(safe_interval,),
            daemon=True,
            name="scheduler-loop",
        )
        _scheduler_thread.start()

    _log.info("scheduler started | interval=%ss", safe_interval)
    return {
        **_SECURITY,
        "status":           "started",
        "interval_seconds": safe_interval,
    }


def scheduler_stop() -> dict[str, Any]:
    """
    Arka plan scheduler'ı durdurur.

    Çalışmıyorsa "already_stopped" döner.
    """
    global _is_running

    with _scheduler_lock:
        if not _is_running:
            return {**_SECURITY, "status": "already_stopped"}
        _is_running = False
        _stop_event.set()

    _log.info("scheduler stop requested")
    return {**_SECURITY, "status": "stopped"}


def get_scheduler_status() -> dict[str, Any]:
    """
    Scheduler'ın mevcut durumunu döndürür.
    """
    with _scheduler_lock:
        thread_alive = (
            _scheduler_thread is not None and _scheduler_thread.is_alive()
        )
        return {
            **_SECURITY,
            "running":          _is_running and thread_alive,
            "interval_seconds": _interval_seconds,
            "last_run_id":      _last_run_id,
            "last_run_at":      _last_run_at,
        }
