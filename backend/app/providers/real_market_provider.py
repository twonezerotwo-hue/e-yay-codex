"""
RealMarketProvider — Gerçek piyasa verisi.
Kaynak önceliği: yfinance → CoinGecko → FRED → Mock fallback

Veri kaynakları:
  yfinance  : BTC, Brent, Gold, Silver, Copper, DXY, HYG, JNK, NASDAQ,
              QQQ, S&P500, FXI, Shanghai Composite
  CoinGecko : BTC.D, USDT.D, TOTAL, TOTAL2 (global endpoint, API key yok)
  FRED CSV  : US02Y, US10Y, US20Y, USCPI, USPPI, M2SL
  Türev     : XAUXAG, BTCXAUK, XAUUSDK, XAGUSDK (temel fiyatlardan hesaplanır)

Herhangi bir kaynak başarısız olursa ilgili asset için mock değerine düşer
ve fallback_used=True ile işaretlenir. Execution: OFF / NO_EXECUTION.
"""
from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Optional

from app.domain import AssetCategory, AssetCode, SourceTier, get_asset_definition
from app.providers.base import MarketProvider, MarketProviderPayload
from app.providers.mock_market_provider import MOCK_ASSET_VALUES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ticker / series ID eşlemeleri
# ---------------------------------------------------------------------------

_YFINANCE_MAP: dict[AssetCode, str] = {
    AssetCode.BTCUSD:             "BTC-USD",
    AssetCode.BRENT:              "BZ=F",
    AssetCode.XAUUSD:             "GC=F",
    AssetCode.XAGUSD:             "SI=F",
    AssetCode.DXY:                "DX-Y.NYB",
    AssetCode.HYG:                "HYG",
    AssetCode.JNK:                "JNK",
    AssetCode.NASDAQ:             "^IXIC",
    AssetCode.QQQ:                "QQQ",
    AssetCode.SP500:              "^GSPC",
    AssetCode.FXI:                "FXI",
    AssetCode.SHANGHAI_COMPOSITE: "000001.SS",
    AssetCode.XCUUSD:             "HG=F",   # USD/pound — olduğu gibi sakla
    # Hazine getirileri — FRED yerine yfinance kullan (daha güvenilir)
    AssetCode.US02Y:              "^IRX",   # 13-haftalık T-bill ≈ 2Y proxy
    AssetCode.US10Y:              "^TNX",   # 10Y Treasury
    AssetCode.US20Y:              "^TYX",   # 30Y Treasury (20Y proxy)
}

# FRED series_id → (series_id, units_param)
# units=pc1 → percent change from year ago (YoY %)
_FRED_MAP: dict[AssetCode, tuple[str, str]] = {
    AssetCode.US02Y: ("DGS2",      ""),
    AssetCode.US10Y: ("DGS10",     ""),
    AssetCode.US20Y: ("DGS20",     ""),
    AssetCode.USCPI: ("CPIAUCSL",  "pc1"),
    AssetCode.USPPI: ("PPIACO",    "pc1"),
    AssetCode.M2SL:  ("M2SL",      ""),
}

_COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
_CACHE_TTL_SECONDS = 300   # 5 dakika

# macOS Homebrew Python'da SSL sertifikaları için unverified context kullan
_SSL_CTX = ssl._create_unverified_context()

# ---------------------------------------------------------------------------
# Basit bellek önbelleği
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, float]] = {}   # key → (value, expire_epoch)


def _cached(key: str) -> Optional[float]:
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _set_cache(key: str, value: float) -> None:
    _cache[key] = (value, time.monotonic() + _CACHE_TTL_SECONDS)


# ---------------------------------------------------------------------------
# yfinance toplu çekimi
# ---------------------------------------------------------------------------

def _fetch_single_yf(ticker: str) -> tuple[str, Optional[float]]:
    """Tek bir ticker için fast_info.last_price ile anlık fiyat çeker."""
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        price = t.fast_info.last_price
        if price and price == price and price > 0:   # None ve NaN kontrolü
            return ticker, float(price)
    except Exception as exc:
        logger.debug("yfinance fast_info %s başarısız: %s", ticker, exc)
    return ticker, None


def _fetch_yfinance_batch(tickers: list[str]) -> dict[str, float]:
    """
    Tüm ticker'ları paralel iş parçacıklarıyla fast_info üzerinden çeker.
    yf.download() yerine fast_info kullanıldığı için ~10× daha hızlıdır.
    """
    result: dict[str, float] = {}
    if not tickers:
        return result
    with ThreadPoolExecutor(max_workers=min(len(tickers), 8)) as pool:
        futures = {pool.submit(_fetch_single_yf, t): t for t in tickers}
        for future in as_completed(futures, timeout=15):
            try:
                ticker, price = future.result()
                if price is not None:
                    result[ticker] = price
            except Exception as exc:
                logger.debug("yfinance worker hata: %s", exc)
    logger.info("yfinance fast_info: %d/%d ticker başarılı", len(result), len(tickers))
    return result


# ---------------------------------------------------------------------------
# FRED CSV çekimi
# ---------------------------------------------------------------------------

def _fetch_fred(series_id: str, units: str = "") -> Optional[float]:
    """FRED CSV endpoint'inden en güncel değeri çeker."""
    cache_key = f"fred:{series_id}:{units}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached

    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        if units:
            url += f"&units={units}"
        req = urllib.request.Request(url, headers={"User-Agent": "E-YAY-BrainChain/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            content = resp.read().decode("utf-8")

        value: Optional[float] = None
        for line in reversed(content.strip().splitlines()[1:]):   # başlık satırını atla
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[1] not in ("", ".", "NA", "#N/A"):
                try:
                    value = float(parts[1])
                    break
                except ValueError:
                    continue

        if value is not None:
            _set_cache(cache_key, value)
            logger.debug("FRED %s → %.4f", series_id, value)
        return value
    except Exception as exc:
        logger.warning("FRED %s çekimi başarısız: %s", series_id, exc)
        return None


# ---------------------------------------------------------------------------
# CoinGecko global endpoint
# ---------------------------------------------------------------------------

def _fetch_coingecko() -> dict[str, float]:
    """CoinGecko global market verilerini çeker: BTC.D, USDT.D, TOTAL, TOTAL2."""
    # Önce önbellekte var mı kontrol et
    keys = ("cg:btcd", "cg:usdtd", "cg:total", "cg:total2")
    cached_vals = [_cached(k) for k in keys]
    if all(v is not None for v in cached_vals):
        return dict(zip(("btcd", "usdtd", "total", "total2"), cached_vals))  # type: ignore[arg-type]

    try:
        req = urllib.request.Request(
            _COINGECKO_GLOBAL_URL,
            headers={
                "User-Agent": "E-YAY-BrainChain/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        d = payload["data"]
        pct = d.get("market_cap_percentage", {})
        btcd  = float(pct.get("btc", 0.0))
        usdtd = float(pct.get("usdt", 0.0))

        total_usd  = float(d.get("total_market_cap", {}).get("usd", 0.0))
        total_b    = total_usd / 1e9
        # TOTAL2 = TOTAL - BTC market cap
        btc_mc     = total_usd * (btcd / 100.0)
        total2_b   = (total_usd - btc_mc) / 1e9

        result = {"btcd": btcd, "usdtd": usdtd, "total": total_b, "total2": total2_b}
        for k, v in zip(("cg:btcd", "cg:usdtd", "cg:total", "cg:total2"),
                        (btcd, usdtd, total_b, total2_b)):
            _set_cache(k, v)

        logger.debug("CoinGecko: BTC.D=%.2f%% USDT.D=%.2f%% TOTAL=%.0fB", btcd, usdtd, total_b)
        return result
    except Exception as exc:
        logger.warning("CoinGecko çekimi başarısız: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Ana provider sınıfı
# ---------------------------------------------------------------------------

def _fetch_fred_all() -> dict[AssetCode, float]:
    """Tüm FRED serilerini paralel olarak çeker."""
    result: dict[AssetCode, float] = {}
    def _fetch_one(code: AssetCode) -> tuple[AssetCode, Optional[float]]:
        series_id, units = _FRED_MAP[code]
        return code, _fetch_fred(series_id, units)

    with ThreadPoolExecutor(max_workers=len(_FRED_MAP)) as pool:
        futures = {pool.submit(_fetch_one, code): code for code in _FRED_MAP}
        for future in as_completed(futures, timeout=20):
            try:
                code, val = future.result()
                if val is not None:
                    result[code] = val
            except Exception as exc:
                logger.debug("FRED parallel worker hata: %s", exc)
    logger.info("FRED: %d/%d seri başarılı", len(result), len(_FRED_MAP))
    return result


class RealMarketProvider(MarketProvider):
    """
    Gerçek piyasa verisi sağlayıcısı.
    Tüm kaynaklar (yfinance, CoinGecko, FRED) paralel prefetch edilir.
    İlk yanıt ~5–15 saniyede gelir; sonraki çağrılar önbellekten anında döner.
    Her başarısız veri noktası için mock değerine düşer.
    """

    def __init__(self) -> None:
        self._yf:   dict[str, float] = {}
        self._cg:   dict[str, float] = {}
        self._fred: dict[AssetCode, float] = {}
        self._fetched_at: datetime = datetime.now(UTC)
        self._prefetch()

    def _prefetch(self) -> None:
        """yfinance, CoinGecko ve FRED'i paralel olarak tek seferde çeker."""
        tickers = list(_YFINANCE_MAP.values())
        logger.info(
            "Gerçek piyasa verisi prefetch başlıyor: %d yfinance + %d FRED + CoinGecko…",
            len(tickers), len(_FRED_MAP),
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            yf_future   = pool.submit(_fetch_yfinance_batch, tickers)
            cg_future   = pool.submit(_fetch_coingecko)
            fred_future = pool.submit(_fetch_fred_all)

            self._yf   = yf_future.result()
            self._cg   = cg_future.result()
            self._fred = fred_future.result()

        self._fetched_at = datetime.now(UTC)
        logger.info(
            "Prefetch tamamlandı: yfinance=%d/%d, CoinGecko=%d/4, FRED=%d/%d",
            len(self._yf), len(tickers),
            len(self._cg),
            len(self._fred), len(_FRED_MAP),
        )

    # ------------------------------------------------------------------

    def get_asset_data(self, asset_symbol: AssetCode | str) -> MarketProviderPayload:
        code = asset_symbol if isinstance(asset_symbol, AssetCode) else AssetCode(asset_symbol)
        asset_def  = get_asset_definition(code)
        fallback   = MOCK_ASSET_VALUES[code]
        now        = self._fetched_at

        value, fallback_used = self._resolve(code, fallback)
        source_name, source_tier = self._source_meta(code, fallback_used)

        return MarketProviderPayload(
            asset_symbol  = code,
            value         = value,
            unit          = asset_def.unit,
            source_name   = source_name,
            source_tier   = source_tier,
            observed_at   = now,
            available_at  = now,
            stored_at     = now,
            fallback_used = fallback_used,
            raw_payload_ref = f"real://market/{code.value.lower()}",
        )

    # ------------------------------------------------------------------
    # Değer çözümleme
    # ------------------------------------------------------------------

    # Birim dönüşüm sabiti: HG=F $/pound → $/ton
    _LBS_PER_TON = 2_204.623

    def _resolve(self, code: AssetCode, fallback: float) -> tuple[float, bool]:
        # 1. yfinance doğrudan (yield asset'ler için FRED fallback zincirlenir)
        if code in _YFINANCE_MAP:
            ticker = _YFINANCE_MAP[code]
            val = self._yf.get(ticker)
            if val and val == val:   # None ve NaN kontrolü
                # Bakır: HG=F $/pound → $/ton dönüşümü
                # Rejim servisi eşiği 9,000 $/ton kullanıyor
                if code == AssetCode.XCUUSD:
                    val = val * self._LBS_PER_TON
                return val, False
            # yfinance başarısız — FRED'e düş (yalnızca yield asset'ler için)
            if code in _FRED_MAP:
                fred_val = self._fred.get(code)
                if fred_val is not None:
                    return fred_val, False
            return fallback, True

        # 2. CoinGecko
        cg_key = {
            AssetCode.BTC_DOMINANCE:  "btcd",
            AssetCode.USDT_DOMINANCE: "usdtd",
            AssetCode.TOTAL:          "total",
            AssetCode.TOTAL2:         "total2",
        }.get(code)
        if cg_key:
            val = self._cg.get(cg_key)
            return (val, False) if val else (fallback, True)

        # 3. FRED (prefetch edilmiş önbellekten)
        if code in _FRED_MAP:
            val = self._fred.get(code)
            return (val, False) if val is not None else (fallback, True)

        # 4. Türev oranlar
        if code == AssetCode.XAUXAG:
            xau, _ = self._resolve(AssetCode.XAUUSD, MOCK_ASSET_VALUES[AssetCode.XAUUSD])
            xag, _ = self._resolve(AssetCode.XAGUSD, MOCK_ASSET_VALUES[AssetCode.XAGUSD])
            return (xau / xag, False) if xag > 0 else (fallback, True)

        if code == AssetCode.BTCXAUK:
            btc, _ = self._resolve(AssetCode.BTCUSD, MOCK_ASSET_VALUES[AssetCode.BTCUSD])
            xau, _ = self._resolve(AssetCode.XAUUSD, MOCK_ASSET_VALUES[AssetCode.XAUUSD])
            return (btc / xau, False) if xau > 0 else (fallback, True)

        if code == AssetCode.XAUUSDK:
            # Normalise: $2000 = 1.0 referans
            xau, _ = self._resolve(AssetCode.XAUUSD, MOCK_ASSET_VALUES[AssetCode.XAUUSD])
            return xau / 2000.0, False

        if code == AssetCode.XAGUSDK:
            # Normalise: $25 = 1.0 referans
            xag, _ = self._resolve(AssetCode.XAGUSD, MOCK_ASSET_VALUES[AssetCode.XAGUSD])
            return xag / 25.0, False

        logger.warning("AssetCode %s için veri kaynağı yok, mock kullanılıyor", code)
        return fallback, True

    # ------------------------------------------------------------------

    def _source_meta(self, code: AssetCode, fallback_used: bool) -> tuple[str, SourceTier]:
        if fallback_used:
            return "fallback_mock", SourceTier.FALLBACK
        if code in _YFINANCE_MAP:
            return "yfinance", SourceTier.PRIMARY
        if code in (AssetCode.BTC_DOMINANCE, AssetCode.USDT_DOMINANCE,
                    AssetCode.TOTAL, AssetCode.TOTAL2):
            return "coingecko", SourceTier.PRIMARY
        if code in _FRED_MAP and code not in _YFINANCE_MAP:
            return "fred", SourceTier.SECONDARY
        return "derived", SourceTier.PRIMARY


__all__ = ["RealMarketProvider"]
