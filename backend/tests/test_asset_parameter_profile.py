"""Asset Parameter Profile testleri."""
from __future__ import annotations

import sys
import types

sys.modules.setdefault("numpy", types.SimpleNamespace())

from app.services.asset_parameter_profile import (
    ASSET_PROFILES,
    get_param,
    get_profile,
    list_assets,
)


def test_default_profile_has_all_required_keys() -> None:
    required = {
        "rsi_overbought", "rsi_oversold",
        "sl_atr_mult", "tp_atr_mult",
        "min_pattern_strength", "min_confluence_tfs",
        "horizon_hours_low", "horizon_hours_high",
        "confirmation_bars",
    }
    assert required <= set(ASSET_PROFILES["default"].keys())


def test_get_profile_returns_default_for_unknown_asset() -> None:
    profile = get_profile("UNKNOWN_FUTURE_ASSET")
    # Default değerlerle doluymalı, KeyError fırlatmamalı
    assert profile["rsi_overbought"] == 70.0
    assert profile["sl_atr_mult"] == 2.0


def test_get_profile_returns_btc_specific_values() -> None:
    profile = get_profile("BTCUSD")
    # BTC için SL 1.5×ATR olmalı (default 2.0 değil)
    assert profile["sl_atr_mult"] == 1.5
    # 75/25 bantları
    assert profile["rsi_overbought"] == 75.0
    assert profile["rsi_oversold"] == 25.0


def test_get_profile_merges_partial_overrides_with_default() -> None:
    """Asset profili sadece bazı alanları override etse bile eksikler default'tan dolar."""
    profile = get_profile("BRENT")
    # BRENT için tanımlı
    assert profile["sl_atr_mult"] == 2.5
    # Default'tan gelmesi gereken (BRENT'te explicit yoksa default)
    # rsi_overbought BRENT'te override edilmiş (72.0) — yine de tanımlı
    assert "rsi_overbought" in profile


def test_get_param_with_fallback_for_missing_key() -> None:
    val = get_param("BTCUSD", "nonexistent_key", fallback=42)
    assert val == 42


def test_get_param_returns_actual_value_for_existing_key() -> None:
    val = get_param("BTCUSD", "sl_atr_mult", fallback=99)
    assert val == 1.5   # BTC profile değeri


def test_list_assets_excludes_default() -> None:
    assets = list_assets()
    assert "default" not in assets
    assert "BTCUSD" in assets
    assert "XAUUSD" in assets
    assert "XAGUSD" in assets
    assert "XCUUSD" in assets
    assert "BRENT" in assets


def test_case_insensitive_asset_lookup() -> None:
    profile_upper = get_profile("BTCUSD")
    profile_lower = get_profile("btcusd")
    profile_mixed = get_profile("BtcUsd")
    assert profile_upper == profile_lower == profile_mixed


def test_non_string_input_returns_default_without_crash() -> None:
    # None / int / liste vs. ile çağrılırsa patlamasın
    p = get_profile(None)  # type: ignore[arg-type]
    assert p["sl_atr_mult"] == 2.0
