"""
Integration tests for StooqDailyProvider wired through
SourceRegistryBoundProviderAdapter into ProviderIngestionService.

All tests use injectable fixture CSV — no network calls are made.
Verifies: source binding construction, VerifiedProviderPayload output,
source attribution preservation, ingestion service integration,
paper-safe snapshot persistence, and graceful failure on bad CSV.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.domain import AssetCode
from app.domain.assets import get_asset_definition
from app.providers import SourceRegistryBoundProviderAdapter
from app.providers import VerifiedProviderPayload
from app.providers.stooq_adapter import (
    build_stooq_registry_bound_adapter,
    build_stooq_source_bindings,
)
from app.services import MarketSnapshotService, ProviderIngestionService
from app.storage import SnapshotStore

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

_FIXTURE_CSV = """\
Date,Open,High,Low,Close,Volume
2026-05-27,483.50,488.00,482.00,486.75,61234000
"""

_BAD_CSV = "Date,Open,High,Low,Volume\n2026-05-27,483.50,488.00,482.00,61234000\n"

_STOOQ_ASSET_CODES = (AssetCode.QQQ, AssetCode.HYG, AssetCode.JNK, AssetCode.FXI)
_STOOQ_ASSETS = tuple(get_asset_definition(code) for code in _STOOQ_ASSET_CODES)


def _fixture_fetch(_url: str) -> str:
    return _FIXTURE_CSV


def _build_fixture_adapter() -> SourceRegistryBoundProviderAdapter:
    return build_stooq_registry_bound_adapter(fetch_fn=_fixture_fetch)


class _FakeSession:
    def add(self, _: object) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


# ---------------------------------------------------------------------------
# build_stooq_source_bindings
# ---------------------------------------------------------------------------


def test_stooq_source_bindings_returns_all_four_assets():
    bindings = build_stooq_source_bindings()
    assert set(bindings.keys()) == {
        AssetCode.QQQ.value,
        AssetCode.HYG.value,
        AssetCode.JNK.value,
        AssetCode.FXI.value,
    }


def test_stooq_source_bindings_are_paper_safe():
    for binding in build_stooq_source_bindings().values():
        assert binding.paper_safe is True


def test_stooq_source_bindings_are_simulation_only():
    for binding in build_stooq_source_bindings().values():
        assert binding.verified is False
        assert binding.decision_usage == "simulation_only"


def test_stooq_source_bindings_are_active():
    for binding in build_stooq_source_bindings().values():
        assert binding.active is True


def test_stooq_source_bindings_use_stooq_registry_provider():
    for binding in build_stooq_source_bindings().values():
        assert binding.registry_provider == "stooq_daily_csv"


def test_stooq_source_bindings_have_expected_source_ids():
    bindings = build_stooq_source_bindings()
    assert bindings[AssetCode.QQQ.value].source_id == "stooq_qqq_daily"
    assert bindings[AssetCode.HYG.value].source_id == "stooq_hyg_daily"
    assert bindings[AssetCode.JNK.value].source_id == "stooq_jnk_daily"
    assert bindings[AssetCode.FXI.value].source_id == "stooq_fxi_daily"


# ---------------------------------------------------------------------------
# SourceRegistryBoundProviderAdapter wrapping
# ---------------------------------------------------------------------------


def test_stooq_registry_bound_adapter_emits_verified_payload():
    adapter = _build_fixture_adapter()
    payload = adapter.get_asset_data(AssetCode.QQQ)
    assert isinstance(payload, VerifiedProviderPayload)
    assert payload.asset_symbol == AssetCode.QQQ
    assert payload.value == pytest.approx(486.75)
    assert payload.unit == "usd_per_share"


def test_stooq_registry_bound_adapter_source_id_preserved():
    adapter = _build_fixture_adapter()
    payload = adapter.get_asset_data(AssetCode.HYG)
    assert payload.source_id == "stooq_hyg_daily"
    assert payload.registry_provider == "stooq_daily_csv"


def test_stooq_registry_bound_adapter_source_name_preserved():
    adapter = _build_fixture_adapter()
    payload = adapter.get_asset_data(AssetCode.JNK)
    assert payload.source_name == "stooq_daily_csv"


def test_stooq_registry_bound_adapter_payload_is_paper_safe():
    adapter = _build_fixture_adapter()
    payload = adapter.get_asset_data(AssetCode.FXI)
    assert payload.paper_safe is True
    assert payload.verified is False
    assert payload.decision_usage == "simulation_only"


def test_stooq_registry_bound_adapter_raises_on_unsupported_asset():
    adapter = _build_fixture_adapter()
    with pytest.raises(ValueError, match="No source binding configured"):
        adapter.get_asset_data(AssetCode.BTCUSD)


def test_stooq_registry_bound_adapter_list_bindings_returns_four():
    adapter = _build_fixture_adapter()
    bindings = adapter.list_bindings()
    assert len(bindings) == 4
    source_ids = {b.source_id for b in bindings}
    assert source_ids == {
        "stooq_qqq_daily",
        "stooq_hyg_daily",
        "stooq_jnk_daily",
        "stooq_fxi_daily",
    }


# ---------------------------------------------------------------------------
# ProviderIngestionService integration
# ---------------------------------------------------------------------------


def test_stooq_ingestion_processes_four_stooq_assets():
    adapter = _build_fixture_adapter()
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(assets=_STOOQ_ASSETS)

    assert result.total_assets_processed == 4
    assert result.successful_snapshots == 4
    assert result.failed_snapshots == 0
    assert result.failed_assets == ()


def test_stooq_ingestion_result_has_paper_safe_observations():
    adapter = _build_fixture_adapter()
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(assets=_STOOQ_ASSETS)

    summary = result.source_observation_persistence_payload["summary"]
    assert summary["contract"] == "verified_provider_adapter_v1"
    assert summary["total_bound_sources"] == 4
    assert summary["paper_safe_sources"] == 4
    assert summary["simulation_only_sources"] == 4
    assert summary["verified_sources"] == 0


def test_stooq_ingestion_source_observations_use_stooq_source_ids():
    adapter = _build_fixture_adapter()
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(assets=_STOOQ_ASSETS)

    source_observations = result.source_observation_persistence_payload[
        "source_observations"
    ]
    assert "stooq_qqq_daily" in source_observations
    assert "stooq_hyg_daily" in source_observations
    assert "stooq_jnk_daily" in source_observations
    assert "stooq_fxi_daily" in source_observations


def test_stooq_ingestion_persists_to_snapshot_store(tmp_path: Path):
    adapter = _build_fixture_adapter()
    store = SnapshotStore(tmp_path / "stooq_paper_snapshots.jsonl")

    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(
        assets=_STOOQ_ASSETS,
        persist_result=True,
        snapshot_store=store,
        snapshot_metadata={
            "source_registry_version": "1.0",
            "feature_registry_version": "1.0",
            "missing_sources": [],
            "stale_sources": [],
            "report_type": "stooq_paper_ingestion",
            "mode": "PAPER_SAFE",
            "execution_mode": "PAPER_ONLY",
        },
    )

    assert result.stored_snapshot_metadata is not None
    assert result.stored_snapshot_metadata["mode"] == "PAPER_SAFE"
    assert result.stored_snapshot_metadata["decision_permission"] == "NO_EXECUTION"
    assert result.stored_snapshot_metadata["execution_mode"] == "PAPER_ONLY"
    assert len(result.stored_snapshot_metadata["snapshots"]) == 4

    loaded = store.load_snapshot(result.stored_snapshot_metadata["snapshot_id"])
    assert loaded == result.stored_snapshot_metadata


def test_stooq_ingestion_snapshot_assets_are_correct(tmp_path: Path):
    adapter = _build_fixture_adapter()
    store = SnapshotStore(tmp_path / "stooq_paper_snapshots.jsonl")

    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(
        assets=_STOOQ_ASSETS,
        persist_result=True,
        snapshot_store=store,
        snapshot_metadata={
            "source_registry_version": "1.0",
            "feature_registry_version": "1.0",
            "missing_sources": [],
            "stale_sources": [],
            "report_type": "stooq_paper_ingestion",
            "mode": "PAPER_SAFE",
            "execution_mode": "PAPER_ONLY",
        },
    )

    asset_symbols = {
        snap["asset_symbol"]
        for snap in result.stored_snapshot_metadata["snapshots"]
    }
    assert asset_symbols == {"QQQ", "HYG", "JNK", "FXI"}

    qqq_snap = next(
        s for s in result.stored_snapshot_metadata["snapshots"]
        if s["asset_symbol"] == "QQQ"
    )
    assert qqq_snap["source_name"] == "stooq_daily_csv"
    assert qqq_snap["unit"] == "usd_per_share"
    assert qqq_snap["fallback_used"] is False
    assert qqq_snap["raw_payload_ref"] == "stooq://daily/qqq.us"


def test_stooq_ingestion_bad_csv_for_one_asset_fails_safely():
    def _selective_fetch(url: str) -> str:
        if "qqq.us" in url:
            return _BAD_CSV  # missing Close column — will raise ValueError
        return _FIXTURE_CSV

    adapter = build_stooq_registry_bound_adapter(fetch_fn=_selective_fetch)
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(assets=_STOOQ_ASSETS)

    assert result.total_assets_processed == 4
    assert result.failed_snapshots == 1
    assert result.failed_assets == ("QQQ",)
    assert result.successful_snapshots == 3


# ---------------------------------------------------------------------------
# No-network guarantee
# ---------------------------------------------------------------------------


def test_stooq_ingestion_fixture_never_calls_network(monkeypatch):
    import urllib.request as _urllib

    def _fail(_url: str, **_kwargs: object) -> object:
        raise AssertionError(
            "Network call detected — integration tests must not touch the internet"
        )

    monkeypatch.setattr(_urllib, "urlopen", _fail)

    adapter = _build_fixture_adapter()
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(assets=_STOOQ_ASSETS)

    assert result.successful_snapshots == 4


__all__ = [name for name in globals() if not name.startswith("_")]
