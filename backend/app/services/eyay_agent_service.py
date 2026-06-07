"""
E-YAY BrainChain — Ajansal Sohbet Servisi (Çift-Sağlayıcı).

Birincil   : Groq (llama-3.3-70b-versatile) — ucuz, hızlı, OpenAI uyumlu tool use.
Geri Düşüş : Claude (claude-opus-4-7) — Groq erişilemediğinde devreye girer.

Araçlar (her iki sağlayıcı için aynı):
  • get_full_regime_report()      — 4-katman makro rejim + varlık sinyalleri
  • get_capital_rotation()        — Sermaye rotasyonu ve para akışı
  • get_geo_news()                — Jeopolitik haberler
  • get_technical_analysis(code)  — Teknik analiz (destek/direnç/RSI/MACD)
  • get_event_calendar()          — Yaklaşan kataliz olayları

PAPER_SAFE / NO_EXECUTION — İşlem emri, portföy tavsiyesi yasak.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Generator

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_TTL = 300  # 5 dakika

# ── Sağlayıcı ayarları ────────────────────────────────────────────────────────

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BACKUP_MODEL = os.environ.get("GROQ_BACKUP_MODEL", "llama-3.1-8b-instant")
CLAUDE_MODEL = os.environ.get("CLAUDE_AGENT_MODEL", "claude-opus-4-7")
PRIMARY_PROVIDER = os.environ.get("EYAY_PRIMARY_PROVIDER", "groq").lower()


# ── Sys-path yardımcısı ────────────────────────────────────────────────────────

def _ensure_path() -> None:
    s = str(_REPO_ROOT)
    if s not in sys.path:
        sys.path.insert(0, s)


# ── Tam pipeline önbelleği ─────────────────────────────────────────────────────

_pipeline_cache: tuple[float, Any] | None = None


def _run_pipeline() -> Any | None:
    """Tam veri hattını çalıştır, RegimeReport döndür. 5 dk TTL."""
    global _pipeline_cache
    now = time.monotonic()
    if _pipeline_cache and (now - _pipeline_cache[0]) < _CACHE_TTL:
        return _pipeline_cache[1]

    _ensure_path()
    try:
        from registry import build_source_registry_entries, load_source_registry

        from app.providers import (
            MockMarketProvider,
            SourceRegistryBoundProviderAdapter,
            build_provider_source_bindings,
        )
        from app.providers.real_market_provider import RealMarketProvider
        from app.services import MarketSnapshotService, ProviderIngestionService
        from app.services.regime_report_service import RegimeReportService

        class _FS:
            def add(self, _): pass
            def commit(self): pass
            def rollback(self): pass

        try:
            base = RealMarketProvider()
        except Exception:
            base = MockMarketProvider()

        src = load_source_registry()
        entries = build_source_registry_entries(src)
        provider = SourceRegistryBoundProviderAdapter(
            base, build_provider_source_bindings(entries)
        )
        result = ProviderIngestionService(
            MarketSnapshotService(_FS()), provider
        ).run()
        snapshots = tuple(p.snapshot for p in result.persisted_snapshots)
        report = RegimeReportService().generate(snapshots)
        _pipeline_cache = (now, report)
        return report
    except Exception as exc:
        logger.error("Pipeline hatası: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# HAM TOOL FONKSİYONLARI — her iki sağlayıcıdan da çağrılabilir
# ─────────────────────────────────────────────────────────────────────────────

def _tool_get_full_regime_report() -> str:
    """4-katman tam piyasa raporu (kompakt — 8b TPM limitiyle uyumlu)."""
    import dataclasses

    report = _run_pipeline()
    if report is None:
        return "Veri alınamadı — pipeline hatası."

    macro = dataclasses.asdict(report.macro_layer)
    appetite = dataclasses.asdict(report.appetite_layer)

    lines: list[str] = [
        f"REJİM: {macro['regime']} (güven %{macro['confidence_pct']})",
        f"MAKRO: DXY={macro['dxy_signal']} | Enerji={macro['energy_signal']}"
        f" | YieldC={macro['yield_curve_signal']} | M2={macro['m2_signal']}",
        f"İŞTAH: {appetite['status']} | Kredi={appetite['credit_signal']}"
        f" | BTC.D={appetite['btc_dominance_signal']} | Korku={appetite['safe_haven_signal']}",
        "",
        "SİNYALLER (BLOCKING + CONFIRMED öncelik, ilk 10):",
    ]

    # Sıralama + 10 ile sınırla — 19 varlık 8b TPM'i şişiriyor
    sorted_signals = sorted(
        report.asset_signals,
        key=lambda s: {
            "BLOCKING": 0, "CONFIRMED": 1, "PENDING": 2,
            "NEUTRAL": 3, "VERİ_YOK": 4,
        }.get(s.status, 3),
    )[:10]

    for sig in sorted_signals:
        v = sig.value
        val = f"{v:,.2f}{sig.unit}" if v is not None else "?"
        d7 = f" 7g:{sig.delta_7d_pct:+.1f}%" if sig.delta_7d_pct is not None else ""
        action = (
            f"→{sig.asset_action}"
            if getattr(sig, "asset_action", None) and sig.asset_action != "NEUTRAL"
            else ""
        )
        lines.append(f"  {sig.asset_code:<10} {val:<14} [{sig.status[:4]}]{d7} {action}")

    # Teyit özeti (detay yok — sadece sayım + eksik)
    met = sum(1 for c in report.confirmation_checklist if c.met)
    total = len(report.confirmation_checklist)
    unmet = [c.signal for c in report.confirmation_checklist if not c.met]
    lines += [
        "",
        f"TEYİT: {met}/{total}" + (f" | EKSİK: {', '.join(unmet[:3])}" if unmet else ""),
        f"KARAR: {report.decision} — {report.verdict[:120]}",
    ]
    return "\n".join(lines)


def _tool_get_capital_rotation() -> str:
    """Sermaye rotasyonu ve para akışı."""
    try:
        from app.providers.capital_rotation_provider import CapitalRotationProvider

        rot = CapitalRotationProvider().compute()
        if rot is None or rot.error:
            return f"Sermaye rotasyonu verisi alınamadı: {rot.error if rot else 'None'}"

        lines: list[str] = [
            f"SERMAYE ROTASYONU — Konviksiyon: {rot.conviction}/10",
            f"Birincil akış : {rot.primary_flow}",
        ]
        if rot.secondary_flow:
            lines.append(f"İkincil akış  : {rot.secondary_flow}")

        lines += ["", "VARLIK SINIFI SKORLARI:"]
        for cs in sorted(rot.class_scores, key=lambda x: -x.score):
            lines.append(
                f"  {cs.name:<12} Skor:{cs.score:+.2f}  30g:{cs.momentum_30d:+.1f}%  {cs.direction}"
            )

        if rot.ratios:
            lines += ["", "ÇAP ORANLAR:"]
            for r in rot.ratios[:8]:
                lines.append(
                    f"  {r.pair:<18} {r.value:.3f}  Δ30g:{r.delta_30d_pct:+.1f}%"
                    f"  {r.trend}  → {r.meaning}"
                )

        if rot.correlations:
            lines += ["", "KORELASYONLAR (30g):"]
            for c in rot.correlations[:6]:
                lines.append(f"  {c.pair:<20} {c.corr_30d:+.2f}  {c.regime}")

        if rot.key_insights:
            lines += ["", "ÖNEMLİ ÇIKARIMLAR:"]
            for ins in sorted(rot.key_insights, key=lambda x: -x.importance)[:5]:
                lines.append(f"  {ins.icon} {ins.text}")

        lines += ["", f"BAĞLAM : {rot.rotation_context}"]
        if rot.synthesis:
            lines.append(f"SENTEZ : {rot.synthesis}")

        return "\n".join(lines)
    except Exception as exc:
        return f"Sermaye rotasyonu hatası: {exc}"


def _tool_get_geo_news() -> str:
    """Jeopolitik haberler."""
    try:
        from app.providers.geo_news_provider import GeoNewsProvider

        headlines = GeoNewsProvider().fetch(max_total=30)
        if not headlines:
            return "Jeopolitik haber bulunamadı."

        region_labels = {
            "usa": "ABD", "iran": "İRAN", "israel": "İSRAİL",
            "china": "ÇİN", "russia": "RUSYA",
            "europe": "AVRUPA", "global": "KÜRESEL",
        }
        region_groups: dict[str, list] = {}
        for h in headlines:
            lbl = region_labels.get(h.region, h.region.upper())
            region_groups.setdefault(lbl, []).append(h)

        sent_icon = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}
        lines: list[str] = [f"JEOPOLİTİK HABERLER ({len(headlines)} haber):"]
        for region, rh in region_groups.items():
            lines.append(f"\n{region}:")
            for h in rh[:4]:
                icon = sent_icon.get(h.sentiment, "•")
                lines.append(f"  {icon} [{h.source}] {h.title}")

        return "\n".join(lines)
    except Exception as exc:
        return f"Haber hatası: {exc}"


def _tool_get_technical_analysis(asset_code: str) -> str:
    """Tek varlık için teknik analiz."""
    _ALIASES: dict[str, str] = {
        "btc": "BTCUSD", "bitcoin": "BTCUSD",
        "gold": "XAUUSD", "altin": "XAUUSD", "altın": "XAUUSD", "xau": "XAUUSD",
        "silver": "XAGUSD", "gümüş": "XAGUSD", "gumus": "XAGUSD", "xag": "XAGUSD",
        "copper": "XCUUSD", "bakır": "XCUUSD", "bakir": "XCUUSD",
        "oil": "BRENT", "petrol": "BRENT", "brent": "BRENT",
        "dxy": "DXY", "dollar": "DXY", "dolar": "DXY",
        "vix": "VIX",
        "sp500": "SP500", "spx": "SP500", "spy": "SP500", "s&p": "SP500",
        "hyg": "HYG",
        "qqq": "QQQ", "nasdaq": "QQQ",
        "iwm": "IWM", "russell": "IWM",
        "lqd": "LQD",
        "smh": "SMH",
        "xlf": "XLF",
    }
    code = _ALIASES.get(asset_code.strip().lower(), asset_code.strip().upper())

    try:
        from app.providers.technical_provider import TechnicalProvider

        insights = TechnicalProvider().compute()
        if code not in insights:
            available = ", ".join(sorted(insights.keys()))
            return (
                f"'{code}' için teknik veri bulunamadı.\n"
                f"Mevcut varlıklar: {available}"
            )

        t = insights[code]
        lv = t.levels
        rsi_str = f"{t.rsi_14:.1f}" if t.rsi_14 is not None else "?"
        vol_str = f"{t.volume_ratio:.2f}x ort." if t.volume_ratio is not None else "?"

        lines = [
            f"TEKNİK ANALİZ — {code} ({t.timeframe})",
            f"Güncel Fiyat : {t.current_price:,.2f}",
            f"Yapı         : {t.structure}",
            "",
            "SEVİYELER:",
            f"  Destek    : {lv.support:,.2f}",
            f"  Direnç    : {lv.resistance:,.2f}",
            f"  Stop-Loss : {lv.stop_loss:,.2f}",
            f"  Kar Al    : {lv.take_profit:,.2f}",
            f"  ATR(14)   : {lv.atr:,.2f}  (%{lv.atr_pct:.1f} günlük volatilite)",
            "",
            "GÖSTERGELER:",
            f"  RSI(14) : {rsi_str}",
            f"  MACD    : {t.macd_signal}",
            f"  Hacim   : {vol_str}",
            "",
            f"SKOR: {t.technical_score}/100",
            f"  Yapı:{t.structure_score}/25  Momentum:{t.momentum_score}/25"
            f"  Bölge:{t.zone_score}/25  Hacim:{t.volume_score}/25",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"Teknik analiz hatası ({code}): {exc}"


def _tool_get_event_calendar() -> str:
    """Yaklaşan kataliz olayları."""
    try:
        from app.services.event_calendar_service import EventCalendarService

        events = EventCalendarService().fetch_upcoming(horizon_days=60, max_events=20)
        if not events:
            return "Yaklaşan kataliz olayı bulunamadı (60 gün içinde)."

        imp_icon = {"CRITICAL": "🔴", "HIGH": "🟡", "MEDIUM": "⚪"}
        lines: list[str] = [
            f"YAKLAŞAN KATALIZ OLAYLARI ({len(events)} olay, 60 gün içinde):"
        ]
        for ev in events:
            icon = imp_icon.get(ev.importance, "•")
            lines.append(
                f"\n{icon} {ev.date} (+{ev.days_until}g) — {ev.name} [{ev.category}/{ev.importance}]"
            )
            if ev.expectation:
                lines.append(f"   Beklenti : {ev.expectation}")
            if ev.market_impact:
                lines.append(f"   Etki     : {ev.market_impact}")

        return "\n".join(lines)
    except Exception as exc:
        return f"Takvim hatası: {exc}"


# ── Araç kayıt defteri ────────────────────────────────────────────────────────

TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "get_full_regime_report": lambda: _tool_get_full_regime_report(),
    "get_capital_rotation":   lambda: _tool_get_capital_rotation(),
    "get_geo_news":           lambda: _tool_get_geo_news(),
    "get_technical_analysis": lambda asset_code: _tool_get_technical_analysis(asset_code),
    "get_event_calendar":     lambda: _tool_get_event_calendar(),
}

_TOOL_LABELS: dict[str, str] = {
    "get_full_regime_report": "Rejim raporu alınıyor…",
    "get_capital_rotation":   "Sermaye rotasyonu hesaplanıyor…",
    "get_geo_news":           "Jeopolitik haberler alınıyor…",
    "get_technical_analysis": "Teknik analiz yapılıyor…",
    "get_event_calendar":     "Takvim kontrol ediliyor…",
}


def _label_for(tool_name: str, args: dict) -> str:
    base = _TOOL_LABELS.get(tool_name, f"{tool_name}…")
    if tool_name == "get_technical_analysis":
        code = (args or {}).get("asset_code", "")
        if code:
            return f"Teknik analiz: {str(code).upper()}…"
    return base


# ── OpenAI / Groq tool şemaları ───────────────────────────────────────────────

GROQ_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_full_regime_report",
            "description": (
                "E-YAY 4-katman makro rejim raporu: rejim kodu (RISK_ON/TRANSITIONING/"
                "DEFENSIVE/CRISIS), DXY/Brent/yield/M2 sinyalleri, risk iştahı, "
                "19 varlığın durumu (CONFIRMED/BLOCKING/PENDING) + eylem önerisi, "
                "teyit listesi, portföy kararı (BEKLE/AÇIL/KÜÇÜLT/KAPAT). "
                "Genel piyasa durumu, karar gerekçesi soruları için kullan."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_capital_rotation",
            "description": (
                "Sermaye rotasyonu: büyük para nereye akıyor? Birincil/ikincil akış, "
                "7 varlık sınıfı skoru (ALTIN/GÜMÜŞ/TAHVİL/BTC/HİSSE/NAKİT/PETROL), "
                "çapraz oranlar (GLD/DXY, BTC/DXY, TLT/SPY), 30g korelasyonlar. "
                "'Para nereye gidiyor?', korelasyon, sermaye rotasyonu soruları."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_geo_news",
            "description": (
                "Güncel jeopolitik haberler: ABD, İran, İsrail, Çin, Rusya, Avrupa. "
                "Her haber için başlık, kaynak, sentiment (BULLISH/BEARISH/NEUTRAL). "
                "Haber, jeopolitik gelişme, bölgesel risk soruları için."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_analysis",
            "description": (
                "Belirli bir varlık için teknik analiz: destek/direnç, ATR, RSI(14), "
                "MACD, hacim, teknik skor (0-100). Spesifik varlık seviye soruları için."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_code": {
                        "type": "string",
                        "description": (
                            "Varlık kodu: BTCUSD, XAUUSD (Altın), XAGUSD (Gümüş), "
                            "XCUUSD (Bakır), BRENT, DXY, VIX, SP500, HYG, QQQ, "
                            "IWM, LQD, SMH, XLF"
                        ),
                    }
                },
                "required": ["asset_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_calendar",
            "description": (
                "Yaklaşan piyasa katalizörleri: Fed, OPEC, enflasyon verileri, önemli "
                "ekonomik olaylar. Her olay için tarih, kategori, önem, beklenti. "
                "Takvim, upcoming events, yakın vadeli risk soruları için."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ── Claude @beta_tool wrapper'ları (fallback için) ────────────────────────────

_TOOLS_AVAILABLE_CLAUDE = False
AGENT_TOOLS_CLAUDE: list = []

try:
    from anthropic.lib.tools import beta_tool

    @beta_tool
    def get_full_regime_report() -> str:
        """E-YAY 4-katman makro rejim raporu: rejim, DXY/Brent/yield/M2 sinyalleri, risk iştahı, 19 varlığın durumu + eylem önerisi, teyit listesi, portföy kararı. Genel piyasa durumu ve karar gerekçesi soruları için kullan."""
        return _tool_get_full_regime_report()

    @beta_tool
    def get_capital_rotation() -> str:
        """Sermaye rotasyonu: büyük para nereye akıyor? 7 varlık sınıfı skoru, çapraz oranlar, 30g korelasyonlar. 'Para nereye gidiyor?', korelasyon, rotasyon soruları için."""
        return _tool_get_capital_rotation()

    @beta_tool
    def get_geo_news() -> str:
        """Güncel jeopolitik haberler: ABD, İran, İsrail, Çin, Rusya, Avrupa. Haber, jeopolitik gelişme, bölgesel risk soruları için."""
        return _tool_get_geo_news()

    @beta_tool
    def get_technical_analysis(asset_code: str) -> str:
        """Belirli bir varlık için teknik analiz: destek/direnç, ATR, RSI, MACD, hacim, teknik skor. asset_code: BTCUSD, XAUUSD, XAGUSD, XCUUSD, BRENT, DXY, VIX, SP500, HYG, QQQ, IWM, LQD, SMH, XLF."""
        return _tool_get_technical_analysis(asset_code)

    @beta_tool
    def get_event_calendar() -> str:
        """Yaklaşan piyasa katalizörleri: Fed, OPEC, enflasyon, önemli olaylar. Takvim ve yakın vadeli risk soruları için."""
        return _tool_get_event_calendar()

    AGENT_TOOLS_CLAUDE = [
        get_full_regime_report,
        get_capital_rotation,
        get_geo_news,
        get_technical_analysis,
        get_event_calendar,
    ]
    _TOOLS_AVAILABLE_CLAUDE = True

except ImportError as _err:
    logger.warning("Claude beta_tool yüklenemedi: %s", _err)


# ── Sistem prompt ──────────────────────────────────────────────────────────────

AGENT_SYSTEM = """\
Sen E-YAY piyasa stratejistisin. PAPER_SAFE — al/sat emri verme.

KATI ARAÇ KURALLARI (token tasarrufu):
- Soru SPESİFİK bir varlığa sorulduysa SADECE o varlığın aracını çağır
  Örnek: "BTC ne?" → get_technical_analysis("BTCUSD") yalnız bu, başka tool YOK
- "Genel piyasa", "rejim", "karar" → SADECE get_full_regime_report
- "Para nereye akıyor", "rotasyon", "korelasyon" → SADECE get_capital_rotation
- "Haber", "İran/Çin/Fed" → SADECE get_geo_news
- "Bu hafta ne var", "Fed toplantısı" → SADECE get_event_calendar
- MAKSİMUM 2 TOOL ÇAĞRIR. 1 tool yetiyorsa 2 çağırma.

YANIT KURALLARI:
- Türkçe, kısa, somut. 100-200 kelime hedef.
- Disclaimer yok, PAPER_SAFE bilinir.
- Sayı ver: "destek 58.700, direnç 75.000" gibi.
- Sonuç önce, gerekçe sonra."""


# ─────────────────────────────────────────────────────────────────────────────
# GROQ stream (primary)
# ─────────────────────────────────────────────────────────────────────────────

def _groq_chat_stream(messages: list[dict], model: str = GROQ_MODEL) -> Generator[str, None, None]:
    """Groq üzerinden ajansal sohbet — OpenAI-uyumlu manuel tool loop."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY tanımlı değil.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL, timeout=60.0)

    # Mesaj geçmişini OpenAI formatına çevir
    convo: list[dict] = [{"role": "system", "content": AGENT_SYSTEM}]
    for m in messages:
        convo.append({"role": m["role"], "content": m["content"]})

    # 8b TPM 6k limitini aşmamak için 8b'de daha düşük max_tokens
    is_8b = "8b" in model
    max_iterations = 4 if is_8b else 5
    max_tokens = 800 if is_8b else 2000

    for it in range(max_iterations):
        # Son iterasyonda tool çağırmayı yasak et — özet/cevap zorla
        is_final = (it == max_iterations - 1)
        kwargs = dict(
            model=model,
            messages=convo,
            stream=True,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        if is_final:
            kwargs["tool_choice"] = "none"
            # Son yanıtta önceki tool sonuçlarına dayanarak özet iste
            convo.append({
                "role": "user",
                "content": (
                    "Yukarıdaki araç verilerine dayanarak SORUMU ŞİMDİ Türkçe yanıtla. "
                    "Yeni araç ÇAĞIRMA. Kısa, somut, sayılarla."
                ),
            })
            kwargs["messages"] = convo
        else:
            kwargs["tools"] = GROQ_TOOL_SCHEMAS

        resp = client.chat.completions.create(**kwargs)

        # Streaming sırasında parçaları biriktir
        full_text = ""
        tool_calls_acc: list[dict] = []  # index → {"id", "name", "args"}

        for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # Metin parçası
            if getattr(delta, "content", None):
                full_text += delta.content
                yield f"data: {json.dumps({'text': delta.content}, ensure_ascii=False)}\n\n"

            # Araç çağrısı parçaları
            if getattr(delta, "tool_calls", None):
                for tcd in delta.tool_calls:
                    idx = tcd.index
                    while len(tool_calls_acc) <= idx:
                        tool_calls_acc.append({"id": "", "name": "", "args": ""})
                    if tcd.id:
                        tool_calls_acc[idx]["id"] = tcd.id
                    if tcd.function:
                        if tcd.function.name:
                            tool_calls_acc[idx]["name"] = tcd.function.name
                        if tcd.function.arguments:
                            tool_calls_acc[idx]["args"] += tcd.function.arguments

        # Araç çağrısı yoksa — bittik
        if not tool_calls_acc:
            return

        # Asistan mesajını geçmişe ekle (tool_call'larla)
        convo.append({
            "role": "assistant",
            "content": full_text or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"] or "{}"},
                }
                for tc in tool_calls_acc
            ],
        })

        # Her aracı çalıştır, sonucu geçmişe ekle, label yayınla
        for tc in tool_calls_acc:
            name = tc["name"]
            try:
                args = json.loads(tc["args"]) if tc["args"] else {}
            except json.JSONDecodeError:
                args = {}

            label = _label_for(name, args)
            yield f"data: {json.dumps({'tool': name, 'label': label}, ensure_ascii=False)}\n\n"

            fn = TOOL_FUNCTIONS.get(name)
            if fn is None:
                result = f"Bilinmeyen araç: {name}"
            else:
                try:
                    result = fn(**args) if args else fn()
                except Exception as exc:
                    result = f"Araç hatası ({name}): {exc}"

            convo.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    # Maks iterasyona ulaşıldı
    yield f"data: {json.dumps({'text': '\\n\\n[Maks araç iterasyonuna ulaşıldı.]'}, ensure_ascii=False)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# CLAUDE stream (fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _claude_chat_stream(messages: list[dict]) -> Generator[str, None, None]:
    """Claude üzerinden ajansal sohbet — beta_tool runner ile."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY tanımlı değil.")
    if not _TOOLS_AVAILABLE_CLAUDE:
        raise RuntimeError("Claude beta_tool yüklü değil.")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    runner = client.beta.messages.tool_runner(
        stream=True,
        model=CLAUDE_MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=AGENT_SYSTEM,
        messages=messages,
        tools=AGENT_TOOLS_CLAUDE,
    )

    for stream in runner:
        for text in stream.text_stream:
            yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"

        final_msg = stream.get_final_message()
        for block in final_msg.content:
            if block.type == "tool_use":
                label = _label_for(block.name, dict(block.input or {}))
                yield f"data: {json.dumps({'tool': block.name, 'label': label}, ensure_ascii=False)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Genel akış — Groq → Claude fallback
# ─────────────────────────────────────────────────────────────────────────────

def _is_rate_limit(exc: Exception) -> bool:
    """Groq rate-limit hatası mı? (429 + 'rate_limit')"""
    s = str(exc).lower()
    return "429" in s or "rate_limit" in s or "tokens per day" in s


def _is_daily_limit(exc: Exception) -> bool:
    """Groq günlük (TPD) limit hatası mı?"""
    s = str(exc).lower()
    return "tokens per day" in s or "tpd" in s


# ── 70b TPD-dolu skip cache (process içi) ──────────────────────────────────────
# Eğer 70b günlük limiti dolu çıkarsa, sonraki çağrılarda direkt 8b'ye git.
# 90 dakika sonra cache temizlenir (Groq reset için tipik süre).
_GROQ_70B_SKIP_UNTIL: float = 0.0
_GROQ_70B_SKIP_DURATION = 5400  # 90 dk


def _is_70b_locked() -> bool:
    return time.monotonic() < _GROQ_70B_SKIP_UNTIL


def _lock_70b():
    global _GROQ_70B_SKIP_UNTIL
    _GROQ_70B_SKIP_UNTIL = time.monotonic() + _GROQ_70B_SKIP_DURATION
    logger.warning("Groq 70b günlük limit doldu — %d dk skip cache aktif.",
                   _GROQ_70B_SKIP_DURATION // 60)


def agent_chat_stream(messages: list[dict]) -> Generator[str, None, None]:
    """
    Ajansal sohbet akışı — 3 katmanlı fallback.

    Sıralama:
      1) Groq llama-3.3-70b-versatile (yüksek kalite)
      2) Groq llama-3.1-8b-instant   (ayrı TPD kotası, rate-limit yedeği)
      3) Claude opus-4-7              (Anthropic key varsa)

    Frontend'in algıladığı SSE format aynıdır:
        data: {"text": "..."}
        data: {"tool": "...", "label": "..."}
        data: {"provider": "groq-70b"|"groq-8b"|"claude", "status": "active"|"fallback"}
        data: {"error": "..."}
        data: [DONE]
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")
    claude_key = os.environ.get("ANTHROPIC_API_KEY", "")

    # ── 1) Groq 70b — birincil (eğer son 90dk içinde TPD doldurmamışsa)
    skip_70b = _is_70b_locked()
    if groq_key and not skip_70b:
        try:
            payload = {"provider": "groq-70b", "status": "active", "model": GROQ_MODEL}
            yield f"data: {json.dumps(payload)}\n\n"
            yield from _groq_chat_stream(messages, model=GROQ_MODEL)
            yield "data: [DONE]\n\n"
            return
        except Exception as exc_70b:
            is_rate = _is_rate_limit(exc_70b)
            if _is_daily_limit(exc_70b):
                _lock_70b()
            logger.warning("Groq 70b başarısız (%s): %s",
                           "RATE-LIMIT" if is_rate else "ERROR", exc_70b)

            # ── 2) Groq 8b yedek — ayrı TPD kotası
            if is_rate:
                try:
                    payload = {
                        "provider": "groq-8b",
                        "status": "fallback",
                        "model": GROQ_BACKUP_MODEL,
                        "reason": "günlük token limit (70b)",
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    yield from _groq_chat_stream(messages, model=GROQ_BACKUP_MODEL)
                    yield "data: [DONE]\n\n"
                    return
                except Exception as exc_8b:
                    logger.warning("Groq 8b de başarısız: %s", exc_8b)
                    last_exc = exc_8b
            else:
                last_exc = exc_70b

            # ── 3) Claude yedek
            if claude_key:
                try:
                    payload = {
                        "provider": "claude",
                        "status": "fallback",
                        "reason": str(last_exc)[:120],
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    yield from _claude_chat_stream(messages)
                    yield "data: [DONE]\n\n"
                    return
                except Exception as exc_cl:
                    logger.exception("Claude da başarısız")
                    err = (
                        f"Tüm sağlayıcılar başarısız. "
                        f"Groq 70b/8b: token/hata · Claude: {str(exc_cl)[:120]}"
                    )
                    yield f"data: {json.dumps({'error': err}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            # Groq yenildi + Claude key yok → hata
            err = (
                f"Groq token limit doldu, Claude API key yok. "
                f"Detay: {str(last_exc)[:150]}"
            )
            yield f"data: {json.dumps({'error': err}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

    # ── Groq key var ama 70b skip kilidi aktif → direkt 8b ile başla
    if groq_key and skip_70b:
        try:
            payload = {
                "provider": "groq-8b",
                "status": "active",
                "model": GROQ_BACKUP_MODEL,
                "reason": "70b günlük kotası dolu (yedek model aktif)",
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield from _groq_chat_stream(messages, model=GROQ_BACKUP_MODEL)
            yield "data: [DONE]\n\n"
            return
        except Exception as exc_8b:
            logger.warning("Groq 8b doğrudan da başarısız: %s", exc_8b)
            if claude_key:
                try:
                    payload = {"provider": "claude", "status": "fallback", "reason": str(exc_8b)[:120]}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    yield from _claude_chat_stream(messages)
                except Exception:
                    err = (
                        "Tüm sağlayıcılar şu an dolu. Groq 8b dakika başına token limiti aştı. "
                        "Lütfen 30-60 saniye sonra tekrar dene."
                    )
                    yield f"data: {json.dumps({'error': err}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            err = (
                "Groq 8b dakika limit doldu (70b günlük kotası da dolu). "
                "30-60 saniye sonra tekrar deneyin."
            )
            yield f"data: {json.dumps({'error': err}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

    # ── Groq key yok → sadece Claude
    if claude_key:
        try:
            yield f"data: {json.dumps({'provider': 'claude', 'status': 'active'})}\n\n"
            yield from _claude_chat_stream(messages)
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)[:200]}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Hiçbir key yok
    err = "GROQ_API_KEY veya ANTHROPIC_API_KEY .env dosyasında olmalı."
    yield f"data: {json.dumps({'error': err}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


__all__ = [
    "agent_chat_stream",
    "AGENT_SYSTEM",
    "TOOL_FUNCTIONS",
    "GROQ_TOOL_SCHEMAS",
    "AGENT_TOOLS_CLAUDE",
    "PRIMARY_PROVIDER",
    "GROQ_MODEL",
    "CLAUDE_MODEL",
]
