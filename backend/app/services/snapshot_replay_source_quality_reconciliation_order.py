from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry,
)
from app.services.snapshot_replay_source_common import (
    SEVERITY_LABEL_SCORES,
)
from app.services.snapshot_replay_source_quality_common import (
    derive_severity_label_from_rank,
    severity_ranking_gap_magnitude_sequence,
    severity_ranking_gap_sequence,
    severity_ranking_order_key,
)

class SnapshotReplaySourceQualityReconciliationOrderMixin:
    def _build_source_diagnostics_severity_ranking_rank_label_consistency_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking rank/label consistency reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank/label consistency reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation(
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
                malformed_ranking_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[
            SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry
        ] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_fields: set[str] = set()
        aggregate_mismatched_fields: set[str] = set()
        aggregate_malformed_ranking_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_diagnostics_summary")
            if not isinstance(summary, Mapping):
                invalid_snapshots += 1
                aggregate_malformed_ranking_count += 1
                entries.append(
                    SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        checked_feature_count=0,
                        consistent_rank_label_feature_count=0,
                        inconsistent_rank_label_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking rank/label consistency reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            checked_feature_count = 0
            consistent_rank_label_feature_count = 0
            inconsistent_rank_label_feature_count = 0
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue
                feature_name = ranking_entry.get("feature_name")
                status = ranking_entry.get("status")
                critical = ranking_entry.get("critical")
                severity_level = ranking_entry.get("severity_level")
                raw_severity_rank = ranking_entry.get("severity_rank")
                if not isinstance(feature_name, str) or not feature_name.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(status, str) or not status.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(critical, bool):
                    malformed_ranking_count += 1
                    continue
                if not isinstance(severity_level, str) or not severity_level.strip():
                    malformed_ranking_count += 1
                    continue
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_ranking_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue

                checked_feature_count += 1
                expected_severity_level = derive_severity_label_from_rank(severity_rank)
                if severity_level == expected_severity_level:
                    consistent_rank_label_feature_count += 1
                else:
                    inconsistent_rank_label_feature_count += 1

            mismatched_fields: list[str] = []
            available_checks = checked_feature_count
            aligned_checks = consistent_rank_label_feature_count
            if (
                "severity_ranking" not in missing_fields
                and inconsistent_rank_label_feature_count > 0
            ):
                mismatched_fields.append("severity_ranking_rank_label_consistency")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank/label consistency reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking labels diverged from the deterministic rank-derived severity labels."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank/label consistency reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking labels remained aligned with the deterministic rank-derived severity labels."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    checked_feature_count=checked_feature_count,
                    consistent_rank_label_feature_count=consistent_rank_label_feature_count,
                    inconsistent_rank_label_feature_count=inconsistent_rank_label_feature_count,
                    missing_fields=tuple(sorted(missing_fields)),
                    mismatched_fields=tuple(sorted(mismatched_fields)),
                    malformed_ranking_count=malformed_ranking_count,
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
            f"Source diagnostics severity-ranking rank/label consistency reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking rank/label consistency reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking rank/label consistency field(s) diverged from the deterministic rank-derived severity labels."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during rank/label consistency reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank/label consistency reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingRankLabelConsistencyReconciliation(
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
            malformed_ranking_count=aggregate_malformed_ranking_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostics_severity_ranking_rank_order_continuity_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking rank-order continuity reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank-order continuity reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation(
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
                malformed_ranking_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[
            SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry
        ] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_fields: set[str] = set()
        aggregate_mismatched_fields: set[str] = set()
        aggregate_malformed_ranking_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_diagnostics_summary")
            if not isinstance(summary, Mapping):
                invalid_snapshots += 1
                aggregate_malformed_ranking_count += 1
                entries.append(
                    SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        checked_feature_count=0,
                        consistent_rank_order_feature_count=0,
                        reordered_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking rank-order continuity reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            persisted_entries: list[tuple[str, int, str, str]] = []
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue
                feature_name = ranking_entry.get("feature_name")
                status = ranking_entry.get("status")
                critical = ranking_entry.get("critical")
                severity_level = ranking_entry.get("severity_level")
                raw_severity_rank = ranking_entry.get("severity_rank")
                if not isinstance(feature_name, str) or not feature_name.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(status, str) or not status.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(critical, bool):
                    malformed_ranking_count += 1
                    continue
                if not isinstance(severity_level, str) or not severity_level.strip():
                    malformed_ranking_count += 1
                    continue
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_ranking_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue

                persisted_entries.append(
                    (feature_name, severity_rank, status, severity_level)
                )

            expected_entries = tuple(
                sorted(
                    persisted_entries,
                    key=lambda entry: severity_ranking_order_key(
                        severity_rank=entry[1],
                        feature_name=entry[0],
                        status=entry[2],
                        severity_level=entry[3],
                    ),
                )
            )
            persisted_tuple = tuple(persisted_entries)
            checked_feature_count = len(persisted_tuple)
            consistent_rank_order_feature_count = sum(
                1
                for index, entry in enumerate(persisted_tuple)
                if index < len(expected_entries) and entry == expected_entries[index]
            )
            reordered_feature_count = max(
                checked_feature_count - consistent_rank_order_feature_count,
                0,
            )

            mismatched_fields: list[str] = []
            if "severity_ranking" not in missing_fields and reordered_feature_count > 0:
                mismatched_fields.append("severity_ranking_rank_order_continuity")

            consistency_percentage = round(
                (consistent_rank_order_feature_count / checked_feature_count) * 100.0,
                2,
            ) if checked_feature_count > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank-order continuity reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking order diverged from the deterministic descending rank order."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank-order continuity reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking order remained aligned with the deterministic descending rank order."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    checked_feature_count=checked_feature_count,
                    consistent_rank_order_feature_count=consistent_rank_order_feature_count,
                    reordered_feature_count=reordered_feature_count,
                    missing_fields=tuple(sorted(missing_fields)),
                    mismatched_fields=tuple(sorted(mismatched_fields)),
                    malformed_ranking_count=malformed_ranking_count,
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
            f"Source diagnostics severity-ranking rank-order continuity reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking rank-order continuity reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking rank-order continuity field(s) diverged from the deterministic descending rank order."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during rank-order continuity reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank-order continuity reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingRankOrderContinuityReconciliation(
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
            malformed_ranking_count=aggregate_malformed_ranking_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostics_severity_ranking_rank_gap_continuity_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking rank-gap continuity reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank-gap continuity reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation(
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
                malformed_ranking_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[
            SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry
        ] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_fields: set[str] = set()
        aggregate_mismatched_fields: set[str] = set()
        aggregate_malformed_ranking_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_diagnostics_summary")
            if not isinstance(summary, Mapping):
                invalid_snapshots += 1
                aggregate_malformed_ranking_count += 1
                entries.append(
                    SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        checked_gap_count=0,
                        consistent_rank_gap_count=0,
                        discontinuous_rank_gap_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking rank-gap continuity reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            persisted_entries: list[tuple[str, int, str, str]] = []
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue
                feature_name = ranking_entry.get("feature_name")
                status = ranking_entry.get("status")
                critical = ranking_entry.get("critical")
                severity_level = ranking_entry.get("severity_level")
                raw_severity_rank = ranking_entry.get("severity_rank")
                if not isinstance(feature_name, str) or not feature_name.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(status, str) or not status.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(critical, bool):
                    malformed_ranking_count += 1
                    continue
                if not isinstance(severity_level, str) or not severity_level.strip():
                    malformed_ranking_count += 1
                    continue
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_ranking_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue

                persisted_entries.append(
                    (feature_name, severity_rank, status, severity_level)
                )

            expected_entries = tuple(
                sorted(
                    persisted_entries,
                    key=lambda entry: severity_ranking_order_key(
                        severity_rank=entry[1],
                        feature_name=entry[0],
                        status=entry[2],
                        severity_level=entry[3],
                    ),
                )
            )
            persisted_tuple = tuple(persisted_entries)
            persisted_gap_sequence = severity_ranking_gap_sequence(persisted_tuple)
            expected_gap_sequence = severity_ranking_gap_sequence(expected_entries)
            checked_gap_count = len(expected_gap_sequence)
            consistent_rank_gap_count = sum(
                1
                for index, gap in enumerate(persisted_gap_sequence)
                if index < len(expected_gap_sequence) and gap == expected_gap_sequence[index]
            )
            discontinuous_rank_gap_count = max(
                checked_gap_count - consistent_rank_gap_count,
                0,
            )

            mismatched_fields: list[str] = []
            if "severity_ranking" not in missing_fields and discontinuous_rank_gap_count > 0:
                mismatched_fields.append("severity_ranking_rank_gap_continuity")

            if checked_gap_count == 0 and not missing_fields and malformed_ranking_count == 0:
                consistency_percentage = 100.0
            else:
                consistency_percentage = round(
                    (consistent_rank_gap_count / checked_gap_count) * 100.0,
                    2,
                ) if checked_gap_count > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank-gap continuity reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking gaps diverged from the deterministic descending rank-gap sequence."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank-gap continuity reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking gaps remained aligned with the deterministic descending rank-gap sequence."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    checked_gap_count=checked_gap_count,
                    consistent_rank_gap_count=consistent_rank_gap_count,
                    discontinuous_rank_gap_count=discontinuous_rank_gap_count,
                    missing_fields=tuple(sorted(missing_fields)),
                    mismatched_fields=tuple(sorted(mismatched_fields)),
                    malformed_ranking_count=malformed_ranking_count,
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
            f"Source diagnostics severity-ranking rank-gap continuity reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking rank-gap continuity reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking rank-gap continuity field(s) diverged from the deterministic descending rank-gap sequence."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during rank-gap continuity reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank-gap continuity reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingRankGapContinuityReconciliation(
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
            malformed_ranking_count=aggregate_malformed_ranking_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostics_severity_ranking_rank_gap_magnitude_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking rank-gap magnitude reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank-gap magnitude reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation(
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
                malformed_ranking_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[
            SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry
        ] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_fields: set[str] = set()
        aggregate_mismatched_fields: set[str] = set()
        aggregate_malformed_ranking_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_diagnostics_summary")
            if not isinstance(summary, Mapping):
                invalid_snapshots += 1
                aggregate_malformed_ranking_count += 1
                entries.append(
                    SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        checked_gap_count=0,
                        consistent_rank_gap_magnitude_count=0,
                        mismatched_rank_gap_magnitude_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking rank-gap magnitude reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            persisted_entries: list[tuple[str, int, str, str]] = []
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue
                feature_name = ranking_entry.get("feature_name")
                status = ranking_entry.get("status")
                critical = ranking_entry.get("critical")
                severity_level = ranking_entry.get("severity_level")
                raw_severity_rank = ranking_entry.get("severity_rank")
                if not isinstance(feature_name, str) or not feature_name.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(status, str) or not status.strip():
                    malformed_ranking_count += 1
                    continue
                if not isinstance(critical, bool):
                    malformed_ranking_count += 1
                    continue
                if not isinstance(severity_level, str) or not severity_level.strip():
                    malformed_ranking_count += 1
                    continue
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_ranking_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue

                persisted_entries.append(
                    (feature_name, severity_rank, status, severity_level)
                )

            expected_entries = tuple(
                sorted(
                    persisted_entries,
                    key=lambda entry: severity_ranking_order_key(
                        severity_rank=entry[1],
                        feature_name=entry[0],
                        status=entry[2],
                        severity_level=entry[3],
                    ),
                )
            )
            persisted_tuple = tuple(persisted_entries)
            persisted_gap_magnitudes = severity_ranking_gap_magnitude_sequence(
                persisted_tuple
            )
            expected_gap_magnitudes = severity_ranking_gap_magnitude_sequence(
                expected_entries
            )
            checked_gap_count = len(expected_gap_magnitudes)
            consistent_rank_gap_magnitude_count = sum(
                1
                for index, gap in enumerate(persisted_gap_magnitudes)
                if index < len(expected_gap_magnitudes)
                and gap == expected_gap_magnitudes[index]
            )
            mismatched_rank_gap_magnitude_count = max(
                checked_gap_count - consistent_rank_gap_magnitude_count,
                0,
            )

            mismatched_fields: list[str] = []
            if (
                "severity_ranking" not in missing_fields
                and mismatched_rank_gap_magnitude_count > 0
            ):
                mismatched_fields.append("severity_ranking_rank_gap_magnitude")

            if checked_gap_count == 0 and not missing_fields and malformed_ranking_count == 0:
                consistency_percentage = 100.0
            else:
                consistency_percentage = round(
                    (consistent_rank_gap_magnitude_count / checked_gap_count) * 100.0,
                    2,
                ) if checked_gap_count > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank-gap magnitude reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking gap magnitudes diverged from the deterministic descending rank-gap magnitudes."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking rank-gap magnitude reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking gap magnitudes remained aligned with the deterministic descending rank-gap magnitudes."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    checked_gap_count=checked_gap_count,
                    consistent_rank_gap_magnitude_count=consistent_rank_gap_magnitude_count,
                    mismatched_rank_gap_magnitude_count=mismatched_rank_gap_magnitude_count,
                    missing_fields=tuple(sorted(missing_fields)),
                    mismatched_fields=tuple(sorted(mismatched_fields)),
                    malformed_ranking_count=malformed_ranking_count,
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
            f"Source diagnostics severity-ranking rank-gap magnitude reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking rank-gap magnitude reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking rank-gap magnitude field(s) diverged from the deterministic descending rank-gap magnitudes."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during rank-gap magnitude reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking rank-gap magnitude reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingRankGapMagnitudeReconciliation(
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
            malformed_ranking_count=aggregate_malformed_ranking_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = ["SnapshotReplaySourceQualityReconciliationOrderMixin"]
