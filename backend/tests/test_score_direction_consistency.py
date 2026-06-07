"""Skor-yön tutarlılık testleri.

Banner'da görünen "BULLISH +44.2" tarzı gösterimler iki ayrı skor sisteminin
karıştırılmasından doğan kafa karışıklığı yaratıyordu. Bu test dosyası iki
sistemin eşiklerini SABIT tutmak ve geriye dönük bir bug girmesini önlemek
için var.

1) Consensus engine: final_score 0..100 → bullish > 55, bearish < 45
2) Chart pattern  : consolidated_score −100..+100 → BULLISH ≥ +25, BEARISH ≤ −25
"""
from __future__ import annotations

from app.services.consensus_engine import get_direction


# ── 1) Consensus 0..100 ─────────────────────────────────────────────────────

def test_consensus_score_above_55_is_bullish() -> None:
    assert get_direction(55.1) == "bullish"
    assert get_direction(60.0) == "bullish"
    assert get_direction(100.0) == "bullish"


def test_consensus_score_below_45_is_bearish() -> None:
    assert get_direction(44.9) == "bearish"
    assert get_direction(30.0) == "bearish"
    assert get_direction(0.0) == "bearish"


def test_consensus_score_in_neutral_band_is_neutral() -> None:
    # 44.2 — banner bug'ının kaynağı olan değer
    assert get_direction(44.2) == "bearish"   # 45 altı → bearish, BULLISH değil
    assert get_direction(45.0) == "neutral"   # tam eşikte → neutral
    assert get_direction(50.0) == "neutral"
    assert get_direction(54.9) == "neutral"
    assert get_direction(55.0) == "neutral"   # tam eşikte → neutral


def test_consensus_threshold_constants_unchanged() -> None:
    """
    Eşikler değişmediği sürece consensus_weights.yaml ile aynı kalmalı.
    Birisi default eşikleri 50.0/50.0 vs. yaparsa fark eden bir guard.
    """
    import inspect
    src = inspect.getsource(get_direction)
    # Default değerlerde 55 ve 45 görünmeli
    assert "55.0" in src and "45.0" in src


# ── 2) Chart pattern −100..+100 (build_all_patterns lokal eşikleri) ──────────

def test_chart_pattern_bias_thresholds_are_distinct_from_consensus() -> None:
    """
    chart_patterns endpoint'i ±25 eşik kullanır. Consensus 55/45 eşiğiyle
    karıştırılmamalıdır.
    """
    from app.api import chart_patterns as cp_api
    src = inspect.getsource(cp_api._build_all_patterns)
    # Eşikler ±25 olmalı
    assert "25.0" in src
    # bias label sistemleri ayrı olmalı
    assert '"BULLISH"' in src and '"BEARISH"' in src


import inspect  # noqa: E402 — alttaki test fonksiyonu da kullanıyor
