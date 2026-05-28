from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api import ceo_report
from app.domain import MarketSnapshot
from app.services import DataQualityDecision
from app.services import DataQualityScoreResult
from app.services import PersistedMarketSnapshot
from app.services import ProviderIngestionResult
from app.main import app


client = TestClient(app)


def test_ceo_report_demo_endpoint_returns_end_to_end_payload() -> None:
    response = client.get("/api/v1/ceo-report/demo")
    body = response.json()

    assert response.status_code == 200
    assert body["app_name"] == "E-yAy BrainChain"
    assert body["environment"] == "development"
    assert body["data_mode"] == "simulation"
    assert body["pipeline_summary"] == {
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
    assert body["risk_engine_result"]["risk_action"] == "HOLD"
    assert body["risk_engine_result"]["kill_switch_active"] is False
    assert body["report"]["risk_action"] == "HOLD"
    assert body["report"]["execution_status"] == "OFF / NO_EXECUTION"
    assert body["snapshot_persistence"] == {
        "enabled": False,
        "persisted": False,
        "snapshot_id": None,
        "store_path": None,
        "failure": None,
    }
    assert body["audit_source_payload"]["simulation_only"] is True
    assert body["audit_source_payload"]["source_registry_version"] == "1.0"
    assert body["audit_source_payload"]["provider_adapter"] == {
        "contract": "verified_provider_adapter_v1",
        "normalization_mode": "batch_stored_at",
        "total_bound_sources": 27,
        "verified_sources": 24,
        "simulation_only_sources": 3,
        "paper_safe_sources": 27,
    }
    assert body["audit_source_payload"]["source_binding"]["coverage"]["uncovered_assets"] == []
    assert 5 <= len(body["report"]["short_report_sentences"]) <= 10


def test_ceo_report_demo_endpoint_is_deterministic() -> None:
    first_response = client.get("/api/v1/ceo-report/demo")
    second_response = client.get("/api/v1/ceo-report/demo")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()


def test_ceo_report_demo_endpoint_includes_request_id_header_and_trigger_catalog() -> None:
    response = client.get("/api/v1/ceo-report/demo")
    body = response.json()
    trigger_codes = [trigger["trigger_code"] for trigger in body["trigger_results"]]

    assert response.headers.get("X-Request-ID")
    assert trigger_codes == [
        "RED_ENERGY_SHOCK",
        "BTC_RISK_OFF_WARNING",
        "BTC_RISK_ON_CANDIDATE",
        "GOLD_HEDGE_BREAKOUT",
        "SILVER_STRATEGIC_METALS_REGIME",
        "SILVER_MOMENTUM_ACCELERATION",
        "SILVER_EXHAUSTION_WATCH",
        "HYG_JNK_BREAKDOWN_WATCH",
    ]
    assert body["report"]["key_triggers"] == []
    assert body["audit_source_payload"]["source_observation_map"]["approved_btcusd_feed"] == "2026-05-19T09:28:00+00:00"
    assert body["audit_source_payload"]["source_observation_map"]["approved_xagusdk_reference_feed"] == "2026-05-19T09:28:00+00:00"
    assert body["audit_source_payload"]["missing_source_ids"] == []
    assert body["audit_source_payload"]["stale_source_ids"] == []
    assert body["audit_source_payload"]["source_freshness_summary"] == {
        "total_sources": 27,
        "total_active_sources": 27,
        "fresh_sources": 27,
        "stale_sources": 0,
        "sources_missing_timestamps": 0,
        "not_evaluated_sources": 0,
        "evaluation_mode": "observed",
    }
    assert body["audit_source_payload"]["source_diagnostics_summary"] == {
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
    assert body["audit_source_payload"]["audit_record"] == {
        "timestamp_utc": "2026-05-19T09:28:00+00:00",
        "event_type": "ceo_report_demo_generated",
        "message": "Simulation-only CEO report demo payload generated.",
        "details_json": {
            "data_mode": "simulation",
            "risk_action": "HOLD",
            "total_assets_processed": 27,
            "successful_snapshots": 27,
            "source_registry_version": "1.0",
        },
        "request_id": None,
    }


def test_ceo_report_demo_endpoint_returns_controlled_503_when_pipeline_is_incomplete(monkeypatch) -> None:
    snapshot = MarketSnapshot(
        asset_symbol="BRENT",
        value=82.35,
        unit="usd_per_barrel",
        source_name="mock_energy_provider",
        source_tier="primary",
        observed_at=datetime(2026, 5, 19, 9, 1, 0, tzinfo=UTC),
        available_at=datetime(2026, 5, 19, 9, 2, 0, tzinfo=UTC),
        stored_at=datetime(2026, 5, 19, 9, 3, 0, tzinfo=UTC),
        data_quality_score=100.0,
    )

    dqs_result = DataQualityScoreResult(
        total_score=100.0,
        decision=DataQualityDecision.PASS,
        component_scores={
            "freshness_score": 100.0,
            "source_tier_score": 100.0,
            "cross_provider_agreement_score": 100.0,
            "completeness_score": 100.0,
            "timestamp_integrity_score": 100.0,
            "anomaly_consistency_score": 100.0,
        },
    )

    def mock_run(self) -> ProviderIngestionResult:
        return ProviderIngestionResult(
            total_assets_processed=27,
            successful_snapshots=26,
            failed_snapshots=1,
            dqs_decision_counts={
                "PASS": 26,
                "DEGRADED_PASS": 0,
                "LIMITED_ANALYSIS_ONLY": 0,
                "FAIL_NO_DECISION": 0,
            },
            persisted_snapshots=(PersistedMarketSnapshot(snapshot=snapshot, dqs_result=dqs_result),),
            provider_payloads=(),
            source_observation_persistence_payload={
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
            },
            failed_assets=("BTCUSD",),
        )

    monkeypatch.setattr(ceo_report.ProviderIngestionService, "run", mock_run)

    response = client.get("/api/v1/ceo-report/demo")
    body = response.json()

    assert response.status_code == 503
    assert body == {
        "error_code": "CEO_REPORT_DEMO_INCOMPLETE",
        "message": "CEO report demo pipeline is incomplete and remains simulation-only unavailable.",
        "details": {
            "total_assets_processed": 27,
            "successful_snapshots": 26,
            "failed_snapshots": 1,
            "failed_assets": ["BTCUSD"],
        },
        "request_id": body["request_id"],
    }
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_ceo_report_demo_endpoint_wraps_unexpected_pipeline_failure(monkeypatch) -> None:
    def mock_run(self) -> ProviderIngestionResult:
        raise RuntimeError("mock pipeline crash")

    monkeypatch.setattr(ceo_report.ProviderIngestionService, "run", mock_run)

    response = client.get("/api/v1/ceo-report/demo")
    body = response.json()

    assert response.status_code == 503
    assert body == {
        "error_code": "CEO_REPORT_DEMO_PIPELINE_FAILED",
        "message": "CEO report demo pipeline failed before report generation.",
        "details": {"reason": "mock pipeline crash"},
        "request_id": body["request_id"],
    }
    assert response.headers.get("X-Request-ID") == body["request_id"]


def test_ceo_report_demo_endpoint_can_persist_snapshot_metadata_when_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        ceo_report,
        "build_demo_snapshot_store",
        lambda: ceo_report.SnapshotStore(tmp_path / "ceo_report_demo.jsonl"),
    )

    response = client.get("/api/v1/ceo-report/demo?persist_snapshot=true")
    body = response.json()

    assert response.status_code == 200
    assert body["snapshot_persistence"]["enabled"] is True
    assert body["snapshot_persistence"]["persisted"] is True
    assert body["snapshot_persistence"]["snapshot_id"] is not None
    assert body["snapshot_persistence"]["snapshot_metadata"]["mode"] == "SIMULATION"
    assert body["snapshot_persistence"]["snapshot_metadata"]["decision_permission"] == "NO_EXECUTION"
    assert body["snapshot_persistence"]["snapshot_metadata"]["execution_mode"] == "NO_EXECUTION"
    assert body["snapshot_persistence"]["snapshot_metadata"]["source_registry_version"] == "1.0"
    assert body["snapshot_persistence"]["snapshot_metadata"]["feature_registry_version"] == "1.0"
    assert body["snapshot_persistence"]["snapshot_metadata"]["missing_sources"] == []
    assert body["snapshot_persistence"]["snapshot_metadata"]["stale_sources"] == []
    assert body["snapshot_persistence"]["snapshot_metadata"]["report_type"] == "ceo_report_demo_input_snapshot"
    assert len(body["snapshot_persistence"]["snapshot_metadata"]["snapshots"]) == 27
    assert body["snapshot_persistence"]["snapshot_metadata"]["audit_source_payload"] == {
        "source_registry_version": "1.0",
        "provider_adapter": {
            "contract": "verified_provider_adapter_v1",
            "normalization_mode": "batch_stored_at",
            "total_bound_sources": 27,
            "verified_sources": 24,
            "simulation_only_sources": 3,
            "paper_safe_sources": 27,
        },
        "source_observation_map": body["audit_source_payload"]["source_observation_map"],
        "missing_source_ids": [],
        "stale_source_ids": [],
        "audit_record": body["audit_source_payload"]["audit_record"],
    }


def test_ceo_report_demo_endpoint_remains_safe_if_snapshot_persistence_fails(monkeypatch) -> None:
    class FailingSnapshotStore:
        storage_path = "memory://disabled"

        def save_snapshot(self, snapshot_payload):
            raise RuntimeError("snapshot store unavailable")

    monkeypatch.setattr(
        ceo_report,
        "build_demo_snapshot_store",
        lambda: FailingSnapshotStore(),
    )

    response = client.get("/api/v1/ceo-report/demo?persist_snapshot=true")
    body = response.json()

    assert response.status_code == 200
    assert body["snapshot_persistence"] == {
        "enabled": True,
        "persisted": False,
        "snapshot_id": None,
        "store_path": "memory://disabled",
        "failure": {
            "error_code": "CEO_REPORT_SNAPSHOT_PERSIST_FAILED",
            "message": "Snapshot persistence failed for the CEO report demo endpoint.",
            "details": {"reason": "snapshot store unavailable"},
        },
    }

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
