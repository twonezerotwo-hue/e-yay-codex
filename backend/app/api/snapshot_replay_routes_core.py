from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from app.api import snapshot_replay as snapshot_replay_compat
from app.api.snapshot_replay_serializers import (
    _serialize_comparison_result,
    _serialize_dqs_stability,
    _serialize_drift_classification,
    _serialize_drift_trend_leaderboard,
    _serialize_drift_trend_score,
    _serialize_regime_summary,
    _serialize_regime_timeline,
    _serialize_replay_result,
    _serialize_risk_action_stability,
    _serialize_rolling_backtest_diagnostics,
    _serialize_trigger_persistence_leaderboard,
    _summarize_backtest_result,
)
from app.core.errors import AppError

router = APIRouter(tags=["snapshots"])


def build_snapshot_replay_service():
    return snapshot_replay_compat.build_snapshot_replay_service()

@router.get("/backtest/summary")
def snapshot_backtest_summary(
    limit: int = Query(default=10),
    report_type: str | None = Query(default=None),
    snapshot_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    try:
        backtest_result = build_snapshot_replay_service().run_backtest(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
    except ValueError as exc:
        raise AppError(
            error_code="SNAPSHOT_BACKTEST_INVALID_REQUEST",
            message="Snapshot backtest request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if backtest_result.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_BACKTEST_EMPTY",
            message="No replayable paper snapshots were found for the requested backtest.",
            details={
                "total_snapshots_requested": backtest_result.total_snapshots_requested,
                "failed_replays": backtest_result.failed_replays,
                "failures": list(backtest_result.failures),
            },
            status_code=404,
        )

    return _summarize_backtest_result(backtest_result)

@router.get("/backtest/rolling-diagnostics")
def snapshot_backtest_rolling_diagnostics(
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
            error_code="SNAPSHOT_ROLLING_DIAGNOSTICS_INVALID_REQUEST",
            message="Snapshot rolling diagnostics request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_ROLLING_DIAGNOSTICS_EMPTY",
            message="No replayable paper snapshots were found for rolling diagnostics.",
            details={
                "total_snapshots_requested": rolling_diagnostics.total_snapshots_requested,
                "failed_replays": rolling_diagnostics.failed_replays,
                "failures": list(rolling_diagnostics.failures),
            },
            status_code=404,
        )

    return _serialize_rolling_backtest_diagnostics(rolling_diagnostics)

@router.get("/backtest/trigger-persistence-leaderboard")
def snapshot_backtest_trigger_persistence_leaderboard(
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
            error_code="SNAPSHOT_TRIGGER_PERSISTENCE_INVALID_REQUEST",
            message="Snapshot trigger persistence leaderboard request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_TRIGGER_PERSISTENCE_EMPTY",
            message="No replayable paper snapshots were found for trigger persistence leaderboard generation.",
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
        "trigger_persistence_leaderboard": _serialize_trigger_persistence_leaderboard(
            rolling_diagnostics.trigger_persistence_leaderboard
        ),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/backtest/drift-trend-leaderboard")
def snapshot_backtest_drift_trend_leaderboard(
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
            error_code="SNAPSHOT_DRIFT_TREND_LEADERBOARD_INVALID_REQUEST",
            message="Snapshot drift trend leaderboard request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_DRIFT_TREND_LEADERBOARD_EMPTY",
            message="No replayable paper snapshots were found for drift trend leaderboard generation.",
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
        "drift_trend_score": _serialize_drift_trend_score(rolling_diagnostics.drift_trend_score),
        "drift_trend_leaderboard": _serialize_drift_trend_leaderboard(
            rolling_diagnostics.drift_trend_leaderboard
        ),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/backtest/dqs-stability")
def snapshot_backtest_dqs_stability(
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
            error_code="SNAPSHOT_DQS_STABILITY_INVALID_REQUEST",
            message="Snapshot DQS stability request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_DQS_STABILITY_EMPTY",
            message="No replayable paper snapshots were found for DQS stability analysis.",
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
        "dqs_stability": _serialize_dqs_stability(rolling_diagnostics.dqs_stability),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/backtest/risk-action-stability")
def snapshot_backtest_risk_action_stability(
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
            error_code="SNAPSHOT_RISK_ACTION_STABILITY_INVALID_REQUEST",
            message="Snapshot risk action stability request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_RISK_ACTION_STABILITY_EMPTY",
            message="No replayable paper snapshots were found for risk action stability analysis.",
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
        "risk_action_path": list(rolling_diagnostics.risk_action_path),
        "risk_action_stability": _serialize_risk_action_stability(
            rolling_diagnostics.risk_action_stability
        ),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/backtest/regime-timeline")
def snapshot_backtest_regime_timeline(
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
            error_code="SNAPSHOT_REGIME_TIMELINE_INVALID_REQUEST",
            message="Snapshot regime timeline request is invalid.",
            details={"reason": str(exc)},
            status_code=400,
        ) from exc

    if rolling_diagnostics.successful_replays == 0:
        raise AppError(
            error_code="SNAPSHOT_REGIME_TIMELINE_EMPTY",
            message="No replayable paper snapshots were found for regime timeline generation.",
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
        "regime_summary": _serialize_regime_summary(rolling_diagnostics.regime_summary),
        "regime_timeline": _serialize_regime_timeline(rolling_diagnostics.regime_timeline),
        "failures": list(rolling_diagnostics.failures),
        "paper_safe": rolling_diagnostics.paper_safe,
        "network_calls": rolling_diagnostics.network_calls,
        "execution_side_effects": rolling_diagnostics.execution_side_effects,
    }

@router.get("/compare")
def compare_saved_snapshots(
    baseline_snapshot_id: str = Query(),
    candidate_snapshot_id: str = Query(),
) -> dict[str, object]:
    replay_service = build_snapshot_replay_service()

    try:
        comparison_result = replay_service.compare_snapshots(
            baseline_snapshot_id,
            candidate_snapshot_id,
        )
    except KeyError as exc:
        missing_snapshot_id = exc.args[0] if exc.args else "unknown"
        raise AppError(
            error_code="SNAPSHOT_COMPARISON_NOT_FOUND",
            message="One or more requested paper snapshots could not be found for comparison.",
            details={
                "baseline_snapshot_id": baseline_snapshot_id,
                "candidate_snapshot_id": candidate_snapshot_id,
                "missing_snapshot_id": missing_snapshot_id,
            },
            status_code=404,
        ) from exc
    except (TypeError, ValueError) as exc:
        raise AppError(
            error_code="SNAPSHOT_COMPARISON_INVALID",
            message="Requested paper snapshots could not be compared safely.",
            details={
                "baseline_snapshot_id": baseline_snapshot_id,
                "candidate_snapshot_id": candidate_snapshot_id,
                "reason": str(exc),
            },
            status_code=422,
        ) from exc

    return {
        **_serialize_comparison_result(comparison_result),
        "drift_classification": _serialize_drift_classification(
            replay_service.classify_comparison_result(comparison_result)
        ),
    }

@router.get("/{snapshot_id}/replay")
def replay_saved_snapshot(snapshot_id: str) -> dict[str, object]:
    replay_service = build_snapshot_replay_service()

    try:
        replay_result = replay_service.replay_snapshot(snapshot_id)
    except KeyError as exc:
        raise AppError(
            error_code="SNAPSHOT_NOT_FOUND",
            message="Requested paper snapshot could not be found.",
            details={"snapshot_id": snapshot_id},
            status_code=404,
        ) from exc
    except (TypeError, ValueError) as exc:
        raise AppError(
            error_code="SNAPSHOT_REPLAY_INVALID",
            message="Requested paper snapshot could not be replayed safely.",
            details={"snapshot_id": snapshot_id, "reason": str(exc)},
            status_code=422,
        ) from exc

    return _serialize_replay_result(replay_result)

__all__ = ["router"]
