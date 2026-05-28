from app.domain import AssetCode
from app.providers import MockMarketProvider
from app.providers import ProviderSourceBinding
from app.providers import SourceRegistryBoundProviderAdapter
from app.services import SourceObservationService


def build_adapter() -> SourceRegistryBoundProviderAdapter:
    return SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        {
            AssetCode.BTCUSD: ProviderSourceBinding(
                asset_symbol=AssetCode.BTCUSD,
                source_id="approved_btcusd_feed",
                registry_provider="approved_crypto_feed",
                verified=True,
                decision_usage="verified_required",
                active=True,
                paper_safe=True,
            ),
            AssetCode.BRENT: ProviderSourceBinding(
                asset_symbol=AssetCode.BRENT,
                source_id="approved_brent_feed",
                registry_provider="approved_energy_feed",
                verified=True,
                decision_usage="verified_required",
                active=True,
                paper_safe=True,
            ),
            AssetCode.XAUUSDK: ProviderSourceBinding(
                asset_symbol=AssetCode.XAUUSDK,
                source_id="approved_xauusdk_reference_feed",
                registry_provider="approved_reference_feed",
                verified=False,
                decision_usage="simulation_only",
                active=True,
                paper_safe=True,
            ),
        },
    )


def test_source_observation_mapping_normalizes_to_batch_time() -> None:
    adapter = build_adapter()
    service = SourceObservationService()
    payloads = [
        adapter.get_asset_data(AssetCode.BTCUSD),
        adapter.get_asset_data(AssetCode.BRENT),
        adapter.get_asset_data(AssetCode.XAUUSDK),
    ]

    records = service.build_records(payloads)
    observations = service.build_source_observations(payloads)
    batch_time = max(payload.stored_at for payload in payloads)

    assert {record.mapped_at for record in records} == {batch_time}
    assert observations == {
        "approved_btcusd_feed": batch_time,
        "approved_brent_feed": batch_time,
        "approved_xauusdk_reference_feed": batch_time,
    }

    assert service.build_mapping_summary(records) == {
        "contract": "verified_provider_adapter_v1",
        "normalization_mode": "batch_stored_at",
        "total_bound_sources": 3,
        "verified_sources": 2,
        "simulation_only_sources": 1,
        "paper_safe_sources": 3,
    }


def test_source_observation_mapping_can_preserve_per_source_time() -> None:
    adapter = build_adapter()
    service = SourceObservationService()
    payloads = [
        adapter.get_asset_data(AssetCode.BTCUSD),
        adapter.get_asset_data(AssetCode.BRENT),
    ]

    records = service.build_records(payloads, normalize_to_batch_time=False)
    observations = service.build_source_observations(payloads, normalize_to_batch_time=False)

    assert records[0].mapped_at == payloads[0].stored_at
    assert records[1].mapped_at == payloads[1].stored_at
    assert observations == {
        "approved_btcusd_feed": payloads[0].stored_at,
        "approved_brent_feed": payloads[1].stored_at,
    }


def test_source_observation_mapping_handles_empty_payloads() -> None:
    service = SourceObservationService()

    assert service.build_records([]) == ()
    assert service.build_source_observations([]) == {}
    assert service.build_mapping_summary(()) == {
        "contract": "verified_provider_adapter_v1",
        "normalization_mode": "batch_stored_at",
        "total_bound_sources": 0,
        "verified_sources": 0,
        "simulation_only_sources": 0,
        "paper_safe_sources": 0,
    }


def test_source_observation_mapping_builds_serializable_persistence_payload() -> None:
    adapter = build_adapter()
    service = SourceObservationService()
    payloads = [
        adapter.get_asset_data(AssetCode.BTCUSD),
        adapter.get_asset_data(AssetCode.BRENT),
        adapter.get_asset_data(AssetCode.XAUUSDK),
    ]

    persistence_payload = service.build_persistence_payload(payloads)

    assert persistence_payload["summary"] == {
        "contract": "verified_provider_adapter_v1",
        "normalization_mode": "batch_stored_at",
        "total_bound_sources": 3,
        "verified_sources": 2,
        "simulation_only_sources": 1,
        "paper_safe_sources": 3,
    }
    assert persistence_payload["source_observations"] == {
        "approved_btcusd_feed": "2026-05-19T09:27:00+00:00",
        "approved_brent_feed": "2026-05-19T09:27:00+00:00",
        "approved_xauusdk_reference_feed": "2026-05-19T09:27:00+00:00",
    }
    assert persistence_payload["records"][0] == {
        "source_id": "approved_btcusd_feed",
        "asset_symbol": "BTCUSD",
        "registry_provider": "approved_crypto_feed",
        "observed_at": "2026-05-19T09:00:00+00:00",
        "available_at": "2026-05-19T09:01:00+00:00",
        "stored_at": "2026-05-19T09:02:00+00:00",
        "mapped_at": "2026-05-19T09:27:00+00:00",
        "verified": True,
        "decision_usage": "verified_required",
        "paper_safe": True,
    }

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
