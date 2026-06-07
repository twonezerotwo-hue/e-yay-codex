"""
Multi-Model Ensemble — Sprint 10 / Item 10 (puan 65).

Farklı persona'larla (ve mümkünse farklı modellerle) aynı veriden 2-3 ayrı
AI rapor üretip verdict'leri oyla. Anlaşma seviyesi (agreement_pct) ve
karşı argümanlar (divergences) ek bir güven katmanı verir.

Tasarım:
  • Default ensemble: [analyst, risk_officer, macro_strategist]
  • Her run paralel değil — token rate-limit'i koruyalım: sıralı, force_refresh=True
  • Verdict'leri yön (+1/-1/0) skoruna çevirip ortalama → final_direction
  • Disagreement varsa narrative'leri kısa özetle göster

Audit'e kaydedilir. PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.providers.geo_news_provider import GeoHeadline


@dataclass
class EnsembleVote:
    persona: str
    model: str
    verdict: str
    direction: int           # -1 bearish · 0 neutral · +1 bullish
    narrative_preview: str
    key_signals: list[str] = field(default_factory=list)
    confidence_note: str | None = None
    error: str | None = None


@dataclass
class EnsembleReport:
    generated_at: str
    final_direction: int                  # -1/0/+1
    final_label: str                      # bullish/bearish/neutral/conflict
    agreement_pct: float                  # 0..100 — kaçı aynı yönde
    votes: list[EnsembleVote] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)
    error: str | None = None


_DIRECTION_KEYWORDS = {
    +1: ("bullish", "yukarı", "yükseliş", "long", "risk-on", "alış"),
    -1: ("bearish", "aşağı", "düşüş", "short", "risk-off", "satış"),
}


def _verdict_to_direction(verdict: str | None) -> int:
    if not verdict:
        return 0
    v = verdict.lower()
    for d, words in _DIRECTION_KEYWORDS.items():
        if any(w in v for w in words):
            return d
    return 0


def _label_from_direction(d: int) -> str:
    return {+1: "bullish", -1: "bearish", 0: "neutral"}.get(d, "neutral")


def run_ensemble(
    *,
    macro: dict[str, Any],
    appetite: dict[str, Any],
    assets: list[dict[str, Any]],
    checklist: list[dict[str, Any]],
    decision: str,
    verdict: str,
    geo_news: tuple[GeoHeadline, ...],
    rotation: Any = None,
    personas: list[str] | None = None,
) -> EnsembleReport:
    """Ensemble pass — sırayla persona'lar koşturulur."""
    from app.services.ai_analyst_service import generate_ai_report
    personas = personas or ["analyst", "risk_officer", "macro_strategist"]

    votes: list[EnsembleVote] = []
    for pk in personas:
        try:
            report = generate_ai_report(
                macro=macro,
                appetite=appetite,
                assets=assets,
                checklist=checklist,
                decision=decision,
                verdict=verdict,
                geo_news=geo_news,
                rotation=rotation,
                force_refresh=True,        # Ensemble cache'i atlamalı
                persona_key=pk,
            )
            verdict_text = report.verdict or ""
            d = _verdict_to_direction(verdict_text)
            votes.append(EnsembleVote(
                persona=pk,
                model=report.model,
                verdict=verdict_text,
                direction=d,
                narrative_preview=(report.narrative or "")[:280],
                key_signals=report.key_signals or [],
                confidence_note=report.confidence_note,
                error=report.error,
            ))
        except Exception as exc:
            votes.append(EnsembleVote(
                persona=pk,
                model="?",
                verdict="",
                direction=0,
                narrative_preview="",
                error=str(exc)[:240],
            ))

    # Final yön: oy ortalaması
    valid = [v for v in votes if v.error is None]
    if not valid:
        return EnsembleReport(
            generated_at=datetime.now(UTC).isoformat(),
            final_direction=0,
            final_label="neutral",
            agreement_pct=0.0,
            votes=votes,
            error="all_personas_failed",
        )

    avg = sum(v.direction for v in valid) / len(valid)
    # Sıkı eşik: |avg| ≥ 0.5 ise yön belirgin, değilse "conflict"
    if avg >= 0.5:
        final_dir, final_label = +1, "bullish"
    elif avg <= -0.5:
        final_dir, final_label = -1, "bearish"
    elif any(v.direction != 0 for v in valid):
        final_dir, final_label = 0, "conflict"
    else:
        final_dir, final_label = 0, "neutral"

    # Agreement %: çoğunluk yön / toplam
    counts: dict[int, int] = {-1: 0, 0: 0, +1: 0}
    for v in valid:
        counts[v.direction] = counts.get(v.direction, 0) + 1
    majority = max(counts.values())
    agreement_pct = round(100.0 * majority / len(valid), 1)

    # Divergences: farklı yön kıyaslamaları
    divergences: list[str] = []
    if final_label == "conflict" or agreement_pct < 100.0:
        for v in valid:
            if v.direction != final_dir or final_label == "conflict":
                divergences.append(
                    f"{v.persona}({_label_from_direction(v.direction)}): "
                    f"{v.verdict[:140]}"
                )

    return EnsembleReport(
        generated_at=datetime.now(UTC).isoformat(),
        final_direction=final_dir,
        final_label=final_label,
        agreement_pct=agreement_pct,
        votes=votes,
        divergences=divergences[:5],
    )


def report_to_dict(report: EnsembleReport) -> dict[str, Any]:
    out = asdict(report)
    return out


__all__ = ["EnsembleVote", "EnsembleReport", "run_ensemble", "report_to_dict"]
