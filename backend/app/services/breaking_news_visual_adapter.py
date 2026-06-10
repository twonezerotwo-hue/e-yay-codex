"""
FAZ 15 — Breaking News 3D Visual Adapter.

Mevcut news/report çıktısını "event radar" UI için node/asset/link
modeline çevirir. KARAR ÜRETMEZ — sadece görsel katman.

Garantiler:
  - Read-only.
  - PAPER_SAFE / NO_EXECUTION.
  - Paper trading / agent / risk gate / auto tune bu modülü kullanmaz.
  - Haber yoksa → status="degraded" veya boş nodes; crash yok.
  - Mock/synthetic veri yok.

Output schema: breaking_news_visual_v1
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "breaking_news_visual_v1"
SOURCE         = "agent_insight_or_report_news"
VISUAL_MODE    = "event_radar"

# ── Kategori keyword setleri (öncelik sıralı) ────────────────────────────────

_CATEGORY_KEYWORDS: list[tuple[str, frozenset[str]]] = [
    ("war", frozenset({
        "iran", "israel", "hormuz", "war", "missile", "attack", "strike",
        "hezbollah", "hamas", "drone", "bomb", "troops", "conflict",
        "invasion", "nuclear", "military", "helicopter", "warship",
    })),
    ("us_policy", frozenset({
        "trump", "white house", "pentagon", "tariff",
    })),
    ("macro", frozenset({
        "cpi", "fomc", "fed", "nfp", "pce", "inflation", "jobless",
        "rate decision", "payroll",
    })),
    ("energy", frozenset({
        "oil", "brent", "opec", "eia", "crude",
    })),
    ("crypto", frozenset({
        "btc", "bitcoin", "eth", "ethereum", "crypto", "stablecoin",
    })),
    ("metals", frozenset({
        "gold", "silver", "xau", "xag",
    })),
    ("risk_market", frozenset({
        "vix", "dxy", "hyg", "spy", "qqq", "nasdaq", "s&p", "dollar index",
    })),
]

_CATEGORY_LABEL: dict[str, str] = {
    "war":         "Savaş / Jeopolitik",
    "us_policy":   "ABD Politikası",
    "macro":       "Makro Veri",
    "energy":      "Enerji",
    "crypto":      "Kripto",
    "metals":      "Metaller",
    "risk_market": "Risk / Piyasa",
}

# Kategori → etkilenen assetler (+ yön)
_CATEGORY_ASSETS: dict[str, list[tuple[str, str]]] = {
    "war":         [("BRENT", "up"), ("GOLD", "up"), ("VIX", "up"), ("DXY", "up")],
    "us_policy":   [("DXY", "up"), ("VIX", "up"), ("SPY", "down")],
    "macro":       [("DXY", "up"), ("VIX", "up"), ("SPY", "down")],
    "energy":      [("BRENT", "up")],
    "crypto":      [("BTC", "down")],
    "metals":      [("GOLD", "down"), ("SILVER", "down")],
    "risk_market": [("VIX", "up"), ("DXY", "up"), ("SPY", "down")],
}

_CATEGORY_REASON: dict[str, str] = {
    "war":         "Savaş/enerji riski",
    "us_policy":   "Politika belirsizliği",
    "macro":       "Makro veri riski",
    "energy":      "Enerji arz riski",
    "crypto":      "Kripto haber akışı",
    "metals":      "Metal fiyatlaması",
    "risk_market": "Risk göstergesi",
}

_SEVERITY_STRENGTH: dict[str, float] = {
    "critical": 0.9, "high": 0.75, "medium": 0.5, "low": 0.3,
}

_MAX_NODES = 8


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _categorize(title_low: str) -> str | None:
    for cat, kws in _CATEGORY_KEYWORDS:
        if any(kw in title_low for kw in kws):
            return cat
    return None


def _severity_for(category: str, title_low: str, relevance: str) -> str:
    if category == "war":
        hot = ("breaking", "strike", "attack", "missile", "hormuz", "shoot")
        if relevance == "HIGH" or any(k in title_low for k in hot):
            return "critical"
        return "high"
    if category == "macro":
        return "high" if relevance == "HIGH" else "medium"
    if category in ("us_policy", "energy", "crypto", "metals", "risk_market"):
        return "medium" if relevance in ("HIGH", "MEDIUM") else "low"
    return "low"


def _age_minutes(published_at: str, now: datetime) -> int | None:
    if not published_at:
        return None
    try:
        ts = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        delta = (now - ts).total_seconds() / 60
        if delta < 0:
            return 0
        return int(delta)
    except (ValueError, TypeError):
        return None


def _degraded(reason: str) -> dict[str, Any]:
    return {
        "status":              "degraded",
        "schema_version":      SCHEMA_VERSION,
        "source":              SOURCE,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "visual_mode":         VISUAL_MODE,
        "risk_level":          "low",
        "active_count":        0,
        "nodes":               [],
        "asset_impacts":       [],
        "links":               [],
        "fallback_reason":     reason,
    }


# ── Ana adapter ───────────────────────────────────────────────────────────────

def build_news_visual_payload(news_headlines: list[dict] | None) -> dict[str, Any]:
    """
    news_headlines (report.news_headlines formatı) → event_radar payload.
    Karar üretmez. Read-only.
    """
    if not news_headlines:
        return _degraded("no_news_data")

    now = datetime.now(UTC)
    nodes: list[dict[str, Any]] = []
    severity_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}

    for i, n in enumerate(news_headlines):
        if not isinstance(n, dict):
            continue
        title = str(n.get("title") or "")
        if not title.strip():
            continue
        title_low = title.lower()
        cat = _categorize(title_low)
        if cat is None:
            continue
        relevance = str(n.get("relevance") or "").upper()
        sev = _severity_for(cat, title_low, relevance)
        affected = [a for a, _d in _CATEGORY_ASSETS.get(cat, [])]
        nodes.append({
            "id":              f"{cat}_{i}",
            "label":           _CATEGORY_LABEL.get(cat, cat),
            "category":        cat,
            "severity":        sev,
            "source":          str(n.get("source") or ""),
            "headline":        title[:140],
            "affected_assets": affected,
            "age_minutes":     _age_minutes(str(n.get("published_at") or ""), now),
        })

    # En şiddetli haberler önce, max _MAX_NODES
    nodes.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
    nodes = nodes[:_MAX_NODES]

    # Asset impacts + links
    impacts: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    for node in nodes:
        cat      = node["category"]
        strength = _SEVERITY_STRENGTH.get(node["severity"], 0.3)
        for asset, direction in _CATEGORY_ASSETS.get(cat, []):
            prev = impacts.get(asset)
            if prev is None or strength > prev["strength"]:
                impacts[asset] = {
                    "asset":    asset,
                    "impact":   direction,
                    "strength": strength,
                    "reason":   _CATEGORY_REASON.get(cat, cat),
                }
            links.append({
                "from":      node["id"],
                "to":        asset,
                "strength":  strength,
                "direction": "risk_up" if direction == "up" else "risk_down",
            })

    # Risk level
    sevs = {n["severity"] for n in nodes}
    if "critical" in sevs:
        risk_level = "critical"
    elif "high" in sevs:
        risk_level = "high"
    elif "medium" in sevs:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "status":              "ok",
        "schema_version":      SCHEMA_VERSION,
        "source":              SOURCE,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "visual_mode":         VISUAL_MODE,
        "risk_level":          risk_level,
        "active_count":        len(nodes),
        "nodes":               nodes,
        "asset_impacts":       sorted(impacts.values(), key=lambda x: x["strength"], reverse=True),
        "links":               links,
        "fallback_reason":     None,
    }
