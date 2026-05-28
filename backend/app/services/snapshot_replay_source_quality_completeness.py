from __future__ import annotations

from typing import Any

from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime

from app.services.snapshot_replay_models import (
    SnapshotRawPayloadReferenceCompleteness,
    SnapshotRawPayloadReferenceCompletenessEntry,
    SnapshotSourceRecordCompleteness,
    SnapshotSourceRecordCompletenessEntry,
)


class SnapshotReplaySourceQualityCompletenessMixin:
    def _build_raw_payload_reference_completeness(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotRawPayloadReferenceCompleteness:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for raw payload reference completeness analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during raw payload reference analysis."
                )
            return SnapshotRawPayloadReferenceCompleteness(
                completeness_classification="invalid",
                average_completeness_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                complete_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_reference_assets=(),
                empty_reference_assets=(),
                malformed_reference_assets=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotRawPayloadReferenceCompletenessEntry] = []
        aggregate_missing_assets: set[str] = set()
        aggregate_empty_assets: set[str] = set()
        aggregate_malformed_assets: set[str] = set()
        complete_snapshots = 0
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

            serialized_snapshots = snapshot_payload.get("snapshots")
            if not isinstance(serialized_snapshots, list) or not serialized_snapshots:
                invalid_snapshots += 1
                entries.append(
                    SnapshotRawPayloadReferenceCompletenessEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        completeness_classification="invalid",
                        completeness_percentage=0.0,
                        total_records=0,
                        complete_records=0,
                        partial_reference_assets=(),
                        missing_reference_assets=(),
                        empty_reference_assets=(),
                        malformed_reference_assets=("SNAPSHOT_RECORDS",),
                        diagnostic="Raw payload reference completeness could not be evaluated because snapshot records were missing or malformed.",
                    )
                )
                aggregate_malformed_assets.add("SNAPSHOT_RECORDS")
                continue

            total_records = 0
            complete_records = 0
            partial_reference_assets: set[str] = set()
            missing_reference_assets: set[str] = set()
            empty_reference_assets: set[str] = set()
            malformed_reference_assets: set[str] = set()

            for record_index, snapshot_record in enumerate(serialized_snapshots):
                total_records += 1
                if not isinstance(snapshot_record, Mapping):
                    malformed_reference_assets.add(f"UNKNOWN_RECORD_{record_index}")
                    continue

                raw_asset_symbol = snapshot_record.get("asset_symbol")
                if isinstance(raw_asset_symbol, str) and raw_asset_symbol.strip():
                    asset_symbol = raw_asset_symbol.strip()
                else:
                    asset_symbol = f"UNKNOWN_ASSET_{record_index}"

                if "raw_payload_ref" not in snapshot_record or snapshot_record.get("raw_payload_ref") is None:
                    missing_reference_assets.add(asset_symbol)
                    continue

                raw_payload_ref = snapshot_record.get("raw_payload_ref")
                if not isinstance(raw_payload_ref, str):
                    malformed_reference_assets.add(asset_symbol)
                    continue

                normalized_payload_ref = raw_payload_ref.strip()
                if not normalized_payload_ref:
                    empty_reference_assets.add(asset_symbol)
                    continue

                scheme, separator, remainder = normalized_payload_ref.partition("://")
                if not separator:
                    malformed_reference_assets.add(asset_symbol)
                    continue
                if not scheme.strip():
                    malformed_reference_assets.add(asset_symbol)
                    continue
                if not remainder.strip():
                    partial_reference_assets.add(asset_symbol)
                    continue

                complete_records += 1

            completeness_percentage = round(
                (complete_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if malformed_reference_assets:
                completeness_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Malformed raw payload references were detected for {len(malformed_reference_assets)} asset record(s)."
                )
            elif complete_records == total_records:
                completeness_classification = "complete"
                complete_snapshots += 1
                diagnostic = "All snapshot records preserved a usable raw payload reference."
            elif completeness_percentage >= 70.0:
                completeness_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    f"Raw payload references were partially complete for {complete_records} of {total_records} snapshot record(s)."
                )
            else:
                completeness_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    f"Raw payload references were degraded for {total_records - complete_records} of {total_records} snapshot record(s)."
                )

            aggregate_missing_assets.update(missing_reference_assets)
            aggregate_empty_assets.update(empty_reference_assets)
            aggregate_malformed_assets.update(malformed_reference_assets)
            entries.append(
                SnapshotRawPayloadReferenceCompletenessEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    completeness_classification=completeness_classification,
                    completeness_percentage=completeness_percentage,
                    total_records=total_records,
                    complete_records=complete_records,
                    partial_reference_assets=tuple(sorted(partial_reference_assets)),
                    missing_reference_assets=tuple(sorted(missing_reference_assets)),
                    empty_reference_assets=tuple(sorted(empty_reference_assets)),
                    malformed_reference_assets=tuple(sorted(malformed_reference_assets)),
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            completeness_classification = "invalid"
        elif degraded_snapshots > 0:
            completeness_classification = "degraded"
        elif partial_snapshots > 0:
            completeness_classification = "partial"
        else:
            completeness_classification = "complete"

        average_completeness_percentage = round(
            sum(entry.completeness_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Raw payload reference completeness is {completeness_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_assets:
            diagnostics.append(
                f"{len(aggregate_missing_assets)} asset symbol(s) were missing raw payload references."
            )
        if aggregate_empty_assets:
            diagnostics.append(
                f"{len(aggregate_empty_assets)} asset symbol(s) contained empty raw payload references."
            )
        if aggregate_malformed_assets:
            diagnostics.append(
                f"{len(aggregate_malformed_assets)} asset symbol(s) contained malformed raw payload references."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during raw payload reference analysis."
            )

        return SnapshotRawPayloadReferenceCompleteness(
            completeness_classification=completeness_classification,
            average_completeness_percentage=average_completeness_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            complete_snapshots=complete_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_reference_assets=tuple(sorted(aggregate_missing_assets)),
            empty_reference_assets=tuple(sorted(aggregate_empty_assets)),
            malformed_reference_assets=tuple(sorted(aggregate_malformed_assets)),
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_source_record_completeness(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceRecordCompleteness:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for source record completeness analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source record completeness analysis."
                )
            return SnapshotSourceRecordCompleteness(
                completeness_classification="invalid",
                average_completeness_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                complete_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                aggregate_missing_field_counts={},
                malformed_record_count=0,
                missing_field_diagnostics=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        core_required_fields = (
            "source_id",
            "asset_symbol",
            "registry_provider",
            "observed_at",
            "available_at",
            "stored_at",
            "mapped_at",
            "verified",
            "decision_usage",
            "paper_safe",
        )
        timestamp_fields = {"observed_at", "available_at", "stored_at", "mapped_at"}
        optional_metadata_fields = (
            "value",
            "confidence",
            "freshness_seconds",
            "freshness_status",
        )

        entries: list[SnapshotSourceRecordCompletenessEntry] = []
        aggregate_missing_field_counts: Counter[str] = Counter()
        aggregate_missing_field_diagnostics: set[str] = set()
        aggregate_malformed_record_count = 0
        complete_snapshots = 0
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
                    SnapshotSourceRecordCompletenessEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        completeness_classification="invalid",
                        completeness_percentage=0.0,
                        total_records=0,
                        complete_records=0,
                        missing_field_counts={},
                        missing_field_diagnostics=("source_observation_records:missing_or_malformed",),
                        malformed_record_count=1,
                        diagnostic="Source observation records were missing or malformed in this saved snapshot.",
                    )
                )
                aggregate_missing_field_diagnostics.add("source_observation_records:missing_or_malformed")
                continue

            expected_optional_fields = tuple(
                field_name
                for field_name in optional_metadata_fields
                if any(
                    isinstance(record, Mapping) and field_name in record
                    for record in source_observation_records
                )
            )
            required_fields = core_required_fields + expected_optional_fields
            missing_field_counts: Counter[str] = Counter()
            missing_field_diagnostics: list[str] = []
            complete_records = 0
            malformed_record_count = 0

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    missing_field_diagnostics.append(f"record_{record_index}:malformed_record")
                    continue

                record_label = str(
                    record.get("asset_symbol")
                    or record.get("source_id")
                    or f"record_{record_index}"
                )
                record_has_issue = False

                for field_name in required_fields:
                    if field_name not in record or record[field_name] is None:
                        missing_field_counts[field_name] += 1
                        missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                        record_has_issue = True
                        continue

                    value = record[field_name]
                    if field_name in {"source_id", "asset_symbol", "registry_provider", "decision_usage", "freshness_status"}:
                        if not isinstance(value, str) or not value.strip():
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name in timestamp_fields:
                        try:
                            self._parse_datetime(value)
                        except Exception:
                            malformed_record_count += 1
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:malformed")
                            record_has_issue = True
                    elif field_name in {"verified", "paper_safe"}:
                        if not isinstance(value, bool):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name == "value":
                        if not isinstance(value, (int, float)):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name == "confidence":
                        if not isinstance(value, (int, float)):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True
                    elif field_name == "freshness_seconds":
                        if not isinstance(value, int):
                            missing_field_counts[field_name] += 1
                            missing_field_diagnostics.append(f"{record_label}:{field_name}:missing")
                            record_has_issue = True

                if not record_has_issue:
                    complete_records += 1

            total_records = len(source_observation_records)
            completeness_percentage = round(
                (complete_records / total_records) * 100,
                2,
            ) if total_records else 0.0

            if malformed_record_count > 0:
                completeness_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Source observation records contained {malformed_record_count} malformed record or timestamp issue(s)."
                )
            elif complete_records == total_records:
                completeness_classification = "complete"
                complete_snapshots += 1
                diagnostic = "All source observation records preserved the required paper-safe fields."
            elif completeness_percentage >= 70.0:
                completeness_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    f"Source observation records were partially complete for {complete_records} of {total_records} record(s)."
                )
            else:
                completeness_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    f"Source observation records were degraded for {total_records - complete_records} of {total_records} record(s)."
                )

            aggregate_missing_field_counts.update(missing_field_counts)
            aggregate_missing_field_diagnostics.update(missing_field_diagnostics)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceRecordCompletenessEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    completeness_classification=completeness_classification,
                    completeness_percentage=completeness_percentage,
                    total_records=total_records,
                    complete_records=complete_records,
                    missing_field_counts=dict(sorted(missing_field_counts.items())),
                    missing_field_diagnostics=tuple(sorted(missing_field_diagnostics)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if invalid_snapshots > 0:
            completeness_classification = "invalid"
        elif degraded_snapshots > 0:
            completeness_classification = "degraded"
        elif partial_snapshots > 0:
            completeness_classification = "partial"
        else:
            completeness_classification = "complete"

        average_completeness_percentage = round(
            sum(entry.completeness_percentage for entry in entries) / snapshots_checked,
            2,
        ) if snapshots_checked else 0.0

        diagnostics.append(
            f"Source record completeness is {completeness_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_field_counts:
            diagnostics.append(
                f"Missing-field diagnostics were raised for {sum(aggregate_missing_field_counts.values())} source record field(s)."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source record issue(s) were detected."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source record completeness analysis."
            )

        return SnapshotSourceRecordCompleteness(
            completeness_classification=completeness_classification,
            average_completeness_percentage=average_completeness_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            complete_snapshots=complete_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            aggregate_missing_field_counts=dict(sorted(aggregate_missing_field_counts.items())),
            malformed_record_count=aggregate_malformed_record_count,
            missing_field_diagnostics=tuple(sorted(aggregate_missing_field_diagnostics)),
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
