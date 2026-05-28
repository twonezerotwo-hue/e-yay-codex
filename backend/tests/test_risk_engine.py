from app.services.data_quality_service import DataQualityDecision
from app.services.data_quality_service import DataQualityScoreResult
from app.services.risk_engine import RiskAction
from app.services.risk_engine import RiskEngine
from app.services.risk_engine import SnapshotRiskInput
from app.services.trigger_engine import TriggerConfirmationStatus
from app.services.trigger_engine import TriggerResult
from app.services.trigger_engine import TriggerSeverity


def build_dqs_result(decision: DataQualityDecision, total_score: float = 100.0) -> DataQualityScoreResult:
    return DataQualityScoreResult(
        total_score=total_score,
        decision=decision,
        component_scores={
            "freshness_score": total_score,
            "source_tier_score": total_score,
            "cross_provider_agreement_score": total_score,
            "completeness_score": total_score,
            "timestamp_integrity_score": total_score,
            "anomaly_consistency_score": total_score,
        },
    )


def build_trigger(
    trigger_code: str,
    *,
    severity: TriggerSeverity,
    asset_symbol: str,
    is_triggered: bool = True,
    confirmation_status: TriggerConfirmationStatus = TriggerConfirmationStatus.CONFIRMED,
) -> TriggerResult:
    return TriggerResult(
        trigger_code=trigger_code,
        severity=severity,
        asset_symbol=asset_symbol,
        is_triggered=is_triggered,
        confirmation_status=confirmation_status,
        message=f"{trigger_code} message",
    )


def test_fail_no_decision_on_critical_snapshot_triggers_kill_switch() -> None:
    result = RiskEngine().evaluate(
        [SnapshotRiskInput(asset_symbol="BTCUSD", dqs_result=build_dqs_result(DataQualityDecision.FAIL_NO_DECISION))],
        [],
    )

    assert result.risk_action == RiskAction.KILL_SWITCH
    assert result.kill_switch_active is True
    assert "CRITICAL_DQS_FAIL_NO_DECISION:BTCUSD" in result.reason_codes


def test_limited_analysis_only_on_critical_snapshot_triggers_no_position_increase() -> None:
    result = RiskEngine().evaluate(
        [SnapshotRiskInput(asset_symbol="BRENT", dqs_result=build_dqs_result(DataQualityDecision.LIMITED_ANALYSIS_ONLY, 60.0))],
        [],
    )

    assert result.risk_action == RiskAction.NO_POSITION_INCREASE
    assert result.kill_switch_active is False
    assert "CRITICAL_DQS_LIMITED_ANALYSIS_ONLY:BRENT" in result.reason_codes


def test_confirmed_brent_red_trigger_enforces_no_position_increase() -> None:
    result = RiskEngine().evaluate(
        [SnapshotRiskInput(asset_symbol="BRENT", dqs_result=build_dqs_result(DataQualityDecision.PASS))],
        [
            build_trigger(
                "RED_ENERGY_SHOCK",
                severity=TriggerSeverity.RED,
                asset_symbol="BRENT",
            )
        ],
    )

    assert result.risk_action == RiskAction.NO_POSITION_INCREASE
    assert "RED_ENERGY_SHOCK_CONFIRMED" in result.reason_codes


def test_multiple_serious_triggers_raise_risk_reduce() -> None:
    result = RiskEngine().evaluate(
        [SnapshotRiskInput(asset_symbol="BTCUSD", dqs_result=build_dqs_result(DataQualityDecision.PASS))],
        [
            build_trigger(
                "RED_ENERGY_SHOCK",
                severity=TriggerSeverity.RED,
                asset_symbol="BRENT",
            ),
            build_trigger(
                "BTC_RISK_OFF_WARNING",
                severity=TriggerSeverity.ORANGE,
                asset_symbol="BTCUSD",
            ),
        ],
    )

    assert result.risk_action == RiskAction.RISK_REDUCE
    assert "MULTI_SEVERE_TRIGGER_STACK" in result.reason_codes


def test_silver_strategic_trigger_adds_note_without_hard_risk_action() -> None:
    result = RiskEngine().evaluate(
        [SnapshotRiskInput(asset_symbol="XAGUSD", dqs_result=build_dqs_result(DataQualityDecision.PASS))],
        [
            build_trigger(
                "SILVER_STRATEGIC_METALS_REGIME",
                severity=TriggerSeverity.YELLOW,
                asset_symbol="XAGUSD",
            )
        ],
    )

    assert result.risk_action == RiskAction.HOLD
    assert "SILVER_STRATEGIC_METALS_REGIME_NOTE" in result.reason_codes


def test_priority_order_preserves_harsher_decision() -> None:
    result = RiskEngine().evaluate(
        [
            SnapshotRiskInput(asset_symbol="BTCUSD", dqs_result=build_dqs_result(DataQualityDecision.FAIL_NO_DECISION, 40.0)),
            SnapshotRiskInput(asset_symbol="XAUUSD", dqs_result=build_dqs_result(DataQualityDecision.LIMITED_ANALYSIS_ONLY, 60.0)),
        ],
        [
            build_trigger(
                "RED_ENERGY_SHOCK",
                severity=TriggerSeverity.RED,
                asset_symbol="BRENT",
            ),
            build_trigger(
                "BTC_RISK_OFF_WARNING",
                severity=TriggerSeverity.ORANGE,
                asset_symbol="BTCUSD",
            ),
            build_trigger(
                "GOLD_HEDGE_BREAKOUT",
                severity=TriggerSeverity.YELLOW,
                asset_symbol="XAUUSD",
            ),
        ],
    )

    assert result.risk_action == RiskAction.KILL_SWITCH
    assert result.kill_switch_active is True
    assert result.reason_codes[0] == "CRITICAL_DQS_FAIL_NO_DECISION:BTCUSD"

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
