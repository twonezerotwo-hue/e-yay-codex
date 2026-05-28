
from __future__ import annotations

from app.services.risk_engine import RiskAction
from app.services.snapshot_replay_core import SnapshotReplayCore
from app.services.snapshot_replay_models import SnapshotAnomalyWatchlistDiagnostics
from app.services.snapshot_replay_models import SnapshotAnomalyWatchlistItem
from app.services.snapshot_replay_models import SnapshotComparisonResult
from app.services.snapshot_replay_models import SnapshotDriftClassification
from app.services.snapshot_replay_models import SnapshotDriftTrendLeaderboard
from app.services.snapshot_replay_models import SnapshotDriftTrendLeaderboardEntry
from app.services.snapshot_replay_models import SnapshotDriftTrendScore
from app.services.snapshot_replay_models import SnapshotReplayResult
from app.services.snapshot_replay_models import SnapshotTriggerPersistenceLeaderboard
from app.services.snapshot_replay_models import SnapshotTriggerPersistenceLeaderboardEntry
from app.services.trigger_engine import TriggerSeverity

SEVERITY_PRIORITY = {
    TriggerSeverity.INFO: 0,
    TriggerSeverity.YELLOW: 1,
    TriggerSeverity.ORANGE: 2,
    TriggerSeverity.RED: 3,
}

DRIFT_TREND_WEIGHTS = {
    'CONDITIONS_IMPROVED': -2,
    'STABLE': 0,
    'TRIGGER_SET_EXPANDED': 1,
    'SOURCE_FRESHNESS_DEGRADED': 2,
    'RISK_GUARDRAIL_TIGHTENED': 2,
    'SOURCE_COVERAGE_DEGRADED': 3,
    'RISK_ESCALATION_MULTI_SIGNAL': 3,
    'KILL_SWITCH_ACTIVATED': 4,
    'SAFETY_GUARDRAIL_BREACH': 5,
}


class SnapshotReplayTransitionDiagnostics(SnapshotReplayCore):
    def classify_comparison_result(
        self,
        comparison_result: SnapshotComparisonResult,
    ) -> SnapshotDriftClassification:
        anomaly_flags = self._build_anomaly_flags(comparison_result)

        if not comparison_result.paper_safe or not comparison_result.execution_status_consistent:
            drift_code = "SAFETY_GUARDRAIL_BREACH"
            severity = TriggerSeverity.RED
            summary = "Replay safety guardrails diverged and the comparison must remain blocked from any execution path."
        elif comparison_result.kill_switch_changed and comparison_result.kill_switch_to:
            drift_code = "KILL_SWITCH_ACTIVATED"
            severity = TriggerSeverity.RED
            summary = "The candidate snapshot activates the kill switch and forces a full stop condition."
        elif comparison_result.risk_action_changed and comparison_result.risk_action_to == RiskAction.RISK_REDUCE.value:
            drift_code = "RISK_ESCALATION_MULTI_SIGNAL"
            severity = TriggerSeverity.ORANGE
            summary = "Risk posture escalated to RISK_REDUCE because multiple serious signals stacked in the candidate snapshot."
        elif comparison_result.risk_action_changed and comparison_result.risk_action_to == RiskAction.NO_POSITION_INCREASE.value:
            drift_code = "RISK_GUARDRAIL_TIGHTENED"
            severity = TriggerSeverity.YELLOW
            summary = "Risk posture tightened to NO_POSITION_INCREASE in the candidate snapshot."
        elif comparison_result.missing_sources_added:
            drift_code = "SOURCE_COVERAGE_DEGRADED"
            severity = TriggerSeverity.ORANGE
            summary = "The candidate snapshot added missing source coverage gaps."
        elif comparison_result.stale_sources_added:
            drift_code = "SOURCE_FRESHNESS_DEGRADED"
            severity = TriggerSeverity.YELLOW
            summary = "The candidate snapshot added stale-source exposure."
        elif comparison_result.new_trigger_codes:
            drift_code = "TRIGGER_SET_EXPANDED"
            severity = TriggerSeverity.YELLOW
            summary = "The candidate snapshot introduced new active triggers without changing higher-level risk controls."
        elif (
            comparison_result.cleared_trigger_codes
            or comparison_result.cleared_reason_codes
            or comparison_result.missing_sources_cleared
            or comparison_result.stale_sources_cleared
            or comparison_result.risk_action_changed
        ):
            drift_code = "CONDITIONS_IMPROVED"
            severity = TriggerSeverity.INFO
            summary = "The candidate snapshot improved or cleared previously active risk, trigger, or source conditions."
        else:
            drift_code = "STABLE"
            severity = TriggerSeverity.INFO
            summary = "No material deterministic drift was detected between the two saved snapshots."

        return SnapshotDriftClassification(
            baseline_snapshot_id=comparison_result.baseline_snapshot_id,
            candidate_snapshot_id=comparison_result.candidate_snapshot_id,
            drift_code=drift_code,
            severity=severity,
            summary=summary,
            anomaly_flags=anomaly_flags,
            paper_safe=comparison_result.paper_safe,
            execution_status_consistent=comparison_result.execution_status_consistent,
        )

    @staticmethod
    def _build_anomaly_flags(
        comparison_result: SnapshotComparisonResult,
    ) -> tuple[str, ...]:
        anomaly_flags: list[str] = []
        anomaly_flags.extend(
            f"NEW_TRIGGER:{trigger_code}"
            for trigger_code in comparison_result.new_trigger_codes
        )
        anomaly_flags.extend(
            f"CLEARED_TRIGGER:{trigger_code}"
            for trigger_code in comparison_result.cleared_trigger_codes
        )
        anomaly_flags.extend(
            f"NEW_REASON:{reason_code}"
            for reason_code in comparison_result.new_reason_codes
        )
        anomaly_flags.extend(
            f"CLEARED_REASON:{reason_code}"
            for reason_code in comparison_result.cleared_reason_codes
        )
        anomaly_flags.extend(
            f"MISSING_SOURCE_ADDED:{source_id}"
            for source_id in comparison_result.missing_sources_added
        )
        anomaly_flags.extend(
            f"MISSING_SOURCE_CLEARED:{source_id}"
            for source_id in comparison_result.missing_sources_cleared
        )
        anomaly_flags.extend(
            f"STALE_SOURCE_ADDED:{source_id}"
            for source_id in comparison_result.stale_sources_added
        )
        anomaly_flags.extend(
            f"STALE_SOURCE_CLEARED:{source_id}"
            for source_id in comparison_result.stale_sources_cleared
        )
        return tuple(anomaly_flags)

    def _build_anomaly_watchlist(
        self,
        drift_classifications: tuple[SnapshotDriftClassification, ...],
        comparison_results: tuple[SnapshotComparisonResult, ...],
    ) -> SnapshotAnomalyWatchlistDiagnostics:
        stable_transitions = 0
        improving_transitions = 0
        anomalous_transitions = 0
        watchlist_buckets: dict[str, dict[str, object]] = {}

        for drift_classification, comparison_result in zip(
            drift_classifications,
            comparison_results,
            strict=True,
        ):
            if drift_classification.drift_code == "STABLE":
                stable_transitions += 1
                continue

            if drift_classification.drift_code == "CONDITIONS_IMPROVED":
                improving_transitions += 1
                continue

            anomalous_transitions += 1
            bucket = watchlist_buckets.setdefault(
                drift_classification.drift_code,
                {
                    "severity": drift_classification.severity,
                    "occurrence_count": 0,
                    "first_snapshot_id": drift_classification.baseline_snapshot_id,
                    "latest_snapshot_id": drift_classification.candidate_snapshot_id,
                    "related_snapshot_pairs": [],
                    "trigger_codes": set(),
                    "reason_codes": set(),
                    "source_ids": set(),
                    "latest_summary": drift_classification.summary,
                },
            )
            bucket["occurrence_count"] = int(bucket["occurrence_count"]) + 1
            bucket["latest_snapshot_id"] = drift_classification.candidate_snapshot_id
            bucket["related_snapshot_pairs"].append(
                f"{drift_classification.baseline_snapshot_id}->{drift_classification.candidate_snapshot_id}"
            )
            bucket["latest_summary"] = drift_classification.summary
            if SEVERITY_PRIORITY[drift_classification.severity] > SEVERITY_PRIORITY[bucket["severity"]]:
                bucket["severity"] = drift_classification.severity

            bucket["trigger_codes"].update(comparison_result.new_trigger_codes)
            bucket["trigger_codes"].update(comparison_result.cleared_trigger_codes)
            bucket["reason_codes"].update(comparison_result.new_reason_codes)
            bucket["reason_codes"].update(comparison_result.cleared_reason_codes)
            bucket["source_ids"].update(comparison_result.missing_sources_added)
            bucket["source_ids"].update(comparison_result.missing_sources_cleared)
            bucket["source_ids"].update(comparison_result.stale_sources_added)
            bucket["source_ids"].update(comparison_result.stale_sources_cleared)

        watchlist_items = tuple(
            SnapshotAnomalyWatchlistItem(
                watchlist_code=watchlist_code,
                severity=bucket["severity"],
                occurrence_count=int(bucket["occurrence_count"]),
                first_snapshot_id=str(bucket["first_snapshot_id"]),
                latest_snapshot_id=str(bucket["latest_snapshot_id"]),
                related_snapshot_pairs=tuple(bucket["related_snapshot_pairs"]),
                trigger_codes=tuple(sorted(bucket["trigger_codes"])),
                reason_codes=tuple(sorted(bucket["reason_codes"])),
                source_ids=tuple(sorted(bucket["source_ids"])),
                latest_summary=str(bucket["latest_summary"]),
            )
            for watchlist_code, bucket in sorted(
                watchlist_buckets.items(),
                key=lambda item: (
                    -SEVERITY_PRIORITY[item[1]["severity"]],
                    item[0],
                ),
            )
        )

        return SnapshotAnomalyWatchlistDiagnostics(
            total_items=len(watchlist_items),
            stable_transitions=stable_transitions,
            improving_transitions=improving_transitions,
            anomalous_transitions=anomalous_transitions,
            watchlist_items=watchlist_items,
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_drift_trend_score(
        self,
        drift_classifications: tuple[SnapshotDriftClassification, ...],
        *,
        failure_count: int = 0,
    ) -> SnapshotDriftTrendScore:
        diagnostics: list[str] = []

        if not drift_classifications:
            diagnostics.append("At least two replayable snapshots are required to calculate drift trends.")
            if failure_count > 0:
                diagnostics.append(f"{failure_count} snapshot replay(s) failed during trend evaluation.")
            return SnapshotDriftTrendScore(
                trend_classification="insufficient_data",
                trend_score=0,
                severity_bucket="NONE",
                comparison_count=0,
                improving_transitions=0,
                deteriorating_transitions=0,
                stable_transitions=0,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        trend_score = sum(
            DRIFT_TREND_WEIGHTS.get(drift_classification.drift_code, 0)
            for drift_classification in drift_classifications
        )
        improving_transitions = sum(
            1
            for drift_classification in drift_classifications
            if DRIFT_TREND_WEIGHTS.get(drift_classification.drift_code, 0) < 0
        )
        deteriorating_transitions = sum(
            1
            for drift_classification in drift_classifications
            if DRIFT_TREND_WEIGHTS.get(drift_classification.drift_code, 0) > 0
        )
        stable_transitions = sum(
            1
            for drift_classification in drift_classifications
            if DRIFT_TREND_WEIGHTS.get(drift_classification.drift_code, 0) == 0
        )

        if trend_score > 0:
            trend_classification = "deteriorating"
        elif trend_score < 0:
            trend_classification = "improving"
        else:
            trend_classification = "stable"

        absolute_score = abs(trend_score)
        if absolute_score == 0:
            severity_bucket = "NONE"
        elif absolute_score <= 2:
            severity_bucket = "LOW"
        elif absolute_score <= 4:
            severity_bucket = "MEDIUM"
        elif absolute_score <= 7:
            severity_bucket = "HIGH"
        else:
            severity_bucket = "CRITICAL"

        diagnostics.append(
            f"Trend classification is {trend_classification} across {len(drift_classifications)} deterministic drift transition(s)."
        )
        if failure_count > 0:
            diagnostics.append(f"{failure_count} snapshot replay(s) failed during trend evaluation.")

        return SnapshotDriftTrendScore(
            trend_classification=trend_classification,
            trend_score=trend_score,
            severity_bucket=severity_bucket,
            comparison_count=len(drift_classifications),
            improving_transitions=improving_transitions,
            deteriorating_transitions=deteriorating_transitions,
            stable_transitions=stable_transitions,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_drift_trend_leaderboard(
        self,
        drift_classifications: tuple[SnapshotDriftClassification, ...],
    ) -> SnapshotDriftTrendLeaderboard:
        if not drift_classifications:
            return SnapshotDriftTrendLeaderboard(
                total_entries=0,
                entries=(),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        direction_priority = {
            "deteriorating": 0,
            "stable": 1,
            "improving": 2,
        }
        buckets: dict[str, dict[str, object]] = {}

        for drift_classification in drift_classifications:
            bucket = buckets.setdefault(
                drift_classification.drift_code,
                {
                    "severity": drift_classification.severity,
                    "occurrence_count": 0,
                    "total_weight": 0,
                    "related_snapshot_pairs": [],
                    "latest_summary": drift_classification.summary,
                },
            )
            bucket["occurrence_count"] = int(bucket["occurrence_count"]) + 1
            bucket["total_weight"] = int(bucket["total_weight"]) + DRIFT_TREND_WEIGHTS.get(
                drift_classification.drift_code,
                0,
            )
            bucket["related_snapshot_pairs"].append(
                f"{drift_classification.baseline_snapshot_id}->{drift_classification.candidate_snapshot_id}"
            )
            bucket["latest_summary"] = drift_classification.summary
            if SEVERITY_PRIORITY[drift_classification.severity] > SEVERITY_PRIORITY[bucket["severity"]]:
                bucket["severity"] = drift_classification.severity

        leaderboard_entries: list[SnapshotDriftTrendLeaderboardEntry] = []
        for drift_code, bucket in buckets.items():
            total_weight = int(bucket["total_weight"])
            if total_weight > 0:
                direction = "deteriorating"
            elif total_weight < 0:
                direction = "improving"
            else:
                direction = "stable"
            leaderboard_entries.append(
                SnapshotDriftTrendLeaderboardEntry(
                    rank=0,
                    drift_code=drift_code,
                    direction=direction,
                    severity=bucket["severity"],
                    occurrence_count=int(bucket["occurrence_count"]),
                    total_weight=total_weight,
                    related_snapshot_pairs=tuple(bucket["related_snapshot_pairs"]),
                    latest_summary=str(bucket["latest_summary"]),
                )
            )

        ranked_entries = tuple(
            SnapshotDriftTrendLeaderboardEntry(
                rank=index,
                drift_code=entry.drift_code,
                direction=entry.direction,
                severity=entry.severity,
                occurrence_count=entry.occurrence_count,
                total_weight=entry.total_weight,
                related_snapshot_pairs=entry.related_snapshot_pairs,
                latest_summary=entry.latest_summary,
            )
            for index, entry in enumerate(
                sorted(
                    leaderboard_entries,
                    key=lambda item: (
                        direction_priority[item.direction],
                        -abs(item.total_weight),
                        -SEVERITY_PRIORITY[item.severity],
                        -item.occurrence_count,
                        item.drift_code,
                    ),
                ),
                start=1,
            )
        )

        return SnapshotDriftTrendLeaderboard(
            total_entries=len(ranked_entries),
            entries=ranked_entries,
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_trigger_persistence_leaderboard(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
    ) -> SnapshotTriggerPersistenceLeaderboard:
        diagnostics: list[str] = []
        total_snapshots = len(replay_results)
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for trigger persistence analysis.")
            return SnapshotTriggerPersistenceLeaderboard(
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
        seen_codes: set[str] = set()

        for replay_result in replay_results:
            active_triggers = {
                trigger.trigger_code: trigger
                for trigger in replay_result.trigger_results
                if trigger.is_triggered
            }
            active_codes = set(active_triggers)

            for trigger_code in sorted(seen_codes - active_codes):
                streaks[trigger_code] = 0

            for trigger_code, trigger in active_triggers.items():
                bucket = buckets.setdefault(
                    trigger_code,
                    {
                        "asset_symbol": trigger.asset_symbol,
                        "severity": trigger.severity,
                        "active_snapshot_count": 0,
                        "longest_streak": 0,
                        "first_snapshot_id": replay_result.snapshot_id,
                        "latest_snapshot_id": replay_result.snapshot_id,
                        "active_snapshot_ids": [],
                        "latest_message": trigger.message,
                    },
                )
                bucket["active_snapshot_count"] = int(bucket["active_snapshot_count"]) + 1
                bucket["latest_snapshot_id"] = replay_result.snapshot_id
                bucket["active_snapshot_ids"].append(replay_result.snapshot_id)
                bucket["latest_message"] = trigger.message
                if SEVERITY_PRIORITY[trigger.severity] > SEVERITY_PRIORITY[bucket["severity"]]:
                    bucket["severity"] = trigger.severity

                current_streak = streaks.get(trigger_code, 0) + 1
                streaks[trigger_code] = current_streak
                if current_streak > int(bucket["longest_streak"]):
                    bucket["longest_streak"] = current_streak

            seen_codes.update(active_codes)

        if not buckets:
            diagnostics.append("No active replay triggers were found in the requested saved snapshots.")
            return SnapshotTriggerPersistenceLeaderboard(
                total_entries=0,
                total_snapshots=total_snapshots,
                entries=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        leaderboard_entries: list[SnapshotTriggerPersistenceLeaderboardEntry] = []
        for trigger_code, bucket in buckets.items():
            active_snapshot_count = int(bucket["active_snapshot_count"])
            longest_streak = int(bucket["longest_streak"])
            if active_snapshot_count == total_snapshots and total_snapshots > 1:
                persistence_classification = "persistent"
            elif longest_streak >= 2:
                persistence_classification = "recurring"
            else:
                persistence_classification = "intermittent"

            leaderboard_entries.append(
                SnapshotTriggerPersistenceLeaderboardEntry(
                    rank=0,
                    trigger_code=trigger_code,
                    asset_symbol=str(bucket["asset_symbol"]),
                    severity=bucket["severity"],
                    persistence_classification=persistence_classification,
                    active_snapshot_count=active_snapshot_count,
                    persistence_ratio=round(active_snapshot_count / total_snapshots, 4),
                    longest_streak=longest_streak,
                    first_snapshot_id=str(bucket["first_snapshot_id"]),
                    latest_snapshot_id=str(bucket["latest_snapshot_id"]),
                    active_snapshot_ids=tuple(bucket["active_snapshot_ids"]),
                    latest_message=str(bucket["latest_message"]),
                )
            )

        ranked_entries = tuple(
            SnapshotTriggerPersistenceLeaderboardEntry(
                rank=index,
                trigger_code=entry.trigger_code,
                asset_symbol=entry.asset_symbol,
                severity=entry.severity,
                persistence_classification=entry.persistence_classification,
                active_snapshot_count=entry.active_snapshot_count,
                persistence_ratio=entry.persistence_ratio,
                longest_streak=entry.longest_streak,
                first_snapshot_id=entry.first_snapshot_id,
                latest_snapshot_id=entry.latest_snapshot_id,
                active_snapshot_ids=entry.active_snapshot_ids,
                latest_message=entry.latest_message,
            )
            for index, entry in enumerate(
                sorted(
                    leaderboard_entries,
                    key=lambda item: (
                        -item.active_snapshot_count,
                        -item.longest_streak,
                        -SEVERITY_PRIORITY[item.severity],
                        item.trigger_code,
                    ),
                ),
                start=1,
            )
        )

        diagnostics.append(
            f"Trigger persistence leaderboard covers {total_snapshots} saved snapshot(s) and {len(ranked_entries)} active trigger type(s)."
        )

        return SnapshotTriggerPersistenceLeaderboard(
            total_entries=len(ranked_entries),
            total_snapshots=total_snapshots,
            entries=ranked_entries,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
