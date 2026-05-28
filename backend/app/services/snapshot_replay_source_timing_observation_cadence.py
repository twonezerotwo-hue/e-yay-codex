from __future__ import annotations

from app.services.snapshot_replay_source_common import (
    Any,
    Mapping,
    SnapshotSourceObservationAvailabilityLagDrift,
    SnapshotSourceObservationAvailabilityLagDriftEntry,
    SnapshotSourceObservationCadenceDrift,
    SnapshotSourceObservationCadenceEntry,
    UTC,
    datetime,
)


class SnapshotReplaySourceTimingObservationCadenceMixin:
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

__all__ = ["SnapshotReplaySourceTimingObservationCadenceMixin"]
