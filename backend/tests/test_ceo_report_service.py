from app.services.ceo_report_service import CEOReportService
from app.services.risk_engine import RiskAction
from app.services.risk_engine import RiskEngineResult
from app.services.trigger_engine import TriggerConfirmationStatus
from app.services.trigger_engine import TriggerResult
from app.services.trigger_engine import TriggerSeverity


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


def build_risk_result(
    risk_action: RiskAction,
    *,
    reason_codes: tuple[str, ...] = (),
    summary: str | None = None,
    kill_switch_active: bool | None = None,
) -> RiskEngineResult:
    return RiskEngineResult(
        risk_action=risk_action,
        reason_codes=reason_codes,
        summary=summary or f"Risk action set to {risk_action.value}.",
        kill_switch_active=risk_action == RiskAction.KILL_SWITCH if kill_switch_active is None else kill_switch_active,
    )


def test_trigger_and_risk_results_are_transferred_to_report() -> None:
    report = CEOReportService().generate(
        [
            build_trigger(
                "GOLD_HEDGE_BREAKOUT",
                severity=TriggerSeverity.YELLOW,
                asset_symbol="XAUUSD",
            ),
            build_trigger(
                "SILVER_STRATEGIC_METALS_REGIME",
                severity=TriggerSeverity.YELLOW,
                asset_symbol="XAGUSD",
            ),
        ],
        build_risk_result(
            RiskAction.NO_POSITION_INCREASE,
            reason_codes=("GOLD_HEDGE_BREAKOUT_CONFIRMED", "SILVER_STRATEGIC_METALS_REGIME_NOTE"),
        ),
    )

    assert report.risk_action == RiskAction.NO_POSITION_INCREASE
    assert report.owner_action.startswith("Do not increase positions.")
    assert "Gold hedge demand is strengthening." in report.key_triggers
    assert "Silver is entering a strategic metals watch regime." in report.key_triggers


def test_execution_status_is_always_off_no_execution() -> None:
    report = CEOReportService().generate([], build_risk_result(RiskAction.HOLD))

    assert report.execution_status == "OFF / NO_EXECUTION"


def test_red_energy_shock_is_called_out_in_report() -> None:
    report = CEOReportService().generate(
        [
            build_trigger(
                "RED_ENERGY_SHOCK",
                severity=TriggerSeverity.RED,
                asset_symbol="BRENT",
            )
        ],
        build_risk_result(
            RiskAction.NO_POSITION_INCREASE,
            reason_codes=("RED_ENERGY_SHOCK_CONFIRMED",),
        ),
    )

    assert "Energy shock risk is elevated." in report.key_triggers
    assert any("Energy shock risk is elevated." in sentence for sentence in report.short_report_sentences)


def test_kill_switch_report_uses_strong_stop_language() -> None:
    report = CEOReportService().generate(
        [],
        build_risk_result(
            RiskAction.KILL_SWITCH,
            reason_codes=("CRITICAL_DQS_FAIL_NO_DECISION:BTCUSD",),
        ),
    )

    assert report.report_title == "CEO Risk Alert - Immediate Stop"
    assert report.owner_action.startswith("Stop escalation immediately.")
    assert any("stop condition" in sentence.lower() for sentence in report.short_report_sentences)


def test_short_report_sentence_count_stays_between_five_and_ten() -> None:
    report = CEOReportService().generate(
        [
            build_trigger(
                "RED_ENERGY_SHOCK",
                severity=TriggerSeverity.RED,
                asset_symbol="BRENT",
            ),
            build_trigger(
                "GOLD_HEDGE_BREAKOUT",
                severity=TriggerSeverity.YELLOW,
                asset_symbol="XAUUSD",
            ),
            build_trigger(
                "SILVER_STRATEGIC_METALS_REGIME",
                severity=TriggerSeverity.YELLOW,
                asset_symbol="XAGUSD",
            ),
        ],
        build_risk_result(
            RiskAction.RISK_REDUCE,
            reason_codes=("MULTI_SEVERE_TRIGGER_STACK",),
        ),
    )

    assert 5 <= len(report.short_report_sentences) <= 10

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
