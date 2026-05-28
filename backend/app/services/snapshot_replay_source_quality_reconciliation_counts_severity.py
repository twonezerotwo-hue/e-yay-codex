from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry,
    SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation,
    SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry,
)
from app.services.snapshot_replay_source_common import (
    CRITICAL_SEVERITY_MIN_RANK,
    HIGH_SEVERITY_MIN_RANK,
    INFO_SEVERITY_MAX_RANK,
    WARNING_SEVERITY_MAX_RANK,
    WARNING_SEVERITY_MIN_RANK,
)

class SnapshotReplaySourceQualityReconciliationCountsSeverityMixin:
    def _build_source_diagnostics_severity_ranking_feature_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking feature-count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking feature-count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_severity_ranking_feature_count=0,
                        derived_severity_ranking_feature_count=0,
                        critical_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking feature-count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
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

            summary_severity_ranking_feature_count = len(raw_severity_ranking)
            derived_severity_ranking_feature_count = 0
            critical_feature_count = 0
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue
                feature_name = ranking_entry.get("feature_name")
                status = ranking_entry.get("status")
                critical = ranking_entry.get("critical")
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
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue
                if severity_rank > 0:
                    derived_severity_ranking_feature_count += 1
                    if critical:
                        critical_feature_count += 1

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "severity_ranking" not in missing_fields:
                available_checks += 1
                if (
                    summary_severity_ranking_feature_count
                    == derived_severity_ranking_feature_count
                ):
                    aligned_checks += 1
                else:
                    mismatched_fields.append("severity_ranking_feature_count")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking feature-count reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking feature counts diverged from the deterministic actionable-entry count."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking feature-count reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking feature counts remained aligned with the deterministic actionable-entry count."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_severity_ranking_feature_count=summary_severity_ranking_feature_count,
                    derived_severity_ranking_feature_count=derived_severity_ranking_feature_count,
                    critical_feature_count=critical_feature_count,
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
            f"Source diagnostics severity-ranking feature-count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking feature-count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking feature-count field(s) diverged from the deterministic actionable-entry count."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during feature-count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking feature-count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingFeatureCountReconciliation(
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

    def _build_source_diagnostics_severity_ranking_warning_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking warning-count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking warning-count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_warning_feature_count=0,
                        derived_warning_feature_count=0,
                        high_severity_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking warning-count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
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

            summary_warning_feature_count = 0
            derived_warning_feature_count = 0
            high_severity_feature_count = 0
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
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue
                if severity_rank <= 0:
                    continue
                if severity_level == "warning":
                    summary_warning_feature_count += 1
                if (
                    severity_level == "critical"
                    or severity_rank >= HIGH_SEVERITY_MIN_RANK
                ):
                    high_severity_feature_count += 1
                if (
                    severity_level == "warning"
                    or (
                        severity_level != "critical"
                        and WARNING_SEVERITY_MIN_RANK <= severity_rank <= WARNING_SEVERITY_MAX_RANK
                    )
                ):
                    derived_warning_feature_count += 1

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "severity_ranking" not in missing_fields:
                available_checks += 1
                if summary_warning_feature_count == derived_warning_feature_count:
                    aligned_checks += 1
                else:
                    mismatched_fields.append("severity_ranking_warning_count")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking warning-count reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking warning counts diverged from the deterministic warning-severity derivation."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking warning-count reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking warning counts remained aligned with the deterministic warning-severity derivation."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_warning_feature_count=summary_warning_feature_count,
                    derived_warning_feature_count=derived_warning_feature_count,
                    high_severity_feature_count=high_severity_feature_count,
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
            f"Source diagnostics severity-ranking warning-count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking warning-count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking warning-count field(s) diverged from the deterministic warning-severity derivation."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during warning-count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking warning-count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingWarningCountReconciliation(
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

    def _build_source_diagnostics_severity_ranking_info_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking info-count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking info-count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_info_feature_count=0,
                        derived_info_feature_count=0,
                        warning_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking info-count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
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

            summary_info_feature_count = 0
            derived_info_feature_count = 0
            warning_feature_count = 0
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
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue

                if severity_level == "warning" or (
                    severity_level != "critical"
                    and WARNING_SEVERITY_MIN_RANK <= severity_rank <= WARNING_SEVERITY_MAX_RANK
                ):
                    warning_feature_count += 1
                if severity_level == "info":
                    summary_info_feature_count += 1
                if severity_level == "info" or severity_rank <= INFO_SEVERITY_MAX_RANK:
                    derived_info_feature_count += 1

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "severity_ranking" not in missing_fields:
                available_checks += 1
                if summary_info_feature_count == derived_info_feature_count:
                    aligned_checks += 1
                else:
                    mismatched_fields.append("severity_ranking_info_count")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking info-count reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking info counts diverged from the deterministic info-severity derivation."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking info-count reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking info counts remained aligned with the deterministic info-severity derivation."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_info_feature_count=summary_info_feature_count,
                    derived_info_feature_count=derived_info_feature_count,
                    warning_feature_count=warning_feature_count,
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
            f"Source diagnostics severity-ranking info-count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking info-count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking info-count field(s) diverged from the deterministic info-severity derivation."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during info-count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking info-count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingInfoCountReconciliation(
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

    def _build_source_diagnostics_severity_ranking_non_actionable_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking non-actionable-count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking non-actionable-count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation(
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
            SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry
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
                    SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_non_actionable_feature_count=0,
                        derived_non_actionable_feature_count=0,
                        info_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking non-actionable-count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
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

            summary_non_actionable_feature_count = 0
            derived_non_actionable_feature_count = 0
            info_feature_count = 0
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
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue

                if severity_level == "info":
                    summary_non_actionable_feature_count += 1
                if severity_rank <= INFO_SEVERITY_MAX_RANK:
                    derived_non_actionable_feature_count += 1
                if severity_level == "info" or severity_rank <= INFO_SEVERITY_MAX_RANK:
                    info_feature_count += 1

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "severity_ranking" not in missing_fields:
                available_checks += 1
                if (
                    summary_non_actionable_feature_count
                    == derived_non_actionable_feature_count
                ):
                    aligned_checks += 1
                else:
                    mismatched_fields.append("severity_ranking_non_actionable_count")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking non-actionable-count reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking non-actionable counts diverged from the deterministic zero-rank derivation."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking non-actionable-count reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking non-actionable counts remained aligned with the deterministic zero-rank derivation."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_non_actionable_feature_count=summary_non_actionable_feature_count,
                    derived_non_actionable_feature_count=derived_non_actionable_feature_count,
                    info_feature_count=info_feature_count,
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
            f"Source diagnostics severity-ranking non-actionable-count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking non-actionable-count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking non-actionable-count field(s) diverged from the deterministic zero-rank derivation."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during non-actionable-count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking non-actionable-count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingNonActionableCountReconciliation(
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

    def _build_source_diagnostics_severity_ranking_critical_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-ranking critical-count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking critical-count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_critical_feature_count=0,
                        derived_critical_feature_count=0,
                        high_severity_feature_count=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics severity-ranking critical-count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
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

            summary_critical_feature_count = 0
            derived_critical_feature_count = 0
            high_severity_feature_count = 0
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
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_ranking_count += 1
                    continue
                if severity_rank <= 0:
                    continue
                if critical:
                    summary_critical_feature_count += 1
                if (
                    severity_level == "critical"
                    or severity_rank >= HIGH_SEVERITY_MIN_RANK
                ):
                    high_severity_feature_count += 1
                if (
                    severity_level == "critical"
                    or severity_rank >= CRITICAL_SEVERITY_MIN_RANK
                ):
                    derived_critical_feature_count += 1

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "severity_ranking" not in missing_fields:
                available_checks += 1
                if summary_critical_feature_count == derived_critical_feature_count:
                    aligned_checks += 1
                else:
                    mismatched_fields.append("severity_ranking_critical_count")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking critical-count reconciliation was invalid because persisted severity-ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking critical counts diverged from the deterministic critical-severity derivation."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-ranking critical-count reconciliation was partial because persisted severity-ranking metadata was missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics severity-ranking critical counts remained aligned with the deterministic critical-severity derivation."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_critical_feature_count=summary_critical_feature_count,
                    derived_critical_feature_count=derived_critical_feature_count,
                    high_severity_feature_count=high_severity_feature_count,
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
            f"Source diagnostics severity-ranking critical-count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during severity-ranking critical-count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted severity-ranking critical-count field(s) diverged from the deterministic critical-severity derivation."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity-ranking issue(s) were detected during critical-count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-ranking critical-count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankingCriticalCountReconciliation(
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

__all__ = ["SnapshotReplaySourceQualityReconciliationCountsSeverityMixin"]
