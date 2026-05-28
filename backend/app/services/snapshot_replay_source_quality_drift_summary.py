from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDiagnosticsAverageCoverageDrift,
    SnapshotSourceDiagnosticsAverageCoverageDriftEntry,
    SnapshotSourceDiagnosticsReadyFeatureDrift,
    SnapshotSourceDiagnosticsReadyFeatureDriftEntry,
    SnapshotSourceObservationConfidenceDrift,
    SnapshotSourceObservationConfidenceDriftEntry,
    SnapshotSourceObservationSummaryDrift,
    SnapshotSourceObservationSummaryDriftEntry,
)

class SnapshotReplaySourceQualityDriftSummaryMixin:
    def _build_source_observation_summary_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationSummaryDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source observation summary drift analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation summary drift analysis."
                )
            return SnapshotSourceObservationSummaryDrift(
                drift_classification="insufficient_data",
                average_summary_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                expected_total_bound_sources=0,
                expected_verified_sources=0,
                expected_simulation_only_sources=0,
                expected_paper_safe_sources=0,
                normalization_mode_changes=0,
                malformed_summary_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        registry_entries = build_source_registry_entries(load_source_registry())
        active_entries = tuple(entry for entry in registry_entries if entry.active)
        expected_total_bound_sources = len(active_entries)
        expected_verified_sources = sum(1 for entry in active_entries if entry.verified)
        expected_simulation_only_sources = sum(
            1
            for entry in active_entries
            if entry.decision_usage == "simulation_only"
        )
        expected_paper_safe_sources = expected_total_bound_sources

        entries: list[SnapshotSourceObservationSummaryDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        normalization_mode_changes = 0
        malformed_summary_count = 0
        previous_valid_entry: SnapshotSourceObservationSummaryDriftEntry | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_observation_summary")
            if not isinstance(summary, Mapping):
                insufficient_data_snapshots += 1
                malformed_summary_count += 1
                entries.append(
                    SnapshotSourceObservationSummaryDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        summary_score=0.0,
                        contract=None,
                        normalization_mode=None,
                        total_bound_sources=None,
                        verified_sources=None,
                        simulation_only_sources=None,
                        paper_safe_sources=None,
                        total_bound_source_delta=None,
                        verified_source_delta=None,
                        paper_safe_source_delta=None,
                        simulation_only_source_delta=None,
                        malformed_field_count=1,
                        diagnostic="Source observation summary drift could not be evaluated because the persisted summary was missing or malformed.",
                    )
                )
                continue

            malformed_field_count = 0
            contract = summary.get("contract")
            if not isinstance(contract, str) or not contract.strip():
                contract_value: str | None = None
                malformed_field_count += 1
            else:
                contract_value = contract.strip()

            normalization_mode = summary.get("normalization_mode")
            if not isinstance(normalization_mode, str) or not normalization_mode.strip():
                normalization_mode_value: str | None = None
                malformed_field_count += 1
            else:
                normalization_mode_value = normalization_mode.strip()

            def parse_count(field_name: str) -> int | None:
                nonlocal malformed_field_count
                value = summary.get(field_name)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    malformed_field_count += 1
                    return None
                return int(value)

            total_bound_sources = parse_count("total_bound_sources")
            verified_sources = parse_count("verified_sources")
            simulation_only_sources = parse_count("simulation_only_sources")
            paper_safe_sources = parse_count("paper_safe_sources")

            if (
                total_bound_sources is not None
                and verified_sources is not None
                and verified_sources > total_bound_sources
            ):
                malformed_field_count += 1
            if (
                total_bound_sources is not None
                and simulation_only_sources is not None
                and simulation_only_sources > total_bound_sources
            ):
                malformed_field_count += 1
            if (
                total_bound_sources is not None
                and paper_safe_sources is not None
                and paper_safe_sources > total_bound_sources
            ):
                malformed_field_count += 1

            if malformed_field_count > 0 or total_bound_sources in (None, 0) or verified_sources is None or simulation_only_sources is None or paper_safe_sources is None:
                insufficient_data_snapshots += 1
                malformed_summary_count += malformed_field_count or 1
                entries.append(
                    SnapshotSourceObservationSummaryDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        summary_score=0.0,
                        contract=contract_value,
                        normalization_mode=normalization_mode_value,
                        total_bound_sources=total_bound_sources,
                        verified_sources=verified_sources,
                        simulation_only_sources=simulation_only_sources,
                        paper_safe_sources=paper_safe_sources,
                        total_bound_source_delta=None,
                        verified_source_delta=None,
                        paper_safe_source_delta=None,
                        simulation_only_source_delta=None,
                        malformed_field_count=malformed_field_count or 1,
                        diagnostic="Source observation summary drift could not be evaluated because one or more persisted summary fields were missing or malformed.",
                    )
                )
                continue

            total_ratio = min(total_bound_sources / max(expected_total_bound_sources, 1), 1.0)
            verified_ratio = min(verified_sources / max(expected_verified_sources, 1), 1.0)
            paper_safe_ratio = min(paper_safe_sources / max(expected_paper_safe_sources, 1), 1.0)
            simulation_closeness_ratio = 1.0 - min(
                abs(simulation_only_sources - expected_simulation_only_sources) / max(expected_total_bound_sources, 1),
                1.0,
            )
            summary_score = round(
                total_ratio * 35
                + verified_ratio * 35
                + paper_safe_ratio * 20
                + simulation_closeness_ratio * 10,
                2,
            )

            if previous_valid_entry is None:
                total_bound_source_delta = total_bound_sources - expected_total_bound_sources
                verified_source_delta = verified_sources - expected_verified_sources
                paper_safe_source_delta = paper_safe_sources - expected_paper_safe_sources
                simulation_only_source_delta = simulation_only_sources - expected_simulation_only_sources
                if summary_score >= 95.0:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = "Source observation summary matched the expected paper-safe baseline."
                else:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = "Source observation summary drifted below the expected paper-safe baseline."
            else:
                total_bound_source_delta = total_bound_sources - (previous_valid_entry.total_bound_sources or 0)
                verified_source_delta = verified_sources - (previous_valid_entry.verified_sources or 0)
                paper_safe_source_delta = paper_safe_sources - (previous_valid_entry.paper_safe_sources or 0)
                simulation_only_source_delta = simulation_only_sources - (previous_valid_entry.simulation_only_sources or 0)
                score_delta = round(summary_score - previous_valid_entry.summary_score, 2)

                improving_signals = 0
                degrading_signals = 0

                if total_bound_source_delta > 0:
                    improving_signals += 1
                elif total_bound_source_delta < 0:
                    degrading_signals += 1

                if verified_source_delta > 0:
                    improving_signals += 1
                elif verified_source_delta < 0:
                    degrading_signals += 1

                if paper_safe_source_delta > 0:
                    improving_signals += 1
                elif paper_safe_source_delta < 0:
                    degrading_signals += 1

                previous_simulation_distance = abs(
                    (previous_valid_entry.simulation_only_sources or 0) - expected_simulation_only_sources
                )
                current_simulation_distance = abs(
                    simulation_only_sources - expected_simulation_only_sources
                )
                if current_simulation_distance < previous_simulation_distance:
                    improving_signals += 1
                elif current_simulation_distance > previous_simulation_distance:
                    degrading_signals += 1

                if normalization_mode_value != previous_valid_entry.normalization_mode:
                    normalization_mode_changes += 1
                    degrading_signals += 1

                if score_delta > 0.5:
                    improving_signals += 1
                elif score_delta < -0.5:
                    degrading_signals += 1

                if improving_signals == 0 and degrading_signals == 0:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = "Source observation summary remained stable compared with the previous saved snapshot."
                elif improving_signals > 0 and degrading_signals == 0:
                    drift_classification = "improving"
                    improving_snapshots += 1
                    diagnostic = "Source observation summary improved compared with the previous saved snapshot."
                elif degrading_signals > 0 and improving_signals == 0:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = "Source observation summary degraded compared with the previous saved snapshot."
                else:
                    drift_classification = "mixed"
                    mixed_snapshots += 1
                    diagnostic = "Source observation summary changed in mixed directions compared with the previous saved snapshot."

            current_entry = SnapshotSourceObservationSummaryDriftEntry(
                snapshot_id=snapshot_id,
                created_at=created_at,
                drift_classification=drift_classification,
                summary_score=summary_score,
                contract=contract_value,
                normalization_mode=normalization_mode_value,
                total_bound_sources=total_bound_sources,
                verified_sources=verified_sources,
                simulation_only_sources=simulation_only_sources,
                paper_safe_sources=paper_safe_sources,
                total_bound_source_delta=total_bound_source_delta,
                verified_source_delta=verified_source_delta,
                paper_safe_source_delta=paper_safe_source_delta,
                simulation_only_source_delta=simulation_only_source_delta,
                malformed_field_count=malformed_field_count,
                diagnostic=diagnostic,
            )
            entries.append(current_entry)
            previous_valid_entry = current_entry

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_summary_score = 0.0
            severity_score = 0
        else:
            average_summary_score = round(
                sum(entry.summary_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            if len(valid_entries) == 1:
                drift_classification = valid_entries[0].drift_classification
            else:
                first_score = valid_entries[0].summary_score
                latest_score = valid_entries[-1].summary_score
                entry_classes = {entry.drift_classification for entry in valid_entries}
                if entry_classes == {"stable"}:
                    drift_classification = "stable"
                elif (
                    latest_score > first_score
                    and "mixed" not in entry_classes
                    and valid_entries[-1].drift_classification in {"stable", "improving"}
                ):
                    drift_classification = "improving"
                elif (
                    latest_score < first_score
                    and "mixed" not in entry_classes
                    and valid_entries[-1].drift_classification in {"stable", "degrading"}
                ):
                    drift_classification = "degrading"
                else:
                    drift_classification = "mixed"
            severity_score = int(round(max(0.0, 100.0 - valid_entries[-1].summary_score)))

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation summary drift remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation summary drift degraded across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation summary drift improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation summary drift was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation summary drift had insufficient usable data.")

        if normalization_mode_changes > 0:
            diagnostics.append(
                f"Source observation summary normalization mode changed {normalization_mode_changes} time(s) across the saved snapshots."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source observation summary field issue(s) were detected during summary drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation summary drift analysis."
            )

        return SnapshotSourceObservationSummaryDrift(
            drift_classification=drift_classification,
            average_summary_score=average_summary_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            expected_total_bound_sources=expected_total_bound_sources,
            expected_verified_sources=expected_verified_sources,
            expected_simulation_only_sources=expected_simulation_only_sources,
            expected_paper_safe_sources=expected_paper_safe_sources,
            normalization_mode_changes=normalization_mode_changes,
            malformed_summary_count=malformed_summary_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_confidence_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationConfidenceDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation confidence drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation confidence drift analysis."
                )
            return SnapshotSourceObservationConfidenceDrift(
                drift_classification="insufficient_data",
                average_confidence_score=0.0,
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
                missing_confidence_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        def normalize_confidence_score(raw_value: object) -> float:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError("confidence must be numeric")
            numeric_value = float(raw_value)
            if 0.0 <= numeric_value <= 1.0:
                return round(numeric_value * 100.0, 2)
            if 0.0 <= numeric_value <= 100.0:
                return round(numeric_value, 2)
            raise ValueError("confidence must be between 0 and 1 or between 0 and 100")

        entries: list[SnapshotSourceObservationConfidenceDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        aggregate_degraded_source_ids: set[str] = set()
        aggregate_improved_source_ids: set[str] = set()
        aggregate_missing_confidence_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        previous_confidence_by_source: dict[str, float] | None = None
        previous_average_confidence_score: float | None = None

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
                    SnapshotSourceObservationConfidenceDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_confidence_score=0.0,
                        previous_average_confidence_score=previous_average_confidence_score,
                        confidence_delta_from_previous=None,
                        total_records=0,
                        valid_confidence_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_confidence_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source observation confidence drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            confidence_by_source: dict[str, float] = {}
            missing_confidence_source_ids: set[str] = set()
            degraded_source_ids: set[str] = set()
            improved_source_ids: set[str] = set()
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

                if "confidence" not in record or record.get("confidence") is None:
                    missing_confidence_source_ids.add(source_id)
                    continue

                try:
                    confidence_by_source[source_id] = normalize_confidence_score(record.get("confidence"))
                except Exception:
                    malformed_record_count += 1
                    continue

            valid_confidence_records = len(confidence_by_source)
            if valid_confidence_records == 0:
                insufficient_data_snapshots += 1
                aggregate_missing_confidence_source_ids.update(missing_confidence_source_ids)
                aggregate_malformed_record_count += malformed_record_count
                entries.append(
                    SnapshotSourceObservationConfidenceDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_confidence_score=0.0,
                        previous_average_confidence_score=previous_average_confidence_score,
                        confidence_delta_from_previous=None,
                        total_records=total_records,
                        valid_confidence_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_confidence_source_ids=tuple(sorted(missing_confidence_source_ids)),
                        malformed_record_count=malformed_record_count,
                        diagnostic="Source observation confidence drift had insufficient usable confidence metadata in this saved snapshot.",
                    )
                )
                continue

            average_confidence_score = round(
                sum(confidence_by_source.values()) / valid_confidence_records,
                2,
            )
            confidence_delta_from_previous: float | None = None

            if previous_confidence_by_source is None or previous_average_confidence_score is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = "Source observation confidence established the replay baseline."
            else:
                confidence_delta_from_previous = round(
                    average_confidence_score - previous_average_confidence_score,
                    2,
                )
                for source_id, confidence_score in confidence_by_source.items():
                    previous_score = previous_confidence_by_source.get(source_id)
                    if previous_score is None:
                        continue
                    if confidence_score > previous_score:
                        improved_source_ids.add(source_id)
                    elif confidence_score < previous_score:
                        degraded_source_ids.add(source_id)

                if degraded_source_ids and improved_source_ids:
                    drift_classification = "mixed"
                    mixed_snapshots += 1
                    diagnostic = (
                        "Source observation confidence drift was mixed because some sources improved while others deteriorated compared with the previous saved snapshot."
                    )
                elif degraded_source_ids:
                    drift_classification = "degrading"
                    degrading_snapshots += 1
                    diagnostic = (
                        "Source observation confidence drift deteriorated compared with the previous saved snapshot."
                    )
                elif improved_source_ids:
                    drift_classification = "improving"
                    improving_snapshots += 1
                    diagnostic = (
                        "Source observation confidence drift improved compared with the previous saved snapshot."
                    )
                else:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = (
                        "Source observation confidence remained stable compared with the previous saved snapshot."
                    )

            aggregate_degraded_source_ids.update(degraded_source_ids)
            aggregate_improved_source_ids.update(improved_source_ids)
            aggregate_missing_confidence_source_ids.update(missing_confidence_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceObservationConfidenceDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    average_confidence_score=average_confidence_score,
                    previous_average_confidence_score=previous_average_confidence_score,
                    confidence_delta_from_previous=confidence_delta_from_previous,
                    total_records=total_records,
                    valid_confidence_records=valid_confidence_records,
                    degraded_source_ids=tuple(sorted(degraded_source_ids)),
                    improved_source_ids=tuple(sorted(improved_source_ids)),
                    missing_confidence_source_ids=tuple(sorted(missing_confidence_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )
            previous_confidence_by_source = dict(confidence_by_source)
            previous_average_confidence_score = average_confidence_score

        snapshots_checked = len(entries)
        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_confidence_score = 0.0
            severity_score = 0
        else:
            average_confidence_score = round(
                sum(entry.average_confidence_score for entry in valid_entries) / len(valid_entries),
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
                        abs(entry.confidence_delta_from_previous or 0.0)
                        for entry in valid_entries
                    )
                )
            )

        if drift_classification == "stable":
            diagnostics.append(
                f"Source observation confidence remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source observation confidence deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source observation confidence improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source observation confidence drift was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source observation confidence drift had insufficient usable data.")

        if aggregate_missing_confidence_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_confidence_source_ids)} source ID(s) were missing persisted confidence metadata."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during confidence drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation confidence drift analysis."
            )

        return SnapshotSourceObservationConfidenceDrift(
            drift_classification=drift_classification,
            average_confidence_score=average_confidence_score,
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
            missing_confidence_source_ids=tuple(sorted(aggregate_missing_confidence_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostics_average_coverage_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsAverageCoverageDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics average-coverage drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics average-coverage drift analysis."
                )
            return SnapshotSourceDiagnosticsAverageCoverageDrift(
                drift_classification="insufficient_data",
                average_coverage_score=0.0,
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

        entries: list[SnapshotSourceDiagnosticsAverageCoverageDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_average_coverage_score: float | None = None
        previous_minimum_coverage_score: float | None = None

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
                    SnapshotSourceDiagnosticsAverageCoverageDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        average_coverage_score=0.0,
                        previous_average_coverage_score=previous_average_coverage_score,
                        coverage_score_delta=None,
                        minimum_coverage_score=0.0,
                        total_features=0,
                        ready_features=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics average-coverage drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            malformed_field_count = 0
            try:
                average_coverage_score = round(float(summary["average_coverage_score"]), 2)
            except Exception:
                average_coverage_score = 0.0
                malformed_field_count += 1
            try:
                minimum_coverage_score = round(float(summary["minimum_coverage_score"]), 2)
            except Exception:
                minimum_coverage_score = 0.0
                malformed_field_count += 1
            try:
                total_features = int(summary["total_features"])
            except Exception:
                total_features = 0
                malformed_field_count += 1
            try:
                ready_features = int(summary["ready_features"])
            except Exception:
                ready_features = 0
                malformed_field_count += 1

            coverage_score_delta: float | None = None
            if previous_average_coverage_score is not None:
                coverage_score_delta = round(
                    average_coverage_score - previous_average_coverage_score,
                    2,
                )

            if malformed_field_count > 0 or total_features <= 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics average-coverage drift could not be evaluated because persisted summary fields were malformed or incomplete."
                )
            elif previous_average_coverage_score is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics average-coverage baseline was established from persisted summary metadata."
                )
            elif coverage_score_delta is not None and coverage_score_delta < 0:
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics average coverage deteriorated compared with the previous saved snapshot."
                )
            elif coverage_score_delta is not None and coverage_score_delta > 0:
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics average coverage improved compared with the previous saved snapshot."
                )
            elif previous_minimum_coverage_score is not None and minimum_coverage_score != previous_minimum_coverage_score:
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics average coverage stayed flat, but the persisted minimum coverage floor changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics average coverage remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsAverageCoverageDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    average_coverage_score=average_coverage_score,
                    previous_average_coverage_score=previous_average_coverage_score,
                    coverage_score_delta=coverage_score_delta,
                    minimum_coverage_score=minimum_coverage_score,
                    total_features=total_features,
                    ready_features=ready_features,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0 and total_features > 0:
                previous_average_coverage_score = average_coverage_score
                previous_minimum_coverage_score = minimum_coverage_score

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_coverage_score = 0.0
            severity_score = 0
        else:
            average_coverage_score = round(
                sum(entry.average_coverage_score for entry in valid_entries) / len(valid_entries),
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
                    max(abs(entry.coverage_score_delta or 0.0) for entry in valid_entries)
                )
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics average coverage remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics average coverage deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics average coverage improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics average coverage was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics average-coverage drift had insufficient usable summary metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source diagnostics summary field issue(s) were detected during average-coverage drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics average-coverage drift analysis."
            )

        return SnapshotSourceDiagnosticsAverageCoverageDrift(
            drift_classification=drift_classification,
            average_coverage_score=average_coverage_score,
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

    def _build_source_diagnostics_ready_feature_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsReadyFeatureDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics ready-feature drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics ready-feature drift analysis."
                )
            return SnapshotSourceDiagnosticsReadyFeatureDrift(
                drift_classification="insufficient_data",
                average_ready_features=0.0,
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

        entries: list[SnapshotSourceDiagnosticsReadyFeatureDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        malformed_summary_count = 0
        previous_ready_features: int | None = None
        previous_total_missing_assets: int | None = None

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
                    SnapshotSourceDiagnosticsReadyFeatureDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        ready_features=0,
                        previous_ready_features=previous_ready_features,
                        ready_feature_delta=None,
                        total_features=0,
                        total_missing_assets=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics ready-feature drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            malformed_field_count = 0
            try:
                ready_features = int(summary["ready_features"])
            except Exception:
                ready_features = 0
                malformed_field_count += 1
            try:
                total_features = int(summary["total_features"])
            except Exception:
                total_features = 0
                malformed_field_count += 1
            try:
                total_missing_assets = int(summary["total_missing_assets"])
            except Exception:
                total_missing_assets = 0
                malformed_field_count += 1

            ready_feature_delta: int | None = None
            if previous_ready_features is not None:
                ready_feature_delta = ready_features - previous_ready_features

            if malformed_field_count > 0 or total_features <= 0:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source diagnostics ready-feature drift could not be evaluated because persisted summary fields were malformed or incomplete."
                )
            elif previous_ready_features is None:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics ready-feature baseline was established from persisted summary metadata."
                )
            elif ready_feature_delta is not None and ready_feature_delta < 0:
                drift_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source diagnostics ready-feature coverage deteriorated compared with the previous saved snapshot."
                )
            elif ready_feature_delta is not None and ready_feature_delta > 0:
                drift_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source diagnostics ready-feature coverage improved compared with the previous saved snapshot."
                )
            elif (
                previous_total_missing_assets is not None
                and total_missing_assets != previous_total_missing_assets
            ):
                drift_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source diagnostics ready-feature counts stayed flat, but persisted missing-asset pressure changed."
                )
            else:
                drift_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostics ready-feature coverage remained stable compared with the previous saved snapshot."
                )

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceDiagnosticsReadyFeatureDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    ready_features=ready_features,
                    previous_ready_features=previous_ready_features,
                    ready_feature_delta=ready_feature_delta,
                    total_features=total_features,
                    total_missing_assets=total_missing_assets,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

            if malformed_field_count == 0 and total_features > 0:
                previous_ready_features = ready_features
                previous_total_missing_assets = total_missing_assets

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_ready_features = 0.0
            severity_score = 0
        else:
            average_ready_features = round(
                sum(entry.ready_features for entry in valid_entries) / len(valid_entries),
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
                max(abs(entry.ready_feature_delta or 0) for entry in valid_entries)
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics ready-feature coverage remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source diagnostics ready-feature coverage deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source diagnostics ready-feature coverage improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source diagnostics ready-feature coverage was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics ready-feature drift had insufficient usable summary metadata."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source diagnostics summary field issue(s) were detected during ready-feature drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics ready-feature drift analysis."
            )

        return SnapshotSourceDiagnosticsReadyFeatureDrift(
            drift_classification=drift_classification,
            average_ready_features=average_ready_features,
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

__all__ = ["SnapshotReplaySourceQualityDriftSummaryMixin"]
