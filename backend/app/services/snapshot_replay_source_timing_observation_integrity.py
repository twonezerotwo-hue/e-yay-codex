from __future__ import annotations

from app.services.snapshot_replay_source_common import (
    Any,
    Counter,
    Mapping,
    SnapshotMappedAtAlignmentConsistency,
    SnapshotMappedAtAlignmentConsistencyEntry,
    SnapshotSourceObservationNormalizationModeDrift,
    SnapshotSourceObservationNormalizationModeDriftEntry,
    SnapshotSourceObservationTimestampIntegrityDrift,
    SnapshotSourceObservationTimestampIntegrityDriftEntry,
    UTC,
    VALID_NORMALIZATION_MODES,
    datetime,
)


class SnapshotReplaySourceTimingObservationIntegrityMixin:
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

__all__ = ["SnapshotReplaySourceTimingObservationIntegrityMixin"]
