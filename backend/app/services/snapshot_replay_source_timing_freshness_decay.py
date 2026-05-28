from __future__ import annotations

from app.services.snapshot_replay_source_common import (
    Any,
    Counter,
    Mapping,
    SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift,
    SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry,
    SnapshotSourceFreshnessPolicyDrift,
    SnapshotSourceFreshnessPolicyDriftEntry,
    SnapshotStaleSourceListThresholdReconciliation,
    SnapshotStaleSourceListThresholdReconciliationEntry,
    UTC,
    VALID_FRESHNESS_EVALUATION_MODES,
    datetime,
)


class SnapshotReplaySourceTimingFreshnessDecayMixin:
    def _build_source_freshness_policy_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceFreshnessPolicyDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source freshness policy drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source freshness policy drift analysis."
                )
            return SnapshotSourceFreshnessPolicyDrift(
                drift_classification="insufficient_data",
                average_policy_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                degrading_snapshots=0,
                improving_snapshots=0,
                mixed_snapshots=0,
                insufficient_data_snapshots=0,
                evaluation_mode_changes=0,
                malformed_summary_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceFreshnessPolicyDriftEntry] = []
        stable_snapshots = 0
        degrading_snapshots = 0
        improving_snapshots = 0
        mixed_snapshots = 0
        insufficient_data_snapshots = 0
        evaluation_mode_changes = 0
        malformed_summary_count = 0
        previous_policy_score: float | None = None
        previous_negative_signature: tuple[int, int, int] | None = None
        previous_evaluation_mode: str | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            summary = snapshot_payload.get("source_freshness_summary")
            if not isinstance(summary, Mapping):
                malformed_summary_count += 1
                insufficient_data_snapshots += 1
                entries.append(
                    SnapshotSourceFreshnessPolicyDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        policy_score=0.0,
                        previous_policy_score=previous_policy_score,
                        policy_score_delta=None,
                        total_active_sources=0,
                        fresh_source_count=0,
                        stale_source_count=0,
                        missing_timestamp_source_count=0,
                        not_evaluated_source_count=0,
                        evaluation_mode=None,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source freshness policy drift could not be evaluated because persisted source_freshness_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            malformed_field_count = 0
            try:
                total_active_sources = int(summary["total_active_sources"])
            except Exception:
                total_active_sources = 0
                malformed_field_count += 1
            try:
                fresh_source_count = int(summary["fresh_sources"])
            except Exception:
                fresh_source_count = 0
                malformed_field_count += 1
            try:
                stale_source_count = int(summary["stale_sources"])
            except Exception:
                stale_source_count = 0
                malformed_field_count += 1
            try:
                missing_timestamp_source_count = int(summary["sources_missing_timestamps"])
            except Exception:
                missing_timestamp_source_count = 0
                malformed_field_count += 1
            try:
                not_evaluated_source_count = int(summary["not_evaluated_sources"])
            except Exception:
                not_evaluated_source_count = 0
                malformed_field_count += 1

            raw_evaluation_mode = summary.get("evaluation_mode")
            evaluation_mode = (
                raw_evaluation_mode.strip()
                if isinstance(raw_evaluation_mode, str) and raw_evaluation_mode.strip()
                else None
            )
            if evaluation_mode is None:
                malformed_field_count += 1

            if total_active_sources < 0:
                malformed_field_count += 1
            if (
                total_active_sources > 0
                and fresh_source_count + stale_source_count + missing_timestamp_source_count + not_evaluated_source_count
                != total_active_sources
            ):
                malformed_field_count += 1

            if total_active_sources > 0:
                policy_score = round((fresh_source_count / total_active_sources) * 100.0, 2)
            else:
                policy_score = 0.0

            policy_score_delta: float | None = None
            prior_policy_score = previous_policy_score
            negative_signature = (
                stale_source_count,
                missing_timestamp_source_count,
                not_evaluated_source_count,
            )

            if (
                malformed_field_count > 0
                or total_active_sources <= 0
                or evaluation_mode != "observed"
            ):
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                if evaluation_mode != "observed" and evaluation_mode is not None:
                    diagnostic = (
                        "Source freshness policy drift could not be evaluated because freshness policy metadata was not persisted in observed mode."
                    )
                else:
                    diagnostic = (
                        "Source freshness policy drift could not be evaluated because persisted freshness summary fields were malformed or incomplete."
                    )
            else:
                if previous_policy_score is not None:
                    policy_score_delta = round(policy_score - previous_policy_score, 2)
                if previous_policy_score is None:
                    drift_classification = "stable"
                    stable_snapshots += 1
                    diagnostic = (
                        "Source freshness policy baseline was established from persisted freshness summary metadata."
                    )
                else:
                    if evaluation_mode != previous_evaluation_mode:
                        evaluation_mode_changes += 1
                    if policy_score_delta is not None and policy_score_delta < 0:
                        drift_classification = "degrading"
                        degrading_snapshots += 1
                        diagnostic = (
                            "Source freshness policy coverage deteriorated compared with the previous saved snapshot."
                        )
                    elif policy_score_delta is not None and policy_score_delta > 0:
                        drift_classification = "improving"
                        improving_snapshots += 1
                        diagnostic = (
                            "Source freshness policy coverage improved compared with the previous saved snapshot."
                        )
                    elif previous_negative_signature is not None and negative_signature != previous_negative_signature:
                        drift_classification = "mixed"
                        mixed_snapshots += 1
                        diagnostic = (
                            "Source freshness policy score stayed flat, but stale or missing-timestamp source composition changed."
                        )
                    else:
                        drift_classification = "stable"
                        stable_snapshots += 1
                        diagnostic = (
                            "Source freshness policy coverage remained stable compared with the previous saved snapshot."
                        )

                previous_policy_score = policy_score
                previous_negative_signature = negative_signature
                previous_evaluation_mode = evaluation_mode

            malformed_summary_count += malformed_field_count
            entries.append(
                SnapshotSourceFreshnessPolicyDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    policy_score=policy_score,
                    previous_policy_score=prior_policy_score,
                    policy_score_delta=policy_score_delta,
                    total_active_sources=total_active_sources,
                    fresh_source_count=fresh_source_count,
                    stale_source_count=stale_source_count,
                    missing_timestamp_source_count=missing_timestamp_source_count,
                    not_evaluated_source_count=not_evaluated_source_count,
                    evaluation_mode=evaluation_mode,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

        valid_entries = tuple(
            entry
            for entry in entries
            if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_policy_score = 0.0
            severity_score = 0
        else:
            average_policy_score = round(
                sum(entry.policy_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            if mixed_snapshots > 0 or (degrading_snapshots > 0 and improving_snapshots > 0):
                drift_classification = "mixed"
            elif degrading_snapshots > 0:
                drift_classification = "degrading"
            elif improving_snapshots > 0:
                drift_classification = "improving"
            else:
                drift_classification = "stable"
            severity_score = int(
                round(
                    max(
                        abs(entry.policy_score_delta or 0.0)
                        for entry in valid_entries
                    )
                )
            )

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source freshness policy coverage remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degrading":
            diagnostics.append(
                f"Source freshness policy coverage deteriorated across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "improving":
            diagnostics.append(
                f"Source freshness policy coverage improved across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "mixed":
            diagnostics.append(
                f"Source freshness policy coverage was mixed across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append("Source freshness policy drift had insufficient usable summary metadata.")
        if evaluation_mode_changes > 0:
            diagnostics.append(
                f"Persisted freshness evaluation mode changed {evaluation_mode_changes} time(s) across the requested snapshots."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed freshness summary field issue(s) were detected during source freshness policy drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source freshness policy drift analysis."
            )

        return SnapshotSourceFreshnessPolicyDrift(
            drift_classification=drift_classification,
            average_policy_score=average_policy_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            degrading_snapshots=degrading_snapshots,
            improving_snapshots=improving_snapshots,
            mixed_snapshots=mixed_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            evaluation_mode_changes=evaluation_mode_changes,
            malformed_summary_count=malformed_summary_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_source_diagnostics_freshness_evaluation_mode_drift(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for source diagnostics freshness-evaluation-mode drift analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics freshness-evaluation-mode drift analysis."
                )
            return SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift(
                drift_classification="insufficient_data",
                average_mode_consistency_score=0.0,
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                stable_snapshots=0,
                drifting_snapshots=0,
                degraded_snapshots=0,
                insufficient_data_snapshots=0,
                dominant_freshness_evaluation_mode=None,
                latest_freshness_evaluation_mode=None,
                freshness_evaluation_mode_counts={},
                mode_transition_count=0,
                malformed_summary_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry] = []
        stable_snapshots = 0
        drifting_snapshots = 0
        degraded_snapshots = 0
        insufficient_data_snapshots = 0
        mode_transition_count = 0
        malformed_summary_count = 0
        mode_counts: Counter[str] = Counter()
        previous_mode: str | None = None

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)
            prior_mode = previous_mode

            summary = snapshot_payload.get("source_diagnostics_summary")
            if not isinstance(summary, Mapping):
                malformed_summary_count += 1
                insufficient_data_snapshots += 1
                entries.append(
                    SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        drift_classification="insufficient_data",
                        freshness_evaluation_mode=None,
                        previous_freshness_evaluation_mode=prior_mode,
                        mode_consistency_score=0.0,
                        total_features=0,
                        features_with_stale_sources=0,
                        total_stale_assets=0,
                        malformed_field_count=1,
                        diagnostic=(
                            "Source diagnostics freshness-evaluation-mode drift could not be evaluated because persisted source_diagnostics_summary metadata was missing or malformed."
                        ),
                    )
                )
                continue

            malformed_field_count = 0
            raw_mode = summary.get("freshness_evaluation_mode")
            evaluation_mode = (
                raw_mode.strip()
                if isinstance(raw_mode, str)
                and raw_mode.strip()
                and raw_mode.strip() in VALID_FRESHNESS_EVALUATION_MODES
                else None
            )
            if evaluation_mode is None:
                malformed_field_count += 1

            try:
                total_features = int(summary["total_features"])
            except Exception:
                total_features = 0
                malformed_field_count += 1
            try:
                features_with_stale_sources = int(summary["features_with_stale_sources"])
            except Exception:
                features_with_stale_sources = 0
                malformed_field_count += 1
            try:
                total_stale_assets = int(summary["total_stale_assets"])
            except Exception:
                total_stale_assets = 0
                malformed_field_count += 1

            if evaluation_mode is None:
                drift_classification = "insufficient_data"
                insufficient_data_snapshots += 1
                mode_consistency_score = 0.0
                diagnostic = (
                    "Source diagnostics freshness-evaluation-mode drift could not be evaluated because the persisted freshness_evaluation_mode field was missing or invalid."
                )
            elif previous_mode is None:
                if evaluation_mode == "observed":
                    drift_classification = "stable"
                    stable_snapshots += 1
                    mode_consistency_score = 100.0
                    diagnostic = (
                        "Source diagnostics freshness-evaluation-mode baseline was established from observed freshness evaluation."
                    )
                else:
                    drift_classification = "degraded"
                    degraded_snapshots += 1
                    mode_consistency_score = 50.0
                    diagnostic = (
                        "Source diagnostics freshness evaluation remained in not_evaluated mode, so persisted stale-source diagnostics are less informative."
                    )
            elif evaluation_mode != previous_mode:
                drift_classification = "drifting"
                drifting_snapshots += 1
                mode_transition_count += 1
                mode_consistency_score = 50.0
                diagnostic = (
                    "Source diagnostics freshness-evaluation-mode changed compared with the previous saved snapshot."
                )
            elif evaluation_mode == "observed":
                drift_classification = "stable"
                stable_snapshots += 1
                mode_consistency_score = 100.0
                diagnostic = (
                    "Source diagnostics freshness-evaluation-mode remained stable in observed mode."
                )
            else:
                drift_classification = "degraded"
                degraded_snapshots += 1
                mode_consistency_score = 50.0
                diagnostic = (
                    "Source diagnostics freshness-evaluation-mode remained in not_evaluated mode."
                )

            malformed_summary_count += malformed_field_count
            if evaluation_mode is not None:
                mode_counts[evaluation_mode] += 1
                previous_mode = evaluation_mode

            entries.append(
                SnapshotSourceDiagnosticsFreshnessEvaluationModeDriftEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    drift_classification=drift_classification,
                    freshness_evaluation_mode=evaluation_mode,
                    previous_freshness_evaluation_mode=prior_mode,
                    mode_consistency_score=mode_consistency_score,
                    total_features=total_features,
                    features_with_stale_sources=features_with_stale_sources,
                    total_stale_assets=total_stale_assets,
                    malformed_field_count=malformed_field_count,
                    diagnostic=diagnostic,
                )
            )

        valid_entries = tuple(
            entry for entry in entries if entry.drift_classification != "insufficient_data"
        )
        if not valid_entries:
            drift_classification = "insufficient_data"
            average_mode_consistency_score = 0.0
            severity_score = 0
            dominant_freshness_evaluation_mode = None
            latest_freshness_evaluation_mode = None
        else:
            average_mode_consistency_score = round(
                sum(entry.mode_consistency_score for entry in valid_entries) / len(valid_entries),
                2,
            )
            latest_freshness_evaluation_mode = valid_entries[-1].freshness_evaluation_mode
            dominant_freshness_evaluation_mode = sorted(
                mode_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]
            if drifting_snapshots > 0:
                drift_classification = "drifting"
            elif degraded_snapshots > 0:
                drift_classification = "degraded"
            else:
                drift_classification = "stable"
            severity_score = int(round(max(0.0, 100.0 - valid_entries[-1].mode_consistency_score)))

        snapshots_checked = len(entries)
        if drift_classification == "stable":
            diagnostics.append(
                f"Source diagnostics freshness-evaluation-mode remained stable across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "drifting":
            diagnostics.append(
                f"Source diagnostics freshness-evaluation-mode drifted across {snapshots_checked} saved snapshot(s)."
            )
        elif drift_classification == "degraded":
            diagnostics.append(
                f"Source diagnostics freshness-evaluation-mode remained degraded across {snapshots_checked} saved snapshot(s)."
            )
        else:
            diagnostics.append(
                "Source diagnostics freshness-evaluation-mode drift had insufficient usable summary metadata."
            )
        if mode_transition_count > 0:
            diagnostics.append(
                f"Persisted source diagnostics freshness-evaluation-mode changed {mode_transition_count} time(s) across the requested snapshots."
            )
        if malformed_summary_count > 0:
            diagnostics.append(
                f"{malformed_summary_count} malformed source diagnostics summary field issue(s) were detected during freshness-evaluation-mode drift analysis."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during source diagnostics freshness-evaluation-mode drift analysis."
            )

        return SnapshotSourceDiagnosticsFreshnessEvaluationModeDrift(
            drift_classification=drift_classification,
            average_mode_consistency_score=average_mode_consistency_score,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            stable_snapshots=stable_snapshots,
            drifting_snapshots=drifting_snapshots,
            degraded_snapshots=degraded_snapshots,
            insufficient_data_snapshots=insufficient_data_snapshots,
            dominant_freshness_evaluation_mode=dominant_freshness_evaluation_mode,
            latest_freshness_evaluation_mode=latest_freshness_evaluation_mode,
            freshness_evaluation_mode_counts=dict(sorted(mode_counts.items())),
            mode_transition_count=mode_transition_count,
            malformed_summary_count=malformed_summary_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

    def _build_stale_source_list_threshold_reconciliation(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotStaleSourceListThresholdReconciliation:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append(
                "No saved snapshots were available for stale-source list threshold reconciliation analysis."
            )
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during stale-source list threshold reconciliation analysis."
                )
            return SnapshotStaleSourceListThresholdReconciliation(
                consistency_classification="invalid",
                average_consistency_percentage=0.0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                consistent_snapshots=0,
                partial_snapshots=0,
                degraded_snapshots=0,
                invalid_snapshots=0,
                missing_timestamp_source_ids=(),
                threshold_mismatch_source_ids=(),
                malformed_field_count=0,
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotStaleSourceListThresholdReconciliationEntry] = []
        consistent_snapshots = 0
        partial_snapshots = 0
        degraded_snapshots = 0
        invalid_snapshots = 0
        aggregate_missing_timestamp_source_ids: set[str] = set()
        aggregate_threshold_mismatch_source_ids: set[str] = set()
        aggregate_malformed_field_count = 0

        for snapshot_payload in snapshot_payloads:
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
                evaluation_time = self._parse_datetime(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)
                evaluation_time = datetime.now(UTC)

            source_observations = snapshot_payload.get("source_observations")
            persisted_stale_sources = snapshot_payload.get("stale_sources", ())
            malformed_field_count = 0

            if not isinstance(source_observations, Mapping):
                malformed_field_count += 1
                source_observations = {}
            if not isinstance(persisted_stale_sources, (list, tuple)):
                malformed_field_count += 1
                persisted_stale_sources = ()

            persisted_stale_source_ids: set[str] = set()
            for source_id in persisted_stale_sources:
                if not isinstance(source_id, str) or not source_id.strip():
                    malformed_field_count += 1
                    continue
                persisted_stale_source_ids.add(source_id.strip())

            try:
                from registry import build_source_freshness_diagnostics

                freshness_diagnostics = build_source_freshness_diagnostics(
                    source_observations=source_observations,
                    as_of_utc=evaluation_time,
                )
                freshness_sources = freshness_diagnostics["sources"]
            except Exception:
                freshness_sources = None
                malformed_field_count += 1

            if not isinstance(freshness_sources, list):
                invalid_snapshots += 1
                aggregate_malformed_field_count += malformed_field_count
                entries.append(
                    SnapshotStaleSourceListThresholdReconciliationEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        reconciliation_classification="invalid",
                        consistency_percentage=0.0,
                        total_active_sources=0,
                        aligned_sources=0,
                        threshold_stale_source_count=0,
                        persisted_stale_source_count=len(persisted_stale_source_ids),
                        missing_timestamp_source_ids=(),
                        threshold_mismatch_source_ids=(),
                        malformed_field_count=max(1, malformed_field_count),
                        diagnostic="Stale-source list threshold reconciliation could not be evaluated because persisted source freshness policy inputs were missing or malformed.",
                    )
                )
                continue

            active_sources = [
                entry
                for entry in freshness_sources
                if isinstance(entry, Mapping) and bool(entry.get("active"))
            ]
            total_active_sources = len(active_sources)
            threshold_stale_source_ids = {
                str(entry["source_id"])
                for entry in active_sources
                if entry.get("freshness_status") == "stale"
            }
            missing_timestamp_source_ids = {
                str(entry["source_id"])
                for entry in active_sources
                if entry.get("freshness_status") == "missing_timestamp"
            }
            active_source_ids = {
                str(entry["source_id"])
                for entry in active_sources
                if isinstance(entry.get("source_id"), str) and entry.get("source_id")
            }
            threshold_mismatch_source_ids = {
                source_id
                for source_id in active_source_ids
                if ((source_id in threshold_stale_source_ids) != (source_id in persisted_stale_source_ids))
            }
            aligned_sources = max(0, total_active_sources - len(threshold_mismatch_source_ids))
            consistency_percentage = round(
                (aligned_sources / total_active_sources) * 100.0,
                2,
            ) if total_active_sources else 0.0

            if malformed_field_count > 0:
                reconciliation_classification = "invalid"
                invalid_snapshots += 1
                diagnostic = (
                    "Stale-source list threshold reconciliation was invalid because one or more persisted freshness-policy fields were malformed."
                )
            elif threshold_mismatch_source_ids:
                reconciliation_classification = "degraded"
                degraded_snapshots += 1
                diagnostic = (
                    "Persisted stale-source list diverged from deterministic freshness-policy threshold evaluation."
                )
            elif missing_timestamp_source_ids:
                reconciliation_classification = "partial"
                partial_snapshots += 1
                diagnostic = (
                    "Stale-source list threshold reconciliation was partial because one or more active source timestamps were missing."
                )
            else:
                reconciliation_classification = "consistent"
                consistent_snapshots += 1
                diagnostic = (
                    "Persisted stale-source list remained aligned with deterministic freshness-policy threshold evaluation."
                )

            aggregate_missing_timestamp_source_ids.update(missing_timestamp_source_ids)
            aggregate_threshold_mismatch_source_ids.update(threshold_mismatch_source_ids)
            aggregate_malformed_field_count += malformed_field_count
            entries.append(
                SnapshotStaleSourceListThresholdReconciliationEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    reconciliation_classification=reconciliation_classification,
                    consistency_percentage=consistency_percentage,
                    total_active_sources=total_active_sources,
                    aligned_sources=aligned_sources,
                    threshold_stale_source_count=len(threshold_stale_source_ids),
                    persisted_stale_source_count=len(persisted_stale_source_ids),
                    missing_timestamp_source_ids=tuple(sorted(missing_timestamp_source_ids)),
                    threshold_mismatch_source_ids=tuple(sorted(threshold_mismatch_source_ids)),
                    malformed_field_count=malformed_field_count,
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
            f"Stale-source list threshold reconciliation is {consistency_classification} across {snapshots_checked} saved snapshot(s)."
        )
        if aggregate_missing_timestamp_source_ids:
            diagnostics.append(
                f"{len(aggregate_missing_timestamp_source_ids)} source ID(s) were missing timestamps during stale-source threshold evaluation."
            )
        if aggregate_threshold_mismatch_source_ids:
            diagnostics.append(
                f"{len(aggregate_threshold_mismatch_source_ids)} source ID(s) diverged from the persisted stale-source list."
            )
        if aggregate_malformed_field_count > 0:
            diagnostics.append(
                f"{aggregate_malformed_field_count} malformed field issue(s) were detected during stale-source list threshold reconciliation."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during stale-source list threshold reconciliation analysis."
            )

        return SnapshotStaleSourceListThresholdReconciliation(
            consistency_classification=consistency_classification,
            average_consistency_percentage=average_consistency_percentage,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            consistent_snapshots=consistent_snapshots,
            partial_snapshots=partial_snapshots,
            degraded_snapshots=degraded_snapshots,
            invalid_snapshots=invalid_snapshots,
            missing_timestamp_source_ids=tuple(sorted(aggregate_missing_timestamp_source_ids)),
            threshold_mismatch_source_ids=tuple(sorted(aggregate_threshold_mismatch_source_ids)),
            malformed_field_count=aggregate_malformed_field_count,
            entries=tuple(entries),
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )

__all__ = ["SnapshotReplaySourceTimingFreshnessDecayMixin"]
