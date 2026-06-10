"""
FAZ 15 — Breaking News Visual Adapter testleri.

Kapsam:
  1. War headline → category=war, severity high/critical
  2. CPI/FOMC headline → category=macro
  3. Oil headline → affected asset BRENT
  4. Crypto headline → affected asset BTC
  5. Haber yok → degraded, crash yok
  6. NO_EXECUTION / PAPER_SAFE her durumda zorlanır
  7. Kategorisiz haberler atlanır
  8. risk_level kuralları
  9. Links node→asset üretiliyor
  10. Endpoint read-only (GET ok, POST 405)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.breaking_news_visual_adapter import (
    SCHEMA_VERSION,
    build_news_visual_payload,
)


def _news(title: str, relevance: str = "HIGH", source: str = "Test",
          published_at: str = "") -> dict:
    return {
        "title": title, "relevance": relevance, "sentiment": "BEARISH",
        "source": source, "url": "", "published_at": published_at, "tags": [],
    }


# ── 1. War → category war, severity high/critical ────────────────────────────

def test_war_headline_category_and_severity():
    payload = build_news_visual_payload([
        _news("Iran fires missiles at US base near Hormuz strait"),
    ])
    assert payload["status"] == "ok"
    node = payload["nodes"][0]
    assert node["category"] == "war"
    assert node["severity"] in ("high", "critical")
    assert "BRENT" in node["affected_assets"]
    assert "VIX" in node["affected_assets"]


# ── 2. CPI/FOMC → macro ──────────────────────────────────────────────────────

def test_macro_headline_category():
    payload = build_news_visual_payload([
        _news("US CPI data comes in hotter than expected"),
        _news("FOMC holds rates steady", relevance="MEDIUM"),
    ])
    cats = {n["category"] for n in payload["nodes"]}
    assert cats == {"macro"}
    assert payload["nodes"][0]["severity"] in ("high", "medium")


# ── 3. Oil → BRENT etkisi ────────────────────────────────────────────────────

def test_oil_headline_affects_brent():
    payload = build_news_visual_payload([
        _news("OPEC announces surprise production cut for crude oil"),
    ])
    node = payload["nodes"][0]
    assert node["category"] == "energy"
    assert "BRENT" in node["affected_assets"]
    assets = {a["asset"] for a in payload["asset_impacts"]}
    assert "BRENT" in assets


# ── 4. Crypto → BTC etkisi ───────────────────────────────────────────────────

def test_crypto_headline_affects_btc():
    payload = build_news_visual_payload([
        _news("Bitcoin slides as crypto sentiment weakens"),
    ])
    node = payload["nodes"][0]
    assert node["category"] == "crypto"
    assert "BTC" in node["affected_assets"]
    assets = {a["asset"] for a in payload["asset_impacts"]}
    assert "BTC" in assets


# ── 5. Haber yok → degraded, crash yok ───────────────────────────────────────

def test_no_news_degraded():
    for empty in (None, []):
        payload = build_news_visual_payload(empty)
        assert payload["status"] == "degraded"
        assert payload["fallback_reason"] == "no_news_data"
        assert payload["nodes"] == []
        assert payload["active_count"] == 0


# ── 6. PAPER_SAFE / NO_EXECUTION zorlanır ────────────────────────────────────

def test_paper_safe_enforced():
    ok = build_news_visual_payload([_news("Iran attack on tanker")])
    deg = build_news_visual_payload([])
    for p in (ok, deg):
        assert p["decision_permission"] == "NO_EXECUTION"
        assert p["execution_mode"] == "PAPER_SAFE"
        assert p["visual_mode"] == "event_radar"
        assert p["schema_version"] == SCHEMA_VERSION


# ── 7. Kategorisiz haber atlanır ─────────────────────────────────────────────

def test_uncategorized_headline_skipped():
    payload = build_news_visual_payload([
        _news("Local sports team wins championship"),
        _news("Iran missile strike escalates"),
    ])
    assert payload["active_count"] == 1
    assert payload["nodes"][0]["category"] == "war"


# ── 8. risk_level kuralları ──────────────────────────────────────────────────

def test_risk_level_critical_on_war():
    payload = build_news_visual_payload([
        _news("Breaking: missile attack near Hormuz", relevance="HIGH"),
    ])
    assert payload["risk_level"] == "critical"


def test_risk_level_medium_on_energy_only():
    payload = build_news_visual_payload([
        _news("Brent crude trades sideways", relevance="MEDIUM"),
    ])
    assert payload["risk_level"] == "medium"


# ── 9. Links üretiliyor ──────────────────────────────────────────────────────

def test_links_connect_node_to_assets():
    payload = build_news_visual_payload([
        _news("Iran war escalation fears rise"),
    ])
    node_id = payload["nodes"][0]["id"]
    assert len(payload["links"]) >= 3
    for link in payload["links"]:
        assert link["from"] == node_id
        assert link["direction"] in ("risk_up", "risk_down")
        assert 0 < link["strength"] <= 1


# ── 10. Endpoint read-only ───────────────────────────────────────────────────

def test_endpoint_read_only(monkeypatch):
    from app.main import app
    import app.api.breaking_news_visual as mod

    mod._CACHE = None
    monkeypatch.setattr(
        "app.storage.hourly_snapshot_store.load_recent_hourly_snapshots",
        lambda limit=1: [{"report": {"news_headlines": [
            _news("Iran strike fears push oil higher"),
        ]}}],
    )

    client = TestClient(app)
    r = client.get("/api/v1/breaking-news/visual")
    assert r.status_code == 200
    data = r.json()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["decision_permission"] == "NO_EXECUTION"
    assert data["status"] == "ok"
    assert data["active_count"] >= 1

    assert client.post("/api/v1/breaking-news/visual").status_code in (404, 405)
    assert client.delete("/api/v1/breaking-news/visual").status_code in (404, 405)
