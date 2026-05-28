from __future__ import annotations

from app.services.snapshot_replay_source_common import (
    Any,
    Mapping,
    SnapshotSourceFreshnessStatusThresholdReconciliation,
    SnapshotSourceFreshnessStatusThresholdReconciliationEntry,
    SnapshotSourceFreshnessSummaryReconciliation,
    SnapshotSourceFreshnessSummaryReconciliationEntry,
    SnapshotSourceObservationFreshnessSecondsDrift,
    SnapshotSourceObservationFreshnessSecondsDriftEntry,
    UTC,
    datetime,
)


class SnapshotReplaySourceTimingFreshnessStatusMixin:
    def _build_source_freshness_summary_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceFreshnessSummaryReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source freshness summary reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source freshness summary reconciliation analysis."
                )
            return SnapshotSourceFreshnessSummaryReconciliation(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_freshness_source_ids=(),
                record_only_stale_source_ids=(),
                summary_only_stale_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceFreshnessSummaryReconciliationEntry] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_freshness_source_ids: set[str] = set()
        aggregate_record_only_stale_source_ids: set[str] = set()
        aggregate_summary_only_stale_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            summary_stale_sources = snapshot_payload.get("stale_sources", ())
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceFreshnessSummaryReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        aligned_records=0,
                        record_stale_source_count=0,
                        summary_stale_source_count=0,
                        record_degraded_source_count=0,
                        record_fresh_source_count=0,
                        missing_freshness_source_ids=(),
                        record_only_stale_source_ids=(),
                        summary_only_stale_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source freshness summary reconciliation could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            if not isinstance(summary_stale_sources, (list, tuple)):
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceFreshnessSummaryReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=len(source_observation_records),
                        aligned_records=0,
                        record_stale_source_count=0,
                        summary_stale_source_count=0,
                        record_degraded_source_count=0,
                        record_fresh_source_count=0,
                        missing_freshness_source_ids=(),
                        record_only_stale_source_ids=(),
                        summary_only_stale_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source freshness summary reconciliation could not be evaluated because persisted stale-sources summary metadata was malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            aligned_records = 0
            malformed_record_count = 0
            missing_freshness_source_ids: set[str] = set()
            record_stale_source_ids: set[str] = set()
            record_degraded_source_ids: set[str] = set()
            record_fresh_source_ids: set[str] = set()
            summary_stale_source_id_set = {
                source_id.strip()
                for source_id in summary_stale_sources
                if isinstance(source_id, str) and source_id.strip()
            }

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                freshness_status = record.get("freshness_status")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                if not isinstance(freshness_status, str) or not freshness_status.strip():
                    missing_freshness_source_ids.add(source_id)
                    continue

                normalized_status = freshness_status.strip()
                if normalized_status == "stale":
                    record_stale_source_ids.add(source_id)
                elif normalized_status == "degraded":
                    record_degraded_source_ids.add(source_id)
                elif normalized_status == "fresh":
                    record_fresh_source_ids.add(source_id)
                else:
                    missing_freshness_source_ids.add(source_id)
                    continue

                if (
                    (normalized_status == "stale" and source_id in summary_stale_source_id_set)
                    or (normalized_status != "stale" and source_id not in summary_stale_source_id_set)
                ):
                    aligned_records += 1

            record_only_stale_source_ids = record_stale_source_ids - summary_stale_source_id_set
            summary_only_stale_source_ids = summary_stale_source_id_set - record_stale_source_ids
            consistency_percentage = round(
                (aligned_records / total_records) * 100.0,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source freshness summary reconciliation was invalid because one or more source observation records were malformed."
                )
            elif record_only_stale_source_ids or summary_only_stale_source_ids:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source freshness summary reconciliation was degraded because record-level stale source IDs diverged from the persisted stale-sources summary."
                )
            elif missing_freshness_source_ids:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source freshness summary reconciliation was partial because one or more source observation records were missing usable freshness metadata."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted stale-source summary remained aligned with record-level freshness metadata."
                )

            aggregate_missing_freshness_source_ids.update(missing_freshness_source_ids)
            aggregate_record_only_stale_source_ids.update(record_only_stale_source_ids)
            aggregate_summary_only_stale_source_ids.update(summary_only_stale_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceFreshnessSummaryReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    aligned_records=aligned_records,
                    record_stale_source_count=len(record_stale_source_ids),
                    summary_stale_source_count=len(summary_stale_source_id_set),
                    record_degraded_source_count=len(record_degraded_source_ids),
                    record_fresh_source_count=len(record_fresh_source_ids),
                    missing_freshness_source_ids=tuple(sorted(missing_freshness_source_ids)),
                    record_only_stale_source_ids=tuple(sorted(record_only_stale_source_ids)),
                    summary_only_stale_source_ids=tuple(sorted(summary_only_stale_source_ids)),
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
            f"Source freshness summary reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_freshness_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_freshness_source_ids)} source ID(s) were missing usable freshness metadata."
            )
        if aggregate_record_only_stale_source_ids:
            diagnostics.append(
                f"{len(aggregate_record_only_stale_source_ids)} stale source ID(s) appeared only in record-level freshness metadata."
            )
        if aggregate_summary_only_stale_source_ids:
            diagnostics.append(
                f"{len(aggregate_summary_only_stale_source_ids)} stale source ID(s) appeared only in the persisted stale-sources summary."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during source freshness summary reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source freshness summary reconciliation analysis."
            )

        return SnapshotSourceFreshnessSummaryReconciliation(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_freshness_source_ids=tuple(sorted(aggregate_missing_freshness_source_ids)),
            record_only_stale_source_ids=tuple(sorted(aggregate_record_only_stale_source_ids)),
            summary_only_stale_source_ids=tuple(sorted(aggregate_summary_only_stale_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    @staticmethod
    def _derive_freshness_threshold_status(
        *,
        freshness_seconds: int,
        is_stale: bool,
    ) -> str:
        if is_stale or freshness_seconds > 300:
            return "stale"
        if freshness_seconds > 120:
            return "degraded"
        return "fresh"

    def _build_source_observation_freshness_seconds_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationFreshnessSecondsDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation freshness-seconds drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation freshness-seconds drift analysis."
                )
            return SnapshotSourceObservationFreshnessSecondsDrift(
                drift_classification="insufficient_data",
                average_freshness_seconds=0.0,
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
                missing_freshness_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceObservationFreshnessSecondsDriftEntry] = []
        aggregate_degraded_source_ids: set[str] = set()
        aggregate_improved_source_ids: set[str] = set()
        aggregate_missing_freshness_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        previous_freshness_by_source: dict[str, int] = {}
        previous_average_freshness_seconds: float | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            serialized_snapshots = snapshot_payload.get("snapshots")
            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(serialized_snapshots, list) or not serialized_snapshots:
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationFreshnessSecondsDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_freshness_seconds=0.0,
                        previous_average_freshness_seconds=previous_average_freshness_seconds,
                        freshness_delta_from_previous_seconds=None,
                        total_records=0,
                        valid_freshness_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_freshness_source_ids=(),
                        malformed_record_count=1,
                        diagnostic=(
                            "Source observation freshness-seconds drift could not be evaluated because snapshot freshness records were missing or malformed."
                        ),
                    )
                )
                continue

            if not isinstance(source_observation_records, list) or not source_observation_records:
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationFreshnessSecondsDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_freshness_seconds=0.0,
                        previous_average_freshness_seconds=previous_average_freshness_seconds,
                        freshness_delta_from_previous_seconds=None,
                        total_records=0,
                        valid_freshness_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_freshness_source_ids=(),
                        malformed_record_count=1,
                        diagnostic=(
                            "Source observation freshness-seconds drift could not be evaluated because source observation records were missing or malformed."
                        ),
                    )
                )
                continue

            freshness_by_asset: dict[str, int] = {}
            malformed_record_count = 0
            for snapshot_data in serialized_snapshots:
                if not isinstance(snapshot_data, Mapping):
                    malformed_record_count += 1
                    continue

                raw_asset_symbol = snapshot_data.get("asset_symbol")
                raw_freshness_seconds = snapshot_data.get("freshness_seconds")
                if not isinstance(raw_asset_symbol, str) or not raw_asset_symbol.strip():
                    malformed_record_count += 1
                    continue

                try:
                    freshness_by_asset[raw_asset_symbol.strip()] = int(raw_freshness_seconds)
                except Exception:
                    malformed_record_count += 1

            total_records = len(source_observation_records)
            valid_freshness_records = 0
            current_freshness_by_source: dict[str, int] = {}
            missing_freshness_source_ids: set[str] = set()

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                raw_asset_symbol = record.get("asset_symbol")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                if not isinstance(raw_asset_symbol, str) or not raw_asset_symbol.strip():
                    malformed_record_count += 1
                    continue

                source_id = raw_source_id.strip()
                asset_symbol = raw_asset_symbol.strip()
                freshness_seconds = freshness_by_asset.get(asset_symbol)
                if freshness_seconds is None:
                    missing_freshness_source_ids.add(source_id)
                    continue

                current_freshness_by_source[source_id] = freshness_seconds
                valid_freshness_records += 1

            if current_freshness_by_source:
                average_freshness_seconds = round(
                    sum(current_freshness_by_source.values()) / len(current_freshness_by_source),
                    2,
                )
            else:
                average_freshness_seconds = 0.0

            degraded_source_ids: set[str] = set()
            improved_source_ids: set[str] = set()
            freshness_delta_from_previous_seconds: float | None = None

            if not current_freshness_by_source:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source observation freshness-seconds drift could not be evaluated because no usable source-to-freshness mappings were available."
                )
            else:
                if previous_average_freshness_seconds is not None:
                    freshness_delta_from_previous_seconds = round(
                        average_freshness_seconds - previous_average_freshness_seconds,
                        2,
                    )

                if not previous_freshness_by_source:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = (
                        "Source observation freshness-seconds baseline was established from persisted snapshot freshness values."
                    )
                else:
                    for source_id, freshness_seconds in current_freshness_by_source.items():
                        previous_freshness_seconds = previous_freshness_by_source.get(source_id)
                        if previous_freshness_seconds is None:
                            continue
                        if freshness_seconds > previous_freshness_seconds:
                            degraded_source_ids.add(source_id)
                        elif freshness_seconds < previous_freshness_seconds:
                            improved_source_ids.add(source_id)

                    if degraded_source_ids and improved_source_ids:
                        drift_classification = "mixed"
                        mixed_snapshots += 1
                        diagnostic = (
                            "Source observation freshness-seconds drift was mixed because some sources became fresher while others deteriorated."
                        )
                    elif degraded_source_ids:
                        drift_classification = "degrading"
                        degrading_snapshots += 1
                        diagnostic = (
                            "Source observation freshness-seconds deteriorated compared with the previous saved snapshot."
                        )
                    elif improved_source_ids:
                        drift_classification = "improving"
                        improving_snapshots += 1
                        diagnostic = (
                            "Source observation freshness-seconds improved compared with the previous saved snapshot."
                        )
                    else:
                        drift_classification = "stable"
                        stable_snapshots += 1
                        diagnostic = (
                            "Source observation freshness-seconds remained stable compared with the previous saved snapshot."
                        )

            aggregate_degraded_source_ids.update(degraded_source_ids)
            aggregate_improved_source_ids.update(improved_source_ids)
            aggregate_missing_freshness_source_ids.update(missing_freshness_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceObservationFreshnessSecondsDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    average_freshness_seconds=average_freshness_seconds,
                    previous_average_freshness_seconds=previous_average_freshness_seconds,
                    freshness_delta_from_previous_seconds=freshness_delta_from_previous_seconds,
                    total_records=total_records,
                    valid_freshness_records=valid_freshness_records,
                    degraded_source_ids=tuple(sorted(degraded_source_ids)),
                    improved_source_ids=tuple(sorted(improved_source_ids)),
                    missing_freshness_source_ids=tuple(sorted(missing_freshness_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

            if current_freshness_by_source:
                previous_freshness_by_source = dict(current_freshness_by_source)
                previous_average_freshness_seconds = average_freshness_seconds

        snapshots_checked = len(entries)
        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_freshness_seconds = 0.0
            severity_score = 0
        else:
            average_freshness_seconds = round(
                sum(entry.average_freshness_seconds for entry in valid_entries) / len(valid_entries),
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
                        abs(entry.freshness_delta_from_previous_seconds or 0.0)
                        for entry in valid_entries
                    )
                )
            )

        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation freshness-seconds remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation freshness-seconds deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation freshness-seconds improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation freshness-seconds were mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation freshness-seconds drift had insufficient usable data.")

        if aggregate_missing_freshness_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_freshness_source_ids)} source ID(s) were missing freshness-seconds coverage from persisted snapshots."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed record issue(s) were detected during source observation freshness-seconds drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation freshness-seconds drift analysis."
            )

        return SnapshotSourceObservationFreshnessSecondsDrift(
            drift_classification=drift_classification,
            average_freshness_seconds=average_freshness_seconds,
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
            missing_freshness_source_ids=tuple(sorted(aggregate_missing_freshness_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_freshness_status_threshold_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceFreshnessStatusThresholdReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source freshness-status threshold reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source freshness-status threshold reconciliation analysis."
                )
            return SnapshotSourceFreshnessStatusThresholdReconciliation(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_freshness_status_source_ids=(),
                threshold_mismatch_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceFreshnessStatusThresholdReconciliationEntry] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_freshness_status_source_ids: set[str] = set()
        aggregate_threshold_mismatch_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            serialized_snapshots = snapshot_payload.get("snapshots")
            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(serialized_snapshots, list) or not serialized_snapshots:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceFreshnessStatusThresholdReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        aligned_records=0,
                        fresh_threshold_source_count=0,
                        degraded_threshold_source_count=0,
                        stale_threshold_source_count=0,
                        missing_freshness_status_source_ids=(),
                        threshold_mismatch_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source freshness-status threshold reconciliation could not be evaluated because snapshot freshness records were missing or malformed.",
                    )
                )
                continue

            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceFreshnessStatusThresholdReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        aligned_records=0,
                        fresh_threshold_source_count=0,
                        degraded_threshold_source_count=0,
                        stale_threshold_source_count=0,
                        missing_freshness_status_source_ids=(),
                        threshold_mismatch_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source freshness-status threshold reconciliation could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            freshness_by_asset: dict[str, tuple[int, bool]] = {}
            malformed_record_count = 0
            for snapshot_data in serialized_snapshots:
                if not isinstance(snapshot_data, Mapping):
                    malformed_record_count += 1
                    continue

                raw_asset_symbol = snapshot_data.get("asset_symbol")
                raw_freshness_seconds = snapshot_data.get("freshness_seconds")
                if not isinstance(raw_asset_symbol, str) or not raw_asset_symbol.strip():
                    malformed_record_count += 1
                    continue

                try:
                    freshness_seconds = int(raw_freshness_seconds)
                except Exception:
                    malformed_record_count += 1
                    continue

                freshness_by_asset[raw_asset_symbol.strip()] = (
                    freshness_seconds,
                    bool(snapshot_data.get("is_stale", False)),
                )

            total_records = len(source_observation_records)
            aligned_records = 0
            fresh_threshold_source_count = 0
            degraded_threshold_source_count = 0
            stale_threshold_source_count = 0
            missing_freshness_status_source_ids: set[str] = set()
            threshold_mismatch_source_ids: set[str] = set()

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                raw_asset_symbol = record.get("asset_symbol")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                if not isinstance(raw_asset_symbol, str) or not raw_asset_symbol.strip():
                    malformed_record_count += 1
                    continue

                source_id = raw_source_id.strip()
                asset_symbol = raw_asset_symbol.strip()
                freshness_pair = freshness_by_asset.get(asset_symbol)
                if freshness_pair is None:
                    malformed_record_count += 1
                    continue

                raw_freshness_status = record.get("freshness_status")
                if not isinstance(raw_freshness_status, str) or not raw_freshness_status.strip():
                    missing_freshness_status_source_ids.add(source_id)
                    continue

                normalized_status = raw_freshness_status.strip()
                if normalized_status not in {"fresh", "degraded", "stale"}:
                    missing_freshness_status_source_ids.add(source_id)
                    continue

                derived_status = self._derive_freshness_threshold_status(
                    freshness_seconds=freshness_pair[0],
                    is_stale=freshness_pair[1],
                )
                if derived_status == "fresh":
                    fresh_threshold_source_count += 1
                elif derived_status == "degraded":
                    degraded_threshold_source_count += 1
                else:
                    stale_threshold_source_count += 1

                if normalized_status == derived_status:
                    aligned_records += 1
                else:
                    threshold_mismatch_source_ids.add(source_id)

            consistency_percentage = round(
                (aligned_records / total_records) * 100.0,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source freshness-status threshold reconciliation was invalid because one or more persisted records were malformed."
                )
            elif threshold_mismatch_source_ids:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source freshness-status threshold reconciliation was degraded because persisted freshness statuses diverged from deterministic freshness-seconds threshold bands."
                )
            elif missing_freshness_status_source_ids:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source freshness-status threshold reconciliation was partial because one or more source observation records were missing usable freshness-status metadata."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted freshness-status metadata remained aligned with deterministic freshness-seconds threshold bands."
                )

            aggregate_missing_freshness_status_source_ids.update(
                missing_freshness_status_source_ids
            )
            aggregate_threshold_mismatch_source_ids.update(threshold_mismatch_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceFreshnessStatusThresholdReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    aligned_records=aligned_records,
                    fresh_threshold_source_count=fresh_threshold_source_count,
                    degraded_threshold_source_count=degraded_threshold_source_count,
                    stale_threshold_source_count=stale_threshold_source_count,
                    missing_freshness_status_source_ids=tuple(
                        sorted(missing_freshness_status_source_ids)
                    ),
                    threshold_mismatch_source_ids=tuple(
                        sorted(threshold_mismatch_source_ids)
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
            f"Source freshness-status threshold reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_freshness_status_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_freshness_status_source_ids)} source ID(s) were missing usable freshness-status metadata."
            )
        if aggregate_threshold_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_threshold_mismatch_source_ids)} source ID(s) diverged from deterministic freshness-seconds threshold bands."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed record issue(s) were detected during source freshness-status threshold reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source freshness-status threshold reconciliation analysis."
            )

        return SnapshotSourceFreshnessStatusThresholdReconciliation(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_freshness_status_source_ids=tuple(
                sorted(aggregate_missing_freshness_status_source_ids)
            ),
            threshold_mismatch_source_ids=tuple(
                sorted(aggregate_threshold_mismatch_source_ids)
            ),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = ["SnapshotReplaySourceTimingFreshnessStatusMixin"]
