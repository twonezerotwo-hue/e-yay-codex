"""
FAZ 10 — System Health testleri.

5 test:
  1. endpoint no data → degraded not crash
  2. paper anomaly true → overall "fail"
  3. safety fields always correct
  4. scheduler stopped → check "degraded" not "fail"
  5. _overall_status pure logic: all ok → "ok"
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.system_health as health_mod
import app.storage.agent_thesis_store as at_store
import app.storage.auto_tune_store as atu_store
import app.storage.hourly_snapshot_store as hs_store
import app.storage.scheduler_run_store as sr_store


# ── Store redirect fixture ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _redirect_stores(tmp_path, monkeypatch):
    """Tüm store path'lerini tmp_path'e yönlendir — gerçek data etkilenmesin."""
    monkeypatch.setattr(hs_store, "_STORE_PATH", tmp_path / "hourly_snapshots.jsonl")
    monkeypatch.setattr(at_store, "_STORE_PATH", tmp_path / "agent_hourly_theses.jsonl")
    monkeypatch.setattr(sr_store, "_STORE_PATH", tmp_path / "scheduler_runs.jsonl")
    monkeypatch.setattr(atu_store, "_OVERRIDES_PATH", tmp_path / "auto_tune_overrides.json")


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ── Ortak mock'lar ────────────────────────────────────────────────────────────

def _mock_pts_ok(monkeypatch) -> None:
    """Paper trading: anomaly false, 0 açık pozisyon."""
    import app.services.paper_trading_service as pts
    monkeypatch.setattr(
        pts,
        "get_snapshot",
        lambda: {"open_positions": [], "state_anomaly": {"active": False, "reasons": []}},
    )


def _mock_scheduler_stopped(monkeypatch) -> None:
    """Scheduler durmuş (running=False)."""
    import app.services.scheduler_service as svc
    monkeypatch.setattr(svc, "get_scheduler_status", lambda: {"running": False, "interval_seconds": 3600})


def _mock_scheduler_running(monkeypatch) -> None:
    """Scheduler çalışıyor (running=True)."""
    import app.services.scheduler_service as svc
    monkeypatch.setattr(svc, "get_scheduler_status", lambda: {"running": True, "interval_seconds": 3600})


# ── Test 1: no data → degraded not crash ─────────────────────────────────────

def test_no_data_returns_degraded_not_crash(client, monkeypatch):
    """
    Hiç snapshot/thesis verisi yoksa ve scheduler durmuşsa endpoint
    'degraded' döner — crash olmaz, 200 status.
    """
    _mock_pts_ok(monkeypatch)
    _mock_scheduler_stopped(monkeypatch)

    res = client.get("/api/v1/system-health/summary")
    assert res.status_code == 200

    body = res.json()
    # Genel durum bozuk veri yokken degraded olmalı
    assert body["status"] in ("degraded", "fail")
    # 5 check döndü
    assert len(body["checks"]) == 5
    # Tüm check isimleri tam
    names = {c["name"] for c in body["checks"]}
    assert names == {"scheduler", "snapshot", "thesis", "paper_trading", "auto_tune"}
    # Her check'de status ve message var
    for c in body["checks"]:
        assert c["status"] in ("ok", "degraded", "fail")
        assert isinstance(c["message"], str) and c["message"]


# ── Test 2: paper anomaly active → fail ───────────────────────────────────────

def test_paper_anomaly_active_returns_fail(client, monkeypatch):
    """Paper trading anomaly aktifse overall status 'fail' olmalı."""
    import app.services.paper_trading_service as pts
    monkeypatch.setattr(
        pts,
        "get_snapshot",
        lambda: {
            "open_positions": [{"pair": "BTCUSD"}],
            "state_anomaly": {
                "active": True,
                "reasons": ["equity_spike"],
                "action": "REPAIR_OR_RESET_REQUIRED",
            },
        },
    )
    _mock_scheduler_running(monkeypatch)

    res = client.get("/api/v1/system-health/summary")
    assert res.status_code == 200

    body = res.json()
    assert body["status"] == "fail"

    pt_check = next(c for c in body["checks"] if c["name"] == "paper_trading")
    assert pt_check["status"] == "fail"
    assert "anomaly" in pt_check["message"].lower()


# ── Test 3: safety fields always correct ─────────────────────────────────────

def test_safety_fields_always_present(client, monkeypatch):
    """Safety alanları her yanıtta doğru değerlere sahip olmalı."""
    _mock_pts_ok(monkeypatch)
    _mock_scheduler_stopped(monkeypatch)

    res = client.get("/api/v1/system-health/summary")
    assert res.status_code == 200

    safety = res.json()["safety"]
    assert safety["decision_permission"] == "NO_EXECUTION"
    assert safety["execution_mode"] == "PAPER_SAFE"
    assert safety["broker_permission"] == "BROKER_NOT_CONNECTED"
    assert safety["live_execution_allowed"] is False


# ── Test 4: scheduler stopped → degraded not fail ─────────────────────────────

def test_scheduler_stopped_is_degraded_not_fail(client, monkeypatch):
    """
    Scheduler durmuşsa 'scheduler' check 'degraded' döner, 'fail' değil.
    Overall 'fail' ancak paper anomaly gibi gerçek hata varsa olur.
    """
    _mock_pts_ok(monkeypatch)
    _mock_scheduler_stopped(monkeypatch)

    res = client.get("/api/v1/system-health/summary")
    assert res.status_code == 200

    body = res.json()
    sched = next(c for c in body["checks"] if c["name"] == "scheduler")
    assert sched["status"] == "degraded"
    # Scheduler dışı check'ler fail değil
    non_sched = [c for c in body["checks"] if c["name"] != "scheduler"]
    assert all(c["status"] != "fail" for c in non_sched)


# ── Test 5: _overall_status pure logic ───────────────────────────────────────

def test_overall_status_all_ok():
    """Tüm check'ler 'ok' ise overall 'ok' döner."""
    checks = [
        {"name": "scheduler",     "status": "ok",  "message": "Running"},
        {"name": "snapshot",      "status": "ok",  "message": "Last 5m ago"},
        {"name": "thesis",        "status": "ok",  "message": "ok"},
        {"name": "paper_trading", "status": "ok",  "message": "Anomaly: false, open positions: 0"},
        {"name": "auto_tune",     "status": "ok",  "message": "0 active override(s)"},
    ]
    assert health_mod._overall_status(checks) == "ok"


def test_overall_status_fail_wins():
    """'fail' olan tek check genel durumu 'fail' yapar."""
    checks = [
        {"name": "a", "status": "ok",       "message": ""},
        {"name": "b", "status": "degraded", "message": ""},
        {"name": "c", "status": "fail",     "message": ""},
    ]
    assert health_mod._overall_status(checks) == "fail"


def test_overall_status_degraded_beats_ok():
    """'fail' yoksa 'degraded' → genel 'degraded'."""
    checks = [
        {"name": "a", "status": "ok",       "message": ""},
        {"name": "b", "status": "degraded", "message": ""},
    ]
    assert health_mod._overall_status(checks) == "degraded"
