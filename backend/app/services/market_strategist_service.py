"""
Market Strategist Service — Senaryo & Aktör Perspektif Analizi
─────────────────────────────────────────────────────────────────────────────

Üst düzey jeopolitik piyasa stratejisti gibi cevap üretir:
  • Mevcut teknik sinyalleri, rejimi, multi-TF hizalamayı, S/R kalitesini,
    chart pattern teyitlerini ve son haber akışını okur.
  • ABD/İsrail/İran/Çin/Rusya/OPEC/Fed gibi aktörlerin **kamuya açık**
    insentif yapılarına göre senaryo akıl yürütmesi yapar.
  • Asla içerden bilgi iddiası, gizli devlet planı, broker emri veya
    al/sat talimatı üretmez.

PAPER_SAFE / NO_EXECUTION. Tüm kararlar insana aittir.

Veri kaynakları — yalnızca mevcut sistem servisleri:
  - regime_report_service / api.consensus._build_pipeline
  - consensus_engine
  - agent_chart_reader_service
  - chart_pattern_provider (api.chart_patterns)
  - signal_attribution_service
  - sr_quality_service
  - alert_event_service
  - news_provider (varsa, opsiyonel)
  - agent_audit_log (son N karar)
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Yasak ifade listeleri — modelin çıktısında ve cevap derleme aşamasında filtre
_FORBIDDEN_EXECUTION_PATTERNS = (
    r"\bbuy\b", r"\bsell\b", r"\bexecute\b", r"\bplace order\b",
    r"\bal emri\b", r"\bsat emri\b", r"\baçıl\b", r"\bshort aç\b", r"\blong aç\b",
    r"\bbroker\b", r"\bemir gönder\b", r"\border placement\b",
)
_FORBIDDEN_INSIDER_PATTERNS = (
    r"\binsider\b", r"\bgizli plan\b", r"\bsecret plan\b",
    r"\bI know what (?:Trump|Iran|Putin|Xi|Biden|Netanyahu) will\b",
    r"\biçeriden öğrendim\b", r"\bgizli bilgi\b",
    r"\bclassified intelligence\b",
)

_DEFAULT_SYMBOLS = ("BTCUSD", "XAUUSD", "XAGUSD", "BRENT")
_CLAUDE_MODEL = os.environ.get("CLAUDE_AGENT_MODEL", "claude-opus-4-7")

# Groq (primary) → Claude (fallback) — kullanıcı `provider` ile manuel override edebilir
_GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
_GROQ_BACKUP_MODEL = os.environ.get("GROQ_BACKUP_MODEL", "llama-3.1-8b-instant")
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_VALID_PROVIDERS = ("auto", "groq", "claude")


# ── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class StrategistContext:
    """Aktör perspektif analizinin girdi paketi."""
    snapshot_id:        str | None
    generated_at:       str
    regime:             str | None
    decision:           str | None
    consensus_summary:  list[dict[str, Any]]     = field(default_factory=list)
    chart_patterns:     dict[str, dict]          = field(default_factory=dict)
    chart_readings:     dict[str, dict]          = field(default_factory=dict)
    signal_attribution: dict[str, Any]           = field(default_factory=dict)
    sr_quality:         dict[str, dict]          = field(default_factory=dict)
    recent_alerts:      list[dict[str, Any]]     = field(default_factory=list)
    recent_headlines:   list[dict[str, Any]]     = field(default_factory=list)
    recent_audits:      list[dict[str, Any]]     = field(default_factory=list)
    missing_data:       list[str]                = field(default_factory=list)


@dataclass
class StrategistResponse:
    """Yapılandırılmış strateji cevabı."""
    answer:                 str
    market_read:            list[str]            = field(default_factory=list)
    cross_asset_map:        list[dict[str, Any]] = field(default_factory=list)
    actor_perspective_map:  list[dict[str, Any]] = field(default_factory=list)
    headline_scenarios:     list[dict[str, Any]] = field(default_factory=list)
    invalidation:           list[str]            = field(default_factory=list)
    confidence:             dict[str, Any]       = field(default_factory=dict)
    evidence_refs:          list[dict[str, Any]] = field(default_factory=list)
    safety_notice:          str                  = ""
    abstained:              bool                 = False
    abstain_reason:         str | None           = None
    model_used:             str | None           = None


# ── Context builder ─────────────────────────────────────────────────────────

def _safe_call(label: str, fn, *args, **kwargs):
    """Hata sırasında log'a yaz, None döndür — context derlemesi kırılmasın."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.debug("strategist context %s atlandı: %s", label, exc)
        return None


def build_context(
    symbols: list[str] | None = None,
    snapshot_id: str | None = None,
) -> StrategistContext:
    """Stratejist için tüm sistem verisini topla.

    Hiçbir live data provider çağrısı eklenmez; sadece mevcut servisler okunur.
    """
    syms = [s.upper() for s in (symbols or _DEFAULT_SYMBOLS)]
    missing: list[str] = []

    # ── 1. Regime + consensus pipeline (mevcut) ─────────────────────────────
    regime = None
    decision = None
    consensus_summary: list[dict[str, Any]] = []
    try:
        from app.api.consensus import _build_full_signal, _build_pipeline
        report, rotation, mtf, _raw = _build_pipeline()
        regime = getattr(report, "regime", None) or getattr(getattr(report, "macro_layer", None), "regime", None)
        decision = getattr(report, "decision", None)
        for asset in syms:
            asset_meta = next(
                (a for a in getattr(report, "asset_signals", []) if a.asset_code == asset),
                None,
            )
            if asset_meta is None:
                missing.append(f"asset_signal:{asset}")
                continue
            try:
                full = _build_full_signal(asset_meta, report, rotation, mtf)
                consensus_summary.append({
                    "symbol":           asset,
                    "final_score":      full.get("final_score"),
                    "final_direction":  full.get("final_direction"),
                    "confluence":       full.get("confluence", {}).get("status"),
                    "primary_tf":       full.get("primary_tf"),
                    "raw_regime":       full.get("raw_regime"),
                    "top_contribs":     _top_contribs(full),
                })
            except Exception as exc:
                missing.append(f"consensus:{asset}:{type(exc).__name__}")
    except Exception as exc:
        missing.append(f"pipeline:{type(exc).__name__}")

    # ── 2. Chart patterns (4 ana parite × 3 TF, cached) ─────────────────────
    chart_patterns: dict[str, dict] = {}
    try:
        from app.api.chart_patterns import _build_all_patterns
        all_patterns = _safe_call("chart_patterns", _build_all_patterns) or {}
        for sym in syms:
            if sym in all_patterns:
                chart_patterns[sym] = all_patterns[sym]
    except Exception:
        missing.append("chart_patterns")

    # ── 3. Agent chart reader (multi-TF S/R + ATR + RSI) ────────────────────
    chart_readings: dict[str, dict] = {}
    try:
        from app.services import agent_chart_reader_service as cr
        for sym in syms:
            r = _safe_call(f"chart_reader:{sym}", cr.read_chart, sym, ("1h", "4h", "1d"))
            if r is not None:
                chart_readings[sym] = cr.reading_to_dict(r)
    except Exception:
        missing.append("chart_reader")

    # ── 4. Signal attribution (modül bazlı PnL) ─────────────────────────────
    signal_attribution: dict[str, Any] = {}
    try:
        from app.services import signal_attribution_service as sas
        signal_attribution = _safe_call("attribution", sas.summary) or {}
    except Exception:
        missing.append("signal_attribution")

    # ── 5. S/R quality — chart readings + sr_quality_service ────────────────
    sr_quality: dict[str, dict] = {}
    try:
        import numpy as _np  # noqa: F401  — bağımlılık doğrulama
        for sym, reading in chart_readings.items():
            views = reading.get("views") or {}
            primary_tf = reading.get("primary_tf") or "1d"
            v = views.get(primary_tf)
            if not v:
                continue
            sup = v.get("support") or 0.0
            res = v.get("resistance") or 0.0
            # evaluate_pair OHLCV array ister; burada elimizde yok → sadece
            # seviyeleri ve mevcut rating'i raporla, hesap yapma
            sr_quality[sym] = {
                "support":    sup,
                "resistance": res,
                "atr":        v.get("atr"),
                "rsi_14":     v.get("rsi_14"),
                "note":       "level only (OHLCV cache yok)",
            }
    except Exception:
        missing.append("sr_quality")

    # ── 6. Alerts (last 10) ─────────────────────────────────────────────────
    recent_alerts: list[dict[str, Any]] = []
    try:
        from app.services import alert_event_service as alerts
        recent_alerts = _safe_call("alerts", alerts.get_recent, 10) or []
    except Exception:
        missing.append("alerts")

    # ── 7. News headlines (last 15, varsa) ──────────────────────────────────
    recent_headlines: list[dict[str, Any]] = []
    try:
        from app.providers.news_provider import NewsProvider
        provider = NewsProvider()
        headlines = _safe_call("news", provider.fetch_headlines, 15) or ()
        for h in headlines[:15]:
            recent_headlines.append({
                "title":     getattr(h, "title", ""),
                "source":    getattr(h, "source", ""),
                "sentiment": getattr(h, "sentiment", ""),
                "published": str(getattr(h, "published_at", "")),
            })
    except Exception:
        missing.append("news")

    # ── 8. Agent audit (last 8) ─────────────────────────────────────────────
    recent_audits: list[dict[str, Any]] = []
    try:
        from app.services import agent_audit_log as audit
        recent_audits = _safe_call("audit", audit.get_recent, 8) or []
    except Exception:
        missing.append("audit")

    return StrategistContext(
        snapshot_id        = snapshot_id,
        generated_at       = datetime.now(UTC).isoformat(),
        regime             = regime,
        decision           = decision,
        consensus_summary  = consensus_summary,
        chart_patterns     = chart_patterns,
        chart_readings     = chart_readings,
        signal_attribution = signal_attribution,
        sr_quality         = sr_quality,
        recent_alerts      = recent_alerts,
        recent_headlines   = recent_headlines,
        recent_audits      = recent_audits,
        missing_data       = missing,
    )


def _top_contribs(full_signal: dict[str, Any], top_n: int = 3) -> list[dict[str, Any]]:
    base = full_signal.get("base") or {}
    contribs = (base.get("contributions") or {})
    items: list[dict[str, Any]] = []
    for mod, payload in contribs.items():
        ws = 0.0
        if isinstance(payload, dict):
            ws = float(payload.get("weighted_score") or 0.0)
        elif isinstance(payload, (int, float)):
            ws = float(payload)
        items.append({"module": mod, "weighted_score": round(ws, 2)})
    items.sort(key=lambda x: abs(x["weighted_score"]), reverse=True)
    return items[:top_n]


# ── System & user prompts ───────────────────────────────────────────────────

def _build_system_prompt(language: str) -> str:
    lang_clause = "Türkçe" if language.lower().startswith("tr") else "English"
    return f"""You are E-YAY's MARKET STRATEGIST. You speak like a serious geopolitical
markets/commodities strategist who reads tape and macro/political context.

LANGUAGE: Answer in {lang_clause}. Direct, sharp, professional — NOT academic, NOT chatty.

WHAT YOU CAN DO:
  • Read the structured context (regime, consensus, multi-TF technicals,
    chart patterns, signal attribution, S/R quality, recent alerts, news).
  • Reason about ACTORS' (US/Israel/Iran/China/Russia/OPEC/Fed) likely
    incentives FROM PUBLIC MARKET DATA only.
  • Produce scenario-based market interpretation and likely narrative catalysts.
  • Identify invalidation levels — what would prove your scenario wrong.

ABSOLUTE PROHIBITIONS:
  • NEVER claim insider information, classified intelligence, or non-public
    state plans. Always frame actor reasoning with phrases like:
    "kamuya açık piyasa verisi ve senaryo akıl yürütmesine göre" /
    "based on public market data and scenario reasoning".
  • NEVER produce buy/sell/execute/al/sat instructions or position-size advice.
  • NEVER pretend to know what Trump/Iran/Putin/Xi/etc. WILL say or do.
    Always use conditional language: "If X wants Y, market would need Z."
  • NEVER suggest market manipulation or operational political advice.
  • NEVER skip the safety_notice or invalidation sections.

OUTPUT FORMAT — STRICT JSON only, no prose around it. Schema:
{{
  "answer": "<short executive summary, 2-4 sentences>",
  "market_read": ["<one-line technical reads, 3-6 items>"],
  "cross_asset_map": [
    {{"axis": "<e.g. risk-on vs commodity premium>", "stance": "<your read>"}}
  ],
  "actor_perspective_map": [
    {{
      "actor": "US | Israel | Iran | China | Russia | OPEC | Fed",
      "public_incentive": "<derived from observable policy stance>",
      "likely_narrative_lever": "<what story they'd push to align market>",
      "evidence_basis": "<which context items support this>"
    }}
  ],
  "headline_scenarios": [
    {{"name": "<scenario>", "trigger": "<headline shape>", "market_path": "<expected reaction>"}}
  ],
  "invalidation": ["<level or condition that would prove the scenario wrong>"],
  "confidence": {{"band": "low | medium | high", "rationale": "<one line>"}},
  "evidence_refs": [
    {{"type": "consensus|chart|attribution|alert|news|audit", "ref": "<symbol or id>", "what": "<what it shows>"}}
  ],
  "safety_notice": "Senaryo analizi; içerden bilgi DEĞİL. PAPER_SAFE / NO_EXECUTION."
}}

If the provided context is too thin to support a scenario, return:
{{"abstained": true, "abstain_reason": "<which data is missing>", "safety_notice": "..."}}
"""


def _build_user_prompt(question: str, ctx: StrategistContext) -> str:
    blob = {
        "snapshot_id":        ctx.snapshot_id,
        "generated_at":       ctx.generated_at,
        "regime":             ctx.regime,
        "decision":           ctx.decision,
        "consensus_summary":  ctx.consensus_summary,
        "chart_patterns":     ctx.chart_patterns,
        "chart_readings":     ctx.chart_readings,
        "signal_attribution": ctx.signal_attribution,
        "sr_quality":         ctx.sr_quality,
        "recent_alerts":      ctx.recent_alerts,
        "recent_headlines":   ctx.recent_headlines,
        "recent_audits":      ctx.recent_audits,
        "missing_data":       ctx.missing_data,
    }
    return (
        f"USER QUESTION:\n{question.strip()}\n\n"
        f"SYSTEM CONTEXT (JSON, use only this — no external data):\n"
        f"{json.dumps(blob, ensure_ascii=False, default=str)[:24000]}\n"
    )


# ── LLM call ────────────────────────────────────────────────────────────────

def _call_groq_model(system_prompt: str, user_prompt: str, model: str) -> tuple[str, str] | None:
    """Groq'tan (OpenAI-uyumlu) belirli bir modelle tek-shot cevap al."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL, timeout=60.0)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=2500,
            temperature=0.4,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = resp.choices[0].message.content or ""
        return raw, f"groq/{model}"
    except Exception as exc:
        logger.warning("strategist Groq %s çağrısı başarısız: %s", model, exc)
        return None


def _call_groq(system_prompt: str, user_prompt: str) -> tuple[str, str] | None:
    """Groq fallback zinciri: önce ana model, olmazsa yedek model."""
    result = _call_groq_model(system_prompt, user_prompt, _GROQ_MODEL)
    if result is not None:
        return result
    return _call_groq_model(system_prompt, user_prompt, _GROQ_BACKUP_MODEL)


def _call_claude(system_prompt: str, user_prompt: str) -> tuple[str, str] | None:
    """Anthropic Claude tek-shot çağrı. API key yoksa None → abstain path."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=2500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                raw = block.text
                break
        return raw, _CLAUDE_MODEL
    except Exception as exc:
        logger.warning("strategist Claude çağrısı başarısız: %s", exc)
        return None


def _call_llm(system_prompt: str, user_prompt: str, *, provider: str = "auto") -> tuple[str, str] | None:
    """
    Sağlayıcı seçimine göre LLM çağrısı.

    - "groq"  : yalnızca Groq dene (model fallback zinciriyle)
    - "claude": yalnızca Claude dene
    - "auto"  : Groq önce, olmazsa Claude (varsayılan öncelik sırası)

    API key yoksa veya çağrı başarısızsa None → abstain path.
    """
    if provider == "groq":
        return _call_groq(system_prompt, user_prompt)
    if provider == "claude":
        return _call_claude(system_prompt, user_prompt)

    result = _call_groq(system_prompt, user_prompt)
    if result is not None:
        return result
    return _call_claude(system_prompt, user_prompt)


# ── Response parsing & safety filtering ─────────────────────────────────────

def _extract_json_blob(raw: str) -> dict | None:
    """Modelin döndürdüğü metinden ilk top-level JSON objesini al."""
    if not raw:
        return None
    raw = raw.strip()
    # Code-fence stripping
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).rstrip("`").strip()
    # İlk { ile son } arası
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _contains_forbidden(text: str) -> tuple[bool, str | None]:
    if not isinstance(text, str) or not text:
        return False, None
    low = text.lower()
    for pat in _FORBIDDEN_EXECUTION_PATTERNS:
        if re.search(pat, low):
            return True, f"execution_language:{pat}"
    for pat in _FORBIDDEN_INSIDER_PATTERNS:
        if re.search(pat, low):
            return True, f"insider_claim:{pat}"
    return False, None


def _sanitize_section(items: Any) -> Any:
    """Cevabın metin alanlarında yasak ifade varsa redacted ile değiştir."""
    if isinstance(items, str):
        hit, _ = _contains_forbidden(items)
        return "[REDACTED · execution/insider phrase removed]" if hit else items
    if isinstance(items, list):
        return [_sanitize_section(x) for x in items]
    if isinstance(items, dict):
        return {k: _sanitize_section(v) for k, v in items.items()}
    return items


def _build_abstain(reason: str, ctx: StrategistContext) -> StrategistResponse:
    return StrategistResponse(
        answer=(
            "Veri tabanı senaryo akıl yürütmesi için yetersiz. "
            "Lütfen tick'i bekleyin veya snapshot_id ile yeniden deneyin."
        ),
        market_read=[],
        cross_asset_map=[],
        actor_perspective_map=[],
        headline_scenarios=[],
        invalidation=["Senaryo iddiası yok — abstain"],
        confidence={"band": "low", "rationale": reason},
        evidence_refs=[
            {"type": "system", "ref": "missing_data", "what": ", ".join(ctx.missing_data[:8])}
        ],
        safety_notice=(
            "Senaryo analizi; içerden bilgi DEĞİL. PAPER_SAFE / NO_EXECUTION. "
            "Tüm kararlar insana aittir."
        ),
        abstained=True,
        abstain_reason=reason,
        model_used=None,
    )


def _has_minimum_context(ctx: StrategistContext) -> bool:
    """Senaryo çıkarımı için minimum eşik: en az consensus veya chart_readings."""
    return bool(ctx.consensus_summary or ctx.chart_readings or ctx.chart_patterns)


# ── Public entry ────────────────────────────────────────────────────────────

def answer(
    question: str,
    *,
    symbols: list[str] | None = None,
    snapshot_id: str | None = None,
    language: str = "tr",
    provider: str | None = None,
) -> tuple[StrategistResponse, StrategistContext]:
    """
    Stratejist cevabı üret. Veri yoksa abstain, LLM yoksa abstain.

    `provider`: "auto" (varsayılan, Groq önce → Claude yedek) | "groq" | "claude"
    Geçersiz/boş değer "auto" olarak ele alınır — kullanıcı dilerse manuel seçer.

    Returns: (StrategistResponse, StrategistContext)
    """
    provider_choice = provider if provider in _VALID_PROVIDERS else "auto"

    ctx = build_context(symbols=symbols, snapshot_id=snapshot_id)

    if not isinstance(question, str) or not question.strip():
        return _build_abstain("empty_question", ctx), ctx

    if not _has_minimum_context(ctx):
        return _build_abstain("insufficient_context", ctx), ctx

    system_prompt = _build_system_prompt(language)
    user_prompt   = _build_user_prompt(question, ctx)

    llm_result = _call_llm(system_prompt, user_prompt, provider=provider_choice)
    if llm_result is None:
        return _build_abstain("llm_unavailable", ctx), ctx

    raw, model_used = llm_result
    parsed = _extract_json_blob(raw)
    if parsed is None:
        return _build_abstain("model_parse_failed", ctx), ctx

    # Model kendisi abstain ettiyse
    if parsed.get("abstained") is True:
        return StrategistResponse(
            answer=parsed.get("answer", "Veri yetersiz."),
            invalidation=parsed.get("invalidation", []),
            confidence=parsed.get("confidence", {"band": "low"}),
            evidence_refs=parsed.get("evidence_refs", []),
            safety_notice=parsed.get("safety_notice", _default_safety()),
            abstained=True,
            abstain_reason=parsed.get("abstain_reason", "model_abstain"),
            model_used=model_used,
        ), ctx

    # Sanitize: yasak ifadeleri redacted yap
    cleaned = _sanitize_section(parsed)

    return StrategistResponse(
        answer                = str(cleaned.get("answer", "")).strip(),
        market_read           = list(cleaned.get("market_read", [])),
        cross_asset_map       = list(cleaned.get("cross_asset_map", [])),
        actor_perspective_map = list(cleaned.get("actor_perspective_map", [])),
        headline_scenarios    = list(cleaned.get("headline_scenarios", [])),
        invalidation          = list(cleaned.get("invalidation", [])),
        confidence            = dict(cleaned.get("confidence", {"band": "low"})),
        evidence_refs         = list(cleaned.get("evidence_refs", [])),
        safety_notice         = str(cleaned.get("safety_notice", _default_safety())),
        abstained             = False,
        abstain_reason        = None,
        model_used            = model_used,
    ), ctx


def _default_safety() -> str:
    return (
        "Senaryo analizi; içerden bilgi DEĞİL. Kamuya açık piyasa verisi ve "
        "akıl yürütmeye dayanır. PAPER_SAFE · NO_EXECUTION · tüm kararlar insana aittir."
    )


__all__ = [
    "StrategistContext",
    "StrategistResponse",
    "build_context",
    "answer",
]
