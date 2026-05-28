
from __future__ import annotations

from collections import Counter

from app.services.data_quality_service import DataQualityDecision
from app.services.risk_engine import ACTION_PRIORITY
from app.services.snapshot_replay_core import SnapshotReplayCore
from app.services.snapshot_replay_models import SnapshotDqsStability
from app.services.snapshot_replay_models import SnapshotDqsStabilityPathEntry
from app.services.snapshot_replay_models import SnapshotReplayRegimeSummary
from app.services.snapshot_replay_models import SnapshotReplayRegimeTimeline
from app.services.snapshot_replay_models import SnapshotReplayRegimeTimelineEntry
from app.services.snapshot_replay_models import SnapshotReplayResult
from app.services.snapshot_replay_models import SnapshotRiskActionStability

DQS_DECISION_PRIORITY = {
    DataQualityDecision.PASS: 0,
    DataQualityDecision.DEGRADED_PASS: 1,
    DataQualityDecision.LIMITED_ANALYSIS_ONLY: 2,
    DataQualityDecision.FAIL_NO_DECISION: 3,
}


class SnapshotReplayRegimeDiagnostics(SnapshotReplayCore):
    def _build_replay_regime_summary(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
    ) -> SnapshotReplayRegimeSummary:
        diagnostics: list[str] = []
        regimes_with_snapshot_ids = [
            (replay_result.snapshot_id, replay_result.replay_regime)
            for replay_result in replay_results
            if replay_result.replay_regime is not None
        ]
        available_regimes = [regime for _, regime in regimes_with_snapshot_ids]
        missing_regime_count = sum(
            1
            for replay_result in replay_results
            if replay_result.replay_regime is None
        )

        if not available_regimes:
            diagnostics.append("No saved replay regimes were present in the requested snapshots.")
            missing_diagnostics = sorted(
                {
                    replay_result.replay_regime_diagnostic
                    for replay_result in replay_results
                    if replay_result.replay_regime_diagnostic is not None
                }
            )
            diagnostics.extend(missing_diagnostics)
            return SnapshotReplayRegimeSummary(
                status="missing",
                distribution_classification="missing",
                dominant_regime=None,
                regime_distribution={},
                transition_count=0,
                mixed_or_unstable=False,
                available_regime_count=0,
                missing_regime_count=missing_regime_count,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        regime_distribution = Counter(available_regimes)
        dominant_regime = sorted(
            regime_distribution.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]
        transition_count = 0
        previous_regime: str | None = None
        for _, current_regime in regimes_with_snapshot_ids:
            if previous_regime is not None and current_regime != previous_regime:
                transition_count += 1
            previous_regime = current_regime

        dominant_share = regime_distribution[dominant_regime] / len(available_regimes)
        if missing_regime_count == len(replay_results):
            status = "missing"
        elif missing_regime_count > 0:
            status = "partial"
        else:
            status = "available"

        if len(regime_distribution) == 1:
            distribution_classification = "dominant"
        elif transition_count >= 2 or dominant_share < 0.6:
            distribution_classification = "unstable"
        else:
            distribution_classification = "mixed"

        mixed_or_unstable = distribution_classification in {"mixed", "unstable"}
        diagnostics.append(
            f"Dominant replay regime is {dominant_regime} across {len(available_regimes)} saved snapshot regime observation(s)."
        )
        if missing_regime_count > 0:
            diagnostics.append(f"{missing_regime_count} saved snapshot(s) did not include replay regime metadata.")

        return SnapshotReplayRegimeSummary(
            status=status,
            distribution_classification=distribution_classification,
            dominant_regime=dominant_regime,
            regime_distribution=dict(sorted(regime_distribution.items())),
            transition_count=transition_count,
            mixed_or_unstable=mixed_or_unstable,
            available_regime_count=len(available_regimes),
            missing_regime_count=missing_regime_count,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_replay_regime_timeline(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
        *,
        regime_summary: SnapshotReplayRegimeSummary,
    ) -> SnapshotReplayRegimeTimeline:
        if regime_summary.available_regime_count == 0:
            status = "missing"
        elif regime_summary.missing_regime_count > 0:
            status = "partial"
        else:
            status = "available"

        entries: list[SnapshotReplayRegimeTimelineEntry] = []
        previous_regime: str | None = None
        dominant_regime = regime_summary.dominant_regime

        for replay_result in replay_results:
            if replay_result.replay_regime is not None:
                entry_status = "available"
                diagnostic = None
            elif replay_result.replay_regime_diagnostic == "Saved replay regime metadata was present but malformed.":
                entry_status = "malformed"
                diagnostic = replay_result.replay_regime_diagnostic
            else:
                entry_status = "missing"
                diagnostic = replay_result.replay_regime_diagnostic

            transition_from_previous = (
                previous_regime is not None
                and replay_result.replay_regime is not None
                and replay_result.replay_regime != previous_regime
            )
            dominant_regime_match = (
                dominant_regime is not None and replay_result.replay_regime == dominant_regime
            )
            entries.append(
                SnapshotReplayRegimeTimelineEntry(
                    snapshot_id=replay_result.snapshot_id,
                    created_at=replay_result.created_at,
                    replay_regime=replay_result.replay_regime,
                    status=entry_status,
                    diagnostic=diagnostic,
                    transition_from_previous=transition_from_previous,
                    dominant_regime_match=dominant_regime_match,
                )
            )
            if replay_result.replay_regime is not None:
                previous_regime = replay_result.replay_regime

        diagnostics = list(regime_summary.diagnostics)
        diagnostics.append(
            f"Replay regime timeline covers {len(replay_results)} saved snapshot(s) in chronological order."
        )

        return SnapshotReplayRegimeTimeline(
            status=status,
            total_snapshots=len(replay_results),
            dominant_regime=dominant_regime,
            transition_count=regime_summary.transition_count,
            mixed_or_unstable=regime_summary.mixed_or_unstable,
            available_regime_count=regime_summary.available_regime_count,
            missing_regime_count=regime_summary.missing_regime_count,
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_dqs_stability(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
        *,
        failure_count: int = 0,
    ) -> SnapshotDqsStability:
        diagnostics: list[str] = []
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for DQS stability analysis.")
            if failure_count > 0:
                diagnostics.append(f"{failure_count} snapshot replay(s) failed during DQS stability analysis.")
            return SnapshotDqsStability(
                stability_classification="missing",
                dominant_decision=None,
                first_decision=None,
                latest_decision=None,
                transition_count=0,
                unique_decision_count=0,
                lowest_minimum_score=None,
                highest_minimum_score=None,
                average_score_delta=0.0,
                decision_counts={},
                path=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        path_entries: list[SnapshotDqsStabilityPathEntry] = []
        for replay_result in replay_results:
            core_quality_results = tuple(
                snapshot_quality_result
                for snapshot_quality_result in replay_result.snapshot_quality_results
                if snapshot_quality_result.required_for_core_report
            )
            if not core_quality_results:
                continue

            aggregate_decision = max(
                (snapshot_quality_result.dqs_result.decision for snapshot_quality_result in core_quality_results),
                key=lambda decision: DQS_DECISION_PRIORITY[decision],
            )
            minimum_score = min(
                snapshot_quality_result.dqs_result.total_score
                for snapshot_quality_result in core_quality_results
            )
            average_score = round(
                sum(
                    snapshot_quality_result.dqs_result.total_score
                    for snapshot_quality_result in core_quality_results
                ) / len(core_quality_results),
                2,
            )
            path_entries.append(
                SnapshotDqsStabilityPathEntry(
                    snapshot_id=replay_result.snapshot_id,
                    created_at=replay_result.created_at,
                    aggregate_decision=aggregate_decision,
                    minimum_score=minimum_score,
                    average_score=average_score,
                    core_snapshot_count=len(core_quality_results),
                )
            )

        if not path_entries:
            diagnostics.append("No core-report DQS observations were available for DQS stability analysis.")
            if failure_count > 0:
                diagnostics.append(f"{failure_count} snapshot replay(s) failed during DQS stability analysis.")
            return SnapshotDqsStability(
                stability_classification="missing",
                dominant_decision=None,
                first_decision=None,
                latest_decision=None,
                transition_count=0,
                unique_decision_count=0,
                lowest_minimum_score=None,
                highest_minimum_score=None,
                average_score_delta=0.0,
                decision_counts={},
                path=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        decision_counts_counter = Counter(
            path_entry.aggregate_decision.value
            for path_entry in path_entries
        )
        dominant_decision = sorted(
            decision_counts_counter.items(),
            key=lambda item: (-item[1], -DQS_DECISION_PRIORITY[DataQualityDecision(item[0])], item[0]),
        )[0][0]
        transition_count = sum(
            1
            for index in range(1, len(path_entries))
            if path_entries[index].aggregate_decision != path_entries[index - 1].aggregate_decision
        )

        first_decision = path_entries[0].aggregate_decision
        latest_decision = path_entries[-1].aggregate_decision
        average_score_delta = round(
            path_entries[-1].average_score - path_entries[0].average_score,
            2,
        )

        if len(path_entries) < 2:
            stability_classification = "insufficient_data"
            diagnostics.append("At least two replayable snapshots are required to evaluate DQS stability.")
        elif transition_count == 0:
            stability_classification = "stable"
            diagnostics.append(
                f"DQS aggregate decision remained {first_decision.value} across {len(path_entries)} saved snapshot(s)."
            )
        elif DQS_DECISION_PRIORITY[latest_decision] > DQS_DECISION_PRIORITY[first_decision]:
            stability_classification = "deteriorating"
            diagnostics.append(
                f"DQS aggregate decision deteriorated from {first_decision.value} to {latest_decision.value} across saved snapshots."
            )
        elif DQS_DECISION_PRIORITY[latest_decision] < DQS_DECISION_PRIORITY[first_decision]:
            stability_classification = "improving"
            diagnostics.append(
                f"DQS aggregate decision improved from {first_decision.value} to {latest_decision.value} across saved snapshots."
            )
        else:
            stability_classification = "mixed"
            diagnostics.append(
                f"DQS aggregate decision revisited the same decision band with {transition_count} transition(s) across saved snapshots."
            )

        if failure_count > 0:
            diagnostics.append(f"{failure_count} snapshot replay(s) failed during DQS stability analysis.")

        return SnapshotDqsStability(
            stability_classification=stability_classification,
            dominant_decision=dominant_decision,
            first_decision=first_decision.value,
            latest_decision=latest_decision.value,
            transition_count=transition_count,
            unique_decision_count=len(decision_counts_counter),
            lowest_minimum_score=min(path_entry.minimum_score for path_entry in path_entries),
            highest_minimum_score=max(path_entry.minimum_score for path_entry in path_entries),
            average_score_delta=average_score_delta,
            decision_counts=dict(sorted(decision_counts_counter.items())),
            path=tuple(path_entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_risk_action_stability(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
        *,
        failure_count: int = 0,
    ) -> SnapshotRiskActionStability:
        diagnostics: list[str] = []
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for risk action stability analysis.")
            if failure_count > 0:
                diagnostics.append(f"{failure_count} snapshot replay(s) failed during risk action stability analysis.")
            return SnapshotRiskActionStability(
                stability_classification="missing",
                dominant_risk_action=None,
                first_risk_action=None,
                latest_risk_action=None,
                transition_count=0,
                longest_stable_run=0,
                unique_action_count=0,
                risk_action_counts={},
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        risk_actions = [
            replay_result.risk_engine_result.risk_action
            for replay_result in replay_results
        ]
        risk_action_counts_counter = Counter(action.value for action in risk_actions)
        dominant_risk_action = sorted(
            risk_action_counts_counter.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]
        transition_count = sum(
            1
            for index in range(1, len(risk_actions))
            if risk_actions[index] != risk_actions[index - 1]
        )

        longest_stable_run = 1
        current_run = 1
        for index in range(1, len(risk_actions)):
            if risk_actions[index] == risk_actions[index - 1]:
                current_run += 1
            else:
                if current_run > longest_stable_run:
                    longest_stable_run = current_run
                current_run = 1
        if current_run > longest_stable_run:
            longest_stable_run = current_run

        if len(risk_actions) < 2:
            stability_classification = "insufficient_data"
            diagnostics.append("At least two replayable snapshots are required to evaluate risk action stability.")
        elif transition_count == 0:
            stability_classification = "stable"
            diagnostics.append(
                f"Risk action remained {risk_actions[0].value} across {len(risk_actions)} saved snapshot(s)."
            )
        elif len(risk_action_counts_counter) >= 3 or transition_count >= 3:
            stability_classification = "volatile"
            diagnostics.append(
                f"Risk action changed {transition_count} time(s) across {len(risk_actions)} saved snapshot(s) and should be treated as unstable."
            )
        elif ACTION_PRIORITY[risk_actions[-1]] > ACTION_PRIORITY[risk_actions[0]]:
            stability_classification = "tightening"
            diagnostics.append(
                f"Risk action tightened from {risk_actions[0].value} to {risk_actions[-1].value} across saved snapshots."
            )
        elif ACTION_PRIORITY[risk_actions[-1]] < ACTION_PRIORITY[risk_actions[0]]:
            stability_classification = "relaxing"
            diagnostics.append(
                f"Risk action relaxed from {risk_actions[0].value} to {risk_actions[-1].value} across saved snapshots."
            )
        else:
            stability_classification = "mixed"
            diagnostics.append(
                f"Risk action revisited the same severity band with {transition_count} transition(s) across saved snapshots."
            )

        if failure_count > 0:
            diagnostics.append(f"{failure_count} snapshot replay(s) failed during risk action stability analysis.")

        return SnapshotRiskActionStability(
            stability_classification=stability_classification,
            dominant_risk_action=dominant_risk_action,
            first_risk_action=risk_actions[0].value,
            latest_risk_action=risk_actions[-1].value,
            transition_count=transition_count,
            longest_stable_run=longest_stable_run,
            unique_action_count=len(risk_action_counts_counter),
            risk_action_counts=dict(sorted(risk_action_counts_counter.items())),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
