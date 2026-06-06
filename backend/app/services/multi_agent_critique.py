"""
Multi-Agent Critique — Sprint 3 / TradingAgents-inspired.

Agent cevabını üç bakış açısıyla denetler:
  • BULL  — boğa perspektifi (devil's advocate for bullish)
  • BEAR  — ayı perspektifi (devil's advocate for bearish)
  • RISK  — risk eleştirmeni (ne yanlış gidebilir?)

Sonuç: critique result + synthesis (aligned/divergent/abstain/risk_elevated).

V1: kural tabanlı, deterministik, LLM çağrısı YOK.
Veriye bakıp pattern arar; agent'ın iddiasını kanıtla karşılaştırır.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["BULL", "BEAR", "RISK"]
Synthesis = Literal["ALIGNED", "DIVERGENT", "ABSTAIN_RECOMMENDED", "RISK_ELEVATED"]


@dataclass
class PerspectiveView:
    role: Role
    points: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    strength: float = 0.0   # 0-100, bu görüşü destekleyen kanıt yoğunluğu

    def to_dict(self) -> dict[str, Any]:
        return {
            "role":      self.role,
            "points":    self.points,
            "citations": self.citations,
            "strength":  round(self.strength, 1),
        }


@dataclass
class CritiqueResult:
    bull: PerspectiveView
    bear: PerspectiveView
    risk: PerspectiveView
    synthesis: Synthesis
    challenges: list[str]                # orijinal cevaba spesifik itirazlar
    revised_confidence_pct: float        # critique sonrası önerilen confidence
    final_recommendation: str            # özet (safety footer'lı)
    agreement_with_original: bool        # critique orijinali destekliyor mu?

    def to_dict(self) -> dict[str, Any]:
        return {
            "bull":                    self.bull.to_dict(),
            "bear":                    self.bear.to_dict(),
            "risk":                    self.risk.to_dict(),
            "synthesis":               self.synthesis,
            "challenges":              self.challenges,
            "revised_confidence_pct":  round(self.revised_confidence_pct, 1),
            "final_recommendation":    self.final_recommendation,
            "agreement_with_original": self.agreement_with_original,
        }


# ── BULL advocate ─────────────────────────────────────────────────────────────

def _bull_perspective(
    *,
    consensus: dict | None,
    regime: dict | None,
    news: list | None,
    chart_patterns: dict | None,
) -> PerspectiveView:
    points: list[str] = []
    citations: list[str] = []
    score = 0.0

    # 1) Consensus skoru bullish tarafa kayıyor mu?
    if consensus:
        cs = consensus.get("final_score") or consensus.get("consensus_score")
        if isinstance(cs, (int, float)) and cs > 55:
            points.append(f"Consensus skoru {cs:.1f} bullish bandda (>55).")
            citations.append("consensus.final_score")
            score += 30.0

    # 2) Regime risk-on mu?
    if regime:
        rg = (regime.get("regime") or "").upper()
        if rg in ("RISK_ON", "LIQUIDITY_EXPANSION", "MEGA_BULL", "BULL"):
            points.append(f"Rejim '{rg}' risk-on — momentum hedefli stratejiler avantajlı.")
            citations.append("regime.regime")
            score += 25.0

    # 3) Chart pattern bullish?
    if isinstance(chart_patterns, dict):
        bull_pairs = [
            (k, v) for k, v in chart_patterns.items()
            if isinstance(v, dict) and v.get("bias") == "BULLISH"
        ]
        if bull_pairs:
            tags = ", ".join(p[0] for p in bull_pairs[:3])
            points.append(f"Chart pattern BULLISH: {tags}")
            citations.append("chart_patterns")
            score += 20.0

    # 4) Pozitif haber yoğunluğu
    if isinstance(news, list) and news:
        pos = sum(1 for h in news if str(getattr(h, "sentiment", None) or
                  (h.get("sentiment") if isinstance(h, dict) else "")).upper() == "BULLISH")
        if pos >= 3:
            points.append(f"Son haberlerde {pos} bullish başlık.")
            citations.append("news.sentiment")
            score += 15.0

    if not points:
        points.append("Bullish görüşü destekleyen güçlü kanıt yok.")

    return PerspectiveView(role="BULL", points=points, citations=citations,
                           strength=min(100.0, score))


# ── BEAR advocate ─────────────────────────────────────────────────────────────

def _bear_perspective(
    *,
    consensus: dict | None,
    regime: dict | None,
    news: list | None,
    chart_patterns: dict | None,
) -> PerspectiveView:
    points: list[str] = []
    citations: list[str] = []
    score = 0.0

    if consensus:
        cs = consensus.get("final_score") or consensus.get("consensus_score")
        if isinstance(cs, (int, float)) and cs < 45:
            points.append(f"Consensus skoru {cs:.1f} bearish bandda (<45).")
            citations.append("consensus.final_score")
            score += 30.0

    if regime:
        rg = (regime.get("regime") or "").upper()
        if rg in ("RISK_OFF", "DEFENSIVE", "CRISIS", "BEAR_2022", "BEAR_2022_AGGRESSIVE"):
            points.append(f"Rejim '{rg}' risk-off — savunmacı tutum gerekiyor.")
            citations.append("regime.regime")
            score += 25.0

    if isinstance(chart_patterns, dict):
        bear_pairs = [
            (k, v) for k, v in chart_patterns.items()
            if isinstance(v, dict) and v.get("bias") == "BEARISH"
        ]
        if bear_pairs:
            tags = ", ".join(p[0] for p in bear_pairs[:3])
            points.append(f"Chart pattern BEARISH: {tags}")
            citations.append("chart_patterns")
            score += 20.0

    if isinstance(news, list) and news:
        neg = sum(1 for h in news if str(getattr(h, "sentiment", None) or
                  (h.get("sentiment") if isinstance(h, dict) else "")).upper() == "BEARISH")
        if neg >= 3:
            points.append(f"Son haberlerde {neg} bearish başlık.")
            citations.append("news.sentiment")
            score += 15.0

    if not points:
        points.append("Bearish görüşü destekleyen güçlü kanıt yok.")

    return PerspectiveView(role="BEAR", points=points, citations=citations,
                           strength=min(100.0, score))


# ── RISK critic ───────────────────────────────────────────────────────────────

def _risk_perspective(
    *,
    consensus: dict | None,
    data_quality: dict | None,
    validation: dict | None,
    market_clock: dict | None,
    news: list | None,
) -> PerspectiveView:
    points: list[str] = []
    citations: list[str] = []
    score = 0.0

    # 1) Veri kalitesi düşük mü?
    if isinstance(data_quality, dict):
        dq = data_quality.get("quality_score")
        if isinstance(dq, (int, float)) and dq < 55:
            points.append(f"Veri kalitesi düşük: DQS={dq:.1f}")
            citations.append("data_quality.quality_score")
            score += 25.0
        if data_quality.get("decision") == "DEGRADED":
            points.append("Veri kalitesi DEGRADED — kararlar süpheli.")
            citations.append("data_quality.decision")
            score += 20.0

    # 2) Snapshot stale mi?
    if isinstance(validation, dict):
        age = validation.get("snapshot_age_seconds")
        if isinstance(age, (int, float)) and age > 600:
            points.append(f"Snapshot stale: {age:.0f}s.")
            citations.append("validation.snapshot_age_seconds")
            score += 20.0
        if validation.get("missing_fields"):
            mf = validation["missing_fields"]
            points.append(f"Eksik alanlar: {mf}")
            citations.append("validation.missing_fields")
            score += 15.0

    # 3) Consensus nötr bandda mı (45-55)?
    if consensus:
        cs = consensus.get("final_score") or consensus.get("consensus_score")
        if isinstance(cs, (int, float)) and 45 <= cs <= 55:
            points.append(f"Consensus {cs:.1f} nötr bandda — yön belirsiz.")
            citations.append("consensus.final_score")
            score += 15.0

    # 4) Piyasa kapalı (hafta sonu) gap riski?
    if isinstance(market_clock, dict) and market_clock.get("weekend"):
        points.append("Hafta sonu — XAUUSD/XAGUSD/BRENT için gap riski.")
        citations.append("market_clock.weekend")
        score += 15.0

    # 5) Jeopolitik haber yoğunluğu son 24 saatte?
    if isinstance(news, list):
        geo = sum(1 for h in news if str(getattr(h, "category", None) or
                   (h.get("category") if isinstance(h, dict) else "")).upper() in
                   ("GEOPOLITICAL", "GEO", "POLITICS"))
        if geo >= 2:
            points.append(f"Jeopolitik gündem yüksek ({geo} başlık) — volatilite riski.")
            citations.append("news.category")
            score += 10.0

    if not points:
        points.append("Belirgin yapısal risk işareti tespit edilmedi.")

    return PerspectiveView(role="RISK", points=points, citations=citations,
                           strength=min(100.0, score))


# ── Synthesis ────────────────────────────────────────────────────────────────

def _direction_from_consensus(consensus: dict | None) -> str | None:
    if not consensus:
        return None
    d = consensus.get("final_direction") or consensus.get("direction")
    if isinstance(d, str):
        return d.lower()
    cs = consensus.get("final_score") or consensus.get("consensus_score")
    if isinstance(cs, (int, float)):
        if cs > 55: return "bullish"
        if cs < 45: return "bearish"
        return "neutral"
    return None


def _synthesize(
    bull: PerspectiveView,
    bear: PerspectiveView,
    risk: PerspectiveView,
    *,
    original_direction: str | None,
    original_confidence_pct: float | None,
) -> tuple[Synthesis, list[str], float, bool]:
    challenges: list[str] = []

    # 1) Risk hakim mi?
    if risk.strength >= 60:
        challenges.append(f"Risk eleştirmeni güçlü (puan {risk.strength:.0f}) — kararı zayıflatır.")

    # 2) Bull ile bear çakışıyor mu?
    high_bull = bull.strength >= 50
    high_bear = bear.strength >= 50
    if high_bull and high_bear:
        synthesis: Synthesis = "ABSTAIN_RECOMMENDED"
        challenges.append("Hem bullish hem bearish kanıt güçlü — yön belirsiz.")
    elif risk.strength >= 60 and not high_bull and not high_bear:
        synthesis = "RISK_ELEVATED"
    elif high_bull and not high_bear:
        # Bull baskın
        if original_direction == "bearish":
            synthesis = "DIVERGENT"
            challenges.append("Orijinal bearish ama bullish kanıt baskın.")
        else:
            synthesis = "ALIGNED"
    elif high_bear and not high_bull:
        if original_direction == "bullish":
            synthesis = "DIVERGENT"
            challenges.append("Orijinal bullish ama bearish kanıt baskın.")
        else:
            synthesis = "ALIGNED"
    else:
        synthesis = "RISK_ELEVATED" if risk.strength >= 40 else "ALIGNED"

    # 3) Confidence revize
    base = float(original_confidence_pct) if original_confidence_pct is not None else 50.0
    penalty = 0.0
    if synthesis == "ABSTAIN_RECOMMENDED": penalty = 40.0
    elif synthesis == "DIVERGENT":         penalty = 25.0
    elif synthesis == "RISK_ELEVATED":     penalty = 15.0
    # Risk strength ek penalty
    penalty += min(20.0, risk.strength * 0.15)
    revised = max(0.0, min(100.0, base - penalty))

    agreement = synthesis in ("ALIGNED",)

    return synthesis, challenges, revised, agreement


# ── Public API ───────────────────────────────────────────────────────────────

def critique(
    *,
    agent_response: dict | None = None,
    consensus: dict | None = None,
    regime: dict | None = None,
    news: list | None = None,
    chart_patterns: dict | None = None,
    data_quality: dict | None = None,
    validation: dict | None = None,
    market_clock: dict | None = None,
) -> CritiqueResult:
    """3 perspektifle agent cevabını denetle."""
    bull = _bull_perspective(consensus=consensus, regime=regime, news=news,
                              chart_patterns=chart_patterns)
    bear = _bear_perspective(consensus=consensus, regime=regime, news=news,
                              chart_patterns=chart_patterns)
    risk_v = _risk_perspective(consensus=consensus, data_quality=data_quality,
                                validation=validation, market_clock=market_clock,
                                news=news)

    # Orijinal cevaptan yön ve confidence çek
    original_direction = _direction_from_consensus(consensus)
    original_confidence: float | None = None
    if isinstance(agent_response, dict):
        c = agent_response.get("confidence")
        if isinstance(c, dict):
            original_confidence = c.get("confidence_pct")

    synthesis, challenges, revised_conf, agreement = _synthesize(
        bull, bear, risk_v,
        original_direction=original_direction,
        original_confidence_pct=original_confidence,
    )

    # Final recommendation metni
    summary_lines: list[str] = []
    if synthesis == "ABSTAIN_RECOMMENDED":
        summary_lines.append("Zıt yönlü kanıtlar dengeli — agent yön bildirmemeli.")
    elif synthesis == "DIVERGENT":
        summary_lines.append("Critic, orijinal cevapla uyumsuz — gerekçeyi yeniden gözden geçir.")
    elif synthesis == "RISK_ELEVATED":
        summary_lines.append("Risk yüksek — pozisyon büyüklüğü düşürülmeli, stop'lar sıkı tutulmalı.")
    else:
        summary_lines.append("Critic orijinal değerlendirmeyi destekliyor.")
    summary_lines.append(f"Bull gücü: {bull.strength:.0f} · Bear: {bear.strength:.0f} · Risk: {risk_v.strength:.0f}")
    summary_lines.append(f"Önerilen confidence: %{revised_conf:.0f} (orijinal {original_confidence})")

    return CritiqueResult(
        bull=bull,
        bear=bear,
        risk=risk_v,
        synthesis=synthesis,
        challenges=challenges,
        revised_confidence_pct=revised_conf,
        final_recommendation=" • ".join(summary_lines),
        agreement_with_original=agreement,
    )


__all__ = [
    "PerspectiveView",
    "CritiqueResult",
    "Synthesis",
    "critique",
]
