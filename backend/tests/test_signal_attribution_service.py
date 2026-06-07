"""Signal Attribution Service testleri.

Modül bazlı PnL attribution: hangi modül kazandırıyor / kaybettiriyor?
"""
from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any

# numpy importları teknik provider'da var → test ortamında stub
sys.modules.setdefault("numpy", types.SimpleNamespace())

from app.services import signal_attribution_service as sas


@dataclass
class _FakeTrade:
    id:          int
    pair:        str
    side:        str
    entry_price: float = 60000.0
    exit_price:  float = 61200.0
    entry_at:    str = "2026-06-05T00:00:00+00:00"
    exit_at:     str = "2026-06-05T01:00:00+00:00"
    size_usd:    float = 25000.0
    pnl_usd:     float = 0.0
    pnl_pct:     float = 0.0
    duration_min: int = 60
    reason:      str = "test"
    open_signal: dict[str, Any] = field(default_factory=dict)
    exit_signal: dict[str, Any] = field(default_factory=dict)
    verdict:     str = ""
    fingerprint: str = "test_fp"
    risk_plan:   dict[str, Any] = field(default_factory=dict)


def _signal_with_contribs(touche: float = 12.0, fundamental: float = 8.0,
                           news: float = 5.0, sentinel: float = 15.0,
                           quantum: float = 10.0, chart_pattern: float = 6.0) -> dict[str, Any]:
    return {
        "final_score":     65.0,
        "final_direction": "bullish",
        "base": {
            "contributions": {
                "touche":        {"weighted_score": touche},
                "fundamental":   {"weighted_score": fundamental},
                "news":          {"weighted_score": news},
                "sentinel":      {"weighted_score": sentinel},
                "quantum":       {"weighted_score": quantum},
                "chart_pattern": {"weighted_score": chart_pattern},
            }
        },
    }


def _reset() -> None:
    sas.reset()


# ── 1) Tek trade için pay dağılımı ───────────────────────────────────────────

def test_record_trade_distributes_pnl_proportional_to_module_weighted_scores() -> None:
    _reset()
    # Sentinel %33.3, touche/quantum eşit, en küçük news/chart_pattern
    trade = _FakeTrade(
        id=1, pair="BTCUSD", side="LONG",
        pnl_usd=100.0, pnl_pct=1.0, verdict="WIN",
        open_signal=_signal_with_contribs(),
    )
    attr = sas.record_trade(trade)
    assert attr is not None
    assert attr.trade_id == 1
    assert attr.pair == "BTCUSD"
    assert attr.verdict == "WIN"

    # Toplam pay 1.0'a yakın olmalı (yuvarlama toleransı)
    total_share = sum(m["share"] for m in attr.module_shares.values())
    assert abs(total_share - 1.0) < 0.001

    # Toplam pnl_share, pnl_usd'ye yakın olmalı
    total_pnl = sum(m["pnl_share"] for m in attr.module_shares.values())
    assert abs(total_pnl - 100.0) < 0.1

    # En yüksek weighted_score (sentinel=15) en büyük payı almalı
    sentinel = attr.module_shares["sentinel"]
    touche   = attr.module_shares["touche"]
    assert sentinel["share"] > touche["share"]


# ── 2) Negatif PnL (LOSS) için pay yönü korunur ─────────────────────────────

def test_loss_distributes_negative_pnl_to_all_contributing_modules() -> None:
    _reset()
    trade = _FakeTrade(
        id=2, pair="BTCUSD", side="LONG",
        pnl_usd=-50.0, pnl_pct=-0.5, verdict="LOSS",
        open_signal=_signal_with_contribs(),
    )
    attr = sas.record_trade(trade)
    assert attr is not None

    for mod_payload in attr.module_shares.values():
        # Negatif PnL → her modülün payı da negatif olmalı
        assert mod_payload["pnl_share"] <= 0.0


# ── 3) Module stats — birden fazla trade'in toplamı ─────────────────────────

def test_module_stats_aggregates_across_multiple_trades() -> None:
    _reset()
    for i, pnl in enumerate([100.0, -40.0, 60.0, -30.0, 50.0], start=10):
        verdict = "WIN" if pnl > 0 else "LOSS"
        sas.record_trade(_FakeTrade(
            id=i, pair="BTCUSD", side="LONG",
            pnl_usd=pnl, pnl_pct=pnl/1000,
            verdict=verdict,
            open_signal=_signal_with_contribs(),
        ))

    stats = sas.get_module_stats()
    # 6 modülün hepsi katkı verdiği için hepsi raporlanmalı
    modules = {m["module"] for m in stats}
    assert modules >= {"touche", "fundamental", "news", "sentinel", "quantum", "chart_pattern"}

    # Her modül için trade_count 5 olmalı
    for m in stats:
        assert m["trade_count"] == 5
        assert m["wins"] + m["losses"] + m["break_even"] == 5

    # Toplam PnL'in modüller arası toplamı ~140 olmalı (100-40+60-30+50)
    total_distributed = sum(m["total_pnl_share"] for m in stats)
    assert abs(total_distributed - 140.0) < 1.0


# ── 4) Pair filtresi ────────────────────────────────────────────────────────

def test_module_stats_respects_pair_filter() -> None:
    _reset()
    sas.record_trade(_FakeTrade(
        id=20, pair="BTCUSD", side="LONG", pnl_usd=100.0,
        verdict="WIN", open_signal=_signal_with_contribs(),
    ))
    sas.record_trade(_FakeTrade(
        id=21, pair="XAUUSD", side="LONG", pnl_usd=-50.0,
        verdict="LOSS", open_signal=_signal_with_contribs(),
    ))

    btc_only = sas.get_module_stats(pair_filter="BTCUSD")
    for m in btc_only:
        assert m["trade_count"] == 1
        assert m["wins"] == 1

    xau_only = sas.get_module_stats(pair_filter="XAUUSD")
    for m in xau_only:
        assert m["trade_count"] == 1
        assert m["losses"] == 1


# ── 5) Hatalı/boş open_signal güvenli iniş ──────────────────────────────────

def test_record_trade_with_missing_contributions_returns_empty_shares() -> None:
    _reset()
    trade = _FakeTrade(
        id=30, pair="BTCUSD", side="LONG",
        pnl_usd=50.0, verdict="WIN",
        open_signal={"final_score": 60.0},   # no base.contributions
    )
    attr = sas.record_trade(trade)
    assert attr is not None
    assert attr.module_shares == {}


def test_record_trade_with_none_open_signal_does_not_crash() -> None:
    _reset()
    trade = _FakeTrade(id=31, pair="BTCUSD", side="LONG", pnl_usd=10.0,
                      verdict="BREAK_EVEN", open_signal={})
    attr = sas.record_trade(trade)
    assert attr is not None
    assert attr.module_shares == {}


# ── 6) Summary endpoint — best/worst module ─────────────────────────────────

def test_summary_identifies_best_and_worst_modules() -> None:
    _reset()
    # Sentinel'i ağır kazandırıcı yapacak şekilde 2 WIN trade
    sas.record_trade(_FakeTrade(
        id=40, pair="BTCUSD", side="LONG", pnl_usd=200.0, verdict="WIN",
        open_signal=_signal_with_contribs(sentinel=20.0, touche=2.0,
                                         fundamental=2.0, news=2.0,
                                         quantum=2.0, chart_pattern=2.0),
    ))
    summary = sas.summary()
    assert summary["trade_count"] >= 1
    assert summary["best_module"] is not None
    # Sentinel ağır olduğu için best_module sentinel olmalı
    assert summary["best_module"] == "sentinel"
