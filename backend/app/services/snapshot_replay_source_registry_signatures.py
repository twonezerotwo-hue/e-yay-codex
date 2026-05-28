from __future__ import annotations

from collections import Counter
from collections import defaultdict
import re

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    SnapshotReplayFullSurfaceContractSignatureConsistency,
    SnapshotReplayFullSurfaceContractSignatureConsistencyEntry,
    SnapshotReplaySourceDiagnosticContractSignatureDrift,
    SnapshotReplaySourceDiagnosticContractSignatureDriftEntry,
)
from app.services.snapshot_replay_source_common import Any, Mapping, UTC, datetime


_DIAGNOSTIC_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DIAGNOSTIC_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_GROUP_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
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


def _build_contract_signature(diagnostic_key: str, diagnostic_group: str) -> str:
    return f"{diagnostic_key}|{diagnostic_group}"


def _build_service_builder_signature(
    diagnostic_key: str,
    builder_name: str,
) -> str:
    return f"{diagnostic_key}|{builder_name}"


def _build_serializer_signature(
    diagnostic_key: str,
    serializer_name: str,
) -> str:
    return f"{diagnostic_key}|{serializer_name}"


def _build_api_route_signature(
    diagnostic_key: str,
    api_route_path: str,
) -> str:
    return f"{diagnostic_key}|{api_route_path}"


def _build_rolling_bundle_signature(
    diagnostic_key: str,
    rolling_bundle_field_name: str,
) -> str:
    return f"{diagnostic_key}|{rolling_bundle_field_name}"


def _build_rolling_serializer_signature(
    diagnostic_key: str,
    rolling_serializer_field_name: str,
) -> str:
    return f"{diagnostic_key}|{rolling_serializer_field_name}"


def _build_full_surface_signature(
    *,
    contract_signature: str,
    service_builder_signature: str | None,
    serializer_signature: str | None,
    api_route_signature: str | None,
    rolling_bundle_signature: str | None,
    rolling_serializer_signature: str | None,
) -> str:
    return "|".join(
        (
            f"contract={contract_signature}",
            f"service={service_builder_signature or 'missing'}",
            f"serializer={serializer_signature or 'missing'}",
            f"route={api_route_signature or 'missing'}",
            f"rolling_bundle={rolling_bundle_signature or 'missing'}",
            f"rolling_serializer={rolling_serializer_signature or 'missing'}",
        )
    )


def _route_path_is_valid(path: str) -> bool:
    prefix = source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_ROUTE_PREFIX
    if not path.startswith(prefix):
        return False
    route_slug = path[len(prefix) :]
    return bool(_DIAGNOSTIC_SLUG_PATTERN.fullmatch(route_slug))


class SnapshotReplaySourceRegistrySignaturesMixin:
    def _build_full_surface_contract_signature_consistency(
        self,
    ) -> SnapshotReplayFullSurfaceContractSignatureConsistency:
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
            return SnapshotReplayFullSurfaceContractSignatureConsistency(
                consistency_classification="insufficient_data",
                consistency_percentage=0.0,
                total_diagnostics_registered=0,
                consistent_diagnostic_count=0,
                partial_diagnostic_count=0,
                degraded_diagnostic_count=0,
                missing_signature_component_count=0,
                invalid_signature_component_count=0,
                mismatched_signature_component_count=0,
                duplicate_signature_record_count=0,
                conflicting_signature_record_count=0,
                missing_contract_signatures=(),
                invalid_contract_signatures=(),
                mismatched_contract_signatures=(),
                missing_service_builder_signatures=(),
                invalid_service_builder_signatures=(),
                mismatched_service_builder_signatures=(),
                missing_serializer_signatures=(),
                invalid_serializer_signatures=(),
                mismatched_serializer_signatures=(),
                missing_api_route_signatures=(),
                invalid_api_route_signatures=(),
                mismatched_api_route_signatures=(),
                missing_rolling_bundle_signatures=(),
                invalid_rolling_bundle_signatures=(),
                mismatched_rolling_bundle_signatures=(),
                missing_rolling_serializer_signatures=(),
                invalid_rolling_serializer_signatures=(),
                mismatched_rolling_serializer_signatures=(),
                duplicate_signature_records=(),
                conflicting_signature_records=(),
                entries=(),
                diagnostics=(
                    "No source diagnostic contract signatures were registered for full-surface signature consistency analysis.",
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
        actual_contract_groups = {
            slug: source_diagnostic_contracts.snapshot_replay_source_diagnostic_group(slug)
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

        actual_contract_signatures = {
            slug: _build_contract_signature(
                actual_diagnostic_keys[slug],
                actual_contract_groups[slug],
            )
            for slug in registered_slugs
        }
        actual_service_builder_signatures = {
            slug: _build_service_builder_signature(
                actual_diagnostic_keys[slug],
                actual_service_builder_names[slug],
            )
            if slug in service_slug_set
            else None
            for slug in registered_slugs
        }
        actual_serializer_signatures = {
            slug: _build_serializer_signature(
                actual_diagnostic_keys[slug],
                actual_serializer_names[slug],
            )
            if slug in serializer_slug_set
            else None
            for slug in registered_slugs
        }
        actual_api_route_signatures = {
            slug: _build_api_route_signature(
                actual_diagnostic_keys[slug],
                actual_api_route_paths[slug],
            )
            if slug in api_route_slug_set
            else None
            for slug in registered_slugs
        }
        actual_rolling_bundle_signatures = {
            slug: _build_rolling_bundle_signature(
                actual_diagnostic_keys[slug],
                actual_rolling_bundle_field_names[slug],
            )
            if slug in rolling_bundle_slug_set
            else None
            for slug in registered_slugs
        }
        actual_rolling_serializer_signatures = {
            slug: _build_rolling_serializer_signature(
                actual_diagnostic_keys[slug],
                actual_rolling_serializer_field_names[slug],
            )
            if slug in rolling_serializer_slug_set
            else None
            for slug in registered_slugs
        }

        duplicate_fields_by_slug: dict[str, set[str]] = defaultdict(set)
        duplicate_signature_records: set[str] = set()

        def record_duplicate_surface_entries(
            field_name: str,
            slugs: tuple[str, ...],
            signatures_by_slug: Mapping[str, str | None],
        ) -> None:
            for slug, count in Counter(slugs).items():
                if count > 1:
                    duplicate_fields_by_slug[slug].add(field_name)
                    signature = signatures_by_slug.get(slug)
                    if signature is not None:
                        duplicate_signature_records.add(f"{field_name}:{signature}")

        record_duplicate_surface_entries(
            "service_builder_signature",
            service_slugs,
            actual_service_builder_signatures,
        )
        record_duplicate_surface_entries(
            "serializer_signature",
            serializer_slugs,
            actual_serializer_signatures,
        )
        record_duplicate_surface_entries(
            "api_route_signature",
            api_route_slugs,
            actual_api_route_signatures,
        )
        record_duplicate_surface_entries(
            "rolling_bundle_signature",
            rolling_bundle_slugs,
            actual_rolling_bundle_signatures,
        )
        record_duplicate_surface_entries(
            "rolling_serializer_signature",
            rolling_serializer_slugs,
            actual_rolling_serializer_signatures,
        )

        conflicting_fields_by_slug: dict[str, set[str]] = defaultdict(set)
        conflicting_signature_records: set[str] = set()

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
                    conflicting_signature_records.add(f"{field_name}:{value}")

        record_conflicts("contract_signature", actual_contract_signatures)
        record_conflicts(
            "service_builder_signature",
            {
                slug: signature
                for slug, signature in actual_service_builder_signatures.items()
                if signature is not None
            },
        )
        record_conflicts(
            "serializer_signature",
            {
                slug: signature
                for slug, signature in actual_serializer_signatures.items()
                if signature is not None
            },
        )
        record_conflicts(
            "api_route_signature",
            {
                slug: signature
                for slug, signature in actual_api_route_signatures.items()
                if signature is not None
            },
        )
        record_conflicts(
            "rolling_bundle_signature",
            {
                slug: signature
                for slug, signature in actual_rolling_bundle_signatures.items()
                if signature is not None
            },
        )
        record_conflicts(
            "rolling_serializer_signature",
            {
                slug: signature
                for slug, signature in actual_rolling_serializer_signatures.items()
                if signature is not None
            },
        )

        missing_contract_signatures: list[str] = []
        invalid_contract_signatures: list[str] = []
        mismatched_contract_signatures: list[str] = []
        missing_service_builder_signatures: list[str] = []
        invalid_service_builder_signatures: list[str] = []
        mismatched_service_builder_signatures: list[str] = []
        missing_serializer_signatures: list[str] = []
        invalid_serializer_signatures: list[str] = []
        mismatched_serializer_signatures: list[str] = []
        missing_api_route_signatures: list[str] = []
        invalid_api_route_signatures: list[str] = []
        mismatched_api_route_signatures: list[str] = []
        missing_rolling_bundle_signatures: list[str] = []
        invalid_rolling_bundle_signatures: list[str] = []
        mismatched_rolling_bundle_signatures: list[str] = []
        missing_rolling_serializer_signatures: list[str] = []
        invalid_rolling_serializer_signatures: list[str] = []
        mismatched_rolling_serializer_signatures: list[str] = []

        entries: list[SnapshotReplayFullSurfaceContractSignatureConsistencyEntry] = []
        consistent_diagnostic_count = 0
        partial_diagnostic_count = 0
        degraded_diagnostic_count = 0

        for slug in registered_slugs:
            expected_diagnostic_key = _expected_diagnostic_key(slug)
            expected_contract_group = str(group_by_slug.get(slug, "unknown"))
            expected_service_builder_name = _expected_service_builder_name(slug)
            expected_serializer_name = _expected_serializer_name(slug)
            expected_api_route_path = _expected_api_route_path(slug)
            expected_rolling_bundle_field_name = _expected_rolling_bundle_field_name(slug)
            expected_rolling_serializer_field_name = (
                _expected_rolling_serializer_field_name(slug)
            )

            actual_diagnostic_key = actual_diagnostic_keys[slug]
            actual_contract_group = actual_contract_groups[slug]
            actual_service_builder_name = actual_service_builder_names[slug]
            actual_serializer_name = actual_serializer_names[slug]
            actual_api_route_path = actual_api_route_paths[slug]
            actual_rolling_bundle_field_name = actual_rolling_bundle_field_names[slug]
            actual_rolling_serializer_field_name = (
                actual_rolling_serializer_field_names[slug]
            )

            expected_contract_signature = _build_contract_signature(
                expected_diagnostic_key,
                expected_contract_group,
            )
            actual_contract_signature = actual_contract_signatures[slug]
            expected_service_builder_signature = _build_service_builder_signature(
                expected_diagnostic_key,
                expected_service_builder_name,
            )
            expected_serializer_signature = _build_serializer_signature(
                expected_diagnostic_key,
                expected_serializer_name,
            )
            expected_api_route_signature = _build_api_route_signature(
                expected_diagnostic_key,
                expected_api_route_path,
            )
            expected_rolling_bundle_signature = _build_rolling_bundle_signature(
                expected_diagnostic_key,
                expected_rolling_bundle_field_name,
            )
            expected_rolling_serializer_signature = _build_rolling_serializer_signature(
                expected_diagnostic_key,
                expected_rolling_serializer_field_name,
            )

            actual_service_builder_signature = actual_service_builder_signatures[slug]
            actual_serializer_signature = actual_serializer_signatures[slug]
            actual_api_route_signature = actual_api_route_signatures[slug]
            actual_rolling_bundle_signature = actual_rolling_bundle_signatures[slug]
            actual_rolling_serializer_signature = (
                actual_rolling_serializer_signatures[slug]
            )

            service_builder_surface_present = slug in service_slug_set
            serializer_surface_present = slug in serializer_slug_set
            api_route_surface_present = slug in api_route_slug_set
            rolling_bundle_surface_present = slug in rolling_bundle_slug_set
            rolling_serializer_surface_present = slug in rolling_serializer_slug_set

            expected_full_surface_signature = _build_full_surface_signature(
                contract_signature=expected_contract_signature,
                service_builder_signature=expected_service_builder_signature,
                serializer_signature=expected_serializer_signature,
                api_route_signature=expected_api_route_signature,
                rolling_bundle_signature=expected_rolling_bundle_signature,
                rolling_serializer_signature=expected_rolling_serializer_signature,
            )
            actual_full_surface_signature = _build_full_surface_signature(
                contract_signature=actual_contract_signature,
                service_builder_signature=actual_service_builder_signature,
                serializer_signature=actual_serializer_signature,
                api_route_signature=actual_api_route_signature,
                rolling_bundle_signature=actual_rolling_bundle_signature,
                rolling_serializer_signature=actual_rolling_serializer_signature,
            )

            missing_signature_components: list[str] = []
            invalid_signature_components: list[str] = []
            mismatched_signature_components: list[str] = []
            duplicate_signature_components = sorted(
                duplicate_fields_by_slug.get(slug, set())
            )
            conflicting_signature_components = sorted(
                conflicting_fields_by_slug.get(slug, set())
            )

            if slug not in group_by_slug or expected_contract_group in ("", "unknown"):
                missing_signature_components.append("contract_signature")
                missing_contract_signatures.append(expected_contract_signature)
            if (
                not _DIAGNOSTIC_SLUG_PATTERN.fullmatch(slug)
                or not _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key)
                or not _GROUP_NAME_PATTERN.fullmatch(actual_contract_group)
            ):
                invalid_signature_components.append("contract_signature")
                invalid_contract_signatures.append(actual_contract_signature)
            if actual_contract_signature != expected_contract_signature:
                mismatched_signature_components.append("contract_signature")
                mismatched_contract_signatures.append(actual_contract_signature)

            if not service_builder_surface_present or actual_service_builder_signature is None:
                missing_signature_components.append("service_builder_signature")
                missing_service_builder_signatures.append(
                    expected_service_builder_signature
                )
            else:
                if not (
                    _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key)
                    and _SERVICE_BUILDER_PATTERN.fullmatch(actual_service_builder_name)
                ):
                    invalid_signature_components.append("service_builder_signature")
                    invalid_service_builder_signatures.append(
                        actual_service_builder_signature
                    )
                if (
                    actual_service_builder_signature
                    != expected_service_builder_signature
                ):
                    mismatched_signature_components.append("service_builder_signature")
                    mismatched_service_builder_signatures.append(
                        actual_service_builder_signature
                    )

            if not serializer_surface_present or actual_serializer_signature is None:
                missing_signature_components.append("serializer_signature")
                missing_serializer_signatures.append(expected_serializer_signature)
            else:
                if not (
                    _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key)
                    and _SERIALIZER_KEY_PATTERN.fullmatch(actual_serializer_name)
                ):
                    invalid_signature_components.append("serializer_signature")
                    invalid_serializer_signatures.append(actual_serializer_signature)
                if actual_serializer_signature != expected_serializer_signature:
                    mismatched_signature_components.append("serializer_signature")
                    mismatched_serializer_signatures.append(
                        actual_serializer_signature
                    )

            if not api_route_surface_present or actual_api_route_signature is None:
                missing_signature_components.append("api_route_signature")
                missing_api_route_signatures.append(expected_api_route_signature)
            else:
                if not (
                    _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key)
                    and _route_path_is_valid(actual_api_route_path)
                ):
                    invalid_signature_components.append("api_route_signature")
                    invalid_api_route_signatures.append(actual_api_route_signature)
                if actual_api_route_signature != expected_api_route_signature:
                    mismatched_signature_components.append("api_route_signature")
                    mismatched_api_route_signatures.append(actual_api_route_signature)

            if not rolling_bundle_surface_present or actual_rolling_bundle_signature is None:
                missing_signature_components.append("rolling_bundle_signature")
                missing_rolling_bundle_signatures.append(
                    expected_rolling_bundle_signature
                )
            else:
                if not (
                    _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key)
                    and _DIAGNOSTIC_KEY_PATTERN.fullmatch(
                        actual_rolling_bundle_field_name
                    )
                ):
                    invalid_signature_components.append("rolling_bundle_signature")
                    invalid_rolling_bundle_signatures.append(
                        actual_rolling_bundle_signature
                    )
                if (
                    actual_rolling_bundle_signature
                    != expected_rolling_bundle_signature
                ):
                    mismatched_signature_components.append("rolling_bundle_signature")
                    mismatched_rolling_bundle_signatures.append(
                        actual_rolling_bundle_signature
                    )

            if (
                not rolling_serializer_surface_present
                or actual_rolling_serializer_signature is None
            ):
                missing_signature_components.append("rolling_serializer_signature")
                missing_rolling_serializer_signatures.append(
                    expected_rolling_serializer_signature
                )
            else:
                if not (
                    _DIAGNOSTIC_KEY_PATTERN.fullmatch(actual_diagnostic_key)
                    and _DIAGNOSTIC_KEY_PATTERN.fullmatch(
                        actual_rolling_serializer_field_name
                    )
                ):
                    invalid_signature_components.append("rolling_serializer_signature")
                    invalid_rolling_serializer_signatures.append(
                        actual_rolling_serializer_signature
                    )
                if (
                    actual_rolling_serializer_signature
                    != expected_rolling_serializer_signature
                ):
                    mismatched_signature_components.append(
                        "rolling_serializer_signature"
                    )
                    mismatched_rolling_serializer_signatures.append(
                        actual_rolling_serializer_signature
                    )

            inconsistent_signature_component_count = len(
                {
                    *missing_signature_components,
                    *invalid_signature_components,
                    *mismatched_signature_components,
                    *duplicate_signature_components,
                    *conflicting_signature_components,
                }
            )
            consistency_percentage = round(
                max(0.0, ((6 - inconsistent_signature_component_count) / 6) * 100.0),
                2,
            )

            if inconsistent_signature_component_count == 0:
                consistency_classification = "consistent"
                consistent_diagnostic_count += 1
                diagnostic = (
                    "Contract, builder, serializer, route, and rolling signatures remained aligned for this source diagnostic contract."
                )
            elif inconsistent_signature_component_count <= 2:
                consistency_classification = "partial"
                partial_diagnostic_count += 1
                diagnostic = (
                    "Full-surface contract signature consistency was partial because one or two signature surfaces diverged from the normalized contract expectation."
                )
            else:
                consistency_classification = "degraded"
                degraded_diagnostic_count += 1
                diagnostic = (
                    "Full-surface contract signature consistency was degraded because multiple signature surfaces diverged from the normalized contract expectation."
                )

            entries.append(
                SnapshotReplayFullSurfaceContractSignatureConsistencyEntry(
                    diagnostic_slug=slug,
                    expected_contract_signature=expected_contract_signature,
                    actual_contract_signature=actual_contract_signature,
                    expected_service_builder_signature=expected_service_builder_signature,
                    actual_service_builder_signature=actual_service_builder_signature,
                    expected_serializer_signature=expected_serializer_signature,
                    actual_serializer_signature=actual_serializer_signature,
                    expected_api_route_signature=expected_api_route_signature,
                    actual_api_route_signature=actual_api_route_signature,
                    expected_rolling_bundle_signature=expected_rolling_bundle_signature,
                    actual_rolling_bundle_signature=actual_rolling_bundle_signature,
                    expected_rolling_serializer_signature=expected_rolling_serializer_signature,
                    actual_rolling_serializer_signature=actual_rolling_serializer_signature,
                    expected_full_surface_signature=expected_full_surface_signature,
                    actual_full_surface_signature=actual_full_surface_signature,
                    service_builder_surface_present=service_builder_surface_present,
                    serializer_surface_present=serializer_surface_present,
                    api_route_surface_present=api_route_surface_present,
                    rolling_bundle_surface_present=rolling_bundle_surface_present,
                    rolling_serializer_surface_present=rolling_serializer_surface_present,
                    missing_signature_components=tuple(missing_signature_components),
                    invalid_signature_components=tuple(invalid_signature_components),
                    mismatched_signature_components=tuple(
                        mismatched_signature_components
                    ),
                    duplicate_signature_components=tuple(
                        duplicate_signature_components
                    ),
                    conflicting_signature_components=tuple(
                        conflicting_signature_components
                    ),
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
            f"Full-surface contract signature consistency is {consistency_classification} across {total_diagnostics_registered} registered source diagnostic contract(s)."
        ]
        if missing_contract_signatures or missing_service_builder_signatures:
            diagnostics.append(
                "At least one expected contract signature component was missing from the explicit runtime contract surfaces."
            )
        if mismatched_contract_signatures or mismatched_service_builder_signatures:
            diagnostics.append(
                "One or more contract signature surfaces diverged from their normalized contract expectation."
            )
        if conflicting_signature_records:
            diagnostics.append(
                f"{len(conflicting_signature_records)} conflicting signature record(s) were detected across normalized contract surfaces."
            )

        return SnapshotReplayFullSurfaceContractSignatureConsistency(
            consistency_classification=consistency_classification,
            consistency_percentage=consistency_percentage,
            total_diagnostics_registered=total_diagnostics_registered,
            consistent_diagnostic_count=consistent_diagnostic_count,
            partial_diagnostic_count=partial_diagnostic_count,
            degraded_diagnostic_count=degraded_diagnostic_count,
            missing_signature_component_count=sum(
                len(entry.missing_signature_components) for entry in entries
            ),
            invalid_signature_component_count=sum(
                len(entry.invalid_signature_components) for entry in entries
            ),
            mismatched_signature_component_count=sum(
                len(entry.mismatched_signature_components) for entry in entries
            ),
            duplicate_signature_record_count=len(duplicate_signature_records),
            conflicting_signature_record_count=len(conflicting_signature_records),
            missing_contract_signatures=tuple(sorted(set(missing_contract_signatures))),
            invalid_contract_signatures=tuple(sorted(set(invalid_contract_signatures))),
            mismatched_contract_signatures=tuple(
                sorted(set(mismatched_contract_signatures))
            ),
            missing_service_builder_signatures=tuple(
                sorted(set(missing_service_builder_signatures))
            ),
            invalid_service_builder_signatures=tuple(
                sorted(set(invalid_service_builder_signatures))
            ),
            mismatched_service_builder_signatures=tuple(
                sorted(set(mismatched_service_builder_signatures))
            ),
            missing_serializer_signatures=tuple(
                sorted(set(missing_serializer_signatures))
            ),
            invalid_serializer_signatures=tuple(
                sorted(set(invalid_serializer_signatures))
            ),
            mismatched_serializer_signatures=tuple(
                sorted(set(mismatched_serializer_signatures))
            ),
            missing_api_route_signatures=tuple(
                sorted(set(missing_api_route_signatures))
            ),
            invalid_api_route_signatures=tuple(
                sorted(set(invalid_api_route_signatures))
            ),
            mismatched_api_route_signatures=tuple(
                sorted(set(mismatched_api_route_signatures))
            ),
            missing_rolling_bundle_signatures=tuple(
                sorted(set(missing_rolling_bundle_signatures))
            ),
            invalid_rolling_bundle_signatures=tuple(
                sorted(set(invalid_rolling_bundle_signatures))
            ),
            mismatched_rolling_bundle_signatures=tuple(
                sorted(set(mismatched_rolling_bundle_signatures))
            ),
            missing_rolling_serializer_signatures=tuple(
                sorted(set(missing_rolling_serializer_signatures))
            ),
            invalid_rolling_serializer_signatures=tuple(
                sorted(set(invalid_rolling_serializer_signatures))
            ),
            mismatched_rolling_serializer_signatures=tuple(
                sorted(set(mismatched_rolling_serializer_signatures))
            ),
            duplicate_signature_records=tuple(sorted(duplicate_signature_records)),
            conflicting_signature_records=tuple(sorted(conflicting_signature_records)),
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostic_contract_signature_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplaySourceDiagnosticContractSignatureDrift:
        signature_consistency = (
            self._build_full_surface_contract_signature_consistency()
        )
        severity_score = min(
            100,
            signature_consistency.missing_signature_component_count * 10
            + signature_consistency.invalid_signature_component_count * 15
            + signature_consistency.mismatched_signature_component_count * 10
            + signature_consistency.duplicate_signature_record_count * 10
            + signature_consistency.conflicting_signature_record_count * 20,
        )
        diagnostics: list[str] = []

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostic contract signature drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic contract signature drift analysis."
                )
            return SnapshotReplaySourceDiagnosticContractSignatureDrift(
                drift_classification="insufficient_data",
                average_consistency_percentage=signature_consistency.consistency_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                missing_signature_component_count=signature_consistency.missing_signature_component_count,
                invalid_signature_component_count=signature_consistency.invalid_signature_component_count,
                mismatched_signature_component_count=signature_consistency.mismatched_signature_component_count,
                duplicate_signature_record_count=signature_consistency.duplicate_signature_record_count,
                conflicting_signature_record_count=signature_consistency.conflicting_signature_record_count,
                missing_contract_signatures=signature_consistency.missing_contract_signatures,
                invalid_contract_signatures=signature_consistency.invalid_contract_signatures,
                mismatched_contract_signatures=signature_consistency.mismatched_contract_signatures,
                missing_service_builder_signatures=signature_consistency.missing_service_builder_signatures,
                invalid_service_builder_signatures=signature_consistency.invalid_service_builder_signatures,
                mismatched_service_builder_signatures=signature_consistency.mismatched_service_builder_signatures,
                missing_serializer_signatures=signature_consistency.missing_serializer_signatures,
                invalid_serializer_signatures=signature_consistency.invalid_serializer_signatures,
                mismatched_serializer_signatures=signature_consistency.mismatched_serializer_signatures,
                missing_api_route_signatures=signature_consistency.missing_api_route_signatures,
                invalid_api_route_signatures=signature_consistency.invalid_api_route_signatures,
                mismatched_api_route_signatures=signature_consistency.mismatched_api_route_signatures,
                missing_rolling_bundle_signatures=signature_consistency.missing_rolling_bundle_signatures,
                invalid_rolling_bundle_signatures=signature_consistency.invalid_rolling_bundle_signatures,
                mismatched_rolling_bundle_signatures=signature_consistency.mismatched_rolling_bundle_signatures,
                missing_rolling_serializer_signatures=signature_consistency.missing_rolling_serializer_signatures,
                invalid_rolling_serializer_signatures=signature_consistency.invalid_rolling_serializer_signatures,
                mismatched_rolling_serializer_signatures=signature_consistency.mismatched_rolling_serializer_signatures,
                duplicate_signature_records=signature_consistency.duplicate_signature_records,
                conflicting_signature_records=signature_consistency.conflicting_signature_records,
                full_surface_contract_signature_consistency=signature_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if signature_consistency.consistency_classification == "consistent":
            entry_drift_classification = "stable"
        elif signature_consistency.consistency_classification == "partial":
            entry_drift_classification = "drifting"
        elif signature_consistency.consistency_classification == "degraded":
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplaySourceDiagnosticContractSignatureDriftEntry] = []
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
                    "Source diagnostic contract signatures remained stable for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract signatures drifted because one or two normalized signature surfaces diverged."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract signatures were degraded because multiple normalized signature surfaces diverged."
                )
            else:
                diagnostic = (
                    "Source diagnostic contract signatures could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplaySourceDiagnosticContractSignatureDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    consistency_percentage=signature_consistency.consistency_percentage,
                    total_diagnostics_registered=signature_consistency.total_diagnostics_registered,
                    missing_signature_component_count=signature_consistency.missing_signature_component_count,
                    invalid_signature_component_count=signature_consistency.invalid_signature_component_count,
                    mismatched_signature_component_count=signature_consistency.mismatched_signature_component_count,
                    duplicate_signature_record_count=signature_consistency.duplicate_signature_record_count,
                    conflicting_signature_record_count=signature_consistency.conflicting_signature_record_count,
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
            f"Source diagnostic contract signature drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(signature_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic contract signature drift analysis."
            )

        return SnapshotReplaySourceDiagnosticContractSignatureDrift(
            drift_classification=drift_classification,
            average_consistency_percentage=signature_consistency.consistency_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            missing_signature_component_count=signature_consistency.missing_signature_component_count,
            invalid_signature_component_count=signature_consistency.invalid_signature_component_count,
            mismatched_signature_component_count=signature_consistency.mismatched_signature_component_count,
            duplicate_signature_record_count=signature_consistency.duplicate_signature_record_count,
            conflicting_signature_record_count=signature_consistency.conflicting_signature_record_count,
            missing_contract_signatures=signature_consistency.missing_contract_signatures,
            invalid_contract_signatures=signature_consistency.invalid_contract_signatures,
            mismatched_contract_signatures=signature_consistency.mismatched_contract_signatures,
            missing_service_builder_signatures=signature_consistency.missing_service_builder_signatures,
            invalid_service_builder_signatures=signature_consistency.invalid_service_builder_signatures,
            mismatched_service_builder_signatures=signature_consistency.mismatched_service_builder_signatures,
            missing_serializer_signatures=signature_consistency.missing_serializer_signatures,
            invalid_serializer_signatures=signature_consistency.invalid_serializer_signatures,
            mismatched_serializer_signatures=signature_consistency.mismatched_serializer_signatures,
            missing_api_route_signatures=signature_consistency.missing_api_route_signatures,
            invalid_api_route_signatures=signature_consistency.invalid_api_route_signatures,
            mismatched_api_route_signatures=signature_consistency.mismatched_api_route_signatures,
            missing_rolling_bundle_signatures=signature_consistency.missing_rolling_bundle_signatures,
            invalid_rolling_bundle_signatures=signature_consistency.invalid_rolling_bundle_signatures,
            mismatched_rolling_bundle_signatures=signature_consistency.mismatched_rolling_bundle_signatures,
            missing_rolling_serializer_signatures=signature_consistency.missing_rolling_serializer_signatures,
            invalid_rolling_serializer_signatures=signature_consistency.invalid_rolling_serializer_signatures,
            mismatched_rolling_serializer_signatures=signature_consistency.mismatched_rolling_serializer_signatures,
            duplicate_signature_records=signature_consistency.duplicate_signature_records,
            conflicting_signature_records=signature_consistency.conflicting_signature_records,
            full_surface_contract_signature_consistency=signature_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistrySignaturesMixin"]
