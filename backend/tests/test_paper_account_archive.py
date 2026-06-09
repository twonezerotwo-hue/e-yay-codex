"""
Paper Account Archive testleri.

Kapsam:
  1. archive_and_finalize_paper_state: arşiv dosyası oluşur
  2. Kapalı trade'ler finalize edilir
  3. Duplicate finalize yapılmaz
  4. archive_finalize_and_reset: balance/equity 100k, pnl 0, trades 0
  5. weight_adjustments / training_history korunur
  6. Korunan JSONL dosyaları silinmez
  7. Boş trade listesiyle arşiv yine de oluşur
  8. Hata durumunda arşiv yazımı graceful
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from app.services.paper_account_archive import (
    archive_and_finalize_paper_state,
    _ARCHIVE_DIR,
    _PROTECTED_FILES,
)


# ── Yardımcı fixture ─────────────────────────────────────────────────────────

def _make_closed_trade(pair="BTCUSD", trade_id=1, pnl_pct=-2.0):
    return {
        "id":          trade_id,
        "pair":        pair,
        "side":        "LONG",
        "entry_price": 100.0,
        "exit_price":  98.0,
        "entry_at":    "2026-01-01T10:00:00+00:00",
        "exit_at":     "2026-01-01T12:00:00+00:00",
        "pnl_pct":     pnl_pct,
        "pnl_usd":     -200.0,
        "reason":      "SL",
        "open_signal": {},
    }


def _make_snapshot(trades=None):
    return {
        "balance":           100_000.0,
        "equity":            99_000.0,
        "realized_pnl_usd":  -1_000.0,
        "open_positions":    [],
        "trades":            trades or [],
        "pending_orders":    {},
        "manual_ready_trades": {},
    }


# ── 1. Arşiv dosyası oluşur ──────────────────────────────────────────────────

def test_archive_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.paper_account_archive._ARCHIVE_DIR", tmp_path)
    # Finalize mock — sadece dosya yazmayı test ediyoruz
    monkeypatch.setattr(
        "app.services.paper_account_archive._finalize_closed_trades",
        lambda trades: {"finalized": 0, "skipped": 0, "failed": 0, "memory_ids": []},
    )
    snap = _make_snapshot()
    result = archive_and_finalize_paper_state(snap, reason="test_archive")

    assert "archive_path" in result
    archive_file = Path(result["archive_path"])
    assert archive_file.exists()
    content = json.loads(archive_file.read_text(encoding="utf-8"))
    assert content["archive_reason"] == "test_archive"
    assert content["execution_mode"] == "PAPER_SAFE"
    assert content["decision_permission"] == "NO_EXECUTION"
    assert "state_snapshot" in content


# ── 2. Trade finalize ─────────────────────────────────────────────────────────

def test_archive_finalizes_closed_trades(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.paper_account_archive._ARCHIVE_DIR", tmp_path)
    finalize_calls = []

    def _fake_finalize(trades):
        finalize_calls.append(len(trades))
        return {"finalized": len(trades), "skipped": 0, "failed": 0, "memory_ids": ["mid1"]}

    monkeypatch.setattr(
        "app.services.paper_account_archive._finalize_closed_trades",
        _fake_finalize,
    )
    snap = _make_snapshot(trades=[_make_closed_trade(trade_id=1), _make_closed_trade(trade_id=2)])
    result = archive_and_finalize_paper_state(snap)

    assert finalize_calls == [2]
    assert result["finalize_result"]["finalized"] == 2


# ── 3. Duplicate finalize yapılmaz ────────────────────────────────────────────

def test_no_duplicate_finalize(tmp_path, monkeypatch):
    """load_finalized_fingerprints() mevcut fingerprint döndürürse skip."""
    monkeypatch.setattr("app.services.paper_account_archive._ARCHIVE_DIR", tmp_path)

    trade = _make_closed_trade(trade_id=99)

    # Fingerprint = "tid_99" (trade id'den)
    from app.services.mistake_memory_service import _trade_fingerprint
    fp = _trade_fingerprint(trade)

    monkeypatch.setattr(
        "app.storage.mistake_memory_store.load_finalized_fingerprints",
        lambda: {fp},
    )
    monkeypatch.setattr(
        "app.storage.learning_candidate_store.load_recent_learning_candidates",
        lambda limit=50: [],
    )
    monkeypatch.setattr(
        "app.storage.position_recheck_store.load_recent_position_rechecks",
        lambda limit=50: [],
    )

    snap = _make_snapshot(trades=[trade])
    result = archive_and_finalize_paper_state(snap)

    assert result["finalize_result"]["skipped"] == 1
    assert result["finalize_result"]["finalized"] == 0


# ── 4. archive_finalize_and_reset: state temizlenir ──────────────────────────

def test_archive_finalize_and_reset_clears_state(tmp_path, monkeypatch):
    """Reset sonrası balance=100k, pnl=0, trades=0 — disk'e yazma mock."""
    import app.services.paper_trading_service as pts

    saved_states: list = []

    # Arşiv + finalize mock
    monkeypatch.setattr(
        "app.services.paper_account_archive.archive_and_finalize_paper_state",
        lambda snap, reason="": {
            "archive_path": str(tmp_path / "arc.json"),
            "finalize_result": {"finalized": 0, "skipped": 0, "failed": 0, "memory_ids": []},
            "protected_files": [],
            "decision_permission": "NO_EXECUTION",
            "execution_mode": "PAPER_SAFE",
        },
    )
    # Disk yazımını mock — gerçek state dosyasını değiştirme
    monkeypatch.setattr(pts, "_save_state", lambda st: saved_states.append(st))

    result = pts.archive_finalize_and_reset(reason="test_reset")

    assert result["status"] == "archived_and_reset"
    assert result["starting_balance"] == 100_000.0
    assert result["equity"] == 100_000.0
    assert result["realized_pnl_usd"] == 0.0
    assert result["open_positions"] == 0
    assert result["trade_count"] == 0
    assert result["state_anomaly_active"] is False
    assert result["decision_permission"] == "NO_EXECUTION"
    assert result["execution_mode"] == "PAPER_SAFE"
    # Disk'e bir kez yazıldı
    assert len(saved_states) == 1
    fresh = saved_states[0]
    assert len(fresh.trades) == 0
    assert len(fresh.positions) == 0
    assert fresh.realized_pnl_usd == 0.0


# ── 5. weight_adjustments / training_history korunur ─────────────────────────

def test_weight_adjustments_preserved_after_reset(tmp_path, monkeypatch):
    import app.services.paper_trading_service as pts
    from app.services.paper_trading_service import TradingState

    saved_states: list = []

    # Fake load — custom weights içeren state
    fake_st = TradingState()
    fake_st.weight_adjustments = {"BTCUSD": 1.25}
    fake_st.training_history = [{"trained_at": "2026-01-01"}]
    monkeypatch.setattr(pts, "_load_state", lambda: fake_st)

    monkeypatch.setattr(
        "app.services.paper_account_archive.archive_and_finalize_paper_state",
        lambda snap, reason="": {
            "archive_path": str(tmp_path / "arc.json"),
            "finalize_result": {"finalized": 0, "skipped": 0, "failed": 0, "memory_ids": []},
            "protected_files": [],
            "decision_permission": "NO_EXECUTION",
            "execution_mode": "PAPER_SAFE",
        },
    )
    monkeypatch.setattr(pts, "_save_state", lambda st: saved_states.append(st))

    pts.archive_finalize_and_reset(reason="preserve_test")

    assert len(saved_states) == 1
    fresh = saved_states[0]
    assert fresh.weight_adjustments.get("BTCUSD") == 1.25
    assert len(fresh.training_history) == 1


# ── 6. Korunan dosyalar listede ──────────────────────────────────────────────

def test_protected_files_in_result(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.paper_account_archive._ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.paper_account_archive._finalize_closed_trades",
        lambda trades: {"finalized": 0, "skipped": 0, "failed": 0, "memory_ids": []},
    )
    result = archive_and_finalize_paper_state(_make_snapshot())
    protected = result["protected_files"]
    assert "mistake_memory.jsonl" in protected
    assert "learning_candidates.jsonl" in protected
    assert "auto_tune_overrides.json" in protected


# ── 7. Boş trade listesiyle arşiv yine de oluşur ─────────────────────────────

def test_archive_with_no_trades(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.paper_account_archive._ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.paper_account_archive._finalize_closed_trades",
        lambda trades: {"finalized": 0, "skipped": 0, "failed": 0, "memory_ids": []},
    )
    result = archive_and_finalize_paper_state(_make_snapshot(trades=[]))
    assert Path(result["archive_path"]).exists()
    assert result["finalize_result"]["finalized"] == 0
