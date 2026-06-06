from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi import Query

from app.core.config import Settings
from app.core.config import get_settings
from app.core.errors import AppError
from app.providers import build_provider_source_bindings
from app.providers import MockMarketProvider
from app.providers import SourceRegistryBoundProviderAdapter
from app.services import CEOReportService
from app.services import MarketSnapshotService
from app.services import ProviderIngestionResult
from app.services import ProviderIngestionService
from app.services import RiskEngine
from app.services import SnapshotRiskInput
from app.services import TriggerEngine
from app.storage import SnapshotStore
from app.storage import build_local_snapshot_store


router = APIRouter(prefix="/ceo-report", tags=["ceo-report"])
REPO_ROOT = Path(__file__).resolve().parents[3]


class DemoSnapshotSession:
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


def _ensure_repo_root_on_path() -> None:
    repo_root_str = str(REPO_ROOT)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def _validate_demo_pipeline_result(ingestion_result: ProviderIngestionResult) -> None:
    if ingestion_result.total_assets_processed == 0 or not ingestion_result.persisted_snapshots:
        raise AppError(
            error_code="CEO_REPORT_DEMO_EMPTY",
            message="CEO report demo pipeline did not produce any snapshots.",
            details={
                "total_assets_processed": ingestion_result.total_assets_processed,
                "successful_snapshots": ingestion_result.successful_snapshots,
                "failed_snapshots": ingestion_result.failed_snapshots,
            },
            status_code=503,
        )

    if (
        ingestion_result.failed_snapshots > 0
        or ingestion_result.successful_snapshots != ingestion_result.total_assets_processed
    ):
        raise AppError(
            error_code="CEO_REPORT_DEMO_INCOMPLETE",
            message="CEO report demo pipeline is incomplete and remains simulation-only unavailable.",
            details={
                "total_assets_processed": ingestion_result.total_assets_processed,
                "successful_snapshots": ingestion_result.successful_snapshots,
                "failed_snapshots": ingestion_result.failed_snapshots,
                "failed_assets": list(ingestion_result.failed_assets),
            },
            status_code=503,
        )


def _build_audit_source_payload(
    ingestion_result: ProviderIngestionResult,
    *,
    source_registry: dict[str, object],
    risk_action: str,
) -> dict[str, object]:
    _ensure_repo_root_on_path()

    from audit.logger import create_audit_record
    from registry import build_feature_source_diagnostics
    from registry import build_report_source_binding
    from registry import build_source_freshness_diagnostics
    from reports.generator import load_feature_registry

    feature_registry = load_feature_registry()
    source_observation_payload = ingestion_result.source_observation_persistence_payload
    source_observations = source_observation_payload["source_observations"]
    observation_summary = source_observation_payload["summary"]
    records = source_observation_payload["records"]
    evaluation_time = max(
        persisted.snapshot.stored_at
        for persisted in ingestion_result.persisted_snapshots
    )

    source_binding = build_report_source_binding(source_registry)
    source_freshness = build_source_freshness_diagnostics(
        source_registry,
        source_observations=source_observations,
        as_of_utc=evaluation_time,
    )
    source_diagnostics = build_feature_source_diagnostics(
        feature_registry,
        source_registry,
        source_observations=source_observations,
        as_of_utc=evaluation_time,
    )

    if source_binding["coverage"]["uncovered_assets"]:
        raise AppError(
            error_code="CEO_REPORT_SOURCE_BINDING_INCOMPLETE",
            message="CEO report demo source binding is incomplete.",
            details={"uncovered_assets": source_binding["coverage"]["uncovered_assets"]},
            status_code=503,
        )

    if source_diagnostics["summary"]["features_with_missing_sources"] > 0:
        raise AppError(
            error_code="CEO_REPORT_SOURCE_DIAGNOSTICS_INCOMPLETE",
            message="CEO report demo source diagnostics are missing required sources.",
            details={
                "features_with_missing_sources": source_diagnostics["summary"]["features_with_missing_sources"],
                "total_missing_assets": source_diagnostics["summary"]["total_missing_assets"],
            },
            status_code=503,
        )

    audit_record = create_audit_record(
        event_type="ceo_report_demo_generated",
        message="Simulation-only CEO report demo payload generated.",
        details_json={
            "data_mode": "simulation",
            "risk_action": risk_action,
            "total_assets_processed": ingestion_result.total_assets_processed,
            "successful_snapshots": ingestion_result.successful_snapshots,
            "source_registry_version": source_registry["version"],
        },
        request_id=None,
        created_at=evaluation_time,
    )

    return {
        "simulation_only": True,
        "source_registry_version": source_registry["version"],
        "provider_adapter": observation_summary,
        "source_observation_map": source_observations,
        "source_observation_persistence_payload": {
            "summary": observation_summary,
            "records": records,
            "source_observations": source_observations,
        },
        "missing_source_ids": sorted(
            source["source_id"]
            for source in source_freshness["sources"]
            if source["freshness_status"] == "missing_timestamp"
        ),
        "stale_source_ids": sorted(
            source["source_id"]
            for source in source_freshness["sources"]
            if source["freshness_status"] == "stale"
        ),
        "source_binding": source_binding,
        "source_freshness_summary": source_freshness["summary"],
        "source_diagnostics_summary": source_diagnostics["summary"],
        "audit_record": audit_record,
    }


def _build_snapshot_persistence_metadata(
    *,
    source_registry: dict[str, object],
    feature_registry: dict[str, object],
    audit_source_payload: dict[str, object],
) -> dict[str, object]:
    return {
        "source_registry_version": source_registry["version"],
        "feature_registry_version": feature_registry["version"],
        "missing_sources": list(audit_source_payload["missing_source_ids"]),
        "stale_sources": list(audit_source_payload["stale_source_ids"]),
        "report_type": "ceo_report_demo_input_snapshot",
        "mode": "SIMULATION",
        "execution_mode": "NO_EXECUTION",
        "source_binding_summary": audit_source_payload["source_binding"]["coverage"],
        "source_freshness_summary": audit_source_payload["source_freshness_summary"],
        "source_diagnostics_summary": audit_source_payload["source_diagnostics_summary"],
        "audit_source_payload": {
            "source_registry_version": audit_source_payload["source_registry_version"],
            "provider_adapter": audit_source_payload["provider_adapter"],
            "source_observation_map": audit_source_payload["source_observation_map"],
            "missing_source_ids": audit_source_payload["missing_source_ids"],
            "stale_source_ids": audit_source_payload["stale_source_ids"],
            "audit_record": audit_source_payload["audit_record"],
        },
    }


def build_demo_snapshot_store() -> SnapshotStore:
    return build_local_snapshot_store()


def build_demo_ceo_report_payload(
    settings: Settings,
    *,
    persist_snapshot: bool = False,
) -> dict[str, object]:
    _ensure_repo_root_on_path()

    from registry import build_source_registry_entries
    from registry import load_source_registry
    from reports.generator import load_feature_registry

    session = DemoSnapshotSession()
    snapshot_service = MarketSnapshotService(session)
    source_registry = load_source_registry()
    feature_registry = load_feature_registry()
    source_registry_entries = build_source_registry_entries(source_registry)
    provider = SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        build_provider_source_bindings(source_registry_entries),
    )
    ingestion_service = ProviderIngestionService(snapshot_service, provider)

    try:
        ingestion_result = ingestion_service.run()
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            error_code="CEO_REPORT_DEMO_PIPELINE_FAILED",
            message="CEO report demo pipeline failed before report generation.",
            details={"reason": str(exc) or exc.__class__.__name__},
            status_code=503,
        ) from exc

    _validate_demo_pipeline_result(ingestion_result)

    snapshots = tuple(persisted.snapshot for persisted in ingestion_result.persisted_snapshots)
    trigger_results = TriggerEngine().evaluate(snapshots)
    snapshot_risk_inputs = tuple(
        SnapshotRiskInput(
            asset_symbol=persisted.snapshot.asset_symbol,
            dqs_result=persisted.dqs_result,
        )
        for persisted in ingestion_result.persisted_snapshots
    )
    risk_result = RiskEngine().evaluate(snapshot_risk_inputs, trigger_results)
    ceo_report = CEOReportService().generate(trigger_results, risk_result)
    audit_source_payload = _build_audit_source_payload(
        ingestion_result,
        risk_action=risk_result.risk_action.value,
        source_registry=source_registry,
    )
    snapshot_persistence = {
        "enabled": persist_snapshot,
        "persisted": False,
        "snapshot_id": None,
        "store_path": None,
        "failure": None,
    }

    if persist_snapshot:
        snapshot_store = build_demo_snapshot_store()
        snapshot_persistence["store_path"] = str(snapshot_store.storage_path)
        try:
            stored_snapshot_metadata = ingestion_service.persist_ingestion_result(
                ingestion_result,
                snapshot_store=snapshot_store,
                snapshot_metadata=_build_snapshot_persistence_metadata(
                    source_registry=source_registry,
                    feature_registry=feature_registry,
                    audit_source_payload=audit_source_payload,
                ),
            )
            snapshot_persistence["persisted"] = True
            snapshot_persistence["snapshot_id"] = stored_snapshot_metadata["snapshot_id"]
            snapshot_persistence["snapshot_metadata"] = stored_snapshot_metadata
        except Exception as exc:
            snapshot_persistence["failure"] = {
                "error_code": "CEO_REPORT_SNAPSHOT_PERSIST_FAILED",
                "message": "Snapshot persistence failed for the CEO report demo endpoint.",
                "details": {"reason": str(exc) or exc.__class__.__name__},
            }

    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "data_mode": "simulation",
        "pipeline_summary": {
            "total_assets_processed": ingestion_result.total_assets_processed,
            "successful_snapshots": ingestion_result.successful_snapshots,
            "failed_snapshots": ingestion_result.failed_snapshots,
            "dqs_decision_counts": ingestion_result.dqs_decision_counts,
            "failed_assets": list(ingestion_result.failed_assets),
        },
        "trigger_results": [
            {
                "trigger_code": trigger.trigger_code,
                "severity": trigger.severity.value,
                "asset_symbol": trigger.asset_symbol,
                "is_triggered": trigger.is_triggered,
                "confirmation_status": trigger.confirmation_status.value,
                "message": trigger.message,
            }
            for trigger in trigger_results
        ],
        "risk_engine_result": {
            "risk_action": risk_result.risk_action.value,
            "reason_codes": list(risk_result.reason_codes),
            "summary": risk_result.summary,
            "kill_switch_active": risk_result.kill_switch_active,
        },
        "report": {
            "report_title": ceo_report.report_title,
            "regime_summary": ceo_report.regime_summary,
            "key_triggers": list(ceo_report.key_triggers),
            "risk_action": ceo_report.risk_action.value,
            "owner_action": ceo_report.owner_action,
            "execution_status": ceo_report.execution_status,
            "short_report_sentences": list(ceo_report.short_report_sentences),
        },
        "snapshot_persistence": snapshot_persistence,
        "audit_source_payload": audit_source_payload,
    }


@router.get("/demo")
def ceo_report_demo(
    persist_snapshot: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return build_demo_ceo_report_payload(settings, persist_snapshot=persist_snapshot)

__all__ = [name for name in globals() if not name.startswith('_')]
