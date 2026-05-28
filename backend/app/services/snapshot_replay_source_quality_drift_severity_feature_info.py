from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsInfoFeatureDrift,
    SnapshotSourceDiagnosticsInfoFeatureDriftEntry,
)
from app.services.snapshot_replay_source_common import (
    INFO_SEVERITY_MAX_RANK,
    WARNING_SEVERITY_MAX_RANK,
    WARNING_SEVERITY_MIN_RANK,
)


class SnapshotReplaySourceQualityDriftSeverityFeatureInfoMixin:
    def _build_source_diagnostics_info_feature_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsInfoFeatureDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics info-feature drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics info-feature drift analysis."
                )
            return SnapshotSourceDiagnosticsInfoFeatureDrift(
                drift_classification="insufficient_data",
                average_info_feature_count=0.0,
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

        entries: list[SnapshotSourceDiagnosticsInfoFeatureDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_info_feature_count: int | None = None
        previous_warning_feature_count: int | None = None

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
                    SnapshotSourceDiagnosticsInfoFeatureDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        info_feature_count=0,
                        previous_info_feature_count=previous_info_feature_count,
                        info_feature_delta=None,
                        warning_feature_count=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics info-feature drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            raw_severity_ranking = summary.get("severity_ranking")
            malformed_field_count = 0
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                malformed_field_count += 1

            info_feature_count = 0
            warning_feature_count = 0
            for ranking_entry in raw_severity_ranking:
                if not isinstance(ranking_entry, Mapping):
                    malformed_field_count += 1
                    continue
                feature_name = ranking_entry.get("feature_name")
                status = ranking_entry.get("status")
                critical = ranking_entry.get("critical")
                severity_level = ranking_entry.get("severity_level")
                raw_severity_rank = ranking_entry.get("severity_rank")
                if not isinstance(feature_name, str) or not feature_name.strip():
                    malformed_field_count += 1
                    continue
                if not isinstance(status, str) or not status.strip():
                    malformed_field_count += 1
                    continue
                if not isinstance(critical, bool):
                    malformed_field_count += 1
                    continue
                if not isinstance(severity_level, str) or not severity_level.strip():
                    malformed_field_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_field_count += 1
                    continue
                if severity_level == "warning" or (
                    severity_level != "critical"
                    and WARNING_SEVERITY_MIN_RANK <= severity_rank <= WARNING_SEVERITY_MAX_RANK
                ):
                    warning_feature_count += 1
                if severity_level == "info" or severity_rank <= INFO_SEVERITY_MAX_RANK:
                    info_feature_count += 1

            info_feature_delta: int | None = None
            if previous_info_feature_count is not None:
                info_feature_delta = info_feature_count - previous_info_feature_count

            if malformed_field_count > 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics info-feature drift could not be evaluated because persisted severity-ranking fields were malformed or incomplete."
                )
            elif previous_info_feature_count is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics info-feature baseline was established from persisted severity-ranking metadata."
                )
            elif info_feature_delta is not None and info_feature_delta > 0:
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics info-feature pressure deteriorated compared with the previous saved snapshot."
                )
            elif info_feature_delta is not None and info_feature_delta < 0:
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics info-feature pressure improved compared with the previous saved snapshot."
                )
            elif (
                previous_warning_feature_count is not None
                and warning_feature_count != previous_warning_feature_count
            ):
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics info-feature counts stayed flat, but persisted warning-feature pressure changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics info-feature pressure remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsInfoFeatureDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    info_feature_count=info_feature_count,
                    previous_info_feature_count=previous_info_feature_count,
                    info_feature_delta=info_feature_delta,
                    warning_feature_count=warning_feature_count,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0:
                previous_info_feature_count = info_feature_count
                previous_warning_feature_count = warning_feature_count

        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_info_feature_count = 0.0
            severity_score = 0
        else:
            average_info_feature_count = round(
                sum(entry.info_feature_count for entry in valid_entries) / len(valid_entries),
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
            severity_score = int(max(abs(entry.info_feature_delta or 0) for entry in valid_entries))

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics info-feature pressure remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics info-feature pressure deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics info-feature pressure improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics info-feature pressure was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics info-feature drift had insufficient usable severity-ranking metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed severity-ranking field issue(s) were detected during info-feature drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics info-feature drift analysis."
            )

        return SnapshotSourceDiagnosticsInfoFeatureDrift(
            drift_classification=drift_classification,
            average_info_feature_count=average_info_feature_count,
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


__all__ = ["SnapshotReplaySourceQualityDriftSeverityFeatureInfoMixin"]
