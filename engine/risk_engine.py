from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def evaluate_risk(
    *,
    data_quality_score: float,
    critical_missing_data: bool,
    verified_data_available: bool,
    thresholds: Mapping[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    action = str(thresholds["default_action"])

    if data_quality_score < float(thresholds["no_trade_data_quality_score"]):
        action = str(thresholds["no_trade_action"])
        reasons.append("data_quality_below_threshold")
    elif critical_missing_data and bool(thresholds["no_position_increase_on_critical_missing_data"]):
        action = str(thresholds["no_position_increase_action"])
        reasons.append("critical_missing_data")
    elif not verified_data_available and bool(thresholds["simulation_only_when_verified_data_unavailable"]):
        action = str(thresholds["simulation_only_action"])
        reasons.append("verified_data_unavailable")

    return {
        "final_gate": "risk_engine",
        "action": action,
        "execution_mode": str(thresholds["execution_mode"]),
        "auto_full_enabled": bool(thresholds["auto_full_enabled"]),
        "reasons": reasons,
    }
