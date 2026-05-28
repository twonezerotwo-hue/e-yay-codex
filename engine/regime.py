from __future__ import annotations

from collections.abc import Mapping


def determine_regime(
    score: float,
    previous_regime: str | None,
    thresholds: Mapping[str, float],
) -> str:
    current_regime = (previous_regime or "neutral").lower()
    bull_enter = float(thresholds["bull_enter"])
    bull_exit = float(thresholds["bull_exit"])
    bear_enter = float(thresholds["bear_enter"])
    bear_exit = float(thresholds["bear_exit"])

    if current_regime == "bull":
        if score >= bull_exit:
            return "bull"
        if score <= bear_enter:
            return "bear"
        return "neutral"

    if current_regime == "bear":
        if score <= bear_exit:
            return "bear"
        if score >= bull_enter:
            return "bull"
        return "neutral"

    if score >= bull_enter:
        return "bull"
    if score <= bear_enter:
        return "bear"
    return "neutral"
