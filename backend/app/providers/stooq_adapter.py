"""
Stooq daily CSV provider — paper-safe, read-only, no API key required.
Network fetch is injectable so tests run fully offline.
Must not execute trades. Must not produce buy/sell decisions.
"""
from __future__ import annotations

import csv
import io
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final

from app.domain import AssetCode, SourceTier
from app.providers.base import MarketProvider, MarketProviderPayload
from app.providers.verified_adapter import ProviderSourceBinding, SourceRegistryBoundProviderAdapter

_STOOQ_URL_TEMPLATE: Final[str] = "https://stooq.com/q/d/l/?s={symbol}&i=d"

# Maps AssetCode → (stooq_ticker, canonical_unit).
# Unit must match AssetDefinition.unit exactly (validated by MarketSnapshot).
_STOOQ_ASSET_MAP: Final[dict[AssetCode, tuple[str, str]]] = {
    AssetCode.QQQ: ("qqq.us", "usd_per_share"),
    AssetCode.HYG: ("hyg.us", "usd_per_share"),
    AssetCode.JNK: ("jnk.us", "usd_per_share"),
    AssetCode.FXI: ("fxi.us", "usd_per_share"),
}

_SOURCE_NAME: Final[str] = "stooq_daily_csv"


def _default_fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


class StooqDailyProvider(MarketProvider):
    """
    Paper-safe provider that fetches Stooq free daily closing prices.
    Supports a small subset of ETF assets available on stooq.com.
    Inject fetch_fn to run offline (tests always use a fixture lambda).
    """

    def __init__(
        self,
        fetch_fn: Callable[[str], str] = _default_fetch,
    ) -> None:
        self._fetch_fn = fetch_fn

    @classmethod
    def supported_assets(cls) -> frozenset[AssetCode]:
        return frozenset(_STOOQ_ASSET_MAP)

    @classmethod
    def source_url_for(cls, asset_code: AssetCode) -> str:
        if asset_code not in _STOOQ_ASSET_MAP:
            raise ValueError(
                f"StooqDailyProvider does not support: {asset_code.value}"
            )
        stooq_symbol, _ = _STOOQ_ASSET_MAP[asset_code]
        return _STOOQ_URL_TEMPLATE.format(symbol=stooq_symbol)

    def get_asset_data(self, asset_symbol: AssetCode | str) -> MarketProviderPayload:
        asset_code = (
            asset_symbol
            if isinstance(asset_symbol, AssetCode)
            else AssetCode(asset_symbol)
        )
        if asset_code not in _STOOQ_ASSET_MAP:
            raise ValueError(
                f"StooqDailyProvider does not support asset: {asset_code.value}"
            )
        stooq_symbol, unit = _STOOQ_ASSET_MAP[asset_code]
        url = _STOOQ_URL_TEMPLATE.format(symbol=stooq_symbol)
        csv_text = self._fetch_fn(url)
        return self._parse_csv_response(asset_code, stooq_symbol, unit, csv_text)

    @staticmethod
    def _parse_csv_response(
        asset_code: AssetCode,
        stooq_symbol: str,
        unit: str,
        csv_text: str,
    ) -> MarketProviderPayload:
        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        rows = list(reader)

        if not rows:
            raise ValueError(
                f"StooqDailyProvider: empty or unrecognised CSV for symbol {stooq_symbol!r}"
            )

        latest = rows[-1]

        try:
            date_str = latest["Date"]
            close_str = latest["Close"]
        except KeyError as exc:
            raise ValueError(
                f"StooqDailyProvider: missing expected CSV column {exc}"
                f" for {stooq_symbol!r}"
            ) from exc

        if not date_str.strip() or not close_str.strip():
            raise ValueError(
                f"StooqDailyProvider: blank Date or Close in CSV row"
                f" for {stooq_symbol!r}"
            )

        try:
            close_value = float(close_str)
        except ValueError as exc:
            raise ValueError(
                f"StooqDailyProvider: non-numeric Close value {close_str!r}"
                f" for {stooq_symbol!r}"
            ) from exc

        observed_at = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(
            tzinfo=UTC
        )
        now = datetime.now(UTC)

        return MarketProviderPayload(
            asset_symbol=asset_code,
            value=close_value,
            unit=unit,
            source_name=_SOURCE_NAME,
            source_tier=SourceTier.SECONDARY,
            observed_at=observed_at,
            available_at=observed_at,
            stored_at=now,
            fallback_used=False,
            raw_payload_ref=f"stooq://daily/{stooq_symbol}",
        )


def build_stooq_source_bindings() -> dict[str, ProviderSourceBinding]:
    """
    Build ProviderSourceBinding objects for the 4 Stooq ETF assets.
    All bindings: verified=False, decision_usage="simulation_only",
    active=True, paper_safe=True.

    Kept separate from source_registry_v1.0.yaml to avoid overwriting the
    existing abstract approved feeds for QQQ/HYG/JNK/FXI. Safe for
    paper/simulation use only — must not be used for trading execution.
    """
    _entries = (
        (AssetCode.QQQ, "stooq_qqq_daily"),
        (AssetCode.HYG, "stooq_hyg_daily"),
        (AssetCode.JNK, "stooq_jnk_daily"),
        (AssetCode.FXI, "stooq_fxi_daily"),
    )
    return {
        asset_code.value: ProviderSourceBinding(
            asset_symbol=asset_code,
            source_id=source_id,
            registry_provider="stooq_daily_csv",
            verified=False,
            decision_usage="simulation_only",
            active=True,
            paper_safe=True,
        )
        for asset_code, source_id in _entries
    }


def build_stooq_registry_bound_adapter(
    fetch_fn: Callable[[str], str] = _default_fetch,
) -> SourceRegistryBoundProviderAdapter:
    """
    Build a SourceRegistryBoundProviderAdapter wrapping StooqDailyProvider.
    Inject fetch_fn to run offline (tests always inject a fixture lambda).
    Default fetch_fn uses urllib (live network) — only use for real ingestion.
    Safe for paper/simulation only — must not be used for trading execution.
    """
    return SourceRegistryBoundProviderAdapter(
        StooqDailyProvider(fetch_fn=fetch_fn),
        build_stooq_source_bindings(),
    )


__all__ = [name for name in globals() if not name.startswith("_")]
