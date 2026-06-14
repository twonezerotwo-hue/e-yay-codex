"""PHASE 2 — Codex core güvenlik invariant'ları (regresyon ağı).

Bu dosya, sistemin OLGUN güvenlik davranışlarını tek yerde kilitler. Saf-fonksiyon
seviyesinde, ağ/IO olmadan. (Invariant #2 "AI size artıramaz" → ayrı dosyada:
test_ai_opinion_no_size_boost.py. Snapshot replay / attribution / risk_gate_view
invariant'ları kendi mevcut adanmış testlerinde korunur.)

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.execution_boundary import boundary_status, require_paper_safe
from app.services import paper_trading_service as pts


# ── Invariant 1: PAPER_SAFE / NO_EXECUTION default ────────────────────────────

def test_paper_safe_no_execution_is_default():
    ps = require_paper_safe()
    assert ps["mode"] == "PAPER_SAFE"
    assert ps["execution"] == "OFF"
    st = boundary_status()
    blob = " ".join(str(v) for v in st.values()).upper()
    assert "PAPER_SAFE" in blob or st.get("mode") == "PAPER_SAFE"
    assert "ON" not in str(st.get("execution", "OFF")).upper()


# ── Invariant 3: price sanity impossible fiyatları reddeder ───────────────────

def test_price_sanity_rejects_impossible_prices():
    # cross-pair contamination: BTC için $7,405 absolute bound altında
    assert pts._is_price_sane("BTCUSD", 7405.0) is False
    # XAUUSD'ye BTC fiyatı / saçma düşük
    assert pts._is_price_sane("XAUUSD", 716.0) is False
    # negatif/sıfır
    assert pts._is_price_sane("BTCUSD", 0.0) is False
    assert pts._is_price_sane("BTCUSD", -5.0) is False
    # makul fiyatlar kabul
    assert pts._is_price_sane("BTCUSD", 64000.0) is True
    assert pts._is_price_sane("XAUUSD", 2400.0) is True


def test_price_sanity_jump_guard():
    # önceki tick'e göre >%30 sapma → reddet (BTC 64k → 40k = -37.5%)
    assert pts._is_price_sane("BTCUSD", 40000.0, previous_price=64000.0) is False
    # küçük hareket kabul
    assert pts._is_price_sane("BTCUSD", 63000.0, previous_price=64000.0) is True


# ── Invariant 4: state anomaly yeni trade'i bloklamak için tespit eder ────────

def _state(realized: float = 0.0) -> pts.TradingState:
    return pts.TradingState(starting_balance=100_000.0, realized_pnl_usd=realized)


def test_state_anomaly_not_flagged_for_normal_state():
    res = pts._detect_state_anomaly(_state(333.0), equity=100_333.0, daily_pnl=333.0)
    assert res["detected"] is False
    assert res["reasons"] == []


def test_state_anomaly_flags_inflated_realized_and_equity():
    # realized PnL başlangıç bakiyenin 3 katını aşıyor
    r = pts._detect_state_anomaly(_state(400_000.0))
    assert r["detected"] is True and r["reasons"]
    # equity 3x üstü
    r2 = pts._detect_state_anomaly(_state(0.0), equity=400_000.0)
    assert r2["detected"] is True
    # günlük PnL başlangıcın %50'sini aşıyor
    r3 = pts._detect_state_anomaly(_state(0.0), daily_pnl=60_000.0)
    assert r3["detected"] is True


# ── Invariant 5: DEFENSIVE / CRISIS → manual approval kuyruğu ─────────────────

def test_defensive_crisis_require_manual_approval():
    assert "DEFENSIVE" in pts._MANUAL_APPROVAL_REGIMES
    assert "CRISIS" in pts._MANUAL_APPROVAL_REGIMES
    # risk-on rejimler manuel onay gerektirmez
    assert "RISK_ON" not in pts._MANUAL_APPROVAL_REGIMES
    assert "NEUTRAL" not in pts._MANUAL_APPROVAL_REGIMES


# ── Invariant 7: learning/outcome context eksik/bozuksa crash etmez ───────────

def test_outcome_fields_resilient_to_minimal_trade():
    trade = SimpleNamespace(pair="BTCUSD", side="LONG", open_signal={}, reason="x")
    fields = pts._build_outcome_fields(trade)   # best-effort — patlamamalı
    assert isinstance(fields, dict)
    assert fields["asset"] == "BTCUSD"
    assert fields["side"] == "LONG"


# ── Sabit kontratı: traded pairs + price bounds beklenen değerlerde ───────────

def test_traded_pairs_and_bounds_contract():
    assert pts.TRADED_PAIRS == ("BTCUSD", "XAUUSD", "XAGUSD", "BRENT")
    for pair in pts.TRADED_PAIRS:
        if pair in pts.PRICE_SANITY_BOUNDS:
            lo, hi = pts.PRICE_SANITY_BOUNDS[pair]
            assert 0 < lo < hi
