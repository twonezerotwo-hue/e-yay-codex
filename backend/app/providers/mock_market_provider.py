from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain import AssetCategory
from app.domain import AssetCode
from app.domain import SourceTier
from app.domain import get_asset_definition
from app.providers.base import MarketProvider
from app.providers.base import MarketProviderPayload


BASE_OBSERVED_AT = datetime(2026, 5, 19, 9, 0, 0, tzinfo=UTC)

MOCK_ASSET_VALUES: dict[AssetCode, float] = {
    AssetCode.BTCUSD: 105000.5,
    AssetCode.BRENT: 82.35,
    AssetCode.XAUUSD: 2418.4,
    AssetCode.XAGUSD: 31.2,
    AssetCode.DXY: 104.8,
    AssetCode.HYG: 77.4,
    AssetCode.JNK: 95.1,
    AssetCode.NASDAQ: 18640.0,
    AssetCode.QQQ: 492.7,
    AssetCode.SP500: 5285.5,
    AssetCode.BTC_DOMINANCE: 54.1,
    AssetCode.USDT_DOMINANCE: 6.2,
    AssetCode.TOTAL: 2680.0,
    AssetCode.TOTAL2: 1210.0,
    AssetCode.US02Y: 4.81,
    AssetCode.US10Y: 4.42,
    AssetCode.US20Y: 4.67,
    AssetCode.USCPI: 3.1,
    AssetCode.USPPI: 2.4,
    AssetCode.M2SL: 20950.0,
    AssetCode.FXI: 24.3,
    AssetCode.SHANGHAI_COMPOSITE: 3112.0,
    AssetCode.XCUUSD: 4.68,
    AssetCode.XAUXAG: 77.5,
    AssetCode.BTCXAUK: 43.4,
    AssetCode.XAUUSDK: 1.02,
    AssetCode.XAGUSDK: 0.97,
}

SOURCE_NAME_BY_CATEGORY: dict[AssetCategory, str] = {
    AssetCategory.CRYPTO: "mock_crypto_provider",
    AssetCategory.CRYPTO_STRUCTURE: "mock_crypto_structure_provider",
    AssetCategory.ENERGY: "mock_energy_provider",
    AssetCategory.PRECIOUS_METALS: "mock_metals_provider",
    AssetCategory.RELATIVE_RATIOS: "mock_ratio_provider",
    AssetCategory.CREDIT: "mock_credit_provider",
    AssetCategory.DOLLAR_FX: "mock_fx_provider",
    AssetCategory.EQUITIES_US: "mock_us_equity_provider",
    AssetCategory.EQUITIES_CHINA: "mock_china_equity_provider",
    AssetCategory.RATES: "mock_rates_provider",
    AssetCategory.INFLATION_LIQUIDITY: "mock_macro_provider",
    AssetCategory.INDUSTRIAL_METALS: "mock_industrial_metals_provider",
    AssetCategory.LOCAL_REFERENCE: "mock_reference_provider",
}

SOURCE_TIER_BY_CATEGORY: dict[AssetCategory, SourceTier] = {
    AssetCategory.CRYPTO: SourceTier.PRIMARY,
    AssetCategory.CRYPTO_STRUCTURE: SourceTier.PRIMARY,
    AssetCategory.ENERGY: SourceTier.PRIMARY,
    AssetCategory.PRECIOUS_METALS: SourceTier.PRIMARY,
    AssetCategory.RELATIVE_RATIOS: SourceTier.PRIMARY,
    AssetCategory.CREDIT: SourceTier.PRIMARY,
    AssetCategory.DOLLAR_FX: SourceTier.PRIMARY,
    AssetCategory.EQUITIES_US: SourceTier.PRIMARY,
    AssetCategory.EQUITIES_CHINA: SourceTier.SECONDARY,
    AssetCategory.RATES: SourceTier.SECONDARY,
    AssetCategory.INFLATION_LIQUIDITY: SourceTier.SECONDARY,
    AssetCategory.INDUSTRIAL_METALS: SourceTier.PRIMARY,
    AssetCategory.LOCAL_REFERENCE: SourceTier.REFERENCE,
}


class MockMarketProvider(MarketProvider):
    def get_asset_data(self, asset_symbol: AssetCode | str) -> MarketProviderPayload:
        asset_code = asset_symbol if isinstance(asset_symbol, AssetCode) else AssetCode(asset_symbol)
        asset_definition = get_asset_definition(asset_code)
        asset_index = list(AssetCode).index(asset_code)
        observed_at = BASE_OBSERVED_AT + timedelta(minutes=asset_index)
        available_at = observed_at + timedelta(minutes=1)
        stored_at = available_at + timedelta(minutes=1)

        return MarketProviderPayload(
            asset_symbol=asset_code,
            value=MOCK_ASSET_VALUES[asset_code],
            unit=asset_definition.unit,
            source_name=SOURCE_NAME_BY_CATEGORY[asset_definition.category],
            source_tier=SOURCE_TIER_BY_CATEGORY[asset_definition.category],
            observed_at=observed_at,
            available_at=available_at,
            stored_at=stored_at,
            fallback_used=False,
            raw_payload_ref=f"mock://market/{asset_code.value.lower()}",
        )

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
