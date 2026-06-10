"""Rotation pattern tespiti — DOLAR_GÜCÜ/NAKİT uyum regresyon testleri.

Sınıf adı `NAKİT` → `DOLAR_GÜCÜ` olarak yeniden adlandırıldıktan sonra
pattern fonksiyonlarının doğru tetiklendiğini garanti eder. Daha önce
`_detect_rotation_pattern` hâlâ `NAKİT` aradığı için DEFENSIVE_RISK_ON
tamamen ölüydü.
"""
from __future__ import annotations

from app.providers.capital_rotation_provider import (
    AssetClassScore,
    _CLASS_MAIN_ASSET,
    _detect_rotation_pattern,
)

_ALL_CLASSES = ("ALTIN", "GÜMÜŞ", "TAHVİL", "BTC", "HİSSE", "DOLAR_GÜCÜ", "PETROL")


def _scores(directions: dict[str, str]) -> list[AssetClassScore]:
    """directions: {sınıf: 'GİRİŞ'|'ÇIKIŞ'}; verilmeyenler NÖTR."""
    out: list[AssetClassScore] = []
    for name in _ALL_CLASSES:
        d = directions.get(name, "NÖTR")
        score = 1.0 if d == "GİRİŞ" else -1.0 if d == "ÇIKIŞ" else 0.0
        out.append(AssetClassScore(name=name, score=score, momentum_30d=score * 5, direction=d))
    return out


def test_class_names_no_longer_use_nakit() -> None:
    assert "NAKİT" not in _CLASS_MAIN_ASSET
    assert "DOLAR_GÜCÜ" in _CLASS_MAIN_ASSET


def test_defensive_risk_on_fires_with_dolar_gucu() -> None:
    scores = _scores({
        "HİSSE": "GİRİŞ", "DOLAR_GÜCÜ": "GİRİŞ",
        "ALTIN": "ÇIKIŞ", "BTC": "ÇIKIŞ",
    })
    assert _detect_rotation_pattern(scores) == "DEFENSIVE_RISK_ON"


def test_pure_risk_on_with_dolar_gucu_exit() -> None:
    scores = _scores({
        "HİSSE": "GİRİŞ", "BTC": "GİRİŞ",
        "DOLAR_GÜCÜ": "ÇIKIŞ",
    })
    assert _detect_rotation_pattern(scores) == "PURE_RISK_ON"


def test_pure_risk_on_with_tahvil_exit() -> None:
    scores = _scores({
        "HİSSE": "GİRİŞ", "BTC": "GİRİŞ",
        "TAHVİL": "ÇIKIŞ",
    })
    assert _detect_rotation_pattern(scores) == "PURE_RISK_ON"


def test_flight_to_safety_altin_tahvil() -> None:
    scores = _scores({
        "ALTIN": "GİRİŞ", "TAHVİL": "GİRİŞ",
        "HİSSE": "ÇIKIŞ",
    })
    assert _detect_rotation_pattern(scores) == "FLIGHT_TO_SAFETY"


def test_flight_to_safety_altin_dolar_gucu() -> None:
    scores = _scores({
        "ALTIN": "GİRİŞ", "DOLAR_GÜCÜ": "GİRİŞ",
        "BTC": "ÇIKIŞ",
    })
    assert _detect_rotation_pattern(scores) == "FLIGHT_TO_SAFETY"
