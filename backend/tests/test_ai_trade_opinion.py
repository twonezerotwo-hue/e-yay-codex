"""
AI Trade Opinion Layer testleri.

Kapsam:
  • Açık pozisyon → HOLD / REDUCE / CLOSE_WATCH opinion
  • Pozisyon yokken best_candidate veya no_trade_reason
  • Mistake memory conviction düşürür
  • Banner headline sadece pozisyon sayısı yazmaz
  • Store save/recent çalışır
  • Scheduler step mevcut
  • Paper state mutate edilmez (read-only)
"""
from __future__ import annotations

import copy
import json

import pytest

from app.services.ai_trade_opinion_service import (
    SCHEMA_VERSION,
    TRACKED_ASSETS,
    build_ai_trade_opinion,
)


# ── Sentetik context üreticiler ───────────────────────────────────────────────

def _mtf(structure_1h="BULLISH", structure_4h="BULLISH", structure_1d="BULLISH",
         price=61000.0, support=60000.0, resistance=64000.0):
    def tf(name, st):
        return {
            "timeframe": name, "structure": st, "current_price": price,
            "levels": {"support": support, "resistance": resistance, "atr": 400.0},
            "rsi_14": 50.0,
        }
    return {"1h": tf("1h", structure_1h), "4h": tf("4h", structure_4h),
            "1d": tf("1d", structure_1d)}


def _ctx(*, positions=None, mistake_pairs=(), regime="NEUTRAL", appetite="NEUTRAL",
         statuses=None, mtf_overrides=None, news=()):
    statuses = statuses or {}
    mtf_overrides = mtf_overrides or {}
    asset_signals = [
        {"asset_code": a, "status": statuses.get(a, "PENDING"),
         "action_trigger": f"{a} 1H kapanış teyidi", "value": 100.0}
        for a in TRACKED_ASSETS
    ]
    mtf = {a: mtf_overrides.get(a, _mtf()) for a in TRACKED_ASSETS}
    return {
        "now": "2026-06-10T12:00:00+00:00",
        "snapshot": {
            "report": {
                "macro_layer":    {"regime": regime},
                "appetite_layer": {"status": appetite},
                "asset_signals":  asset_signals,
                "news_headlines": list(news),
                "upcoming_catalysts": [],
            },
            "mtf": mtf,
        },
        "prev_snapshot": None,
        "thesis": None, "thesis_sanity": None,
        "paper_state": {"open_positions": positions or []},
        "rechecks": [], "learning_candidates": [],
        "mistake_memory": [{"pair": p} for p in mistake_pairs],
        "weekly_calibration": None, "auto_tune_overrides": {},
        "system_health": None,
    }


def _long_pos(pair="BRENT", entry=92.0, pnl_pct=None):
    pos = {"pair": pair, "side": "LONG", "entry_price": entry,
           "size_usd": 7000.0, "stop_loss": entry * 0.97}
    if pnl_pct is not None:
        pos["pnl_pct"] = pnl_pct
    return pos


# ── Şema & güvenlik ───────────────────────────────────────────────────────────

def test_schema_and_safety_fields():
    out = build_ai_trade_opinion(_ctx())
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["execution_mode"] == "PAPER_SAFE"
    assert out["live_execution_allowed"] is False
    assert len(out["asset_opinions"]) == len(TRACKED_ASSETS)
    for ao in out["asset_opinions"]:
        assert ao["opinion"]
        assert ao["conviction"] in ("low", "medium", "high")
        assert ao["trigger_needed"]
        assert ao["invalidation"]


# ── Açık pozisyon opinionları ────────────────────────────────────────────────

def test_open_position_profitable_aligned_is_hold():
    ctx = _ctx(positions=[_long_pos(pnl_pct=2.5)])
    out = build_ai_trade_opinion(ctx)
    po = out["open_position_opinions"][0]
    assert po["pair"] == "BRENT"
    assert po["opinion"] == "HOLD"
    assert po["invalidation"]


def test_open_position_losing_broken_short_tf_is_close_watch():
    bad = _mtf(structure_1h="BEARISH", structure_4h="BEARISH", structure_1d="BEARISH")
    ctx = _ctx(positions=[_long_pos(pnl_pct=-3.0)],
               mtf_overrides={"BRENT": bad})
    out = build_ai_trade_opinion(ctx)
    po = out["open_position_opinions"][0]
    assert po["opinion"] == "CLOSE_WATCH"


def test_open_position_losing_but_big_tf_support_is_hold():
    mixed = _mtf(structure_1h="BEARISH", structure_4h="BULLISH", structure_1d="BULLISH")
    ctx = _ctx(positions=[_long_pos(pnl_pct=-1.0)],
               mtf_overrides={"BRENT": mixed})
    out = build_ai_trade_opinion(ctx)
    assert out["open_position_opinions"][0]["opinion"] == "HOLD"


def test_open_position_profit_but_1h_flipped_is_reduce():
    mixed = _mtf(structure_1h="BEARISH", structure_4h="BULLISH", structure_1d="BULLISH")
    ctx = _ctx(positions=[_long_pos(pnl_pct=3.0)],
               mtf_overrides={"BRENT": mixed})
    out = build_ai_trade_opinion(ctx)
    assert out["open_position_opinions"][0]["opinion"] == "REDUCE"


def test_brent_war_news_but_losing_drops_conviction():
    bad = _mtf(structure_1h="BEARISH", structure_4h="BEARISH")
    ctx = _ctx(positions=[_long_pos(pnl_pct=-2.0)],
               mtf_overrides={"BRENT": bad},
               news=({"title": "US strikes Iran missile sites"},))
    out = build_ai_trade_opinion(ctx)
    po = out["open_position_opinions"][0]
    assert po["conviction"] == "low"
    assert "conviction" in po["reason"].lower() or "savaş" in po["reason"].lower()


# ── Best candidate / no trade ────────────────────────────────────────────────

def test_strong_setup_produces_best_candidate():
    ctx = _ctx(statuses={"BTCUSD": "CONFIRMED"})
    out = build_ai_trade_opinion(ctx)
    assert out["best_candidate"]["asset"] == "BTCUSD"
    assert out["best_candidate"]["bias"] == "long"
    assert out["no_trade_reason"] == ""


def test_weak_market_no_candidate_with_reason():
    weak = {a: _mtf("BEARISH", "BEARISH", "BEARISH") for a in TRACKED_ASSETS}
    ctx = _ctx(regime="DEFENSIVE", appetite="WEAK", mtf_overrides=weak)
    out = build_ai_trade_opinion(ctx)
    assert out["best_candidate"]["asset"] == "NONE"
    assert out["no_trade_reason"]


def test_avoid_when_score_low():
    weak = {a: _mtf("BEARISH", "BEARISH", "BEARISH") for a in TRACKED_ASSETS}
    ctx = _ctx(regime="DEFENSIVE", appetite="WEAK", mtf_overrides=weak,
               statuses={a: "BLOCKING" for a in TRACKED_ASSETS})
    out = build_ai_trade_opinion(ctx)
    assert all(a["opinion"] == "AVOID" for a in out["asset_opinions"])


# ── Mistake memory conviction etkisi ─────────────────────────────────────────

def test_mistake_memory_lowers_conviction():
    base = _ctx(statuses={"BTCUSD": "CONFIRMED"})
    clean = build_ai_trade_opinion(copy.deepcopy(base))
    dirty = build_ai_trade_opinion(_ctx(statuses={"BTCUSD": "CONFIRMED"},
                                        mistake_pairs=("BTCUSD", "BTCUSD")))
    order = {"low": 0, "medium": 1, "high": 2}
    c0 = next(a for a in clean["asset_opinions"] if a["asset"] == "BTCUSD")
    c1 = next(a for a in dirty["asset_opinions"] if a["asset"] == "BTCUSD")
    assert order[c1["conviction"]] < order[c0["conviction"]]
    assert any("mistake memory" in s.lower() for s in c1["against"])


# ── Read-only garanti ────────────────────────────────────────────────────────

def test_paper_state_not_mutated():
    pos = [_long_pos(pnl_pct=1.0)]
    ctx = _ctx(positions=pos)
    before = copy.deepcopy(ctx["paper_state"])
    build_ai_trade_opinion(ctx)
    assert ctx["paper_state"] == before


# ── market_opinion net olmalı ────────────────────────────────────────────────

def test_market_opinion_is_not_just_position_count():
    ctx = _ctx(positions=[_long_pos(pnl_pct=1.0)])
    out = build_ai_trade_opinion(ctx)
    mo = out["market_opinion"]
    assert "pozisyon var" not in mo.lower()
    assert "BRENT" in mo  # net asset fikri içermeli


# ── Store ────────────────────────────────────────────────────────────────────

def test_store_save_and_recent(tmp_path, monkeypatch):
    from app.storage import ai_trade_opinion_store as store
    monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "ops.jsonl")

    op = build_ai_trade_opinion(_ctx())
    oid = store.save_ai_trade_opinion(op)
    assert oid

    items = store.load_recent_ai_trade_opinions(limit=5)
    assert len(items) == 1
    rec = items[0]
    assert rec["opinion_id"] == oid
    assert rec["execution_mode"] == "PAPER_SAFE"
    assert rec["live_execution_allowed"] is False

    # bozuk satır atlanır
    with (tmp_path / "ops.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("not-json\n")
    assert len(store.load_recent_ai_trade_opinions(limit=5)) == 1


# ── Scheduler step ───────────────────────────────────────────────────────────

def test_scheduler_has_ai_trade_opinion_step():
    from app.services import scheduler_service
    assert hasattr(scheduler_service, "_run_step_ai_trade_opinion")


def test_scheduler_step_logs_opinion(tmp_path, monkeypatch):
    from app.services import scheduler_service
    from app.storage import ai_trade_opinion_store as store
    monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "ops.jsonl")
    monkeypatch.setattr(
        "app.services.ai_trade_opinion_service.collect_opinion_context",
        lambda: _ctx(),
    )
    step = scheduler_service._run_step_ai_trade_opinion()
    assert step["name"] == "ai_trade_opinion"
    assert step["status"] == "success"
    assert store.load_recent_ai_trade_opinions(limit=2)


# ── Banner entegrasyonu ──────────────────────────────────────────────────────

def test_banner_headline_uses_opinion(monkeypatch):
    """managing_position modunda headline net fikir içermeli."""
    from app.services import agent_banner_service as abs_

    fake_opinion = build_ai_trade_opinion(_ctx(positions=[_long_pos(pnl_pct=1.0)]))
    monkeypatch.setattr(
        "app.services.ai_trade_opinion_service.build_ai_trade_opinion",
        lambda ctx=None: fake_opinion,
    )
    banner = abs_.build_agent_banner()
    assert "trade_opinion_brief" in banner
    if banner["mode"] in ("managing_position", "learning", "waiting"):
        hl = banner["headline"]
        assert "açık pozisyon —" not in hl  # eski "N açık pozisyon — ..." kalıbı
