"""
Agent Insight Service — proaktif stratejist motoru.

RegimeReport + CapitalRotation + TechnicalInsight + NewsHeadlines'a bakarak
yatırım stratejistinin yapacağı sentezi tek/çok cümleyle üretir.

Çoklu katman sentezleri:
  • CRITICAL    — sistemik eşik kırılması (HYG/VIX kriz seviyesi)
  • CLUSTER     — 2+ varlık aynı anda sert hareket (ortak hikaye)
  • LEVEL       — fiyat destek/dirence ATR-bazlı yakın (kırılım izleme)
  • CATALYST    — kritik haber + asset_impact → tetikleyici
  • REVERSAL    — "Buradan dönüş için ne olmalı" senaryosu
  • ROTATION    — sermaye akış kalıbı

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

InsightSeverity = Literal["CRITICAL", "WARNING", "OPPORTUNITY", "OBSERVATION"]


@dataclass(frozen=True)
class AgentInsight:
    severity: InsightSeverity
    headline: str         # ana çıkarım — kullanıcının göreceği özet
    detail: str           # 1-3 cümle stratejist analizi
    asset_code: str       # ilgili varlık (varsa)
    icon: str             # 🚨 ⚠️ 🎯 👁 🔗
    generated_at: str


# ── Önbellek (60sn) ───────────────────────────────────────────────────────────

_INSIGHT_CACHE: tuple[float, list[AgentInsight]] | None = None
_CACHE_TTL = 60


# ── Eşikler ───────────────────────────────────────────────────────────────────

VIX_DANGER     = 25.0
VIX_CRISIS     = 40.0
HYG_BREAK      = 78.0
HYG_CRISIS     = 74.0

# Cluster (çoklu varlık) düşüş — 7g %
CLUSTER_DROP_PCT = -3.0
CLUSTER_SURGE_PCT =  3.0
MIN_CLUSTER_SIZE  = 2

# Destek/direnç yakınlığı — ATR cinsinden
NEAR_LEVEL_ATR = 1.5    # current ile S/R arası mesafe ≤ 1.5 ATR ise "yakın"

# Varlık kategorileri — cluster sentezi için
ASSET_GROUPS = {
    "kripto":         {"BTCUSD", "ETHUSD"},
    "değerli metal":  {"XAUUSD", "XAGUSD", "XCUUSD"},
    "majör hisse":    {"SP500", "QQQ", "IWM"},
    "tahvil":         {"TLT", "LQD", "HYG"},
    "enerji/emtia":   {"BRENT", "OIL", "XCUUSD"},
}

# Jeopolitik bölge anahtar kelimeleri — haber-tetikleyici eşleştirme
GEO_TRIGGERS = {
    "iran":   ("İran", ("iran", "tehran", "khamenei", "ayetullah", "tahran")),
    "russia": ("Rusya/Ukrayna", ("russia", "ukraine", "putin", "kremlin", "zelensk", "rusya", "ukrayna")),
    "israel": ("İsrail/Orta Doğu", ("israel", "gaza", "netanyahu", "hezbollah", "hamas", "israil", "gazze")),
    "fed":    ("Fed/Para Politikası", ("fed", "powell", "fomc", "faiz", "rate hike", "rate cut")),
    "trump":  ("Trump/Beyaz Saray", ("trump", "white house", "tariff", "gümrük")),
    "china":  ("Çin", ("china", "beijing", "xi jinping", "pboc", "çin", "pekin")),
}


def _classify_news_region(title: str) -> str | None:
    """Bir haberin hangi jeopolitik bölgeye ait olduğunu döndürür."""
    lower = title.lower()
    for region, (_, keywords) in GEO_TRIGGERS.items():
        if any(kw in lower for kw in keywords):
            return region
    return None


# ── Ana üretici ───────────────────────────────────────────────────────────────

def generate_insights(report: Any, rotation: Any | None = None) -> list[AgentInsight]:
    """Çok katmanlı stratejist gözlemleri üret."""
    import time
    global _INSIGHT_CACHE

    now = time.monotonic()
    if _INSIGHT_CACHE and (now - _INSIGHT_CACHE[0]) < _CACHE_TTL:
        return _INSIGHT_CACHE[1]

    iso_now = datetime.now(UTC).isoformat()
    insights: list[AgentInsight] = []

    signals = list(report.asset_signals)
    signals_by_code: dict[str, Any] = {s.asset_code: s for s in signals}
    tech_by_code: dict[str, Any] = {t.asset_code: t for t in (report.tech_insights or [])}
    news_list = list(report.news_headlines or [])

    # ────────────────────────────────────────────────────────────────────────
    # 1) KRİTİK — VIX, HYG sistemik eşikler
    # ────────────────────────────────────────────────────────────────────────
    vix = signals_by_code.get("VIX")
    if vix and vix.value is not None:
        if vix.value >= VIX_CRISIS:
            insights.append(AgentInsight(
                "CRITICAL",
                f"VIX {vix.value:.1f} — KRİZ MODU",
                "Korku endeksi sistemik panik bölgesinde. Tüm risk pozisyonları gözden geçir.",
                "VIX", "🚨", iso_now,
            ))
        elif vix.value >= VIX_DANGER:
            insights.append(AgentInsight(
                "WARNING",
                f"VIX {vix.value:.1f} — korku yükseliyor",
                f"Tarihsel ortalama (15-18) üstünde. {VIX_CRISIS}'a hızlanırsa risk-off rejimi aktifleşir.",
                "VIX", "⚠️", iso_now,
            ))

    hyg = signals_by_code.get("HYG")
    if hyg and hyg.value is not None:
        if hyg.value <= HYG_CRISIS:
            insights.append(AgentInsight(
                "CRITICAL",
                f"HYG ${hyg.value:.2f} — kredi krizi başladı",
                "Yüksek getirili tahviller kritik altında, sistemik kredi stresi. KAPAT modu eşiğinde.",
                "HYG", "🚨", iso_now,
            ))
        elif hyg.value <= HYG_BREAK:
            insights.append(AgentInsight(
                "WARNING",
                f"HYG ${hyg.value:.2f} — kredi baskıda",
                f"${HYG_CRISIS} altı kırılırsa sistemik risk. Bu zinciri izle: HYG↓ → spread↑ → hisse↓.",
                "HYG", "⚠️", iso_now,
            ))

    # ────────────────────────────────────────────────────────────────────────
    # 2) CLUSTER — 2+ varlık aynı yönde sert hareket
    # ────────────────────────────────────────────────────────────────────────
    big_drops = [s for s in signals
                 if s.delta_7d_pct is not None and s.delta_7d_pct <= CLUSTER_DROP_PCT]
    big_drops.sort(key=lambda x: x.delta_7d_pct)

    for group_name, codes in ASSET_GROUPS.items():
        members_down = [s for s in big_drops if s.asset_code in codes]
        if len(members_down) >= MIN_CLUSTER_SIZE:
            names = ", ".join(f"{s.asset_code} ({s.delta_7d_pct:+.1f}%)" for s in members_down[:3])
            avg_drop = sum(s.delta_7d_pct for s in members_down) / len(members_down)

            # Sebep tahmini — grup tipine göre
            cause = ""
            if group_name == "kripto":
                cause = "Genel kripto kanaması — risk iştahı zayıf, BTC.D yükseliyor olabilir, altcoin'lerden çıkış net."
            elif group_name == "değerli metal":
                cause = "Metal kompleksi baskı altında — güçlü dolar momentumu metal kompleksini birlikte düşürüyor."
            elif group_name == "majör hisse":
                cause = "Hisse senedi cephesi zayıflıyor — risk-off rotasyon işareti olabilir."
            elif group_name == "enerji/emtia":
                cause = "Emtia tarafında talep zayıflığı — Çin yavaşlama veya küresel resesyon endişesi."

            insights.append(AgentInsight(
                "WARNING",
                f"{group_name.upper()} kümesi sert düşüyor (ort. {avg_drop:+.1f}%)",
                f"{names}. {cause}",
                members_down[0].asset_code,
                "🔗", iso_now,
            ))

    # Aynısı yukarı — sert çıkış
    big_surges = [s for s in signals
                  if s.delta_7d_pct is not None and s.delta_7d_pct >= CLUSTER_SURGE_PCT]
    for group_name, codes in ASSET_GROUPS.items():
        members_up = [s for s in big_surges if s.asset_code in codes]
        if len(members_up) >= MIN_CLUSTER_SIZE and group_name not in ("değerli metal",):
            # değerli metal'i üstte zaten ele aldık (cluster down öncelikli)
            names = ", ".join(f"{s.asset_code} ({s.delta_7d_pct:+.1f}%)" for s in members_up[:3])
            insights.append(AgentInsight(
                "OPPORTUNITY",
                f"{group_name.upper()} kümesi güçlü yükselişte",
                f"{names} — bu kategoride momentum birikiyor, devam etme potansiyeli var.",
                members_up[0].asset_code,
                "🔗", iso_now,
            ))
            break  # tek küme yeter

    # ────────────────────────────────────────────────────────────────────────
    # 3) LEVEL — fiyat destek/dirence ATR-bazlı yakın
    # ────────────────────────────────────────────────────────────────────────
    for code, t in tech_by_code.items():
        if code in {"VIX", "DXY"}:  # bunlar için yön farklı
            continue
        try:
            lv = t.levels
            if lv.atr <= 0:
                continue

            dist_to_support    = abs(t.current_price - lv.support)    / lv.atr
            dist_to_resistance = abs(lv.resistance - t.current_price) / lv.atr

            # Desteğe yakın + aşağı momentum varsa "kritik kırılım izlemesi"
            if dist_to_support < NEAR_LEVEL_ATR and t.structure in ("BEARISH", "NEUTRAL"):
                pct_to = ((t.current_price - lv.support) / t.current_price) * 100
                insights.append(AgentInsight(
                    "WARNING",
                    f"{code} desteğe çok yakın (${lv.support:,.0f}, %{pct_to:.1f} mesafe)",
                    f"Fiyat ${t.current_price:,.0f}, ATR ${lv.atr:,.0f}. Kırılırsa eski destek dirence dönüşür, "
                    f"yeni hedef ${lv.support - 2 * lv.atr:,.0f}. Stop seviyesi ${lv.stop_loss:,.0f}.",
                    code, "🎯", iso_now,
                ))
            # Direnci kırma yakın + yukarı momentum varsa fırsat
            elif dist_to_resistance < NEAR_LEVEL_ATR and t.structure in ("BULLISH", "NEUTRAL"):
                pct_to = ((lv.resistance - t.current_price) / t.current_price) * 100
                insights.append(AgentInsight(
                    "OPPORTUNITY",
                    f"{code} direnç kırılım eşiğinde (${lv.resistance:,.0f}, %{pct_to:.1f} mesafe)",
                    f"Fiyat ${t.current_price:,.0f}, ATR ${lv.atr:,.0f}. Kırılım onaylanırsa hedef "
                    f"${lv.take_profit:,.0f}. RSI: {t.rsi_14 if t.rsi_14 else '?'} · MACD: {t.macd_signal}.",
                    code, "🎯", iso_now,
                ))
        except Exception:
            continue

    # ────────────────────────────────────────────────────────────────────────
    # 4) CATALYST — kritik haber + asset_impact → "X olduğu için Y baskıda"
    # ────────────────────────────────────────────────────────────────────────
    geo_hot = {}  # region → en taze BEARISH haber
    for h in news_list[:15]:
        if getattr(h, "relevance", "") not in ("HIGH", "MEDIUM"):
            continue
        region = _classify_news_region(getattr(h, "title", ""))
        if not region:
            continue
        sentiment = getattr(h, "sentiment", "NEUTRAL")
        if sentiment != "BEARISH":
            continue
        if region not in geo_hot:
            geo_hot[region] = h

    for region, h in list(geo_hot.items())[:2]:  # en sıcak 2 jeopolitik bölge
        region_label = GEO_TRIGGERS[region][0]
        title_display = (getattr(h, "title_tr", "") or h.title)[:90]

        # Bu haberin etkilediği varlıkları al
        impacts = getattr(h, "asset_impact", None) or []
        impact_codes = [imp.asset_code for imp in impacts if imp.direction in ("positive", "negative")]

        if impact_codes:
            primary_code = impact_codes[0]
            direction = next(
                (imp.direction for imp in impacts if imp.asset_code == primary_code),
                "neutral"
            )
            arrow = "↑" if direction == "positive" else "↓"
            insights.append(AgentInsight(
                "WARNING",
                f"{region_label} haberi {primary_code}'yi etkiliyor ({arrow})",
                f"\"{title_display}\" — {region_label} ekseninde baskı sürüyor. "
                f"Bu haberin geri çekilmesi ({region_label.split('/')[0]}'a ateşkes / kötü haber azalması) "
                f"{primary_code} için kritik dönüş noktası olabilir.",
                primary_code, "📰", iso_now,
            ))
        else:
            insights.append(AgentInsight(
                "OBSERVATION",
                f"{region_label}: kritik haber akışı",
                f"\"{title_display}\" — bu cepheden çıkacak ateşkes/anlaşma haberleri piyasa rejimini değiştirebilir.",
                "", "📰", iso_now,
            ))

    # ────────────────────────────────────────────────────────────────────────
    # 5) REVERSAL — "Buradan dönüş için ne olmalı" sentezi
    # ────────────────────────────────────────────────────────────────────────
    # Mevcut karar KAPAT/KÜÇÜLT ise, dönüş için somut tetikleyici öner
    if report.decision in ("KÜÇÜLT", "KAPAT"):
        triggers: list[str] = []

        # En kritik 1-2 jeopolitik cephe
        if geo_hot:
            for region, h in list(geo_hot.items())[:1]:
                region_label = GEO_TRIGGERS[region][0]
                triggers.append(f"{region_label} cephesinde ateşkes/anlaşma haberi")

        # VIX inişi
        if vix and vix.value is not None and vix.value > 20:
            triggers.append(f"VIX'in {VIX_DANGER:.0f} altına geri çekilmesi")

        # Düşen kümeler için döngü tetikleyici
        kripto_down = [s for s in big_drops if s.asset_code in ASSET_GROUPS["kripto"]]
        metal_down  = [s for s in big_drops if s.asset_code in ASSET_GROUPS["değerli metal"]]

        if kripto_down and metal_down:
            triggers.append("Dolar momentumunun (DXY 30g) kırılması — metal/kripto birlikte kanıyor")
        elif kripto_down:
            triggers.append("BTC dominansının düşmesi + USDT.D'nin gerilemesi")
        elif metal_down:
            triggers.append("Dolar zayıflaması — DXY'nin 99 altı kalıcı geçişi")

        if triggers:
            insights.append(AgentInsight(
                "OBSERVATION",
                "Buradan dönüş için ne olmalı?",
                f"Karar {report.decision} — dönüş senaryosu için gereken tetikleyiciler: "
                + " · ".join(f"({i+1}) {t}" for i, t in enumerate(triggers[:3])) + ".",
                "", "🔄", iso_now,
            ))

    # ────────────────────────────────────────────────────────────────────────
    # 6) ROTATION — sermaye akış kalıbı
    # ────────────────────────────────────────────────────────────────────────
    if rotation and not rotation.error and rotation.synthesis:
        synth_lower = (rotation.synthesis or "").lower()
        pattern = None
        if "defansif risk-on" in synth_lower:
            pattern = ("Sermaye: defansif risk-on (hisse + nakit birlikte)",
                       "Klasik 'güçlü-dolar-büyümesi'. Metal/kripto baskı altında. DXY momentumu kırılırsa kompleks tersine döner.",
                       "🎯", "OBSERVATION")
        elif "güvenli liman" in synth_lower:
            pattern = ("Sermaye güvenli limanlara akıyor — risk-off başladı",
                       "Altın/tahvil/nakitten en az ikisi giriş alıyor. Hisse/kripto satışı süreklilik kazanabilir.",
                       "⚠️", "WARNING")
        elif "saf risk-on" in synth_lower:
            pattern = ("Sermaye: saf risk-on — spekülatif iştah aktif",
                       "Hisse + BTC birlikte giriş alıyor. Bu rejimin sürebilmesi için VIX düşük, kredi (HYG) güçlü kalmalı.",
                       "🎯", "OPPORTUNITY")
        elif "enflasyon" in synth_lower:
            pattern = ("Sermaye: enflasyon hedge'i aktif",
                       "Altın + emtia giriş, tahvil çıkış. Yield eğrisi ve CPI verilerini yakın izle.",
                       "🎯", "OBSERVATION")

        if pattern:
            head, det, ico, sev = pattern
            insights.append(AgentInsight(sev, head, det, "", ico, iso_now))

    # ────────────────────────────────────────────────────────────────────────
    # 7) BLOCKING (geriye kalan core bloklar)
    # ────────────────────────────────────────────────────────────────────────
    blocking = [s for s in signals if s.status == "BLOCKING"]
    core = {"BTCUSD", "SP500", "DXY", "BRENT", "VIX", "HYG"}
    blocker_seen = {ins.asset_code for ins in insights}
    for b in blocking:
        if b.asset_code in core and b.asset_code not in blocker_seen:
            insights.append(AgentInsight(
                "WARNING",
                f"{b.asset_name} ({b.asset_code}) sistem bloklayıcı",
                (b.reason or "Pozisyon açılışı için bu sinyalin temizlenmesi gerekiyor.")[:200],
                b.asset_code, "⚠️", iso_now,
            ))
            break

    # ────────────────────────────────────────────────────────────────────────
    # Boş ise genel durum
    # ────────────────────────────────────────────────────────────────────────
    if not insights:
        insights.append(AgentInsight(
            "OBSERVATION",
            f"Sistem stabil — karar: {report.decision}",
            report.verdict or "Mevcut rejim devam ediyor, kritik sinyal yok.",
            "", "👁", iso_now,
        ))

    # Severity sıralaması (CRITICAL en başta)
    sev_order = {"CRITICAL": 0, "WARNING": 1, "OPPORTUNITY": 2, "OBSERVATION": 3}
    insights.sort(key=lambda i: sev_order[i.severity])

    # En önemli 8'i tut (çoklu kategori desteklesin)
    _INSIGHT_CACHE = (now, insights[:8])
    return _INSIGHT_CACHE[1]


# ────────────────────────────────────────────────────────────────────────────
# Paper Trading Karar Zinciri Sentezi
# ────────────────────────────────────────────────────────────────────────────
#
# Agent, kullanıcıya HAM blokları (DQS / Trigger / Risk / Entry / Exit / vs.)
# göstermez — bunları içsel analiz olarak okur ve insight üretir.
# UI yalnızca insight + disiplinli decision label görür.

def synthesize_paper_decision_insights(decision_payload: dict[str, Any]) -> list[AgentInsight]:
    """
    paper_decision_service.build_latest_decision().to_dict() çıktısını okur,
    UI'a göstermek istediğimiz kritik insight'lara dönüştürür.

    Aşağıdaki durumları yakalar (öncelik sırasına göre):
      • KILL_SWITCH aktif                        → CRITICAL
      • DQS BLOCKED veya FAIL_NO_DECISION        → CRITICAL
      • RISK_REDUCE + açık pozisyon              → WARNING (KÜÇÜLT)
      • RISK_REDUCE + flat                       → WARNING (YENİ RİSK AÇMA)
      • NO_POSITION_INCREASE                     → WARNING
      • setup_validity=True + flat               → OPPORTUNITY (giriş hazır)
      • why_no_trade dolu + flat                 → OBSERVATION (bekleyiş sebebi)
      • learning_layer.prediction_id             → OBSERVATION (kararlı log)

    Tüm insight'ler kısa, eylem yönelimli; ham veri sızıntısı YOK.
    """
    if not isinstance(decision_payload, dict):
        return []

    now_iso = datetime.now(UTC).isoformat()
    out: list[AgentInsight] = []

    risk     = decision_payload.get("risk_engine_verdict") or {}
    dq       = decision_payload.get("data_quality_status") or {}
    paper    = decision_payload.get("paper_trading_decision") or {}
    learning = decision_payload.get("learning_layer") or {}
    triggers = decision_payload.get("trigger_engine_output") or {}
    label    = str(decision_payload.get("decision_label") or "")

    has_open      = bool(paper.get("has_open_positions"))
    risk_action   = str(risk.get("risk_action") or "HOLD")
    kill_switch   = bool(risk.get("kill_switch_active"))
    dqs_decision  = str(dq.get("dqs_decision") or "")
    dqs_permission = str(dq.get("decision_permission") or "")
    setup_valid   = bool(paper.get("setup_validity"))
    would_pair    = paper.get("would_trade_asset")
    would_dir     = paper.get("would_trade_direction")
    consensus     = paper.get("best_consensus_score")
    why_no_trade  = paper.get("why_no_trade") or []

    # 1) KILL_SWITCH — en üst öncelik
    if kill_switch or risk_action == "KILL_SWITCH":
        out.append(AgentInsight(
            "CRITICAL",
            "Sistem durduruldu — KILL_SWITCH aktif",
            "Risk motoru kritik veri/sistem koşulu nedeniyle tüm yeni işlemleri durdurdu. "
            "Mevcut pozisyonlar gözden geçirilmeli, yeni risk açılmamalı.",
            "", "🛑", now_iso,
        ))

    # 2) DQS koruması
    if dqs_decision == "FAIL_NO_DECISION":
        out.append(AgentInsight(
            "CRITICAL",
            "Veri kalitesi karar vermek için yetersiz",
            f"DQS {dq.get('overall_dqs', '?')}/100 ile karar verme eşiğinin altında. "
            "Yeni paper trade açılamaz; mevcut pozisyonlar takip ediliyor.",
            "", "⚠", now_iso,
        ))
    elif dqs_permission == "BELOW_THRESHOLD":
        out.append(AgentInsight(
            "WARNING",
            "Veri kalitesi giriş eşiğinin altında",
            f"DQS {dq.get('overall_dqs', '?')}/100 — yeni pozisyon açmak için yeterli güven yok. "
            "Stale/mock kaynaklar düzelene dek bekliyorum.",
            "", "⚠", now_iso,
        ))

    # 3) Risk action bağlı uyarı
    if risk_action == "RISK_REDUCE" and not has_open:
        out.append(AgentInsight(
            "WARNING",
            "Risk modu yüksek — yeni risk açmıyorum",
            "Risk motoru çoklu sert teyit gördü; açık pozisyonum olmadığı için 'KÜÇÜLT' demiyorum. "
            "Yeni giriş için baskı azalmasını bekliyorum.",
            "", "🛡", now_iso,
        ))
    elif risk_action == "RISK_REDUCE" and has_open:
        out.append(AgentInsight(
            "WARNING",
            "Açık pozisyonları küçültme zamanı",
            "Risk motoru RISK_REDUCE — açık pozisyonları boyut/maruziyet açısından gözden geçirmem gerek.",
            "", "🛡", now_iso,
        ))
    elif risk_action == "NO_POSITION_INCREASE":
        out.append(AgentInsight(
            "WARNING",
            "Pozisyon artırma yasak — mevcut maruziyet sabit",
            "Risk motoru ek risk almaya izin vermiyor. Mevcut pozisyonlar korunabilir, "
            "ama yeni giriş veya scale-in yapılamaz.",
            "", "🛡", now_iso,
        ))

    # 4) Giriş fırsatı
    if setup_valid and not has_open and would_pair and would_dir and not kill_switch:
        conf_pct = ""
        try:
            if consensus is not None:
                conf_pct = f" ({float(consensus):.0f}/100 güven)"
        except Exception:
            pass
        out.append(AgentInsight(
            "OPPORTUNITY",
            f"{would_pair} {would_dir} setup'ı hazır{conf_pct}",
            "Konsensus, veri kalitesi ve risk kapısı uygun — şartlar tamamlanırsa giriş üretebilirim. "
            "Önce makro/kredi teyitlerini izlemek istiyorum.",
            str(would_pair), "🎯", now_iso,
        ))

    # 5) why_no_trade — agent neyi beklediğini açıkça yazar
    if why_no_trade and not has_open:
        first = str(why_no_trade[0])
        # Teknik kodları sade Türkçeye çevir
        translate = {
            "no_directional_consensus":      "Yönlü konsensus oluşmamış",
            "data_quality_blocks_open":      "Veri kalitesi giriş için yetersiz",
            "risk_engine_blocks_new:KILL_SWITCH":         "Risk motoru sistemi durdurdu",
            "risk_engine_blocks_new:RISK_REDUCE":         "Risk motoru yeni girişi kapadı",
            "risk_engine_blocks_new:NO_POSITION_INCREASE":"Risk motoru ek pozisyona izin vermiyor",
        }
        reason = translate.get(first, first)
        out.append(AgentInsight(
            "OBSERVATION",
            "Şu an açık pozisyonum yok — neyi bekliyorum?",
            f"Engelleyici: {reason}. Bu koşul kalkana kadar paper trade açmıyorum.",
            "", "👁", now_iso,
        ))

    # 6) Confirmed trigger sayısı — ek bağlam
    confirmed = triggers.get("confirmed_triggers") or []
    severity_high = triggers.get("trigger_severity") in ("ORANGE", "RED")
    if severity_high and len(confirmed) >= 2 and not any(i.severity == "CRITICAL" for i in out):
        out.append(AgentInsight(
            "WARNING",
            f"{len(confirmed)} kritik tetikleyici teyitlendi",
            "Risk hesaba katmam gereken çoklu sert sinyal aktif; karar disiplini sıkı tutuluyor.",
            "", "🚨", now_iso,
        ))

    # 7) Learning layer — prediction kaydı
    pred_id = learning.get("prediction_id")
    if pred_id and label:
        out.append(AgentInsight(
            "OBSERVATION",
            f"Karar log'landı: {label}",
            f"Bu karar {pred_id} kimliğiyle kayıt altında — sonuç ileride gözden geçirilecek.",
            "", "📌", now_iso,
        ))

    return out


def derive_paper_decision_label_safely(decision_payload: dict[str, Any]) -> str:
    """Frontend'in PORTFÖY KARARI rozetinde göstereceği disiplinli label."""
    if not isinstance(decision_payload, dict):
        return ""
    return str(decision_payload.get("decision_label") or "")


__all__ = [
    "AgentInsight",
    "InsightSeverity",
    "generate_insights",
    "synthesize_paper_decision_insights",
    "derive_paper_decision_label_safely",
]
