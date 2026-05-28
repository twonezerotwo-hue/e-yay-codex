from __future__ import annotations

from app.services import SnapshotRawPayloadReferenceCompleteness
from app.services import SnapshotSourceRecordCompleteness



def _serialize_raw_payload_reference_completeness(
    raw_payload_reference_completeness: SnapshotRawPayloadReferenceCompleteness,
) -> dict[str, object]:
    return {
        "completeness_classification": raw_payload_reference_completeness.completeness_classification,
        "average_completeness_percentage": raw_payload_reference_completeness.average_completeness_percentage,
        "total_snapshots_requested": raw_payload_reference_completeness.total_snapshots_requested,
        "snapshots_checked": raw_payload_reference_completeness.snapshots_checked,
        "complete_snapshots": raw_payload_reference_completeness.complete_snapshots,
        "partial_snapshots": raw_payload_reference_completeness.partial_snapshots,
        "degraded_snapshots": raw_payload_reference_completeness.degraded_snapshots,
        "invalid_snapshots": raw_payload_reference_completeness.invalid_snapshots,
        "missing_reference_assets": list(raw_payload_reference_completeness.missing_reference_assets),
        "empty_reference_assets": list(raw_payload_reference_completeness.empty_reference_assets),
        "malformed_reference_assets": list(raw_payload_reference_completeness.malformed_reference_assets),
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "completeness_classification": entry.completeness_classification,
                "completeness_percentage": entry.completeness_percentage,
                "total_records": entry.total_records,
                "complete_records": entry.complete_records,
                "partial_reference_assets": list(entry.partial_reference_assets),
                "missing_reference_assets": list(entry.missing_reference_assets),
                "empty_reference_assets": list(entry.empty_reference_assets),
                "malformed_reference_assets": list(entry.malformed_reference_assets),
                "diagnostic": entry.diagnostic,
            }
            for entry in raw_payload_reference_completeness.entries
        ],
        "failures": list(raw_payload_reference_completeness.failures),
        "diagnostics": list(raw_payload_reference_completeness.diagnostics),
        "paper_safe": raw_payload_reference_completeness.paper_safe,
        "network_calls": raw_payload_reference_completeness.network_calls,
        "execution_side_effects": raw_payload_reference_completeness.execution_side_effects,
    }

def _serialize_source_record_completeness(
    source_record_completeness: SnapshotSourceRecordCompleteness,
) -> dict[str, object]:
    return {
        "completeness_classification": source_record_completeness.completeness_classification,
        "average_completeness_percentage": source_record_completeness.average_completeness_percentage,
        "total_snapshots_requested": source_record_completeness.total_snapshots_requested,
        "snapshots_checked": source_record_completeness.snapshots_checked,
        "complete_snapshots": source_record_completeness.complete_snapshots,
        "partial_snapshots": source_record_completeness.partial_snapshots,
        "degraded_snapshots": source_record_completeness.degraded_snapshots,
        "invalid_snapshots": source_record_completeness.invalid_snapshots,
        "aggregate_missing_field_counts": source_record_completeness.aggregate_missing_field_counts,
        "malformed_record_count": source_record_completeness.malformed_record_count,
        "missing_field_diagnostics": list(source_record_completeness.missing_field_diagnostics),
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "completeness_classification": entry.completeness_classification,
                "completeness_percentage": entry.completeness_percentage,
                "total_records": entry.total_records,
                "complete_records": entry.complete_records,
                "missing_field_counts": entry.missing_field_counts,
                "missing_field_diagnostics": list(entry.missing_field_diagnostics),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_record_completeness.entries
        ],
        "failures": list(source_record_completeness.failures),
        "diagnostics": list(source_record_completeness.diagnostics),
        "paper_safe": source_record_completeness.paper_safe,
        "network_calls": source_record_completeness.network_calls,
        "execution_side_effects": source_record_completeness.execution_side_effects,
    }
