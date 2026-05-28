from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsSeverityRankDensityDrift,
    SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry,
    SnapshotSourceDiagnosticsSeverityRankDrift,
    SnapshotSourceDiagnosticsSeverityRankDriftEntry,
    SnapshotSourceDiagnosticsSeverityRankSpreadDrift,
    SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry,
)
from app.services.snapshot_replay_source_common import (
    SEVERITY_LABEL_SCORES,
)
from app.services.snapshot_replay_source_quality_common import (
    severity_rank_density,
    severity_rank_spread,
)

class SnapshotReplaySourceQualityDriftSeverityRankMixin:
    def _build_source_diagnostics_severity_rank_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-rank drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-rank drift analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankDrift(
                drift_classification="insufficient_data",
                average_severity_rank_total=0.0,
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_severity_rank_total: int | None = None
        previous_severity_ranking_feature_count: int | None = None

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
                    SnapshotSourceDiagnosticsSeverityRankDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        severity_rank_total=0,
                        previous_severity_rank_total=previous_severity_rank_total,
                        severity_rank_total_delta=None,
                        severity_ranking_feature_count=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics severity-rank drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            raw_severity_ranking = summary.get("severity_ranking")
            malformed_field_count = 0
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                malformed_field_count += 1

            severity_rank_total = 0
            severity_ranking_feature_count = 0
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
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_field_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_field_count += 1
                    continue

                severity_ranking_feature_count += 1
                severity_rank_total += severity_rank

            severity_rank_total_delta: int | None = None
            if previous_severity_rank_total is not None:
                severity_rank_total_delta = severity_rank_total - previous_severity_rank_total

            if malformed_field_count > 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank drift could not be evaluated because persisted severity-ranking rank fields were malformed or incomplete."
                )
            elif previous_severity_rank_total is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank baseline was established from persisted severity-ranking metadata."
                )
            elif severity_rank_total_delta is not None and severity_rank_total_delta > 0:
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank pressure deteriorated compared with the previous saved snapshot."
                )
            elif severity_rank_total_delta is not None and severity_rank_total_delta < 0:
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank pressure improved compared with the previous saved snapshot."
                )
            elif (
                previous_severity_ranking_feature_count is not None
                and severity_ranking_feature_count
                != previous_severity_ranking_feature_count
            ):
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank totals stayed flat, but persisted severity-ranking feature counts changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank pressure remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    severity_rank_total=severity_rank_total,
                    previous_severity_rank_total=previous_severity_rank_total,
                    severity_rank_total_delta=severity_rank_total_delta,
                    severity_ranking_feature_count=severity_ranking_feature_count,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0:
                previous_severity_rank_total = severity_rank_total
                previous_severity_ranking_feature_count = severity_ranking_feature_count

        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_severity_rank_total = 0.0
            severity_score = 0
        else:
            average_severity_rank_total = round(
                sum(entry.severity_rank_total for entry in valid_entries)
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
                max(abs(entry.severity_rank_total_delta or 0) for entry in valid_entries)
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics severity-rank pressure remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics severity-rank pressure deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics severity-rank pressure improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics severity-rank pressure was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics severity-rank drift had insufficient usable severity-ranking metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed severity-ranking rank field issue(s) were detected during severity-rank drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-rank drift analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankDrift(
            drift_classification=drift_classification,
            average_severity_rank_total=average_severity_rank_total,
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

    def _build_source_diagnostics_severity_rank_density_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankDensityDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-rank density drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-rank density drift analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankDensityDrift(
                drift_classification="insufficient_data",
                average_severity_rank_density=0.0,
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_severity_rank_density: float | None = None
        previous_severity_rank_total: int | None = None
        previous_severity_ranking_feature_count: int | None = None

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
                    SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        severity_rank_density=0.0,
                        previous_severity_rank_density=previous_severity_rank_density,
                        severity_rank_density_delta=None,
                        severity_ranking_feature_count=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics severity-rank density drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            raw_severity_ranking = summary.get("severity_ranking")
            malformed_field_count = 0
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                malformed_field_count += 1

            severity_rank_total = 0
            severity_ranking_feature_count = 0
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
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_field_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_field_count += 1
                    continue

                severity_ranking_feature_count += 1
                severity_rank_total += severity_rank

            severity_rank_density_value = severity_rank_density(
                severity_rank_total,
                severity_ranking_feature_count,
            )
            severity_rank_density_delta: float | None = None
            if previous_severity_rank_density is not None:
                severity_rank_density_delta = round(
                    severity_rank_density_value - previous_severity_rank_density,
                    2,
                )

            if malformed_field_count > 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank density drift could not be evaluated because persisted severity-ranking rank fields were malformed or incomplete."
                )
            elif previous_severity_rank_density is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank density baseline was established from persisted severity-ranking metadata."
                )
            elif (
                severity_rank_density_delta is not None
                and severity_rank_density_delta > 0
            ):
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank density deteriorated compared with the previous saved snapshot."
                )
            elif (
                severity_rank_density_delta is not None
                and severity_rank_density_delta < 0
            ):
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank density improved compared with the previous saved snapshot."
                )
            elif (
                previous_severity_ranking_feature_count is not None
                and previous_severity_rank_total is not None
                and (
                    severity_ranking_feature_count != previous_severity_ranking_feature_count
                    or severity_rank_total != previous_severity_rank_total
                )
            ):
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank density stayed flat, but persisted severity-ranking totals or feature counts changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank density remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankDensityDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    severity_rank_density=severity_rank_density_value,
                    previous_severity_rank_density=previous_severity_rank_density,
                    severity_rank_density_delta=severity_rank_density_delta,
                    severity_ranking_feature_count=severity_ranking_feature_count,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0:
                previous_severity_rank_density = severity_rank_density_value
                previous_severity_rank_total = severity_rank_total
                previous_severity_ranking_feature_count = severity_ranking_feature_count

        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_severity_rank_density = 0.0
            severity_score = 0
        else:
            average_severity_rank_density = round(
                sum(entry.severity_rank_density for entry in valid_entries)
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
                round(
                    max(
                        abs(entry.severity_rank_density_delta or 0.0)
                        for entry in valid_entries
                    )
                )
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics severity-rank density remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics severity-rank density deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics severity-rank density improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics severity-rank density was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics severity-rank density drift had insufficient usable severity-ranking metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed severity-ranking rank field issue(s) were detected during severity-rank density drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-rank density drift analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankDensityDrift(
            drift_classification=drift_classification,
            average_severity_rank_density=average_severity_rank_density,
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

    def _build_source_diagnostics_severity_rank_spread_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsSeverityRankSpreadDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics severity-rank spread drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-rank spread drift analysis."
                )
            return SnapshotSourceDiagnosticsSeverityRankSpreadDrift(
                drift_classification="insufficient_data",
                average_severity_rank_spread=0.0,
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

        entries: list[SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_severity_rank_spread: int | None = None
        previous_severity_rank_total: int | None = None
        previous_severity_ranking_feature_count: int | None = None

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
                    SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        severity_rank_spread=0,
                        previous_severity_rank_spread=previous_severity_rank_spread,
                        severity_rank_spread_delta=None,
                        severity_ranking_feature_count=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics severity-rank spread drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            raw_severity_ranking = summary.get("severity_ranking")
            malformed_field_count = 0
            if not isinstance(raw_severity_ranking, list):
                raw_severity_ranking = []
                malformed_field_count += 1

            severity_ranks: list[int] = []
            severity_rank_total = 0
            severity_ranking_feature_count = 0
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
                if severity_level not in SEVERITY_LABEL_SCORES:
                    malformed_field_count += 1
                    continue
                try:
                    severity_rank = int(raw_severity_rank)
                except Exception:
                    malformed_field_count += 1
                    continue

                severity_ranks.append(severity_rank)
                severity_rank_total += severity_rank
                severity_ranking_feature_count += 1

            severity_rank_spread_value = severity_rank_spread(tuple(severity_ranks))
            severity_rank_spread_delta: int | None = None
            if previous_severity_rank_spread is not None:
                severity_rank_spread_delta = (
                    severity_rank_spread_value - previous_severity_rank_spread
                )

            if malformed_field_count > 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank spread drift could not be evaluated because persisted severity-ranking rank fields were malformed or incomplete."
                )
            elif previous_severity_rank_spread is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank spread baseline was established from persisted severity-ranking metadata."
                )
            elif severity_rank_spread_delta is not None and severity_rank_spread_delta > 0:
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank spread deteriorated compared with the previous saved snapshot."
                )
            elif severity_rank_spread_delta is not None and severity_rank_spread_delta < 0:
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank spread improved compared with the previous saved snapshot."
                )
            elif (
                previous_severity_ranking_feature_count is not None
                and previous_severity_rank_total is not None
                and (
                    severity_ranking_feature_count != previous_severity_ranking_feature_count
                    or severity_rank_total != previous_severity_rank_total
                )
            ):
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank spread stayed flat, but persisted severity-ranking totals or feature counts changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics severity-rank spread remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsSeverityRankSpreadDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    severity_rank_spread=severity_rank_spread_value,
                    previous_severity_rank_spread=previous_severity_rank_spread,
                    severity_rank_spread_delta=severity_rank_spread_delta,
                    severity_ranking_feature_count=severity_ranking_feature_count,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0:
                previous_severity_rank_spread = severity_rank_spread_value
                previous_severity_rank_total = severity_rank_total
                previous_severity_ranking_feature_count = severity_ranking_feature_count

        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_severity_rank_spread = 0.0
            severity_score = 0
        else:
            average_severity_rank_spread = round(
                sum(entry.severity_rank_spread for entry in valid_entries)
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
                max(abs(entry.severity_rank_spread_delta or 0) for entry in valid_entries)
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics severity-rank spread remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics severity-rank spread deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics severity-rank spread improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics severity-rank spread was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics severity-rank spread drift had insufficient usable severity-ranking metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed severity-ranking rank field issue(s) were detected during severity-rank spread drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics severity-rank spread drift analysis."
            )

        return SnapshotSourceDiagnosticsSeverityRankSpreadDrift(
            drift_classification=drift_classification,
            average_severity_rank_spread=average_severity_rank_spread,
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

__all__ = ["SnapshotReplaySourceQualityDriftSeverityRankMixin"]
