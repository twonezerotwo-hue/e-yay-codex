from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from app.api import snapshot_replay as snapshot_replay_compat
from app.api.snapshot_replay_source_serializers import (
    _serialize_fallback_usage_recurrence,
    _serialize_no_execution_guardrail_consistency,
    _serialize_paper_safe_source_flag_consistency,
    _serialize_provider_adapter_contract_consistency,
    _serialize_rolling_source_diagnostic_bundle_coverage_drift,
    _serialize_source_diagnostic_group_coverage_drift,
    _serialize_source_diagnostic_contract_signature_drift,
    _serialize_source_diagnostic_naming_contract_drift,
    _serialize_source_diagnostic_metadata_completeness_drift,
    _serialize_source_diagnostic_surface_count_drift,
    _serialize_source_diagnostics_contract_coverage_drift,
    _serialize_source_registry_binding_drift,
    _serialize_source_verification_drift,
    _serialize_source_diagnostic_contract_field_set_drift,
    _serialize_full_surface_response_field_set_consistency,
)
from app.core.errors import AppError

router = APIRouter(tags=["snapshots"])


def build_snapshot_replay_service():
    return snapshot_replay_compat.build_snapshot_replay_service()

@router.get("/backtest/no-execution-guardrail-consistency")
def snapshot_backtest_no_execution_guardrail_consistency(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        guardrail_consistency = build_snapshot_replay_service().build_no_execution_guardrail_consistency(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_NO_EXECUTION_GUARDRAIL_INVALID_REQUEST",
            message="Snapshot NO_EXECUTION guardrail consistency request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if guardrail_consistency.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_NO_EXECUTION_GUARDRAIL_EMPTY",
            message="No saved paper snapshots were found for NO_EXECUTION guardrail consistency analysis.",
            details={
                "total_snapshots_requested": guardrail_consistency.total_snapshots_requested,
                "failures": list(guardrail_consistency.failures),
            },
            status_code=404,
        )

    return _serialize_no_execution_guardrail_consistency(guardrail_consistency)

@router.get("/backtest/fallback-usage-recurrence")
def snapshot_backtest_fallback_usage_recurrence(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        fallback_usage_recurrence = build_snapshot_replay_service().build_fallback_usage_recurrence(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_FALLBACK_USAGE_INVALID_REQUEST",
            message="Snapshot fallback usage recurrence request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if fallback_usage_recurrence.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_FALLBACK_USAGE_EMPTY",
            message="No saved paper snapshots were found for fallback usage recurrence analysis.",
            details={
                "total_snapshots_requested": fallback_usage_recurrence.total_snapshots_requested,
                "failures": list(fallback_usage_recurrence.failures),
            },
            status_code=404,
        )

    return _serialize_fallback_usage_recurrence(fallback_usage_recurrence)

@router.get("/backtest/source-registry-binding-drift")
def snapshot_backtest_source_registry_binding_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_registry_binding_drift = (
            build_snapshot_replay_service().build_source_registry_binding_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_REGISTRY_BINDING_DRIFT_INVALID_REQUEST",
            message="Snapshot source registry binding drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_registry_binding_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_REGISTRY_BINDING_DRIFT_EMPTY",
            message="No saved paper snapshots were found for source registry binding drift analysis.",
            details={
                "total_snapshots_requested": source_registry_binding_drift.total_snapshots_requested,
                "failures": list(source_registry_binding_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_registry_binding_drift(source_registry_binding_drift)

@router.get("/backtest/source-verification-drift")
def snapshot_backtest_source_verification_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_verification_drift = (
            build_snapshot_replay_service().build_source_verification_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_VERIFICATION_DRIFT_INVALID_REQUEST",
            message="Snapshot source verification drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_verification_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_VERIFICATION_DRIFT_EMPTY",
            message="No saved paper snapshots were found for source verification drift analysis.",
            details={
                "total_snapshots_requested": source_verification_drift.total_snapshots_requested,
                "failures": list(source_verification_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_verification_drift(source_verification_drift)

@router.get("/backtest/paper-safe-source-flag-consistency")
def snapshot_backtest_paper_safe_source_flag_consistency(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        paper_safe_source_flag_consistency = (
            build_snapshot_replay_service().build_paper_safe_source_flag_consistency(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_PAPER_SAFE_SOURCE_FLAG_CONSISTENCY_INVALID_REQUEST",
            message="Snapshot paper-safe source flag consistency request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if paper_safe_source_flag_consistency.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_PAPER_SAFE_SOURCE_FLAG_CONSISTENCY_EMPTY",
            message="No saved paper snapshots were found for paper-safe source flag consistency analysis.",
            details={
                "total_snapshots_requested": paper_safe_source_flag_consistency.total_snapshots_requested,
                "failures": list(paper_safe_source_flag_consistency.failures),
            },
            status_code=404,
        )

    return _serialize_paper_safe_source_flag_consistency(paper_safe_source_flag_consistency)

@router.get("/backtest/provider-adapter-contract-consistency")
def snapshot_backtest_provider_adapter_contract_consistency(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        provider_adapter_contract_consistency = (
            build_snapshot_replay_service().build_provider_adapter_contract_consistency(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_PROVIDER_ADAPTER_CONTRACT_CONSISTENCY_INVALID_REQUEST",
            message="Snapshot provider adapter contract consistency request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if provider_adapter_contract_consistency.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_PROVIDER_ADAPTER_CONTRACT_CONSISTENCY_EMPTY",
            message="No saved paper snapshots were found for provider adapter contract consistency analysis.",
            details={
                "total_snapshots_requested": provider_adapter_contract_consistency.total_snapshots_requested,
                "failures": list(provider_adapter_contract_consistency.failures),
            },
            status_code=404,
        )

    return _serialize_provider_adapter_contract_consistency(provider_adapter_contract_consistency)

@router.get("/backtest/source-diagnostics-contract-coverage-drift")
def snapshot_backtest_source_diagnostics_contract_coverage_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        contract_coverage_drift = (
            build_snapshot_replay_service().build_source_diagnostics_contract_coverage_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_CONTRACT_COVERAGE_INVALID_REQUEST",
            message="Snapshot source diagnostics contract coverage drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if contract_coverage_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_CONTRACT_COVERAGE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics contract coverage drift analysis.",
            details={
                "total_snapshots_requested": contract_coverage_drift.total_snapshots_requested,
                "failures": list(contract_coverage_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_contract_coverage_drift(
        contract_coverage_drift
    )

@router.get("/backtest/source-diagnostic-group-coverage-drift")
def snapshot_backtest_source_diagnostic_group_coverage_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        group_coverage_drift = (
            build_snapshot_replay_service().build_source_diagnostic_group_coverage_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_GROUP_COVERAGE_INVALID_REQUEST",
            message="Snapshot source diagnostic group coverage drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if group_coverage_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_GROUP_COVERAGE_EMPTY",
            message="No saved paper snapshots were found for source diagnostic group coverage drift analysis.",
            details={
                "total_snapshots_requested": group_coverage_drift.total_snapshots_requested,
                "failures": list(group_coverage_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostic_group_coverage_drift(group_coverage_drift)

@router.get("/backtest/source-diagnostic-surface-count-drift")
def snapshot_backtest_source_diagnostic_surface_count_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        surface_count_drift = (
            build_snapshot_replay_service().build_source_diagnostic_surface_count_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_SURFACE_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostic surface count drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if surface_count_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_SURFACE_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostic surface count drift analysis.",
            details={
                "total_snapshots_requested": surface_count_drift.total_snapshots_requested,
                "failures": list(surface_count_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostic_surface_count_drift(surface_count_drift)

@router.get("/backtest/source-diagnostic-metadata-completeness-drift")
def snapshot_backtest_source_diagnostic_metadata_completeness_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        metadata_completeness_drift = (
            build_snapshot_replay_service().build_source_diagnostic_metadata_completeness_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_METADATA_COMPLETENESS_INVALID_REQUEST",
            message="Snapshot source diagnostic metadata completeness drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if metadata_completeness_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_METADATA_COMPLETENESS_EMPTY",
            message="No saved paper snapshots were found for source diagnostic metadata completeness drift analysis.",
            details={
                "total_snapshots_requested": metadata_completeness_drift.total_snapshots_requested,
                "failures": list(metadata_completeness_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostic_metadata_completeness_drift(
        metadata_completeness_drift
    )

@router.get("/backtest/source-diagnostic-naming-contract-drift")
def snapshot_backtest_source_diagnostic_naming_contract_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        naming_contract_drift = (
            build_snapshot_replay_service().build_source_diagnostic_naming_contract_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_NAMING_CONTRACT_INVALID_REQUEST",
            message="Snapshot source diagnostic naming contract drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if naming_contract_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_NAMING_CONTRACT_EMPTY",
            message="No saved paper snapshots were found for source diagnostic naming contract drift analysis.",
            details={
                "total_snapshots_requested": naming_contract_drift.total_snapshots_requested,
                "failures": list(naming_contract_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostic_naming_contract_drift(
        naming_contract_drift
    )

@router.get("/backtest/source-diagnostic-contract-signature-drift")
def snapshot_backtest_source_diagnostic_contract_signature_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        contract_signature_drift = (
            build_snapshot_replay_service().build_source_diagnostic_contract_signature_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_CONTRACT_SIGNATURE_INVALID_REQUEST",
            message="Snapshot source diagnostic contract signature drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if contract_signature_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTIC_CONTRACT_SIGNATURE_EMPTY",
            message="No saved paper snapshots were found for source diagnostic contract signature drift analysis.",
            details={
                "total_snapshots_requested": contract_signature_drift.total_snapshots_requested,
                "failures": list(contract_signature_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostic_contract_signature_drift(
        contract_signature_drift
    )

@router.get("/backtest/rolling-source-diagnostic-bundle-coverage-drift")
def snapshot_backtest_rolling_source_diagnostic_bundle_coverage_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        rolling_bundle_coverage_drift = (
            build_snapshot_replay_service().build_rolling_source_diagnostic_bundle_coverage_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_ROLLING_SOURCE_DIAGNOSTIC_BUNDLE_COVERAGE_INVALID_REQUEST",
            message="Snapshot rolling source diagnostic bundle coverage drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_bundle_coverage_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_ROLLING_SOURCE_DIAGNOSTIC_BUNDLE_COVERAGE_EMPTY",
            message="No saved paper snapshots were found for rolling source diagnostic bundle coverage drift analysis.",
            details={
                "total_snapshots_requested": rolling_bundle_coverage_drift.total_snapshots_requested,
                "failures": list(rolling_bundle_coverage_drift.failures),
            },
            status_code=404,
        )

    return _serialize_rolling_source_diagnostic_bundle_coverage_drift(
        rolling_bundle_coverage_drift
    )

@router.get("/backtest/source-diagnostic-contract-field-set-drift")
def snapshot_backtest_source_diagnostic_contract_field_set_drift() -> dict[str, object]:
    field_set_drift = (
        build_snapshot_replay_service().build_source_diagnostic_contract_field_set_drift()
    )
    return _serialize_source_diagnostic_contract_field_set_drift(field_set_drift)


@router.get("/backtest/full-surface-response-field-set-consistency")
def snapshot_backtest_full_surface_response_field_set_consistency() -> dict[str, object]:
    consistency = (
        build_snapshot_replay_service().build_full_surface_response_field_set_consistency()
    )
    return _serialize_full_surface_response_field_set_consistency(consistency)


__all__ = ["router"]
