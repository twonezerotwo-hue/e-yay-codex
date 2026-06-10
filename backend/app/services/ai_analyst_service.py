"""
AI Analist Servisi — E-YAY BrainChain.
Token-minimal: sıkıştırılmış prompt, max_tokens=2500, günlük öğrenme döngüsü.
Önbellek: 15 dakika. Execution: OFF / NO_EXECUTION.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.providers.capital_rotation_provider import CapitalRotation
from app.providers.geo_news_provider import GeoHeadline
from app.services.report_journal import build_learning_block, load_recent, save

# ---------------------------------------------------------------------------
# Çıktı modeli
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AIAnalystReport:
    generated_at: str
    model: str
    cached: bool
    narrative: str
    key_signals: list[str]
    verdict: str
    confidence_note: str
    error: str | None


# ---------------------------------------------------------------------------
# Önbellek (15 dk)
# ---------------------------------------------------------------------------

_CACHE_TTL = 7200  # 2 saat — bkz. _GROQ_DAILY_CALL_BUDGET açıklaması
_STALE_TTL = 14400  # 4 saatlik stale-while-error: rate-limit varsa eski raporu göster
_cached_report: AIAnalystReport | None = None
_cached_at: float = 0.0


def _get_cached() -> AIAnalystReport | None:
    if _cached_report is not None and (time.monotonic() - _cached_at) < _CACHE_TTL:
        import dataclasses
        return dataclasses.replace(_cached_report, cached=True)
    return None


def _get_stale() -> AIAnalystReport | None:
    """Son çare: rapor üretilemedi ama elde eski/cached rapor var."""
    if _cached_report is not None and (time.monotonic() - _cached_at) < _STALE_TTL:
        import dataclasses
        return dataclasses.replace(_cached_report, cached=True)
    return None


def _set_cache(report: AIAnalystReport) -> None:
    global _cached_report, _cached_at
    _cached_report = report
    _cached_at = time.monotonic()


# ---------------------------------------------------------------------------
# Günlük Groq çağrı bütçesi — otomatik sayfa yenilemesi (30s/60s) Groq'u
# günde onlarca kez tetiklemesin.
#
# Ölçülen prompt boyutu (gerçek pipeline verisiyle): ~1700 token (girdi).
# max_tokens=2500 (çıktı tavanı) → en kötü durumda ~4200 token/çağrı,
# tipik kullanımda (gözlenen rapor uzunluklarına göre) ~2200-2700 token/çağrı.
#
# llama-3.3-70b-versatile ücretsiz katman: TPD = 100.000 token/gün. Bu kota
# AI raporu + market stratejisti + agent arasında PAYLAŞILIR; AI raporuna
# yaklaşık %40'lık bir pay (~40k token/gün) ayırıyoruz, gerisi diğer
# servisler için kalsın:
#   12 çağrı/gün × ~3450 token (ortalama) ≈ 41k token  → %41 — güvenli marj
#   12 çağrı/gün × ~4200 token (en kötü)  ≈ 50k token  → %50 — yine limit altı
#
# _CACHE_TTL = 2 saat → sürekli trafikte doğal üst sınır = 24 çağrı/gün;
# bu sayaç (varsayılan 12/gün) Groq'u günde en fazla ~2 saatte bir, gerçekte
# ortalama ~her 2 saatte bir dener. Tavan dolunca Groq hiç denenmez — zaten
# 429 dönecek isteği boşa harcamadan doğrudan Claude'a / stale önbelleğe
# düşülür. Diske kalıcı, restart'ta sıfırlanmaz.
# ---------------------------------------------------------------------------

_GROQ_DAILY_CALL_BUDGET = int(os.environ.get("AI_REPORT_GROQ_DAILY_BUDGET", "12"))
_BUDGET_FILE = Path(__file__).resolve().parents[2] / "data" / "groq_daily_budget.json"
_budget_date = ""
_budget_used = 0


def _load_budget() -> None:
    global _budget_date, _budget_used
    today = datetime.now(UTC).date().isoformat()
    if _budget_date == today:
        return
    _budget_date = today
    _budget_used = 0
    try:
        raw = json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
        if raw.get("date") == today:
            _budget_used = int(raw.get("used", 0))
    except (OSError, ValueError, TypeError):
        pass


def _try_consume_groq_budget() -> bool:
    """Bugün Groq deneme hakkı kaldıysa tüketir → True; tavan dolduysa → False."""
    global _budget_used
    _load_budget()
    if _budget_used >= _GROQ_DAILY_CALL_BUDGET:
        return False
    _budget_used += 1
    try:
        _BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BUDGET_FILE.write_text(
            json.dumps({"date": _budget_date, "used": _budget_used}), encoding="utf-8",
        )
    except OSError:
        pass
    return True


# ---------------------------------------------------------------------------
# Prompt — token-minimal
# ---------------------------------------------------------------------------

def _build_prompt(
    macro: dict[str, Any],
    appetite: dict[str, Any],
    assets: list[dict[str, Any]],
    checklist: list[dict[str, Any]],
    decision: str,
    verdict_text: str,
    geo_news: tuple[GeoHeadline, ...],
    rotation: CapitalRotation | None = None,
    learning_block: str = "",
) -> str:

    # ── Asset tablosu — değer + delta + durum ───────────────────────────────
    def _fmt(a: dict) -> str:
        v = a.get("value")
        u = a.get("unit", "")
        val = f"{v:,.2f}{u}" if v is not None else "?"
        d7 = f" Δ7g:{a['delta_7d_pct']:+.1f}%" if a.get("delta_7d_pct") is not None else ""
        reason = a.get("reason", "")[:60]
        return f"  {a.get('asset_code'):12s} {val}{d7} [{a.get('status')}] {reason}"

    # BLOCKING ve CONFIRMED önce — sadece ilk 10 (token tasarrufu)
    sorted_assets = sorted(
        assets,
        key=lambda a: {"BLOCKING": 0, "CONFIRMED": 1, "PENDING": 2}.get(a.get("status", ""), 3)
    )[:10]
    asset_table = "\n".join(_fmt(a) for a in sorted_assets)

    # ── Teyit listesi ───────────────────────────────────────────────────────
    met = sum(1 for c in checklist if c.get("met"))
    total = len(checklist)
    unmet_items = [c["signal"] for c in checklist if not c.get("met")]
    checklist_line = f"{met}/{total} teyit tamamlandı"
    if unmet_items:
        checklist_line += f" | EKSIK: {', '.join(unmet_items)}"

    # ── Jeopolitik haberler — kompakt ───────────────────────────────────────
    region_map: dict[str, list[str]] = {}
    labels = {"usa": "ABD", "iran": "İRAN", "israel": "İSRAİL",
              "china": "ÇİN", "russia": "RUSYA", "europe": "AVRUPA", "global": "KÜRESEL"}
    for h in geo_news[:12]:  # ilk 12 başlık yeterli
        lbl = labels.get(h.region, h.region.upper())
        region_map.setdefault(lbl, []).append(f"[{h.sentiment[0]}] {h.title[:70]}")
    geo_block = "\n".join(
        f"  {lbl}: " + " / ".join(headlines[:2])
        for lbl, headlines in region_map.items()
    ) or "  Haber yok"

    # ── Sermaye rotasyonu — kompakt (8b TPM limiti için kısa) ───────────────
    rot_block = ""
    if rotation and rotation.error is None:
        top_scores = " | ".join(
            f"{cs.name}:{cs.score:+.2f}({cs.direction[0]})"
            for cs in sorted(rotation.class_scores, key=lambda x: -abs(x.score))[:5]
        )
        top_insights = " · ".join(
            ins.text[:70] for ins in sorted(rotation.key_insights, key=lambda x: -x.importance)[:3]
        )
        rot_block = (
            f"\nSERMAYE: akış={rotation.primary_flow}"
            f"{' → ' + rotation.secondary_flow if rotation.secondary_flow else ''}"
            f" · konv={rotation.conviction}/10"
            f"\n  Sınıf: {top_scores}"
            f"\n  Öngörü: {top_insights}"
        )

    # ── Prompt — kompakt (8b TPM 6k limiti için) ─────────────────────────────
    return f"""Sen finansal hikaye anlatıcısısın. PAPER_SAFE — işlem önerisi yasak. Çıktı: Türkçe.

KURALLAR:
- Hedef: piyasayı bilmeyen biri okuyup anlasın
- Teknik terim/etiket yok (CONFIRMED/BLOCKING/Δ7g vs.) — Türkçe açıkla
- Rakamı önce açıkla, sonra göm
- Düz akıcı paragraf — başlık/madde/emoji yok
- Karar "{decision}" — neden doğru olduğunu net açıkla (her varlık için ayrı)
- "Bekle" = "dokunma" değil — hangi varlık şu an actionable, hangisi değil, neden?

YAPI:
1) Haber → piyasa tepkisi → neden beklenmedik (varsa)
2) Para nereye akıyor (sade dille)
3) Senaryo: "Eğer X olursa → varlık yön+seviye; olmazsa → ..."
4) Karar gerekçesi (her varlık için neden long/wait/avoid)

── BAĞLAM ──
HABERLER (öncelik):
{geo_block}

PIYASA: {macro.get('regime','?')} (güven %{macro.get('confidence_pct','?')}) | DXY={macro.get('dxy_signal','?')} | Enerji={macro.get('energy_signal','?')} | Yield={macro.get('yield_curve_signal','?')}
İŞTAH: {appetite.get('status','?')} | Kredi={appetite.get('credit_signal','?')} | Korku={appetite.get('safe_haven_signal','?')}

VARLIKLAR (en kritik):
{asset_table}
{rot_block}

KARAR: {decision} — {verdict_text}
TEYİT: {checklist_line}
{learning_block}

ÇIKTI (SADECE JSON):
{{
  "narrative": "3-4 paragraf düz metin, \\n\\n ayracı. Habere başla, para akışı, senaryo ile bitir.",
  "key_signals": ["Sıradan dilde 3-5 sinyal — örn: 'BTC borsayla ayrıştı, büyük para kriptodan hisseye geçti'"],
  "verdict": "{decision} kararı neden doğru — tek cümle, sıradan dilde",
  "confidence_note": "En az emin olunan nokta — sade dille"
}}"""


# ---------------------------------------------------------------------------
# Ana servis — Groq (primary) → Claude (fallback)
# ---------------------------------------------------------------------------

_GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
_GROQ_BACKUP_MODEL = os.environ.get("GROQ_BACKUP_MODEL", "llama-3.1-8b-instant")
_CLAUDE_MODEL = "claude-haiku-4-5"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Kullanıcı manuel sağlayıcı seçebilir — varsayılan "auto" Groq önce → Claude yedek
_VALID_PROVIDERS = ("auto", "groq", "claude")

_SYS_PROMPT = (
    "Sen bir finansal hikaye anlatıcısısın. Yalnızca geçerli JSON "
    "döndür — başka hiçbir şey yazma. Schema: "
    '{"narrative": str, "key_signals": [str], "verdict": str, "confidence_note": str}'
)


def _build_system_prompt(persona_key: str | None, regime: str | None) -> tuple[str, float]:
    """Persona modülünden sistem promptu üret. Eski _SYS_PROMPT'a fallback."""
    try:
        from app.services.agent_persona import build_system_prompt, temperature_for
        sp = build_system_prompt(persona_key=persona_key, regime=regime)
        return sp, temperature_for(persona_key)
    except Exception:
        return _SYS_PROMPT, 0.5


def _call_groq_model(
    prompt: str,
    model: str,
    *,
    persona_key: str | None = None,
    regime: str | None = None,
) -> tuple[str, str] | None:
    """Groq'tan belirli bir modelle JSON cevabı al."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL, timeout=60.0)
        system_prompt, temp = _build_system_prompt(persona_key, regime)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=1800,
            temperature=temp,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content or ""
        return raw, f"groq/{model}"
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Groq %s başarısız: %s", model, exc)
        return None


def _call_groq(
    prompt: str,
    *,
    persona_key: str | None = None,
    regime: str | None = None,
) -> tuple[str, str] | None:
    """
    Çoklu Groq model fallback:
    1) llama-3.3-70b-versatile (yüksek kalite)
    2) llama-3.1-8b-instant   (ayrı TPD kotası, ucuz yedek)
    """
    result = _call_groq_model(prompt, _GROQ_MODEL, persona_key=persona_key, regime=regime)
    if result is not None:
        return result
    return _call_groq_model(prompt, _GROQ_BACKUP_MODEL, persona_key=persona_key, regime=regime)


def _call_claude(
    prompt: str,
    *,
    persona_key: str | None = None,
    regime: str | None = None,
) -> tuple[str, str] | None:
    """Claude fallback. (raw, model_used) veya None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        system_prompt, _ = _build_system_prompt(persona_key, regime)
        response = client.messages.create(
            model=_CLAUDE_MODEL,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = ""
        for block in response.content:
            if block.type == "text":
                raw = block.text
                break
        return raw, _CLAUDE_MODEL
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Claude da başarısız: %s", exc)
        return None


def generate_ai_report(
    macro: dict[str, Any],
    appetite: dict[str, Any],
    assets: list[dict[str, Any]],
    checklist: list[dict[str, Any]],
    decision: str,
    verdict: str,
    geo_news: tuple[GeoHeadline, ...],
    *,
    rotation: CapitalRotation | None = None,
    force_refresh: bool = False,
    persona_key: str | None = None,
    provider: str | None = None,
) -> AIAnalystReport:
    """
    `provider`: "auto" (varsayılan, Groq önce → Claude yedek) | "groq" | "claude".
    Kullanıcı manuel bir sağlayıcı seçtiğinde (groq/claude) önbellek atlanır —
    aksi halde diğer sağlayıcının önbelleğe aldığı rapor dönebilir.
    """
    provider_choice = provider if provider in _VALID_PROVIDERS else "auto"
    bypass_cache_for_provider = provider_choice != "auto"

    if not force_refresh and not bypass_cache_for_provider:
        cached = _get_cached()
        if cached:
            return cached

    now_iso = datetime.now(UTC).isoformat()

    groq_key = os.environ.get("GROQ_API_KEY", "")
    claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not groq_key and not claude_key:
        return AIAnalystReport(
            generated_at=now_iso, model="(none)", cached=False,
            narrative="", key_signals=[],
            verdict="GROQ_API_KEY veya ANTHROPIC_API_KEY tanımlı değil.",
            confidence_note="",
            error="No API key configured.",
        )

    # Geçmiş raporları yükle → öğrenme bloğu
    past = load_recent(n=5)
    learning_block = build_learning_block(past, assets) if past else ""

    prompt = _build_prompt(
        macro, appetite, assets, checklist,
        decision, verdict, geo_news, rotation,
        learning_block=learning_block,
    )

    regime_for_prompt = (macro or {}).get("regime")

    if provider_choice == "groq":
        result = (
            _call_groq(prompt, persona_key=persona_key, regime=regime_for_prompt)
            if _try_consume_groq_budget() else None
        )
    elif provider_choice == "claude":
        result = _call_claude(prompt, persona_key=persona_key, regime=regime_for_prompt)
    else:
        # auto: günlük Groq bütçesi varsa önce Groq dene → yoksa/başarısızsa Claude'a düş.
        # Bütçe dolduysa Groq hiç denenmez (zaten 429 dönecek isteği boşa harcamayız).
        result = (
            _call_groq(prompt, persona_key=persona_key, regime=regime_for_prompt)
            if _try_consume_groq_budget() else None
        )
        if result is None:
            result = _call_claude(prompt, persona_key=persona_key, regime=regime_for_prompt)

    if result is None:
        # Son çare: 2 saatlik stale cache varsa onu kullan
        # (Groq günlük token limiti dolduğunda kullanıcı boş ekran görmesin)
        stale = _get_stale()
        if stale is not None:
            import dataclasses
            return dataclasses.replace(
                stale,
                confidence_note=stale.confidence_note + " (stale — Groq token limiti)",
            )
        return AIAnalystReport(
            generated_at=now_iso, model="(failed)", cached=False,
            narrative="", key_signals=[],
            verdict="Her iki sağlayıcı da başarısız (Groq + Claude).",
            confidence_note="",
            error="Both providers failed.",
        )

    raw, model_used = result

    # JSON ayıkla
    try:
        if not raw.strip().startswith("{"):
            s = raw.find("{"); e = raw.rfind("}") + 1
            if s >= 0 and e > s:
                raw = raw[s:e]
        data = json.loads(raw)
    except Exception as exc:
        return AIAnalystReport(
            generated_at=now_iso, model=model_used, cached=False,
            narrative="", key_signals=[],
            verdict="Rapor JSON ayrıştırılamadı.",
            confidence_note="",
            error=f"JSON parse error: {exc}",
        )

    report = AIAnalystReport(
        generated_at=now_iso, model=model_used, cached=False,
        narrative=data.get("narrative", ""),
        key_signals=data.get("key_signals", []),
        verdict=data.get("verdict", ""),
        confidence_note=data.get("confidence_note", ""),
        error=None,
    )

    # Günlüğe kaydet
    regime = macro.get("regime", "")
    try:
        save(
            decision=decision,
            regime=regime,
            verdict=report.verdict,
            key_signals=report.key_signals,
            assets=assets,
        )
    except Exception:  # noqa: BLE001
        pass  # Journal hatası raporu bloklamamalı

    _set_cache(report)
    return report


__all__ = [name for name in globals() if not name.startswith("_")]
