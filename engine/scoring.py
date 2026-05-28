from __future__ import annotations

from collections.abc import Mapping


def calculate_group_scores(
    normalized_features: Mapping[str, Mapping[str, float]],
    weights_config: Mapping[str, object],
) -> dict[str, float]:
    group_scores: dict[str, float] = {}

    for group_name, feature_weights in weights_config["score_groups"].items():
        weighted_total = 0.0
        for feature_name, weight in feature_weights.items():
            weighted_total += normalized_features[group_name][feature_name] * float(weight)
        group_scores[group_name] = round(weighted_total, 4)

    return group_scores


def calculate_overall_score(group_scores: Mapping[str, float]) -> float:
    if not group_scores:
        return 0.0

    total_score = sum(group_scores.values())
    return round(total_score / len(group_scores), 4)
