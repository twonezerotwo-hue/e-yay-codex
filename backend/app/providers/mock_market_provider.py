from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain import AssetCategory
from app.domain import AssetCode
from app.domain import SourceTier
from app.domain import get_asset_definition
from app.providers.base import MarketProvider
from app.providers.base import MarketProviderPayload


BASE_OBSERVED_AT = datetime(2026, 6, 6, 9, 0, 0, tzinfo=UTC)

# Haziran 2026 piyasa fiyatları (yfinance + CoinGecko + FRED)
MOCK_ASSET_VALUES: dict[AssetCode, float] = {
    AssetCode.BTCUSD:            60_915.0,   # BTC-USD
    AssetCode.BRENT:                 93.09,  # BZ=F
    AssetCode.XAUUSD:             4_337.1,   # GC=F
    AssetCode.XAGUSD:                68.94,  # SI=F
    AssetCode.DXY:                  100.07,  # DX-Y.NYB
    AssetCode.HYG:                   79.43,  # HYG ETF
    AssetCode.JNK:                   95.73,  # JNK ETF
    AssetCode.NASDAQ:            25_709.0,   # ^IXIC
    AssetCode.QQQ:                  705.06,  # QQQ ETF
    AssetCode.SP500:              7_383.7,   # ^GSPC
    AssetCode.BTC_DOMINANCE:         56.15,  # CoinGecko BTC.D %
    AssetCode.USDT_DOMINANCE:         8.59,  # CoinGecko USDT.D %
    AssetCode.TOTAL:              2_177.0,   # CoinGecko global market cap (B$)
    AssetCode.TOTAL2:               955.0,   # CoinGecko ex-BTC (B$)
    AssetCode.US02Y:                  3.63,  # ^IRX proxy
    AssetCode.US10Y:                  4.54,  # ^TNX
    AssetCode.US20Y:                  5.00,  # ^TYX (30Y proxy)
    AssetCode.USCPI:                  2.4,   # yoy%
    AssetCode.USPPI:                  2.1,   # yoy%
    AssetCode.M2SL:              21_500.0,   # B$
    AssetCode.FXI:                   34.75,  # FXI ETF
    AssetCode.SHANGHAI_COMPOSITE: 4_027.7,  # 000001.SS
    AssetCode.XCUUSD:            13_805.0,   # HG=F $6.26/lb × 2204.62
    AssetCode.XAUXAG:                62.9,   # 4337 / 68.94
    AssetCode.BTCXAUK:               14.0,   # 60915 / 4337
    AssetCode.XAUUSDK:                2.17,  # 4337 / 2000
    AssetCode.XAGUSDK:                2.76,  # 68.94 / 25
    # Göstergeler
    AssetCode.VIX:                   21.5,   # ^VIX
    AssetCode.REAL_YIELD:             2.3,   # DFII10 (TIPS 10Y)
    AssetCode.HY_SPREAD:              3.5,   # ICE BofA HY OAS
    AssetCode.ETHUSD:             1_567.0,   # ETH-USD
    AssetCode.IWM:                  281.6,   # IWM ETF
    AssetCode.LQD:                  108.2,   # LQD ETF
    AssetCode.SMH:                  569.7,   # SMH ETF
    AssetCode.XLF:                   52.3,   # XLF ETF
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
    AssetCategory.VOLATILITY:      "mock_volatility_provider",
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
    AssetCategory.VOLATILITY:      SourceTier.PRIMARY,
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
