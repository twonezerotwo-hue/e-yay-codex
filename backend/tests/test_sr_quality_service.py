"""S/R quality service testleri."""
from __future__ import annotations

import sys

# Diğer test dosyaları numpy'i SimpleNamespace olarak stub'layabiliyor.
# Bu test gerçek numpy fonksiyonlarına (random, linspace) ihtiyaç duyar.
if "numpy" in sys.modules and not hasattr(sys.modules["numpy"], "random"):
    del sys.modules["numpy"]
import numpy as np  # noqa: E402

# sr_quality_service'i de yeniden import ettir (numpy referansı tazelensin)
for _mod in [m for m in list(sys.modules) if m.startswith("app.services.sr_quality_service")]:
    del sys.modules[_mod]

from app.services.sr_quality_service import evaluate_level, evaluate_pair  # noqa: E402


def _ohlcv_bouncing_off_support(level: float, n: int = 60) -> tuple[np.ndarray, ...]:
    """
    Destek seviyesinde 3 kez tepki gösteren OHLC üret.
    Bar 10, 25, 45 'te low seviyeye değiyor, sonra yukarı dönüyor.
    """
    rng = np.random.default_rng(42)
    base = level * 1.05
    closes = np.array([base + rng.normal(0, level * 0.005) for _ in range(n)])
    highs  = closes + level * 0.01
    lows   = closes - level * 0.01
    opens  = closes - level * 0.002

    # 3 touch noktası: low → level
    for i in (10, 25, 45):
        lows[i]   = level         # tam seviyeye değdi
        closes[i] = level * 1.012  # güçlü rebound
        opens[i]  = level * 1.005
        highs[i]  = closes[i] + level * 0.003

    return opens, highs, lows, closes


def test_support_with_three_touches_yields_strong_rating() -> None:
    level = 100.0
    o, h, l, c = _ohlcv_bouncing_off_support(level)
    q = evaluate_level(level, "support", o, h, l, c, atr=1.0, proximity_atr=0.5)
    assert q.touch_count >= 3
    assert q.body_violations == 0
    assert q.rating in ("MEDIUM", "STRONG")
    assert q.quality_score >= 45.0


def test_untested_level_returns_untested_rating() -> None:
    n = 60
    rng = np.random.default_rng(7)
    closes = 200.0 + rng.normal(0, 1.0, n)
    highs = closes + 0.5
    lows  = closes - 0.5
    opens = closes - 0.1
    q = evaluate_level(50.0, "support", opens, highs, lows, closes, atr=1.0)
    assert q.touch_count == 0
    assert q.rating == "UNTESTED"
    assert q.quality_score == 0.0


def test_broken_support_with_body_violations_lowers_score() -> None:
    """Bar close seviyenin altında → support kırıldı."""
    n = 60
    rng = np.random.default_rng(11)
    level = 100.0
    closes = np.array([level * 1.02 + rng.normal(0, 0.1) for _ in range(n)])
    highs = closes + 0.3
    lows  = closes - 0.3
    opens = closes - 0.05

    # Bar 10 → touch
    lows[10] = level; closes[10] = level * 1.01
    # Bar 30, 35 → BODY BREAK (close < level)
    lows[30] = level - 1.0; closes[30] = level - 0.8
    lows[35] = level - 1.5; closes[35] = level - 1.2

    q = evaluate_level(level, "support", opens, highs, lows, closes, atr=1.0)
    assert q.body_violations >= 2
    # Body violation penalty 16 → quality_score düşmüş olmalı
    assert q.quality_score < 60.0


def test_recent_touch_yields_higher_recency_score_than_old_touch() -> None:
    n = 60
    level = 100.0
    rng = np.random.default_rng(2)
    closes_recent = np.array([level * 1.02 + rng.normal(0, 0.05) for _ in range(n)])
    highs_recent = closes_recent + 0.3; lows_recent = closes_recent - 0.3
    opens_recent = closes_recent - 0.05
    # Touch yakın geçmişte: bar 55, 57, 58
    for i in (55, 57, 58):
        lows_recent[i] = level; closes_recent[i] = level * 1.015

    closes_old = closes_recent.copy(); highs_old = highs_recent.copy()
    lows_old = lows_recent.copy(); opens_old = opens_recent.copy()
    # Touch uzak geçmişte: bar 2, 4, 6 — son test 53 bar önce
    for i in (55, 57, 58):
        lows_old[i] = level * 1.02; closes_old[i] = level * 1.025
    for i in (2, 4, 6):
        lows_old[i] = level; closes_old[i] = level * 1.015

    q_recent = evaluate_level(level, "support", opens_recent, highs_recent, lows_recent, closes_recent, atr=1.0)
    q_old    = evaluate_level(level, "support", opens_old, highs_old, lows_old, closes_old, atr=1.0)

    assert q_recent.last_touch_bars_ago < q_old.last_touch_bars_ago
    assert q_recent.quality_score >= q_old.quality_score


def test_evaluate_pair_returns_both_sides() -> None:
    n = 60
    rng = np.random.default_rng(99)
    base = 100.0
    closes = base + rng.normal(0, 1.0, n)
    highs  = closes + 1.0
    lows   = closes - 1.0
    opens  = closes - 0.2

    result = evaluate_pair(90.0, 110.0, opens, highs, lows, closes, atr=1.0)
    assert "support" in result and "resistance" in result
    assert result["support"]["level"] == 90.0
    assert result["resistance"]["level"] == 110.0
    assert "rating" in result["support"]
    assert "quality_score" in result["resistance"]


def test_invalid_level_returns_untested_without_crash() -> None:
    n = 30
    closes = np.linspace(100, 105, n)
    highs  = closes + 0.5
    lows   = closes - 0.5
    opens  = closes - 0.1
    q = evaluate_level(0.0, "support", opens, highs, lows, closes)
    assert q.rating == "UNTESTED"
    assert q.quality_score == 0.0
