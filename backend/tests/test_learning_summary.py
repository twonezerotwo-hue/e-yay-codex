"""
FAZ 8 — Learning Summary endpoint testleri.

6 test:
  1. Tüm store boşken endpoint çalışır (null fields döner)
  2. Güvenlik alanları her zaman mevcuttur
  3. Calibration varsa özet doğru doldurulur
  4. Active overrides doğru listeye dönüştürülür
  5. Latest memory summary doğru çıkarılır
  6. Override yoksa active_overrides boş liste döner (null DEĞİL)
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.storage.auto_tune_store as at_store
import app.storage.mistake_memory_store as mm_store
import app.storage.weekly_calibration_store as wc_store


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _redirect_stores(tmp_path, monkeypatch):
    """Tüm store path'lerini geçici dizine yönlendir."""
    monkeypatch.setattr(wc_store, "_STORE_PATH", tmp_path / "weekly_calibrations.jsonl")
    monkeypatch.setattr(at_store, "_ADJ_STORE_PATH", tmp_path / "auto_tune_adjustments.jsonl")
    monkeypatch.setattr(at_store, "_OVERRIDES_PATH", tmp_path / "auto_tune_overrides.json")
    monkeypatch.setattr(mm_store, "_STORE_PATH", tmp_path / "mistake_memory.jsonl")


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_calibration(tmp_path: Path) -> str:
    """Geçerli bir calibration kaydı yazar ve calibration_id döndürür."""
    cal_id = str(uuid.uuid4())
    record = {
        "calibration_id": cal_id,
        "created_at": _utc_now(),
        "schema_version": "weekly_calibration_v1",
        "lookback_days": 7,
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_SAFE",
        "auto_changes_allowed": False,
        "sample": {
            "trades": 15,
            "memories": 8,
            "evidence_quality": "full",
        },
        "performance": {
            "win_rate": 0.60,
            "profit_factor": 1.45,
            "expectancy_usd": 62.50,
        },
        "auto_tune_candidates": [],
    }
    path = tmp_path / "weekly_calibrations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    return cal_id


def _write_memory(tmp_path: Path) -> str:
    """Geçerli bir mistake memory kaydı yazar ve memory_id döndürür."""
    mem_id = str(uuid.uuid4())
    record = {
        "memory_id": mem_id,
        "created_at": _utc_now(),
        "schema_version": "mistake_memory_v1",
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_SAFE",
        "record_type": "final_memory",
        "is_final": True,
        "source_trade_fingerprint": "fp_test",
        "trade": {"pair": "XAUUSD", "verdict": "LOSS"},
        "opening_context": {},
        "candidate_evidence": {},
        "recheck_evidence": {},
        "final_labels": [
            {"code": "bearish_pattern_ignored_confirmed", "type": "mistake", "severity": "high",
             "reason": "Pattern tespit edildi ama giriş yapıldı"},
        ],
        "final_summary": {
            "result": "loss",
            "main_lesson": "Pattern tespit edildi ama giriş yapıldı",
            "should_adjust_weights": True,
            "recommended_review": "pattern_weight",
        },
    }
    path = tmp_path / "mistake_memory.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    return mem_id


def _write_overrides(tmp_path: Path) -> None:
    """Geçerli bir overrides.json yazar."""
    data = {
        "schema_version": "auto_tune_overrides_v1",
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_SAFE",
        "broker_permission": "BROKER_NOT_CONNECTED",
        "live_execution_allowed": False,
        "updated_at": _utc_now(),
        "overrides": {
            "position_size_multiplier": {
                "LONG + pattern_bearish": 0.85,
            },
        },
    }
    path = tmp_path / "auto_tune_overrides.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ── Test 1: Tüm store boşken endpoint çalışır ────────────────────────────────

def test_summary_empty_stores(client):
    res = client.get("/api/v1/learning/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["latest_calibration"] is None
    assert body["latest_adjustment"] is None
    assert body["latest_memory"] is None
    assert isinstance(body["active_overrides"], list)
    assert len(body["active_overrides"]) == 0


# ── Test 2: Güvenlik alanları her zaman mevcuttur ────────────────────────────

def test_summary_safety_fields_always_present(client):
    res = client.get("/api/v1/learning/summary")
    assert res.status_code == 200
    safety = res.json()["safety"]
    assert safety["decision_permission"] == "NO_EXECUTION"
    assert safety["execution_mode"] == "PAPER_SAFE"
    assert safety["broker_permission"] == "BROKER_NOT_CONNECTED"
    assert safety["live_execution_allowed"] is False
    assert "override_scope" in safety


# ── Test 3: Calibration varsa özet doğru doldurulur ──────────────────────────

def test_summary_calibration_populated(tmp_path, client):
    cal_id = _write_calibration(tmp_path)
    res = client.get("/api/v1/learning/summary")
    assert res.status_code == 200
    cal = res.json()["latest_calibration"]
    assert cal is not None
    assert cal["calibration_id"] == cal_id
    assert cal["performance"]["win_rate"] == pytest.approx(0.60)
    assert cal["performance"]["profit_factor"] == pytest.approx(1.45)
    assert cal["performance"]["expectancy_usd"] == pytest.approx(62.50)
    assert cal["evidence_quality"] == "full"


# ── Test 4: Active overrides doğru listeye dönüştürülür ──────────────────────

def test_summary_active_overrides(tmp_path, client):
    _write_overrides(tmp_path)
    res = client.get("/api/v1/learning/summary")
    assert res.status_code == 200
    overrides = res.json()["active_overrides"]
    assert len(overrides) == 1
    ov = overrides[0]
    assert ov["target"] == "position_size_multiplier"
    assert ov["condition"] == "LONG + pattern_bearish"
    assert ov["value"] == pytest.approx(0.85)
    assert ov["last_updated"] is not None


# ── Test 5: Latest memory summary doğru çıkarılır ────────────────────────────

def test_summary_memory_populated(tmp_path, client):
    mem_id = _write_memory(tmp_path)
    res = client.get("/api/v1/learning/summary")
    assert res.status_code == 200
    mem = res.json()["latest_memory"]
    assert mem is not None
    assert mem["memory_id"] == mem_id
    assert mem["pair"] == "XAUUSD"
    assert mem["result"] == "LOSS"
    assert "bearish_pattern_ignored_confirmed" in mem["final_labels"]
    assert "Pattern tespit edildi" in mem["main_lesson"]


# ── Test 6: Override yoksa active_overrides boş liste döner ──────────────────

def test_summary_no_overrides_returns_empty_list(client):
    """Override dosyası yokken active_overrides null değil [] olmalı."""
    res = client.get("/api/v1/learning/summary")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["active_overrides"], list)
    assert body["active_overrides"] == []
