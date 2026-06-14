"""Signal chain tracker — gözlemci/etiketleyici katman testleri.

Section-8 mock senaryoları:
  1. BTCUSD LONG 1D            → single_signal (60s)
  2. BTCUSD LONG 1D tekrar     → same_timeframe_duplicate
  3. BTCUSD LONG 4H            → double_timeframe_signal (30s)
  4. BTCUSD LONG 1H            → triple_timeframe_confirmation (auto_open_reason)
  5. XAUUSD LONG 1D + SHORT 4H → timeframe_conflict
  6. cancel edilen 1D + sonra 4H → double olarak tanınır
  7. context_for learning alanlarını doldurur
"""
from __future__ import annotations

import pytest

from app.services import signal_chain_tracker as sct


@pytest.fixture()
def tmp_state(tmp_path, monkeypatch):
    """Her test kendi izole state dosyasıyla başlasın (paper state'e dokunmaz)."""
    path = tmp_path / "signal_chain_state.json"
    monkeypatch.setattr(sct, "_STATE_PATH", path)
    return path


def test_full_chain_single_double_triple(tmp_state):
    # 1) İlk sinyal — single, 60s
    c = sct.observe("BTCUSD", "LONG", "1d", {"1d": "bullish"})
    assert c.signal_level == sct.SINGLE
    assert c.countdown_seconds == 60
    assert c.confirmed_timeframes == ["1d"]
    assert c.auto_open_reason == ""

    # 2) Aynı TF tekrar — duplicate, auto-open yok. Tekrar tekrar gelse de
    #    duplicate_timeframes distinct kalır (sınırsız büyümez); hits sayacı artar.
    for _ in range(3):
        c = sct.observe("BTCUSD", "LONG", "1d", {"1d": "bullish"})
    assert c.signal_level == sct.DUPLICATE
    assert "1d" in c.duplicate_timeframes
    assert c.duplicate_timeframes == ["1d"]   # distinct — tick başına büyümez
    assert c.duplicate_hits == 3              # toplam tekrar tick sayısı
    assert c.auto_open_reason == ""

    # 3) İkinci farklı TF aynı yön — double, 30s
    c = sct.observe("BTCUSD", "LONG", "4h", {"4h": "bullish", "1d": "bullish"})
    assert c.signal_level == sct.DOUBLE
    assert c.countdown_seconds == 30
    assert set(c.confirmed_timeframes) == {"1d", "4h"}

    # 4) Üçüncü farklı TF aynı yön — triple, auto_open_reason
    c = sct.observe("BTCUSD", "LONG", "1h", {"1h": "bullish", "4h": "bullish", "1d": "bullish"})
    assert c.signal_level == sct.TRIPLE
    assert c.auto_open_reason == sct.TRIPLE
    assert c.countdown_seconds == 0
    assert set(c.confirmed_timeframes) == {"1d", "4h", "1h"}

    # 7) context_for learning alanlarını doldurur
    ctx = sct.context_for("BTCUSD")
    assert ctx["signal_chain_type"] == sct.TRIPLE
    assert set(ctx["confirmed_timeframes"]) == {"1d", "4h", "1h"}
    assert ctx["auto_open_reason"] == sct.TRIPLE
    assert ctx["countdown_seconds"] == 0
    assert ctx["duplicate_count"] == 1   # distinct duplicate TF — tick sayısı değil
    assert ctx["duplicate_hits"] == 3    # toplam tekrar tick sayısı (additive)
    assert isinstance(ctx["rejected_before_open"], list)
    assert ctx["conflict_count"] == 0


def test_timeframe_conflict(tmp_state):
    sct.observe("XAUUSD", "LONG", "1d", {"1d": "bullish"})
    c = sct.observe("XAUUSD", "SHORT", "4h", {"4h": "bearish"})
    assert c.signal_level == sct.CONFLICT
    assert "4h" in c.conflict_timeframes
    # Ters sinyal işlem açtırmaz — auto_open_reason boş kalır
    assert c.auto_open_reason == ""
    assert c.last_notification["tone"] == "red"


def test_cancel_then_confirm_is_double(tmp_state):
    # İlk 1D sinyali → single
    c = sct.observe("BRENT", "LONG", "1d", {"1d": "bullish"})
    assert c.signal_level == sct.SINGLE

    # Kullanıcı iptal eder → çöpe gitmez, watch memory'de kalır
    c = sct.apply_user_action("BRENT", "cancel")
    assert c is not None
    assert c.user_action == "cancelled"
    assert "1d" in c.rejected_timeframes

    # Sonra 4H gelir → double olarak tanınmalı (1d hafızada)
    c = sct.observe("BRENT", "LONG", "4h", {"4h": "bullish"})
    assert c.signal_level == sct.DOUBLE
    assert set(c.confirmed_timeframes) == {"1d", "4h"}
    assert c.user_action == ""  # yeni teyit → yeniden aktif

    # rejected geçmişte kalır → "rejected_then_confirmed" izlenebilir
    ctx = sct.context_for("BRENT")
    assert "1d" in ctx["rejected_before_open"]


def test_snapshot_shape_and_countdown(tmp_state):
    sct.observe("BTCUSD", "LONG", "1d", {"1d": "bullish"})
    snap = sct.snapshot()
    assert isinstance(snap, list)
    assert len(snap) == 1
    entry = snap[0]
    assert entry["asset"] == "BTCUSD"
    assert entry["signal_level"] == sct.SINGLE
    assert 0 <= entry["countdown_seconds"] <= 60
    assert entry["last_notification"]["tone"] == "amber"
    assert entry["last_notification"]["text"]


def test_legacy_duplicate_list_dedups_on_load(tmp_state):
    # Eski/bozuk state: duplicate_timeframes tick başına büyümüş, duplicate_hits yok.
    import json

    legacy = {
        "chains": {
            "ETHUSD": {
                "asset": "ETHUSD",
                "side": "LONG",
                "confirmed_timeframes": ["1h"],
                "duplicate_timeframes": ["1h"] * 200,
            },
        },
    }
    tmp_state.write_text(json.dumps(legacy), encoding="utf-8")

    ctx = sct.context_for("ETHUSD")
    assert ctx["duplicate_count"] == 1     # distinct'e indirgendi (200 → 1)
    assert ctx["duplicate_hits"] == 200    # eski liste uzunluğu hits'e taşındı


def test_observe_never_raises_on_empty_inputs(tmp_state):
    # Best-effort: bozuk/eksik girdilerde patlamamalı
    c = sct.observe("BTCUSD", "LONG", "", {})
    assert c.asset == "BTCUSD"
    assert c.side == "LONG"
    assert sct.context_for("UNKNOWN") == {}
    assert sct.apply_user_action("UNKNOWN", "cancel") is None


# ── Learning memory: signal_chain alanları outcome kaydına akar (additive) ────

def test_build_outcome_fields_includes_signal_chain():
    from types import SimpleNamespace

    from app.services import paper_trading_service as pts

    chain_ctx = {
        "signal_chain_type": "double_timeframe_signal",
        "confirmed_timeframes": ["1d", "4h"],
        "rejected_before_open": ["1d"],
        "duplicate_count": 2,
        "conflict_count": 0,
        "auto_open_reason": "",
        "countdown_seconds": 30,
    }
    trade = SimpleNamespace(
        pair="BTCUSD", side="LONG",
        open_signal={"signal_chain": chain_ctx, "final_score": 70.0},
        reason="consensus", pnl_usd=120.0, pnl_pct=0.5, duration_min=42,
        entry_at="2026-06-13T00:00:00+00:00", exit_at="2026-06-13T01:00:00+00:00",
    )
    f = pts._build_outcome_fields(trade)
    assert f["signal_chain_type"] == "double_timeframe_signal"
    assert f["confirmed_timeframes"] == ["1d", "4h"]
    assert f["rejected_before_open"] == ["1d"]
    assert f["duplicate_count"] == 2
    assert f["conflict_count"] == 0
    assert f["countdown_seconds"] == 30


def test_build_outcome_fields_without_chain_is_safe():
    from types import SimpleNamespace

    from app.services import paper_trading_service as pts

    trade = SimpleNamespace(pair="XAUUSD", side="SHORT", open_signal={}, reason="x")
    f = pts._build_outcome_fields(trade)
    # Chain yoksa schema kırılmaz; alanlar None/boş liste döner
    assert f["signal_chain_type"] is None
    assert f["confirmed_timeframes"] == []
    assert f["rejected_before_open"] == []
    assert f["auto_open_reason"] is None
