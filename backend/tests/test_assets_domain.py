from app.domain import AssetCategory
from app.domain import AssetCode
from app.domain import get_asset_definition
from app.domain import list_main_assets


EXPECTED_ASSET_SYMBOLS = (
    "BTCUSD",
    "BRENT",
    "XAUUSD",
    "XAGUSD",
    "DXY",
    "HYG",
    "JNK",
    "NASDAQ",
    "QQQ",
    "SP500",
    "BTC.D",
    "USDT.D",
    "TOTAL",
    "TOTAL2",
    "US02Y",
    "US10Y",
    "US20Y",
    "USCPI",
    "USPPI",
    "M2SL",
    "FXI",
    "SHANGHAI_COMPOSITE",
    "XCUUSD",
    "XAUXAG",
    "BTCXAUK",
    "XAUUSDK",
    "XAGUSDK",
)


def test_asset_enum_is_complete() -> None:
    assert tuple(asset.code.value for asset in list_main_assets()) == EXPECTED_ASSET_SYMBOLS


def test_every_asset_has_required_metadata() -> None:
    for asset_code in AssetCode:
        asset = get_asset_definition(asset_code)

        assert asset.symbol == asset_code.value
        assert asset.canonical_name
        assert isinstance(asset.category, AssetCategory)
        assert asset.unit
        assert isinstance(asset.required_for_core_report, bool)


def test_core_report_required_flags_match_expected_asset_subset() -> None:
    required_assets = {
        asset.code.value
        for asset in list_main_assets()
        if asset.required_for_core_report
    }
    optional_assets = {
        asset.code.value
        for asset in list_main_assets()
        if not asset.required_for_core_report
    }

    assert required_assets == set(EXPECTED_ASSET_SYMBOLS) - {
        "BTCXAUK",
        "XAUUSDK",
        "XAGUSDK",
    }
    assert optional_assets == {"BTCXAUK", "XAUUSDK", "XAGUSDK"}

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
