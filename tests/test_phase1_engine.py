from engine.normalize import build_normalization_context
from engine.regime import determine_regime
from engine.risk_engine import evaluate_risk
from engine.scoring import calculate_group_scores, calculate_overall_score
from reports.generator import load_feature_registry, load_thresholds, load_weights


SAMPLE_RAW_FEATURES = {
    "liquidity_trend": 1.0,
    "inflation_stability": 7.0,
    "credit_spread_stress": 120.0,
    "volatility_pressure": 20.0,
}


def test_normalization_output_between_zero_and_one_hundred() -> None:
    feature_registry = load_feature_registry()
    context = build_normalization_context(SAMPLE_RAW_FEATURES, feature_registry)

    for group_values in context["normalized_features"].values():
        for normalized_value in group_values.values():
            assert 0.0 <= normalized_value <= 100.0


def test_scoring_output_is_deterministic() -> None:
    feature_registry = load_feature_registry()
    weights = load_weights()
    context = build_normalization_context(SAMPLE_RAW_FEATURES, feature_registry)

    group_scores = calculate_group_scores(context["normalized_features"], weights)
    overall_score = calculate_overall_score(group_scores)

    assert group_scores == {
        "macro_regime": 64.0,
        "market_risk": 74.5,
    }
    assert overall_score == 69.25


def test_regime_hysteresis_behavior() -> None:
    thresholds = load_thresholds()["regime"]

    assert determine_regime(72.0, "neutral", thresholds) == "bull"
    assert determine_regime(60.0, "bull", thresholds) == "bull"
    assert determine_regime(50.0, "bull", thresholds) == "neutral"
    assert determine_regime(28.0, "neutral", thresholds) == "bear"
    assert determine_regime(40.0, "bear", thresholds) == "bear"
    assert determine_regime(50.0, "bear", thresholds) == "neutral"


def test_risk_engine_sets_no_trade_on_low_data_quality() -> None:
    thresholds = load_thresholds()["risk"]

    risk_result = evaluate_risk(
        data_quality_score=49.0,
        critical_missing_data=False,
        verified_data_available=True,
        thresholds=thresholds,
    )

    assert risk_result["action"] == "NO_TRADE"
    assert risk_result["final_gate"] == "risk_engine"
    assert risk_result["execution_mode"] == "NO_EXECUTION"
    assert risk_result["auto_full_enabled"] is False
