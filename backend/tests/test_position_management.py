"""
Position Management (FAZ 3) — unit testler.

Kapsam:
  Parçalı Alım
    1-8: state, max size, average entry, SL/TP/RR yeniden hesap,
         stop yakınlık, kill switch, DQS, audit
  Sistem Kontrollü Ekleme
    1-4: add_levels şeması, fiyat tetik, paper_auto risk gate, manuel mode
  Manuel SL/TP
    1-6: değişiklik, RR, backup, reset, RR uyarısı, override badge
  İşlem Açılma Sebebi
    1-5: pattern nötr, pattern negatif, consensus, aggression, fallback
  Backward Compatibility
    1-3: eski state, default add_plan, manual_override yok

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.services import paper_trading_service as pts
from app.services import position_management_service as pms


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_state(tmp_path, monkeypatch):
    """Boş bir state dosyası ile yalıtılmış test ortamı."""
    state_path = tmp_path / "paper_trading_state.json"
    monkeypatch.setattr(pts, "_STATE_PATH", state_path)
    yield state_path


def _make_position(
    pair: str = "BTCUSD",
    *,
    side: str = "LONG",
    entry: float = 64000.0,
    size_usd: float = 23905.0,
    stop_loss: float = 62000.0,
    take_profit: float = 68000.0,
    open_signal: dict | None = None,
    add_plan: dict | None = None,
    manual_risk_override: dict | None = None,
    average_entry_price: float | None = None,
) -> pts.Position:
    return pts.Position(
        pair=pair,
        side=side,
        entry_price=entry,
        entry_at=datetime.now(UTC).isoformat(),
        size_usd=size_usd,
        last_signal="test",
        stop_loss=stop_loss,
        take_profit=take_profit,
        open_signal=open_signal or {},
        add_plan=add_plan or {},
        manual_risk_override=manual_risk_override or {},
        average_entry_price=average_entry_price if average_entry_price is not None else entry,
    )


def _save_with_position(state_path, pos: pts.Position, last_price: float = 64000.0):
    """Bir pozisyonla state dosyası kur — last_tick_prices doldur."""
    st = pts.TradingState()
    st.positions[pos.pair] = pos
    st.last_tick_prices = {pos.pair: last_price}
    st.last_tick_at = datetime.now(UTC).isoformat()
    pts._save_state(st)


# ─────────────────────────────────────────────────────────────────────────────
# Parçalı Alım
# ─────────────────────────────────────────────────────────────────────────────

def test_add_plan_initialized_with_correct_defaults():
    plan = pms.initialize_default_add_plan(
        current_size_usd=25_000.0,
        position_size_constant=25_000.0,
        average_entry=64000.0,
    )
    assert plan["mode"] == "manual"
    assert plan["current_size_usd"] == 25_000.0
    assert plan["max_position_size_usd"] == 30_000.0
    assert plan["remaining_add_capacity_usd"] == 5_000.0
    assert plan["add_levels"] == []
    assert plan["last_control_result"] is None


def test_add_blocked_when_max_position_size_exceeded(fresh_state):
    pos = _make_position(size_usd=29_000.0, add_plan=pms.initialize_default_add_plan(
        29_000.0, position_size_constant=25_000.0, average_entry=64000.0,
    ))
    _save_with_position(fresh_state, pos)
    result = pms.add_to_position("BTCUSD", add_size_usd=5_000.0, reason="test")
    assert result["status"] == "rejected"
    assert result["control"]["status"] == "blocked"
    assert "Maks" in result["control"]["reason"]


def test_add_recalculates_average_entry(fresh_state):
    pos = _make_position(
        entry=64000.0, size_usd=20_000.0,
        stop_loss=61000.0, take_profit=68000.0,   # R/R = 1.33 → güvenli
    )
    _save_with_position(fresh_state, pos, last_price=63000.0)
    result = pms.add_to_position(
        "BTCUSD", add_size_usd=4_000.0, reason="average_down", add_price=63000.0,
    )
    assert result["status"] == "added", f"{result}"
    # Yeni avg = (64000*20000 + 63000*4000) / 24000 = 63833.33
    new_avg = result["new_average_entry"]
    assert 63800 < new_avg < 63850


def test_add_recalculates_rr_after_add(fresh_state):
    pos = _make_position(
        entry=64000.0, size_usd=20_000.0,
        stop_loss=62000.0, take_profit=68000.0,   # R/R = 2.0
    )
    _save_with_position(fresh_state, pos, last_price=63500.0)
    result = pms.add_to_position(
        "BTCUSD", add_size_usd=4_000.0, reason="support_reaction", add_price=63500.0,
    )
    assert result["status"] == "added", f"{result}"
    after = result["control"]["after_add_preview"]
    # RR yeniden hesaplandı — sıfırdan farklı
    assert after["rr"] > 0
    assert after["average_entry"] != 64000.0


def test_add_blocked_when_price_too_close_to_stop(fresh_state):
    pos = _make_position(entry=64000.0, size_usd=20_000.0, stop_loss=63900.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos, last_price=63920.0)
    # add_price stop'a çok yakın (% 0.03)
    result = pms.add_to_position(
        "BTCUSD", add_size_usd=2000.0, reason="test", add_price=63920.0,
    )
    assert result["status"] == "rejected"
    assert "stop" in result["control"]["reason"].lower()


def test_add_blocked_when_kill_switch(fresh_state):
    pos = _make_position()
    _save_with_position(fresh_state, pos)
    result = pms.add_to_position(
        "BTCUSD", add_size_usd=1000.0, reason="test", kill_switch=True,
    )
    assert result["status"] == "rejected"
    assert "switch" in result["control"]["reason"].lower()


def test_add_blocked_when_dqs_low(fresh_state):
    pos = _make_position()
    _save_with_position(fresh_state, pos)
    result = pms.add_to_position(
        "BTCUSD", add_size_usd=1000.0, reason="test", dqs_score=40,
    )
    assert result["status"] == "rejected"
    assert "dqs" in result["control"]["reason"].lower()


def test_add_writes_to_add_history(fresh_state):
    pos = _make_position(entry=64000.0, size_usd=20_000.0)
    _save_with_position(fresh_state, pos, last_price=64000.0)
    pms.add_to_position("BTCUSD", add_size_usd=1000.0, reason="momentum_reclaim")
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    assert len(p.add_history) == 1
    assert p.add_history[0]["reason"] == "momentum_reclaim"
    assert p.add_history[0]["add_size_usd"] == 1000.0


# ─────────────────────────────────────────────────────────────────────────────
# Sistem Kontrollü Ekleme
# ─────────────────────────────────────────────────────────────────────────────

def test_update_add_plan_with_add_levels(fresh_state):
    pos = _make_position(add_plan=pms.initialize_default_add_plan(
        23905.0, position_size_constant=25_000.0, average_entry=64000.0,
    ))
    _save_with_position(fresh_state, pos)
    levels = [
        {
            "trigger_type": "price_pullback",
            "trigger_price": 63600.0,
            "add_size_usd": 2000.0,
            "condition_text": "Destek üstünde tepki",
            "status": "waiting",
        },
        {
            "trigger_type": "manual",
            "add_size_usd": 1500.0,
            "condition_text": "Derin destek",
            "status": "manual_required",
            "requires_manual_confirmation": True,
        },
    ]
    result = pms.update_add_plan("BTCUSD", add_levels=levels)
    assert result["status"] == "updated"
    assert len(result["add_plan"]["add_levels"]) == 2
    assert result["add_plan"]["add_levels"][0]["trigger_price"] == 63600.0
    assert result["add_plan"]["add_levels"][1]["requires_manual_confirmation"] is True


def test_update_add_plan_rejects_max_size_below_current(fresh_state):
    pos = _make_position(size_usd=25000.0)
    _save_with_position(fresh_state, pos)
    result = pms.update_add_plan("BTCUSD", max_position_size_usd=20000.0)
    assert result["status"] == "invalid_max_size"


def test_paper_auto_mode_passes_when_safe(fresh_state):
    pos = _make_position(
        entry=64000.0, size_usd=20000.0,
        stop_loss=62000.0, take_profit=68000.0,   # R/R = 2.0
    )
    _save_with_position(fresh_state, pos, last_price=64000.0)
    result = pms.preview_add("BTCUSD", 1000.0, mode="paper_auto")
    assert result["status"] == "ok"
    assert result["control"]["status"] in ("allowed", "risk_warning")


def test_manual_mode_preview_returns_allowed_status(fresh_state):
    pos = _make_position(
        entry=64000.0, size_usd=20000.0,
        stop_loss=62000.0, take_profit=68000.0,
    )
    _save_with_position(fresh_state, pos, last_price=64000.0)
    result = pms.preview_add("BTCUSD", 1000.0, mode="manual")
    assert result["status"] == "ok"
    # manuel modda kullanıcı zaten onay verir — allowed
    assert result["control"]["status"] in ("allowed", "risk_warning")


# ─────────────────────────────────────────────────────────────────────────────
# Manuel SL/TP
# ─────────────────────────────────────────────────────────────────────────────

def test_manual_sl_tp_override(fresh_state):
    pos = _make_position(entry=64000.0, stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    result = pms.set_manual_risk_override(
        "BTCUSD",
        new_stop_loss=63400.0, new_take_profit=65800.0,
        reason="tighten_stop",
    )
    assert result["status"] == "overridden"
    override = result["override"]
    assert override["is_manual_override"] is True
    assert override["new_stop_loss"] == 63400.0
    assert override["new_take_profit"] == 65800.0
    assert override["previous_stop_loss"] == 63000.0


def test_manual_sl_tp_new_rr_computed(fresh_state):
    pos = _make_position(entry=64000.0, stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    result = pms.set_manual_risk_override(
        "BTCUSD", new_stop_loss=63500.0, new_take_profit=65500.0, reason="test",
    )
    # New RR = (65500-64000) / (64000-63500) = 1500/500 = 3.0
    assert abs(result["override"]["new_rr"] - 3.0) < 0.05


def test_manual_sl_tp_saves_auto_plan_backup(fresh_state):
    pos = _make_position(entry=64000.0, stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    pms.set_manual_risk_override(
        "BTCUSD", new_stop_loss=63500.0, new_take_profit=65500.0, reason="test",
    )
    st = pts._load_state()
    backup = st.positions["BTCUSD"].manual_risk_override["auto_plan_backup"]
    assert backup["stop_loss"] == 63000.0
    assert backup["take_profit"] == 66000.0


def test_reset_to_auto_risk_plan(fresh_state):
    pos = _make_position(entry=64000.0, stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    pms.set_manual_risk_override(
        "BTCUSD", new_stop_loss=63500.0, new_take_profit=65500.0, reason="test",
    )
    result = pms.reset_to_auto_risk_plan("BTCUSD")
    assert result["status"] == "reset"
    assert result["stop_loss"] == 63000.0
    assert result["take_profit"] == 66000.0
    st = pts._load_state()
    assert st.positions["BTCUSD"].manual_risk_override == {}


def test_manual_sl_tp_warns_when_rr_below_1(fresh_state):
    pos = _make_position(entry=64000.0, stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    # SL geniş, TP yakın → R/R < 1
    result = pms.set_manual_risk_override(
        "BTCUSD", new_stop_loss=63000.0, new_take_profit=64500.0, reason="test",
    )
    assert result["status"] == "overridden"
    warnings = result["override"].get("warnings", [])
    assert any("R/R" in w for w in warnings)


def test_manual_sl_tp_invalid_direction_long(fresh_state):
    pos = _make_position(side="LONG", entry=64000.0, stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    # LONG için SL>entry verirsek hata
    result = pms.set_manual_risk_override(
        "BTCUSD", new_stop_loss=65000.0, new_take_profit=66000.0, reason="test",
    )
    assert result["status"] == "invalid_direction"


# ─────────────────────────────────────────────────────────────────────────────
# İşlem Açılma Sebebi
# ─────────────────────────────────────────────────────────────────────────────

def test_explanation_pattern_neutral_marks_not_primary():
    open_signal = {
        "pattern_bias": "NEUTRAL",
        "pattern_score": -2.8,
        "final_score": 65.0,
        "final_direction": "bullish",
    }
    expl = pms.build_opening_explanation(open_signal, pair="BTCUSD", side="LONG")
    assert expl["was_pattern_primary_reason"] is False
    assert "pattern" in expl["primary_reason"].lower() or "consensus" in expl["primary_reason"].lower()
    # Pattern not'unda "ana açılış sebebi değildi" geçmeli
    assert any("ana" in n.lower() for n in expl["pattern_notes"])


def test_explanation_pattern_negative_added_to_opposing():
    open_signal = {
        "pattern_bias": "BEARISH",
        "pattern_score": -15.0,
        "final_score": 62.0,
        "final_direction": "bullish",
    }
    expl = pms.build_opening_explanation(open_signal, pair="BTCUSD", side="LONG")
    assert any("pattern" in s.lower() and "bearish" in s.lower() for s in expl["opposing_signals"])


def test_explanation_consensus_appears_in_supporting():
    open_signal = {
        "final_score": 72.0,
        "final_direction": "bullish",
        "raw_regime": "RISK_ON",
    }
    expl = pms.build_opening_explanation(open_signal, pair="BTCUSD", side="LONG")
    assert "consensus" in expl["supporting_layers"]


def test_explanation_aggression_appears_in_supporting():
    open_signal = {
        "final_score": 60.0, "final_direction": "bullish",
        "aggression_context": {
            "aggression_level": "high",
            "recommended_timeframe": "1h",
        },
    }
    expl = pms.build_opening_explanation(open_signal, pair="BTCUSD", side="LONG")
    assert "aggression" in expl["supporting_layers"]
    assert "high" in expl["supporting_layers"]["aggression"].lower()


def test_explanation_fallback_when_open_signal_empty():
    expl = pms.build_opening_explanation({}, pair="BTCUSD", side="LONG")
    # Boş open_signal'da bile primary_reason boş kalmamalı
    assert expl["primary_reason"]
    assert len(expl["primary_reason"]) > 20


def test_explanation_invalidation_always_present():
    expl = pms.build_opening_explanation({}, pair="BTCUSD", side="LONG")
    assert "Stop" in expl["invalidation_summary"][0]


# ─────────────────────────────────────────────────────────────────────────────
# Backward Compatibility
# ─────────────────────────────────────────────────────────────────────────────

def test_old_state_loads_with_empty_position_management_fields(fresh_state):
    """Eski state dosyası — add_plan/manual_risk_override/opening_explanation YOK."""
    old_state = {
        "starting_balance": 100_000.0,
        "realized_pnl_usd": 0.0,
        "positions": {
            "BTCUSD": {
                "pair": "BTCUSD", "side": "LONG",
                "entry_price": 64000.0,
                "entry_at": "2025-01-01T00:00:00+00:00",
                "size_usd": 25_000.0, "last_signal": "test",
                "stop_loss": 63000.0, "take_profit": 66000.0,
                # add_plan / manual_risk_override / opening_explanation YOK
            },
        },
        "pending_orders": {}, "rejected_signals": {}, "manual_ready_trades": {},
        "trades": [], "weight_adjustments": {},
        "last_trained_at_trade_count": 0, "training_history": [],
        "last_tick_prices": {"BTCUSD": 64000.0}, "last_tick_signals": {},
    }
    fresh_state.write_text(json.dumps(old_state), encoding="utf-8")
    st = pts._load_state()
    pos = st.positions["BTCUSD"]
    assert pos.add_plan == {}
    assert pos.manual_risk_override == {}
    assert pos.opening_explanation == {}
    assert pos.add_history == []
    # average_entry_price entry_price'a düşmeli
    assert pos.average_entry_price == 64000.0


def test_snapshot_auto_initializes_default_add_plan_for_old_positions(fresh_state):
    """get_snapshot() eski pozisyonlar için snapshot-only default add_plan üretir."""
    old_state = {
        "starting_balance": 100_000.0, "realized_pnl_usd": 0.0,
        "positions": {
            "BTCUSD": {
                "pair": "BTCUSD", "side": "LONG",
                "entry_price": 64000.0,
                "entry_at": "2025-01-01T00:00:00+00:00",
                "size_usd": 25_000.0, "last_signal": "test",
                "stop_loss": 63000.0, "take_profit": 66000.0,
            },
        },
        "pending_orders": {}, "rejected_signals": {}, "manual_ready_trades": {},
        "trades": [], "weight_adjustments": {},
        "last_trained_at_trade_count": 0, "training_history": [],
        "last_tick_prices": {"BTCUSD": 64000.0}, "last_tick_signals": {},
    }
    fresh_state.write_text(json.dumps(old_state), encoding="utf-8")
    snap = pts.get_snapshot()
    open_pos = snap["open_positions"][0]
    # Snapshot-only enrichment — default add_plan dolu olmalı
    assert open_pos["add_plan"] != {}
    assert open_pos["add_plan"]["mode"] == "manual"
    # opening_explanation default'u boş open_signal'dan üretilmiş olmalı
    assert open_pos["opening_explanation"] != {}
    assert open_pos["opening_explanation"]["primary_reason"]
    # State dosyasında YOK kalmalı (snapshot-only)
    st = pts._load_state()
    assert st.positions["BTCUSD"].add_plan == {}
    assert st.positions["BTCUSD"].opening_explanation == {}


def test_position_without_manual_override_keeps_default_risk_plan(fresh_state):
    pos = _make_position(stop_loss=63000.0, take_profit=66000.0)
    _save_with_position(fresh_state, pos)
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    assert p.manual_risk_override == {}
    assert p.stop_loss == 63000.0
    assert p.take_profit == 66000.0


# ─────────────────────────────────────────────────────────────────────────────
# TP Plan Execution (FAZ 3 — gerçek partial TP tetikleyicisi)
# ─────────────────────────────────────────────────────────────────────────────

def test_partial_tp_uses_take_profit_plan_when_present(fresh_state):
    """take_profit_plan.partial_tp_price LONG için tetiklenirse partial TP çalışsın."""
    pos = _make_position(
        entry=64000.0, size_usd=20_000.0,
        stop_loss=62000.0, take_profit=68000.0,
        open_signal={
            "atr": 200.0,    # Eski ATR fallback için 1×ATR = 64200 olur
            "take_profit_plan": {
                "partial_tp_enabled": True,
                "partial_tp_price": 65000.0,  # ATR fallback'tan farklı → izolasyonu kanıtlar
                "partial_tp_at_r": 1.0,
                "final_tp_at_r":   2.0,
            },
        },
    )
    pos.risk_plan = {"atr_used": 200.0}
    _save_with_position(fresh_state, pos, last_price=65000.0)
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    # Fiyat plan partial_tp_price'a ulaştı (LONG → 65000 ≥ 65000)
    closed = pts._apply_risk_management(st, p, "BTCUSD", price=65010.0, now_iso="2026-06-08T12:00:00+00:00")
    assert closed is False  # partial TP kapatma değil, half realize
    assert p.partial_tp_taken is True
    audit = p.open_signal.get("partial_tp_execution") or {}
    assert audit.get("source") == "take_profit_plan"
    assert audit.get("partial_tp_price") == 65000.0


def test_partial_tp_falls_back_to_atr_when_plan_missing(fresh_state):
    """take_profit_plan yoksa eski ATR (entry±ATR) fallback davranışı çalışsın."""
    pos = _make_position(
        entry=64000.0, size_usd=20_000.0,
        stop_loss=62000.0, take_profit=68000.0,
        open_signal={"atr": 200.0},  # take_profit_plan YOK
    )
    pos.risk_plan = {"atr_used": 200.0}
    _save_with_position(fresh_state, pos, last_price=64200.0)
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    # TP1 (entry+1×ATR = 64200) tetiklendi
    pts._apply_risk_management(st, p, "BTCUSD", price=64210.0, now_iso="2026-06-08T12:00:00+00:00")
    assert p.partial_tp_taken is True
    audit = p.open_signal.get("partial_tp_execution") or {}
    assert audit.get("source") == "atr_fallback"


def test_partial_tp_does_not_fire_twice(fresh_state):
    """partial_tp_taken=True ise tekrar tetiklenmemeli."""
    pos = _make_position(
        entry=64000.0, size_usd=10_000.0,
        stop_loss=62000.0, take_profit=68000.0,
        open_signal={
            "atr": 200.0,
            "take_profit_plan": {
                "partial_tp_enabled": True,
                "partial_tp_price":   65000.0,
            },
        },
    )
    pos.risk_plan = {"atr_used": 200.0}
    pos.partial_tp_taken = True   # zaten alınmış
    pos.original_size_usd = 20_000.0
    _save_with_position(fresh_state, pos, last_price=65500.0)
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    prev_size = p.size_usd
    pts._apply_risk_management(st, p, "BTCUSD", price=65500.0, now_iso="2026-06-08T12:00:00+00:00")
    # Boyut DEĞIŞMEMELI (tekrar partial TP alınmadı)
    assert p.size_usd == prev_size
    # Audit'e ekleme yapılmadı
    assert "partial_tp_execution" not in (p.open_signal or {})


def test_partial_tp_short_side_direction(fresh_state):
    """SHORT pozisyonda partial TP fiyat partial_tp_price'a düşünce tetiklenir."""
    pos = _make_position(
        side="SHORT", entry=64000.0, size_usd=20_000.0,
        stop_loss=66000.0, take_profit=60000.0,
        open_signal={
            "atr": 200.0,
            "take_profit_plan": {
                "partial_tp_enabled": True,
                "partial_tp_price":   63000.0,  # entry'nin altında — SHORT için kâr
            },
        },
    )
    pos.risk_plan = {"atr_used": 200.0}
    _save_with_position(fresh_state, pos, last_price=62980.0)
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    closed = pts._apply_risk_management(st, p, "BTCUSD", price=62980.0, now_iso="2026-06-08T12:00:00+00:00")
    assert closed is False
    assert p.partial_tp_taken is True
    audit = p.open_signal.get("partial_tp_execution") or {}
    assert audit.get("source") == "take_profit_plan"


def test_partial_tp_plan_disabled_falls_back_to_atr(fresh_state):
    """take_profit_plan.partial_tp_enabled=False ise plan yok sayılır, ATR fallback çalışır."""
    pos = _make_position(
        entry=64000.0, size_usd=20_000.0,
        stop_loss=62000.0, take_profit=68000.0,
        open_signal={
            "atr": 200.0,
            "take_profit_plan": {
                "partial_tp_enabled": False,
                "partial_tp_price":   65000.0,
            },
        },
    )
    pos.risk_plan = {"atr_used": 200.0}
    _save_with_position(fresh_state, pos, last_price=64200.0)
    st = pts._load_state()
    p = st.positions["BTCUSD"]
    pts._apply_risk_management(st, p, "BTCUSD", price=64210.0, now_iso="2026-06-08T12:00:00+00:00")
    assert p.partial_tp_taken is True
    audit = p.open_signal.get("partial_tp_execution") or {}
    assert audit.get("source") == "atr_fallback"
