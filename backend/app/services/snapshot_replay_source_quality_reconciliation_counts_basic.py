from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation,
    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry,
    SnapshotSourceDiagnosticsMissingAssetCountReconciliation,
    SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry,
    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation,
    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry,
    SnapshotSourceDiagnosticsStaleAssetCountReconciliation,
    SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry,
)

class SnapshotReplaySourceQualityReconciliationCountsBasicMixin:
    def _build_source_diagnostics_stale_asset_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsStaleAssetCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics stale-asset count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics stale-asset count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsStaleAssetCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_features_with_stale_sources=0,
                        derived_features_with_stale_sources=0,
                        summary_total_stale_assets=0,
                        derived_total_stale_assets=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics stale-asset count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            try:
                summary_features_with_stale_sources = int(summary["features_with_stale_sources"])
            except Exception:
                summary_features_with_stale_sources = 0
                missing_fields.append("features_with_stale_sources")
            try:
                summary_total_stale_assets = int(summary["total_stale_assets"])
            except Exception:
                summary_total_stale_assets = 0
                missing_fields.append("total_stale_assets")

            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            derived_features_with_stale_sources = 0
            derived_total_stale_assets = 0
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue

                raw_stale_assets = ranking_entry.get("stale_assets", [])
                raw_status = ranking_entry.get("status")
                if not isinstance(raw_stale_assets, list) or not isinstance(raw_status, str):
                    malformed_ranking_count += 1
                    continue

                stale_assets = [
                    asset_code
                    for asset_code in raw_stale_assets
                    if isinstance(asset_code, str) and asset_code.strip()
                ]
                if len(stale_assets) != len(raw_stale_assets):
                    malformed_ranking_count += 1
                if raw_status == "stale_required_sources" or stale_assets:
                    if stale_assets:
                        derived_features_with_stale_sources += 1
                        derived_total_stale_assets += len(stale_assets)

            aligned_fields = 0
            mismatched_fields: list[str] = []
            if "features_with_stale_sources" not in missing_fields:
                if summary_features_with_stale_sources == derived_features_with_stale_sources:
                    aligned_fields += 1
                else:
                    mismatched_fields.append("features_with_stale_sources")
            if "total_stale_assets" not in missing_fields:
                if summary_total_stale_assets == derived_total_stale_assets:
                    aligned_fields += 1
                else:
                    mismatched_fields.append("total_stale_assets")

            available_checks = 2 - len(
                [field for field in missing_fields if field in {"features_with_stale_sources", "total_stale_assets"}]
            )
            consistency_percentage = round(
                (aligned_fields / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-asset count reconciliation was invalid because persisted severity_ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics stale-asset counts diverged from the persisted severity_ranking breakdown."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-asset count reconciliation was partial because one or more persisted summary fields were missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics stale-asset counts remained aligned with the severity_ranking breakdown."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsStaleAssetCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_features_with_stale_sources=summary_features_with_stale_sources,
                    derived_features_with_stale_sources=derived_features_with_stale_sources,
                    summary_total_stale_assets=summary_total_stale_assets,
                    derived_total_stale_assets=derived_total_stale_assets,
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
            f"Source diagnostics stale-asset count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during stale-asset count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted stale-asset count field(s) diverged from the severity_ranking breakdown."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity_ranking issue(s) were detected during stale-asset count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics stale-asset count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsStaleAssetCountReconciliation(
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

    def _build_source_diagnostics_minimum_coverage_floor_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics minimum-coverage floor reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics minimum-coverage floor reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_minimum_coverage_score=0.0,
                        derived_minimum_coverage_score=None,
                        total_features=0,
                        ready_features=0,
                        floor_derivation_mode=None,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics minimum-coverage floor reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            try:
                summary_minimum_coverage_score = round(float(summary["minimum_coverage_score"]), 2)
            except Exception:
                summary_minimum_coverage_score = 0.0
                missing_fields.append("minimum_coverage_score")
            try:
                total_features = int(summary["total_features"])
            except Exception:
                total_features = 0
                missing_fields.append("total_features")
            try:
                ready_features = int(summary["ready_features"])
            except Exception:
                ready_features = 0
                missing_fields.append("ready_features")

            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            ranking_coverage_scores: list[float] = []
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue
                raw_coverage_score = ranking_entry.get("coverage_score")
                try:
                    ranking_coverage_scores.append(round(float(raw_coverage_score), 2))
                except Exception:
                    malformed_ranking_count += 1

            if ranking_coverage_scores:
                derived_minimum_coverage_score = min(ranking_coverage_scores)
                floor_derivation_mode = "severity_ranking"
            elif (
                "total_features" not in missing_fields
                and "ready_features" not in missing_fields
                and total_features > 0
                and ready_features == total_features
            ):
                derived_minimum_coverage_score = 100.0
                floor_derivation_mode = "all_features_ready"
            else:
                derived_minimum_coverage_score = None
                floor_derivation_mode = None

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "minimum_coverage_score" not in missing_fields and derived_minimum_coverage_score is not None:
                available_checks += 1
                if summary_minimum_coverage_score == derived_minimum_coverage_score:
                    aligned_checks += 1
                else:
                    mismatched_fields.append("minimum_coverage_score")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics minimum-coverage floor reconciliation was invalid because persisted severity_ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics minimum coverage floor diverged from the persisted severity_ranking or ready-feature rule."
                )
            elif missing_fields or derived_minimum_coverage_score is None:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics minimum-coverage floor reconciliation was partial because one or more persisted summary fields were missing or the floor could not be derived safely."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics minimum coverage floor remained aligned with the persisted severity_ranking or ready-feature rule."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_minimum_coverage_score=summary_minimum_coverage_score,
                    derived_minimum_coverage_score=derived_minimum_coverage_score,
                    total_features=total_features,
                    ready_features=ready_features,
                    floor_derivation_mode=floor_derivation_mode,
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
            f"Source diagnostics minimum-coverage floor reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during minimum-coverage floor reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted minimum-coverage floor field(s) diverged from the deterministic derivation rule."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity_ranking issue(s) were detected during minimum-coverage floor reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics minimum-coverage floor reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsMinimumCoverageFloorReconciliation(
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

    def _build_source_diagnostics_missing_asset_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsMissingAssetCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics missing-asset count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics missing-asset count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsMissingAssetCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_features_with_missing_sources=0,
                        derived_features_with_missing_sources=0,
                        summary_total_missing_assets=0,
                        derived_total_missing_assets=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics missing-asset count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            try:
                summary_features_with_missing_sources = int(
                    summary["features_with_missing_sources"]
                )
            except Exception:
                summary_features_with_missing_sources = 0
                missing_fields.append("features_with_missing_sources")
            try:
                summary_total_missing_assets = int(summary["total_missing_assets"])
            except Exception:
                summary_total_missing_assets = 0
                missing_fields.append("total_missing_assets")

            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            derived_features_with_missing_sources = 0
            derived_total_missing_assets = 0
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue

                raw_missing_assets = ranking_entry.get("missing_assets", [])
                raw_status = ranking_entry.get("status")
                if not isinstance(raw_missing_assets, list) or not isinstance(raw_status, str):
                    malformed_ranking_count += 1
                    continue

                missing_assets = [
                    asset_code
                    for asset_code in raw_missing_assets
                    if isinstance(asset_code, str) and asset_code.strip()
                ]
                if len(missing_assets) != len(raw_missing_assets):
                    malformed_ranking_count += 1
                if raw_status == "missing_required_sources" or missing_assets:
                    if missing_assets:
                        derived_features_with_missing_sources += 1
                        derived_total_missing_assets += len(missing_assets)

            aligned_fields = 0
            mismatched_fields: list[str] = []
            if "features_with_missing_sources" not in missing_fields:
                if summary_features_with_missing_sources == derived_features_with_missing_sources:
                    aligned_fields += 1
                else:
                    mismatched_fields.append("features_with_missing_sources")
            if "total_missing_assets" not in missing_fields:
                if summary_total_missing_assets == derived_total_missing_assets:
                    aligned_fields += 1
                else:
                    mismatched_fields.append("total_missing_assets")

            available_checks = 2 - len(
                [
                    field
                    for field in missing_fields
                    if field in {"features_with_missing_sources", "total_missing_assets"}
                ]
            )
            consistency_percentage = round(
                (aligned_fields / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics missing-asset count reconciliation was invalid because persisted severity_ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics missing-asset counts diverged from the persisted severity_ranking breakdown."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics missing-asset count reconciliation was partial because one or more persisted summary fields were missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics missing-asset counts remained aligned with the severity_ranking breakdown."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsMissingAssetCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_features_with_missing_sources=summary_features_with_missing_sources,
                    derived_features_with_missing_sources=derived_features_with_missing_sources,
                    summary_total_missing_assets=summary_total_missing_assets,
                    derived_total_missing_assets=derived_total_missing_assets,
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
            f"Source diagnostics missing-asset count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during missing-asset count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted missing-asset count field(s) diverged from the severity_ranking breakdown."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity_ranking issue(s) were detected during missing-asset count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics missing-asset count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsMissingAssetCountReconciliation(
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

    def _build_source_diagnostics_missing_source_feature_count_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics missing-source feature-count reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics missing-source feature-count reconciliation analysis."
                )
            return SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation(
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

        entries: list[SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry] = []
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
                    SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        summary_features_with_missing_sources=0,
                        derived_features_with_missing_sources=0,
                        total_missing_assets=0,
                        missing_fields=("source_diagnostics_summary",),
                        mismatched_fields=(),
                        malformed_ranking_count=1,
                        diagnostic=(
                            "Source diagnostics missing-source feature-count reconciliation could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            missing_fields: list[str] = []
            malformed_ranking_count = 0
            try:
                summary_features_with_missing_sources = int(
                    summary["features_with_missing_sources"]
                )
            except Exception:
                summary_features_with_missing_sources = 0
                missing_fields.append("features_with_missing_sources")
            try:
                total_missing_assets = int(summary["total_missing_assets"])
            except Exception:
                total_missing_assets = 0
                missing_fields.append("total_missing_assets")

            raw_severity_ranking = summary.get("severity_ranking")
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                missing_fields.append("severity_ranking")

            derived_features_with_missing_sources = 0
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_ranking_count += 1
                    continue

                raw_missing_assets = ranking_entry.get("missing_assets", [])
                raw_status = ranking_entry.get("status")
                if not isinstance(raw_missing_assets, list) or not isinstance(raw_status, str):
                    malformed_ranking_count += 1
                    continue

                missing_assets = [
                    asset_code
                    for asset_code in raw_missing_assets
                    if isinstance(asset_code, str) and asset_code.strip()
                ]
                if len(missing_assets) != len(raw_missing_assets):
                    malformed_ranking_count += 1
                if raw_status == "missing_required_sources" or missing_assets:
                    if missing_assets:
                        derived_features_with_missing_sources += 1

            mismatched_fields: list[str] = []
            available_checks = 0
            aligned_checks = 0
            if "features_with_missing_sources" not in missing_fields:
                available_checks += 1
                if summary_features_with_missing_sources == derived_features_with_missing_sources:
                    aligned_checks += 1
                else:
                    mismatched_fields.append("features_with_missing_sources")

            consistency_percentage = round(
                (aligned_checks / available_checks) * 100.0,
                2,
            ) if available_checks > 0 else 0.0

            if malformed_ranking_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source diagnostics missing-source feature-count reconciliation was invalid because persisted severity_ranking entries were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics missing-source feature counts diverged from the persisted severity_ranking breakdown."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source diagnostics missing-source feature-count reconciliation was partial because one or more persisted summary fields were missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source diagnostics missing-source feature counts remained aligned with the severity_ranking breakdown."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_ranking_count += malformed_ranking_count
            entries.append(
                SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    summary_features_with_missing_sources=summary_features_with_missing_sources,
                    derived_features_with_missing_sources=derived_features_with_missing_sources,
                    total_missing_assets=total_missing_assets,
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
            f"Source diagnostics missing-source feature-count reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted source diagnostics summary field(s) were missing during missing-source feature-count reconciliation."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted missing-source feature-count field(s) diverged from the severity_ranking breakdown."
            )
        if aggregate_malformed_ranking_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_ranking_count} malformed severity_ranking issue(s) were detected during missing-source feature-count reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics missing-source feature-count reconciliation analysis."
            )

        return SnapshotSourceDiagnosticsMissingSourceFeatureCountReconciliation(
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

__all__ = ["SnapshotReplaySourceQualityReconciliationCountsBasicMixin"]
