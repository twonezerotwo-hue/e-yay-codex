from datetime import UTC, datetime
from datetime import timedelta

from app.domain import AssetCategory
from app.domain import AssetCode
from app.domain import list_main_assets
from registry import build_feature_source_diagnostics
from registry import build_report_source_binding
from registry import build_source_freshness_diagnostics
from registry import build_source_registry_entries
from registry import load_source_registry
from reports.generator import CONFIG_DIR
from reports.generator import SCHEMA_DIR
from reports.generator import load_feature_registry
from reports.generator import load_json_schema
from reports.generator import load_yaml_file
from reports.generator import validate_config


def test_source_registry_schema_validation() -> None:
    source_registry = load_yaml_file(CONFIG_DIR / "source_registry_v1.0.yaml")
    schema = load_json_schema(SCHEMA_DIR / "source_registry.schema.json")

    validated = validate_config(source_registry, schema)

    assert validated["version"] == "1.0"
    assert validated["freshness_policy"]["realtime"]["max_age_minutes"] == 15
    assert len(validated["sources"]) >= 1


def test_main_asset_catalog_contains_expected_foundation_assets() -> None:
    asset_codes = {asset.code for asset in list_main_assets()}

    assert AssetCode.BTCUSD in asset_codes
    assert AssetCode.BRENT in asset_codes
    assert AssetCode.BTC_DOMINANCE in asset_codes
    assert AssetCode.USCPI in asset_codes
    assert AssetCode.BTCXAUK in asset_codes
    assert AssetCategory.LOCAL_REFERENCE in {asset.category for asset in list_main_assets()}


def test_source_registry_entries_map_to_asset_catalog() -> None:
    entries = build_source_registry_entries(load_source_registry())
    registry_by_source_id = {entry.source_id: entry for entry in entries}

    assert registry_by_source_id["approved_btcusd_feed"].asset.code == AssetCode.BTCUSD
    assert registry_by_source_id["approved_uscpi_feed"].asset.category == AssetCategory.INFLATION_LIQUIDITY
    assert registry_by_source_id["approved_qqq_feed"].decision_usage == "verified_required"


def test_unverified_registry_entries_are_simulation_only() -> None:
    entries = build_source_registry_entries(load_source_registry())
    unverified_entries = [entry for entry in entries if not entry.verified]

    assert {entry.asset.code for entry in unverified_entries} == {
        AssetCode.BTCXAUK,
        AssetCode.XAUUSDK,
        AssetCode.XAGUSDK,
    }
    assert {entry.decision_usage for entry in unverified_entries} == {"simulation_only"}


def test_report_source_binding_covers_full_asset_catalog() -> None:
    source_binding = build_report_source_binding(load_source_registry())
    bindings_by_asset = {
        binding["asset_code"]: binding for binding in source_binding["bindings"]
    }

    assert source_binding["source_registry_version"] == "1.0"
    assert len(bindings_by_asset) == len(list_main_assets())
    assert source_binding["coverage"]["uncovered_assets"] == []
    assert source_binding["coverage"]["simulation_only_assets"] == 3
    assert source_binding["coverage"]["verified_required_assets"] == len(list_main_assets()) - 3
    assert bindings_by_asset["QQQ"]["live_eligible"] is True
    assert bindings_by_asset["BTCXAUK"]["decision_usages"] == ["simulation_only"]
    assert bindings_by_asset["BTCXAUK"]["live_eligible"] is False
    assert bindings_by_asset["BTCXAUK"]["required_for_core_report"] is False


def test_feature_source_diagnostics_are_ready_for_current_registry() -> None:
    diagnostics = build_feature_source_diagnostics(
        load_feature_registry(),
        load_source_registry(),
    )
    diagnostics_by_feature = {
        feature["feature_name"]: feature for feature in diagnostics["features"]
    }

    assert diagnostics["source_registry_version"] == "1.0"
    assert diagnostics["summary"] == {
        "total_features": 4,
        "ready_features": 4,
        "features_with_missing_sources": 0,
        "total_missing_assets": 0,
        "features_with_stale_sources": 0,
        "total_stale_assets": 0,
        "average_coverage_score": 100.0,
        "minimum_coverage_score": 100.0,
        "freshness_evaluation_mode": "not_evaluated",
        "severity_ranking": [],
    }
    assert diagnostics_by_feature["liquidity_trend"]["required_assets"] == ["M2SL", "US10Y", "DXY"]
    assert diagnostics_by_feature["liquidity_trend"]["status"] == "ready"
    assert diagnostics_by_feature["liquidity_trend"]["coverage_score"] == 100.0
    assert diagnostics_by_feature["liquidity_trend"]["severity_level"] == "none"
    assert diagnostics_by_feature["liquidity_trend"]["severity_rank"] == 0
    assert diagnostics_by_feature["volatility_pressure"]["asset_diagnostics"][0]["asset_code"] == "QQQ"


def test_feature_source_diagnostics_flag_missing_or_insufficient_sources() -> None:
    feature_registry = load_feature_registry()
    source_registry = load_source_registry()
    modified_sources: list[dict[str, object]] = []

    for source in source_registry["sources"]:
        updated_source = dict(source)
        if updated_source["source_id"] == "approved_uscpi_feed":
            updated_source["active"] = False
        if updated_source["source_id"] == "approved_jnk_feed":
            updated_source["verified"] = False
            updated_source["decision_usage"] = "simulation_only"
        modified_sources.append(updated_source)

    diagnostics = build_feature_source_diagnostics(
        feature_registry,
        {
            "version": source_registry["version"],
            "freshness_policy": source_registry["freshness_policy"],
            "sources": modified_sources,
        },
    )
    diagnostics_by_feature = {
        feature["feature_name"]: feature for feature in diagnostics["features"]
    }
    inflation_assets = {
        asset["asset_code"]: asset for asset in diagnostics_by_feature["inflation_stability"]["asset_diagnostics"]
    }
    credit_assets = {
        asset["asset_code"]: asset for asset in diagnostics_by_feature["credit_spread_stress"]["asset_diagnostics"]
    }

    assert diagnostics["summary"]["features_with_missing_sources"] == 2
    assert diagnostics["summary"]["total_missing_assets"] == 2
    assert diagnostics["summary"]["features_with_stale_sources"] == 0
    assert diagnostics["summary"]["average_coverage_score"] == 78.12
    assert diagnostics["summary"]["minimum_coverage_score"] == 50.0
    assert diagnostics["summary"]["severity_ranking"] == [
        {
            "feature_name": "inflation_stability",
            "score_group": "macro_regime",
            "critical": False,
            "status": "missing_required_sources",
            "coverage_score": 50.0,
            "severity_rank": 40,
            "severity_level": "high",
            "missing_assets": ["USCPI"],
            "stale_assets": [],
        },
        {
            "feature_name": "credit_spread_stress",
            "score_group": "market_risk",
            "critical": True,
            "status": "missing_required_sources",
            "coverage_score": 62.5,
            "severity_rank": 35,
            "severity_level": "high",
            "missing_assets": ["JNK"],
            "stale_assets": [],
        },
    ]
    assert diagnostics_by_feature["inflation_stability"]["status"] == "missing_required_sources"
    assert diagnostics_by_feature["inflation_stability"]["missing_assets"] == ["USCPI"]
    assert diagnostics_by_feature["inflation_stability"]["coverage_score"] == 50.0
    assert diagnostics_by_feature["inflation_stability"]["severity_level"] == "high"
    assert inflation_assets["USCPI"]["status"] == "missing_active_source"
    assert inflation_assets["USCPI"]["issue_type"] == "no_active_source"
    assert diagnostics_by_feature["credit_spread_stress"]["missing_assets"] == ["JNK"]
    assert diagnostics_by_feature["credit_spread_stress"]["coverage_score"] == 62.5
    assert diagnostics_by_feature["credit_spread_stress"]["severity_level"] == "high"
    assert credit_assets["JNK"]["status"] == "insufficient_decision_usage"
    assert credit_assets["JNK"]["issue_type"] == "minimum_decision_usage_not_met"


def test_source_freshness_and_feature_diagnostics_flag_stale_sources() -> None:
    as_of_utc = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    source_registry = load_source_registry()
    feature_registry = load_feature_registry()
    source_observations: dict[str, datetime] = {}

    for source in source_registry["sources"]:
        source_observations[source["source_id"]] = as_of_utc - timedelta(minutes=5)

    source_observations["approved_uscpi_feed"] = as_of_utc - timedelta(days=40)

    source_freshness = build_source_freshness_diagnostics(
        source_registry,
        source_observations=source_observations,
        as_of_utc=as_of_utc,
    )
    diagnostics = build_feature_source_diagnostics(
        feature_registry,
        source_registry,
        source_observations=source_observations,
        as_of_utc=as_of_utc,
    )
    diagnostics_by_feature = {
        feature["feature_name"]: feature for feature in diagnostics["features"]
    }
    inflation_assets = {
        asset["asset_code"]: asset for asset in diagnostics_by_feature["inflation_stability"]["asset_diagnostics"]
    }

    assert source_freshness["summary"] == {
        "total_sources": len(source_registry["sources"]),
        "total_active_sources": len(source_registry["sources"]),
        "fresh_sources": len(source_registry["sources"]) - 1,
        "stale_sources": 1,
        "sources_missing_timestamps": 0,
        "not_evaluated_sources": 0,
        "evaluation_mode": "observed",
    }
    assert diagnostics["summary"]["features_with_stale_sources"] == 1
    assert diagnostics["summary"]["total_stale_assets"] == 1
    assert diagnostics["summary"]["ready_features"] == 3
    assert diagnostics["summary"]["average_coverage_score"] == 93.75
    assert diagnostics["summary"]["minimum_coverage_score"] == 75.0
    assert diagnostics["summary"]["freshness_evaluation_mode"] == "observed"
    assert diagnostics["summary"]["severity_ranking"] == [
        {
            "feature_name": "inflation_stability",
            "score_group": "macro_regime",
            "critical": False,
            "status": "stale_required_sources",
            "coverage_score": 75.0,
            "severity_rank": 20,
            "severity_level": "low",
            "missing_assets": [],
            "stale_assets": ["USCPI"],
        }
    ]
    assert diagnostics_by_feature["inflation_stability"]["status"] == "stale_required_sources"
    assert diagnostics_by_feature["inflation_stability"]["stale_assets"] == ["USCPI"]
    assert diagnostics_by_feature["inflation_stability"]["coverage_score"] == 75.0
    assert diagnostics_by_feature["inflation_stability"]["severity_level"] == "low"
    assert inflation_assets["USCPI"]["status"] == "stale_source"
    assert inflation_assets["USCPI"]["issue_type"] == "freshness_policy_not_met"
