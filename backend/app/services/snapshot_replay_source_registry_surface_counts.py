from __future__ import annotations

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    RollingBacktestDiagnostics,
    SnapshotReplayContractSurfaceCountConsistency,
    SnapshotReplayContractSurfaceCountConsistencyEntry,
    SnapshotReplaySourceDiagnosticSurfaceCountDrift,
    SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry,
)
from app.services.snapshot_replay_source_common import Any, Mapping, UTC, datetime


class SnapshotReplaySourceRegistrySurfaceCountsMixin:
    def _build_contract_surface_count_consistency(
        self,
    ) -> SnapshotReplayContractSurfaceCountConsistency:
        contract_registry_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_GROUP_BY_SLUG.keys()
        )
        contract_group_set = set(
            source_diagnostic_contracts.snapshot_replay_source_diagnostic_contract_groups()
        )
        service_builder_slug_set = {
            slug
            for slug in source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
            if callable(
                getattr(
                    self,
                    source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                        slug
                    ),
                    None,
                )
            )
        }
        api_route_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS
        )
        serializer_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS
        )
        rolling_bundle_field_names = frozenset(
            RollingBacktestDiagnostics.__annotations__.keys()
        )
        rolling_bundle_slug_set = {
            slug
            for slug in source_diagnostic_contracts.SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS
            if source_diagnostic_contracts.snapshot_replay_source_diagnostic_rolling_field_name(
                slug
            )
            in rolling_bundle_field_names
        }

        represented_group_set = (
            contract_group_set
            | set(
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                    service_builder_slug_set
                )
            )
            | set(
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                    api_route_slug_set
                )
            )
            | set(
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                    serializer_slug_set
                )
            )
            | set(
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_groups_for_slugs(
                    rolling_bundle_slug_set
                )
            )
        )
        route_serializer_group_alignment_consistency = (
            self._build_route_serializer_group_alignment_consistency()
        )

        total_diagnostics_registered = len(contract_registry_slug_set)
        total_groups_registered = len(contract_group_set)
        surface_counts = (
            ("contract_registry", total_diagnostics_registered, total_diagnostics_registered),
            ("service_builders", len(service_builder_slug_set), total_diagnostics_registered),
            ("api_routes", len(api_route_slug_set), total_diagnostics_registered),
            ("serializers", len(serializer_slug_set), total_diagnostics_registered),
            ("rolling_bundle", len(rolling_bundle_slug_set), total_diagnostics_registered),
            ("diagnostic_groups", len(represented_group_set), total_groups_registered),
        )

        if not surface_counts:
            return SnapshotReplayContractSurfaceCountConsistency(
                consistency_classification="insufficient_data",
                consistency_percentage=0.0,
                total_surfaces_checked=0,
                total_diagnostics_registered=0,
                total_groups_registered=0,
                contract_registry_count=0,
                service_builder_count=0,
                api_route_count=0,
                serializer_count=0,
                rolling_bundle_count=0,
                diagnostic_group_count=0,
                consistent_surface_count=0,
                mismatched_surface_count=0,
                mismatched_surface_names=(),
                group_alignment_consistency_classification=route_serializer_group_alignment_consistency.consistency_classification,
                group_alignment_clean_but_count_mismatched=False,
                entries=(),
                diagnostics=(
                    "No source diagnostic contract surfaces were registered for surface count consistency analysis.",
                ),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotReplayContractSurfaceCountConsistencyEntry] = []
        consistent_surface_count = 0
        mismatched_surface_names: list[str] = []

        for surface_name, actual_count, expected_count in surface_counts:
            count_delta = actual_count - expected_count
            if expected_count == 0:
                consistency_percentage = 100.0 if actual_count == 0 else 0.0
            else:
                consistency_percentage = round(
                    max(0.0, 100.0 - (abs(count_delta) / expected_count) * 100.0),
                    2,
                )

            if count_delta == 0:
                consistency_classification = "consistent"
                consistent_surface_count += 1
                diagnostic = (
                    f"{surface_name} surface count matched the explicit contract baseline."
                )
            else:
                consistency_classification = "degraded"
                mismatched_surface_names.append(surface_name)
                if count_delta < 0:
                    diagnostic = (
                        f"{surface_name} surface count was lower than the explicit contract baseline by {abs(count_delta)}."
                    )
                else:
                    diagnostic = (
                        f"{surface_name} surface count exceeded the explicit contract baseline by {count_delta}."
                    )

            entries.append(
                SnapshotReplayContractSurfaceCountConsistencyEntry(
                    surface_name=surface_name,
                    expected_count=expected_count,
                    actual_count=actual_count,
                    count_delta=count_delta,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    diagnostic=diagnostic,
                )
            )

        total_surfaces_checked = len(entries)
        mismatched_surface_count = len(mismatched_surface_names)
        consistency_percentage = round(
            sum(entry.consistency_percentage for entry in entries) / total_surfaces_checked,
            2,
        )
        if mismatched_surface_count == 0:
            consistency_classification = "consistent"
        elif mismatched_surface_count == 1:
            consistency_classification = "partial"
        else:
            consistency_classification = "degraded"

        group_alignment_clean_but_count_mismatched = (
            route_serializer_group_alignment_consistency.consistency_classification
            == "consistent"
            and mismatched_surface_count > 0
        )

        diagnostics = [
            f"Replay diagnostic surface count consistency is {consistency_classification} across {total_surfaces_checked} registered contract surface(s)."
        ]
        if mismatched_surface_names:
            diagnostics.append(
                f"{len(set(mismatched_surface_names))} source diagnostic contract surface(s) had count mismatches."
            )
        if group_alignment_clean_but_count_mismatched:
            diagnostics.append(
                "Diagnostic group alignment remained consistent while surface-count consistency drifted."
            )

        return SnapshotReplayContractSurfaceCountConsistency(
            consistency_classification=consistency_classification,
            consistency_percentage=consistency_percentage,
            total_surfaces_checked=total_surfaces_checked,
            total_diagnostics_registered=total_diagnostics_registered,
            total_groups_registered=total_groups_registered,
            contract_registry_count=total_diagnostics_registered,
            service_builder_count=len(service_builder_slug_set),
            api_route_count=len(api_route_slug_set),
            serializer_count=len(serializer_slug_set),
            rolling_bundle_count=len(rolling_bundle_slug_set),
            diagnostic_group_count=len(represented_group_set),
            consistent_surface_count=consistent_surface_count,
            mismatched_surface_count=mismatched_surface_count,
            mismatched_surface_names=tuple(sorted(set(mismatched_surface_names))),
            group_alignment_consistency_classification=route_serializer_group_alignment_consistency.consistency_classification,
            group_alignment_clean_but_count_mismatched=group_alignment_clean_but_count_mismatched,
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_source_diagnostic_surface_count_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplaySourceDiagnosticSurfaceCountDrift:
        contract_surface_count_consistency = (
            self._build_contract_surface_count_consistency()
        )
        diagnostics: list[str] = []
        severity_score = min(
            100,
            contract_surface_count_consistency.mismatched_surface_count * 25,
        )

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostic surface count drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic surface count drift analysis."
                )
            return SnapshotReplaySourceDiagnosticSurfaceCountDrift(
                drift_classification="insufficient_data",
                average_consistency_percentage=contract_surface_count_consistency.consistency_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                mismatched_surface_names=contract_surface_count_consistency.mismatched_surface_names,
                group_alignment_consistency_classification=contract_surface_count_consistency.group_alignment_consistency_classification,
                group_alignment_clean_but_count_mismatched=contract_surface_count_consistency.group_alignment_clean_but_count_mismatched,
                contract_surface_count_consistency=contract_surface_count_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if contract_surface_count_consistency.consistency_classification == "consistent":
            entry_drift_classification = "stable"
        elif contract_surface_count_consistency.consistency_classification == "partial":
            entry_drift_classification = "drifting"
        elif contract_surface_count_consistency.consistency_classification == "degraded":
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry] = []
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
                    "Source diagnostic surface counts remained stable for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Source diagnostic surface counts drifted because one contract surface count was incomplete."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Source diagnostic surface counts were degraded because multiple contract surface counts diverged."
                )
            else:
                diagnostic = (
                    "Source diagnostic surface counts could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    consistency_percentage=contract_surface_count_consistency.consistency_percentage,
                    total_surfaces_checked=contract_surface_count_consistency.total_surfaces_checked,
                    total_diagnostics_registered=contract_surface_count_consistency.total_diagnostics_registered,
                    total_groups_registered=contract_surface_count_consistency.total_groups_registered,
                    contract_registry_count=contract_surface_count_consistency.contract_registry_count,
                    service_builder_count=contract_surface_count_consistency.service_builder_count,
                    api_route_count=contract_surface_count_consistency.api_route_count,
                    serializer_count=contract_surface_count_consistency.serializer_count,
                    rolling_bundle_count=contract_surface_count_consistency.rolling_bundle_count,
                    diagnostic_group_count=contract_surface_count_consistency.diagnostic_group_count,
                    mismatched_surface_count=contract_surface_count_consistency.mismatched_surface_count,
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
            f"Source diagnostic surface count drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(contract_surface_count_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostic surface count drift analysis."
            )

        return SnapshotReplaySourceDiagnosticSurfaceCountDrift(
            drift_classification=drift_classification,
            average_consistency_percentage=contract_surface_count_consistency.consistency_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            mismatched_surface_names=contract_surface_count_consistency.mismatched_surface_names,
            group_alignment_consistency_classification=contract_surface_count_consistency.group_alignment_consistency_classification,
            group_alignment_clean_but_count_mismatched=contract_surface_count_consistency.group_alignment_clean_but_count_mismatched,
            contract_surface_count_consistency=contract_surface_count_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistrySurfaceCountsMixin"]
