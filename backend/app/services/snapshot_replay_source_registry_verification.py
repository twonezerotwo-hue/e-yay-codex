from __future__ import annotations

from app.services.snapshot_replay_source_common import (
    Any,
    EXPECTED_PROVIDER_ADAPTER_CONTRACT,
    Mapping,
    SnapshotPaperSafeSourceFlagConsistency,
    SnapshotPaperSafeSourceFlagConsistencyEntry,
    SnapshotProviderAdapterContractConsistency,
    SnapshotProviderAdapterContractConsistencyEntry,
    SnapshotSourceRegistryBindingDrift,
    SnapshotSourceRegistryBindingDriftEntry,
    SnapshotSourceVerificationDrift,
    SnapshotSourceVerificationDriftEntry,
    UTC,
    datetime,
)


class SnapshotReplaySourceRegistryVerificationMixin:
    def _build_source_registry_binding_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceRegistryBindingDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source registry binding drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source registry binding drift analysis."
                )
            return SnapshotSourceRegistryBindingDrift(
                drift_classification="insufficient_data",
                severity_score=0,
                current_source_registry_version="unknown",
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                registry_version_mismatch_count=0,
                unbound_source_ids=(),
                provider_mismatch_source_ids=(),
                asset_mismatch_source_ids=(),
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
        current_source_registry_version = str(source_registry["version"])
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {entry.source_id: entry for entry in registry_entries}

        entries: list[SnapshotSourceRegistryBindingDriftEntry] = []
        stable_snapshots = 0
        drifting_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        registry_version_mismatch_count = 0
        aggregate_unbound_source_ids: set[str] = set()
        aggregate_provider_mismatch_source_ids: set[str] = set()
        aggregate_asset_mismatch_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get(
                "created_at", datetime.now(UTC).isoformat()
            )
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            snapshot_source_registry_version = str(
                snapshot_payload.get("source_registry_version", "unknown")
            )
            registry_version_mismatch = (
                snapshot_source_registry_version != current_source_registry_version
            )
            if registry_version_mismatch:
                registry_version_mismatch_count += 1

            source_observation_records = snapshot_payload.get(
                "source_observation_records"
            )
            if (
                not isinstance(source_observation_records, list)
                or not source_observation_records
            ):
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceRegistryBindingDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        source_registry_version=snapshot_source_registry_version,
                        registry_version_mismatch=registry_version_mismatch,
                        binding_classification="invalid",
                        total_records=0,
                        matched_records=0,
                        unbound_source_ids=(),
                        provider_mismatch_source_ids=(),
                        asset_mismatch_source_ids=(),
                        malformed_record_count=1,
                        severity_score=100,
                        diagnostic="Source registry binding drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            matched_records = 0
            malformed_record_count = 0
            unbound_source_ids: set[str] = set()
            provider_mismatch_source_ids: set[str] = set()
            asset_mismatch_source_ids: set[str] = set()

            for record_index, record in enumerate(source_observation_records):
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unbound_source_ids.add(source_id)
                    continue

                record_asset_symbol = record.get("asset_symbol")
                if record_asset_symbol != registry_entry.asset.code.value:
                    asset_mismatch_source_ids.add(source_id)

                record_registry_provider = record.get("registry_provider")
                if record_registry_provider != registry_entry.provider:
                    provider_mismatch_source_ids.add(source_id)

                if (
                    source_id not in asset_mismatch_source_ids
                    and source_id not in provider_mismatch_source_ids
                ):
                    matched_records += 1

            severity_score = min(
                100,
                (20 if registry_version_mismatch else 0)
                + len(unbound_source_ids) * 25
                + len(provider_mismatch_source_ids) * 15
                + len(asset_mismatch_source_ids) * 15
                + malformed_record_count * 30,
            )

            if malformed_record_count > 0:
                binding_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    f"Source registry binding drift encountered {malformed_record_count} malformed record(s)."
                )
            elif (
                len(unbound_source_ids)
                + len(provider_mismatch_source_ids)
                + len(asset_mismatch_source_ids)
            ) >= max(2, total_records // 4) or (
                registry_version_mismatch
                and (
                    unbound_source_ids
                    or provider_mismatch_source_ids
                    or asset_mismatch_source_ids
                )
            ):
                binding_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Source registry binding drift was degraded because registry version or source binding mismatches accumulated."
                )
            elif (
                registry_version_mismatch
                or unbound_source_ids
                or provider_mismatch_source_ids
                or asset_mismatch_source_ids
            ):
                binding_classification = "drifting"
                drifting_snapshots += 1
                diagnostic = "Source registry binding drift was detected in this saved snapshot."
            else:
                binding_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "All source observation records matched the current source registry binding."
                )

            aggregate_unbound_source_ids.update(unbound_source_ids)
            aggregate_provider_mismatch_source_ids.update(
                provider_mismatch_source_ids
            )
            aggregate_asset_mismatch_source_ids.update(asset_mismatch_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceRegistryBindingDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    source_registry_version=snapshot_source_registry_version,
                    registry_version_mismatch=registry_version_mismatch,
                    binding_classification=binding_classification,
                    total_records=total_records,
                    matched_records=matched_records,
                    unbound_source_ids=tuple(sorted(unbound_source_ids)),
                    provider_mismatch_source_ids=tuple(
                        sorted(provider_mismatch_source_ids)
                    ),
                    asset_mismatch_source_ids=tuple(sorted(asset_mismatch_source_ids)),
                    malformed_record_count=malformed_record_count,
                    severity_score=severity_score,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if snapshots_checked == 0:
            drift_classification = "insufficient_data"
        elif degraded_snapshots > 0 or invalid_snapshots > 0:
            drift_classification = "degraded"
        elif drifting_snapshots > 0:
            drift_classification = "drifting"
        else:
            drift_classification = "stable"

        severity_score = min(100, sum(entry.severity_score for entry in entries))

        if snapshots_checked == 0:
            diagnostics.append(
                "No saved snapshots were available for source registry binding drift analysis."
            )
        elif drift_classification == "stable":
            diagnostics.append(
                f"Source registry bindings remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "drifting":
            diagnostics.append(
                f"Source registry binding drift was detected across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                f"Source registry binding drift was degraded across {snapshots_checked} saved snapshot(s)."
            )

        if registry_version_mismatch_count > 0:
            diagnostics.append(
                f"{registry_version_mismatch_count} snapshot(s) used a different source registry version than the current registry."
            )
        if aggregate_unbound_source_ids:
            diagnostics.append(
                f"{len(aggregate_unbound_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_provider_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_provider_mismatch_source_ids)} source ID(s) had provider binding mismatches."
            )
        if aggregate_asset_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_asset_mismatch_source_ids)} source ID(s) had asset binding mismatches."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during binding drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source registry binding drift analysis."
            )

        return SnapshotSourceRegistryBindingDrift(
            drift_classification=drift_classification,
            severity_score=severity_score,
            current_source_registry_version=current_source_registry_version,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            registry_version_mismatch_count=registry_version_mismatch_count,
            unbound_source_ids=tuple(sorted(aggregate_unbound_source_ids)),
            provider_mismatch_source_ids=tuple(
                sorted(aggregate_provider_mismatch_source_ids)
            ),
            asset_mismatch_source_ids=tuple(sorted(aggregate_asset_mismatch_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_verification_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceVerificationDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source verification drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source verification drift analysis."
                )
            return SnapshotSourceVerificationDrift(
                drift_classification="insufficient_data",
                average_verification_score=0.0,
                severity_score=0,
                current_source_registry_version="unknown",
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                degraded_source_ids=(),
                improved_source_ids=(),
                missing_verification_source_ids=(),
                unknown_registry_source_ids=(),
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
        current_source_registry_version = str(source_registry["version"])
        registry_entries = build_source_registry_entries(source_registry)
        registry_by_source_id = {entry.source_id: entry for entry in registry_entries}

        entries: list[SnapshotSourceVerificationDriftEntry] = []
        aggregate_degraded_source_ids: set[str] = set()
        aggregate_improved_source_ids: set[str] = set()
        aggregate_missing_verification_source_ids: set[str] = set()
        aggregate_unknown_registry_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get(
                "created_at", datetime.now(UTC).isoformat()
            )
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get(
                "source_observation_records"
            )
            if (
                not isinstance(source_observation_records, list)
                or not source_observation_records
            ):
                insufficient_data_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotSourceVerificationDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        verification_classification="insufficient_data",
                        verification_score=0.0,
                        total_records=0,
                        verified_records=0,
                        expected_verified_records=0,
                        degraded_source_ids=(),
                        improved_source_ids=(),
                        missing_verification_source_ids=(),
                        unknown_registry_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Source verification drift could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            verified_records = 0
            expected_verified_records = 0
            degraded_source_ids: set[str] = set()
            improved_source_ids: set[str] = set()
            missing_verification_source_ids: set[str] = set()
            unknown_registry_source_ids: set[str] = set()
            malformed_record_count = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unknown_registry_source_ids.add(source_id)
                elif registry_entry.verified:
                    expected_verified_records += 1

                raw_verified = record.get("verified")
                if not isinstance(raw_verified, bool):
                    missing_verification_source_ids.add(source_id)
                    continue

                if raw_verified:
                    verified_records += 1

                if registry_entry is None:
                    continue
                if registry_entry.verified and raw_verified is False:
                    degraded_source_ids.add(source_id)
                elif not registry_entry.verified and raw_verified is True:
                    improved_source_ids.add(source_id)

            severity_score = min(
                100,
                len(degraded_source_ids) * 25
                + len(missing_verification_source_ids) * 15
                + len(unknown_registry_source_ids) * 10
                + malformed_record_count * 20,
            )
            verification_score = round(max(0, 100 - severity_score), 2)

            if malformed_record_count >= total_records:
                verification_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                diagnostic = (
                    "Source verification drift was insufficient because all source observation records were malformed."
                )
            elif degraded_source_ids and improved_source_ids:
                verification_classification = "mixed"
                mixed_snapshots += 1
                diagnostic = (
                    "Source verification drift was mixed because degraded and improved verification signals appeared together."
                )
            elif (
                degraded_source_ids
                or missing_verification_source_ids
                or unknown_registry_source_ids
                or malformed_record_count > 0
            ):
                verification_classification = "degrading"
                degrading_snapshots += 1
                diagnostic = (
                    "Source verification drift degraded because verified source trust weakened or verification metadata became incomplete."
                )
            elif improved_source_ids:
                verification_classification = "improving"
                improving_snapshots += 1
                diagnostic = (
                    "Source verification drift improved because previously unverified sources now appear verified."
                )
            else:
                verification_classification = "stable"
                stable_snapshots += 1
                diagnostic = (
                    "Source verification status remained stable for all persisted source observation records."
                )

            aggregate_degraded_source_ids.update(degraded_source_ids)
            aggregate_improved_source_ids.update(improved_source_ids)
            aggregate_missing_verification_source_ids.update(
                missing_verification_source_ids
            )
            aggregate_unknown_registry_source_ids.update(
                unknown_registry_source_ids
            )
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotSourceVerificationDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    verification_classification=verification_classification,
                    verification_score=verification_score,
                    total_records=total_records,
                    verified_records=verified_records,
                    expected_verified_records=expected_verified_records,
                    degraded_source_ids=tuple(sorted(degraded_source_ids)),
                    improved_source_ids=tuple(sorted(improved_source_ids)),
                    missing_verification_source_ids=tuple(
                        sorted(missing_verification_source_ids)
                    ),
                    unknown_registry_source_ids=tuple(
                        sorted(unknown_registry_source_ids)
                    ),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        evaluable_entries = tuple(
            entry
            for entry in entries
            if entry.verification_classification != "insufficient_data"
        )

        if not evaluable_entries:
            drift_classification = "insufficient_data"
            average_verification_score = 0.0
            severity_score = 0
        else:
            scores = [entry.verification_score for entry in evaluable_entries]
            if len(evaluable_entries) == 1:
                drift_classification = evaluable_entries[
                    0
                ].verification_classification
            else:
                non_decreasing = all(
                    scores[index] >= scores[index - 1]
                    for index in range(1, len(scores))
                )
                non_increasing = all(
                    scores[index] <= scores[index - 1]
                    for index in range(1, len(scores))
                )
                has_degrading = any(
                    entry.verification_classification == "degrading"
                    for entry in evaluable_entries
                )
                has_improving = any(
                    entry.verification_classification == "improving"
                    for entry in evaluable_entries
                )
                has_mixed = any(
                    entry.verification_classification == "mixed"
                    for entry in evaluable_entries
                )

                if all(
                    entry.verification_classification == "stable"
                    for entry in evaluable_entries
                ):
                    drift_classification = "stable"
                elif (
                    non_decreasing
                    and scores[-1] > scores[0]
                    and not has_mixed
                    and not (has_degrading and has_improving)
                ):
                    drift_classification = "improving"
                elif (
                    non_increasing
                    and scores[-1] < scores[0]
                    and not has_mixed
                    and not (has_degrading and has_improving)
                ):
                    drift_classification = "degrading"
                elif has_improving and not has_degrading and not has_mixed:
                    drift_classification = "improving"
                elif has_mixed or (has_degrading and has_improving):
                    drift_classification = "mixed"
                elif has_degrading and scores[-1] < scores[0]:
                    drift_classification = "degrading"
                elif has_improving and scores[-1] > scores[0]:
                    drift_classification = "improving"
                elif any(
                    entry.verification_classification != "stable"
                    for entry in evaluable_entries
                ):
                    drift_classification = "mixed"
                else:
                    drift_classification = "stable"

            average_verification_score = round(
                sum(entry.verification_score for entry in evaluable_entries)
                / len(evaluable_entries),
                2,
            )
            severity_score = int(round(100 - evaluable_entries[-1].verification_score))

        if drift_classification == "stable":
            diagnostics.append(
                f"Source verification drift remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source verification drift degraded across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source verification drift improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source verification drift was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source verification drift had insufficient usable data.")

        if aggregate_degraded_source_ids:
            diagnostics.append(
                f"{len(aggregate_degraded_source_ids)} source ID(s) drifted from verified to unverified status."
            )
        if aggregate_improved_source_ids:
            diagnostics.append(
                f"{len(aggregate_improved_source_ids)} source ID(s) improved from unverified to verified status."
            )
        if aggregate_missing_verification_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_verification_source_ids)} source ID(s) were missing usable verification metadata."
            )
        if aggregate_unknown_registry_source_ids:
            diagnostics.append(
                f"{len(aggregate_unknown_registry_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during source verification drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source verification drift analysis."
            )

        return SnapshotSourceVerificationDrift(
            drift_classification=drift_classification,
            average_verification_score=average_verification_score,
            severity_score=severity_score,
            current_source_registry_version=current_source_registry_version,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            degraded_source_ids=tuple(sorted(aggregate_degraded_source_ids)),
            improved_source_ids=tuple(sorted(aggregate_improved_source_ids)),
            missing_verification_source_ids=tuple(
                sorted(aggregate_missing_verification_source_ids)
            ),
            unknown_registry_source_ids=tuple(
                sorted(aggregate_unknown_registry_source_ids)
            ),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_paper_safe_source_flag_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotPaperSafeSourceFlagConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for paper-safe source flag consistency analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during paper-safe source flag consistency analysis."
                )
            return SnapshotPaperSafeSourceFlagConsistency(
                consistency_classification="insufficient_data",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                false_flag_source_ids=(),
                missing_flag_source_ids=(),
                malformed_flag_source_ids=(),
                contradictory_source_ids=(),
                unknown_registry_source_ids=(),
                unsafe_source_ids=(),
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
        registry_by_source_id = {entry.source_id: entry for entry in registry_entries}

        entries: list[SnapshotPaperSafeSourceFlagConsistencyEntry] = []
        aggregate_false_flag_source_ids: set[str] = set()
        aggregate_missing_flag_source_ids: set[str] = set()
        aggregate_malformed_flag_source_ids: set[str] = set()
        aggregate_contradictory_source_ids: set[str] = set()
        aggregate_unknown_registry_source_ids: set[str] = set()
        aggregate_unsafe_source_ids: set[str] = set()
        aggregate_malformed_record_count = 0
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get(
                "created_at", datetime.now(UTC).isoformat()
            )
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            source_observation_records = snapshot_payload.get(
                "source_observation_records"
            )
            if (
                not isinstance(source_observation_records, list)
                or not source_observation_records
            ):
                invalid_snapshots += 1
                aggregate_malformed_record_count += 1
                entries.append(
                    SnapshotPaperSafeSourceFlagConsistencyEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        consistency_classification="invalid",
                        consistency_percentage=0.0,
                        total_records=0,
                        safe_records=0,
                        false_flag_source_ids=(),
                        missing_flag_source_ids=(),
                        malformed_flag_source_ids=(),
                        contradictory_source_ids=(),
                        unknown_registry_source_ids=(),
                        unsafe_source_ids=(),
                        malformed_record_count=1,
                        diagnostic="Paper-safe source flag consistency could not be evaluated because source observation records were missing or malformed.",
                    )
                )
                continue

            total_records = len(source_observation_records)
            safe_records = 0
            false_flag_source_ids: set[str] = set()
            missing_flag_source_ids: set[str] = set()
            malformed_flag_source_ids: set[str] = set()
            contradictory_source_ids: set[str] = set()
            unknown_registry_source_ids: set[str] = set()
            unsafe_source_ids: set[str] = set()
            malformed_record_count = 0

            for record in source_observation_records:
                if not isinstance(record, Mapping):
                    malformed_record_count += 1
                    continue

                raw_source_id = record.get("source_id")
                if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                    malformed_record_count += 1
                    continue
                source_id = raw_source_id.strip()

                registry_entry = registry_by_source_id.get(source_id)
                if registry_entry is None:
                    unknown_registry_source_ids.add(source_id)

                raw_paper_safe = record.get("paper_safe")
                if raw_paper_safe is None:
                    missing_flag_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue
                if not isinstance(raw_paper_safe, bool):
                    malformed_flag_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue
                if raw_paper_safe is False:
                    false_flag_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue

                decision_usage_value = record.get("decision_usage")
                if not isinstance(decision_usage_value, str) or not decision_usage_value.strip():
                    decision_usage = (
                        registry_entry.decision_usage
                        if registry_entry is not None
                        else None
                    )
                else:
                    decision_usage = decision_usage_value.strip()

                verified_value = record.get("verified")
                if verified_value is False and decision_usage == "verified_required":
                    contradictory_source_ids.add(source_id)
                    unsafe_source_ids.add(source_id)
                    continue

                safe_records += 1

            consistency_percentage = (
                round((safe_records / total_records) * 100, 2)
                if total_records
                else 0.0
            )

            if malformed_record_count > 0 or malformed_flag_source_ids:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Paper-safe source flag consistency was invalid because malformed record or flag structures were detected."
                )
            elif false_flag_source_ids or contradictory_source_ids:
                consistency_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Paper-safe source flag consistency was degraded because unsafe or contradictory source flags were detected."
                )
            elif missing_flag_source_ids or unknown_registry_source_ids:
                consistency_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Paper-safe source flag consistency was partial because some source flags or registry bindings were incomplete."
                )
            else:
                consistency_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "All source observation records preserved consistent paper-safe flags."
                )

            aggregate_false_flag_source_ids.update(false_flag_source_ids)
            aggregate_missing_flag_source_ids.update(missing_flag_source_ids)
            aggregate_malformed_flag_source_ids.update(malformed_flag_source_ids)
            aggregate_contradictory_source_ids.update(contradictory_source_ids)
            aggregate_unknown_registry_source_ids.update(
                unknown_registry_source_ids
            )
            aggregate_unsafe_source_ids.update(unsafe_source_ids)
            aggregate_malformed_record_count += malformed_record_count
            entries.append(
                SnapshotPaperSafeSourceFlagConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    total_records=total_records,
                    safe_records=safe_records,
                    false_flag_source_ids=tuple(sorted(false_flag_source_ids)),
                    missing_flag_source_ids=tuple(sorted(missing_flag_source_ids)),
                    malformed_flag_source_ids=tuple(sorted(malformed_flag_source_ids)),
                    contradictory_source_ids=tuple(sorted(contradictory_source_ids)),
                    unknown_registry_source_ids=tuple(
                        sorted(unknown_registry_source_ids)
                    ),
                    unsafe_source_ids=tuple(sorted(unsafe_source_ids)),
                    malformed_record_count=malformed_record_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if snapshots_checked == 0:
            consistency_classification = "insufficient_data"
            average_consistency_percentage = 0.0
        else:
            if invalid_snapshots > 0:
                consistency_classification = "invalid"
            elif degraded_snapshots > 0:
                consistency_classification = "degraded"
            elif partial_snapshots > 0:
                consistency_classification = "partial"
            else:
                consistency_classification = "consistent"

            average_consistency_percentage = round(
                sum(entry.consistency_percentage for entry in entries)
                / snapshots_checked,
                2,
            )

        diagnostics.append(
            f"Paper-safe source flag consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_false_flag_source_ids:
            diagnostics.append(
                f"{len(aggregate_false_flag_source_ids)} source ID(s) were explicitly marked paper_safe=false."
            )
        if aggregate_missing_flag_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_flag_source_ids)} source ID(s) were missing usable paper-safe flags."
            )
        if aggregate_malformed_flag_source_ids:
            diagnostics.append(
                f"{len(aggregate_malformed_flag_source_ids)} source ID(s) had malformed paper-safe flags."
            )
        if aggregate_contradictory_source_ids:
            diagnostics.append(
                f"{len(aggregate_contradictory_source_ids)} source ID(s) had contradictory paper-safe versus verification metadata."
            )
        if aggregate_unknown_registry_source_ids:
            diagnostics.append(
                f"{len(aggregate_unknown_registry_source_ids)} source ID(s) were not present in the current source registry."
            )
        if aggregate_malformed_record_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_record_count} malformed source observation record(s) were detected during paper-safe source flag consistency analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during paper-safe source flag consistency analysis."
            )

        return SnapshotPaperSafeSourceFlagConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            false_flag_source_ids=tuple(sorted(aggregate_false_flag_source_ids)),
            missing_flag_source_ids=tuple(sorted(aggregate_missing_flag_source_ids)),
            malformed_flag_source_ids=tuple(
                sorted(aggregate_malformed_flag_source_ids)
            ),
            contradictory_source_ids=tuple(sorted(aggregate_contradictory_source_ids)),
            unknown_registry_source_ids=tuple(
                sorted(aggregate_unknown_registry_source_ids)
            ),
            unsafe_source_ids=tuple(sorted(aggregate_unsafe_source_ids)),
            malformed_record_count=aggregate_malformed_record_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_provider_adapter_contract_consistency(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotProviderAdapterContractConsistency:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for provider adapter contract consistency analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during provider adapter contract consistency analysis."
                )
            return SnapshotProviderAdapterContractConsistency(
                consistency_classification="insufficient_data",
                average_consistency_percentage=0.0,
                expected_contract=EXPECTED_PROVIDER_ADAPTER_CONTRACT,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_contract_snapshot_ids=(),
                mismatched_contract_snapshot_ids=(),
                bound_source_mismatch_snapshot_ids=(),
                malformed_snapshot_ids=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotProviderAdapterContractConsistencyEntry] = []
        missing_contract_snapshot_ids: list[str] = []
        mismatched_contract_snapshot_ids: list[str] = []
        bound_source_mismatch_snapshot_ids: list[str] = []
        malformed_snapshot_ids: list[str] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get(
                "created_at", datetime.now(UTC).isoformat()
            )
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_observation_summary")
            audit_source_payload = snapshot_payload.get("audit_source_payload")
            provider_adapter = self._read_nested_mapping_value(
                audit_source_payload, "provider_adapter"
            )

            missing_fields: list[str] = []
            mismatched_fields: list[str] = []
            malformed_field_count = 0

            if not isinstance(summary, Mapping):
                malformed_field_count += 1
                source_observation_contract = None
                source_observation_total_bound_sources = None
            else:
                raw_source_observation_contract = summary.get("contract")
                if (
                    not isinstance(raw_source_observation_contract, str)
                    or not raw_source_observation_contract.strip()
                ):
                    source_observation_contract = None
                    missing_fields.append("source_observation_summary.contract")
                else:
                    source_observation_contract = raw_source_observation_contract.strip()

                raw_source_observation_total_bound_sources = summary.get(
                    "total_bound_sources"
                )
                if isinstance(raw_source_observation_total_bound_sources, bool) or (
                    raw_source_observation_total_bound_sources is not None
                    and not isinstance(
                        raw_source_observation_total_bound_sources, int
                    )
                ):
                    source_observation_total_bound_sources = None
                    malformed_field_count += 1
                elif raw_source_observation_total_bound_sources is None:
                    source_observation_total_bound_sources = None
                    missing_fields.append(
                        "source_observation_summary.total_bound_sources"
                    )
                else:
                    source_observation_total_bound_sources = int(
                        raw_source_observation_total_bound_sources
                    )

            if not isinstance(provider_adapter, Mapping):
                provider_adapter_contract = None
                provider_adapter_total_bound_sources = None
                missing_fields.extend(
                    [
                        "audit_source_payload.provider_adapter.contract",
                        "audit_source_payload.provider_adapter.total_bound_sources",
                    ]
                )
            else:
                raw_provider_adapter_contract = provider_adapter.get("contract")
                if (
                    not isinstance(raw_provider_adapter_contract, str)
                    or not raw_provider_adapter_contract.strip()
                ):
                    provider_adapter_contract = None
                    missing_fields.append("audit_source_payload.provider_adapter.contract")
                else:
                    provider_adapter_contract = raw_provider_adapter_contract.strip()

                raw_provider_adapter_total_bound_sources = provider_adapter.get(
                    "total_bound_sources"
                )
                if isinstance(raw_provider_adapter_total_bound_sources, bool) or (
                    raw_provider_adapter_total_bound_sources is not None
                    and not isinstance(raw_provider_adapter_total_bound_sources, int)
                ):
                    provider_adapter_total_bound_sources = None
                    malformed_field_count += 1
                elif raw_provider_adapter_total_bound_sources is None:
                    provider_adapter_total_bound_sources = None
                    missing_fields.append(
                        "audit_source_payload.provider_adapter.total_bound_sources"
                    )
                else:
                    provider_adapter_total_bound_sources = int(
                        raw_provider_adapter_total_bound_sources
                    )

            if (
                source_observation_contract
                and source_observation_contract != EXPECTED_PROVIDER_ADAPTER_CONTRACT
            ):
                mismatched_fields.append("source_observation_summary.contract")
            if (
                provider_adapter_contract
                and provider_adapter_contract != EXPECTED_PROVIDER_ADAPTER_CONTRACT
            ):
                mismatched_fields.append("audit_source_payload.provider_adapter.contract")
            if (
                source_observation_contract is not None
                and provider_adapter_contract is not None
                and source_observation_contract != provider_adapter_contract
            ):
                mismatched_fields.append("provider_adapter.contract_alignment")

            if (
                source_observation_total_bound_sources is not None
                and provider_adapter_total_bound_sources is not None
                and source_observation_total_bound_sources
                != provider_adapter_total_bound_sources
            ):
                mismatched_fields.append(
                    "provider_adapter.total_bound_sources_alignment"
                )

            if malformed_field_count > 0:
                consistency_classification = "invalid"
                invalid_snapshots += 1
                malformed_snapshot_ids.append(snapshot_id)
                consistency_percentage = 0.0
                diagnostic = (
                    "Provider adapter contract consistency could not be evaluated because persisted contract metadata was malformed."
                )
            else:
                penalty = len(missing_fields) * 20 + len(mismatched_fields) * 35
                consistency_percentage = round(max(0.0, 100.0 - penalty), 2)

                if any(field.endswith("contract") for field in missing_fields):
                    missing_contract_snapshot_ids.append(snapshot_id)
                if any("contract" in field for field in mismatched_fields):
                    mismatched_contract_snapshot_ids.append(snapshot_id)
                if "provider_adapter.total_bound_sources_alignment" in mismatched_fields:
                    bound_source_mismatch_snapshot_ids.append(snapshot_id)

                if mismatched_fields:
                    consistency_classification = "degraded"
                    degraded_snapshots += 1
                    diagnostic = (
                        "Provider adapter contract consistency was degraded because persisted contract metadata diverged."
                    )
                elif missing_fields:
                    consistency_classification = "partial"
                    partial_snapshots += 1
                    diagnostic = (
                        "Provider adapter contract consistency was partial because persisted contract metadata was incomplete."
                    )
                else:
                    consistency_classification = "consistent"
                    consistent_snapshots += 1
                    diagnostic = (
                        "Provider adapter contract metadata remained consistent across persisted snapshot surfaces."
                    )

            entries.append(
                SnapshotProviderAdapterContractConsistencyEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    consistency_classification=consistency_classification,
                    consistency_percentage=consistency_percentage,
                    source_observation_contract=source_observation_contract,
                    provider_adapter_contract=provider_adapter_contract,
                    source_observation_total_bound_sources=source_observation_total_bound_sources,
                    provider_adapter_total_bound_sources=provider_adapter_total_bound_sources,
                    missing_fields=tuple(sorted(set(missing_fields))),
                    mismatched_fields=tuple(sorted(set(mismatched_fields))),
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

        snapshots_checked = len(entries)
        if snapshots_checked == 0:
            consistency_classification = "insufficient_data"
            average_consistency_percentage = 0.0
        else:
            if invalid_snapshots > 0:
                consistency_classification = "invalid"
            elif degraded_snapshots > 0:
                consistency_classification = "degraded"
            elif partial_snapshots > 0:
                consistency_classification = "partial"
            else:
                consistency_classification = "consistent"

            average_consistency_percentage = round(
                sum(entry.consistency_percentage for entry in entries)
                / snapshots_checked,
                2,
            )

        diagnostics.append(
            f"Provider adapter contract consistency is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if missing_contract_snapshot_ids:
            diagnostics.append(
                f"{len(missing_contract_snapshot_ids)} snapshot(s) were missing contract metadata on one or more persisted surfaces."
            )
        if mismatched_contract_snapshot_ids:
            diagnostics.append(
                f"{len(mismatched_contract_snapshot_ids)} snapshot(s) had contract values that diverged from the expected provider adapter contract."
            )
        if bound_source_mismatch_snapshot_ids:
            diagnostics.append(
                f"{len(bound_source_mismatch_snapshot_ids)} snapshot(s) had mismatched bound-source totals between persisted summary surfaces."
            )
        if malformed_snapshot_ids:
            diagnostics.append(
                f"{len(malformed_snapshot_ids)} snapshot(s) contained malformed provider adapter contract metadata."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during provider adapter contract consistency analysis."
            )

        return SnapshotProviderAdapterContractConsistency(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            expected_contract=EXPECTED_PROVIDER_ADAPTER_CONTRACT,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_contract_snapshot_ids=tuple(sorted(missing_contract_snapshot_ids)),
            mismatched_contract_snapshot_ids=tuple(
                sorted(mismatched_contract_snapshot_ids)
            ),
            bound_source_mismatch_snapshot_ids=tuple(
                sorted(bound_source_mismatch_snapshot_ids)
            ),
            malformed_snapshot_ids=tuple(sorted(malformed_snapshot_ids)),
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )


__all__ = ["SnapshotReplaySourceRegistryVerificationMixin"]
