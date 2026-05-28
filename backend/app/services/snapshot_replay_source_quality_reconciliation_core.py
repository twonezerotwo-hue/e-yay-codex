from __future__ import annotations

from typing import Any

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotSourceDecisionUsageConsistency,
    SnapshotSourceDecisionUsageConsistencyEntry,
    SnapshotSourceObservationRecordSummaryReconciliation,
    SnapshotSourceObservationRecordSummaryReconciliationEntry,
    SnapshotVerifiedSourceCoverageReconciliation,
    SnapshotVerifiedSourceCoverageReconciliationEntry,
)
from app.services.snapshot_replay_source_common import (
    ALLOWED_DECISION_USAGES,
)

class SnapshotReplaySourceQualityReconciliationCoreMixin:
    def _build_source_decision_usage_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDecisionUsageConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source decision-usage consistency analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source decision-usage consistency analysis."
                )
            return SnapshotSourceDecisionUsageConsistency(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                aggregate_decision_usage_counts={},
                mismatched_source_ids=(),
                unsafe_source_ids=(),
                unknown_registry_source_ids=(),
                missing_decision_usage_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {
            entry.source_id: entry
            for entry in registry_entries
        }

        entries: list[SnapshotSourceDecisionUsageConsistencyEntry] = []
        aggregate_decision_usage_counts: Counter[str] = Counter()
        aggregate_mismatched_source_ids: set[str] = set()
        aggregate_unsafe_source_ids: set[str] = set()
        aggregate_unknown_registry_source_ids: set[str] = set()
        aggregate_missing_decision_usage_source_ids: set[str] = set()
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

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceDecisionUsageConsistencyEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        consistency_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        consistent_records=0,
                        decision_usage_counts={},
                        mismatched_source_ids=(),
                        unsafe_source_ids=(),
                        unknown_registry_source_ids=(),
                        missing_decision_usage_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source decision-usage consistency could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            consistent_records = 0
            malformed_record_count = 0
            decision_usage_counts: Counter[str] = Counter()
            mismatched_source_ids: set[str] = set()
            unsafe_source_ids: set[str] = set()
            unknown_registry_source_ids: set[str] = set()
            missing_decision_usage_source_ids: set[str] = set()

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                raw_decision_usage = record.get("decision_usage")
                if not isinstance(raw_decision_usage, str) or not raw_decision_usage.strip():
                    missing_decision_usage_source_ids.add(source_id)
                    continue
                decision_usage = raw_decision_usage.strip()
                if decision_usage not in ALLOWED_DECISION_USAGES:
                    malformed_record_count += 1
                    continue

                decision_usage_counts[decision_usage] += 1
                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unknown_registry_source_ids.add(source_id)
                elif decision_usage != registry_entry.decision_usage:
                    mismatched_source_ids.add(source_id)

                paper_safe = record.get("paper_safe")
                verified = record.get("verified")
                if paper_safe is not True:
                    unsafe_source_ids.add(source_id)
                if verified is False and decision_usage != "simulation_only":
                    unsafe_source_ids.add(source_id)

                if (
                    source_id not in mismatched_source_ids
                    and source_id not in unsafe_source_ids
                    and source_id not in unknown_registry_source_ids
                    and source_id not in missing_decision_usage_source_ids
                ):
                    consistent_records += 1

            consistency_percentage = round(
                (consistent_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Source decision-usage consistency encountered {malformed_record_count} malformed record(s)."
                )
            elif mismatched_source_ids or unsafe_source_ids:
                consistency_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = "Source decision-usage consistency was degraded by mismatched or unsafe source usage."
            elif unknown_registry_source_ids or missing_decision_usage_source_ids:
                consistency_classification = "partial"
                partial_snapshots += 1
                diagnostic = "Source decision-usage consistency was partial because some source bindings or usage values were incomplete."
            else:
                consistency_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = "All source observation records preserved consistent decision-usage metadata."

            aggregate_decision_usage_counts.update(decision_usage_counts)
            aggregate_mismatched_source_ids.update(mismatched_source_ids)
            aggregate_unsafe_source_ids.update(unsafe_source_ids)
            aggregate_unknown_registry_source_ids.update(unknown_registry_source_ids)
            aggregate_missing_decision_usage_source_ids.update(missing_decision_usage_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceDecisionUsageConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    consistent_records=consistent_records,
                    decision_usage_counts=dict(sorted(decision_usage_counts.items())),
                    mismatched_source_ids=tuple(sorted(mismatched_source_ids)),
                    unsafe_source_ids=tuple(sorted(unsafe_source_ids)),
                    unknown_registry_source_ids=tuple(sorted(unknown_registry_source_ids)),
                    missing_decision_usage_source_ids=tuple(sorted(missing_decision_usage_source_ids)),
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
            f"Source decision-usage consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_mismatched_source_ids:
            diagnostics.append(
                f"{len(aggregate_mismatched_source_ids)} source ID(s) had decision-usage mismatches against the current source registry."
            )
        if aggregate_unsafe_source_ids:
            diagnostics.append(
                f"{len(aggregate_unsafe_source_ids)} source ID(s) violated paper-safe decision-usage expectations."
            )
        if aggregate_unknown_registry_source_ids:
            diagnostics.append(
                f"{len(aggregate_unknown_registry_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_missing_decision_usage_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_decision_usage_source_ids)} source ID(s) were missing usable decision-usage metadata."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during decision-usage consistency analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source decision-usage consistency analysis."
            )

        return SnapshotSourceDecisionUsageConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            aggregate_decision_usage_counts=dict(sorted(aggregate_decision_usage_counts.items())),
            mismatched_source_ids=tuple(sorted(aggregate_mismatched_source_ids)),
            unsafe_source_ids=tuple(sorted(aggregate_unsafe_source_ids)),
            unknown_registry_source_ids=tuple(sorted(aggregate_unknown_registry_source_ids)),
            missing_decision_usage_source_ids=tuple(sorted(aggregate_missing_decision_usage_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_observation_record_summary_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceObservationRecordSummaryReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source observation record/summary reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source observation record/summary reconciliation analysis."
                )
            return SnapshotSourceObservationRecordSummaryReconciliation(
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
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceObservationRecordSummaryReconciliationEntry] = []
        aggregate_missing_fields: set[str] = set()
        aggregate_mismatched_fields: set[str] = set()
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

            source_observation_records = snapshot_payload.get("source_observation_records")
            summary = snapshot_payload.get("source_observation_summary")
            missing_fields: set[str] = set()
            mismatched_fields: set[str] = set()
            malformed_record_count = 0

            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceObservationRecordSummaryReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        record_total_bound_sources=0,
                        summary_total_bound_sources=None,
                        record_verified_sources=0,
                        summary_verified_sources=None,
                        record_simulation_only_sources=0,
                        summary_simulation_only_sources=None,
                        record_paper_safe_sources=0,
                        summary_paper_safe_sources=None,
                        missing_fields=("source_observation_records",),
                        mismatched_fields=(),
                        malformed_record_count=1,
                        diagnostic=(
                            "Source observation record/summary reconciliation could not be evaluated because source observation records were missing or malformed."
                        ),
                    )
                )
                aggregate_missing_fields.add("source_observation_records")
                continue

            record_total_bound_sources = len(source_observation_records)
            record_verified_sources = 0
            record_simulation_only_sources = 0
            record_paper_safe_sources = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_verified = record.get("verified")
                if isinstance(raw_verified, bool):
                    if raw_verified:
                        record_verified_sources += 1
                else:
                    malformed_record_count += 1

                raw_decision_usage = record.get("decision_usage")
                if isinstance(raw_decision_usage, str) and raw_decision_usage.strip():
                    if raw_decision_usage.strip() == "simulation_only":
                        record_simulation_only_sources += 1
                else:
                    malformed_record_count += 1

                raw_paper_safe = record.get("paper_safe")
                if isinstance(raw_paper_safe, bool):
                    if raw_paper_safe:
                        record_paper_safe_sources += 1
                else:
                    malformed_record_count += 1

            def parse_summary_count(field_name: str) -> int | None:
                value = summary.get(field_name) if isinstance(summary, Mapping) else None
                if value is None:
                    missing_fields.add(field_name)
                    return None
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    missing_fields.add(field_name)
                    return None
                return int(value)

            if not isinstance(summary, Mapping):
                missing_fields.update(
                    {
                        "source_observation_summary",
                        "total_bound_sources",
                        "verified_sources",
                        "simulation_only_sources",
                        "paper_safe_sources",
                    }
                )
                summary_total_bound_sources = None
                summary_verified_sources = None
                summary_simulation_only_sources = None
                summary_paper_safe_sources = None
            else:
                summary_total_bound_sources = parse_summary_count("total_bound_sources")
                summary_verified_sources = parse_summary_count("verified_sources")
                summary_simulation_only_sources = parse_summary_count("simulation_only_sources")
                summary_paper_safe_sources = parse_summary_count("paper_safe_sources")

            if (
                summary_total_bound_sources is not None
                and summary_total_bound_sources != record_total_bound_sources
            ):
                mismatched_fields.add("total_bound_sources")
            if (
                summary_verified_sources is not None
                and summary_verified_sources != record_verified_sources
            ):
                mismatched_fields.add("verified_sources")
            if (
                summary_simulation_only_sources is not None
                and summary_simulation_only_sources != record_simulation_only_sources
            ):
                mismatched_fields.add("simulation_only_sources")
            if (
                summary_paper_safe_sources is not None
                and summary_paper_safe_sources != record_paper_safe_sources
            ):
                mismatched_fields.add("paper_safe_sources")

            consistency_percentage = round(
                max(
                    0.0,
                    100.0
                    - len(missing_fields) * 15
                    - len(mismatched_fields) * 25
                    - malformed_record_count * 20,
                ),
                2,
            )

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Source observation record/summary reconciliation was invalid because one or more persisted source records were malformed."
                )
            elif mismatched_fields:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source observation record/summary reconciliation was degraded because persisted summary counts diverged from the source observation records."
                )
            elif missing_fields:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Source observation record/summary reconciliation was partial because one or more persisted summary fields were missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted source observation summary counts remained aligned with the underlying source observation records."
                )

            aggregate_missing_fields.update(missing_fields)
            aggregate_mismatched_fields.update(mismatched_fields)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceObservationRecordSummaryReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    record_total_bound_sources=record_total_bound_sources,
                    summary_total_bound_sources=summary_total_bound_sources,
                    record_verified_sources=record_verified_sources,
                    summary_verified_sources=summary_verified_sources,
                    record_simulation_only_sources=record_simulation_only_sources,
                    summary_simulation_only_sources=summary_simulation_only_sources,
                    record_paper_safe_sources=record_paper_safe_sources,
                    summary_paper_safe_sources=summary_paper_safe_sources,
                    missing_fields=tuple(sorted(missing_fields)),
                    mismatched_fields=tuple(sorted(mismatched_fields)),
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
            f"Source observation record/summary reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_fields:
            diagnostics.append(
                f"{len(aggregate_missing_fields)} persisted summary field(s) were missing during record/summary reconciliation analysis."
            )
        if aggregate_mismatched_fields:
            diagnostics.append(
                f"{len(aggregate_mismatched_fields)} persisted summary count field(s) diverged from the underlying source observation records."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during record/summary reconciliation analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source observation record/summary reconciliation analysis."
            )

        return SnapshotSourceObservationRecordSummaryReconciliation(
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
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_verified_source_coverage_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotVerifiedSourceCoverageReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for verified-source coverage reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during verified-source coverage reconciliation analysis."
                )
            return SnapshotVerifiedSourceCoverageReconciliation(
                consistency_classification="invalid",
                average_coverage_percentage=0.0,
                expected_verified_source_count=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_verified_source_ids=(),
                unexpected_verified_source_ids=(),
                malformed_record_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        from registry import build_source_registry_entries
        from registry import load_source_registry

        source_registry = load_source_registry()
        registry_entries = build_source_registry_entries(source_registry)
        expected_verified_source_ids = tuple(
            sorted(
                entry.source_id
                for entry in registry_entries
                if entry.active and entry.verified
            )
        )
        expected_verified_source_id_set = set(expected_verified_source_ids)

        entries: list[SnapshotVerifiedSourceCoverageReconciliationEntry] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_verified_source_ids: set[str] = set()
        aggregate_unexpected_verified_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get("source_observation_records")
            if not isinstance(source_observation_records, list) or not source_observation_records:
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotVerifiedSourceCoverageReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        coverage_percentage=0.0,
                        expected_verified_source_count=len(expected_verified_source_ids),
                        observed_verified_source_count=0,
                        matched_verified_source_count=0,
                        missing_verified_source_ids=expected_verified_source_ids,
                        unexpected_verified_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Verified-source coverage reconciliation could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            observed_verified_source_ids: set[str] = set()
            malformed_record_count = 0
            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                verified_flag = record.get("verified")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                if not isinstance(verified_flag, bool):
                    malformed_record_count += 1
                    continue
                if verified_flag:
                    observed_verified_source_ids.add(raw_source_id.strip())

            matched_verified_source_ids = expected_verified_source_id_set & observed_verified_source_ids
            missing_verified_source_ids = expected_verified_source_id_set - observed_verified_source_ids
            unexpected_verified_source_ids = observed_verified_source_ids - expected_verified_source_id_set
            coverage_percentage = round(
                (len(matched_verified_source_ids) / max(len(expected_verified_source_ids), 1)) * 100.0,
                2,
            )

            if malformed_record_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Verified-source coverage reconciliation was invalid because one or more persisted source observation records were malformed."
                )
            elif not missing_verified_source_ids and not unexpected_verified_source_ids:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted verified-source coverage matched the current active verified source registry set."
                )
            elif coverage_percentage >= 70.0 and not unexpected_verified_source_ids:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Persisted verified-source coverage was partial because one or more expected verified sources were missing."
                )
            else:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted verified-source coverage was degraded because expected verified sources were missing or unexpected verified sources appeared."
                )

            aggregate_missing_verified_source_ids.update(missing_verified_source_ids)
            aggregate_unexpected_verified_source_ids.update(unexpected_verified_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotVerifiedSourceCoverageReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    coverage_percentage=coverage_percentage,
                    expected_verified_source_count=len(expected_verified_source_ids),
                    observed_verified_source_count=len(observed_verified_source_ids),
                    matched_verified_source_count=len(matched_verified_source_ids),
                    missing_verified_source_ids=tuple(sorted(missing_verified_source_ids)),
                    unexpected_verified_source_ids=tuple(sorted(unexpected_verified_source_ids)),
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

        average_coverage_percentage = round(
            sum(entry.coverage_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Verified-source coverage reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_verified_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_verified_source_ids)} expected verified source ID(s) were missing from persisted verified coverage."
            )
        if aggregate_unexpected_verified_source_ids:
            diagnostics.append(
                f"{len(aggregate_unexpected_verified_source_ids)} persisted source ID(s) were marked verified but are not in the current active verified registry set."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record issue(s) were detected during verified-source coverage reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during verified-source coverage reconciliation analysis."
            )

        return SnapshotVerifiedSourceCoverageReconciliation(
            consistency_classification=consistency_classification,
            average_coverage_percentage=average_coverage_percentage,
            expected_verified_source_count=len(expected_verified_source_ids),
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_verified_source_ids=tuple(sorted(aggregate_missing_verified_source_ids)),
            unexpected_verified_source_ids=tuple(sorted(aggregate_unexpected_verified_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = ["SnapshotReplaySourceQualityReconciliationCoreMixin"]
