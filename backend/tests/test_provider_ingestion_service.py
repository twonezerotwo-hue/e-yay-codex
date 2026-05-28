from pathlib import Path

from app.domain import AssetCode
from app.domain import list_main_assets
from app.providers import MockMarketProvider
from app.providers import ProviderSourceBinding
from app.providers import SourceRegistryBoundProviderAdapter
from app.providers import build_provider_source_bindings
from app.services import MarketSnapshotService
from app.services import ProviderIngestionService
from app.storage import SnapshotStore
from registry import build_source_registry_entries
from registry import load_source_registry


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


class FailingMockMarketProvider(MockMarketProvider):
    def get_asset_data(self, asset_symbol: AssetCode | str):
        asset_code = asset_symbol if isinstance(asset_symbol, AssetCode) else AssetCode(asset_symbol)
        if asset_code == AssetCode.BTCUSD:
            raise RuntimeError("mock provider failure")
        return super().get_asset_data(asset_code)


def build_full_adapter(*, provider: MockMarketProvider | None = None) -> SourceRegistryBoundProviderAdapter:
    source_registry_entries = build_source_registry_entries(load_source_registry())
    return SourceRegistryBoundProviderAdapter(
        provider or MockMarketProvider(),
        build_provider_source_bindings(source_registry_entries),
    )


def test_provider_ingestion_service_processes_all_assets_and_builds_persistence_payload() -> None:
    session = FakeSession()
    adapter = build_full_adapter()
    result = ProviderIngestionService(MarketSnapshotService(session), adapter).run()

    assert result.total_assets_processed == 27
    assert result.successful_snapshots == 27
    assert result.failed_snapshots == 0
    assert result.failed_assets == ()
    assert len(result.persisted_snapshots) == 27
    assert len(result.provider_payloads) == 27
    assert result.dqs_decision_counts == {
        "PASS": 24,
        "DEGRADED_PASS": 3,
        "LIMITED_ANALYSIS_ONLY": 0,
        "FAIL_NO_DECISION": 0,
    }
    assert result.source_observation_persistence_payload["summary"] == {
        "contract": "verified_provider_adapter_v1",
        "normalization_mode": "batch_stored_at",
        "total_bound_sources": 27,
        "verified_sources": 24,
        "simulation_only_sources": 3,
        "paper_safe_sources": 27,
    }
    assert result.source_observation_persistence_payload["source_observations"]["approved_btcusd_feed"] == "2026-05-19T09:28:00+00:00"
    assert len(result.source_observation_persistence_payload["records"]) == 27
    assert session.commit_calls == 27


def test_provider_ingestion_service_can_persist_snapshot_metadata(tmp_path: Path) -> None:
    session = FakeSession()
    adapter = build_full_adapter()
    store = SnapshotStore(tmp_path / "paper_ingestion.jsonl")
    result = ProviderIngestionService(MarketSnapshotService(session), adapter).run(
        persist_result=True,
        snapshot_store=store,
        snapshot_metadata={
            "source_registry_version": "1.0",
            "feature_registry_version": "1.0",
            "missing_sources": [],
            "stale_sources": [],
            "report_type": "provider_ingestion_paper_snapshot",
            "mode": "PAPER_SAFE",
            "execution_mode": "PAPER_ONLY",
        },
    )

    assert result.stored_snapshot_metadata is not None
    assert result.stored_snapshot_metadata["mode"] == "PAPER_SAFE"
    assert result.stored_snapshot_metadata["decision_permission"] == "NO_EXECUTION"
    assert result.stored_snapshot_metadata["execution_mode"] == "PAPER_ONLY"
    assert result.stored_snapshot_metadata["source_registry_version"] == "1.0"
    assert result.stored_snapshot_metadata["feature_registry_version"] == "1.0"
    assert result.stored_snapshot_metadata["missing_sources"] == []
    assert result.stored_snapshot_metadata["stale_sources"] == []
    assert len(result.stored_snapshot_metadata["snapshots"]) == 27
    brent_snapshot = next(
        snapshot
        for snapshot in result.stored_snapshot_metadata["snapshots"]
        if snapshot["asset_symbol"] == "BRENT"
    )
    assert brent_snapshot == {
        "asset_symbol": "BRENT",
        "value": 82.35,
        "unit": "usd_per_barrel",
        "source_name": "mock_energy_provider",
        "source_tier": "primary",
        "observed_at": "2026-05-19T09:01:00+00:00",
        "available_at": "2026-05-19T09:02:00+00:00",
        "stored_at": "2026-05-19T09:03:00+00:00",
        "freshness_seconds": 120,
        "is_stale": False,
        "fallback_used": False,
        "data_quality_score": 100.0,
        "raw_payload_ref": "mock://market/brent",
        "dqs_result": {
            "total_score": 100.0,
            "decision": "PASS",
            "component_scores": {
                "freshness_score": 100.0,
                "source_tier_score": 100.0,
                "cross_provider_agreement_score": 100.0,
                "completeness_score": 100.0,
                "timestamp_integrity_score": 100.0,
                "anomaly_consistency_score": 100.0,
            },
        },
    }
    assert result.stored_snapshot_metadata["pipeline_summary"]["total_assets_processed"] == 27
    loaded_snapshot = store.load_snapshot(result.stored_snapshot_metadata["snapshot_id"])
    assert loaded_snapshot == result.stored_snapshot_metadata


def test_provider_ingestion_service_default_behavior_remains_without_persistence() -> None:
    session = FakeSession()
    adapter = build_full_adapter()
    result = ProviderIngestionService(MarketSnapshotService(session), adapter).run()

    assert result.stored_snapshot_metadata is None


def test_provider_ingestion_service_handles_failing_assets_without_crashing() -> None:
    session = FakeSession()
    adapter = build_full_adapter(provider=FailingMockMarketProvider())
    result = ProviderIngestionService(MarketSnapshotService(session), adapter).run()

    assert result.total_assets_processed == 27
    assert result.successful_snapshots == 26
    assert result.failed_snapshots == 1
    assert result.failed_assets == ("BTCUSD",)
    assert len(result.persisted_snapshots) == 26
    assert len(result.provider_payloads) == 26
    assert len(result.source_observation_persistence_payload["records"]) == 26
    assert "approved_btcusd_feed" not in result.source_observation_persistence_payload["source_observations"]
    assert session.commit_calls == 26


def test_provider_ingestion_service_enforces_paper_safe_payloads() -> None:
    session = FakeSession()
    asset = next(asset for asset in list_main_assets() if asset.code == AssetCode.BTCUSD)
    adapter = SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        {
            AssetCode.BTCUSD.value: ProviderSourceBinding(
                asset_symbol=AssetCode.BTCUSD,
                source_id="approved_btcusd_feed",
                registry_provider="approved_crypto_feed",
                verified=True,
                decision_usage="verified_required",
                active=True,
                paper_safe=False,
            )
        },
    )

    result = ProviderIngestionService(MarketSnapshotService(session), adapter).run((asset,))

    assert result.total_assets_processed == 1
    assert result.successful_snapshots == 0
    assert result.failed_snapshots == 1
    assert result.failed_assets == ("BTCUSD",)
    assert result.source_observation_persistence_payload == {
        "summary": {
            "contract": "verified_provider_adapter_v1",
            "normalization_mode": "batch_stored_at",
            "total_bound_sources": 0,
            "verified_sources": 0,
            "simulation_only_sources": 0,
            "paper_safe_sources": 0,
        },
        "records": [],
        "source_observations": {},
    }
    assert session.commit_calls == 0

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
