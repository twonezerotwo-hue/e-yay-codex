"""
End-to-end replay tests for Stooq fixture data.

Pipeline:
  build_stooq_registry_bound_adapter(fixture) -> ProviderIngestionService
  -> SnapshotStore (tmp JSONL) -> SnapshotReplayService.replay_snapshot
  -> SnapshotReplayService.build_rolling_backtest_diagnostics

All tests run fully offline — no network calls are made.
"""
from __future__ import annotations

import urllib.request as _urllib
from pathlib import Path

import pytest

from app.domain import AssetCode
from app.domain.assets import get_asset_definition
from app.providers.stooq_adapter import build_stooq_registry_bound_adapter
from app.services import MarketSnapshotService, ProviderIngestionService
from app.services.snapshot_replay_service import SnapshotReplayService
from app.storage import SnapshotStore

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_FIXTURE_CSV = """\
Date,Open,High,Low,Close,Volume
2026-05-27,483.50,488.00,482.00,486.75,61234000
"""

_STOOQ_ASSET_CODES = (AssetCode.QQQ, AssetCode.HYG, AssetCode.JNK, AssetCode.FXI)
_STOOQ_ASSETS = tuple(get_asset_definition(code) for code in _STOOQ_ASSET_CODES)

_SNAPSHOT_METADATA = {
    "source_registry_version": "1.0",
    "feature_registry_version": "1.0",
    "missing_sources": [],
    "stale_sources": [],
    "report_type": "stooq_paper_ingestion",
    "mode": "PAPER_SAFE",
    "execution_mode": "PAPER_ONLY",
}


def _fixture_fetch(_url: str) -> str:
    return _FIXTURE_CSV


class _FakeSession:
    def add(self, _: object) -> None:
        pass

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _build_populated_store(tmp_path: Path) -> tuple[SnapshotStore, str]:
    """Persist one Stooq fixture snapshot; return (store, snapshot_id)."""
    store = SnapshotStore(tmp_path / "stooq_paper_snapshots.jsonl")
    adapter = build_stooq_registry_bound_adapter(fetch_fn=_fixture_fetch)
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), adapter
    ).run(
        assets=_STOOQ_ASSETS,
        persist_result=True,
        snapshot_store=store,
        snapshot_metadata=_SNAPSHOT_METADATA,
    )
    assert result.stored_snapshot_metadata is not None
    return store, str(result.stored_snapshot_metadata["snapshot_id"])


# ---------------------------------------------------------------------------
# replay_snapshot — paper-safe guardrails
# ---------------------------------------------------------------------------


def test_stooq_replay_result_mode_is_paper_safe(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.mode == "PAPER_SAFE"


def test_stooq_replay_result_execution_mode_is_paper_only(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.execution_mode == "PAPER_ONLY"


def test_stooq_replay_result_decision_permission_is_no_execution(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.decision_permission == "NO_EXECUTION"


# ---------------------------------------------------------------------------
# replay_snapshot — source observations contain Stooq source IDs
# ---------------------------------------------------------------------------


def test_stooq_replay_source_observations_contain_all_four_stooq_ids(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    obs_keys = set(result.source_observations.keys())
    assert {"stooq_qqq_daily", "stooq_hyg_daily", "stooq_jnk_daily", "stooq_fxi_daily"}.issubset(obs_keys)


def test_stooq_replay_snapshots_have_stooq_daily_csv_source_name(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    source_names = {snap.source_name for snap in result.snapshots}
    assert "stooq_daily_csv" in source_names


def test_stooq_replay_all_four_assets_present(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    asset_codes = {snap.asset_symbol for snap in result.snapshots}
    assert asset_codes == set(_STOOQ_ASSET_CODES)


# ---------------------------------------------------------------------------
# replay_snapshot — no network calls
# ---------------------------------------------------------------------------


def test_stooq_replay_makes_no_network_calls(tmp_path: Path, monkeypatch):
    store, snapshot_id = _build_populated_store(tmp_path)

    def _fail(_url: str, **_kwargs: object) -> object:
        raise AssertionError("Network call detected — replay must not touch the internet")

    monkeypatch.setattr(_urllib, "urlopen", _fail)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.decision_permission == "NO_EXECUTION"


# ---------------------------------------------------------------------------
# replay_snapshot — downstream pipeline smoke check
# ---------------------------------------------------------------------------


def test_stooq_replay_risk_engine_result_is_present(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.risk_engine_result is not None
    assert result.risk_engine_result.risk_action is not None


def test_stooq_replay_ceo_report_is_present(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.ceo_report is not None


def test_stooq_replay_snapshot_id_is_stable(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    result = SnapshotReplayService(store).replay_snapshot(snapshot_id)
    assert result.snapshot_id == snapshot_id


# ---------------------------------------------------------------------------
# build_rolling_backtest_diagnostics — single snapshot
# ---------------------------------------------------------------------------


def test_stooq_rolling_backtest_processes_one_snapshot(tmp_path: Path):
    store, _ = _build_populated_store(tmp_path)
    diag = SnapshotReplayService(store).build_rolling_backtest_diagnostics()
    assert diag.total_snapshots_requested == 1
    assert diag.successful_replays == 1
    assert diag.failed_replays == 0


def test_stooq_rolling_backtest_ordered_snapshot_ids_has_one_entry(tmp_path: Path):
    store, snapshot_id = _build_populated_store(tmp_path)
    diag = SnapshotReplayService(store).build_rolling_backtest_diagnostics()
    assert len(diag.ordered_snapshot_ids) == 1
    assert diag.ordered_snapshot_ids[0] == snapshot_id


def test_stooq_rolling_backtest_no_comparisons_for_single_snapshot(tmp_path: Path):
    store, _ = _build_populated_store(tmp_path)
    diag = SnapshotReplayService(store).build_rolling_backtest_diagnostics()
    assert diag.comparisons_generated == 0
    assert diag.comparison_results == ()


def test_stooq_rolling_backtest_drift_trend_score_is_present(tmp_path: Path):
    store, _ = _build_populated_store(tmp_path)
    diag = SnapshotReplayService(store).build_rolling_backtest_diagnostics()
    assert diag.drift_trend_score is not None


def test_stooq_rolling_backtest_source_gap_leaderboard_is_present(tmp_path: Path):
    store, _ = _build_populated_store(tmp_path)
    diag = SnapshotReplayService(store).build_rolling_backtest_diagnostics()
    assert diag.source_gap_recurrence_leaderboard is not None


__all__ = [name for name in globals() if not name.startswith("_")]
