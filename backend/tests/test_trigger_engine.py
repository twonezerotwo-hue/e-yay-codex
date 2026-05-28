from datetime import UTC, datetime
from datetime import timedelta

from app.domain import AssetCode
from app.domain import MarketSnapshot
from app.domain import get_asset_definition
from app.services.trigger_engine import TriggerConfirmationStatus
from app.services.trigger_engine import TriggerEngine
from app.services.trigger_engine import TriggerSeverity


def build_snapshot(asset_symbol: AssetCode | str, value: float) -> MarketSnapshot:
    asset_definition = get_asset_definition(asset_symbol)
    observed_at = datetime(2026, 5, 19, 10, 0, 0, tzinfo=UTC)
    available_at = observed_at + timedelta(minutes=1)
    stored_at = available_at + timedelta(minutes=1)

    return MarketSnapshot(
        asset_symbol=asset_definition.code,
        value=value,
        unit=asset_definition.unit,
        source_name="deterministic_test_provider",
        source_tier="primary",
        observed_at=observed_at,
        available_at=available_at,
        stored_at=stored_at,
        data_quality_score=100.0,
    )


def get_trigger(results: tuple, trigger_code: str):
    return next(result for result in results if result.trigger_code == trigger_code)


def test_brent_above_120_emits_red_energy_shock() -> None:
    results = TriggerEngine().evaluate([build_snapshot(AssetCode.BRENT, 121.0)])

    trigger = get_trigger(results, "RED_ENERGY_SHOCK")
    assert trigger.is_triggered is True
    assert trigger.severity == TriggerSeverity.RED
    assert trigger.confirmation_status == TriggerConfirmationStatus.CONFIRMED
    assert trigger.asset_symbol == "BRENT"


def test_btc_below_75k_emits_risk_off_warning() -> None:
    results = TriggerEngine().evaluate([build_snapshot(AssetCode.BTCUSD, 74000.0)])

    trigger = get_trigger(results, "BTC_RISK_OFF_WARNING")
    assert trigger.is_triggered is True
    assert trigger.severity == TriggerSeverity.ORANGE
    assert trigger.confirmation_status == TriggerConfirmationStatus.CONFIRMED


def test_gold_breakout_trigger_works() -> None:
    results = TriggerEngine().evaluate([build_snapshot(AssetCode.XAUUSD, 4661.0)])

    trigger = get_trigger(results, "GOLD_HEDGE_BREAKOUT")
    assert trigger.is_triggered is True
    assert trigger.asset_symbol == "XAUUSD"


def test_silver_thresholds_are_evaluated_deterministically() -> None:
    strategic_results = TriggerEngine().evaluate([build_snapshot(AssetCode.XAGUSD, 66.0)])
    momentum_results = TriggerEngine().evaluate([build_snapshot(AssetCode.XAGUSD, 91.0)])
    exhaustion_results = TriggerEngine().evaluate([build_snapshot(AssetCode.XAGUSD, 97.0)])

    assert get_trigger(strategic_results, "SILVER_STRATEGIC_METALS_REGIME").is_triggered is True
    assert get_trigger(strategic_results, "SILVER_MOMENTUM_ACCELERATION").is_triggered is False
    assert get_trigger(strategic_results, "SILVER_EXHAUSTION_WATCH").is_triggered is False

    assert get_trigger(momentum_results, "SILVER_STRATEGIC_METALS_REGIME").is_triggered is True
    assert get_trigger(momentum_results, "SILVER_MOMENTUM_ACCELERATION").is_triggered is True
    assert get_trigger(momentum_results, "SILVER_EXHAUSTION_WATCH").is_triggered is False

    assert get_trigger(exhaustion_results, "SILVER_STRATEGIC_METALS_REGIME").is_triggered is True
    assert get_trigger(exhaustion_results, "SILVER_MOMENTUM_ACCELERATION").is_triggered is True
    assert get_trigger(exhaustion_results, "SILVER_EXHAUSTION_WATCH").is_triggered is True


def test_placeholder_triggers_return_safe_inactive_state() -> None:
    results = TriggerEngine().evaluate(
        [
            build_snapshot(AssetCode.BTCUSD, 81000.0),
            build_snapshot(AssetCode.HYG, 77.4),
            build_snapshot(AssetCode.JNK, 95.1),
        ]
    )

    btc_candidate = get_trigger(results, "BTC_RISK_ON_CANDIDATE")
    hyg_jnk_placeholder = get_trigger(results, "HYG_JNK_BREAKDOWN_WATCH")

    assert btc_candidate.is_triggered is False
    assert btc_candidate.confirmation_status == TriggerConfirmationStatus.PLACEHOLDER
    assert "placeholder" in btc_candidate.message.lower()

    assert hyg_jnk_placeholder.is_triggered is False
    assert hyg_jnk_placeholder.severity == TriggerSeverity.INFO
    assert hyg_jnk_placeholder.confirmation_status == TriggerConfirmationStatus.PLACEHOLDER


def test_non_trigger_conditions_remain_false() -> None:
    results = TriggerEngine().evaluate(
        [
            build_snapshot(AssetCode.BRENT, 100.0),
            build_snapshot(AssetCode.BTCUSD, 78000.0),
            build_snapshot(AssetCode.XAUUSD, 4500.0),
            build_snapshot(AssetCode.XAGUSD, 40.0),
        ]
    )

    assert get_trigger(results, "RED_ENERGY_SHOCK").is_triggered is False
    assert get_trigger(results, "BTC_RISK_OFF_WARNING").is_triggered is False
    assert get_trigger(results, "GOLD_HEDGE_BREAKOUT").is_triggered is False
    assert get_trigger(results, "SILVER_STRATEGIC_METALS_REGIME").is_triggered is False

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
