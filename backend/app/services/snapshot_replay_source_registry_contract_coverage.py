from __future__ import annotations

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    SnapshotReplayDiagnosticEndpointCoverageConsistency,
    SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry,
    SnapshotReplaySourceDiagnosticsContractCoverageDrift,
    SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry,
)
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any


class SnapshotReplaySourceRegistryContractCoverageMixin:
    def _build_source_diagnostic_endpoint_coverage_consistency(
        self,
    ) -> SnapshotReplayDiagnosticEndpointCoverageConsistency:
        service_slug_set = set(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS)
        route_slug_set = set(source_diagnostic_contracts.SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS)
        serializer_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS
        )
        registered_slugs = tuple(
            sorted(service_slug_set | route_slug_set | serializer_slug_set)
        )

        if not registered_slugs:
            return SnapshotReplayDiagnosticEndpointCoverageConsistency(
                consistency_classification="insufficient_data",
                consistency_percentage=0.0,
                total_diagnostics_registered=0,
                service_builder_count=0,
                api_route_count=0,
                serializer_count=0,
                consistent_diagnostic_count=0,
                partial_diagnostic_count=0,
                degraded_diagnostic_count=0,
                missing_service_builder_names=(),
                missing_api_route_paths=(),
                missing_serializer_names=(),
                entries=(),
                diagnostics=(
                    "No source diagnostic contracts were registered for endpoint coverage consistency analysis.",
                ),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry] = []
        missing_service_builder_names: list[str] = []
        missing_api_route_paths: list[str] = []
        missing_serializer_names: list[str] = []
        consistent_diagnostic_count = 0
        partial_diagnostic_count = 0
        degraded_diagnostic_count = 0

        for slug in registered_slugs:
            diagnostic_key = source_diagnostic_contracts.snapshot_replay_source_diagnostic_key(
                slug
            )
            diagnostic_group = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_group(
                    slug
                )
            )
            service_builder_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                    slug
                )
            )
            api_route_path = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_route_path(
                    slug
                )
            )
            serializer_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_serializer_name(
                    slug
                )
            )

            service_builder_present = slug in service_slug_set and callable(
                getattr(self, service_builder_name, None)
            )
            api_route_present = slug in route_slug_set
            serializer_present = slug in serializer_slug_set

            consistency_percentage = round(
                (50.0 if service_builder_present else 0.0)
                + (25.0 if api_route_present else 0.0)
                + (25.0 if serializer_present else 0.0),
                2,
            )

            if service_builder_present and api_route_present and serializer_present:
                consistency_classification = "consistent"
                consistent_diagnostic_count += 1
                diagnostic = (
                    "Service builder, API route, and serializer coverage remained aligned for this source diagnostic contract."
                )
            elif service_builder_present and (api_route_present or serializer_present):
                consistency_classification = "partial"
                partial_diagnostic_count += 1
                diagnostic = (
                    "Source diagnostic contract coverage was partial because one API exposure surface was missing."
                )
            else:
                consistency_classification = "degraded"
                degraded_diagnostic_count += 1
                diagnostic = (
                    "Source diagnostic contract coverage was degraded because service, route, or serializer coverage diverged."
                )

            if not service_builder_present:
                missing_service_builder_names.append(service_builder_name)
            if not api_route_present:
                missing_api_route_paths.append(api_route_path)
            if not serializer_present:
                missing_serializer_names.append(serializer_name)

            entries.append(
                SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry(
                    diagnostic_key=diagnostic_key,
                    diagnostic_group=diagnostic_group,
                    service_builder_name=service_builder_name,
                    api_route_path=api_route_path,
                    serializer_name=serializer_name,
                    service_builder_present=service_builder_present,
                    api_route_present=api_route_present,
                    serializer_present=serializer_present,
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
            f"Replay diagnostic endpoint coverage consistency is {consistency_classification} across {total_diagnostics_registered} registered source diagnostic contract(s)."
        ]
        if missing_service_builder_names:
            diagnostics.append(
                f"{len(set(missing_service_builder_names))} source diagnostic builder(s) were missing from the current service contract coverage."
            )
        if missing_api_route_paths:
            diagnostics.append(
                f"{len(set(missing_api_route_paths))} source diagnostic route(s) were missing from the explicit API coverage registry."
            )
        if missing_serializer_names:
            diagnostics.append(
                f"{len(set(missing_serializer_names))} source diagnostic serializer(s) were missing from the explicit serializer coverage registry."
            )

        return SnapshotReplayDiagnosticEndpointCoverageConsistency(
            consistency_classification=consistency_classification,
            consistency_percentage=consistency_percentage,
            total_diagnostics_registered=total_diagnostics_registered,
            service_builder_count=sum(1 for entry in entries if entry.service_builder_present),
            api_route_count=sum(1 for entry in entries if entry.api_route_present),
            serializer_count=sum(1 for entry in entries if entry.serializer_present),
            consistent_diagnostic_count=consistent_diagnostic_count,
            partial_diagnostic_count=partial_diagnostic_count,
            degraded_diagnostic_count=degraded_diagnostic_count,
            missing_service_builder_names=tuple(sorted(set(missing_service_builder_names))),
            missing_api_route_paths=tuple(sorted(set(missing_api_route_paths))),
            missing_serializer_names=tuple(sorted(set(missing_serializer_names))),
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_source_diagnostics_contract_coverage_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplaySourceDiagnosticsContractCoverageDrift:
        endpoint_coverage_consistency = (
            self._build_source_diagnostic_endpoint_coverage_consistency()
        )
        diagnostics: list[str] = []
        severity_score = min(
            100,
            len(endpoint_coverage_consistency.missing_service_builder_names) * 50
            + len(endpoint_coverage_consistency.missing_api_route_paths) * 25
            + len(endpoint_coverage_consistency.missing_serializer_names) * 25,
        )

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics contract coverage drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics contract coverage drift analysis."
                )
            return SnapshotReplaySourceDiagnosticsContractCoverageDrift(
                drift_classification="insufficient_data",
                average_coverage_percentage=endpoint_coverage_consistency.consistency_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                missing_service_builder_names=endpoint_coverage_consistency.missing_service_builder_names,
                missing_api_route_paths=endpoint_coverage_consistency.missing_api_route_paths,
                missing_serializer_names=endpoint_coverage_consistency.missing_serializer_names,
                endpoint_coverage_consistency=endpoint_coverage_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if endpoint_coverage_consistency.consistency_classification == "consistent":
            entry_drift_classification = "stable"
        elif endpoint_coverage_consistency.consistency_classification == "partial":
            entry_drift_classification = "drifting"
        elif endpoint_coverage_consistency.consistency_classification == "degraded":
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry] = []
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
                    "Source diagnostic contract coverage remained stable for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract coverage drifted because one API exposure surface was incomplete."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Source diagnostic contract coverage was degraded because service, route, or serializer coverage diverged."
                )
            else:
                diagnostic = (
                    "Source diagnostic contract coverage could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    coverage_percentage=endpoint_coverage_consistency.consistency_percentage,
                    total_diagnostics_registered=endpoint_coverage_consistency.total_diagnostics_registered,
                    covered_service_builder_count=endpoint_coverage_consistency.service_builder_count,
                    covered_api_route_count=endpoint_coverage_consistency.api_route_count,
                    covered_serializer_count=endpoint_coverage_consistency.serializer_count,
                    missing_service_builder_count=len(
                        endpoint_coverage_consistency.missing_service_builder_names
                    ),
                    missing_api_route_count=len(
                        endpoint_coverage_consistency.missing_api_route_paths
                    ),
                    missing_serializer_count=len(
                        endpoint_coverage_consistency.missing_serializer_names
                    ),
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
            f"Source diagnostics contract coverage drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(endpoint_coverage_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics contract coverage drift analysis."
            )

        return SnapshotReplaySourceDiagnosticsContractCoverageDrift(
            drift_classification=drift_classification,
            average_coverage_percentage=endpoint_coverage_consistency.consistency_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            missing_service_builder_names=endpoint_coverage_consistency.missing_service_builder_names,
            missing_api_route_paths=endpoint_coverage_consistency.missing_api_route_paths,
            missing_serializer_names=endpoint_coverage_consistency.missing_serializer_names,
            endpoint_coverage_consistency=endpoint_coverage_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryContractCoverageMixin"]
