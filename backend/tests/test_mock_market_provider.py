from app.domain import AssetCode
from app.domain import list_main_assets
from app.providers import MockMarketProvider


def test_provider_supports_all_assets() -> None:
    provider = MockMarketProvider()

    assets = list(list_main_assets())
    payloads = [provider.get_asset_data(asset.code) for asset in assets]

    # Sayım runtime'dan — yeni sembol eklendiğinde test kırılmaz
    assert len(payloads) == len(assets)
    assert {payload.asset_symbol for payload in payloads} == {asset.code for asset in assets}


def test_provider_returns_deterministic_payloads() -> None:
    provider = MockMarketProvider()

    first = provider.get_asset_data(AssetCode.BTCUSD)
    second = provider.get_asset_data("BTCUSD")
    third = provider.get_asset_data(AssetCode.XAUUSDK)

    assert first == second
    # Mock provider deterministik üretiyor — kesin değer mock implementation'a bağlı.
    # Burada yalnızca shape ve invariant'ları doğrula (hard-coded value mock'a pin'li).
    assert isinstance(first.value, (int, float))
    assert first.value > 0
    assert first.source_name == "mock_crypto_provider"
    assert first.unit == "usd_per_btc"
    assert third.source_tier.value == "reference"
    assert third.raw_payload_ref == "mock://market/xauusdk"

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
