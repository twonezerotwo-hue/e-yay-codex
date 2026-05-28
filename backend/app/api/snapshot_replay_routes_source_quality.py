from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from app.api import snapshot_replay as snapshot_replay_compat
from app.api.snapshot_replay_source_serializers import (
    _serialize_raw_payload_reference_completeness,
    _serialize_source_decision_usage_consistency,
    _serialize_source_diagnostics_average_coverage_drift,
    _serialize_source_diagnostics_critical_feature_drift,
    _serialize_source_diagnostics_high_severity_drift,
    _serialize_source_diagnostics_info_feature_drift,
    _serialize_source_diagnostics_minimum_coverage_floor_reconciliation,
    _serialize_source_diagnostics_missing_asset_count_reconciliation,
    _serialize_source_diagnostics_missing_source_feature_count_reconciliation,
    _serialize_source_diagnostics_ready_feature_drift,
    _serialize_source_diagnostics_severity_label_drift,
    _serialize_source_diagnostics_severity_rank_density_drift,
    _serialize_source_diagnostics_severity_rank_drift,
    _serialize_source_diagnostics_severity_rank_spread_drift,
    _serialize_source_diagnostics_severity_ranking_critical_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_feature_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_info_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_non_actionable_count_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation,
    _serialize_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation,
    _serialize_source_diagnostics_severity_ranking_warning_count_reconciliation,
    _serialize_source_diagnostics_stale_asset_count_reconciliation,
    _serialize_source_diagnostics_stale_feature_drift,
    _serialize_source_diagnostics_warning_feature_drift,
    _serialize_source_diagnostics_zero_rank_drift,
    _serialize_source_gap_recurrence_leaderboard,
    _serialize_source_observation_confidence_drift,
    _serialize_source_observation_record_summary_reconciliation,
    _serialize_source_observation_summary_drift,
    _serialize_source_record_completeness,
    _serialize_verified_source_coverage_reconciliation,
)
from app.core.errors import AppError

router = APIRouter(tags=["snapshots"])


def build_snapshot_replay_service():
    return snapshot_replay_compat.build_snapshot_replay_service()

@router.get("/backtest/source-gap-recurrence-leaderboard")
def snapshot_backtest_source_gap_recurrence_leaderboard(
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
            error_code="SNAPSHOT_SOURCE_GAP_RECURRENCE_INVALID_REQUEST",
            message="Snapshot source gap recurrence leaderboard request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_GAP_RECURRENCE_EMPTY",
            message="No replayable paper snapshots were found for source gap recurrence leaderboard generation.",
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
        "source_gap_recurrence_leaderboard": _serialize_source_gap_recurrence_leaderboard(
            rolling_diagnostics.source_gap_recurrence_leaderboard
        ),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/backtest/raw-payload-reference-completeness")
def snapshot_backtest_raw_payload_reference_completeness(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        raw_payload_reference_completeness = (
            build_snapshot_replay_service().build_raw_payload_reference_completeness(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_RAW_PAYLOAD_REFERENCE_INVALID_REQUEST",
            message="Snapshot raw payload reference completeness request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if raw_payload_reference_completeness.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_RAW_PAYLOAD_REFERENCE_EMPTY",
            message="No saved paper snapshots were found for raw payload reference completeness analysis.",
            details={
                "total_snapshots_requested": raw_payload_reference_completeness.total_snapshots_requested,
                "failures": list(raw_payload_reference_completeness.failures),
            },
            status_code=404,
        )

    return _serialize_raw_payload_reference_completeness(raw_payload_reference_completeness)

@router.get("/backtest/source-record-completeness")
def snapshot_backtest_source_record_completeness(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_record_completeness = build_snapshot_replay_service().build_source_record_completeness(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_RECORD_COMPLETENESS_INVALID_REQUEST",
            message="Snapshot source record completeness request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_record_completeness.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_RECORD_COMPLETENESS_EMPTY",
            message="No saved paper snapshots were found for source record completeness analysis.",
            details={
                "total_snapshots_requested": source_record_completeness.total_snapshots_requested,
                "failures": list(source_record_completeness.failures),
            },
            status_code=404,
        )

    return _serialize_source_record_completeness(source_record_completeness)

@router.get("/backtest/source-decision-usage-consistency")
def snapshot_backtest_source_decision_usage_consistency(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_decision_usage_consistency = (
            build_snapshot_replay_service().build_source_decision_usage_consistency(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DECISION_USAGE_CONSISTENCY_INVALID_REQUEST",
            message="Snapshot source decision-usage consistency request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_decision_usage_consistency.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DECISION_USAGE_CONSISTENCY_EMPTY",
            message="No saved paper snapshots were found for source decision-usage consistency analysis.",
            details={
                "total_snapshots_requested": source_decision_usage_consistency.total_snapshots_requested,
                "failures": list(source_decision_usage_consistency.failures),
            },
            status_code=404,
        )

    return _serialize_source_decision_usage_consistency(source_decision_usage_consistency)

@router.get("/backtest/source-observation-summary-drift")
def snapshot_backtest_source_observation_summary_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_observation_summary_drift = (
            build_snapshot_replay_service().build_source_observation_summary_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_SUMMARY_DRIFT_INVALID_REQUEST",
            message="Snapshot source observation summary drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_observation_summary_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_SUMMARY_DRIFT_EMPTY",
            message="No saved paper snapshots were found for source observation summary drift analysis.",
            details={
                "total_snapshots_requested": source_observation_summary_drift.total_snapshots_requested,
                "failures": list(source_observation_summary_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_summary_drift(source_observation_summary_drift)

@router.get("/backtest/source-observation-record-summary-reconciliation")
def snapshot_backtest_source_observation_record_summary_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        record_summary_reconciliation = (
            build_snapshot_replay_service().build_source_observation_record_summary_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_RECORD_SUMMARY_RECONCILIATION_INVALID_REQUEST",
            message="Snapshot source observation record/summary reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if record_summary_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_RECORD_SUMMARY_RECONCILIATION_EMPTY",
            message="No saved paper snapshots were found for source observation record/summary reconciliation analysis.",
            details={
                "total_snapshots_requested": record_summary_reconciliation.total_snapshots_requested,
                "failures": list(record_summary_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_record_summary_reconciliation(
        record_summary_reconciliation
    )

@router.get("/backtest/source-observation-confidence-drift")
def snapshot_backtest_source_observation_confidence_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_observation_confidence_drift = (
            build_snapshot_replay_service().build_source_observation_confidence_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_CONFIDENCE_INVALID_REQUEST",
            message="Snapshot source observation confidence drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_observation_confidence_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_OBSERVATION_CONFIDENCE_EMPTY",
            message="No saved paper snapshots were found for source observation confidence drift analysis.",
            details={
                "total_snapshots_requested": source_observation_confidence_drift.total_snapshots_requested,
                "failures": list(source_observation_confidence_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_observation_confidence_drift(source_observation_confidence_drift)

@router.get("/backtest/verified-source-coverage-reconciliation")
def snapshot_backtest_verified_source_coverage_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        verified_source_coverage_reconciliation = (
            build_snapshot_replay_service().build_verified_source_coverage_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_VERIFIED_SOURCE_COVERAGE_INVALID_REQUEST",
            message="Snapshot verified-source coverage reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if verified_source_coverage_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_VERIFIED_SOURCE_COVERAGE_EMPTY",
            message="No saved paper snapshots were found for verified-source coverage reconciliation analysis.",
            details={
                "total_snapshots_requested": verified_source_coverage_reconciliation.total_snapshots_requested,
                "failures": list(verified_source_coverage_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_verified_source_coverage_reconciliation(
        verified_source_coverage_reconciliation
    )

@router.get("/backtest/source-diagnostics-stale-asset-count-reconciliation")
def snapshot_backtest_source_diagnostics_stale_asset_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_stale_asset_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_stale_asset_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_STALE_ASSET_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics stale-asset count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_stale_asset_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_STALE_ASSET_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics stale-asset count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_stale_asset_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_stale_asset_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_stale_asset_count_reconciliation(
        source_diagnostics_stale_asset_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-average-coverage-drift")
def snapshot_backtest_source_diagnostics_average_coverage_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_average_coverage_drift = (
            build_snapshot_replay_service().build_source_diagnostics_average_coverage_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_AVERAGE_COVERAGE_INVALID_REQUEST",
            message="Snapshot source diagnostics average-coverage drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_average_coverage_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_AVERAGE_COVERAGE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics average-coverage drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_average_coverage_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_average_coverage_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_average_coverage_drift(
        source_diagnostics_average_coverage_drift
    )

@router.get("/backtest/source-diagnostics-minimum-coverage-floor-reconciliation")
def snapshot_backtest_source_diagnostics_minimum_coverage_floor_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_minimum_coverage_floor_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_minimum_coverage_floor_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_MINIMUM_COVERAGE_INVALID_REQUEST",
            message="Snapshot source diagnostics minimum-coverage floor reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_minimum_coverage_floor_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_MINIMUM_COVERAGE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics minimum-coverage floor reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_minimum_coverage_floor_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_minimum_coverage_floor_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_minimum_coverage_floor_reconciliation(
        source_diagnostics_minimum_coverage_floor_reconciliation
    )

@router.get("/backtest/source-diagnostics-ready-feature-drift")
def snapshot_backtest_source_diagnostics_ready_feature_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_ready_feature_drift = (
            build_snapshot_replay_service().build_source_diagnostics_ready_feature_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_READY_FEATURE_INVALID_REQUEST",
            message="Snapshot source diagnostics ready-feature drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_ready_feature_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_READY_FEATURE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics ready-feature drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_ready_feature_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_ready_feature_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_ready_feature_drift(
        source_diagnostics_ready_feature_drift
    )

@router.get("/backtest/source-diagnostics-stale-feature-drift")
def snapshot_backtest_source_diagnostics_stale_feature_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_stale_feature_drift = (
            build_snapshot_replay_service().build_source_diagnostics_stale_feature_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_STALE_FEATURE_INVALID_REQUEST",
            message="Snapshot source diagnostics stale-feature drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_stale_feature_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_STALE_FEATURE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics stale-feature drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_stale_feature_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_stale_feature_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_stale_feature_drift(
        source_diagnostics_stale_feature_drift
    )

@router.get("/backtest/source-diagnostics-critical-feature-drift")
def snapshot_backtest_source_diagnostics_critical_feature_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_critical_feature_drift = (
            build_snapshot_replay_service().build_source_diagnostics_critical_feature_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_CRITICAL_FEATURE_INVALID_REQUEST",
            message="Snapshot source diagnostics critical-feature drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_critical_feature_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_CRITICAL_FEATURE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics critical-feature drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_critical_feature_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_critical_feature_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_critical_feature_drift(
        source_diagnostics_critical_feature_drift
    )

@router.get("/backtest/source-diagnostics-high-severity-drift")
def snapshot_backtest_source_diagnostics_high_severity_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_high_severity_drift = (
            build_snapshot_replay_service().build_source_diagnostics_high_severity_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_HIGH_SEVERITY_INVALID_REQUEST",
            message="Snapshot source diagnostics high-severity drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_high_severity_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_HIGH_SEVERITY_EMPTY",
            message="No saved paper snapshots were found for source diagnostics high-severity drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_high_severity_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_high_severity_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_high_severity_drift(
        source_diagnostics_high_severity_drift
    )

@router.get("/backtest/source-diagnostics-warning-feature-drift")
def snapshot_backtest_source_diagnostics_warning_feature_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_warning_feature_drift = (
            build_snapshot_replay_service().build_source_diagnostics_warning_feature_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_WARNING_FEATURE_INVALID_REQUEST",
            message="Snapshot source diagnostics warning-feature drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_warning_feature_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_WARNING_FEATURE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics warning-feature drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_warning_feature_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_warning_feature_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_warning_feature_drift(
        source_diagnostics_warning_feature_drift
    )

@router.get("/backtest/source-diagnostics-info-feature-drift")
def snapshot_backtest_source_diagnostics_info_feature_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_info_feature_drift = (
            build_snapshot_replay_service().build_source_diagnostics_info_feature_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_INFO_FEATURE_INVALID_REQUEST",
            message="Snapshot source diagnostics info-feature drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_info_feature_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_INFO_FEATURE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics info-feature drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_info_feature_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_info_feature_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_info_feature_drift(
        source_diagnostics_info_feature_drift
    )

@router.get("/backtest/source-diagnostics-zero-rank-drift")
def snapshot_backtest_source_diagnostics_zero_rank_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_zero_rank_drift = (
            build_snapshot_replay_service().build_source_diagnostics_zero_rank_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_ZERO_RANK_INVALID_REQUEST",
            message="Snapshot source diagnostics zero-rank drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_zero_rank_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_ZERO_RANK_EMPTY",
            message="No saved paper snapshots were found for source diagnostics zero-rank drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_zero_rank_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_zero_rank_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_zero_rank_drift(
        source_diagnostics_zero_rank_drift
    )

@router.get("/backtest/source-diagnostics-severity-label-drift")
def snapshot_backtest_source_diagnostics_severity_label_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_label_drift = (
            build_snapshot_replay_service().build_source_diagnostics_severity_label_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_LABEL_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-label drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_label_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_LABEL_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-label drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_label_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_label_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_label_drift(
        source_diagnostics_severity_label_drift
    )

@router.get("/backtest/source-diagnostics-severity-rank-drift")
def snapshot_backtest_source_diagnostics_severity_rank_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_rank_drift = (
            build_snapshot_replay_service().build_source_diagnostics_severity_rank_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANK_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-rank drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_rank_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANK_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-rank drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_rank_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_rank_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_rank_drift(
        source_diagnostics_severity_rank_drift
    )

@router.get("/backtest/source-diagnostics-severity-rank-density-drift")
def snapshot_backtest_source_diagnostics_severity_rank_density_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_rank_density_drift = (
            build_snapshot_replay_service().build_source_diagnostics_severity_rank_density_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANK_DENSITY_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-rank density drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_rank_density_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANK_DENSITY_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-rank density drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_rank_density_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_rank_density_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_rank_density_drift(
        source_diagnostics_severity_rank_density_drift
    )

@router.get("/backtest/source-diagnostics-severity-rank-spread-drift")
def snapshot_backtest_source_diagnostics_severity_rank_spread_drift(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_rank_spread_drift = (
            build_snapshot_replay_service().build_source_diagnostics_severity_rank_spread_drift(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANK_SPREAD_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-rank spread drift request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_rank_spread_drift.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANK_SPREAD_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-rank spread drift analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_rank_spread_drift.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_rank_spread_drift.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_rank_spread_drift(
        source_diagnostics_severity_rank_spread_drift
    )

@router.get("/backtest/source-diagnostics-severity-ranking-feature-count-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_feature_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_feature_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_feature_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking feature-count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_ranking_feature_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking feature-count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_feature_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_feature_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_feature_count_reconciliation(
        source_diagnostics_severity_ranking_feature_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-warning-count-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_warning_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_warning_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_warning_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_WARNING_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking warning-count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_ranking_warning_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_WARNING_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking warning-count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_warning_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_warning_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_warning_count_reconciliation(
        source_diagnostics_severity_ranking_warning_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-info-count-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_info_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_info_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_info_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_INFO_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking info-count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_ranking_info_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_INFO_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking info-count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_info_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_info_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_info_count_reconciliation(
        source_diagnostics_severity_ranking_info_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-non-actionable-count-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_non_actionable_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_NON_ACTIONABLE_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking non-actionable-count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if (
        source_diagnostics_severity_ranking_non_actionable_count_reconciliation.snapshots_checked
        == 0
    ):
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_NON_ACTIONABLE_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking non-actionable-count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_non_actionable_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_non_actionable_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
        source_diagnostics_severity_ranking_non_actionable_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-rank-label-consistency-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_rank_label_consistency_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_LABEL_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking rank/label consistency reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if (
        source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.snapshots_checked
        == 0
    ):
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_LABEL_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking rank/label consistency reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_rank_label_consistency_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
        source_diagnostics_severity_ranking_rank_label_consistency_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-rank-order-continuity-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_rank_order_continuity_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_ORDER_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking rank-order continuity reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if (
        source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.snapshots_checked
        == 0
    ):
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_ORDER_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking rank-order continuity reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_rank_order_continuity_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
        source_diagnostics_severity_ranking_rank_order_continuity_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_GAP_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking rank-gap continuity reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if (
        source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.snapshots_checked
        == 0
    ):
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_GAP_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking rank-gap continuity reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
        source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_GAP_MAGNITUDE_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking rank-gap magnitude reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if (
        source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.snapshots_checked
        == 0
    ):
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_RANK_GAP_MAGNITUDE_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking rank-gap magnitude reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
        source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation
    )

@router.get("/backtest/source-diagnostics-severity-ranking-critical-count-reconciliation")
def snapshot_backtest_source_diagnostics_severity_ranking_critical_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_severity_ranking_critical_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_severity_ranking_critical_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_CRITICAL_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics severity-ranking critical-count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_severity_ranking_critical_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_SEVERITY_RANKING_CRITICAL_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics severity-ranking critical-count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_severity_ranking_critical_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_severity_ranking_critical_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_severity_ranking_critical_count_reconciliation(
        source_diagnostics_severity_ranking_critical_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-missing-source-feature-count-reconciliation")
def snapshot_backtest_source_diagnostics_missing_source_feature_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_missing_source_feature_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_missing_source_feature_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_MISSING_SOURCE_FEATURE_COUNT_INVALID_REQUEST",
            message="Snapshot source diagnostics missing-source feature-count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_missing_source_feature_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_MISSING_SOURCE_FEATURE_COUNT_EMPTY",
            message="No saved paper snapshots were found for source diagnostics missing-source feature-count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_missing_source_feature_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_missing_source_feature_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_missing_source_feature_count_reconciliation(
        source_diagnostics_missing_source_feature_count_reconciliation
    )

@router.get("/backtest/source-diagnostics-missing-asset-count-reconciliation")
def snapshot_backtest_source_diagnostics_missing_asset_count_reconciliation(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        source_diagnostics_missing_asset_count_reconciliation = (
            build_snapshot_replay_service().build_source_diagnostics_missing_asset_count_reconciliation(
                snapshot_ids=snapshot_ids,
                limit=limit,
                report_type=report_type,
            )
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_MISSING_ASSET_INVALID_REQUEST",
            message="Snapshot source diagnostics missing-asset count reconciliation request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if source_diagnostics_missing_asset_count_reconciliation.snapshots_checked == 0:
        raise AppError(
            error_code="SNAPSHOT_SOURCE_DIAGNOSTICS_MISSING_ASSET_EMPTY",
            message="No saved paper snapshots were found for source diagnostics missing-asset count reconciliation analysis.",
            details={
                "total_snapshots_requested": source_diagnostics_missing_asset_count_reconciliation.total_snapshots_requested,
                "failures": list(source_diagnostics_missing_asset_count_reconciliation.failures),
            },
            status_code=404,
        )

    return _serialize_source_diagnostics_missing_asset_count_reconciliation(
        source_diagnostics_missing_asset_count_reconciliation
    )

__all__ = ["router"]
