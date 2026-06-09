"""
FAZ 13 — Event Calendar Context testleri.

Kapsam:
  1. CPI katalog event varsa event_calendar_note dolu
  2. CPI expectation yoksa "beklenti kaydı yok" içeriyor
  3. Savaş haberi varsa event_story savaş fiyatlaması söylüyor
  4. Brent düşüş + BTC destek → price_story ikisini de söylüyor
  5. Boş snapshot → tüm alanlar "yok" mesajı döndürüyor
  6. Headline only "mixed" olmuyor — market_thought dolu
  7. Position varken de market_thought piyasa fikri içeriyor
  8. Haber keyword CPI taraması çalışıyor
  9. next_trigger flip_conditions'dan geliyor
  10. market_pricing_note senaryo olasılığı içeriyor
  11. Web scrape/mock veri yok — "beklenti kaydı yok" doğru yazılıyor
"""
from __future__ import annotations

import pytest

from app.services.event_calendar_context import build_event_calendar_context


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _report(**kwargs) -> dict:
    """Minimal test raporu oluştur."""
    base = {
        "macro_layer":          {"regime": "TRANSITIONING", "confidence_pct": 60,
                                 "dxy_signal": "NÖTR (100.01) — belirgin baskı yok",
                                 "energy_signal": "İZLE (91 $)"},
        "appetite_layer":       {"status": "MODERATE", "summary": "orta risk iştahı"},
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


# ── 1. CPI katalog event → event_calendar_note dolu ─────────────────────────

def test_cpi_catalyst_fills_event_calendar_note():
    report = _report(upcoming_catalysts=[{
        "id": "cpi_june",
        "name": "ABD CPI Haziran",
        "days_until": 1,
        "importance": "HIGH",
        "expectation": "",
    }])
    ctx = build_event_calendar_context(report)
    assert ctx["event_calendar_note"] != "event beklenti kaydı yok"
    assert "CPI" in ctx["event_calendar_note"] or "cpi" in ctx["event_calendar_note"].lower()
    assert "Yarın" in ctx["event_calendar_note"] or "Bugün" in ctx["event_calendar_note"]


# ── 2. CPI expectation boşsa "beklenti kaydı yok" yazar ─────────────────────

def test_cpi_without_expectation_says_kayit_yok():
    report = _report(upcoming_catalysts=[{
        "id": "cpi_june",
        "name": "ABD CPI",
        "days_until": 1,
        "importance": "HIGH",
        "expectation": "",    # boş
    }])
    ctx = build_event_calendar_context(report)
    note = ctx["event_calendar_note"]
    assert "beklenti kaydı yok" in note.lower()
    # Uydurma rakam/yüzde yazılmamalı
    import re
    assert not re.search(r"%\d+\.\d+", note), "Uydurma beklenti rakamı!"


# ── 3. Savaş haberi → event_story fiyatlama diyor ────────────────────────────

def test_war_news_fills_event_story():
    report = _report(news_headlines=[{
        "title":     "Iran fires missiles at US troops near Hormuz strait",
        "sentiment": "BEARISH",
        "relevance": "HIGH",
        "source":    "Reuters",
    }])
    ctx = build_event_calendar_context(report)
    story = ctx["event_story"]
    assert "Jeopolitik başlık yok" not in story
    assert len(story) > 20  # anlamlı içerik var


# ── 4. Brent düşüş + BTC destek → price_story ikisini içeriyor ──────────────

def test_price_story_brent_and_btc():
    report = _report(
        asset_signals=[
            {"asset_code": "BTCUSD", "asset_action": "LONG_AWAIT", "value": 61000},
            {"asset_code": "BRENT",  "asset_action": "SHORT",      "value": 85.5},
        ],
        macro_layer={"regime": "TRANSITIONING", "confidence_pct": 55,
                     "dxy_signal": "NÖTR (101.5)", "energy_signal": "düş eğilimi"},
        appetite_layer={"status": "MODERATE"},
    )
    ctx = build_event_calendar_context(report)
    ps = ctx["price_story"]
    assert "BTC" in ps
    assert "Brent" in ps or "85" in ps


# ── 5. Boş snapshot → varsayılan "yok" mesajları ────────────────────────────

def test_empty_report_returns_defaults():
    ctx = build_event_calendar_context({})
    assert ctx["event_calendar_note"] == "event beklenti kaydı yok"
    assert "yok" in ctx["price_story"].lower() or "veri" in ctx["price_story"].lower()
    assert "yok" in ctx["next_trigger"].lower()


# ── 6. market_thought "kayıt yok" dışında dolu ───────────────────────────────

def test_market_thought_not_just_mixed():
    report = _report(
        asset_signals=[{"asset_code": "BTCUSD", "asset_action": "LONG_AWAIT", "value": 62000}],
        scenarios=[
            {"key": "bull", "label": "Boğa", "probability_pct": 40},
            {"key": "bear", "label": "Ayı",  "probability_pct": 20},
        ],
    )
    ctx = build_event_calendar_context(report)
    thought = ctx["market_thought"]
    # "mixed" veya "1 işlem var" gibi kısa/anlamsız değil
    assert len(thought) > 30
    assert "mixed" not in thought.lower()


# ── 7. Pozisyon varken bile market_thought piyasa fikri içeriyor ─────────────

def test_market_thought_with_position():
    """Position flag build_event_calendar_context'e geçmez — sadece snapshot_report bazlı."""
    report = _report(
        macro_layer={"regime": "RISK_ON", "confidence_pct": 72,
                     "dxy_signal": "DÜŞÜK (99.5)", "energy_signal": "yatay"},
        appetite_layer={"status": "STRONG"},
    )
    ctx = build_event_calendar_context(report)
    thought = ctx["market_thought"]
    assert "risk-on" in thought.lower() or "güçlü" in thought.lower()


# ── 8. Haber keyword CPI taraması ────────────────────────────────────────────

def test_news_keyword_cpi_detected():
    report = _report(news_headlines=[{
        "title":     "US CPI data releases higher than expected",
        "sentiment": "BEARISH",
        "relevance": "HIGH",
        "source":    "Bloomberg",
    }])
    ctx = build_event_calendar_context(report)
    note = ctx["event_calendar_note"]
    assert "CPI" in note
    assert "beklenti kaydı yok" in note.lower()  # expectation rakamı yok


# ── 9. next_trigger flip_conditions'dan geliyor ──────────────────────────────

def test_next_trigger_from_flip_conditions():
    report = _report(flip_conditions=[
        {"direction": "AL", "conditions": ["BTC $60,000 desteği geri alım", "DXY 103 altı"]}
    ])
    ctx = build_event_calendar_context(report)
    assert "BTC" in ctx["next_trigger"] or "60,000" in ctx["next_trigger"]


def test_next_trigger_empty_when_no_flip():
    ctx = build_event_calendar_context(_report())
    assert ctx["next_trigger"] == "tetikleyici kaydı yok"


# ── 10. market_pricing_note senaryo olasılığı içeriyor ──────────────────────

def test_market_pricing_note_has_scenarios():
    report = _report(scenarios=[
        {"key": "bull", "label": "Boğa", "probability_pct": 45},
        {"key": "base", "label": "Baz",  "probability_pct": 35},
        {"key": "bear", "label": "Ayı",  "probability_pct": 20},
    ])
    ctx = build_event_calendar_context(report)
    note = ctx["market_pricing_note"]
    assert "45" in note or "20" in note  # olasılık yazıldı


# ── 11. FOMC katalog varsa beklenti olmadan "beklenti kaydı yok" ──────────────

def test_fomc_catalyst_no_expectation():
    report = _report(upcoming_catalysts=[{
        "id": "fomc_june",
        "name": "FOMC Toplantısı",
        "days_until": 2,
        "importance": "CRITICAL",
        "expectation": "N/A",
    }])
    ctx = build_event_calendar_context(report)
    note = ctx["event_calendar_note"]
    assert "beklenti kaydı yok" in note.lower()
    assert "FOMC" in note or "fomc" in note.lower() or "Toplantı" in note
