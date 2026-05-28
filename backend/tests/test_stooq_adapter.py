"""
Unit tests for StooqDailyProvider.
All tests use local fixture CSV strings — no network calls are made.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain import AssetCode, SourceTier
from app.providers.stooq_adapter import StooqDailyProvider

_SAMPLE_CSV = """\
Date,Open,High,Low,Close,Volume
2026-05-26,480.10,485.30,479.00,483.25,54312000
2026-05-27,483.50,488.00,482.00,486.75,61234000
"""

_SINGLE_ROW_CSV = """\
Date,Open,High,Low,Close,Volume
2026-05-27,483.50,488.00,482.00,486.75,61234000
"""


def _fixture_provider(fixture_csv: str) -> StooqDailyProvider:
    return StooqDailyProvider(fetch_fn=lambda _url: fixture_csv)


# ---------------------------------------------------------------------------
# supported_assets
# ---------------------------------------------------------------------------


def test_stooq_adapter_supported_assets_includes_etfs():
    supported = StooqDailyProvider.supported_assets()
    assert AssetCode.QQQ in supported
    assert AssetCode.HYG in supported
    assert AssetCode.JNK in supported
    assert AssetCode.FXI in supported


def test_stooq_adapter_supported_assets_excludes_unsupported():
    supported = StooqDailyProvider.supported_assets()
    assert AssetCode.BTCUSD not in supported
    assert AssetCode.BRENT not in supported
    assert AssetCode.XAUUSD not in supported


# ---------------------------------------------------------------------------
# get_asset_data — happy path
# ---------------------------------------------------------------------------


def test_stooq_adapter_parses_value_and_unit():
    provider = _fixture_provider(_SINGLE_ROW_CSV)
    payload = provider.get_asset_data(AssetCode.QQQ)

    assert payload.asset_symbol == AssetCode.QQQ
    assert payload.value == pytest.approx(486.75)
    assert payload.unit == "usd_per_share"


def test_stooq_adapter_parses_observed_at():
    provider = _fixture_provider(_SINGLE_ROW_CSV)
    payload = provider.get_asset_data(AssetCode.QQQ)

    assert payload.observed_at == datetime(2026, 5, 27, tzinfo=UTC)
    assert payload.available_at == datetime(2026, 5, 27, tzinfo=UTC)


def test_stooq_adapter_uses_last_row_of_csv():
    provider = _fixture_provider(_SAMPLE_CSV)
    payload = provider.get_asset_data(AssetCode.QQQ)

    assert payload.value == pytest.approx(486.75)
    assert payload.observed_at == datetime(2026, 5, 27, tzinfo=UTC)


def test_stooq_adapter_source_attribution():
    provider = _fixture_provider(_SINGLE_ROW_CSV)
    payload = provider.get_asset_data(AssetCode.JNK)

    assert payload.source_name == "stooq_daily_csv"
    assert payload.source_tier == SourceTier.SECONDARY
    assert payload.raw_payload_ref == "stooq://daily/jnk.us"
    assert payload.fallback_used is False


def test_stooq_adapter_stored_at_is_current_utc():
    before = datetime.now(UTC)
    payload = _fixture_provider(_SINGLE_ROW_CSV).get_asset_data(AssetCode.HYG)
    after = datetime.now(UTC)

    assert before <= payload.stored_at <= after


def test_stooq_adapter_returns_correct_unit_per_asset():
    for asset_code in (AssetCode.QQQ, AssetCode.HYG, AssetCode.JNK, AssetCode.FXI):
        payload = _fixture_provider(_SINGLE_ROW_CSV).get_asset_data(asset_code)
        assert payload.unit == "usd_per_share", f"Wrong unit for {asset_code}"


# ---------------------------------------------------------------------------
# get_asset_data — error cases
# ---------------------------------------------------------------------------


def test_stooq_adapter_raises_on_unsupported_asset_code():
    provider = _fixture_provider(_SINGLE_ROW_CSV)
    with pytest.raises(ValueError, match="does not support asset: BTCUSD"):
        provider.get_asset_data(AssetCode.BTCUSD)


def test_stooq_adapter_raises_on_unsupported_asset_string():
    provider = _fixture_provider(_SINGLE_ROW_CSV)
    with pytest.raises(ValueError):
        provider.get_asset_data("BRENT")


def test_stooq_adapter_raises_on_empty_csv():
    provider = _fixture_provider("")
    with pytest.raises(ValueError, match="empty or unrecognised"):
        provider.get_asset_data(AssetCode.QQQ)


def test_stooq_adapter_raises_on_header_only_csv():
    header_only = "Date,Open,High,Low,Close,Volume\n"
    provider = _fixture_provider(header_only)
    with pytest.raises(ValueError, match="empty or unrecognised"):
        provider.get_asset_data(AssetCode.QQQ)


def test_stooq_adapter_raises_on_missing_close_column():
    bad_csv = "Date,Open,High,Low,Volume\n2026-05-27,483.50,488.00,482.00,61234000\n"
    provider = _fixture_provider(bad_csv)
    with pytest.raises(ValueError, match="missing expected CSV column"):
        provider.get_asset_data(AssetCode.QQQ)


def test_stooq_adapter_raises_on_non_numeric_close():
    bad_csv = "Date,Open,High,Low,Close,Volume\n2026-05-27,483.50,488.00,482.00,N/A,61234000\n"
    provider = _fixture_provider(bad_csv)
    with pytest.raises(ValueError, match="non-numeric Close"):
        provider.get_asset_data(AssetCode.QQQ)


def test_stooq_adapter_raises_on_blank_close():
    bad_csv = "Date,Open,High,Low,Close,Volume\n2026-05-27,483.50,488.00,482.00,,61234000\n"
    provider = _fixture_provider(bad_csv)
    with pytest.raises(ValueError, match="blank Date or Close"):
        provider.get_asset_data(AssetCode.QQQ)


# ---------------------------------------------------------------------------
# source_url_for
# ---------------------------------------------------------------------------


def test_stooq_adapter_source_url_contains_stooq_symbol():
    assert "qqq.us" in StooqDailyProvider.source_url_for(AssetCode.QQQ)
    assert "hyg.us" in StooqDailyProvider.source_url_for(AssetCode.HYG)
    assert "jnk.us" in StooqDailyProvider.source_url_for(AssetCode.JNK)
    assert "fxi.us" in StooqDailyProvider.source_url_for(AssetCode.FXI)


def test_stooq_adapter_source_url_contains_stooq_domain():
    url = StooqDailyProvider.source_url_for(AssetCode.QQQ)
    assert "stooq.com" in url


def test_stooq_adapter_source_url_raises_for_unsupported():
    with pytest.raises(ValueError):
        StooqDailyProvider.source_url_for(AssetCode.BTCUSD)


# ---------------------------------------------------------------------------
# No-network guarantee: fetch_fn is always the fixture lambda in tests above.
# The default _default_fetch (urllib) is never invoked by any test here.
# ---------------------------------------------------------------------------


def test_stooq_adapter_fixture_fetch_fn_never_calls_network(monkeypatch):
    import urllib.request as _urllib

    def _fail(_url, **_kwargs):
        raise AssertionError("Network call detected — tests must not touch the internet")

    monkeypatch.setattr(_urllib, "urlopen", _fail)
    payload = _fixture_provider(_SINGLE_ROW_CSV).get_asset_data(AssetCode.QQQ)
    assert payload.value == pytest.approx(486.75)


__all__ = [name for name in globals() if not name.startswith("_")]
