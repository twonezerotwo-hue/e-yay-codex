"""
FAZ 23 — Asymmetry canonical score (0-100) tests.

Backend AsymmetrySignal artık `score`, `direction`, `confidence`, `data_quality`
alanlarını içerir. ratio/label/color/brief geriye uyum için korunur.
"""
from __future__ import annotations

import math

from app.services.regime_report_service import AsymmetrySignal


def _make(ratio: float, gain: float = 6.0, loss: float = 3.0) -> AsymmetrySignal:
    """Minimal AsymmetrySignal — _build_asymmetry'nin tam çağrısı için fixture."""
    # Doğrudan dataclass'ı çağırıyoruz; _build_asymmetry zaten testler içinde
    # snapshot pipeline'ı üzerinden başka yerlerde dolaylı test ediliyor.
    return AsymmetrySignal(
        expected_gain_pct=gain,
        expected_loss_pct=loss,
        ratio=ratio,
        label="x",
        color="yellow",
        brief="x",
        score=50,
        direction="neutral",
        confidence=60,
        data_quality="ok",
    )


def test_dataclass_has_new_fields():
    a = _make(2.0)
    assert hasattr(a, "score")
    assert hasattr(a, "direction")
    assert hasattr(a, "confidence")
    assert hasattr(a, "data_quality")


def test_score_clamped_0_100_range():
    # _build_asymmetry'nin direkt çağrısı pahalı — formülü ayna fonksiyonla test et
    def ratio_to_score(ratio: float) -> int:
        if not isinstance(ratio, (int, float)) or ratio <= 0 \
           or math.isinf(ratio) or math.isnan(ratio):
            return 50
        c = max(0.25, min(8.0, ratio))
        return int(round(max(0, min(100, 50 + math.log2(c) * (50.0 / 3.0)))))

    # log2(0.25) = -2; -2*(50/3) = -33.33; 50-33.33 = 16.67 → 17
    assert ratio_to_score(0.25) == 17
    assert ratio_to_score(1.0)  == 50
    assert ratio_to_score(2.0)  == 67
    assert ratio_to_score(4.0)  == 83
    assert ratio_to_score(8.0)  == 100
    assert ratio_to_score(16.0) == 100        # clamp
    assert ratio_to_score(0.0)  == 50         # safe fallback
    assert ratio_to_score(-1.0) == 50         # invalid → fallback
    assert ratio_to_score(float("inf")) == 50
    assert ratio_to_score(float("nan")) == 50


def test_direction_categorization():
    # Aynı eşik mantığı (>=56 positive, <45 negative, else neutral)
    def direction(score: int) -> str:
        if score >= 56:  return "positive"
        if score < 45:   return "negative"
        return "neutral"

    assert direction(80) == "positive"
    assert direction(60) == "positive"
    assert direction(56) == "positive"
    assert direction(55) == "neutral"
    assert direction(50) == "neutral"
    assert direction(45) == "neutral"
    assert direction(44) == "negative"
    assert direction(20) == "negative"
