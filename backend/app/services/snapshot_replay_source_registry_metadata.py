from __future__ import annotations

from collections import Counter
from collections import defaultdict
import re

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    RollingBacktestDiagnostics,
    SnapshotReplayContractMetadataNormalizationConsistency,
    SnapshotReplayContractMetadataNormalizationConsistencyEntry,
    SnapshotReplaySourceDiagnosticMetadataCompletenessDrift,
    SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry,
)
from app.services.snapshot_replay_source_common import Any, Mapping, UTC, datetime


_DIAGNOSTIC_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DIAGNOSTIC_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_DIAGNOSTIC_GROUP_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_SERVICE_BUILDER_PATTERN = re.compile(r"^build_[a-z0-9]+(?:_[a-z0-9]+)*$")
_SERIALIZER_KEY_PATTERN = re.compile(r"^_serialize_[a-z0-9]+(?:_[a-z0-9]+)*$")


class SnapshotReplaySourceRegistryMetadataMixin:
    def _build_contract_metadata_normalization_consistency(
        self,
    ) -> SnapshotReplayContractMetadataNormalizationConsistency:
        service_slugs = tuple(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS)
        api_route_slugs = tuple(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS)
        serializer_slugs = tuple(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS)
        rolling_bundle_slugs = tuple(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS
        )
        rolling_serializer_slugs = tuple(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS
        )
        group_by_slug = dict(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_GROUP_BY_SLUG)
        rolling_bundle_field_names = frozenset(
            RollingBacktestDiagnostics.__annotations__.keys()
        )

        registered_slugs = tuple(
            sorted(
                set(group_by_slug.keys())
                | set(service_slugs)
                | set(api_route_slugs)
                | set(serializer_slugs)
                | set(rolling_bundle_slugs)
                | set(rolling_serializer_slugs)
            )
        )

        if not registered_slugs:
            return SnapshotReplayContractMetadataNormalizationConsistency(
                consistency_classification="insufficient_data",
                completeness_percentage=0.0,
                total_diagnostics_registered=0,
                complete_metadata_count=0,
                partial_metadata_count=0,
                degraded_metadata_count=0,
                missing_metadata_field_count=0,
                invalid_metadata_field_count=0,
                duplicate_metadata_record_count=0,
                conflicting_metadata_record_count=0,
                missing_group_diagnostic_keys=(),
                invalid_group_diagnostic_keys=(),
                invalid_group_names=(),
                invalid_diagnostic_slugs=(),
                invalid_diagnostic_keys=(),
                missing_service_builder_keys=(),
                invalid_service_builder_keys=(),
                missing_api_route_keys=(),
                invalid_api_route_keys=(),
                missing_serializer_keys=(),
                invalid_serializer_keys=(),
                missing_rolling_bundle_keys=(),
                invalid_rolling_bundle_keys=(),
                missing_rolling_serializer_keys=(),
                invalid_rolling_serializer_keys=(),
                duplicate_metadata_records=(),
                conflicting_metadata_records=(),
                entries=(),
                diagnostics=(
                    "No source diagnostic contract metadata entries were registered for metadata completeness analysis.",
                ),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        service_slug_set = set(service_slugs)
        api_route_slug_set = set(api_route_slugs)
        serializer_slug_set = set(serializer_slugs)
        rolling_bundle_slug_set = set(rolling_bundle_slugs)
        rolling_serializer_slug_set = set(rolling_serializer_slugs)

        duplicate_fields_by_slug: dict[str, set[str]] = defaultdict(set)
        duplicate_metadata_records: set[str] = set()

        for slug, count in Counter(service_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("service_builder_key")
                duplicate_metadata_records.add(
                    "service_builder_key:"
                    + source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                        slug
                    )
                )
        for slug, count in Counter(api_route_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("api_route_key")
                duplicate_metadata_records.add(
                    "api_route_key:"
                    + source_diagnostic_contracts.snapshot_replay_source_diagnostic_route_path(
                        slug
                    )
                )
        for slug, count in Counter(serializer_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("serializer_key")
                duplicate_metadata_records.add(
                    "serializer_key:"
                    + source_diagnostic_contracts.snapshot_replay_source_diagnostic_serializer_name(
                        slug
                    )
                )
        for slug, count in Counter(rolling_bundle_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("rolling_bundle_key")
                duplicate_metadata_records.add(
                    "rolling_bundle_key:"
                    + source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_field_name(
                        slug
                    )
                )
        for slug, count in Counter(rolling_serializer_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("rolling_serializer_key")
                duplicate_metadata_records.add(
                    "rolling_serializer_key:"
                    + source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_serializer_field_name(
                        slug
                    )
                )

        conflicting_fields_by_slug: dict[str, set[str]] = defaultdict(set)
        conflicting_metadata_records: set[str] = set()

        def record_conflicts(
            field_name: str,
            values_by_slug: Mapping[str, str],
        ) -> None:
            value_to_slugs: dict[str, set[str]] = defaultdict(set)
            for slug, value in values_by_slug.items():
                value_to_slugs[value].add(slug)
            for value, slugs in value_to_slugs.items():
                if len(slugs) > 1:
                    for slug in slugs:
                        conflicting_fields_by_slug[slug].add(field_name)
                    conflicting_metadata_records.add(
                        f"{field_name}:{value}"
                    )

        record_conflicts(
            "diagnostic_key",
            {
                slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_key(
                    slug
                )
                for slug in registered_slugs
            },
        )
        record_conflicts(
            "service_builder_key",
            {
                slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                    slug
                )
                for slug in service_slug_set
            },
        )
        record_conflicts(
            "api_route_key",
            {
                slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_route_path(
                    slug
                )
                for slug in api_route_slug_set
            },
        )
        record_conflicts(
            "serializer_key",
            {
                slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_serializer_name(
                    slug
                )
                for slug in serializer_slug_set
            },
        )
        record_conflicts(
            "rolling_bundle_key",
            {
                slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_field_name(
                    slug
                )
                for slug in rolling_bundle_slug_set
            },
        )
        record_conflicts(
            "rolling_serializer_key",
            {
                slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_serializer_field_name(
                    slug
                )
                for slug in rolling_serializer_slug_set
            },
        )

        missing_group_diagnostic_keys: list[str] = []
        invalid_group_diagnostic_keys: list[str] = []
        invalid_group_names: list[str] = []
        invalid_diagnostic_slugs: list[str] = []
        invalid_diagnostic_keys: list[str] = []
        missing_service_builder_keys: list[str] = []
        invalid_service_builder_keys: list[str] = []
        missing_api_route_keys: list[str] = []
        invalid_api_route_keys: list[str] = []
        missing_serializer_keys: list[str] = []
        invalid_serializer_keys: list[str] = []
        missing_rolling_bundle_keys: list[str] = []
        invalid_rolling_bundle_keys: list[str] = []
        missing_rolling_serializer_keys: list[str] = []
        invalid_rolling_serializer_keys: list[str] = []

        entries: list[SnapshotReplayContractMetadataNormalizationConsistencyEntry] = []
        complete_metadata_count = 0
        partial_metadata_count = 0
        degraded_metadata_count = 0

        for slug in registered_slugs:
            diagnostic_key = source_diagnostic_contracts.snapshot_replay_source_diagnostic_key(
                slug
            )
            diagnostic_group = source_diagnostic_contracts.snapshot_replay_source_diagnostic_group(
                slug
            )
            service_builder_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                    slug
                )
            )
            api_route_path = source_diagnostic_contracts.snapshot_replay_source_diagnostic_route_path(
                slug
            )
            serializer_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_serializer_name(
                    slug
                )
            )
            rolling_bundle_field_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_field_name(
                    slug
                )
            )
            rolling_serializer_field_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_serializer_field_name(
                    slug
                )
            )

            slug_is_valid = bool(_DIAGNOSTIC_SLUG_PATTERN.fullmatch(slug))
            diagnostic_key_is_valid = bool(
                _DIAGNOSTIC_KEY_PATTERN.fullmatch(diagnostic_key)
            )
            contract_group_present = slug in group_by_slug
            contract_group_is_valid = contract_group_present and bool(
                _DIAGNOSTIC_GROUP_PATTERN.fullmatch(diagnostic_group)
            )

            service_builder_key_present = slug in service_slug_set and callable(
                getattr(self, service_builder_name, None)
            )
            service_builder_key_is_valid = (
                slug in service_slug_set
                and bool(_SERVICE_BUILDER_PATTERN.fullmatch(service_builder_name))
                and callable(getattr(self, service_builder_name, None))
            )

            api_route_key_present = slug in api_route_slug_set
            api_route_key_is_valid = (
                slug in api_route_slug_set
                and slug_is_valid
                and api_route_path
                == source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_ROUTE_PREFIX
                + slug
            )

            serializer_key_present = slug in serializer_slug_set
            serializer_key_is_valid = slug in serializer_slug_set and bool(
                _SERIALIZER_KEY_PATTERN.fullmatch(serializer_name)
            )

            rolling_bundle_key_present = slug in rolling_bundle_slug_set and (
                rolling_bundle_field_name in rolling_bundle_field_names
            )
            rolling_bundle_key_is_valid = (
                slug in rolling_bundle_slug_set
                and bool(_DIAGNOSTIC_KEY_PATTERN.fullmatch(rolling_bundle_field_name))
                and rolling_bundle_field_name in rolling_bundle_field_names
            )

            rolling_serializer_key_present = slug in rolling_serializer_slug_set
            rolling_serializer_key_is_valid = slug in rolling_serializer_slug_set and bool(
                _DIAGNOSTIC_KEY_PATTERN.fullmatch(rolling_serializer_field_name)
            )

            missing_metadata_fields: list[str] = []
            invalid_metadata_fields: list[str] = []
            duplicate_metadata_fields: list[str] = sorted(
                duplicate_fields_by_slug.get(slug, set())
            )
            conflicting_metadata_fields: list[str] = sorted(
                conflicting_fields_by_slug.get(slug, set())
            )

            if not slug_is_valid:
                invalid_metadata_fields.append("diagnostic_slug")
                invalid_diagnostic_slugs.append(slug)

            if not diagnostic_key_is_valid:
                invalid_metadata_fields.append("diagnostic_key")
                invalid_diagnostic_keys.append(diagnostic_key)

            if not contract_group_present:
                missing_metadata_fields.append("contract_group")
                missing_group_diagnostic_keys.append(diagnostic_key)
            elif not contract_group_is_valid:
                invalid_metadata_fields.append("contract_group")
                invalid_group_diagnostic_keys.append(diagnostic_key)
                invalid_group_names.append(diagnostic_group)

            if slug not in service_slug_set:
                missing_metadata_fields.append("service_builder_key")
                missing_service_builder_keys.append(service_builder_name)
            elif not service_builder_key_is_valid:
                invalid_metadata_fields.append("service_builder_key")
                invalid_service_builder_keys.append(service_builder_name)

            if slug not in api_route_slug_set:
                missing_metadata_fields.append("api_route_key")
                missing_api_route_keys.append(api_route_path)
            elif not api_route_key_is_valid:
                invalid_metadata_fields.append("api_route_key")
                invalid_api_route_keys.append(api_route_path)

            if slug not in serializer_slug_set:
                missing_metadata_fields.append("serializer_key")
                missing_serializer_keys.append(serializer_name)
            elif not serializer_key_is_valid:
                invalid_metadata_fields.append("serializer_key")
                invalid_serializer_keys.append(serializer_name)

            if slug not in rolling_bundle_slug_set:
                missing_metadata_fields.append("rolling_bundle_key")
                missing_rolling_bundle_keys.append(rolling_bundle_field_name)
            elif not rolling_bundle_key_is_valid:
                invalid_metadata_fields.append("rolling_bundle_key")
                invalid_rolling_bundle_keys.append(rolling_bundle_field_name)

            if slug not in rolling_serializer_slug_set:
                missing_metadata_fields.append("rolling_serializer_key")
                missing_rolling_serializer_keys.append(rolling_serializer_field_name)
            elif not rolling_serializer_key_is_valid:
                invalid_metadata_fields.append("rolling_serializer_key")
                invalid_rolling_serializer_keys.append(rolling_serializer_field_name)

            good_field_count = sum(
                (
                    slug_is_valid
                    and "diagnostic_slug" not in conflicting_metadata_fields,
                    diagnostic_key_is_valid
                    and "diagnostic_key" not in conflicting_metadata_fields,
                    contract_group_present
                    and contract_group_is_valid
                    and "contract_group" not in duplicate_metadata_fields
                    and "contract_group" not in conflicting_metadata_fields,
                    service_builder_key_present
                    and service_builder_key_is_valid
                    and "service_builder_key" not in duplicate_metadata_fields
                    and "service_builder_key" not in conflicting_metadata_fields,
                    api_route_key_present
                    and api_route_key_is_valid
                    and "api_route_key" not in duplicate_metadata_fields
                    and "api_route_key" not in conflicting_metadata_fields,
                    serializer_key_present
                    and serializer_key_is_valid
                    and "serializer_key" not in duplicate_metadata_fields
                    and "serializer_key" not in conflicting_metadata_fields,
                    rolling_bundle_key_present
                    and rolling_bundle_key_is_valid
                    and "rolling_bundle_key" not in duplicate_metadata_fields
                    and "rolling_bundle_key" not in conflicting_metadata_fields,
                    rolling_serializer_key_present
                    and rolling_serializer_key_is_valid
                    and "rolling_serializer_key" not in duplicate_metadata_fields
                    and "rolling_serializer_key" not in conflicting_metadata_fields,
                )
            )
            completeness_percentage = round((good_field_count / 8.0) * 100.0, 2)

            if good_field_count == 8:
                consistency_classification = "consistent"
                complete_metadata_count += 1
                diagnostic = (
                    "Source diagnostic contract metadata remained complete and normalized across the explicit registry surfaces."
                )
            elif good_field_count >= 6:
                consistency_classification = "partial"
                partial_metadata_count += 1
                diagnostic = (
                    "Source diagnostic contract metadata was partial because one or two normalized metadata surfaces were missing, invalid, duplicated, or conflicting."
                )
            else:
                consistency_classification = "degraded"
                degraded_metadata_count += 1
                diagnostic = (
                    "Source diagnostic contract metadata was degraded because multiple normalized metadata surfaces were missing, invalid, duplicated, or conflicting."
                )

            entries.append(
                SnapshotReplayContractMetadataNormalizationConsistencyEntry(
                    diagnostic_slug=slug,
                    diagnostic_key=diagnostic_key,
                    diagnostic_group=diagnostic_group,
                    service_builder_name=service_builder_name,
                    api_route_path=api_route_path,
                    serializer_name=serializer_name,
                    rolling_bundle_field_name=rolling_bundle_field_name,
                    rolling_serializer_field_name=rolling_serializer_field_name,
                    contract_group_present=contract_group_present,
                    service_builder_key_present=service_builder_key_present,
                    api_route_key_present=api_route_key_present,
                    serializer_key_present=serializer_key_present,
                    rolling_bundle_key_present=rolling_bundle_key_present,
                    rolling_serializer_key_present=rolling_serializer_key_present,
                    missing_metadata_fields=tuple(missing_metadata_fields),
                    invalid_metadata_fields=tuple(invalid_metadata_fields),
                    duplicate_metadata_fields=tuple(duplicate_metadata_fields),
                    conflicting_metadata_fields=tuple(conflicting_metadata_fields),
                    consistency_classification=consistency_classification,
                    completeness_percentage=completeness_percentage,
                    diagnostic=diagnostic,
                )
            )

        total_diagnostics_registered = len(entries)
        completeness_percentage = round(
            sum(entry.completeness_percentage for entry in entries)
            / total_diagnostics_registered,
            2,
        )

        if degraded_metadata_count > 0:
            consistency_classification = "degraded"
        elif partial_metadata_count > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        missing_metadata_field_count = sum(
            len(entry.missing_metadata_fields) for entry in entries
        )
        invalid_metadata_field_count = sum(
            len(entry.invalid_metadata_fields) for entry in entries
        )

        diagnostics = [
            f"Replay diagnostic contract metadata normalization consistency is {consistency_classification} across {total_diagnostics_registered} registered source diagnostic contract(s)."
        ]
        if missing_metadata_field_count:
            diagnostics.append(
                f"{missing_metadata_field_count} metadata field gap(s) were detected across the explicit source diagnostic contract registry."
            )
        if invalid_metadata_field_count:
            diagnostics.append(
                f"{invalid_metadata_field_count} normalized metadata field validation issue(s) were detected across the explicit source diagnostic contract registry."
            )
        if duplicate_metadata_records:
            diagnostics.append(
                f"{len(duplicate_metadata_records)} duplicated metadata record(s) were detected across the explicit source diagnostic contract registry."
            )
        if conflicting_metadata_records:
            diagnostics.append(
                f"{len(conflicting_metadata_records)} conflicting metadata record(s) were detected across the explicit source diagnostic contract registry."
            )

        return SnapshotReplayContractMetadataNormalizationConsistency(
            consistency_classification=consistency_classification,
            completeness_percentage=completeness_percentage,
            total_diagnostics_registered=total_diagnostics_registered,
            complete_metadata_count=complete_metadata_count,
            partial_metadata_count=partial_metadata_count,
            degraded_metadata_count=degraded_metadata_count,
            missing_metadata_field_count=missing_metadata_field_count,
            invalid_metadata_field_count=invalid_metadata_field_count,
            duplicate_metadata_record_count=len(duplicate_metadata_records),
            conflicting_metadata_record_count=len(conflicting_metadata_records),
            missing_group_diagnostic_keys=tuple(sorted(set(missing_group_diagnostic_keys))),
            invalid_group_diagnostic_keys=tuple(sorted(set(invalid_group_diagnostic_keys))),
            invalid_group_names=tuple(sorted(set(invalid_group_names))),
            invalid_diagnostic_slugs=tuple(sorted(set(invalid_diagnostic_slugs))),
            invalid_diagnostic_keys=tuple(sorted(set(invalid_diagnostic_keys))),
            missing_service_builder_keys=tuple(sorted(set(missing_service_builder_keys))),
            invalid_service_builder_keys=tuple(sorted(set(invalid_service_builder_keys))),
            missing_api_route_keys=tuple(sorted(set(missing_api_route_keys))),
            invalid_api_route_keys=tuple(sorted(set(invalid_api_route_keys))),
            missing_serializer_keys=tuple(sorted(set(missing_serializer_keys))),
            invalid_serializer_keys=tuple(sorted(set(invalid_serializer_keys))),
            missing_rolling_bundle_keys=tuple(sorted(set(missing_rolling_bundle_keys))),
            invalid_rolling_bundle_keys=tuple(sorted(set(invalid_rolling_bundle_keys))),
            missing_rolling_serializer_keys=tuple(
                sorted(set(missing_rolling_serializer_keys))
            ),
            invalid_rolling_serializer_keys=tuple(
                sorted(set(invalid_rolling_serializer_keys))
            ),
            duplicate_metadata_records=tuple(sorted(duplicate_metadata_records)),
            conflicting_metadata_records=tuple(sorted(conflicting_metadata_records)),
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_source_diagnostic_metadata_completeness_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplaySourceDiagnosticMetadataCompletenessDrift:
        contract_metadata_normalization_consistency = (
            self._build_contract_metadata_normalization_consistency()
        )
        diagnostics: list[str] = []
        severity_score = min(
            100,
            contract_metadata_normalization_consistency.missing_metadata_field_count * 10
            + contract_metadata_normalization_consistency.invalid_metadata_field_count
            * 10
            + contract_metadata_normalization_consistency.duplicate_metadata_record_count
            * 5
            + contract_metadata_normalization_consistency.conflicting_metadata_record_count
            * 5,
        )

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostic metadata completeness drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic metadata completeness drift analysis."
                )
            return SnapshotReplaySourceDiagnosticMetadataCompletenessDrift(
                drift_classification="insufficient_data",
                average_completeness_percentage=contract_metadata_normalization_consistency.completeness_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                missing_metadata_field_count=contract_metadata_normalization_consistency.missing_metadata_field_count,
                invalid_metadata_field_count=contract_metadata_normalization_consistency.invalid_metadata_field_count,
                duplicate_metadata_record_count=contract_metadata_normalization_consistency.duplicate_metadata_record_count,
                conflicting_metadata_record_count=contract_metadata_normalization_consistency.conflicting_metadata_record_count,
                missing_group_diagnostic_keys=contract_metadata_normalization_consistency.missing_group_diagnostic_keys,
                invalid_group_diagnostic_keys=contract_metadata_normalization_consistency.invalid_group_diagnostic_keys,
                invalid_group_names=contract_metadata_normalization_consistency.invalid_group_names,
                invalid_diagnostic_slugs=contract_metadata_normalization_consistency.invalid_diagnostic_slugs,
                invalid_diagnostic_keys=contract_metadata_normalization_consistency.invalid_diagnostic_keys,
                missing_service_builder_keys=contract_metadata_normalization_consistency.missing_service_builder_keys,
                invalid_service_builder_keys=contract_metadata_normalization_consistency.invalid_service_builder_keys,
                missing_api_route_keys=contract_metadata_normalization_consistency.missing_api_route_keys,
                invalid_api_route_keys=contract_metadata_normalization_consistency.invalid_api_route_keys,
                missing_serializer_keys=contract_metadata_normalization_consistency.missing_serializer_keys,
                invalid_serializer_keys=contract_metadata_normalization_consistency.invalid_serializer_keys,
                missing_rolling_bundle_keys=contract_metadata_normalization_consistency.missing_rolling_bundle_keys,
                invalid_rolling_bundle_keys=contract_metadata_normalization_consistency.invalid_rolling_bundle_keys,
                missing_rolling_serializer_keys=contract_metadata_normalization_consistency.missing_rolling_serializer_keys,
                invalid_rolling_serializer_keys=contract_metadata_normalization_consistency.invalid_rolling_serializer_keys,
                duplicate_metadata_records=contract_metadata_normalization_consistency.duplicate_metadata_records,
                conflicting_metadata_records=contract_metadata_normalization_consistency.conflicting_metadata_records,
                contract_metadata_normalization_consistency=contract_metadata_normalization_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if (
            contract_metadata_normalization_consistency.consistency_classification
            == "consistent"
        ):
            entry_drift_classification = "stable"
        elif (
            contract_metadata_normalization_consistency.consistency_classification
            == "partial"
        ):
            entry_drift_classification = "drifting"
        elif (
            contract_metadata_normalization_consistency.consistency_classification
            == "degraded"
        ):
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry] = []
        stable_snapshots = 0
        drifting_snapshots = 0
        degraded_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get(
                "created_at", datetime.now(UTC).isoformat()
            )
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            if entry_drift_classification == "stable":
                stable_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract metadata remained complete and normalized for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract metadata drifted because one or two normalized metadata surfaces were incomplete."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract metadata was degraded because multiple normalized metadata surfaces diverged."
                )
            else:
                diagnostic = (
                    "Source diagnostic contract metadata could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    completeness_percentage=contract_metadata_normalization_consistency.completeness_percentage,
                    total_diagnostics_registered=contract_metadata_normalization_consistency.total_diagnostics_registered,
                    complete_metadata_count=contract_metadata_normalization_consistency.complete_metadata_count,
                    partial_metadata_count=contract_metadata_normalization_consistency.partial_metadata_count,
                    degraded_metadata_count=contract_metadata_normalization_consistency.degraded_metadata_count,
                    missing_metadata_field_count=contract_metadata_normalization_consistency.missing_metadata_field_count,
                    invalid_metadata_field_count=contract_metadata_normalization_consistency.invalid_metadata_field_count,
                    duplicate_metadata_record_count=contract_metadata_normalization_consistency.duplicate_metadata_record_count,
                    conflicting_metadata_record_count=contract_metadata_normalization_consistency.conflicting_metadata_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if degraded_snapshots > 0:
            drift_classification = "degraded"
        elif drifting_snapshots > 0:
            drift_classification = "drifting"
        else:
            drift_classification = "stable"

        diagnostics.append(
            f"Source diagnostic metadata completeness drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(contract_metadata_normalization_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic metadata completeness drift analysis."
            )

        return SnapshotReplaySourceDiagnosticMetadataCompletenessDrift(
            drift_classification=drift_classification,
            average_completeness_percentage=contract_metadata_normalization_consistency.completeness_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            missing_metadata_field_count=contract_metadata_normalization_consistency.missing_metadata_field_count,
            invalid_metadata_field_count=contract_metadata_normalization_consistency.invalid_metadata_field_count,
            duplicate_metadata_record_count=contract_metadata_normalization_consistency.duplicate_metadata_record_count,
            conflicting_metadata_record_count=contract_metadata_normalization_consistency.conflicting_metadata_record_count,
            missing_group_diagnostic_keys=contract_metadata_normalization_consistency.missing_group_diagnostic_keys,
            invalid_group_diagnostic_keys=contract_metadata_normalization_consistency.invalid_group_diagnostic_keys,
            invalid_group_names=contract_metadata_normalization_consistency.invalid_group_names,
            invalid_diagnostic_slugs=contract_metadata_normalization_consistency.invalid_diagnostic_slugs,
            invalid_diagnostic_keys=contract_metadata_normalization_consistency.invalid_diagnostic_keys,
            missing_service_builder_keys=contract_metadata_normalization_consistency.missing_service_builder_keys,
            invalid_service_builder_keys=contract_metadata_normalization_consistency.invalid_service_builder_keys,
            missing_api_route_keys=contract_metadata_normalization_consistency.missing_api_route_keys,
            invalid_api_route_keys=contract_metadata_normalization_consistency.invalid_api_route_keys,
            missing_serializer_keys=contract_metadata_normalization_consistency.missing_serializer_keys,
            invalid_serializer_keys=contract_metadata_normalization_consistency.invalid_serializer_keys,
            missing_rolling_bundle_keys=contract_metadata_normalization_consistency.missing_rolling_bundle_keys,
            invalid_rolling_bundle_keys=contract_metadata_normalization_consistency.invalid_rolling_bundle_keys,
            missing_rolling_serializer_keys=contract_metadata_normalization_consistency.missing_rolling_serializer_keys,
            invalid_rolling_serializer_keys=contract_metadata_normalization_consistency.invalid_rolling_serializer_keys,
            duplicate_metadata_records=contract_metadata_normalization_consistency.duplicate_metadata_records,
            conflicting_metadata_records=contract_metadata_normalization_consistency.conflicting_metadata_records,
            contract_metadata_normalization_consistency=contract_metadata_normalization_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryMetadataMixin"]
