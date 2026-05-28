"""
News provider — free RSS feeds only, no API key required.
Fetches headlines from Yahoo Finance, CoinDesk, Reuters.
fetch_fn is injectable so tests run fully offline.
Never executes trades. Read-only intelligence layer.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
import urllib.request

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewsHeadline:
    title: str
    source: str
    url: str
    published_at: str
    relevance: str   # HIGH / MEDIUM / LOW
    sentiment: str   # BULLISH / BEARISH / NEUTRAL
    tags: tuple[str, ...]


# ---------------------------------------------------------------------------
# Keyword dictionaries
# ---------------------------------------------------------------------------

_BULLISH_WORDS: Final[frozenset[str]] = frozenset({
    "surge", "rally", "rise", "soar", "climb", "gain", "jump", "record",
    "high", "bullish", "approval", "adoption", "launch", "outperform",
    "recovery", "rebound", "breakout", "strong", "growth", "expand",
    "yükseliş", "artış", "toparlanma", "rekor",
})

_BEARISH_WORDS: Final[frozenset[str]] = frozenset({
    "crash", "fall", "plunge", "drop", "decline", "tumble", "crisis",
    "ban", "restrict", "fear", "risk", "warning", "concern", "inflation",
    "recession", "collapse", "sell", "loss", "weak", "pressure", "down",
    "düşüş", "çöküş", "baskı", "resesyon", "endişe",
})

_CRYPTO_TAGS: Final[frozenset[str]] = frozenset({
    "bitcoin", "btc", "crypto", "ethereum", "eth", "blockchain",
    "stablecoin", "altcoin", "defi", "nft", "coinbase", "binance",
})

_MACRO_TAGS: Final[frozenset[str]] = frozenset({
    "fed", "federal reserve", "interest rate", "inflation", "cpi", "ppi",
    "gdp", "recession", "treasury", "yield", "dollar", "dxy", "m2",
    "powell", "fomc", "monetary", "fiscal",
})

_ENERGY_TAGS: Final[frozenset[str]] = frozenset({
    "oil", "brent", "crude", "opec", "energy", "gas", "natural gas",
    "petroleum", "refinery", "ukraine", "russia", "middle east", "war",
})

_METALS_TAGS: Final[frozenset[str]] = frozenset({
    "gold", "silver", "copper", "platinum", "palladium", "precious",
    "metals", "mining", "xau", "xag",
})

# ---------------------------------------------------------------------------
# RSS feed definitions
# ---------------------------------------------------------------------------

_RSS_FEEDS: Final[list[dict[str, str]]] = [
    {
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD,GC=F,CL=F,DX-Y.NYB&region=US&lang=en-US",
        "source": "Yahoo Finance",
    },
    {
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "source": "CoinDesk",
    },
    {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source": "Reuters",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "E-YAY/1.0 (paper-safe news reader)"},
    )
    with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _classify_sentiment(text: str) -> str:
    lower = text.lower()
    words = set(lower.split())
    bullish = len(words & _BULLISH_WORDS)
    bearish = len(words & _BEARISH_WORDS)
    if bearish > bullish:
        return "BEARISH"
    if bullish > bearish:
        return "BULLISH"
    return "NEUTRAL"


def _classify_tags(text: str) -> tuple[str, ...]:
    lower = text.lower()
    tags: list[str] = []
    if any(kw in lower for kw in _CRYPTO_TAGS):
        tags.append("crypto")
    if any(kw in lower for kw in _MACRO_TAGS):
        tags.append("macro")
    if any(kw in lower for kw in _ENERGY_TAGS):
        tags.append("energy")
    if any(kw in lower for kw in _METALS_TAGS):
        tags.append("metals")
    return tuple(tags) if tags else ("general",)


def _classify_relevance(tags: tuple[str, ...]) -> str:
    if "crypto" in tags or "macro" in tags:
        return "HIGH"
    if "energy" in tags or "metals" in tags:
        return "MEDIUM"
    return "LOW"


def _parse_rss(xml_text: str, source: str) -> list[NewsHeadline]:
    headlines: list[NewsHeadline] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return headlines

    # Handle both RSS 2.0 and Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    for item in items[:10]:  # max 10 per feed
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate") or item.find("published")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if not title:
            continue

        url = ""
        if link_el is not None:
            url = (link_el.text or link_el.get("href", "")).strip()

        published_at = pub_el.text.strip() if pub_el is not None and pub_el.text else str(datetime.now(UTC))

        tags = _classify_tags(title)
        sentiment = _classify_sentiment(title)
        relevance = _classify_relevance(tags)

        headlines.append(NewsHeadline(
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            relevance=relevance,
            sentiment=sentiment,
            tags=tags,
        ))

    return headlines


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class NewsProvider:
    """
    Fetches and classifies recent headlines from free RSS feeds.
    Inject fetch_fn for offline tests. Never makes trading decisions.
    """

    def __init__(
        self,
        fetch_fn: Callable[[str], str] = _default_fetch,
        feeds: list[dict[str, str]] | None = None,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._feeds = feeds if feeds is not None else _RSS_FEEDS

    def fetch_headlines(self, max_total: int = 20) -> tuple[NewsHeadline, ...]:
        all_headlines: list[NewsHeadline] = []
        for feed in self._feeds:
            try:
                xml_text = self._fetch_fn(feed["url"])
                parsed = _parse_rss(xml_text, feed["source"])
                all_headlines.extend(parsed)
            except Exception:  # noqa: BLE001
                # Never crash the report because news is unavailable
                continue

        # Sort by relevance: HIGH first, then MEDIUM, then LOW
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_headlines = sorted(all_headlines, key=lambda h: order.get(h.relevance, 3))
        return tuple(sorted_headlines[:max_total])


__all__ = [name for name in globals() if not name.startswith("_")]
