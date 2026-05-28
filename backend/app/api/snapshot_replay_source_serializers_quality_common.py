from __future__ import annotations

from app.services import SnapshotFallbackUsageRecurrence
from app.services import SnapshotSourceGapRecurrenceLeaderboard



def _serialize_source_gap_recurrence_leaderboard(
    source_gap_recurrence_leaderboard: SnapshotSourceGapRecurrenceLeaderboard,
) -> dict[str, object]:
    return {
        "total_entries": source_gap_recurrence_leaderboard.total_entries,
        "total_snapshots": source_gap_recurrence_leaderboard.total_snapshots,
        "entries": [
            {
                "rank": entry.rank,
                "source_id": entry.source_id,
                "gap_status": entry.gap_status,
                "severity": entry.severity.value,
                "recurrence_classification": entry.recurrence_classification,
                "occurrence_count": entry.occurrence_count,
                "recurrence_ratio": entry.recurrence_ratio,
                "longest_streak": entry.longest_streak,
                "first_snapshot_id": entry.first_snapshot_id,
                "latest_snapshot_id": entry.latest_snapshot_id,
                "affected_snapshot_ids": list(entry.affected_snapshot_ids),
            }
            for entry in source_gap_recurrence_leaderboard.entries
        ],
        "diagnostics": list(source_gap_recurrence_leaderboard.diagnostics),
        "paper_safe": source_gap_recurrence_leaderboard.paper_safe,
        "network_calls": source_gap_recurrence_leaderboard.network_calls,
        "execution_side_effects": source_gap_recurrence_leaderboard.execution_side_effects,
    }

def _serialize_fallback_usage_recurrence(
    fallback_usage_recurrence: SnapshotFallbackUsageRecurrence,
) -> dict[str, object]:
    return {
        "stability_classification": fallback_usage_recurrence.stability_classification,
        "severity_score": fallback_usage_recurrence.severity_score,
        "total_snapshots_requested": fallback_usage_recurrence.total_snapshots_requested,
        "snapshots_checked": fallback_usage_recurrence.snapshots_checked,
        "snapshots_with_fallback": fallback_usage_recurrence.snapshots_with_fallback,
        "total_fallback_events": fallback_usage_recurrence.total_fallback_events,
        "unique_fallback_providers": fallback_usage_recurrence.unique_fallback_providers,
        "malformed_snapshot_count": fallback_usage_recurrence.malformed_snapshot_count,
        "missing_provider_metadata_count": fallback_usage_recurrence.missing_provider_metadata_count,
        "timeline": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "status": entry.status,
                "fallback_event_count": entry.fallback_event_count,
                "fallback_provider_count": entry.fallback_provider_count,
                "affected_providers": list(entry.affected_providers),
                "affected_assets": list(entry.affected_assets),
                "severity_score": entry.severity_score,
                "diagnostic": entry.diagnostic,
            }
            for entry in fallback_usage_recurrence.timeline
        ],
        "recurring_entries": [
            {
                "rank": entry.rank,
                "provider_name": entry.provider_name,
                "recurrence_classification": entry.recurrence_classification,
                "severity_score": entry.severity_score,
                "occurrence_count": entry.occurrence_count,
                "recurrence_ratio": entry.recurrence_ratio,
                "longest_streak": entry.longest_streak,
                "affected_snapshot_ids": list(entry.affected_snapshot_ids),
                "affected_assets": list(entry.affected_assets),
                "missing_provider_metadata_count": entry.missing_provider_metadata_count,
            }
            for entry in fallback_usage_recurrence.recurring_entries
        ],
        "entries": [
            {
                "rank": entry.rank,
                "provider_name": entry.provider_name,
                "recurrence_classification": entry.recurrence_classification,
                "severity_score": entry.severity_score,
                "occurrence_count": entry.occurrence_count,
                "recurrence_ratio": entry.recurrence_ratio,
                "longest_streak": entry.longest_streak,
                "affected_snapshot_ids": list(entry.affected_snapshot_ids),
                "affected_assets": list(entry.affected_assets),
                "missing_provider_metadata_count": entry.missing_provider_metadata_count,
            }
            for entry in fallback_usage_recurrence.entries
        ],
        "failures": list(fallback_usage_recurrence.failures),
        "diagnostics": list(fallback_usage_recurrence.diagnostics),
        "paper_safe": fallback_usage_recurrence.paper_safe,
        "network_calls": fallback_usage_recurrence.network_calls,
        "execution_side_effects": fallback_usage_recurrence.execution_side_effects,
    }
