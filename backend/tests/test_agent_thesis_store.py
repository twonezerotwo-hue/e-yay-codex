"""
FAZ 2 — agent_thesis_store testleri.

Kapsam: save / load / güvenlik zorlaması / bozuk satır toleransı.
Mock market data yok; sadece minimal payload fixture'ları.
"""
from __future__ import annotations

import json
import uuid

import pytest

from app.storage.agent_thesis_store import (
    _SCHEMA_VERSION,
    load_recent_agent_theses,
    save_agent_thesis,
)


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_store(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    monkeypatch.setattr(mod, "_STORE_PATH", tmp_path / "agent_hourly_theses.jsonl")


def _minimal_thesis(**overrides) -> dict:
    t = {
        "market_view":  {"primary_bias": "mixed", "confidence": 0.6},
        "asset_bias":   {"BTCUSD": {"bias": "watch", "reason": "test", "contradictions": []}},
        "paper_trading_context": {
            "permission":     "context_only",
            "can_open_trade": False,
            "reason":         "test",
        },
    }
    t.update(overrides)
    return t


# ── 1. Temel kayıt ────────────────────────────────────────────────────────────

def test_save_returns_valid_uuid(tmp_path):
    tid = save_agent_thesis(_minimal_thesis())
    assert uuid.UUID(tid)


def test_jsonl_one_line_per_record(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    save_agent_thesis(_minimal_thesis())
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1


def test_jsonl_record_is_valid_json(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    save_agent_thesis(_minimal_thesis())
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["schema_version"] == _SCHEMA_VERSION


def test_multiple_saves_append(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    for _ in range(3):
        save_agent_thesis(_minimal_thesis())
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


# ── 2. Güvenlik zorlaması ────────────────────────────────────────────────────

def test_decision_permission_always_no_execution(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    t = _minimal_thesis()
    t["decision_permission"] = "LIVE_TRADING"  # zorla üzerine yazılmalı
    save_agent_thesis(t)
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["decision_permission"] == "NO_EXECUTION"


def test_execution_mode_always_paper_safe(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    t = _minimal_thesis()
    t["execution_mode"] = "REAL_EXECUTION"
    save_agent_thesis(t)
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["execution_mode"] == "PAPER_SAFE"


def test_can_open_trade_always_false(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    t = _minimal_thesis()
    t["paper_trading_context"]["can_open_trade"] = True  # zorla False yapılmalı
    save_agent_thesis(t)
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["paper_trading_context"]["can_open_trade"] is False


def test_permission_always_context_only(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    t = _minimal_thesis()
    t["paper_trading_context"]["permission"] = "execute"  # zorla üzerine yazılmalı
    save_agent_thesis(t)
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["paper_trading_context"]["permission"] == "context_only"


# ── 3. Zorunlu alan varlığı ───────────────────────────────────────────────────

def test_saved_record_has_required_fields(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    save_agent_thesis(_minimal_thesis())
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    for field in (
        "thesis_id", "created_at", "schema_version",
        "decision_permission", "execution_mode",
        "market_view", "asset_bias", "paper_trading_context",
    ):
        assert field in rec, f"Eksik: {field}"


# ── 4. load_recent_agent_theses ──────────────────────────────────────────────

def test_load_empty_when_no_file():
    assert load_recent_agent_theses() == []


def test_load_returns_saved(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    save_agent_thesis(_minimal_thesis())
    save_agent_thesis(_minimal_thesis())
    records = load_recent_agent_theses()
    assert len(records) == 2


def test_load_limit_respected(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    for _ in range(10):
        save_agent_thesis(_minimal_thesis())
    records = load_recent_agent_theses(limit=3)
    assert len(records) == 3


def test_load_returns_most_recent(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    ids = [save_agent_thesis(_minimal_thesis()) for _ in range(5)]
    records = load_recent_agent_theses(limit=2)
    returned = [r["thesis_id"] for r in records]
    assert returned == ids[-2:]


def test_load_skips_corrupt_line(tmp_path, monkeypatch):
    import app.storage.agent_thesis_store as mod
    p = tmp_path / "agent_hourly_theses.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)

    p.write_text(
        '{"thesis_id":"a","created_at":"x","schema_version":"v1",'
        '"decision_permission":"NO_EXECUTION","execution_mode":"PAPER_SAFE",'
        '"market_view":{},"asset_bias":{},'
        '"paper_trading_context":{"can_open_trade":false,"permission":"context_only"}}\n'
        'BOZUK_SATIR\n'
        '{"thesis_id":"b","created_at":"y","schema_version":"v1",'
        '"decision_permission":"NO_EXECUTION","execution_mode":"PAPER_SAFE",'
        '"market_view":{},"asset_bias":{},'
        '"paper_trading_context":{"can_open_trade":false,"permission":"context_only"}}\n',
        encoding="utf-8",
    )
    records = load_recent_agent_theses()
    assert len(records) == 2
    assert records[0]["thesis_id"] == "a"
    assert records[1]["thesis_id"] == "b"
