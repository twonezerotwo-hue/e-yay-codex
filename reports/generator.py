from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from engine.normalize import build_normalization_context
from engine.regime import determine_regime
from engine.risk_engine import evaluate_risk
from engine.scoring import calculate_group_scores, calculate_overall_score


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"
SCHEMA_DIR = REPO_ROOT / "schemas"


def load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return dict(data)


def load_json_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_config(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    jsonschema.validate(instance=data, schema=schema)
    return data


def _load_and_validate(config_name: str, schema_name: str) -> dict[str, Any]:
    data = load_yaml_file(CONFIG_DIR / config_name)
    schema = load_json_schema(SCHEMA_DIR / schema_name)
    return validate_config(data, schema)


def load_feature_registry() -> dict[str, Any]:
    return _load_and_validate("feature_registry_v1.0.yaml", "feature_registry.schema.json")


def load_weights() -> dict[str, Any]:
    return _load_and_validate("weights_v1.0.yaml", "weights.schema.json")


def load_thresholds() -> dict[str, Any]:
    return _load_and_validate("thresholds_v1.0.yaml", "thresholds.schema.json")


def load_source_registry() -> dict[str, Any]:
    return _load_and_validate("source_registry_v1.0.yaml", "source_registry.schema.json")


def generate_daily_report(
    raw_features: dict[str, float],
    *,
    previous_regime: str | None = None,
    verified_data_available: bool = False,
    as_of_utc: datetime | None = None,
    source_observations: dict[str, datetime | str] | None = None,
) -> dict[str, Any]:
    feature_registry = load_feature_registry()
    source_registry = load_source_registry()
    weights = load_weights()
    thresholds = load_thresholds()
    normalization_context = build_normalization_context(raw_features, feature_registry)
    group_scores = calculate_group_scores(normalization_context["normalized_features"], weights)
    overall_score = calculate_overall_score(group_scores)
    regime = determine_regime(overall_score, previous_regime, thresholds["regime"])
    risk = evaluate_risk(
        data_quality_score=normalization_context["data_quality_score"],
        critical_missing_data=normalization_context["critical_missing_data"],
        verified_data_available=verified_data_available,
        thresholds=thresholds["risk"],
    )
    from registry.source_registry import build_feature_source_diagnostics
    from registry.source_registry import build_source_freshness_diagnostics
    from registry.source_registry import build_report_source_binding

    source_binding = build_report_source_binding(source_registry)
    source_freshness = build_source_freshness_diagnostics(
        source_registry,
        source_observations=source_observations,
        as_of_utc=as_of_utc,
    )
    source_diagnostics = build_feature_source_diagnostics(
        feature_registry,
        source_registry,
        source_observations=source_observations,
        as_of_utc=as_of_utc,
    )

    timestamp = (as_of_utc or datetime.now(UTC)).astimezone(UTC).isoformat()
    report = {
        "report_type": "deterministic_daily_report_phase1",
        "as_of_utc": timestamp,
        "feature_registry_version": feature_registry["version"],
        "source_registry_version": source_registry["version"],
        "weights_version": weights["version"],
        "thresholds_version": thresholds["version"],
        "verified_data_available": verified_data_available,
        "normalized_features": normalization_context["normalized_features"],
        "data_quality_score": normalization_context["data_quality_score"],
        "missing_features": normalization_context["missing_features"],
        "source_binding": source_binding,
        "source_freshness": source_freshness,
        "source_diagnostics": source_diagnostics,
        "scores": {
            "groups": group_scores,
            "overall": overall_score,
        },
        "regime": regime,
        "risk": risk,
    }
    required_sections = thresholds["report"]["required_sections"]
    report["report_complete"] = all(report.get(section) not in (None, {}, []) for section in required_sections)
    return report
