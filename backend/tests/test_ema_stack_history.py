"""EMA200 yeterli geçmişle çalışıyor mu — regresyon testi.

Daha önce teknik provider 90 günlük (~64 işlem barı) veri çekiyordu; _ema_stack
ise ≥200 bar istiyordu → EMA hizalama skoru pratikte hep "unavailable" kalıyordu.
period 365d'ye çıkarıldı (~252 bar). Bu test 200-bar eşiğinin davranışını sabitler.
"""
from __future__ import annotations

import numpy as np

from app.providers.technical_provider import _ema_stack


def test_unavailable_below_200_bars() -> None:
    close = np.linspace(100, 150, 90)  # 90 bar — yetersiz
    label, score = _ema_stack(close)
    assert label == "unavailable"
    assert score == 0


def test_bullish_stack_with_enough_history() -> None:
    # 220 bar, istikrarlı yükseliş → EMA20 > EMA50 > EMA200
    close = np.linspace(100, 200, 220)
    label, score = _ema_stack(close)
    assert label == "bullish"
    assert score == 5


def test_bearish_stack_with_enough_history() -> None:
    # 220 bar, istikrarlı düşüş → EMA20 < EMA50 < EMA200
    close = np.linspace(200, 100, 220)
    label, score = _ema_stack(close)
    assert label == "bearish"
    assert score == 5


def test_not_unavailable_at_252_bars() -> None:
    # 365d ≈ 252 işlem barı; bu uzunlukta artık "unavailable" dönmemeli
    close = np.linspace(100, 120, 252)
    label, _ = _ema_stack(close)
    assert label != "unavailable"
