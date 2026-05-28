from pathlib import Path

from fastapi.testclient import TestClient

from app.api import snapshot_replay
from app.main import app
from app.providers import MockMarketProvider
from app.providers import SourceRegistryBoundProviderAdapter
from app.providers import build_provider_source_bindings
from app.services import MarketSnapshotService
from app.services import ProviderIngestionService
from app.storage import SnapshotStore
from registry import build_source_registry_entries
from registry import load_source_registry


client = TestClient(app)


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
) -> tuple[SnapshotStore, dict[str, object]]:
    session = FakeSession()
    store = SnapshotStore(tmp_path / "api_snapshots.jsonl")
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
            "audit_source_payload": {
                "source_registry_version": "1.0",
                "provider_adapter": {
                    "contract": "verified_provider_adapter_v1",
                    "total_bound_sources": 27,
                },
            },
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


def test_snapshot_replay_endpoint_returns_paper_safe_replay_payload(tmp_path, monkeypatch) -> None:
    store, stored_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(f"/api/v1/snapshots/{stored_snapshot['snapshot_id']}/replay")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["snapshot_id"] == "snapshot_api_a"
    assert body["paper_safe"] is True
    assert body["execution_mode"] == "PAPER_ONLY"
    assert body["decision_permission"] == "NO_EXECUTION"
    assert body["source_registry_version"] == "1.0"
    assert body["feature_registry_version"] == "1.0"
    assert body["snapshot_count"] == 27
    assert body["source_observation_count"] == 27
    assert body["risk_engine_result"]["risk_action"] == "HOLD"
    assert body["report"]["execution_status"] == "OFF / NO_EXECUTION"
    assert body["audit_source_payload"] == {
        "source_registry_version": "1.0",
        "provider_adapter": {
            "contract": "verified_provider_adapter_v1",
            "total_bound_sources": 27,
        },
    }


def test_snapshot_replay_endpoint_returns_controlled_404_for_missing_snapshot(tmp_path, monkeypatch) -> None:
    store, _ = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/missing_snapshot/replay")
    body = response.json()

    assert response.status_code == 404
    assert body == {
        "error_code": "SNAPSHOT_NOT_FOUND",
        "message": "Requested paper snapshot could not be found.",
        "details": {"snapshot_id": "missing_snapshot"},
        "request_id": body["request_id"],
    }
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_snapshot_replay_endpoint_returns_controlled_422_for_unsafe_payload(monkeypatch) -> None:
    class UnsafeReplayService:
        def replay_snapshot(self, snapshot_id: str):
            raise ValueError("snapshot replay payload execution_mode must remain PAPER_ONLY or NO_EXECUTION.")

    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_service", lambda: UnsafeReplayService())

    response = client.get("/api/v1/snapshots/unsafe_snapshot/replay")
    body = response.json()

    assert response.status_code == 422
    assert body == {
        "error_code": "SNAPSHOT_REPLAY_INVALID",
        "message": "Requested paper snapshot could not be replayed safely.",
        "details": {
            "snapshot_id": "unsafe_snapshot",
            "reason": "snapshot replay payload execution_mode must remain PAPER_ONLY or NO_EXECUTION.",
        },
        "request_id": body["request_id"],
    }
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_snapshot_backtest_summary_endpoint_returns_aggregate_summary(tmp_path, monkeypatch) -> None:
    store, first_snapshot = persist_snapshot_fixture(
        tmp_path,
        report_type="provider_ingestion_paper_snapshot",
        snapshot_id="snapshot_api_a",
    )
    persist_snapshot_fixture(
        tmp_path,
        report_type="paper_backtest_candidate",
        snapshot_id="snapshot_api_b",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/summary?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 2
    assert body["successful_replays"] == 2
    assert body["failed_replays"] == 0
    assert body["successful_snapshot_ids"] == ["snapshot_api_b", first_snapshot["snapshot_id"]]
    assert body["failed_snapshot_ids"] == []
    assert body["report_type_counts"] == {
        "paper_backtest_candidate": 1,
        "provider_ingestion_paper_snapshot": 1,
    }
    assert body["risk_action_counts"] == {"HOLD": 2}
    assert body["trigger_hit_counts"] == {}
    assert body["kill_switch_count"] == 0
    assert body["missing_source_snapshots"] == 0
    assert body["stale_source_snapshots"] == 0
    assert body["execution_statuses"] == ["OFF / NO_EXECUTION"]
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_backtest_summary_endpoint_can_filter_report_type(tmp_path, monkeypatch) -> None:
    store, _ = persist_snapshot_fixture(
        tmp_path,
        report_type="provider_ingestion_paper_snapshot",
        snapshot_id="snapshot_api_a",
    )
    persist_snapshot_fixture(
        tmp_path,
        report_type="paper_backtest_candidate",
        snapshot_id="snapshot_api_b",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/summary?limit=2&report_type=paper_backtest_candidate")
    body = response.json()

    assert response.status_code == 200
    assert body["total_snapshots_requested"] == 1
    assert body["successful_replays"] == 1
    assert body["failed_replays"] == 0
    assert body["successful_snapshot_ids"] == ["snapshot_api_b"]
    assert body["report_type_counts"] == {"paper_backtest_candidate": 1}


def test_snapshot_backtest_summary_endpoint_returns_controlled_404_when_empty(tmp_path, monkeypatch) -> None:
    empty_store = SnapshotStore(tmp_path / "empty_snapshots.jsonl")
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: empty_store)

    response = client.get("/api/v1/snapshots/backtest/summary?limit=5")
    body = response.json()

    assert response.status_code == 404
    assert body == {
        "error_code": "SNAPSHOT_BACKTEST_EMPTY",
        "message": "No replayable paper snapshots were found for the requested backtest.",
        "details": {
            "total_snapshots_requested": 0,
            "failed_replays": 0,
            "failures": [],
        },
        "request_id": body["request_id"],
    }
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_snapshot_compare_endpoint_returns_deterministic_delta_payload(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/compare?baseline_snapshot_id=snapshot_api_a&candidate_snapshot_id=snapshot_api_b"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body == {
        "baseline_snapshot_id": "snapshot_api_a",
        "candidate_snapshot_id": "snapshot_api_b",
        "baseline_created_at": "2026-05-19T09:28:00+00:00",
        "candidate_created_at": "2026-05-19T09:29:00+00:00",
        "baseline_report_type": "provider_ingestion_paper_snapshot",
        "candidate_report_type": "provider_ingestion_paper_snapshot",
        "risk_action_changed": True,
        "risk_action_from": "HOLD",
        "risk_action_to": "NO_POSITION_INCREASE",
        "kill_switch_changed": False,
        "kill_switch_from": False,
        "kill_switch_to": False,
        "new_trigger_codes": ["RED_ENERGY_SHOCK"],
        "cleared_trigger_codes": [],
        "unchanged_trigger_codes": [],
        "new_reason_codes": ["RED_ENERGY_SHOCK_CONFIRMED"],
        "cleared_reason_codes": [],
        "missing_sources_added": [],
        "missing_sources_cleared": [],
        "stale_sources_added": [],
        "stale_sources_cleared": [],
        "execution_status_consistent": True,
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
        "drift_classification": {
            "baseline_snapshot_id": "snapshot_api_a",
            "candidate_snapshot_id": "snapshot_api_b",
            "drift_code": "RISK_GUARDRAIL_TIGHTENED",
            "severity": "YELLOW",
            "summary": "Risk posture tightened to NO_POSITION_INCREASE in the candidate snapshot.",
            "anomaly_flags": [
                "NEW_TRIGGER:RED_ENERGY_SHOCK",
                "NEW_REASON:RED_ENERGY_SHOCK_CONFIRMED",
            ],
            "paper_safe": True,
            "execution_status_consistent": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
        },
    }


def test_snapshot_compare_endpoint_returns_controlled_404_for_missing_snapshot(tmp_path, monkeypatch) -> None:
    store, _ = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/compare?baseline_snapshot_id=snapshot_api_a&candidate_snapshot_id=missing_snapshot"
    )
    body = response.json()

    assert response.status_code == 404
    assert body == {
        "error_code": "SNAPSHOT_COMPARISON_NOT_FOUND",
        "message": "One or more requested paper snapshots could not be found for comparison.",
        "details": {
            "baseline_snapshot_id": "snapshot_api_a",
            "candidate_snapshot_id": "missing_snapshot",
            "missing_snapshot_id": "missing_snapshot",
        },
        "request_id": body["request_id"],
    }
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_snapshot_rolling_diagnostics_endpoint_returns_transition_summary(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={},
        extra_fields={"replay_regime": "HEDGE_BID"},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/rolling-diagnostics?limit=4")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 4
    assert body["successful_replays"] == 4
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == ["snapshot_api_a", "snapshot_api_b", "snapshot_api_c", "snapshot_api_d"]
    assert body["risk_action_path"] == [
        {
            "snapshot_id": "snapshot_api_a",
            "created_at": "2026-05-19T09:28:00+00:00",
            "risk_action": "HOLD",
            "kill_switch_active": False,
        },
        {
            "snapshot_id": "snapshot_api_b",
            "created_at": "2026-05-19T09:29:00+00:00",
            "risk_action": "NO_POSITION_INCREASE",
            "kill_switch_active": False,
        },
        {
            "snapshot_id": "snapshot_api_c",
            "created_at": "2026-05-19T09:30:00+00:00",
            "risk_action": "RISK_REDUCE",
            "kill_switch_active": False,
        },
        {
            "snapshot_id": "snapshot_api_d",
            "created_at": "2026-05-19T09:31:00+00:00",
            "risk_action": "HOLD",
            "kill_switch_active": False,
        },
    ]
    assert body["comparisons_generated"] == 3
    assert body["risk_action_changes"] == 3
    assert body["kill_switch_count"] == 0
    assert body["risk_action_counts"] == {
        "HOLD": 2,
        "NO_POSITION_INCREASE": 1,
        "RISK_REDUCE": 1,
    }
    assert body["trigger_transition_counts"] == {
        "RED_ENERGY_SHOCK": 1,
        "SILVER_EXHAUSTION_WATCH": 1,
        "SILVER_MOMENTUM_ACCELERATION": 1,
        "SILVER_STRATEGIC_METALS_REGIME": 1,
    }
    assert len(body["comparison_results"]) == 3
    assert body["drift_classifications"] == [
        {
            "baseline_snapshot_id": "snapshot_api_a",
            "candidate_snapshot_id": "snapshot_api_b",
            "drift_code": "RISK_GUARDRAIL_TIGHTENED",
            "severity": "YELLOW",
            "summary": "Risk posture tightened to NO_POSITION_INCREASE in the candidate snapshot.",
            "anomaly_flags": [
                "NEW_TRIGGER:RED_ENERGY_SHOCK",
                "NEW_REASON:RED_ENERGY_SHOCK_CONFIRMED",
            ],
            "paper_safe": True,
            "execution_status_consistent": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
        },
        {
            "baseline_snapshot_id": "snapshot_api_b",
            "candidate_snapshot_id": "snapshot_api_c",
            "drift_code": "RISK_ESCALATION_MULTI_SIGNAL",
            "severity": "ORANGE",
            "summary": "Risk posture escalated to RISK_REDUCE because multiple serious signals stacked in the candidate snapshot.",
            "anomaly_flags": [
                "NEW_TRIGGER:SILVER_EXHAUSTION_WATCH",
                "NEW_TRIGGER:SILVER_MOMENTUM_ACCELERATION",
                "NEW_TRIGGER:SILVER_STRATEGIC_METALS_REGIME",
                "NEW_REASON:MULTI_SEVERE_TRIGGER_STACK",
                "NEW_REASON:SILVER_STRATEGIC_METALS_REGIME_NOTE",
            ],
            "paper_safe": True,
            "execution_status_consistent": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
        },
        {
            "baseline_snapshot_id": "snapshot_api_c",
            "candidate_snapshot_id": "snapshot_api_d",
            "drift_code": "CONDITIONS_IMPROVED",
            "severity": "INFO",
            "summary": "The candidate snapshot improved or cleared previously active risk, trigger, or source conditions.",
            "anomaly_flags": [
                "CLEARED_TRIGGER:RED_ENERGY_SHOCK",
                "CLEARED_TRIGGER:SILVER_EXHAUSTION_WATCH",
                "CLEARED_TRIGGER:SILVER_MOMENTUM_ACCELERATION",
                "CLEARED_TRIGGER:SILVER_STRATEGIC_METALS_REGIME",
                "CLEARED_REASON:MULTI_SEVERE_TRIGGER_STACK",
                "CLEARED_REASON:RED_ENERGY_SHOCK_CONFIRMED",
                "CLEARED_REASON:SILVER_STRATEGIC_METALS_REGIME_NOTE",
            ],
            "paper_safe": True,
            "execution_status_consistent": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
        },
    ]
    assert body["drift_trend_score"] == {
        "trend_classification": "deteriorating",
        "trend_score": 3,
        "severity_bucket": "MEDIUM",
        "comparison_count": 3,
        "improving_transitions": 1,
        "deteriorating_transitions": 2,
        "stable_transitions": 0,
        "diagnostics": [
            "Trend classification is deteriorating across 3 deterministic drift transition(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["regime_summary"] == {
        "status": "partial",
        "distribution_classification": "mixed",
        "dominant_regime": "RISK_OFF",
        "regime_distribution": {
            "HEDGE_BID": 1,
            "RISK_OFF": 2,
        },
        "transition_count": 1,
        "mixed_or_unstable": True,
        "available_regime_count": 3,
        "missing_regime_count": 1,
        "diagnostics": [
            "Dominant replay regime is RISK_OFF across 3 saved snapshot regime observation(s).",
            "1 saved snapshot(s) did not include replay regime metadata.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["anomaly_watchlist"] == {
        "summary": {
            "total_items": 2,
            "stable_transitions": 0,
            "improving_transitions": 1,
            "anomalous_transitions": 2,
            "paper_safe": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
        },
        "watchlist_items": [
            {
                "watchlist_code": "RISK_ESCALATION_MULTI_SIGNAL",
                "severity": "ORANGE",
                "occurrence_count": 1,
                "first_snapshot_id": "snapshot_api_b",
                "latest_snapshot_id": "snapshot_api_c",
                "related_snapshot_pairs": ["snapshot_api_b->snapshot_api_c"],
                "trigger_codes": [
                    "SILVER_EXHAUSTION_WATCH",
                    "SILVER_MOMENTUM_ACCELERATION",
                    "SILVER_STRATEGIC_METALS_REGIME",
                ],
                "reason_codes": [
                    "MULTI_SEVERE_TRIGGER_STACK",
                    "SILVER_STRATEGIC_METALS_REGIME_NOTE",
                ],
                "source_ids": [],
                "latest_summary": "Risk posture escalated to RISK_REDUCE because multiple serious signals stacked in the candidate snapshot.",
            },
            {
                "watchlist_code": "RISK_GUARDRAIL_TIGHTENED",
                "severity": "YELLOW",
                "occurrence_count": 1,
                "first_snapshot_id": "snapshot_api_a",
                "latest_snapshot_id": "snapshot_api_b",
                "related_snapshot_pairs": ["snapshot_api_a->snapshot_api_b"],
                "trigger_codes": ["RED_ENERGY_SHOCK"],
                "reason_codes": ["RED_ENERGY_SHOCK_CONFIRMED"],
                "source_ids": [],
                "latest_summary": "Risk posture tightened to NO_POSITION_INCREASE in the candidate snapshot.",
            },
        ],
    }
    assert body["fallback_usage_recurrence"] == {
        "stability_classification": "stable",
        "severity_score": 0,
        "total_snapshots_requested": 4,
        "snapshots_checked": 4,
        "snapshots_with_fallback": 0,
        "total_fallback_events": 0,
        "unique_fallback_providers": 0,
        "malformed_snapshot_count": 0,
        "missing_provider_metadata_count": 0,
        "timeline": [
            {
                "snapshot_id": "snapshot_api_a",
                "created_at": "2026-05-19T09:28:00+00:00",
                "status": "stable",
                "fallback_event_count": 0,
                "fallback_provider_count": 0,
                "affected_providers": [],
                "affected_assets": [],
                "severity_score": 0,
                "diagnostic": "No fallback providers were used in this saved payload.",
            },
            {
                "snapshot_id": "snapshot_api_b",
                "created_at": "2026-05-19T09:29:00+00:00",
                "status": "stable",
                "fallback_event_count": 0,
                "fallback_provider_count": 0,
                "affected_providers": [],
                "affected_assets": [],
                "severity_score": 0,
                "diagnostic": "No fallback providers were used in this saved payload.",
            },
            {
                "snapshot_id": "snapshot_api_c",
                "created_at": "2026-05-19T09:30:00+00:00",
                "status": "stable",
                "fallback_event_count": 0,
                "fallback_provider_count": 0,
                "affected_providers": [],
                "affected_assets": [],
                "severity_score": 0,
                "diagnostic": "No fallback providers were used in this saved payload.",
            },
            {
                "snapshot_id": "snapshot_api_d",
                "created_at": "2026-05-19T09:31:00+00:00",
                "status": "stable",
                "fallback_event_count": 0,
                "fallback_provider_count": 0,
                "affected_providers": [],
                "affected_assets": [],
                "severity_score": 0,
                "diagnostic": "No fallback providers were used in this saved payload.",
            },
        ],
        "recurring_entries": [],
        "entries": [],
        "failures": [],
        "diagnostics": [
            "No fallback provider usage was detected across 4 saved snapshot(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["raw_payload_reference_completeness"] == {
        "completeness_classification": "complete",
        "average_completeness_percentage": 100.0,
        "total_snapshots_requested": 4,
        "snapshots_checked": 4,
        "complete_snapshots": 4,
        "partial_snapshots": 0,
        "degraded_snapshots": 0,
        "invalid_snapshots": 0,
        "missing_reference_assets": [],
        "empty_reference_assets": [],
        "malformed_reference_assets": [],
        "entries": [
            {
                "snapshot_id": "snapshot_api_a",
                "created_at": "2026-05-19T09:28:00+00:00",
                "completeness_classification": "complete",
                "completeness_percentage": 100.0,
                "total_records": 27,
                "complete_records": 27,
                "partial_reference_assets": [],
                "missing_reference_assets": [],
                "empty_reference_assets": [],
                "malformed_reference_assets": [],
                "diagnostic": "All snapshot records preserved a usable raw payload reference.",
            },
            {
                "snapshot_id": "snapshot_api_b",
                "created_at": "2026-05-19T09:29:00+00:00",
                "completeness_classification": "complete",
                "completeness_percentage": 100.0,
                "total_records": 27,
                "complete_records": 27,
                "partial_reference_assets": [],
                "missing_reference_assets": [],
                "empty_reference_assets": [],
                "malformed_reference_assets": [],
                "diagnostic": "All snapshot records preserved a usable raw payload reference.",
            },
            {
                "snapshot_id": "snapshot_api_c",
                "created_at": "2026-05-19T09:30:00+00:00",
                "completeness_classification": "complete",
                "completeness_percentage": 100.0,
                "total_records": 27,
                "complete_records": 27,
                "partial_reference_assets": [],
                "missing_reference_assets": [],
                "empty_reference_assets": [],
                "malformed_reference_assets": [],
                "diagnostic": "All snapshot records preserved a usable raw payload reference.",
            },
            {
                "snapshot_id": "snapshot_api_d",
                "created_at": "2026-05-19T09:31:00+00:00",
                "completeness_classification": "complete",
                "completeness_percentage": 100.0,
                "total_records": 27,
                "complete_records": 27,
                "partial_reference_assets": [],
                "missing_reference_assets": [],
                "empty_reference_assets": [],
                "malformed_reference_assets": [],
                "diagnostic": "All snapshot records preserved a usable raw payload reference.",
            },
        ],
        "failures": [],
        "diagnostics": [
            "Raw payload reference completeness is complete across 4 saved snapshot(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["source_observation_cadence_drift"]["paper_safe"] is True
    assert body["source_record_completeness"]["paper_safe"] is True
    assert body["source_verification_drift"]["paper_safe"] is True
    assert body["paper_safe_source_flag_consistency"]["paper_safe"] is True
    assert body["source_observation_summary_drift"]["paper_safe"] is True
    assert body["provider_adapter_contract_consistency"]["paper_safe"] is True
    assert body["source_observation_timestamp_integrity_drift"]["paper_safe"] is True
    assert body["source_observation_record_summary_reconciliation"]["paper_safe"] is True
    assert body["source_observation_normalization_mode_drift"]["paper_safe"] is True
    assert body["mapped_at_alignment_consistency"]["paper_safe"] is True
    assert body["source_observation_confidence_drift"]["paper_safe"] is True
    assert body["verified_source_coverage_reconciliation"]["paper_safe"] is True
    assert body["source_observation_availability_lag_drift"]["paper_safe"] is True
    assert body["source_freshness_summary_reconciliation"]["paper_safe"] is True
    assert body["source_freshness_policy_drift"]["paper_safe"] is True
    assert body["stale_source_list_threshold_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_freshness_evaluation_mode_drift"]["paper_safe"] is True
    assert body["source_diagnostics_stale_asset_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_average_coverage_drift"]["paper_safe"] is True
    assert body["source_diagnostics_minimum_coverage_floor_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_ready_feature_drift"]["paper_safe"] is True
    assert body["source_diagnostics_stale_feature_drift"]["paper_safe"] is True
    assert body["source_diagnostics_critical_feature_drift"]["paper_safe"] is True
    assert body["source_diagnostics_high_severity_drift"]["paper_safe"] is True
    assert body["source_diagnostics_warning_feature_drift"]["paper_safe"] is True
    assert body["source_diagnostics_info_feature_drift"]["paper_safe"] is True
    assert body["source_diagnostics_zero_rank_drift"]["paper_safe"] is True
    assert body["source_diagnostics_severity_label_drift"]["paper_safe"] is True
    assert body["source_diagnostics_severity_rank_drift"]["paper_safe"] is True
    assert body["source_diagnostics_severity_rank_density_drift"]["paper_safe"] is True
    assert body["source_diagnostics_severity_rank_spread_drift"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_feature_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_warning_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_info_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_non_actionable_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_rank_label_consistency_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_rank_order_continuity_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_severity_ranking_critical_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_missing_source_feature_count_reconciliation"]["paper_safe"] is True
    assert body["source_diagnostics_missing_asset_count_reconciliation"]["paper_safe"] is True
    assert body["source_observation_freshness_seconds_drift"]["paper_safe"] is True
    assert body["source_freshness_status_threshold_reconciliation"]["paper_safe"] is True
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_rolling_diagnostics_endpoint_returns_safe_missing_regime_summary(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/rolling-diagnostics?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert body["regime_summary"] == {
        "status": "missing",
        "distribution_classification": "missing",
        "dominant_regime": None,
        "regime_distribution": {},
        "transition_count": 0,
        "mixed_or_unstable": False,
        "available_regime_count": 0,
        "missing_regime_count": 2,
        "diagnostics": [
            "No saved replay regimes were present in the requested snapshots.",
            "Saved replay regime metadata was not present.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def test_snapshot_drift_trend_leaderboard_endpoint_returns_ranked_entries(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        "snapshot_api_b",
        new_snapshot_id="snapshot_api_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 82.35},
    )
    persist_snapshot_variant(
        store,
        "snapshot_api_c",
        new_snapshot_id="snapshot_api_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/drift-trend-leaderboard?limit=4")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 4
    assert body["successful_replays"] == 4
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == [
        "snapshot_api_a",
        "snapshot_api_b",
        "snapshot_api_c",
        "snapshot_api_d",
    ]
    assert body["drift_trend_score"] == {
        "trend_classification": "deteriorating",
        "trend_score": 2,
        "severity_bucket": "LOW",
        "comparison_count": 3,
        "improving_transitions": 1,
        "deteriorating_transitions": 2,
        "stable_transitions": 0,
        "diagnostics": [
            "Trend classification is deteriorating across 3 deterministic drift transition(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["drift_trend_leaderboard"] == {
        "total_entries": 2,
        "entries": [
            {
                "rank": 1,
                "drift_code": "RISK_GUARDRAIL_TIGHTENED",
                "direction": "deteriorating",
                "severity": "YELLOW",
                "occurrence_count": 2,
                "total_weight": 4,
                "related_snapshot_pairs": [
                    "snapshot_api_a->snapshot_api_b",
                    "snapshot_api_c->snapshot_api_d",
                ],
                "latest_summary": "Risk posture tightened to NO_POSITION_INCREASE in the candidate snapshot.",
            },
            {
                "rank": 2,
                "drift_code": "CONDITIONS_IMPROVED",
                "direction": "improving",
                "severity": "INFO",
                "occurrence_count": 1,
                "total_weight": -2,
                "related_snapshot_pairs": ["snapshot_api_b->snapshot_api_c"],
                "latest_summary": "The candidate snapshot improved or cleared previously active risk, trigger, or source conditions.",
            },
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_regime_timeline_endpoint_returns_paper_safe_timeline(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
        extra_fields={"replay_regime": "RISK_OFF"},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={},
        extra_fields={"replay_regime": "HEDGE_BID"},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/regime-timeline?limit=4")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 4
    assert body["successful_replays"] == 4
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == [
        "snapshot_api_a",
        "snapshot_api_b",
        "snapshot_api_c",
        "snapshot_api_d",
    ]
    assert body["regime_summary"]["dominant_regime"] == "RISK_OFF"
    assert body["regime_timeline"] == {
        "status": "partial",
        "total_snapshots": 4,
        "dominant_regime": "RISK_OFF",
        "transition_count": 1,
        "mixed_or_unstable": True,
        "available_regime_count": 3,
        "missing_regime_count": 1,
        "entries": [
            {
                "snapshot_id": "snapshot_api_a",
                "created_at": "2026-05-19T09:28:00+00:00",
                "replay_regime": None,
                "status": "missing",
                "diagnostic": "Saved replay regime metadata was not present.",
                "transition_from_previous": False,
                "dominant_regime_match": False,
            },
            {
                "snapshot_id": "snapshot_api_b",
                "created_at": "2026-05-19T09:29:00+00:00",
                "replay_regime": "RISK_OFF",
                "status": "available",
                "diagnostic": None,
                "transition_from_previous": False,
                "dominant_regime_match": True,
            },
            {
                "snapshot_id": "snapshot_api_c",
                "created_at": "2026-05-19T09:30:00+00:00",
                "replay_regime": "RISK_OFF",
                "status": "available",
                "diagnostic": None,
                "transition_from_previous": False,
                "dominant_regime_match": True,
            },
            {
                "snapshot_id": "snapshot_api_d",
                "created_at": "2026-05-19T09:31:00+00:00",
                "replay_regime": "HEDGE_BID",
                "status": "available",
                "diagnostic": None,
                "transition_from_previous": True,
                "dominant_regime_match": False,
            },
        ],
        "diagnostics": [
            "Dominant replay regime is RISK_OFF across 3 saved snapshot regime observation(s).",
            "1 saved snapshot(s) did not include replay regime metadata.",
            "Replay regime timeline covers 4 saved snapshot(s) in chronological order.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_regime_timeline_endpoint_returns_safe_missing_regime_diagnostics(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/regime-timeline?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert body["regime_timeline"] == {
        "status": "missing",
        "total_snapshots": 2,
        "dominant_regime": None,
        "transition_count": 0,
        "mixed_or_unstable": False,
        "available_regime_count": 0,
        "missing_regime_count": 2,
        "entries": [
            {
                "snapshot_id": "snapshot_api_a",
                "created_at": "2026-05-19T09:28:00+00:00",
                "replay_regime": None,
                "status": "missing",
                "diagnostic": "Saved replay regime metadata was not present.",
                "transition_from_previous": False,
                "dominant_regime_match": False,
            },
            {
                "snapshot_id": "snapshot_api_b",
                "created_at": "2026-05-19T09:29:00+00:00",
                "replay_regime": None,
                "status": "missing",
                "diagnostic": "Saved replay regime metadata was not present.",
                "transition_from_previous": False,
                "dominant_regime_match": False,
            },
        ],
        "diagnostics": [
            "No saved replay regimes were present in the requested snapshots.",
            "Saved replay regime metadata was not present.",
            "Replay regime timeline covers 2 saved snapshot(s) in chronological order.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def test_snapshot_trigger_persistence_leaderboard_endpoint_returns_ranked_payload(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_c",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={"BRENT": 130.0, "XAGUSD": 97.0},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={"BRENT": 130.0},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/trigger-persistence-leaderboard?limit=4")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 4
    assert body["successful_replays"] == 4
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == [
        "snapshot_api_a",
        "snapshot_api_b",
        "snapshot_api_c",
        "snapshot_api_d",
    ]
    assert body["trigger_persistence_leaderboard"] == {
        "total_entries": 4,
        "total_snapshots": 4,
        "entries": [
            {
                "rank": 1,
                "trigger_code": "RED_ENERGY_SHOCK",
                "asset_symbol": "BRENT",
                "severity": "RED",
                "persistence_classification": "recurring",
                "active_snapshot_count": 3,
                "persistence_ratio": 0.75,
                "longest_streak": 3,
                "first_snapshot_id": "snapshot_api_b",
                "latest_snapshot_id": "snapshot_api_d",
                "active_snapshot_ids": [
                    "snapshot_api_b",
                    "snapshot_api_c",
                    "snapshot_api_d",
                ],
                "latest_message": "Brent is above the energy shock threshold.",
            },
            {
                "rank": 2,
                "trigger_code": "SILVER_EXHAUSTION_WATCH",
                "asset_symbol": "XAGUSD",
                "severity": "RED",
                "persistence_classification": "intermittent",
                "active_snapshot_count": 1,
                "persistence_ratio": 0.25,
                "longest_streak": 1,
                "first_snapshot_id": "snapshot_api_c",
                "latest_snapshot_id": "snapshot_api_c",
                "active_snapshot_ids": ["snapshot_api_c"],
                "latest_message": "Silver is above the exhaustion watch threshold.",
            },
            {
                "rank": 3,
                "trigger_code": "SILVER_MOMENTUM_ACCELERATION",
                "asset_symbol": "XAGUSD",
                "severity": "ORANGE",
                "persistence_classification": "intermittent",
                "active_snapshot_count": 1,
                "persistence_ratio": 0.25,
                "longest_streak": 1,
                "first_snapshot_id": "snapshot_api_c",
                "latest_snapshot_id": "snapshot_api_c",
                "active_snapshot_ids": ["snapshot_api_c"],
                "latest_message": "Silver is above the momentum acceleration threshold.",
            },
            {
                "rank": 4,
                "trigger_code": "SILVER_STRATEGIC_METALS_REGIME",
                "asset_symbol": "XAGUSD",
                "severity": "YELLOW",
                "persistence_classification": "intermittent",
                "active_snapshot_count": 1,
                "persistence_ratio": 0.25,
                "longest_streak": 1,
                "first_snapshot_id": "snapshot_api_c",
                "latest_snapshot_id": "snapshot_api_c",
                "active_snapshot_ids": ["snapshot_api_c"],
                "latest_message": "Silver is above the strategic metals regime threshold.",
            },
        ],
        "diagnostics": [
            "Trigger persistence leaderboard covers 4 saved snapshot(s) and 4 active trigger type(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_risk_action_stability_endpoint_returns_paper_safe_summary(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/risk-action-stability?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 2
    assert body["successful_replays"] == 2
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == ["snapshot_api_a", "snapshot_api_b"]
    assert body["risk_action_path"] == [
        {
            "snapshot_id": "snapshot_api_a",
            "created_at": "2026-05-19T09:28:00+00:00",
            "risk_action": "HOLD",
            "kill_switch_active": False,
        },
        {
            "snapshot_id": "snapshot_api_b",
            "created_at": "2026-05-19T09:29:00+00:00",
            "risk_action": "HOLD",
            "kill_switch_active": False,
        },
    ]
    assert body["risk_action_stability"] == {
        "stability_classification": "stable",
        "dominant_risk_action": "HOLD",
        "first_risk_action": "HOLD",
        "latest_risk_action": "HOLD",
        "transition_count": 0,
        "longest_stable_run": 2,
        "unique_action_count": 1,
        "risk_action_counts": {"HOLD": 2},
        "diagnostics": [
            "Risk action remained HOLD across 2 saved snapshot(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_risk_action_stability_endpoint_handles_insufficient_data_safely(tmp_path, monkeypatch) -> None:
    store, _ = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/risk-action-stability?limit=1")
    body = response.json()

    assert response.status_code == 200
    assert body["risk_action_stability"] == {
        "stability_classification": "insufficient_data",
        "dominant_risk_action": "HOLD",
        "first_risk_action": "HOLD",
        "latest_risk_action": "HOLD",
        "transition_count": 0,
        "longest_stable_run": 1,
        "unique_action_count": 1,
        "risk_action_counts": {"HOLD": 1},
        "diagnostics": [
            "At least two replayable snapshots are required to evaluate risk action stability.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def test_snapshot_source_gap_recurrence_leaderboard_endpoint_returns_ranked_payload(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"missing_sources": ["energy_feed"]},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_c",
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
        new_snapshot_id="snapshot_api_d",
        created_at="2026-05-19T09:31:00+00:00",
        asset_overrides={},
        extra_fields={"stale_sources": ["macro_feed"]},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/source-gap-recurrence-leaderboard?limit=4")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 4
    assert body["successful_replays"] == 4
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == [
        "snapshot_api_a",
        "snapshot_api_b",
        "snapshot_api_c",
        "snapshot_api_d",
    ]
    assert body["source_gap_recurrence_leaderboard"] == {
        "total_entries": 2,
        "total_snapshots": 4,
        "entries": [
            {
                "rank": 1,
                "source_id": "energy_feed",
                "gap_status": "missing",
                "severity": "ORANGE",
                "recurrence_classification": "recurring",
                "occurrence_count": 2,
                "recurrence_ratio": 0.5,
                "longest_streak": 2,
                "first_snapshot_id": "snapshot_api_b",
                "latest_snapshot_id": "snapshot_api_c",
                "affected_snapshot_ids": ["snapshot_api_b", "snapshot_api_c"],
            },
            {
                "rank": 2,
                "source_id": "macro_feed",
                "gap_status": "stale",
                "severity": "YELLOW",
                "recurrence_classification": "recurring",
                "occurrence_count": 2,
                "recurrence_ratio": 0.5,
                "longest_streak": 2,
                "first_snapshot_id": "snapshot_api_c",
                "latest_snapshot_id": "snapshot_api_d",
                "affected_snapshot_ids": ["snapshot_api_c", "snapshot_api_d"],
            },
        ],
        "diagnostics": [
            "Source gap recurrence leaderboard covers 4 saved snapshot(s) and 2 gap source(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_dqs_stability_endpoint_returns_paper_safe_summary(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/dqs-stability?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 2
    assert body["successful_replays"] == 2
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == ["snapshot_api_a", "snapshot_api_b"]
    assert body["dqs_stability"]["stability_classification"] == "stable"
    assert body["dqs_stability"]["dominant_decision"] == body["dqs_stability"]["first_decision"]
    assert body["dqs_stability"]["first_decision"] == body["dqs_stability"]["latest_decision"]
    assert body["dqs_stability"]["transition_count"] == 0
    assert body["dqs_stability"]["unique_decision_count"] == 1
    assert len(body["dqs_stability"]["path"]) == 2
    assert body["dqs_stability"]["path"][0]["snapshot_id"] == "snapshot_api_a"
    assert body["dqs_stability"]["path"][1]["snapshot_id"] == "snapshot_api_b"
    assert body["dqs_stability"]["diagnostics"] == [
        f"DQS aggregate decision remained {body['dqs_stability']['first_decision']} across 2 saved snapshot(s).",
    ]
    assert body["dqs_stability"]["paper_safe"] is True
    assert body["dqs_stability"]["network_calls"] is False
    assert body["dqs_stability"]["execution_side_effects"] == "NO_EXECUTION"
    assert body["paper_safe"] is True


def test_snapshot_dqs_stability_endpoint_handles_deterioration_safely(tmp_path, monkeypatch) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
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
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/dqs-stability?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert body["dqs_stability"]["stability_classification"] == "deteriorating"
    assert body["dqs_stability"]["latest_decision"] == "FAIL_NO_DECISION"
    assert body["dqs_stability"]["transition_count"] == 1
    assert body["dqs_stability"]["unique_decision_count"] == 2
    assert body["dqs_stability"]["lowest_minimum_score"] == 35.0
    assert body["dqs_stability"]["path"][1]["aggregate_decision"] == "FAIL_NO_DECISION"
    assert body["dqs_stability"]["diagnostics"] == [
        f"DQS aggregate decision deteriorated from {body['dqs_stability']['first_decision']} to FAIL_NO_DECISION across saved snapshots.",
    ]


def test_snapshot_source_freshness_decay_timeline_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    degraded_source_observations = dict(baseline_snapshot["source_observations"])
    first_source_id = sorted(degraded_source_observations)[0]
    degraded_source_observations[first_source_id] = "2026-05-18T00:00:00+00:00"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": degraded_source_observations},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/source-freshness-decay-timeline?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["total_snapshots_requested"] == 2
    assert body["successful_replays"] == 2
    assert body["failed_replays"] == 0
    assert body["ordered_snapshot_ids"] == ["snapshot_api_a", "snapshot_api_b"]
    assert body["source_freshness_decay_timeline"] == {
        "decay_classification": "degrading",
        "total_snapshots": 2,
        "evaluable_snapshots": 2,
        "missing_freshness_snapshots": 0,
        "first_status": "fresh",
        "latest_status": "stale",
        "dominant_status": "fresh",
        "worst_status": "stale",
        "transition_count": 1,
        "decay_score_delta": 2,
        "entries": [
            {
                "snapshot_id": "snapshot_api_a",
                "created_at": "2026-05-19T09:28:00+00:00",
                "freshness_status": "fresh",
                "fresh_source_count": 27,
                "stale_source_count": 0,
                "missing_timestamp_source_count": 0,
                "degraded_source_count": 0,
                "total_active_sources": 27,
                "decay_score": 0,
                "diagnostic": "All active sources satisfied freshness policy at replay time.",
            },
            {
                "snapshot_id": "snapshot_api_b",
                "created_at": "2026-05-19T09:29:00+00:00",
                "freshness_status": "stale",
                "fresh_source_count": 26,
                "stale_source_count": 1,
                "missing_timestamp_source_count": 0,
                "degraded_source_count": 1,
                "total_active_sources": 27,
                "decay_score": 2,
                "diagnostic": "1 source(s) breached freshness policy and 0 source(s) missed timestamps.",
            },
        ],
        "failures": [],
        "total_snapshots_requested": 2,
        "diagnostics": [
            "Source freshness deteriorated from fresh to stale across saved snapshots.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }
    assert body["failures"] == []
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_no_execution_guardrail_consistency_endpoint_returns_violations_safely(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    safe_snapshot_payload = store.load_snapshot(baseline_snapshot["snapshot_id"])
    unsafe_snapshot_payload = dict(safe_snapshot_payload)
    unsafe_snapshot_payload["snapshot_id"] = "snapshot_api_unsafe"
    unsafe_snapshot_payload["created_at"] = "2026-05-19T09:29:00+00:00"
    unsafe_snapshot_payload["decision_permission"] = "EXECUTE"
    store._write_entries([safe_snapshot_payload, unsafe_snapshot_payload])
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/no-execution-guardrail-consistency?limit=2")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body == {
        "consistency_status": "violations_detected",
        "total_snapshots_requested": 2,
        "snapshots_checked": 2,
        "consistent_snapshots": 1,
        "violation_count": 1,
        "entries": [
            {
                "snapshot_id": "snapshot_api_a",
                "created_at": "2026-05-19T09:28:00+00:00",
                "report_type": "provider_ingestion_paper_snapshot",
                "mode": "PAPER_SAFE",
                "execution_mode": "PAPER_ONLY",
                "decision_permission": "NO_EXECUTION",
                "consistent": True,
                "violation_codes": [],
                "diagnostic": "Snapshot preserved the NO_EXECUTION guardrail.",
            },
            {
                "snapshot_id": "snapshot_api_unsafe",
                "created_at": "2026-05-19T09:29:00+00:00",
                "report_type": "provider_ingestion_paper_snapshot",
                "mode": "PAPER_SAFE",
                "execution_mode": "PAPER_ONLY",
                "decision_permission": "EXECUTE",
                "consistent": False,
                "violation_codes": ["DECISION_PERMISSION_BREACH"],
                "diagnostic": "Snapshot violated the paper-safe NO_EXECUTION guardrail: DECISION_PERMISSION_BREACH.",
            },
        ],
        "violations": [
            {
                "snapshot_id": "snapshot_api_unsafe",
                "created_at": "2026-05-19T09:29:00+00:00",
                "report_type": "provider_ingestion_paper_snapshot",
                "mode": "PAPER_SAFE",
                "execution_mode": "PAPER_ONLY",
                "decision_permission": "EXECUTE",
                "consistent": False,
                "violation_codes": ["DECISION_PERMISSION_BREACH"],
                "diagnostic": "Snapshot violated the paper-safe NO_EXECUTION guardrail: DECISION_PERMISSION_BREACH.",
            },
        ],
        "failures": [],
        "diagnostics": [
            "Detected 1 NO_EXECUTION guardrail violation(s) across 2 saved snapshot(s).",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def test_snapshot_fallback_usage_recurrence_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
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
        new_snapshot_id="snapshot_api_c",
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
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/fallback-usage-recurrence?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_b&snapshot_ids=snapshot_api_c"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["stability_classification"] == "elevated"
    assert body["severity_score"] == 55
    assert body["snapshots_checked"] == 3
    assert body["snapshots_with_fallback"] == 2
    assert body["total_fallback_events"] == 3
    assert body["timeline"][1]["status"] == "elevated"
    assert body["timeline"][2]["status"] == "critical"
    assert body["recurring_entries"] == [
        {
            "rank": 1,
            "provider_name": "fallback_energy_provider",
            "recurrence_classification": "elevated",
            "severity_score": 70,
            "occurrence_count": 2,
            "recurrence_ratio": 0.67,
            "longest_streak": 2,
            "affected_snapshot_ids": ["snapshot_api_b", "snapshot_api_c"],
            "affected_assets": ["BRENT", "XAUUSD"],
            "missing_provider_metadata_count": 0,
        },
    ]
    assert body["diagnostics"] == [
        "Fallback usage recurrence is elevated across 3 saved snapshot(s).",
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_raw_payload_reference_completeness_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            "BRENT": {
                "raw_payload_ref": None,
            },
        },
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/raw-payload-reference-completeness?snapshot_ids=snapshot_api_partial"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body == {
        "completeness_classification": "partial",
        "average_completeness_percentage": 96.3,
        "total_snapshots_requested": 1,
        "snapshots_checked": 1,
        "complete_snapshots": 0,
        "partial_snapshots": 1,
        "degraded_snapshots": 0,
        "invalid_snapshots": 0,
        "missing_reference_assets": ["BRENT"],
        "empty_reference_assets": [],
        "malformed_reference_assets": [],
        "entries": [
            {
                "snapshot_id": "snapshot_api_partial",
                "created_at": "2026-05-19T09:29:00+00:00",
                "completeness_classification": "partial",
                "completeness_percentage": 96.3,
                "total_records": 27,
                "complete_records": 26,
                "partial_reference_assets": [],
                "missing_reference_assets": ["BRENT"],
                "empty_reference_assets": [],
                "malformed_reference_assets": [],
                "diagnostic": "Raw payload references were partially complete for 26 of 27 snapshot record(s).",
            },
        ],
        "failures": [],
        "diagnostics": [
            "Raw payload reference completeness is partial across 1 saved snapshot(s).",
            "1 asset symbol(s) were missing raw payload references.",
        ],
        "paper_safe": True,
        "network_calls": False,
        "execution_side_effects": "NO_EXECUTION",
    }


def test_snapshot_source_observation_cadence_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    stable_source_observations = {
        source_id: "2026-05-19T09:29:00+00:00"
        for source_id in baseline_snapshot["source_observations"]
    }
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_b",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observations": stable_source_observations},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-cadence-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_b"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["cadence_classification"] == "stable"
    assert body["cadence_score"] == 100
    assert body["severity_bucket"] == "NONE"
    assert body["snapshots_checked"] == 2
    assert body["evaluable_snapshots"] == 2
    assert body["missing_timestamp_snapshots"] == 0
    assert body["entries"][0]["cadence_status"] == "baseline"
    assert body["entries"][1]["cadence_status"] == "stable"
    assert body["entries"][1]["interval_seconds_from_previous"] == 60
    assert body["diagnostics"] == [
        "Source observation cadence remained stable across 2 evaluable saved snapshot(s).",
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_record_completeness_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    first_record_label = str(source_observation_records[0]["asset_symbol"])
    source_observation_records[0]["registry_provider"] = ""
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_partial_records",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-record-completeness?snapshot_ids=snapshot_api_partial_records"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["completeness_classification"] == "partial"
    assert body["average_completeness_percentage"] == 96.3
    assert body["snapshots_checked"] == 1
    assert body["complete_snapshots"] == 0
    assert body["partial_snapshots"] == 1
    assert body["degraded_snapshots"] == 0
    assert body["invalid_snapshots"] == 0
    assert body["aggregate_missing_field_counts"] == {"registry_provider": 1}
    assert body["missing_field_diagnostics"] == [f"{first_record_label}:registry_provider:missing"]
    assert body["entries"][0]["completeness_classification"] == "partial"
    assert body["entries"][0]["complete_records"] == 26
    assert body["entries"][0]["missing_field_counts"] == {"registry_provider": 1}
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_registry_binding_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    drifted_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["registry_provider"] = "drifted_provider"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_binding_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-registry-binding-drift?snapshot_ids=snapshot_api_binding_drift"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "drifting"
    assert body["severity_score"] == 15
    assert body["current_source_registry_version"] == "1.0"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 0
    assert body["drifting_snapshots"] == 1
    assert body["degraded_snapshots"] == 0
    assert body["invalid_snapshots"] == 0
    assert body["provider_mismatch_source_ids"] == [drifted_source_id]
    assert body["entries"][0]["binding_classification"] == "drifting"
    assert body["entries"][0]["matched_records"] == 26
    assert body["entries"][0]["provider_mismatch_source_ids"] == [drifted_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_decision_usage_consistency_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_usage_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-decision-usage-consistency?snapshot_ids=snapshot_api_usage_drift"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 92.59
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["aggregate_decision_usage_counts"] == {
        "simulation_only": 4,
        "verified_required": 23,
    }
    assert body["mismatched_source_ids"] == [mismatched_source_id]
    assert body["unsafe_source_ids"] == [unsafe_source_id]
    assert body["entries"][0]["consistency_classification"] == "degraded"
    assert body["entries"][0]["consistent_records"] == 25
    assert body["entries"][0]["mismatched_source_ids"] == [mismatched_source_id]
    assert body["entries"][0]["unsafe_source_ids"] == [unsafe_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_verification_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_verification_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-verification-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_verification_drift"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_verification_score"] == 87.5
    assert body["severity_score"] == 25
    assert body["current_source_registry_version"] == "1.0"
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["improving_snapshots"] == 0
    assert body["mixed_snapshots"] == 0
    assert body["degraded_source_ids"] == [degraded_source_id]
    assert body["entries"][1]["verification_classification"] == "degrading"
    assert body["entries"][1]["verification_score"] == 75.0
    assert body["entries"][1]["degraded_source_ids"] == [degraded_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_paper_safe_source_flag_consistency_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_flag_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/paper-safe-source-flag-consistency?snapshot_ids=snapshot_api_source_flag_drift"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 92.59
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["false_flag_source_ids"] == [false_source_id]
    assert body["missing_flag_source_ids"] == [missing_source_id]
    assert body["unsafe_source_ids"] == sorted([false_source_id, missing_source_id])
    assert body["entries"][0]["consistency_classification"] == "degraded"
    assert body["entries"][0]["safe_records"] == 25
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_summary_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    degraded_summary = dict(baseline_snapshot["source_observation_summary"])
    degraded_summary["verified_sources"] = 20
    degraded_summary["paper_safe_sources"] = 25
    degraded_summary["total_bound_sources"] = 25
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_summary_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-summary-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_summary_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_summary_score"] == 95.05
    assert body["severity_score"] == 10
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["expected_total_bound_sources"] == 27
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["verified_sources"] == 20
    assert body["entries"][1]["paper_safe_sources"] == 25
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_provider_adapter_contract_consistency_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    audit_source_payload = dict(baseline_snapshot["audit_source_payload"])
    provider_adapter = dict(audit_source_payload["provider_adapter"])
    provider_adapter["contract"] = "verified_provider_adapter_v2"
    provider_adapter["total_bound_sources"] = 26
    audit_source_payload["provider_adapter"] = provider_adapter
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_contract_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"audit_source_payload": audit_source_payload},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/provider-adapter-contract-consistency?snapshot_ids=snapshot_api_contract_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["expected_contract"] == "verified_provider_adapter_v1"
    assert body["snapshots_checked"] == 1
    assert body["degraded_snapshots"] == 1
    assert body["mismatched_contract_snapshot_ids"] == ["snapshot_api_contract_degraded"]
    assert body["bound_source_mismatch_snapshot_ids"] == ["snapshot_api_contract_degraded"]
    assert body["entries"][0]["mismatched_fields"] == [
        "audit_source_payload.provider_adapter.contract",
        "provider_adapter.contract_alignment",
        "provider_adapter.total_bound_sources_alignment",
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_timestamp_integrity_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    source_observation_records = [
        dict(record)
        for record in baseline_snapshot["source_observation_records"]
    ]
    degraded_source_id = str(source_observation_records[0]["source_id"])
    source_observation_records[0]["available_at"] = "2026-05-19T09:35:00+00:00"
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_timestamp_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-timestamp-integrity-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_timestamp_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_integrity_score"] == 98.15
    assert body["severity_score"] == 4
    assert body["snapshots_checked"] == 2
    assert body["degrading_snapshots"] == 1
    assert body["sequence_violation_source_ids"] == [degraded_source_id]
    assert body["entries"][1]["integrity_classification"] == "degrading"
    assert body["entries"][1]["integrity_score"] == 96.3
    assert body["entries"][1]["sequence_violation_source_ids"] == [degraded_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_record_summary_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    summary = dict(baseline_snapshot["source_observation_summary"])
    summary["verified_sources"] = 20
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_reconciliation_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_summary": summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-record-summary-reconciliation?snapshot_ids=snapshot_api_reconciliation_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 75.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["verified_sources"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["record_verified_sources"] == 24
    assert body["entries"][0]["summary_verified_sources"] == 20
    assert body["entries"][0]["mismatched_fields"] == ["verified_sources"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_confidence_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_confidence_high",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": high_confidence_records},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_confidence_low",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": low_confidence_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-confidence-drift?snapshot_ids=snapshot_api_confidence_high&snapshot_ids=snapshot_api_confidence_low"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_confidence_score"] == 85.0
    assert body["severity_score"] == 10
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["improving_snapshots"] == 0
    assert body["mixed_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert len(body["degraded_source_ids"]) == 27
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["average_confidence_score"] == 80.0
    assert body["entries"][1]["confidence_delta_from_previous"] == -10.0
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_verified_source_coverage_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_verified_partial",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/verified-source-coverage-reconciliation?snapshot_ids=snapshot_api_verified_partial"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "partial"
    assert body["average_coverage_percentage"] == 95.83
    assert body["expected_verified_source_count"] == 24
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 1
    assert body["degraded_snapshots"] == 0
    assert body["invalid_snapshots"] == 0
    assert body["missing_verified_source_ids"] == [missing_verified_source_id]
    assert body["unexpected_verified_source_ids"] == []
    assert body["entries"][0]["reconciliation_classification"] == "partial"
    assert body["entries"][0]["matched_verified_source_count"] == 23
    assert body["entries"][0]["missing_verified_source_ids"] == [missing_verified_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_availability_lag_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_lag_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": source_observation_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-availability-lag-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_lag_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_lag_seconds"] == 62.22
    assert body["severity_score"] == 4
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["improving_snapshots"] == 0
    assert body["mixed_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert body["degraded_source_ids"] == [degraded_source_id]
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["average_lag_seconds"] == 64.44
    assert body["entries"][1]["lag_delta_from_previous_seconds"] == 4.44
    assert body["entries"][1]["degraded_source_ids"] == [degraded_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_freshness_summary_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_freshness_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_observation_records": freshness_records},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-freshness-summary-reconciliation?snapshot_ids=snapshot_api_freshness_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 96.3
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["record_only_stale_source_ids"] == [stale_source_id]
    assert body["summary_only_stale_source_ids"] == []
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["record_only_stale_source_ids"] == [stale_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_freshness_seconds_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    degraded_source_id = str(baseline_snapshot["source_observation_records"][0]["source_id"])
    degraded_asset_symbol = str(baseline_snapshot["source_observation_records"][0]["asset_symbol"])
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_freshness_seconds_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        snapshot_field_overrides={
            degraded_asset_symbol: {
                "freshness_seconds": 240,
            }
        },
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-freshness-seconds-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_freshness_seconds_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_freshness_seconds"] == 122.22
    assert body["severity_score"] == 4
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["improving_snapshots"] == 0
    assert body["mixed_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert body["degraded_source_ids"] == [degraded_source_id]
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["average_freshness_seconds"] == 124.44
    assert body["entries"][1]["freshness_delta_from_previous_seconds"] == 4.44
    assert body["entries"][1]["degraded_source_ids"] == [degraded_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_freshness_status_threshold_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_freshness_threshold_degraded",
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
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-freshness-status-threshold-reconciliation?snapshot_ids=snapshot_api_freshness_threshold_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 96.3
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["threshold_mismatch_source_ids"] == [mismatched_source_id]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["aligned_records"] == 26
    assert body["entries"][0]["stale_threshold_source_count"] == 1
    assert body["entries"][0]["threshold_mismatch_source_ids"] == [mismatched_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_freshness_policy_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_policy_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_freshness_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_policy_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_freshness_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-freshness-policy-drift?snapshot_ids=snapshot_api_policy_healthy&snapshot_ids=snapshot_api_policy_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_policy_score"] == 98.15
    assert body["severity_score"] == 4
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["improving_snapshots"] == 0
    assert body["mixed_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert body["entries"][0]["drift_classification"] == "stable"
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["policy_score"] == 96.3
    assert body["entries"][1]["policy_score_delta"] == -3.7
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_stale_source_list_threshold_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
    mismatched_source_id = str(baseline_snapshot["source_observation_records"][0]["source_id"])
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_stale_threshold_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"stale_sources": [mismatched_source_id]},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/stale-source-list-threshold-reconciliation?snapshot_ids=snapshot_api_stale_threshold_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 96.3
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["threshold_mismatch_source_ids"] == [mismatched_source_id]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["aligned_sources"] == 26
    assert body["entries"][0]["threshold_mismatch_source_ids"] == [mismatched_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_freshness_evaluation_mode_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_mode_observed",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": observed_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_mode_not_evaluated",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": not_evaluated_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-freshness-evaluation-mode-drift?snapshot_ids=snapshot_api_source_mode_observed&snapshot_ids=snapshot_api_source_mode_not_evaluated"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "drifting"
    assert body["average_mode_consistency_score"] == 75.0
    assert body["severity_score"] == 50
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 1
    assert body["degraded_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert body["latest_freshness_evaluation_mode"] == "not_evaluated"
    assert body["mode_transition_count"] == 1
    assert body["entries"][1]["drift_classification"] == "drifting"
    assert body["entries"][1]["previous_freshness_evaluation_mode"] == "observed"
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_stale_asset_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_stale_assets_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-stale-asset-count-reconciliation?snapshot_ids=snapshot_api_source_stale_assets_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 50.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["total_stale_assets"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["derived_total_stale_assets"] == 2
    assert body["entries"][0]["mismatched_fields"] == ["total_stale_assets"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_average_coverage_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_coverage_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_coverage_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-average-coverage-drift?snapshot_ids=snapshot_api_source_coverage_healthy&snapshot_ids=snapshot_api_source_coverage_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_coverage_score"] == 97.5
    assert body["severity_score"] == 5
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["improving_snapshots"] == 0
    assert body["mixed_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["coverage_score_delta"] == -5.0
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_minimum_coverage_floor_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_floor_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-minimum-coverage-floor-reconciliation?snapshot_ids=snapshot_api_source_floor_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["minimum_coverage_score"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["derived_minimum_coverage_score"] == 80.0
    assert body["entries"][0]["mismatched_fields"] == ["minimum_coverage_score"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_ready_feature_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_ready_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_ready_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-ready-feature-drift?snapshot_ids=snapshot_api_source_ready_healthy&snapshot_ids=snapshot_api_source_ready_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_ready_features"] == 3.5
    assert body["severity_score"] == 1
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["ready_feature_delta"] == -1
    assert body["entries"][1]["total_missing_assets"] == 2
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_stale_feature_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_stale_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_stale_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-stale-feature-drift?snapshot_ids=snapshot_api_source_stale_healthy&snapshot_ids=snapshot_api_source_stale_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_stale_features"] == 1.0
    assert body["severity_score"] == 2
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["stale_feature_delta"] == 2
    assert body["entries"][1]["total_stale_assets"] == 3
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_critical_feature_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_critical_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_critical_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-critical-feature-drift?snapshot_ids=snapshot_api_source_critical_healthy&snapshot_ids=snapshot_api_source_critical_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_critical_feature_count"] == 0.5
    assert body["severity_score"] == 1
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["critical_feature_delta"] == 1
    assert body["entries"][1]["severity_ranking_feature_count"] == 2
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_high_severity_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_high_severity_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_high_severity_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-high-severity-drift?snapshot_ids=snapshot_api_source_high_severity_healthy&snapshot_ids=snapshot_api_source_high_severity_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_high_severity_feature_count"] == 1.0
    assert body["severity_score"] == 2
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["high_severity_feature_delta"] == 2
    assert body["entries"][1]["critical_severity_feature_count"] == 1
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_warning_feature_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_warning_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_warning_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-warning-feature-drift?snapshot_ids=snapshot_api_source_warning_healthy&snapshot_ids=snapshot_api_source_warning_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_warning_feature_count"] == 0.5
    assert body["severity_score"] == 1
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["warning_feature_delta"] == 1
    assert body["entries"][1]["high_severity_feature_count"] == 2
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_info_feature_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_info_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_info_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-info-feature-drift?snapshot_ids=snapshot_api_source_info_healthy&snapshot_ids=snapshot_api_source_info_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_info_feature_count"] == 0.5
    assert body["severity_score"] == 1
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["info_feature_delta"] == 1
    assert body["entries"][1]["warning_feature_count"] == 0
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_zero_rank_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_zero_rank_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_zero_rank_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-zero-rank-drift?snapshot_ids=snapshot_api_source_zero_rank_healthy&snapshot_ids=snapshot_api_source_zero_rank_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_zero_rank_feature_count"] == 0.5
    assert body["severity_score"] == 1
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["zero_rank_feature_delta"] == 1
    assert body["entries"][1]["info_feature_count"] == 1
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_label_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_label_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_severity_label_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-label-drift?snapshot_ids=snapshot_api_source_severity_label_healthy&snapshot_ids=snapshot_api_source_severity_label_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_severity_label_score"] == 2.5
    assert body["severity_score"] == 5
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["severity_label_score_delta"] == 5
    assert body["entries"][1]["severity_ranking_feature_count"] == 2
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_rank_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_severity_rank_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-rank-drift?snapshot_ids=snapshot_api_source_severity_rank_healthy&snapshot_ids=snapshot_api_source_severity_rank_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_severity_rank_total"] == 8.0
    assert body["severity_score"] == 16
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["severity_rank_total_delta"] == 16
    assert body["entries"][1]["severity_ranking_feature_count"] == 3
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_rank_density_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_density_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_severity_rank_density_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-rank-density-drift?snapshot_ids=snapshot_api_source_severity_rank_density_healthy&snapshot_ids=snapshot_api_source_severity_rank_density_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_severity_rank_density"] == 2.67
    assert body["severity_score"] == 5
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["severity_rank_density"] == 5.33
    assert body["entries"][1]["severity_rank_density_delta"] == 5.33
    assert body["entries"][1]["severity_ranking_feature_count"] == 3
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_rank_spread_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_spread_healthy",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": healthy_summary},
    )
    persist_snapshot_variant(
        store,
        baseline_snapshot["snapshot_id"],
        new_snapshot_id="snapshot_api_source_severity_rank_spread_degraded",
        created_at="2026-05-19T09:30:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": degraded_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-rank-spread-drift?snapshot_ids=snapshot_api_source_severity_rank_spread_healthy&snapshot_ids=snapshot_api_source_severity_rank_spread_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "degrading"
    assert body["average_severity_rank_spread"] == 5.0
    assert body["severity_score"] == 10
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["degrading_snapshots"] == 1
    assert body["entries"][1]["drift_classification"] == "degrading"
    assert body["entries"][1]["severity_rank_spread"] == 10
    assert body["entries"][1]["severity_rank_spread_delta"] == 10
    assert body["entries"][1]["severity_ranking_feature_count"] == 3
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_feature_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-feature-count-reconciliation?snapshot_ids=snapshot_api_source_severity_count_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_feature_count"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["derived_severity_ranking_feature_count"] == 1
    assert body["entries"][0]["mismatched_fields"] == ["severity_ranking_feature_count"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_warning_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_warning_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-warning-count-reconciliation?snapshot_ids=snapshot_api_source_severity_warning_count_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_warning_count"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["summary_warning_feature_count"] == 0
    assert body["entries"][0]["derived_warning_feature_count"] == 1
    assert body["entries"][0]["high_severity_feature_count"] == 2
    assert body["entries"][0]["mismatched_fields"] == ["severity_ranking_warning_count"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_info_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_info_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-info-count-reconciliation?snapshot_ids=snapshot_api_source_severity_info_count_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_info_count"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["summary_info_feature_count"] == 0
    assert body["entries"][0]["derived_info_feature_count"] == 1
    assert body["entries"][0]["warning_feature_count"] == 1
    assert body["entries"][0]["mismatched_fields"] == ["severity_ranking_info_count"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_non_actionable_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_non_actionable_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-non-actionable-count-reconciliation?snapshot_ids=snapshot_api_source_severity_non_actionable_count_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_non_actionable_count"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["summary_non_actionable_feature_count"] == 0
    assert body["entries"][0]["derived_non_actionable_feature_count"] == 1
    assert body["entries"][0]["info_feature_count"] == 1
    assert body["entries"][0]["mismatched_fields"] == [
        "severity_ranking_non_actionable_count"
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_label_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-label-consistency-reconciliation?snapshot_ids=snapshot_api_source_severity_rank_label_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_rank_label_consistency"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["checked_feature_count"] == 2
    assert body["entries"][0]["consistent_rank_label_feature_count"] == 0
    assert body["entries"][0]["inconsistent_rank_label_feature_count"] == 2
    assert body["entries"][0]["mismatched_fields"] == [
        "severity_ranking_rank_label_consistency"
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_order_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-order-continuity-reconciliation?snapshot_ids=snapshot_api_source_severity_rank_order_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_rank_order_continuity"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["checked_feature_count"] == 2
    assert body["entries"][0]["consistent_rank_order_feature_count"] == 0
    assert body["entries"][0]["reordered_feature_count"] == 2
    assert body["entries"][0]["mismatched_fields"] == [
        "severity_ranking_rank_order_continuity"
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_gap_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation?snapshot_ids=snapshot_api_source_severity_rank_gap_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_rank_gap_continuity"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["checked_gap_count"] == 2
    assert body["entries"][0]["consistent_rank_gap_count"] == 0
    assert body["entries"][0]["discontinuous_rank_gap_count"] == 2
    assert body["entries"][0]["mismatched_fields"] == [
        "severity_ranking_rank_gap_continuity"
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_rank_gap_magnitude_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation?snapshot_ids=snapshot_api_source_severity_rank_gap_magnitude_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 50.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_rank_gap_magnitude"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["checked_gap_count"] == 2
    assert body["entries"][0]["consistent_rank_gap_magnitude_count"] == 1
    assert body["entries"][0]["mismatched_rank_gap_magnitude_count"] == 1
    assert body["entries"][0]["mismatched_fields"] == [
        "severity_ranking_rank_gap_magnitude"
    ]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_severity_ranking_critical_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_severity_critical_count_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-severity-ranking-critical-count-reconciliation?snapshot_ids=snapshot_api_source_severity_critical_count_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["severity_ranking_critical_count"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["summary_critical_feature_count"] == 0
    assert body["entries"][0]["derived_critical_feature_count"] == 1
    assert body["entries"][0]["high_severity_feature_count"] == 2
    assert body["entries"][0]["mismatched_fields"] == ["severity_ranking_critical_count"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_missing_source_feature_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_missing_feature_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-missing-source-feature-count-reconciliation?snapshot_ids=snapshot_api_source_missing_feature_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 0.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["features_with_missing_sources"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["derived_features_with_missing_sources"] == 1
    assert body["entries"][0]["mismatched_fields"] == ["features_with_missing_sources"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_missing_asset_count_reconciliation_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_source_missing_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={"source_diagnostics_summary": diagnostics_summary},
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-missing-asset-count-reconciliation?snapshot_ids=snapshot_api_source_missing_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 50.0
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["mismatched_fields"] == ["total_missing_assets"]
    assert body["entries"][0]["reconciliation_classification"] == "degraded"
    assert body["entries"][0]["derived_total_missing_assets"] == 2
    assert body["entries"][0]["mismatched_fields"] == ["total_missing_assets"]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_observation_normalization_mode_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_mode_drift",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={
            "source_observation_records": per_source_records,
            "source_observation_summary": per_source_summary,
            "source_observations": per_source_observations,
        },
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-observation-normalization-mode-drift?snapshot_ids=snapshot_api_a&snapshot_ids=snapshot_api_mode_drift"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "drifting"
    assert body["average_mode_consistency_score"] == 75.0
    assert body["severity_score"] == 50
    assert body["snapshots_checked"] == 2
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 1
    assert body["degraded_snapshots"] == 0
    assert body["insufficient_data_snapshots"] == 0
    assert body["dominant_normalization_mode"] == "batch_stored_at"
    assert body["latest_normalization_mode"] == "per_source_stored_at"
    assert body["normalization_mode_counts"] == {
        "batch_stored_at": 1,
        "per_source_stored_at": 1,
    }
    assert body["mode_transition_count"] == 1
    assert body["entries"][1]["drift_classification"] == "drifting"
    assert body["entries"][1]["normalization_mode"] == "per_source_stored_at"
    assert body["entries"][1]["previous_normalization_mode"] == "batch_stored_at"
    assert body["entries"][1]["mode_consistency_score"] == 50.0
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_mapped_at_alignment_consistency_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(tmp_path, snapshot_id="snapshot_api_a")
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
        new_snapshot_id="snapshot_api_mapped_degraded",
        created_at="2026-05-19T09:29:00+00:00",
        asset_overrides={},
        extra_fields={
            "source_observation_records": source_observation_records,
            "source_observations": source_observations,
        },
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/mapped-at-alignment-consistency?snapshot_ids=snapshot_api_mapped_degraded"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] == "degraded"
    assert body["average_consistency_percentage"] == 96.3
    assert body["snapshots_checked"] == 1
    assert body["consistent_snapshots"] == 0
    assert body["partial_snapshots"] == 0
    assert body["degraded_snapshots"] == 1
    assert body["invalid_snapshots"] == 0
    assert body["batch_anchor_mismatch_source_ids"] == [degraded_source_id]
    assert body["entries"][0]["consistency_classification"] == "degraded"
    assert body["entries"][0]["aligned_records"] == 26
    assert body["entries"][0]["batch_anchor_mismatch_source_ids"] == [degraded_source_id]
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostics_contract_coverage_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_contract_coverage",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostics-contract-coverage-drift?snapshot_ids=snapshot_api_contract_coverage"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_coverage_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["missing_service_builder_names"] == []
    assert body["missing_api_route_paths"] == []
    assert body["missing_serializer_names"] == []
    assert body["entries"][0]["drift_classification"] == "stable"
    assert body["entries"][0]["coverage_percentage"] == 100.0
    assert body["endpoint_coverage_consistency"]["consistency_classification"] == "consistent"
    assert body["endpoint_coverage_consistency"]["consistency_percentage"] == 100.0
    assert body["endpoint_coverage_consistency"]["total_diagnostics_registered"] >= 40
    assert any(
        entry["diagnostic_key"] == "source_record_completeness"
        and entry["service_builder_present"] is True
        and entry["api_route_present"] is True
        and entry["serializer_present"] is True
        for entry in body["endpoint_coverage_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostic_group_coverage_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_group_coverage",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostic-group-coverage-drift?snapshot_ids=snapshot_api_group_coverage"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_coverage_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["missing_contract_groups"] == []
    assert body["missing_service_groups"] == []
    assert body["missing_api_route_groups"] == []
    assert body["missing_serializer_groups"] == []
    assert body["missing_rolling_bundle_groups"] == []
    assert body["entries"][0]["drift_classification"] == "stable"
    assert body["entries"][0]["coverage_percentage"] == 100.0
    assert (
        body["route_serializer_group_alignment_consistency"]["consistency_classification"]
        == "consistent"
    )
    assert (
        body["route_serializer_group_alignment_consistency"]["consistency_percentage"]
        == 100.0
    )
    assert (
        body["route_serializer_group_alignment_consistency"]["total_groups_registered"]
        >= 5
    )
    assert any(
        entry["diagnostic_group"] == "quality_completeness"
        and entry["contract_group_present"] is True
        and entry["service_group_present"] is True
        and entry["api_route_group_present"] is True
        and entry["serializer_group_present"] is True
        and entry["rolling_bundle_group_present"] is True
        for entry in body["route_serializer_group_alignment_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostic_surface_count_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_surface_count",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostic-surface-count-drift?snapshot_ids=snapshot_api_surface_count"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_consistency_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["mismatched_surface_names"] == []
    assert body["group_alignment_consistency_classification"] == "consistent"
    assert body["group_alignment_clean_but_count_mismatched"] is False
    assert body["entries"][0]["drift_classification"] == "stable"
    assert body["entries"][0]["consistency_percentage"] == 100.0
    assert (
        body["contract_surface_count_consistency"]["consistency_classification"]
        == "consistent"
    )
    assert body["contract_surface_count_consistency"]["consistency_percentage"] == 100.0
    assert body["contract_surface_count_consistency"]["total_surfaces_checked"] == 6
    assert (
        body["contract_surface_count_consistency"]["total_diagnostics_registered"]
        >= 40
    )
    assert any(
        entry["surface_name"] == "api_routes"
        and entry["actual_count"] == entry["expected_count"]
        and entry["consistency_classification"] == "consistent"
        for entry in body["contract_surface_count_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostic_metadata_completeness_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_metadata_completeness",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostic-metadata-completeness-drift?snapshot_ids=snapshot_api_metadata_completeness"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_completeness_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["missing_metadata_field_count"] == 0
    assert body["invalid_metadata_field_count"] == 0
    assert body["duplicate_metadata_record_count"] == 0
    assert body["conflicting_metadata_record_count"] == 0
    assert body["missing_group_diagnostic_keys"] == []
    assert body["invalid_group_diagnostic_keys"] == []
    assert body["invalid_diagnostic_slugs"] == []
    assert body["invalid_diagnostic_keys"] == []
    assert (
        body["contract_metadata_normalization_consistency"]["consistency_classification"]
        == "consistent"
    )
    assert (
        body["contract_metadata_normalization_consistency"]["completeness_percentage"]
        == 100.0
    )
    assert (
        body["contract_metadata_normalization_consistency"]["total_diagnostics_registered"]
        >= 40
    )
    assert any(
        entry["diagnostic_key"] == "source_record_completeness"
        and entry["contract_group_present"] is True
        and entry["service_builder_key_present"] is True
        and entry["api_route_key_present"] is True
        and entry["serializer_key_present"] is True
        and entry["rolling_bundle_key_present"] is True
        and entry["rolling_serializer_key_present"] is True
        for entry in body["contract_metadata_normalization_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostic_naming_contract_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_naming_contract",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostic-naming-contract-drift?snapshot_ids=snapshot_api_naming_contract"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_consistency_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["invalid_name_field_count"] == 0
    assert body["mismatched_name_field_count"] == 0
    assert body["duplicate_name_record_count"] == 0
    assert body["conflicting_name_record_count"] == 0
    assert body["invalid_diagnostic_slugs"] == []
    assert body["mismatched_diagnostic_keys"] == []
    assert (
        body["builder_serializer_route_naming_consistency"]["consistency_classification"]
        == "consistent"
    )
    assert (
        body["builder_serializer_route_naming_consistency"]["consistency_percentage"]
        == 100.0
    )
    assert (
        body["builder_serializer_route_naming_consistency"]["total_diagnostics_registered"]
        >= 40
    )
    assert any(
        entry["diagnostic_slug"] == "source-record-completeness"
        and entry["actual_diagnostic_key"] == "source_record_completeness"
        and entry["actual_service_builder_name"] == "build_source_record_completeness"
        and entry["actual_serializer_name"] == "_serialize_source_record_completeness"
        and entry["actual_api_route_path"] == "/api/v1/snapshots/backtest/source-record-completeness"
        and entry["actual_rolling_bundle_field_name"] == "source_record_completeness"
        and entry["actual_rolling_serializer_field_name"] == "source_record_completeness"
        and entry["invalid_name_fields"] == []
        and entry["mismatched_name_fields"] == []
        for entry in body["builder_serializer_route_naming_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_source_diagnostic_contract_signature_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_contract_signature",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/source-diagnostic-contract-signature-drift?snapshot_ids=snapshot_api_contract_signature"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_consistency_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["missing_signature_component_count"] == 0
    assert body["invalid_signature_component_count"] == 0
    assert body["mismatched_signature_component_count"] == 0
    assert body["duplicate_signature_record_count"] == 0
    assert body["conflicting_signature_record_count"] == 0
    assert body["missing_contract_signatures"] == []
    assert body["mismatched_service_builder_signatures"] == []
    assert (
        body["full_surface_contract_signature_consistency"]["consistency_classification"]
        == "consistent"
    )
    assert (
        body["full_surface_contract_signature_consistency"]["consistency_percentage"]
        == 100.0
    )
    assert (
        body["full_surface_contract_signature_consistency"]["total_diagnostics_registered"]
        >= 40
    )
    assert any(
        entry["diagnostic_slug"] == "source-record-completeness"
        and entry["actual_contract_signature"]
        == "source_record_completeness|quality_completeness"
        and entry["actual_service_builder_signature"]
        == "source_record_completeness|build_source_record_completeness"
        and entry["actual_serializer_signature"]
        == "source_record_completeness|_serialize_source_record_completeness"
        and entry["actual_api_route_signature"]
        == "source_record_completeness|/api/v1/snapshots/backtest/source-record-completeness"
        and entry["actual_rolling_bundle_signature"]
        == "source_record_completeness|source_record_completeness"
        and entry["actual_rolling_serializer_signature"]
        == "source_record_completeness|source_record_completeness"
        and entry["missing_signature_components"] == []
        and entry["invalid_signature_components"] == []
        and entry["mismatched_signature_components"] == []
        for entry in body["full_surface_contract_signature_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_rolling_source_diagnostic_bundle_coverage_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, baseline_snapshot = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_rolling_bundle_coverage",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get(
        "/api/v1/snapshots/backtest/rolling-source-diagnostic-bundle-coverage-drift?snapshot_ids=snapshot_api_rolling_bundle_coverage"
    )
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] == "stable"
    assert body["average_coverage_percentage"] == 100.0
    assert body["severity_score"] == 0
    assert body["contract_source"] == "explicit_runtime_contract_registry"
    assert body["snapshots_checked"] == 1
    assert body["stable_snapshots"] == 1
    assert body["drifting_snapshots"] == 0
    assert body["degraded_snapshots"] == 0
    assert body["missing_dedicated_service_builder_names"] == []
    assert body["missing_dedicated_api_route_paths"] == []
    assert body["missing_dedicated_serializer_names"] == []
    assert body["missing_rolling_bundle_field_names"] == []
    assert body["missing_rolling_serializer_field_names"] == []
    assert body["entries"][0]["drift_classification"] == "stable"
    assert body["entries"][0]["coverage_percentage"] == 100.0
    assert (
        body["dedicated_rolling_diagnostic_consistency"]["consistency_classification"]
        == "consistent"
    )
    assert body["dedicated_rolling_diagnostic_consistency"]["consistency_percentage"] == 100.0
    assert (
        body["dedicated_rolling_diagnostic_consistency"]["total_diagnostics_registered"]
        >= 40
    )
    assert any(
        entry["diagnostic_key"] == "source_record_completeness"
        and entry["dedicated_service_builder_present"] is True
        and entry["dedicated_api_route_present"] is True
        and entry["dedicated_serializer_present"] is True
        and entry["rolling_bundle_present"] is True
        and entry["rolling_serializer_present"] is True
        for entry in body["dedicated_rolling_diagnostic_consistency"]["entries"]
    )
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"

def test_snapshot_source_diagnostic_contract_field_set_drift_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, _ = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_field_set_drift",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/source-diagnostic-contract-field-set-drift")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["drift_classification"] in ("stable", "drifting", "degraded")
    assert 0.0 <= body["consistency_percentage"] <= 100.0
    assert body["total_diagnostics_registered"] >= 49
    assert isinstance(body["entries"], list)
    assert len(body["entries"]) >= 49
    assert isinstance(body["standard_field_set"], list)
    assert len(body["standard_field_set"]) >= 1
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


def test_snapshot_full_surface_response_field_set_consistency_endpoint_returns_paper_safe_payload(
    tmp_path,
    monkeypatch,
) -> None:
    store, _ = persist_snapshot_fixture(
        tmp_path,
        snapshot_id="snapshot_api_full_surface_consistency",
    )
    monkeypatch.setattr(snapshot_replay, "build_snapshot_replay_store", lambda: store)

    response = client.get("/api/v1/snapshots/backtest/full-surface-response-field-set-consistency")
    body = response.json()

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert body["consistency_classification"] in ("consistent", "partial", "degraded")
    assert 0.0 <= body["consistency_percentage"] <= 100.0
    assert body["total_diagnostics_registered"] >= 49
    assert isinstance(body["entries"], list)
    assert len(body["entries"]) >= 49
    assert isinstance(body["standard_field_set"], list)
    assert len(body["standard_field_set"]) >= 1
    assert body["paper_safe"] is True
    assert body["network_calls"] is False
    assert body["execution_side_effects"] == "NO_EXECUTION"


__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
