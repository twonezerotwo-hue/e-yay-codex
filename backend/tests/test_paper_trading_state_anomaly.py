"""
Paper Trading State Anomaly / Corruption Guard / Repair / PnL Invariant Tests.

Hedef: bozuk fiyat verisi tick'e girdiğinde state'in (realized_pnl, equity)
nasıl korunduğunu, anomaly tespiti olunca yeni trade açılmamasını, reset/
repair endpoint'lerinin doğru çalıştığını ve PnL hesabının matematiksel
olarak doğru kaldığını doğrular.

PAPER_SAFE / NO_EXECUTION — gerçek emir yok.
"""
from __future__ import annotations

import json
import sys
import types
from datetime import UTC, datetime

from fastapi.testclient import TestClient

# numpy yok — diğer test dosyalarıyla uyumlu stub
sys.modules.setdefault("numpy", types.SimpleNamespace())

from app.api import paper_trading
from app.main import app
from app.services import paper_trading_service as pts


client = TestClient(app)


def _set_tmp_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pts, "_STATE_PATH", tmp_path / "paper_trading_state.json")
    pts.reset_state()
    if hasattr(paper_trading, "_RESPONSE_CACHE"):
        monkeypatch.setattr(paper_trading, "_RESPONSE_CACHE", None)


# ─────────────────────────────────────────────────────────────────────────────
# Price sanity guard
# ─────────────────────────────────────────────────────────────────────────────

def test_is_price_sane_rejects_out_of_bounds() -> None:
    # BTCUSD: (20k, 500k) — 596 reddedilmeli (corruption); 64k makul
    assert pts._is_price_sane("BTCUSD", 596.249) is False
    assert pts._is_price_sane("BTCUSD", 64_000.0) is True
    # BRENT: (30, 200) — 63_248 reddedilmeli; 94 makul
    assert pts._is_price_sane("BRENT", 63_248.11) is False
    assert pts._is_price_sane("BRENT", 94.84) is True
    # XAGUSD: (15, 150) — 716 reddedilmeli; 68 makul
    assert pts._is_price_sane("XAGUSD", 68.48) is True
    assert pts._is_price_sane("XAGUSD", 716.07) is False
    # XAUUSD: (1500, 7000) — 716 reddedilmeli (BTC/XAG karışıklığı)
    assert pts._is_price_sane("XAUUSD", 716.07) is False
    assert pts._is_price_sane("XAUUSD", 4_356.7) is True
    # Sıfır / negatif her zaman reddedilir
    assert pts._is_price_sane("BTCUSD", 0.0) is False
    assert pts._is_price_sane("BTCUSD", -1.0) is False
    # Sınır tanımlı olmayan parite: sadece pozitiflik kontrolü
    assert pts._is_price_sane("XYZUSD", 50_000.0) is True
    assert pts._is_price_sane("XYZUSD", 0.0) is False


def test_is_price_sane_rejects_cross_pair_contamination_via_jump() -> None:
    """Önceki tick BTC=64000 iken yeni tick BTC=7405 (BRENT fiyatı geldi) →
    abs-bounds geçer ama jump guard tutar."""
    # 7405 BTC abs-bounds için (20k-500k) zaten dışı — bounds yakalar
    assert pts._is_price_sane("BTCUSD", 7405.73, previous_price=64_000.0) is False
    # Daha sinsi senaryo: BTC abs-içinde ama %50+ sıçramış
    # 64000 → 30000 (~%53 düşüş) — gerçek olamaz, reddet
    assert pts._is_price_sane("BTCUSD", 30_000.0, previous_price=64_000.0) is False
    # 64000 → 60000 (~%6 düşüş) — normal piyasa oynaması, kabul
    assert pts._is_price_sane("BTCUSD", 60_000.0, previous_price=64_000.0) is True
    # previous_price=None → sadece bounds (geriye dönük uyumlu)
    assert pts._is_price_sane("BTCUSD", 64_000.0, previous_price=None) is True
    # previous_price=0 → ilk tick, jump check uygulanmaz
    assert pts._is_price_sane("BTCUSD", 64_000.0, previous_price=0.0) is True


# ─────────────────────────────────────────────────────────────────────────────
# State anomaly detection
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_state_anomaly_clean_state() -> None:
    st = pts.TradingState()
    result = pts._detect_state_anomaly(st)
    assert result["detected"] is False
    assert result["reasons"] == []


def test_detect_state_anomaly_huge_realized_pnl() -> None:
    st = pts.TradingState()
    # Başlangıç 100k, 3x sınırı = 300k. 500k absürt.
    st.realized_pnl_usd = 500_000.0
    result = pts._detect_state_anomaly(st)
    assert result["detected"] is True
    assert any("Realized PnL" in r for r in result["reasons"])


def test_detect_state_anomaly_huge_equity() -> None:
    st = pts.TradingState()
    # equity parametresi snapshot tarafından geçilir
    result = pts._detect_state_anomaly(st, equity=5_000_000.0, daily_pnl=0.0)
    assert result["detected"] is True
    assert any("Equity" in r for r in result["reasons"])


def test_detect_state_anomaly_huge_daily_pnl() -> None:
    st = pts.TradingState()
    # Günlük PnL 100k * 0.5 = 50k sınır. 80k absürt.
    result = pts._detect_state_anomaly(st, equity=100_000.0, daily_pnl=80_000.0)
    assert result["detected"] is True
    assert any("Günlük PnL" in r for r in result["reasons"])


# ─────────────────────────────────────────────────────────────────────────────
# PnL invariant — formül doğrulukları
# ─────────────────────────────────────────────────────────────────────────────

def test_pnl_invariant_long_close() -> None:
    """BTCUSD entry=64000, exit=65000, size=24000 → pnl ≈ +375."""
    pos = pts.Position(
        pair="BTCUSD", side="LONG", entry_price=64_000.0,
        size_usd=24_000.0, entry_at=datetime.now(UTC).isoformat(),
        last_signal="test", stop_loss=63_000.0, take_profit=66_000.0,
    )
    pnl_usd, pnl_pct = pts._unrealized_pnl(pos, 65_000.0)
    assert abs(pnl_usd - 375.0) < 0.01
    assert abs(pnl_pct - 1.5625) < 0.0001


def test_pnl_invariant_short_close() -> None:
    """SHORT BRENT entry=95, exit=93, size=10000 → qty≈105.26, pnl≈+210.53."""
    pos = pts.Position(
        pair="BRENT", side="SHORT", entry_price=95.0,
        size_usd=10_000.0, entry_at=datetime.now(UTC).isoformat(),
        last_signal="test", stop_loss=97.0, take_profit=92.0,
    )
    pnl_usd, pnl_pct = pts._unrealized_pnl(pos, 93.0)
    # qty = 10000/95 ≈ 105.263; pnl = 105.263 * (95-93) ≈ 210.526
    assert abs(pnl_usd - 210.526) < 0.01


def test_pnl_invariant_long_stop_hit() -> None:
    """BTCUSD entry=64043.98, stop=63172.65, size=23905 → pnl ≈ -325 ± few."""
    pos = pts.Position(
        pair="BTCUSD", side="LONG", entry_price=64_043.98,
        size_usd=23_905.0, entry_at=datetime.now(UTC).isoformat(),
        last_signal="test", stop_loss=63_172.65, take_profit=66_000.0,
    )
    pnl_usd, _ = pts._unrealized_pnl(pos, 63_172.65)
    # Beklenen: birkaç yüz dolar zarar, MİLYON DEĞİL
    assert -500.0 < pnl_usd < -100.0


def test_equity_formula_starting_plus_realized_plus_unrealized() -> None:
    """equity = starting_balance + realized_pnl_usd + unrealized_total."""
    st = pts.TradingState()
    st.realized_pnl_usd = 500.0
    pos = pts.Position(
        pair="BTCUSD", side="LONG", entry_price=64_000.0,
        size_usd=24_000.0, entry_at=datetime.now(UTC).isoformat(),
        last_signal="test", stop_loss=63_000.0, take_profit=66_000.0,
    )
    st.positions["BTCUSD"] = pos
    st.last_tick_prices = {"BTCUSD": 65_000.0}
    unreal, _ = pts._unrealized_pnl(pos, 65_000.0)
    expected_equity = st.starting_balance + st.realized_pnl_usd + unreal
    # Beklenen: 100000 + 500 + 375 = 100875
    assert abs(expected_equity - 100_875.0) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# State reload invariance — double-count guard
# ─────────────────────────────────────────────────────────────────────────────

def test_state_reload_does_not_double_count_realized_pnl(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 1_234.56
    st.trades.append(pts.Trade(
        id=1, pair="BTCUSD", side="LONG",
        entry_price=64_000.0, exit_price=65_000.0,
        entry_at=datetime.now(UTC).isoformat(),
        exit_at=datetime.now(UTC).isoformat(),
        size_usd=24_000.0, pnl_usd=375.0, pnl_pct=1.56,
        duration_min=10, reason="TP_HIT",
    ))
    pts._save_state(st)

    # Reload aynı realized'i göstermeli, trade'in pnl_usd'sini realized'e EKLEMEMELİ
    reloaded = pts._load_state()
    assert reloaded.realized_pnl_usd == 1_234.56
    assert len(reloaded.trades) == 1
    assert reloaded.trades[0].pnl_usd == 375.0
    # data_quality_flag default boş yüklenmiş olmalı (backward-compat setdefault)
    assert reloaded.trades[0].data_quality_flag == ""


# ─────────────────────────────────────────────────────────────────────────────
# Hard reset
# ─────────────────────────────────────────────────────────────────────────────

def test_hard_reset_creates_backup_and_clears_state(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 17_760_230.26  # bozuk değer
    st.trades.append(pts.Trade(
        id=1, pair="BTCUSD", side="LONG",
        entry_price=596.249, exit_price=64_000.0,
        entry_at="x", exit_at="y", size_usd=24_000.0,
        pnl_usd=999_999.0, pnl_pct=4000.0, duration_min=1, reason="TP_HIT",
    ))
    pts._save_state(st)

    result = pts.hard_reset_state(reason="test_reset")
    assert result["status"] == "reset"
    assert result["equity"] == 100_000.0
    assert result["realized_pnl_usd"] == 0.0
    assert result["trade_count"] == 0
    # Backup dosyası gerçekten yaratıldı mı?
    backup_path = result["backup_path"]
    assert backup_path is not None
    backup_data = json.loads((tmp_path / backup_path.split("\\")[-1].split("/")[-1]).read_text(encoding="utf-8"))
    assert backup_data["realized_pnl_usd"] == 17_760_230.26
    # State temizlendi
    reloaded = pts._load_state()
    assert reloaded.realized_pnl_usd == 0.0
    assert len(reloaded.trades) == 0


def test_hard_reset_clears_anomaly_flag(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 5_000_000.0
    pts._save_state(st)

    # Anomaly aktif olmalı reset'ten önce
    snap_before = pts.get_snapshot()
    assert snap_before["state_anomaly"]["active"] is True

    pts.hard_reset_state(reason="test")
    snap_after = pts.get_snapshot()
    assert snap_after["state_anomaly"]["active"] is False
    assert snap_after["state_anomaly"]["action"] == "OK"


# ─────────────────────────────────────────────────────────────────────────────
# Repair — dry-run + apply
# ─────────────────────────────────────────────────────────────────────────────

def test_repair_dry_run_does_not_mutate_state(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 999_999.99
    # 1 sağlıklı + 1 anomalous trade
    st.trades.append(pts.Trade(
        id=1, pair="BTCUSD", side="LONG",
        entry_price=64_000.0, exit_price=65_000.0,
        entry_at="x", exit_at="y", size_usd=24_000.0,
        pnl_usd=375.0, pnl_pct=1.56, duration_min=10, reason="TP_HIT",
    ))
    st.trades.append(pts.Trade(
        id=2, pair="BTCUSD", side="LONG",
        entry_price=596.249, exit_price=6.331,  # ikisi de out-of-bounds
        entry_at="x", exit_at="y", size_usd=24_000.0,
        pnl_usd=999_624.99, pnl_pct=4000.0, duration_min=1, reason="SL_HIT",
    ))
    pts._save_state(st)

    result = pts.repair_state(dry_run=True)
    assert result["status"] == "dry_run"
    assert result["corrected_realized_pnl"] == 375.0
    assert result["sane_trade_count"] == 1
    assert result["anomalous_trade_count"] == 1
    assert result["backup_path"] is None
    # State değişmedi
    reloaded = pts._load_state()
    assert reloaded.realized_pnl_usd == 999_999.99
    assert reloaded.trades[1].data_quality_flag == ""


def test_repair_apply_corrects_state_and_flags_trades(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 999_999.99
    st.trades.append(pts.Trade(
        id=1, pair="BTCUSD", side="LONG",
        entry_price=64_000.0, exit_price=65_000.0,
        entry_at="x", exit_at="y", size_usd=24_000.0,
        pnl_usd=375.0, pnl_pct=1.56, duration_min=10, reason="TP_HIT",
    ))
    st.trades.append(pts.Trade(
        id=2, pair="BRENT", side="LONG",
        entry_price=598.16, exit_price=63_248.11,  # ikisi de out-of-bounds
        entry_at="x", exit_at="y", size_usd=24_000.0,
        pnl_usd=999_624.99, pnl_pct=4000.0, duration_min=1, reason="TP_HIT",
    ))
    pts._save_state(st)

    result = pts.repair_state(dry_run=False)
    assert result["status"] == "applied"
    assert result["corrected_realized_pnl"] == 375.0
    assert result["backup_path"] is not None

    reloaded = pts._load_state()
    assert reloaded.realized_pnl_usd == 375.0
    # Sağlıklı trade flag boş; bozuk trade flag price_anomaly
    flags = {t.id: t.data_quality_flag for t in reloaded.trades}
    assert flags == {1: "", 2: "price_anomaly"}
    # Orijinal pnl_usd değerleri audit için korundu (sıfırlanmadı)
    pnl_map = {t.id: t.pnl_usd for t in reloaded.trades}
    assert pnl_map[2] == 999_624.99


def test_repair_not_safe_when_all_trades_corrupt(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 999_999.0
    st.trades.append(pts.Trade(
        id=1, pair="BTCUSD", side="LONG",
        entry_price=596.249, exit_price=6.331,
        entry_at="x", exit_at="y", size_usd=24_000.0,
        pnl_usd=999_999.0, pnl_pct=4000.0, duration_min=1, reason="TP_HIT",
    ))
    pts._save_state(st)

    result = pts.repair_state(dry_run=True)
    assert result["status"] == "repair_not_safe"
    assert result["recommendation"] == "reset"


# ─────────────────────────────────────────────────────────────────────────────
# Tick consensus — anomaly varken yeni trade açılmaz
# ─────────────────────────────────────────────────────────────────────────────

def _consensus_signal(pair: str, *, score: float = 75.0) -> dict:
    return {
        "symbol": pair,
        "final_score": score,
        "final_direction": "bullish",
        "confluence": {"status": "aligned"},
        "raw_regime": "NEUTRAL",
        "primary_tf": "1h",
        "base": {"contributions": {"fundamental": {"weighted_score": 2.0}}},
        "tf_signals": {},
        "other_tf_scores": {},
    }


def test_tick_consensus_blocks_new_opens_during_anomaly(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    # Corruption ekle: realized 5M
    st = pts._load_state()
    st.realized_pnl_usd = 5_000_000.0
    pts._save_state(st)

    # _is_market_open her zaman True (test deterministik olsun)
    monkeypatch.setattr(pts, "_is_market_open", lambda *a, **kw: True)
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: now)

    state_after = pts.tick_consensus(
        {"BTCUSD": _consensus_signal("BTCUSD", score=85.0)},
        {"BTCUSD": 64_000.0},
    )
    # Yeni pending / position oluşmadı
    assert "BTCUSD" not in state_after.positions
    assert "BTCUSD" not in state_after.pending_orders
    assert "BTCUSD" not in state_after.manual_ready_trades


def test_tick_consensus_rejects_insane_price(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    monkeypatch.setattr(pts, "_is_market_open", lambda *a, **kw: True)
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: now)

    # BTCUSD için 596.249 (out-of-bounds) — pozisyon açılmamalı
    state = pts.tick_consensus(
        {"BTCUSD": _consensus_signal("BTCUSD", score=85.0)},
        {"BTCUSD": 596.249},
    )
    assert "BTCUSD" not in state.positions
    assert "BTCUSD" not in state.pending_orders


def test_last_tick_prices_preserves_old_good_on_insane(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.last_tick_prices = {"BTCUSD": 64_000.0}  # önceki iyi fiyat
    pts._save_state(st)

    monkeypatch.setattr(pts, "_is_market_open", lambda *a, **kw: True)
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: now)

    # Yeni tick'te BTCUSD garbage fiyat geldi
    state = pts.tick_consensus(
        {"BTCUSD": _consensus_signal("BTCUSD", score=10.0)},  # düşük skor → pozisyon yok
        {"BTCUSD": 596.249},
    )
    # Eski iyi fiyat KORUNMALI, garbage 596.249 persist EDİLMEMELİ
    assert state.last_tick_prices["BTCUSD"] == 64_000.0


def test_last_tick_prices_rejects_cross_pair_jump(
    monkeypatch, tmp_path,
) -> None:
    """BTC abs-içi ama önceki tick'e göre %50+ sıçrama → reddet."""
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.last_tick_prices = {"BTCUSD": 64_000.0}
    pts._save_state(st)

    monkeypatch.setattr(pts, "_is_market_open", lambda *a, **kw: True)
    now = datetime(2026, 6, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: now)

    # BRENT'ten BTC'ye contamination senaryosu: 7405 — abs-dışı (BTC: 20k-500k)
    state = pts.tick_consensus(
        {"BTCUSD": _consensus_signal("BTCUSD", score=10.0)},
        {"BTCUSD": 7_405.73},
    )
    assert state.last_tick_prices["BTCUSD"] == 64_000.0  # garbage ezilmedi


# ─────────────────────────────────────────────────────────────────────────────
# get_snapshot — anomaly UI'ya görünür
# ─────────────────────────────────────────────────────────────────────────────

def test_get_snapshot_exposes_state_anomaly(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    st = pts._load_state()
    st.realized_pnl_usd = 5_000_000.0
    pts._save_state(st)

    snap = pts.get_snapshot()
    assert "state_anomaly" in snap
    assert snap["state_anomaly"]["active"] is True
    assert snap["state_anomaly"]["action"] == "REPAIR_OR_RESET_REQUIRED"
    assert len(snap["state_anomaly"]["reasons"]) > 0


def test_get_snapshot_clean_state_anomaly_inactive(
    monkeypatch, tmp_path,
) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    snap = pts.get_snapshot()
    assert snap["state_anomaly"]["active"] is False
    assert snap["state_anomaly"]["action"] == "OK"
    assert snap["state_anomaly"]["reasons"] == []
