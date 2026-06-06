from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain import AssetCode
from app.domain import get_asset_definition
from app.services.data_quality_service import DataQualityDecision
from app.services.data_quality_service import DataQualityScoreResult
from app.services.trigger_engine import TriggerConfirmationStatus
from app.services.trigger_engine import TriggerResult
from app.services.trigger_engine import TriggerSeverity


class RiskAction(str, Enum):
    WATCH = "WATCH"
    HOLD = "HOLD"
    NO_POSITION_INCREASE = "NO_POSITION_INCREASE"
    RISK_REDUCE = "RISK_REDUCE"
    HEDGE_INCREASE = "HEDGE_INCREASE"
    KILL_SWITCH = "KILL_SWITCH"


ACTION_PRIORITY = {
    RiskAction.HOLD: 0,
    RiskAction.WATCH: 1,
    RiskAction.HEDGE_INCREASE: 2,
    RiskAction.NO_POSITION_INCREASE: 3,
    RiskAction.RISK_REDUCE: 4,
    RiskAction.KILL_SWITCH: 5,
}


@dataclass(frozen=True)
class SnapshotRiskInput:
    asset_symbol: AssetCode | str
    dqs_result: DataQualityScoreResult
    required_for_core_report: bool | None = None

    def __post_init__(self) -> None:
        asset_code = self.asset_symbol if isinstance(self.asset_symbol, AssetCode) else AssetCode(self.asset_symbol)
        required_for_core_report = self.required_for_core_report
        if required_for_core_report is None:
            required_for_core_report = get_asset_definition(asset_code).required_for_core_report

        object.__setattr__(self, "asset_symbol", asset_code)
        object.__setattr__(self, "required_for_core_report", bool(required_for_core_report))


@dataclass(frozen=True)
class RiskEngineResult:
    risk_action: RiskAction
    reason_codes: tuple[str, ...]
    summary: str
    kill_switch_active: bool


class RiskEngine:
    def evaluate(
        self,
        snapshot_quality_results: list[SnapshotRiskInput] | tuple[SnapshotRiskInput, ...],
        trigger_results: list[TriggerResult] | tuple[TriggerResult, ...],
    ) -> RiskEngineResult:
        action = RiskAction.HOLD
        reason_codes: list[str] = []

        for snapshot_result in snapshot_quality_results:
            if not snapshot_result.required_for_core_report:
                continue

            if snapshot_result.dqs_result.decision == DataQualityDecision.FAIL_NO_DECISION:
                action = self._raise_action(action, RiskAction.KILL_SWITCH)
                reason_codes.append(f"CRITICAL_DQS_FAIL_NO_DECISION:{snapshot_result.asset_symbol.value}")
                continue

            if snapshot_result.dqs_result.decision == DataQualityDecision.LIMITED_ANALYSIS_ONLY:
                action = self._raise_action(action, RiskAction.NO_POSITION_INCREASE)
                reason_codes.append(f"CRITICAL_DQS_LIMITED_ANALYSIS_ONLY:{snapshot_result.asset_symbol.value}")

        confirmed_triggered = tuple(
            trigger
            for trigger in trigger_results
            if trigger.is_triggered and trigger.confirmation_status == TriggerConfirmationStatus.CONFIRMED
        )
        severe_confirmed = tuple(
            trigger for trigger in confirmed_triggered if trigger.severity in {TriggerSeverity.RED, TriggerSeverity.ORANGE}
        )

        if len(severe_confirmed) >= 2:
            action = self._raise_action(action, RiskAction.RISK_REDUCE)
            reason_codes.append("MULTI_SEVERE_TRIGGER_STACK")

        for trigger in confirmed_triggered:
            if trigger.trigger_code == "RED_ENERGY_SHOCK":
                action = self._raise_action(action, RiskAction.NO_POSITION_INCREASE)
                reason_codes.append("RED_ENERGY_SHOCK_CONFIRMED")
            elif trigger.trigger_code == "BTC_RISK_OFF_WARNING":
                action = self._raise_action(action, RiskAction.WATCH)
                reason_codes.append("BTC_RISK_OFF_WARNING_CONFIRMED")
            elif trigger.trigger_code == "GOLD_HEDGE_BREAKOUT":
                action = self._raise_action(action, RiskAction.WATCH)
                reason_codes.append("GOLD_HEDGE_BREAKOUT_CONFIRMED")
            elif trigger.trigger_code == "SILVER_STRATEGIC_METALS_REGIME":
                reason_codes.append("SILVER_STRATEGIC_METALS_REGIME_NOTE")

        deduped_reason_codes = self._dedupe_reason_codes(reason_codes)
        return RiskEngineResult(
            risk_action=action,
            reason_codes=deduped_reason_codes,
            summary=self._build_summary(action, deduped_reason_codes),
            kill_switch_active=action == RiskAction.KILL_SWITCH,
        )

    def _raise_action(self, current_action: RiskAction, candidate_action: RiskAction) -> RiskAction:
        if ACTION_PRIORITY[candidate_action] > ACTION_PRIORITY[current_action]:
            return candidate_action
        return current_action

    @staticmethod
    def _dedupe_reason_codes(reason_codes: list[str]) -> tuple[str, ...]:
        ordered_unique: list[str] = []
        seen: set[str] = set()
        for reason_code in reason_codes:
            if reason_code in seen:
                continue
            seen.add(reason_code)
            ordered_unique.append(reason_code)
        return tuple(ordered_unique)

    @staticmethod
    def _build_summary(action: RiskAction, reason_codes: tuple[str, ...]) -> str:
        if not reason_codes:
            return f"Risk action remains {action.value} with no escalations."
        return f"Risk action set to {action.value} due to: {', '.join(reason_codes)}."

__all__ = [name for name in globals() if not name.startswith('_')]
