
from __future__ import annotations

from dataclasses import dataclass

from app.services.trigger_engine import TriggerSeverity

@dataclass(frozen=True)
class SnapshotSourceGapRecurrenceEntry:
    rank: int
    source_id: str
    gap_status: str
    severity: TriggerSeverity
    recurrence_classification: str
    occurrence_count: int
    recurrence_ratio: float
    longest_streak: int
    first_snapshot_id: str
    latest_snapshot_id: str
    affected_snapshot_ids: tuple[str, ...]

@dataclass(frozen=True)
class SnapshotSourceGapRecurrenceLeaderboard:
    total_entries: int
    total_snapshots: int
    entries: tuple[SnapshotSourceGapRecurrenceEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotNoExecutionGuardrailEntry:
    snapshot_id: str
    created_at: str
    report_type: str
    mode: str
    execution_mode: str
    decision_permission: str
    consistent: bool
    violation_codes: tuple[str, ...]
    diagnostic: str

@dataclass(frozen=True)
class SnapshotNoExecutionGuardrailConsistency:
    consistency_status: str
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    violation_count: int
    entries: tuple[SnapshotNoExecutionGuardrailEntry, ...]
    violations: tuple[SnapshotNoExecutionGuardrailEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotFallbackUsageTimelineEntry:
    snapshot_id: str
    created_at: str
    status: str
    fallback_event_count: int
    fallback_provider_count: int
    affected_providers: tuple[str, ...]
    affected_assets: tuple[str, ...]
    severity_score: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotFallbackUsageRecurrenceEntry:
    rank: int
    provider_name: str
    recurrence_classification: str
    severity_score: int
    occurrence_count: int
    recurrence_ratio: float
    longest_streak: int
    affected_snapshot_ids: tuple[str, ...]
    affected_assets: tuple[str, ...]
    missing_provider_metadata_count: int

@dataclass(frozen=True)
class SnapshotFallbackUsageRecurrence:
    stability_classification: str
    severity_score: int
    total_snapshots_requested: int
    snapshots_checked: int
    snapshots_with_fallback: int
    total_fallback_events: int
    unique_fallback_providers: int
    malformed_snapshot_count: int
    missing_provider_metadata_count: int
    timeline: tuple[SnapshotFallbackUsageTimelineEntry, ...]
    recurring_entries: tuple[SnapshotFallbackUsageRecurrenceEntry, ...]
    entries: tuple[SnapshotFallbackUsageRecurrenceEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceRegistryBindingDriftEntry:
    snapshot_id: str
    created_at: str
    source_registry_version: str
    registry_version_mismatch: bool
    binding_classification: str
    total_records: int
    matched_records: int
    unbound_source_ids: tuple[str, ...]
    provider_mismatch_source_ids: tuple[str, ...]
    asset_mismatch_source_ids: tuple[str, ...]
    malformed_record_count: int
    severity_score: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceRegistryBindingDrift:
    drift_classification: str
    severity_score: int
    current_source_registry_version: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    registry_version_mismatch_count: int
    unbound_source_ids: tuple[str, ...]
    provider_mismatch_source_ids: tuple[str, ...]
    asset_mismatch_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceRegistryBindingDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotSourceVerificationDriftEntry:
    snapshot_id: str
    created_at: str
    verification_classification: str
    verification_score: float
    total_records: int
    verified_records: int
    expected_verified_records: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_verification_source_ids: tuple[str, ...]
    unknown_registry_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotSourceVerificationDrift:
    drift_classification: str
    average_verification_score: float
    severity_score: int
    current_source_registry_version: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    degrading_snapshots: int
    improving_snapshots: int
    mixed_snapshots: int
    insufficient_data_snapshots: int
    degraded_source_ids: tuple[str, ...]
    improved_source_ids: tuple[str, ...]
    missing_verification_source_ids: tuple[str, ...]
    unknown_registry_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotSourceVerificationDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotPaperSafeSourceFlagConsistencyEntry:
    snapshot_id: str
    created_at: str
    consistency_classification: str
    consistency_percentage: float
    total_records: int
    safe_records: int
    false_flag_source_ids: tuple[str, ...]
    missing_flag_source_ids: tuple[str, ...]
    malformed_flag_source_ids: tuple[str, ...]
    contradictory_source_ids: tuple[str, ...]
    unknown_registry_source_ids: tuple[str, ...]
    unsafe_source_ids: tuple[str, ...]
    malformed_record_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotPaperSafeSourceFlagConsistency:
    consistency_classification: str
    average_consistency_percentage: float
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    false_flag_source_ids: tuple[str, ...]
    missing_flag_source_ids: tuple[str, ...]
    malformed_flag_source_ids: tuple[str, ...]
    contradictory_source_ids: tuple[str, ...]
    unknown_registry_source_ids: tuple[str, ...]
    unsafe_source_ids: tuple[str, ...]
    malformed_record_count: int
    entries: tuple[SnapshotPaperSafeSourceFlagConsistencyEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotProviderAdapterContractConsistencyEntry:
    snapshot_id: str
    created_at: str
    consistency_classification: str
    consistency_percentage: float
    source_observation_contract: str | None
    provider_adapter_contract: str | None
    source_observation_total_bound_sources: int | None
    provider_adapter_total_bound_sources: int | None
    missing_fields: tuple[str, ...]
    mismatched_fields: tuple[str, ...]
    malformed_field_count: int
    diagnostic: str

@dataclass(frozen=True)
class SnapshotProviderAdapterContractConsistency:
    consistency_classification: str
    average_consistency_percentage: float
    expected_contract: str
    total_snapshots_requested: int
    snapshots_checked: int
    consistent_snapshots: int
    partial_snapshots: int
    degraded_snapshots: int
    invalid_snapshots: int
    missing_contract_snapshot_ids: tuple[str, ...]
    mismatched_contract_snapshot_ids: tuple[str, ...]
    bound_source_mismatch_snapshot_ids: tuple[str, ...]
    malformed_snapshot_ids: tuple[str, ...]
    entries: tuple[SnapshotProviderAdapterContractConsistencyEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry:
    diagnostic_group: str
    contract_group_present: bool
    service_group_present: bool
    api_route_group_present: bool
    serializer_group_present: bool
    rolling_bundle_group_present: bool
    consistency_classification: str
    consistency_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayRouteSerializerGroupAlignmentConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_groups_registered: int
    contract_group_count: int
    service_group_count: int
    api_route_group_count: int
    serializer_group_count: int
    rolling_bundle_group_count: int
    consistent_group_count: int
    partial_group_count: int
    degraded_group_count: int
    missing_contract_groups: tuple[str, ...]
    missing_service_groups: tuple[str, ...]
    missing_api_route_groups: tuple[str, ...]
    missing_serializer_groups: tuple[str, ...]
    missing_rolling_bundle_groups: tuple[str, ...]
    entries: tuple[SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    coverage_percentage: float
    total_groups_registered: int
    covered_contract_group_count: int
    covered_service_group_count: int
    covered_api_route_group_count: int
    covered_serializer_group_count: int
    covered_rolling_bundle_group_count: int
    missing_contract_group_count: int
    missing_service_group_count: int
    missing_api_route_group_count: int
    missing_serializer_group_count: int
    missing_rolling_bundle_group_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticGroupCoverageDrift:
    drift_classification: str
    average_coverage_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    missing_contract_groups: tuple[str, ...]
    missing_service_groups: tuple[str, ...]
    missing_api_route_groups: tuple[str, ...]
    missing_serializer_groups: tuple[str, ...]
    missing_rolling_bundle_groups: tuple[str, ...]
    route_serializer_group_alignment_consistency: SnapshotReplayRouteSerializerGroupAlignmentConsistency
    entries: tuple[SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayContractSurfaceCountConsistencyEntry:
    surface_name: str
    expected_count: int
    actual_count: int
    count_delta: int
    consistency_classification: str
    consistency_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayContractSurfaceCountConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_surfaces_checked: int
    total_diagnostics_registered: int
    total_groups_registered: int
    contract_registry_count: int
    service_builder_count: int
    api_route_count: int
    serializer_count: int
    rolling_bundle_count: int
    diagnostic_group_count: int
    consistent_surface_count: int
    mismatched_surface_count: int
    mismatched_surface_names: tuple[str, ...]
    group_alignment_consistency_classification: str
    group_alignment_clean_but_count_mismatched: bool
    entries: tuple[SnapshotReplayContractSurfaceCountConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    consistency_percentage: float
    total_surfaces_checked: int
    total_diagnostics_registered: int
    total_groups_registered: int
    contract_registry_count: int
    service_builder_count: int
    api_route_count: int
    serializer_count: int
    rolling_bundle_count: int
    diagnostic_group_count: int
    mismatched_surface_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticSurfaceCountDrift:
    drift_classification: str
    average_consistency_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    mismatched_surface_names: tuple[str, ...]
    group_alignment_consistency_classification: str
    group_alignment_clean_but_count_mismatched: bool
    contract_surface_count_consistency: SnapshotReplayContractSurfaceCountConsistency
    entries: tuple[SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayContractMetadataNormalizationConsistencyEntry:
    diagnostic_slug: str
    diagnostic_key: str
    diagnostic_group: str
    service_builder_name: str
    api_route_path: str
    serializer_name: str
    rolling_bundle_field_name: str
    rolling_serializer_field_name: str
    contract_group_present: bool
    service_builder_key_present: bool
    api_route_key_present: bool
    serializer_key_present: bool
    rolling_bundle_key_present: bool
    rolling_serializer_key_present: bool
    missing_metadata_fields: tuple[str, ...]
    invalid_metadata_fields: tuple[str, ...]
    duplicate_metadata_fields: tuple[str, ...]
    conflicting_metadata_fields: tuple[str, ...]
    consistency_classification: str
    completeness_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayContractMetadataNormalizationConsistency:
    consistency_classification: str
    completeness_percentage: float
    total_diagnostics_registered: int
    complete_metadata_count: int
    partial_metadata_count: int
    degraded_metadata_count: int
    missing_metadata_field_count: int
    invalid_metadata_field_count: int
    duplicate_metadata_record_count: int
    conflicting_metadata_record_count: int
    missing_group_diagnostic_keys: tuple[str, ...]
    invalid_group_diagnostic_keys: tuple[str, ...]
    invalid_group_names: tuple[str, ...]
    invalid_diagnostic_slugs: tuple[str, ...]
    invalid_diagnostic_keys: tuple[str, ...]
    missing_service_builder_keys: tuple[str, ...]
    invalid_service_builder_keys: tuple[str, ...]
    missing_api_route_keys: tuple[str, ...]
    invalid_api_route_keys: tuple[str, ...]
    missing_serializer_keys: tuple[str, ...]
    invalid_serializer_keys: tuple[str, ...]
    missing_rolling_bundle_keys: tuple[str, ...]
    invalid_rolling_bundle_keys: tuple[str, ...]
    missing_rolling_serializer_keys: tuple[str, ...]
    invalid_rolling_serializer_keys: tuple[str, ...]
    duplicate_metadata_records: tuple[str, ...]
    conflicting_metadata_records: tuple[str, ...]
    entries: tuple[SnapshotReplayContractMetadataNormalizationConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    completeness_percentage: float
    total_diagnostics_registered: int
    complete_metadata_count: int
    partial_metadata_count: int
    degraded_metadata_count: int
    missing_metadata_field_count: int
    invalid_metadata_field_count: int
    duplicate_metadata_record_count: int
    conflicting_metadata_record_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticMetadataCompletenessDrift:
    drift_classification: str
    average_completeness_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    missing_metadata_field_count: int
    invalid_metadata_field_count: int
    duplicate_metadata_record_count: int
    conflicting_metadata_record_count: int
    missing_group_diagnostic_keys: tuple[str, ...]
    invalid_group_diagnostic_keys: tuple[str, ...]
    invalid_group_names: tuple[str, ...]
    invalid_diagnostic_slugs: tuple[str, ...]
    invalid_diagnostic_keys: tuple[str, ...]
    missing_service_builder_keys: tuple[str, ...]
    invalid_service_builder_keys: tuple[str, ...]
    missing_api_route_keys: tuple[str, ...]
    invalid_api_route_keys: tuple[str, ...]
    missing_serializer_keys: tuple[str, ...]
    invalid_serializer_keys: tuple[str, ...]
    missing_rolling_bundle_keys: tuple[str, ...]
    invalid_rolling_bundle_keys: tuple[str, ...]
    missing_rolling_serializer_keys: tuple[str, ...]
    invalid_rolling_serializer_keys: tuple[str, ...]
    duplicate_metadata_records: tuple[str, ...]
    conflicting_metadata_records: tuple[str, ...]
    contract_metadata_normalization_consistency: SnapshotReplayContractMetadataNormalizationConsistency
    entries: tuple[SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry:
    diagnostic_slug: str
    expected_diagnostic_key: str
    actual_diagnostic_key: str
    expected_service_builder_name: str
    actual_service_builder_name: str
    expected_serializer_name: str
    actual_serializer_name: str
    expected_api_route_path: str
    actual_api_route_path: str
    expected_rolling_bundle_field_name: str
    actual_rolling_bundle_field_name: str
    expected_rolling_serializer_field_name: str
    actual_rolling_serializer_field_name: str
    service_builder_surface_present: bool
    serializer_surface_present: bool
    api_route_surface_present: bool
    rolling_bundle_surface_present: bool
    rolling_serializer_surface_present: bool
    invalid_name_fields: tuple[str, ...]
    mismatched_name_fields: tuple[str, ...]
    duplicate_name_fields: tuple[str, ...]
    conflicting_name_fields: tuple[str, ...]
    consistency_classification: str
    consistency_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayBuilderSerializerRouteNamingConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    consistent_diagnostic_count: int
    partial_diagnostic_count: int
    degraded_diagnostic_count: int
    invalid_name_field_count: int
    mismatched_name_field_count: int
    duplicate_name_record_count: int
    conflicting_name_record_count: int
    invalid_diagnostic_slugs: tuple[str, ...]
    invalid_diagnostic_keys: tuple[str, ...]
    mismatched_diagnostic_keys: tuple[str, ...]
    invalid_service_builder_names: tuple[str, ...]
    mismatched_service_builder_names: tuple[str, ...]
    invalid_serializer_names: tuple[str, ...]
    mismatched_serializer_names: tuple[str, ...]
    invalid_api_route_paths: tuple[str, ...]
    mismatched_api_route_paths: tuple[str, ...]
    invalid_rolling_bundle_field_names: tuple[str, ...]
    mismatched_rolling_bundle_field_names: tuple[str, ...]
    invalid_rolling_serializer_field_names: tuple[str, ...]
    mismatched_rolling_serializer_field_names: tuple[str, ...]
    duplicate_name_records: tuple[str, ...]
    conflicting_name_records: tuple[str, ...]
    entries: tuple[SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticNamingContractDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    invalid_name_field_count: int
    mismatched_name_field_count: int
    duplicate_name_record_count: int
    conflicting_name_record_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticNamingContractDrift:
    drift_classification: str
    average_consistency_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    invalid_name_field_count: int
    mismatched_name_field_count: int
    duplicate_name_record_count: int
    conflicting_name_record_count: int
    invalid_diagnostic_slugs: tuple[str, ...]
    invalid_diagnostic_keys: tuple[str, ...]
    mismatched_diagnostic_keys: tuple[str, ...]
    invalid_service_builder_names: tuple[str, ...]
    mismatched_service_builder_names: tuple[str, ...]
    invalid_serializer_names: tuple[str, ...]
    mismatched_serializer_names: tuple[str, ...]
    invalid_api_route_paths: tuple[str, ...]
    mismatched_api_route_paths: tuple[str, ...]
    invalid_rolling_bundle_field_names: tuple[str, ...]
    mismatched_rolling_bundle_field_names: tuple[str, ...]
    invalid_rolling_serializer_field_names: tuple[str, ...]
    mismatched_rolling_serializer_field_names: tuple[str, ...]
    duplicate_name_records: tuple[str, ...]
    conflicting_name_records: tuple[str, ...]
    builder_serializer_route_naming_consistency: SnapshotReplayBuilderSerializerRouteNamingConsistency
    entries: tuple[SnapshotReplaySourceDiagnosticNamingContractDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayFullSurfaceContractSignatureConsistencyEntry:
    diagnostic_slug: str
    expected_contract_signature: str
    actual_contract_signature: str
    expected_service_builder_signature: str
    actual_service_builder_signature: str | None
    expected_serializer_signature: str
    actual_serializer_signature: str | None
    expected_api_route_signature: str
    actual_api_route_signature: str | None
    expected_rolling_bundle_signature: str
    actual_rolling_bundle_signature: str | None
    expected_rolling_serializer_signature: str
    actual_rolling_serializer_signature: str | None
    expected_full_surface_signature: str
    actual_full_surface_signature: str
    service_builder_surface_present: bool
    serializer_surface_present: bool
    api_route_surface_present: bool
    rolling_bundle_surface_present: bool
    rolling_serializer_surface_present: bool
    missing_signature_components: tuple[str, ...]
    invalid_signature_components: tuple[str, ...]
    mismatched_signature_components: tuple[str, ...]
    duplicate_signature_components: tuple[str, ...]
    conflicting_signature_components: tuple[str, ...]
    consistency_classification: str
    consistency_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayFullSurfaceContractSignatureConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    consistent_diagnostic_count: int
    partial_diagnostic_count: int
    degraded_diagnostic_count: int
    missing_signature_component_count: int
    invalid_signature_component_count: int
    mismatched_signature_component_count: int
    duplicate_signature_record_count: int
    conflicting_signature_record_count: int
    missing_contract_signatures: tuple[str, ...]
    invalid_contract_signatures: tuple[str, ...]
    mismatched_contract_signatures: tuple[str, ...]
    missing_service_builder_signatures: tuple[str, ...]
    invalid_service_builder_signatures: tuple[str, ...]
    mismatched_service_builder_signatures: tuple[str, ...]
    missing_serializer_signatures: tuple[str, ...]
    invalid_serializer_signatures: tuple[str, ...]
    mismatched_serializer_signatures: tuple[str, ...]
    missing_api_route_signatures: tuple[str, ...]
    invalid_api_route_signatures: tuple[str, ...]
    mismatched_api_route_signatures: tuple[str, ...]
    missing_rolling_bundle_signatures: tuple[str, ...]
    invalid_rolling_bundle_signatures: tuple[str, ...]
    mismatched_rolling_bundle_signatures: tuple[str, ...]
    missing_rolling_serializer_signatures: tuple[str, ...]
    invalid_rolling_serializer_signatures: tuple[str, ...]
    mismatched_rolling_serializer_signatures: tuple[str, ...]
    duplicate_signature_records: tuple[str, ...]
    conflicting_signature_records: tuple[str, ...]
    entries: tuple[SnapshotReplayFullSurfaceContractSignatureConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticContractSignatureDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    missing_signature_component_count: int
    invalid_signature_component_count: int
    mismatched_signature_component_count: int
    duplicate_signature_record_count: int
    conflicting_signature_record_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticContractSignatureDrift:
    drift_classification: str
    average_consistency_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    missing_signature_component_count: int
    invalid_signature_component_count: int
    mismatched_signature_component_count: int
    duplicate_signature_record_count: int
    conflicting_signature_record_count: int
    missing_contract_signatures: tuple[str, ...]
    invalid_contract_signatures: tuple[str, ...]
    mismatched_contract_signatures: tuple[str, ...]
    missing_service_builder_signatures: tuple[str, ...]
    invalid_service_builder_signatures: tuple[str, ...]
    mismatched_service_builder_signatures: tuple[str, ...]
    missing_serializer_signatures: tuple[str, ...]
    invalid_serializer_signatures: tuple[str, ...]
    mismatched_serializer_signatures: tuple[str, ...]
    missing_api_route_signatures: tuple[str, ...]
    invalid_api_route_signatures: tuple[str, ...]
    mismatched_api_route_signatures: tuple[str, ...]
    missing_rolling_bundle_signatures: tuple[str, ...]
    invalid_rolling_bundle_signatures: tuple[str, ...]
    mismatched_rolling_bundle_signatures: tuple[str, ...]
    missing_rolling_serializer_signatures: tuple[str, ...]
    invalid_rolling_serializer_signatures: tuple[str, ...]
    mismatched_rolling_serializer_signatures: tuple[str, ...]
    duplicate_signature_records: tuple[str, ...]
    conflicting_signature_records: tuple[str, ...]
    full_surface_contract_signature_consistency: SnapshotReplayFullSurfaceContractSignatureConsistency
    entries: tuple[SnapshotReplaySourceDiagnosticContractSignatureDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry:
    diagnostic_key: str
    diagnostic_group: str
    service_builder_name: str
    api_route_path: str
    serializer_name: str
    service_builder_present: bool
    api_route_present: bool
    serializer_present: bool
    consistency_classification: str
    consistency_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayDiagnosticEndpointCoverageConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    service_builder_count: int
    api_route_count: int
    serializer_count: int
    consistent_diagnostic_count: int
    partial_diagnostic_count: int
    degraded_diagnostic_count: int
    missing_service_builder_names: tuple[str, ...]
    missing_api_route_paths: tuple[str, ...]
    missing_serializer_names: tuple[str, ...]
    entries: tuple[SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    coverage_percentage: float
    total_diagnostics_registered: int
    covered_service_builder_count: int
    covered_api_route_count: int
    covered_serializer_count: int
    missing_service_builder_count: int
    missing_api_route_count: int
    missing_serializer_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticsContractCoverageDrift:
    drift_classification: str
    average_coverage_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    missing_service_builder_names: tuple[str, ...]
    missing_api_route_paths: tuple[str, ...]
    missing_serializer_names: tuple[str, ...]
    endpoint_coverage_consistency: SnapshotReplayDiagnosticEndpointCoverageConsistency
    entries: tuple[SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry:
    diagnostic_key: str
    diagnostic_group: str
    dedicated_service_builder_name: str
    dedicated_api_route_path: str
    dedicated_serializer_name: str
    rolling_bundle_field_name: str
    rolling_serializer_field_name: str
    dedicated_service_builder_present: bool
    dedicated_api_route_present: bool
    dedicated_serializer_present: bool
    rolling_bundle_present: bool
    rolling_serializer_present: bool
    consistency_classification: str
    consistency_percentage: float
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayDedicatedRollingDiagnosticConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    dedicated_service_builder_count: int
    dedicated_api_route_count: int
    dedicated_serializer_count: int
    rolling_bundle_count: int
    rolling_serializer_count: int
    consistent_diagnostic_count: int
    partial_diagnostic_count: int
    degraded_diagnostic_count: int
    missing_dedicated_service_builder_names: tuple[str, ...]
    missing_dedicated_api_route_paths: tuple[str, ...]
    missing_dedicated_serializer_names: tuple[str, ...]
    missing_rolling_bundle_field_names: tuple[str, ...]
    missing_rolling_serializer_field_names: tuple[str, ...]
    entries: tuple[SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry:
    snapshot_id: str
    created_at: str
    drift_classification: str
    coverage_percentage: float
    total_diagnostics_registered: int
    covered_dedicated_service_builder_count: int
    covered_dedicated_api_route_count: int
    covered_dedicated_serializer_count: int
    covered_rolling_bundle_count: int
    covered_rolling_serializer_count: int
    missing_dedicated_service_builder_count: int
    missing_dedicated_api_route_count: int
    missing_dedicated_serializer_count: int
    missing_rolling_bundle_count: int
    missing_rolling_serializer_count: int
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift:
    drift_classification: str
    average_coverage_percentage: float
    severity_score: int
    contract_source: str
    total_snapshots_requested: int
    snapshots_checked: int
    stable_snapshots: int
    drifting_snapshots: int
    degraded_snapshots: int
    insufficient_data_snapshots: int
    missing_dedicated_service_builder_names: tuple[str, ...]
    missing_dedicated_api_route_paths: tuple[str, ...]
    missing_dedicated_serializer_names: tuple[str, ...]
    missing_rolling_bundle_field_names: tuple[str, ...]
    missing_rolling_serializer_field_names: tuple[str, ...]
    dedicated_rolling_diagnostic_consistency: SnapshotReplayDedicatedRollingDiagnosticConsistency
    entries: tuple[SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry, ...]
    failures: tuple[dict[str, str], ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str

@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry:
    slug: str
    diagnostic_key: str
    diagnostic_group: str
    model_class_name: str
    has_all_standard_fields: bool
    present_standard_fields: tuple[str, ...]
    missing_standard_fields: tuple[str, ...]
    extra_fields: tuple[str, ...]
    total_fields: int
    drift_classification: str
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplaySourceDiagnosticContractFieldSetDrift:
    drift_classification: str
    consistency_percentage: float
    severity_score: int
    total_diagnostics_registered: int
    fully_consistent_count: int
    partially_consistent_count: int
    missing_standard_field_count: int
    standard_field_set: tuple[str, ...]
    entries: tuple[SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


@dataclass(frozen=True)
class SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry:
    slug: str
    diagnostic_key: str
    diagnostic_group: str
    model_class_name: str
    has_all_standard_fields: bool
    present_standard_fields: tuple[str, ...]
    missing_standard_fields: tuple[str, ...]
    total_fields: int
    consistency_classification: str
    diagnostic: str


@dataclass(frozen=True)
class SnapshotReplayFullSurfaceResponseFieldSetConsistency:
    consistency_classification: str
    consistency_percentage: float
    total_diagnostics_registered: int
    fully_consistent_count: int
    partially_consistent_count: int
    degraded_count: int
    standard_field_set: tuple[str, ...]
    entries: tuple[SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry, ...]
    diagnostics: tuple[str, ...]
    paper_safe: bool
    network_calls: bool
    execution_side_effects: str


__all__ = [
    "SnapshotSourceGapRecurrenceEntry",
    "SnapshotSourceGapRecurrenceLeaderboard",
    "SnapshotNoExecutionGuardrailEntry",
    "SnapshotNoExecutionGuardrailConsistency",
    "SnapshotFallbackUsageTimelineEntry",
    "SnapshotFallbackUsageRecurrenceEntry",
    "SnapshotFallbackUsageRecurrence",
    "SnapshotSourceRegistryBindingDriftEntry",
    "SnapshotSourceRegistryBindingDrift",
    "SnapshotSourceVerificationDriftEntry",
    "SnapshotSourceVerificationDrift",
    "SnapshotPaperSafeSourceFlagConsistencyEntry",
    "SnapshotPaperSafeSourceFlagConsistency",
    "SnapshotProviderAdapterContractConsistencyEntry",
    "SnapshotProviderAdapterContractConsistency",
    "SnapshotReplayRouteSerializerGroupAlignmentConsistencyEntry",
    "SnapshotReplayRouteSerializerGroupAlignmentConsistency",
    "SnapshotReplaySourceDiagnosticGroupCoverageDriftEntry",
    "SnapshotReplaySourceDiagnosticGroupCoverageDrift",
    "SnapshotReplayContractSurfaceCountConsistencyEntry",
    "SnapshotReplayContractSurfaceCountConsistency",
    "SnapshotReplaySourceDiagnosticSurfaceCountDriftEntry",
    "SnapshotReplaySourceDiagnosticSurfaceCountDrift",
    "SnapshotReplayContractMetadataNormalizationConsistencyEntry",
    "SnapshotReplayContractMetadataNormalizationConsistency",
    "SnapshotReplaySourceDiagnosticMetadataCompletenessDriftEntry",
    "SnapshotReplaySourceDiagnosticMetadataCompletenessDrift",
    "SnapshotReplayBuilderSerializerRouteNamingConsistencyEntry",
    "SnapshotReplayBuilderSerializerRouteNamingConsistency",
    "SnapshotReplaySourceDiagnosticNamingContractDriftEntry",
    "SnapshotReplaySourceDiagnosticNamingContractDrift",
    "SnapshotReplayFullSurfaceContractSignatureConsistencyEntry",
    "SnapshotReplayFullSurfaceContractSignatureConsistency",
    "SnapshotReplaySourceDiagnosticContractSignatureDriftEntry",
    "SnapshotReplaySourceDiagnosticContractSignatureDrift",
    "SnapshotReplayDiagnosticEndpointCoverageConsistencyEntry",
    "SnapshotReplayDiagnosticEndpointCoverageConsistency",
    "SnapshotReplaySourceDiagnosticsContractCoverageDriftEntry",
    "SnapshotReplaySourceDiagnosticsContractCoverageDrift",
    "SnapshotReplayDedicatedRollingDiagnosticConsistencyEntry",
    "SnapshotReplayDedicatedRollingDiagnosticConsistency",
    "SnapshotReplayRollingSourceDiagnosticBundleCoverageDriftEntry",
    "SnapshotReplayRollingSourceDiagnosticBundleCoverageDrift",
    "SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry",
    "SnapshotReplaySourceDiagnosticContractFieldSetDrift",
    "SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry",
    "SnapshotReplayFullSurfaceResponseFieldSetConsistency",
]
