"""
FAZ 14 — News-aware banner headline + news_story testleri.

Kapsam:
  1. War headline + VIX up → news_story savaş/risk içeriyor
  2. War headline + Brent down → "Brent geri" / "panik değil"
  3. War headline + fiyat teyidi yok → jeopolitik not
  4. Crypto crash → news_story BTC/ETH zayıf
  5. Metals crash → news_story Gold/Silver zayıf
  6. Crypto asset_signals → price_story BTC/ETH zayıf (event_calendar_context)
  7. Metals asset_signals → price_story Gold/Silver zayıf (event_calendar_context)
  8. Open position → headline sadece pozisyon sayısı değil; haber varsa içerir
  9. No position + no news → headline "mixed" veya yasak cümle değil
  10. source_news_titles son haberleri içeriyor
  11. Haber yoksa news_story boş
"""
from __future__ import annotations

import pytest

from app.services.agent_banner_service import (
    _build_news_story,
    _classify_headlines,
)
from app.services.event_calendar_context import build_event_calendar_context


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _news(title: str, relevance: str = "HIGH", sentiment: str = "BEARISH") -> dict:
    return {"title": title, "relevance": relevance, "sentiment": sentiment, "source": "Test"}


def _sig(code: str, action: str, value: float = 100.0) -> dict:
    return {"asset_code": code, "asset_action": action, "value": value}


def _report(**kwargs) -> dict:
    base: dict = {
        "macro_layer":          {"regime": "TRANSITIONING", "confidence_pct": 60,
                                 "dxy_signal": "NÖTR (100.0)", "energy_signal": "yatay"},
        "appetite_layer":       {"status": "MODERATE"},
        "asset_signals":        [],
        "confirmation_checklist": [],
        "scenarios":            [],
        "asymmetry":            {},
        "flip_conditions":      [],
        "news_headlines":       [],
        "upcoming_catalysts":   [],
    }
    base.update(kwargs)
    return base


def _fake_ctx(**kwargs) -> dict:
    base: dict = {
        "open_positions":       [],
        "anomaly_active":       False,
        "anomaly_reasons":      [],
        "latest_snapshot":      None,
        "prev_snapshot":        None,
        "snapshot_decision":    None,
        "prev_decision":        None,
        "snapshot_report":      {},
        "latest_thesis":        None,
        "thesis_safe":          None,
        "thesis_issues":        [],
        "thesis_reasons":       [],
        "thesis_contradictions": [],
        "thesis_watchlist":     [],
        "thesis_market_view":   {},
        "thesis_asset_bias":    {},
        "latest_recheck":       None,
        "candidates":           [],
        "latest_memory":        None,
        "latest_calibration":   None,
        "active_overrides":     [],
        "news_headlines":       [],
        "asset_signals":        [],
        "macro_layer":          {},
        "news_classification":  {},
        "now":                  "2026-06-10T00:00:00+00:00",
    }
    base.update(kwargs)
    return base


# ── 1. War + VIX up → risk fiyatlaması ───────────────────────────────────────

def test_war_vix_up_news_story_contains_risk():
    cls    = _classify_headlines([_news("Iran fires missiles near Hormuz strait")])
    story  = _build_news_story(cls, [_sig("VIX", "LONG", 30)], {})
    lower  = story.lower()
    assert "risk" in lower or "savaş" in lower or "jeopolitik" in lower


# ── 2. War + Brent down → piyasa panik değil ─────────────────────────────────

def test_war_brent_down_no_panic():
    cls   = _classify_headlines([_news("Iran military strike on US forces")])
    story = _build_news_story(cls, [_sig("BRENT", "SHORT", 85)], {})
    lower = story.lower()
    assert "brent" in lower and ("geri" in lower or "panik" in lower)


# ── 3. War + no price confirmation → jeopolitik not ─────────────────────────

def test_war_no_price_confirmation():
    cls   = _classify_headlines([_news("Israel launches strikes against Hezbollah")])
    story = _build_news_story(cls, [], {})
    assert "jeopolitik" in story.lower() or "teyit" in story.lower()


# ── 4. Crypto news + BTC/ETH bearish → news_story BTC/ETH zayıf ─────────────

def test_crypto_news_with_bearish_signals():
    cls   = _classify_headlines([_news("Bitcoin and Ethereum crash on risk-off wave")])
    sigs  = [_sig("BTCUSD", "SHORT", 55000), _sig("ETHUSD", "SHORT", 2000)]
    story = _build_news_story(cls, sigs, {})
    assert "BTC" in story and ("ETH" in story or "zayıf" in story.lower())


# ── 5. Metals news + Gold+Silver bearish → Gold/Silver zayıf ─────────────────

def test_metals_news_with_bearish_signals():
    cls   = _classify_headlines([_news("Gold and Silver plunge as dollar surges")])
    sigs  = [_sig("XAUUSD", "SHORT", 2100), _sig("XAGUSD", "SHORT", 27)]
    story = _build_news_story(cls, sigs, {})
    assert "Gold" in story or "Silver" in story
    assert "zayıf" in story.lower() or "çözülüyor" in story.lower()


# ── 6. price_story: BTC+ETH both SHORT → "BTC/ETH zayıf" ────────────────────

def test_price_story_btc_eth_both_short():
    rep = _report(asset_signals=[
        _sig("BTCUSD", "SHORT", 58000),
        _sig("ETHUSD", "SHORT", 2100),
    ])
    ctx = build_event_calendar_context(rep)
    ps  = ctx["price_story"]
    assert "BTC/ETH" in ps
    assert "zayıf" in ps.lower() or "bozulmuş" in ps.lower()


# ── 7. price_story: XAUUSD+XAGUSD both SHORT → "Gold/Silver zayıf" ──────────

def test_price_story_gold_silver_both_short():
    rep = _report(asset_signals=[
        _sig("XAUUSD", "SHORT", 2090),
        _sig("XAGUSD", "SHORT", 26),
    ])
    ctx = build_event_calendar_context(rep)
    ps  = ctx["price_story"]
    assert "Gold" in ps or "Silver" in ps
    assert "zayıf" in ps.lower() or "çözülüyor" in ps.lower()


# ── 8. Open position + war news → headline pozisyon+haber içeriyor ────────────

def test_managing_position_headline_contains_news(monkeypatch):
    import app.services.agent_banner_service as abs_

    news_list = [_news("Iran sends warships to Hormuz, Brent rises")]
    cls       = _classify_headlines(news_list)
    ctx       = _fake_ctx(
        open_positions=[{"pair": "XAGUSD", "side": "LONG", "pnl_pct": -1.2, "entry_price": 30.5}],
        news_headlines=news_list,
        asset_signals=[_sig("BRENT", "LONG", 91)],
        macro_layer={"regime": "TRANSITIONING", "confidence_pct": 55,
                     "dxy_signal": "NÖTR (101.0)", "energy_signal": "yatay"},
        news_classification=cls,
    )
    monkeypatch.setattr(abs_, "_collect_context", lambda: ctx)
    banner   = abs_.build_agent_banner()
    headline = banner["headline"]

    assert "XAGUSD" in headline
    assert any(kw in headline.lower() for kw in ["savaş", "risk", "iran", "brent", "jeopolitik"])
    # Headline sadece "1 pozisyon yönetiliyor" olmamalı
    assert headline != "📊 1 açık pozisyon yönetiliyor: XAGUSD"


# ── 9. No position, no news → headline "mixed" değil ─────────────────────────

def test_waiting_headline_not_mixed_or_forbidden(monkeypatch):
    import app.services.agent_banner_service as abs_

    ctx = _fake_ctx(
        latest_thesis={"id": "t1"},
        thesis_safe=True,
        snapshot_decision="IZLE",
        thesis_market_view={"stance": "RISK_ON"},
    )
    monkeypatch.setattr(abs_, "_collect_context", lambda: ctx)
    banner   = abs_.build_agent_banner()
    headline = banner["headline"].lower()

    assert "mixed" not in headline
    assert headline not in ("piyasa izleniyor", "uygun sinyal bekliyorum", "kayıt yok")
    assert len(banner["headline"]) > 10


# ── 10. source_news_titles son haberleri içeriyor ────────────────────────────

def test_source_news_titles_populated(monkeypatch):
    import app.services.agent_banner_service as abs_

    news_list = [
        _news("CPI data hits higher than expected"),
        _news("Bitcoin drops 5% on low volume"),
        _news("FOMC meeting minutes released"),
    ]
    cls = _classify_headlines(news_list)
    ctx = _fake_ctx(news_headlines=news_list, news_classification=cls)
    monkeypatch.setattr(abs_, "_collect_context", lambda: ctx)
    banner = abs_.build_agent_banner()

    titles = banner.get("source_news_titles") or []
    assert isinstance(titles, list)
    assert len(titles) > 0
    combined = " ".join(titles)
    assert "CPI" in combined or "Bitcoin" in combined or "FOMC" in combined


# ── 11. Haber yoksa news_story boş ───────────────────────────────────────────

def test_no_news_story_is_empty():
    cls   = _classify_headlines([])
    story = _build_news_story(cls, [], {})
    assert story == ""


# ── 12. generated_at ve updated_at banner'da var ─────────────────────────────

def test_banner_has_generated_at_and_updated_at(monkeypatch):
    import app.services.agent_banner_service as abs_

    ctx = _fake_ctx()
    monkeypatch.setattr(abs_, "_collect_context", lambda: ctx)
    banner = abs_.build_agent_banner()

    assert "generated_at" in banner
    assert "updated_at" in banner
    assert banner["generated_at"] == banner["updated_at"]
