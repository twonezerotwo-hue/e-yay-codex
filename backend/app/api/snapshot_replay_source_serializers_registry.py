from __future__ import annotations



from app.services import SnapshotNoExecutionGuardrailConsistency
from app.services import SnapshotSourceVerificationDrift
from app.services import SnapshotPaperSafeSourceFlagConsistency
from app.services import SnapshotProviderAdapterContractConsistency
from app.services import SnapshotReplaySourceDiagnosticGroupCoverageDrift
from app.services import SnapshotReplaySourceDiagnosticContractSignatureDrift
from app.services import SnapshotReplaySourceDiagnosticNamingContractDrift
from app.services import SnapshotReplaySourceDiagnosticMetadataCompletenessDrift
from app.services import SnapshotReplaySourceDiagnosticSurfaceCountDrift
from app.services import SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift
from app.services import SnapshotReplaySourceDiagnosticsContractCoverageDrift
from app.services import SnapshotSourceRegistryBindingDrift
from app.services import SnapshotReplaySourceDiagnosticContractFieldSetDrift
from app.services import SnapshotReplayFullSurfaceResponseFieldSetConsistency

def _serialize_no_execution_guardrail_consistency(
    no_execution_guardrail_consistency: SnapshotNoExecutionGuardrailConsistency,
) -> dict[str, object]:
    def serialize_entry(entry) -> dict[str, object]:
        return {
            "snapshot_id": entry.snapshot_id,
            "created_at": entry.created_at,
            "report_type": entry.report_type,
            "mode": entry.mode,
            "execution_mode": entry.execution_mode,
            "decision_permission": entry.decision_permission,
            "consistent": entry.consistent,
            "violation_codes": list(entry.violation_codes),
            "diagnostic": entry.diagnostic,
        }

    return {
        "consistency_status": no_execution_guardrail_consistency.consistency_status,
        "total_snapshots_requested": no_execution_guardrail_consistency.total_snapshots_requested,
        "snapshots_checked": no_execution_guardrail_consistency.snapshots_checked,
        "consistent_snapshots": no_execution_guardrail_consistency.consistent_snapshots,
        "violation_count": no_execution_guardrail_consistency.violation_count,
        "entries": [
            serialize_entry(entry)
            for entry in no_execution_guardrail_consistency.entries
        ],
        "violations": [
            serialize_entry(entry)
            for entry in no_execution_guardrail_consistency.violations
        ],
        "failures": list(no_execution_guardrail_consistency.failures),
        "diagnostics": list(no_execution_guardrail_consistency.diagnostics),
        "paper_safe": no_execution_guardrail_consistency.paper_safe,
        "network_calls": no_execution_guardrail_consistency.network_calls,
        "execution_side_effects": no_execution_guardrail_consistency.execution_side_effects,
    }

def _serialize_source_registry_binding_drift(
    source_registry_binding_drift: SnapshotSourceRegistryBindingDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_registry_binding_drift.drift_classification,
        "severity_score": source_registry_binding_drift.severity_score,
        "current_source_registry_version": source_registry_binding_drift.current_source_registry_version,
        "total_snapshots_requested": source_registry_binding_drift.total_snapshots_requested,
        "snapshots_checked": source_registry_binding_drift.snapshots_checked,
        "stable_snapshots": source_registry_binding_drift.stable_snapshots,
        "drifting_snapshots": source_registry_binding_drift.drifting_snapshots,
        "degraded_snapshots": source_registry_binding_drift.degraded_snapshots,
        "invalid_snapshots": source_registry_binding_drift.invalid_snapshots,
        "registry_version_mismatch_count": source_registry_binding_drift.registry_version_mismatch_count,
        "unbound_source_ids": list(source_registry_binding_drift.unbound_source_ids),
        "provider_mismatch_source_ids": list(source_registry_binding_drift.provider_mismatch_source_ids),
        "asset_mismatch_source_ids": list(source_registry_binding_drift.asset_mismatch_source_ids),
        "malformed_record_count": source_registry_binding_drift.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "source_registry_version": entry.source_registry_version,
                "registry_version_mismatch": entry.registry_version_mismatch,
                "binding_classification": entry.binding_classification,
                "total_records": entry.total_records,
                "matched_records": entry.matched_records,
                "unbound_source_ids": list(entry.unbound_source_ids),
                "provider_mismatch_source_ids": list(entry.provider_mismatch_source_ids),
                "asset_mismatch_source_ids": list(entry.asset_mismatch_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "severity_score": entry.severity_score,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_registry_binding_drift.entries
        ],
        "failures": list(source_registry_binding_drift.failures),
        "diagnostics": list(source_registry_binding_drift.diagnostics),
        "paper_safe": source_registry_binding_drift.paper_safe,
        "network_calls": source_registry_binding_drift.network_calls,
        "execution_side_effects": source_registry_binding_drift.execution_side_effects,
    }

def _serialize_source_verification_drift(
    source_verification_drift: SnapshotSourceVerificationDrift,
) -> dict[str, object]:
    return {
        "drift_classification": source_verification_drift.drift_classification,
        "average_verification_score": source_verification_drift.average_verification_score,
        "severity_score": source_verification_drift.severity_score,
        "current_source_registry_version": source_verification_drift.current_source_registry_version,
        "total_snapshots_requested": source_verification_drift.total_snapshots_requested,
        "snapshots_checked": source_verification_drift.snapshots_checked,
        "stable_snapshots": source_verification_drift.stable_snapshots,
        "degrading_snapshots": source_verification_drift.degrading_snapshots,
        "improving_snapshots": source_verification_drift.improving_snapshots,
        "mixed_snapshots": source_verification_drift.mixed_snapshots,
        "insufficient_data_snapshots": source_verification_drift.insufficient_data_snapshots,
        "degraded_source_ids": list(source_verification_drift.degraded_source_ids),
        "improved_source_ids": list(source_verification_drift.improved_source_ids),
        "missing_verification_source_ids": list(source_verification_drift.missing_verification_source_ids),
        "unknown_registry_source_ids": list(source_verification_drift.unknown_registry_source_ids),
        "malformed_record_count": source_verification_drift.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "verification_classification": entry.verification_classification,
                "verification_score": entry.verification_score,
                "total_records": entry.total_records,
                "verified_records": entry.verified_records,
                "expected_verified_records": entry.expected_verified_records,
                "degraded_source_ids": list(entry.degraded_source_ids),
                "improved_source_ids": list(entry.improved_source_ids),
                "missing_verification_source_ids": list(entry.missing_verification_source_ids),
                "unknown_registry_source_ids": list(entry.unknown_registry_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in source_verification_drift.entries
        ],
        "failures": list(source_verification_drift.failures),
        "diagnostics": list(source_verification_drift.diagnostics),
        "paper_safe": source_verification_drift.paper_safe,
        "network_calls": source_verification_drift.network_calls,
        "execution_side_effects": source_verification_drift.execution_side_effects,
    }

def _serialize_paper_safe_source_flag_consistency(
    paper_safe_source_flag_consistency: SnapshotPaperSafeSourceFlagConsistency,
) -> dict[str, object]:
    return {
        "consistency_classification": paper_safe_source_flag_consistency.consistency_classification,
        "average_consistency_percentage": paper_safe_source_flag_consistency.average_consistency_percentage,
        "total_snapshots_requested": paper_safe_source_flag_consistency.total_snapshots_requested,
        "snapshots_checked": paper_safe_source_flag_consistency.snapshots_checked,
        "consistent_snapshots": paper_safe_source_flag_consistency.consistent_snapshots,
        "partial_snapshots": paper_safe_source_flag_consistency.partial_snapshots,
        "degraded_snapshots": paper_safe_source_flag_consistency.degraded_snapshots,
        "invalid_snapshots": paper_safe_source_flag_consistency.invalid_snapshots,
        "false_flag_source_ids": list(paper_safe_source_flag_consistency.false_flag_source_ids),
        "missing_flag_source_ids": list(paper_safe_source_flag_consistency.missing_flag_source_ids),
        "malformed_flag_source_ids": list(paper_safe_source_flag_consistency.malformed_flag_source_ids),
        "contradictory_source_ids": list(paper_safe_source_flag_consistency.contradictory_source_ids),
        "unknown_registry_source_ids": list(paper_safe_source_flag_consistency.unknown_registry_source_ids),
        "unsafe_source_ids": list(paper_safe_source_flag_consistency.unsafe_source_ids),
        "malformed_record_count": paper_safe_source_flag_consistency.malformed_record_count,
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "consistency_classification": entry.consistency_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_records": entry.total_records,
                "safe_records": entry.safe_records,
                "false_flag_source_ids": list(entry.false_flag_source_ids),
                "missing_flag_source_ids": list(entry.missing_flag_source_ids),
                "malformed_flag_source_ids": list(entry.malformed_flag_source_ids),
                "contradictory_source_ids": list(entry.contradictory_source_ids),
                "unknown_registry_source_ids": list(entry.unknown_registry_source_ids),
                "unsafe_source_ids": list(entry.unsafe_source_ids),
                "malformed_record_count": entry.malformed_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in paper_safe_source_flag_consistency.entries
        ],
        "failures": list(paper_safe_source_flag_consistency.failures),
        "diagnostics": list(paper_safe_source_flag_consistency.diagnostics),
        "paper_safe": paper_safe_source_flag_consistency.paper_safe,
        "network_calls": paper_safe_source_flag_consistency.network_calls,
        "execution_side_effects": paper_safe_source_flag_consistency.execution_side_effects,
    }

def _serialize_provider_adapter_contract_consistency(
    provider_adapter_contract_consistency: SnapshotProviderAdapterContractConsistency,
) -> dict[str, object]:
    return {
        "consistency_classification": provider_adapter_contract_consistency.consistency_classification,
        "average_consistency_percentage": provider_adapter_contract_consistency.average_consistency_percentage,
        "expected_contract": provider_adapter_contract_consistency.expected_contract,
        "total_snapshots_requested": provider_adapter_contract_consistency.total_snapshots_requested,
        "snapshots_checked": provider_adapter_contract_consistency.snapshots_checked,
        "consistent_snapshots": provider_adapter_contract_consistency.consistent_snapshots,
        "partial_snapshots": provider_adapter_contract_consistency.partial_snapshots,
        "degraded_snapshots": provider_adapter_contract_consistency.degraded_snapshots,
        "invalid_snapshots": provider_adapter_contract_consistency.invalid_snapshots,
        "missing_contract_snapshot_ids": list(provider_adapter_contract_consistency.missing_contract_snapshot_ids),
        "mismatched_contract_snapshot_ids": list(provider_adapter_contract_consistency.mismatched_contract_snapshot_ids),
        "bound_source_mismatch_snapshot_ids": list(provider_adapter_contract_consistency.bound_source_mismatch_snapshot_ids),
        "malformed_snapshot_ids": list(provider_adapter_contract_consistency.malformed_snapshot_ids),
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "consistency_classification": entry.consistency_classification,
                "consistency_percentage": entry.consistency_percentage,
                "source_observation_contract": entry.source_observation_contract,
                "provider_adapter_contract": entry.provider_adapter_contract,
                "source_observation_total_bound_sources": entry.source_observation_total_bound_sources,
                "provider_adapter_total_bound_sources": entry.provider_adapter_total_bound_sources,
                "missing_fields": list(entry.missing_fields),
                "mismatched_fields": list(entry.mismatched_fields),
                "malformed_field_count": entry.malformed_field_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in provider_adapter_contract_consistency.entries
        ],
        "failures": list(provider_adapter_contract_consistency.failures),
        "diagnostics": list(provider_adapter_contract_consistency.diagnostics),
        "paper_safe": provider_adapter_contract_consistency.paper_safe,
        "network_calls": provider_adapter_contract_consistency.network_calls,
        "execution_side_effects": provider_adapter_contract_consistency.execution_side_effects,
    }

def _serialize_source_diagnostics_contract_coverage_drift(
    contract_coverage_drift: SnapshotReplaySourceDiagnosticsContractCoverageDrift,
) -> dict[str, object]:
    endpoint_coverage_consistency = (
        contract_coverage_drift.endpoint_coverage_consistency
    )
    return {
        "drift_classification": contract_coverage_drift.drift_classification,
        "average_coverage_percentage": contract_coverage_drift.average_coverage_percentage,
        "severity_score": contract_coverage_drift.severity_score,
        "contract_source": contract_coverage_drift.contract_source,
        "total_snapshots_requested": contract_coverage_drift.total_snapshots_requested,
        "snapshots_checked": contract_coverage_drift.snapshots_checked,
        "stable_snapshots": contract_coverage_drift.stable_snapshots,
        "drifting_snapshots": contract_coverage_drift.drifting_snapshots,
        "degraded_snapshots": contract_coverage_drift.degraded_snapshots,
        "insufficient_data_snapshots": contract_coverage_drift.insufficient_data_snapshots,
        "missing_service_builder_names": list(
            contract_coverage_drift.missing_service_builder_names
        ),
        "missing_api_route_paths": list(
            contract_coverage_drift.missing_api_route_paths
        ),
        "missing_serializer_names": list(
            contract_coverage_drift.missing_serializer_names
        ),
        "endpoint_coverage_consistency": {
            "consistency_classification": endpoint_coverage_consistency.consistency_classification,
            "consistency_percentage": endpoint_coverage_consistency.consistency_percentage,
            "total_diagnostics_registered": endpoint_coverage_consistency.total_diagnostics_registered,
            "service_builder_count": endpoint_coverage_consistency.service_builder_count,
            "api_route_count": endpoint_coverage_consistency.api_route_count,
            "serializer_count": endpoint_coverage_consistency.serializer_count,
            "consistent_diagnostic_count": endpoint_coverage_consistency.consistent_diagnostic_count,
            "partial_diagnostic_count": endpoint_coverage_consistency.partial_diagnostic_count,
            "degraded_diagnostic_count": endpoint_coverage_consistency.degraded_diagnostic_count,
            "missing_service_builder_names": list(
                endpoint_coverage_consistency.missing_service_builder_names
            ),
            "missing_api_route_paths": list(
                endpoint_coverage_consistency.missing_api_route_paths
            ),
            "missing_serializer_names": list(
                endpoint_coverage_consistency.missing_serializer_names
            ),
            "entries": [
                {
                    "diagnostic_key": entry.diagnostic_key,
                    "diagnostic_group": entry.diagnostic_group,
                    "service_builder_name": entry.service_builder_name,
                    "api_route_path": entry.api_route_path,
                    "serializer_name": entry.serializer_name,
                    "service_builder_present": entry.service_builder_present,
                    "api_route_present": entry.api_route_present,
                    "serializer_present": entry.serializer_present,
                    "consistency_classification": entry.consistency_classification,
                    "consistency_percentage": entry.consistency_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in endpoint_coverage_consistency.entries
            ],
            "diagnostics": list(endpoint_coverage_consistency.diagnostics),
            "paper_safe": endpoint_coverage_consistency.paper_safe,
            "network_calls": endpoint_coverage_consistency.network_calls,
            "execution_side_effects": endpoint_coverage_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "coverage_percentage": entry.coverage_percentage,
                "total_diagnostics_registered": entry.total_diagnostics_registered,
                "covered_service_builder_count": entry.covered_service_builder_count,
                "covered_api_route_count": entry.covered_api_route_count,
                "covered_serializer_count": entry.covered_serializer_count,
                "missing_service_builder_count": entry.missing_service_builder_count,
                "missing_api_route_count": entry.missing_api_route_count,
                "missing_serializer_count": entry.missing_serializer_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in contract_coverage_drift.entries
        ],
        "failures": list(contract_coverage_drift.failures),
        "diagnostics": list(contract_coverage_drift.diagnostics),
        "paper_safe": contract_coverage_drift.paper_safe,
        "network_calls": contract_coverage_drift.network_calls,
        "execution_side_effects": contract_coverage_drift.execution_side_effects,
    }


def _serialize_source_diagnostic_group_coverage_drift(
    group_coverage_drift: SnapshotReplaySourceDiagnosticGroupCoverageDrift,
) -> dict[str, object]:
    route_serializer_group_alignment_consistency = (
        group_coverage_drift.route_serializer_group_alignment_consistency
    )
    return {
        "drift_classification": group_coverage_drift.drift_classification,
        "average_coverage_percentage": group_coverage_drift.average_coverage_percentage,
        "severity_score": group_coverage_drift.severity_score,
        "contract_source": group_coverage_drift.contract_source,
        "total_snapshots_requested": group_coverage_drift.total_snapshots_requested,
        "snapshots_checked": group_coverage_drift.snapshots_checked,
        "stable_snapshots": group_coverage_drift.stable_snapshots,
        "drifting_snapshots": group_coverage_drift.drifting_snapshots,
        "degraded_snapshots": group_coverage_drift.degraded_snapshots,
        "insufficient_data_snapshots": group_coverage_drift.insufficient_data_snapshots,
        "missing_contract_groups": list(group_coverage_drift.missing_contract_groups),
        "missing_service_groups": list(group_coverage_drift.missing_service_groups),
        "missing_api_route_groups": list(group_coverage_drift.missing_api_route_groups),
        "missing_serializer_groups": list(group_coverage_drift.missing_serializer_groups),
        "missing_rolling_bundle_groups": list(
            group_coverage_drift.missing_rolling_bundle_groups
        ),
        "route_serializer_group_alignment_consistency": {
            "consistency_classification": route_serializer_group_alignment_consistency.consistency_classification,
            "consistency_percentage": route_serializer_group_alignment_consistency.consistency_percentage,
            "total_groups_registered": route_serializer_group_alignment_consistency.total_groups_registered,
            "contract_group_count": route_serializer_group_alignment_consistency.contract_group_count,
            "service_group_count": route_serializer_group_alignment_consistency.service_group_count,
            "api_route_group_count": route_serializer_group_alignment_consistency.api_route_group_count,
            "serializer_group_count": route_serializer_group_alignment_consistency.serializer_group_count,
            "rolling_bundle_group_count": route_serializer_group_alignment_consistency.rolling_bundle_group_count,
            "consistent_group_count": route_serializer_group_alignment_consistency.consistent_group_count,
            "partial_group_count": route_serializer_group_alignment_consistency.partial_group_count,
            "degraded_group_count": route_serializer_group_alignment_consistency.degraded_group_count,
            "missing_contract_groups": list(
                route_serializer_group_alignment_consistency.missing_contract_groups
            ),
            "missing_service_groups": list(
                route_serializer_group_alignment_consistency.missing_service_groups
            ),
            "missing_api_route_groups": list(
                route_serializer_group_alignment_consistency.missing_api_route_groups
            ),
            "missing_serializer_groups": list(
                route_serializer_group_alignment_consistency.missing_serializer_groups
            ),
            "missing_rolling_bundle_groups": list(
                route_serializer_group_alignment_consistency.missing_rolling_bundle_groups
            ),
            "entries": [
                {
                    "diagnostic_group": entry.diagnostic_group,
                    "contract_group_present": entry.contract_group_present,
                    "service_group_present": entry.service_group_present,
                    "api_route_group_present": entry.api_route_group_present,
                    "serializer_group_present": entry.serializer_group_present,
                    "rolling_bundle_group_present": entry.rolling_bundle_group_present,
                    "consistency_classification": entry.consistency_classification,
                    "consistency_percentage": entry.consistency_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in route_serializer_group_alignment_consistency.entries
            ],
            "diagnostics": list(route_serializer_group_alignment_consistency.diagnostics),
            "paper_safe": route_serializer_group_alignment_consistency.paper_safe,
            "network_calls": route_serializer_group_alignment_consistency.network_calls,
            "execution_side_effects": route_serializer_group_alignment_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "coverage_percentage": entry.coverage_percentage,
                "total_groups_registered": entry.total_groups_registered,
                "covered_contract_group_count": entry.covered_contract_group_count,
                "covered_service_group_count": entry.covered_service_group_count,
                "covered_api_route_group_count": entry.covered_api_route_group_count,
                "covered_serializer_group_count": entry.covered_serializer_group_count,
                "covered_rolling_bundle_group_count": entry.covered_rolling_bundle_group_count,
                "missing_contract_group_count": entry.missing_contract_group_count,
                "missing_service_group_count": entry.missing_service_group_count,
                "missing_api_route_group_count": entry.missing_api_route_group_count,
                "missing_serializer_group_count": entry.missing_serializer_group_count,
                "missing_rolling_bundle_group_count": entry.missing_rolling_bundle_group_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in group_coverage_drift.entries
        ],
        "failures": list(group_coverage_drift.failures),
        "diagnostics": list(group_coverage_drift.diagnostics),
        "paper_safe": group_coverage_drift.paper_safe,
        "network_calls": group_coverage_drift.network_calls,
        "execution_side_effects": group_coverage_drift.execution_side_effects,
    }


def _serialize_source_diagnostic_surface_count_drift(
    surface_count_drift: SnapshotReplaySourceDiagnosticSurfaceCountDrift,
) -> dict[str, object]:
    contract_surface_count_consistency = (
        surface_count_drift.contract_surface_count_consistency
    )
    return {
        "drift_classification": surface_count_drift.drift_classification,
        "average_consistency_percentage": surface_count_drift.average_consistency_percentage,
        "severity_score": surface_count_drift.severity_score,
        "contract_source": surface_count_drift.contract_source,
        "total_snapshots_requested": surface_count_drift.total_snapshots_requested,
        "snapshots_checked": surface_count_drift.snapshots_checked,
        "stable_snapshots": surface_count_drift.stable_snapshots,
        "drifting_snapshots": surface_count_drift.drifting_snapshots,
        "degraded_snapshots": surface_count_drift.degraded_snapshots,
        "insufficient_data_snapshots": surface_count_drift.insufficient_data_snapshots,
        "mismatched_surface_names": list(surface_count_drift.mismatched_surface_names),
        "group_alignment_consistency_classification": (
            surface_count_drift.group_alignment_consistency_classification
        ),
        "group_alignment_clean_but_count_mismatched": (
            surface_count_drift.group_alignment_clean_but_count_mismatched
        ),
        "contract_surface_count_consistency": {
            "consistency_classification": contract_surface_count_consistency.consistency_classification,
            "consistency_percentage": contract_surface_count_consistency.consistency_percentage,
            "total_surfaces_checked": contract_surface_count_consistency.total_surfaces_checked,
            "total_diagnostics_registered": contract_surface_count_consistency.total_diagnostics_registered,
            "total_groups_registered": contract_surface_count_consistency.total_groups_registered,
            "contract_registry_count": contract_surface_count_consistency.contract_registry_count,
            "service_builder_count": contract_surface_count_consistency.service_builder_count,
            "api_route_count": contract_surface_count_consistency.api_route_count,
            "serializer_count": contract_surface_count_consistency.serializer_count,
            "rolling_bundle_count": contract_surface_count_consistency.rolling_bundle_count,
            "diagnostic_group_count": contract_surface_count_consistency.diagnostic_group_count,
            "consistent_surface_count": contract_surface_count_consistency.consistent_surface_count,
            "mismatched_surface_count": contract_surface_count_consistency.mismatched_surface_count,
            "mismatched_surface_names": list(
                contract_surface_count_consistency.mismatched_surface_names
            ),
            "group_alignment_consistency_classification": (
                contract_surface_count_consistency.group_alignment_consistency_classification
            ),
            "group_alignment_clean_but_count_mismatched": (
                contract_surface_count_consistency.group_alignment_clean_but_count_mismatched
            ),
            "entries": [
                {
                    "surface_name": entry.surface_name,
                    "expected_count": entry.expected_count,
                    "actual_count": entry.actual_count,
                    "count_delta": entry.count_delta,
                    "consistency_classification": entry.consistency_classification,
                    "consistency_percentage": entry.consistency_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in contract_surface_count_consistency.entries
            ],
            "diagnostics": list(contract_surface_count_consistency.diagnostics),
            "paper_safe": contract_surface_count_consistency.paper_safe,
            "network_calls": contract_surface_count_consistency.network_calls,
            "execution_side_effects": contract_surface_count_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_surfaces_checked": entry.total_surfaces_checked,
                "total_diagnostics_registered": entry.total_diagnostics_registered,
                "total_groups_registered": entry.total_groups_registered,
                "contract_registry_count": entry.contract_registry_count,
                "service_builder_count": entry.service_builder_count,
                "api_route_count": entry.api_route_count,
                "serializer_count": entry.serializer_count,
                "rolling_bundle_count": entry.rolling_bundle_count,
                "diagnostic_group_count": entry.diagnostic_group_count,
                "mismatched_surface_count": entry.mismatched_surface_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in surface_count_drift.entries
        ],
        "failures": list(surface_count_drift.failures),
        "diagnostics": list(surface_count_drift.diagnostics),
        "paper_safe": surface_count_drift.paper_safe,
        "network_calls": surface_count_drift.network_calls,
        "execution_side_effects": surface_count_drift.execution_side_effects,
    }


def _serialize_source_diagnostic_metadata_completeness_drift(
    metadata_completeness_drift: SnapshotReplaySourceDiagnosticMetadataCompletenessDrift,
) -> dict[str, object]:
    contract_metadata_normalization_consistency = (
        metadata_completeness_drift.contract_metadata_normalization_consistency
    )
    return {
        "drift_classification": metadata_completeness_drift.drift_classification,
        "average_completeness_percentage": metadata_completeness_drift.average_completeness_percentage,
        "severity_score": metadata_completeness_drift.severity_score,
        "contract_source": metadata_completeness_drift.contract_source,
        "total_snapshots_requested": metadata_completeness_drift.total_snapshots_requested,
        "snapshots_checked": metadata_completeness_drift.snapshots_checked,
        "stable_snapshots": metadata_completeness_drift.stable_snapshots,
        "drifting_snapshots": metadata_completeness_drift.drifting_snapshots,
        "degraded_snapshots": metadata_completeness_drift.degraded_snapshots,
        "insufficient_data_snapshots": metadata_completeness_drift.insufficient_data_snapshots,
        "missing_metadata_field_count": metadata_completeness_drift.missing_metadata_field_count,
        "invalid_metadata_field_count": metadata_completeness_drift.invalid_metadata_field_count,
        "duplicate_metadata_record_count": metadata_completeness_drift.duplicate_metadata_record_count,
        "conflicting_metadata_record_count": metadata_completeness_drift.conflicting_metadata_record_count,
        "missing_group_diagnostic_keys": list(
            metadata_completeness_drift.missing_group_diagnostic_keys
        ),
        "invalid_group_diagnostic_keys": list(
            metadata_completeness_drift.invalid_group_diagnostic_keys
        ),
        "invalid_group_names": list(metadata_completeness_drift.invalid_group_names),
        "invalid_diagnostic_slugs": list(
            metadata_completeness_drift.invalid_diagnostic_slugs
        ),
        "invalid_diagnostic_keys": list(
            metadata_completeness_drift.invalid_diagnostic_keys
        ),
        "missing_service_builder_keys": list(
            metadata_completeness_drift.missing_service_builder_keys
        ),
        "invalid_service_builder_keys": list(
            metadata_completeness_drift.invalid_service_builder_keys
        ),
        "missing_api_route_keys": list(
            metadata_completeness_drift.missing_api_route_keys
        ),
        "invalid_api_route_keys": list(
            metadata_completeness_drift.invalid_api_route_keys
        ),
        "missing_serializer_keys": list(
            metadata_completeness_drift.missing_serializer_keys
        ),
        "invalid_serializer_keys": list(
            metadata_completeness_drift.invalid_serializer_keys
        ),
        "missing_rolling_bundle_keys": list(
            metadata_completeness_drift.missing_rolling_bundle_keys
        ),
        "invalid_rolling_bundle_keys": list(
            metadata_completeness_drift.invalid_rolling_bundle_keys
        ),
        "missing_rolling_serializer_keys": list(
            metadata_completeness_drift.missing_rolling_serializer_keys
        ),
        "invalid_rolling_serializer_keys": list(
            metadata_completeness_drift.invalid_rolling_serializer_keys
        ),
        "duplicate_metadata_records": list(
            metadata_completeness_drift.duplicate_metadata_records
        ),
        "conflicting_metadata_records": list(
            metadata_completeness_drift.conflicting_metadata_records
        ),
        "contract_metadata_normalization_consistency": {
            "consistency_classification": contract_metadata_normalization_consistency.consistency_classification,
            "completeness_percentage": contract_metadata_normalization_consistency.completeness_percentage,
            "total_diagnostics_registered": contract_metadata_normalization_consistency.total_diagnostics_registered,
            "complete_metadata_count": contract_metadata_normalization_consistency.complete_metadata_count,
            "partial_metadata_count": contract_metadata_normalization_consistency.partial_metadata_count,
            "degraded_metadata_count": contract_metadata_normalization_consistency.degraded_metadata_count,
            "missing_metadata_field_count": contract_metadata_normalization_consistency.missing_metadata_field_count,
            "invalid_metadata_field_count": contract_metadata_normalization_consistency.invalid_metadata_field_count,
            "duplicate_metadata_record_count": contract_metadata_normalization_consistency.duplicate_metadata_record_count,
            "conflicting_metadata_record_count": contract_metadata_normalization_consistency.conflicting_metadata_record_count,
            "missing_group_diagnostic_keys": list(
                contract_metadata_normalization_consistency.missing_group_diagnostic_keys
            ),
            "invalid_group_diagnostic_keys": list(
                contract_metadata_normalization_consistency.invalid_group_diagnostic_keys
            ),
            "invalid_group_names": list(
                contract_metadata_normalization_consistency.invalid_group_names
            ),
            "invalid_diagnostic_slugs": list(
                contract_metadata_normalization_consistency.invalid_diagnostic_slugs
            ),
            "invalid_diagnostic_keys": list(
                contract_metadata_normalization_consistency.invalid_diagnostic_keys
            ),
            "missing_service_builder_keys": list(
                contract_metadata_normalization_consistency.missing_service_builder_keys
            ),
            "invalid_service_builder_keys": list(
                contract_metadata_normalization_consistency.invalid_service_builder_keys
            ),
            "missing_api_route_keys": list(
                contract_metadata_normalization_consistency.missing_api_route_keys
            ),
            "invalid_api_route_keys": list(
                contract_metadata_normalization_consistency.invalid_api_route_keys
            ),
            "missing_serializer_keys": list(
                contract_metadata_normalization_consistency.missing_serializer_keys
            ),
            "invalid_serializer_keys": list(
                contract_metadata_normalization_consistency.invalid_serializer_keys
            ),
            "missing_rolling_bundle_keys": list(
                contract_metadata_normalization_consistency.missing_rolling_bundle_keys
            ),
            "invalid_rolling_bundle_keys": list(
                contract_metadata_normalization_consistency.invalid_rolling_bundle_keys
            ),
            "missing_rolling_serializer_keys": list(
                contract_metadata_normalization_consistency.missing_rolling_serializer_keys
            ),
            "invalid_rolling_serializer_keys": list(
                contract_metadata_normalization_consistency.invalid_rolling_serializer_keys
            ),
            "duplicate_metadata_records": list(
                contract_metadata_normalization_consistency.duplicate_metadata_records
            ),
            "conflicting_metadata_records": list(
                contract_metadata_normalization_consistency.conflicting_metadata_records
            ),
            "entries": [
                {
                    "diagnostic_slug": entry.diagnostic_slug,
                    "diagnostic_key": entry.diagnostic_key,
                    "diagnostic_group": entry.diagnostic_group,
                    "service_builder_name": entry.service_builder_name,
                    "api_route_path": entry.api_route_path,
                    "serializer_name": entry.serializer_name,
                    "rolling_bundle_field_name": entry.rolling_bundle_field_name,
                    "rolling_serializer_field_name": entry.rolling_serializer_field_name,
                    "contract_group_present": entry.contract_group_present,
                    "service_builder_key_present": entry.service_builder_key_present,
                    "api_route_key_present": entry.api_route_key_present,
                    "serializer_key_present": entry.serializer_key_present,
                    "rolling_bundle_key_present": entry.rolling_bundle_key_present,
                    "rolling_serializer_key_present": entry.rolling_serializer_key_present,
                    "missing_metadata_fields": list(entry.missing_metadata_fields),
                    "invalid_metadata_fields": list(entry.invalid_metadata_fields),
                    "duplicate_metadata_fields": list(entry.duplicate_metadata_fields),
                    "conflicting_metadata_fields": list(entry.conflicting_metadata_fields),
                    "consistency_classification": entry.consistency_classification,
                    "completeness_percentage": entry.completeness_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in contract_metadata_normalization_consistency.entries
            ],
            "diagnostics": list(contract_metadata_normalization_consistency.diagnostics),
            "paper_safe": contract_metadata_normalization_consistency.paper_safe,
            "network_calls": contract_metadata_normalization_consistency.network_calls,
            "execution_side_effects": contract_metadata_normalization_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "completeness_percentage": entry.completeness_percentage,
                "total_diagnostics_registered": entry.total_diagnostics_registered,
                "complete_metadata_count": entry.complete_metadata_count,
                "partial_metadata_count": entry.partial_metadata_count,
                "degraded_metadata_count": entry.degraded_metadata_count,
                "missing_metadata_field_count": entry.missing_metadata_field_count,
                "invalid_metadata_field_count": entry.invalid_metadata_field_count,
                "duplicate_metadata_record_count": entry.duplicate_metadata_record_count,
                "conflicting_metadata_record_count": entry.conflicting_metadata_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in metadata_completeness_drift.entries
        ],
        "failures": list(metadata_completeness_drift.failures),
        "diagnostics": list(metadata_completeness_drift.diagnostics),
        "paper_safe": metadata_completeness_drift.paper_safe,
        "network_calls": metadata_completeness_drift.network_calls,
        "execution_side_effects": metadata_completeness_drift.execution_side_effects,
    }


def _serialize_source_diagnostic_naming_contract_drift(
    naming_contract_drift: SnapshotReplaySourceDiagnosticNamingContractDrift,
) -> dict[str, object]:
    naming_consistency = naming_contract_drift.builder_serializer_route_naming_consistency
    return {
        "drift_classification": naming_contract_drift.drift_classification,
        "average_consistency_percentage": naming_contract_drift.average_consistency_percentage,
        "severity_score": naming_contract_drift.severity_score,
        "contract_source": naming_contract_drift.contract_source,
        "total_snapshots_requested": naming_contract_drift.total_snapshots_requested,
        "snapshots_checked": naming_contract_drift.snapshots_checked,
        "stable_snapshots": naming_contract_drift.stable_snapshots,
        "drifting_snapshots": naming_contract_drift.drifting_snapshots,
        "degraded_snapshots": naming_contract_drift.degraded_snapshots,
        "insufficient_data_snapshots": naming_contract_drift.insufficient_data_snapshots,
        "invalid_name_field_count": naming_contract_drift.invalid_name_field_count,
        "mismatched_name_field_count": naming_contract_drift.mismatched_name_field_count,
        "duplicate_name_record_count": naming_contract_drift.duplicate_name_record_count,
        "conflicting_name_record_count": naming_contract_drift.conflicting_name_record_count,
        "invalid_diagnostic_slugs": list(
            naming_contract_drift.invalid_diagnostic_slugs
        ),
        "invalid_diagnostic_keys": list(
            naming_contract_drift.invalid_diagnostic_keys
        ),
        "mismatched_diagnostic_keys": list(
            naming_contract_drift.mismatched_diagnostic_keys
        ),
        "invalid_service_builder_names": list(
            naming_contract_drift.invalid_service_builder_names
        ),
        "mismatched_service_builder_names": list(
            naming_contract_drift.mismatched_service_builder_names
        ),
        "invalid_serializer_names": list(
            naming_contract_drift.invalid_serializer_names
        ),
        "mismatched_serializer_names": list(
            naming_contract_drift.mismatched_serializer_names
        ),
        "invalid_api_route_paths": list(
            naming_contract_drift.invalid_api_route_paths
        ),
        "mismatched_api_route_paths": list(
            naming_contract_drift.mismatched_api_route_paths
        ),
        "invalid_rolling_bundle_field_names": list(
            naming_contract_drift.invalid_rolling_bundle_field_names
        ),
        "mismatched_rolling_bundle_field_names": list(
            naming_contract_drift.mismatched_rolling_bundle_field_names
        ),
        "invalid_rolling_serializer_field_names": list(
            naming_contract_drift.invalid_rolling_serializer_field_names
        ),
        "mismatched_rolling_serializer_field_names": list(
            naming_contract_drift.mismatched_rolling_serializer_field_names
        ),
        "duplicate_name_records": list(naming_contract_drift.duplicate_name_records),
        "conflicting_name_records": list(
            naming_contract_drift.conflicting_name_records
        ),
        "builder_serializer_route_naming_consistency": {
            "consistency_classification": naming_consistency.consistency_classification,
            "consistency_percentage": naming_consistency.consistency_percentage,
            "total_diagnostics_registered": naming_consistency.total_diagnostics_registered,
            "consistent_diagnostic_count": naming_consistency.consistent_diagnostic_count,
            "partial_diagnostic_count": naming_consistency.partial_diagnostic_count,
            "degraded_diagnostic_count": naming_consistency.degraded_diagnostic_count,
            "invalid_name_field_count": naming_consistency.invalid_name_field_count,
            "mismatched_name_field_count": naming_consistency.mismatched_name_field_count,
            "duplicate_name_record_count": naming_consistency.duplicate_name_record_count,
            "conflicting_name_record_count": naming_consistency.conflicting_name_record_count,
            "invalid_diagnostic_slugs": list(naming_consistency.invalid_diagnostic_slugs),
            "invalid_diagnostic_keys": list(naming_consistency.invalid_diagnostic_keys),
            "mismatched_diagnostic_keys": list(
                naming_consistency.mismatched_diagnostic_keys
            ),
            "invalid_service_builder_names": list(
                naming_consistency.invalid_service_builder_names
            ),
            "mismatched_service_builder_names": list(
                naming_consistency.mismatched_service_builder_names
            ),
            "invalid_serializer_names": list(
                naming_consistency.invalid_serializer_names
            ),
            "mismatched_serializer_names": list(
                naming_consistency.mismatched_serializer_names
            ),
            "invalid_api_route_paths": list(
                naming_consistency.invalid_api_route_paths
            ),
            "mismatched_api_route_paths": list(
                naming_consistency.mismatched_api_route_paths
            ),
            "invalid_rolling_bundle_field_names": list(
                naming_consistency.invalid_rolling_bundle_field_names
            ),
            "mismatched_rolling_bundle_field_names": list(
                naming_consistency.mismatched_rolling_bundle_field_names
            ),
            "invalid_rolling_serializer_field_names": list(
                naming_consistency.invalid_rolling_serializer_field_names
            ),
            "mismatched_rolling_serializer_field_names": list(
                naming_consistency.mismatched_rolling_serializer_field_names
            ),
            "duplicate_name_records": list(naming_consistency.duplicate_name_records),
            "conflicting_name_records": list(
                naming_consistency.conflicting_name_records
            ),
            "entries": [
                {
                    "diagnostic_slug": entry.diagnostic_slug,
                    "expected_diagnostic_key": entry.expected_diagnostic_key,
                    "actual_diagnostic_key": entry.actual_diagnostic_key,
                    "expected_service_builder_name": entry.expected_service_builder_name,
                    "actual_service_builder_name": entry.actual_service_builder_name,
                    "expected_serializer_name": entry.expected_serializer_name,
                    "actual_serializer_name": entry.actual_serializer_name,
                    "expected_api_route_path": entry.expected_api_route_path,
                    "actual_api_route_path": entry.actual_api_route_path,
                    "expected_rolling_bundle_field_name": entry.expected_rolling_bundle_field_name,
                    "actual_rolling_bundle_field_name": entry.actual_rolling_bundle_field_name,
                    "expected_rolling_serializer_field_name": entry.expected_rolling_serializer_field_name,
                    "actual_rolling_serializer_field_name": entry.actual_rolling_serializer_field_name,
                    "service_builder_surface_present": entry.service_builder_surface_present,
                    "serializer_surface_present": entry.serializer_surface_present,
                    "api_route_surface_present": entry.api_route_surface_present,
                    "rolling_bundle_surface_present": entry.rolling_bundle_surface_present,
                    "rolling_serializer_surface_present": entry.rolling_serializer_surface_present,
                    "invalid_name_fields": list(entry.invalid_name_fields),
                    "mismatched_name_fields": list(entry.mismatched_name_fields),
                    "duplicate_name_fields": list(entry.duplicate_name_fields),
                    "conflicting_name_fields": list(entry.conflicting_name_fields),
                    "consistency_classification": entry.consistency_classification,
                    "consistency_percentage": entry.consistency_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in naming_consistency.entries
            ],
            "diagnostics": list(naming_consistency.diagnostics),
            "paper_safe": naming_consistency.paper_safe,
            "network_calls": naming_consistency.network_calls,
            "execution_side_effects": naming_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_diagnostics_registered": entry.total_diagnostics_registered,
                "invalid_name_field_count": entry.invalid_name_field_count,
                "mismatched_name_field_count": entry.mismatched_name_field_count,
                "duplicate_name_record_count": entry.duplicate_name_record_count,
                "conflicting_name_record_count": entry.conflicting_name_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in naming_contract_drift.entries
        ],
        "failures": list(naming_contract_drift.failures),
        "diagnostics": list(naming_contract_drift.diagnostics),
        "paper_safe": naming_contract_drift.paper_safe,
        "network_calls": naming_contract_drift.network_calls,
        "execution_side_effects": naming_contract_drift.execution_side_effects,
    }


def _serialize_source_diagnostic_contract_signature_drift(
    contract_signature_drift: SnapshotReplaySourceDiagnosticContractSignatureDrift,
) -> dict[str, object]:
    signature_consistency = (
        contract_signature_drift.full_surface_contract_signature_consistency
    )
    return {
        "drift_classification": contract_signature_drift.drift_classification,
        "average_consistency_percentage": contract_signature_drift.average_consistency_percentage,
        "severity_score": contract_signature_drift.severity_score,
        "contract_source": contract_signature_drift.contract_source,
        "total_snapshots_requested": contract_signature_drift.total_snapshots_requested,
        "snapshots_checked": contract_signature_drift.snapshots_checked,
        "stable_snapshots": contract_signature_drift.stable_snapshots,
        "drifting_snapshots": contract_signature_drift.drifting_snapshots,
        "degraded_snapshots": contract_signature_drift.degraded_snapshots,
        "insufficient_data_snapshots": contract_signature_drift.insufficient_data_snapshots,
        "missing_signature_component_count": contract_signature_drift.missing_signature_component_count,
        "invalid_signature_component_count": contract_signature_drift.invalid_signature_component_count,
        "mismatched_signature_component_count": contract_signature_drift.mismatched_signature_component_count,
        "duplicate_signature_record_count": contract_signature_drift.duplicate_signature_record_count,
        "conflicting_signature_record_count": contract_signature_drift.conflicting_signature_record_count,
        "missing_contract_signatures": list(
            contract_signature_drift.missing_contract_signatures
        ),
        "invalid_contract_signatures": list(
            contract_signature_drift.invalid_contract_signatures
        ),
        "mismatched_contract_signatures": list(
            contract_signature_drift.mismatched_contract_signatures
        ),
        "missing_service_builder_signatures": list(
            contract_signature_drift.missing_service_builder_signatures
        ),
        "invalid_service_builder_signatures": list(
            contract_signature_drift.invalid_service_builder_signatures
        ),
        "mismatched_service_builder_signatures": list(
            contract_signature_drift.mismatched_service_builder_signatures
        ),
        "missing_serializer_signatures": list(
            contract_signature_drift.missing_serializer_signatures
        ),
        "invalid_serializer_signatures": list(
            contract_signature_drift.invalid_serializer_signatures
        ),
        "mismatched_serializer_signatures": list(
            contract_signature_drift.mismatched_serializer_signatures
        ),
        "missing_api_route_signatures": list(
            contract_signature_drift.missing_api_route_signatures
        ),
        "invalid_api_route_signatures": list(
            contract_signature_drift.invalid_api_route_signatures
        ),
        "mismatched_api_route_signatures": list(
            contract_signature_drift.mismatched_api_route_signatures
        ),
        "missing_rolling_bundle_signatures": list(
            contract_signature_drift.missing_rolling_bundle_signatures
        ),
        "invalid_rolling_bundle_signatures": list(
            contract_signature_drift.invalid_rolling_bundle_signatures
        ),
        "mismatched_rolling_bundle_signatures": list(
            contract_signature_drift.mismatched_rolling_bundle_signatures
        ),
        "missing_rolling_serializer_signatures": list(
            contract_signature_drift.missing_rolling_serializer_signatures
        ),
        "invalid_rolling_serializer_signatures": list(
            contract_signature_drift.invalid_rolling_serializer_signatures
        ),
        "mismatched_rolling_serializer_signatures": list(
            contract_signature_drift.mismatched_rolling_serializer_signatures
        ),
        "duplicate_signature_records": list(
            contract_signature_drift.duplicate_signature_records
        ),
        "conflicting_signature_records": list(
            contract_signature_drift.conflicting_signature_records
        ),
        "full_surface_contract_signature_consistency": {
            "consistency_classification": signature_consistency.consistency_classification,
            "consistency_percentage": signature_consistency.consistency_percentage,
            "total_diagnostics_registered": signature_consistency.total_diagnostics_registered,
            "consistent_diagnostic_count": signature_consistency.consistent_diagnostic_count,
            "partial_diagnostic_count": signature_consistency.partial_diagnostic_count,
            "degraded_diagnostic_count": signature_consistency.degraded_diagnostic_count,
            "missing_signature_component_count": signature_consistency.missing_signature_component_count,
            "invalid_signature_component_count": signature_consistency.invalid_signature_component_count,
            "mismatched_signature_component_count": signature_consistency.mismatched_signature_component_count,
            "duplicate_signature_record_count": signature_consistency.duplicate_signature_record_count,
            "conflicting_signature_record_count": signature_consistency.conflicting_signature_record_count,
            "missing_contract_signatures": list(
                signature_consistency.missing_contract_signatures
            ),
            "invalid_contract_signatures": list(
                signature_consistency.invalid_contract_signatures
            ),
            "mismatched_contract_signatures": list(
                signature_consistency.mismatched_contract_signatures
            ),
            "missing_service_builder_signatures": list(
                signature_consistency.missing_service_builder_signatures
            ),
            "invalid_service_builder_signatures": list(
                signature_consistency.invalid_service_builder_signatures
            ),
            "mismatched_service_builder_signatures": list(
                signature_consistency.mismatched_service_builder_signatures
            ),
            "missing_serializer_signatures": list(
                signature_consistency.missing_serializer_signatures
            ),
            "invalid_serializer_signatures": list(
                signature_consistency.invalid_serializer_signatures
            ),
            "mismatched_serializer_signatures": list(
                signature_consistency.mismatched_serializer_signatures
            ),
            "missing_api_route_signatures": list(
                signature_consistency.missing_api_route_signatures
            ),
            "invalid_api_route_signatures": list(
                signature_consistency.invalid_api_route_signatures
            ),
            "mismatched_api_route_signatures": list(
                signature_consistency.mismatched_api_route_signatures
            ),
            "missing_rolling_bundle_signatures": list(
                signature_consistency.missing_rolling_bundle_signatures
            ),
            "invalid_rolling_bundle_signatures": list(
                signature_consistency.invalid_rolling_bundle_signatures
            ),
            "mismatched_rolling_bundle_signatures": list(
                signature_consistency.mismatched_rolling_bundle_signatures
            ),
            "missing_rolling_serializer_signatures": list(
                signature_consistency.missing_rolling_serializer_signatures
            ),
            "invalid_rolling_serializer_signatures": list(
                signature_consistency.invalid_rolling_serializer_signatures
            ),
            "mismatched_rolling_serializer_signatures": list(
                signature_consistency.mismatched_rolling_serializer_signatures
            ),
            "duplicate_signature_records": list(
                signature_consistency.duplicate_signature_records
            ),
            "conflicting_signature_records": list(
                signature_consistency.conflicting_signature_records
            ),
            "entries": [
                {
                    "diagnostic_slug": entry.diagnostic_slug,
                    "expected_contract_signature": entry.expected_contract_signature,
                    "actual_contract_signature": entry.actual_contract_signature,
                    "expected_service_builder_signature": entry.expected_service_builder_signature,
                    "actual_service_builder_signature": entry.actual_service_builder_signature,
                    "expected_serializer_signature": entry.expected_serializer_signature,
                    "actual_serializer_signature": entry.actual_serializer_signature,
                    "expected_api_route_signature": entry.expected_api_route_signature,
                    "actual_api_route_signature": entry.actual_api_route_signature,
                    "expected_rolling_bundle_signature": entry.expected_rolling_bundle_signature,
                    "actual_rolling_bundle_signature": entry.actual_rolling_bundle_signature,
                    "expected_rolling_serializer_signature": entry.expected_rolling_serializer_signature,
                    "actual_rolling_serializer_signature": entry.actual_rolling_serializer_signature,
                    "expected_full_surface_signature": entry.expected_full_surface_signature,
                    "actual_full_surface_signature": entry.actual_full_surface_signature,
                    "service_builder_surface_present": entry.service_builder_surface_present,
                    "serializer_surface_present": entry.serializer_surface_present,
                    "api_route_surface_present": entry.api_route_surface_present,
                    "rolling_bundle_surface_present": entry.rolling_bundle_surface_present,
                    "rolling_serializer_surface_present": entry.rolling_serializer_surface_present,
                    "missing_signature_components": list(entry.missing_signature_components),
                    "invalid_signature_components": list(entry.invalid_signature_components),
                    "mismatched_signature_components": list(entry.mismatched_signature_components),
                    "duplicate_signature_components": list(entry.duplicate_signature_components),
                    "conflicting_signature_components": list(entry.conflicting_signature_components),
                    "consistency_classification": entry.consistency_classification,
                    "consistency_percentage": entry.consistency_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in signature_consistency.entries
            ],
            "diagnostics": list(signature_consistency.diagnostics),
            "paper_safe": signature_consistency.paper_safe,
            "network_calls": signature_consistency.network_calls,
            "execution_side_effects": signature_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "consistency_percentage": entry.consistency_percentage,
                "total_diagnostics_registered": entry.total_diagnostics_registered,
                "missing_signature_component_count": entry.missing_signature_component_count,
                "invalid_signature_component_count": entry.invalid_signature_component_count,
                "mismatched_signature_component_count": entry.mismatched_signature_component_count,
                "duplicate_signature_record_count": entry.duplicate_signature_record_count,
                "conflicting_signature_record_count": entry.conflicting_signature_record_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in contract_signature_drift.entries
        ],
        "failures": list(contract_signature_drift.failures),
        "diagnostics": list(contract_signature_drift.diagnostics),
        "paper_safe": contract_signature_drift.paper_safe,
        "network_calls": contract_signature_drift.network_calls,
        "execution_side_effects": contract_signature_drift.execution_side_effects,
    }


def _serialize_rolling_source_diagnostic_bundle_coverage_drift(
    rolling_bundle_coverage_drift: SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift,
) -> dict[str, object]:
    dedicated_rolling_diagnostic_consistency = (
        rolling_bundle_coverage_drift.dedicated_rolling_diagnostic_consistency
    )
    return {
        "drift_classification": rolling_bundle_coverage_drift.drift_classification,
        "average_coverage_percentage": rolling_bundle_coverage_drift.average_coverage_percentage,
        "severity_score": rolling_bundle_coverage_drift.severity_score,
        "contract_source": rolling_bundle_coverage_drift.contract_source,
        "total_snapshots_requested": rolling_bundle_coverage_drift.total_snapshots_requested,
        "snapshots_checked": rolling_bundle_coverage_drift.snapshots_checked,
        "stable_snapshots": rolling_bundle_coverage_drift.stable_snapshots,
        "drifting_snapshots": rolling_bundle_coverage_drift.drifting_snapshots,
        "degraded_snapshots": rolling_bundle_coverage_drift.degraded_snapshots,
        "insufficient_data_snapshots": rolling_bundle_coverage_drift.insufficient_data_snapshots,
        "missing_dedicated_service_builder_names": list(
            rolling_bundle_coverage_drift.missing_dedicated_service_builder_names
        ),
        "missing_dedicated_api_route_paths": list(
            rolling_bundle_coverage_drift.missing_dedicated_api_route_paths
        ),
        "missing_dedicated_serializer_names": list(
            rolling_bundle_coverage_drift.missing_dedicated_serializer_names
        ),
        "missing_rolling_bundle_field_names": list(
            rolling_bundle_coverage_drift.missing_rolling_bundle_field_names
        ),
        "missing_rolling_serializer_field_names": list(
            rolling_bundle_coverage_drift.missing_rolling_serializer_field_names
        ),
        "dedicated_rolling_diagnostic_consistency": {
            "consistency_classification": dedicated_rolling_diagnostic_consistency.consistency_classification,
            "consistency_percentage": dedicated_rolling_diagnostic_consistency.consistency_percentage,
            "total_diagnostics_registered": dedicated_rolling_diagnostic_consistency.total_diagnostics_registered,
            "dedicated_service_builder_count": dedicated_rolling_diagnostic_consistency.dedicated_service_builder_count,
            "dedicated_api_route_count": dedicated_rolling_diagnostic_consistency.dedicated_api_route_count,
            "dedicated_serializer_count": dedicated_rolling_diagnostic_consistency.dedicated_serializer_count,
            "rolling_bundle_count": dedicated_rolling_diagnostic_consistency.rolling_bundle_count,
            "rolling_serializer_count": dedicated_rolling_diagnostic_consistency.rolling_serializer_count,
            "consistent_diagnostic_count": dedicated_rolling_diagnostic_consistency.consistent_diagnostic_count,
            "partial_diagnostic_count": dedicated_rolling_diagnostic_consistency.partial_diagnostic_count,
            "degraded_diagnostic_count": dedicated_rolling_diagnostic_consistency.degraded_diagnostic_count,
            "missing_dedicated_service_builder_names": list(
                dedicated_rolling_diagnostic_consistency.missing_dedicated_service_builder_names
            ),
            "missing_dedicated_api_route_paths": list(
                dedicated_rolling_diagnostic_consistency.missing_dedicated_api_route_paths
            ),
            "missing_dedicated_serializer_names": list(
                dedicated_rolling_diagnostic_consistency.missing_dedicated_serializer_names
            ),
            "missing_rolling_bundle_field_names": list(
                dedicated_rolling_diagnostic_consistency.missing_rolling_bundle_field_names
            ),
            "missing_rolling_serializer_field_names": list(
                dedicated_rolling_diagnostic_consistency.missing_rolling_serializer_field_names
            ),
            "entries": [
                {
                    "diagnostic_key": entry.diagnostic_key,
                    "diagnostic_group": entry.diagnostic_group,
                    "dedicated_service_builder_name": entry.dedicated_service_builder_name,
                    "dedicated_api_route_path": entry.dedicated_api_route_path,
                    "dedicated_serializer_name": entry.dedicated_serializer_name,
                    "rolling_bundle_field_name": entry.rolling_bundle_field_name,
                    "rolling_serializer_field_name": entry.rolling_serializer_field_name,
                    "dedicated_service_builder_present": entry.dedicated_service_builder_present,
                    "dedicated_api_route_present": entry.dedicated_api_route_present,
                    "dedicated_serializer_present": entry.dedicated_serializer_present,
                    "rolling_bundle_present": entry.rolling_bundle_present,
                    "rolling_serializer_present": entry.rolling_serializer_present,
                    "consistency_classification": entry.consistency_classification,
                    "consistency_percentage": entry.consistency_percentage,
                    "diagnostic": entry.diagnostic,
                }
                for entry in dedicated_rolling_diagnostic_consistency.entries
            ],
            "diagnostics": list(dedicated_rolling_diagnostic_consistency.diagnostics),
            "paper_safe": dedicated_rolling_diagnostic_consistency.paper_safe,
            "network_calls": dedicated_rolling_diagnostic_consistency.network_calls,
            "execution_side_effects": dedicated_rolling_diagnostic_consistency.execution_side_effects,
        },
        "entries": [
            {
                "snapshot_id": entry.snapshot_id,
                "created_at": entry.created_at,
                "drift_classification": entry.drift_classification,
                "coverage_percentage": entry.coverage_percentage,
                "total_diagnostics_registered": entry.total_diagnostics_registered,
                "covered_dedicated_service_builder_count": entry.covered_dedicated_service_builder_count,
                "covered_dedicated_api_route_count": entry.covered_dedicated_api_route_count,
                "covered_dedicated_serializer_count": entry.covered_dedicated_serializer_count,
                "covered_rolling_bundle_count": entry.covered_rolling_bundle_count,
                "covered_rolling_serializer_count": entry.covered_rolling_serializer_count,
                "missing_dedicated_service_builder_count": entry.missing_dedicated_service_builder_count,
                "missing_dedicated_api_route_count": entry.missing_dedicated_api_route_count,
                "missing_dedicated_serializer_count": entry.missing_dedicated_serializer_count,
                "missing_rolling_bundle_count": entry.missing_rolling_bundle_count,
                "missing_rolling_serializer_count": entry.missing_rolling_serializer_count,
                "diagnostic": entry.diagnostic,
            }
            for entry in rolling_bundle_coverage_drift.entries
        ],
        "failures": list(rolling_bundle_coverage_drift.failures),
        "diagnostics": list(rolling_bundle_coverage_drift.diagnostics),
        "paper_safe": rolling_bundle_coverage_drift.paper_safe,
        "network_calls": rolling_bundle_coverage_drift.network_calls,
        "execution_side_effects": rolling_bundle_coverage_drift.execution_side_effects,
    }


def _serialize_source_diagnostic_contract_field_set_drift(
    field_set_drift: SnapshotReplaySourceDiagnosticContractFieldSetDrift,
) -> dict[str, object]:
    return {
        "drift_classification": field_set_drift.drift_classification,
        "consistency_percentage": field_set_drift.consistency_percentage,
        "severity_score": field_set_drift.severity_score,
        "total_diagnostics_registered": field_set_drift.total_diagnostics_registered,
        "fully_consistent_count": field_set_drift.fully_consistent_count,
        "partially_consistent_count": field_set_drift.partially_consistent_count,
        "missing_standard_field_count": field_set_drift.missing_standard_field_count,
        "standard_field_set": list(field_set_drift.standard_field_set),
        "entries": [
            {
                "slug": entry.slug,
                "diagnostic_key": entry.diagnostic_key,
                "diagnostic_group": entry.diagnostic_group,
                "model_class_name": entry.model_class_name,
                "has_all_standard_fields": entry.has_all_standard_fields,
                "present_standard_fields": list(entry.present_standard_fields),
                "missing_standard_fields": list(entry.missing_standard_fields),
                "extra_fields": list(entry.extra_fields),
                "total_fields": entry.total_fields,
                "drift_classification": entry.drift_classification,
                "diagnostic": entry.diagnostic,
            }
            for entry in field_set_drift.entries
        ],
        "diagnostics": list(field_set_drift.diagnostics),
        "paper_safe": field_set_drift.paper_safe,
        "network_calls": field_set_drift.network_calls,
        "execution_side_effects": field_set_drift.execution_side_effects,
    }


def _serialize_full_surface_response_field_set_consistency(
    consistency: SnapshotReplayFullSurfaceResponseFieldSetConsistency,
) -> dict[str, object]:
    return {
        "consistency_classification": consistency.consistency_classification,
        "consistency_percentage": consistency.consistency_percentage,
        "total_diagnostics_registered": consistency.total_diagnostics_registered,
        "fully_consistent_count": consistency.fully_consistent_count,
        "partially_consistent_count": consistency.partially_consistent_count,
        "degraded_count": consistency.degraded_count,
        "standard_field_set": list(consistency.standard_field_set),
        "entries": [
            {
                "slug": entry.slug,
                "diagnostic_key": entry.diagnostic_key,
                "diagnostic_group": entry.diagnostic_group,
                "model_class_name": entry.model_class_name,
                "has_all_standard_fields": entry.has_all_standard_fields,
                "present_standard_fields": list(entry.present_standard_fields),
                "missing_standard_fields": list(entry.missing_standard_fields),
                "total_fields": entry.total_fields,
                "consistency_classification": entry.consistency_classification,
                "diagnostic": entry.diagnostic,
            }
            for entry in consistency.entries
        ],
        "diagnostics": list(consistency.diagnostics),
        "paper_safe": consistency.paper_safe,
        "network_calls": consistency.network_calls,
        "execution_side_effects": consistency.execution_side_effects,
    }
