from datetime import UTC, datetime
from datetime import timedelta

from audit.logger import create_audit_record
from reports.generator import generate_daily_report
from reports.generator import load_source_registry


SAMPLE_RAW_FEATURES = {
    "liquidity_trend": 1.0,
    "inflation_stability": 7.0,
    "credit_spread_stress": 120.0,
    "volatility_pressure": 20.0,
}


def test_report_is_complete() -> None:
    source_count = len(load_source_registry()["sources"])
    report = generate_daily_report(
        SAMPLE_RAW_FEATURES,
        previous_regime="neutral",
        verified_data_available=False,
        as_of_utc=datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC),
    )

    assert report["report_complete"] is True
    assert report["scores"]["overall"] == 69.25
    assert report["risk"]["action"] == "SIMULATION_ONLY"
    assert report["regime"] == "neutral"
    assert report["source_registry_version"] == "1.0"
    assert report["source_binding"]["source_registry_version"] == "1.0"
    assert report["source_binding"]["coverage"]["uncovered_assets"] == []
    assert report["source_binding"]["coverage"]["simulation_only_assets"] == 3
    assert report["source_freshness"]["source_registry_version"] == "1.0"
    assert report["source_freshness"]["summary"] == {
        "total_sources": source_count,
        "total_active_sources": source_count,
        "fresh_sources": 0,
        "stale_sources": 0,
        "sources_missing_timestamps": 0,
        "not_evaluated_sources": source_count,
        "evaluation_mode": "not_evaluated",
    }
    assert report["source_diagnostics"]["source_registry_version"] == "1.0"
    assert report["source_diagnostics"]["summary"] == {
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


def test_audit_record_creation() -> None:
    record = create_audit_record(
        event_type="daily_report_generated",
        message="Phase 1 deterministic report created.",
        details_json={"regime": "neutral"},
        request_id="daily-report-001",
        created_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC),
    )

    assert record == {
        "timestamp_utc": "2026-05-18T12:00:00+00:00",
        "event_type": "daily_report_generated",
        "message": "Phase 1 deterministic report created.",
        "details_json": {"regime": "neutral"},
        "request_id": "daily-report-001",
    }


def test_report_surfaces_stale_source_diagnostics_when_observations_are_old() -> None:
    as_of_utc = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    source_registry = load_source_registry()
    source_observations: dict[str, datetime] = {}

    for source in source_registry["sources"]:
        source_observations[source["source_id"]] = as_of_utc - timedelta(minutes=5)

    source_observations["approved_uscpi_feed"] = as_of_utc - timedelta(days=40)

    report = generate_daily_report(
        SAMPLE_RAW_FEATURES,
        previous_regime="neutral",
        verified_data_available=False,
        as_of_utc=as_of_utc,
        source_observations=source_observations,
    )
    inflation_diagnostic = next(
        feature
        for feature in report["source_diagnostics"]["features"]
        if feature["feature_name"] == "inflation_stability"
    )

    assert report["source_freshness"]["summary"]["evaluation_mode"] == "observed"
    assert report["source_freshness"]["summary"]["stale_sources"] == 1
    assert report["source_diagnostics"]["summary"]["average_coverage_score"] == 93.75
    assert report["source_diagnostics"]["summary"]["severity_ranking"] == [
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
    assert inflation_diagnostic["status"] == "stale_required_sources"
    assert inflation_diagnostic["stale_assets"] == ["USCPI"]
    assert inflation_diagnostic["coverage_score"] == 75.0
