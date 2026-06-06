"""
E-YAY → Consensus adaptör.

E-YAY'ın mevcut katmanlarını (RegimeReport, CapitalRotation, News, Technical)
5-modül consensus skorlarına çevirir.

Modül haritası:
  touche      = TechnicalProvider — technical_score 0-100 (zaten doğru ölçek)
  fundamental = ConfirmationChecklist — met/total ratio (ratio_0_1)
  news        = NewsProvider sentiment ortalaması (signed_neg1_pos1)
  sentinel    = MacroLayer confidence_pct (zaten 0-100)
  quantum     = CapitalRotation conviction (zaten 0-100)
"""
from __future__ import annotations

from typing import Any


def _technical_score_for(asset_code: str, tech_insights: Any, tf: str | None = None) -> float | None:
    """TechnicalProvider'dan asset için technical_score (0-100).

    - tech_insights dict[asset_code] = TechnicalInsight  →  klasik (tek TF)
    - tech_insights dict[asset_code][tf] = TechnicalInsight  →  multi-TF
    - tf belirtilirse multi-TF dict'inden o TF'i seç
    """
    ti = None
    if isinstance(tech_insights, dict):
        node = tech_insights.get(asset_code)
        if isinstance(node, dict) and tf:
            ti = node.get(tf)
        else:
            ti = node
    else:
        ti = next((t for t in (tech_insights or []) if t.asset_code == asset_code), None)

    if ti is None:
        return None
    return float(getattr(ti, "technical_score", 50.0))


def _fundamental_ratio(report: Any) -> float | None:
    """ConfirmationChecklist met / total — ratio_0_1."""
    checklist = getattr(report, "confirmation_checklist", None) or []
    if not checklist:
        return None
    total = len(checklist)
    if total == 0:
        return None
    met = sum(1 for c in checklist if getattr(c, "met", False))
    return met / total  # 0.0 .. 1.0


def _news_sentiment_score(report: Any) -> float | None:
    """NewsProvider sentiment ortalaması — signed_neg1_pos1.
       BULLISH=+1, BEARISH=-1, NEUTRAL=0. Relevance ile ağırlıklı."""
    headlines = getattr(report, "news_headlines", None) or []
    if not headlines:
        return None

    weights = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.2}
    sentiment_values = {"BULLISH": 1.0, "BEARISH": -1.0, "NEUTRAL": 0.0}

    total_weight = 0.0
    weighted_sum = 0.0
    for h in headlines:
        w = weights.get(getattr(h, "relevance", "LOW"), 0.2)
        s = sentiment_values.get(getattr(h, "sentiment", "NEUTRAL"), 0.0)
        total_weight += w
        weighted_sum += w * s

    if total_weight <= 0:
        return None
    return weighted_sum / total_weight  # -1.0 .. +1.0


def _sentinel_macro_score(report: Any) -> float | None:
    """MacroLayer confidence_pct (0-100) + AppetiteLayer durumu ayarlama."""
    macro = getattr(report, "macro_layer", None)
    if macro is None:
        return None

    base = float(getattr(macro, "confidence_pct", 50))

    # AppetiteLayer ile hafif ayarlama:
    # STRONG → +10, MODERATE → 0, WEAK → -10, CRISIS → -20
    appetite = getattr(report, "appetite_layer", None)
    if appetite is not None:
        status = getattr(appetite, "status", "MODERATE")
        adj = {"STRONG": 10, "MODERATE": 0, "WEAK": -10, "CRISIS": -20}.get(status, 0)
        base = max(0.0, min(100.0, base + adj))

    return base


def _quantum_rotation_score(rotation: Any) -> float | None:
    """CapitalRotation conviction (0-100). Akış yönü ile yön ayarlaması."""
    if rotation is None or getattr(rotation, "error", None):
        return None

    conviction = float(getattr(rotation, "conviction", 0))  # 0-100

    # Akış yönü risk-on/risk-off ayarı:
    # primary_flow = "HİSSE" veya "BTC" → bullish katkı (+20)
    # primary_flow = "ALTIN" veya "TAHVİL" veya "NAKİT" → bearish (-20)
    primary = (getattr(rotation, "primary_flow", "") or "").upper()
    risk_on_flows  = {"HİSSE", "HISSE", "BTC", "PETROL", "GÜMÜŞ", "GUMUS", "BAKIR"}
    risk_off_flows = {"ALTIN", "TAHVİL", "TAHVIL", "NAKİT", "NAKIT"}

    if primary in risk_on_flows:
        return min(100.0, conviction + 20.0)
    if primary in risk_off_flows:
        return max(0.0, 50.0 - conviction)
    return conviction


def _chart_pattern_score(asset_code: str, timeframe: str | None = None) -> float | None:
    """Chart Pattern Provider'dan asset+TF için pattern_score (-100..+100).

    Provider cache'i 3 dk, yeni yfinance çağrısı tetiklemez genelde.
    Hata olursa None döner → consensus modül redistribute yapar, mevcut yapı bozulmaz.
    """
    try:
        from app.api.chart_patterns import list_chart_patterns
        all_data = list_chart_patterns()
        pair_data = (all_data.get("pairs") or {}).get(asset_code)
        if pair_data is None:
            return None
        # TF bazlı skor, yoksa consolidated
        tf_dict = pair_data.get("per_tf") or {}
        if timeframe and tf_dict.get(timeframe):
            score = tf_dict[timeframe].get("pattern_score")
            if score is not None:
                return float(score)
        # Fallback: consolidated
        cs = pair_data.get("consolidated_score")
        return float(cs) if cs is not None else None
    except Exception:
        return None


# ── Public API ───────────────────────────────────────────────────────────────

def build_module_scores(
    report: Any,
    rotation: Any | None = None,
    asset_code: str | None = None,
    mtf_insights: Any | None = None,
    timeframe: str | None = None,
) -> dict[str, Any]:
    """
    E-YAY mevcut verisinden consensus için module_scores dict üret.

    Çıktı format: consensus_engine.calculate_consensus_score'a doğrudan verilebilir.
    Eksik modüller skip edilir (None döner → consensus redistribute eder).

    Multi-TF kullanımı:
      • mtf_insights = MultiTimeframeTechnicalProvider().compute() → dict[asset][tf]
      • timeframe = "1h" | "4h" | "1d" → o TF'i seçer
      • Verilmezse report.tech_insights'tan (tek TF, 1d) çekilir.
    """
    scores: dict[str, Any] = {}
    asset_for_tech = asset_code or "BTCUSD"

    # touche — asset+TF spesifik. Multi-TF varsa o, yoksa report'tan.
    if mtf_insights is not None and timeframe:
        touche = _technical_score_for(asset_for_tech, mtf_insights, tf=timeframe)
    else:
        tech_insights = getattr(report, "tech_insights", None) or {}
        touche = _technical_score_for(asset_for_tech, tech_insights)

    if touche is not None:
        scores["touche"] = {"value": touche, "range": "pct_0_100"}

    # fundamental — ratio
    fund = _fundamental_ratio(report)
    if fund is not None:
        scores["fundamental"] = {"value": fund, "range": "ratio_0_1"}

    # news — signed
    news = _news_sentiment_score(report)
    if news is not None:
        scores["news"] = {"value": news, "range": "signed_neg1_pos1"}

    # sentinel — pct
    sentinel = _sentinel_macro_score(report)
    if sentinel is not None:
        scores["sentinel"] = {"value": sentinel, "range": "pct_0_100"}

    # quantum — pct (rotation'dan)
    quantum = _quantum_rotation_score(rotation)
    if quantum is not None:
        scores["quantum"] = {"value": quantum, "range": "pct_0_100"}

    # chart_pattern — signed_neg100_pos100 (mum + trend + S/R skoru)
    # Sadece traded pair'ler için (BTCUSD/XAUUSD/XAGUSD/BRENT). Diğerleri için None.
    pattern_score = _chart_pattern_score(asset_for_tech, timeframe=timeframe)
    if pattern_score is not None:
        scores["chart_pattern"] = {"value": pattern_score, "range": "signed_neg100_pos100"}

    return scores


def get_regime_for_consensus(report: Any) -> str:
    """Report'tan ham rejim kodunu çıkar."""
    macro = getattr(report, "macro_layer", None)
    if macro is None:
        return "TRANSITIONING"
    return getattr(macro, "regime", "TRANSITIONING") or "TRANSITIONING"


__all__ = ["build_module_scores", "get_regime_for_consensus"]
