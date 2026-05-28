from __future__ import annotations

from collections import Counter
from collections import defaultdict
import re

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    SnapshotReplayBuilderSerializerRouteNamingConsistency,
    SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry,
    SnapshotReplaySourceDiagnosticNamingContractDrift,
    SnapshotReplaySourceDiagnosticNamingContractDriftEntry,
)
from app.services.snapshot_replay_source_common import Any, Mapping, UTC, datetime


_DIAGNOSTIC_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DIAGNOSTIC_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_SERVICE_BUILDER_PATTERN = re.compile(r"^build_[a-z0-9]+(?:_[a-z0-9]+)*$")
_SERIALIZER_KEY_PATTERN = re.compile(r"^_serialize_[a-z0-9]+(?:_[a-z0-9]+)*$")


def _expected_diagnostic_key(slug: str) -> str:
    return slug.replace("-", "_")


def _expected_service_builder_name(slug: str) -> str:
    return f"build_{_expected_diagnostic_key(slug)}"


def _expected_serializer_name(slug: str) -> str:
    return f"_serialize_{_expected_diagnostic_key(slug)}"


def _expected_api_route_path(slug: str) -> str:
    return (
        source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_ROUTE_PREFIX
        + slug
    )


def _expected_rolling_bundle_field_name(slug: str) -> str:
    return _expected_diagnostic_key(slug)


def _expected_rolling_serializer_field_name(slug: str) -> str:
    return _expected_diagnostic_key(slug)


def _route_path_is_valid(path: str) -> bool:
    prefix = source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_ROUTE_PREFIX
    if not path.startswith(prefix):
        return False
    route_slug = path[len(prefix) :]
    return bool(_DIAGNOSTIC_SLUG_PATTERN.fullmatch(route_slug))


class SnapshotReplaySourceRegistryNamingMixin:
    def _build_builder_serializer_route_naming_consistency(
        self,
    ) -> SnapshotReplayBuilderSerializerRouteNamingConsistency:
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
            return SnapshotReplayBuilderSerializerRouteNamingConsistency(
                consistency_classification="insufficient_data",
                consistency_percentage=0.0,
                total_diagnostics_registered=0,
                consistent_diagnostic_count=0,
                partial_diagnostic_count=0,
                degraded_diagnostic_count=0,
                invalid_name_field_count=0,
                mismatched_name_field_count=0,
                duplicate_name_record_count=0,
                conflicting_name_record_count=0,
                invalid_diagnostic_slugs=(),
                invalid_diagnostic_keys=(),
                mismatched_diagnostic_keys=(),
                invalid_service_builder_names=(),
                mismatched_service_builder_names=(),
                invalid_serializer_names=(),
                mismatched_serializer_names=(),
                invalid_api_route_paths=(),
                mismatched_api_route_paths=(),
                invalid_rolling_bundle_field_names=(),
                mismatched_rolling_bundle_field_names=(),
                invalid_rolling_serializer_field_names=(),
                mismatched_rolling_serializer_field_names=(),
                duplicate_name_records=(),
                conflicting_name_records=(),
                entries=(),
                diagnostics=(
                    "No source diagnostic naming contracts were registered for naming consistency analysis.",
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

        actual_diagnostic_keys = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_key(slug)
            for slug in registered_slugs
        }
        actual_service_builder_names = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                slug
            )
            for slug in registered_slugs
        }
        actual_serializer_names = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_serializer_name(
                slug
            )
            for slug in registered_slugs
        }
        actual_api_route_paths = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_route_path(
                slug
            )
            for slug in registered_slugs
        }
        actual_rolling_bundle_field_names = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_field_name(
                slug
            )
            for slug in registered_slugs
        }
        actual_rolling_serializer_field_names = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_serializer_field_name(
                slug
            )
            for slug in registered_slugs
        }

        duplicate_fields_by_slug: dict[str, set[str]] = defaultdict(set)
        duplicate_name_records: set[str] = set()

        for slug, count in Counter(service_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("service_builder_name")
                duplicate_name_records.add(
                    "service_builder_name:" + actual_service_builder_names[slug]
                )
        for slug, count in Counter(api_route_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("api_route_path")
                duplicate_name_records.add(
                    "api_route_path:" + actual_api_route_paths[slug]
                )
        for slug, count in Counter(serializer_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("serializer_name")
                duplicate_name_records.add(
                    "serializer_name:" + actual_serializer_names[slug]
                )
        for slug, count in Counter(rolling_bundle_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("rolling_bundle_field_name")
                duplicate_name_records.add(
                    "rolling_bundle_field_name:"
                    + actual_rolling_bundle_field_names[slug]
                )
        for slug, count in Counter(rolling_serializer_slugs).items():
            if count > 1:
                duplicate_fields_by_slug[slug].add("rolling_serializer_field_name")
                duplicate_name_records.add(
                    "rolling_serializer_field_name:"
                    + actual_rolling_serializer_field_names[slug]
                )

        conflicting_fields_by_slug: dict[str, set[str]] = defaultdict(set)
        conflicting_name_records: set[str] = set()

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
                    conflicting_name_records.add(f"{field_name}:{value}")

        record_conflicts("diagnostic_key", actual_diagnostic_keys)
        record_conflicts(
            "service_builder_name",
            {
                slug: actual_service_builder_names[slug]
                for slug in registered_slugs
                if slug in service_slug_set
            },
        )
        record_conflicts(
            "serializer_name",
            {
                slug: actual_serializer_names[slug]
                for slug in registered_slugs
                if slug in serializer_slug_set
            },
        )
        record_conflicts(
            "api_route_path",
            {
                slug: actual_api_route_paths[slug]
                for slug in registered_slugs
                if slug in api_route_slug_set
            },
        )
        record_conflicts(
            "rolling_bundle_field_name",
            {
                slug: actual_rolling_bundle_field_names[slug]
                for slug in registered_slugs
                if slug in rolling_bundle_slug_set
            },
        )
        record_conflicts(
            "rolling_serializer_field_name",
            {
                slug: actual_rolling_serializer_field_names[slug]
                for slug in registered_slugs
                if slug in rolling_serializer_slug_set
            },
        )

        invalid_diagnostic_slugs: list[str] = []
        invalid_diagnostic_keys: list[str] = []
        mismatched_diagnostic_keys: list[str] = []
        invalid_service_builder_names: list[str] = []
        mismatched_service_builder_names: list[str] = []
        invalid_serializer_names: list[str] = []
        mismatched_serializer_names: list[str] = []
        invalid_api_route_paths: list[str] = []
        mismatched_api_route_paths: list[str] = []
        invalid_rolling_bundle_field_names: list[str] = []
        mismatched_rolling_bundle_field_names: list[str] = []
        invalid_rolling_serializer_field_names: list[str] = []
        mismatched_rolling_serializer_field_names: list[str] = []

        entries: list[SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry] = []
        consistent_diagnostic_count = 0
        partial_diagnostic_count = 0
        degraded_diagnostic_count = 0

        for slug in registered_slugs:
            expected_diagnostic_key = _expected_diagnostic_key(slug)
            expected_service_builder_name = _expected_service_builder_name(slug)
            expected_serializer_name = _expected_serializer_name(slug)
            expected_api_route_path = _expected_api_route_path(slug)
            expected_rolling_bundle_field_name = _expected_rolling_bundle_field_name(slug)
            expected_rolling_serializer_field_name = (
                _expected_rolling_serializer_field_name(slug)
            )

            actual_diagnostic_key = actual_diagnostic_keys[slug]
            actual_service_builder_name = actual_service_builder_names[slug]
            actual_serializer_name = actual_serializer_names[slug]
            actual_api_route_path = actual_api_route_paths[slug]
            actual_rolling_bundle_field_name = actual_rolling_bundle_field_names[slug]
            actual_rolling_serializer_field_name = (
                actual_rolling_serializer_field_names[slug]
            )

            service_builder_surface_present = slug in service_slug_set
            serializer_surface_present = slug in serializer_slug_set
            api_route_surface_present = slug in api_route_slug_set
            rolling_bundle_surface_present = slug in rolling_bundle_slug_set
            rolling_serializer_surface_present = slug in rolling_serializer_slug_set

            invalid_name_fields: list[str] = []
            mismatched_name_fields: list[str] = []
            duplicate_name_fields = sorted(duplicate_fields_by_slug.get(slug, set()))
            conflicting_name_fields = sorted(
                conflicting_fields_by_slug.get(slug, set())
            )

            if not _DIAGNOSTIC_SLUG_PATTERN.fullmatch(slug):
                invalid_name_fields.append("diagnostic_slug")
                invalid_diagnostic_slugs.append(slug)

            if actual_diagnostic_key != expected_diagnostic_key:
                mismatched_name_fields.append("diagnostic_key")
                mismatched_diagnostic_keys.append(actual_diagnostic_key)
            if not _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key):
                invalid_name_fields.append("diagnostic_key")
                invalid_diagnostic_keys.append(actual_diagnostic_key)

            if service_builder_surface_present:
                if actual_service_builder_name != expected_service_builder_name:
                    mismatched_name_fields.append("service_builder_name")
                    mismatched_service_builder_names.append(actual_service_builder_name)
                if not _SERVICE_BUILDER_PATTERN.fullmatch(actual_service_builder_name):
                    invalid_name_fields.append("service_builder_name")
                    invalid_service_builder_names.append(actual_service_builder_name)

            if serializer_surface_present:
                if actual_serializer_name != expected_serializer_name:
                    mismatched_name_fields.append("serializer_name")
                    mismatched_serializer_names.append(actual_serializer_name)
                if not _SERIALIZER_KEY_PATTERN.fullmatch(actual_serializer_name):
                    invalid_name_fields.append("serializer_name")
                    invalid_serializer_names.append(actual_serializer_name)

            if api_route_surface_present:
                if actual_api_route_path != expected_api_route_path:
                    mismatched_name_fields.append("api_route_path")
                    mismatched_api_route_paths.append(actual_api_route_path)
                if not _route_path_is_valid(actual_api_route_path):
                    invalid_name_fields.append("api_route_path")
                    invalid_api_route_paths.append(actual_api_route_path)

            if rolling_bundle_surface_present:
                if actual_rolling_bundle_field_name != expected_rolling_bundle_field_name:
                    mismatched_name_fields.append("rolling_bundle_field_name")
                    mismatched_rolling_bundle_field_names.append(
                        actual_rolling_bundle_field_name
                    )
                if not _DIAGNOSTIC_KEY_PATTERN.fullmatch(
                    actual_rolling_bundle_field_name
                ):
                    invalid_name_fields.append("rolling_bundle_field_name")
                    invalid_rolling_bundle_field_names.append(
                        actual_rolling_bundle_field_name
                    )

            if rolling_serializer_surface_present:
                if (
                    actual_rolling_serializer_field_name
                    != expected_rolling_serializer_field_name
                ):
                    mismatched_name_fields.append("rolling_serializer_field_name")
                    mismatched_rolling_serializer_field_names.append(
                        actual_rolling_serializer_field_name
                    )
                if not _DIAGNOSTIC_KEY_PATTERN.fullmatch(
                    actual_rolling_serializer_field_name
                ):
                    invalid_name_fields.append("rolling_serializer_field_name")
                    invalid_rolling_serializer_field_names.append(
                        actual_rolling_serializer_field_name
                    )

            applicable_field_count = 2 + sum(
                (
                    service_builder_surface_present,
                    serializer_surface_present,
                    api_route_surface_present,
                    rolling_bundle_surface_present,
                    rolling_serializer_surface_present,
                )
            )
            inconsistent_field_count = len(
                {
                    *invalid_name_fields,
                    *mismatched_name_fields,
                    *duplicate_name_fields,
                    *conflicting_name_fields,
                }
            )
            consistency_percentage = round(
                max(
                    0.0,
                    ((applicable_field_count - inconsistent_field_count) / applicable_field_count)
                    * 100.0,
                ),
                2,
            )

            if inconsistent_field_count == 0:
                consistency_classification = "consistent"
                consistent_diagnostic_count += 1
                diagnostic = (
                    "Diagnostic key, builder, serializer, route, and rolling naming remained aligned for this source diagnostic contract."
                )
            elif inconsistent_field_count <= 2:
                consistency_classification = "partial"
                partial_diagnostic_count += 1
                diagnostic = (
                    "Source diagnostic naming was partial because one or two contract naming surfaces diverged from the normalized contract expectation."
                )
            else:
                consistency_classification = "degraded"
                degraded_diagnostic_count += 1
                diagnostic = (
                    "Source diagnostic naming was degraded because multiple contract naming surfaces diverged from the normalized contract expectation."
                )

            entries.append(
                SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry(
                    diagnostic_slug=slug,
                    expected_diagnostic_key=expected_diagnostic_key,
                    actual_diagnostic_key=actual_diagnostic_key,
                    expected_service_builder_name=expected_service_builder_name,
                    actual_service_builder_name=actual_service_builder_name,
                    expected_serializer_name=expected_serializer_name,
                    actual_serializer_name=actual_serializer_name,
                    expected_api_route_path=expected_api_route_path,
                    actual_api_route_path=actual_api_route_path,
                    expected_rolling_bundle_field_name=expected_rolling_bundle_field_name,
                    actual_rolling_bundle_field_name=actual_rolling_bundle_field_name,
                    expected_rolling_serializer_field_name=expected_rolling_serializer_field_name,
                    actual_rolling_serializer_field_name=actual_rolling_serializer_field_name,
                    service_builder_surface_present=service_builder_surface_present,
                    serializer_surface_present=serializer_surface_present,
                    api_route_surface_present=api_route_surface_present,
                    rolling_bundle_surface_present=rolling_bundle_surface_present,
                    rolling_serializer_surface_present=rolling_serializer_surface_present,
                    invalid_name_fields=tuple(invalid_name_fields),
                    mismatched_name_fields=tuple(mismatched_name_fields),
                    duplicate_name_fields=tuple(duplicate_name_fields),
                    conflicting_name_fields=tuple(conflicting_name_fields),
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    diagnostic=diagnostic,
                )
            )

        total_diagnostics_registered = len(entries)
        consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries)
            / total_diagnostics_registered,
            2,
        )

        if degraded_diagnostic_count > 0:
            consistency_classification = "degraded"
        elif partial_diagnostic_count > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        diagnostics = [
            f"Replay diagnostic naming consistency is {consistency_classification} across {total_diagnostics_registered} registered source diagnostic contract(s)."
        ]
        if invalid_diagnostic_slugs:
            diagnostics.append(
                f"{len(set(invalid_diagnostic_slugs))} diagnostic slug(s) used invalid naming."
            )
        if mismatched_service_builder_names or mismatched_serializer_names:
            diagnostics.append(
                "Builder or serializer names diverged from their normalized diagnostic key expectations."
            )
        if mismatched_api_route_paths:
            diagnostics.append(
                f"{len(set(mismatched_api_route_paths))} API route path(s) diverged from the normalized route naming expectation."
            )
        if conflicting_name_records:
            diagnostics.append(
                f"{len(conflicting_name_records)} conflicting diagnostic naming record(s) were detected across normalized contract surfaces."
            )

        return SnapshotReplayBuilderSerializerRouteNamingConsistency(
            consistency_classification=consistency_classification,
            consistency_percentage=consistency_percentage,
            total_diagnostics_registered=total_diagnostics_registered,
            consistent_diagnostic_count=consistent_diagnostic_count,
            partial_diagnostic_count=partial_diagnostic_count,
            degraded_diagnostic_count=degraded_diagnostic_count,
            invalid_name_field_count=sum(
                len(entry.invalid_name_fields) for entry in entries
            ),
            mismatched_name_field_count=sum(
                len(entry.mismatched_name_fields) for entry in entries
            ),
            duplicate_name_record_count=len(duplicate_name_records),
            conflicting_name_record_count=len(conflicting_name_records),
            invalid_diagnostic_slugs=tuple(sorted(set(invalid_diagnostic_slugs))),
            invalid_diagnostic_keys=tuple(sorted(set(invalid_diagnostic_keys))),
            mismatched_diagnostic_keys=tuple(sorted(set(mismatched_diagnostic_keys))),
            invalid_service_builder_names=tuple(
                sorted(set(invalid_service_builder_names))
            ),
            mismatched_service_builder_names=tuple(
                sorted(set(mismatched_service_builder_names))
            ),
            invalid_serializer_names=tuple(sorted(set(invalid_serializer_names))),
            mismatched_serializer_names=tuple(
                sorted(set(mismatched_serializer_names))
            ),
            invalid_api_route_paths=tuple(sorted(set(invalid_api_route_paths))),
            mismatched_api_route_paths=tuple(sorted(set(mismatched_api_route_paths))),
            invalid_rolling_bundle_field_names=tuple(
                sorted(set(invalid_rolling_bundle_field_names))
            ),
            mismatched_rolling_bundle_field_names=tuple(
                sorted(set(mismatched_rolling_bundle_field_names))
            ),
            invalid_rolling_serializer_field_names=tuple(
                sorted(set(invalid_rolling_serializer_field_names))
            ),
            mismatched_rolling_serializer_field_names=tuple(
                sorted(set(mismatched_rolling_serializer_field_names))
            ),
            duplicate_name_records=tuple(sorted(duplicate_name_records)),
            conflicting_name_records=tuple(sorted(conflicting_name_records)),
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostic_naming_contract_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplaySourceDiagnosticNamingContractDrift:
        naming_consistency = self._build_builder_serializer_route_naming_consistency()
        severity_score = min(
            100,
            naming_consistency.invalid_name_field_count * 15
            + naming_consistency.mismatched_name_field_count * 10
            + naming_consistency.duplicate_name_record_count * 10
            + naming_consistency.conflicting_name_record_count * 20,
        )
        diagnostics: list[str] = []

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostic naming contract drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic naming contract drift analysis."
                )
            return SnapshotReplaySourceDiagnosticNamingContractDrift(
                drift_classification="insufficient_data",
                average_consistency_percentage=naming_consistency.consistency_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                invalid_name_field_count=naming_consistency.invalid_name_field_count,
                mismatched_name_field_count=naming_consistency.mismatched_name_field_count,
                duplicate_name_record_count=naming_consistency.duplicate_name_record_count,
                conflicting_name_record_count=naming_consistency.conflicting_name_record_count,
                invalid_diagnostic_slugs=naming_consistency.invalid_diagnostic_slugs,
                invalid_diagnostic_keys=naming_consistency.invalid_diagnostic_keys,
                mismatched_diagnostic_keys=naming_consistency.mismatched_diagnostic_keys,
                invalid_service_builder_names=naming_consistency.invalid_service_builder_names,
                mismatched_service_builder_names=naming_consistency.mismatched_service_builder_names,
                invalid_serializer_names=naming_consistency.invalid_serializer_names,
                mismatched_serializer_names=naming_consistency.mismatched_serializer_names,
                invalid_api_route_paths=naming_consistency.invalid_api_route_paths,
                mismatched_api_route_paths=naming_consistency.mismatched_api_route_paths,
                invalid_rolling_bundle_field_names=naming_consistency.invalid_rolling_bundle_field_names,
                mismatched_rolling_bundle_field_names=naming_consistency.mismatched_rolling_bundle_field_names,
                invalid_rolling_serializer_field_names=naming_consistency.invalid_rolling_serializer_field_names,
                mismatched_rolling_serializer_field_names=naming_consistency.mismatched_rolling_serializer_field_names,
                duplicate_name_records=naming_consistency.duplicate_name_records,
                conflicting_name_records=naming_consistency.conflicting_name_records,
                builder_serializer_route_naming_consistency=naming_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if naming_consistency.consistency_classification == "consistent":
            entry_drift_classification = "stable"
        elif naming_consistency.consistency_classification == "partial":
            entry_drift_classification = "drifting"
        elif naming_consistency.consistency_classification == "degraded":
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplaySourceDiagnosticNamingContractDriftEntry] = []
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
                    "Source diagnostic naming remained stable for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Source diagnostic naming drifted because one or two normalized naming surfaces diverged."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Source diagnostic naming was degraded because multiple normalized naming surfaces diverged."
                )
            else:
                diagnostic = (
                    "Source diagnostic naming could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplaySourceDiagnosticNamingContractDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    consistency_percentage=naming_consistency.consistency_percentage,
                    total_diagnostics_registered=naming_consistency.total_diagnostics_registered,
                    invalid_name_field_count=naming_consistency.invalid_name_field_count,
                    mismatched_name_field_count=naming_consistency.mismatched_name_field_count,
                    duplicate_name_record_count=naming_consistency.duplicate_name_record_count,
                    conflicting_name_record_count=naming_consistency.conflicting_name_record_count,
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
            f"Source diagnostic naming contract drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(naming_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic naming contract drift analysis."
            )

        return SnapshotReplaySourceDiagnosticNamingContractDrift(
            drift_classification=drift_classification,
            average_consistency_percentage=naming_consistency.consistency_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            invalid_name_field_count=naming_consistency.invalid_name_field_count,
            mismatched_name_field_count=naming_consistency.mismatched_name_field_count,
            duplicate_name_record_count=naming_consistency.duplicate_name_record_count,
            conflicting_name_record_count=naming_consistency.conflicting_name_record_count,
            invalid_diagnostic_slugs=naming_consistency.invalid_diagnostic_slugs,
            invalid_diagnostic_keys=naming_consistency.invalid_diagnostic_keys,
            mismatched_diagnostic_keys=naming_consistency.mismatched_diagnostic_keys,
            invalid_service_builder_names=naming_consistency.invalid_service_builder_names,
            mismatched_service_builder_names=naming_consistency.mismatched_service_builder_names,
            invalid_serializer_names=naming_consistency.invalid_serializer_names,
            mismatched_serializer_names=naming_consistency.mismatched_serializer_names,
            invalid_api_route_paths=naming_consistency.invalid_api_route_paths,
            mismatched_api_route_paths=naming_consistency.mismatched_api_route_paths,
            invalid_rolling_bundle_field_names=naming_consistency.invalid_rolling_bundle_field_names,
            mismatched_rolling_bundle_field_names=naming_consistency.mismatched_rolling_bundle_field_names,
            invalid_rolling_serializer_field_names=naming_consistency.invalid_rolling_serializer_field_names,
            mismatched_rolling_serializer_field_names=naming_consistency.mismatched_rolling_serializer_field_names,
            duplicate_name_records=naming_consistency.duplicate_name_records,
            conflicting_name_records=naming_consistency.conflicting_name_records,
            builder_serializer_route_naming_consistency=naming_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryNamingMixin"]
