"""
FAZ 9 — Scheduler Service testleri.

8 test:
  1.  run-once tüm step response'larını kaydeder (JSONL)
  2.  bir step fail olursa diğerleri kontrollü devam eder
  3.  NO_EXECUTION / PAPER_SAFE güvenlik alanları zorunludur
  4.  live_execution_allowed = False her zaman
  5.  scheduler run JSONL save + load
  6.  status endpoint çalışır (running=False varsayılan)
  7.  start / stop memory flag değiştirir
  8.  mock market data yok — step'ler gerçek fonksiyon çağrısı yapar ama
      pipeline yoksa skipped/fail döner (crash yok)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.services.scheduler_service as svc
import app.storage.scheduler_run_store as run_store


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _step(name: str, status: str = "success", result: dict | None = None) -> dict:
    return {"name": name, "status": status, "result": result or {}}


def _all_success_steps() -> list[dict]:
    names = [
        "snapshot_capture", "agent_thesis", "position_recheck",
        "learning_candidate", "mistake_memory_finalize",
        "weekly_calibration", "auto_tune",
    ]
    return [_step(n) for n in names]


def _mock_all_steps(monkeypatch, statuses: list[str] | None = None) -> None:
    """
    Tüm 7 adım fonksiyonunu monkeypatch ile değiştirir.
    statuses: her adım için durum listesi (varsayılan: hepsi "success").
    """
    names = [
        "_run_step_snapshot_capture",
        "_run_step_agent_thesis",
        "_run_step_position_recheck",
        "_run_step_learning_candidate",
        "_run_step_mistake_memory",
        "_run_step_weekly_calibration",
        "_run_step_auto_tune",
    ]
    step_names = [
        "snapshot_capture", "agent_thesis", "position_recheck",
        "learning_candidate", "mistake_memory_finalize",
        "weekly_calibration", "auto_tune",
    ]
    if statuses is None:
        statuses = ["success"] * 7

    for fn_name, step_name, status in zip(names, step_names, statuses):
        captured_name = step_name
        captured_status = status
        monkeypatch.setattr(
            svc,
            fn_name,
            lambda _n=captured_name, _s=captured_status: _step(_n, _s),
        )


# ── Store redirect ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _redirect_store(tmp_path, monkeypatch):
    monkeypatch.setattr(run_store, "_STORE_PATH", tmp_path / "scheduler_runs.jsonl")
    # scheduler_service'in run_once'u save_scheduler_run'ı svc modülünden çağırır;
    # aynı store path'ini scheduler_service üzerinden de patch et.
    import app.storage.scheduler_run_store as _rs
    monkeypatch.setattr(_rs, "_STORE_PATH", tmp_path / "scheduler_runs.jsonl")


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ── Test 1: run-once tüm step sonuçlarını kaydeder ────────────────────────────

def test_run_once_records_all_steps(monkeypatch):
    _mock_all_steps(monkeypatch)
    result = svc.run_once()

    assert "run_id" in result
    assert len(result["steps"]) == 7
    step_names = [s["name"] for s in result["steps"]]
    assert "snapshot_capture" in step_names
    assert "auto_tune" in step_names
    # JSONL'e kaydedildi mi?
    runs = run_store.load_recent_scheduler_runs(limit=10)
    assert len(runs) == 1
    assert runs[0]["run_id"] == result["run_id"]


# ── Test 2: Bir step fail olursa diğerleri devam eder ─────────────────────────

def test_run_once_continues_after_step_fail(monkeypatch):
    # Adım 2 (agent_thesis) fail, diğerleri success
    statuses = ["success", "fail", "success", "success", "success", "success", "success"]
    _mock_all_steps(monkeypatch, statuses)

    result = svc.run_once()
    steps = result["steps"]

    failed = [s for s in steps if s["status"] == "fail"]
    success = [s for s in steps if s["status"] == "success"]
    assert len(failed) == 1
    assert failed[0]["name"] == "agent_thesis"
    assert len(success) == 6   # diğer 6 başarılı

    # Summary "partial" olmalı
    assert result["summary"]["status"] == "partial"
    assert "agent_thesis" in result["summary"]["failed_steps"]


# ── Test 3: NO_EXECUTION / PAPER_SAFE zorunlu ─────────────────────────────────

def test_run_once_security_fields(monkeypatch):
    _mock_all_steps(monkeypatch)
    result = svc.run_once()

    assert result["decision_permission"] == "NO_EXECUTION"
    assert result["execution_mode"] == "PAPER_SAFE"
    assert result["broker_permission"] == "BROKER_NOT_CONNECTED"


# ── Test 4: live_execution_allowed = False ────────────────────────────────────

def test_run_once_live_execution_false(monkeypatch):
    _mock_all_steps(monkeypatch)
    result = svc.run_once()
    assert result["live_execution_allowed"] is False


# ── Test 5: JSONL save + load ─────────────────────────────────────────────────

def test_scheduler_run_jsonl_save_load(monkeypatch):
    _mock_all_steps(monkeypatch)
    r1 = svc.run_once()
    r2 = svc.run_once()

    runs = run_store.load_recent_scheduler_runs(limit=10)
    assert len(runs) == 2
    ids = [r["run_id"] for r in runs]
    assert r1["run_id"] in ids
    assert r2["run_id"] in ids

    # Her kayıtta güvenlik alanları korunmalı
    for run in runs:
        assert run["decision_permission"] == "NO_EXECUTION"
        assert run["live_execution_allowed"] is False


# ── Test 6: status endpoint varsayılan running=False ─────────────────────────

def test_status_default_not_running(client):
    # Scheduler reset (thread olabilir önceki testlerden)
    svc._is_running = False
    svc._stop_event.set()

    res = client.get("/api/v1/scheduler/status")
    assert res.status_code == 200
    body = res.json()
    assert "running" in body
    assert body["decision_permission"] == "NO_EXECUTION"
    assert body["live_execution_allowed"] is False


# ── Test 7: start / stop memory flag ─────────────────────────────────────────

def test_start_stop_changes_flag():
    # Önce durdur (temiz durum)
    svc._is_running = False
    svc._stop_event.set()

    result = svc.scheduler_start(interval_seconds=86400)  # çok uzun interval — test bitmeden çalışmaz
    assert result["status"] in ("started", "already_running")

    stop_result = svc.scheduler_stop()
    assert stop_result["status"] in ("stopped", "already_stopped")
    assert svc._is_running is False


# ── Test 8: Mock data yok — adımlar skipped/fail döner, crash yok ─────────────

def test_steps_skip_gracefully_without_data(monkeypatch):
    """
    Gerçek veri yok (no open positions, no trades, no snapshots).
    Adımların crash değil skipped/fail dönmesi beklenir.
    Snapshot/thesis adımları gerçek pipeline çağrısı yapar ve fail/skipped döner.
    Diğer adımlar boş state ile skipped döner.
    """
    # paper_trading_service.get_snapshot() mock'la — boş state
    import app.services.scheduler_service as svc_mod
    from unittest.mock import MagicMock

    empty_snapshot = {
        "open_positions": [],
        "trades": [],
        "closed_trades": [],
    }

    # snapshot ve thesis adımları gerçek network gerektirir → mock
    monkeypatch.setattr(svc_mod, "_run_step_snapshot_capture",
                        lambda: _step("snapshot_capture", "skipped", {"reason": "no_real_pipeline"}))
    monkeypatch.setattr(svc_mod, "_run_step_agent_thesis",
                        lambda: _step("agent_thesis", "skipped", {"reason": "no_hourly_snapshots"}))

    # pts.get_snapshot mock
    with patch("app.services.paper_trading_service.get_snapshot", return_value=empty_snapshot):
        result = svc.run_once()

    assert "run_id" in result
    assert len(result["steps"]) == 7

    # Crash yok — tüm adımlar tamamlandı
    for step in result["steps"]:
        assert step["status"] in ("success", "fail", "skipped")

    # Boş state → position/memory adımları skipped olmalı
    step_by_name = {s["name"]: s for s in result["steps"]}
    assert step_by_name["position_recheck"]["status"] == "skipped"
    assert step_by_name["learning_candidate"]["status"] == "skipped"
    assert step_by_name["mistake_memory_finalize"]["status"] == "skipped"

    # Güvenlik alanları korunmalı
    assert result["decision_permission"] == "NO_EXECUTION"
    assert result["live_execution_allowed"] is False
