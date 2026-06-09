"""CapitalRotationProvider için veri kalitesi sanity guard testleri."""
from __future__ import annotations

import pytest

from app.providers.capital_rotation_provider import (
    CorrelationPair,
    _check_correlation_quality,
    _check_return_quality,
    _CLASS_MAIN_ASSET,
    _FLOW_SIGNALS,
)


# ── identical_returns_across_assets ──────────────────────────────────────────


def test_identical_returns_detected_when_five_match() -> None:
    momenta = {
        "BTC": -6.71, "GLD": -6.71, "TLT": -6.71, "SPY": -6.71, "DXY": -6.71,
        "OIL": -2.1,
    }
    assert _check_return_quality(momenta) == "identical_returns_across_assets"


def test_diverse_returns_pass() -> None:
    momenta = {
        "BTC": -8.4, "GLD": +2.3, "TLT": +1.1, "SPY": -3.2, "DXY": +0.4,
        "OIL": -5.8, "XAG": +1.9,
    }
    assert _check_return_quality(momenta) is None


def test_returns_below_threshold_count_not_flagged() -> None:
    # 4 aynı (5'in altı) — fail etmemeli
    momenta = {
        "BTC": -6.71, "GLD": -6.71, "TLT": -6.71, "SPY": -6.71,
        "DXY": +1.5, "OIL": -2.3, "XAG": +0.8,
    }
    assert _check_return_quality(momenta) is None


# ── degenerate_correlation_matrix ────────────────────────────────────────────


def _corr(pair: str, c: float) -> CorrelationPair:
    return CorrelationPair(pair=pair, corr_30d=c, regime="GÜÇLÜ_POZİTİF", explanation="")


def test_degenerate_matrix_detected_when_most_are_extreme() -> None:
    corrs = [
        _corr("BTC/DXY", 1.0), _corr("BTC/GLD", 1.0), _corr("BTC/SPY", 1.0),
        _corr("GLD/TLT", 1.0), _corr("GLD/DXY", 1.0), _corr("HYG/SPY", 1.0),
        _corr("TLT/SPY", 0.5), _corr("OIL/DXY", -0.2),
    ]
    assert _check_correlation_quality(corrs) == "degenerate_correlation_matrix"


def test_healthy_correlation_matrix_passes() -> None:
    corrs = [
        _corr("BTC/DXY", -0.32), _corr("BTC/GLD", +0.45), _corr("BTC/SPY", +0.68),
        _corr("GLD/TLT", +0.21), _corr("GLD/DXY", -0.18), _corr("HYG/SPY", +0.72),
        _corr("TLT/SPY", -0.41), _corr("OIL/DXY", -0.28),
    ]
    assert _check_correlation_quality(corrs) is None


def test_too_few_correlations_skipped() -> None:
    corrs = [_corr("BTC/DXY", 1.0), _corr("BTC/GLD", 1.0)]
    assert _check_correlation_quality(corrs) is None


# ── DXY no longer in NAKİT bucket ────────────────────────────────────────────


def test_dxy_class_renamed_to_dolar_gucu() -> None:
    assert "DOLAR_GÜCÜ" in _CLASS_MAIN_ASSET
    assert _CLASS_MAIN_ASSET["DOLAR_GÜCÜ"] == "DXY"
    assert "NAKİT" not in _CLASS_MAIN_ASSET
    assert "NAKİT" not in _FLOW_SIGNALS
    assert "DOLAR_GÜCÜ" in _FLOW_SIGNALS


# ── Error result smoke ──────────────────────────────────────────────────────


def test_error_result_returns_invalid_state_with_known_synthesis() -> None:
    from app.providers.capital_rotation_provider import _error_result
    r = _error_result("identical_returns_across_assets")
    assert r.error == "identical_returns_across_assets"
    assert r.conviction == 0
    assert "güvenilir değil" in r.synthesis
    assert len(r.class_scores) == 0
    assert len(r.correlations) == 0


@pytest.mark.parametrize(
    "code",
    ["identical_returns_across_assets", "degenerate_correlation_matrix", "data_insufficient"],
)
def test_known_reason_codes_get_specific_synthesis(code: str) -> None:
    from app.providers.capital_rotation_provider import _ERROR_SYNTHESIS
    assert code in _ERROR_SYNTHESIS
    assert "durduruldu" in _ERROR_SYNTHESIS[code]
