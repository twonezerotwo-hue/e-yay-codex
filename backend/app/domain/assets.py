from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetCategory(str, Enum):
    CRYPTO = "crypto"
    CRYPTO_STRUCTURE = "crypto_structure"
    ENERGY = "energy"
    PRECIOUS_METALS = "precious_metals"
    RELATIVE_RATIOS = "relative_ratios"
    CREDIT = "credit"
    DOLLAR_FX = "dollar_fx"
    EQUITIES_US = "equities_us"
    EQUITIES_CHINA = "equities_china"
    RATES = "rates"
    INFLATION_LIQUIDITY = "inflation_liquidity"
    INDUSTRIAL_METALS = "industrial_metals"
    LOCAL_REFERENCE = "local_reference"
    VOLATILITY = "volatility"


class AssetCode(str, Enum):
    BTCUSD = "BTCUSD"
    BRENT = "BRENT"
    XAUUSD = "XAUUSD"
    XAGUSD = "XAGUSD"
    DXY = "DXY"
    HYG = "HYG"
    JNK = "JNK"
    NASDAQ = "NASDAQ"
    QQQ = "QQQ"
    SP500 = "SP500"
    BTC_DOMINANCE = "BTC.D"
    USDT_DOMINANCE = "USDT.D"
    TOTAL = "TOTAL"
    TOTAL2 = "TOTAL2"
    US02Y = "US02Y"
    US10Y = "US10Y"
    US20Y = "US20Y"
    USCPI = "USCPI"
    USPPI = "USPPI"
    M2SL = "M2SL"
    FXI = "FXI"
    SHANGHAI_COMPOSITE = "SHANGHAI_COMPOSITE"
    XCUUSD = "XCUUSD"
    XAUXAG = "XAUXAG"
    BTCXAUK = "BTCXAUK"
    XAUUSDK = "XAUUSDK"
    XAGUSDK = "XAGUSDK"
    # --- Yeni göstergeler ---
    VIX       = "VIX"
    REAL_YIELD= "REAL_YIELD"
    HY_SPREAD = "HY_SPREAD"
    ETHUSD    = "ETHUSD"
    IWM       = "IWM"
    LQD       = "LQD"
    SMH       = "SMH"
    XLF       = "XLF"


@dataclass(frozen=True)
class AssetDefinition:
    code: AssetCode
    symbol: str
    canonical_name: str
    category: AssetCategory
    unit: str
    required_for_core_report: bool
    requires_verified_data_for_live: bool = True

    @property
    def display_name(self) -> str:
        return self.canonical_name


def _asset(
    code: AssetCode,
    canonical_name: str,
    category: AssetCategory,
    unit: str,
    *,
    required_for_core_report: bool,
    requires_verified_data_for_live: bool = True,
) -> AssetDefinition:
    return AssetDefinition(
        code=code,
        symbol=code.value,
        canonical_name=canonical_name,
        category=category,
        unit=unit,
        required_for_core_report=required_for_core_report,
        requires_verified_data_for_live=requires_verified_data_for_live,
    )


ASSET_CATALOG: dict[AssetCode, AssetDefinition] = {
    AssetCode.BTCUSD: _asset(
        AssetCode.BTCUSD,
        "Bitcoin / US Dollar",
        AssetCategory.CRYPTO,
        "usd_per_btc",
        required_for_core_report=True,
    ),
    AssetCode.BRENT: _asset(
        AssetCode.BRENT,
        "Brent Crude Oil",
        AssetCategory.ENERGY,
        "usd_per_barrel",
        required_for_core_report=True,
    ),
    AssetCode.XAUUSD: _asset(
        AssetCode.XAUUSD,
        "Gold / US Dollar",
        AssetCategory.PRECIOUS_METALS,
        "usd_per_ounce",
        required_for_core_report=True,
    ),
    AssetCode.XAGUSD: _asset(
        AssetCode.XAGUSD,
        "Silver / US Dollar",
        AssetCategory.PRECIOUS_METALS,
        "usd_per_ounce",
        required_for_core_report=True,
    ),
    AssetCode.DXY: _asset(
        AssetCode.DXY,
        "US Dollar Index",
        AssetCategory.DOLLAR_FX,
        "index_points",
        required_for_core_report=True,
    ),
    AssetCode.HYG: _asset(
        AssetCode.HYG,
        "iShares iBoxx High Yield Corporate Bond ETF",
        AssetCategory.CREDIT,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.JNK: _asset(
        AssetCode.JNK,
        "SPDR Bloomberg High Yield Bond ETF",
        AssetCategory.CREDIT,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.NASDAQ: _asset(
        AssetCode.NASDAQ,
        "Nasdaq Composite",
        AssetCategory.EQUITIES_US,
        "index_points",
        required_for_core_report=True,
    ),
    AssetCode.QQQ: _asset(
        AssetCode.QQQ,
        "Invesco QQQ Trust",
        AssetCategory.EQUITIES_US,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.SP500: _asset(
        AssetCode.SP500,
        "S&P 500 Index",
        AssetCategory.EQUITIES_US,
        "index_points",
        required_for_core_report=True,
    ),
    AssetCode.BTC_DOMINANCE: _asset(
        AssetCode.BTC_DOMINANCE,
        "Bitcoin Dominance",
        AssetCategory.CRYPTO_STRUCTURE,
        "percent",
        required_for_core_report=True,
    ),
    AssetCode.USDT_DOMINANCE: _asset(
        AssetCode.USDT_DOMINANCE,
        "Tether Dominance",
        AssetCategory.CRYPTO_STRUCTURE,
        "percent",
        required_for_core_report=True,
    ),
    AssetCode.TOTAL: _asset(
        AssetCode.TOTAL,
        "Total Crypto Market Cap",
        AssetCategory.CRYPTO_STRUCTURE,
        "usd_billions",
        required_for_core_report=True,
    ),
    AssetCode.TOTAL2: _asset(
        AssetCode.TOTAL2,
        "Total Crypto Market Cap ex BTC",
        AssetCategory.CRYPTO_STRUCTURE,
        "usd_billions",
        required_for_core_report=True,
    ),
    AssetCode.US02Y: _asset(
        AssetCode.US02Y,
        "US 2Y Treasury Yield",
        AssetCategory.RATES,
        "yield_percent",
        required_for_core_report=True,
    ),
    AssetCode.US10Y: _asset(
        AssetCode.US10Y,
        "US 10Y Treasury Yield",
        AssetCategory.RATES,
        "yield_percent",
        required_for_core_report=True,
    ),
    AssetCode.US20Y: _asset(
        AssetCode.US20Y,
        "US 20Y Treasury Yield",
        AssetCategory.RATES,
        "yield_percent",
        required_for_core_report=True,
    ),
    AssetCode.USCPI: _asset(
        AssetCode.USCPI,
        "US Consumer Price Index",
        AssetCategory.INFLATION_LIQUIDITY,
        "year_over_year_percent",
        required_for_core_report=True,
    ),
    AssetCode.USPPI: _asset(
        AssetCode.USPPI,
        "US Producer Price Index",
        AssetCategory.INFLATION_LIQUIDITY,
        "year_over_year_percent",
        required_for_core_report=True,
    ),
    AssetCode.M2SL: _asset(
        AssetCode.M2SL,
        "US Money Supply M2",
        AssetCategory.INFLATION_LIQUIDITY,
        "usd_billions",
        required_for_core_report=True,
    ),
    AssetCode.FXI: _asset(
        AssetCode.FXI,
        "iShares China Large-Cap ETF",
        AssetCategory.EQUITIES_CHINA,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.SHANGHAI_COMPOSITE: _asset(
        AssetCode.SHANGHAI_COMPOSITE,
        "Shanghai Composite Index",
        AssetCategory.EQUITIES_CHINA,
        "index_points",
        required_for_core_report=True,
    ),
    AssetCode.XCUUSD: _asset(
        AssetCode.XCUUSD,
        "Copper / US Dollar",
        AssetCategory.INDUSTRIAL_METALS,
        "usd_per_pound",
        required_for_core_report=True,
    ),
    AssetCode.XAUXAG: _asset(
        AssetCode.XAUXAG,
        "Gold / Silver Ratio",
        AssetCategory.RELATIVE_RATIOS,
        "ratio",
        required_for_core_report=True,
    ),
    AssetCode.BTCXAUK: _asset(
        AssetCode.BTCXAUK,
        "Bitcoin / Gold (Local Reference)",
        AssetCategory.LOCAL_REFERENCE,
        "ratio",
        required_for_core_report=False,
        requires_verified_data_for_live=False,
    ),
    AssetCode.XAUUSDK: _asset(
        AssetCode.XAUUSDK,
        "Gold / US Dollar (Local Reference)",
        AssetCategory.LOCAL_REFERENCE,
        "local_reference_index",
        required_for_core_report=False,
        requires_verified_data_for_live=False,
    ),
    AssetCode.XAGUSDK: _asset(
        AssetCode.XAGUSDK,
        "Silver / US Dollar (Local Reference)",
        AssetCategory.LOCAL_REFERENCE,
        "local_reference_index",
        required_for_core_report=False,
        requires_verified_data_for_live=False,
    ),
    # --- Yeni göstergeler ---
    AssetCode.VIX: _asset(
        AssetCode.VIX,
        "CBOE Volatility Index",
        AssetCategory.VOLATILITY,
        "index_points",
        required_for_core_report=True,
    ),
    AssetCode.REAL_YIELD: _asset(
        AssetCode.REAL_YIELD,
        "US 10Y Real Yield (TIPS)",
        AssetCategory.RATES,
        "yield_percent",
        required_for_core_report=True,
    ),
    AssetCode.HY_SPREAD: _asset(
        AssetCode.HY_SPREAD,
        "ICE BofA HY Credit Spread",
        AssetCategory.CREDIT,
        "spread_percent",
        required_for_core_report=True,
    ),
    AssetCode.ETHUSD: _asset(
        AssetCode.ETHUSD,
        "Ethereum / US Dollar",
        AssetCategory.CRYPTO,
        "usd_per_eth",
        required_for_core_report=True,
    ),
    AssetCode.IWM: _asset(
        AssetCode.IWM,
        "iShares Russell 2000 ETF",
        AssetCategory.EQUITIES_US,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.LQD: _asset(
        AssetCode.LQD,
        "iShares Investment Grade Bond ETF",
        AssetCategory.CREDIT,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.SMH: _asset(
        AssetCode.SMH,
        "VanEck Semiconductor ETF",
        AssetCategory.EQUITIES_US,
        "usd_per_share",
        required_for_core_report=True,
    ),
    AssetCode.XLF: _asset(
        AssetCode.XLF,
        "Financial Select Sector SPDR",
        AssetCategory.EQUITIES_US,
        "usd_per_share",
        required_for_core_report=True,
    ),
}


def get_asset_definition(asset_code: AssetCode | str) -> AssetDefinition:
    code = asset_code if isinstance(asset_code, AssetCode) else AssetCode(asset_code)
    return ASSET_CATALOG[code]


def list_main_assets() -> tuple[AssetDefinition, ...]:
    return tuple(ASSET_CATALOG[asset_code] for asset_code in AssetCode)

__all__ = [name for name in globals() if not name.startswith('_')]
