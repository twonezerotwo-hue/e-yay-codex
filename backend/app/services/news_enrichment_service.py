"""
News Enrichment Service — Haber kartını piyasa terminali seviyesine taşır.

Mevcut `NewsHeadline` çıktısına şu alanları ekler (deterministik, kural tabanlı):

  • severity        — RED / ORANGE / YELLOW / BLUE (kart rengi + harita marker'ı)
  • claim_status    — VERIFIED / PARTIAL / UNVERIFIED / CONTEXT_ONLY (kaynak güveni)
  • decision_impact — 1 satırlık: Risk/Paper engine bu haberi nasıl yorumladı
  • location        — coğrafi referans (ad + lat/lon + bölge kodu)
  • event_id        — stable kısa hash, frontend marker eşleştirme için

PAPER_SAFE / NO_EXECUTION — saf analiz; gerçek emir yok.

Kullanım:
    from app.providers.news_provider import NewsHeadline
    from app.services.news_enrichment_service import enrich_headlines

    enriched = enrich_headlines(headlines, regime_decision="WATCH")
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from typing import Iterable

from app.providers.news_provider import NewsHeadline, NewsLocation


# ── 1. Stratejik bölge sözlüğü ───────────────────────────────────────────────

# (anahtar kelime → (gösterim adı, lat, lon, region_code))
# Sıralama önemli: spesifik (Strait of Hormuz) genel (Iran) öncesinde olmalı.
_LOCATION_KEYWORDS: list[tuple[tuple[str, ...], NewsLocation]] = [
    # ── Chokepoints (en spesifik) ───────────────────────────────────────────
    (("strait of hormuz", "hormuz strait", "hürmüz", "hormoz"),
     NewsLocation("Strait of Hormuz", 26.57, 56.25, "CHOKE_HORMUZ")),
    (("suez canal", "süveyş kanalı", "suez"),
     NewsLocation("Suez Canal",       30.10, 32.55, "CHOKE_SUEZ")),
    (("bab el-mandeb", "bab al-mandab", "bab-el mandeb", "babül mendep"),
     NewsLocation("Bab el-Mandeb",    12.58, 43.32, "CHOKE_BAB")),
    (("south china sea", "güney çin denizi"),
     NewsLocation("South China Sea",  13.00, 115.00, "REGION_SCS")),
    (("taiwan strait", "tayvan boğazı"),
     NewsLocation("Taiwan Strait",    24.50, 119.50, "CHOKE_TAIWAN")),

    # ── Gulf / Middle East cluster ──────────────────────────────────────────
    (("persian gulf", "arabian gulf", "basra körfezi", "körfez"),
     NewsLocation("Persian Gulf",     26.50, 51.50, "REGION_GULF")),
    (("red sea", "kızıldeniz"),
     NewsLocation("Red Sea",          20.00, 38.50, "REGION_REDSEA")),
    (("gaza", "gazze", "rafah", "khan younis"),
     NewsLocation("Gaza",             31.50, 34.45, "ZONE_GAZA")),
    (("west bank", "batı şeria"),
     NewsLocation("West Bank",        32.00, 35.25, "ZONE_WBANK")),
    (("lebanon", "lübnan", "beirut", "hezbollah"),
     NewsLocation("Lebanon",          33.85, 35.85, "C_LB")),
    (("yemen", "yemen", "houthi", "husi"),
     NewsLocation("Yemen",            15.55, 48.52, "C_YE")),
    (("syria", "suriye", "damascus"),
     NewsLocation("Syria",            34.80, 38.99, "C_SY")),

    # ── Country-level (kalıp eşleşmesi) ─────────────────────────────────────
    (("israel", "israil", "netanyahu", "tel aviv", "knesset"),
     NewsLocation("Israel",           31.78, 35.21, "C_IL")),
    (("iran ", "tehran", "iranian", "khamenei", "iran's", "iran-"),
     NewsLocation("Iran",             32.43, 53.69, "C_IR")),
    (("russia", "rusya", "moscow", "putin", "kremlin"),
     NewsLocation("Russia",           61.52, 105.32, "C_RU")),
    (("ukraine", "ukrayna", "kyiv", "kiev", "zelensky"),
     NewsLocation("Ukraine",          48.38, 31.17, "C_UA")),
    (("china", "çin", "xi jinping", "beijing", "pekin", "pboc"),
     NewsLocation("China",            35.86, 104.20, "C_CN")),
    (("taiwan", "tayvan", "taipei"),
     NewsLocation("Taiwan",           23.70, 121.00, "C_TW")),
    (("japan", "japonya", "tokyo", "boj"),
     NewsLocation("Japan",            36.20, 138.25, "C_JP")),
    (("south korea", "güney kore", "seoul"),
     NewsLocation("South Korea",      35.91, 127.77, "C_KR")),
    (("north korea", "kuzey kore", "pyongyang", "kim jong"),
     NewsLocation("North Korea",      40.34, 127.51, "C_KP")),
    (("turkey", "türkiye", "ankara", "istanbul", "erdogan", "erdoğan"),
     NewsLocation("Türkiye",          39.93, 32.85, "C_TR")),
    (("saudi", "suudi", "riyadh", "mbs"),
     NewsLocation("Saudi Arabia",     23.89, 45.07, "C_SA")),
    (("uae", "emirate", "dubai", "abu dhabi", "bae"),
     NewsLocation("UAE",              23.42, 53.85, "C_AE")),
    (("qatar", "katar", "doha"),
     NewsLocation("Qatar",            25.35, 51.18, "C_QA")),
    (("iraq", "irak", "baghdad", "bağdat"),
     NewsLocation("Iraq",             33.22, 43.68, "C_IQ")),
    (("egypt", "mısır", "cairo", "kahire"),
     NewsLocation("Egypt",            26.82, 30.80, "C_EG")),
    (("opec", "opec+"),
     NewsLocation("OPEC HQ (Vienna)", 48.21, 16.37, "ORG_OPEC")),

    # ── US / Fed / Wall Street ──────────────────────────────────────────────
    (("federal reserve", "fed ", "fomc", "powell", "fed's", "fed-"),
     NewsLocation("US Federal Reserve", 38.89, -77.04, "ORG_FED")),
    (("white house", "trump", "biden", "washington", "u.s. treasury", "treasury"),
     NewsLocation("Washington DC",     38.91, -77.04, "C_US_DC")),
    (("wall street", "new york", "nyse", "nasdaq", "manhattan"),
     NewsLocation("New York",          40.71, -74.01, "C_US_NY")),
    (("united states", " us ", "u.s.", "amerika", " usa "),
     NewsLocation("United States",     39.83, -98.58, "C_US")),

    # ── Europe ──────────────────────────────────────────────────────────────
    (("european central bank", "ecb", "lagarde"),
     NewsLocation("ECB (Frankfurt)",  50.11, 8.68, "ORG_ECB")),
    (("european union", "brussels", "brüksel", "eu commission"),
     NewsLocation("EU (Brussels)",    50.85, 4.35, "ORG_EU")),
    (("germany", "almanya", "berlin", "bundesbank"),
     NewsLocation("Germany",          51.17, 10.45, "C_DE")),
    (("uk ", "united kingdom", "britain", "london", "boe", "bank of england"),
     NewsLocation("United Kingdom",   55.38, -3.44, "C_GB")),
    (("france", "fransa", "paris", "macron"),
     NewsLocation("France",           46.23, 2.21, "C_FR")),

    # ── Asia commodities ────────────────────────────────────────────────────
    (("india", "hindistan", "mumbai", "delhi", "modi"),
     NewsLocation("India",            20.59, 78.96, "C_IN")),
    (("venezuela", "caracas"),
     NewsLocation("Venezuela",        6.42, -66.59, "C_VE")),
    (("brazil", "brezilya", "brasilia"),
     NewsLocation("Brazil",           -14.24, -51.93, "C_BR")),
]


def _extract_location(title: str) -> NewsLocation | None:
    """Başlık metninden en spesifik bilinen lokasyonu çıkar. None ise yok say."""
    low = " " + title.lower() + " "
    for keywords, loc in _LOCATION_KEYWORDS:
        if any(kw in low for kw in keywords):
            return loc
    return None


# ── 2. Severity sınıflandırması ──────────────────────────────────────────────

# RED — sistemik/savaş/enerji şoku tetikleyiciler
_RED_PATTERNS = (
    r"\b(war|invasion|missile strike|airstrike|nuclear|wmd|atom|atomic)\b",
    r"\b(systemic crisis|banking collapse|bank run|liquidity crisis)\b",
    r"\b(oil shock|energy shock|opec emergency|chokepoint closed|hormuz closed|suez blocked)\b",
    r"\bsavaş\b|\bsaldırı\b|\bnükleer\b|\bişgal\b",
    r"\benerji şoku\b|\bsistemik kriz\b",
)
# ORANGE — yüksek dikkat
_ORANGE_PATTERNS = (
    r"\b(strike|attack|escalat|sanction|tariff|embargo|seizure|standoff)\b",
    r"\b(downgrade|default risk|credit warning|recession warning|rate hike surprise)\b",
    r"\b(red sea|hormuz|suez|yemen|hezbollah|houthi)\b",
    r"\bsaldırı\b|\byaptırım\b|\btarife\b|\bambargo\b|\bgerilim\b",
)
# BLUE/GREEN — destekleyici / olumlu
_BLUE_PATTERNS = (
    r"\b(ceasefire|truce|deal|agreement|peace|de-escalat|breakthrough)\b",
    r"\b(rate cut|easing|stimulus|tax cut|recovery|growth beat)\b",
    r"\bateşkes\b|\banlaşma\b|\bbarış\b|\bfaiz indirimi\b",
)


def _classify_severity(title: str, relevance: str) -> str:
    low = title.lower()
    if any(re.search(p, low) for p in _RED_PATTERNS):
        return "RED"
    if any(re.search(p, low) for p in _ORANGE_PATTERNS):
        return "ORANGE"
    if any(re.search(p, low) for p in _BLUE_PATTERNS):
        return "BLUE"
    # Fallback: relevance'a göre
    if relevance == "HIGH":
        return "ORANGE"
    if relevance == "MEDIUM":
        return "YELLOW"
    return "BLUE"


# ── 3. Claim status — kaynağa ve dil yapısına göre ───────────────────────────

# Yüksek güven kaynakları (resmi / kurumsal)
_VERIFIED_SOURCES = frozenset({
    "Federal Reserve", "Fed Reserve", "ECB", "BoE", "BoJ", "PBoC",
    "Reuters", "Bloomberg", "Associated Press", "AP", "AFP",
    "BBC World", "Wall Street Journal", "Financial Times", "Treasury",
})
# Orta güven (resmi devlet ajansları — kendi taraflı)
_PARTIAL_SOURCES = frozenset({
    "Xinhua", "TASS", "Anadolu Agency", "IRNA", "PressTV", "Al Jazeera",
    "Jerusalem Post",
})
# Belirsiz iddia göstergeleri
_UNVERIFIED_HINTS = (
    "alleged", "rumor", "rumour", "reportedly", "claims", "claim ", "iddia",
    "söylenti", "duyumu", "iddiaya göre", "haberlere göre", "kaynaklara göre",
)


def _classify_claim_status(headline: NewsHeadline) -> str:
    src = (headline.source or "").strip()
    low_title = headline.title.lower()

    # 1) Belirsiz iddia göstergesi başlıkta varsa → UNVERIFIED
    if any(h in low_title for h in _UNVERIFIED_HINTS):
        return "UNVERIFIED"
    # 2) Resmi kurumsal kaynak → VERIFIED
    if src in _VERIFIED_SOURCES:
        return "VERIFIED"
    # 3) Devlet/taraflı kaynak → PARTIAL
    if src in _PARTIAL_SOURCES:
        return "PARTIAL"
    # 4) Default: bağlam — yorum yapmaz
    return "CONTEXT_ONLY"


# ── 4. Decision impact — sistemin bu haberi nasıl yorumladığını anlat ────────

def _build_decision_impact(
    headline: NewsHeadline,
    severity: str,
    regime_decision: str | None,
) -> str:
    """Risk Engine / Paper Engine perspektifinden 1 satır yorum."""
    asset_count = len(headline.asset_impact)
    high_relevance = headline.relevance == "HIGH"
    regime = (regime_decision or "").upper()

    # Kritik tehdit
    if severity == "RED":
        return (
            "Risk Engine bu haberi tetikleyici (RED) olarak değerlendiriyor; "
            "Paper Engine yeni pozisyon açmıyor, NO_POSITION_INCREASE devrede."
        )
    # Yüksek dikkat
    if severity == "ORANGE":
        if regime in ("DEFENSIVE", "CRISIS"):
            return (
                "Mevcut savunma rejimine destek; Paper Engine yalnız manuel "
                "onaylı pozisyon kabul ediyor."
            )
        return (
            "Risk Engine WATCH seviyesine taşıyor; Paper Engine teyit "
            "(HYG/JNK, DXY) bekliyor."
        )
    # Destekleyici
    if severity == "BLUE":
        if asset_count > 0:
            return (
                "Risk Engine destekleyici sayıyor; Paper Engine sinyaller "
                "uyumluysa pozisyon adayı oluşturabilir."
            )
        return "Risk iştahını destekleyici makro bağlam; aksiyon değişikliği yok."
    # Orta veya bilgi amaçlı
    if high_relevance:
        return "Yüksek önemli bağlam haberi; tek başına karar değiştirmez, teyit aranır."
    return "Bilgi amaçlı; karar mekaniğine ek katkı yok."


# ── 5. Event ID — stable hash ────────────────────────────────────────────────

def _build_event_id(headline: NewsHeadline) -> str:
    """Başlık + kaynak + zaman üzerinden 10 karakter stable hash."""
    blob = f"{headline.title}|{headline.source}|{headline.published_at}".encode("utf-8")
    return "ev_" + hashlib.sha1(blob).hexdigest()[:8]


# ── 6. Public API ────────────────────────────────────────────────────────────

def enrich_headline(
    headline: NewsHeadline,
    *,
    regime_decision: str | None = None,
) -> NewsHeadline:
    """Tek bir NewsHeadline'ı zenginleştir.

    Mevcut alanları korur — sadece boş olan severity/claim_status/
    decision_impact/location/event_id alanlarını doldurur.
    """
    severity = headline.severity or _classify_severity(headline.title, headline.relevance)
    claim_status = headline.claim_status or _classify_claim_status(headline)
    decision_impact = headline.decision_impact or _build_decision_impact(
        headline, severity, regime_decision,
    )
    location = headline.location or _extract_location(headline.title)
    event_id = headline.event_id or _build_event_id(headline)

    return replace(
        headline,
        severity=severity,
        claim_status=claim_status,
        decision_impact=decision_impact,
        location=location,
        event_id=event_id,
    )


def enrich_headlines(
    headlines: Iterable[NewsHeadline],
    *,
    regime_decision: str | None = None,
) -> tuple[NewsHeadline, ...]:
    """Bir koleksiyondaki tüm haberleri zenginleştir."""
    return tuple(
        enrich_headline(h, regime_decision=regime_decision)
        for h in headlines
    )


__all__ = [
    "enrich_headline",
    "enrich_headlines",
]
