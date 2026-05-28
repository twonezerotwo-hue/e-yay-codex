from __future__ import annotations

from dataclasses import dataclass

from app.services.risk_engine import RiskAction
from app.services.risk_engine import RiskEngineResult
from app.services.trigger_engine import TriggerResult


EXECUTION_STATUS = "OFF / NO_EXECUTION"

TRIGGER_LABELS = {
    "RED_ENERGY_SHOCK": "Energy shock risk is elevated.",
    "BTC_RISK_OFF_WARNING": "Bitcoin is leaning risk-off.",
    "BTC_RISK_ON_CANDIDATE": "Bitcoin upside is not yet confirmed by credit data.",
    "GOLD_HEDGE_BREAKOUT": "Gold hedge demand is strengthening.",
    "SILVER_STRATEGIC_METALS_REGIME": "Silver is entering a strategic metals watch regime.",
    "SILVER_MOMENTUM_ACCELERATION": "Silver momentum is accelerating.",
    "SILVER_EXHAUSTION_WATCH": "Silver is approaching an exhaustion zone.",
    "HYG_JNK_BREAKDOWN_WATCH": "Credit breakdown confirmation is still pending.",
}


@dataclass(frozen=True)
class CEOReport:
    report_title: str
    regime_summary: str
    key_triggers: tuple[str, ...]
    risk_action: RiskAction
    owner_action: str
    execution_status: str
    short_report_sentences: tuple[str, ...]


class CEOReportService:
    def generate(
        self,
        trigger_results: list[TriggerResult] | tuple[TriggerResult, ...],
        risk_engine_result: RiskEngineResult,
    ) -> CEOReport:
        active_triggers = tuple(
            trigger
            for trigger in trigger_results
            if trigger.is_triggered
        )
        key_triggers = self._build_key_triggers(active_triggers)
        regime_summary = self._build_regime_summary(risk_engine_result, key_triggers)
        owner_action = self._build_owner_action(risk_engine_result.risk_action)
        short_report_sentences = self._build_short_report_sentences(
            risk_engine_result=risk_engine_result,
            key_triggers=key_triggers,
            regime_summary=regime_summary,
            owner_action=owner_action,
        )

        return CEOReport(
            report_title=self._build_report_title(risk_engine_result.risk_action),
            regime_summary=regime_summary,
            key_triggers=key_triggers,
            risk_action=risk_engine_result.risk_action,
            owner_action=owner_action,
            execution_status=EXECUTION_STATUS,
            short_report_sentences=short_report_sentences,
        )

    def _build_report_title(self, risk_action: RiskAction) -> str:
        if risk_action == RiskAction.KILL_SWITCH:
            return "CEO Risk Alert - Immediate Stop"
        if risk_action == RiskAction.RISK_REDUCE:
            return "CEO Risk Alert - Reduce Exposure"
        if risk_action == RiskAction.NO_POSITION_INCREASE:
            return "CEO Risk Alert - Do Not Add Risk"
        if risk_action == RiskAction.WATCH:
            return "CEO Watch Brief"
        if risk_action == RiskAction.HEDGE_INCREASE:
            return "CEO Hedge Brief"
        return "CEO Market Brief"

    def _build_regime_summary(
        self,
        risk_engine_result: RiskEngineResult,
        key_triggers: tuple[str, ...],
    ) -> str:
        if risk_engine_result.risk_action == RiskAction.KILL_SWITCH:
            return "Data or risk integrity is not strong enough to continue normal decision flow."
        if any("Energy shock" in trigger for trigger in key_triggers):
            return "Energy stress is rising and broad risk posture should stay defensive."
        if any("Gold hedge demand" in trigger for trigger in key_triggers):
            return "Defensive hedge demand is building even without a full stop condition."
        if any("Silver is entering a strategic metals watch regime." == trigger for trigger in key_triggers):
            return "Strategic metals deserve closer monitoring, but the signal is not a hard risk escalation by itself."
        if risk_engine_result.risk_action == RiskAction.RISK_REDUCE:
            return "Multiple serious signals are aligned and justify a tighter risk posture."
        if risk_engine_result.risk_action == RiskAction.NO_POSITION_INCREASE:
            return "Signal quality or market stress is high enough to block fresh risk expansion."
        if risk_engine_result.risk_action == RiskAction.WATCH:
            return "Conditions are mixed and require close monitoring before any stronger move."
        return "No hard escalation is active, but the system remains in validation-first monitoring mode."

    def _build_owner_action(self, risk_action: RiskAction) -> str:
        if risk_action == RiskAction.KILL_SWITCH:
            return "Stop escalation immediately. Keep execution OFF and investigate before any new decision cycle."
        if risk_action == RiskAction.RISK_REDUCE:
            return "Reduce risk posture and avoid adding exposure until the stress stack clears."
        if risk_action == RiskAction.NO_POSITION_INCREASE:
            return "Do not increase positions. Keep execution OFF and wait for cleaner confirmation."
        if risk_action == RiskAction.HEDGE_INCREASE:
            return "Increase protection and keep execution OFF until the hedge need is reassessed."
        if risk_action == RiskAction.WATCH:
            return "Stay on watch, keep execution OFF, and review the next validated update."
        return "Hold current stance, keep execution OFF, and continue normal monitoring."

    def _build_key_triggers(self, active_triggers: tuple[TriggerResult, ...]) -> tuple[str, ...]:
        labels: list[str] = []
        seen: set[str] = set()
        for trigger in active_triggers:
            label = TRIGGER_LABELS.get(trigger.trigger_code, trigger.message)
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return tuple(labels)

    def _build_short_report_sentences(
        self,
        *,
        risk_engine_result: RiskEngineResult,
        key_triggers: tuple[str, ...],
        regime_summary: str,
        owner_action: str,
    ) -> tuple[str, ...]:
        sentences = [
            f"Execution remains {EXECUTION_STATUS}.",
            regime_summary,
            f"Current risk action is {risk_engine_result.risk_action.value}.",
            owner_action,
        ]

        if key_triggers:
            for trigger_label in key_triggers[:4]:
                sentences.append(trigger_label)
        else:
            sentences.append("No confirmed trigger is forcing a stronger posture right now.")

        if risk_engine_result.kill_switch_active:
            sentences.append("This is a stop condition, not a watch condition.")
        else:
            sentences.append("The system stays deterministic and waits for validated follow-through.")

        if len(sentences) < 5:
            sentences.append("No live execution path is opened by this report.")

        return tuple(sentences[:10])

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
