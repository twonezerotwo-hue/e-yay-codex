"""Regression tests for the technical-insight sanity / drift guards.

Bug context: yfinance ThreadPoolExecutor occasionally returns the wrong asset's
DataFrame to a thread, so e.g. BTC ends up with XAG's bars. Without guards
this contaminated insight bleeds into asset cards, owner_actions,
flip_conditions, and (worst case) paper-trading decisions.

Two guards now exist:
    1. _is_insight_sane  → asset-specific min/max price bounds inside the
       technical providers.
    2. _validate_tech_map_against_snapshots → cross-checks each insight's
       current_price against the live market snapshot value (5% tolerance).
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain import AssetCode
from app.domain.market_snapshot import MarketSnapshot, SourceTier
from app.providers.technical_provider import (
    DynamicLevels,
    TechnicalInsight,
    _is_insight_sane,
)
from app.services.regime_report_service import _validate_tech_map_against_snapshots


# ── helpers ──────────────────────────────────────────────────────────────────


_UNITS: dict[AssetCode, str] = {
    AssetCode.BTCUSD: "usd_per_btc",
    AssetCode.XAUUSD: "usd_per_ounce",
    AssetCode.XAGUSD: "usd_per_ounce",
    AssetCode.BRENT:  "usd_per_barrel",
    AssetCode.XCUUSD: "usd_per_pound",
    AssetCode.DXY:    "index_points",
    AssetCode.VIX:    "index_points",
    AssetCode.HYG:    "usd_per_share",
}


# Asset bound içine düşen varsayılan S/R değerleri (asset-aware)
_DEFAULT_SR: dict[str, tuple[float, float]] = {
    "BTCUSD": (55_000.0, 75_000.0),
    "XAUUSD":  (4_100.0,  4_880.0),
    "XAGUSD":     (61.0,     89.0),
    "BRENT":      (85.0,    102.0),
    "XCUUSD": (12_000.0, 16_000.0),
    "DXY":       (95.0,    105.0),
    "VIX":       (15.0,     30.0),
    "HYG":       (75.0,     85.0),
}


def _mk_insight(code: str, current: float, support: float | None = None, resistance: float | None = None) -> TechnicalInsight:
    if support is None or resistance is None:
        s, r = _DEFAULT_SR.get(code, (50.0, 100.0))
        support, resistance = s, r
    return TechnicalInsight(
        asset_code=code,
        timeframe="1d",
        current_price=current,
        structure="NEUTRAL",
        levels=DynamicLevels(
            support=support, resistance=resistance,
            atr=1.0,
            stop_loss=support - 0.5, take_profit=resistance + 0.5,
            atr_pct=1.0,
        ),
        rsi_14=50.0, macd_signal="NEUTRAL", volume_ratio=1.0,
        structure_score=10, momentum_score=10, zone_score=10, volume_score=10,
        technical_score=40,
    )


def _mk_snap(code: AssetCode, value: float) -> MarketSnapshot:
    now = datetime.now(UTC)
    return MarketSnapshot(
        asset_symbol=code, value=value, unit=_UNITS[code],
        source_name="t", source_tier=SourceTier.PRIMARY,
        observed_at=now, available_at=now, stored_at=now,
    )


# ── _is_insight_sane: per-asset bounds ───────────────────────────────────────


@pytest.mark.parametrize(
    "code, current, support, resistance",
    [
        ("BTCUSD", 62_700.0, 59_000.0, 75_000.0),
        ("XAUUSD",  4_350.0,  4_100.0,  4_880.0),
        ("XAGUSD",     68.5,     61.0,     89.0),
        ("BRENT",      92.5,     85.0,    102.0),
        ("XCUUSD", 14_000.0, 12_000.0, 16_000.0),
        ("DXY",        99.8,     95.0,    105.0),
    ],
)
def test_sanity_accepts_realistic_values(code: str, current: float, support: float, resistance: float) -> None:
    assert _is_insight_sane(code, current, support, resistance) is True


@pytest.mark.parametrize(
    "code, current, support, resistance",
    [
        # BTC with XAG-scale values (yfinance contamination)
        ("BTCUSD", 68.5, 61.0, 89.0),
        # XAU with XAG-scale values
        ("XAUUSD", 68.5, 61.0, 89.0),
        # QQQ with XAU-scale values
        ("QQQ", 4_356.0, 4_100.0, 4_880.0),
        # VIX with XAU-scale values
        ("VIX", 4_356.0, 4_100.0, 4_880.0),
        # BTC at sub-thousand range (the "BTC $86 desteği" bug)
        ("BTCUSD", 86.0, 83.0, 100.0),
        # XCU at lb scale when ton bound expected
        ("XCUUSD", 4.5, 3.8, 5.2),
        # XCU absurd scale ($9M/ton)
        ("XCUUSD", 9_040_718.0, 9_000_000.0, 10_000_000.0),
    ],
)
def test_sanity_rejects_contaminated_values(code: str, current: float, support: float, resistance: float) -> None:
    assert _is_insight_sane(code, current, support, resistance) is False


# ── _validate_tech_map_against_snapshots: drift cross-check ──────────────────


def test_drift_filter_drops_contaminated_insights() -> None:
    """BTC/BRENT/DXY/VIX have wrong values; the filter should drop only them."""
    tech_map = {
        "BTCUSD": _mk_insight("BTCUSD",    68.5),     # XAG leaked → drift huge
        "XAUUSD": _mk_insight("XAUUSD", 4_356.0),     # ok
        "XAGUSD": _mk_insight("XAGUSD",    68.5),     # ok
        "BRENT":  _mk_insight("BRENT",     68.5),     # XAG leaked
        "DXY":    _mk_insight("DXY",       68.5),     # XAG leaked
        "VIX":    _mk_insight("VIX",    4_356.0),     # XAU leaked
        "HYG":    _mk_insight("HYG",       79.5),     # ok
    }

    snap_map = {
        AssetCode.BTCUSD: _mk_snap(AssetCode.BTCUSD, 62_700.0),
        AssetCode.XAUUSD: _mk_snap(AssetCode.XAUUSD,  4_356.0),
        AssetCode.XAGUSD: _mk_snap(AssetCode.XAGUSD,     68.58),
        AssetCode.BRENT:  _mk_snap(AssetCode.BRENT,      92.5),
        AssetCode.DXY:    _mk_snap(AssetCode.DXY,        99.8),
        AssetCode.VIX:    _mk_snap(AssetCode.VIX,        18.0),
        AssetCode.HYG:    _mk_snap(AssetCode.HYG,        79.5),
    }

    validated = _validate_tech_map_against_snapshots(tech_map, snap_map)
    assert set(validated.keys()) == {"XAUUSD", "XAGUSD", "HYG"}


def test_drift_filter_keeps_clean_map_intact() -> None:
    """When all insights match snapshots, nothing should be dropped."""
    tech_map = {
        "BTCUSD": _mk_insight("BTCUSD", 62_700.0),
        "XAUUSD": _mk_insight("XAUUSD",  4_356.0),
        "XAGUSD": _mk_insight("XAGUSD",     68.5),
    }
    snap_map = {
        AssetCode.BTCUSD: _mk_snap(AssetCode.BTCUSD, 62_700.0),
        AssetCode.XAUUSD: _mk_snap(AssetCode.XAUUSD,  4_356.0),
        AssetCode.XAGUSD: _mk_snap(AssetCode.XAGUSD,     68.58),
    }
    assert set(_validate_tech_map_against_snapshots(tech_map, snap_map).keys()) == set(tech_map.keys())


def test_drift_filter_keeps_when_snapshot_missing() -> None:
    """Without a snapshot for cross-check, the insight is kept (no false drops)."""
    tech_map = {"BTCUSD": _mk_insight("BTCUSD", 62_700.0)}
    assert _validate_tech_map_against_snapshots(tech_map, {}) == tech_map


def test_drift_filter_skips_xcuusd_unit_conversion() -> None:
    """XCUUSD intentionally not in cross-check map because of lb→MT mult conversion."""
    tech_map = {"XCUUSD": _mk_insight("XCUUSD", 14_000.0)}  # mult-adjusted ton scale
    snap_map = {AssetCode.XCUUSD: _mk_snap(AssetCode.XCUUSD, 6.35)}  # raw lb
    # Even though raw drift is huge, the filter must not drop XCU.
    assert "XCUUSD" in _validate_tech_map_against_snapshots(tech_map, snap_map)
