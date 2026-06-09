"""
FAZ 1.6 — hourly_snapshots endpoint testleri.

KURAL: POST /capture için gerçek pipeline başarısız olursa not_saved beklenir.
Mock pipeline başarısı ile sentetik market data oluşturulmaz.

Kapsam:
  • GET  /recent — boş / dolu / limit parametresi
  • POST /capture — pipeline exception → not_saved
  • POST /capture — pipeline kısmi çıktı (None fields) → not_saved
  • POST /capture — güvenlik başlıkları (security constants)
"""
from __future__ import annotations

import importlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ── TestClient ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Store izolasyonu ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_store(tmp_path, monkeypatch):
    """Her test kendi geçici JSONL dosyasını kullanır."""
    import app.storage.hourly_snapshot_store as store_mod
    p = tmp_path / "test_hourly_snapshots.jsonl"
    monkeypatch.setattr(store_mod, "_STORE_PATH", p)
    # hourly_snapshots API modülü store'u doğrudan import ettiğinden
    # modül içindeki referansları da yenile
    import app.api.hourly_snapshots as api_mod
    from app.storage import hourly_snapshot_store as store_mod2
    monkeypatch.setattr(api_mod, "save_hourly_snapshot", store_mod2.save_hourly_snapshot)
    monkeypatch.setattr(api_mod, "load_recent_hourly_snapshots", store_mod2.load_recent_hourly_snapshots)
    yield p


# ── GET /recent ───────────────────────────────────────────────────────────────

def test_recent_empty_when_no_snapshots(client):
    resp = client.get("/api/v1/hourly-snapshots/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["count"] == 0
    assert body["snapshots"] == []


def test_recent_returns_saved_records(client, _isolate_store):
    """Store'a doğrudan 2 kayıt ekle → /recent 2 döndürmeli."""
    from app.storage.hourly_snapshot_store import save_hourly_snapshot
    _minimal = {
        "report": {"regime": "NEUTRAL"},
        "rotation": {"primary_flow": "BTC"},
        "mtf": {"BTCUSD": {}},
        "paper_trading": {"open_positions": []},
        "data_quality": {"quality_score": 80},
    }
    save_hourly_snapshot(_minimal)
    save_hourly_snapshot(_minimal)

    resp = client.get("/api/v1/hourly-snapshots/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["snapshots"]) == 2


def test_recent_limit_query_param(client, _isolate_store):
    """10 kayıt ekle, limit=3 ile istek at → 3 döner."""
    from app.storage.hourly_snapshot_store import save_hourly_snapshot
    _minimal = {
        "report": {}, "rotation": {}, "mtf": {},
        "paper_trading": {}, "data_quality": {},
    }
    for _ in range(10):
        save_hourly_snapshot(_minimal)

    resp = client.get("/api/v1/hourly-snapshots/recent?limit=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    assert len(body["snapshots"]) == 3


def test_recent_limit_clamped_to_max(client, _isolate_store):
    """limit=999 → _MAX_LIMIT (200) ile kısıtlanmalı; crash olmamalı."""
    resp = client.get("/api/v1/hourly-snapshots/recent?limit=999")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_recent_records_have_schema_version(client, _isolate_store):
    from app.storage.hourly_snapshot_store import save_hourly_snapshot
    save_hourly_snapshot({
        "report": {}, "rotation": {}, "mtf": {},
        "paper_trading": {}, "data_quality": {},
    })
    resp = client.get("/api/v1/hourly-snapshots/recent")
    records = resp.json()["snapshots"]
    assert records[0]["schema_version"] == "hourly_snapshot_v1"


# ── POST /capture — not_saved senaryoları ─────────────────────────────────────

def test_capture_not_saved_when_pipeline_raises(client, monkeypatch):
    """_build_pipeline exception atar → not_saved döner."""
    import app.api.hourly_snapshots as api_mod

    def _raise_pipeline():
        raise RuntimeError("simulated provider timeout")

    monkeypatch.setattr(api_mod, "_build_pipeline", _raise_pipeline)

    resp = client.post("/api/v1/hourly-snapshots/capture")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_saved"
    assert body["reason"] == "real_pipeline_data_unavailable"


def test_capture_not_saved_when_all_pipeline_outputs_none(client, monkeypatch):
    """_build_pipeline (None, None, None, []) döner → not_saved."""
    import app.api.hourly_snapshots as api_mod

    def _none_pipeline():
        return (None, None, None, [])

    monkeypatch.setattr(api_mod, "_build_pipeline", _none_pipeline)

    resp = client.post("/api/v1/hourly-snapshots/capture")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_saved"
    assert body["reason"] == "real_pipeline_data_unavailable"
    assert "report" in body["missing"]
    assert "rotation" in body["missing"]
    assert "mtf" in body["missing"]


def test_capture_not_saved_when_rotation_missing(client, monkeypatch):
    """report var, rotation None → not_saved (üçü birden zorunlu)."""
    import app.api.hourly_snapshots as api_mod

    class _FakeReport:
        pass

    def _partial_pipeline():
        return (_FakeReport(), None, None, [])

    monkeypatch.setattr(api_mod, "_build_pipeline", _partial_pipeline)

    resp = client.post("/api/v1/hourly-snapshots/capture")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_saved"
    assert "rotation" in body["missing"]


def test_capture_not_saved_when_mtf_empty_dict(client, monkeypatch):
    """mtf boş dict → falsy → not_saved."""
    import app.api.hourly_snapshots as api_mod

    class _FakeReport:
        pass

    class _FakeRotation:
        pass

    def _empty_mtf_pipeline():
        return (_FakeReport(), _FakeRotation(), {}, [])

    monkeypatch.setattr(api_mod, "_build_pipeline", _empty_mtf_pipeline)

    resp = client.post("/api/v1/hourly-snapshots/capture")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_saved"
    assert "mtf" in body["missing"]


def test_capture_not_saved_when_report_none_only(client, monkeypatch):
    """rotation + mtf var, report None → not_saved."""
    import app.api.hourly_snapshots as api_mod

    class _FakeRotation:
        pass

    def _no_report_pipeline():
        return (None, _FakeRotation(), {"BTCUSD": {"1h": {}}}, [])

    monkeypatch.setattr(api_mod, "_build_pipeline", _no_report_pipeline)

    resp = client.post("/api/v1/hourly-snapshots/capture")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_saved"
    assert "report" in body["missing"]


# ── POST /capture — güvenlik denetimleri ─────────────────────────────────────

def test_capture_exception_response_has_no_execution_field(client, monkeypatch):
    """
    Pipeline tamamen exception atar; yanıt gövdesinde NO_EXECUTION/PAPER_SAFE
    içeren bir 'saved' yanıtı YOK — çünkü not_saved döndü.
    Bu test, exception durumunda 'saved' yanıtının gönderilmediğini doğrular.
    """
    import app.api.hourly_snapshots as api_mod

    def _fail():
        raise ConnectionError("data provider unreachable")

    monkeypatch.setattr(api_mod, "_build_pipeline", _fail)

    resp = client.post("/api/v1/hourly-snapshots/capture")
    body = resp.json()
    # saved yanıtı gelmemeli
    assert body.get("status") != "saved"
    # snapshot_id olmamalı
    assert "snapshot_id" not in body


def test_capture_no_snapshot_written_on_failure(client, _isolate_store, monkeypatch):
    """Pipeline exception atar → JSONL dosyasına hiçbir kayıt yazılmaz."""
    import app.api.hourly_snapshots as api_mod

    def _fail():
        raise ValueError("no market data")

    monkeypatch.setattr(api_mod, "_build_pipeline", _fail)

    client.post("/api/v1/hourly-snapshots/capture")

    # Store boş kalmalı
    resp = client.get("/api/v1/hourly-snapshots/recent")
    assert resp.json()["count"] == 0
