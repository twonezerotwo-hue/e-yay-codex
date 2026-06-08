"""
News provider — free RSS feeds only, no API key required.
Fetches headlines from Yahoo Finance, CoinDesk, Reuters.
fetch_fn is injectable so tests run fully offline.
Never executes trades. Read-only intelligence layer.
"""
from __future__ import annotations

import hashlib as _hashlib
import json as _json_mod
import time as _time
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
class AssetImpact:
    """Haberin belirli bir varlık üzerindeki tahmini etkisi."""
    asset_code: str    # "XAUUSD", "BRENT", "BTCUSD", vb.
    direction: str     # "positive" | "negative" | "neutral"
    note: str          # Kısa karar bağlamı notu


@dataclass(frozen=True)
class NewsLocation:
    """Haberin coğrafi referansı — harita panelinde marker için."""
    name: str          # "Strait of Hormuz", "Iran", "USA", vb.
    lat: float
    lon: float
    region_code: str = ""   # ISO 3166-1 alpha-2 veya 'CHOKE_HORMUZ', 'CHOKE_SUEZ', vb.


@dataclass(frozen=True)
class NewsHeadline:
    title: str
    source: str
    url: str
    published_at: str
    relevance: str              # HIGH / MEDIUM / LOW
    sentiment: str              # BULLISH / BEARISH / NEUTRAL
    tags: tuple[str, ...]
    asset_impact: tuple[AssetImpact, ...] = ()  # kural tabanlı varlık etkisi
    title_tr: str = ""          # AI ile Türkçe çevirisi (boşsa orijinal kullanılır)
    # ── Profesyonel haber alanları (geriye uyumlu, default boş) ──
    severity: str = ""          # "RED" | "ORANGE" | "YELLOW" | "BLUE" — kart rengi
    claim_status: str = ""      # "VERIFIED" | "PARTIAL" | "UNVERIFIED" | "CONTEXT_ONLY"
    decision_impact: str = ""   # 1 satır: Risk/Paper engine bunu nasıl yorumladı
    location: NewsLocation | None = None
    event_id: str = ""          # stable hash — frontend marker eşleştirme için


# ---------------------------------------------------------------------------
# Keyword dictionaries
# ---------------------------------------------------------------------------

_BULLISH_WORDS: Final[frozenset[str]] = frozenset({
    # EN — fiyat hareketi
    "surge", "rally", "rise", "soar", "climb", "gain", "jump", "record",
    "bullish", "breakout", "rebound", "recovery", "outperform",
    # EN — ekonomik pozitif
    "strong", "growth", "expand", "beat", "beats", "upside", "better-than-expected",
    "approval", "adoption", "launch", "stimulus",
    # EN — jeopolitik/makro pozitif
    "ceasefire", "deal", "agreement", "peace", "relief",
    # EN — Fed/makro dovish
    "cut", "easing", "dovish", "pause", "pivot", "rate cut", "soft landing",
    # EN — piyasa modu
    "risk-on", "risk on",
    # TR
    "yükseliş", "artış", "toparlanma", "rekor", "güçlü", "büyüme",
    "anlaşma", "ateşkes", "ferahlama", "teşvik", "faiz indirimi",
    "güven", "pozitif", "olumlu", "açılış", "yükseldi", "arttı",
    "beklentilerin üzerinde", "yumuşak iniş",
})

_BEARISH_WORDS: Final[frozenset[str]] = frozenset({
    # EN — fiyat hareketi
    "crash", "fall", "plunge", "drop", "decline", "tumble",
    "sell", "loss", "down", "downgrade",
    # EN — ekonomik negatif
    "weak", "recession", "crisis", "collapse",
    "miss", "misses", "downside", "worse-than-expected", "unemployment",
    # EN — risk/belirsizlik
    "ban", "restrict", "fear", "warning", "concern", "inflation",
    "pressure", "sanction", "tariff", "default",
    # EN — jeopolitik/askeri
    "strike", "attack", "escalat", "tension", "conflict", "war",
    # EN — Fed/makro hawkish
    "hawkish", "hike", "tighten", "rate hike",
    # EN — piyasa modu
    "risk-off", "risk off",
    # TR
    "düşüş", "çöküş", "baskı", "resesyon", "endişe", "kriz", "zayıf",
    "saldırı", "gerilim", "tırmanma", "yaptırım", "gümrük", "vergi",
    "düştü", "azaldı", "olumsuz", "negatif", "tehdit", "kaygı",
    "beklentilerin altında", "işsizlik arttı",
})

_CRYPTO_TAGS: Final[frozenset[str]] = frozenset({
    "bitcoin", "btc", "crypto", "ethereum", "eth", "blockchain",
    "stablecoin", "altcoin", "defi", "nft", "coinbase", "binance",
    "kripto", "blokzincir",
})

_MACRO_TAGS: Final[frozenset[str]] = frozenset({
    "fed", "federal reserve", "interest rate", "inflation", "cpi", "ppi",
    "gdp", "recession", "treasury", "yield", "dollar", "dxy", "m2",
    "powell", "fomc", "monetary", "fiscal", "tariff", "trade war",
    "trump", "white house", "biden", "yellen", "debt ceiling",
    # TR
    "faiz", "enflasyon", "merkez bankası", "tcmb", "büyüme", "bütçe",
    "gümrük vergisi", "ticaret savaşı",
})

_ENERGY_TAGS: Final[frozenset[str]] = frozenset({
    "oil", "brent", "crude", "opec", "energy", "gas", "natural gas",
    "petroleum", "refinery", "pipeline", "lng", "shale",
    # TR
    "petrol", "doğalgaz", "enerji", "boru hattı",
})

_METALS_TAGS: Final[frozenset[str]] = frozenset({
    "gold", "silver", "copper", "platinum", "palladium", "precious",
    "metals", "mining", "xau", "xag",
    # TR
    "altın", "gümüş", "bakır", "metal", "maden",
})

# Jeopolitik — ABD Beyaz Saray/FED · Çin · İran · İsrail · Türkiye · Rusya
_GEO_TAGS: Final[frozenset[str]] = frozenset({
    # ABD
    "trump", "white house", "pentagon", "congress", "senate", "cia",
    "nato", "state department", "washington",
    # Çin
    "china", "beijing", "xi jinping", "pboc", "pla", "taiwan",
    "çin", "pekin", "xi",
    # İran
    "iran", "tehran", "khamenei", "irgc", "nuclear", "strait of hormuz",
    "tahran", "nükleer",
    # İsrail / Orta Doğu
    "israel", "gaza", "hamas", "hezbollah", "netanyahu", "west bank",
    "idf", "rafah", "middle east", "lebanon",
    "israil", "gazze", "orta doğu", "lübnan",
    # Türkiye
    "turkey", "türkiye", "erdogan", "erdoğan", "ankara", "tcmb",
    "istanbul", "bist", "lira", "try",
    # Rusya / Ukrayna
    "russia", "ukraine", "kremlin", "putin", "zelensky", "nato",
    "rusya", "ukrayna", "putin", "zelenskiy", "moskova",
    # Genel jeopolitik
    "war", "conflict", "sanction", "airstrike", "missile",
    "geopolitic", "ceasefire", "peace talks", "refugee",
    "drone strike", "military operation", "invasion", "offensive",
    "savaş", "çatışma", "yaptırım", "ateşkes", "barış görüşmeleri",
    "askeri operasyon", "insansız hava", "füze",
})

# ---------------------------------------------------------------------------
# RSS feed definitions
# ---------------------------------------------------------------------------

_RSS_FEEDS: Final[list[dict[str, str]]] = [
    # ── Piyasa & finansal birincil ────────────────────────────────────────────
    {
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",        # CNBC Top News (geniş, taze)
        "source": "CNBC",
    },
    {
        "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",         # CNBC Economy
        "source": "CNBC Economy",
    },
    {
        "url": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",  # MarketWatch Market Pulse (taze, finansal)
        "source": "MarketWatch",
    },
    {
        "url": "https://feeds.content.dowjones.io/public/rss/RSSWSJD",         # WSJ Tech & Markets
        "source": "WSJ Markets",
    },
    {
        "url": "https://www.investing.com/rss/news_25.rss",                    # Investing.com Stock Market
        "source": "Investing.com",
    },
    {
        "url": "https://www.investing.com/rss/news_301.rss",                   # Investing.com Forex (DXY, EUR/USD)
        "source": "Investing FX",
    },
    {
        "url": "https://www.investing.com/rss/news_11.rss",                    # Investing.com Commodities (Brent, Gold)
        "source": "Investing Emtia",
    },
    # ── Kripto ────────────────────────────────────────────────────────────────
    {
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "source": "CoinDesk",
    },
    {
        "url": "https://cointelegraph.com/rss",
        "source": "Cointelegraph",
    },
    {
        "url": "https://decrypt.co/feed",
        "source": "Decrypt",
    },
    # ── Fed / Para politikası ─────────────────────────────────────────────────
    {
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "source": "Fed Reserve",
    },
    # ── Reuters (Google News proxy — doğrudan RSS kapalı) ────────────────────
    {
        "url": "https://news.google.com/rss/search?q=when:1d+site:reuters.com+(markets+OR+fed+OR+oil+OR+gold+OR+crypto)&hl=en-US&gl=US&ceid=US:en",
        "source": "Reuters",
    },
    {
        "url": "https://news.google.com/rss/search?q=when:1d+(Bloomberg+OR+\"Financial+Times\")+(markets+OR+fed+OR+oil)&hl=en-US&gl=US&ceid=US:en",
        "source": "Bloomberg/FT",
    },
    # ── Jeopolitik: Orta Doğu ─────────────────────────────────────────────────
    {
        "url": "https://www.jpost.com/Rss/RssFeedsHeadlines.aspx",
        "source": "Jerusalem Post",
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "source": "Al Jazeera",
    },
    # ── Jeopolitik: Genel dünya ───────────────────────────────────────────────
    {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "source": "BBC World",
    },
    {
        "url": "https://www.aa.com.tr/en/rss/default?cat=world",
        "source": "Anadolu Agency",
    },
]

# ---------------------------------------------------------------------------
# AI etki sınıflandırması — sabitler ve önbellek
# ---------------------------------------------------------------------------

_TRACKED_ASSETS: Final[tuple[str, ...]] = (
    "BTCUSD", "XAUUSD", "XAGUSD", "XCUUSD", "BRENT",
    "DXY", "SP500", "VIX", "HY_SPREAD", "US10Y", "TLT", "HYG",
)

# başlık md5 → ((impacts_tuple, title_tr), monotonic_timestamp)
_AI_IMP_CACHE: dict[str, tuple[tuple[tuple[AssetImpact, ...], str], float]] = {}

# RSS toplu sonuç cache — 60sn mini cache
_RSS_RESULT_CACHE: tuple[tuple["NewsHeadline", ...], float] | None = None
_AI_IMP_TTL: Final[int] = 1800  # 30 dk — Groq 8b TPD 500k limitine göre
                                 # (48 çağrı/gün × ~4.5k token = ~216k token, %43)
_RSS_CACHE_TTL: Final[int] = 60  # 60 sn — RSS fetch'i sayfa yenilemelerinde sık-fetch yapmasın

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import ssl as _ssl
_SSL_CTX = _ssl._create_unverified_context()   # macOS sertifika sorunu bypass


def _default_fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "E-YAY/1.0 (paper-safe news reader)"},
    )
    with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def _classify_sentiment(text: str) -> str:
    lower = text.lower()
    words = set(lower.split())
    # Tek kelime eşleşmeleri
    bullish = len(words & _BULLISH_WORDS)
    bearish = len(words & _BEARISH_WORDS)
    # Çok kelimeli ifade eşleşmeleri (substring)
    for phrase in ("risk-on", "risk on", "rate cut", "soft landing", "better-than-expected"):
        if phrase in lower:
            bullish += 1
    for phrase in ("risk-off", "risk off", "rate hike", "worse-than-expected"):
        if phrase in lower:
            bearish += 1
    if bearish > bullish:
        return "BEARISH"
    if bullish > bearish:
        return "BULLISH"
    return "NEUTRAL"


def _classify_tags(text: str) -> tuple[str, ...]:
    lower = text.lower()
    tags: list[str] = []
    if any(kw in lower for kw in _GEO_TAGS):
        tags.append("geo")
    if any(kw in lower for kw in _CRYPTO_TAGS):
        tags.append("crypto")
    if any(kw in lower for kw in _MACRO_TAGS):
        tags.append("macro")
    if any(kw in lower for kw in _ENERGY_TAGS):
        tags.append("energy")
    if any(kw in lower for kw in _METALS_TAGS):
        tags.append("metals")
    return tuple(tags) if tags else ("general",)


def _classify_asset_impact(title: str, sentiment: str) -> tuple[AssetImpact, ...]:
    """
    Haber başlığını tarayarak hangi asset'lerin etkilendiğini ve yönünü çıkarır.
    Sentiment doğrudan asset fiyat yönüne map edilir (BULLISH→positive, vb.).
    Karar zinciri notu dinamik olarak üretilir.
    """
    lower = title.lower()
    pos   = sentiment == "BULLISH"
    neg   = sentiment == "BEARISH"
    dirn  = "positive" if pos else ("negative" if neg else "neutral")

    impacts: list[AssetImpact] = []

    # ── Kıymetli metaller ──────────────────────────────────────────────────
    if any(kw in lower for kw in ("gold", "xau", "altın")):
        note = (
            "Hedge talebi zayıflıyor" if neg else
            "Güvenli liman talebi artıyor" if pos else
            "Altın hareketini izle"
        )
        impacts.append(AssetImpact("XAUUSD", dirn, note))

    if any(kw in lower for kw in ("silver", "xag", "gümüş")):
        note = (
            "Gümüş momentumu kırılıyor" if neg else
            "Stratejik metal talebi güçleniyor" if pos else
            "Gümüş hareketini izle"
        )
        impacts.append(AssetImpact("XAGUSD", dirn, note))

    if any(kw in lower for kw in ("copper", "bakır")):
        note = (
            "Sanayi talebi zayıflıyor" if neg else
            "Küresel büyüme teyidi güçleniyor" if pos else
            "Bakır hareketini izle"
        )
        impacts.append(AssetImpact("XCUUSD", dirn, note))

    # ── Enerji ────────────────────────────────────────────────────────────
    if any(kw in lower for kw in ("oil", "brent", "crude", "opec", "petrol")):
        note = (
            "Enerji arz riski / petrol fiyatı yükseliyor" if pos else
            "Enerji fiyatı gerileyebilir — arz baskısı azalıyor" if neg else
            "Enerji fiyatını izle"
        )
        # BRENT direction = varlığın kendi fiyat yönü (sentiment ile aynı)
        # "Oil prices climb" → BULLISH → BRENT positive (▲) — ekonomik etki ayrı değerlendirme
        impacts.append(AssetImpact("BRENT", dirn, note))

    # ── Kripto ────────────────────────────────────────────────────────────
    if any(kw in lower for kw in ("bitcoin", "btc", "crypto", "ethereum", "eth", "blockchain")):
        note = (
            "BTC risk iştahı düşüyor" if neg else
            "Kripto risk iştahı artıyor" if pos else
            "Kripto momentumu izle"
        )
        impacts.append(AssetImpact("BTCUSD", dirn, note))

    # ── Dolar / DXY ───────────────────────────────────────────────────────
    if any(kw in lower for kw in ("dollar", "dxy", "usd index")):
        note = (
            "Dolar güçleniyor — risk-off baskısı" if pos else
            "Dolar zayıflıyor — likidite açılıyor" if neg else
            "DXY seviyesini izle"
        )
        impacts.append(AssetImpact("DXY", dirn, note))

    # ── Fed / Makro / Faiz ────────────────────────────────────────────────
    if any(kw in lower for kw in ("fed", "federal reserve", "inflation", "cpi", "ppi", "fomc", "rate hike", "rate cut", "enflasyon")):
        # Hawkish macro → DXY up, BTC/altın down (genellikle)
        macro_note = (
            "Hawkish sinyal: dolar ve faizler yukarı baskıda" if neg else
            "Dovish sinyal: risk varlıkları olumlu etkilenir" if pos else
            "Makro veri etkisini izle"
        )
        impacts.append(AssetImpact("DXY", "positive" if neg else dirn, macro_note))

    # ── Kredi / Tahvil ────────────────────────────────────────────────────
    if any(kw in lower for kw in ("credit", "bond", "yield", "treasury", "hyg", "jnk", "spread")):
        note = (
            "Kredi spreadi genişliyor — risk-off" if neg else
            "Kredi koşulları iyileşiyor" if pos else
            "Kredi piyasasını izle"
        )
        impacts.append(AssetImpact("HY_SPREAD", "negative" if neg else dirn, note))

    # ── VIX / Korku ───────────────────────────────────────────────────────
    if any(kw in lower for kw in ("vix", "fear", "panic", "volatility", "war", "geopolit",
                                   "iran", "ukraine", "russia", "airstrike", "missile",
                                   "military strike", "drone strike",
                                   "savaş", "çatışma", "füze saldırısı", "gerilim")):
        note = (
            "VIX yükseliş ihtimali — yeni giriş ertelenmeli" if neg else
            "Jeopolitik risk haritasını izle"
        )
        impacts.append(AssetImpact("VIX", "positive" if neg else "neutral", note))

    # ── Trump / Beyaz Saray / Tarife ─────────────────────────────────────
    if any(kw in lower for kw in ("trump", "white house", "tariff", "trade war", "executive order",
                                   "gümrük", "ticaret savaşı")):
        dxy_note = (
            "Tarife/Trump belirsizliği — dolar baskı altında" if neg else
            "Trump politikası dolar güçlendiriyor" if pos else
            "Trump açıklamasını DXY üzerinden izle"
        )
        impacts.append(AssetImpact("DXY", dirn, dxy_note))

    # ── Çin / Beijing / Xi ───────────────────────────────────────────────
    if any(kw in lower for kw in ("china", "beijing", "xi jinping", "pboc", "çin", "pekin")):
        cu_note = (
            "Çin yavaşlaması bakır talebini baskılıyor" if neg else
            "Çin teşviki sanayi metal talebini canlandırıyor" if pos else
            "Çin verisi bakır talebini belirleyecek"
        )
        impacts.append(AssetImpact("XCUUSD", dirn, cu_note))

    # ── İsrail / Orta Doğu ───────────────────────────────────────────────
    # Burada BRENT için geopolitik risk primi mantığı: eskalasyon → BRENT↑, ateşkes → BRENT↓
    # Haberin overall sentiment'i değil, jeopolitik bağlamı belirleyici
    if any(kw in lower for kw in ("israel", "gaza", "hamas", "hezbollah", "netanyahu",
                                   "idf", "rafah", "west bank",
                                   "israil", "gazze", "lübnan")):
        # Eskalasyon kelimeleri → enerji risk primi yükselir → BRENT↑
        escalation = any(kw in lower for kw in (
            "attack", "strike", "airstrike", "bomb", "missile", "offensive",
            "invade", "escalat", "expand", "military operation",
            "saldırı", "hava saldırısı", "füze", "tırmanma", "askeri operasyon",
        ))
        deescalation = any(kw in lower for kw in (
            "ceasefire", "truce", "peace", "deal", "agreement", "hostage",
            "ateşkes", "barış", "anlaşma", "müzakere",
        ))
        if escalation:
            brent_dir, oil_note = "positive", "Orta Doğu eskalasyonu — enerji arz riski↑"
        elif deescalation:
            brent_dir, oil_note = "negative", "Orta Doğu gerilimi azalıyor — enerji risk primi düşüyor"
        else:
            brent_dir, oil_note = "neutral", "Orta Doğu gelişmelerini enerji üzerinden izle"
        impacts.append(AssetImpact("BRENT", brent_dir, oil_note))

    # ── Rusya / Ukrayna ───────────────────────────────────────────────────
    if any(kw in lower for kw in ("russia", "ukraine", "kremlin", "putin", "zelensky",
                                   "rusya", "ukrayna", "zelenskiy")):
        au_note = (
            "Rusya/Ukrayna krizi güvenli liman talebini artırıyor" if neg else
            "Rusya-Ukrayna gerilimi azalıyor — risk-on" if pos else
            "Rusya/Ukrayna haberi altın ve enerjide etki"
        )
        impacts.append(AssetImpact("XAUUSD", "positive" if neg else dirn, au_note))

    # Max 4 etki — geo hikayeler daha çok sinyal taşır
    return tuple(impacts[:4])


def _build_classifier_prompt(items: list[tuple[str, str]]) -> str:
    """Sınıflandırma + Türkçe çeviri için ortak prompt (Groq + Claude için)."""
    headlines_json = _json_mod.dumps(
        [{"title": t, "sentiment": s} for t, s in items],
        ensure_ascii=False,
        indent=2,
    )
    assets_str = ", ".join(_TRACKED_ASSETS)

    return f"""Sen bir finans haberi sınıflandırma ve çeviri asistanısın. PAPER_SAFE / NO_EXECUTION — yatırım tavsiyesi verme.

Görev: Her haber için:
  1. Başlığı doğal, anlamlı Türkçe'ye çevir (title_tr)
  2. Etkilenen finansal varlıkları belirle (impacts)

TAKİP EDİLEN VARLIKLAR: {assets_str}

ÇEVİRİ KURALLARI:
- Akıcı Türkçe — kelime kelime değil, anlam çevirisi
- Tickerleri (BTC, ETH, SPX) ve özel isimleri (Trump, Powell) DEĞİŞTİRME
- Ölçü birimlerini koru: $, %, ¥
- Başlık biçeminde — kısa, vurgulu

VARLIK ETKİSİ KURALLARI:
- Her haber için maksimum 3 varlık — yalnızca güçlü ilişkiler
- direction: "positive" (fiyat artış) | "negative" (fiyat düşüş) | "neutral"
- note: Türkçe, 4-7 kelime — neden bu varlık etkileniyor?

KILAVUZ:
- Jeopolitik gerilim/savaş/saldırı → VIX↑, XAUUSD↑, BRENT↑
- Ateşkes/barış                     → VIX↓, XAUUSD↓, BRENT↓
- Fed hawkish/faiz artışı           → DXY↑, BTCUSD↓, SP500↓
- Fed dovish/faiz indirimi          → DXY↓, BTCUSD↑, SP500↑
- CPI yüksek/sürpriz enflasyon      → DXY↑, SP500↓
- Çin teşvik/PBOC                   → XCUUSD↑, SP500↑
- BTC/kripto düzenleme              → BTCUSD, VIX
- OPEC kesinti/arz                  → BRENT↑

GİRDİ:
{headlines_json}

YALNIZCA JSON döndür. Schema:
{{
  "results": [
    {{
      "title": "<orijinal başlık — girdidekiyle BIREBIR aynı>",
      "title_tr": "<doğal Türkçe çeviri>",
      "impacts": [
        {{"asset_code": "XAUUSD", "direction": "positive", "note": "Güvenli liman talebi"}}
      ]
    }}
  ]
}}"""


def _parse_classifier_response(raw: str) -> dict[str, tuple[tuple[AssetImpact, ...], str]]:
    """AI yanıtını {title: (impacts, title_tr)} biçimine çevirir."""
    if not raw.strip().startswith("{"):
        start = raw.find("{"); end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]

    data = _json_mod.loads(raw)
    out: dict[str, tuple[tuple[AssetImpact, ...], str]] = {}
    for item in data.get("results", []):
        title = item.get("title", "")
        if not title:
            continue
        title_tr = (item.get("title_tr") or "").strip()
        impacts = tuple(
            AssetImpact(
                asset_code=imp["asset_code"],
                direction=imp.get("direction", "neutral"),
                note=imp.get("note", ""),
            )
            for imp in item.get("impacts", [])
            if imp.get("asset_code") in _TRACKED_ASSETS
        )
        out[title] = (impacts, title_tr)
    return out


def _ai_classify_batch(
    items: list[tuple[str, str]],  # [(title, sentiment), ...]
) -> dict[str, tuple[tuple[AssetImpact, ...], str]]:
    """
    Haber başlıklarını sınıflandır + Türkçe'ye çevir.
    Birincil: Groq llama-3.3-70b-versatile (ucuz, hızlı).
    Yedek: Claude haiku-4-5.
    Dönüş: {title: ((impacts), title_tr)}. Hata → boş dict (statik fallback).
    """
    if not items:
        return {}

    import os as _os
    import logging as _log
    logger = _log.getLogger(__name__)

    prompt = _build_classifier_prompt(items)

    # ── 1) GROQ (primary) ─────────────────────────────────────────────────────
    # Haber çevirisi için HAFİF model: llama-3.1-8b-instant
    # TPD limiti 100k tokenli 70b modelden 5x cömert; haberlere yeterli.
    groq_key = _os.environ.get("GROQ_API_KEY", "")
    groq_model = _os.environ.get("GROQ_NEWS_MODEL", "llama-3.1-8b-instant")
    if groq_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=groq_key,
                            base_url="https://api.groq.com/openai/v1",
                            timeout=45.0)
            resp = client.chat.completions.create(
                model=groq_model,
                max_tokens=3500,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system",
                     "content": "Sen finansal haber sınıflandırıcısı ve Türkçe çevirmensin. Yalnızca geçerli JSON döndür."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = resp.choices[0].message.content or ""
            return _parse_classifier_response(raw)
        except Exception as exc:
            logger.warning("Groq haber sınıflandırma başarısız: %s — Claude'a düşülüyor.", exc)

    # ── 2) CLAUDE (fallback) ──────────────────────────────────────────────────
    claude_key = _os.environ.get("ANTHROPIC_API_KEY", "")
    if claude_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=claude_key)
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    raw = block.text
                    break
            return _parse_classifier_response(raw)
        except Exception as exc:
            logger.error("Claude haber sınıflandırma da başarısız: %s", exc)

    return {}


def _ai_classify_headlines(
    headlines: list[NewsHeadline],
) -> dict[str, tuple[tuple[AssetImpact, ...], str]]:
    """
    AI ile haberleri toplu sınıflandır + Türkçe'ye çevir.
    Önbellek: 6 saat (çeviri token tasarrufu).
    Dönüş: {title: ((impacts), title_tr)}.

    Çeviri için TÜM relevance seviyeleri AI'a gider (LOW dahil),
    ama LOW haberlerin impacts tarafı boş tutulabilir.
    """
    now = _time.monotonic()
    results: dict[str, tuple[tuple[AssetImpact, ...], str]] = {}
    needs_ai: list[tuple[str, str]] = []

    for h in headlines:
        key = _hashlib.md5(h.title.encode("utf-8", errors="replace")).hexdigest()
        cached = _AI_IMP_CACHE.get(key)
        if cached and (now - cached[1]) < _AI_IMP_TTL:
            results[h.title] = cached[0]
        else:
            needs_ai.append((h.title, h.sentiment))

    # Token tasarrufu: tek seferde max 15 haber çevir, kalanı sonraki tetiklenmede
    if needs_ai:
        batch = _ai_classify_batch(needs_ai[:15])
        for title, value in batch.items():
            key = _hashlib.md5(title.encode("utf-8", errors="replace")).hexdigest()
            _AI_IMP_CACHE[key] = (value, now)
            results[title] = value

    return results


def _classify_relevance(tags: tuple[str, ...]) -> str:
    if "geo" in tags or "macro" in tags or "crypto" in tags:
        return "HIGH"
    if "energy" in tags or "metals" in tags:
        return "MEDIUM"
    return "LOW"


def _parse_pub_date(raw: str) -> "datetime | None":
    """RFC-2822 ve yaygın RSS/Atom tarih formatlarını UTC datetime'a çevirir."""
    if not raw:
        return None
    raw = raw.strip()

    # 1) RFC-2822 (standart RSS)
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
    except Exception:
        pass

    # 2) ISO-8601 — modern fromisoformat (3 haneli ms ile gelen veriler dahil)
    iso_try = raw.replace("Z", "+00:00")
    # 4 haneli ms gibi non-standart varyasyonları kes
    if "." in iso_try and "+" in iso_try[iso_try.index("."):]:
        head, _, tail = iso_try.partition(".")
        ms_part, plus, tz = tail.partition("+")
        if len(ms_part) > 6:
            ms_part = ms_part[:6]
        iso_try = f"{head}.{ms_part}+{tz}" if plus else f"{head}.{ms_part}"
    try:
        dt = datetime.fromisoformat(iso_try)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        pass

    # 3) Eski/manuel formatlar
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S",
        "%a, %d %b %Y %H:%M %Z",
        "%d %b %Y %H:%M:%S %z",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    return None


_MAX_AGE_HOURS: Final[int] = 24  # 24 saatten eski haberler atılır — taze haber kuralı

# Alakasız haberleri direkt eleme (finansal/jeopolitik bağlamı olmayanlar)
_DROP_PATTERNS: Final[tuple[str, ...]] = (
    "social security", "retirement", "401(k)", "401k", "medicare",
    "lifestyle", "luxury", "vacation", "wedding", "celebrity",
    "horoscope", "sports", "football", "basketball", "soccer match",
    "movie review", "tv show", "netflix", "streaming service",
    "recipe", "diet", "weight loss", "skincare",
)


def _is_irrelevant(title: str) -> bool:
    """Piyasa/jeopolitik bağlamı olmayan haberleri direkt at."""
    lower = title.lower()
    return any(p in lower for p in _DROP_PATTERNS)


def _parse_rss(xml_text: str, source: str) -> list[NewsHeadline]:
    headlines: list[NewsHeadline] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return headlines

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    now_utc = datetime.now(UTC)
    raw_items: list[tuple[datetime, NewsHeadline]] = []

    for item in items[:25]:  # feed başına 25 tara — filtre sonrası en fazla 6 kalır
        title_el = item.find("title")
        link_el  = item.find("link")
        # pubDate / dc:date / Atom published — `or` zinciri Element ile çalışmaz
        # (boş Element False değerlendirilir), bu yüzden explicit `is not None`
        pub_el = None
        for tag in (
            "pubDate",
            "atom:published",
            "published",
            "{http://purl.org/dc/elements/1.1/}date",
            "updated",
        ):
            candidate = item.find(tag, ns) if ":" in tag else item.find(tag)
            if candidate is not None:
                pub_el = candidate
                break

        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title:
            continue

        # ── Alakasız haberi direkt at (Social Security, lifestyle vs.) ──
        if _is_irrelevant(title):
            continue

        url = ""
        if link_el is not None:
            url = (link_el.text or link_el.get("href", "")).strip()

        raw_date = (pub_el.text or "").strip() if pub_el is not None else ""
        pub_dt   = _parse_pub_date(raw_date)

        # Tarih yoksa: feed'i atla (önceki "şimdiki zaman" yalanı bug'ıydı)
        if pub_dt is None:
            continue

        # 24 saatten eski haberi atla
        age_h = (now_utc - pub_dt).total_seconds() / 3600
        if age_h > _MAX_AGE_HOURS or age_h < -1:  # negatif = saat dilim hatası
            continue

        published_at = pub_dt.isoformat()

        tags         = _classify_tags(title)
        sentiment    = _classify_sentiment(title)
        relevance    = _classify_relevance(tags)
        asset_impact = _classify_asset_impact(title, sentiment)

        raw_items.append((pub_dt, NewsHeadline(
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            relevance=relevance,
            sentiment=sentiment,
            tags=tags,
            asset_impact=asset_impact,
        )))

    # En yeni önce sırala, feed başına max 6
    raw_items.sort(key=lambda x: x[0], reverse=True)
    headlines = [h for _, h in raw_items[:6]]
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

    def fetch_headlines(self, max_total: int = 30) -> tuple[NewsHeadline, ...]:
        import dataclasses as _dc
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # ── 60 sn mini cache — sayfa yenilemelerinin her birinde 17 RSS çekmeyi önler
        global _RSS_RESULT_CACHE
        now_m = _time.monotonic()
        if _RSS_RESULT_CACHE is not None:
            cached_top, cached_ts = _RSS_RESULT_CACHE
            if (now_m - cached_ts) < _RSS_CACHE_TTL:
                return cached_top

        all_headlines: list[NewsHeadline] = []

        # Tüm feed'leri paralel çek — 17 feed seri olarak 30s+ sürebilir
        def _fetch_one(feed: dict[str, str]) -> list[NewsHeadline]:
            try:
                xml_text = self._fetch_fn(feed["url"])
                return _parse_rss(xml_text, feed["source"])
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_fetch_one, f): f for f in self._feeds}
            for fut in as_completed(futures):
                all_headlines.extend(fut.result())

        # Tekrar eden başlıkları sil (farklı kaynaklar aynı haberi vermiş olabilir)
        seen: set[str] = set()
        deduped: list[NewsHeadline] = []
        for h in all_headlines:
            key = h.title.lower().strip()[:100]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(h)

        # Birleşik sıralama: önce relevance, sonra tazelik (en yeni önce)
        # Bu sayede 23 saatlik bir HIGH, 1 saatlik bir LOW'un önünde durur (HIGH önemli)
        # ama aynı relevance içinde yeni olan kazanır.
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        deduped.sort(key=lambda h: (
            order.get(h.relevance, 3),
            -_parse_pub_date(h.published_at).timestamp()  # negatif → en yeni en üstte
            if _parse_pub_date(h.published_at) else 0,
        ))
        top = deduped[:max_total]

        # AI ile varlık etkisi + Türkçe çeviri (Groq → Claude fallback)
        ai_results = _ai_classify_headlines(top)
        if ai_results:
            new_top: list[NewsHeadline] = []
            for h in top:
                pair = ai_results.get(h.title)
                if pair is None:
                    new_top.append(h)
                    continue
                impacts, title_tr = pair
                # impacts boşsa (LOW haberler) static fallback'i koru
                new_impacts = impacts if impacts else h.asset_impact
                new_top.append(_dc.replace(
                    h,
                    asset_impact=new_impacts,
                    title_tr=title_tr or h.title_tr,
                ))
            top = new_top

        result = tuple(top)

        # 60 sn mini cache — sık sayfa yenilemelerinde 17 RSS'i tekrar çekme
        globals()["_RSS_RESULT_CACHE"] = (result, _time.monotonic())

        return result


__all__ = [name for name in globals() if not name.startswith("_")]
