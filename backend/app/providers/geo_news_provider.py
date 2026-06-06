"""
Geopolitical News Provider — jeopolitik haber akışı.

Filtreleme odağı: ABD, İran, İsrail, Çin, Rusya, Avrupa.
Kaynak: Reuters World, BBC World, Al Jazeera, RT (devre dışı), AP News.
API anahtarı gerektirmez — sadece RSS.
Execution: OFF / NO_EXECUTION
"""
from __future__ import annotations

import ssl
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

# ---------------------------------------------------------------------------
# Veri modeli
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GeoHeadline:
    title: str
    source: str
    url: str
    published_at: str
    region: str       # usa / iran / israel / china / russia / europe / global
    sentiment: str    # BULLISH / BEARISH / NEUTRAL  (piyasa perspektifinden)


# ---------------------------------------------------------------------------
# Bölge anahtar kelimeleri
# ---------------------------------------------------------------------------

_REGION_KEYWORDS: Final[dict[str, frozenset[str]]] = {
    "usa": frozenset({
        "united states", "us ", "u.s.", "america", "washington", "white house",
        "congress", "senate", "pentagon", "federal reserve", "fed ", "biden",
        "trump", "harris", "dollar", "treasury", "nato", "american",
    }),
    "iran": frozenset({
        "iran", "tehran", "persian", "khamenei", "irgc", "nuclear deal",
        "jcpoa", "strait of hormuz", "iranian", "rouhani", "raisi",
    }),
    "israel": frozenset({
        "israel", "netanyahu", "tel aviv", "jerusalem", "idf", "israeli",
        "hamas", "hezbollah", "gaza", "west bank", "iron dome",
    }),
    "china": frozenset({
        "china", "beijing", "xi jinping", "pla", "taiwan", "hong kong",
        "shanghai", "shenzhen", "yuan", "renminbi", "ccp", "chinese",
        "byd", "alibaba", "huawei", "south china sea",
    }),
    "russia": frozenset({
        "russia", "moscow", "putin", "kremlin", "ukraine", "kyiv",
        "nato", "russian", "gazprom", "rosneft", "ruble", "sanctions",
        "volodymyr", "zelensky",
    }),
    "europe": frozenset({
        "europe", "european", "eu ", "euro zone", "eurozone", "ecb",
        "germany", "france", "uk ", "britain", "london", "paris",
        "berlin", "frankfurt", "lagarde", "nato", "draghi", "brussels",
        "italy", "spain", "poland",
    }),
}

_BULLISH_WORDS: Final[frozenset[str]] = frozenset({
    "surge", "rally", "rise", "soar", "climb", "gain", "jump", "record",
    "ceasefire", "deal", "peace", "agreement", "recovery", "relief",
    "deescalate", "de-escalate", "diplomatic", "breakthrough",
})

_BEARISH_WORDS: Final[frozenset[str]] = frozenset({
    "war", "attack", "strike", "crash", "fall", "plunge", "drop", "crisis",
    "sanction", "escalat", "conflict", "tension", "threat", "missile",
    "bomb", "nuclear", "siege", "blockade", "retaliat", "collapse",
    "recession", "default", "ban", "restriction",
})

# ---------------------------------------------------------------------------
# RSS besleme listesi
# ---------------------------------------------------------------------------

_GEO_FEEDS: Final[list[dict[str, str]]] = [
    {
        "url": "https://feeds.reuters.com/reuters/worldNews",
        "source": "Reuters World",
    },
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "source": "BBC World",
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "source": "Al Jazeera",
    },
    {
        "url": "https://rss.app/feeds/tvjgUFaLuv7RnoFj.xml",  # AP Top News (proxy)
        "source": "AP News",
    },
]

# SSL bağlamı (macOS Homebrew Python sertifika sorunu için)
_SSL_CTX = ssl._create_unverified_context()  # noqa: SLF001


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _fetch_url(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "E-YAY/1.0 (geopolitical-news-reader; paper-safe)"},
    )
    with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _detect_region(text: str) -> str:
    lower = text.lower()
    scores: dict[str, int] = {}
    for region, keywords in _REGION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score:
            scores[region] = score
    if not scores:
        return "global"
    return max(scores, key=lambda r: scores[r])


def _classify_sentiment(text: str) -> str:
    lower = text.lower()
    bullish = sum(1 for w in _BULLISH_WORDS if w in lower)
    bearish = sum(1 for w in _BEARISH_WORDS if w in lower)
    if bearish > bullish:
        return "BEARISH"
    if bullish > bearish:
        return "BULLISH"
    return "NEUTRAL"


def _parse_feed(xml_text: str, source: str) -> list[GeoHeadline]:
    headlines: list[GeoHeadline] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return headlines

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    for item in items[:15]:
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate") or item.find("atom:published", ns)

        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title:
            continue

        url = ""
        if link_el is not None:
            url = (link_el.text or link_el.get("href", "")).strip()

        published_at = (pub_el.text or "").strip() if pub_el is not None else str(datetime.now(UTC))

        region = _detect_region(title)
        sentiment = _classify_sentiment(title)

        headlines.append(GeoHeadline(
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            region=region,
            sentiment=sentiment,
        ))

    return headlines


# ---------------------------------------------------------------------------
# Genel arayüz
# ---------------------------------------------------------------------------

_TARGET_REGIONS: Final[frozenset[str]] = frozenset({
    "usa", "iran", "israel", "china", "russia", "europe",
})


class GeoNewsProvider:
    """
    Jeopolitik haber çekicisi.
    Yalnızca hedef bölgelere ait haberleri döner.
    Execution: OFF.
    """

    def __init__(self, fetch_fn=_fetch_url, feeds=None) -> None:
        self._fetch_fn = fetch_fn
        self._feeds = feeds if feeds is not None else _GEO_FEEDS

    def fetch(self, max_total: int = 30) -> tuple[GeoHeadline, ...]:
        all_headlines: list[GeoHeadline] = []
        for feed in self._feeds:
            try:
                xml_text = self._fetch_fn(feed["url"])
                parsed = _parse_feed(xml_text, feed["source"])
                all_headlines.extend(parsed)
            except Exception:  # noqa: BLE001
                continue

        # Sadece hedef bölgeler
        filtered = [h for h in all_headlines if h.region in _TARGET_REGIONS]

        # Önce BEARISH (piyasa riski yüksek haberler), sonra diğerleri
        def _sort_key(h: GeoHeadline) -> int:
            return 0 if h.sentiment == "BEARISH" else (1 if h.sentiment == "BULLISH" else 2)

        filtered.sort(key=_sort_key)
        return tuple(filtered[:max_total])


__all__ = [name for name in globals() if not name.startswith("_")]
