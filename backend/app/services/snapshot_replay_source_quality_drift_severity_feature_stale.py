from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsStaleFeatureDrift,
    SnapshotSourceDiagnosticsStaleFeatureDriftEntry,
)


class SnapshotReplaySourceQualityDriftSeverityFeatureStaleMixin:
    def _build_source_diagnostics_stale_feature_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsStaleFeatureDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics stale-feature drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics stale-feature drift analysis."
                )
            return SnapshotSourceDiagnosticsStaleFeatureDrift(
                drift_classification="insufficient_data",
                average_stale_features=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                malformed_summary_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceDiagnosticsStaleFeatureDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_features_with_stale_sources: int | None = None
        previous_total_stale_assets: int | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_diagnostics_summary")
            if not isinstance(summary, Mapping):
                malformed_summary_count += 1
                insufficient_data_snapshots += 1
                entries.append(
                    SnapshotSourceDiagnosticsStaleFeatureDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        features_with_stale_sources=0,
                        previous_features_with_stale_sources=previous_features_with_stale_sources,
                        stale_feature_delta=None,
                        total_features=0,
                        total_stale_assets=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics stale-feature drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            malformed_field_count = 0
            try:
                features_with_stale_sources = int(summary["features_with_stale_sources"])
            except Exception:
                features_with_stale_sources = 0
                malformed_field_count += 1
            try:
                total_features = int(summary["total_features"])
            except Exception:
                total_features = 0
                malformed_field_count += 1
            try:
                total_stale_assets = int(summary["total_stale_assets"])
            except Exception:
                total_stale_assets = 0
                malformed_field_count += 1

            stale_feature_delta: int | None = None
            if previous_features_with_stale_sources is not None:
                stale_feature_delta = (
                    features_with_stale_sources - previous_features_with_stale_sources
                )

            if malformed_field_count > 0 or total_features <= 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-feature drift could not be evaluated because persisted summary fields were malformed or incomplete."
                )
            elif previous_features_with_stale_sources is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-feature baseline was established from persisted summary metadata."
                )
            elif stale_feature_delta is not None and stale_feature_delta > 0:
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-feature pressure deteriorated compared with the previous saved snapshot."
                )
            elif stale_feature_delta is not None and stale_feature_delta < 0:
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-feature pressure improved compared with the previous saved snapshot."
                )
            elif (
                previous_total_stale_assets is not None
                and total_stale_assets != previous_total_stale_assets
            ):
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-feature counts stayed flat, but persisted stale-asset pressure changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics stale-feature pressure remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsStaleFeatureDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    features_with_stale_sources=features_with_stale_sources,
                    previous_features_with_stale_sources=previous_features_with_stale_sources,
                    stale_feature_delta=stale_feature_delta,
                    total_features=total_features,
                    total_stale_assets=total_stale_assets,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0 and total_features > 0:
                previous_features_with_stale_sources = features_with_stale_sources
                previous_total_stale_assets = total_stale_assets

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_stale_features = 0.0
            severity_score = 0
        else:
            average_stale_features = round(
                sum(entry.features_with_stale_sources for entry in valid_entries)
                / len(valid_entries),
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
                max(abs(entry.stale_feature_delta or 0) for entry in valid_entries)
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics stale-feature pressure remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics stale-feature pressure deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics stale-feature pressure improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics stale-feature pressure was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics stale-feature drift had insufficient usable summary metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source diagnostics summary field issue(s) were detected during stale-feature drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics stale-feature drift analysis."
            )

        return SnapshotSourceDiagnosticsStaleFeatureDrift(
            drift_classification=drift_classification,
            average_stale_features=average_stale_features,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            malformed_summary_count=malformed_summary_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = ["SnapshotReplaySourceQualityDriftSeverityFeatureStaleMixin"]
