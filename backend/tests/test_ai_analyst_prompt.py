"""AI Analyst prompt builder — conviction ölçeği regresyon testi.

Rotation conviction 0-100 ölçeğinde üretilir; prompt daha önce `/10` yazıyordu
(yanlış ölçek). Bu test `/100` yazıldığını sabitler.
"""
from __future__ import annotations

from app.providers.capital_rotation_provider import (
    AssetClassScore,
    CapitalRotation,
    KeyInsight,
)
from app.services.ai_analyst_service import _build_prompt


def _rotation(conviction: int = 70) -> CapitalRotation:
    return CapitalRotation(
        primary_flow="HİSSE",
        secondary_flow="BTC",
        conviction=conviction,
        class_scores=(
            AssetClassScore(name="HİSSE", score=1.2, momentum_30d=6.0, direction="GİRİŞ"),
            AssetClassScore(name="ALTIN", score=-0.8, momentum_30d=-4.0, direction="ÇIKIŞ"),
        ),
        key_insights=(KeyInsight(icon="🟢", text="Hisse öncü", importance=3),),
        synthesis="Hisse sermaye çekiyor.",
        ratios=(),
        correlations=(),
        rotation_context="",
        error=None,
    )


def test_conviction_scale_is_per_100() -> None:
    prompt = _build_prompt(
        macro={"regime": "RISK_ON", "confidence_pct": 65},
        appetite={"status": "STRONG"},
        assets=[],
        checklist=[],
        decision="AÇIL",
        verdict_text="risk-on",
        geo_news=(),
        rotation=_rotation(70),
    )
    assert "konv=70/100" in prompt
    # Eski hatalı ölçek (/10) geri gelmemeli
    assert "konv=70/10\n" not in prompt
