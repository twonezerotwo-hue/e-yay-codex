from __future__ import annotations

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    SnapshotReplayRouteSerializerGroupAlignmentConsistency,
    SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry,
    SnapshotReplaySourceDiagnosticGroupCoverageDrift,
    SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry,
)
from app.services.snapshot_replay_source_common import Any, Mapping, UTC, datetime


class SnapshotReplaySourceRegistryGroupCoverageMixin:
    def _build_route_serializer_group_alignment_consistency(
        self,
    ) -> SnapshotReplayRouteSerializerGroupAlignmentConsistency:
        contract_group_set = set(
            source_diagnostic_contracts.snapshot_replay_source_diagnostic_contract_groups()
        )
        service_group_set = set(
            source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
            )
        )
        route_group_set = set(
            source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                source_diagnostic_contracts.SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS
            )
        )
        serializer_group_set = set(
            source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS
            )
        )
        rolling_bundle_group_set = set(
            source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                source_diagnostic_contracts.SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS
            )
        )
        registered_groups = tuple(
            sorted(
                contract_group_set
                | service_group_set
                | route_group_set
                | serializer_group_set
                | rolling_bundle_group_set
            )
        )

        if not registered_groups:
            return SnapshotReplayRouteSerializerGroupAlignmentConsistency(
                consistency_classification="insufficient_data",
                consistency_percentage=0.0,
                total_groups_registered=0,
                contract_group_count=0,
                service_group_count=0,
                api_route_group_count=0,
                serializer_group_count=0,
                rolling_bundle_group_count=0,
                consistent_group_count=0,
                partial_group_count=0,
                degraded_group_count=0,
                missing_contract_groups=(),
                missing_service_groups=(),
                missing_api_route_groups=(),
                missing_serializer_groups=(),
                missing_rolling_bundle_groups=(),
                entries=(),
                diagnostics=(
                    "No source diagnostic groups were registered for route and serializer group alignment consistency analysis.",
                ),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry] = []
        missing_contract_groups: list[str] = []
        missing_service_groups: list[str] = []
        missing_api_route_groups: list[str] = []
        missing_serializer_groups: list[str] = []
        missing_rolling_bundle_groups: list[str] = []
        consistent_group_count = 0
        partial_group_count = 0
        degraded_group_count = 0

        for diagnostic_group in registered_groups:
            contract_group_present = diagnostic_group in contract_group_set
            service_group_present = diagnostic_group in service_group_set
            api_route_group_present = diagnostic_group in route_group_set
            serializer_group_present = diagnostic_group in serializer_group_set
            rolling_bundle_group_present = diagnostic_group in rolling_bundle_group_set

            present_count = sum(
                (
                    contract_group_present,
                    service_group_present,
                    api_route_group_present,
                    serializer_group_present,
                    rolling_bundle_group_present,
                )
            )
            consistency_percentage = round(present_count * 20.0, 2)

            if present_count == 5:
                consistency_classification = "consistent"
                consistent_group_count += 1
                diagnostic = (
                    "Service, route, serializer, contract, and rolling bundle group coverage remained aligned for this source diagnostic group."
                )
            elif present_count == 4:
                consistency_classification = "partial"
                partial_group_count += 1
                diagnostic = (
                    "Source diagnostic group coverage was partial because one contract surface was missing for this group."
                )
            else:
                consistency_classification = "degraded"
                degraded_group_count += 1
                diagnostic = (
                    "Source diagnostic group coverage was degraded because multiple service, route, serializer, contract, or rolling bundle surfaces diverged for this group."
                )

            if not contract_group_present:
                missing_contract_groups.append(diagnostic_group)
            if not service_group_present:
                missing_service_groups.append(diagnostic_group)
            if not api_route_group_present:
                missing_api_route_groups.append(diagnostic_group)
            if not serializer_group_present:
                missing_serializer_groups.append(diagnostic_group)
            if not rolling_bundle_group_present:
                missing_rolling_bundle_groups.append(diagnostic_group)

            entries.append(
                SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry(
                    diagnostic_group=diagnostic_group,
                    contract_group_present=contract_group_present,
                    service_group_present=service_group_present,
                    api_route_group_present=api_route_group_present,
                    serializer_group_present=serializer_group_present,
                    rolling_bundle_group_present=rolling_bundle_group_present,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    diagnostic=diagnostic,
                )
            )

        total_groups_registered = len(entries)
        consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries)
            / total_groups_registered,
            2,
        )

        if degraded_group_count > 0:
            consistency_classification = "degraded"
        elif partial_group_count > 0:
            consistency_classification = "partial"
        else:
            consistency_classification = "consistent"

        diagnostics = [
            f"Replay diagnostic group coverage consistency is {consistency_classification} across {total_groups_registered} registered source diagnostic group(s)."
        ]
        if missing_contract_groups:
            diagnostics.append(
                f"{len(set(missing_contract_groups))} source diagnostic group(s) were missing from the explicit contract group registry."
            )
        if missing_service_groups:
            diagnostics.append(
                f"{len(set(missing_service_groups))} source diagnostic group(s) were missing from the service group surface."
            )
        if missing_api_route_groups:
            diagnostics.append(
                f"{len(set(missing_api_route_groups))} source diagnostic group(s) were missing from the API route group surface."
            )
        if missing_serializer_groups:
            diagnostics.append(
                f"{len(set(missing_serializer_groups))} source diagnostic group(s) were missing from the serializer group surface."
            )
        if missing_rolling_bundle_groups:
            diagnostics.append(
                f"{len(set(missing_rolling_bundle_groups))} source diagnostic group(s) were missing from the rolling bundle group surface."
            )

        return SnapshotReplayRouteSerializerGroupAlignmentConsistency(
            consistency_classification=consistency_classification,
            consistency_percentage=consistency_percentage,
            total_groups_registered=total_groups_registered,
            contract_group_count=sum(1 for entry in entries if entry.contract_group_present),
            service_group_count=sum(1 for entry in entries if entry.service_group_present),
            api_route_group_count=sum(1 for entry in entries if entry.api_route_group_present),
            serializer_group_count=sum(1 for entry in entries if entry.serializer_group_present),
            rolling_bundle_group_count=sum(
                1 for entry in entries if entry.rolling_bundle_group_present
            ),
            consistent_group_count=consistent_group_count,
            partial_group_count=partial_group_count,
            degraded_group_count=degraded_group_count,
            missing_contract_groups=tuple(sorted(set(missing_contract_groups))),
            missing_service_groups=tuple(sorted(set(missing_service_groups))),
            missing_api_route_groups=tuple(sorted(set(missing_api_route_groups))),
            missing_serializer_groups=tuple(sorted(set(missing_serializer_groups))),
            missing_rolling_bundle_groups=tuple(
                sorted(set(missing_rolling_bundle_groups))
            ),
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_source_diagnostic_group_coverage_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplaySourceDiagnosticGroupCoverageDrift:
        route_serializer_group_alignment_consistency = (
            self._build_route_serializer_group_alignment_consistency()
        )
        diagnostics: list[str] = []
        severity_score = min(
            100,
            len(route_serializer_group_alignment_consistency.missing_contract_groups) * 20
            + len(route_serializer_group_alignment_consistency.missing_service_groups) * 20
            + len(route_serializer_group_alignment_consistency.missing_api_route_groups) * 20
            + len(route_serializer_group_alignment_consistency.missing_serializer_groups) * 20
            + len(route_serializer_group_alignment_consistency.missing_rolling_bundle_groups)
            * 20,
        )

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostic group coverage drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic group coverage drift analysis."
                )
            return SnapshotReplaySourceDiagnosticGroupCoverageDrift(
                drift_classification="insufficient_data",
                average_coverage_percentage=route_serializer_group_alignment_consistency.consistency_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                missing_contract_groups=route_serializer_group_alignment_consistency.missing_contract_groups,
                missing_service_groups=route_serializer_group_alignment_consistency.missing_service_groups,
                missing_api_route_groups=route_serializer_group_alignment_consistency.missing_api_route_groups,
                missing_serializer_groups=route_serializer_group_alignment_consistency.missing_serializer_groups,
                missing_rolling_bundle_groups=route_serializer_group_alignment_consistency.missing_rolling_bundle_groups,
                route_serializer_group_alignment_consistency=route_serializer_group_alignment_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if (
            route_serializer_group_alignment_consistency.consistency_classification
            == "consistent"
        ):
            entry_drift_classification = "stable"
        elif (
            route_serializer_group_alignment_consistency.consistency_classification
            == "partial"
        ):
            entry_drift_classification = "drifting"
        elif (
            route_serializer_group_alignment_consistency.consistency_classification
            == "degraded"
        ):
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry] = []
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
                    "Source diagnostic group coverage remained stable for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Source diagnostic group coverage drifted because one group-level contract surface was incomplete."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Source diagnostic group coverage was degraded because multiple group-level service, route, serializer, contract, or rolling bundle surfaces diverged."
                )
            else:
                diagnostic = (
                    "Source diagnostic group coverage could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    coverage_percentage=route_serializer_group_alignment_consistency.consistency_percentage,
                    total_groups_registered=route_serializer_group_alignment_consistency.total_groups_registered,
                    covered_contract_group_count=route_serializer_group_alignment_consistency.contract_group_count,
                    covered_service_group_count=route_serializer_group_alignment_consistency.service_group_count,
                    covered_api_route_group_count=route_serializer_group_alignment_consistency.api_route_group_count,
                    covered_serializer_group_count=route_serializer_group_alignment_consistency.serializer_group_count,
                    covered_rolling_bundle_group_count=route_serializer_group_alignment_consistency.rolling_bundle_group_count,
                    missing_contract_group_count=len(
                        route_serializer_group_alignment_consistency.missing_contract_groups
                    ),
                    missing_service_group_count=len(
                        route_serializer_group_alignment_consistency.missing_service_groups
                    ),
                    missing_api_route_group_count=len(
                        route_serializer_group_alignment_consistency.missing_api_route_groups
                    ),
                    missing_serializer_group_count=len(
                        route_serializer_group_alignment_consistency.missing_serializer_groups
                    ),
                    missing_rolling_bundle_group_count=len(
                        route_serializer_group_alignment_consistency.missing_rolling_bundle_groups
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
            f"Source diagnostic group coverage drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(route_serializer_group_alignment_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic group coverage drift analysis."
            )

        return SnapshotReplaySourceDiagnosticGroupCoverageDrift(
            drift_classification=drift_classification,
            average_coverage_percentage=route_serializer_group_alignment_consistency.consistency_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            missing_contract_groups=route_serializer_group_alignment_consistency.missing_contract_groups,
            missing_service_groups=route_serializer_group_alignment_consistency.missing_service_groups,
            missing_api_route_groups=route_serializer_group_alignment_consistency.missing_api_route_groups,
            missing_serializer_groups=route_serializer_group_alignment_consistency.missing_serializer_groups,
            missing_rolling_bundle_groups=route_serializer_group_alignment_consistency.missing_rolling_bundle_groups,
            route_serializer_group_alignment_consistency=route_serializer_group_alignment_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryGroupCoverageMixin"]
