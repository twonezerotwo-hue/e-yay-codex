"""
Similar Trade Memory testleri.

1. memory yoksa available=False
2. benzer memory varsa matches/wins/losses doğru
3. pair eşleşmesi olmayan kayıtlar match sayılmaz
4. open_signal (signal_snapshot) içine similar_memory_context yazılıyor
5. find_similar exception içmez (store erişilemiyor)
"""
from __future__ import annotations

import pytest
import app.storage.mistake_memory_store as mm_store
import app.services.similar_trade_memory as svc


@pytest.fixture(autouse=True)
def _redirect(tmp_path, monkeypatch):
    monkeypatch.setattr(mm_store, "_STORE_PATH", tmp_path / "mistake_memory.jsonl")


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _make_record(pair="BTCUSD", side="LONG", pnl_pct=1.5, labels=None,
                 primary_tf="1h", confluence="STRONG", pattern_bias="bullish"):
    return {
        "trade": {"pair": pair, "side": side, "pnl_pct": pnl_pct},
        "opening_context": {
            "pair": pair, "side": side,
            "primary_tf": primary_tf,
            "confluence_status": confluence,
            "pattern_bias": pattern_bias,
        },
        "final_labels": labels or [],
    }


# ── Test 1: memory yoksa available=False ──────────────────────────────────────

def test_no_memory_returns_unavailable():
    result = svc.find_similar_trade_memories({}, pair="BTCUSD", side="LONG")
    assert result["available"] is False
    assert result["matches"] == 0


# ── Test 2: benzer memory — matches/wins/losses doğru ────────────────────────

def test_similar_memory_found():
    mm_store.save_mistake_memory(_make_record(pair="BTCUSD", side="LONG", pnl_pct=2.0,
                                              labels=["bullish_confirmed"]))
    mm_store.save_mistake_memory(_make_record(pair="BTCUSD", side="LONG", pnl_pct=-1.5,
                                              labels=["bullish_confirmed"]))
    sig = {"primary_tf": "1h", "confluence_status": "STRONG", "pattern_bias": "bullish"}
    result = svc.find_similar_trade_memories(sig, pair="BTCUSD", side="LONG")
    assert result["available"] is True
    assert result["matches"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["avg_pnl_pct"] == pytest.approx(0.25, abs=0.01)
    assert "bullish_confirmed" in result["common_labels"]


# ── Test 3: farklı pair match sayılmaz ───────────────────────────────────────

def test_different_pair_not_matched():
    # ETHUSD kaydı — BTCUSD sinyaline benzer sayılmamalı (pair mismatch → -3 puan)
    mm_store.save_mistake_memory(_make_record(pair="ETHUSD", side="LONG", pnl_pct=1.0))
    sig = {"primary_tf": "1h", "confluence_status": "STRONG", "pattern_bias": "bullish"}
    result = svc.find_similar_trade_memories(sig, pair="BTCUSD", side="LONG")
    assert result["available"] is False


# ── Test 4: open_signal içine similar_memory_context yazılıyor ───────────────

def test_similar_memory_injected_into_open_signal(monkeypatch, tmp_path):
    """_route_new_open_signal'ın signal_snapshot'ına similar_memory_context eklendi mi?"""
    import app.services.paper_trading_service as pts
    import app.services.agent_thesis_context as atc

    # store monkeypatch
    monkeypatch.setattr(mm_store, "_STORE_PATH", tmp_path / "mm2.jsonl")
    mm_store.save_mistake_memory(_make_record(pair="XAUUSD", side="SHORT", pnl_pct=-2.0,
                                              labels=["false_breakout"]))

    # thesis context stub
    monkeypatch.setattr(atc, "load_latest_safe_thesis", lambda: None)
    monkeypatch.setattr(atc, "build_thesis_trade_context", lambda pair, thesis: {})

    captured: list[dict] = []

    def _fake_queue(st, *, pair, side, price, size_usd, last_signal,
                    signal_snapshot, fingerprint, now_dt, atr_value,
                    primary_tf, is_recurring):
        captured.append(signal_snapshot)

    monkeypatch.setattr(pts, "_queue_pending_open", _fake_queue)

    # Basit TradingState
    from app.services.paper_trading_service import TradingState
    from datetime import datetime, UTC
    st = TradingState.__new__(TradingState)
    st.pending_orders = {}
    st.manual_ready_trades = {}

    sig = {
        "primary_tf": "1h",
        "confluence_status": "STRONG",
        "pattern_bias": "bearish",
    }
    pts._route_new_open_signal(
        st, pair="XAUUSD", side="SHORT", price=2400.0, size_usd=500.0,
        last_signal="SHORT@0.75", signal_snapshot=sig, fingerprint="fp1",
        now_dt=datetime.now(UTC), atr_value=5.0, primary_tf="1h",
        is_recurring=False, raw_regime="NEUTRAL",
    )

    assert len(captured) == 1
    snap = captured[0]
    assert "similar_memory_context" in snap
    ctx = snap["similar_memory_context"]
    assert ctx["available"] is True
    assert ctx["matches"] >= 1


# ── Test 5: store erişilemiyor — exception içilir ─────────────────────────────

def test_store_unreachable_returns_empty(monkeypatch):
    monkeypatch.setattr(
        mm_store, "load_recent_mistake_memory",
        lambda limit=50: (_ for _ in ()).throw(RuntimeError("disk error")),
    )
    result = svc.find_similar_trade_memories({}, pair="BTCUSD", side="LONG")
    assert result["available"] is False
