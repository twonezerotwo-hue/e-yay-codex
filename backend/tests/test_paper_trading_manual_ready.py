"""
Paper Trading — Manuel Açılabilir Kuyruğu (manual_ready_trades) testleri

Kapsam:
  1) reject → pending kaybolur, manual_ready_trades'e taşınır
  2) Aynı (side, fingerprint, primary_tf) sinyali tekrar gelirse SESSIZ block
  3) Aynı side+fingerprint AMA FARKLI primary_tf → 'yinelenen sinyal' yeni pending açar
  4) Aynı pair için yön değişirse → 'yinelenen' alarmı
  5) dismiss_manual_ready: manual_ready listeden çıkar
  6) force_open_manual_ready: pozisyon açar, manual_ready+rejected temizlenir
  7) Pending otomatik açıldığında manual_ready varsa o da temizlenir
  8) snapshot dict'i manual_ready_trades alanı içerir
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

import app.services.paper_trading_service as pts
from app.services.paper_trading_service import (
    ManualReadyTrade,
    PendingOpenOrder,
    RejectedOpenSignal,
    TradingState,
    _is_recurring_signal,
    _clear_rejected_signal_if_changed,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    """Disk state'ini geçici dosyaya yönlendir — test'ler izole."""
    monkeypatch.setattr(pts, "_STATE_PATH", tmp_path / "state.json")
    pts.reset_state()
    return pts._load_state()


def _seed_pending(pair="BTCUSD", side="LONG", fp="btc|risk_on|bullish|65|aligned|touche",
                  tf="1H") -> PendingOpenOrder:
    now = pts._utc_now()
    return PendingOpenOrder(
        pair=pair, side=side,
        requested_at=now.isoformat(),
        execute_at=(now + timedelta(seconds=60)).isoformat(),
        requested_price=60000.0,
        size_usd=25000.0,
        last_signal="BULLISH@65",
        open_signal={"final_score": 65.0, "final_direction": "BULLISH",
                     "primary_tf": tf, "symbol": pair},
        fingerprint=fp,
        atr_value=1500.0,
        primary_tf=tf,
    )


# ── 1. reject taşır ─────────────────────────────────────────────────────────

def test_reject_moves_pending_to_manual_ready(fresh_state):
    st = pts._load_state()
    st.pending_orders["BTCUSD"] = _seed_pending()
    pts._save_state(st)

    ok = pts.reject_pending_open("BTCUSD")
    assert ok is True

    st2 = pts._load_state()
    assert "BTCUSD" not in st2.pending_orders, "pending temizlenmeli"
    assert "BTCUSD" in st2.manual_ready_trades, "manual_ready'ye taşınmalı"
    mr = st2.manual_ready_trades["BTCUSD"]
    assert mr.side == "LONG"
    assert mr.primary_tf == "1H"
    # rejected_signals da kayıt altında olmalı (silent block için)
    assert "BTCUSD" in st2.rejected_signals
    assert st2.rejected_signals["BTCUSD"].primary_tf == "1H"


# ── 2. Aynı sinyal sessiz block ─────────────────────────────────────────────

def test_same_signal_silent_block(fresh_state):
    st = TradingState()
    st.rejected_signals["BTCUSD"] = RejectedOpenSignal(
        pair="BTCUSD", side="LONG",
        fingerprint="fp_a", rejected_at="2026-06-07T00:00:00Z",
        primary_tf="1H",
    )
    blocked = _clear_rejected_signal_if_changed(st, "BTCUSD", "LONG", "fp_a", "1H")
    assert blocked is True, "Aynı side+fp+tf → sessiz block"
    # rejected_signals hâlâ duruyor
    assert "BTCUSD" in st.rejected_signals


# ── 3. Farklı primary_tf → block YOK, yinelenen olur ───────────────────────

def test_different_tf_clears_block(fresh_state):
    st = TradingState()
    st.rejected_signals["BTCUSD"] = RejectedOpenSignal(
        pair="BTCUSD", side="LONG",
        fingerprint="fp_a", rejected_at="ts", primary_tf="1H",
    )
    blocked = _clear_rejected_signal_if_changed(st, "BTCUSD", "LONG", "fp_a", "4H")
    assert blocked is False, "Farklı TF → block kalkmalı"
    # ve rejection temizlenir
    assert "BTCUSD" not in st.rejected_signals


# ── 4. _is_recurring_signal: TF veya side mismatch ──────────────────────────

def test_recurring_signal_tf_mismatch(fresh_state):
    st = TradingState()
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="BULLISH@65", size_usd=25000.0, requested_price=60000.0,
        fingerprint="fp_a", primary_tf="1H",
    )
    # Aynı side LONG ama farklı TF → recurring
    assert _is_recurring_signal(st, "BTCUSD", "LONG", "4H") is True
    # Aynı TF → recurring değil
    assert _is_recurring_signal(st, "BTCUSD", "LONG", "1H") is False
    # Farklı side → recurring
    assert _is_recurring_signal(st, "BTCUSD", "SHORT", "1H") is True
    # manual_ready yok → recurring değil
    st.manual_ready_trades.clear()
    assert _is_recurring_signal(st, "BTCUSD", "LONG", "4H") is False


# ── 5. dismiss_manual_ready ─────────────────────────────────────────────────

def test_dismiss_manual_ready(fresh_state):
    st = pts._load_state()
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="x", size_usd=25000.0, requested_price=60000.0,
        primary_tf="1H",
    )
    pts._save_state(st)

    ok = pts.dismiss_manual_ready("BTCUSD")
    assert ok is True
    st2 = pts._load_state()
    assert "BTCUSD" not in st2.manual_ready_trades

    # ikinci kez → not_found
    assert pts.dismiss_manual_ready("BTCUSD") is False


# ── 6. force_open_manual_ready ──────────────────────────────────────────────

def test_force_open_manual_ready_creates_position(fresh_state):
    st = pts._load_state()
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="BULLISH@65",
        size_usd=25000.0, requested_price=60000.0,
        open_signal={"final_score": 65.0, "final_direction": "BULLISH", "symbol": "BTCUSD"},
        fingerprint="fp_a", atr_value=1500.0, primary_tf="1H",
    )
    st.rejected_signals["BTCUSD"] = RejectedOpenSignal(
        pair="BTCUSD", side="LONG", fingerprint="fp_a",
        rejected_at="t2", primary_tf="1H",
    )
    pts._save_state(st)

    # Piyasa açık varsayalım — BTCUSD 7/24
    result = pts.force_open_manual_ready("BTCUSD", current_price=62000.0)
    assert result["status"] == "opened"
    assert result["price"] == 62000.0

    st2 = pts._load_state()
    assert "BTCUSD" in st2.positions, "Pozisyon oluşmalı"
    assert st2.positions["BTCUSD"].entry_price == 62000.0
    assert st2.positions["BTCUSD"].side == "LONG"
    # manual_ready + rejected temizlenmeli
    assert "BTCUSD" not in st2.manual_ready_trades
    assert "BTCUSD" not in st2.rejected_signals


def test_force_open_manual_ready_not_found(fresh_state):
    result = pts.force_open_manual_ready("BTCUSD", current_price=62000.0)
    assert result["status"] == "not_found"


def test_force_open_manual_ready_no_price(fresh_state):
    st = pts._load_state()
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="x", size_usd=25000.0, requested_price=60000.0,
        primary_tf="1H",
    )
    # last_tick_prices boş
    st.last_tick_prices = {}
    pts._save_state(st)
    result = pts.force_open_manual_ready("BTCUSD")  # current_price=None, no last_tick
    assert result["status"] == "no_price"


# ── 7. Pending otomatik açıldığında manual_ready de temizlenir ─────────────

def test_pending_auto_open_clears_manual_ready(fresh_state):
    st = pts._load_state()
    # Hem pending hem manual_ready olduğunu varsay (köşe durum: yinelenen sinyal kabul edildi)
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="x", size_usd=25000.0, requested_price=60000.0,
        primary_tf="1H",
    )
    pending = _seed_pending()
    pts._open_position_from_pending(st, pending, current_price=62000.0,
                                    opened_at="2026-06-07T00:00:00Z")
    assert "BTCUSD" in st.positions
    assert "BTCUSD" not in st.manual_ready_trades, \
        "Otomatik açılım sonrası manual_ready temizlenmeli"


# ── 8. get_snapshot manual_ready_trades alanı içeriyor ─────────────────────

def test_snapshot_exposes_manual_ready(fresh_state):
    st = pts._load_state()
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="BULLISH@65", size_usd=25000.0, requested_price=60000.0,
        primary_tf="1H",
    )
    st.last_tick_prices = {"BTCUSD": 62000.0}
    pts._save_state(st)

    snap = pts.get_snapshot()
    assert "manual_ready_trades" in snap
    assert len(snap["manual_ready_trades"]) == 1
    item = snap["manual_ready_trades"][0]
    assert item["pair"] == "BTCUSD"
    assert item["side"] == "LONG"
    assert item["primary_tf"] == "1H"
    assert item["current_price"] == 62000.0
    assert "market_open" in item


# ── 9. PendingOpenOrder.is_recurring bayrağı kaydedilip okunur ─────────────

def test_pending_recurring_flag_persists(fresh_state):
    st = pts._load_state()
    pending = _seed_pending()
    pending.is_recurring = True
    st.pending_orders["BTCUSD"] = pending
    pts._save_state(st)

    st2 = pts._load_state()
    assert st2.pending_orders["BTCUSD"].is_recurring is True
    assert st2.pending_orders["BTCUSD"].primary_tf == "1H"


# ── 10. API endpoint smoke — open/dismiss/reject ────────────────────────────

def test_api_endpoints_smoke(fresh_state, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    # Execution mode'u paper_safe için OFF tut — require_paper_safe pass etsin
    monkeypatch.setenv("EXECUTION_MODE", "OFF")

    # State yarat
    st = pts._load_state()
    st.manual_ready_trades["BTCUSD"] = ManualReadyTrade(
        pair="BTCUSD", side="LONG",
        requested_at="t1", rejected_at="t2",
        last_signal="x", size_usd=25000.0, requested_price=60000.0,
        primary_tf="1H",
    )
    st.last_tick_prices = {"BTCUSD": 62000.0}
    pts._save_state(st)

    client = TestClient(app)

    # dismiss
    r = client.post("/api/v1/trading/manual-ready/BTCUSD/dismiss")
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"

    # Tekrar dismiss → not_found
    r = client.post("/api/v1/trading/manual-ready/BTCUSD/dismiss")
    assert r.json()["status"] == "not_found"

    # open: yok → not_found
    r = client.post("/api/v1/trading/manual-ready/BTCUSD/open")
    assert r.json()["status"] == "not_found"

    # Bilinmeyen pair → 400
    r = client.post("/api/v1/trading/manual-ready/UNKNOWN/dismiss")
    # dismiss UNKNOWN pair-validation YOK; not_found döner
    assert r.status_code == 200
