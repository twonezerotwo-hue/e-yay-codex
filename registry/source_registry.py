from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.assets import AssetDefinition, get_asset_definition
from app.domain.assets import list_main_assets
from reports.generator import load_json_schema
from reports.generator import load_yaml_file
from reports.generator import validate_config
from reports.generator import CONFIG_DIR
from reports.generator import SCHEMA_DIR


DECISION_USAGE_PRIORITY = {
    "simulation_only": 0,
    "verified_required": 1,
}

ASSET_COVERAGE_CREDITS = {
    "ready": 100.0,
    "stale_source": 50.0,
    "insufficient_decision_usage": 25.0,
    "missing_active_source": 0.0,
}

ISSUE_SEVERITY_WEIGHTS = {
    None: 0,
    "no_active_source": 4,
    "minimum_decision_usage_not_met": 3,
    "freshness_policy_not_met": 2,
    "missing_source_timestamp": 2,
}


@dataclass(frozen=True)
class SourceRegistryEntry:
    source_id: str
    asset: AssetDefinition
    provider: str
    source_type: str
    cadence: str
    verified: bool
    decision_usage: str
    active: bool


def load_source_registry() -> dict[str, Any]:
    source_registry = load_yaml_file(CONFIG_DIR / "source_registry_v1.0.yaml")
    schema = load_json_schema(SCHEMA_DIR / "source_registry.schema.json")
    return validate_config(source_registry, schema)


def build_source_registry_entries(
    source_registry: dict[str, Any] | None = None,
) -> tuple[SourceRegistryEntry, ...]:
    registry_data = source_registry or load_source_registry()
    entries: list[SourceRegistryEntry] = []

    for source in registry_data["sources"]:
        asset = get_asset_definition(source["asset_code"])

        if asset.category.value != source["asset_category"]:
            raise ValueError(
                f"Source category mismatch for {source['source_id']}: "
                f"{source['asset_category']} != {asset.category.value}"
            )

        if not source["verified"] and source["decision_usage"] != "simulation_only":
            raise ValueError(
                f"Unverified source {source['source_id']} must use simulation_only decision usage."
            )

        entries.append(
            SourceRegistryEntry(
                source_id=source["source_id"],
                asset=asset,
                provider=source["provider"],
                source_type=source["source_type"],
                cadence=source["cadence"],
                verified=bool(source["verified"]),
                decision_usage=source["decision_usage"],
                active=bool(source["active"]),
            )
        )

    return tuple(entries)


def build_source_registry_index(
    entries: tuple[SourceRegistryEntry, ...] | None = None,
    *,
    source_registry: dict[str, Any] | None = None,
) -> dict[str, tuple[SourceRegistryEntry, ...]]:
    resolved_entries = entries or build_source_registry_entries(source_registry)
    indexed_entries: dict[str, list[SourceRegistryEntry]] = {
        asset.code.value: [] for asset in list_main_assets()
    }

    for entry in resolved_entries:
        indexed_entries.setdefault(entry.asset.code.value, []).append(entry)

    return {
        asset_code: tuple(asset_entries)
        for asset_code, asset_entries in indexed_entries.items()
    }


def _normalize_utc_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed_value = value
    elif isinstance(value, str):
        parsed_value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("Source observation timestamps must be datetime or ISO8601 strings.")

    if parsed_value.tzinfo is None:
        parsed_value = parsed_value.replace(tzinfo=UTC)

    return parsed_value.astimezone(UTC)


def build_source_freshness_diagnostics(
    source_registry: dict[str, Any] | None = None,
    *,
    source_observations: Mapping[str, datetime | str] | None = None,
    as_of_utc: datetime | None = None,
) -> dict[str, Any]:
    registry_data = source_registry or load_source_registry()
    entries = build_source_registry_entries(registry_data)
    freshness_policy = registry_data["freshness_policy"]
    evaluation_time = (as_of_utc or datetime.now(UTC)).astimezone(UTC)
    evaluation_mode = "observed" if source_observations is not None else "not_evaluated"

    diagnostics: list[dict[str, Any]] = []
    fresh_sources = 0
    stale_sources = 0
    sources_missing_timestamps = 0
    not_evaluated_sources = 0

    for entry in entries:
        max_age_minutes = int(freshness_policy[entry.cadence]["max_age_minutes"])
        last_updated_utc: str | None = None
        age_minutes: float | None = None

        if source_observations is None:
            freshness_status = "not_evaluated"
            issue_type = "source_observations_not_provided"
            if entry.active:
                not_evaluated_sources += 1
        else:
            observation_value = source_observations.get(entry.source_id)
            if observation_value is None:
                freshness_status = "missing_timestamp"
                issue_type = "missing_source_timestamp"
                if entry.active:
                    sources_missing_timestamps += 1
            else:
                observed_at = _normalize_utc_datetime(observation_value)
                age_minutes = round((evaluation_time - observed_at).total_seconds() / 60.0, 2)
                if age_minutes < 0:
                    raise ValueError(
                        f"Source observation for {entry.source_id} cannot be later than the evaluation time."
                    )

                last_updated_utc = observed_at.isoformat()
                if age_minutes <= max_age_minutes:
                    freshness_status = "fresh"
                    issue_type = None
                    if entry.active:
                        fresh_sources += 1
                else:
                    freshness_status = "stale"
                    issue_type = "freshness_policy_not_met"
                    if entry.active:
                        stale_sources += 1

        diagnostics.append(
            {
                "source_id": entry.source_id,
                "asset_code": entry.asset.code.value,
                "cadence": entry.cadence,
                "active": entry.active,
                "max_age_minutes": max_age_minutes,
                "last_updated_utc": last_updated_utc,
                "age_minutes": age_minutes,
                "freshness_status": freshness_status,
                "issue_type": issue_type,
            }
        )

    return {
        "source_registry_version": registry_data["version"],
        "as_of_utc": evaluation_time.isoformat(),
        "freshness_policy": freshness_policy,
        "sources": diagnostics,
        "summary": {
            "total_sources": len(diagnostics),
            "total_active_sources": sum(1 for entry in entries if entry.active),
            "fresh_sources": fresh_sources,
            "stale_sources": stale_sources,
            "sources_missing_timestamps": sources_missing_timestamps,
            "not_evaluated_sources": not_evaluated_sources,
            "evaluation_mode": evaluation_mode,
        },
    }


def build_report_source_binding(
    source_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry_data = source_registry or load_source_registry()
    entries = build_source_registry_entries(registry_data)
    index = build_source_registry_index(entries)

    bindings: list[dict[str, Any]] = []
    uncovered_assets: list[str] = []
    verified_required_assets = 0
    simulation_only_assets = 0

    for asset in list_main_assets():
        asset_entries = index[asset.code.value]
        source_ids = [entry.source_id for entry in asset_entries if entry.active]
        decision_usages = list(
            dict.fromkeys(entry.decision_usage for entry in asset_entries if entry.active)
        )
        has_verified_required_source = any(
            entry.active and entry.verified and entry.decision_usage == "verified_required"
            for entry in asset_entries
        )

        if has_verified_required_source:
            verified_required_assets += 1
        elif source_ids:
            simulation_only_assets += 1
        else:
            uncovered_assets.append(asset.code.value)

        bindings.append(
            {
                "asset_code": asset.code.value,
                "symbol": asset.symbol,
                "canonical_name": asset.canonical_name,
                "display_name": asset.display_name,
                "asset_category": asset.category.value,
                "unit": asset.unit,
                "required_for_core_report": asset.required_for_core_report,
                "source_ids": source_ids,
                "coverage_status": "covered" if source_ids else "missing",
                "decision_usages": decision_usages,
                "live_eligible": has_verified_required_source
                and asset.requires_verified_data_for_live,
            }
        )

    return {
        "source_registry_version": registry_data["version"],
        "bindings": bindings,
        "coverage": {
            "total_assets": len(bindings),
            "covered_assets": len(bindings) - len(uncovered_assets),
            "uncovered_assets": uncovered_assets,
            "verified_required_assets": verified_required_assets,
            "simulation_only_assets": simulation_only_assets,
        },
    }


def _meets_minimum_decision_usage(
    candidate_usage: str,
    minimum_decision_usage: str,
) -> bool:
    return DECISION_USAGE_PRIORITY[candidate_usage] >= DECISION_USAGE_PRIORITY[minimum_decision_usage]


def _calculate_feature_severity_rank(
    *,
    is_critical: bool,
    asset_diagnostics: list[dict[str, Any]],
) -> int:
    highest_issue_weight = max(
        ISSUE_SEVERITY_WEIGHTS[asset["issue_type"]]
        for asset in asset_diagnostics
    )
    if highest_issue_weight == 0:
        return 0

    return highest_issue_weight * 10 + (5 if is_critical else 0)


def _build_feature_severity_level(severity_rank: int) -> str:
    if severity_rank >= 45:
        return "critical"
    if severity_rank >= 35:
        return "high"
    if severity_rank >= 25:
        return "medium"
    if severity_rank > 0:
        return "low"
    return "none"


def build_feature_source_diagnostics(
    feature_registry: dict[str, Any],
    source_registry: dict[str, Any] | None = None,
    *,
    source_observations: Mapping[str, datetime | str] | None = None,
    as_of_utc: datetime | None = None,
) -> dict[str, Any]:
    registry_data = source_registry or load_source_registry()
    entries = build_source_registry_entries(registry_data)
    index = build_source_registry_index(entries)
    freshness_diagnostics = build_source_freshness_diagnostics(
        registry_data,
        source_observations=source_observations,
        as_of_utc=as_of_utc,
    )
    freshness_by_source_id = {
        source["source_id"]: source for source in freshness_diagnostics["sources"]
    }
    freshness_evaluation_mode = freshness_diagnostics["summary"]["evaluation_mode"]

    diagnostics: list[dict[str, Any]] = []
    features_with_missing_sources = 0
    total_missing_assets = 0
    features_with_stale_sources = 0
    total_stale_assets = 0

    for group_name, group_config in feature_registry["score_groups"].items():
        for feature_name, feature_config in group_config["features"].items():
            requirements = feature_config["source_requirements"]
            is_critical = bool(feature_config["critical"])
            required_assets = list(requirements["required_assets"])
            minimum_decision_usage = requirements["minimum_decision_usage"]
            asset_diagnostics: list[dict[str, Any]] = []
            missing_assets: list[str] = []
            stale_assets: list[str] = []

            for asset_code in required_assets:
                asset_entries = index.get(asset_code, ())
                active_source_ids = [entry.source_id for entry in asset_entries if entry.active]
                eligible_source_ids = [
                    entry.source_id
                    for entry in asset_entries
                    if entry.active
                    and _meets_minimum_decision_usage(
                        entry.decision_usage,
                        minimum_decision_usage,
                    )
                ]
                fresh_source_ids = [
                    source_id
                    for source_id in eligible_source_ids
                    if freshness_by_source_id[source_id]["freshness_status"] == "fresh"
                ]
                stale_source_ids = [
                    source_id
                    for source_id in eligible_source_ids
                    if freshness_by_source_id[source_id]["freshness_status"] == "stale"
                ]
                missing_timestamp_source_ids = [
                    source_id
                    for source_id in eligible_source_ids
                    if freshness_by_source_id[source_id]["freshness_status"] == "missing_timestamp"
                ]

                if fresh_source_ids or (
                    freshness_evaluation_mode == "not_evaluated" and eligible_source_ids
                ):
                    status = "ready"
                    issue_type = None
                elif stale_source_ids:
                    status = "stale_source"
                    issue_type = "freshness_policy_not_met"
                    stale_assets.append(asset_code)
                elif missing_timestamp_source_ids:
                    status = "stale_source"
                    issue_type = "missing_source_timestamp"
                    stale_assets.append(asset_code)
                elif active_source_ids:
                    status = "insufficient_decision_usage"
                    issue_type = "minimum_decision_usage_not_met"
                    missing_assets.append(asset_code)
                else:
                    status = "missing_active_source"
                    issue_type = "no_active_source"
                    missing_assets.append(asset_code)

                asset_diagnostics.append(
                    {
                        "asset_code": asset_code,
                        "status": status,
                        "issue_type": issue_type,
                        "active_source_ids": active_source_ids,
                        "eligible_source_ids": eligible_source_ids,
                        "fresh_source_ids": fresh_source_ids,
                        "stale_source_ids": stale_source_ids,
                        "missing_timestamp_source_ids": missing_timestamp_source_ids,
                        "coverage_credit": ASSET_COVERAGE_CREDITS[status],
                    }
                )

            if missing_assets:
                feature_status = "missing_required_sources"
            elif stale_assets:
                feature_status = "stale_required_sources"
            else:
                feature_status = "ready"

            if missing_assets:
                features_with_missing_sources += 1
                total_missing_assets += len(missing_assets)
            if stale_assets:
                features_with_stale_sources += 1
                total_stale_assets += len(stale_assets)

            coverage_score = round(
                sum(asset["coverage_credit"] for asset in asset_diagnostics) / len(asset_diagnostics),
                2,
            )
            severity_rank = _calculate_feature_severity_rank(
                is_critical=is_critical,
                asset_diagnostics=asset_diagnostics,
            )
            severity_level = _build_feature_severity_level(severity_rank)

            diagnostics.append(
                {
                    "score_group": group_name,
                    "feature_name": feature_name,
                    "critical": is_critical,
                    "minimum_decision_usage": minimum_decision_usage,
                    "required_assets": required_assets,
                    "missing_assets": missing_assets,
                    "stale_assets": stale_assets,
                    "status": feature_status,
                    "coverage_score": coverage_score,
                    "severity_rank": severity_rank,
                    "severity_level": severity_level,
                    "asset_diagnostics": asset_diagnostics,
                }
            )

    severity_ranking = sorted(
        (
            {
                "feature_name": feature["feature_name"],
                "score_group": feature["score_group"],
                "critical": feature["critical"],
                "status": feature["status"],
                "coverage_score": feature["coverage_score"],
                "severity_rank": feature["severity_rank"],
                "severity_level": feature["severity_level"],
                "missing_assets": feature["missing_assets"],
                "stale_assets": feature["stale_assets"],
            }
            for feature in diagnostics
            if feature["severity_rank"] > 0
        ),
        key=lambda item: (-item["severity_rank"], item["coverage_score"], item["feature_name"]),
    )

    return {
        "source_registry_version": registry_data["version"],
        "features": diagnostics,
        "summary": {
            "total_features": len(diagnostics),
            "ready_features": sum(1 for feature in diagnostics if feature["status"] == "ready"),
            "features_with_missing_sources": features_with_missing_sources,
            "total_missing_assets": total_missing_assets,
            "features_with_stale_sources": features_with_stale_sources,
            "total_stale_assets": total_stale_assets,
            "average_coverage_score": round(
                sum(feature["coverage_score"] for feature in diagnostics) / len(diagnostics),
                2,
            ),
            "minimum_coverage_score": min(feature["coverage_score"] for feature in diagnostics),
            "freshness_evaluation_mode": freshness_evaluation_mode,
            "severity_ranking": severity_ranking,
        },
    }
