"""
Event Calendar Context — FAZ 13.

build_event_calendar_context(snapshot_report) -> dict

Stored snapshot verisinden piyasa fikri + olay takvimi farkındalığı üretir.

Garantiler:
  • Web scrape yok.
  • Mock / synthetic veri yok.
  • Veri yoksa açık "kayıt yok" döner.
  • Uydurma CPI beklentisi / rakam yazılmaz.
  • PAPER_SAFE / NO_EXECUTION — karar motoru etkilenmez.

Çıktı alanları:
  market_thought       — en fazla 4 cümle özet (ne değişti / ne anlama geliyor / ne bekliyorum)
  price_story          — kritik fiyat seviyeleri anlatısı
  event_story          — jeopolitik / savaş başlığı farkındalığı
  event_calendar_note  — yaklaşan yüksek etkili makro olay
  market_pricing_note  — piyasanın neyi fiyatladığı
  next_trigger         — ilk flip koşulu (AL / KÜÇÜLT)
"""
from __future__ import annotations

import re
from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

_HIGH_IMPACT_EVENTS: dict[str, str] = {
    "CPI":     "enflasyon verisi — DXY/BTC/HYG yönünü belirleyebilir",
    "FOMC":    "Fed faiz kararı — risk iştahını doğrudan etkiler",
    "NFP":     "tarım dışı istihdam — Fed beklentisini şekillendirir",
    "EIA":     "petrol envanter verisi — Brent/enerji sektörü yönü",
    "OPEC":    "üretim kararı — Brent fiyat yönü",
    "PCE":     "Fed tercihli enflasyon göstergesi",
    "PPI":     "üretici fiyatları — enflasyon öncüsü",
    "GDP":     "büyüme verisi — risk iştahı",
    "JOBLESS": "işsizlik başvuruları — istihdam sağlığı",
    "RETAIL":  "perakende satışlar — tüketim gücü",
}

# Savaş / jeopolitik sinyal kelimeleri (büyük/küçük harf bağımsız)
_WAR_KEYWORDS = frozenset({
    "war", "attack", "missile", "military", "iran", "hormuz",
    "hezbollah", "hamas", "drone", "strike", "bomb", "troops",
    "conflict", "invasion", "troops", "nuclear", "sanction",
})

_APPETITE_TR: dict[str, str] = {
    "STRONG": "güçlü risk iştahı",
    "MODERATE": "orta risk iştahı",
    "WEAK": "zayıf risk iştahı",
    "CRISIS": "kriz ortamı — risk iştahı çöktü",
}

_REGIME_TR: dict[str, str] = {
    "RISK_ON":       "risk-on",
    "TRANSITIONING": "geçiş",
    "DEFENSIVE":     "savunmacı",
    "CRISIS":        "kriz",
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _asset_value(signals: list[dict], code: str) -> float | None:
    for s in signals:
        if str(s.get("asset_code") or "").upper() == code.upper():
            return _safe_float(s.get("value"))
    return None


def _asset_action(signals: list[dict], code: str) -> str:
    for s in signals:
        if str(s.get("asset_code") or "").upper() == code.upper():
            return str(s.get("asset_action") or "")
    return ""


# ── Event calendar ─────────────────────────────────────────────────────────────

def _event_calendar_note(catalysts: list[dict], news: list[dict]) -> str:
    """
    Yaklaşan yüksek etkili makro olay notu.

    Önce upcoming_catalysts'e bak (days_until <= 3, importance HIGH/CRITICAL).
    Bulunamazsa news başlıklarında anahtar kelime ara.
    Her iki kaynakta da yoksa → "event beklenti kaydı yok".
    Beklenti rakamı (örn. CPI %X) veri yoksa yazılmaz.
    """
    # 1. Katalog kaydı
    near_events: list[dict] = []
    for c in catalysts:
        days = _safe_float(c.get("days_until"))
        imp  = str(c.get("importance") or "").upper()
        if days is not None and days <= 3 and imp in ("CRITICAL", "HIGH"):
            near_events.append(c)

    if near_events:
        ev = near_events[0]
        name = str(ev.get("name") or ev.get("id") or "Makro olay")
        days = _safe_float(ev.get("days_until")) or 0
        exp  = str(ev.get("expectation") or "").strip()
        day_str = "Bugün" if days <= 0 else ("Yarın" if days <= 1 else f"{int(days)} gün içinde")
        note = f"{day_str} {name} var; piyasa veri öncesi teyit bekliyor."
        if exp and exp.lower() not in ("n/a", "unknown", ""):
            note += f" Beklenti: {exp}."
        else:
            note += " Beklenti kaydı yok; sadece olay riski okunuyor."
        return note

    # 2. Haber başlıklarında keyword tarama
    for n in news:
        title = str(n.get("title") or "").upper()
        for kw, desc in _HIGH_IMPACT_EVENTS.items():
            if re.search(rf"\b{kw}\b", title):
                src = str(n.get("source") or "")
                src_str = f" ({src})" if src else ""
                return (
                    f"Haberlerde {kw} başlığı var{src_str}; {desc}. "
                    "Beklenti kaydı yok; sadece olay riski okunuyor."
                )

    return "event beklenti kaydı yok"


# ── Jeopolitik / savaş hikayesi ───────────────────────────────────────────────

def _event_story(news: list[dict]) -> str:
    """
    War / jeopolitik başlık varsa fiyatlama notu.
    Yoksa kısa "temiz" mesajı.
    """
    war_titles: list[str] = []
    for n in news:
        title_low = str(n.get("title") or "").lower()
        if any(kw in title_low for kw in _WAR_KEYWORDS):
            war_titles.append(str(n.get("title") or ""))

    if not war_titles:
        return "Jeopolitik başlık yok; fiyatlama normal veri akışına bakıyor."

    # En fazla 2 başlık özet
    sample = war_titles[0][:80] + ("…" if len(war_titles[0]) > 80 else "")
    count_str = f"{len(war_titles)} jeopolitik başlık" if len(war_titles) > 1 else "Jeopolitik başlık"
    return (
        f"{count_str} fiyatlamayı etkiliyor: \"{sample}\". "
        "Yeni haber gelmeden Brent/Gold yönü netleşmeyebilir."
    )


# ── Fiyat hikayesi ─────────────────────────────────────────────────────────────

def _price_story(
    signals: list[dict],
    macro: dict,
    appetite_status: str,
    confirmation: list[dict],
) -> str:
    """
    Kritik fiyat seviyesi anlatısı — BTC/Brent/DXY/HYG.
    Yalnızca gerçek sinyal değerlerini kullanır.
    """
    parts: list[str] = []

    # BTC
    btc_val    = _asset_value(signals, "BTCUSD")
    btc_action = _asset_action(signals, "BTCUSD")
    if btc_val is not None:
        if btc_action in ("LONG_AWAIT", "LONG"):
            parts.append(f"BTC ${btc_val:,.0f} destek bölgesinde; kırılım değil kapanış teyidi beklenmeli.")
        elif btc_action in ("SHORT", "AVOID"):
            parts.append(f"BTC ${btc_val:,.0f} — baskı altında, yön belirsiz.")
        else:
            parts.append(f"BTC ${btc_val:,.0f} nötr bölgede.")

    # Brent
    brent_val    = _asset_value(signals, "BRENT")
    brent_action = _asset_action(signals, "BRENT")
    energy_sig   = str(macro.get("energy_signal") or "").lower()
    if brent_val is not None:
        if "prim" in energy_sig or brent_action in ("LONG", "LONG_AWAIT"):
            parts.append(f"Brent ${brent_val:.1f} yükseliş eğiliminde; enerji riski artıyor.")
        elif "düş" in energy_sig or brent_action in ("SHORT", "AVOID"):
            parts.append(f"Brent ${brent_val:.1f} geri çekiliyor; enerji riski azalıyor ama teyit bekle.")
        else:
            parts.append(f"Brent ${brent_val:.1f} yatay seyrediyor.")

    # DXY — macro_layer'dan dxy_signal string okuma
    dxy_sig = str(macro.get("dxy_signal") or "").lower()
    if "104" in dxy_sig or dxy_sig:
        # parse value if present (format: "NÖTR (100.01) — belirgin baskı yok")
        m = re.search(r"\((\d+\.\d+)\)", dxy_sig)
        dxy_val = float(m.group(1)) if m else None
        if dxy_val is not None:
            if dxy_val < 104:
                parts.append(f"DXY {dxy_val:.1f} — dolar sıkılaşması sınırlı.")
            elif dxy_val > 106:
                parts.append(f"DXY {dxy_val:.1f} — dolar baskısı yüksek, risk varlıkları zorlanabilir.")

    # HYG / kredi
    hyg_val = _asset_value(signals, "HYG")
    if hyg_val is not None:
        if hyg_val > 78:
            parts.append("Kredi tarafı panik üretmiyor.")
        elif hyg_val < 74:
            parts.append(f"HYG ${hyg_val:.1f} — kredi spreadi genişliyor, dikkat.")

    # Onay listesinden destekleyici bilgi
    conf_met = [c.get("signal", "") for c in confirmation if c.get("met")]
    if conf_met:
        parts.append(f"{len(conf_met)} teknik teyit aktif.")

    return " ".join(parts) if parts else "Fiyat seviyesi verisi yok."


# ── Piyasanın fiyatladığı ──────────────────────────────────────────────────────

def _market_pricing_note(
    macro: dict,
    appetite_status: str,
    scenarios: list[dict],
    asymmetry: dict,
) -> str:
    """
    DXY + risk iştahı + senaryo dağılımından fiyatlama özeti.
    """
    parts: list[str] = []

    # Regime
    regime = str(macro.get("regime") or "").upper()
    regime_tr = _REGIME_TR.get(regime, regime.lower())
    conf_pct = _safe_float(macro.get("confidence_pct"))
    if regime_tr:
        conf_str = f" (%{conf_pct:.0f} güven)" if conf_pct else ""
        parts.append(f"Makro rejim: {regime_tr}{conf_str}.")

    # Risk iştahı
    apt_tr = _APPETITE_TR.get(appetite_status.upper(), "")
    if apt_tr:
        parts.append(f"Risk iştahı {apt_tr}.")

    # Senaryo dağılımı
    bull = next((s for s in scenarios if s.get("key") == "bull"), None)
    bear = next((s for s in scenarios if s.get("key") == "bear"), None)
    if bull and bear:
        bp = _safe_float(bull.get("probability_pct"))
        brp = _safe_float(bear.get("probability_pct"))
        if bp is not None and brp is not None:
            parts.append(f"Boğa senaryosu %{bp:.0f}, ayı %{brp:.0f} olasılıkla fiyatlanıyor.")

    # Asimetri
    ratio = _safe_float(asymmetry.get("ratio"))
    if ratio and ratio > 3:
        parts.append(f"Risk/ödül asimetrisi: {ratio:.1f}× — ödül tarafı lehine.")
    elif ratio and ratio < 1.5:
        parts.append("Risk/ödül dengesi zayıf; büyük pozisyon açmak için değil.")

    return " ".join(parts) if parts else "Fiyatlama özeti yok."


# ── Sonraki tetikleyici ────────────────────────────────────────────────────────

def _next_trigger(flip_conditions: list[dict]) -> str:
    """
    flip_conditions'dan ilk anlamlı tetikleyici.
    Önce AL, yoksa KÜÇÜLT, yoksa boş.
    """
    prio = ["AL", "AÇIL", "KORU"]
    for direction in prio:
        for fc in flip_conditions:
            if str(fc.get("direction") or "").upper() == direction:
                conds = fc.get("conditions") or []
                if conds:
                    return str(conds[0])[:120]

    # Herhangi biri
    for fc in flip_conditions:
        conds = fc.get("conditions") or []
        if conds:
            direction = fc.get("direction", "")
            return f"[{direction}] {str(conds[0])[:110]}"

    return "tetikleyici kaydı yok"


# ── Genel piyasa fikri ────────────────────────────────────────────────────────

def _market_thought(
    regime: str,
    conf_pct: float | None,
    appetite_status: str,
    event_note: str,
    event_story: str,
    price_story_str: str,
    next_trigger_str: str,
) -> str:
    """
    En fazla 4 cümle: ne değişti / ne anlama geliyor / ne bekliyorum.
    Kayıt yoksa açık yazar, uydurma içerik üretmez.
    """
    sentences: list[str] = []

    # 1. Makro durum
    regime_tr = _REGIME_TR.get(regime, regime.lower() if regime else "")
    apt_tr    = _APPETITE_TR.get(appetite_status.upper(), "")
    if regime_tr and apt_tr:
        conf_str = f" (%{conf_pct:.0f} güven)" if conf_pct else ""
        sentences.append(f"Piyasa {regime_tr} rejimde{conf_str}, {apt_tr} var.")
    elif regime_tr:
        sentences.append(f"Piyasa {regime_tr} rejimde.")

    # 2. Fiyat özeti (ilk cümle varsa)
    if price_story_str and price_story_str != "Fiyat seviyesi verisi yok.":
        first_ps = price_story_str.split(".")[0].strip()
        if first_ps:
            sentences.append(first_ps + ".")

    # 3. Olay/jeopolitik
    if "jeopolitik başlık yok" not in event_story.lower():
        # War active
        es_short = event_story.split(".")[0].strip()
        if es_short:
            sentences.append(es_short + ".")
    elif event_note != "event beklenti kaydı yok":
        en_short = event_note.split(".")[0].strip()
        if en_short:
            sentences.append(en_short + ".")

    # 4. Beklenti / tetikleyici
    if next_trigger_str and next_trigger_str != "tetikleyici kaydı yok":
        sentences.append(f"Pozisyon için izle: {next_trigger_str}.")

    if not sentences:
        return "Piyasa verisi yok — snapshot bekleniyor."

    return " ".join(sentences[:4])


# ── Public API ────────────────────────────────────────────────────────────────

def build_event_calendar_context(snapshot_report: dict[str, Any]) -> dict[str, Any]:
    """
    Snapshot report'tan piyasa fikri + olay takvimi farkındalığı üretir.

    Args:
        snapshot_report: hourly_snapshot["report"] dict'i.

    Returns:
        {
            "market_thought":       str,
            "price_story":          str,
            "event_story":          str,
            "event_calendar_note":  str,
            "market_pricing_note":  str,
            "next_trigger":         str,
        }
    """
    if not snapshot_report:
        return {
            "market_thought":      "Snapshot verisi yok — kayıt bekleniyor.",
            "price_story":         "Fiyat seviyesi verisi yok.",
            "event_story":         "Jeopolitik başlık yok; fiyatlama normal veri akışına bakıyor.",
            "event_calendar_note": "event beklenti kaydı yok",
            "market_pricing_note": "Fiyatlama özeti yok.",
            "next_trigger":        "tetikleyici kaydı yok",
        }

    catalysts    = list(snapshot_report.get("upcoming_catalysts") or [])
    news         = list(snapshot_report.get("news_headlines") or [])
    signals      = list(snapshot_report.get("asset_signals") or [])
    macro        = dict(snapshot_report.get("macro_layer") or {})
    appetite_raw = dict(snapshot_report.get("appetite_layer") or {})
    scenarios    = list(snapshot_report.get("scenarios") or [])
    asymmetry    = dict(snapshot_report.get("asymmetry") or {})
    flip_conds   = list(snapshot_report.get("flip_conditions") or [])
    confirmation = list(snapshot_report.get("confirmation_checklist") or [])

    appetite_status = str(appetite_raw.get("status") or "")
    regime          = str(macro.get("regime") or "").upper()
    conf_pct        = _safe_float(macro.get("confidence_pct"))

    evt_note     = _event_calendar_note(catalysts, news)
    evt_story    = _event_story(news)
    price_str    = _price_story(signals, macro, appetite_status, confirmation)
    pricing_note = _market_pricing_note(macro, appetite_status, scenarios, asymmetry)
    trigger      = _next_trigger(flip_conds)
    thought      = _market_thought(
        regime, conf_pct, appetite_status,
        evt_note, evt_story, price_str, trigger,
    )

    return {
        "market_thought":      thought,
        "price_story":         price_str,
        "event_story":         evt_story,
        "event_calendar_note": evt_note,
        "market_pricing_note": pricing_note,
        "next_trigger":        trigger,
    }
