
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Mapping

from app.services.snapshot_replay_core import SnapshotReplayCore
from app.services.snapshot_replay_models import SnapshotFallbackUsageRecurrence
from app.services.snapshot_replay_models import SnapshotFallbackUsageRecurrenceEntry
from app.services.snapshot_replay_models import SnapshotFallbackUsageTimelineEntry
from app.services.snapshot_replay_models import SnapshotNoExecutionGuardrailConsistency
from app.services.snapshot_replay_models import SnapshotNoExecutionGuardrailEntry
from app.services.snapshot_replay_models import SnapshotRawPayloadReferenceCompleteness
from app.services.snapshot_replay_models import SnapshotRawPayloadReferenceCompletenessEntry
from app.services.snapshot_replay_models import SnapshotReplayResult
from app.services.snapshot_replay_models import SnapshotSourceFreshnessDecayTimeline
from app.services.snapshot_replay_models import SnapshotSourceFreshnessDecayTimelineEntry
from app.services.snapshot_replay_models import SnapshotSourceGapRecurrenceEntry
from app.services.snapshot_replay_models import SnapshotSourceGapRecurrenceLeaderboard
from app.services.snapshot_replay_models import SnapshotSourceObservationCadenceDrift
from app.services.snapshot_replay_models import SnapshotSourceObservationCadenceEntry
from app.services.snapshot_replay_models import SnapshotSourceDecisionUsageConsistency
from app.services.snapshot_replay_models import SnapshotSourceDecisionUsageConsistencyEntry
from app.services.snapshot_replay_models import SnapshotSourceVerificationDrift
from app.services.snapshot_replay_models import SnapshotSourceVerificationDriftEntry
from app.services.snapshot_replay_models import SnapshotPaperSafeSourceFlagConsistency
from app.services.snapshot_replay_models import SnapshotPaperSafeSourceFlagConsistencyEntry
from app.services.snapshot_replay_models import SnapshotSourceObservationSummaryDrift
from app.services.snapshot_replay_models import SnapshotSourceObservationSummaryDriftEntry
from app.services.snapshot_replay_models import SnapshotSourceObservationTimestampIntegrityDrift
from app.services.snapshot_replay_models import SnapshotSourceObservationTimestampIntegrityDriftEntry
from app.services.snapshot_replay_models import SnapshotSourceObservationRecordSummaryReconciliation
from app.services.snapshot_replay_models import SnapshotSourceObservationRecordSummaryReconciliationEntry
from app.services.snapshot_replay_models import SnapshotSourceObservationNormalizationModeDrift
from app.services.snapshot_replay_models import SnapshotSourceObservationNormalizationModeDriftEntry
from app.services.snapshot_replay_models import SnapshotSourceObservationConfidenceDrift
from app.services.snapshot_replay_models import SnapshotSourceObservationConfidenceDriftEntry
from app.services.snapshot_replay_models import SnapshotSourceObservationAvailabilityLagDrift
from app.services.snapshot_replay_models import SnapshotSourceObservationAvailabilityLagDriftEntry
from app.services.snapshot_replay_models import SnapshotMappedAtAlignmentConsistency
from app.services.snapshot_replay_models import SnapshotMappedAtAlignmentConsistencyEntry
from app.services.snapshot_replay_models import SnapshotProviderAdapterContractConsistency
from app.services.snapshot_replay_models import SnapshotProviderAdapterContractConsistencyEntry
from app.services.snapshot_replay_models import SnapshotSourceRegistryBindingDrift
from app.services.snapshot_replay_models import SnapshotSourceRegistryBindingDriftEntry
from app.services.snapshot_replay_models import SnapshotSourceRecordCompleteness
from app.services.snapshot_replay_models import SnapshotSourceRecordCompletenessEntry
from app.services.snapshot_replay_models import SnapshotVerifiedSourceCoverageReconciliation
from app.services.snapshot_replay_models import SnapshotVerifiedSourceCoverageReconciliationEntry
from app.services.snapshot_replay_models import SnapshotSourceFreshnessSummaryReconciliation
from app.services.snapshot_replay_models import SnapshotSourceFreshnessSummaryReconciliationEntry
from app.storage import SnapshotStore
from app.services.trigger_engine import TriggerSeverity

SEVERITY_PRIORITY = {
    TriggerSeverity.INFO: 0,
    TriggerSeverity.YELLOW: 1,
    TriggerSeverity.ORANGE: 2,
    TriggerSeverity.RED: 3,
}

SOURCE_GAP_STATUS_PRIORITY = {
    'stale': 0,
    'missing': 1,
    'mixed': 2,
}

SOURCE_FRESHNESS_STATUS_PRIORITY = {
    'fresh': 0,
    'degraded': 1,
    'stale': 2,
}

ALLOWED_DECISION_USAGES = {
    "simulation_only",
    "verified_required",
}

EXPECTED_PROVIDER_ADAPTER_CONTRACT = "verified_provider_adapter_v1"
VALID_NORMALIZATION_MODES = {
    "batch_stored_at",
    "per_source_stored_at",
}


class SnapshotReplaySourceDiagnostics(SnapshotReplayCore):
    def build_source_freshness_decay_timeline(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceFreshnessDecayTimeline:
        backtest_result, ordered_replay_results = self._run_ordered_backtest(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_freshness_decay_timeline(
            ordered_replay_results,
            failure_count=backtest_result.failed_replays,
        )

    def build_fallback_usage_recurrence(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotFallbackUsageRecurrence:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_fallback_usage_recurrence(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_raw_payload_reference_completeness(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotRawPayloadReferenceCompleteness:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_raw_payload_reference_completeness(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_cadence_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationCadenceDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_cadence_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_record_completeness(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceRecordCompleteness:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_record_completeness(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_registry_binding_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceRegistryBindingDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_registry_binding_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_decision_usage_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceDecisionUsageConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_decision_usage_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_verification_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceVerificationDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_verification_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_paper_safe_source_flag_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotPaperSafeSourceFlagConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_paper_safe_source_flag_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_summary_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationSummaryDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_summary_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_provider_adapter_contract_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotProviderAdapterContractConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_provider_adapter_contract_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_timestamp_integrity_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationTimestampIntegrityDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_timestamp_integrity_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_record_summary_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationRecordSummaryReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_record_summary_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_normalization_mode_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationNormalizationModeDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_normalization_mode_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_mapped_at_alignment_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotMappedAtAlignmentConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_mapped_at_alignment_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_confidence_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationConfidenceDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_confidence_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_verified_source_coverage_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotVerifiedSourceCoverageReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_verified_source_coverage_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_observation_availability_lag_drift(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceObservationAvailabilityLagDrift:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_observation_availability_lag_drift(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_source_freshness_summary_reconciliation(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotSourceFreshnessSummaryReconciliation:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_source_freshness_summary_reconciliation(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def build_no_execution_guardrail_consistency(
        self,
        *,
        snapshot_ids: tuple[str, ...] | list[str] | None = None,
        limit: int = 10,
        report_type: str | None = None,
    ) -> SnapshotNoExecutionGuardrailConsistency:
        snapshot_payloads, failures, total_requested = self._load_ordered_snapshot_payloads(
            snapshot_ids=snapshot_ids,
            limit=limit,
            report_type=report_type,
        )
        return self._build_no_execution_guardrail_consistency(
            snapshot_payloads,
            total_snapshots_requested=total_requested,
            failures=failures,
        )

    def _build_source_gap_recurrence_leaderboard(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
    ) -> SnapshotSourceGapRecurrenceLeaderboard:
        diagnostics: list[str] = []
        total_snapshots = len(replay_results)
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for source gap recurrence analysis.")
            return SnapshotSourceGapRecurrenceLeaderboard(
                total_entries=0,
                total_snapshots=0,
                entries=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        buckets: dict[str, dict[str, object]] = {}
        streaks: dict[str, int] = {}
        seen_sources: set[str] = set()

        for replay_result in replay_results:
            active_sources: dict[str, str] = {}
            for source_id in replay_result.missing_sources:
                active_sources[source_id] = "missing"
            for source_id in replay_result.stale_sources:
                if source_id in active_sources and active_sources[source_id] != "stale":
                    active_sources[source_id] = "mixed"
                elif source_id not in active_sources:
                    active_sources[source_id] = "stale"

            active_source_ids = set(active_sources)
            for source_id in sorted(seen_sources - active_source_ids):
                streaks[source_id] = 0

            for source_id, gap_status in active_sources.items():
                severity = TriggerSeverity.ORANGE if gap_status in {"missing", "mixed"} else TriggerSeverity.YELLOW
                bucket = buckets.setdefault(
                    source_id,
                    {
                        "gap_statuses": set(),
                        "severity": severity,
                        "occurrence_count": 0,
                        "longest_streak": 0,
                        "first_snapshot_id": replay_result.snapshot_id,
                        "latest_snapshot_id": replay_result.snapshot_id,
                        "affected_snapshot_ids": [],
                    },
                )
                bucket["gap_statuses"].add(gap_status)
                bucket["occurrence_count"] = int(bucket["occurrence_count"]) + 1
                bucket["latest_snapshot_id"] = replay_result.snapshot_id
                bucket["affected_snapshot_ids"].append(replay_result.snapshot_id)
                if SEVERITY_PRIORITY[severity] > SEVERITY_PRIORITY[bucket["severity"]]:
                    bucket["severity"] = severity

                current_streak = streaks.get(source_id, 0) + 1
                streaks[source_id] = current_streak
                if current_streak > int(bucket["longest_streak"]):
                    bucket["longest_streak"] = current_streak

            seen_sources.update(active_source_ids)

        if not buckets:
            diagnostics.append("No missing or stale source gaps were found in the requested saved snapshots.")
            return SnapshotSourceGapRecurrenceLeaderboard(
                total_entries=0,
                total_snapshots=total_snapshots,
                entries=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        leaderboard_entries: list[SnapshotSourceGapRecurrenceEntry] = []
        for source_id, bucket in buckets.items():
            gap_statuses = bucket["gap_statuses"]
            if "mixed" in gap_statuses or len(gap_statuses) > 1:
                gap_status = "mixed"
            elif "missing" in gap_statuses:
                gap_status = "missing"
            else:
                gap_status = "stale"

            occurrence_count = int(bucket["occurrence_count"])
            longest_streak = int(bucket["longest_streak"])
            if occurrence_count == total_snapshots and total_snapshots > 1:
                recurrence_classification = "persistent"
            elif longest_streak >= 2:
                recurrence_classification = "recurring"
            else:
                recurrence_classification = "intermittent"

            leaderboard_entries.append(
                SnapshotSourceGapRecurrenceEntry(
                    rank=0,
                    source_id=source_id,
                    gap_status=gap_status,
                    severity=bucket["severity"],
                    recurrence_classification=recurrence_classification,
                    occurrence_count=occurrence_count,
                    recurrence_ratio=round(occurrence_count / total_snapshots, 4),
                    longest_streak=longest_streak,
                    first_snapshot_id=str(bucket["first_snapshot_id"]),
                    latest_snapshot_id=str(bucket["latest_snapshot_id"]),
                    affected_snapshot_ids=tuple(bucket["affected_snapshot_ids"]),
                )
            )

        ranked_entries = tuple(
            SnapshotSourceGapRecurrenceEntry(
                rank=index,
                source_id=entry.source_id,
                gap_status=entry.gap_status,
                severity=entry.severity,
                recurrence_classification=entry.recurrence_classification,
                occurrence_count=entry.occurrence_count,
                recurrence_ratio=entry.recurrence_ratio,
                longest_streak=entry.longest_streak,
                first_snapshot_id=entry.first_snapshot_id,
                latest_snapshot_id=entry.latest_snapshot_id,
                affected_snapshot_ids=entry.affected_snapshot_ids,
            )
            for index, entry in enumerate(
                sorted(
                    leaderboard_entries,
                    key=lambda item: (
                        -item.occurrence_count,
                        -item.longest_streak,
                        -SEVERITY_PRIORITY[item.severity],
                        -SOURCE_GAP_STATUS_PRIORITY[item.gap_status],
                        item.source_id,
                    ),
                ),
                start=1,
            )
        )

        diagnostics.append(
            f"Source gap recurrence leaderboard covers {total_snapshots} saved snapshot(s) and {len(ranked_entries)} gap source(s)."
        )

        return SnapshotSourceGapRecurrenceLeaderboard(
            total_entries=len(ranked_entries),
            total_snapshots=total_snapshots,
            entries=ranked_entries,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_freshness_decay_timeline(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
        *,
        failure_count: int = 0,
    ) -> SnapshotSourceFreshnessDecayTimeline:
        diagnostics: list[str] = []
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for source freshness decay analysis.")
            if failure_count > 0:
                diagnostics.append(
                    f"{failure_count} snapshot replay(s) failed during source freshness decay analysis."
                )
            return SnapshotSourceFreshnessDecayTimeline(
                decay_classification="insufficient_data",
                total_snapshots=0,
                evaluable_snapshots=0,
                missing_freshness_snapshots=0,
                first_status=None,
                latest_status=None,
                dominant_status=None,
                worst_status=None,
                transition_count=0,
                decay_score_delta=0,
                entries=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceFreshnessDecayTimelineEntry] = []
        evaluable_entries: list[SnapshotSourceFreshnessDecayTimelineEntry] = []
        missing_freshness_snapshots = 0

        for replay_result in replay_results:
            try:
                from registry import build_source_freshness_diagnostics

                freshness_diagnostics = build_source_freshness_diagnostics(
                    source_observations=replay_result.source_observations,
                    as_of_utc=self._parse_datetime(replay_result.created_at),
                )
            except Exception as exc:
                missing_freshness_snapshots += 1
                entries.append(
                    SnapshotSourceFreshnessDecayTimelineEntry(
                        snapshot_id=replay_result.snapshot_id,
                        created_at=replay_result.created_at,
                        freshness_status="missing_freshness",
                        fresh_source_count=0,
                        stale_source_count=0,
                        missing_timestamp_source_count=0,
                        degraded_source_count=0,
                        total_active_sources=0,
                        decay_score=None,
                        diagnostic=f"Freshness diagnostics could not be evaluated safely: {str(exc) or exc.__class__.__name__}",
                    )
                )
                continue

            summary = freshness_diagnostics["summary"]
            fresh_source_count = int(summary["fresh_sources"])
            stale_source_count = int(summary["stale_sources"])
            missing_timestamp_source_count = int(summary["sources_missing_timestamps"])
            total_active_sources = int(summary["total_active_sources"])
            degraded_source_count = stale_source_count + missing_timestamp_source_count
            decay_score = stale_source_count * 2 + missing_timestamp_source_count

            if stale_source_count > 0:
                freshness_status = "stale"
                diagnostic = (
                    f"{stale_source_count} source(s) breached freshness policy and "
                    f"{missing_timestamp_source_count} source(s) missed timestamps."
                )
            elif missing_timestamp_source_count > 0:
                freshness_status = "degraded"
                diagnostic = (
                    f"{missing_timestamp_source_count} active source timestamp(s) were missing at replay time."
                )
            else:
                freshness_status = "fresh"
                diagnostic = "All active sources satisfied freshness policy at replay time."

            entry = SnapshotSourceFreshnessDecayTimelineEntry(
                snapshot_id=replay_result.snapshot_id,
                created_at=replay_result.created_at,
                freshness_status=freshness_status,
                fresh_source_count=fresh_source_count,
                stale_source_count=stale_source_count,
                missing_timestamp_source_count=missing_timestamp_source_count,
                degraded_source_count=degraded_source_count,
                total_active_sources=total_active_sources,
                decay_score=decay_score,
                diagnostic=diagnostic,
            )
            entries.append(entry)
            evaluable_entries.append(entry)

        if len(evaluable_entries) < 2:
            diagnostics.append(
                "At least two replayable snapshots with evaluable source freshness data are required."
            )
            if missing_freshness_snapshots > 0:
                diagnostics.append(
                    f"{missing_freshness_snapshots} snapshot(s) had missing or malformed freshness inputs."
                )
            if failure_count > 0:
                diagnostics.append(
                    f"{failure_count} snapshot replay(s) failed during source freshness decay analysis."
                )
            return SnapshotSourceFreshnessDecayTimeline(
                decay_classification="insufficient_data",
                total_snapshots=len(entries),
                evaluable_snapshots=len(evaluable_entries),
                missing_freshness_snapshots=missing_freshness_snapshots,
                first_status=evaluable_entries[0].freshness_status if evaluable_entries else None,
                latest_status=evaluable_entries[-1].freshness_status if evaluable_entries else None,
                dominant_status=evaluable_entries[0].freshness_status if evaluable_entries else None,
                worst_status=evaluable_entries[0].freshness_status if evaluable_entries else None,
                transition_count=0,
                decay_score_delta=0,
                entries=tuple(entries),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        first_entry = evaluable_entries[0]
        latest_entry = evaluable_entries[-1]
        decay_score_delta = int(latest_entry.decay_score or 0) - int(first_entry.decay_score or 0)
        transition_count = sum(
            1
            for index in range(1, len(evaluable_entries))
            if (
                evaluable_entries[index].decay_score != evaluable_entries[index - 1].decay_score
                or evaluable_entries[index].freshness_status
                != evaluable_entries[index - 1].freshness_status
            )
        )
        status_counts = Counter(entry.freshness_status for entry in evaluable_entries)
        dominant_status = sorted(
            status_counts.items(),
            key=lambda item: (-item[1], SOURCE_FRESHNESS_STATUS_PRIORITY[item[0]], item[0]),
        )[0][0]
        worst_status = max(
            (entry.freshness_status for entry in evaluable_entries),
            key=lambda status: SOURCE_FRESHNESS_STATUS_PRIORITY[status],
        )

        if decay_score_delta > 0:
            decay_classification = "degrading"
            diagnostics.append(
                f"Source freshness deteriorated from {first_entry.freshness_status} to {latest_entry.freshness_status} across saved snapshots."
            )
        elif decay_score_delta < 0:
            decay_classification = "improving"
            diagnostics.append(
                f"Source freshness improved from {first_entry.freshness_status} to {latest_entry.freshness_status} across saved snapshots."
            )
        else:
            decay_classification = "stable"
            diagnostics.append(
                f"Source freshness remained in a stable {latest_entry.freshness_status} band across {len(evaluable_entries)} evaluable saved snapshot(s)."
            )

        if missing_freshness_snapshots > 0:
            diagnostics.append(
                f"{missing_freshness_snapshots} snapshot(s) had missing or malformed freshness inputs."
            )
        if failure_count > 0:
            diagnostics.append(
                f"{failure_count} snapshot replay(s) failed during source freshness decay analysis."
            )

        return SnapshotSourceFreshnessDecayTimeline(
            decay_classification=decay_classification,
            total_snapshots=len(entries),
            evaluable_snapshots=len(evaluable_entries),
            missing_freshness_snapshots=missing_freshness_snapshots,
            first_status=first_entry.freshness_status,
            latest_status=latest_entry.freshness_status,
            dominant_status=dominant_status,
            worst_status=worst_status,
            transition_count=transition_count,
            decay_score_delta=decay_score_delta,
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_fallback_usage_recurrence(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotFallbackUsageRecurrence:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for fallback usage recurrence analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during fallback usage analysis."
                )
            return SnapshotFallbackUsageRecurrence(
                stability_classification="insufficient_data",
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                snapshots_with_fallback=0,
                total_fallback_events=0,
                unique_fallback_providers=0,
                malformed_snapshot_count=0,
                missing_provider_metadata_count=0,
                timeline=(),
                recurring_entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        timeline: list[SnapshotFallbackUsageTimelineEntry] = []
        provider_buckets: dict[str, dict[str, object]] = {}
        total_fallback_events = 0
        snapshots_with_fallback = 0
        malformed_snapshot_count = 0
        missing_provider_metadata_count = 0

        for snapshot_index, snapshot_payload in enumerate(snapshot_payloads):
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            serialized_snapshots = snapshot_payload.get("snapshots")
            if not isinstance(serialized_snapshots, list):
                malformed_snapshot_count += 1
                timeline.append(
                    SnapshotFallbackUsageTimelineEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        status="critical",
                        fallback_event_count=0,
                        fallback_provider_count=0,
                        affected_providers=(),
                        affected_assets=(),
                        severity_score=100,
                        diagnostic="Fallback usage diagnostics could not be evaluated because snapshot records were malformed.",
                    )
                )
                continue

            fallback_event_count = 0
            snapshot_malformed_records = 0
            snapshot_missing_provider_metadata = 0
            affected_providers: set[str] = set()
            affected_assets: set[str] = set()
            providers_in_snapshot: set[str] = set()

            for record_index, snapshot_record in enumerate(serialized_snapshots):
                if not isinstance(snapshot_record, Mapping):
                    snapshot_malformed_records += 1
                    continue

                if not bool(snapshot_record.get("fallback_used")):
                    continue

                fallback_event_count += 1
                total_fallback_events += 1

                raw_provider_name = snapshot_record.get("source_name")
                if isinstance(raw_provider_name, str) and raw_provider_name.strip():
                    provider_name = raw_provider_name.strip()
                else:
                    provider_name = "unknown_provider"
                    snapshot_missing_provider_metadata += 1
                    missing_provider_metadata_count += 1

                raw_asset_symbol = snapshot_record.get("asset_symbol")
                if isinstance(raw_asset_symbol, str) and raw_asset_symbol.strip():
                    asset_symbol = raw_asset_symbol.strip()
                else:
                    asset_symbol = f"UNKNOWN_ASSET_{record_index}"

                affected_providers.add(provider_name)
                affected_assets.add(asset_symbol)
                providers_in_snapshot.add(provider_name)

                provider_bucket = provider_buckets.setdefault(
                    provider_name,
                    {
                        "occurrence_count": 0,
                        "indices": [],
                        "snapshot_ids": [],
                        "assets": set(),
                        "missing_provider_metadata_count": 0,
                    },
                )
                if snapshot_id not in provider_bucket["snapshot_ids"]:
                    provider_bucket["occurrence_count"] += 1
                    provider_bucket["indices"].append(snapshot_index)
                    provider_bucket["snapshot_ids"].append(snapshot_id)
                provider_bucket["assets"].add(asset_symbol)
                provider_bucket["missing_provider_metadata_count"] += int(provider_name == "unknown_provider")

            if fallback_event_count > 0:
                snapshots_with_fallback += 1

            severity_score = min(
                100,
                fallback_event_count * 25
                + snapshot_missing_provider_metadata * 25
                + snapshot_malformed_records * 35,
            )
            if snapshot_malformed_records > 0 or snapshot_missing_provider_metadata > 0:
                status = "critical"
            elif fallback_event_count >= 2:
                status = "critical"
            elif fallback_event_count == 1:
                status = "elevated"
            else:
                status = "stable"

            if snapshot_malformed_records > 0:
                malformed_snapshot_count += 1
                diagnostic = (
                    f"Fallback usage diagnostics encountered {snapshot_malformed_records} malformed snapshot record(s)."
                )
            elif snapshot_missing_provider_metadata > 0:
                diagnostic = (
                    f"{snapshot_missing_provider_metadata} fallback event(s) had missing provider metadata."
                )
            elif fallback_event_count > 0:
                diagnostic = (
                    f"Fallback providers were used for {fallback_event_count} snapshot record(s) in this saved payload."
                )
            else:
                diagnostic = "No fallback providers were used in this saved payload."

            timeline.append(
                SnapshotFallbackUsageTimelineEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    status=status,
                    fallback_event_count=fallback_event_count,
                    fallback_provider_count=len(providers_in_snapshot),
                    affected_providers=tuple(sorted(affected_providers)),
                    affected_assets=tuple(sorted(affected_assets)),
                    severity_score=severity_score,
                    diagnostic=diagnostic,
                )
            )

        recurring_entries: list[SnapshotFallbackUsageRecurrenceEntry] = []
        snapshots_checked = len(timeline)
        for provider_name, provider_bucket in provider_buckets.items():
            occurrence_count = int(provider_bucket["occurrence_count"])
            indices = sorted(int(index) for index in provider_bucket["indices"])
            longest_streak = 0
            current_streak = 0
            previous_index: int | None = None
            for index in indices:
                if previous_index is None or index == previous_index + 1:
                    current_streak += 1
                else:
                    current_streak = 1
                longest_streak = max(longest_streak, current_streak)
                previous_index = index

            recurrence_ratio = round(
                occurrence_count / snapshots_checked,
                2,
            ) if snapshots_checked else 0.0
            provider_missing_metadata_count = int(provider_bucket["missing_provider_metadata_count"])
            severity_score = min(
                100,
                occurrence_count * 20 + longest_streak * 15 + provider_missing_metadata_count * 25,
            )
            if provider_missing_metadata_count > 0 or occurrence_count >= 3 or recurrence_ratio >= 0.75:
                recurrence_classification = "critical"
            elif occurrence_count >= 2 or longest_streak >= 2 or recurrence_ratio >= 0.5:
                recurrence_classification = "elevated"
            else:
                recurrence_classification = "stable"

            recurring_entries.append(
                SnapshotFallbackUsageRecurrenceEntry(
                    rank=0,
                    provider_name=provider_name,
                    recurrence_classification=recurrence_classification,
                    severity_score=severity_score,
                    occurrence_count=occurrence_count,
                    recurrence_ratio=recurrence_ratio,
                    longest_streak=longest_streak,
                    affected_snapshot_ids=tuple(provider_bucket["snapshot_ids"]),
                    affected_assets=tuple(sorted(provider_bucket["assets"])),
                    missing_provider_metadata_count=provider_missing_metadata_count,
                )
            )

        ranked_entries = tuple(
            SnapshotFallbackUsageRecurrenceEntry(
                rank=index,
                provider_name=entry.provider_name,
                recurrence_classification=entry.recurrence_classification,
                severity_score=entry.severity_score,
                occurrence_count=entry.occurrence_count,
                recurrence_ratio=entry.recurrence_ratio,
                longest_streak=entry.longest_streak,
                affected_snapshot_ids=entry.affected_snapshot_ids,
                affected_assets=entry.affected_assets,
                missing_provider_metadata_count=entry.missing_provider_metadata_count,
            )
            for index, entry in enumerate(
                sorted(
                    recurring_entries,
                    key=lambda item: (
                        -item.occurrence_count,
                        -item.longest_streak,
                        -item.severity_score,
                        item.provider_name,
                    ),
                ),
                start=1,
            )
        )

        if snapshots_checked < 2:
            stability_classification = "insufficient_data"
            diagnostics.append("At least two saved snapshots are required to evaluate fallback usage recurrence.")
        elif malformed_snapshot_count > 0 or missing_provider_metadata_count > 0:
            stability_classification = "critical"
            diagnostics.append(
                f"Fallback usage recurrence is critical across {snapshots_checked} saved snapshot(s)."
            )
        elif total_fallback_events > 0:
            stability_classification = "elevated"
            diagnostics.append(
                f"Fallback usage recurrence is elevated across {snapshots_checked} saved snapshot(s)."
            )
        else:
            stability_classification = "stable"
            diagnostics.append(
                f"No fallback provider usage was detected across {snapshots_checked} saved snapshot(s)."
            )

        if malformed_snapshot_count > 0:
            diagnostics.append(
                f"{malformed_snapshot_count} saved snapshot(s) contained malformed fallback usage records."
            )
        if missing_provider_metadata_count > 0:
            diagnostics.append(
                f"{missing_provider_metadata_count} fallback event(s) had missing provider metadata."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during fallback usage analysis."
            )

        severity_score = min(
            100,
            total_fallback_events * 15
            + len(ranked_entries) * 10
            + malformed_snapshot_count * 20
            + missing_provider_metadata_count * 20,
        )

        return SnapshotFallbackUsageRecurrence(
            stability_classification=stability_classification,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            snapshots_with_fallback=snapshots_with_fallback,
            total_fallback_events=total_fallback_events,
            unique_fallback_providers=len(ranked_entries),
            malformed_snapshot_count=malformed_snapshot_count,
            missing_provider_metadata_count=missing_provider_metadata_count,
            timeline=tuple(timeline),
            recurring_entries=ranked_entries,
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_raw_payload_reference_completeness(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotRawPayloadReferenceCompleteness:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for raw payload reference completeness analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during raw payload reference analysis."
                )
            return SnapshotRawPayloadReferenceCompleteness(
                completeness_classification="invalid",
                average_completeness_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                complete_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_reference_assets=(),
                empty_reference_assets=(),
                malformed_reference_assets=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotRawPayloadReferenceCompletenessEntry] = []
        aggregate_missing_assets: set[str] = set()
        aggregate_empty_assets: set[str] = set()
        aggregate_malformed_assets: set[str] = set()
        complete_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            serialized_snapshots = snapshot_payload.get("snapshots")
            if not isinstance(serialized_snapshots, list) or not serialized_snapshots:
                invalid_snapshots += 1
                entries.append(
                    SnapshotRawPayloadReferenceCompletenessEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        completeness_classification="invalid",
                        completeness_percentage=0.0,
                        total_records=0,
                        complete_records=0,
                        partial_reference_assets=(),
                        missing_reference_assets=(),
                        empty_reference_assets=(),
                        malformed_reference_assets=("SNAPSHOT_RECORDS",),
                        diagnostic="Raw payload reference completeness could not be evaluated because snapshot records were missing or malformed.",
                    )
                )
                aggregate_malformed_assets.add("SNAPSHOT_RECORDS")
                continue

            total_records = 0
            complete_records = 0
            partial_reference_assets: set[str] = set()
            missing_reference_assets: set[str] = set()
            empty_reference_assets: set[str] = set()
            malformed_reference_assets: set[str] = set()

            for record_index, snapshot_record in enumerate(serialized_snapshots):
                total_records += 1
                if not isinstance(snapshot_record, Mapping):
                    malformed_reference_assets.add(f"UNKNOWN_RECORD_{record_index}")
                    continue

                raw_asset_symbol = snapshot_record.get("asset_symbol")
                if isinstance(raw_asset_symbol, str) and raw_asset_symbol.strip():
                    asset_symbol = raw_asset_symbol.strip()
                else:
                    asset_symbol = f"UNKNOWN_ASSET_{record_index}"

                if "raw_payload_ref" not in snapshot_record or snapshot_record.get("raw_payload_ref") is None:
                    missing_reference_assets.add(asset_symbol)
                    continue

                raw_payload_ref = snapshot_record.get("raw_payload_ref")
                if not isinstance(raw_payload_ref, str):
                    malformed_reference_assets.add(asset_symbol)
                    continue

                normalized_payload_ref = raw_payload_ref.strip()
                if not normalized_payload_ref:
                    empty_reference_assets.add(asset_symbol)
                    continue

                scheme, separator, remainder = normalized_payload_ref.partition("://")
                if not separator:
                    malformed_reference_assets.add(asset_symbol)
                    continue
                if not scheme.strip():
                    malformed_reference_assets.add(asset_symbol)
                    continue
                if not remainder.strip():
                    partial_reference_assets.add(asset_symbol)
                    continue

                complete_records += 1

            completeness_percentage = round(
                (complete_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if malformed_reference_assets:
                completeness_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Malformed raw payload references were detected for {len(malformed_reference_assets)} asset record(s)."
                )
            elif complete_records == total_records:
                completeness_classification = "complete"
                complete_snapshots += 1
                diagnostic = "All snapshot records preserved a usable raw payload reference."
            elif completeness_percentage >= 70.0:
                completeness_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    f"Raw payload references were partially complete for {complete_records} of {total_records} snapshot record(s)."
                )
            else:
                completeness_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    f"Raw payload references were degraded for {total_records - complete_records} of {total_records} snapshot record(s)."
                )

            aggregate_missing_assets.update(missing_reference_assets)
            aggregate_empty_assets.update(empty_reference_assets)
            aggregate_malformed_assets.update(malformed_reference_assets)
            entries.append(
                SnapshotRawPayloadReferenceCompletenessEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    completeness_classification=completeness_classification,
                    completeness_percentage=completeness_percentage,
                    total_records=total_records,
                    complete_records=complete_records,
                    partial_reference_assets=tuple(sorted(partial_reference_assets)),
                    missing_reference_assets=tuple(sorted(missing_reference_assets)),
                    empty_reference_assets=tuple(sorted(empty_reference_assets)),
                    malformed_reference_assets=tuple(sorted(malformed_reference_assets)),
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            completeness_classification = "invalid"
        elif degraded_snapshots > 0:
            completeness_classification = "degraded"
        elif partial_snapshots > 0:
            completeness_classification = "partial"
        else:
            completeness_classification = "complete"

        average_completeness_percentage = round(
            sum(entry.completeness_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Raw payload reference completeness is {completeness_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_assets:
            diagnostics.append(
                f"{len(aggregate_missing_assets)} asset symbol(s) were missing raw payload references."
            )
        if aggregate_empty_assets:
            diagnostics.append(
                f"{len(aggregate_empty_assets)} asset symbol(s) contained empty raw payload references."
            )
        if aggregate_malformed_assets:
            diagnostics.append(
                f"{len(aggregate_malformed_assets)} asset symbol(s) contained malformed raw payload references."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during raw payload reference analysis."
            )

        return SnapshotRawPayloadReferenceCompleteness(
            completeness_classification=completeness_classification,
            average_completeness_percentage=average_completeness_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            complete_snapshots=complete_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_reference_assets=tuple(sorted(aggregate_missing_assets)),
            empty_reference_assets=tuple(sorted(aggregate_empty_assets)),
            malformed_reference_assets=tuple(sorted(aggregate_malformed_assets)),
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_cadence_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationCadenceDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source observation cadence analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation cadence analysis."
                )
            return SnapshotSourceObservationCadenceDrift(
                cadence_classification="insufficient_data",
                cadence_score=0,
                severity_bucket="NONE",
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                evaluable_snapshots=0,
                missing_timestamp_snapshots=0,
                transition_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        raw_entries: list[dict[str, object]] = []
        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observations = snapshot_payload.get("source_observations")
            if not isinstance(source_observations, Mapping):
                raw_entries.append(
                    {
                        "snapshot_id": snapshot_id,
                        "created_at": created_at,
                        "anchor_observed_at": None,
                        "observed_source_count": 0,
                        "missing_timestamp_source_count": 0,
                    }
                )
                continue

            parsed_timestamps: list[datetime] = []
            missing_timestamp_source_count = 0
            for observed_at in source_observations.values():
                try:
                    parsed_timestamps.append(self._parse_datetime(observed_at))
                except Exception:
                    missing_timestamp_source_count += 1

            anchor_observed_at = max(parsed_timestamps) if parsed_timestamps else None
            raw_entries.append(
                {
                    "snapshot_id": snapshot_id,
                    "created_at": created_at,
                    "anchor_observed_at": anchor_observed_at,
                    "observed_source_count": len(parsed_timestamps),
                    "missing_timestamp_source_count": missing_timestamp_source_count,
                }
            )

        evaluable_indices = [
            index
            for index, raw_entry in enumerate(raw_entries)
            if raw_entry["anchor_observed_at"] is not None
        ]
        intervals_by_index: dict[int, int] = {}
        interval_values: list[int] = []

        previous_index: int | None = None
        for current_index in evaluable_indices:
            if previous_index is None:
                previous_index = current_index
                continue

            previous_anchor = raw_entries[previous_index]["anchor_observed_at"]
            current_anchor = raw_entries[current_index]["anchor_observed_at"]
            interval_seconds = max(
                0,
                int((current_anchor - previous_anchor).total_seconds()),
            )
            intervals_by_index[current_index] = interval_seconds
            interval_values.append(interval_seconds)
            previous_index = current_index

        positive_intervals = [value for value in interval_values if value > 0]
        reference_interval = min(positive_intervals) if positive_intervals else None
        cadence_status_by_index: dict[int, str] = {}

        for current_index in evaluable_indices:
            if current_index not in intervals_by_index:
                cadence_status_by_index[current_index] = "baseline"
                continue

            interval_seconds = intervals_by_index[current_index]
            if reference_interval is None:
                cadence_status_by_index[current_index] = "stable"
                continue

            interval_ratio = interval_seconds / reference_interval if reference_interval else 0.0
            if interval_seconds <= 0 or interval_ratio > 3.0:
                cadence_status_by_index[current_index] = "degraded"
            elif interval_ratio > 1.5 or interval_ratio < 0.5:
                cadence_status_by_index[current_index] = "irregular"
            else:
                cadence_status_by_index[current_index] = "stable"

        entries: list[SnapshotSourceObservationCadenceEntry] = []
        evaluable_snapshots = 0
        missing_timestamp_snapshots = 0

        for index, raw_entry in enumerate(raw_entries):
            anchor_observed_at = raw_entry["anchor_observed_at"]
            missing_timestamp_source_count = int(raw_entry["missing_timestamp_source_count"])
            observed_source_count = int(raw_entry["observed_source_count"])
            if anchor_observed_at is None:
                cadence_status = "missing_timestamps"
                cadence_score = None
                diagnostic = "Source observation timestamps were missing or malformed in this saved snapshot."
                missing_timestamp_snapshots += 1
            else:
                evaluable_snapshots += 1
                cadence_status = cadence_status_by_index.get(index, "stable")
                interval_seconds = intervals_by_index.get(index)
                if cadence_status == "baseline":
                    cadence_score = 100
                    diagnostic = "Cadence baseline established from persisted source observation timestamps."
                elif cadence_status == "stable":
                    cadence_score = 100
                    diagnostic = (
                        f"Source observation cadence matched the stable band at {interval_seconds} second(s)."
                    )
                elif cadence_status == "irregular":
                    cadence_score = 65
                    diagnostic = (
                        f"Source observation cadence deviated from the stable band with a {interval_seconds}-second interval."
                    )
                else:
                    cadence_score = 35
                    if interval_seconds == 0:
                        diagnostic = "Source observation cadence did not advance between saved snapshots."
                    else:
                        diagnostic = (
                            f"Source observation cadence gap widened to {interval_seconds} second(s)."
                        )

            entries.append(
                SnapshotSourceObservationCadenceEntry(
                    snapshot_id=str(raw_entry["snapshot_id"]),
                    created_at=str(raw_entry["created_at"]),
                    cadence_status=cadence_status,
                    anchor_observed_at=(
                        anchor_observed_at.isoformat()
                        if isinstance(anchor_observed_at, datetime)
                        else None
                    ),
                    observed_source_count=observed_source_count,
                    missing_timestamp_source_count=missing_timestamp_source_count,
                    interval_seconds_from_previous=intervals_by_index.get(index),
                    cadence_score=cadence_score,
                    diagnostic=diagnostic,
                )
            )

        evaluable_statuses = [
            entry.cadence_status
            for entry in entries
            if entry.cadence_status != "missing_timestamps"
        ]
        comparable_statuses = [
            status
            for status in evaluable_statuses
            if status != "baseline"
        ]
        transition_count = sum(
            1
            for index in range(1, len(comparable_statuses))
            if comparable_statuses[index] != comparable_statuses[index - 1]
        )

        if evaluable_snapshots < 2:
            cadence_classification = "insufficient_data"
            cadence_score = 0
            severity_bucket = "NONE"
            diagnostics.append(
                "At least two saved snapshots with valid source observation timestamps are required to evaluate cadence drift."
            )
        elif missing_timestamp_snapshots > 0 or "degraded" in comparable_statuses:
            cadence_classification = "degraded"
            cadence_score = 35
            severity_bucket = "HIGH"
            diagnostics.append(
                "Source observation cadence degraded because one or more saved snapshots contained cadence gaps or missing timestamps."
            )
        elif "irregular" in comparable_statuses:
            cadence_classification = "irregular"
            cadence_score = 65
            severity_bucket = "MEDIUM"
            diagnostics.append(
                "Source observation cadence became irregular across saved snapshots without a hard cadence gap."
            )
        else:
            cadence_classification = "stable"
            cadence_score = 100
            severity_bucket = "NONE"
            diagnostics.append(
                f"Source observation cadence remained stable across {evaluable_snapshots} evaluable saved snapshot(s)."
            )

        if missing_timestamp_snapshots > 0:
            diagnostics.append(
                f"{missing_timestamp_snapshots} snapshot(s) had missing or malformed source observation timestamps."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation cadence analysis."
            )

        return SnapshotSourceObservationCadenceDrift(
            cadence_classification=cadence_classification,
            cadence_score=cadence_score,
            severity_bucket=severity_bucket,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=len(entries),
            evaluable_snapshots=evaluable_snapshots,
            missing_timestamp_snapshots=missing_timestamp_snapshots,
            transition_count=transition_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_record_completeness(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceRecordCompleteness:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source record completeness analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source record completeness analysis."
                )
            return SnapshotSourceRecordCompleteness(
                completeness_classification="invalid",
                average_completeness_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                complete_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                aggregate_missing_field_counts={},
                malformed_record_count=0,
                missing_field_diagnostics=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        core_required_fields = (
            "source_id",
            "asset_symbol",
            "registry_provider",
            "observed_at",
            "available_at",
            "stored_at",
            "mapped_at",
            "verified",
            "decision_usage",
            "paper_safe",
        )
        timestamp_fields = {"observed_at", "available_at", "stored_at", "mapped_at"}
        optional_metadata_fields = (
            "value",
            "confidence",
            "freshness_seconds",
            "freshness_status",
        )

        entries: list[SnapshotSourceRecordCompletenessEntry] = []
        aggregate_missing_field_counts: Counter[str] = Counter()
        aggregate_missing_field_diagnostics: set[str] = set()
        aggregate_malformed_record_count = 0
        complete_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceRecordCompletenessEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        completeness_classification="invalid",
                        completeness_percentage=0.0,
                        total_records=0,
                        complete_records=0,
                        missing_field_counts={},
                        missing_field_diagnostics=("source_observation_records:missing_or_malformed",),
                        malformed_record_count=1,
                        diagnostic="Source observation records were missing or malformed in this saved snapshot.",
                    )
                )
                aggregate_missing_field_diagnostics.add("source_observation_records:missing_or_malformed")
                continue

            expected_optional_fields = tuple(
                field_name
                for field_name in optional_metadata_fields
                if any(
                    isinstance(record, Mapping) and field_name in record
                    for record in source_observation_records
                )
            )
            required_fields = core_required_fields + expected_optional_fields
            missing_field_counts: Counter[str] = Counter()
            missing_field_diagnostics: list[str] = []
            complete_records = 0
            malformed_record_count = 0

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    missing_field_diagnostics.append(f"record_{record_index}:malformed_record")
                    continue

                record_label = str(
                    record.get("asset_symbol")
                    or record.get("source_id")
                    or f"record_{record_index}"
                )
                record_has_issue = False

                for field_name in required_fields:
                    if field_name not in record or record[field_name] is None:
                        missing_field_counts[field_name] += 1
                        missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                        record_has_issue = True
                        continue

                    value = record[field_name]
                    if field_name in {"source_id", "asset_symbol", "registry_provider", "decision_usage", "freshness_status"}:
                        if not isinstance(value, str) or not value.strip():
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name in timestamp_fields:
                        try:
                            self._parse_datetime(value)
                        except Exception:
                            malformed_record_count += 1
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:malformed")
                            record_has_issue = True
                    elif field_name in {"verified", "paper_safe"}:
                        if not isinstance(value, bool):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name == "value":
                        if not isinstance(value, (int, float)):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name == "confidence":
                        if not isinstance(value, (int, float)):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name == "freshness_seconds":
                        if not isinstance(value, int):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True

                if not record_has_issue:
                    complete_records += 1

            total_records = len(source_observation_records)
            completeness_percentage = round(
                (complete_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                completeness_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Source observation records contained {malformed_record_count} malformed record or timestamp issue(s)."
                )
            elif complete_records == total_records:
                completeness_classification = "complete"
                complete_snapshots += 1
                diagnostic = "All source observation records preserved the required paper-safe fields."
            elif completeness_percentage >= 70.0:
                completeness_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    f"Source observation records were partially complete for {complete_records} of {total_records} record(s)."
                )
            else:
                completeness_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    f"Source observation records were degraded for {total_records - complete_records} of {total_records} record(s)."
                )

            aggregate_missing_field_counts.update(missing_field_counts)
            aggregate_missing_field_diagnostics.update(missing_field_diagnostics)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceRecordCompletenessEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    completeness_classification=completeness_classification,
                    completeness_percentage=completeness_percentage,
                    total_records=total_records,
                    complete_records=complete_records,
                    missing_field_counts=dict(sorted(missing_field_counts.items())),
                    missing_field_diagnostics=tuple(sorted(missing_field_diagnostics)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            completeness_classification = "invalid"
        elif degraded_snapshots > 0:
            completeness_classification = "degraded"
        elif partial_snapshots > 0:
            completeness_classification = "partial"
        else:
            completeness_classification = "complete"

        average_completeness_percentage = round(
            sum(entry.completeness_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Source record completeness is {completeness_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_field_counts:
            diagnostics.append(
                f"Missing-field diagnostics were raised for {sum(aggregate_missing_field_counts.values())} source record field(s)."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source record issue(s) were detected."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source record completeness analysis."
            )

        return SnapshotSourceRecordCompleteness(
            completeness_classification=completeness_classification,
            average_completeness_percentage=average_completeness_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            complete_snapshots=complete_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            aggregate_missing_field_counts=dict(sorted(aggregate_missing_field_counts.items())),
            malformed_record_count=aggregate_malformed_record_count,
            missing_field_diagnostics=tuple(sorted(aggregate_missing_field_diagnostics)),
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_registry_binding_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceRegistryBindingDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source registry binding drift analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source registry binding drift analysis."
                )
            return SnapshotSourceRegistryBindingDrift(
                drift_classification="insufficient_data",
                severity_score=0,
                current_source_registry_version="unknown",
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                registry_version_mismatch_count=0,
                unbound_source_ids=(),
                provider_mismatch_source_ids=(),
                asset_mismatch_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        current_source_registry_version = str(source_registry["version"])
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {
            entry.source_id: entry
            for entry in registry_entries
        }

        entries: list[SnapshotSourceRegistryBindingDriftEntry] = []
        stable_snapshots = 0
        drifting_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        registry_version_mismatch_count = 0
        aggregate_unbound_source_ids: set[str] = set()
        aggregate_provider_mismatch_source_ids: set[str] = set()
        aggregate_asset_mismatch_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            snapshot_source_registry_version = str(
                snapshot_payload.get("source_registry_version", "unknown")
            )
            registry_version_mismatch = (
                snapshot_source_registry_version != current_source_registry_version
            )
            if registry_version_mismatch:
                registry_version_mismatch_count += 1

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceRegistryBindingDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        source_registry_version=snapshot_source_registry_version,
                        registry_version_mismatch=registry_version_mismatch,
                        binding_classification="invalid",
                        total_records=0,
                        matched_records=0,
                        unbound_source_ids=(),
                        provider_mismatch_source_ids=(),
                        asset_mismatch_source_ids=(),
                        malformed_record_count=1,
                        severity_score=100,
                        diagnostic="Source registry binding drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            matched_records = 0
            malformed_record_count = 0
            unbound_source_ids: set[str] = set()
            provider_mismatch_source_ids: set[str] = set()
            asset_mismatch_source_ids: set[str] = set()

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unbound_source_ids.add(source_id)
                    continue

                record_asset_symbol = record.get("asset_symbol")
                if record_asset_symbol != registry_entry.asset.code.value:
                    asset_mismatch_source_ids.add(source_id)

                record_registry_provider = record.get("registry_provider")
                if record_registry_provider != registry_entry.provider:
                    provider_mismatch_source_ids.add(source_id)

                if (
                    source_id not in asset_mismatch_source_ids
                    and source_id not in provider_mismatch_source_ids
                ):
                    matched_records += 1

            severity_score = min(
                100,
                (20 if registry_version_mismatch else 0)
                + len(unbound_source_ids) * 25
                + len(provider_mismatch_source_ids) * 15
                + len(asset_mismatch_source_ids) * 15
                + malformed_record_count * 30,
            )

            if malformed_record_count > 0:
                binding_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Source registry binding drift encountered {malformed_record_count} malformed record(s)."
                )
            elif (
                len(unbound_source_ids)
                + len(provider_mismatch_source_ids)
                + len(asset_mismatch_source_ids)
            ) >= max(2, total_records // 4) or (
                registry_version_mismatch
                and (
                    unbound_source_ids
                    or provider_mismatch_source_ids
                    or asset_mismatch_source_ids
                )
            ):
                binding_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source registry binding drift was degraded because registry version or source binding mismatches accumulated."
                )
            elif (
                registry_version_mismatch
                or unbound_source_ids
                or provider_mismatch_source_ids
                or asset_mismatch_source_ids
            ):
                binding_classification = "drifting"
                drifting_snapshots += 1
                diagnostic = "Source registry binding drift was detected in this saved snapshot."
            else:
                binding_classification = "stable"
                stable_snapshots += 1
                diagnostic = "All source observation records matched the current source registry binding."

            aggregate_unbound_source_ids.update(unbound_source_ids)
            aggregate_provider_mismatch_source_ids.update(provider_mismatch_source_ids)
            aggregate_asset_mismatch_source_ids.update(asset_mismatch_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceRegistryBindingDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    source_registry_version=snapshot_source_registry_version,
                    registry_version_mismatch=registry_version_mismatch,
                    binding_classification=binding_classification,
                    total_records=total_records,
                    matched_records=matched_records,
                    unbound_source_ids=tuple(sorted(unbound_source_ids)),
                    provider_mismatch_source_ids=tuple(sorted(provider_mismatch_source_ids)),
                    asset_mismatch_source_ids=tuple(sorted(asset_mismatch_source_ids)),
                    malformed_record_count=malformed_record_count,
                    severity_score=severity_score,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if snapshots_checked == 0:
            drift_classification = "insufficient_data"
        elif degraded_snapshots > 0 or invalid_snapshots > 0:
            drift_classification = "degraded"
        elif drifting_snapshots > 0:
            drift_classification = "drifting"
        else:
            drift_classification = "stable"

        severity_score = min(
            100,
            sum(entry.severity_score for entry in entries),
        )

        if snapshots_checked == 0:
            diagnostics.append("No saved snapshots were available for source registry binding drift analysis.")
        elif drift_classification == "stable":
            diagnostics.append(
                f"Source registry bindings remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "drifting":
            diagnostics.append(
                f"Source registry binding drift was detected across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                f"Source registry binding drift was degraded across {snapshots_checked} saved snapshot(s)."
            )

        if registry_version_mismatch_count > 0:
            diagnostics.append(
                f"{registry_version_mismatch_count} snapshot(s) used a different source registry version than the current registry."
            )
        if aggregate_unbound_source_ids:
            diagnostics.append(
                f"{len(aggregate_unbound_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_provider_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_provider_mismatch_source_ids)} source ID(s) had provider binding mismatches."
            )
        if aggregate_asset_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_asset_mismatch_source_ids)} source ID(s) had asset binding mismatches."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during binding drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source registry binding drift analysis."
            )

        return SnapshotSourceRegistryBindingDrift(
            drift_classification=drift_classification,
            severity_score=severity_score,
            current_source_registry_version=current_source_registry_version,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            registry_version_mismatch_count=registry_version_mismatch_count,
            unbound_source_ids=tuple(sorted(aggregate_unbound_source_ids)),
            provider_mismatch_source_ids=tuple(sorted(aggregate_provider_mismatch_source_ids)),
            asset_mismatch_source_ids=tuple(sorted(aggregate_asset_mismatch_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_decision_usage_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDecisionUsageConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source decision-usage consistency analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source decision-usage consistency analysis."
                )
            return SnapshotSourceDecisionUsageConsistency(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                aggregate_decision_usage_counts={},
                mismatched_source_ids=(),
                unsafe_source_ids=(),
                unknown_registry_source_ids=(),
                missing_decision_usage_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {
            entry.source_id: entry
            for entry in registry_entries
        }

        entries: list[SnapshotSourceDecisionUsageConsistencyEntry] = []
        aggregate_decision_usage_counts: Counter[str] = Counter()
        aggregate_mismatched_source_ids: set[str] = set()
        aggregate_unsafe_source_ids: set[str] = set()
        aggregate_unknown_registry_source_ids: set[str] = set()
        aggregate_missing_decision_usage_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceDecisionUsageConsistencyEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        consistency_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        consistent_records=0,
                        decision_usage_counts={},
                        mismatched_source_ids=(),
                        unsafe_source_ids=(),
                        unknown_registry_source_ids=(),
                        missing_decision_usage_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source decision-usage consistency could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            consistent_records = 0
            malformed_record_count = 0
            decision_usage_counts: Counter[str] = Counter()
            mismatched_source_ids: set[str] = set()
            unsafe_source_ids: set[str] = set()
            unknown_registry_source_ids: set[str] = set()
            missing_decision_usage_source_ids: set[str] = set()

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                raw_decision_usage = record.get("decision_usage")
                if not isinstance(raw_decision_usage, str) or not raw_decision_usage.strip():
                    missing_decision_usage_source_ids.add(source_id)
                    continue
                decision_usage = raw_decision_usage.strip()
                if decision_usage not in ALLOWED_DECISION_USAGES:
                    malformed_record_count += 1
                    continue

                decision_usage_counts[decision_usage] += 1
                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unknown_registry_source_ids.add(source_id)
                elif decision_usage != registry_entry.decision_usage:
                    mismatched_source_ids.add(source_id)

                paper_safe = record.get("paper_safe")
                verified = record.get("verified")
                if paper_safe is not True:
                    unsafe_source_ids.add(source_id)
                if verified is False and decision_usage != "simulation_only":
                    unsafe_source_ids.add(source_id)

                if (
                    source_id not in mismatched_source_ids
                    and source_id not in unsafe_source_ids
                    and source_id not in unknown_registry_source_ids
                    and source_id not in missing_decision_usage_source_ids
                ):
                    consistent_records += 1

            consistency_percentage = round(
                (consistent_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Source decision-usage consistency encountered {malformed_record_count} malformed record(s)."
                )
            elif mismatched_source_ids or unsafe_source_ids:
                consistency_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = "Source decision-usage consistency was degraded by mismatched or unsafe source usage."
            elif unknown_registry_source_ids or missing_decision_usage_source_ids:
                consistency_classification = "partial"
                partial_snapshots += 1
                diagnostic = "Source decision-usage consistency was partial because some source bindings or usage values were incomplete."
            else:
                consistency_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = "All source observation records preserved consistent decision-usage metadata."

            aggregate_decision_usage_counts.update(decision_usage_counts)
            aggregate_mismatched_source_ids.update(mismatched_source_ids)
            aggregate_unsafe_source_ids.update(unsafe_source_ids)
            aggregate_unknown_registry_source_ids.update(unknown_registry_source_ids)
            aggregate_missing_decision_usage_source_ids.update(missing_decision_usage_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceDecisionUsageConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    consistent_records=consistent_records,
                    decision_usage_counts=dict(sorted(decision_usage_counts.items())),
                    mismatched_source_ids=tuple(sorted(mismatched_source_ids)),
                    unsafe_source_ids=tuple(sorted(unsafe_source_ids)),
                    unknown_registry_source_ids=tuple(sorted(unknown_registry_source_ids)),
                    missing_decision_usage_source_ids=tuple(sorted(missing_decision_usage_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            consistency_classification = "invalid"
        elif degraded_snapshots > 0:
            consistency_classification = "degraded"
        elif partial_snapshots > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        average_consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Source decision-usage consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_mismatched_source_ids:
            diagnostics.append(
                f"{len(aggregate_mismatched_source_ids)} source ID(s) had decision-usage mismatches against the current source registry."
            )
        if aggregate_unsafe_source_ids:
            diagnostics.append(
                f"{len(aggregate_unsafe_source_ids)} source ID(s) violated paper-safe decision-usage expectations."
            )
        if aggregate_unknown_registry_source_ids:
            diagnostics.append(
                f"{len(aggregate_unknown_registry_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_missing_decision_usage_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_decision_usage_source_ids)} source ID(s) were missing usable decision-usage metadata."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during decision-usage consistency analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source decision-usage consistency analysis."
            )

        return SnapshotSourceDecisionUsageConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            aggregate_decision_usage_counts=dict(sorted(aggregate_decision_usage_counts.items())),
            mismatched_source_ids=tuple(sorted(aggregate_mismatched_source_ids)),
            unsafe_source_ids=tuple(sorted(aggregate_unsafe_source_ids)),
            unknown_registry_source_ids=tuple(sorted(aggregate_unknown_registry_source_ids)),
            missing_decision_usage_source_ids=tuple(sorted(aggregate_missing_decision_usage_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_verification_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceVerificationDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source verification drift analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source verification drift analysis."
                )
            return SnapshotSourceVerificationDrift(
                drift_classification="insufficient_data",
                average_verification_score=0.0,
                severity_score=0,
                current_source_registry_version="unknown",
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                degraded_source_ids=(),
                improved_source_ids=(),
                missing_verification_source_ids=(),
                unknown_registry_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        current_source_registry_version = str(source_registry["version"])
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {entry.source_id: entry for entry in registry_entries}

        entries: list[SnapshotSourceVerificationDriftEntry] = []
        aggregate_degraded_source_ids: set[str] = set()
        aggregate_improved_source_ids: set[str] = set()
        aggregate_missing_verification_source_ids: set[str] = set()
        aggregate_unknown_registry_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceVerificationDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        verification_classification="insufficient_data",
                        verification_score=0.0,
                        total_records=0,
                        verified_records=0,
                        expected_verified_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_verification_source_ids=(),
                        unknown_registry_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source verification drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            verified_records = 0
            expected_verified_records = 0
            degraded_source_ids: set[str] = set()
            improved_source_ids: set[str] = set()
            missing_verification_source_ids: set[str] = set()
            unknown_registry_source_ids: set[str] = set()
            malformed_record_count = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unknown_registry_source_ids.add(source_id)
                elif registry_entry.verified:
                    expected_verified_records += 1

                raw_verified = record.get("verified")
                if not isinstance(raw_verified, bool):
                    missing_verification_source_ids.add(source_id)
                    continue

                if raw_verified:
                    verified_records += 1

                if registry_entry is None:
                    continue
                if registry_entry.verified and raw_verified is False:
                    degraded_source_ids.add(source_id)
                elif not registry_entry.verified and raw_verified is True:
                    improved_source_ids.add(source_id)

            severity_score = min(
                100,
                len(degraded_source_ids) * 25
                + len(missing_verification_source_ids) * 15
                + len(unknown_registry_source_ids) * 10
                + malformed_record_count * 20,
            )
            verification_score = round(max(0, 100 - severity_score), 2)

            if malformed_record_count >= total_records:
                verification_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = "Source verification drift was insufficient because all source observation records were malformed."
            elif degraded_source_ids and improved_source_ids:
                verification_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = "Source verification drift was mixed because degraded and improved verification signals appeared together."
            elif degraded_source_ids or missing_verification_source_ids or unknown_registry_source_ids or malformed_record_count > 0:
                verification_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = "Source verification drift degraded because verified source trust weakened or verification metadata became incomplete."
            elif improved_source_ids:
                verification_classification = "improving"
                improving_snapshots += 1
                diagnostic = "Source verification drift improved because previously unverified sources now appear verified."
            else:
                verification_classification = "stable"
                stable_snapshots += 1
                diagnostic = "Source verification status remained stable for all persisted source observation records."

            aggregate_degraded_source_ids.update(degraded_source_ids)
            aggregate_improved_source_ids.update(improved_source_ids)
            aggregate_missing_verification_source_ids.update(missing_verification_source_ids)
            aggregate_unknown_registry_source_ids.update(unknown_registry_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceVerificationDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    verification_classification=verification_classification,
                    verification_score=verification_score,
                    total_records=total_records,
                    verified_records=verified_records,
                    expected_verified_records=expected_verified_records,
                    degraded_source_ids=tuple(sorted(degraded_source_ids)),
                    improved_source_ids=tuple(sorted(improved_source_ids)),
                    missing_verification_source_ids=tuple(sorted(missing_verification_source_ids)),
                    unknown_registry_source_ids=tuple(sorted(unknown_registry_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        evaluable_entries = tuple(
            entry
            for entry in entries
            if entry.verification_classification != "insufficient_data"
        )

        if not evaluable_entries:
            drift_classification = "insufficient_data"
            average_verification_score = 0.0
            severity_score = 0
        else:
            scores = [entry.verification_score for entry in evaluable_entries]
            if len(evaluable_entries) == 1:
                drift_classification = evaluable_entries[0].verification_classification
            else:
                non_decreasing = all(scores[index] >= scores[index - 1] for index in range(1, len(scores)))
                non_increasing = all(scores[index] <= scores[index - 1] for index in range(1, len(scores)))
                has_degrading = any(
                    entry.verification_classification == "degrading"
                    for entry in evaluable_entries
                )
                has_improving = any(
                    entry.verification_classification == "improving"
                    for entry in evaluable_entries
                )
                has_mixed = any(
                    entry.verification_classification == "mixed"
                    for entry in evaluable_entries
                )

                if all(entry.verification_classification == "stable" for entry in evaluable_entries):
                    drift_classification = "stable"
                elif (
                    non_decreasing
                    and scores[-1] > scores[0]
                    and not has_mixed
                    and not (has_degrading and has_improving)
                ):
                    drift_classification = "improving"
                elif (
                    non_increasing
                    and scores[-1] < scores[0]
                    and not has_mixed
                    and not (has_degrading and has_improving)
                ):
                    drift_classification = "degrading"
                elif has_improving and not has_degrading and not has_mixed:
                    drift_classification = "improving"
                elif has_mixed or (has_degrading and has_improving):
                    drift_classification = "mixed"
                elif has_degrading and scores[-1] < scores[0]:
                    drift_classification = "degrading"
                elif has_improving and scores[-1] > scores[0]:
                    drift_classification = "improving"
                elif any(entry.verification_classification != "stable" for entry in evaluable_entries):
                    drift_classification = "mixed"
                else:
                    drift_classification = "stable"

            average_verification_score = round(
                sum(entry.verification_score for entry in evaluable_entries) / len(evaluable_entries),
                2,
            )
            severity_score = int(round(100 - evaluable_entries[-1].verification_score))

        if drift_classification == "stable":
            diagnostics.append(
                f"Source verification drift remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source verification drift degraded across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source verification drift improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source verification drift was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source verification drift had insufficient usable data.")

        if aggregate_degraded_source_ids:
            diagnostics.append(
                f"{len(aggregate_degraded_source_ids)} source ID(s) drifted from verified to unverified status."
            )
        if aggregate_improved_source_ids:
            diagnostics.append(
                f"{len(aggregate_improved_source_ids)} source ID(s) improved from unverified to verified status."
            )
        if aggregate_missing_verification_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_verification_source_ids)} source ID(s) were missing usable verification metadata."
            )
        if aggregate_unknown_registry_source_ids:
            diagnostics.append(
                f"{len(aggregate_unknown_registry_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during source verification drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source verification drift analysis."
            )

        return SnapshotSourceVerificationDrift(
            drift_classification=drift_classification,
            average_verification_score=average_verification_score,
            severity_score=severity_score,
            current_source_registry_version=current_source_registry_version,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            degraded_source_ids=tuple(sorted(aggregate_degraded_source_ids)),
            improved_source_ids=tuple(sorted(aggregate_improved_source_ids)),
            missing_verification_source_ids=tuple(sorted(aggregate_missing_verification_source_ids)),
            unknown_registry_source_ids=tuple(sorted(aggregate_unknown_registry_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_paper_safe_source_flag_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotPaperSafeSourceFlagConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for paper-safe source flag consistency analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during paper-safe source flag consistency analysis."
                )
            return SnapshotPaperSafeSourceFlagConsistency(
                consistency_classification="insufficient_data",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                false_flag_source_ids=(),
                missing_flag_source_ids=(),
                malformed_flag_source_ids=(),
                contradictory_source_ids=(),
                unknown_registry_source_ids=(),
                unsafe_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {entry.source_id: entry for entry in registry_entries}

        entries: list[SnapshotPaperSafeSourceFlagConsistencyEntry] = []
        aggregate_false_flag_source_ids: set[str] = set()
        aggregate_missing_flag_source_ids: set[str] = set()
        aggregate_malformed_flag_source_ids: set[str] = set()
        aggregate_contradictory_source_ids: set[str] = set()
        aggregate_unknown_registry_source_ids: set[str] = set()
        aggregate_unsafe_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotPaperSafeSourceFlagConsistencyEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        consistency_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        safe_records=0,
                        false_flag_source_ids=(),
                        missing_flag_source_ids=(),
                        malformed_flag_source_ids=(),
                        contradictory_source_ids=(),
                        unknown_registry_source_ids=(),
                        unsafe_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Paper-safe source flag consistency could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            safe_records = 0
            false_flag_source_ids: set[str] = set()
            missing_flag_source_ids: set[str] = set()
            malformed_flag_source_ids: set[str] = set()
            contradictory_source_ids: set[str] = set()
            unknown_registry_source_ids: set[str] = set()
            unsafe_source_ids: set[str] = set()
            malformed_record_count = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unknown_registry_source_ids.add(source_id)

                raw_paper_safe = record.get("paper_safe")
                if raw_paper_safe is None:
                    missing_flag_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue
                if not isinstance(raw_paper_safe, bool):
                    malformed_flag_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue
                if raw_paper_safe is False:
                    false_flag_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue

                decision_usage_value = record.get("decision_usage")
                if not isinstance(decision_usage_value, str) or not decision_usage_value.strip():
                    decision_usage = registry_entry.decision_usage if registry_entry is not None else None
                else:
                    decision_usage = decision_usage_value.strip()

                verified_value = record.get("verified")
                if verified_value is False and decision_usage == "verified_required":
                    contradictory_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue

                safe_records += 1

            consistency_percentage = round((safe_records / total_records) * 100, 2) if total_records else 0.0

            if malformed_record_count > 0 or malformed_flag_source_ids:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = "Paper-safe source flag consistency was invalid because malformed record or flag structures were detected."
            elif false_flag_source_ids or contradictory_source_ids:
                consistency_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = "Paper-safe source flag consistency was degraded because unsafe or contradictory source flags were detected."
            elif missing_flag_source_ids or unknown_registry_source_ids:
                consistency_classification = "partial"
                partial_snapshots += 1
                diagnostic = "Paper-safe source flag consistency was partial because some source flags or registry bindings were incomplete."
            else:
                consistency_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = "All source observation records preserved consistent paper-safe flags."

            aggregate_false_flag_source_ids.update(false_flag_source_ids)
            aggregate_missing_flag_source_ids.update(missing_flag_source_ids)
            aggregate_malformed_flag_source_ids.update(malformed_flag_source_ids)
            aggregate_contradictory_source_ids.update(contradictory_source_ids)
            aggregate_unknown_registry_source_ids.update(unknown_registry_source_ids)
            aggregate_unsafe_source_ids.update(unsafe_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotPaperSafeSourceFlagConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    safe_records=safe_records,
                    false_flag_source_ids=tuple(sorted(false_flag_source_ids)),
                    missing_flag_source_ids=tuple(sorted(missing_flag_source_ids)),
                    malformed_flag_source_ids=tuple(sorted(malformed_flag_source_ids)),
                    contradictory_source_ids=tuple(sorted(contradictory_source_ids)),
                    unknown_registry_source_ids=tuple(sorted(unknown_registry_source_ids)),
                    unsafe_source_ids=tuple(sorted(unsafe_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if snapshots_checked == 0:
            consistency_classification = "insufficient_data"
            average_consistency_percentage = 0.0
        else:
            if invalid_snapshots > 0:
                consistency_classification = "invalid"
            elif degraded_snapshots > 0:
                consistency_classification = "degraded"
            elif partial_snapshots > 0:
                consistency_classification = "partial"
            else:
                consistency_classification = "consistent"

            average_consistency_percentage = round(
                sum(entry.consistency_percentage for entry in entries) / snapshots_checked,
                2,
            )

        diagnostics.append(
            f"Paper-safe source flag consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_false_flag_source_ids:
            diagnostics.append(
                f"{len(aggregate_false_flag_source_ids)} source ID(s) were explicitly marked paper_safe=false."
            )
        if aggregate_missing_flag_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_flag_source_ids)} source ID(s) were missing usable paper-safe flags."
            )
        if aggregate_malformed_flag_source_ids:
            diagnostics.append(
                f"{len(aggregate_malformed_flag_source_ids)} source ID(s) had malformed paper-safe flags."
            )
        if aggregate_contradictory_source_ids:
            diagnostics.append(
                f"{len(aggregate_contradictory_source_ids)} source ID(s) had contradictory paper-safe versus verification metadata."
            )
        if aggregate_unknown_registry_source_ids:
            diagnostics.append(
                f"{len(aggregate_unknown_registry_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during paper-safe source flag consistency analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during paper-safe source flag consistency analysis."
            )

        return SnapshotPaperSafeSourceFlagConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            false_flag_source_ids=tuple(sorted(aggregate_false_flag_source_ids)),
            missing_flag_source_ids=tuple(sorted(aggregate_missing_flag_source_ids)),
            malformed_flag_source_ids=tuple(sorted(aggregate_malformed_flag_source_ids)),
            contradictory_source_ids=tuple(sorted(aggregate_contradictory_source_ids)),
            unknown_registry_source_ids=tuple(sorted(aggregate_unknown_registry_source_ids)),
            unsafe_source_ids=tuple(sorted(aggregate_unsafe_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_summary_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationSummaryDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source observation summary drift analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation summary drift analysis."
                )
            return SnapshotSourceObservationSummaryDrift(
                drift_classification="insufficient_data",
                average_summary_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                expected_total_bound_sources=0,
                expected_verified_sources=0,
                expected_simulation_only_sources=0,
                expected_paper_safe_sources=0,
                normalization_mode_changes=0,
                malformed_summary_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        registry_entries = build_source_registry_entries(load_source_registry())
        active_entries = tuple(entry for entry in registry_entries if entry.active)
        expected_total_bound_sources = len(active_entries)
        expected_verified_sources = sum(1 for entry in active_entries if entry.verified)
        expected_simulation_only_sources = sum(
            1
            for entry in active_entries
            if entry.decision_usage == "simulation_only"
        )
        expected_paper_safe_sources = expected_total_bound_sources

        entries: list[SnapshotSourceObservationSummaryDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        normalization_mode_changes = 0
        malformed_summary_count = 0
        previous_valid_entry: SnapshotSourceObservationSummaryDriftEntry | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_observation_summary")
            if not isinstance(summary, Mapping):
                insufficient_data_snapshots += 1
                malformed_summary_count += 1
                entries.append(
                    SnapshotSourceObservationSummaryDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        summary_score=0.0,
                        contract=None,
                        normalization_mode=None,
                        total_bound_sources=None,
                        verified_sources=None,
                        simulation_only_sources=None,
                        paper_safe_sources=None,
                        total_bound_source_delta=None,
                        verified_source_delta=None,
                        paper_safe_source_delta=None,
                        simulation_only_source_delta=None,
                        malformed_field_count=1,
                        diagnostic="Source observation summary drift could not be evaluated because the persisted summary was missing or malformed.",
                    )
                )
                continue

            malformed_field_count = 0
            contract = summary.get("contract")
            if not isinstance(contract, str) or not contract.strip():
                contract_value: str | None = None
                malformed_field_count += 1
            else:
                contract_value = contract.strip()

            normalization_mode = summary.get("normalization_mode")
            if not isinstance(normalization_mode, str) or not normalization_mode.strip():
                normalization_mode_value: str | None = None
                malformed_field_count += 1
            else:
                normalization_mode_value = normalization_mode.strip()

            def parse_count(field_name: str) -> int | None:
                nonlocal malformed_field_count
                value = summary.get(field_name)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    malformed_field_count += 1
                    return None
                return int(value)

            total_bound_sources = parse_count("total_bound_sources")
            verified_sources = parse_count("verified_sources")
            simulation_only_sources = parse_count("simulation_only_sources")
            paper_safe_sources = parse_count("paper_safe_sources")

            if (
                total_bound_sources is not None
                and verified_sources is not None
                and verified_sources > total_bound_sources
            ):
                malformed_field_count += 1
            if (
                total_bound_sources is not None
                and simulation_only_sources is not None
                and simulation_only_sources > total_bound_sources
            ):
                malformed_field_count += 1
            if (
                total_bound_sources is not None
                and paper_safe_sources is not None
                and paper_safe_sources > total_bound_sources
            ):
                malformed_field_count += 1

            if malformed_field_count > 0 or total_bound_sources in (None, 0) or verified_sources is None or simulation_only_sources is None or paper_safe_sources is None:
                insufficient_data_snapshots += 1
                malformed_summary_count += malformed_field_count or 1
                entries.append(
                    SnapshotSourceObservationSummaryDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        summary_score=0.0,
                        contract=contract_value,
                        normalization_mode=normalization_mode_value,
                        total_bound_sources=total_bound_sources,
                        verified_sources=verified_sources,
                        simulation_only_sources=simulation_only_sources,
                        paper_safe_sources=paper_safe_sources,
                        total_bound_source_delta=None,
                        verified_source_delta=None,
                        paper_safe_source_delta=None,
                        simulation_only_source_delta=None,
                        malformed_field_count=malformed_field_count or 1,
                        diagnostic="Source observation summary drift could not be evaluated because one or more persisted summary fields were missing or malformed.",
                    )
                )
                continue

            total_ratio = min(total_bound_sources / max(expected_total_bound_sources, 1), 1.0)
            verified_ratio = min(verified_sources / max(expected_verified_sources, 1), 1.0)
            paper_safe_ratio = min(paper_safe_sources / max(expected_paper_safe_sources, 1), 1.0)
            simulation_closeness_ratio = 1.0 - min(
                abs(simulation_only_sources - expected_simulation_only_sources) / max(expected_total_bound_sources, 1),
                1.0,
            )
            summary_score = round(
                total_ratio * 35
                + verified_ratio * 35
                + paper_safe_ratio * 20
                + simulation_closeness_ratio * 10,
                2,
            )

            if previous_valid_entry is None:
                total_bound_source_delta = total_bound_sources - expected_total_bound_sources
                verified_source_delta = verified_sources - expected_verified_sources
                paper_safe_source_delta = paper_safe_sources - expected_paper_safe_sources
                simulation_only_source_delta = simulation_only_sources - expected_simulation_only_sources
                if summary_score >= 95.0:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = "Source observation summary matched the expected paper-safe baseline."
                else:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = "Source observation summary drifted below the expected paper-safe baseline."
            else:
                total_bound_source_delta = total_bound_sources - (previous_valid_entry.total_bound_sources or 0)
                verified_source_delta = verified_sources - (previous_valid_entry.verified_sources or 0)
                paper_safe_source_delta = paper_safe_sources - (previous_valid_entry.paper_safe_sources or 0)
                simulation_only_source_delta = simulation_only_sources - (previous_valid_entry.simulation_only_sources or 0)
                score_delta = round(summary_score - previous_valid_entry.summary_score, 2)

                improving_signals = 0
                degrading_signals = 0

                if total_bound_source_delta > 0:
                    improving_signals += 1
                elif total_bound_source_delta < 0:
                    degrading_signals += 1

                if verified_source_delta > 0:
                    improving_signals += 1
                elif verified_source_delta < 0:
                    degrading_signals += 1

                if paper_safe_source_delta > 0:
                    improving_signals += 1
                elif paper_safe_source_delta < 0:
                    degrading_signals += 1

                previous_simulation_distance = abs(
                    (previous_valid_entry.simulation_only_sources or 0) - expected_simulation_only_sources
                )
                current_simulation_distance = abs(
                    simulation_only_sources - expected_simulation_only_sources
                )
                if current_simulation_distance < previous_simulation_distance:
                    improving_signals += 1
                elif current_simulation_distance > previous_simulation_distance:
                    degrading_signals += 1

                if normalization_mode_value != previous_valid_entry.normalization_mode:
                    normalization_mode_changes += 1
                    degrading_signals += 1

                if score_delta > 0.5:
                    improving_signals += 1
                elif score_delta < -0.5:
                    degrading_signals += 1

                if improving_signals == 0 and degrading_signals == 0:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = "Source observation summary remained stable compared with the previous saved snapshot."
                elif improving_signals > 0 and degrading_signals == 0:
                    drift_classification = "improving"
                    improving_snapshots += 1
                    diagnostic = "Source observation summary improved compared with the previous saved snapshot."
                elif degrading_signals > 0 and improving_signals == 0:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = "Source observation summary degraded compared with the previous saved snapshot."
                else:
                    drift_classification = "mixed"
                    mixed_snapshots += 1
                    diagnostic = "Source observation summary changed in mixed directions compared with the previous saved snapshot."

            current_entry = SnapshotSourceObservationSummaryDriftEntry(
                snapshot_id=snapshot_id,
                created_at=created_at,
                drift_classification=drift_classification,
                summary_score=summary_score,
                contract=contract_value,
                normalization_mode=normalization_mode_value,
                total_bound_sources=total_bound_sources,
                verified_sources=verified_sources,
                simulation_only_sources=simulation_only_sources,
                paper_safe_sources=paper_safe_sources,
                total_bound_source_delta=total_bound_source_delta,
                verified_source_delta=verified_source_delta,
                paper_safe_source_delta=paper_safe_source_delta,
                simulation_only_source_delta=simulation_only_source_delta,
                malformed_field_count=malformed_field_count,
                diagnostic=diagnostic,
            )
            entries.append(current_entry)
            previous_valid_entry = current_entry

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_summary_score = 0.0
            severity_score = 0
        else:
            average_summary_score = round(
                sum(entry.summary_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            if len(valid_entries) == 1:
                drift_classification = valid_entries[0].drift_classification
            else:
                first_score = valid_entries[0].summary_score
                latest_score = valid_entries[-1].summary_score
                entry_classes = {entry.drift_classification for entry in valid_entries}
                if entry_classes == {"stable"}:
                    drift_classification = "stable"
                elif (
                    latest_score > first_score
                    and "mixed" not in entry_classes
                    and valid_entries[-1].drift_classification in {"stable", "improving"}
                ):
                    drift_classification = "improving"
                elif (
                    latest_score < first_score
                    and "mixed" not in entry_classes
                    and valid_entries[-1].drift_classification in {"stable", "degrading"}
                ):
                    drift_classification = "degrading"
                else:
                    drift_classification = "mixed"
            severity_score = int(round(max(0.0, 100.0 - valid_entries[-1].summary_score)))

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation summary drift remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation summary drift degraded across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation summary drift improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation summary drift was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation summary drift had insufficient usable data.")

        if normalization_mode_changes > 0:
            diagnostics.append(
                f"Source observation summary normalization mode changed {normalization_mode_changes} time(s) across the saved snapshots."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source observation summary field issue(s) were detected during summary drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation summary drift analysis."
            )

        return SnapshotSourceObservationSummaryDrift(
            drift_classification=drift_classification,
            average_summary_score=average_summary_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            expected_total_bound_sources=expected_total_bound_sources,
            expected_verified_sources=expected_verified_sources,
            expected_simulation_only_sources=expected_simulation_only_sources,
            expected_paper_safe_sources=expected_paper_safe_sources,
            normalization_mode_changes=normalization_mode_changes,
            malformed_summary_count=malformed_summary_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_provider_adapter_contract_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotProviderAdapterContractConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for provider adapter contract consistency analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during provider adapter contract consistency analysis."
                )
            return SnapshotProviderAdapterContractConsistency(
                consistency_classification="insufficient_data",
                average_consistency_percentage=0.0,
                expected_contract=EXPECTED_PROVIDER_ADAPTER_CONTRACT,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_contract_snapshot_ids=(),
                mismatched_contract_snapshot_ids=(),
                bound_source_mismatch_snapshot_ids=(),
                malformed_snapshot_ids=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotProviderAdapterContractConsistencyEntry] = []
        missing_contract_snapshot_ids: list[str] = []
        mismatched_contract_snapshot_ids: list[str] = []
        bound_source_mismatch_snapshot_ids: list[str] = []
        malformed_snapshot_ids: list[str] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_observation_summary")
            audit_source_payload = snapshot_payload.get("audit_source_payload")
            provider_adapter = self._read_nested_mapping_value(audit_source_payload, "provider_adapter")

            missing_fields: list[str] = []
            mismatched_fields: list[str] = []
            malformed_field_count = 0

            if not isinstance(summary, Mapping):
                malformed_field_count += 1
                source_observation_contract = None
                source_observation_total_bound_sources = None
            else:
                raw_source_observation_contract = summary.get("contract")
                if not isinstance(raw_source_observation_contract, str) or not raw_source_observation_contract.strip():
                    source_observation_contract = None
                    missing_fields.append("source_observation_summary.contract")
                else:
                    source_observation_contract = raw_source_observation_contract.strip()

                raw_source_observation_total_bound_sources = summary.get("total_bound_sources")
                if isinstance(raw_source_observation_total_bound_sources, bool) or (
                    raw_source_observation_total_bound_sources is not None
                    and not isinstance(raw_source_observation_total_bound_sources, int)
                ):
                    source_observation_total_bound_sources = None
                    malformed_field_count += 1
                elif raw_source_observation_total_bound_sources is None:
                    source_observation_total_bound_sources = None
                    missing_fields.append("source_observation_summary.total_bound_sources")
                else:
                    source_observation_total_bound_sources = int(raw_source_observation_total_bound_sources)

            if not isinstance(provider_adapter, Mapping):
                provider_adapter_contract = None
                provider_adapter_total_bound_sources = None
                missing_fields.extend(
                    [
                        "audit_source_payload.provider_adapter.contract",
                        "audit_source_payload.provider_adapter.total_bound_sources",
                    ]
                )
            else:
                raw_provider_adapter_contract = provider_adapter.get("contract")
                if not isinstance(raw_provider_adapter_contract, str) or not raw_provider_adapter_contract.strip():
                    provider_adapter_contract = None
                    missing_fields.append("audit_source_payload.provider_adapter.contract")
                else:
                    provider_adapter_contract = raw_provider_adapter_contract.strip()

                raw_provider_adapter_total_bound_sources = provider_adapter.get("total_bound_sources")
                if isinstance(raw_provider_adapter_total_bound_sources, bool) or (
                    raw_provider_adapter_total_bound_sources is not None
                    and not isinstance(raw_provider_adapter_total_bound_sources, int)
                ):
                    provider_adapter_total_bound_sources = None
                    malformed_field_count += 1
                elif raw_provider_adapter_total_bound_sources is None:
                    provider_adapter_total_bound_sources = None
                    missing_fields.append("audit_source_payload.provider_adapter.total_bound_sources")
                else:
                    provider_adapter_total_bound_sources = int(raw_provider_adapter_total_bound_sources)

            if source_observation_contract and source_observation_contract != EXPECTED_PROVIDER_ADAPTER_CONTRACT:
                mismatched_fields.append("source_observation_summary.contract")
            if provider_adapter_contract and provider_adapter_contract != EXPECTED_PROVIDER_ADAPTER_CONTRACT:
                mismatched_fields.append("audit_source_payload.provider_adapter.contract")
            if (
                source_observation_contract is not None
                and provider_adapter_contract is not None
                and source_observation_contract != provider_adapter_contract
            ):
                mismatched_fields.append("provider_adapter.contract_alignment")

            if (
                source_observation_total_bound_sources is not None
                and provider_adapter_total_bound_sources is not None
                and source_observation_total_bound_sources != provider_adapter_total_bound_sources
            ):
                mismatched_fields.append("provider_adapter.total_bound_sources_alignment")

            if malformed_field_count > 0:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                malformed_snapshot_ids.append(snapshot_id)
                consistency_percentage = 0.0
                diagnostic = "Provider adapter contract consistency could not be evaluated because persisted contract metadata was malformed."
            else:
                penalty = len(missing_fields) * 20 + len(mismatched_fields) * 35
                consistency_percentage = round(max(0.0, 100.0 - penalty), 2)

                if any(field.endswith("contract") for field in missing_fields):
                    missing_contract_snapshot_ids.append(snapshot_id)
                if any("contract" in field for field in mismatched_fields):
                    mismatched_contract_snapshot_ids.append(snapshot_id)
                if "provider_adapter.total_bound_sources_alignment" in mismatched_fields:
                    bound_source_mismatch_snapshot_ids.append(snapshot_id)

                if mismatched_fields:
                    consistency_classification = "degraded"
                    degraded_snapshots += 1
                    diagnostic = "Provider adapter contract consistency was degraded because persisted contract metadata diverged."
                elif missing_fields:
                    consistency_classification = "partial"
                    partial_snapshots += 1
                    diagnostic = "Provider adapter contract consistency was partial because persisted contract metadata was incomplete."
                else:
                    consistency_classification = "consistent"
                    consistent_snapshots += 1
                    diagnostic = "Provider adapter contract metadata remained consistent across persisted snapshot surfaces."

            entries.append(
                SnapshotProviderAdapterContractConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    source_observation_contract=source_observation_contract,
                    provider_adapter_contract=provider_adapter_contract,
                    source_observation_total_bound_sources=source_observation_total_bound_sources,
                    provider_adapter_total_bound_sources=provider_adapter_total_bound_sources,
                    missing_fields=tuple(sorted(set(missing_fields))),
                    mismatched_fields=tuple(sorted(set(mismatched_fields))),
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if snapshots_checked == 0:
            consistency_classification = "insufficient_data"
            average_consistency_percentage = 0.0
        else:
            if invalid_snapshots > 0:
                consistency_classification = "invalid"
            elif degraded_snapshots > 0:
                consistency_classification = "degraded"
            elif partial_snapshots > 0:
                consistency_classification = "partial"
            else:
                consistency_classification = "consistent"

            average_consistency_percentage = round(
                sum(entry.consistency_percentage for entry in entries) / snapshots_checked,
                2,
            )

        diagnostics.append(
            f"Provider adapter contract consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if missing_contract_snapshot_ids:
            diagnostics.append(
                f"{len(missing_contract_snapshot_ids)} snapshot(s) were missing contract metadata on one or more persisted surfaces."
            )
        if mismatched_contract_snapshot_ids:
            diagnostics.append(
                f"{len(mismatched_contract_snapshot_ids)} snapshot(s) had contract values that diverged from the expected provider adapter contract."
            )
        if bound_source_mismatch_snapshot_ids:
            diagnostics.append(
                f"{len(bound_source_mismatch_snapshot_ids)} snapshot(s) had mismatched bound-source totals between persisted summary surfaces."
            )
        if malformed_snapshot_ids:
            diagnostics.append(
                f"{len(malformed_snapshot_ids)} snapshot(s) contained malformed provider adapter contract metadata."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during provider adapter contract consistency analysis."
            )

        return SnapshotProviderAdapterContractConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            expected_contract=EXPECTED_PROVIDER_ADAPTER_CONTRACT,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_contract_snapshot_ids=tuple(sorted(missing_contract_snapshot_ids)),
            mismatched_contract_snapshot_ids=tuple(sorted(mismatched_contract_snapshot_ids)),
            bound_source_mismatch_snapshot_ids=tuple(sorted(bound_source_mismatch_snapshot_ids)),
            malformed_snapshot_ids=tuple(sorted(malformed_snapshot_ids)),
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_timestamp_integrity_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationTimestampIntegrityDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation timestamp integrity drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation timestamp integrity drift analysis."
                )
            return SnapshotSourceObservationTimestampIntegrityDrift(
                drift_classification="insufficient_data",
                average_integrity_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                missing_timestamp_source_ids=(),
                sequence_violation_source_ids=(),
                mapped_time_regression_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceObservationTimestampIntegrityDriftEntry] = []
        aggregate_missing_timestamp_source_ids: set[str] = set()
        aggregate_sequence_violation_source_ids: set[str] = set()
        aggregate_mapped_time_regression_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        previous_valid_entry: SnapshotSourceObservationTimestampIntegrityDriftEntry | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationTimestampIntegrityDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        integrity_classification="insufficient_data",
                        integrity_score=0.0,
                        total_records=0,
                        valid_records=0,
                        missing_timestamp_source_ids=(),
                        sequence_violation_source_ids=(),
                        mapped_time_regression_source_ids=(),
                        malformed_record_count=1,
                        diagnostic=(
                            "Source observation timestamp integrity drift could not be evaluated because source observation records were missing or malformed."
                        ),
                    )
                )
                continue

            total_records = len(source_observation_records)
            valid_records = 0
            missing_timestamp_source_ids: set[str] = set()
            sequence_violation_source_ids: set[str] = set()
            mapped_time_regression_source_ids: set[str] = set()
            malformed_record_count = 0

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                parsed_timestamps: dict[str, datetime] = {}
                timestamp_failed = False
                for field_name in ("observed_at", "available_at", "stored_at", "mapped_at"):
                    raw_value = record.get(field_name)
                    if not isinstance(raw_value, str) or not raw_value.strip():
                        missing_timestamp_source_ids.add(source_id)
                        timestamp_failed = True
                        break
                    try:
                        parsed_timestamps[field_name] = self._parse_datetime(raw_value)
                    except Exception:
                        missing_timestamp_source_ids.add(source_id)
                        timestamp_failed = True
                        break

                if timestamp_failed:
                    continue

                observed_at = parsed_timestamps["observed_at"]
                available_at = parsed_timestamps["available_at"]
                stored_at = parsed_timestamps["stored_at"]
                mapped_at = parsed_timestamps["mapped_at"]

                if not (observed_at <= available_at <= stored_at):
                    sequence_violation_source_ids.add(source_id)
                if mapped_at < stored_at:
                    mapped_time_regression_source_ids.add(source_id)

                if (
                    source_id not in sequence_violation_source_ids
                    and source_id not in mapped_time_regression_source_ids
                ):
                    valid_records += 1

            integrity_score = round(
                (valid_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if total_records == 0 or malformed_record_count >= total_records:
                integrity_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source observation timestamp integrity drift could not be evaluated because persisted records were entirely malformed."
                )
            else:
                current_issue_total = (
                    len(missing_timestamp_source_ids)
                    + len(sequence_violation_source_ids)
                    + len(mapped_time_regression_source_ids)
                    + malformed_record_count
                )
                issue_bucket_count = sum(
                    1
                    for value in (
                        missing_timestamp_source_ids,
                        sequence_violation_source_ids,
                        mapped_time_regression_source_ids,
                    )
                    if value
                ) + (1 if malformed_record_count > 0 else 0)

                if previous_valid_entry is None:
                    if integrity_score == 100.0:
                        integrity_classification = "stable"
                        stable_snapshots += 1
                        diagnostic = (
                            "All source observation records preserved the expected observed/available/stored/mapped timestamp ordering."
                        )
                    elif issue_bucket_count > 1:
                        integrity_classification = "mixed"
                        mixed_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity showed mixed missing-timestamp and ordering regressions against the paper-safe baseline."
                        )
                    else:
                        integrity_classification = "degrading"
                        degrading_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity drifted below the expected paper-safe baseline."
                        )
                else:
                    previous_issue_total = (
                        len(previous_valid_entry.missing_timestamp_source_ids)
                        + len(previous_valid_entry.sequence_violation_source_ids)
                        + len(previous_valid_entry.mapped_time_regression_source_ids)
                        + previous_valid_entry.malformed_record_count
                    )
                    score_delta = round(
                        integrity_score - previous_valid_entry.integrity_score,
                        2,
                    )

                    if score_delta == 0 and current_issue_total == previous_issue_total:
                        integrity_classification = "stable"
                        stable_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity remained stable compared with the previous saved snapshot."
                        )
                    elif score_delta > 0 and current_issue_total <= previous_issue_total:
                        integrity_classification = "improving"
                        improving_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity improved compared with the previous saved snapshot."
                        )
                    elif score_delta < 0 and current_issue_total >= previous_issue_total:
                        integrity_classification = "degrading"
                        degrading_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity degraded compared with the previous saved snapshot."
                        )
                    elif current_issue_total < previous_issue_total:
                        integrity_classification = "improving"
                        improving_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity reduced its timestamp issue load compared with the previous saved snapshot."
                        )
                    elif current_issue_total > previous_issue_total:
                        integrity_classification = "degrading"
                        degrading_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity accumulated additional timestamp issues compared with the previous saved snapshot."
                        )
                    else:
                        integrity_classification = "mixed"
                        mixed_snapshots += 1
                        diagnostic = (
                            "Source observation timestamp integrity changed in mixed directions compared with the previous saved snapshot."
                        )

            aggregate_missing_timestamp_source_ids.update(missing_timestamp_source_ids)
            aggregate_sequence_violation_source_ids.update(sequence_violation_source_ids)
            aggregate_mapped_time_regression_source_ids.update(mapped_time_regression_source_ids)
            aggregate_malformed_record_count += malformed_record_count

            current_entry = SnapshotSourceObservationTimestampIntegrityDriftEntry(
                snapshot_id=snapshot_id,
                created_at=created_at,
                integrity_classification=integrity_classification,
                integrity_score=integrity_score,
                total_records=total_records,
                valid_records=valid_records,
                missing_timestamp_source_ids=tuple(sorted(missing_timestamp_source_ids)),
                sequence_violation_source_ids=tuple(sorted(sequence_violation_source_ids)),
                mapped_time_regression_source_ids=tuple(sorted(mapped_time_regression_source_ids)),
                malformed_record_count=malformed_record_count,
                diagnostic=diagnostic,
            )
            entries.append(current_entry)
            if integrity_classification != "insufficient_data":
                previous_valid_entry = current_entry

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.integrity_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_integrity_score = 0.0
            severity_score = 0
        else:
            average_integrity_score = round(
                sum(entry.integrity_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            if len(valid_entries) == 1:
                drift_classification = valid_entries[0].integrity_classification
            else:
                first_score = valid_entries[0].integrity_score
                latest_score = valid_entries[-1].integrity_score
                entry_classes = {entry.integrity_classification for entry in valid_entries}
                if entry_classes == {"stable"}:
                    drift_classification = "stable"
                elif (
                    latest_score > first_score
                    and "mixed" not in entry_classes
                    and valid_entries[-1].integrity_classification in {"stable", "improving"}
                ):
                    drift_classification = "improving"
                elif (
                    latest_score < first_score
                    and "mixed" not in entry_classes
                    and valid_entries[-1].integrity_classification in {"stable", "degrading"}
                ):
                    drift_classification = "degrading"
                else:
                    drift_classification = "mixed"
            severity_score = int(round(max(0.0, 100.0 - valid_entries[-1].integrity_score)))

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation timestamp integrity remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation timestamp integrity degraded across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation timestamp integrity improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation timestamp integrity was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation timestamp integrity had insufficient usable data.")

        if aggregate_missing_timestamp_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_timestamp_source_ids)} source ID(s) were missing usable timestamp metadata."
            )
        if aggregate_sequence_violation_source_ids:
            diagnostics.append(
                f"{len(aggregate_sequence_violation_source_ids)} source ID(s) violated observed/available/stored timestamp ordering."
            )
        if aggregate_mapped_time_regression_source_ids:
            diagnostics.append(
                f"{len(aggregate_mapped_time_regression_source_ids)} source ID(s) regressed mapped timestamps below stored timestamps."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during timestamp integrity analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation timestamp integrity drift analysis."
            )

        return SnapshotSourceObservationTimestampIntegrityDrift(
            drift_classification=drift_classification,
            average_integrity_score=average_integrity_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            missing_timestamp_source_ids=tuple(sorted(aggregate_missing_timestamp_source_ids)),
            sequence_violation_source_ids=tuple(sorted(aggregate_sequence_violation_source_ids)),
            mapped_time_regression_source_ids=tuple(sorted(aggregate_mapped_time_regression_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_record_summary_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationRecordSummaryReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation record/summary reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation record/summary reconciliation analysis."
                )
            return SnapshotSourceObservationRecordSummaryReconciliation(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_fields=(),
                mismatched_fields=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceObservationRecordSummaryReconciliationEntry] = []
        aggregate_missing_fields: set[str] = set()
        aggregate_mismatched_fields: set[str] = set()
        aggregate_malformed_record_count = 0
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            summary = snapshot_payload.get("source_observation_summary")
            missing_fields: set[str] = set()
            mismatched_fields: set[str] = set()
            malformed_record_count = 0

            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationRecordSummaryReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        record_total_bound_sources=0,
                        summary_total_bound_sources=None,
                        record_verified_sources=0,
                        summary_verified_sources=None,
                        record_simulation_only_sources=0,
                        summary_simulation_only_sources=None,
                        record_paper_safe_sources=0,
                        summary_paper_safe_sources=None,
                        missing_fields=("source_observation_records",),
                        mismatched_fields=(),
                        malformed_record_count=1,
                        diagnostic=(
                            "Source observation record/summary reconciliation could not be evaluated because source observation records were missing or malformed."
                        ),
                    )
                )
                aggregate_missing_fields.add("source_observation_records")
                continue

            record_total_bound_sources = len(source_observation_records)
            record_verified_sources = 0
            record_simulation_only_sources = 0
            record_paper_safe_sources = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_verified = record.get("verified")
                if isinstance(raw_verified, bool):
                    if raw_verified:
                        record_verified_sources += 1
                else:
                    malformed_record_count += 1

                raw_decision_usage = record.get("decision_usage")
                if isinstance(raw_decision_usage, str) and raw_decision_usage.strip():
                    if raw_decision_usage.strip() == "simulation_only":
                        record_simulation_only_sources += 1
                else:
                    malformed_record_count += 1

                raw_paper_safe = record.get("paper_safe")
                if isinstance(raw_paper_safe, bool):
                    if raw_paper_safe:
                        record_paper_safe_sources += 1
                else:
                    malformed_record_count += 1

            def parse_summary_count(field_name: str) -> int | None:
                value = summary.get(field_name) if isinstance(summary, Mapping) else None
                if value is None:
                    missing_fields.add(field_name)
                    return None
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    missing_fields.add(field_name)
                    return None
                return int(value)

            if not isinstance(summary, Mapping):
                missing_fields.update(
                    {
                        "source_observation_summary",
                        "total_bound_sources",
                        "verified_sources",
                        "simulation_only_sources",
                        "paper_safe_sources",
                    }
                )
                summary_total_bound_sources = None
                summary_verified_sources = None
                summary_simulation_only_sources = None
                summary_paper_safe_sources = None
            else:
                summary_total_bound_sources = parse_summary_count("total_bound_sources")
                summary_verified_sources = parse_summary_count("verified_sources")
                summary_simulation_only_sources = parse_summary_count("simulation_only_sources")
                summary_paper_safe_sources = parse_summary_count("paper_safe_sources")

            if (
                summary_total_bound_sources is not None
                and summary_total_bound_sources != record_total_bound_sources
            ):
                mismatched_fields.add("total_bound_sources")
            if (
                summary_verified_sources is not None
                and summary_verified_sources != record_verified_sources
            ):
                mismatched_fields.add("verified_sources")
            if (
                summary_simulation_only_sources is not None
                and summary_simulation_only_sources != record_simulation_only_sources
            ):
                mismatched_fields.add("simulation_only_sources")
            if (
                summary_paper_safe_sources is not None
                and summary_paper_safe_sources != record_paper_safe_sources
            ):
                mismatched_fields.add("paper_safe_sources")

            consistency_percentage = round(
                max(
                    0.0,
                    100.0
                    - len(missing_fields) * 15
                    - len(mismatched_fields) * 25
                    - malformed_record_count * 20,
                ),
                2,
            )

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source observation record/summary reconciliation was invalid because one or more persisted source records were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source observation record/summary reconciliation was degraded because persisted summary counts diverged from the source observation records."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source observation record/summary reconciliation was partial because one or more persisted summary fields were missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source observation summary counts remained aligned with the underlying source observation records."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceObservationRecordSummaryReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    record_total_bound_sources=record_total_bound_sources,
                    summary_total_bound_sources=summary_total_bound_sources,
                    record_verified_sources=record_verified_sources,
                    summary_verified_sources=summary_verified_sources,
                    record_simulation_only_sources=record_simulation_only_sources,
                    summary_simulation_only_sources=summary_simulation_only_sources,
                    record_paper_safe_sources=record_paper_safe_sources,
                    summary_paper_safe_sources=summary_paper_safe_sources,
                    missing_fields=tuple(sorted(missing_fields)),
                    mismatched_fields=tuple(sorted(mismatched_fields)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            consistency_classification = "invalid"
        elif degraded_snapshots > 0:
            consistency_classification = "degraded"
        elif partial_snapshots > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        average_consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Source observation record/summary reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted summary field(s) were missing during record/summary reconciliation analysis."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted summary count field(s) diverged from the underlying source observation records."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during record/summary reconciliation analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation record/summary reconciliation analysis."
            )

        return SnapshotSourceObservationRecordSummaryReconciliation(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_fields=tuple(sorted(aggregate_missing_fields)),
            mismatched_fields=tuple(sorted(aggregate_mismatched_fields)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_normalization_mode_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationNormalizationModeDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation normalization mode drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation normalization mode drift analysis."
                )
            return SnapshotSourceObservationNormalizationModeDrift(
                drift_classification="insufficient_data",
                average_mode_consistency_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                dominant_normalization_mode=None,
                latest_normalization_mode=None,
                normalization_mode_counts={},
                mode_transition_count=0,
                malformed_summary_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceObservationNormalizationModeDriftEntry] = []
        normalization_mode_counts: Counter[str] = Counter()
        stable_snapshots = 0
        drifting_snapshots = 0
        degraded_snapshots = 0
        insufficient_data_snapshots = 0
        mode_transition_count = 0
        malformed_summary_count = 0
        previous_mode: str | None = None
        latest_normalization_mode: str | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_observation_summary")
            malformed_field_count = 0
            normalization_mode: str | None = None
            total_bound_sources: int | None = None

            if not isinstance(summary, Mapping):
                malformed_field_count += 1
            else:
                raw_normalization_mode = summary.get("normalization_mode")
                if (
                    isinstance(raw_normalization_mode, str)
                    and raw_normalization_mode.strip() in VALID_NORMALIZATION_MODES
                ):
                    normalization_mode = raw_normalization_mode.strip()
                else:
                    malformed_field_count += 1

                raw_total_bound_sources = summary.get("total_bound_sources")
                if raw_total_bound_sources is None:
                    total_bound_sources = None
                elif isinstance(raw_total_bound_sources, int) and not isinstance(raw_total_bound_sources, bool):
                    total_bound_sources = int(raw_total_bound_sources)
                else:
                    malformed_field_count += 1

            if normalization_mode is None:
                insufficient_data_snapshots += 1
                malformed_summary_count += max(1, malformed_field_count)
                entries.append(
                    SnapshotSourceObservationNormalizationModeDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        normalization_mode=None,
                        previous_normalization_mode=previous_mode,
                        mode_consistency_score=0.0,
                        total_bound_sources=total_bound_sources,
                        malformed_field_count=max(1, malformed_field_count),
                        diagnostic=(
                            "Source observation normalization mode drift could not be evaluated because the persisted normalization mode was missing or malformed."
                        ),
                    )
                )
                continue

            normalization_mode_counts[normalization_mode] += 1
            latest_normalization_mode = normalization_mode

            if previous_mode is None:
                drift_classification = "stable"
                mode_consistency_score = 100.0
                stable_snapshots += 1
                diagnostic = "Source observation normalization mode established the replay baseline."
            elif normalization_mode == previous_mode:
                drift_classification = "stable"
                mode_consistency_score = 100.0
                stable_snapshots += 1
                diagnostic = "Source observation normalization mode remained stable compared with the previous saved snapshot."
            else:
                drift_classification = "drifting"
                mode_consistency_score = 50.0
                mode_transition_count += 1
                drifting_snapshots += 1
                diagnostic = (
                    f"Source observation normalization mode drifted from {previous_mode} to {normalization_mode} compared with the previous saved snapshot."
                )

            if malformed_field_count > 0:
                malformed_summary_count += malformed_field_count
                if drift_classification == "stable" and stable_snapshots > 0:
                    stable_snapshots -= 1
                elif drift_classification == "drifting" and drifting_snapshots > 0:
                    drifting_snapshots -= 1
                drift_classification = "degraded"
                mode_consistency_score = min(mode_consistency_score, 75.0)
                degraded_snapshots += 1
                diagnostic = (
                    "Source observation normalization mode was present but companion persisted summary fields were malformed."
                )

            entries.append(
                SnapshotSourceObservationNormalizationModeDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    normalization_mode=normalization_mode,
                    previous_normalization_mode=previous_mode,
                    mode_consistency_score=mode_consistency_score,
                    total_bound_sources=total_bound_sources,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )
            previous_mode = normalization_mode

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_mode_consistency_score = 0.0
            severity_score = 0
            dominant_normalization_mode = None
        else:
            average_mode_consistency_score = round(
                sum(entry.mode_consistency_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            dominant_normalization_mode = sorted(
                normalization_mode_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]
            if degraded_snapshots > 0:
                drift_classification = "degraded"
            elif mode_transition_count > 0:
                drift_classification = "drifting"
            else:
                drift_classification = "stable"
            severity_score = int(round(max(0.0, 100.0 - valid_entries[-1].mode_consistency_score)))

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation normalization mode remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "drifting":
            diagnostics.append(
                f"Source observation normalization mode drifted across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degraded":
            diagnostics.append(
                f"Source observation normalization mode was degraded across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation normalization mode drift had insufficient usable data.")

        if mode_transition_count > 0:
            diagnostics.append(
                f"Source observation normalization mode changed {mode_transition_count} time(s) across the saved snapshots."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source observation summary field issue(s) were detected during normalization mode drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation normalization mode drift analysis."
            )

        return SnapshotSourceObservationNormalizationModeDrift(
            drift_classification=drift_classification,
            average_mode_consistency_score=average_mode_consistency_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            dominant_normalization_mode=dominant_normalization_mode,
            latest_normalization_mode=latest_normalization_mode,
            normalization_mode_counts=dict(sorted(normalization_mode_counts.items())),
            mode_transition_count=mode_transition_count,
            malformed_summary_count=malformed_summary_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_mapped_at_alignment_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotMappedAtAlignmentConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for mapped-at alignment consistency analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during mapped-at alignment consistency analysis."
                )
            return SnapshotMappedAtAlignmentConsistency(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_mapped_at_source_ids=(),
                batch_anchor_mismatch_source_ids=(),
                stored_at_alignment_mismatch_source_ids=(),
                source_observation_alignment_mismatch_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotMappedAtAlignmentConsistencyEntry] = []
        aggregate_missing_mapped_at_source_ids: set[str] = set()
        aggregate_batch_anchor_mismatch_source_ids: set[str] = set()
        aggregate_stored_at_alignment_mismatch_source_ids: set[str] = set()
        aggregate_source_observation_alignment_mismatch_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_observation_summary")
            source_observation_records = snapshot_payload.get("source_observation_records")
            source_observations = snapshot_payload.get("source_observations")

            normalization_mode: str | None = None
            if isinstance(summary, Mapping):
                raw_mode = summary.get("normalization_mode")
                if isinstance(raw_mode, str) and raw_mode.strip() in VALID_NORMALIZATION_MODES:
                    normalization_mode = raw_mode.strip()

            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotMappedAtAlignmentConsistencyEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        consistency_classification="invalid",
                        consistency_percentage=0.0,
                        normalization_mode=normalization_mode,
                        batch_anchor=None,
                        total_records=0,
                        aligned_records=0,
                        missing_mapped_at_source_ids=(),
                        batch_anchor_mismatch_source_ids=(),
                        stored_at_alignment_mismatch_source_ids=(),
                        source_observation_alignment_mismatch_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Mapped-at alignment consistency could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            aligned_records = 0
            missing_mapped_at_source_ids: set[str] = set()
            batch_anchor_mismatch_source_ids: set[str] = set()
            stored_at_alignment_mismatch_source_ids: set[str] = set()
            source_observation_alignment_mismatch_source_ids: set[str] = set()
            malformed_record_count = 0
            stored_at_values: list[datetime] = []
            normalized_records: list[tuple[str, datetime, datetime]] = []

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                raw_stored_at = record.get("stored_at")
                raw_mapped_at = record.get("mapped_at")
                if (
                    not isinstance(raw_stored_at, str)
                    or not raw_stored_at.strip()
                    or not isinstance(raw_mapped_at, str)
                    or not raw_mapped_at.strip()
                ):
                    missing_mapped_at_source_ids.add(source_id)
                    continue

                try:
                    stored_at = self._parse_datetime(raw_stored_at)
                    mapped_at = self._parse_datetime(raw_mapped_at)
                except Exception:
                    missing_mapped_at_source_ids.add(source_id)
                    continue

                stored_at_values.append(stored_at)
                normalized_records.append((source_id, stored_at, mapped_at))

            batch_anchor = max(stored_at_values).isoformat() if stored_at_values else None

            for source_id, stored_at, mapped_at in normalized_records:
                record_aligned = True

                if normalization_mode == "batch_stored_at":
                    if batch_anchor is None or mapped_at.isoformat() != batch_anchor:
                        batch_anchor_mismatch_source_ids.add(source_id)
                        record_aligned = False
                elif normalization_mode == "per_source_stored_at":
                    if mapped_at != stored_at:
                        stored_at_alignment_mismatch_source_ids.add(source_id)
                        record_aligned = False
                else:
                    record_aligned = False

                expected_observation_value = None
                if isinstance(source_observations, Mapping):
                    raw_observation_value = source_observations.get(source_id)
                    if isinstance(raw_observation_value, str) and raw_observation_value.strip():
                        expected_observation_value = raw_observation_value.strip()

                if expected_observation_value != mapped_at.isoformat():
                    source_observation_alignment_mismatch_source_ids.add(source_id)
                    record_aligned = False

                if record_aligned:
                    aligned_records += 1

            consistency_percentage = round(
                (aligned_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if normalization_mode is None or malformed_record_count > 0:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Mapped-at alignment consistency was invalid because persisted normalization metadata or source observation records were malformed."
                )
            elif (
                batch_anchor_mismatch_source_ids
                or stored_at_alignment_mismatch_source_ids
                or source_observation_alignment_mismatch_source_ids
            ):
                consistency_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Mapped-at alignment consistency was degraded because persisted mapped-at values diverged from the declared normalization strategy."
                )
            elif missing_mapped_at_source_ids:
                consistency_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Mapped-at alignment consistency was partial because one or more mapped-at values were missing or unusable."
                )
            else:
                consistency_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted mapped-at values remained aligned with the declared normalization mode and source observation map."
                )

            aggregate_missing_mapped_at_source_ids.update(missing_mapped_at_source_ids)
            aggregate_batch_anchor_mismatch_source_ids.update(batch_anchor_mismatch_source_ids)
            aggregate_stored_at_alignment_mismatch_source_ids.update(stored_at_alignment_mismatch_source_ids)
            aggregate_source_observation_alignment_mismatch_source_ids.update(
                source_observation_alignment_mismatch_source_ids
            )
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotMappedAtAlignmentConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    normalization_mode=normalization_mode,
                    batch_anchor=batch_anchor,
                    total_records=total_records,
                    aligned_records=aligned_records,
                    missing_mapped_at_source_ids=tuple(sorted(missing_mapped_at_source_ids)),
                    batch_anchor_mismatch_source_ids=tuple(sorted(batch_anchor_mismatch_source_ids)),
                    stored_at_alignment_mismatch_source_ids=tuple(sorted(stored_at_alignment_mismatch_source_ids)),
                    source_observation_alignment_mismatch_source_ids=tuple(
                        sorted(source_observation_alignment_mismatch_source_ids)
                    ),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            consistency_classification = "invalid"
        elif degraded_snapshots > 0:
            consistency_classification = "degraded"
        elif partial_snapshots > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        average_consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Mapped-at alignment consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_mapped_at_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_mapped_at_source_ids)} source ID(s) were missing usable mapped-at metadata."
            )
        if aggregate_batch_anchor_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_batch_anchor_mismatch_source_ids)} source ID(s) diverged from the expected batch anchor mapped-at value."
            )
        if aggregate_stored_at_alignment_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_stored_at_alignment_mismatch_source_ids)} source ID(s) diverged from stored-at alignment under per-source normalization."
            )
        if aggregate_source_observation_alignment_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_source_observation_alignment_mismatch_source_ids)} source ID(s) diverged from the persisted source observation map."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during mapped-at alignment analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during mapped-at alignment consistency analysis."
            )

        return SnapshotMappedAtAlignmentConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_mapped_at_source_ids=tuple(sorted(aggregate_missing_mapped_at_source_ids)),
            batch_anchor_mismatch_source_ids=tuple(sorted(aggregate_batch_anchor_mismatch_source_ids)),
            stored_at_alignment_mismatch_source_ids=tuple(
                sorted(aggregate_stored_at_alignment_mismatch_source_ids)
            ),
            source_observation_alignment_mismatch_source_ids=tuple(
                sorted(aggregate_source_observation_alignment_mismatch_source_ids)
            ),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_confidence_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationConfidenceDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation confidence drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation confidence drift analysis."
                )
            return SnapshotSourceObservationConfidenceDrift(
                drift_classification="insufficient_data",
                average_confidence_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                degraded_source_ids=(),
                improved_source_ids=(),
                missing_confidence_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        def normalize_confidence_score(raw_value: object) -> float:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError("confidence must be numeric")
            numeric_value = float(raw_value)
            if 0.0 <= numeric_value <= 1.0:
                return round(numeric_value * 100.0, 2)
            if 0.0 <= numeric_value <= 100.0:
                return round(numeric_value, 2)
            raise ValueError("confidence must be between 0 and 1 or between 0 and 100")

        entries: list[SnapshotSourceObservationConfidenceDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        aggregate_degraded_source_ids: set[str] = set()
        aggregate_improved_source_ids: set[str] = set()
        aggregate_missing_confidence_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        previous_confidence_by_source: dict[str, float] | None = None
        previous_average_confidence_score: float | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationConfidenceDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_confidence_score=0.0,
                        previous_average_confidence_score=previous_average_confidence_score,
                        confidence_delta_from_previous=None,
                        total_records=0,
                        valid_confidence_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_confidence_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source observation confidence drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            confidence_by_source: dict[str, float] = {}
            missing_confidence_source_ids: set[str] = set()
            degraded_source_ids: set[str] = set()
            improved_source_ids: set[str] = set()
            malformed_record_count = 0

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                if "confidence" not in record or record.get("confidence") is None:
                    missing_confidence_source_ids.add(source_id)
                    continue

                try:
                    confidence_by_source[source_id] = normalize_confidence_score(record.get("confidence"))
                except Exception:
                    malformed_record_count += 1
                    continue

            valid_confidence_records = len(confidence_by_source)
            if valid_confidence_records == 0:
                insufficient_data_snapshots += 1
                aggregate_missing_confidence_source_ids.update(missing_confidence_source_ids)
                aggregate_malformed_record_count += malformed_record_count
                entries.append(
                    SnapshotSourceObservationConfidenceDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_confidence_score=0.0,
                        previous_average_confidence_score=previous_average_confidence_score,
                        confidence_delta_from_previous=None,
                        total_records=total_records,
                        valid_confidence_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_confidence_source_ids=tuple(sorted(missing_confidence_source_ids)),
                        malformed_record_count=malformed_record_count,
                        diagnostic="Source observation confidence drift had insufficient usable confidence metadata in this saved snapshot.",
                    )
                )
                continue

            average_confidence_score = round(
                sum(confidence_by_source.values()) / valid_confidence_records,
                2,
            )
            confidence_delta_from_previous: float | None = None

            if previous_confidence_by_source is None or previous_average_confidence_score is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = "Source observation confidence established the replay baseline."
            else:
                confidence_delta_from_previous = round(
                    average_confidence_score - previous_average_confidence_score,
                    2,
                )
                for source_id, confidence_score in confidence_by_source.items():
                    previous_score = previous_confidence_by_source.get(source_id)
                    if previous_score is None:
                        continue
                    if confidence_score > previous_score:
                        improved_source_ids.add(source_id)
                    elif confidence_score < previous_score:
                        degraded_source_ids.add(source_id)

                if degraded_source_ids and improved_source_ids:
                    drift_classification = "mixed"
                    mixed_snapshots += 1
                    diagnostic = (
                        "Source observation confidence drift was mixed because some sources improved while others deteriorated compared with the previous saved snapshot."
                    )
                elif degraded_source_ids:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = (
                        "Source observation confidence drift deteriorated compared with the previous saved snapshot."
                    )
                elif improved_source_ids:
                    drift_classification = "improving"
                    improving_snapshots += 1
                    diagnostic = (
                        "Source observation confidence drift improved compared with the previous saved snapshot."
                    )
                else:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = (
                        "Source observation confidence remained stable compared with the previous saved snapshot."
                    )

            aggregate_degraded_source_ids.update(degraded_source_ids)
            aggregate_improved_source_ids.update(improved_source_ids)
            aggregate_missing_confidence_source_ids.update(missing_confidence_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceObservationConfidenceDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    average_confidence_score=average_confidence_score,
                    previous_average_confidence_score=previous_average_confidence_score,
                    confidence_delta_from_previous=confidence_delta_from_previous,
                    total_records=total_records,
                    valid_confidence_records=valid_confidence_records,
                    degraded_source_ids=tuple(sorted(degraded_source_ids)),
                    improved_source_ids=tuple(sorted(improved_source_ids)),
                    missing_confidence_source_ids=tuple(sorted(missing_confidence_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )
            previous_confidence_by_source = dict(confidence_by_source)
            previous_average_confidence_score = average_confidence_score

        snapshots_checked = len(entries)
        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_confidence_score = 0.0
            severity_score = 0
        else:
            average_confidence_score = round(
                sum(entry.average_confidence_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            if mixed_snapshots > 0 or (degrading_snapshots > 0 and improving_snapshots > 0):
                drift_classification = "mixed"
            elif degrading_snapshots > 0:
                drift_classification = "degrading"
            elif improving_snapshots > 0:
                drift_classification = "improving"
            else:
                drift_classification = "stable"

            severity_score = int(
                round(
                    max(
                        abs(entry.confidence_delta_from_previous or 0.0)
                        for entry in valid_entries
                    )
                )
            )

        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation confidence remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation confidence deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation confidence improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation confidence drift was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation confidence drift had insufficient usable data.")

        if aggregate_missing_confidence_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_confidence_source_ids)} source ID(s) were missing persisted confidence metadata."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during confidence drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation confidence drift analysis."
            )

        return SnapshotSourceObservationConfidenceDrift(
            drift_classification=drift_classification,
            average_confidence_score=average_confidence_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            degraded_source_ids=tuple(sorted(aggregate_degraded_source_ids)),
            improved_source_ids=tuple(sorted(aggregate_improved_source_ids)),
            missing_confidence_source_ids=tuple(sorted(aggregate_missing_confidence_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_verified_source_coverage_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotVerifiedSourceCoverageReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for verified-source coverage reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during verified-source coverage reconciliation analysis."
                )
            return SnapshotVerifiedSourceCoverageReconciliation(
                consistency_classification="invalid",
                average_coverage_percentage=0.0,
                expected_verified_source_count=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_verified_source_ids=(),
                unexpected_verified_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        registry_entries = build_source_registry_entries(source_registry)
        expected_verified_source_ids = tuple(
            sorted(
                entry.source_id
                for entry in registry_entries
                if entry.active and entry.verified
            )
        )
        expected_verified_source_id_set = set(expected_verified_source_ids)

        entries: list[SnapshotVerifiedSourceCoverageReconciliationEntry] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_verified_source_ids: set[str] = set()
        aggregate_unexpected_verified_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotVerifiedSourceCoverageReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        coverage_percentage=0.0,
                        expected_verified_source_count=len(expected_verified_source_ids),
                        observed_verified_source_count=0,
                        matched_verified_source_count=0,
                        missing_verified_source_ids=expected_verified_source_ids,
                        unexpected_verified_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Verified-source coverage reconciliation could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            observed_verified_source_ids: set[str] = set()
            malformed_record_count = 0
            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                verified_flag = record.get("verified")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                if not isinstance(verified_flag, bool):
                    malformed_record_count += 1
                    continue
                if verified_flag:
                    observed_verified_source_ids.add(raw_source_id.strip())

            matched_verified_source_ids = expected_verified_source_id_set & observed_verified_source_ids
            missing_verified_source_ids = expected_verified_source_id_set - observed_verified_source_ids
            unexpected_verified_source_ids = observed_verified_source_ids - expected_verified_source_id_set
            coverage_percentage = round(
                (len(matched_verified_source_ids) / max(len(expected_verified_source_ids), 1)) * 100.0,
                2,
            )

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Verified-source coverage reconciliation was invalid because one or more persisted source observation records were malformed."
                )
            elif not missing_verified_source_ids and not unexpected_verified_source_ids:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted verified-source coverage matched the current active verified source registry set."
                )
            elif coverage_percentage >= 70.0 and not unexpected_verified_source_ids:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Persisted verified-source coverage was partial because one or more expected verified sources were missing."
                )
            else:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted verified-source coverage was degraded because expected verified sources were missing or unexpected verified sources appeared."
                )

            aggregate_missing_verified_source_ids.update(missing_verified_source_ids)
            aggregate_unexpected_verified_source_ids.update(unexpected_verified_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotVerifiedSourceCoverageReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    coverage_percentage=coverage_percentage,
                    expected_verified_source_count=len(expected_verified_source_ids),
                    observed_verified_source_count=len(observed_verified_source_ids),
                    matched_verified_source_count=len(matched_verified_source_ids),
                    missing_verified_source_ids=tuple(sorted(missing_verified_source_ids)),
                    unexpected_verified_source_ids=tuple(sorted(unexpected_verified_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            consistency_classification = "invalid"
        elif degraded_snapshots > 0:
            consistency_classification = "degraded"
        elif partial_snapshots > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        average_coverage_percentage = round(
            sum(entry.coverage_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Verified-source coverage reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_verified_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_verified_source_ids)} expected verified source ID(s) were missing from persisted verified coverage."
            )
        if aggregate_unexpected_verified_source_ids:
            diagnostics.append(
                f"{len(aggregate_unexpected_verified_source_ids)} persisted source ID(s) were marked verified but are not in the current active verified registry set."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during verified-source coverage reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during verified-source coverage reconciliation analysis."
            )

        return SnapshotVerifiedSourceCoverageReconciliation(
            consistency_classification=consistency_classification,
            average_coverage_percentage=average_coverage_percentage,
            expected_verified_source_count=len(expected_verified_source_ids),
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_verified_source_ids=tuple(sorted(aggregate_missing_verified_source_ids)),
            unexpected_verified_source_ids=tuple(sorted(aggregate_unexpected_verified_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_availability_lag_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationAvailabilityLagDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation availability-lag drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation availability-lag drift analysis."
                )
            return SnapshotSourceObservationAvailabilityLagDrift(
                drift_classification="insufficient_data",
                average_lag_seconds=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                degraded_source_ids=(),
                improved_source_ids=(),
                missing_timestamp_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceObservationAvailabilityLagDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        aggregate_degraded_source_ids: set[str] = set()
        aggregate_improved_source_ids: set[str] = set()
        aggregate_missing_timestamp_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        previous_lag_by_source: dict[str, float] | None = None
        previous_average_lag_seconds: float | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationAvailabilityLagDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_lag_seconds=0.0,
                        previous_average_lag_seconds=previous_average_lag_seconds,
                        lag_delta_from_previous_seconds=None,
                        total_records=0,
                        valid_lag_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_timestamp_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source observation availability-lag drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            lag_by_source: dict[str, float] = {}
            degraded_source_ids: set[str] = set()
            improved_source_ids: set[str] = set()
            missing_timestamp_source_ids: set[str] = set()
            malformed_record_count = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                raw_observed_at = record.get("observed_at")
                raw_available_at = record.get("available_at")
                if (
                    not isinstance(raw_observed_at, str)
                    or not raw_observed_at.strip()
                    or not isinstance(raw_available_at, str)
                    or not raw_available_at.strip()
                ):
                    missing_timestamp_source_ids.add(source_id)
                    continue

                try:
                    observed_at = self._parse_datetime(raw_observed_at)
                    available_at = self._parse_datetime(raw_available_at)
                except Exception:
                    malformed_record_count += 1
                    continue

                lag_seconds = round((available_at - observed_at).total_seconds(), 2)
                lag_by_source[source_id] = lag_seconds

            valid_lag_records = len(lag_by_source)
            if valid_lag_records == 0:
                insufficient_data_snapshots += 1
                aggregate_missing_timestamp_source_ids.update(missing_timestamp_source_ids)
                aggregate_malformed_record_count += malformed_record_count
                entries.append(
                    SnapshotSourceObservationAvailabilityLagDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_lag_seconds=0.0,
                        previous_average_lag_seconds=previous_average_lag_seconds,
                        lag_delta_from_previous_seconds=None,
                        total_records=total_records,
                        valid_lag_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_timestamp_source_ids=tuple(sorted(missing_timestamp_source_ids)),
                        malformed_record_count=malformed_record_count,
                        diagnostic="Source observation availability-lag drift had insufficient usable timestamp metadata in this saved snapshot.",
                    )
                )
                continue

            average_lag_seconds = round(
                sum(lag_by_source.values()) / valid_lag_records,
                2,
            )
            lag_delta_from_previous_seconds: float | None = None

            if previous_lag_by_source is None or previous_average_lag_seconds is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = "Source observation availability lag established the replay baseline."
            else:
                lag_delta_from_previous_seconds = round(
                    average_lag_seconds - previous_average_lag_seconds,
                    2,
                )
                for source_id, lag_seconds in lag_by_source.items():
                    previous_lag_seconds = previous_lag_by_source.get(source_id)
                    if previous_lag_seconds is None:
                        continue
                    if lag_seconds > previous_lag_seconds:
                        degraded_source_ids.add(source_id)
                    elif lag_seconds < previous_lag_seconds:
                        improved_source_ids.add(source_id)

                if degraded_source_ids and improved_source_ids:
                    drift_classification = "mixed"
                    mixed_snapshots += 1
                    diagnostic = (
                        "Source observation availability lag was mixed because some source lags increased while others decreased compared with the previous saved snapshot."
                    )
                elif degraded_source_ids:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = (
                        "Source observation availability lag deteriorated compared with the previous saved snapshot."
                    )
                elif improved_source_ids:
                    drift_classification = "improving"
                    improving_snapshots += 1
                    diagnostic = (
                        "Source observation availability lag improved compared with the previous saved snapshot."
                    )
                else:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = (
                        "Source observation availability lag remained stable compared with the previous saved snapshot."
                    )

            aggregate_degraded_source_ids.update(degraded_source_ids)
            aggregate_improved_source_ids.update(improved_source_ids)
            aggregate_missing_timestamp_source_ids.update(missing_timestamp_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceObservationAvailabilityLagDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    average_lag_seconds=average_lag_seconds,
                    previous_average_lag_seconds=previous_average_lag_seconds,
                    lag_delta_from_previous_seconds=lag_delta_from_previous_seconds,
                    total_records=total_records,
                    valid_lag_records=valid_lag_records,
                    degraded_source_ids=tuple(sorted(degraded_source_ids)),
                    improved_source_ids=tuple(sorted(improved_source_ids)),
                    missing_timestamp_source_ids=tuple(sorted(missing_timestamp_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )
            previous_lag_by_source = dict(lag_by_source)
            previous_average_lag_seconds = average_lag_seconds

        snapshots_checked = len(entries)
        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_lag_seconds = 0.0
            severity_score = 0
        else:
            average_lag_seconds = round(
                sum(entry.average_lag_seconds for entry in valid_entries) / len(valid_entries),
                2,
            )
            if mixed_snapshots > 0 or (degrading_snapshots > 0 and improving_snapshots > 0):
                drift_classification = "mixed"
            elif degrading_snapshots > 0:
                drift_classification = "degrading"
            elif improving_snapshots > 0:
                drift_classification = "improving"
            else:
                drift_classification = "stable"
            severity_score = int(
                round(
                    max(
                        abs(entry.lag_delta_from_previous_seconds or 0.0)
                        for entry in valid_entries
                    )
                )
            )

        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation availability lag remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation availability lag deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation availability lag improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation availability lag was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation availability-lag drift had insufficient usable data.")

        if aggregate_missing_timestamp_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_timestamp_source_ids)} source ID(s) were missing observed or available timestamps."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during availability-lag drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation availability-lag drift analysis."
            )

        return SnapshotSourceObservationAvailabilityLagDrift(
            drift_classification=drift_classification,
            average_lag_seconds=average_lag_seconds,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            degraded_source_ids=tuple(sorted(aggregate_degraded_source_ids)),
            improved_source_ids=tuple(sorted(aggregate_improved_source_ids)),
            missing_timestamp_source_ids=tuple(sorted(aggregate_missing_timestamp_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_freshness_summary_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceFreshnessSummaryReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source freshness summary reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source freshness summary reconciliation analysis."
                )
            return SnapshotSourceFreshnessSummaryReconciliation(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_freshness_source_ids=(),
                record_only_stale_source_ids=(),
                summary_only_stale_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceFreshnessSummaryReconciliationEntry] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_freshness_source_ids: set[str] = set()
        aggregate_record_only_stale_source_ids: set[str] = set()
        aggregate_summary_only_stale_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            summary_stale_sources = snapshot_payload.get("stale_sources", ())
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceFreshnessSummaryReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        aligned_records=0,
                        record_stale_source_count=0,
                        summary_stale_source_count=0,
                        record_degraded_source_count=0,
                        record_fresh_source_count=0,
                        missing_freshness_source_ids=(),
                        record_only_stale_source_ids=(),
                        summary_only_stale_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source freshness summary reconciliation could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            if not isinstance(summary_stale_sources, (list, tuple)):
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceFreshnessSummaryReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=len(source_observation_records),
                        aligned_records=0,
                        record_stale_source_count=0,
                        summary_stale_source_count=0,
                        record_degraded_source_count=0,
                        record_fresh_source_count=0,
                        missing_freshness_source_ids=(),
                        record_only_stale_source_ids=(),
                        summary_only_stale_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source freshness summary reconciliation could not be evaluated because persisted stale-sources summary metadata was malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            aligned_records = 0
            malformed_record_count = 0
            missing_freshness_source_ids: set[str] = set()
            record_stale_source_ids: set[str] = set()
            record_degraded_source_ids: set[str] = set()
            record_fresh_source_ids: set[str] = set()
            summary_stale_source_id_set = {
                source_id.strip()
                for source_id in summary_stale_sources
                if isinstance(source_id, str) and source_id.strip()
            }

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                freshness_status = record.get("freshness_status")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                if not isinstance(freshness_status, str) or not freshness_status.strip():
                    missing_freshness_source_ids.add(source_id)
                    continue

                normalized_status = freshness_status.strip()
                if normalized_status == "stale":
                    record_stale_source_ids.add(source_id)
                elif normalized_status == "degraded":
                    record_degraded_source_ids.add(source_id)
                elif normalized_status == "fresh":
                    record_fresh_source_ids.add(source_id)
                else:
                    missing_freshness_source_ids.add(source_id)
                    continue

                if (
                    (normalized_status == "stale" and source_id in summary_stale_source_id_set)
                    or (normalized_status != "stale" and source_id not in summary_stale_source_id_set)
                ):
                    aligned_records += 1

            record_only_stale_source_ids = record_stale_source_ids - summary_stale_source_id_set
            summary_only_stale_source_ids = summary_stale_source_id_set - record_stale_source_ids
            consistency_percentage = round(
                (aligned_records / total_records) * 100.0,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source freshness summary reconciliation was invalid because one or more source observation records were malformed."
                )
            elif record_only_stale_source_ids or summary_only_stale_source_ids:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source freshness summary reconciliation was degraded because record-level stale source IDs diverged from the persisted stale-sources summary."
                )
            elif missing_freshness_source_ids:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source freshness summary reconciliation was partial because one or more source observation records were missing usable freshness metadata."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted stale-source summary remained aligned with record-level freshness metadata."
                )

            aggregate_missing_freshness_source_ids.update(missing_freshness_source_ids)
            aggregate_record_only_stale_source_ids.update(record_only_stale_source_ids)
            aggregate_summary_only_stale_source_ids.update(summary_only_stale_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceFreshnessSummaryReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    aligned_records=aligned_records,
                    record_stale_source_count=len(record_stale_source_ids),
                    summary_stale_source_count=len(summary_stale_source_id_set),
                    record_degraded_source_count=len(record_degraded_source_ids),
                    record_fresh_source_count=len(record_fresh_source_ids),
                    missing_freshness_source_ids=tuple(sorted(missing_freshness_source_ids)),
                    record_only_stale_source_ids=tuple(sorted(record_only_stale_source_ids)),
                    summary_only_stale_source_ids=tuple(sorted(summary_only_stale_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            consistency_classification = "invalid"
        elif degraded_snapshots > 0:
            consistency_classification = "degraded"
        elif partial_snapshots > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        average_consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Source freshness summary reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_freshness_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_freshness_source_ids)} source ID(s) were missing usable freshness metadata."
            )
        if aggregate_record_only_stale_source_ids:
            diagnostics.append(
                f"{len(aggregate_record_only_stale_source_ids)} stale source ID(s) appeared only in record-level freshness metadata."
            )
        if aggregate_summary_only_stale_source_ids:
            diagnostics.append(
                f"{len(aggregate_summary_only_stale_source_ids)} stale source ID(s) appeared only in the persisted stale-sources summary."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during source freshness summary reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source freshness summary reconciliation analysis."
            )

        return SnapshotSourceFreshnessSummaryReconciliation(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_freshness_source_ids=tuple(sorted(aggregate_missing_freshness_source_ids)),
            record_only_stale_source_ids=tuple(sorted(aggregate_record_only_stale_source_ids)),
            summary_only_stale_source_ids=tuple(sorted(aggregate_summary_only_stale_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_no_execution_guardrail_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotNoExecutionGuardrailConsistency:
        diagnostics: list[str] = []
        entries: list[SnapshotNoExecutionGuardrailEntry] = []
        violations: list[SnapshotNoExecutionGuardrailEntry] = []

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)
            report_type = str(snapshot_payload.get("report_type", "unknown"))
            mode = str(snapshot_payload.get("mode", "unknown"))
            execution_mode = str(snapshot_payload.get("execution_mode", "unknown"))
            decision_permission = str(snapshot_payload.get("decision_permission", "unknown"))

            violation_codes: list[str] = []
            if decision_permission != "NO_EXECUTION":
                violation_codes.append("DECISION_PERMISSION_BREACH")
            if execution_mode not in SnapshotStore.ALLOWED_EXECUTION_MODES:
                violation_codes.append("UNSAFE_EXECUTION_MODE")
            if mode not in SnapshotStore.ALLOWED_MODES:
                violation_codes.append("UNSAFE_MODE")

            if violation_codes:
                diagnostic = (
                    "Snapshot violated the paper-safe NO_EXECUTION guardrail: "
                    + ", ".join(violation_codes)
                    + "."
                )
            else:
                diagnostic = "Snapshot preserved the NO_EXECUTION guardrail."

            entry = SnapshotNoExecutionGuardrailEntry(
                snapshot_id=snapshot_id,
                created_at=created_at,
                report_type=report_type,
                mode=mode,
                execution_mode=execution_mode,
                decision_permission=decision_permission,
                consistent=not violation_codes,
                violation_codes=tuple(violation_codes),
                diagnostic=diagnostic,
            )
            entries.append(entry)
            if violation_codes:
                violations.append(entry)

        if not entries:
            diagnostics.append("No saved snapshots were available for NO_EXECUTION guardrail consistency analysis.")
        elif violations:
            diagnostics.append(
                f"Detected {len(violations)} NO_EXECUTION guardrail violation(s) across {len(entries)} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                f"All {len(entries)} saved snapshot(s) preserved the NO_EXECUTION guardrail."
            )

        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during NO_EXECUTION guardrail analysis."
            )

        if not entries:
            consistency_status = "insufficient_data"
        elif violations:
            consistency_status = "violations_detected"
        else:
            consistency_status = "consistent"

        return SnapshotNoExecutionGuardrailConsistency(
            consistency_status=consistency_status,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=len(entries),
            consistent_snapshots=sum(1 for entry in entries if entry.consistent),
            violation_count=len(violations),
            entries=tuple(entries),
            violations=tuple(violations),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
