from app.domain import AssetCode
from app.providers import MockMarketProvider
from app.providers import ProviderSourceBinding
from app.providers import SourceRegistryBoundProviderAdapter


def build_binding(
    asset_symbol: AssetCode | str,
    *,
    source_id: str,
    registry_provider: str,
    verified: bool,
    decision_usage: str,
    active: bool = True,
    paper_safe: bool = True,
) -> ProviderSourceBinding:
    return ProviderSourceBinding(
        asset_symbol=asset_symbol,
        source_id=source_id,
        registry_provider=registry_provider,
        verified=verified,
        decision_usage=decision_usage,
        active=active,
        paper_safe=paper_safe,
    )


def test_adapter_exposes_verified_source_binding_metadata() -> None:
    adapter = SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        {
            AssetCode.BTCUSD: build_binding(
                AssetCode.BTCUSD,
                source_id="approved_btcusd_feed",
                registry_provider="approved_crypto_feed",
                verified=True,
                decision_usage="verified_required",
            )
        },
    )

    payload = adapter.get_asset_data("BTCUSD")

    assert payload.asset_symbol == AssetCode.BTCUSD
    assert payload.value == 105000.5
    assert payload.source_id == "approved_btcusd_feed"
    assert payload.registry_provider == "approved_crypto_feed"
    assert payload.verified is True
    assert payload.decision_usage == "verified_required"
    assert payload.paper_safe is True


def test_adapter_preserves_simulation_only_source_metadata() -> None:
    adapter = SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        {
            AssetCode.XAUUSDK: build_binding(
                AssetCode.XAUUSDK,
                source_id="approved_xauusdk_reference_feed",
                registry_provider="approved_reference_feed",
                verified=False,
                decision_usage="simulation_only",
                paper_safe=True,
            )
        },
    )

    payload = adapter.get_asset_data(AssetCode.XAUUSDK)

    assert payload.asset_symbol == AssetCode.XAUUSDK
    assert payload.verified is False
    assert payload.decision_usage == "simulation_only"
    assert payload.paper_safe is True
    assert payload.source_id == "approved_xauusdk_reference_feed"


def test_adapter_rejects_missing_or_inactive_bindings() -> None:
    adapter = SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        {
            AssetCode.BTCUSD: build_binding(
                AssetCode.BTCUSD,
                source_id="approved_btcusd_feed",
                registry_provider="approved_crypto_feed",
                verified=True,
                decision_usage="verified_required",
            ),
            AssetCode.BRENT: build_binding(
                AssetCode.BRENT,
                source_id="approved_brent_feed",
                registry_provider="approved_energy_feed",
                verified=True,
                decision_usage="verified_required",
                active=False,
            ),
        },
    )

    try:
        adapter.get_asset_data(AssetCode.DXY)
        raise AssertionError("Expected missing binding failure.")
    except ValueError as exc:
        assert str(exc) == "No source binding configured for DXY."

    try:
        adapter.get_asset_data(AssetCode.BRENT)
        raise AssertionError("Expected inactive binding failure.")
    except ValueError as exc:
        assert str(exc) == "Source binding for BRENT is inactive."

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
