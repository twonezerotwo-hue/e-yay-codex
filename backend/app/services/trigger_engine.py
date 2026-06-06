from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain import AssetCode
from app.domain import MarketSnapshot


class TriggerSeverity(str, Enum):
    INFO = "INFO"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class TriggerConfirmationStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    PLACEHOLDER = "PLACEHOLDER"


@dataclass(frozen=True)
class TriggerResult:
    trigger_code: str
    severity: TriggerSeverity
    asset_symbol: str
    is_triggered: bool
    confirmation_status: TriggerConfirmationStatus
    message: str


@dataclass(frozen=True)
class TriggerRule:
    trigger_code: str
    asset_symbol: AssetCode
    severity: TriggerSeverity
    threshold: float
    trigger_message: str


class TriggerEngine:
    def evaluate(self, snapshots: list[MarketSnapshot] | tuple[MarketSnapshot, ...]) -> tuple[TriggerResult, ...]:
        indexed_snapshots = {snapshot.asset_symbol: snapshot for snapshot in snapshots}

        return (
            self._evaluate_threshold_rule(
                rule=TriggerRule(
                    trigger_code="RED_ENERGY_SHOCK",
                    asset_symbol=AssetCode.BRENT,
                    severity=TriggerSeverity.RED,
                    threshold=120.0,
                    trigger_message="Brent is above the energy shock threshold.",
                ),
                snapshots=indexed_snapshots,
            ),
            self._evaluate_threshold_rule(
                rule=TriggerRule(
                    trigger_code="BTC_RISK_OFF_WARNING",
                    asset_symbol=AssetCode.BTCUSD,
                    severity=TriggerSeverity.ORANGE,
                    threshold=75000.0,
                    trigger_message="BTCUSD is below the risk-off warning threshold.",
                ),
                snapshots=indexed_snapshots,
                greater_than=False,
            ),
            self._evaluate_btc_risk_on_candidate(indexed_snapshots),
            self._evaluate_threshold_rule(
                rule=TriggerRule(
                    trigger_code="GOLD_HEDGE_BREAKOUT",
                    asset_symbol=AssetCode.XAUUSD,
                    severity=TriggerSeverity.YELLOW,
                    threshold=4660.0,
                    trigger_message="Gold is above the hedge breakout threshold.",
                ),
                snapshots=indexed_snapshots,
            ),
            self._evaluate_threshold_rule(
                rule=TriggerRule(
                    trigger_code="SILVER_STRATEGIC_METALS_REGIME",
                    asset_symbol=AssetCode.XAGUSD,
                    severity=TriggerSeverity.YELLOW,
                    threshold=65.0,
                    trigger_message="Silver is above the strategic metals regime threshold.",
                ),
                snapshots=indexed_snapshots,
            ),
            self._evaluate_threshold_rule(
                rule=TriggerRule(
                    trigger_code="SILVER_MOMENTUM_ACCELERATION",
                    asset_symbol=AssetCode.XAGUSD,
                    severity=TriggerSeverity.ORANGE,
                    threshold=90.0,
                    trigger_message="Silver is above the momentum acceleration threshold.",
                ),
                snapshots=indexed_snapshots,
            ),
            self._evaluate_threshold_rule(
                rule=TriggerRule(
                    trigger_code="SILVER_EXHAUSTION_WATCH",
                    asset_symbol=AssetCode.XAGUSD,
                    severity=TriggerSeverity.RED,
                    threshold=96.0,
                    trigger_message="Silver is above the exhaustion watch threshold.",
                ),
                snapshots=indexed_snapshots,
            ),
            self._evaluate_hyg_jnk_breakdown_placeholder(indexed_snapshots),
        )

    def _evaluate_threshold_rule(
        self,
        *,
        rule: TriggerRule,
        snapshots: dict[AssetCode, MarketSnapshot],
        greater_than: bool = True,
    ) -> TriggerResult:
        snapshot = snapshots.get(rule.asset_symbol)
        if snapshot is None:
            return TriggerResult(
                trigger_code=rule.trigger_code,
                severity=rule.severity,
                asset_symbol=rule.asset_symbol.value,
                is_triggered=False,
                confirmation_status=TriggerConfirmationStatus.NOT_CONFIRMED,
                message=f"{rule.asset_symbol.value} snapshot is missing; trigger cannot be evaluated.",
            )

        is_triggered = snapshot.value > rule.threshold if greater_than else snapshot.value < rule.threshold
        operator = ">" if greater_than else "<"
        message = rule.trigger_message
        if not is_triggered:
            message = (
                f"{rule.asset_symbol.value} does not meet the threshold condition "
                f"({snapshot.value:.2f} {operator} {rule.threshold:.2f})."
            )

        return TriggerResult(
            trigger_code=rule.trigger_code,
            severity=rule.severity,
            asset_symbol=rule.asset_symbol.value,
            is_triggered=is_triggered,
            confirmation_status=TriggerConfirmationStatus.CONFIRMED,
            message=message,
        )

    def _evaluate_btc_risk_on_candidate(self, snapshots: dict[AssetCode, MarketSnapshot]) -> TriggerResult:
        snapshot = snapshots.get(AssetCode.BTCUSD)
        if snapshot is None:
            return TriggerResult(
                trigger_code="BTC_RISK_ON_CANDIDATE",
                severity=TriggerSeverity.YELLOW,
                asset_symbol=AssetCode.BTCUSD.value,
                is_triggered=False,
                confirmation_status=TriggerConfirmationStatus.NOT_CONFIRMED,
                message="BTCUSD snapshot is missing; recovery confirmation cannot be evaluated.",
            )

        if snapshot.value <= 80000.0:
            return TriggerResult(
                trigger_code="BTC_RISK_ON_CANDIDATE",
                severity=TriggerSeverity.YELLOW,
                asset_symbol=AssetCode.BTCUSD.value,
                is_triggered=False,
                confirmation_status=TriggerConfirmationStatus.PLACEHOLDER,
                message=(
                    "BTCUSD has not crossed the candidate threshold and HYG/JNK recovery "
                    "confirmation remains unavailable."
                ),
            )

        return TriggerResult(
            trigger_code="BTC_RISK_ON_CANDIDATE",
            severity=TriggerSeverity.YELLOW,
            asset_symbol=AssetCode.BTCUSD.value,
            is_triggered=False,
            confirmation_status=TriggerConfirmationStatus.PLACEHOLDER,
            message=(
                "BTCUSD is above 80000, but HYG/JNK recovery confirmation is still a "
                "placeholder and does not activate the trigger."
            ),
        )

    def _evaluate_hyg_jnk_breakdown_placeholder(
        self,
        snapshots: dict[AssetCode, MarketSnapshot],
    ) -> TriggerResult:
        if AssetCode.HYG not in snapshots or AssetCode.JNK not in snapshots:
            return TriggerResult(
                trigger_code="HYG_JNK_BREAKDOWN_WATCH",
                severity=TriggerSeverity.INFO,
                asset_symbol=AssetCode.HYG.value,
                is_triggered=False,
                confirmation_status=TriggerConfirmationStatus.NOT_CONFIRMED,
                message="HYG/JNK snapshots are incomplete; breakdown placeholder cannot be evaluated.",
            )

        return TriggerResult(
            trigger_code="HYG_JNK_BREAKDOWN_WATCH",
            severity=TriggerSeverity.INFO,
            asset_symbol=AssetCode.HYG.value,
            is_triggered=False,
            confirmation_status=TriggerConfirmationStatus.PLACEHOLDER,
            message="HYG/JNK breakdown logic is reserved for a future delta-based signal and remains inactive.",
        )

__all__ = [name for name in globals() if not name.startswith('_')]
