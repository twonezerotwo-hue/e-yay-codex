"""hourly_snapshot_store — FAZ 1 kayıt altyapısı testleri."""
from __future__ import annotations

import json
import uuid

import pytest

from app.storage.hourly_snapshot_store import (
    _REQUIRED_TOP_FIELDS,
    _SCHEMA_VERSION,
    load_recent_hourly_snapshots,
    save_hourly_snapshot,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def store_path(tmp_path, monkeypatch):
    """Her test için izole geçici JSONL dosyası."""
    import app.storage.hourly_snapshot_store as mod
    p = tmp_path / "hourly_snapshots.jsonl"
    monkeypatch.setattr(mod, "_STORE_PATH", p)
    return p


def _minimal_payload(**overrides) -> dict:
    payload = {
        "report":        {"regime": "NEUTRAL"},
        "rotation":      {"primary_flow": "BTC"},
        "mtf":           {"BTCUSD": {}},
        "paper_trading": {"open_positions": []},
        "data_quality":  {"quality_score": 85},
    }
    payload.update(overrides)
    return payload


# ── 1. Temel kayıt ────────────────────────────────────────────────────────────

def test_save_returns_uuid(store_path):
    sid = save_hourly_snapshot(_minimal_payload())
    assert uuid.UUID(sid)  # geçerli UUID4 formatı


def test_jsonl_single_line_per_record(store_path):
    save_hourly_snapshot(_minimal_payload())
    lines = [l for l in store_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1


def test_jsonl_record_is_valid_json(store_path):
    save_hourly_snapshot(_minimal_payload())
    line = store_path.read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["schema_version"] == _SCHEMA_VERSION


def test_multiple_saves_append_lines(store_path):
    for _ in range(3):
        save_hourly_snapshot(_minimal_payload())
    lines = [l for l in store_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


# ── 2. Zorunlu alan varlığı ───────────────────────────────────────────────────

def test_required_fields_present_in_record(store_path):
    save_hourly_snapshot(_minimal_payload())
    record = json.loads(store_path.read_text(encoding="utf-8").strip())
    for field in ("snapshot_id", "created_at", "schema_version",
                  "decision_permission", "execution_mode"):
        assert field in record, f"Eksik zorunlu alan: {field}"


# ── 3. NO_EXECUTION / PAPER_SAFE zorlaması ───────────────────────────────────

def test_decision_permission_always_no_execution(store_path):
    # Dışarıdan farklı bir değer verilse bile ezilmeli
    payload = _minimal_payload()
    payload["decision_permission"] = "LIVE_TRADING"
    save_hourly_snapshot(payload)
    record = json.loads(store_path.read_text(encoding="utf-8").strip())
    assert record["decision_permission"] == "NO_EXECUTION"


def test_execution_mode_always_paper_safe(store_path):
    payload = _minimal_payload()
    payload["execution_mode"] = "REAL_EXECUTION"
    save_hourly_snapshot(payload)
    record = json.loads(store_path.read_text(encoding="utf-8").strip())
    assert record["execution_mode"] == "PAPER_SAFE"


# ── 4. Eksik alan — crash etmemeli ───────────────────────────────────────────

def test_no_crash_on_missing_report(store_path):
    payload = _minimal_payload()
    del payload["report"]
    sid = save_hourly_snapshot(payload)  # crash olmamalı
    assert sid


def test_no_crash_on_completely_empty_payload(store_path):
    sid = save_hourly_snapshot({})
    assert sid


def test_missing_fields_logged_in_data_quality_notes(store_path):
    payload = _minimal_payload()
    del payload["report"]
    del payload["rotation"]
    save_hourly_snapshot(payload)
    record = json.loads(store_path.read_text(encoding="utf-8").strip())
    notes = record["data_quality"].get("notes", [])
    assert any("missing_fields" in n for n in notes)


def test_no_missing_note_when_all_fields_present(store_path):
    save_hourly_snapshot(_minimal_payload())
    record = json.loads(store_path.read_text(encoding="utf-8").strip())
    notes = record["data_quality"].get("notes", [])
    # Eksik alan notu YOK
    assert not any("missing_fields" in n for n in notes)


# ── 5. load_recent_hourly_snapshots ──────────────────────────────────────────

def test_load_empty_when_file_missing(store_path):
    assert load_recent_hourly_snapshots() == []


def test_load_returns_saved_records(store_path):
    save_hourly_snapshot(_minimal_payload())
    save_hourly_snapshot(_minimal_payload())
    records = load_recent_hourly_snapshots()
    assert len(records) == 2


def test_load_limit_respected(store_path):
    for _ in range(10):
        save_hourly_snapshot(_minimal_payload())
    records = load_recent_hourly_snapshots(limit=3)
    assert len(records) == 3


def test_load_returns_most_recent_when_limited(store_path):
    """limit=2 → son 2 kayıt döner (en yeni sonda)."""
    ids = []
    for _ in range(5):
        ids.append(save_hourly_snapshot(_minimal_payload()))
    records = load_recent_hourly_snapshots(limit=2)
    returned_ids = [r["snapshot_id"] for r in records]
    assert returned_ids == ids[-2:]


def test_load_skips_corrupted_line(store_path, monkeypatch):
    import app.storage.hourly_snapshot_store as mod
    # Bir geçerli + bir bozuk + bir geçerli satır yaz
    store_path.write_text(
        '{"snapshot_id":"a","created_at":"x","schema_version":"v1",'
        '"decision_permission":"NO_EXECUTION","execution_mode":"PAPER_SAFE",'
        '"report":{},"rotation":{},"mtf":{},"paper_trading":{},"data_quality":{}}\n'
        'NOT_VALID_JSON\n'
        '{"snapshot_id":"b","created_at":"y","schema_version":"v1",'
        '"decision_permission":"NO_EXECUTION","execution_mode":"PAPER_SAFE",'
        '"report":{},"rotation":{},"mtf":{},"paper_trading":{},"data_quality":{}}\n',
        encoding="utf-8",
    )
    records = load_recent_hourly_snapshots()
    assert len(records) == 2
    assert records[0]["snapshot_id"] == "a"
    assert records[1]["snapshot_id"] == "b"


# ── 6. Şema sürümü ───────────────────────────────────────────────────────────

def test_schema_version_is_hourly_snapshot_v1(store_path):
    save_hourly_snapshot(_minimal_payload())
    record = json.loads(store_path.read_text(encoding="utf-8").strip())
    assert record["schema_version"] == "hourly_snapshot_v1"
