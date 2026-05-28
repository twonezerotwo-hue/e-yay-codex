from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from app.api import snapshot_replay as snapshot_replay_compat
from app.api.snapshot_replay_source_serializers import (
    _serialize_mapped_at_alignment_consistency,
    _serialize_source_diagnostics_freshness_evaluation_mode_drift,
    _serialize_source_freshness_decay_timeline,
    _serialize_source_freshness_policy_drift,
    _serialize_source_freshness_status_threshold_reconciliation,
    _serialize_source_freshness_summary_reconciliation,
    _serialize_source_observation_availability_lag_drift,
    _serialize_source_observation_cadence_drift,
    _serialize_source_observation_freshness_seconds_drift,
    _serialize_source_observation_normalization_mode_drift,
    _serialize_source_observation_timestamp_integrity_drift,
    _serialize_stale_source_list_threshold_reconciliation,
)
from app.core.errors import AppError

router = APIRouter(tags=["snapshots"])


def build_snapshot_replay_service():
    return snapshot_replay_compat.build_snapshot_replay_service()

@router.get("/backtest/source-freshness-decay-timeline")
def snapshot_backtest_source_freshness_decay_timeline(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        rolling_diagnostics = build_snapshot_replay_service().build_rolling_backtest_diagnostics(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_DECAY_INVALID_REQUEST",
            message="Snapshot source freshness decay timeline request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_DECAY_EMPTY",
            message="No replayable paper snapshots were found for source freshness decay analysis.",
            details={
                "total_snapshots_requested": rolling_diagnostics.total_snapshots_requested,
                "failed_replays": rolling_diagnostics.failed_replays,
                "failures": list(rolling_diagnostics.failures),
            },
            status_code=404,
        )

    return {
        "total_snapshots_requested": rolling_diagnostics.total_snapshots_requested,
        "successful_replays": rolling_diagnostics.successful_replays,
        "failed_replays": rolling_diagnostics.failed_replays,
        "ordered_snapshot_ids": list(rolling_diagnostics.ordered_snapshot_ids),
        "source_freshness_decay_timeline": _serialize_source_freshness_decay_timeline(
            rolling_diagnostics.source_freshness_decay_timeline
        ),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/backtest/source-observation-cadence-drift")
def snapshot_backtest_source_observation_cadence_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        cadence_drift = build_snapshot_replay_service().build_source_observation_cadence_drift(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_CADENCE_INVALID_REQUEST",
            message="Snapshot source observation cadence request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if cadence_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_CADENCE_EMPTY",
            message="No saved paper snapshots were found for source observation cadence analysis.",
            details={
                "total_snapshots_requested": cadence_drift.total_snapshots_requested,
                "failures": list(cadence_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_cadence_drift(cadence_drift)

@router.get("/backtest/source-observation-timestamp-integrity-drift")
def snapshot_backtest_source_observation_timestamp_integrity_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        timestamp_integrity_drift = (
            build_snapshot_replay_service().build_source_observation_timestamp_integrity_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_TIMESTAMP_INTEGRITY_INVALID_REQUEST",
            message="Snapshot source observation timestamp integrity drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if timestamp_integrity_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_TIMESTAMP_INTEGRITY_EMPTY",
            message="No saved paper snapshots were found for source observation timestamp integrity drift analysis.",
            details={
                "total_snapshots_requested": timestamp_integrity_drift.total_snapshots_requested,
                "failures": list(timestamp_integrity_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_timestamp_integrity_drift(timestamp_integrity_drift)

@router.get("/backtest/source-observation-normalization-mode-drift")
def snapshot_backtest_source_observation_normalization_mode_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        normalization_mode_drift = (
            build_snapshot_replay_service().build_source_observation_normalization_mode_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_NORMALIZATION_MODE_INVALID_REQUEST",
            message="Snapshot source observation normalization mode drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if normalization_mode_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_NORMALIZATION_MODE_EMPTY",
            message="No saved paper snapshots were found for source observation normalization mode drift analysis.",
            details={
                "total_snapshots_requested": normalization_mode_drift.total_snapshots_requested,
                "failures": list(normalization_mode_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_normalization_mode_drift(normalization_mode_drift)

@router.get("/backtest/mapped-at-alignment-consistency")
def snapshot_backtest_mapped_at_alignment_consistency(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        mapped_at_alignment_consistency = (
            build_snapshot_replay_service().build_mapped_at_alignment_consistency(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_MAPPED_AT_ALIGNMENT_INVALID_REQUEST",
            message="Snapshot mapped-at alignment consistency request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if mapped_at_alignment_consistency.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_MAPPED_AT_ALIGNMENT_EMPTY",
            message="No saved paper snapshots were found for mapped-at alignment consistency analysis.",
            details={
                "total_snapshots_requested": mapped_at_alignment_consistency.total_snapshots_requested,
                "failures": list(mapped_at_alignment_consistency.failures),
            },
            status_code=404,
        )

    return _serialize_mapped_at_alignment_consistency(mapped_at_alignment_consistency)

@router.get("/backtest/source-observation-availability-lag-drift")
def snapshot_backtest_source_observation_availability_lag_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_observation_availability_lag_drift = (
            build_snapshot_replay_service().build_source_observation_availability_lag_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_AVAILABILITY_LAG_INVALID_REQUEST",
            message="Snapshot source observation availability-lag drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_observation_availability_lag_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_AVAILABILITY_LAG_EMPTY",
            message="No saved paper snapshots were found for source observation availability-lag drift analysis.",
            details={
                "total_snapshots_requested": source_observation_availability_lag_drift.total_snapshots_requested,
                "failures": list(source_observation_availability_lag_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_availability_lag_drift(
        source_observation_availability_lag_drift
    )

@router.get("/backtest/source-freshness-summary-reconciliation")
def snapshot_backtest_source_freshness_summary_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_freshness_summary_reconciliation = (
            build_snapshot_replay_service().build_source_freshness_summary_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_SUMMARY_INVALID_REQUEST",
            message="Snapshot source freshness summary reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_freshness_summary_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_SUMMARY_EMPTY",
            message="No saved paper snapshots were found for source freshness summary reconciliation analysis.",
            details={
                "total_snapshots_requested": source_freshness_summary_reconciliation.total_snapshots_requested,
                "failures": list(source_freshness_summary_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_freshness_summary_reconciliation(
        source_freshness_summary_reconciliation
    )

@router.get("/backtest/source-observation-freshness-seconds-drift")
def snapshot_backtest_source_observation_freshness_seconds_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_observation_freshness_seconds_drift = (
            build_snapshot_replay_service().build_source_observation_freshness_seconds_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_FRESHNESS_SECONDS_INVALID_REQUEST",
            message="Snapshot source observation freshness-seconds drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_observation_freshness_seconds_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_FRESHNESS_SECONDS_EMPTY",
            message="No saved paper snapshots were found for source observation freshness-seconds drift analysis.",
            details={
                "total_snapshots_requested": source_observation_freshness_seconds_drift.total_snapshots_requested,
                "failures": list(source_observation_freshness_seconds_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_freshness_seconds_drift(
        source_observation_freshness_seconds_drift
    )

@router.get("/backtest/source-freshness-status-threshold-reconciliation")
def snapshot_backtest_source_freshness_status_threshold_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_freshness_status_threshold_reconciliation = (
            build_snapshot_replay_service().build_source_freshness_status_threshold_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_STATUS_THRESHOLD_INVALID_REQUEST",
            message="Snapshot source freshness-status threshold reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_freshness_status_threshold_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_STATUS_THRESHOLD_EMPTY",
            message="No saved paper snapshots were found for source freshness-status threshold reconciliation analysis.",
            details={
                "total_snapshots_requested": source_freshness_status_threshold_reconciliation.total_snapshots_requested,
                "failures": list(source_freshness_status_threshold_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_freshness_status_threshold_reconciliation(
        source_freshness_status_threshold_reconciliation
    )

@router.get("/backtest/source-freshness-policy-drift")
def snapshot_backtest_source_freshness_policy_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_freshness_policy_drift = (
            build_snapshot_replay_service().build_source_freshness_policy_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_POLICY_INVALID_REQUEST",
            message="Snapshot source freshness policy drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_freshness_policy_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_FRESHNESS_POLICY_EMPTY",
            message="No saved paper snapshots were found for source freshness policy drift analysis.",
            details={
                "total_snapshots_requested": source_freshness_policy_drift.total_snapshots_requested,
                "failures": list(source_freshness_policy_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_freshness_policy_drift(source_freshness_policy_drift)

@router.get("/backtest/stale-source-list-threshold-reconciliation")
def snapshot_backtest_stale_source_list_threshold_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        stale_source_list_threshold_reconciliation = (
            build_snapshot_replay_service().build_stale_source_list_threshold_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_STALE_SOURCE_LIST_THRESHOLD_INVALID_REQUEST",
            message="Snapshot stale-source list threshold reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if stale_source_list_threshold_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_STALE_SOURCE_LIST_THRESHOLD_EMPTY",
            message="No saved paper snapshots were found for stale-source list threshold reconciliation analysis.",
            details={
                "total_snapshots_requested": stale_source_list_threshold_reconciliation.total_snapshots_requested,
                "failures": list(stale_source_list_threshold_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_stale_source_list_threshold_reconciliation(
        stale_source_list_threshold_reconciliation
    )

@router.get("/backtest/source-diagnostics-freshness-evaluation-mode-drift")
def snapshot_backtest_source_diagnostics_freshness_evaluation_mode_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_freshness_evaluation_mode_drift = (
            build_snapshot_replay_service().build_source_diagnostics_freshness_evaluation_mode_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_FRESHNESS_MODE_INVALID_REQUEST",
            message="Snapshot source diagnostics freshness-evaluation-mode drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_freshness_evaluation_mode_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_FRESHNESS_MODE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics freshness-evaluation-mode drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_freshness_evaluation_mode_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_freshness_evaluation_mode_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_freshness_evaluation_mode_drift(
        source_diagnostics_freshness_evaluation_mode_drift
    )

__all__ = ["router"]
