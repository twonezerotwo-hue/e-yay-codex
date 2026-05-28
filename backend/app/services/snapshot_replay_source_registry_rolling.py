from __future__ import annotations

from . import snapshot_replay_source_diagnostic_contracts as source_diagnostic_contracts
from app.services.snapshot_replay_models import (
    RollingBacktestDiagnostics,
    SnapshotReplayDedicatedRollingDiagnosticConsistency,
    SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry,
    SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift,
    SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry,
)
from app.services.snapshot_replay_source_common import Any, Mapping, UTC, datetime


class SnapshotReplaySourceRegistryRollingMixin:
    def _build_dedicated_rolling_diagnostic_consistency(
        self,
    ) -> SnapshotReplayDedicatedRollingDiagnosticConsistency:
        dedicated_service_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERVICE_SLUGS
        )
        dedicated_route_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS
        )
        dedicated_serializer_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS
        )
        rolling_bundle_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS
        )
        rolling_serializer_slug_set = set(
            source_diagnostic_contracts.SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS
        )
        registered_slugs = tuple(
            sorted(
                dedicated_service_slug_set
                | dedicated_route_slug_set
                | dedicated_serializer_slug_set
                | rolling_bundle_slug_set
                | rolling_serializer_slug_set
            )
        )
        rolling_bundle_field_names = frozenset(
            RollingBacktestDiagnostics.__annotations__.keys()
        )

        if not registered_slugs:
            return SnapshotReplayDedicatedRollingDiagnosticConsistency(
                consistency_classification="insufficient_data",
                consistency_percentage=0.0,
                total_diagnostics_registered=0,
                dedicated_service_builder_count=0,
                dedicated_api_route_count=0,
                dedicated_serializer_count=0,
                rolling_bundle_count=0,
                rolling_serializer_count=0,
                consistent_diagnostic_count=0,
                partial_diagnostic_count=0,
                degraded_diagnostic_count=0,
                missing_dedicated_service_builder_names=(),
                missing_dedicated_api_route_paths=(),
                missing_dedicated_serializer_names=(),
                missing_rolling_bundle_field_names=(),
                missing_rolling_serializer_field_names=(),
                entries=(),
                diagnostics=(
                    "No dedicated-versus-rolling source diagnostic contracts were registered for bundle coverage consistency analysis.",
                ),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry] = []
        missing_dedicated_service_builder_names: list[str] = []
        missing_dedicated_api_route_paths: list[str] = []
        missing_dedicated_serializer_names: list[str] = []
        missing_rolling_bundle_field_names: list[str] = []
        missing_rolling_serializer_field_names: list[str] = []
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
            dedicated_service_builder_name = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_builder_name(
                    slug
                )
            )
            dedicated_api_route_path = (
                source_diagnostic_contracts.snapshot_replay_source_diagnostic_route_path(
                    slug
                )
            )
            dedicated_serializer_name = (
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

            dedicated_service_builder_present = slug in dedicated_service_slug_set and callable(
                getattr(self, dedicated_service_builder_name, None)
            )
            dedicated_api_route_present = slug in dedicated_route_slug_set
            dedicated_serializer_present = slug in dedicated_serializer_slug_set
            rolling_bundle_present = (
                slug in rolling_bundle_slug_set
                and rolling_bundle_field_name in rolling_bundle_field_names
            )
            rolling_serializer_present = slug in rolling_serializer_slug_set

            consistency_percentage = round(
                (20.0 if dedicated_service_builder_present else 0.0)
                + (20.0 if dedicated_api_route_present else 0.0)
                + (20.0 if dedicated_serializer_present else 0.0)
                + (20.0 if rolling_bundle_present else 0.0)
                + (20.0 if rolling_serializer_present else 0.0),
                2,
            )

            all_dedicated_present = (
                dedicated_service_builder_present
                and dedicated_api_route_present
                and dedicated_serializer_present
            )
            all_rolling_present = rolling_bundle_present and rolling_serializer_present

            if all_dedicated_present and all_rolling_present:
                consistency_classification = "consistent"
                consistent_diagnostic_count += 1
                diagnostic = (
                    "Dedicated service, API, serializer, and rolling bundle coverage remained aligned for this source diagnostic."
                )
            elif (all_dedicated_present and not all_rolling_present) or (
                all_rolling_present and not all_dedicated_present
            ):
                consistency_classification = "partial"
                partial_diagnostic_count += 1
                if all_dedicated_present:
                    diagnostic = (
                        "Dedicated source diagnostic coverage was complete, but rolling bundle exposure was incomplete."
                    )
                else:
                    diagnostic = (
                        "Rolling bundle exposure was present, but dedicated service or API contract coverage was incomplete."
                    )
            else:
                consistency_classification = "degraded"
                degraded_diagnostic_count += 1
                diagnostic = (
                    "Dedicated-versus-rolling source diagnostic coverage was degraded because multiple contract surfaces diverged."
                )

            if not dedicated_service_builder_present:
                missing_dedicated_service_builder_names.append(
                    dedicated_service_builder_name
                )
            if not dedicated_api_route_present:
                missing_dedicated_api_route_paths.append(dedicated_api_route_path)
            if not dedicated_serializer_present:
                missing_dedicated_serializer_names.append(dedicated_serializer_name)
            if not rolling_bundle_present:
                missing_rolling_bundle_field_names.append(rolling_bundle_field_name)
            if not rolling_serializer_present:
                missing_rolling_serializer_field_names.append(
                    rolling_serializer_field_name
                )

            entries.append(
                SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry(
                    diagnostic_key=diagnostic_key,
                    diagnostic_group=diagnostic_group,
                    dedicated_service_builder_name=dedicated_service_builder_name,
                    dedicated_api_route_path=dedicated_api_route_path,
                    dedicated_serializer_name=dedicated_serializer_name,
                    rolling_bundle_field_name=rolling_bundle_field_name,
                    rolling_serializer_field_name=rolling_serializer_field_name,
                    dedicated_service_builder_present=dedicated_service_builder_present,
                    dedicated_api_route_present=dedicated_api_route_present,
                    dedicated_serializer_present=dedicated_serializer_present,
                    rolling_bundle_present=rolling_bundle_present,
                    rolling_serializer_present=rolling_serializer_present,
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
            f"Dedicated-versus-rolling replay diagnostic consistency is {consistency_classification} across {total_diagnostics_registered} registered source diagnostic contract(s)."
        ]
        if missing_dedicated_service_builder_names:
            diagnostics.append(
                f"{len(set(missing_dedicated_service_builder_names))} dedicated source diagnostic builder(s) were missing from the current service contract coverage."
            )
        if missing_dedicated_api_route_paths:
            diagnostics.append(
                f"{len(set(missing_dedicated_api_route_paths))} dedicated source diagnostic route(s) were missing from the explicit API coverage registry."
            )
        if missing_dedicated_serializer_names:
            diagnostics.append(
                f"{len(set(missing_dedicated_serializer_names))} dedicated source diagnostic serializer(s) were missing from the explicit serializer coverage registry."
            )
        if missing_rolling_bundle_field_names:
            diagnostics.append(
                f"{len(set(missing_rolling_bundle_field_names))} rolling source diagnostic field(s) were missing from the rolling replay bundle contract."
            )
        if missing_rolling_serializer_field_names:
            diagnostics.append(
                f"{len(set(missing_rolling_serializer_field_names))} rolling source diagnostic serializer field(s) were missing from the explicit rolling serializer coverage registry."
            )

        return SnapshotReplayDedicatedRollingDiagnosticConsistency(
            consistency_classification=consistency_classification,
            consistency_percentage=consistency_percentage,
            total_diagnostics_registered=total_diagnostics_registered,
            dedicated_service_builder_count=sum(
                1 for entry in entries if entry.dedicated_service_builder_present
            ),
            dedicated_api_route_count=sum(
                1 for entry in entries if entry.dedicated_api_route_present
            ),
            dedicated_serializer_count=sum(
                1 for entry in entries if entry.dedicated_serializer_present
            ),
            rolling_bundle_count=sum(
                1 for entry in entries if entry.rolling_bundle_present
            ),
            rolling_serializer_count=sum(
                1 for entry in entries if entry.rolling_serializer_present
            ),
            consistent_diagnostic_count=consistent_diagnostic_count,
            partial_diagnostic_count=partial_diagnostic_count,
            degraded_diagnostic_count=degraded_diagnostic_count,
            missing_dedicated_service_builder_names=tuple(
                sorted(set(missing_dedicated_service_builder_names))
            ),
            missing_dedicated_api_route_paths=tuple(
                sorted(set(missing_dedicated_api_route_paths))
            ),
            missing_dedicated_serializer_names=tuple(
                sorted(set(missing_dedicated_serializer_names))
            ),
            missing_rolling_bundle_field_names=tuple(
                sorted(set(missing_rolling_bundle_field_names))
            ),
            missing_rolling_serializer_field_names=tuple(
                sorted(set(missing_rolling_serializer_field_names))
            ),
            entries=tuple(entries),
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_rolling_source_diagnostic_bundle_coverage_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift:
        dedicated_rolling_diagnostic_consistency = (
            self._build_dedicated_rolling_diagnostic_consistency()
        )
        diagnostics: list[str] = []
        severity_score = min(
            100,
            len(
                dedicated_rolling_diagnostic_consistency.missing_dedicated_service_builder_names
            )
            * 20
            + len(
                dedicated_rolling_diagnostic_consistency.missing_dedicated_api_route_paths
            )
            * 20
            + len(
                dedicated_rolling_diagnostic_consistency.missing_dedicated_serializer_names
            )
            * 20
            + len(
                dedicated_rolling_diagnostic_consistency.missing_rolling_bundle_field_names
            )
            * 20
            + len(
                dedicated_rolling_diagnostic_consistency.missing_rolling_serializer_field_names
            )
            * 20,
        )

        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for rolling source diagnostic bundle coverage drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during rolling source diagnostic bundle coverage drift analysis."
                )
            return SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift(
                drift_classification="insufficient_data",
                average_coverage_percentage=dedicated_rolling_diagnostic_consistency.consistency_percentage,
                severity_score=severity_score,
                contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                missing_dedicated_service_builder_names=dedicated_rolling_diagnostic_consistency.missing_dedicated_service_builder_names,
                missing_dedicated_api_route_paths=dedicated_rolling_diagnostic_consistency.missing_dedicated_api_route_paths,
                missing_dedicated_serializer_names=dedicated_rolling_diagnostic_consistency.missing_dedicated_serializer_names,
                missing_rolling_bundle_field_names=dedicated_rolling_diagnostic_consistency.missing_rolling_bundle_field_names,
                missing_rolling_serializer_field_names=dedicated_rolling_diagnostic_consistency.missing_rolling_serializer_field_names,
                dedicated_rolling_diagnostic_consistency=dedicated_rolling_diagnostic_consistency,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        if (
            dedicated_rolling_diagnostic_consistency.consistency_classification
            == "consistent"
        ):
            entry_drift_classification = "stable"
        elif (
            dedicated_rolling_diagnostic_consistency.consistency_classification
            == "partial"
        ):
            entry_drift_classification = "drifting"
        elif (
            dedicated_rolling_diagnostic_consistency.consistency_classification
            == "degraded"
        ):
            entry_drift_classification = "degraded"
        else:
            entry_drift_classification = "insufficient_data"

        entries: list[SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry] = []
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
                    "Rolling source diagnostic bundle coverage remained aligned with the dedicated source diagnostic contract for this saved snapshot."
                )
            elif entry_drift_classification == "drifting":
                drifting_snapshots += 1
                diagnostic = (
                    "Rolling source diagnostic bundle coverage drifted because one dedicated or rolling contract surface was incomplete."
                )
            elif entry_drift_classification == "degraded":
                degraded_snapshots += 1
                diagnostic = (
                    "Rolling source diagnostic bundle coverage was degraded because dedicated and rolling diagnostic contract surfaces diverged."
                )
            else:
                diagnostic = (
                    "Rolling source diagnostic bundle coverage could not be classified for this saved snapshot."
                )

            entries.append(
                SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=entry_drift_classification,
                    coverage_percentage=dedicated_rolling_diagnostic_consistency.consistency_percentage,
                    total_diagnostics_registered=dedicated_rolling_diagnostic_consistency.total_diagnostics_registered,
                    covered_dedicated_service_builder_count=dedicated_rolling_diagnostic_consistency.dedicated_service_builder_count,
                    covered_dedicated_api_route_count=dedicated_rolling_diagnostic_consistency.dedicated_api_route_count,
                    covered_dedicated_serializer_count=dedicated_rolling_diagnostic_consistency.dedicated_serializer_count,
                    covered_rolling_bundle_count=dedicated_rolling_diagnostic_consistency.rolling_bundle_count,
                    covered_rolling_serializer_count=dedicated_rolling_diagnostic_consistency.rolling_serializer_count,
                    missing_dedicated_service_builder_count=len(
                        dedicated_rolling_diagnostic_consistency.missing_dedicated_service_builder_names
                    ),
                    missing_dedicated_api_route_count=len(
                        dedicated_rolling_diagnostic_consistency.missing_dedicated_api_route_paths
                    ),
                    missing_dedicated_serializer_count=len(
                        dedicated_rolling_diagnostic_consistency.missing_dedicated_serializer_names
                    ),
                    missing_rolling_bundle_count=len(
                        dedicated_rolling_diagnostic_consistency.missing_rolling_bundle_field_names
                    ),
                    missing_rolling_serializer_count=len(
                        dedicated_rolling_diagnostic_consistency.missing_rolling_serializer_field_names
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
            f"Rolling source diagnostic bundle coverage drift is {drift_classification} across {snapshots_checked} saved snapshot(s)."
        )
        diagnostics.extend(dedicated_rolling_diagnostic_consistency.diagnostics)
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during rolling source diagnostic bundle coverage drift analysis."
            )

        return SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift(
            drift_classification=drift_classification,
            average_coverage_percentage=dedicated_rolling_diagnostic_consistency.consistency_percentage,
            severity_score=severity_score,
            contract_source=source_diagnostic_contracts.SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=0,
            missing_dedicated_service_builder_names=dedicated_rolling_diagnostic_consistency.missing_dedicated_service_builder_names,
            missing_dedicated_api_route_paths=dedicated_rolling_diagnostic_consistency.missing_dedicated_api_route_paths,
            missing_dedicated_serializer_names=dedicated_rolling_diagnostic_consistency.missing_dedicated_serializer_names,
            missing_rolling_bundle_field_names=dedicated_rolling_diagnostic_consistency.missing_rolling_bundle_field_names,
            missing_rolling_serializer_field_names=dedicated_rolling_diagnostic_consistency.missing_rolling_serializer_field_names,
            dedicated_rolling_diagnostic_consistency=dedicated_rolling_diagnostic_consistency,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryRollingMixin"]
