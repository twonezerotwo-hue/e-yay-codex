
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from app.domain import MarketSnapshot
from app.services.ceo_report_service import CEOReportService
from app.services.data_quality_service import DataQualityDecision
from app.services.data_quality_service import DataQualityScoreResult
from app.services.risk_engine import RiskEngine
from app.services.risk_engine import SnapshotRiskInput
from app.services.trigger_engine import TriggerEngine
from app.storage import SnapshotStore
from app.services.snapshot_replay_models import SnapshotBacktestResult
from app.services.snapshot_replay_models import SnapshotComparisonResult
from app.services.snapshot_replay_models import SnapshotReplayResult


class SnapshotReplayCore:
    def __init__(
        self,
        snapshot_store: SnapshotStore,
        *,
        trigger_engine: TriggerEngine | None = None,
        risk_engine: RiskEngine | None = None,
        ceo_report_service: CEOReportService | None = None,
    ) -> None:
        self.snapshot_store = snapshot_store
        self.trigger_engine = trigger_engine or TriggerEngine()
        self.risk_engine = risk_engine or RiskEngine()
        self.ceo_report_service = ceo_report_service or CEOReportService()

    def replay_snapshot(self, snapshot_id: str) -> SnapshotReplayResult:
        snapshot_payload = self.snapshot_store.load_snapshot(snapshot_id)
        return self.replay_snapshot_payload(snapshot_payload)

    def replay_snapshot_payload(
        self,
        snapshot_payload: Mapping[str, Any],
    ) -> SnapshotReplayResult:
        self._validate_snapshot_payload(snapshot_payload)

        serialized_snapshots = snapshot_payload["snapshots"]
        snapshots = tuple(
            self._deserialize_snapshot(snapshot_data)
            for snapshot_data in serialized_snapshots
        )
        risk_inputs = tuple(
            SnapshotRiskInput(
                asset_symbol=snapshot.asset_symbol,
                dqs_result=self._deserialize_dqs_result(snapshot_data["dqs_result"]),
            )
            for snapshot, snapshot_data in zip(snapshots, serialized_snapshots, strict=True)
        )
        trigger_results = tuple(self.trigger_engine.evaluate(snapshots))
        risk_engine_result = self.risk_engine.evaluate(risk_inputs, trigger_results)
        ceo_report = self.ceo_report_service.generate(trigger_results, risk_engine_result)

        return SnapshotReplayResult(
            snapshot_id=str(snapshot_payload["snapshot_id"]),
            created_at=self._normalize_datetime_string(snapshot_payload["created_at"]),
            report_type=str(snapshot_payload["report_type"]),
            mode=str(snapshot_payload["mode"]),
            execution_mode=str(snapshot_payload["execution_mode"]),
            decision_permission=str(snapshot_payload["decision_permission"]),
            source_registry_version=str(snapshot_payload["source_registry_version"]),
            feature_registry_version=self._optional_string(snapshot_payload.get("feature_registry_version")),
            source_observations=self._normalize_source_observations(snapshot_payload["source_observations"]),
            missing_sources=tuple(str(item) for item in snapshot_payload["missing_sources"]),
            stale_sources=tuple(str(item) for item in snapshot_payload["stale_sources"]),
            snapshots=snapshots,
            snapshot_quality_results=risk_inputs,
            trigger_results=trigger_results,
            risk_engine_result=risk_engine_result,
            ceo_report=ceo_report,
            pipeline_summary=self._normalize_mapping(snapshot_payload.get("pipeline_summary", {})),
            audit_source_payload=self._normalize_optional_mapping(snapshot_payload.get("audit_source_payload")),
            replay_regime=self._extract_replay_regime(snapshot_payload),
            replay_regime_diagnostic=self._build_replay_regime_diagnostic(snapshot_payload),
        )

    def _run_ordered_backtest(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> tuple[SnapshotBacktestResult, tuple[SnapshotReplayResult, ...]]:
        backtest_result = self.run_backtest(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        ordered_replay_results = tuple(
            sorted(
                backtest_result.replay_results,
                key=lambda result: (result.created_at, result.snapshot_id),
            )
        )
        return backtest_result, ordered_replay_results

    def run_backtest(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotBacktestResult:
        resolved_snapshot_ids = self._resolve_snapshot_ids(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        replay_results: list[SnapshotReplayResult] = []
        failures: list[dict[str, str]] = []

        for snapshot_id in resolved_snapshot_ids:
            try:
                replay_results.append(self.replay_snapshot(snapshot_id))
            except Exception as exc:
                failures.append(
                    {
                        "snapshot_id": snapshot_id,
                        "reason": str(exc) or exc.__class__.__name__,
                    }
                )

        return SnapshotBacktestResult(
            total_snapshots_requested=len(resolved_snapshot_ids),
            successful_replays=len(replay_results),
            failed_replays=len(failures),
            replay_results=tuple(replay_results),
            failures=tuple(failures),
        )

    def compare_snapshots(
        self,
        baseline_snapshot_id: str,
        candidate_snapshot_id: str,
    ) -> SnapshotComparisonResult:
        baseline_result = self.replay_snapshot(baseline_snapshot_id)
        candidate_result = self.replay_snapshot(candidate_snapshot_id)
        return self.compare_replay_results(baseline_result, candidate_result)

    def compare_replay_results(
        self,
        baseline_result: SnapshotReplayResult,
        candidate_result: SnapshotReplayResult,
    ) -> SnapshotComparisonResult:
        baseline_trigger_codes = {
            trigger.trigger_code
            for trigger in baseline_result.trigger_results
            if trigger.is_triggered
        }
        candidate_trigger_codes = {
            trigger.trigger_code
            for trigger in candidate_result.trigger_results
            if trigger.is_triggered
        }
        baseline_reason_codes = set(baseline_result.risk_engine_result.reason_codes)
        candidate_reason_codes = set(candidate_result.risk_engine_result.reason_codes)
        baseline_missing_sources = set(baseline_result.missing_sources)
        candidate_missing_sources = set(candidate_result.missing_sources)
        baseline_stale_sources = set(baseline_result.stale_sources)
        candidate_stale_sources = set(candidate_result.stale_sources)
        paper_safe = self._is_paper_safe_replay_result(
            baseline_result,
        ) and self._is_paper_safe_replay_result(candidate_result)

        return SnapshotComparisonResult(
            baseline_snapshot_id=baseline_result.snapshot_id,
            candidate_snapshot_id=candidate_result.snapshot_id,
            baseline_created_at=baseline_result.created_at,
            candidate_created_at=candidate_result.created_at,
            baseline_report_type=baseline_result.report_type,
            candidate_report_type=candidate_result.report_type,
            risk_action_changed=(
                baseline_result.risk_engine_result.risk_action
                != candidate_result.risk_engine_result.risk_action
            ),
            risk_action_from=baseline_result.risk_engine_result.risk_action.value,
            risk_action_to=candidate_result.risk_engine_result.risk_action.value,
            kill_switch_changed=(
                baseline_result.risk_engine_result.kill_switch_active
                != candidate_result.risk_engine_result.kill_switch_active
            ),
            kill_switch_from=baseline_result.risk_engine_result.kill_switch_active,
            kill_switch_to=candidate_result.risk_engine_result.kill_switch_active,
            new_trigger_codes=tuple(sorted(candidate_trigger_codes - baseline_trigger_codes)),
            cleared_trigger_codes=tuple(sorted(baseline_trigger_codes - candidate_trigger_codes)),
            unchanged_trigger_codes=tuple(sorted(candidate_trigger_codes & baseline_trigger_codes)),
            new_reason_codes=tuple(sorted(candidate_reason_codes - baseline_reason_codes)),
            cleared_reason_codes=tuple(sorted(baseline_reason_codes - candidate_reason_codes)),
            missing_sources_added=tuple(sorted(candidate_missing_sources - baseline_missing_sources)),
            missing_sources_cleared=tuple(sorted(baseline_missing_sources - candidate_missing_sources)),
            stale_sources_added=tuple(sorted(candidate_stale_sources - baseline_stale_sources)),
            stale_sources_cleared=tuple(sorted(baseline_stale_sources - candidate_stale_sources)),
            execution_status_consistent=(
                baseline_result.ceo_report.execution_status
                == candidate_result.ceo_report.execution_status
                == "OFF / NO_EXECUTION"
            ),
            paper_safe=paper_safe,
        )

    def _resolve_snapshot_ids(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None,
        limit: int,
        report_type: str | None,
    ) -> tuple[str, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0.")

        if snapshot_ids is not None:
            return tuple(str(snapshot_id) for snapshot_id in snapshot_ids)

        stored_snapshots = self.snapshot_store.list_snapshots(limit=limit)
        filtered_snapshots = [
            snapshot_payload
            for snapshot_payload in stored_snapshots
            if report_type is None or snapshot_payload.get("report_type") == report_type
        ]
        return tuple(
            str(snapshot_payload["snapshot_id"])
            for snapshot_payload in filtered_snapshots
        )

    def _load_ordered_snapshot_payloads(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None,
        limit: int,
        report_type: str | None,
    ) -> tuple[tuple[Mapping[str, Any], ...], tuple[dict[str, str], ...], int]:
        resolved_snapshot_ids = self._resolve_snapshot_ids(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        payloads: list[Mapping[str, Any]] = []
        failures: list[dict[str, str]] = []

        for snapshot_id in resolved_snapshot_ids:
            try:
                payloads.append(self.snapshot_store.load_snapshot(snapshot_id))
            except Exception as exc:
                failures.append(
                    {
                        "snapshot_id": snapshot_id,
                        "reason": str(exc) or exc.__class__.__name__,
                    }
                )

        ordered_payloads = tuple(
            sorted(
                payloads,
                key=lambda payload: (
                    str(payload.get("created_at", "")),
                    str(payload.get("snapshot_id", "")),
                ),
            )
        )
        return ordered_payloads, tuple(failures), len(resolved_snapshot_ids)

    def _validate_snapshot_payload(self, snapshot_payload: Mapping[str, Any]) -> None:
        required_fields = (
            "snapshot_id",
            "created_at",
            "mode",
            "source_registry_version",
            "source_observations",
            "missing_sources",
            "stale_sources",
            "report_type",
            "decision_permission",
            "execution_mode",
            "snapshots",
        )
        missing_fields = [
            field_name
            for field_name in required_fields
            if field_name not in snapshot_payload or snapshot_payload[field_name] is None
        ]
        if missing_fields:
            raise ValueError(
                "snapshot replay payload is missing required fields: "
                + ", ".join(sorted(missing_fields))
            )

        if str(snapshot_payload["mode"]) not in SnapshotStore.ALLOWED_MODES:
            raise ValueError("snapshot replay payload mode must remain PAPER_SAFE or SIMULATION.")

        if str(snapshot_payload["decision_permission"]) != "NO_EXECUTION":
            raise ValueError("snapshot replay payload decision_permission must remain NO_EXECUTION.")

        if str(snapshot_payload["execution_mode"]) not in SnapshotStore.ALLOWED_EXECUTION_MODES:
            raise ValueError(
                "snapshot replay payload execution_mode must remain PAPER_ONLY or NO_EXECUTION."
            )

        if not isinstance(snapshot_payload["source_observations"], Mapping):
            raise TypeError("snapshot replay payload source_observations must be a mapping.")

        if not isinstance(snapshot_payload["missing_sources"], list):
            raise TypeError("snapshot replay payload missing_sources must be a list.")

        if not isinstance(snapshot_payload["stale_sources"], list):
            raise TypeError("snapshot replay payload stale_sources must be a list.")

        if not isinstance(snapshot_payload["snapshots"], list):
            raise TypeError("snapshot replay payload snapshots must be a list.")

        if not snapshot_payload["snapshots"]:
            raise ValueError("snapshot replay payload snapshots must not be empty.")

    def _deserialize_snapshot(self, snapshot_data: Mapping[str, Any]) -> MarketSnapshot:
        return MarketSnapshot(
            asset_symbol=str(snapshot_data["asset_symbol"]),
            value=float(snapshot_data["value"]),
            unit=str(snapshot_data["unit"]),
            source_name=str(snapshot_data["source_name"]),
            source_tier=str(snapshot_data["source_tier"]),
            observed_at=self._parse_datetime(snapshot_data["observed_at"]),
            available_at=self._parse_datetime(snapshot_data["available_at"]),
            stored_at=self._parse_datetime(snapshot_data["stored_at"]),
            freshness_seconds=int(snapshot_data["freshness_seconds"]),
            is_stale=bool(snapshot_data["is_stale"]),
            fallback_used=bool(snapshot_data["fallback_used"]),
            data_quality_score=float(snapshot_data["data_quality_score"]),
            raw_payload_ref=self._optional_string(snapshot_data.get("raw_payload_ref")),
        )

    def _deserialize_dqs_result(
        self,
        dqs_result_data: Mapping[str, Any],
    ) -> DataQualityScoreResult:
        if not isinstance(dqs_result_data, Mapping):
            raise TypeError("snapshot replay payload dqs_result must be a mapping.")

        component_scores = dqs_result_data.get("component_scores")
        if not isinstance(component_scores, Mapping):
            raise TypeError("snapshot replay payload component_scores must be a mapping.")

        return DataQualityScoreResult(
            total_score=float(dqs_result_data["total_score"]),
            decision=DataQualityDecision(str(dqs_result_data["decision"])),
            component_scores={
                str(component_name): float(component_score)
                for component_name, component_score in component_scores.items()
            },
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if not isinstance(value, str):
            raise TypeError("snapshot replay timestamps must be ISO8601 strings.")

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _normalize_datetime_string(self, value: Any) -> str:
        return self._parse_datetime(value).isoformat()

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _normalize_source_observations(
        source_observations: Mapping[str, Any],
    ) -> dict[str, str]:
        return {
            str(source_id): str(observed_at)
            for source_id, observed_at in source_observations.items()
        }

    @staticmethod
    def _normalize_mapping(value: Any) -> dict[str, object]:
        if not isinstance(value, Mapping):
            return {}
        return {
            str(key): item
            for key, item in value.items()
        }

    def _normalize_optional_mapping(self, value: Any) -> dict[str, object] | None:
        if value is None:
            return None
        return self._normalize_mapping(value)

    def _extract_replay_regime(
        self,
        snapshot_payload: Mapping[str, Any],
    ) -> str | None:
        candidate_values = (
            snapshot_payload.get("replay_regime"),
            snapshot_payload.get("regime"),
            self._read_nested_mapping_value(snapshot_payload.get("audit_source_payload"), "replay_regime"),
            self._read_nested_mapping_value(snapshot_payload.get("audit_source_payload"), "regime"),
        )
        for candidate_value in candidate_values:
            if isinstance(candidate_value, str) and candidate_value.strip():
                return candidate_value.strip()
        return None

    def _build_replay_regime_diagnostic(
        self,
        snapshot_payload: Mapping[str, Any],
    ) -> str | None:
        replay_regime = self._extract_replay_regime(snapshot_payload)
        if replay_regime is not None:
            return None

        candidate_values = (
            snapshot_payload.get("replay_regime"),
            snapshot_payload.get("regime"),
            self._read_nested_mapping_value(snapshot_payload.get("audit_source_payload"), "replay_regime"),
            self._read_nested_mapping_value(snapshot_payload.get("audit_source_payload"), "regime"),
        )
        if any(candidate_value is not None for candidate_value in candidate_values):
            return "Saved replay regime metadata was present but malformed."
        return "Saved replay regime metadata was not present."

    @staticmethod
    def _is_paper_safe_replay_result(replay_result: SnapshotReplayResult) -> bool:
        return (
            replay_result.mode in SnapshotStore.ALLOWED_MODES
            and replay_result.execution_mode in SnapshotStore.ALLOWED_EXECUTION_MODES
            and replay_result.decision_permission == "NO_EXECUTION"
            and replay_result.ceo_report.execution_status == "OFF / NO_EXECUTION"
        )

    @staticmethod
    def _read_nested_mapping_value(value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        return None

__all__ = [name for name in globals() if not name.startswith('_')]
