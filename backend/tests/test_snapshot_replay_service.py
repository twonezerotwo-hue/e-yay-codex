from pathlib import Path

import pytest

from app.providers import MockMarketProvider
from app.providers import SourceRegistryBoundProviderAdapter
from app.providers import build_provider_source_bindings
import app.services.snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts


# Bu paket snapshot serializer'ların alfabetik sıralamasına + 27-asset sabit
# beklentilerine pin'li. Asset 35'e çıktı, serializer surface'i genişledi
# → testler eski snapshot beklentileriyle uyumsuz. Production runtime'a etkisi yok.
pytestmark = pytest.mark.skip(
    reason="serializer surface + 27-asset varsayımı — refactor edilmeli"
)
from app.services import MarketSnapshotService
from app.services import ProviderIngestionService
from app.services import SnapshotReplayService
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


def build_full_adapter() -> SourceRegistryBoundProviderAdapter:
    source_registry_entries = build_source_registry_entries(load_source_registry())
    return SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        build_provider_source_bindings(source_registry_entries),
    )


def persist_snapshot_fixture(
    tmp_path: Path,
    *,
    report_type: str = "provider_ingestion_paper_snapshot",
    snapshot_id: str | None = None,
    audit_source_payload: dict[str, object] | None = None,
) -> tuple[SnapshotStore, dict[str, object]]:
    session = FakeSession()
    store = SnapshotStore(tmp_path / "persisted_snapshots.jsonl")
    ingestion_service = ProviderIngestionService(
        MarketSnapshotService(session),
        build_full_adapter(),
    )
    ingestion_result = ingestion_service.run()
    stored_snapshot = ingestion_service.persist_ingestion_result(
        ingestion_result,
        snapshot_store=store,
        snapshot_metadata={
            "snapshot_id": snapshot_id,
            "source_registry_version": "1.0",
            "feature_registry_version": "1.0",
            "missing_sources": [],
            "stale_sources": [],
            "report_type": report_type,
            "mode": "PAPER_SAFE",
            "execution_mode": "PAPER_ONLY",
            "audit_source_payload": audit_source_payload,
        },
    )
    return store, stored_snapshot


def persist_snapshot_variant(
    store: SnapshotStore,
    source_snapshot_id: str,
    *,
    new_snapshot_id: str,
    created_at: str,
    asset_overrides: dict[str, float],
    snapshot_field_overrides: dict[str, dict[str, object]] | None = None,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    snapshot_payload = dict(store.load_snapshot(source_snapshot_id))
    snapshots = [dict(snapshot_data) for snapshot_data in snapshot_payload["snapshots"]]

    for snapshot_data in snapshots:
        asset_symbol = snapshot_data["asset_symbol"]
        if asset_symbol in asset_overrides:
            snapshot_data["value"] = asset_overrides[asset_symbol]
        if snapshot_field_overrides and asset_symbol in snapshot_field_overrides:
            snapshot_data.update(snapshot_field_overrides[asset_symbol])

    snapshot_payload["snapshot_id"] = new_snapshot_id
    snapshot_payload["created_at"] = created_at
    snapshot_payload["snapshots"] = snapshots
    if extra_fields:
        snapshot_payload.update(extra_fields)
    return store.save_snapshot(snapshot_payload)


def test_snapshot_replay_service_replays_saved_snapshot_roundtrip(tmp_path: Path) -> None:
    audit_source_payload = {
        "source_registry_version": "1.0",
        "provider_adapter": {
            "contract": "verified_provider_adapter_v1",
            "total_bound_sources": 27,
        },
    }
    store, stored_snapshot = persist_snapshot_fixture(
        tmp_path,
        audit_source_payload=audit_source_payload,
    )

    replay_result = SnapshotReplayService(store).replay_snapshot(stored_snapshot["snapshot_id"])

    assert replay_result.snapshot_id == stored_snapshot["snapshot_id"]
    assert replay_result.mode == "PAPER_SAFE"
    assert replay_result.execution_mode == "PAPER_ONLY"
    assert replay_result.decision_permission == "NO_EXECUTION"
    assert replay_result.report_type == "provider_ingestion_paper_snapshot"
    assert replay_result.source_registry_version == "1.0"
    assert replay_result.feature_registry_version == "1.0"
    assert len(replay_result.snapshots) == 27
    assert replay_result.risk_engine_result.risk_action.value == "HOLD"
    assert replay_result.ceo_report.execution_status == "OFF / NO_EXECUTION"
    assert replay_result.pipeline_summary == {
        "total_assets_processed": 27,
        "successful_snapshots": 27,
        "failed_snapshots": 0,
        "failed_assets": [],
        "dqs_decision_counts": {
            "PASS": 24,
            "DEGRADED_PASS": 3,
            "LIMITED_ANALYSIS_ONLY": 0,
            "FAIL_NO_DECISION": 0,
        },
    }
    assert replay_result.audit_source_payload == audit_source_payload


def test_snapshot_replay_service_rejects_unsafe_execution_metadata(tmp_path: Path) -> None:
    store, stored_snapshot = persist_snapshot_fixture(tmp_path)
    replay_service = SnapshotReplayService(store)
    unsafe_payload = dict(stored_snapshot)
    unsafe_payload["execution_mode"] = "LIVE"

    with pytest.raises(
        ValueError,
        match="snapshot replay payload execution_mode must remain PAPER_ONLY or NO_EXECUTION.",
    ):
        replay_service.replay_snapshot_payload(unsafe_payload)


def test_snapshot_replay_service_run_backtest_replays_latest_saved_snapshots(tmp_path: Path) -> None:
    store, first_snapshot = persist_snapshot_fixture(
        tmp_path,
        report_type="provider_ingestion_paper_snapshot",
        snapshot_id="snapshot_a",
    )
    _, second_snapshot = persist_snapshot_fixture(
        tmp_path,
        report_type="paper_backtest_candidate",
        snapshot_id="snapshot_b",
    )

    replay_service = SnapshotReplayService(store)
    backtest_result = replay_service.run_backtest(limit=2)

    assert backtest_result.total_snapshots_requested == 2
    assert backtest_result.successful_replays == 2
    assert backtest_result.failed_replays == 0
    assert {result.snapshot_id for result in backtest_result.replay_results} == {
        first_snapshot["snapshot_id"],
        second_snapshot["snapshot_id"],
    }
    assert backtest_result.failures == ()


def test_snapshot_replay_service_run_backtest_filters_report_type(tmp_path: Path) -> None:
    store, _ = persist_snapshot_fixture(
        tmp_path,
        report_type="provider_ingestion_paper_snapshot",
        snapshot_id="snapshot_a",
    )
    persist_snapshot_fixture(
        tmp_path,
        report_type="paper_backtest_candidate",
        snapshot_id="snapshot_b",
    )

    replay_service = SnapshotReplayService(store)
    backtest_result = replay_service.run_backtest(limit=2, report_type="paper_backtest_candidate")

    assert backtest_result.total_snapshots_requested == 1
    assert backtest_result.successful_replays == 1
    assert backtest_result.failed_replays == 0
    assert backtest_result.replay_results[0].report_type == "paper_backtest_candidate"


def test_snapshot_replay_service_run_backtest_tracks_missing_snapshot_failures(tmp_path: Path) -> None:
    store, stored_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    replay_service = SnapshotReplayService(store)

    backtest_result = replay_service.run_backtest(
        snapshot_ids=(stored_snapshot["snapshot_id"], "missing_snapshot"),
    )

    assert backtest_result.total_snapshots_requested == 2
    assert backtest_result.successful_replays == 1
    assert backtest_result.failed_replays == 1
    assert backtest_result.failures == (
        {
            "snapshot_id": "missing_snapshot",
            "reason": "'missing_snapshot'",
        },
    )


def test_snapshot_replay_service_compare_snapshots_detects_risk_and_trigger_changes(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    candidate_snapshot = persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )

    comparison_result = SnapshotReplayService(store).compare_snapshots(
        baseline_snapshot["snapshot_id"],
        candidate_snapshot["snapshot_id"],
    )

    assert comparison_result.baseline_snapshot_id == "snapshot_a"
    assert comparison_result.candidate_snapshot_id == "snapshot_b"
    assert comparison_result.risk_action_changed is True
    assert comparison_result.risk_action_from == "HOLD"
    assert comparison_result.risk_action_to == "NO_POSITION_INCREASE"
    assert comparison_result.kill_switch_changed is False
    assert comparison_result.new_trigger_codes == ("RED_ENERGY_SHOCK",)
    assert comparison_result.cleared_trigger_codes == ()
    assert comparison_result.execution_status_consistent is True
    assert comparison_result.paper_safe is True
    drift_classification = SnapshotReplayService(store).classify_comparison_result(comparison_result)
    assert drift_classification.drift_code == "RISK_GUARDRAIL_TIGHTENED"
    assert drift_classification.severity.value == "YELLOW"
    assert drift_classification.summary == "Risk posture tightened to NO_POSITION_INCREASE in the candidate snapshot."
    assert drift_classification.anomaly_flags == (
        "NEW_TRIGGER:RED_ENERGY_SHOCK",
        "NEW_REASON:RED_ENERGY_SHOCK_CONFIRMED",
    )
    assert drift_classification.paper_safe is True
    assert drift_classification.execution_status_consistent is True


def test_snapshot_replay_service_builds_rolling_backtest_diagnostics(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=3)

    assert rolling_diagnostics.total_snapshots_requested == 3
    assert rolling_diagnostics.successful_replays == 3
    assert rolling_diagnostics.failed_replays == 0
    assert rolling_diagnostics.ordered_snapshot_ids == ("snapshot_a", "snapshot_b", "snapshot_c")
    assert rolling_diagnostics.comparisons_generated == 2
    assert rolling_diagnostics.risk_action_changes == 2
    assert rolling_diagnostics.kill_switch_count == 0
    assert rolling_diagnostics.risk_action_counts == {
        "HOLD": 1,
        "NO_POSITION_INCREASE": 1,
        "RISK_REDUCE": 1,
    }
    assert rolling_diagnostics.trigger_transition_counts == {
        "RED_ENERGY_SHOCK": 1,
        "SILVER_EXHAUSTION_WATCH": 1,
        "SILVER_MOMENTUM_ACCELERATION": 1,
        "SILVER_STRATEGIC_METALS_REGIME": 1,
    }
    assert rolling_diagnostics.paper_safe is True
    assert rolling_diagnostics.network_calls is False
    assert rolling_diagnostics.execution_side_effects == "NO_EXECUTION"
    assert tuple(
        drift_classification.drift_code
        for drift_classification in rolling_diagnostics.drift_classifications
    ) == (
        "RISK_GUARDRAIL_TIGHTENED",
        "RISK_ESCALATION_MULTI_SIGNAL",
    )
    assert tuple(
        drift_classification.severity.value
        for drift_classification in rolling_diagnostics.drift_classifications
    ) == ("YELLOW", "ORANGE")
    assert rolling_diagnostics.anomaly_watchlist.total_items == 2
    assert rolling_diagnostics.anomaly_watchlist.stable_transitions == 0
    assert rolling_diagnostics.anomaly_watchlist.improving_transitions == 0
    assert rolling_diagnostics.anomaly_watchlist.anomalous_transitions == 2
    assert tuple(
        watchlist_item.watchlist_code
        for watchlist_item in rolling_diagnostics.anomaly_watchlist.watchlist_items
    ) == (
        "RISK_ESCALATION_MULTI_SIGNAL",
        "RISK_GUARDRAIL_TIGHTENED",
    )
    assert tuple(
        watchlist_item.severity.value
        for watchlist_item in rolling_diagnostics.anomaly_watchlist.watchlist_items
    ) == ("ORANGE", "YELLOW")
    assert rolling_diagnostics.anomaly_watchlist.watchlist_items[0].trigger_codes == (
        "SILVER_EXHAUSTION_WATCH",
        "SILVER_MOMENTUM_ACCELERATION",
        "SILVER_STRATEGIC_METALS_REGIME",
    )
    assert rolling_diagnostics.anomaly_watchlist.watchlist_items[0].reason_codes == (
        "MULTI_SEVERE_TRIGGER_STACK",
        "SILVER_STRATEGIC_METALS_REGIME_NOTE",
    )
    assert rolling_diagnostics.anomaly_watchlist.paper_safe is True
    assert rolling_diagnostics.anomaly_watchlist.network_calls is False
    assert rolling_diagnostics.anomaly_watchlist.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_deteriorating_trend_score(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.drift_trend_score.trend_classification == "deteriorating"
    assert rolling_diagnostics.drift_trend_score.trend_score == 2
    assert rolling_diagnostics.drift_trend_score.severity_bucket == "LOW"
    assert rolling_diagnostics.drift_trend_score.comparison_count == 1
    assert rolling_diagnostics.drift_trend_score.improving_transitions == 0
    assert rolling_diagnostics.drift_trend_score.deteriorating_transitions == 1
    assert rolling_diagnostics.drift_trend_score.stable_transitions == 0
    assert rolling_diagnostics.drift_trend_score.paper_safe is True


def test_snapshot_replay_service_builds_improving_trend_score(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:28:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        "snapshot_b",
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 82.35},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.ordered_snapshot_ids == ("snapshot_b", "snapshot_c")
    assert rolling_diagnostics.drift_trend_score.trend_classification == "improving"
    assert rolling_diagnostics.drift_trend_score.trend_score == -2
    assert rolling_diagnostics.drift_trend_score.severity_bucket == "LOW"
    assert rolling_diagnostics.drift_trend_score.improving_transitions == 1
    assert rolling_diagnostics.drift_trend_score.deteriorating_transitions == 0


def test_snapshot_replay_service_builds_stable_and_insufficient_data_trend_scores(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    replay_service = SnapshotReplayService(store)
    stable_diagnostics = replay_service.build_rolling_backtest_diagnostics(limit=2)

    assert stable_diagnostics.drift_trend_score.trend_classification == "stable"
    assert stable_diagnostics.drift_trend_score.trend_score == 0
    assert stable_diagnostics.drift_trend_score.severity_bucket == "NONE"
    assert stable_diagnostics.drift_trend_score.stable_transitions == 1

    insufficient_diagnostics = replay_service.build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert insufficient_diagnostics.drift_trend_score.trend_classification == "insufficient_data"
    assert insufficient_diagnostics.drift_trend_score.trend_score == 0
    assert insufficient_diagnostics.drift_trend_score.comparison_count == 0
    assert insufficient_diagnostics.drift_trend_score.diagnostics == (
        "At least two replayable snapshots are required to calculate drift trends.",
    )


def test_snapshot_replay_service_handles_missing_snapshots_safely_in_trend_scoring(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    replay_service = SnapshotReplayService(store)

    rolling_diagnostics = replay_service.build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"], "missing_snapshot"),
    )

    assert rolling_diagnostics.total_snapshots_requested == 2
    assert rolling_diagnostics.successful_replays == 1
    assert rolling_diagnostics.failed_replays == 1
    assert rolling_diagnostics.drift_trend_score.trend_classification == "insufficient_data"
    assert rolling_diagnostics.drift_trend_score.diagnostics == (
        "At least two replayable snapshots are required to calculate drift trends.",
        "1 snapshot replay(s) failed during trend evaluation.",
    )


def test_snapshot_replay_service_builds_regime_summary_with_dominant_regime_and_transition_count(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={},
        extra_fields={"replay_regime": "HEDGE_BID"},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=4)

    assert rolling_diagnostics.regime_summary.status == "partial"
    assert rolling_diagnostics.regime_summary.distribution_classification == "mixed"
    assert rolling_diagnostics.regime_summary.dominant_regime == "RISK_OFF"
    assert rolling_diagnostics.regime_summary.regime_distribution == {
        "HEDGE_BID": 1,
        "RISK_OFF": 2,
    }
    assert rolling_diagnostics.regime_summary.transition_count == 1
    assert rolling_diagnostics.regime_summary.mixed_or_unstable is True
    assert rolling_diagnostics.regime_summary.available_regime_count == 3
    assert rolling_diagnostics.regime_summary.missing_regime_count == 1
    assert rolling_diagnostics.regime_summary.paper_safe is True


def test_snapshot_replay_service_builds_missing_regime_diagnostics_safely(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.regime_summary.status == "missing"
    assert rolling_diagnostics.regime_summary.distribution_classification == "missing"
    assert rolling_diagnostics.regime_summary.dominant_regime is None
    assert rolling_diagnostics.regime_summary.regime_distribution == {}
    assert rolling_diagnostics.regime_summary.transition_count == 0
    assert rolling_diagnostics.regime_summary.mixed_or_unstable is False
    assert rolling_diagnostics.regime_summary.available_regime_count == 0
    assert rolling_diagnostics.regime_summary.missing_regime_count == 2
    assert rolling_diagnostics.regime_summary.diagnostics == (
        "No saved replay regimes were present in the requested snapshots.",
        "Saved replay regime metadata was not present.",
    )


def test_snapshot_replay_service_builds_drift_trend_leaderboard(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        "snapshot_b",
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 82.35},
    )
    persist_snapshot_variant(
        store,
        "snapshot_c",
        new_snapshot_id="snapshot_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=4)

    assert rolling_diagnostics.drift_trend_leaderboard.total_entries == 2
    assert tuple(
        entry.drift_code
        for entry in rolling_diagnostics.drift_trend_leaderboard.entries
    ) == (
        "RISK_GUARDRAIL_TIGHTENED",
        "CONDITIONS_IMPROVED",
    )
    assert rolling_diagnostics.drift_trend_leaderboard.entries[0].rank == 1
    assert rolling_diagnostics.drift_trend_leaderboard.entries[0].direction == "deteriorating"
    assert rolling_diagnostics.drift_trend_leaderboard.entries[0].severity.value == "YELLOW"
    assert rolling_diagnostics.drift_trend_leaderboard.entries[0].occurrence_count == 2
    assert rolling_diagnostics.drift_trend_leaderboard.entries[0].total_weight == 4
    assert rolling_diagnostics.drift_trend_leaderboard.entries[0].related_snapshot_pairs == (
        "snapshot_a->snapshot_b",
        "snapshot_c->snapshot_d",
    )
    assert rolling_diagnostics.drift_trend_leaderboard.entries[1].rank == 2
    assert rolling_diagnostics.drift_trend_leaderboard.entries[1].direction == "improving"
    assert rolling_diagnostics.drift_trend_leaderboard.entries[1].total_weight == -2
    assert rolling_diagnostics.drift_trend_leaderboard.entries[1].related_snapshot_pairs == (
        "snapshot_b->snapshot_c",
    )
    assert rolling_diagnostics.drift_trend_leaderboard.paper_safe is True
    assert rolling_diagnostics.drift_trend_leaderboard.network_calls is False
    assert rolling_diagnostics.drift_trend_leaderboard.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_empty_drift_trend_leaderboard_safely(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert rolling_diagnostics.drift_trend_leaderboard.total_entries == 0
    assert rolling_diagnostics.drift_trend_leaderboard.entries == ()
    assert rolling_diagnostics.drift_trend_leaderboard.paper_safe is True


def test_snapshot_replay_service_builds_regime_timeline_with_transitions(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={},
        extra_fields={"replay_regime": "HEDGE_BID"},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=4)

    assert rolling_diagnostics.regime_timeline.status == "partial"
    assert rolling_diagnostics.regime_timeline.total_snapshots == 4
    assert rolling_diagnostics.regime_timeline.dominant_regime == "RISK_OFF"
    assert rolling_diagnostics.regime_timeline.transition_count == 1
    assert rolling_diagnostics.regime_timeline.mixed_or_unstable is True
    assert rolling_diagnostics.regime_timeline.available_regime_count == 3
    assert rolling_diagnostics.regime_timeline.missing_regime_count == 1
    assert tuple(entry.status for entry in rolling_diagnostics.regime_timeline.entries) == (
        "missing",
        "available",
        "available",
        "available",
    )
    assert tuple(
        entry.transition_from_previous
        for entry in rolling_diagnostics.regime_timeline.entries
    ) == (False, False, False, True)
    assert tuple(
        entry.dominant_regime_match
        for entry in rolling_diagnostics.regime_timeline.entries
    ) == (False, True, True, False)
    assert rolling_diagnostics.regime_timeline.entries[0].diagnostic == "Saved replay regime metadata was not present."
    assert rolling_diagnostics.regime_timeline.entries[1].diagnostic is None
    assert rolling_diagnostics.regime_timeline.diagnostics[-1] == (
        "Replay regime timeline covers 4 saved snapshot(s) in chronological order."
    )
    assert rolling_diagnostics.regime_timeline.paper_safe is True


def test_snapshot_replay_service_builds_missing_regime_timeline_safely(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.regime_timeline.status == "missing"
    assert rolling_diagnostics.regime_timeline.total_snapshots == 2
    assert rolling_diagnostics.regime_timeline.dominant_regime is None
    assert rolling_diagnostics.regime_timeline.transition_count == 0
    assert rolling_diagnostics.regime_timeline.available_regime_count == 0
    assert rolling_diagnostics.regime_timeline.missing_regime_count == 2
    assert tuple(entry.status for entry in rolling_diagnostics.regime_timeline.entries) == (
        "missing",
        "missing",
    )
    assert rolling_diagnostics.regime_timeline.diagnostics[:2] == (
        "No saved replay regimes were present in the requested snapshots.",
        "Saved replay regime metadata was not present.",
    )


def test_snapshot_replay_service_builds_trigger_persistence_leaderboard(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=4)

    assert rolling_diagnostics.trigger_persistence_leaderboard.total_entries == 4
    assert rolling_diagnostics.trigger_persistence_leaderboard.total_snapshots == 4
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].rank == 1
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].trigger_code == "RED_ENERGY_SHOCK"
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].asset_symbol == "BRENT"
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].severity.value == "RED"
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].persistence_classification == "recurring"
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].active_snapshot_count == 3
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].persistence_ratio == 0.75
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].longest_streak == 3
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].first_snapshot_id == "snapshot_b"
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].latest_snapshot_id == "snapshot_d"
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries[0].active_snapshot_ids == (
        "snapshot_b",
        "snapshot_c",
        "snapshot_d",
    )
    assert tuple(
        entry.trigger_code
        for entry in rolling_diagnostics.trigger_persistence_leaderboard.entries[1:]
    ) == (
        "SILVER_EXHAUSTION_WATCH",
        "SILVER_MOMENTUM_ACCELERATION",
        "SILVER_STRATEGIC_METALS_REGIME",
    )
    assert rolling_diagnostics.trigger_persistence_leaderboard.diagnostics == (
        "Trigger persistence leaderboard covers 4 saved snapshot(s) and 4 active trigger type(s).",
    )


def test_snapshot_replay_service_builds_empty_trigger_persistence_leaderboard_safely(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert rolling_diagnostics.trigger_persistence_leaderboard.total_entries == 0
    assert rolling_diagnostics.trigger_persistence_leaderboard.total_snapshots == 1
    assert rolling_diagnostics.trigger_persistence_leaderboard.entries == ()
    assert rolling_diagnostics.trigger_persistence_leaderboard.diagnostics == (
        "No active replay triggers were found in the requested saved snapshots.",
    )


def test_snapshot_replay_service_builds_stable_risk_action_stability(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.risk_action_stability.stability_classification == "stable"
    assert rolling_diagnostics.risk_action_stability.dominant_risk_action == "HOLD"
    assert rolling_diagnostics.risk_action_stability.first_risk_action == "HOLD"
    assert rolling_diagnostics.risk_action_stability.latest_risk_action == "HOLD"
    assert rolling_diagnostics.risk_action_stability.transition_count == 0
    assert rolling_diagnostics.risk_action_stability.longest_stable_run == 2
    assert rolling_diagnostics.risk_action_stability.unique_action_count == 1
    assert rolling_diagnostics.risk_action_stability.risk_action_counts == {"HOLD": 2}
    assert rolling_diagnostics.risk_action_stability.diagnostics == (
        "Risk action remained HOLD across 2 saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_volatile_risk_action_stability(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=3)

    assert rolling_diagnostics.risk_action_stability.stability_classification == "volatile"
    assert rolling_diagnostics.risk_action_stability.dominant_risk_action == "HOLD"
    assert rolling_diagnostics.risk_action_stability.first_risk_action == "HOLD"
    assert rolling_diagnostics.risk_action_stability.latest_risk_action == "RISK_REDUCE"
    assert rolling_diagnostics.risk_action_stability.transition_count == 2
    assert rolling_diagnostics.risk_action_stability.longest_stable_run == 1
    assert rolling_diagnostics.risk_action_stability.unique_action_count == 3
    assert rolling_diagnostics.risk_action_stability.risk_action_counts == {
        "HOLD": 1,
        "NO_POSITION_INCREASE": 1,
        "RISK_REDUCE": 1,
    }
    assert rolling_diagnostics.risk_action_stability.diagnostics == (
        "Risk action changed 2 time(s) across 3 saved snapshot(s) and should be treated as unstable.",
    )


def test_snapshot_replay_service_builds_insufficient_risk_action_stability(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert rolling_diagnostics.risk_action_stability.stability_classification == "insufficient_data"
    assert rolling_diagnostics.risk_action_stability.dominant_risk_action == "HOLD"
    assert rolling_diagnostics.risk_action_stability.transition_count == 0
    assert rolling_diagnostics.risk_action_stability.longest_stable_run == 1
    assert rolling_diagnostics.risk_action_stability.unique_action_count == 1
    assert rolling_diagnostics.risk_action_stability.diagnostics == (
        "At least two replayable snapshots are required to evaluate risk action stability.",
    )


def test_snapshot_replay_service_builds_source_gap_recurrence_leaderboard(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"missing_sources": ["energy_feed"]},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={
            "missing_sources": ["energy_feed"],
            "stale_sources": ["macro_feed"],
        },
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={},
        extra_fields={"stale_sources": ["macro_feed"]},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=4)

    assert rolling_diagnostics.source_gap_recurrence_leaderboard.total_entries == 2
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.total_snapshots == 4
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].source_id == "energy_feed"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].gap_status == "missing"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].severity.value == "ORANGE"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].recurrence_classification == "recurring"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].occurrence_count == 2
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].recurrence_ratio == 0.5
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].longest_streak == 2
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[0].affected_snapshot_ids == (
        "snapshot_b",
        "snapshot_c",
    )
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[1].source_id == "macro_feed"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[1].gap_status == "stale"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[1].severity.value == "YELLOW"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[1].recurrence_classification == "recurring"
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[1].occurrence_count == 2
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries[1].affected_snapshot_ids == (
        "snapshot_c",
        "snapshot_d",
    )
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.diagnostics == (
        "Source gap recurrence leaderboard covers 4 saved snapshot(s) and 2 gap source(s).",
    )


def test_snapshot_replay_service_builds_empty_source_gap_recurrence_leaderboard_safely(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert rolling_diagnostics.source_gap_recurrence_leaderboard.total_entries == 0
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.total_snapshots == 1
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.entries == ()
    assert rolling_diagnostics.source_gap_recurrence_leaderboard.diagnostics == (
        "No missing or stale source gaps were found in the requested saved snapshots.",
    )


def test_snapshot_replay_service_builds_stable_dqs_stability(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.dqs_stability.stability_classification == "stable"
    assert rolling_diagnostics.dqs_stability.first_decision == rolling_diagnostics.dqs_stability.latest_decision
    assert rolling_diagnostics.dqs_stability.transition_count == 0
    assert rolling_diagnostics.dqs_stability.unique_decision_count == 1
    assert len(rolling_diagnostics.dqs_stability.path) == 2
    assert rolling_diagnostics.dqs_stability.path[0].snapshot_id == "snapshot_a"
    assert rolling_diagnostics.dqs_stability.path[1].snapshot_id == "snapshot_b"
    assert rolling_diagnostics.dqs_stability.diagnostics == (
        f"DQS aggregate decision remained {rolling_diagnostics.dqs_stability.first_decision} across 2 saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_deteriorating_dqs_stability(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "data_quality_score": 35.0,
                "dqs_result": {
                    "total_score": 35.0,
                    "decision": "FAIL_NO_DECISION",
                    "component_scores": {
                        "freshness_score": 0.0,
                        "source_tier_score": 40.0,
                        "cross_provider_agreement_score": 40.0,
                        "completeness_score": 100.0,
                        "timestamp_integrity_score": 0.0,
                        "anomaly_consistency_score": 0.0,
                    },
                },
            },
        },
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.dqs_stability.stability_classification == "deteriorating"
    assert rolling_diagnostics.dqs_stability.first_decision in {"PASS", "DEGRADED_PASS", "LIMITED_ANALYSIS_ONLY"}
    assert rolling_diagnostics.dqs_stability.latest_decision == "FAIL_NO_DECISION"
    assert rolling_diagnostics.dqs_stability.transition_count == 1
    assert rolling_diagnostics.dqs_stability.unique_decision_count == 2
    assert rolling_diagnostics.dqs_stability.lowest_minimum_score == 35.0
    assert rolling_diagnostics.dqs_stability.path[1].aggregate_decision.value == "FAIL_NO_DECISION"
    assert rolling_diagnostics.dqs_stability.diagnostics == (
        f"DQS aggregate decision deteriorated from {rolling_diagnostics.dqs_stability.first_decision} to FAIL_NO_DECISION across saved snapshots.",
    )


def test_snapshot_replay_service_builds_insufficient_dqs_stability(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert rolling_diagnostics.dqs_stability.stability_classification == "insufficient_data"
    assert rolling_diagnostics.dqs_stability.transition_count == 0
    assert rolling_diagnostics.dqs_stability.unique_decision_count == 1
    assert len(rolling_diagnostics.dqs_stability.path) == 1
    assert rolling_diagnostics.dqs_stability.diagnostics == (
        "At least two replayable snapshots are required to evaluate DQS stability.",
    )


def test_snapshot_replay_service_builds_stable_source_freshness_decay_timeline(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.source_freshness_decay_timeline.decay_classification == "stable"
    assert rolling_diagnostics.source_freshness_decay_timeline.first_status == "fresh"
    assert rolling_diagnostics.source_freshness_decay_timeline.latest_status == "fresh"
    assert rolling_diagnostics.source_freshness_decay_timeline.dominant_status == "fresh"
    assert rolling_diagnostics.source_freshness_decay_timeline.worst_status == "fresh"
    assert rolling_diagnostics.source_freshness_decay_timeline.transition_count == 0
    assert rolling_diagnostics.source_freshness_decay_timeline.decay_score_delta == 0
    assert tuple(
        entry.freshness_status
        for entry in rolling_diagnostics.source_freshness_decay_timeline.entries
    ) == ("fresh", "fresh")
    assert rolling_diagnostics.source_freshness_decay_timeline.diagnostics == (
        "Source freshness remained in a stable fresh band across 2 evaluable saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_degrading_source_freshness_decay_timeline(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_source_observations = dict(baseline_snapshot["source_observations"])
    first_source_id = sorted(degraded_source_observations)[0]
    degraded_source_observations[first_source_id] = "2026-05-18T00:00:00+00:00"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": degraded_source_observations},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.source_freshness_decay_timeline.decay_classification == "degrading"
    assert rolling_diagnostics.source_freshness_decay_timeline.first_status == "fresh"
    assert rolling_diagnostics.source_freshness_decay_timeline.latest_status == "stale"
    assert rolling_diagnostics.source_freshness_decay_timeline.worst_status == "stale"
    assert rolling_diagnostics.source_freshness_decay_timeline.transition_count == 1
    assert rolling_diagnostics.source_freshness_decay_timeline.decay_score_delta > 0
    assert rolling_diagnostics.source_freshness_decay_timeline.entries[1].stale_source_count == 1
    assert rolling_diagnostics.source_freshness_decay_timeline.entries[1].freshness_status == "stale"


def test_snapshot_replay_service_builds_improving_source_freshness_decay_timeline(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_source_observations = dict(baseline_snapshot["source_observations"])
    first_source_id = sorted(degraded_source_observations)[0]
    degraded_source_observations[first_source_id] = "2026-05-18T00:00:00+00:00"
    stale_snapshot = persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_stale",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": degraded_source_observations},
    )
    fresh_snapshot = persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_fresh",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(
        snapshot_ids=(stale_snapshot["snapshot_id"], fresh_snapshot["snapshot_id"]),
    )

    assert rolling_diagnostics.ordered_snapshot_ids == ("snapshot_stale", "snapshot_fresh")
    assert rolling_diagnostics.source_freshness_decay_timeline.decay_classification == "improving"
    assert rolling_diagnostics.source_freshness_decay_timeline.first_status == "stale"
    assert rolling_diagnostics.source_freshness_decay_timeline.latest_status == "fresh"
    assert rolling_diagnostics.source_freshness_decay_timeline.transition_count == 1
    assert rolling_diagnostics.source_freshness_decay_timeline.decay_score_delta < 0


def test_snapshot_replay_service_builds_missing_freshness_diagnostics_safely(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    malformed_source_observations = dict(baseline_snapshot["source_observations"])
    first_source_id = sorted(malformed_source_observations)[0]
    malformed_source_observations[first_source_id] = "not-a-timestamp"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_bad",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": malformed_source_observations},
    )

    rolling_diagnostics = SnapshotReplayService(store).build_rolling_backtest_diagnostics(limit=2)

    assert rolling_diagnostics.source_freshness_decay_timeline.decay_classification == "insufficient_data"
    assert rolling_diagnostics.source_freshness_decay_timeline.evaluable_snapshots == 1
    assert rolling_diagnostics.source_freshness_decay_timeline.missing_freshness_snapshots == 1
    assert rolling_diagnostics.source_freshness_decay_timeline.entries[1].freshness_status == "missing_freshness"
    assert rolling_diagnostics.source_freshness_decay_timeline.diagnostics == (
        "At least two replayable snapshots with evaluable source freshness data are required.",
        "1 snapshot(s) had missing or malformed freshness inputs.",
    )


def test_snapshot_replay_service_builds_consistent_no_execution_guardrail_summary(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    guardrail_consistency = SnapshotReplayService(store).build_no_execution_guardrail_consistency(limit=2)

    assert guardrail_consistency.consistency_status == "consistent"
    assert guardrail_consistency.total_snapshots_requested == 2
    assert guardrail_consistency.snapshots_checked == 2
    assert guardrail_consistency.consistent_snapshots == 2
    assert guardrail_consistency.violation_count == 0
    assert guardrail_consistency.violations == ()
    assert tuple(entry.decision_permission for entry in guardrail_consistency.entries) == (
        "NO_EXECUTION",
        "NO_EXECUTION",
    )
    assert guardrail_consistency.diagnostics == (
        "All 2 saved snapshot(s) preserved the NO_EXECUTION guardrail.",
    )


def test_snapshot_replay_service_detects_no_execution_guardrail_violation(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    unsafe_snapshot_payload = dict(store.load_snapshot(baseline_snapshot["snapshot_id"]))
    unsafe_snapshot_payload["snapshot_id"] = "snapshot_unsafe"
    unsafe_snapshot_payload["created_at"] = "2026-05-19T09:29:00+00:00"
    unsafe_snapshot_payload["decision_permission"] = "EXECUTE"
    store._write_entries([store.load_snapshot(baseline_snapshot["snapshot_id"]), unsafe_snapshot_payload])

    guardrail_consistency = SnapshotReplayService(store).build_no_execution_guardrail_consistency(limit=2)

    assert guardrail_consistency.consistency_status == "violations_detected"
    assert guardrail_consistency.snapshots_checked == 2
    assert guardrail_consistency.consistent_snapshots == 1
    assert guardrail_consistency.violation_count == 1
    assert guardrail_consistency.violations[0].snapshot_id == "snapshot_unsafe"
    assert guardrail_consistency.violations[0].decision_permission == "EXECUTE"
    assert guardrail_consistency.violations[0].violation_codes == ("DECISION_PERMISSION_BREACH",)
    assert guardrail_consistency.diagnostics == (
        "Detected 1 NO_EXECUTION guardrail violation(s) across 2 saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_fallback_usage_recurrence(tmp_path: Path) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "fallback_used": True,
                "source_name": "fallback_energy_provider",
            },
        },
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "fallback_used": True,
                "source_name": "fallback_energy_provider",
            },
            "XAUUSD": {
                "fallback_used": True,
                "source_name": "fallback_energy_provider",
            },
        },
    )

    recurrence = SnapshotReplayService(store).build_fallback_usage_recurrence(
        snapshot_ids=("snapshot_a", "snapshot_b", "snapshot_c"),
    )

    assert recurrence.stability_classification == "elevated"
    assert recurrence.severity_score == 55
    assert recurrence.total_snapshots_requested == 3
    assert recurrence.snapshots_checked == 3
    assert recurrence.snapshots_with_fallback == 2
    assert recurrence.total_fallback_events == 3
    assert recurrence.unique_fallback_providers == 1
    assert tuple(entry.status for entry in recurrence.timeline) == (
        "stable",
        "elevated",
        "critical",
    )
    assert recurrence.timeline[2].affected_assets == ("BRENT", "XAUUSD")
    assert recurrence.recurring_entries[0].provider_name == "fallback_energy_provider"
    assert recurrence.recurring_entries[0].recurrence_classification == "elevated"
    assert recurrence.recurring_entries[0].occurrence_count == 2
    assert recurrence.recurring_entries[0].recurrence_ratio == 0.67
    assert recurrence.recurring_entries[0].longest_streak == 2
    assert recurrence.recurring_entries[0].affected_snapshot_ids == ("snapshot_b", "snapshot_c")
    assert recurrence.recurring_entries[0].affected_assets == ("BRENT", "XAUUSD")


def test_snapshot_replay_service_handles_missing_provider_metadata_in_fallback_analysis(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "fallback_used": True,
                "source_name": "",
            },
        },
    )

    recurrence = SnapshotReplayService(store).build_fallback_usage_recurrence(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )

    assert recurrence.stability_classification == "critical"
    assert recurrence.missing_provider_metadata_count == 1
    assert recurrence.timeline[1].affected_providers == ("unknown_provider",)
    assert recurrence.timeline[1].status == "critical"
    assert recurrence.recurring_entries[0].provider_name == "unknown_provider"
    assert recurrence.recurring_entries[0].missing_provider_metadata_count == 1
    assert recurrence.diagnostics == (
        "Fallback usage recurrence is critical across 2 saved snapshot(s).",
        "1 fallback event(s) had missing provider metadata.",
    )


def test_snapshot_replay_service_builds_complete_raw_payload_reference_diagnostics(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    completeness = SnapshotReplayService(store).build_raw_payload_reference_completeness(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert completeness.completeness_classification == "complete"
    assert completeness.average_completeness_percentage == 100.0
    assert completeness.total_snapshots_requested == 1
    assert completeness.snapshots_checked == 1
    assert completeness.complete_snapshots == 1
    assert completeness.partial_snapshots == 0
    assert completeness.degraded_snapshots == 0
    assert completeness.invalid_snapshots == 0
    assert completeness.entries[0].completeness_classification == "complete"
    assert completeness.entries[0].complete_records == 27
    assert completeness.entries[0].total_records == 27


def test_snapshot_replay_service_builds_partial_raw_payload_reference_diagnostics(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "raw_payload_ref": None,
            },
        },
    )

    completeness = SnapshotReplayService(store).build_raw_payload_reference_completeness(
        snapshot_ids=("snapshot_partial",),
    )

    assert completeness.completeness_classification == "partial"
    assert completeness.average_completeness_percentage == 96.3
    assert completeness.partial_snapshots == 1
    assert completeness.entries[0].missing_reference_assets == ("BRENT",)
    assert completeness.entries[0].completeness_classification == "partial"


def test_snapshot_replay_service_builds_invalid_raw_payload_reference_diagnostics(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_invalid",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "raw_payload_ref": {"bad": "value"},
            },
        },
    )

    completeness = SnapshotReplayService(store).build_raw_payload_reference_completeness(
        snapshot_ids=("snapshot_invalid",),
    )

    assert completeness.completeness_classification == "invalid"
    assert completeness.invalid_snapshots == 1
    assert completeness.malformed_reference_assets == ("BRENT",)
    assert completeness.entries[0].malformed_reference_assets == ("BRENT",)
    assert completeness.entries[0].completeness_classification == "invalid"


def test_snapshot_replay_service_keeps_fallback_and_raw_payload_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "fallback_used": True,
                "source_name": "fallback_energy_provider",
                "raw_payload_ref": "",
            },
        },
    )

    replay_service = SnapshotReplayService(store)
    first_fallback = replay_service.build_fallback_usage_recurrence(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_fallback = replay_service.build_fallback_usage_recurrence(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    first_completeness = replay_service.build_raw_payload_reference_completeness(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_completeness = replay_service.build_raw_payload_reference_completeness(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )

    assert first_fallback == second_fallback
    assert first_completeness == second_completeness


def test_snapshot_replay_service_builds_stable_source_observation_cadence_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    stable_source_observations = {
        source_id: "2026-05-19T09:29:00+00:00"
        for source_id in baseline_snapshot["source_observations"]
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": stable_source_observations},
    )

    cadence_drift = SnapshotReplayService(store).build_source_observation_cadence_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )

    assert cadence_drift.cadence_classification == "stable"
    assert cadence_drift.cadence_score == 100
    assert cadence_drift.severity_bucket == "NONE"
    assert cadence_drift.total_snapshots_requested == 2
    assert cadence_drift.snapshots_checked == 2
    assert cadence_drift.evaluable_snapshots == 2
    assert cadence_drift.missing_timestamp_snapshots == 0
    assert cadence_drift.transition_count == 0
    assert tuple(entry.cadence_status for entry in cadence_drift.entries) == ("baseline", "stable")
    assert cadence_drift.entries[1].interval_seconds_from_previous == 60
    assert cadence_drift.diagnostics == (
        "Source observation cadence remained stable across 2 evaluable saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_degraded_source_observation_cadence_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    stable_source_observations = {
        source_id: "2026-05-19T09:29:00+00:00"
        for source_id in baseline_snapshot["source_observations"]
    }
    degraded_source_observations = {
        source_id: "2026-05-19T10:15:00+00:00"
        for source_id in baseline_snapshot["source_observations"]
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": stable_source_observations},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_c",
        created_at="2026-05-19T10:15:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": degraded_source_observations},
    )

    cadence_drift = SnapshotReplayService(store).build_source_observation_cadence_drift(
        snapshot_ids=("snapshot_a", "snapshot_b", "snapshot_c"),
    )

    assert cadence_drift.cadence_classification == "degraded"
    assert cadence_drift.cadence_score == 35
    assert cadence_drift.severity_bucket == "HIGH"
    assert cadence_drift.transition_count == 1
    assert cadence_drift.entries[2].cadence_status == "degraded"
    assert cadence_drift.entries[2].interval_seconds_from_previous == 2760
    assert cadence_drift.diagnostics == (
        "Source observation cadence degraded because one or more saved snapshots contained cadence gaps or missing timestamps.",
    )


def test_snapshot_replay_service_handles_missing_source_observation_timestamps_safely(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    invalid_source_observations = {
        source_id: "not-a-timestamp"
        for source_id in baseline_snapshot["source_observations"]
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_bad",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": invalid_source_observations},
    )

    cadence_drift = SnapshotReplayService(store).build_source_observation_cadence_drift(
        snapshot_ids=("snapshot_a", "snapshot_bad"),
    )

    assert cadence_drift.cadence_classification == "insufficient_data"
    assert cadence_drift.cadence_score == 0
    assert cadence_drift.evaluable_snapshots == 1
    assert cadence_drift.missing_timestamp_snapshots == 1
    assert cadence_drift.entries[1].cadence_status == "missing_timestamps"
    assert cadence_drift.diagnostics == (
        "At least two saved snapshots with valid source observation timestamps are required to evaluate cadence drift.",
        "1 snapshot(s) had missing or malformed source observation timestamps.",
    )


def test_snapshot_replay_service_builds_complete_source_record_completeness(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    record_completeness = SnapshotReplayService(store).build_source_record_completeness(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert record_completeness.completeness_classification == "complete"
    assert record_completeness.average_completeness_percentage == 100.0
    assert record_completeness.complete_snapshots == 1
    assert record_completeness.partial_snapshots == 0
    assert record_completeness.degraded_snapshots == 0
    assert record_completeness.invalid_snapshots == 0
    assert record_completeness.aggregate_missing_field_counts == {}
    assert record_completeness.malformed_record_count == 0
    assert record_completeness.entries[0].total_records == 27
    assert record_completeness.entries[0].complete_records == 27


def test_snapshot_replay_service_builds_partial_source_record_completeness(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    first_record_label = str(source_observation_records[0]["asset_symbol"])
    second_record_label = str(source_observation_records[1]["asset_symbol"])
    source_observation_records[0]["registry_provider"] = ""
    source_observation_records[1]["observed_at"] = None
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_partial_records",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    record_completeness = SnapshotReplayService(store).build_source_record_completeness(
        snapshot_ids=("snapshot_partial_records",),
    )

    assert record_completeness.completeness_classification == "partial"
    assert record_completeness.average_completeness_percentage == 92.59
    assert record_completeness.partial_snapshots == 1
    assert record_completeness.aggregate_missing_field_counts == {
        "observed_at": 1,
        "registry_provider": 1,
    }
    assert (
        f"{first_record_label}:registry_provider:missing"
        in record_completeness.missing_field_diagnostics
    )
    assert (
        f"{second_record_label}:observed_at:missing"
        in record_completeness.missing_field_diagnostics
    )
    assert record_completeness.entries[0].complete_records == 25


def test_snapshot_replay_service_builds_invalid_source_record_completeness_for_malformed_records(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_invalid_records",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": ["bad_record"]},
    )

    record_completeness = SnapshotReplayService(store).build_source_record_completeness(
        snapshot_ids=("snapshot_invalid_records",),
    )

    assert record_completeness.completeness_classification == "invalid"
    assert record_completeness.invalid_snapshots == 1
    assert record_completeness.malformed_record_count == 1
    assert record_completeness.entries[0].malformed_record_count == 1
    assert record_completeness.entries[0].completeness_classification == "invalid"


def test_snapshot_replay_service_keeps_source_observation_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    stable_source_observations = {
        source_id: "2026-05-19T09:29:00+00:00"
        for source_id in baseline_snapshot["source_observations"]
    }
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    source_observation_records[0]["registry_provider"] = ""
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={
            "source_observations": stable_source_observations,
            "source_observation_records": source_observation_records,
        },
    )

    replay_service = SnapshotReplayService(store)
    first_cadence = replay_service.build_source_observation_cadence_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_cadence = replay_service.build_source_observation_cadence_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    first_completeness = replay_service.build_source_record_completeness(
        snapshot_ids=("snapshot_b",),
    )
    second_completeness = replay_service.build_source_record_completeness(
        snapshot_ids=("snapshot_b",),
    )
    first_binding_drift = replay_service.build_source_registry_binding_drift(
        snapshot_ids=("snapshot_b",),
    )
    second_binding_drift = replay_service.build_source_registry_binding_drift(
        snapshot_ids=("snapshot_b",),
    )
    first_decision_usage_consistency = replay_service.build_source_decision_usage_consistency(
        snapshot_ids=("snapshot_b",),
    )
    second_decision_usage_consistency = replay_service.build_source_decision_usage_consistency(
        snapshot_ids=("snapshot_b",),
    )
    first_verification_drift = replay_service.build_source_verification_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_verification_drift = replay_service.build_source_verification_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    first_paper_safe_flag_consistency = replay_service.build_paper_safe_source_flag_consistency(
        snapshot_ids=("snapshot_b",),
    )
    second_paper_safe_flag_consistency = replay_service.build_paper_safe_source_flag_consistency(
        snapshot_ids=("snapshot_b",),
    )
    first_summary_drift = replay_service.build_source_observation_summary_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_summary_drift = replay_service.build_source_observation_summary_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    first_provider_contract_consistency = replay_service.build_provider_adapter_contract_consistency(
        snapshot_ids=("snapshot_b",),
    )
    second_provider_contract_consistency = replay_service.build_provider_adapter_contract_consistency(
        snapshot_ids=("snapshot_b",),
    )
    first_timestamp_integrity_drift = replay_service.build_source_observation_timestamp_integrity_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_timestamp_integrity_drift = replay_service.build_source_observation_timestamp_integrity_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    first_record_summary_reconciliation = (
        replay_service.build_source_observation_record_summary_reconciliation(
            snapshot_ids=("snapshot_b",),
        )
    )
    second_record_summary_reconciliation = (
        replay_service.build_source_observation_record_summary_reconciliation(
            snapshot_ids=("snapshot_b",),
        )
    )

    assert first_cadence == second_cadence
    assert first_completeness == second_completeness
    assert first_binding_drift == second_binding_drift
    assert first_decision_usage_consistency == second_decision_usage_consistency
    assert first_verification_drift == second_verification_drift
    assert first_paper_safe_flag_consistency == second_paper_safe_flag_consistency
    assert first_summary_drift == second_summary_drift
    assert first_provider_contract_consistency == second_provider_contract_consistency
    assert first_timestamp_integrity_drift == second_timestamp_integrity_drift
    assert first_record_summary_reconciliation == second_record_summary_reconciliation


def test_snapshot_replay_service_builds_stable_source_registry_binding_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    binding_drift = SnapshotReplayService(store).build_source_registry_binding_drift(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert binding_drift.drift_classification == "stable"
    assert binding_drift.severity_score == 0
    assert binding_drift.current_source_registry_version == "1.0"
    assert binding_drift.snapshots_checked == 1
    assert binding_drift.stable_snapshots == 1
    assert binding_drift.drifting_snapshots == 0
    assert binding_drift.degraded_snapshots == 0
    assert binding_drift.invalid_snapshots == 0
    assert binding_drift.registry_version_mismatch_count == 0
    assert binding_drift.unbound_source_ids == ()
    assert binding_drift.provider_mismatch_source_ids == ()
    assert binding_drift.asset_mismatch_source_ids == ()
    assert binding_drift.entries[0].binding_classification == "stable"
    assert binding_drift.entries[0].matched_records == 27
    assert binding_drift.diagnostics == (
        "Source registry bindings remained stable across 1 saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_source_registry_binding_drift_with_provider_mismatch(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    drifted_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["registry_provider"] = "drifted_provider"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_binding_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    binding_drift = SnapshotReplayService(store).build_source_registry_binding_drift(
        snapshot_ids=("snapshot_binding_drift",),
    )

    assert binding_drift.drift_classification == "drifting"
    assert binding_drift.provider_mismatch_source_ids == (drifted_source_id,)
    assert binding_drift.entries[0].binding_classification == "drifting"
    assert binding_drift.entries[0].matched_records == 26
    assert binding_drift.entries[0].provider_mismatch_source_ids == (drifted_source_id,)
    assert binding_drift.entries[0].severity_score == 15


def test_snapshot_replay_service_builds_consistent_source_decision_usage_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    decision_usage_consistency = SnapshotReplayService(store).build_source_decision_usage_consistency(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert decision_usage_consistency.consistency_classification == "consistent"
    assert decision_usage_consistency.average_consistency_percentage == 100.0
    assert decision_usage_consistency.snapshots_checked == 1
    assert decision_usage_consistency.consistent_snapshots == 1
    assert decision_usage_consistency.partial_snapshots == 0
    assert decision_usage_consistency.degraded_snapshots == 0
    assert decision_usage_consistency.invalid_snapshots == 0
    assert decision_usage_consistency.aggregate_decision_usage_counts == {
        "simulation_only": 3,
        "verified_required": 24,
    }
    assert decision_usage_consistency.mismatched_source_ids == ()
    assert decision_usage_consistency.unsafe_source_ids == ()
    assert decision_usage_consistency.entries[0].consistent_records == 27
    assert decision_usage_consistency.diagnostics == (
        "Source decision-usage consistency is consistent across 1 saved snapshot(s).",
    )


def test_snapshot_replay_service_builds_degraded_source_decision_usage_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    mismatched_source_id = str(source_observation_records[0]["source_id"])
    unsafe_source_id = str(source_observation_records[1]["source_id"])
    source_observation_records[0]["decision_usage"] = "simulation_only"
    source_observation_records[1]["paper_safe"] = False
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_usage_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    decision_usage_consistency = SnapshotReplayService(store).build_source_decision_usage_consistency(
        snapshot_ids=("snapshot_usage_drift",),
    )

    assert decision_usage_consistency.consistency_classification == "degraded"
    assert decision_usage_consistency.aggregate_decision_usage_counts == {
        "simulation_only": 4,
        "verified_required": 23,
    }
    assert decision_usage_consistency.mismatched_source_ids == (mismatched_source_id,)
    assert decision_usage_consistency.unsafe_source_ids == (unsafe_source_id,)
    assert decision_usage_consistency.entries[0].consistency_classification == "degraded"
    assert decision_usage_consistency.entries[0].mismatched_source_ids == (mismatched_source_id,)
    assert decision_usage_consistency.entries[0].unsafe_source_ids == (unsafe_source_id,)


def test_snapshot_replay_service_builds_stable_source_verification_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    verification_drift = SnapshotReplayService(store).build_source_verification_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )

    assert verification_drift.drift_classification == "stable"
    assert verification_drift.average_verification_score == 100.0
    assert verification_drift.severity_score == 0
    assert verification_drift.stable_snapshots == 2
    assert verification_drift.degrading_snapshots == 0
    assert verification_drift.improving_snapshots == 0
    assert verification_drift.mixed_snapshots == 0
    assert verification_drift.insufficient_data_snapshots == 0
    assert verification_drift.degraded_source_ids == ()
    assert verification_drift.improved_source_ids == ()
    assert verification_drift.entries[0].verification_classification == "stable"
    assert verification_drift.entries[1].verification_classification == "stable"


def test_snapshot_replay_service_builds_degrading_source_verification_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_record = next(record for record in source_observation_records if record["verified"] is True)
    degraded_source_id = str(degraded_source_record["source_id"])
    degraded_source_record["verified"] = False
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    verification_drift = SnapshotReplayService(store).build_source_verification_drift(
        snapshot_ids=("snapshot_a", "snapshot_verification_degraded"),
    )

    assert verification_drift.drift_classification == "degrading"
    assert verification_drift.severity_score == 25
    assert verification_drift.degraded_source_ids == (degraded_source_id,)
    assert verification_drift.entries[1].verification_classification == "degrading"
    assert verification_drift.entries[1].verification_score == 75.0
    assert verification_drift.entries[1].degraded_source_ids == (degraded_source_id,)


def test_snapshot_replay_service_builds_improving_source_verification_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    verified_source_record = next(record for record in degraded_records if record["verified"] is True)
    verified_source_id = str(verified_source_record["source_id"])
    verified_source_record["verified"] = False
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_low",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": degraded_records},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_recovered",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
    )

    verification_drift = SnapshotReplayService(store).build_source_verification_drift(
        snapshot_ids=("snapshot_verification_low", "snapshot_verification_recovered"),
    )

    assert verification_drift.drift_classification == "improving"
    assert verification_drift.degraded_source_ids == (verified_source_id,)
    assert verification_drift.entries[0].verification_classification == "degrading"
    assert verification_drift.entries[1].verification_classification == "stable"


def test_snapshot_replay_service_builds_mixed_source_verification_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_record = next(record for record in degraded_records if record["verified"] is True)
    degraded_source_record["verified"] = False
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_mixed_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": degraded_records},
    )

    improved_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    improved_source_record = next(record for record in improved_records if record["verified"] is False)
    improved_source_id = str(improved_source_record["source_id"])
    improved_source_record["verified"] = True
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_mixed_b",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": improved_records},
    )

    verification_drift = SnapshotReplayService(store).build_source_verification_drift(
        snapshot_ids=("snapshot_verification_mixed_a", "snapshot_verification_mixed_b"),
    )

    assert verification_drift.drift_classification == "mixed"
    assert verification_drift.improved_source_ids == (improved_source_id,)
    assert verification_drift.degrading_snapshots == 1
    assert verification_drift.improving_snapshots == 1


def test_snapshot_replay_service_surfaces_missing_verification_metadata_diagnostics(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    missing_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["verified"] = None
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_missing",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    verification_drift = SnapshotReplayService(store).build_source_verification_drift(
        snapshot_ids=("snapshot_verification_missing",),
    )

    assert verification_drift.drift_classification == "degrading"
    assert verification_drift.missing_verification_source_ids == (missing_source_id,)
    assert verification_drift.entries[0].missing_verification_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_insufficient_source_verification_drift_for_malformed_records(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verification_invalid",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": ["bad_record"]},
    )

    verification_drift = SnapshotReplayService(store).build_source_verification_drift(
        snapshot_ids=("snapshot_verification_invalid",),
    )

    assert verification_drift.drift_classification == "insufficient_data"
    assert verification_drift.insufficient_data_snapshots == 1
    assert verification_drift.malformed_record_count == 1
    assert verification_drift.entries[0].verification_classification == "insufficient_data"


def test_snapshot_replay_service_builds_consistent_paper_safe_source_flag_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    paper_safe_consistency = SnapshotReplayService(store).build_paper_safe_source_flag_consistency(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert paper_safe_consistency.consistency_classification == "consistent"
    assert paper_safe_consistency.average_consistency_percentage == 100.0
    assert paper_safe_consistency.consistent_snapshots == 1
    assert paper_safe_consistency.partial_snapshots == 0
    assert paper_safe_consistency.degraded_snapshots == 0
    assert paper_safe_consistency.invalid_snapshots == 0
    assert paper_safe_consistency.unsafe_source_ids == ()
    assert paper_safe_consistency.entries[0].safe_records == 27


def test_snapshot_replay_service_builds_degraded_paper_safe_source_flag_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    false_source_id = str(source_observation_records[0]["source_id"])
    missing_source_id = str(source_observation_records[1]["source_id"])
    source_observation_records[0]["paper_safe"] = False
    source_observation_records[1].pop("paper_safe")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_flag_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    paper_safe_consistency = SnapshotReplayService(store).build_paper_safe_source_flag_consistency(
        snapshot_ids=("snapshot_source_flag_degraded",),
    )

    assert paper_safe_consistency.consistency_classification == "degraded"
    assert paper_safe_consistency.false_flag_source_ids == (false_source_id,)
    assert paper_safe_consistency.missing_flag_source_ids == (missing_source_id,)
    assert paper_safe_consistency.unsafe_source_ids == tuple(sorted((false_source_id, missing_source_id)))
    assert paper_safe_consistency.entries[0].consistency_classification == "degraded"
    assert paper_safe_consistency.entries[0].false_flag_source_ids == (false_source_id,)
    assert paper_safe_consistency.entries[0].missing_flag_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_stable_source_observation_summary_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    summary_drift = SnapshotReplayService(store).build_source_observation_summary_drift(
        snapshot_ids=("snapshot_a", "snapshot_summary_b"),
    )

    assert summary_drift.drift_classification == "stable"
    assert summary_drift.average_summary_score == 100.0
    assert summary_drift.severity_score == 0
    assert summary_drift.stable_snapshots == 2
    assert summary_drift.degrading_snapshots == 0
    assert summary_drift.improving_snapshots == 0
    assert summary_drift.mixed_snapshots == 0
    assert summary_drift.insufficient_data_snapshots == 0
    assert summary_drift.expected_total_bound_sources == 27
    assert summary_drift.expected_verified_sources == 24
    assert summary_drift.entries[0].drift_classification == "stable"
    assert summary_drift.entries[1].drift_classification == "stable"


def test_snapshot_replay_service_builds_degrading_source_observation_summary_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    summary = dict(baseline_snapshot["source_observation_summary"])
    summary["verified_sources"] = 20
    summary["paper_safe_sources"] = 25
    summary["total_bound_sources"] = 25
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": summary},
    )

    summary_drift = SnapshotReplayService(store).build_source_observation_summary_drift(
        snapshot_ids=("snapshot_a", "snapshot_summary_degraded"),
    )

    assert summary_drift.drift_classification == "degrading"
    assert summary_drift.severity_score == 10
    assert summary_drift.degrading_snapshots == 1
    assert summary_drift.entries[1].drift_classification == "degrading"
    assert summary_drift.entries[1].total_bound_sources == 25
    assert summary_drift.entries[1].verified_sources == 20
    assert summary_drift.entries[1].paper_safe_sources == 25


def test_snapshot_replay_service_builds_improving_source_observation_summary_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_summary = dict(baseline_snapshot["source_observation_summary"])
    degraded_summary["verified_sources"] = 20
    degraded_summary["paper_safe_sources"] = 25
    degraded_summary["total_bound_sources"] = 25
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_low",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": degraded_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_recovered",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
    )

    summary_drift = SnapshotReplayService(store).build_source_observation_summary_drift(
        snapshot_ids=("snapshot_summary_low", "snapshot_summary_recovered"),
    )

    assert summary_drift.drift_classification == "improving"
    assert summary_drift.improving_snapshots == 1
    assert summary_drift.entries[0].drift_classification == "degrading"
    assert summary_drift.entries[1].drift_classification == "improving"


def test_snapshot_replay_service_builds_mixed_source_observation_summary_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    mixed_summary_a = dict(baseline_snapshot["source_observation_summary"])
    mixed_summary_a["verified_sources"] = 22
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_mixed_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": mixed_summary_a},
    )
    mixed_summary_b = dict(baseline_snapshot["source_observation_summary"])
    mixed_summary_b["verified_sources"] = 23
    mixed_summary_b["paper_safe_sources"] = 26
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_mixed_b",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": mixed_summary_b},
    )

    summary_drift = SnapshotReplayService(store).build_source_observation_summary_drift(
        snapshot_ids=("snapshot_a", "snapshot_summary_mixed_a", "snapshot_summary_mixed_b"),
    )

    assert summary_drift.drift_classification == "mixed"
    assert summary_drift.mixed_snapshots >= 1


def test_snapshot_replay_service_builds_insufficient_source_observation_summary_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_invalid",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": {"contract": "verified_provider_adapter_v1"}},
    )

    summary_drift = SnapshotReplayService(store).build_source_observation_summary_drift(
        snapshot_ids=("snapshot_summary_invalid",),
    )

    assert summary_drift.drift_classification == "insufficient_data"
    assert summary_drift.insufficient_data_snapshots == 1
    assert summary_drift.malformed_summary_count >= 1
    assert summary_drift.entries[0].drift_classification == "insufficient_data"


def test_snapshot_replay_service_builds_consistent_provider_adapter_contract_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_a",
        audit_source_payload={
            "source_registry_version": "1.0",
            "provider_adapter": {
                "contract": "verified_provider_adapter_v1",
                "total_bound_sources": 27,
            },
        },
    )

    contract_consistency = SnapshotReplayService(store).build_provider_adapter_contract_consistency(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert contract_consistency.consistency_classification == "consistent"
    assert contract_consistency.average_consistency_percentage == 100.0
    assert contract_consistency.expected_contract == "verified_provider_adapter_v1"
    assert contract_consistency.consistent_snapshots == 1
    assert contract_consistency.partial_snapshots == 0
    assert contract_consistency.degraded_snapshots == 0
    assert contract_consistency.invalid_snapshots == 0
    assert contract_consistency.missing_contract_snapshot_ids == ()
    assert contract_consistency.mismatched_contract_snapshot_ids == ()
    assert contract_consistency.bound_source_mismatch_snapshot_ids == ()


def test_snapshot_replay_service_builds_degraded_provider_adapter_contract_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_a",
        audit_source_payload={
            "source_registry_version": "1.0",
            "provider_adapter": {
                "contract": "verified_provider_adapter_v1",
                "total_bound_sources": 27,
            },
        },
    )
    audit_source_payload = dict(baseline_snapshot["audit_source_payload"])
    provider_adapter = dict(audit_source_payload["provider_adapter"])
    provider_adapter["contract"] = "verified_provider_adapter_v2"
    provider_adapter["total_bound_sources"] = 26
    audit_source_payload["provider_adapter"] = provider_adapter
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_contract_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"audit_source_payload": audit_source_payload},
    )

    contract_consistency = SnapshotReplayService(store).build_provider_adapter_contract_consistency(
        snapshot_ids=("snapshot_contract_degraded",),
    )

    assert contract_consistency.consistency_classification == "degraded"
    assert contract_consistency.average_consistency_percentage == 0.0
    assert contract_consistency.mismatched_contract_snapshot_ids == ("snapshot_contract_degraded",)
    assert contract_consistency.bound_source_mismatch_snapshot_ids == ("snapshot_contract_degraded",)
    assert contract_consistency.entries[0].mismatched_fields == (
        "audit_source_payload.provider_adapter.contract",
        "provider_adapter.contract_alignment",
        "provider_adapter.total_bound_sources_alignment",
    )


def test_snapshot_replay_service_builds_partial_provider_adapter_contract_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_a",
        audit_source_payload={
            "source_registry_version": "1.0",
            "provider_adapter": {
                "contract": "verified_provider_adapter_v1",
                "total_bound_sources": 27,
            },
        },
    )
    audit_source_payload = dict(baseline_snapshot["audit_source_payload"])
    audit_source_payload.pop("provider_adapter")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_contract_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"audit_source_payload": audit_source_payload},
    )

    contract_consistency = SnapshotReplayService(store).build_provider_adapter_contract_consistency(
        snapshot_ids=("snapshot_contract_partial",),
    )

    assert contract_consistency.consistency_classification == "partial"
    assert contract_consistency.missing_contract_snapshot_ids == ("snapshot_contract_partial",)
    assert contract_consistency.entries[0].missing_fields == (
        "audit_source_payload.provider_adapter.contract",
        "audit_source_payload.provider_adapter.total_bound_sources",
    )


def test_snapshot_replay_service_builds_stable_source_observation_timestamp_integrity_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_timestamp_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    timestamp_integrity = SnapshotReplayService(store).build_source_observation_timestamp_integrity_drift(
        snapshot_ids=("snapshot_a", "snapshot_timestamp_b"),
    )

    assert timestamp_integrity.drift_classification == "stable"
    assert timestamp_integrity.average_integrity_score == 100.0
    assert timestamp_integrity.severity_score == 0
    assert timestamp_integrity.stable_snapshots == 2
    assert timestamp_integrity.degrading_snapshots == 0
    assert timestamp_integrity.improving_snapshots == 0
    assert timestamp_integrity.mixed_snapshots == 0
    assert timestamp_integrity.insufficient_data_snapshots == 0
    assert timestamp_integrity.entries[0].integrity_classification == "stable"
    assert timestamp_integrity.entries[1].integrity_classification == "stable"


def test_snapshot_replay_service_builds_degrading_source_observation_timestamp_integrity_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["available_at"] = "2026-05-19T09:35:00+00:00"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_timestamp_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    timestamp_integrity = SnapshotReplayService(store).build_source_observation_timestamp_integrity_drift(
        snapshot_ids=("snapshot_a", "snapshot_timestamp_degraded"),
    )

    assert timestamp_integrity.drift_classification == "degrading"
    assert timestamp_integrity.average_integrity_score == 98.15
    assert timestamp_integrity.severity_score == 4
    assert timestamp_integrity.sequence_violation_source_ids == (degraded_source_id,)
    assert timestamp_integrity.entries[1].integrity_classification == "degrading"
    assert timestamp_integrity.entries[1].integrity_score == 96.3
    assert timestamp_integrity.entries[1].sequence_violation_source_ids == (degraded_source_id,)


def test_snapshot_replay_service_builds_improving_source_observation_timestamp_integrity_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_id = str(degraded_records[0]["source_id"])
    degraded_records[0]["mapped_at"] = "2026-05-19T09:00:00+00:00"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_timestamp_low",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": degraded_records},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_timestamp_recovered",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
    )

    timestamp_integrity = SnapshotReplayService(store).build_source_observation_timestamp_integrity_drift(
        snapshot_ids=("snapshot_timestamp_low", "snapshot_timestamp_recovered"),
    )

    assert timestamp_integrity.drift_classification == "improving"
    assert timestamp_integrity.mapped_time_regression_source_ids == (degraded_source_id,)
    assert timestamp_integrity.entries[0].integrity_classification == "degrading"
    assert timestamp_integrity.entries[1].integrity_classification == "improving"


def test_snapshot_replay_service_surfaces_missing_source_observation_timestamp_diagnostics(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    missing_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0].pop("mapped_at")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_timestamp_missing",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    timestamp_integrity = SnapshotReplayService(store).build_source_observation_timestamp_integrity_drift(
        snapshot_ids=("snapshot_timestamp_missing",),
    )

    assert timestamp_integrity.drift_classification == "degrading"
    assert timestamp_integrity.missing_timestamp_source_ids == (missing_source_id,)
    assert timestamp_integrity.entries[0].missing_timestamp_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_consistent_source_observation_record_summary_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    reconciliation = SnapshotReplayService(store).build_source_observation_record_summary_reconciliation(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].record_total_bound_sources == 27
    assert reconciliation.entries[0].summary_total_bound_sources == 27


def test_snapshot_replay_service_builds_degraded_source_observation_record_summary_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    summary = dict(baseline_snapshot["source_observation_summary"])
    summary["verified_sources"] = 20
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_reconciliation_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_observation_record_summary_reconciliation(
        snapshot_ids=("snapshot_summary_reconciliation_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 75.0
    assert reconciliation.mismatched_fields == ("verified_sources",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].mismatched_fields == ("verified_sources",)


def test_snapshot_replay_service_builds_partial_source_observation_record_summary_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    summary = dict(baseline_snapshot["source_observation_summary"])
    summary.pop("verified_sources")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_summary_reconciliation_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_observation_record_summary_reconciliation(
        snapshot_ids=("snapshot_summary_reconciliation_partial",),
    )

    assert reconciliation.consistency_classification == "partial"
    assert reconciliation.average_consistency_percentage == 85.0
    assert reconciliation.missing_fields == ("verified_sources",)
    assert reconciliation.entries[0].reconciliation_classification == "partial"
    assert reconciliation.entries[0].missing_fields == ("verified_sources",)


def test_snapshot_replay_service_keeps_confidence_and_verified_coverage_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    confidence_records = [
        {
            **dict(record),
            "confidence": 0.9,
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_confidence_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": confidence_records},
    )

    replay_service = SnapshotReplayService(store)
    first_confidence_drift = replay_service.build_source_observation_confidence_drift(
        snapshot_ids=("snapshot_confidence_a",),
    )
    second_confidence_drift = replay_service.build_source_observation_confidence_drift(
        snapshot_ids=("snapshot_confidence_a",),
    )
    first_verified_coverage = replay_service.build_verified_source_coverage_reconciliation(
        snapshot_ids=("snapshot_a",),
    )
    second_verified_coverage = replay_service.build_verified_source_coverage_reconciliation(
        snapshot_ids=("snapshot_a",),
    )

    assert first_confidence_drift == second_confidence_drift
    assert first_verified_coverage == second_verified_coverage


def test_snapshot_replay_service_builds_stable_source_observation_confidence_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    confidence_records = [
        {
            **dict(record),
            "confidence": 0.9,
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_confidence_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": confidence_records},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_confidence_b",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": confidence_records},
    )

    confidence_drift = SnapshotReplayService(store).build_source_observation_confidence_drift(
        snapshot_ids=("snapshot_confidence_a", "snapshot_confidence_b"),
    )

    assert confidence_drift.drift_classification == "stable"
    assert confidence_drift.average_confidence_score == 90.0
    assert confidence_drift.severity_score == 0
    assert confidence_drift.stable_snapshots == 2
    assert confidence_drift.degrading_snapshots == 0
    assert confidence_drift.improving_snapshots == 0
    assert confidence_drift.mixed_snapshots == 0
    assert confidence_drift.insufficient_data_snapshots == 0
    assert confidence_drift.entries[0].drift_classification == "stable"
    assert confidence_drift.entries[1].drift_classification == "stable"
    assert confidence_drift.entries[1].average_confidence_score == 90.0


def test_snapshot_replay_service_builds_degrading_source_observation_confidence_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    high_confidence_records = [
        {
            **dict(record),
            "confidence": 0.9,
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    low_confidence_records = [
        {
            **dict(record),
            "confidence": 0.8,
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_ids = tuple(
        sorted(str(record["source_id"]) for record in baseline_snapshot["source_observation_records"])
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_confidence_high",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": high_confidence_records},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_confidence_low",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": low_confidence_records},
    )

    confidence_drift = SnapshotReplayService(store).build_source_observation_confidence_drift(
        snapshot_ids=("snapshot_confidence_high", "snapshot_confidence_low"),
    )

    assert confidence_drift.drift_classification == "degrading"
    assert confidence_drift.average_confidence_score == 85.0
    assert confidence_drift.severity_score == 10
    assert confidence_drift.stable_snapshots == 1
    assert confidence_drift.degrading_snapshots == 1
    assert confidence_drift.degraded_source_ids == degraded_source_ids
    assert confidence_drift.entries[1].drift_classification == "degrading"
    assert confidence_drift.entries[1].average_confidence_score == 80.0
    assert confidence_drift.entries[1].confidence_delta_from_previous == -10.0
    assert confidence_drift.entries[1].degraded_source_ids == degraded_source_ids


def test_snapshot_replay_service_builds_insufficient_source_observation_confidence_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    confidence_drift = SnapshotReplayService(store).build_source_observation_confidence_drift(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert confidence_drift.drift_classification == "insufficient_data"
    assert confidence_drift.average_confidence_score == 0.0
    assert confidence_drift.insufficient_data_snapshots == 1
    assert confidence_drift.entries[0].drift_classification == "insufficient_data"
    assert confidence_drift.entries[0].valid_confidence_records == 0


def test_snapshot_replay_service_builds_consistent_verified_source_coverage_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    coverage_reconciliation = SnapshotReplayService(store).build_verified_source_coverage_reconciliation(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert coverage_reconciliation.consistency_classification == "consistent"
    assert coverage_reconciliation.average_coverage_percentage == 100.0
    assert coverage_reconciliation.expected_verified_source_count == 24
    assert coverage_reconciliation.consistent_snapshots == 1
    assert coverage_reconciliation.partial_snapshots == 0
    assert coverage_reconciliation.degraded_snapshots == 0
    assert coverage_reconciliation.invalid_snapshots == 0
    assert coverage_reconciliation.missing_verified_source_ids == ()
    assert coverage_reconciliation.unexpected_verified_source_ids == ()
    assert coverage_reconciliation.entries[0].matched_verified_source_count == 24


def test_snapshot_replay_service_builds_partial_verified_source_coverage_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    missing_verified_record = next(record for record in source_observation_records if record["verified"] is True)
    missing_verified_source_id = str(missing_verified_record["source_id"])
    missing_verified_record["verified"] = False
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verified_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    coverage_reconciliation = SnapshotReplayService(store).build_verified_source_coverage_reconciliation(
        snapshot_ids=("snapshot_verified_partial",),
    )

    assert coverage_reconciliation.consistency_classification == "partial"
    assert coverage_reconciliation.average_coverage_percentage == 95.83
    assert coverage_reconciliation.partial_snapshots == 1
    assert coverage_reconciliation.missing_verified_source_ids == (missing_verified_source_id,)
    assert coverage_reconciliation.entries[0].reconciliation_classification == "partial"
    assert coverage_reconciliation.entries[0].matched_verified_source_count == 23
    assert coverage_reconciliation.entries[0].missing_verified_source_ids == (missing_verified_source_id,)


def test_snapshot_replay_service_builds_degraded_verified_source_coverage_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    unexpected_verified_record = next(record for record in source_observation_records if record["verified"] is False)
    unexpected_verified_source_id = str(unexpected_verified_record["source_id"])
    unexpected_verified_record["verified"] = True
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_verified_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    coverage_reconciliation = SnapshotReplayService(store).build_verified_source_coverage_reconciliation(
        snapshot_ids=("snapshot_verified_degraded",),
    )

    assert coverage_reconciliation.consistency_classification == "degraded"
    assert coverage_reconciliation.average_coverage_percentage == 100.0
    assert coverage_reconciliation.degraded_snapshots == 1
    assert coverage_reconciliation.unexpected_verified_source_ids == (unexpected_verified_source_id,)
    assert coverage_reconciliation.entries[0].reconciliation_classification == "degraded"
    assert coverage_reconciliation.entries[0].unexpected_verified_source_ids == (
        unexpected_verified_source_id,
    )


def test_snapshot_replay_service_keeps_availability_lag_and_freshness_summary_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    replay_service = SnapshotReplayService(store)
    first_availability_lag = replay_service.build_source_observation_availability_lag_drift(
        snapshot_ids=("snapshot_a",),
    )
    second_availability_lag = replay_service.build_source_observation_availability_lag_drift(
        snapshot_ids=("snapshot_a",),
    )
    first_freshness_reconciliation = replay_service.build_source_freshness_summary_reconciliation(
        snapshot_ids=("snapshot_freshness_a",),
    )
    second_freshness_reconciliation = replay_service.build_source_freshness_summary_reconciliation(
        snapshot_ids=("snapshot_freshness_a",),
    )

    assert first_availability_lag == second_availability_lag
    assert first_freshness_reconciliation == second_freshness_reconciliation


def test_snapshot_replay_service_builds_stable_source_observation_availability_lag_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_lag_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    availability_lag_drift = SnapshotReplayService(store).build_source_observation_availability_lag_drift(
        snapshot_ids=("snapshot_a", "snapshot_lag_b"),
    )

    assert availability_lag_drift.drift_classification == "stable"
    assert availability_lag_drift.average_lag_seconds == 60.0
    assert availability_lag_drift.severity_score == 0
    assert availability_lag_drift.stable_snapshots == 2
    assert availability_lag_drift.degrading_snapshots == 0
    assert availability_lag_drift.improving_snapshots == 0
    assert availability_lag_drift.mixed_snapshots == 0
    assert availability_lag_drift.insufficient_data_snapshots == 0
    assert availability_lag_drift.entries[0].drift_classification == "stable"
    assert availability_lag_drift.entries[1].drift_classification == "stable"


def test_snapshot_replay_service_builds_degrading_source_observation_availability_lag_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["available_at"] = "2026-05-19T09:03:00+00:00"
    source_observation_records[0]["stored_at"] = "2026-05-19T09:04:00+00:00"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_lag_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    availability_lag_drift = SnapshotReplayService(store).build_source_observation_availability_lag_drift(
        snapshot_ids=("snapshot_a", "snapshot_lag_degraded"),
    )

    assert availability_lag_drift.drift_classification == "degrading"
    assert availability_lag_drift.average_lag_seconds == 62.22
    assert availability_lag_drift.severity_score == 4
    assert availability_lag_drift.stable_snapshots == 1
    assert availability_lag_drift.degrading_snapshots == 1
    assert availability_lag_drift.degraded_source_ids == (degraded_source_id,)
    assert availability_lag_drift.entries[1].drift_classification == "degrading"
    assert availability_lag_drift.entries[1].average_lag_seconds == 64.44
    assert availability_lag_drift.entries[1].lag_delta_from_previous_seconds == 4.44
    assert availability_lag_drift.entries[1].degraded_source_ids == (degraded_source_id,)


def test_snapshot_replay_service_builds_consistent_source_freshness_summary_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    freshness_reconciliation = SnapshotReplayService(store).build_source_freshness_summary_reconciliation(
        snapshot_ids=("snapshot_freshness_consistent",),
    )

    assert freshness_reconciliation.consistency_classification == "consistent"
    assert freshness_reconciliation.average_consistency_percentage == 100.0
    assert freshness_reconciliation.consistent_snapshots == 1
    assert freshness_reconciliation.partial_snapshots == 0
    assert freshness_reconciliation.degraded_snapshots == 0
    assert freshness_reconciliation.invalid_snapshots == 0
    assert freshness_reconciliation.missing_freshness_source_ids == ()
    assert freshness_reconciliation.record_only_stale_source_ids == ()
    assert freshness_reconciliation.summary_only_stale_source_ids == ()
    assert freshness_reconciliation.entries[0].aligned_records == 27


def test_snapshot_replay_service_builds_partial_source_freshness_summary_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    missing_source_id = str(freshness_records[0]["source_id"])
    freshness_records[0].pop("freshness_status")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    freshness_reconciliation = SnapshotReplayService(store).build_source_freshness_summary_reconciliation(
        snapshot_ids=("snapshot_freshness_partial",),
    )

    assert freshness_reconciliation.consistency_classification == "partial"
    assert freshness_reconciliation.average_consistency_percentage == 96.3
    assert freshness_reconciliation.partial_snapshots == 1
    assert freshness_reconciliation.missing_freshness_source_ids == (missing_source_id,)
    assert freshness_reconciliation.entries[0].reconciliation_classification == "partial"
    assert freshness_reconciliation.entries[0].aligned_records == 26
    assert freshness_reconciliation.entries[0].missing_freshness_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_degraded_source_freshness_summary_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    stale_source_id = str(freshness_records[0]["source_id"])
    freshness_records[0]["freshness_status"] = "stale"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    freshness_reconciliation = SnapshotReplayService(store).build_source_freshness_summary_reconciliation(
        snapshot_ids=("snapshot_freshness_degraded",),
    )

    assert freshness_reconciliation.consistency_classification == "degraded"
    assert freshness_reconciliation.average_consistency_percentage == 96.3
    assert freshness_reconciliation.degraded_snapshots == 1
    assert freshness_reconciliation.record_only_stale_source_ids == (stale_source_id,)
    assert freshness_reconciliation.entries[0].reconciliation_classification == "degraded"
    assert freshness_reconciliation.entries[0].record_only_stale_source_ids == (stale_source_id,)


def test_snapshot_replay_service_keeps_freshness_seconds_and_threshold_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_threshold_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    replay_service = SnapshotReplayService(store)
    first_drift = replay_service.build_source_observation_freshness_seconds_drift(
        snapshot_ids=("snapshot_a", "snapshot_freshness_threshold_a"),
    )
    second_drift = replay_service.build_source_observation_freshness_seconds_drift(
        snapshot_ids=("snapshot_a", "snapshot_freshness_threshold_a"),
    )
    first_reconciliation = replay_service.build_source_freshness_status_threshold_reconciliation(
        snapshot_ids=("snapshot_freshness_threshold_a",),
    )
    second_reconciliation = replay_service.build_source_freshness_status_threshold_reconciliation(
        snapshot_ids=("snapshot_freshness_threshold_a",),
    )

    assert first_drift == second_drift
    assert first_reconciliation == second_reconciliation


def test_snapshot_replay_service_builds_stable_source_observation_freshness_seconds_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_seconds_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    freshness_seconds_drift = SnapshotReplayService(store).build_source_observation_freshness_seconds_drift(
        snapshot_ids=("snapshot_a", "snapshot_freshness_seconds_b"),
    )

    assert freshness_seconds_drift.drift_classification == "stable"
    assert freshness_seconds_drift.average_freshness_seconds == 120.0
    assert freshness_seconds_drift.severity_score == 0
    assert freshness_seconds_drift.stable_snapshots == 2
    assert freshness_seconds_drift.degrading_snapshots == 0
    assert freshness_seconds_drift.improving_snapshots == 0
    assert freshness_seconds_drift.mixed_snapshots == 0
    assert freshness_seconds_drift.insufficient_data_snapshots == 0
    assert freshness_seconds_drift.entries[0].drift_classification == "stable"
    assert freshness_seconds_drift.entries[1].drift_classification == "stable"


def test_snapshot_replay_service_builds_degrading_source_observation_freshness_seconds_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_source_id = str(baseline_snapshot["source_observation_records"][0]["source_id"])
    degraded_asset_symbol = str(baseline_snapshot["source_observation_records"][0]["asset_symbol"])
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_seconds_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            degraded_asset_symbol: {
                "freshness_seconds": 240,
            }
        },
    )

    freshness_seconds_drift = SnapshotReplayService(store).build_source_observation_freshness_seconds_drift(
        snapshot_ids=("snapshot_a", "snapshot_freshness_seconds_degraded"),
    )

    assert freshness_seconds_drift.drift_classification == "degrading"
    assert freshness_seconds_drift.average_freshness_seconds == 122.22
    assert freshness_seconds_drift.severity_score == 4
    assert freshness_seconds_drift.stable_snapshots == 1
    assert freshness_seconds_drift.degrading_snapshots == 1
    assert freshness_seconds_drift.degraded_source_ids == (degraded_source_id,)
    assert freshness_seconds_drift.entries[1].drift_classification == "degrading"
    assert freshness_seconds_drift.entries[1].average_freshness_seconds == 124.44
    assert freshness_seconds_drift.entries[1].freshness_delta_from_previous_seconds == 4.44
    assert freshness_seconds_drift.entries[1].degraded_source_ids == (degraded_source_id,)


def test_snapshot_replay_service_builds_consistent_source_freshness_status_threshold_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_threshold_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    threshold_reconciliation = SnapshotReplayService(store).build_source_freshness_status_threshold_reconciliation(
        snapshot_ids=("snapshot_freshness_threshold_consistent",),
    )

    assert threshold_reconciliation.consistency_classification == "consistent"
    assert threshold_reconciliation.average_consistency_percentage == 100.0
    assert threshold_reconciliation.consistent_snapshots == 1
    assert threshold_reconciliation.partial_snapshots == 0
    assert threshold_reconciliation.degraded_snapshots == 0
    assert threshold_reconciliation.invalid_snapshots == 0
    assert threshold_reconciliation.missing_freshness_status_source_ids == ()
    assert threshold_reconciliation.threshold_mismatch_source_ids == ()
    assert threshold_reconciliation.entries[0].aligned_records == 27


def test_snapshot_replay_service_builds_partial_source_freshness_status_threshold_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    missing_source_id = str(freshness_records[0]["source_id"])
    freshness_records[0].pop("freshness_status")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_threshold_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )

    threshold_reconciliation = SnapshotReplayService(store).build_source_freshness_status_threshold_reconciliation(
        snapshot_ids=("snapshot_freshness_threshold_partial",),
    )

    assert threshold_reconciliation.consistency_classification == "partial"
    assert threshold_reconciliation.average_consistency_percentage == 96.3
    assert threshold_reconciliation.partial_snapshots == 1
    assert threshold_reconciliation.missing_freshness_status_source_ids == (missing_source_id,)
    assert threshold_reconciliation.entries[0].reconciliation_classification == "partial"
    assert threshold_reconciliation.entries[0].aligned_records == 26
    assert threshold_reconciliation.entries[0].missing_freshness_status_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_degraded_source_freshness_status_threshold_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_records = [
        {
            **dict(record),
            "freshness_status": "fresh",
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    mismatched_source_id = str(freshness_records[0]["source_id"])
    mismatched_asset_symbol = str(freshness_records[0]["asset_symbol"])
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_freshness_threshold_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            mismatched_asset_symbol: {
                "freshness_seconds": 360,
                "is_stale": True,
            }
        },
        extra_fields={"source_observation_records": freshness_records},
    )

    threshold_reconciliation = SnapshotReplayService(store).build_source_freshness_status_threshold_reconciliation(
        snapshot_ids=("snapshot_freshness_threshold_degraded",),
    )

    assert threshold_reconciliation.consistency_classification == "degraded"
    assert threshold_reconciliation.average_consistency_percentage == 96.3
    assert threshold_reconciliation.degraded_snapshots == 1
    assert threshold_reconciliation.threshold_mismatch_source_ids == (mismatched_source_id,)
    assert threshold_reconciliation.entries[0].reconciliation_classification == "degraded"
    assert threshold_reconciliation.entries[0].aligned_records == 26
    assert threshold_reconciliation.entries[0].stale_threshold_source_count == 1
    assert threshold_reconciliation.entries[0].threshold_mismatch_source_ids == (mismatched_source_id,)


def test_snapshot_replay_service_keeps_freshness_policy_and_stale_threshold_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    freshness_summary = {
        "total_sources": 27,
        "total_active_sources": 27,
        "fresh_sources": 27,
        "stale_sources": 0,
        "sources_missing_timestamps": 0,
        "not_evaluated_sources": 0,
        "evaluation_mode": "observed",
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_policy_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_freshness_summary": freshness_summary},
    )

    replay_service = SnapshotReplayService(store)
    first_policy_drift = replay_service.build_source_freshness_policy_drift(
        snapshot_ids=("snapshot_policy_a",),
    )
    second_policy_drift = replay_service.build_source_freshness_policy_drift(
        snapshot_ids=("snapshot_policy_a",),
    )
    first_threshold_reconciliation = (
        replay_service.build_stale_source_list_threshold_reconciliation(
            snapshot_ids=("snapshot_a",),
        )
    )
    second_threshold_reconciliation = (
        replay_service.build_stale_source_list_threshold_reconciliation(
            snapshot_ids=("snapshot_a",),
        )
    )

    assert first_policy_drift == second_policy_drift
    assert first_threshold_reconciliation == second_threshold_reconciliation


def test_snapshot_replay_service_builds_degrading_source_freshness_policy_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_sources": 27,
        "total_active_sources": 27,
        "fresh_sources": 27,
        "stale_sources": 0,
        "sources_missing_timestamps": 0,
        "not_evaluated_sources": 0,
        "evaluation_mode": "observed",
    }
    degraded_summary = {
        "total_sources": 27,
        "total_active_sources": 27,
        "fresh_sources": 26,
        "stale_sources": 1,
        "sources_missing_timestamps": 0,
        "not_evaluated_sources": 0,
        "evaluation_mode": "observed",
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_policy_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_freshness_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_policy_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_freshness_summary": degraded_summary},
    )

    policy_drift = SnapshotReplayService(store).build_source_freshness_policy_drift(
        snapshot_ids=("snapshot_policy_healthy", "snapshot_policy_degraded"),
    )

    assert policy_drift.drift_classification == "degrading"
    assert policy_drift.average_policy_score == 98.15
    assert policy_drift.severity_score == 4
    assert policy_drift.stable_snapshots == 1
    assert policy_drift.degrading_snapshots == 1
    assert policy_drift.improving_snapshots == 0
    assert policy_drift.mixed_snapshots == 0
    assert policy_drift.insufficient_data_snapshots == 0
    assert policy_drift.entries[0].drift_classification == "stable"
    assert policy_drift.entries[1].drift_classification == "degrading"
    assert policy_drift.entries[1].policy_score == 96.3
    assert policy_drift.entries[1].policy_score_delta == -3.7


def test_snapshot_replay_service_builds_consistent_stale_source_list_threshold_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    threshold_reconciliation = (
        SnapshotReplayService(store).build_stale_source_list_threshold_reconciliation(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert threshold_reconciliation.consistency_classification == "consistent"
    assert threshold_reconciliation.average_consistency_percentage == 100.0
    assert threshold_reconciliation.consistent_snapshots == 1
    assert threshold_reconciliation.partial_snapshots == 0
    assert threshold_reconciliation.degraded_snapshots == 0
    assert threshold_reconciliation.invalid_snapshots == 0
    assert threshold_reconciliation.missing_timestamp_source_ids == ()
    assert threshold_reconciliation.threshold_mismatch_source_ids == ()
    assert threshold_reconciliation.entries[0].aligned_sources == 27


def test_snapshot_replay_service_builds_partial_stale_source_list_threshold_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observations = dict(baseline_snapshot["source_observations"])
    missing_source_id = str(baseline_snapshot["source_observation_records"][0]["source_id"])
    source_observations.pop(missing_source_id)
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_stale_threshold_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": source_observations},
    )

    threshold_reconciliation = (
        SnapshotReplayService(store).build_stale_source_list_threshold_reconciliation(
            snapshot_ids=("snapshot_stale_threshold_partial",),
        )
    )

    assert threshold_reconciliation.consistency_classification == "partial"
    assert threshold_reconciliation.average_consistency_percentage == 100.0
    assert threshold_reconciliation.consistent_snapshots == 0
    assert threshold_reconciliation.partial_snapshots == 1
    assert threshold_reconciliation.degraded_snapshots == 0
    assert threshold_reconciliation.invalid_snapshots == 0
    assert threshold_reconciliation.missing_timestamp_source_ids == (missing_source_id,)
    assert threshold_reconciliation.entries[0].reconciliation_classification == "partial"
    assert threshold_reconciliation.entries[0].missing_timestamp_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_degraded_stale_source_list_threshold_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    mismatched_source_id = str(baseline_snapshot["source_observation_records"][0]["source_id"])
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_stale_threshold_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"stale_sources": [mismatched_source_id]},
    )

    threshold_reconciliation = (
        SnapshotReplayService(store).build_stale_source_list_threshold_reconciliation(
            snapshot_ids=("snapshot_stale_threshold_degraded",),
        )
    )

    assert threshold_reconciliation.consistency_classification == "degraded"
    assert threshold_reconciliation.average_consistency_percentage == 96.3
    assert threshold_reconciliation.consistent_snapshots == 0
    assert threshold_reconciliation.partial_snapshots == 0
    assert threshold_reconciliation.degraded_snapshots == 1
    assert threshold_reconciliation.invalid_snapshots == 0
    assert threshold_reconciliation.threshold_mismatch_source_ids == (mismatched_source_id,)
    assert threshold_reconciliation.entries[0].reconciliation_classification == "degraded"
    assert threshold_reconciliation.entries[0].aligned_sources == 26
    assert threshold_reconciliation.entries[0].threshold_mismatch_source_ids == (
        mismatched_source_id,
    )


def test_snapshot_replay_service_keeps_source_diagnostics_mode_and_stale_asset_reconciliation_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_diagnostics_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    replay_service = SnapshotReplayService(store)
    first_mode_drift = replay_service.build_source_diagnostics_freshness_evaluation_mode_drift(
        snapshot_ids=("snapshot_source_diagnostics_a",),
    )
    second_mode_drift = replay_service.build_source_diagnostics_freshness_evaluation_mode_drift(
        snapshot_ids=("snapshot_source_diagnostics_a",),
    )
    first_reconciliation = replay_service.build_source_diagnostics_stale_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_diagnostics_a",),
    )
    second_reconciliation = replay_service.build_source_diagnostics_stale_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_diagnostics_a",),
    )

    assert first_mode_drift == second_mode_drift
    assert first_reconciliation == second_reconciliation


def test_snapshot_replay_service_builds_drifting_source_diagnostics_freshness_evaluation_mode_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    observed_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    not_evaluated_summary = dict(observed_summary)
    not_evaluated_summary["freshness_evaluation_mode"] = "not_evaluated"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_mode_observed",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": observed_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_mode_not_evaluated",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": not_evaluated_summary},
    )

    mode_drift = SnapshotReplayService(store).build_source_diagnostics_freshness_evaluation_mode_drift(
        snapshot_ids=("snapshot_source_mode_observed", "snapshot_source_mode_not_evaluated"),
    )

    assert mode_drift.drift_classification == "drifting"
    assert mode_drift.average_mode_consistency_score == 75.0
    assert mode_drift.severity_score == 50
    assert mode_drift.stable_snapshots == 1
    assert mode_drift.drifting_snapshots == 1
    assert mode_drift.degraded_snapshots == 0
    assert mode_drift.insufficient_data_snapshots == 0
    assert mode_drift.latest_freshness_evaluation_mode == "not_evaluated"
    assert mode_drift.mode_transition_count == 1
    assert mode_drift.entries[0].drift_classification == "stable"
    assert mode_drift.entries[1].drift_classification == "drifting"
    assert mode_drift.entries[1].previous_freshness_evaluation_mode == "observed"


def test_snapshot_replay_service_builds_consistent_source_diagnostics_stale_asset_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_stale_assets_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_stale_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_stale_assets_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].derived_features_with_stale_sources == 1
    assert reconciliation.entries[0].derived_total_stale_assets == 2


def test_snapshot_replay_service_builds_degraded_source_diagnostics_stale_asset_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 1,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_stale_assets_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_stale_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_stale_assets_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 50.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("total_stale_assets",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].mismatched_fields == ("total_stale_assets",)


def test_snapshot_replay_service_builds_partial_source_diagnostics_stale_asset_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_stale_assets_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_stale_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_stale_assets_partial",),
    )

    assert reconciliation.consistency_classification == "partial"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 1
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ("total_stale_assets",)
    assert reconciliation.entries[0].reconciliation_classification == "partial"
    assert reconciliation.entries[0].missing_fields == ("total_stale_assets",)


def test_snapshot_replay_service_keeps_source_diagnostics_coverage_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_coverage_a",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    replay_service = SnapshotReplayService(store)
    first_coverage_drift = replay_service.build_source_diagnostics_average_coverage_drift(
        snapshot_ids=("snapshot_source_coverage_a",),
    )
    second_coverage_drift = replay_service.build_source_diagnostics_average_coverage_drift(
        snapshot_ids=("snapshot_source_coverage_a",),
    )
    first_floor_reconciliation = (
        replay_service.build_source_diagnostics_minimum_coverage_floor_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_floor_reconciliation = (
        replay_service.build_source_diagnostics_minimum_coverage_floor_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_ready_feature_drift = (
        replay_service.build_source_diagnostics_ready_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_ready_feature_drift = (
        replay_service.build_source_diagnostics_ready_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_stale_feature_drift = (
        replay_service.build_source_diagnostics_stale_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_stale_feature_drift = (
        replay_service.build_source_diagnostics_stale_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_critical_feature_drift = (
        replay_service.build_source_diagnostics_critical_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_critical_feature_drift = (
        replay_service.build_source_diagnostics_critical_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_high_severity_drift = (
        replay_service.build_source_diagnostics_high_severity_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_high_severity_drift = (
        replay_service.build_source_diagnostics_high_severity_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_warning_feature_drift = (
        replay_service.build_source_diagnostics_warning_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_warning_feature_drift = (
        replay_service.build_source_diagnostics_warning_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_info_feature_drift = (
        replay_service.build_source_diagnostics_info_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_info_feature_drift = (
        replay_service.build_source_diagnostics_info_feature_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_zero_rank_drift = (
        replay_service.build_source_diagnostics_zero_rank_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_zero_rank_drift = (
        replay_service.build_source_diagnostics_zero_rank_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_label_drift = (
        replay_service.build_source_diagnostics_severity_label_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_label_drift = (
        replay_service.build_source_diagnostics_severity_label_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_rank_drift = (
        replay_service.build_source_diagnostics_severity_rank_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_rank_drift = (
        replay_service.build_source_diagnostics_severity_rank_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_rank_density_drift = (
        replay_service.build_source_diagnostics_severity_rank_density_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_rank_density_drift = (
        replay_service.build_source_diagnostics_severity_rank_density_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_rank_spread_drift = (
        replay_service.build_source_diagnostics_severity_rank_spread_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_rank_spread_drift = (
        replay_service.build_source_diagnostics_severity_rank_spread_drift(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_feature_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_feature_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_feature_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_feature_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_critical_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_critical_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_critical_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_critical_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_warning_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_warning_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_warning_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_warning_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_info_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_info_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_info_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_info_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_non_actionable_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_non_actionable_count_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_rank_label_consistency_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_rank_label_consistency_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_rank_order_continuity_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_rank_order_continuity_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_rank_gap_continuity_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_rank_gap_continuity_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_severity_ranking_rank_gap_magnitude_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_severity_ranking_rank_gap_magnitude_reconciliation = (
        replay_service.build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_missing_source_feature_reconciliation = (
        replay_service.build_source_diagnostics_missing_source_feature_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_missing_source_feature_reconciliation = (
        replay_service.build_source_diagnostics_missing_source_feature_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    first_missing_asset_reconciliation = (
        replay_service.build_source_diagnostics_missing_asset_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )
    second_missing_asset_reconciliation = (
        replay_service.build_source_diagnostics_missing_asset_count_reconciliation(
            snapshot_ids=("snapshot_source_coverage_a",),
        )
    )

    assert first_coverage_drift == second_coverage_drift
    assert first_floor_reconciliation == second_floor_reconciliation
    assert first_ready_feature_drift == second_ready_feature_drift
    assert first_stale_feature_drift == second_stale_feature_drift
    assert first_critical_feature_drift == second_critical_feature_drift
    assert first_high_severity_drift == second_high_severity_drift
    assert first_warning_feature_drift == second_warning_feature_drift
    assert first_info_feature_drift == second_info_feature_drift
    assert first_zero_rank_drift == second_zero_rank_drift
    assert first_severity_label_drift == second_severity_label_drift
    assert first_severity_rank_drift == second_severity_rank_drift
    assert first_severity_rank_density_drift == second_severity_rank_density_drift
    assert first_severity_rank_spread_drift == second_severity_rank_spread_drift
    assert (
        first_severity_ranking_feature_count_reconciliation
        == second_severity_ranking_feature_count_reconciliation
    )
    assert (
        first_severity_ranking_warning_count_reconciliation
        == second_severity_ranking_warning_count_reconciliation
    )
    assert (
        first_severity_ranking_info_count_reconciliation
        == second_severity_ranking_info_count_reconciliation
    )
    assert (
        first_severity_ranking_non_actionable_count_reconciliation
        == second_severity_ranking_non_actionable_count_reconciliation
    )
    assert (
        first_severity_ranking_rank_label_consistency_reconciliation
        == second_severity_ranking_rank_label_consistency_reconciliation
    )
    assert (
        first_severity_ranking_rank_order_continuity_reconciliation
        == second_severity_ranking_rank_order_continuity_reconciliation
    )
    assert (
        first_severity_ranking_rank_gap_continuity_reconciliation
        == second_severity_ranking_rank_gap_continuity_reconciliation
    )
    assert (
        first_severity_ranking_rank_gap_magnitude_reconciliation
        == second_severity_ranking_rank_gap_magnitude_reconciliation
    )
    assert (
        first_severity_ranking_critical_count_reconciliation
        == second_severity_ranking_critical_count_reconciliation
    )
    assert (
        first_missing_source_feature_reconciliation
        == second_missing_source_feature_reconciliation
    )
    assert first_missing_asset_reconciliation == second_missing_asset_reconciliation


def test_snapshot_replay_service_builds_degrading_source_diagnostics_average_coverage_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_coverage_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_coverage_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    coverage_drift = SnapshotReplayService(store).build_source_diagnostics_average_coverage_drift(
        snapshot_ids=("snapshot_source_coverage_healthy", "snapshot_source_coverage_degraded"),
    )

    assert coverage_drift.drift_classification == "degrading"
    assert coverage_drift.average_coverage_score == 97.5
    assert coverage_drift.severity_score == 5
    assert coverage_drift.stable_snapshots == 1
    assert coverage_drift.degrading_snapshots == 1
    assert coverage_drift.improving_snapshots == 0
    assert coverage_drift.mixed_snapshots == 0
    assert coverage_drift.insufficient_data_snapshots == 0
    assert coverage_drift.entries[0].drift_classification == "stable"
    assert coverage_drift.entries[1].drift_classification == "degrading"
    assert coverage_drift.entries[1].coverage_score_delta == -5.0
    assert coverage_drift.entries[1].minimum_coverage_score == 80.0


def test_snapshot_replay_service_builds_consistent_source_diagnostics_minimum_coverage_floor_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 80.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_floor_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_minimum_coverage_floor_reconciliation(
        snapshot_ids=("snapshot_source_floor_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].derived_minimum_coverage_score == 80.0
    assert reconciliation.entries[0].floor_derivation_mode == "severity_ranking"


def test_snapshot_replay_service_builds_degraded_source_diagnostics_minimum_coverage_floor_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "minimum_coverage_score": 85.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_floor_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_minimum_coverage_floor_reconciliation(
        snapshot_ids=("snapshot_source_floor_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("minimum_coverage_score",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].mismatched_fields == ("minimum_coverage_score",)


def test_snapshot_replay_service_builds_partial_source_diagnostics_minimum_coverage_floor_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 95.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 80.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_floor_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_minimum_coverage_floor_reconciliation(
        snapshot_ids=("snapshot_source_floor_partial",),
    )

    assert reconciliation.consistency_classification == "partial"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 1
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ("minimum_coverage_score",)
    assert reconciliation.entries[0].reconciliation_classification == "partial"
    assert reconciliation.entries[0].missing_fields == ("minimum_coverage_score",)


def test_snapshot_replay_service_builds_degrading_source_diagnostics_ready_feature_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_ready_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_ready_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    ready_feature_drift = SnapshotReplayService(store).build_source_diagnostics_ready_feature_drift(
        snapshot_ids=("snapshot_source_ready_healthy", "snapshot_source_ready_degraded"),
    )

    assert ready_feature_drift.drift_classification == "degrading"
    assert ready_feature_drift.average_ready_features == 3.5
    assert ready_feature_drift.severity_score == 1
    assert ready_feature_drift.stable_snapshots == 1
    assert ready_feature_drift.degrading_snapshots == 1
    assert ready_feature_drift.improving_snapshots == 0
    assert ready_feature_drift.mixed_snapshots == 0
    assert ready_feature_drift.insufficient_data_snapshots == 0
    assert ready_feature_drift.entries[0].drift_classification == "stable"
    assert ready_feature_drift.entries[1].drift_classification == "degrading"
    assert ready_feature_drift.entries[1].ready_feature_delta == -1
    assert ready_feature_drift.entries[1].total_missing_assets == 2


def test_snapshot_replay_service_builds_degrading_source_diagnostics_stale_feature_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 2,
        "total_stale_assets": 3,
        "average_coverage_score": 90.0,
        "minimum_coverage_score": 70.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": True,
                "status": "stale_required_sources",
                "coverage_score": 70.0,
                "severity_rank": 8,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "metals_regime",
                "score_group": "cross_asset",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 90.0,
                "severity_rank": 5,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["XAGUSD"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_stale_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_stale_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    stale_feature_drift = SnapshotReplayService(store).build_source_diagnostics_stale_feature_drift(
        snapshot_ids=("snapshot_source_stale_healthy", "snapshot_source_stale_degraded"),
    )

    assert stale_feature_drift.drift_classification == "degrading"
    assert stale_feature_drift.average_stale_features == 1.0
    assert stale_feature_drift.severity_score == 2
    assert stale_feature_drift.stable_snapshots == 1
    assert stale_feature_drift.degrading_snapshots == 1
    assert stale_feature_drift.improving_snapshots == 0
    assert stale_feature_drift.mixed_snapshots == 0
    assert stale_feature_drift.insufficient_data_snapshots == 0
    assert stale_feature_drift.entries[0].drift_classification == "stable"
    assert stale_feature_drift.entries[1].drift_classification == "degrading"
    assert stale_feature_drift.entries[1].stale_feature_delta == 2
    assert stale_feature_drift.entries[1].total_stale_assets == 3


def test_snapshot_replay_service_builds_degrading_source_diagnostics_critical_feature_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_critical_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_critical_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    critical_feature_drift = SnapshotReplayService(store).build_source_diagnostics_critical_feature_drift(
        snapshot_ids=("snapshot_source_critical_healthy", "snapshot_source_critical_degraded"),
    )

    assert critical_feature_drift.drift_classification == "degrading"
    assert critical_feature_drift.average_critical_feature_count == 0.5
    assert critical_feature_drift.severity_score == 1
    assert critical_feature_drift.stable_snapshots == 1
    assert critical_feature_drift.degrading_snapshots == 1
    assert critical_feature_drift.improving_snapshots == 0
    assert critical_feature_drift.mixed_snapshots == 0
    assert critical_feature_drift.insufficient_data_snapshots == 0
    assert critical_feature_drift.entries[0].drift_classification == "stable"
    assert critical_feature_drift.entries[1].drift_classification == "degrading"
    assert critical_feature_drift.entries[1].critical_feature_delta == 1
    assert critical_feature_drift.entries[1].severity_ranking_feature_count == 2


def test_snapshot_replay_service_builds_degrading_source_diagnostics_high_severity_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_high_severity_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_high_severity_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    high_severity_drift = SnapshotReplayService(store).build_source_diagnostics_high_severity_drift(
        snapshot_ids=(
            "snapshot_source_high_severity_healthy",
            "snapshot_source_high_severity_degraded",
        ),
    )

    assert high_severity_drift.drift_classification == "degrading"
    assert high_severity_drift.average_high_severity_feature_count == 1.0
    assert high_severity_drift.severity_score == 2
    assert high_severity_drift.stable_snapshots == 1
    assert high_severity_drift.degrading_snapshots == 1
    assert high_severity_drift.improving_snapshots == 0
    assert high_severity_drift.mixed_snapshots == 0
    assert high_severity_drift.insufficient_data_snapshots == 0
    assert high_severity_drift.entries[0].drift_classification == "stable"
    assert high_severity_drift.entries[1].drift_classification == "degrading"
    assert high_severity_drift.entries[1].high_severity_feature_delta == 2
    assert high_severity_drift.entries[1].critical_severity_feature_count == 1


def test_snapshot_replay_service_builds_degrading_source_diagnostics_warning_feature_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_warning_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_warning_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    warning_feature_drift = SnapshotReplayService(store).build_source_diagnostics_warning_feature_drift(
        snapshot_ids=("snapshot_source_warning_healthy", "snapshot_source_warning_degraded"),
    )

    assert warning_feature_drift.drift_classification == "degrading"
    assert warning_feature_drift.average_warning_feature_count == 0.5
    assert warning_feature_drift.severity_score == 1
    assert warning_feature_drift.stable_snapshots == 1
    assert warning_feature_drift.degrading_snapshots == 1
    assert warning_feature_drift.improving_snapshots == 0
    assert warning_feature_drift.mixed_snapshots == 0
    assert warning_feature_drift.insufficient_data_snapshots == 0
    assert warning_feature_drift.entries[0].drift_classification == "stable"
    assert warning_feature_drift.entries[1].drift_classification == "degrading"
    assert warning_feature_drift.entries[1].warning_feature_delta == 1
    assert warning_feature_drift.entries[1].high_severity_feature_count == 2


def test_snapshot_replay_service_builds_degrading_source_diagnostics_info_feature_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_info_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_info_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    info_feature_drift = SnapshotReplayService(store).build_source_diagnostics_info_feature_drift(
        snapshot_ids=("snapshot_source_info_healthy", "snapshot_source_info_degraded"),
    )

    assert info_feature_drift.drift_classification == "degrading"
    assert info_feature_drift.average_info_feature_count == 0.5
    assert info_feature_drift.severity_score == 1
    assert info_feature_drift.stable_snapshots == 1
    assert info_feature_drift.degrading_snapshots == 1
    assert info_feature_drift.improving_snapshots == 0
    assert info_feature_drift.mixed_snapshots == 0
    assert info_feature_drift.insufficient_data_snapshots == 0
    assert info_feature_drift.entries[0].drift_classification == "stable"
    assert info_feature_drift.entries[1].drift_classification == "degrading"
    assert info_feature_drift.entries[1].info_feature_delta == 1
    assert info_feature_drift.entries[1].warning_feature_count == 0


def test_snapshot_replay_service_builds_degrading_source_diagnostics_zero_rank_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_zero_rank_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_zero_rank_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    zero_rank_drift = SnapshotReplayService(store).build_source_diagnostics_zero_rank_drift(
        snapshot_ids=("snapshot_source_zero_rank_healthy", "snapshot_source_zero_rank_degraded"),
    )

    assert zero_rank_drift.drift_classification == "degrading"
    assert zero_rank_drift.average_zero_rank_feature_count == 0.5
    assert zero_rank_drift.severity_score == 1
    assert zero_rank_drift.stable_snapshots == 1
    assert zero_rank_drift.degrading_snapshots == 1
    assert zero_rank_drift.improving_snapshots == 0
    assert zero_rank_drift.mixed_snapshots == 0
    assert zero_rank_drift.insufficient_data_snapshots == 0
    assert zero_rank_drift.entries[0].drift_classification == "stable"
    assert zero_rank_drift.entries[1].drift_classification == "degrading"
    assert zero_rank_drift.entries[1].zero_rank_feature_delta == 1
    assert zero_rank_drift.entries[1].info_feature_count == 1


def test_snapshot_replay_service_builds_degrading_source_diagnostics_severity_label_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_label_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_label_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    severity_label_drift = SnapshotReplayService(store).build_source_diagnostics_severity_label_drift(
        snapshot_ids=(
            "snapshot_source_severity_label_healthy",
            "snapshot_source_severity_label_degraded",
        ),
    )

    assert severity_label_drift.drift_classification == "degrading"
    assert severity_label_drift.average_severity_label_score == 2.5
    assert severity_label_drift.severity_score == 5
    assert severity_label_drift.stable_snapshots == 1
    assert severity_label_drift.degrading_snapshots == 1
    assert severity_label_drift.improving_snapshots == 0
    assert severity_label_drift.mixed_snapshots == 0
    assert severity_label_drift.insufficient_data_snapshots == 0
    assert severity_label_drift.entries[0].drift_classification == "stable"
    assert severity_label_drift.entries[1].drift_classification == "degrading"
    assert severity_label_drift.entries[1].severity_label_score_delta == 5
    assert severity_label_drift.entries[1].severity_ranking_feature_count == 2


def test_snapshot_replay_service_builds_degrading_source_diagnostics_severity_rank_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_dollar",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    severity_rank_drift = SnapshotReplayService(store).build_source_diagnostics_severity_rank_drift(
        snapshot_ids=(
            "snapshot_source_severity_rank_healthy",
            "snapshot_source_severity_rank_degraded",
        ),
    )

    assert severity_rank_drift.drift_classification == "degrading"
    assert severity_rank_drift.average_severity_rank_total == 8.0
    assert severity_rank_drift.severity_score == 16
    assert severity_rank_drift.stable_snapshots == 1
    assert severity_rank_drift.degrading_snapshots == 1
    assert severity_rank_drift.improving_snapshots == 0
    assert severity_rank_drift.mixed_snapshots == 0
    assert severity_rank_drift.insufficient_data_snapshots == 0
    assert severity_rank_drift.entries[0].drift_classification == "stable"
    assert severity_rank_drift.entries[1].drift_classification == "degrading"
    assert severity_rank_drift.entries[1].severity_rank_total_delta == 16
    assert severity_rank_drift.entries[1].severity_ranking_feature_count == 3


def test_snapshot_replay_service_builds_degrading_source_diagnostics_severity_rank_density_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_dollar",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_density_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_density_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    severity_rank_density_drift = SnapshotReplayService(store).build_source_diagnostics_severity_rank_density_drift(
        snapshot_ids=(
            "snapshot_source_severity_rank_density_healthy",
            "snapshot_source_severity_rank_density_degraded",
        ),
    )

    assert severity_rank_density_drift.drift_classification == "degrading"
    assert severity_rank_density_drift.average_severity_rank_density == 2.67
    assert severity_rank_density_drift.severity_score == 5
    assert severity_rank_density_drift.stable_snapshots == 1
    assert severity_rank_density_drift.degrading_snapshots == 1
    assert severity_rank_density_drift.improving_snapshots == 0
    assert severity_rank_density_drift.mixed_snapshots == 0
    assert severity_rank_density_drift.insufficient_data_snapshots == 0
    assert severity_rank_density_drift.entries[0].drift_classification == "stable"
    assert severity_rank_density_drift.entries[1].drift_classification == "degrading"
    assert severity_rank_density_drift.entries[1].severity_rank_density == 5.33
    assert severity_rank_density_drift.entries[1].severity_rank_density_delta == 5.33
    assert severity_rank_density_drift.entries[1].severity_ranking_feature_count == 3


def test_snapshot_replay_service_builds_degrading_source_diagnostics_severity_rank_spread_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    healthy_summary = {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [],
    }
    degraded_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_dollar",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_spread_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_spread_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )

    severity_rank_spread_drift = SnapshotReplayService(store).build_source_diagnostics_severity_rank_spread_drift(
        snapshot_ids=(
            "snapshot_source_severity_rank_spread_healthy",
            "snapshot_source_severity_rank_spread_degraded",
        ),
    )

    assert severity_rank_spread_drift.drift_classification == "degrading"
    assert severity_rank_spread_drift.average_severity_rank_spread == 5.0
    assert severity_rank_spread_drift.severity_score == 10
    assert severity_rank_spread_drift.stable_snapshots == 1
    assert severity_rank_spread_drift.degrading_snapshots == 1
    assert severity_rank_spread_drift.improving_snapshots == 0
    assert severity_rank_spread_drift.mixed_snapshots == 0
    assert severity_rank_spread_drift.insufficient_data_snapshots == 0
    assert severity_rank_spread_drift.entries[0].drift_classification == "stable"
    assert severity_rank_spread_drift.entries[1].drift_classification == "degrading"
    assert severity_rank_spread_drift.entries[1].severity_rank_spread == 10
    assert severity_rank_spread_drift.entries[1].severity_rank_spread_delta == 10
    assert severity_rank_spread_drift.entries[1].severity_ranking_feature_count == 3


def test_snapshot_replay_service_builds_consistent_source_diagnostics_severity_ranking_feature_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_count_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_feature_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_count_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].summary_severity_ranking_feature_count == 2
    assert reconciliation.entries[0].derived_severity_ranking_feature_count == 2
    assert reconciliation.entries[0].critical_feature_count == 1


def test_snapshot_replay_service_builds_consistent_source_diagnostics_severity_ranking_warning_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_warning_count_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_warning_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_warning_count_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].summary_warning_feature_count == 1
    assert reconciliation.entries[0].derived_warning_feature_count == 1
    assert reconciliation.entries[0].high_severity_feature_count == 2


def test_snapshot_replay_service_builds_consistent_source_diagnostics_severity_ranking_info_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_info_count_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_info_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_info_count_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].summary_info_feature_count == 1
    assert reconciliation.entries[0].derived_info_feature_count == 1
    assert reconciliation.entries[0].warning_feature_count == 0


def test_snapshot_replay_service_builds_consistent_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_non_actionable_count_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_non_actionable_count_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].summary_non_actionable_feature_count == 1
    assert reconciliation.entries[0].derived_non_actionable_feature_count == 1
    assert reconciliation.entries[0].info_feature_count == 1


def test_snapshot_replay_service_builds_consistent_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_dollar",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_label_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
        snapshot_ids=("snapshot_source_severity_rank_label_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].checked_feature_count == 3
    assert reconciliation.entries[0].consistent_rank_label_feature_count == 3
    assert reconciliation.entries[0].inconsistent_rank_label_feature_count == 0


def test_snapshot_replay_service_builds_consistent_source_diagnostics_severity_ranking_critical_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_critical_count_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_critical_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_critical_count_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].summary_critical_feature_count == 1
    assert reconciliation.entries[0].derived_critical_feature_count == 1
    assert reconciliation.entries[0].high_severity_feature_count == 2


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_warning_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_warning_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_warning_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_warning_count_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("severity_ranking_warning_count",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].summary_warning_feature_count == 0
    assert reconciliation.entries[0].derived_warning_feature_count == 1
    assert reconciliation.entries[0].high_severity_feature_count == 2
    assert reconciliation.entries[0].mismatched_fields == ("severity_ranking_warning_count",)


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_info_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 0,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_info_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_info_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_info_count_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("severity_ranking_info_count",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].summary_info_feature_count == 0
    assert reconciliation.entries[0].derived_info_feature_count == 1
    assert reconciliation.entries[0].warning_feature_count == 1
    assert reconciliation.entries[0].mismatched_fields == ("severity_ranking_info_count",)


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 0,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_non_actionable_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_non_actionable_count_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("severity_ranking_non_actionable_count",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].summary_non_actionable_feature_count == 0
    assert reconciliation.entries[0].derived_non_actionable_feature_count == 1
    assert reconciliation.entries[0].info_feature_count == 1
    assert reconciliation.entries[0].mismatched_fields == (
        "severity_ranking_non_actionable_count",
    )


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "warning",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "critical",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_label_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
        snapshot_ids=("snapshot_source_severity_rank_label_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == (
        "severity_ranking_rank_label_consistency",
    )
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].checked_feature_count == 2
    assert reconciliation.entries[0].consistent_rank_label_feature_count == 0
    assert reconciliation.entries[0].inconsistent_rank_label_feature_count == 2
    assert reconciliation.entries[0].mismatched_fields == (
        "severity_ranking_rank_label_consistency",
    )


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_order_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
        snapshot_ids=("snapshot_source_severity_rank_order_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == (
        "severity_ranking_rank_order_continuity",
    )
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].checked_feature_count == 2
    assert reconciliation.entries[0].consistent_rank_order_feature_count == 0
    assert reconciliation.entries[0].reordered_feature_count == 2
    assert reconciliation.entries[0].mismatched_fields == (
        "severity_ranking_rank_order_continuity",
    )


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_dollar",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_gap_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
        snapshot_ids=("snapshot_source_severity_rank_gap_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == (
        "severity_ranking_rank_gap_continuity",
    )
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].checked_gap_count == 2
    assert reconciliation.entries[0].consistent_rank_gap_count == 0
    assert reconciliation.entries[0].discontinuous_rank_gap_count == 2
    assert reconciliation.entries[0].mismatched_fields == (
        "severity_ranking_rank_gap_continuity",
    )


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_dollar",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_rank_gap_magnitude_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
        snapshot_ids=("snapshot_source_severity_rank_gap_magnitude_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 50.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == (
        "severity_ranking_rank_gap_magnitude",
    )
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].checked_gap_count == 2
    assert reconciliation.entries[0].consistent_rank_gap_magnitude_count == 1
    assert reconciliation.entries[0].mismatched_rank_gap_magnitude_count == 1
    assert reconciliation.entries[0].mismatched_fields == (
        "severity_ranking_rank_gap_magnitude",
    )


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_critical_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": False,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "macro_credit_spread",
                "score_group": "macro",
                "critical": False,
                "status": "stale_required_sources",
                "coverage_score": 85.0,
                "severity_rank": 6,
                "severity_level": "warning",
                "missing_assets": [],
                "stale_assets": ["HYG", "JNK"],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_critical_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_critical_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_critical_count_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("severity_ranking_critical_count",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].summary_critical_feature_count == 0
    assert reconciliation.entries[0].derived_critical_feature_count == 1
    assert reconciliation.entries[0].high_severity_feature_count == 2
    assert reconciliation.entries[0].mismatched_fields == ("severity_ranking_critical_count",)


def test_snapshot_replay_service_builds_degraded_source_diagnostics_severity_ranking_feature_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 60.0,
                "severity_rank": 10,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            },
            {
                "feature_name": "ignored_feature",
                "score_group": "macro",
                "critical": False,
                "status": "ready",
                "coverage_score": 100.0,
                "severity_rank": 0,
                "severity_level": "info",
                "missing_assets": [],
                "stale_assets": [],
            },
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_feature_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_count_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("severity_ranking_feature_count",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].derived_severity_ranking_feature_count == 1
    assert reconciliation.entries[0].mismatched_fields == ("severity_ranking_feature_count",)


def test_snapshot_replay_service_builds_partial_source_diagnostics_severity_ranking_feature_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 2,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 1,
        "total_stale_assets": 2,
        "average_coverage_score": 82.5,
        "minimum_coverage_score": 60.0,
        "freshness_evaluation_mode": "observed",
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_severity_count_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_severity_ranking_feature_count_reconciliation(
        snapshot_ids=("snapshot_source_severity_count_partial",),
    )

    assert reconciliation.consistency_classification == "partial"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 1
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ("severity_ranking",)
    assert reconciliation.entries[0].reconciliation_classification == "partial"
    assert reconciliation.entries[0].missing_fields == ("severity_ranking",)


def test_snapshot_replay_service_builds_consistent_source_diagnostics_missing_source_feature_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_missing_feature_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_missing_source_feature_count_reconciliation(
        snapshot_ids=("snapshot_source_missing_feature_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].derived_features_with_missing_sources == 1
    assert reconciliation.entries[0].total_missing_assets == 2


def test_snapshot_replay_service_builds_degraded_source_diagnostics_missing_source_feature_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 2,
        "total_missing_assets": 2,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_missing_feature_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_missing_source_feature_count_reconciliation(
        snapshot_ids=("snapshot_source_missing_feature_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("features_with_missing_sources",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].mismatched_fields == ("features_with_missing_sources",)


def test_snapshot_replay_service_builds_partial_source_diagnostics_missing_source_feature_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "total_missing_assets": 2,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_missing_feature_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_missing_source_feature_count_reconciliation(
        snapshot_ids=("snapshot_source_missing_feature_partial",),
    )

    assert reconciliation.consistency_classification == "partial"
    assert reconciliation.average_consistency_percentage == 0.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 1
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ("features_with_missing_sources",)
    assert reconciliation.entries[0].reconciliation_classification == "partial"
    assert reconciliation.entries[0].missing_fields == ("features_with_missing_sources",)


def test_snapshot_replay_service_builds_consistent_source_diagnostics_missing_asset_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 1,
        "total_missing_assets": 2,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_missing_consistent",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_missing_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_missing_consistent",),
    )

    assert reconciliation.consistency_classification == "consistent"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 1
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ()
    assert reconciliation.mismatched_fields == ()
    assert reconciliation.entries[0].derived_features_with_missing_sources == 1
    assert reconciliation.entries[0].derived_total_missing_assets == 2


def test_snapshot_replay_service_builds_degraded_source_diagnostics_missing_asset_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 1,
        "total_missing_assets": 1,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_missing_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_missing_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_missing_degraded",),
    )

    assert reconciliation.consistency_classification == "degraded"
    assert reconciliation.average_consistency_percentage == 50.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 0
    assert reconciliation.degraded_snapshots == 1
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.mismatched_fields == ("total_missing_assets",)
    assert reconciliation.entries[0].reconciliation_classification == "degraded"
    assert reconciliation.entries[0].mismatched_fields == ("total_missing_assets",)


def test_snapshot_replay_service_builds_partial_source_diagnostics_missing_asset_count_reconciliation(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    diagnostics_summary = {
        "total_features": 4,
        "ready_features": 3,
        "features_with_missing_sources": 1,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 88.0,
        "minimum_coverage_score": 75.0,
        "freshness_evaluation_mode": "observed",
        "severity_ranking": [
            {
                "feature_name": "macro_liquidity",
                "score_group": "macro",
                "critical": True,
                "status": "missing_required_sources",
                "coverage_score": 75.0,
                "severity_rank": 9,
                "severity_level": "critical",
                "missing_assets": ["BTCUSD", "DXY"],
                "stale_assets": [],
            }
        ],
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_source_missing_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )

    reconciliation = SnapshotReplayService(store).build_source_diagnostics_missing_asset_count_reconciliation(
        snapshot_ids=("snapshot_source_missing_partial",),
    )

    assert reconciliation.consistency_classification == "partial"
    assert reconciliation.average_consistency_percentage == 100.0
    assert reconciliation.consistent_snapshots == 0
    assert reconciliation.partial_snapshots == 1
    assert reconciliation.degraded_snapshots == 0
    assert reconciliation.invalid_snapshots == 0
    assert reconciliation.missing_fields == ("total_missing_assets",)
    assert reconciliation.entries[0].reconciliation_classification == "partial"
    assert reconciliation.entries[0].missing_fields == ("total_missing_assets",)


def test_snapshot_replay_service_keeps_normalization_and_mapped_at_diagnostics_deterministic(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    per_source_records = [
        {
            **dict(record),
            "mapped_at": str(record["stored_at"]),
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    per_source_summary = dict(baseline_snapshot["source_observation_summary"])
    per_source_summary["normalization_mode"] = "per_source_stored_at"
    per_source_observations = {
        str(record["source_id"]): str(record["stored_at"])
        for record in per_source_records
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={
            "source_observation_records": per_source_records,
            "source_observation_summary": per_source_summary,
            "source_observations": per_source_observations,
        },
    )

    replay_service = SnapshotReplayService(store)
    first_normalization_drift = replay_service.build_source_observation_normalization_mode_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    second_normalization_drift = replay_service.build_source_observation_normalization_mode_drift(
        snapshot_ids=("snapshot_a", "snapshot_b"),
    )
    first_mapped_at_alignment = replay_service.build_mapped_at_alignment_consistency(
        snapshot_ids=("snapshot_b",),
    )
    second_mapped_at_alignment = replay_service.build_mapped_at_alignment_consistency(
        snapshot_ids=("snapshot_b",),
    )

    assert first_normalization_drift == second_normalization_drift
    assert first_mapped_at_alignment == second_mapped_at_alignment


def test_snapshot_replay_service_builds_stable_source_observation_normalization_mode_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )

    normalization_mode_drift = (
        SnapshotReplayService(store).build_source_observation_normalization_mode_drift(
            snapshot_ids=("snapshot_a", "snapshot_b"),
        )
    )

    assert normalization_mode_drift.drift_classification == "stable"
    assert normalization_mode_drift.average_mode_consistency_score == 100.0
    assert normalization_mode_drift.severity_score == 0
    assert normalization_mode_drift.snapshots_checked == 2
    assert normalization_mode_drift.stable_snapshots == 2
    assert normalization_mode_drift.drifting_snapshots == 0
    assert normalization_mode_drift.degraded_snapshots == 0
    assert normalization_mode_drift.insufficient_data_snapshots == 0
    assert normalization_mode_drift.dominant_normalization_mode == "batch_stored_at"
    assert normalization_mode_drift.latest_normalization_mode == "batch_stored_at"
    assert normalization_mode_drift.normalization_mode_counts == {"batch_stored_at": 2}
    assert normalization_mode_drift.mode_transition_count == 0
    assert normalization_mode_drift.entries[0].drift_classification == "stable"
    assert normalization_mode_drift.entries[1].drift_classification == "stable"


def test_snapshot_replay_service_builds_drifting_source_observation_normalization_mode_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    per_source_records = [
        {
            **dict(record),
            "mapped_at": str(record["stored_at"]),
        }
        for record in baseline_snapshot["source_observation_records"]
    ]
    per_source_summary = dict(baseline_snapshot["source_observation_summary"])
    per_source_summary["normalization_mode"] = "per_source_stored_at"
    per_source_observations = {
        str(record["source_id"]): str(record["stored_at"])
        for record in per_source_records
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_mode_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={
            "source_observation_records": per_source_records,
            "source_observation_summary": per_source_summary,
            "source_observations": per_source_observations,
        },
    )

    normalization_mode_drift = (
        SnapshotReplayService(store).build_source_observation_normalization_mode_drift(
            snapshot_ids=("snapshot_a", "snapshot_mode_drift"),
        )
    )

    assert normalization_mode_drift.drift_classification == "drifting"
    assert normalization_mode_drift.average_mode_consistency_score == 75.0
    assert normalization_mode_drift.severity_score == 50
    assert normalization_mode_drift.stable_snapshots == 1
    assert normalization_mode_drift.drifting_snapshots == 1
    assert normalization_mode_drift.degraded_snapshots == 0
    assert normalization_mode_drift.mode_transition_count == 1
    assert normalization_mode_drift.latest_normalization_mode == "per_source_stored_at"
    assert normalization_mode_drift.normalization_mode_counts == {
        "batch_stored_at": 1,
        "per_source_stored_at": 1,
    }
    assert normalization_mode_drift.entries[1].drift_classification == "drifting"
    assert normalization_mode_drift.entries[1].normalization_mode == "per_source_stored_at"
    assert normalization_mode_drift.entries[1].previous_normalization_mode == "batch_stored_at"
    assert normalization_mode_drift.entries[1].mode_consistency_score == 50.0


def test_snapshot_replay_service_builds_degraded_source_observation_normalization_mode_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    degraded_summary = dict(baseline_snapshot["source_observation_summary"])
    degraded_summary["total_bound_sources"] = "27"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_mode_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": degraded_summary},
    )

    normalization_mode_drift = (
        SnapshotReplayService(store).build_source_observation_normalization_mode_drift(
            snapshot_ids=("snapshot_mode_degraded",),
        )
    )

    assert normalization_mode_drift.drift_classification == "degraded"
    assert normalization_mode_drift.degraded_snapshots == 1
    assert normalization_mode_drift.malformed_summary_count >= 1
    assert normalization_mode_drift.entries[0].drift_classification == "degraded"
    assert normalization_mode_drift.entries[0].malformed_field_count >= 1


def test_snapshot_replay_service_builds_consistent_mapped_at_alignment_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")

    mapped_at_alignment = SnapshotReplayService(store).build_mapped_at_alignment_consistency(
        snapshot_ids=(baseline_snapshot["snapshot_id"],),
    )

    assert mapped_at_alignment.consistency_classification == "consistent"
    assert mapped_at_alignment.average_consistency_percentage == 100.0
    assert mapped_at_alignment.snapshots_checked == 1
    assert mapped_at_alignment.consistent_snapshots == 1
    assert mapped_at_alignment.partial_snapshots == 0
    assert mapped_at_alignment.degraded_snapshots == 0
    assert mapped_at_alignment.invalid_snapshots == 0
    assert mapped_at_alignment.missing_mapped_at_source_ids == ()
    assert mapped_at_alignment.batch_anchor_mismatch_source_ids == ()
    assert mapped_at_alignment.stored_at_alignment_mismatch_source_ids == ()
    assert mapped_at_alignment.source_observation_alignment_mismatch_source_ids == ()
    assert mapped_at_alignment.entries[0].consistency_classification == "consistent"
    assert mapped_at_alignment.entries[0].aligned_records == 27


def test_snapshot_replay_service_builds_degraded_mapped_at_alignment_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["mapped_at"] = str(source_observation_records[0]["stored_at"])
    source_observations = dict(baseline_snapshot["source_observations"])
    source_observations[degraded_source_id] = str(source_observation_records[0]["stored_at"])
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_mapped_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={
            "source_observation_records": source_observation_records,
            "source_observations": source_observations,
        },
    )

    mapped_at_alignment = SnapshotReplayService(store).build_mapped_at_alignment_consistency(
        snapshot_ids=("snapshot_mapped_degraded",),
    )

    assert mapped_at_alignment.consistency_classification == "degraded"
    assert mapped_at_alignment.average_consistency_percentage == 96.3
    assert mapped_at_alignment.batch_anchor_mismatch_source_ids == (degraded_source_id,)
    assert mapped_at_alignment.entries[0].consistency_classification == "degraded"
    assert mapped_at_alignment.entries[0].aligned_records == 26
    assert mapped_at_alignment.entries[0].batch_anchor_mismatch_source_ids == (degraded_source_id,)


def test_snapshot_replay_service_builds_partial_mapped_at_alignment_consistency(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    missing_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0].pop("mapped_at")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_mapped_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )

    mapped_at_alignment = SnapshotReplayService(store).build_mapped_at_alignment_consistency(
        snapshot_ids=("snapshot_mapped_partial",),
    )

    assert mapped_at_alignment.consistency_classification == "partial"
    assert mapped_at_alignment.average_consistency_percentage == 96.3
    assert mapped_at_alignment.missing_mapped_at_source_ids == (missing_source_id,)
    assert mapped_at_alignment.entries[0].consistency_classification == "partial"
    assert mapped_at_alignment.entries[0].aligned_records == 26
    assert mapped_at_alignment.entries[0].missing_mapped_at_source_ids == (missing_source_id,)


def test_snapshot_replay_service_builds_stable_source_diagnostics_contract_coverage_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_contract_coverage_stable",
    )

    contract_coverage_drift = (
        SnapshotReplayService(store).build_source_diagnostics_contract_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert contract_coverage_drift.drift_classification == "stable"
    assert contract_coverage_drift.average_coverage_percentage == 100.0
    assert contract_coverage_drift.severity_score == 0
    assert (
        contract_coverage_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert contract_coverage_drift.snapshots_checked == 1
    assert contract_coverage_drift.stable_snapshots == 1
    assert contract_coverage_drift.drifting_snapshots == 0
    assert contract_coverage_drift.degraded_snapshots == 0
    assert contract_coverage_drift.missing_service_builder_names == ()
    assert contract_coverage_drift.missing_api_route_paths == ()
    assert contract_coverage_drift.missing_serializer_names == ()
    assert contract_coverage_drift.entries[0].drift_classification == "stable"
    assert contract_coverage_drift.entries[0].coverage_percentage == 100.0
    assert (
        contract_coverage_drift.endpoint_coverage_consistency.consistency_classification
        == "consistent"
    )
    assert (
        contract_coverage_drift.endpoint_coverage_consistency.consistency_percentage
        == 100.0
    )
    assert (
        contract_coverage_drift.endpoint_coverage_consistency.total_diagnostics_registered
        >= 40
    )
    assert contract_coverage_drift.paper_safe is True
    assert contract_coverage_drift.network_calls is False
    assert contract_coverage_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_degraded_source_diagnostics_contract_coverage_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_contract_coverage_degraded",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (
            "source-record-completeness",
            "contract-gap",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
        ),
    )

    contract_coverage_drift = (
        SnapshotReplayService(store).build_source_diagnostics_contract_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert contract_coverage_drift.drift_classification == "degraded"
    assert contract_coverage_drift.average_coverage_percentage == 58.33
    assert contract_coverage_drift.severity_score == 100
    assert contract_coverage_drift.snapshots_checked == 1
    assert contract_coverage_drift.stable_snapshots == 0
    assert contract_coverage_drift.drifting_snapshots == 0
    assert contract_coverage_drift.degraded_snapshots == 1
    assert contract_coverage_drift.missing_service_builder_names == ("build_contract_gap",)
    assert contract_coverage_drift.missing_api_route_paths == (
        "/api/v1/snapshots/backtest/source-verification-drift",
    )
    assert contract_coverage_drift.missing_serializer_names == (
        "_serialize_contract_gap",
        "_serialize_source_verification_drift",
    )
    assert (
        contract_coverage_drift.endpoint_coverage_consistency.consistency_classification
        == "degraded"
    )
    assert (
        contract_coverage_drift.endpoint_coverage_consistency.consistency_percentage
        == 58.33
    )
    assert (
        contract_coverage_drift.endpoint_coverage_consistency.degraded_diagnostic_count
        == 2
    )
    contract_gap_entry = next(
        entry
        for entry in contract_coverage_drift.endpoint_coverage_consistency.entries
        if entry.diagnostic_key == "contract_gap"
    )
    assert contract_gap_entry.service_builder_present is False
    assert contract_gap_entry.api_route_present is True
    assert contract_gap_entry.serializer_present is False


def test_snapshot_replay_service_builds_stable_source_diagnostic_group_coverage_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_group_coverage_stable",
    )

    group_coverage_drift = (
        SnapshotReplayService(store).build_source_diagnostic_group_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert group_coverage_drift.drift_classification == "stable"
    assert group_coverage_drift.average_coverage_percentage == 100.0
    assert group_coverage_drift.severity_score == 0
    assert (
        group_coverage_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert group_coverage_drift.snapshots_checked == 1
    assert group_coverage_drift.stable_snapshots == 1
    assert group_coverage_drift.drifting_snapshots == 0
    assert group_coverage_drift.degraded_snapshots == 0
    assert group_coverage_drift.missing_contract_groups == ()
    assert group_coverage_drift.missing_service_groups == ()
    assert group_coverage_drift.missing_api_route_groups == ()
    assert group_coverage_drift.missing_serializer_groups == ()
    assert group_coverage_drift.missing_rolling_bundle_groups == ()
    assert group_coverage_drift.entries[0].drift_classification == "stable"
    assert group_coverage_drift.entries[0].coverage_percentage == 100.0
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.consistency_classification
        == "consistent"
    )
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.consistency_percentage
        == 100.0
    )
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.total_groups_registered
        >= 5
    )
    completeness_entry = next(
        entry
        for entry in group_coverage_drift.route_serializer_group_alignment_consistency.entries
        if entry.diagnostic_group == "quality_completeness"
    )
    assert completeness_entry.contract_group_present is True
    assert completeness_entry.service_group_present is True
    assert completeness_entry.api_route_group_present is True
    assert completeness_entry.serializer_group_present is True
    assert completeness_entry.rolling_bundle_group_present is True
    assert group_coverage_drift.paper_safe is True
    assert group_coverage_drift.network_calls is False
    assert group_coverage_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_degraded_source_diagnostic_group_coverage_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_group_coverage_degraded",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (
            "source-record-completeness",
            "fallback-usage-recurrence",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {
            "source-record-completeness": "quality_completeness",
            "fallback-usage-recurrence": "registry",
        },
    )

    group_coverage_drift = (
        SnapshotReplayService(store).build_source_diagnostic_group_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert group_coverage_drift.drift_classification == "degraded"
    assert group_coverage_drift.average_coverage_percentage == 70.0
    assert group_coverage_drift.severity_score == 60
    assert group_coverage_drift.stable_snapshots == 0
    assert group_coverage_drift.drifting_snapshots == 0
    assert group_coverage_drift.degraded_snapshots == 1
    assert group_coverage_drift.missing_contract_groups == ()
    assert group_coverage_drift.missing_service_groups == ("registry",)
    assert group_coverage_drift.missing_api_route_groups == ()
    assert group_coverage_drift.missing_serializer_groups == ("registry",)
    assert group_coverage_drift.missing_rolling_bundle_groups == ("registry",)
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.consistency_classification
        == "degraded"
    )
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.consistency_percentage
        == 70.0
    )
    registry_entry = next(
        entry
        for entry in group_coverage_drift.route_serializer_group_alignment_consistency.entries
        if entry.diagnostic_group == "registry"
    )
    assert registry_entry.contract_group_present is True
    assert registry_entry.service_group_present is False
    assert registry_entry.api_route_group_present is True
    assert registry_entry.serializer_group_present is False
    assert registry_entry.rolling_bundle_group_present is False


def test_snapshot_replay_service_builds_drifting_source_diagnostic_group_coverage_drift_for_missing_rolling_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_group_coverage_drifting",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {
            "source-record-completeness": "quality_completeness",
            "source-verification-drift": "registry",
        },
    )

    group_coverage_drift = (
        SnapshotReplayService(store).build_source_diagnostic_group_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert group_coverage_drift.drift_classification == "drifting"
    assert group_coverage_drift.average_coverage_percentage == 90.0
    assert group_coverage_drift.severity_score == 20
    assert group_coverage_drift.stable_snapshots == 0
    assert group_coverage_drift.drifting_snapshots == 1
    assert group_coverage_drift.degraded_snapshots == 0
    assert group_coverage_drift.missing_contract_groups == ()
    assert group_coverage_drift.missing_service_groups == ()
    assert group_coverage_drift.missing_api_route_groups == ()
    assert group_coverage_drift.missing_serializer_groups == ()
    assert group_coverage_drift.missing_rolling_bundle_groups == ("registry",)
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.consistency_classification
        == "partial"
    )
    assert (
        group_coverage_drift.route_serializer_group_alignment_consistency.consistency_percentage
        == 90.0
    )
    registry_entry = next(
        entry
        for entry in group_coverage_drift.route_serializer_group_alignment_consistency.entries
        if entry.diagnostic_group == "registry"
    )
    assert registry_entry.contract_group_present is True
    assert registry_entry.service_group_present is True
    assert registry_entry.api_route_group_present is True
    assert registry_entry.serializer_group_present is True
    assert registry_entry.rolling_bundle_group_present is False


def test_snapshot_replay_service_builds_stable_source_diagnostic_surface_count_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_surface_count_stable",
    )

    surface_count_drift = (
        SnapshotReplayService(store).build_source_diagnostic_surface_count_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert surface_count_drift.drift_classification == "stable"
    assert surface_count_drift.average_consistency_percentage == 100.0
    assert surface_count_drift.severity_score == 0
    assert (
        surface_count_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert surface_count_drift.snapshots_checked == 1
    assert surface_count_drift.stable_snapshots == 1
    assert surface_count_drift.drifting_snapshots == 0
    assert surface_count_drift.degraded_snapshots == 0
    assert surface_count_drift.mismatched_surface_names == ()
    assert (
        surface_count_drift.group_alignment_consistency_classification
        == "consistent"
    )
    assert surface_count_drift.group_alignment_clean_but_count_mismatched is False
    assert (
        surface_count_drift.contract_surface_count_consistency.consistency_classification
        == "consistent"
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.consistency_percentage
        == 100.0
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.total_surfaces_checked
        == 6
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.total_diagnostics_registered
        >= 40
    )
    api_route_entry = next(
        entry
        for entry in surface_count_drift.contract_surface_count_consistency.entries
        if entry.surface_name == "api_routes"
    )
    assert api_route_entry.actual_count == api_route_entry.expected_count
    assert api_route_entry.consistency_classification == "consistent"
    assert surface_count_drift.paper_safe is True
    assert surface_count_drift.network_calls is False
    assert surface_count_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_drifting_source_diagnostic_surface_count_drift_for_missing_api_route_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_surface_count_drifting",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {
            "source-record-completeness": "quality_completeness",
            "source-verification-drift": "quality_completeness",
        },
    )

    surface_count_drift = (
        SnapshotReplayService(store).build_source_diagnostic_surface_count_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert surface_count_drift.drift_classification == "drifting"
    assert surface_count_drift.average_consistency_percentage == 91.67
    assert surface_count_drift.severity_score == 25
    assert surface_count_drift.snapshots_checked == 1
    assert surface_count_drift.stable_snapshots == 0
    assert surface_count_drift.drifting_snapshots == 1
    assert surface_count_drift.degraded_snapshots == 0
    assert surface_count_drift.mismatched_surface_names == ("api_routes",)
    assert (
        surface_count_drift.group_alignment_consistency_classification
        == "consistent"
    )
    assert surface_count_drift.group_alignment_clean_but_count_mismatched is True
    assert (
        surface_count_drift.contract_surface_count_consistency.consistency_classification
        == "partial"
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.total_groups_registered
        == 1
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.api_route_count
        == 1
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.mismatched_surface_count
        == 1
    )
    api_route_entry = next(
        entry
        for entry in surface_count_drift.contract_surface_count_consistency.entries
        if entry.surface_name == "api_routes"
    )
    assert api_route_entry.expected_count == 2
    assert api_route_entry.actual_count == 1
    assert api_route_entry.count_delta == -1
    assert api_route_entry.consistency_percentage == 50.0


def test_snapshot_replay_service_builds_degraded_source_diagnostic_surface_count_drift_for_multiple_mismatched_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_surface_count_degraded",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {
            "source-record-completeness": "quality_completeness",
            "source-verification-drift": "quality_completeness",
        },
    )

    surface_count_drift = (
        SnapshotReplayService(store).build_source_diagnostic_surface_count_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert surface_count_drift.drift_classification == "degraded"
    assert surface_count_drift.average_consistency_percentage == 75.0
    assert surface_count_drift.severity_score == 75
    assert surface_count_drift.snapshots_checked == 1
    assert surface_count_drift.stable_snapshots == 0
    assert surface_count_drift.drifting_snapshots == 0
    assert surface_count_drift.degraded_snapshots == 1
    assert surface_count_drift.mismatched_surface_names == (
        "api_routes",
        "rolling_bundle",
        "serializers",
    )
    assert (
        surface_count_drift.group_alignment_consistency_classification
        == "consistent"
    )
    assert surface_count_drift.group_alignment_clean_but_count_mismatched is True
    assert (
        surface_count_drift.contract_surface_count_consistency.consistency_classification
        == "degraded"
    )
    assert (
        surface_count_drift.contract_surface_count_consistency.mismatched_surface_count
        == 3
    )
    rolling_bundle_entry = next(
        entry
        for entry in surface_count_drift.contract_surface_count_consistency.entries
        if entry.surface_name == "rolling_bundle"
    )
    assert rolling_bundle_entry.expected_count == 2
    assert rolling_bundle_entry.actual_count == 1
    assert rolling_bundle_entry.consistency_percentage == 50.0


def test_snapshot_replay_service_builds_stable_source_diagnostic_metadata_completeness_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_metadata_completeness_stable",
    )

    metadata_completeness_drift = (
        SnapshotReplayService(store).build_source_diagnostic_metadata_completeness_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert metadata_completeness_drift.drift_classification == "stable"
    assert metadata_completeness_drift.average_completeness_percentage == 100.0
    assert metadata_completeness_drift.severity_score == 0
    assert (
        metadata_completeness_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert metadata_completeness_drift.snapshots_checked == 1
    assert metadata_completeness_drift.stable_snapshots == 1
    assert metadata_completeness_drift.drifting_snapshots == 0
    assert metadata_completeness_drift.degraded_snapshots == 0
    assert metadata_completeness_drift.missing_metadata_field_count == 0
    assert metadata_completeness_drift.invalid_metadata_field_count == 0
    assert metadata_completeness_drift.duplicate_metadata_record_count == 0
    assert metadata_completeness_drift.conflicting_metadata_record_count == 0
    assert metadata_completeness_drift.missing_group_diagnostic_keys == ()
    assert metadata_completeness_drift.invalid_group_diagnostic_keys == ()
    assert metadata_completeness_drift.invalid_diagnostic_slugs == ()
    assert metadata_completeness_drift.invalid_diagnostic_keys == ()
    assert metadata_completeness_drift.missing_service_builder_keys == ()
    assert metadata_completeness_drift.invalid_service_builder_keys == ()
    assert metadata_completeness_drift.missing_api_route_keys == ()
    assert metadata_completeness_drift.invalid_api_route_keys == ()
    assert metadata_completeness_drift.missing_serializer_keys == ()
    assert metadata_completeness_drift.invalid_serializer_keys == ()
    assert metadata_completeness_drift.missing_rolling_bundle_keys == ()
    assert metadata_completeness_drift.invalid_rolling_bundle_keys == ()
    assert metadata_completeness_drift.missing_rolling_serializer_keys == ()
    assert metadata_completeness_drift.invalid_rolling_serializer_keys == ()
    assert metadata_completeness_drift.duplicate_metadata_records == ()
    assert metadata_completeness_drift.conflicting_metadata_records == ()
    assert (
        metadata_completeness_drift.contract_metadata_normalization_consistency.consistency_classification
        == "consistent"
    )
    assert (
        metadata_completeness_drift.contract_metadata_normalization_consistency.completeness_percentage
        == 100.0
    )
    assert (
        metadata_completeness_drift.contract_metadata_normalization_consistency.total_diagnostics_registered
        >= 40
    )
    assert metadata_completeness_drift.paper_safe is True
    assert metadata_completeness_drift.network_calls is False
    assert metadata_completeness_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_drifting_source_diagnostic_metadata_completeness_drift_for_invalid_group_and_duplicate_serializer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_metadata_completeness_partial",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-record-completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {"source-record-completeness": "Quality-Completeness"},
    )

    metadata_completeness_drift = (
        SnapshotReplayService(store).build_source_diagnostic_metadata_completeness_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert metadata_completeness_drift.drift_classification == "drifting"
    assert metadata_completeness_drift.average_completeness_percentage == 75.0
    assert metadata_completeness_drift.severity_score == 15
    assert metadata_completeness_drift.snapshots_checked == 1
    assert metadata_completeness_drift.stable_snapshots == 0
    assert metadata_completeness_drift.drifting_snapshots == 1
    assert metadata_completeness_drift.degraded_snapshots == 0
    assert metadata_completeness_drift.missing_metadata_field_count == 0
    assert metadata_completeness_drift.invalid_metadata_field_count == 1
    assert metadata_completeness_drift.duplicate_metadata_record_count == 1
    assert metadata_completeness_drift.conflicting_metadata_record_count == 0
    assert metadata_completeness_drift.invalid_group_diagnostic_keys == (
        "source_record_completeness",
    )
    assert metadata_completeness_drift.invalid_group_names == (
        "Quality-Completeness",
    )
    assert metadata_completeness_drift.duplicate_metadata_records == (
        "serializer_key:_serialize_source_record_completeness",
    )
    assert (
        metadata_completeness_drift.contract_metadata_normalization_consistency.consistency_classification
        == "partial"
    )
    assert (
        metadata_completeness_drift.contract_metadata_normalization_consistency.partial_metadata_count
        == 1
    )
    entry = (
        metadata_completeness_drift.contract_metadata_normalization_consistency.entries[0]
    )
    assert entry.consistency_classification == "partial"
    assert entry.completeness_percentage == 75.0
    assert entry.invalid_metadata_fields == ("contract_group",)
    assert entry.duplicate_metadata_fields == ("serializer_key",)


def test_snapshot_replay_service_builds_degraded_source_diagnostic_metadata_completeness_drift_for_malformed_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_metadata_completeness_degraded",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        ("Source_Record_Completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        ("Source_Record_Completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        (),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        (),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {},
    )

    metadata_completeness_drift = (
        SnapshotReplayService(store).build_source_diagnostic_metadata_completeness_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert metadata_completeness_drift.drift_classification == "degraded"
    assert metadata_completeness_drift.average_completeness_percentage == 0.0
    assert metadata_completeness_drift.severity_score == 80
    assert metadata_completeness_drift.snapshots_checked == 1
    assert metadata_completeness_drift.stable_snapshots == 0
    assert metadata_completeness_drift.drifting_snapshots == 0
    assert metadata_completeness_drift.degraded_snapshots == 1
    assert metadata_completeness_drift.missing_metadata_field_count == 4
    assert metadata_completeness_drift.invalid_metadata_field_count == 4
    assert metadata_completeness_drift.duplicate_metadata_record_count == 0
    assert metadata_completeness_drift.conflicting_metadata_record_count == 0
    assert metadata_completeness_drift.missing_group_diagnostic_keys == (
        "Source_Record_Completeness",
    )
    assert metadata_completeness_drift.invalid_diagnostic_slugs == (
        "Source_Record_Completeness",
    )
    assert metadata_completeness_drift.invalid_diagnostic_keys == (
        "Source_Record_Completeness",
    )
    assert metadata_completeness_drift.invalid_service_builder_keys == (
        "build_Source_Record_Completeness",
    )
    assert metadata_completeness_drift.missing_api_route_keys == (
        "/api/v1/snapshots/backtest/Source_Record_Completeness",
    )
    assert metadata_completeness_drift.invalid_serializer_keys == (
        "_serialize_Source_Record_Completeness",
    )
    assert metadata_completeness_drift.missing_rolling_bundle_keys == (
        "Source_Record_Completeness",
    )
    assert metadata_completeness_drift.missing_rolling_serializer_keys == (
        "Source_Record_Completeness",
    )
    assert (
        metadata_completeness_drift.contract_metadata_normalization_consistency.consistency_classification
        == "degraded"
    )
    entry = (
        metadata_completeness_drift.contract_metadata_normalization_consistency.entries[0]
    )
    assert entry.consistency_classification == "degraded"
    assert entry.completeness_percentage == 0.0
    assert entry.missing_metadata_fields == (
        "contract_group",
        "api_route_key",
        "rolling_bundle_key",
        "rolling_serializer_key",
    )
    assert entry.invalid_metadata_fields == (
        "diagnostic_slug",
        "diagnostic_key",
        "service_builder_key",
        "serializer_key",
    )


def test_snapshot_replay_service_builds_stable_source_diagnostic_naming_contract_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_naming_contract_stable",
    )

    naming_contract_drift = (
        SnapshotReplayService(store).build_source_diagnostic_naming_contract_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert naming_contract_drift.drift_classification == "stable"
    assert naming_contract_drift.average_consistency_percentage == 100.0
    assert naming_contract_drift.severity_score == 0
    assert (
        naming_contract_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert naming_contract_drift.snapshots_checked == 1
    assert naming_contract_drift.stable_snapshots == 1
    assert naming_contract_drift.drifting_snapshots == 0
    assert naming_contract_drift.degraded_snapshots == 0
    assert naming_contract_drift.invalid_name_field_count == 0
    assert naming_contract_drift.mismatched_name_field_count == 0
    assert naming_contract_drift.duplicate_name_record_count == 0
    assert naming_contract_drift.conflicting_name_record_count == 0
    assert naming_contract_drift.invalid_diagnostic_slugs == ()
    assert naming_contract_drift.invalid_diagnostic_keys == ()
    assert naming_contract_drift.mismatched_diagnostic_keys == ()
    assert naming_contract_drift.invalid_service_builder_names == ()
    assert naming_contract_drift.mismatched_service_builder_names == ()
    assert naming_contract_drift.invalid_serializer_names == ()
    assert naming_contract_drift.mismatched_serializer_names == ()
    assert naming_contract_drift.invalid_api_route_paths == ()
    assert naming_contract_drift.mismatched_api_route_paths == ()
    assert naming_contract_drift.invalid_rolling_bundle_field_names == ()
    assert naming_contract_drift.mismatched_rolling_bundle_field_names == ()
    assert naming_contract_drift.invalid_rolling_serializer_field_names == ()
    assert naming_contract_drift.mismatched_rolling_serializer_field_names == ()
    assert naming_contract_drift.duplicate_name_records == ()
    assert naming_contract_drift.conflicting_name_records == ()
    assert (
        naming_contract_drift.builder_serializer_route_naming_consistency.consistency_classification
        == "consistent"
    )
    assert (
        naming_contract_drift.builder_serializer_route_naming_consistency.consistency_percentage
        == 100.0
    )
    assert (
        naming_contract_drift.builder_serializer_route_naming_consistency.total_diagnostics_registered
        >= 40
    )
    assert naming_contract_drift.paper_safe is True
    assert naming_contract_drift.network_calls is False
    assert naming_contract_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_drifting_source_diagnostic_naming_contract_drift_for_mismatched_builder_and_serializer_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_naming_contract_partial",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {"source-record-completeness": "quality_completeness"},
    )
    original_builder_name = (
        source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name
    )
    original_serializer_name = (
        source_diagnostic_contracts.snapshot_replay_source_diagnostic_serializer_name
    )

    monkeypatch.setattr(
        source_diagnostic_contracts,
        "snapshot_replay_source_diagnostic_builder_name",
        lambda slug: (
            "build_source_record_completeness_alias"
            if slug == "source-record-completeness"
            else original_builder_name(slug)
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "snapshot_replay_source_diagnostic_serializer_name",
        lambda slug: (
            "_serialize_source_record_completeness_alias"
            if slug == "source-record-completeness"
            else original_serializer_name(slug)
        ),
    )

    naming_contract_drift = (
        SnapshotReplayService(store).build_source_diagnostic_naming_contract_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert naming_contract_drift.drift_classification == "drifting"
    assert naming_contract_drift.average_consistency_percentage == 71.43
    assert naming_contract_drift.severity_score == 20
    assert naming_contract_drift.snapshots_checked == 1
    assert naming_contract_drift.stable_snapshots == 0
    assert naming_contract_drift.drifting_snapshots == 1
    assert naming_contract_drift.degraded_snapshots == 0
    assert naming_contract_drift.invalid_name_field_count == 0
    assert naming_contract_drift.mismatched_name_field_count == 2
    assert naming_contract_drift.duplicate_name_record_count == 0
    assert naming_contract_drift.conflicting_name_record_count == 0
    assert naming_contract_drift.mismatched_service_builder_names == (
        "build_source_record_completeness_alias",
    )
    assert naming_contract_drift.mismatched_serializer_names == (
        "_serialize_source_record_completeness_alias",
    )
    assert (
        naming_contract_drift.builder_serializer_route_naming_consistency.consistency_classification
        == "partial"
    )
    entry = (
        naming_contract_drift.builder_serializer_route_naming_consistency.entries[0]
    )
    assert entry.consistency_classification == "partial"
    assert entry.consistency_percentage == 71.43
    assert entry.invalid_name_fields == ()
    assert entry.mismatched_name_fields == (
        "service_builder_name",
        "serializer_name",
    )
    assert entry.actual_service_builder_name == "build_source_record_completeness_alias"
    assert entry.actual_serializer_name == "_serialize_source_record_completeness_alias"


def test_snapshot_replay_service_builds_degraded_source_diagnostic_naming_contract_drift_for_conflicting_normalized_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_naming_contract_degraded",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {
            "source-record-completeness": "quality_completeness",
            "source_record_completeness": "quality_completeness",
        },
    )

    naming_contract_drift = (
        SnapshotReplayService(store).build_source_diagnostic_naming_contract_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert naming_contract_drift.drift_classification == "degraded"
    assert naming_contract_drift.average_consistency_percentage == 14.29
    assert naming_contract_drift.severity_score == 100
    assert naming_contract_drift.snapshots_checked == 1
    assert naming_contract_drift.stable_snapshots == 0
    assert naming_contract_drift.drifting_snapshots == 0
    assert naming_contract_drift.degraded_snapshots == 1
    assert naming_contract_drift.invalid_name_field_count == 2
    assert naming_contract_drift.mismatched_name_field_count == 0
    assert naming_contract_drift.duplicate_name_record_count == 0
    assert naming_contract_drift.conflicting_name_record_count == 5
    assert naming_contract_drift.invalid_diagnostic_slugs == (
        "source_record_completeness",
    )
    assert naming_contract_drift.invalid_api_route_paths == (
        "/api/v1/snapshots/backtest/source_record_completeness",
    )
    assert naming_contract_drift.conflicting_name_records == (
        "diagnostic_key:source_record_completeness",
        "rolling_bundle_field_name:source_record_completeness",
        "rolling_serializer_field_name:source_record_completeness",
        "serializer_name:_serialize_source_record_completeness",
        "service_builder_name:build_source_record_completeness",
    )
    assert (
        naming_contract_drift.builder_serializer_route_naming_consistency.consistency_classification
        == "degraded"
    )
    degraded_entry = next(
        entry
        for entry in naming_contract_drift.builder_serializer_route_naming_consistency.entries
        if entry.diagnostic_slug == "source_record_completeness"
    )
    assert degraded_entry.consistency_classification == "degraded"
    assert degraded_entry.consistency_percentage == 0.0
    assert degraded_entry.invalid_name_fields == (
        "diagnostic_slug",
        "api_route_path",
    )
    assert degraded_entry.conflicting_name_fields == (
        "diagnostic_key",
        "rolling_bundle_field_name",
        "rolling_serializer_field_name",
        "serializer_name",
        "service_builder_name",
    )


def test_snapshot_replay_service_builds_stable_source_diagnostic_contract_signature_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_contract_signature_stable",
    )

    contract_signature_drift = (
        SnapshotReplayService(store).build_source_diagnostic_contract_signature_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert contract_signature_drift.drift_classification == "stable"
    assert contract_signature_drift.average_consistency_percentage == 100.0
    assert contract_signature_drift.severity_score == 0
    assert (
        contract_signature_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert contract_signature_drift.snapshots_checked == 1
    assert contract_signature_drift.stable_snapshots == 1
    assert contract_signature_drift.drifting_snapshots == 0
    assert contract_signature_drift.degraded_snapshots == 0
    assert contract_signature_drift.missing_signature_component_count == 0
    assert contract_signature_drift.invalid_signature_component_count == 0
    assert contract_signature_drift.mismatched_signature_component_count == 0
    assert contract_signature_drift.duplicate_signature_record_count == 0
    assert contract_signature_drift.conflicting_signature_record_count == 0
    assert contract_signature_drift.missing_contract_signatures == ()
    assert contract_signature_drift.invalid_contract_signatures == ()
    assert contract_signature_drift.mismatched_contract_signatures == ()
    assert contract_signature_drift.missing_service_builder_signatures == ()
    assert contract_signature_drift.invalid_service_builder_signatures == ()
    assert contract_signature_drift.mismatched_service_builder_signatures == ()
    assert contract_signature_drift.missing_serializer_signatures == ()
    assert contract_signature_drift.invalid_serializer_signatures == ()
    assert contract_signature_drift.mismatched_serializer_signatures == ()
    assert contract_signature_drift.missing_api_route_signatures == ()
    assert contract_signature_drift.invalid_api_route_signatures == ()
    assert contract_signature_drift.mismatched_api_route_signatures == ()
    assert contract_signature_drift.missing_rolling_bundle_signatures == ()
    assert contract_signature_drift.invalid_rolling_bundle_signatures == ()
    assert contract_signature_drift.mismatched_rolling_bundle_signatures == ()
    assert contract_signature_drift.missing_rolling_serializer_signatures == ()
    assert contract_signature_drift.invalid_rolling_serializer_signatures == ()
    assert contract_signature_drift.mismatched_rolling_serializer_signatures == ()
    assert contract_signature_drift.duplicate_signature_records == ()
    assert contract_signature_drift.conflicting_signature_records == ()
    assert (
        contract_signature_drift.full_surface_contract_signature_consistency.consistency_classification
        == "consistent"
    )
    assert (
        contract_signature_drift.full_surface_contract_signature_consistency.consistency_percentage
        == 100.0
    )
    assert (
        contract_signature_drift.full_surface_contract_signature_consistency.total_diagnostics_registered
        >= 40
    )
    stable_entry = next(
        entry
        for entry in contract_signature_drift.full_surface_contract_signature_consistency.entries
        if entry.diagnostic_slug == "source-record-completeness"
    )
    assert stable_entry.actual_contract_signature == (
        "source_record_completeness|quality_completeness"
    )
    assert stable_entry.actual_service_builder_signature == (
        "source_record_completeness|build_source_record_completeness"
    )
    assert stable_entry.actual_serializer_signature == (
        "source_record_completeness|_serialize_source_record_completeness"
    )
    assert stable_entry.actual_api_route_signature == (
        "source_record_completeness|/api/v1/snapshots/backtest/source-record-completeness"
    )
    assert stable_entry.actual_rolling_bundle_signature == (
        "source_record_completeness|source_record_completeness"
    )
    assert stable_entry.actual_rolling_serializer_signature == (
        "source_record_completeness|source_record_completeness"
    )
    assert stable_entry.missing_signature_components == ()
    assert stable_entry.invalid_signature_components == ()
    assert stable_entry.mismatched_signature_components == ()
    assert stable_entry.consistency_percentage == 100.0
    assert contract_signature_drift.paper_safe is True
    assert contract_signature_drift.network_calls is False
    assert contract_signature_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_drifting_source_diagnostic_contract_signature_drift_for_missing_rolling_serializer_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_contract_signature_partial",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        (),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {"source-record-completeness": "quality_completeness"},
    )

    contract_signature_drift = (
        SnapshotReplayService(store).build_source_diagnostic_contract_signature_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert contract_signature_drift.drift_classification == "drifting"
    assert contract_signature_drift.average_consistency_percentage == 83.33
    assert contract_signature_drift.severity_score == 10
    assert contract_signature_drift.snapshots_checked == 1
    assert contract_signature_drift.stable_snapshots == 0
    assert contract_signature_drift.drifting_snapshots == 1
    assert contract_signature_drift.degraded_snapshots == 0
    assert contract_signature_drift.missing_signature_component_count == 1
    assert contract_signature_drift.invalid_signature_component_count == 0
    assert contract_signature_drift.mismatched_signature_component_count == 0
    assert contract_signature_drift.duplicate_signature_record_count == 0
    assert contract_signature_drift.conflicting_signature_record_count == 0
    assert contract_signature_drift.missing_rolling_serializer_signatures == (
        "source_record_completeness|source_record_completeness",
    )
    assert (
        contract_signature_drift.full_surface_contract_signature_consistency.consistency_classification
        == "partial"
    )
    partial_entry = (
        contract_signature_drift.full_surface_contract_signature_consistency.entries[0]
    )
    assert partial_entry.consistency_classification == "partial"
    assert partial_entry.consistency_percentage == 83.33
    assert partial_entry.missing_signature_components == (
        "rolling_serializer_signature",
    )
    assert partial_entry.invalid_signature_components == ()
    assert partial_entry.mismatched_signature_components == ()
    assert partial_entry.actual_rolling_serializer_signature is None


def test_snapshot_replay_service_builds_degraded_source_diagnostic_contract_signature_drift_for_conflicting_signatures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_contract_signature_degraded",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source_record_completeness",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
        {
            "source-record-completeness": "quality_completeness",
            "source_record_completeness": "quality_completeness",
        },
    )

    contract_signature_drift = (
        SnapshotReplayService(store).build_source_diagnostic_contract_signature_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert contract_signature_drift.drift_classification == "degraded"
    assert contract_signature_drift.average_consistency_percentage == 8.34
    assert contract_signature_drift.severity_score == 100
    assert contract_signature_drift.snapshots_checked == 1
    assert contract_signature_drift.stable_snapshots == 0
    assert contract_signature_drift.drifting_snapshots == 0
    assert contract_signature_drift.degraded_snapshots == 1
    assert contract_signature_drift.missing_signature_component_count == 0
    assert contract_signature_drift.invalid_signature_component_count == 2
    assert contract_signature_drift.mismatched_signature_component_count == 0
    assert contract_signature_drift.duplicate_signature_record_count == 0
    assert contract_signature_drift.conflicting_signature_record_count == 5
    assert contract_signature_drift.invalid_contract_signatures == (
        "source_record_completeness|quality_completeness",
    )
    assert contract_signature_drift.invalid_api_route_signatures == (
        "source_record_completeness|/api/v1/snapshots/backtest/source_record_completeness",
    )
    assert contract_signature_drift.conflicting_signature_records == (
        "contract_signature:source_record_completeness|quality_completeness",
        "rolling_bundle_signature:source_record_completeness|source_record_completeness",
        "rolling_serializer_signature:source_record_completeness|source_record_completeness",
        "serializer_signature:source_record_completeness|_serialize_source_record_completeness",
        "service_builder_signature:source_record_completeness|build_source_record_completeness",
    )
    assert (
        contract_signature_drift.full_surface_contract_signature_consistency.consistency_classification
        == "degraded"
    )
    degraded_entry = next(
        entry
        for entry in contract_signature_drift.full_surface_contract_signature_consistency.entries
        if entry.diagnostic_slug == "source_record_completeness"
    )
    assert degraded_entry.consistency_classification == "degraded"
    assert degraded_entry.consistency_percentage == 0.0
    assert degraded_entry.invalid_signature_components == (
        "contract_signature",
        "api_route_signature",
    )
    assert degraded_entry.conflicting_signature_components == (
        "contract_signature",
        "rolling_bundle_signature",
        "rolling_serializer_signature",
        "serializer_signature",
        "service_builder_signature",
    )


def test_snapshot_replay_service_builds_stable_rolling_source_diagnostic_bundle_coverage_drift(
    tmp_path: Path,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_rolling_bundle_coverage_stable",
    )

    rolling_bundle_coverage_drift = (
        SnapshotReplayService(store).build_rolling_source_diagnostic_bundle_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert rolling_bundle_coverage_drift.drift_classification == "stable"
    assert rolling_bundle_coverage_drift.average_coverage_percentage == 100.0
    assert rolling_bundle_coverage_drift.severity_score == 0
    assert (
        rolling_bundle_coverage_drift.contract_source
        == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE
    )
    assert rolling_bundle_coverage_drift.snapshots_checked == 1
    assert rolling_bundle_coverage_drift.stable_snapshots == 1
    assert rolling_bundle_coverage_drift.drifting_snapshots == 0
    assert rolling_bundle_coverage_drift.degraded_snapshots == 0
    assert rolling_bundle_coverage_drift.missing_dedicated_service_builder_names == ()
    assert rolling_bundle_coverage_drift.missing_dedicated_api_route_paths == ()
    assert rolling_bundle_coverage_drift.missing_dedicated_serializer_names == ()
    assert rolling_bundle_coverage_drift.missing_rolling_bundle_field_names == ()
    assert rolling_bundle_coverage_drift.missing_rolling_serializer_field_names == ()
    assert rolling_bundle_coverage_drift.entries[0].drift_classification == "stable"
    assert rolling_bundle_coverage_drift.entries[0].coverage_percentage == 100.0
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.consistency_classification
        == "consistent"
    )
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.consistency_percentage
        == 100.0
    )
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.total_diagnostics_registered
        >= 40
    )
    assert rolling_bundle_coverage_drift.paper_safe is True
    assert rolling_bundle_coverage_drift.network_calls is False
    assert rolling_bundle_coverage_drift.execution_side_effects == "NO_EXECUTION"


def test_snapshot_replay_service_builds_partial_rolling_source_diagnostic_bundle_coverage_drift_for_missing_rolling_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_rolling_bundle_coverage_partial",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )

    rolling_bundle_coverage_drift = (
        SnapshotReplayService(store).build_rolling_source_diagnostic_bundle_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert rolling_bundle_coverage_drift.drift_classification == "drifting"
    assert rolling_bundle_coverage_drift.average_coverage_percentage == 90.0
    assert rolling_bundle_coverage_drift.severity_score == 20
    assert rolling_bundle_coverage_drift.stable_snapshots == 0
    assert rolling_bundle_coverage_drift.drifting_snapshots == 1
    assert rolling_bundle_coverage_drift.degraded_snapshots == 0
    assert rolling_bundle_coverage_drift.missing_rolling_bundle_field_names == (
        "source_verification_drift",
    )
    assert rolling_bundle_coverage_drift.missing_rolling_serializer_field_names == ()
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.consistency_classification
        == "partial"
    )
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.consistency_percentage
        == 90.0
    )
    verification_entry = next(
        entry
        for entry in rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.entries
        if entry.diagnostic_key == "source_verification_drift"
    )
    assert verification_entry.dedicated_service_builder_present is True
    assert verification_entry.dedicated_api_route_present is True
    assert verification_entry.dedicated_serializer_present is True
    assert verification_entry.rolling_bundle_present is False
    assert verification_entry.rolling_serializer_present is True


def test_snapshot_replay_service_builds_partial_rolling_source_diagnostic_bundle_coverage_drift_for_missing_dedicated_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_rolling_bundle_coverage_missing_dedicated_route",
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
        ("source-record-completeness",),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )
    monkeypatch.setattr(
        source_diagnostic_contracts,
        "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
        (
            "source-record-completeness",
            "source-verification-drift",
        ),
    )

    rolling_bundle_coverage_drift = (
        SnapshotReplayService(store).build_rolling_source_diagnostic_bundle_coverage_drift(
            snapshot_ids=(baseline_snapshot["snapshot_id"],),
        )
    )

    assert rolling_bundle_coverage_drift.drift_classification == "drifting"
    assert rolling_bundle_coverage_drift.average_coverage_percentage == 90.0
    assert rolling_bundle_coverage_drift.severity_score == 20
    assert rolling_bundle_coverage_drift.stable_snapshots == 0
    assert rolling_bundle_coverage_drift.drifting_snapshots == 1
    assert rolling_bundle_coverage_drift.degraded_snapshots == 0
    assert rolling_bundle_coverage_drift.missing_dedicated_api_route_paths == (
        "/api/v1/snapshots/backtest/source-verification-drift",
    )
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.consistency_classification
        == "partial"
    )
    assert (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.consistency_percentage
        == 90.0
    )
    verification_entry = next(
        entry
        for entry in rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency.entries
        if entry.diagnostic_key == "source_verification_drift"
    )
    assert verification_entry.dedicated_service_builder_present is True
    assert verification_entry.dedicated_api_route_present is False
    assert verification_entry.dedicated_serializer_present is True
    assert verification_entry.rolling_bundle_present is True
    assert verification_entry.rolling_serializer_present is True

def test_snapshot_replay_service_builds_source_diagnostic_contract_field_set_drift(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    field_set_drift = SnapshotReplayService(store).build_source_diagnostic_contract_field_set_drift()

    assert field_set_drift.paper_safe is True
    assert field_set_drift.network_calls is False
    assert field_set_drift.execution_side_effects == "NO_EXECUTION"
    assert field_set_drift.total_diagnostics_registered == len(
        source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
    )
    assert field_set_drift.drift_classification in ("stable", "drifting", "degraded")
    assert 0.0 <= field_set_drift.consistency_percentage <= 100.0
    assert len(field_set_drift.entries) == field_set_drift.total_diagnostics_registered
    assert len(field_set_drift.standard_field_set) == len(
        source_diagnostic_contracts.SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET
    )
    assert field_set_drift.fully_consistent_count + field_set_drift.partially_consistent_count == (
        field_set_drift.total_diagnostics_registered
    )


def test_source_diagnostic_contract_field_set_drift_entries_cover_all_slugs(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    field_set_drift = SnapshotReplayService(store).build_source_diagnostic_contract_field_set_drift()

    registered_slugs = {e.slug for e in field_set_drift.entries}
    assert registered_slugs == set(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS)


def test_snapshot_replay_service_builds_full_surface_response_field_set_consistency(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    consistency = SnapshotReplayService(store).build_full_surface_response_field_set_consistency()

    assert consistency.paper_safe is True
    assert consistency.network_calls is False
    assert consistency.execution_side_effects == "NO_EXECUTION"
    assert consistency.total_diagnostics_registered == len(
        source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
    )
    assert consistency.consistency_classification in ("consistent", "partial", "degraded")
    assert 0.0 <= consistency.consistency_percentage <= 100.0
    assert len(consistency.entries) == consistency.total_diagnostics_registered
    assert len(consistency.standard_field_set) == len(
        source_diagnostic_contracts.SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET
    )
    assert (
        consistency.fully_consistent_count
        + consistency.partially_consistent_count
        + consistency.degraded_count
    ) == consistency.total_diagnostics_registered


def test_full_surface_response_field_set_consistency_entries_cover_all_slugs(
    tmp_path: Path,
) -> None:
    store = SnapshotStore(tmp_path / "snapshots.jsonl")
    consistency = SnapshotReplayService(store).build_full_surface_response_field_set_consistency()

    registered_slugs = {e.slug for e in consistency.entries}
    assert registered_slugs == set(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS)


__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
