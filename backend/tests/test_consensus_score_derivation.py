"""Consensus skoru türetimi — AssetSignal.score yok bug'ı için doğru-ölçek fix.

_derive_consensus_score_from_assets, status dağılımından 0-100/50-merkezli skor
üretir. agent_confidence._consensus_strength bunu "50'den uzaklık = güç" olarak
okur. Kritik kabul kriteri: tek taraflı BLOCKING confidence'ı ŞİŞİRMEMELİ.
"""
from __future__ import annotations

from app.api.ai_report import _derive_consensus_score_from_assets
from app.services.agent_confidence import _consensus_strength


def _assets(**counts: int) -> list[dict]:
    out: list[dict] = []
    for status, n in counts.items():
        out.extend({"status": status} for _ in range(n))
    return out


def _strength(assets: list[dict]) -> float:
    score = _derive_consensus_score_from_assets(assets)
    return _consensus_strength(score)


# ── Skor None davranışı ──────────────────────────────────────────────────────

def test_empty_returns_none() -> None:
    assert _derive_consensus_score_from_assets([]) is None


def test_all_veri_yok_returns_none() -> None:
    assert _derive_consensus_score_from_assets(_assets(VERİ_YOK=8)) is None


# ── Kabul kriterleri ─────────────────────────────────────────────────────────

def test_majority_confirmed_high_consensus() -> None:
    s = _derive_consensus_score_from_assets(_assets(CONFIRMED=8, BLOCKING=2))
    assert s is not None and s >= 75          # makul yüksek
    assert _strength(_assets(CONFIRMED=8, BLOCKING=2)) >= 50


def test_all_confirmed_max_consensus() -> None:
    assert _derive_consensus_score_from_assets(_assets(CONFIRMED=10)) == 100.0


def test_mixed_confirmed_blocking_low_agreement() -> None:
    # 50/50 → 50'ye yakın → güç ~0 (düşük/uyarı)
    s = _derive_consensus_score_from_assets(_assets(CONFIRMED=5, BLOCKING=5))
    assert s is not None and abs(s - 50.0) < 5
    assert _strength(_assets(CONFIRMED=5, BLOCKING=5)) < 15


def test_blocking_heavy_does_not_inflate_confidence() -> None:
    # KRİTİK: tek taraflı BLOCKING confidence'ı yükseltmemeli → güç düşük kalmalı
    s = _derive_consensus_score_from_assets(_assets(BLOCKING=9, CONFIRMED=1))
    assert s is not None and s <= 55
    assert _strength(_assets(BLOCKING=10)) < 15


def test_pending_neutral_moderate() -> None:
    s_pending = _derive_consensus_score_from_assets(_assets(PENDING=10))
    s_neutral = _derive_consensus_score_from_assets(_assets(NEUTRAL=10))
    assert s_pending is not None and 60 <= s_pending <= 75   # orta
    assert s_neutral is not None and abs(s_neutral - 50.0) < 5  # nötr → düşük


def test_low_coverage_drags_score_down() -> None:
    # 1 CONFIRMED + 9 VERİ_YOK → kapsam düşük → skor 50'ye yakın (düşük güven)
    s = _derive_consensus_score_from_assets(_assets(CONFIRMED=1, VERİ_YOK=9))
    assert s is not None and s < 60
