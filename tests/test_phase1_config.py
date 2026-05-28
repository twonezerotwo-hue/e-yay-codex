from math import isclose

from reports.generator import CONFIG_DIR
from reports.generator import SCHEMA_DIR
from reports.generator import load_json_schema
from reports.generator import load_thresholds
from reports.generator import load_weights
from reports.generator import load_yaml_file
from reports.generator import validate_config


def test_feature_registry_schema_validation() -> None:
    feature_registry = load_yaml_file(CONFIG_DIR / "feature_registry_v1.0.yaml")
    schema = load_json_schema(SCHEMA_DIR / "feature_registry.schema.json")

    validated = validate_config(feature_registry, schema)

    assert validated["version"] == "1.0"
    assert "macro_regime" in validated["score_groups"]
    assert validated["score_groups"]["macro_regime"]["features"]["liquidity_trend"]["source_requirements"] == {
        "required_assets": ["M2SL", "US10Y", "DXY"],
        "minimum_decision_usage": "verified_required",
    }


def test_weights_sum_to_one_per_score_group() -> None:
    weights = load_weights()

    for feature_weights in weights["score_groups"].values():
        assert isclose(sum(feature_weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-9)


def test_threshold_loading() -> None:
    thresholds = load_thresholds()

    assert thresholds["version"] == "1.0"
    assert thresholds["risk"]["no_trade_data_quality_score"] == 50.0
    assert "source_binding" in thresholds["report"]["required_sections"]
    assert "source_diagnostics" in thresholds["report"]["required_sections"]
    assert "source_freshness" in thresholds["report"]["required_sections"]
