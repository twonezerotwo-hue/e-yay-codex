from __future__ import annotations

SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_ROUTE_PREFIX = "/api/v1/snapshots/backtest/"
SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE = (
    "explicit_runtime_contract_registry"
)

SOURCE_DIAGNOSTIC_SERVICE_SLUGS = (
    "fallback-usage-recurrence",
    "raw-payload-reference-completeness",
    "source-record-completeness",
    "source-registry-binding-drift",
    "source-decision-usage-consistency",
    "source-verification-drift",
    "paper-safe-source-flag-consistency",
    "source-observation-summary-drift",
    "provider-adapter-contract-consistency",
    "source-freshness-decay-timeline",
    "source-observation-cadence-drift",
    "source-observation-timestamp-integrity-drift",
    "source-observation-record-summary-reconciliation",
    "source-observation-normalization-mode-drift",
    "mapped-at-alignment-consistency",
    "source-observation-confidence-drift",
    "verified-source-coverage-reconciliation",
    "source-observation-availability-lag-drift",
    "source-freshness-summary-reconciliation",
    "source-observation-freshness-seconds-drift",
    "source-freshness-status-threshold-reconciliation",
    "source-freshness-policy-drift",
    "stale-source-list-threshold-reconciliation",
    "source-diagnostics-freshness-evaluation-mode-drift",
    "source-diagnostics-stale-asset-count-reconciliation",
    "source-diagnostics-average-coverage-drift",
    "source-diagnostics-minimum-coverage-floor-reconciliation",
    "source-diagnostics-ready-feature-drift",
    "source-diagnostics-stale-feature-drift",
    "source-diagnostics-critical-feature-drift",
    "source-diagnostics-high-severity-drift",
    "source-diagnostics-warning-feature-drift",
    "source-diagnostics-info-feature-drift",
    "source-diagnostics-zero-rank-drift",
    "source-diagnostics-severity-label-drift",
    "source-diagnostics-severity-rank-drift",
    "source-diagnostics-severity-rank-density-drift",
    "source-diagnostics-severity-rank-spread-drift",
    "source-diagnostics-severity-ranking-feature-count-reconciliation",
    "source-diagnostics-severity-ranking-warning-count-reconciliation",
    "source-diagnostics-severity-ranking-info-count-reconciliation",
    "source-diagnostics-severity-ranking-non-actionable-count-reconciliation",
    "source-diagnostics-severity-ranking-rank-label-consistency-reconciliation",
    "source-diagnostics-severity-ranking-rank-order-continuity-reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation",
    "source-diagnostics-severity-ranking-critical-count-reconciliation",
    "source-diagnostics-missing-source-feature-count-reconciliation",
    "source-diagnostics-missing-asset-count-reconciliation",
)

SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS = SOURCE_DIAGNOSTIC_SERVICE_SLUGS
SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS = SOURCE_DIAGNOSTIC_SERVICE_SLUGS
SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS = (
    "fallback-usage-recurrence",
    "raw-payload-reference-completeness",
    "source-record-completeness",
    "source-registry-binding-drift",
    "source-decision-usage-consistency",
    "source-verification-drift",
    "paper-safe-source-flag-consistency",
    "source-observation-summary-drift",
    "provider-adapter-contract-consistency",
    "source-freshness-decay-timeline",
    "source-observation-cadence-drift",
    "source-observation-timestamp-integrity-drift",
    "source-observation-record-summary-reconciliation",
    "source-observation-normalization-mode-drift",
    "mapped-at-alignment-consistency",
    "source-observation-confidence-drift",
    "verified-source-coverage-reconciliation",
    "source-observation-availability-lag-drift",
    "source-freshness-summary-reconciliation",
    "source-observation-freshness-seconds-drift",
    "source-freshness-status-threshold-reconciliation",
    "source-freshness-policy-drift",
    "stale-source-list-threshold-reconciliation",
    "source-diagnostics-freshness-evaluation-mode-drift",
    "source-diagnostics-stale-asset-count-reconciliation",
    "source-diagnostics-average-coverage-drift",
    "source-diagnostics-minimum-coverage-floor-reconciliation",
    "source-diagnostics-ready-feature-drift",
    "source-diagnostics-stale-feature-drift",
    "source-diagnostics-critical-feature-drift",
    "source-diagnostics-high-severity-drift",
    "source-diagnostics-warning-feature-drift",
    "source-diagnostics-info-feature-drift",
    "source-diagnostics-zero-rank-drift",
    "source-diagnostics-severity-label-drift",
    "source-diagnostics-severity-rank-drift",
    "source-diagnostics-severity-rank-density-drift",
    "source-diagnostics-severity-rank-spread-drift",
    "source-diagnostics-severity-ranking-feature-count-reconciliation",
    "source-diagnostics-severity-ranking-warning-count-reconciliation",
    "source-diagnostics-severity-ranking-info-count-reconciliation",
    "source-diagnostics-severity-ranking-non-actionable-count-reconciliation",
    "source-diagnostics-severity-ranking-rank-label-consistency-reconciliation",
    "source-diagnostics-severity-ranking-rank-order-continuity-reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation",
    "source-diagnostics-severity-ranking-critical-count-reconciliation",
    "source-diagnostics-missing-source-feature-count-reconciliation",
    "source-diagnostics-missing-asset-count-reconciliation",
)
SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS = (
    "fallback-usage-recurrence",
    "raw-payload-reference-completeness",
    "source-record-completeness",
    "source-registry-binding-drift",
    "source-decision-usage-consistency",
    "source-verification-drift",
    "paper-safe-source-flag-consistency",
    "source-observation-summary-drift",
    "provider-adapter-contract-consistency",
    "source-freshness-decay-timeline",
    "source-observation-cadence-drift",
    "source-observation-timestamp-integrity-drift",
    "source-observation-record-summary-reconciliation",
    "source-observation-normalization-mode-drift",
    "mapped-at-alignment-consistency",
    "source-observation-confidence-drift",
    "verified-source-coverage-reconciliation",
    "source-observation-availability-lag-drift",
    "source-freshness-summary-reconciliation",
    "source-observation-freshness-seconds-drift",
    "source-freshness-status-threshold-reconciliation",
    "source-freshness-policy-drift",
    "stale-source-list-threshold-reconciliation",
    "source-diagnostics-freshness-evaluation-mode-drift",
    "source-diagnostics-stale-asset-count-reconciliation",
    "source-diagnostics-average-coverage-drift",
    "source-diagnostics-minimum-coverage-floor-reconciliation",
    "source-diagnostics-ready-feature-drift",
    "source-diagnostics-stale-feature-drift",
    "source-diagnostics-critical-feature-drift",
    "source-diagnostics-high-severity-drift",
    "source-diagnostics-warning-feature-drift",
    "source-diagnostics-info-feature-drift",
    "source-diagnostics-zero-rank-drift",
    "source-diagnostics-severity-label-drift",
    "source-diagnostics-severity-rank-drift",
    "source-diagnostics-severity-rank-density-drift",
    "source-diagnostics-severity-rank-spread-drift",
    "source-diagnostics-severity-ranking-feature-count-reconciliation",
    "source-diagnostics-severity-ranking-warning-count-reconciliation",
    "source-diagnostics-severity-ranking-info-count-reconciliation",
    "source-diagnostics-severity-ranking-non-actionable-count-reconciliation",
    "source-diagnostics-severity-ranking-rank-label-consistency-reconciliation",
    "source-diagnostics-severity-ranking-rank-order-continuity-reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation",
    "source-diagnostics-severity-ranking-critical-count-reconciliation",
    "source-diagnostics-missing-source-feature-count-reconciliation",
    "source-diagnostics-missing-asset-count-reconciliation",
)

SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET = (
    "diagnostics",
    "entries",
    "execution_side_effects",
    "failures",
    "network_calls",
    "paper_safe",
    "total_snapshots_requested",
)

SOURCE_DIAGNOSTIC_GROUP_BY_SLUG = {
    "fallback-usage-recurrence": "registry",
    "raw-payload-reference-completeness": "quality_completeness",
    "source-record-completeness": "quality_completeness",
    "source-registry-binding-drift": "registry",
    "source-decision-usage-consistency": "quality_reconciliation",
    "source-verification-drift": "registry",
    "paper-safe-source-flag-consistency": "registry",
    "source-observation-summary-drift": "quality_drift",
    "provider-adapter-contract-consistency": "registry",
    "source-freshness-decay-timeline": "timing",
    "source-observation-cadence-drift": "timing",
    "source-observation-timestamp-integrity-drift": "timing",
    "source-observation-record-summary-reconciliation": "quality_reconciliation",
    "source-observation-normalization-mode-drift": "timing",
    "mapped-at-alignment-consistency": "timing",
    "source-observation-confidence-drift": "quality_drift",
    "verified-source-coverage-reconciliation": "quality_reconciliation",
    "source-observation-availability-lag-drift": "timing",
    "source-freshness-summary-reconciliation": "timing",
    "source-observation-freshness-seconds-drift": "timing",
    "source-freshness-status-threshold-reconciliation": "timing",
    "source-freshness-policy-drift": "timing",
    "stale-source-list-threshold-reconciliation": "timing",
    "source-diagnostics-freshness-evaluation-mode-drift": "timing",
    "source-diagnostics-stale-asset-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-average-coverage-drift": "quality_drift",
    "source-diagnostics-minimum-coverage-floor-reconciliation": "quality_reconciliation",
    "source-diagnostics-ready-feature-drift": "quality_drift",
    "source-diagnostics-stale-feature-drift": "quality_drift",
    "source-diagnostics-critical-feature-drift": "quality_drift",
    "source-diagnostics-high-severity-drift": "quality_drift",
    "source-diagnostics-warning-feature-drift": "quality_drift",
    "source-diagnostics-info-feature-drift": "quality_drift",
    "source-diagnostics-zero-rank-drift": "quality_drift",
    "source-diagnostics-severity-label-drift": "quality_drift",
    "source-diagnostics-severity-rank-drift": "quality_drift",
    "source-diagnostics-severity-rank-density-drift": "quality_drift",
    "source-diagnostics-severity-rank-spread-drift": "quality_drift",
    "source-diagnostics-severity-ranking-feature-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-warning-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-info-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-non-actionable-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-rank-label-consistency-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-rank-order-continuity-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation": "quality_reconciliation",
    "source-diagnostics-severity-ranking-critical-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-missing-source-feature-count-reconciliation": "quality_reconciliation",
    "source-diagnostics-missing-asset-count-reconciliation": "quality_reconciliation",
}


def snapshot_replay_source_diagnostic_key(slug: str) -> str:
    return slug.replace("-", "_")


def snapshot_replay_source_diagnostic_builder_name(slug: str) -> str:
    return f"build_{snapshot_replay_source_diagnostic_key(slug)}"


def snapshot_replay_source_diagnostic_serializer_name(slug: str) -> str:
    return f"_serialize_{snapshot_replay_source_diagnostic_key(slug)}"


def snapshot_replay_source_diagnostic_route_path(slug: str) -> str:
    return f"{SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_ROUTE_PREFIX}{slug}"


def snapshot_replay_source_diagnostic_group(slug: str) -> str:
    return SOURCE_DIAGNOSTIC_GROUP_BY_SLUG.get(slug, "unknown")


def snapshot_replay_source_diagnostic_contract_groups() -> tuple[str, ...]:
    return tuple(sorted(set(SOURCE_DIAGNOSTIC_GROUP_BY_SLUG.values())))


def snapshot_replay_source_diagnostic_groups_for_slugs(
    slugs: tuple[str, ...] | list[str] | set[str] | frozenset[str],
) -> tuple[str, ...]:
    return tuple(sorted({snapshot_replay_source_diagnostic_group(slug) for slug in slugs}))


def snapshot_replay_source_diagnostic_rolling_field_name(slug: str) -> str:
    return snapshot_replay_source_diagnostic_key(slug)


def snapshot_replay_source_diagnostic_rolling_serializer_field_name(slug: str) -> str:
    return snapshot_replay_source_diagnostic_key(slug)


__all__ = [
    "SNAPSHOT_REPLAY_SOURCE_DIAGNOSTIC_CONTRACT_SOURCE",
    "SOURCE_DIAGNOSTIC_SERVICE_SLUGS",
    "SOURCE_DIAGNOSTIC_API_ROUTE_SLUGS",
    "SOURCE_DIAGNOSTIC_SERIALIZER_SLUGS",
    "SOURCE_DIAGNOSTIC_ROLLING_BUNDLE_SLUGS",
    "SOURCE_DIAGNOSTIC_ROLLING_SERIALIZER_SLUGS",
    "SOURCE_DIAGNOSTIC_GROUP_BY_SLUG",
    "snapshot_replay_source_diagnostic_key",
    "snapshot_replay_source_diagnostic_builder_name",
    "snapshot_replay_source_diagnostic_serializer_name",
    "snapshot_replay_source_diagnostic_route_path",
    "snapshot_replay_source_diagnostic_group",
    "snapshot_replay_source_diagnostic_contract_groups",
    "snapshot_replay_source_diagnostic_groups_for_slugs",
    "snapshot_replay_source_diagnostic_rolling_field_name",
    "snapshot_replay_source_diagnostic_rolling_serializer_field_name",
    "SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET",
]
