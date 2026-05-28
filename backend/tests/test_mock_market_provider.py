from app.domain import AssetCode
from app.domain import list_main_assets
from app.providers import MockMarketProvider


def test_provider_supports_all_assets() -> None:
    provider = MockMarketProvider()

    payloads = [provider.get_asset_data(asset.code) for asset in list_main_assets()]

    assert len(payloads) == 27
    assert {payload.asset_symbol for payload in payloads} == {asset.code for asset in list_main_assets()}


def test_provider_returns_deterministic_payloads() -> None:
    provider = MockMarketProvider()

    first = provider.get_asset_data(AssetCode.BTCUSD)
    second = provider.get_asset_data("BTCUSD")
    third = provider.get_asset_data(AssetCode.XAUUSDK)

    assert first == second
    assert first.value == 105000.5
    assert first.source_name == "mock_crypto_provider"
    assert first.unit == "usd_per_btc"
    assert third.source_tier.value == "reference"
    assert third.raw_payload_ref == "mock://market/xauusdk"

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
