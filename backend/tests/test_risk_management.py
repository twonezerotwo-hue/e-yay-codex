"""
S1: Trailing Stop + Break-Even
S2: Partial Take-Profit (TP1 = entry ± ATR)
SL/TP enforcement (mevcut kodda yoktu)

PAPER_SAFE / NO_EXECUTION
"""
from __future__ import annotations

import sys
import types
from datetime import UTC, datetime, timedelta

sys.modules.setdefault("numpy", types.SimpleNamespace())

from app.services import paper_trading_service as pts
from app.services.paper_trading_service import (
    Position,
    Trade,
    TradingState,
    _apply_risk_management,
    _close_open_position,
    _realize_partial_tp,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fresh_st(tmp_path, monkeypatch):
    monkeypatch.setattr(pts, "_STATE_PATH", tmp_path / "state.json")
    pts.reset_state()
    return pts._load_state()


def _pos(
    *,
    pair: str = "BTCUSD",
    side: str = "LONG",
    entry: float = 60_000.0,
    sl: float = 57_000.0,    # entry - 1.5×ATR (ATR=2000)
    tp: float = 66_000.0,    # entry + 3.0×ATR
    size: float = 25_000.0,
    atr: float = 2_000.0,
    trailing_active: bool = False,
    partial_taken: bool = False,
) -> Position:
    now = datetime.now(UTC).isoformat()
    return Position(
        pair=pair, side=side,
        entry_price=entry, entry_at=now,
        size_usd=size, last_signal="BULLISH@72",
        stop_loss=sl, take_profit=tp,
        open_signal={"atr": atr},
        risk_plan={"atr_used": atr, "stop_loss": sl, "take_profit": tp},
        trailing_stop_active=trailing_active,
        partial_tp_taken=partial_taken,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# SL enforcement (daha önce hiç yoktu!)
# ══════════════════════════════════════════════════════════════════════════════

def test_sl_hit_closes_long_position(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000)
    st.positions["BTCUSD"] = pos

    # Fiyat SL'nin altına düştü
    closed = _apply_risk_management(st, pos, "BTCUSD", price=56_800.0, now_iso=_now())

    assert closed is True
    assert "BTCUSD" not in st.positions, "SL tetiklenince pozisyon kapanmalı"
    assert len(st.trades) == 1
    assert st.trades[0].verdict == "LOSS"
    assert st.trades[0].reason == "SL_HIT"


def test_sl_not_triggered_above_sl(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000)
    st.positions["BTCUSD"] = pos

    closed = _apply_risk_management(st, pos, "BTCUSD", price=58_500.0, now_iso=_now())

    assert closed is False
    assert "BTCUSD" in st.positions


# ══════════════════════════════════════════════════════════════════════════════
# TP enforcement
# ══════════════════════════════════════════════════════════════════════════════

def test_tp_hit_closes_long_position(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    # partial_tp_taken=True → sadece TP_HIT testi yapabilelim
    pos = _pos(entry=60_000, tp=66_000, partial_taken=True)
    st.positions["BTCUSD"] = pos

    closed = _apply_risk_management(st, pos, "BTCUSD", price=66_200.0, now_iso=_now())

    assert closed is True
    assert "BTCUSD" not in st.positions
    assert st.trades[0].verdict == "WIN"
    assert st.trades[0].reason == "TP_HIT"


def test_full_tp_fires_after_partial_tp(monkeypatch, tmp_path):
    """TP2 eşiğine ulaşınca önce partial TP (trade[0]) sonra TP_HIT (trade[1]) tetiklenir."""
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, tp=66_000, atr=2_000, size=25_000)
    st.positions["BTCUSD"] = pos

    # Fiyat TP'nin üstüne fırladı
    closed = _apply_risk_management(st, pos, "BTCUSD", price=66_200.0, now_iso=_now())

    assert closed is True
    assert len(st.trades) == 2
    assert st.trades[0].reason == "PARTIAL_TP1"
    assert st.trades[1].reason == "TP_HIT"


def test_sl_enforced_for_short(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    # SHORT: sl ABOVE entry (price rises → loss)
    pos = _pos(side="SHORT", entry=60_000, sl=63_000, tp=54_000, atr=2000)
    st.positions["BTCUSD"] = pos

    closed = _apply_risk_management(st, pos, "BTCUSD", price=63_500.0, now_iso=_now())

    assert closed is True
    assert st.trades[0].reason == "SL_HIT"


# ══════════════════════════════════════════════════════════════════════════════
# S1: Break-Even (entry + 1×ATR threshold)
# ══════════════════════════════════════════════════════════════════════════════

def test_break_even_activates_at_1x_atr(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, atr=2_000)
    st.positions["BTCUSD"] = pos

    # Fiyat entry + 1×ATR = 62_000 geçti
    closed = _apply_risk_management(st, pos, "BTCUSD", price=62_100.0, now_iso=_now())

    assert closed is False  # Henüz kapanmadı
    assert pos.trailing_stop_active is True
    assert pos.stop_loss >= 60_000.0, "SL en az entry'e çekilmeli (break-even)"


def test_break_even_does_not_lower_sl(monkeypatch, tmp_path):
    """SL hiçbir zaman gerilemez — zaten daha iyi bir SL varsa korur."""
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=61_000, atr=2_000)  # SL already above entry
    st.positions["BTCUSD"] = pos

    _apply_risk_management(st, pos, "BTCUSD", price=62_100.0, now_iso=_now())

    assert pos.stop_loss >= 61_000.0, "Mevcut SL gerilemez"


# ══════════════════════════════════════════════════════════════════════════════
# S1: Trailing Stop (entry + 2×ATR threshold)
# ══════════════════════════════════════════════════════════════════════════════

def test_trailing_stop_activates_at_2x_atr(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, atr=2_000)
    st.positions["BTCUSD"] = pos

    # Fiyat entry + 2×ATR = 64_000 geçti
    _apply_risk_management(st, pos, "BTCUSD", price=64_500.0, now_iso=_now())

    # Trailing SL = price - 1.5×ATR = 64_500 - 3_000 = 61_500
    assert pos.stop_loss >= 61_500.0, "Trailing SL kâr kilitlemeli"
    assert pos.trailing_stop_active is True


def test_trailing_sl_triggers_close_on_reversal(monkeypatch, tmp_path):
    """Fiyat yükseldikten sonra geri gelince trailing SL tetiklenir → BREAK_EVEN veya WIN."""
    st = _fresh_st(tmp_path, monkeypatch)
    # partial_tp_taken=True → partial TP zaten alınmış sayılır, sadece trailing test edilir
    pos = _pos(entry=60_000, sl=57_000, atr=2_000, size=12_500, partial_taken=True)
    st.positions["BTCUSD"] = pos

    # İlk tick: fiyat yükseldi, trailing SL kuruldu (price=64500 > entry+2×ATR=64000)
    _apply_risk_management(st, pos, "BTCUSD", price=64_500.0, now_iso=_now())
    sl_after_trail = pos.stop_loss  # ≈ 61_500

    # İkinci tick: fiyat SL'in altına döndü
    closed = _apply_risk_management(st, pos, "BTCUSD", price=sl_after_trail - 10, now_iso=_now())

    assert closed is True
    assert st.trades[0].reason == "TRAILING_SL"
    # PnL pozitif veya sıfır (kâr bölgesinden kapanıyor)
    assert st.trades[0].pnl_usd >= 0, "Trailing SL BREAK_EVEN veya WIN olmalı"


def test_trailing_sl_for_short(monkeypatch, tmp_path):
    """SHORT için trailing: fiyat düşerken SL (YUKARI) iner."""
    st = _fresh_st(tmp_path, monkeypatch)
    # SHORT: sl above entry
    pos = _pos(side="SHORT", entry=60_000, sl=63_000, tp=54_000, atr=2_000)
    st.positions["BTCUSD"] = pos

    # Fiyat entry - 2×ATR = 56_000 altına düştü
    _apply_risk_management(st, pos, "BTCUSD", price=55_500.0, now_iso=_now())

    # Trailing SL = price + 1.5×ATR = 55_500 + 3_000 = 58_500
    assert pos.stop_loss <= 58_500.0 + 1, "SHORT trailing SL aşağı inmeli"
    assert pos.trailing_stop_active is True


# ══════════════════════════════════════════════════════════════════════════════
# S2: Partial Take-Profit
# ══════════════════════════════════════════════════════════════════════════════

def test_partial_tp_realizes_half_lot(monkeypatch, tmp_path):
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, tp=66_000, atr=2_000, size=25_000)
    st.positions["BTCUSD"] = pos

    # TP1 = entry + 1×ATR = 62_000
    _apply_risk_management(st, pos, "BTCUSD", price=62_100.0, now_iso=_now())

    assert pos.partial_tp_taken is True
    assert pos.size_usd == 12_500.0, "Kalan lot yarıya inmiş olmalı"
    assert pos.original_size_usd == 25_000.0
    assert len(st.trades) == 1
    assert st.trades[0].reason == "PARTIAL_TP1"
    assert st.trades[0].verdict == "WIN"
    assert st.trades[0].size_usd == 12_500.0
    # SL break-even'e çekildi
    assert pos.stop_loss == 60_000.0


def test_partial_tp_not_repeated(monkeypatch, tmp_path):
    """TP1 eşiğinde iken iki kez çağrılsa bile sadece bir kez realize edilir."""
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, tp=66_000, atr=2_000, size=25_000)
    st.positions["BTCUSD"] = pos

    _apply_risk_management(st, pos, "BTCUSD", price=62_100.0, now_iso=_now())
    _apply_risk_management(st, pos, "BTCUSD", price=62_200.0, now_iso=_now())

    assert len(st.trades) == 1, "Partial TP iki kez alınmamalı"
    assert pos.size_usd == 12_500.0


def test_partial_tp_then_trailing_then_close(monkeypatch, tmp_path):
    """Full senaryo:
    1. TP1 → %50 realize + break-even SL
    2. Fiyat daha da yükselir → trailing SL
    3. Fiyat geri döner → trailing SL tetikler → kalan %50 WIN
    """
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, tp=66_000, atr=2_000, size=25_000)
    st.positions["BTCUSD"] = pos

    # TP1: fiyat 62_100 (entry + 1.05×ATR)
    _apply_risk_management(st, pos, "BTCUSD", price=62_100.0, now_iso=_now())
    assert pos.partial_tp_taken is True
    assert pos.size_usd == 12_500.0

    # Trailing: fiyat 64_500 (entry + 2.25×ATR)
    _apply_risk_management(st, pos, "BTCUSD", price=64_500.0, now_iso=_now())
    sl_trailing = pos.stop_loss  # ≈ 61_500

    # Geri dönüş: trailing SL tetikleniyor
    closed = _apply_risk_management(st, pos, "BTCUSD", price=sl_trailing - 50, now_iso=_now())

    assert closed is True
    assert len(st.trades) == 2  # Partial TP trade + final close trade
    assert st.trades[0].reason == "PARTIAL_TP1"
    assert st.trades[1].reason == "TRAILING_SL"
    # Her iki trade da WIN
    assert all(t.verdict == "WIN" for t in st.trades)
    # Toplam PnL pozitif
    total_pnl = sum(t.pnl_usd for t in st.trades)
    assert total_pnl > 0, f"Toplam PnL pozitif olmalı, got {total_pnl}"


def test_partial_tp_not_triggered_below_tp1(monkeypatch, tmp_path):
    """Fiyat TP1 altındayken partial TP tetiklenmez."""
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, tp=66_000, atr=2_000, size=25_000)
    st.positions["BTCUSD"] = pos

    _apply_risk_management(st, pos, "BTCUSD", price=61_500.0, now_iso=_now())

    assert pos.partial_tp_taken is False
    assert pos.size_usd == 25_000.0


def test_no_risk_management_without_atr(monkeypatch, tmp_path):
    """ATR=0 olunca trailing/partial tetiklenmez, SL/TP hâlâ çalışır."""
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, tp=66_000, atr=0, size=25_000)
    st.positions["BTCUSD"] = pos

    # SL hit (atr=0 olsa bile SL enforce edilir)
    closed = _apply_risk_management(st, pos, "BTCUSD", price=56_000.0, now_iso=_now())
    assert closed is True, "ATR sıfır olsa bile SL tetiklenmeli"


def test_break_even_prevents_loss(monkeypatch, tmp_path):
    """Break-even aktifken fiyat entry'e geri dönseydi → BREAK_EVEN (LOSS değil)."""
    st = _fresh_st(tmp_path, monkeypatch)
    pos = _pos(entry=60_000, sl=57_000, atr=2_000)
    st.positions["BTCUSD"] = pos

    # Break-even aktivasyonu
    _apply_risk_management(st, pos, "BTCUSD", price=62_100.0, now_iso=_now())
    assert pos.stop_loss == 60_000.0

    # Fiyat geri döndü, tam SL seviyesinde
    closed = _apply_risk_management(st, pos, "BTCUSD", price=59_990.0, now_iso=_now())

    assert closed is True
    assert st.trades[0].verdict in ("BREAK_EVEN", "WIN")
    assert st.trades[0].pnl_usd >= -5.0, "Break-even kapanış LOSS olmamalı"
