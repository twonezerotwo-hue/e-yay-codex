from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def normalize_feature(
    raw_value: float,
    minimum: float,
    maximum: float,
    *,
    higher_is_better: bool = True,
) -> float:
    if maximum <= minimum:
        raise ValueError("Feature maximum must be greater than minimum.")

    scaled = ((raw_value - minimum) / (maximum - minimum)) * 100.0
    if not higher_is_better:
        scaled = 100.0 - scaled

    clamped = max(0.0, min(100.0, scaled))
    return round(clamped, 4)


def build_normalization_context(
    raw_features: Mapping[str, float],
    feature_registry: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_features: dict[str, dict[str, float]] = {}
    missing_features: list[str] = []
    critical_missing_data = False
    total_features = 0
    available_features = 0

    for group_name, group_config in feature_registry["score_groups"].items():
        normalized_features[group_name] = {}
        for feature_name, feature_config in group_config["features"].items():
            total_features += 1

            if feature_name in raw_features:
                available_features += 1
                normalized_features[group_name][feature_name] = normalize_feature(
                    float(raw_features[feature_name]),
                    float(feature_config["min"]),
                    float(feature_config["max"]),
                    higher_is_better=bool(feature_config["higher_is_better"]),
                )
                continue

            missing_features.append(feature_name)
            normalized_features[group_name][feature_name] = 0.0
            if feature_config["critical"]:
                critical_missing_data = True

    data_quality_score = 0.0
    if total_features:
        data_quality_score = round((available_features / total_features) * 100.0, 2)

    return {
        "normalized_features": normalized_features,
        "missing_features": missing_features,
        "critical_missing_data": critical_missing_data,
        "data_quality_score": data_quality_score,
    }
