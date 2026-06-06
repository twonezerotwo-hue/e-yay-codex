from __future__ import annotations

from app.services.snapshot_replay_source_common import (
    Any,
    Counter,
    Mapping,
    SEVERITY_PRIORITY,
    SOURCE_FRESHNESS_STATUS_PRIORITY,
    SOURCE_GAP_STATUS_PRIORITY,
    SnapshotFallbackUsageRecurrence,
    SnapshotFallbackUsageRecurrenceEntry,
    SnapshotFallbackUsageTimelineEntry,
    SnapshotReplayResult,
    SnapshotSourceFreshnessDecayTimeline,
    SnapshotSourceFreshnessDecayTimelineEntry,
    SnapshotSourceGapRecurrenceEntry,
    SnapshotSourceGapRecurrenceLeaderboard,
    TriggerSeverity,
    UTC,
    datetime,
)


class SnapshotReplaySourceRecurrenceMixin:
    def _build_source_gap_recurrence_leaderboard(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
    ) -> SnapshotSourceGapRecurrenceLeaderboard:
        diagnostics: list[str] = []
        total_snapshots = len(replay_results)
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for source gap recurrence analysis.")
            return SnapshotSourceGapRecurrenceLeaderboard(
                total_entries=0,
                total_snapshots=0,
                entries=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        buckets: dict[str, dict[str, object]] = {}
        streaks: dict[str, int] = {}
        seen_sources: set[str] = set()

        for replay_result in replay_results:
            active_sources: dict[str, str] = {}
            for source_id in replay_result.missing_sources:
                active_sources[source_id] = "missing"
            for source_id in replay_result.stale_sources:
                if source_id in active_sources and active_sources[source_id] != "stale":
                    active_sources[source_id] = "mixed"
                elif source_id not in active_sources:
                    active_sources[source_id] = "stale"

            active_source_ids = set(active_sources)
            for source_id in sorted(seen_sources - active_source_ids):
                streaks[source_id] = 0

            for source_id, gap_status in active_sources.items():
                severity = TriggerSeverity.ORANGE if gap_status in {"missing", "mixed"} else TriggerSeverity.YELLOW
                bucket = buckets.setdefault(
                    source_id,
                    {
                        "gap_statuses": set(),
                        "severity": severity,
                        "occurrence_count": 0,
                        "longest_streak": 0,
                        "first_snapshot_id": replay_result.snapshot_id,
                        "latest_snapshot_id": replay_result.snapshot_id,
                        "affected_snapshot_ids": [],
                    },
                )
                bucket["gap_statuses"].add(gap_status)
                bucket["occurrence_count"] = int(bucket["occurrence_count"]) + 1
                bucket["latest_snapshot_id"] = replay_result.snapshot_id
                bucket["affected_snapshot_ids"].append(replay_result.snapshot_id)
                if SEVERITY_PRIORITY[severity] > SEVERITY_PRIORITY[bucket["severity"]]:
                    bucket["severity"] = severity

                current_streak = streaks.get(source_id, 0) + 1
                streaks[source_id] = current_streak
                if current_streak > int(bucket["longest_streak"]):
                    bucket["longest_streak"] = current_streak

            seen_sources.update(active_source_ids)

        if not buckets:
            diagnostics.append("No missing or stale source gaps were found in the requested saved snapshots.")
            return SnapshotSourceGapRecurrenceLeaderboard(
                total_entries=0,
                total_snapshots=total_snapshots,
                entries=(),
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        leaderboard_entries: list[SnapshotSourceGapRecurrenceEntry] = []
        for source_id, bucket in buckets.items():
            gap_statuses = bucket["gap_statuses"]
            if "mixed" in gap_statuses or len(gap_statuses) > 1:
                gap_status = "mixed"
            elif "missing" in gap_statuses:
                gap_status = "missing"
            else:
                gap_status = "stale"

            occurrence_count = int(bucket["occurrence_count"])
            longest_streak = int(bucket["longest_streak"])
            if occurrence_count == total_snapshots and total_snapshots > 1:
                recurrence_classification = "persistent"
            elif longest_streak >= 2:
                recurrence_classification = "recurring"
            else:
                recurrence_classification = "intermittent"

            leaderboard_entries.append(
                SnapshotSourceGapRecurrenceEntry(
                    rank=0,
                    source_id=source_id,
                    gap_status=gap_status,
                    severity=bucket["severity"],
                    recurrence_classification=recurrence_classification,
                    occurrence_count=occurrence_count,
                    recurrence_ratio=round(occurrence_count / total_snapshots, 4),
                    longest_streak=longest_streak,
                    first_snapshot_id=str(bucket["first_snapshot_id"]),
                    latest_snapshot_id=str(bucket["latest_snapshot_id"]),
                    affected_snapshot_ids=tuple(bucket["affected_snapshot_ids"]),
                )
            )

        ranked_entries = tuple(
            SnapshotSourceGapRecurrenceEntry(
                rank=index,
                source_id=entry.source_id,
                gap_status=entry.gap_status,
                severity=entry.severity,
                recurrence_classification=entry.recurrence_classification,
                occurrence_count=entry.occurrence_count,
                recurrence_ratio=entry.recurrence_ratio,
                longest_streak=entry.longest_streak,
                first_snapshot_id=entry.first_snapshot_id,
                latest_snapshot_id=entry.latest_snapshot_id,
                affected_snapshot_ids=entry.affected_snapshot_ids,
            )
            for index, entry in enumerate(
                sorted(
                    leaderboard_entries,
                    key=lambda item: (
                        -item.occurrence_count,
                        -item.longest_streak,
                        -SEVERITY_PRIORITY[item.severity],
                        -SOURCE_GAP_STATUS_PRIORITY[item.gap_status],
                        item.source_id,
                    ),
                ),
                start=1,
            )
        )

        diagnostics.append(
            f"Source gap recurrence leaderboard covers {total_snapshots} saved snapshot(s) and {len(ranked_entries)} gap source(s)."
        )

        return SnapshotSourceGapRecurrenceLeaderboard(
            total_entries=len(ranked_entries),
            total_snapshots=total_snapshots,
            entries=ranked_entries,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_source_freshness_decay_timeline(
        self,
        replay_results: tuple[SnapshotReplayResult, ...],
        *,
        failure_count: int = 0,
        failures: tuple[dict[str, str], ...] = (),
        total_snapshots_requested: int = 0,
    ) -> SnapshotSourceFreshnessDecayTimeline:
        diagnostics: list[str] = []
        if not replay_results:
            diagnostics.append("No replayable snapshots were available for source freshness decay analysis.")
            if failure_count > 0:
                diagnostics.append(
                    f"{failure_count} snapshot replay(s) failed during source freshness decay analysis."
                )
            return SnapshotSourceFreshnessDecayTimeline(
                decay_classification="insufficient_data",
                total_snapshots=0,
                evaluable_snapshots=0,
                missing_freshness_snapshots=0,
                first_status=None,
                latest_status=None,
                dominant_status=None,
                worst_status=None,
                transition_count=0,
                decay_score_delta=0,
                entries=(),
                failures=failures,
                total_snapshots_requested=total_snapshots_requested,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        entries: list[SnapshotSourceFreshnessDecayTimelineEntry] = []
        evaluable_entries: list[SnapshotSourceFreshnessDecayTimelineEntry] = []
        missing_freshness_snapshots = 0

        for replay_result in replay_results:
            try:
                from registry import build_source_freshness_diagnostics

                freshness_diagnostics = build_source_freshness_diagnostics(
                    source_observations=replay_result.source_observations,
                    as_of_utc=self._parse_datetime(replay_result.created_at),
                )
            except Exception as exc:
                missing_freshness_snapshots += 1
                entries.append(
                    SnapshotSourceFreshnessDecayTimelineEntry(
                        snapshot_id=replay_result.snapshot_id,
                        created_at=replay_result.created_at,
                        freshness_status="missing_freshness",
                        fresh_source_count=0,
                        stale_source_count=0,
                        missing_timestamp_source_count=0,
                        degraded_source_count=0,
                        total_active_sources=0,
                        decay_score=None,
                        diagnostic=f"Freshness diagnostics could not be evaluated safely: {str(exc) or exc.__class__.__name__}",
                    )
                )
                continue

            summary = freshness_diagnostics["summary"]
            fresh_source_count = int(summary["fresh_sources"])
            stale_source_count = int(summary["stale_sources"])
            missing_timestamp_source_count = int(summary["sources_missing_timestamps"])
            total_active_sources = int(summary["total_active_sources"])
            degraded_source_count = stale_source_count + missing_timestamp_source_count
            decay_score = stale_source_count * 2 + missing_timestamp_source_count

            if stale_source_count > 0:
                freshness_status = "stale"
                diagnostic = (
                    f"{stale_source_count} source(s) breached freshness policy and "
                    f"{missing_timestamp_source_count} source(s) missed timestamps."
                )
            elif missing_timestamp_source_count > 0:
                freshness_status = "degraded"
                diagnostic = (
                    f"{missing_timestamp_source_count} active source timestamp(s) were missing at replay time."
                )
            else:
                freshness_status = "fresh"
                diagnostic = "All active sources satisfied freshness policy at replay time."

            entry = SnapshotSourceFreshnessDecayTimelineEntry(
                snapshot_id=replay_result.snapshot_id,
                created_at=replay_result.created_at,
                freshness_status=freshness_status,
                fresh_source_count=fresh_source_count,
                stale_source_count=stale_source_count,
                missing_timestamp_source_count=missing_timestamp_source_count,
                degraded_source_count=degraded_source_count,
                total_active_sources=total_active_sources,
                decay_score=decay_score,
                diagnostic=diagnostic,
            )
            entries.append(entry)
            evaluable_entries.append(entry)

        if len(evaluable_entries) < 2:
            diagnostics.append(
                "At least two replayable snapshots with evaluable source freshness data are required."
            )
            if missing_freshness_snapshots > 0:
                diagnostics.append(
                    f"{missing_freshness_snapshots} snapshot(s) had missing or malformed freshness inputs."
                )
            if failure_count > 0:
                diagnostics.append(
                    f"{failure_count} snapshot replay(s) failed during source freshness decay analysis."
                )
            return SnapshotSourceFreshnessDecayTimeline(
                decay_classification="insufficient_data",
                total_snapshots=len(entries),
                evaluable_snapshots=len(evaluable_entries),
                missing_freshness_snapshots=missing_freshness_snapshots,
                first_status=evaluable_entries[0].freshness_status if evaluable_entries else None,
                latest_status=evaluable_entries[-1].freshness_status if evaluable_entries else None,
                dominant_status=evaluable_entries[0].freshness_status if evaluable_entries else None,
                worst_status=evaluable_entries[0].freshness_status if evaluable_entries else None,
                transition_count=0,
                decay_score_delta=0,
                entries=tuple(entries),
                failures=failures,
                total_snapshots_requested=total_snapshots_requested,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        first_entry = evaluable_entries[0]
        latest_entry = evaluable_entries[-1]
        decay_score_delta = int(latest_entry.decay_score or 0) - int(first_entry.decay_score or 0)
        transition_count = sum(
            1
            for index in range(1, len(evaluable_entries))
            if (
                evaluable_entries[index].decay_score != evaluable_entries[index - 1].decay_score
                or evaluable_entries[index].freshness_status
                != evaluable_entries[index - 1].freshness_status
            )
        )
        status_counts = Counter(entry.freshness_status for entry in evaluable_entries)
        dominant_status = sorted(
            status_counts.items(),
            key=lambda item: (-item[1], SOURCE_FRESHNESS_STATUS_PRIORITY[item[0]], item[0]),
        )[0][0]
        worst_status = max(
            (entry.freshness_status for entry in evaluable_entries),
            key=lambda status: SOURCE_FRESHNESS_STATUS_PRIORITY[status],
        )

        if decay_score_delta > 0:
            decay_classification = "degrading"
            diagnostics.append(
                f"Source freshness deteriorated from {first_entry.freshness_status} to {latest_entry.freshness_status} across saved snapshots."
            )
        elif decay_score_delta < 0:
            decay_classification = "improving"
            diagnostics.append(
                f"Source freshness improved from {first_entry.freshness_status} to {latest_entry.freshness_status} across saved snapshots."
            )
        else:
            decay_classification = "stable"
            diagnostics.append(
                f"Source freshness remained in a stable {latest_entry.freshness_status} band across {len(evaluable_entries)} evaluable saved snapshot(s)."
            )

        if missing_freshness_snapshots > 0:
            diagnostics.append(
                f"{missing_freshness_snapshots} snapshot(s) had missing or malformed freshness inputs."
            )
        if failure_count > 0:
            diagnostics.append(
                f"{failure_count} snapshot replay(s) failed during source freshness decay analysis."
            )

        return SnapshotSourceFreshnessDecayTimeline(
            decay_classification=decay_classification,
            total_snapshots=len(entries),
            evaluable_snapshots=len(evaluable_entries),
            missing_freshness_snapshots=missing_freshness_snapshots,
            first_status=first_entry.freshness_status,
            latest_status=latest_entry.freshness_status,
            dominant_status=dominant_status,
            worst_status=worst_status,
            transition_count=transition_count,
            decay_score_delta=decay_score_delta,
            entries=tuple(entries),
            failures=failures,
            total_snapshots_requested=total_snapshots_requested,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
    def _build_fallback_usage_recurrence(
        self,
        snapshot_payloads: tuple[Mapping[str, Any], ...],
        *,
        total_snapshots_requested: int,
        failures: tuple[dict[str, str], ...] = (),
    ) -> SnapshotFallbackUsageRecurrence:
        diagnostics: list[str] = []
        if not snapshot_payloads:
            diagnostics.append("No saved snapshots were available for fallback usage recurrence analysis.")
            if failures:
                diagnostics.append(
                    f"{len(failures)} snapshot payload(s) could not be loaded during fallback usage analysis."
                )
            return SnapshotFallbackUsageRecurrence(
                stability_classification="insufficient_data",
                severity_score=0,
                total_snapshots_requested=total_snapshots_requested,
                snapshots_checked=0,
                snapshots_with_fallback=0,
                total_fallback_events=0,
                unique_fallback_providers=0,
                malformed_snapshot_count=0,
                missing_provider_metadata_count=0,
                timeline=(),
                recurring_entries=(),
                entries=(),
                failures=failures,
                diagnostics=tuple(diagnostics),
                paper_safe=True,
                network_calls=False,
                execution_side_effects="NO_EXECUTION",
            )

        timeline: list[SnapshotFallbackUsageTimelineEntry] = []
        provider_buckets: dict[str, dict[str, object]] = {}
        total_fallback_events = 0
        snapshots_with_fallback = 0
        malformed_snapshot_count = 0
        missing_provider_metadata_count = 0

        for snapshot_index, snapshot_payload in enumerate(snapshot_payloads):
            snapshot_id = str(snapshot_payload.get("snapshot_id", "unknown"))
            raw_created_at = snapshot_payload.get("created_at", datetime.now(UTC).isoformat())
            try:
                created_at = self._normalize_datetime_string(raw_created_at)
            except Exception:
                created_at = str(raw_created_at)

            serialized_snapshots = snapshot_payload.get("snapshots")
            if not isinstance(serialized_snapshots, list):
                malformed_snapshot_count += 1
                timeline.append(
                    SnapshotFallbackUsageTimelineEntry(
                        snapshot_id=snapshot_id,
                        created_at=created_at,
                        status="critical",
                        fallback_event_count=0,
                        fallback_provider_count=0,
                        affected_providers=(),
                        affected_assets=(),
                        severity_score=100,
                        diagnostic="Fallback usage diagnostics could not be evaluated because snapshot records were malformed.",
                    )
                )
                continue

            fallback_event_count = 0
            snapshot_malformed_records = 0
            snapshot_missing_provider_metadata = 0
            affected_providers: set[str] = set()
            affected_assets: set[str] = set()
            providers_in_snapshot: set[str] = set()

            for record_index, snapshot_record in enumerate(serialized_snapshots):
                if not isinstance(snapshot_record, Mapping):
                    snapshot_malformed_records += 1
                    continue

                if not bool(snapshot_record.get("fallback_used")):
                    continue

                fallback_event_count += 1
                total_fallback_events += 1

                raw_provider_name = snapshot_record.get("source_name")
                if isinstance(raw_provider_name, str) and raw_provider_name.strip():
                    provider_name = raw_provider_name.strip()
                else:
                    provider_name = "unknown_provider"
                    snapshot_missing_provider_metadata += 1
                    missing_provider_metadata_count += 1

                raw_asset_symbol = snapshot_record.get("asset_symbol")
                if isinstance(raw_asset_symbol, str) and raw_asset_symbol.strip():
                    asset_symbol = raw_asset_symbol.strip()
                else:
                    asset_symbol = f"UNKNOWN_ASSET_{record_index}"

                affected_providers.add(provider_name)
                affected_assets.add(asset_symbol)
                providers_in_snapshot.add(provider_name)

                provider_bucket = provider_buckets.setdefault(
                    provider_name,
                    {
                        "occurrence_count": 0,
                        "indices": [],
                        "snapshot_ids": [],
                        "assets": set(),
                        "missing_provider_metadata_count": 0,
                    },
                )
                if snapshot_id not in provider_bucket["snapshot_ids"]:
                    provider_bucket["occurrence_count"] += 1
                    provider_bucket["indices"].append(snapshot_index)
                    provider_bucket["snapshot_ids"].append(snapshot_id)
                provider_bucket["assets"].add(asset_symbol)
                provider_bucket["missing_provider_metadata_count"] += int(provider_name == "unknown_provider")

            if fallback_event_count > 0:
                snapshots_with_fallback += 1

            severity_score = min(
                100,
                fallback_event_count * 25
                + snapshot_missing_provider_metadata * 25
                + snapshot_malformed_records * 35,
            )
            if snapshot_malformed_records > 0 or snapshot_missing_provider_metadata > 0:
                status = "critical"
            elif fallback_event_count >= 2:
                status = "critical"
            elif fallback_event_count == 1:
                status = "elevated"
            else:
                status = "stable"

            if snapshot_malformed_records > 0:
                malformed_snapshot_count += 1
                diagnostic = (
                    f"Fallback usage diagnostics encountered {snapshot_malformed_records} malformed snapshot record(s)."
                )
            elif snapshot_missing_provider_metadata > 0:
                diagnostic = (
                    f"{snapshot_missing_provider_metadata} fallback event(s) had missing provider metadata."
                )
            elif fallback_event_count > 0:
                diagnostic = (
                    f"Fallback providers were used for {fallback_event_count} snapshot record(s) in this saved payload."
                )
            else:
                diagnostic = "No fallback providers were used in this saved payload."

            timeline.append(
                SnapshotFallbackUsageTimelineEntry(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    status=status,
                    fallback_event_count=fallback_event_count,
                    fallback_provider_count=len(providers_in_snapshot),
                    affected_providers=tuple(sorted(affected_providers)),
                    affected_assets=tuple(sorted(affected_assets)),
                    severity_score=severity_score,
                    diagnostic=diagnostic,
                )
            )

        recurring_entries: list[SnapshotFallbackUsageRecurrenceEntry] = []
        snapshots_checked = len(timeline)
        for provider_name, provider_bucket in provider_buckets.items():
            occurrence_count = int(provider_bucket["occurrence_count"])
            indices = sorted(int(index) for index in provider_bucket["indices"])
            longest_streak = 0
            current_streak = 0
            previous_index: int | None = None
            for index in indices:
                if previous_index is None or index == previous_index + 1:
                    current_streak += 1
                else:
                    current_streak = 1
                longest_streak = max(longest_streak, current_streak)
                previous_index = index

            recurrence_ratio = round(
                occurrence_count / snapshots_checked,
                2,
            ) if snapshots_checked else 0.0
            provider_missing_metadata_count = int(provider_bucket["missing_provider_metadata_count"])
            severity_score = min(
                100,
                occurrence_count * 20 + longest_streak * 15 + provider_missing_metadata_count * 25,
            )
            if provider_missing_metadata_count > 0 or occurrence_count >= 3 or recurrence_ratio >= 0.75:
                recurrence_classification = "critical"
            elif occurrence_count >= 2 or longest_streak >= 2 or recurrence_ratio >= 0.5:
                recurrence_classification = "elevated"
            else:
                recurrence_classification = "stable"

            recurring_entries.append(
                SnapshotFallbackUsageRecurrenceEntry(
                    rank=0,
                    provider_name=provider_name,
                    recurrence_classification=recurrence_classification,
                    severity_score=severity_score,
                    occurrence_count=occurrence_count,
                    recurrence_ratio=recurrence_ratio,
                    longest_streak=longest_streak,
                    affected_snapshot_ids=tuple(provider_bucket["snapshot_ids"]),
                    affected_assets=tuple(sorted(provider_bucket["assets"])),
                    missing_provider_metadata_count=provider_missing_metadata_count,
                )
            )

        ranked_entries = tuple(
            SnapshotFallbackUsageRecurrenceEntry(
                rank=index,
                provider_name=entry.provider_name,
                recurrence_classification=entry.recurrence_classification,
                severity_score=entry.severity_score,
                occurrence_count=entry.occurrence_count,
                recurrence_ratio=entry.recurrence_ratio,
                longest_streak=entry.longest_streak,
                affected_snapshot_ids=entry.affected_snapshot_ids,
                affected_assets=entry.affected_assets,
                missing_provider_metadata_count=entry.missing_provider_metadata_count,
            )
            for index, entry in enumerate(
                sorted(
                    recurring_entries,
                    key=lambda item: (
                        -item.occurrence_count,
                        -item.longest_streak,
                        -item.severity_score,
                        item.provider_name,
                    ),
                ),
                start=1,
            )
        )

        if snapshots_checked < 2:
            stability_classification = "insufficient_data"
            diagnostics.append("At least two saved snapshots are required to evaluate fallback usage recurrence.")
        elif malformed_snapshot_count > 0 or missing_provider_metadata_count > 0:
            stability_classification = "critical"
            diagnostics.append(
                f"Fallback usage recurrence is critical across {snapshots_checked} saved snapshot(s)."
            )
        elif total_fallback_events > 0:
            stability_classification = "elevated"
            diagnostics.append(
                f"Fallback usage recurrence is elevated across {snapshots_checked} saved snapshot(s)."
            )
        else:
            stability_classification = "stable"
            diagnostics.append(
                f"No fallback provider usage was detected across {snapshots_checked} saved snapshot(s)."
            )

        if malformed_snapshot_count > 0:
            diagnostics.append(
                f"{malformed_snapshot_count} saved snapshot(s) contained malformed fallback usage records."
            )
        if missing_provider_metadata_count > 0:
            diagnostics.append(
                f"{missing_provider_metadata_count} fallback event(s) had missing provider metadata."
            )
        if failures:
            diagnostics.append(
                f"{len(failures)} snapshot payload(s) could not be loaded during fallback usage analysis."
            )

        severity_score = min(
            100,
            total_fallback_events * 15
            + len(ranked_entries) * 10
            + malformed_snapshot_count * 20
            + missing_provider_metadata_count * 20,
        )

        return SnapshotFallbackUsageRecurrence(
            stability_classification=stability_classification,
            severity_score=severity_score,
            total_snapshots_requested=total_snapshots_requested,
            snapshots_checked=snapshots_checked,
            snapshots_with_fallback=snapshots_with_fallback,
            total_fallback_events=total_fallback_events,
            unique_fallback_providers=len(ranked_entries),
            malformed_snapshot_count=malformed_snapshot_count,
            missing_provider_metadata_count=missing_provider_metadata_count,
            timeline=tuple(timeline),
            recurring_entries=ranked_entries,
            entries=ranked_entries,
            failures=failures,
            diagnostics=tuple(diagnostics),
            paper_safe=True,
            network_calls=False,
            execution_side_effects="NO_EXECUTION",
        )
__all__ = [name for name in globals() if not name.startswith('_')]
