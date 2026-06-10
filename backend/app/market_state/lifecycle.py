"""Paper trading lifecycle classifier.

Mevcut paper_trading_service davranışını DEĞİŞTİRMEZ; var olan sinyalleri
(risk_action, block_reason, aggression_context, add plan) okuyup standart
lifecycle etiketine çevirir. Yeni trade açma davranışı eklemez.

Enum:
  SCOUT_ENTRY        — manual_ready + düşük risk + erken setup
  CONFIRMATION_ENTRY — normal confirmed trade
  MOMENTUM_ADD       — kârdaki pozisyona kontrollü ekleme (add plan)
  RISK_REDUCE        — risk_action=RISK_REDUCE
  KILL_SWITCH_EXIT   — risk_action=KILL_SWITCH
  TIME_STOP_EXIT     — max_holding_time aşıldı
  REGIME_FLIP_EXIT   — rejim kararı tersine döndü
  WATCH_ONLY         — block_reason var, sinyal izleniyor
  NO_TRADE           — hiçbir sinyal yok
"""
from __future__ import annotations

from typing import Any

LIFECYCLE_CODES = (
    "SCOUT_ENTRY",
    "CONFIRMATION_ENTRY",
    "MOMENTUM_ADD",
    "RISK_REDUCE",
    "KILL_SWITCH_EXIT",
    "TIME_STOP_EXIT",
    "REGIME_FLIP_EXIT",
    "WATCH_ONLY",
    "NO_TRADE",
)


def _g(d: Any, key: str, default: Any = None) -> Any:
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)


def classify_position_lifecycle(
    position: Any,
    *,
    risk_action: str | None = None,
    add_plan_active: bool = False,
    regime_flipped: bool = False,
    time_stop_hit: bool = False,
) -> str:
    """Açık bir pozisyon için lifecycle etiketi üretir."""
    if (risk_action or "").upper() == "KILL_SWITCH":
        return "KILL_SWITCH_EXIT"
    if time_stop_hit:
        return "TIME_STOP_EXIT"
    if regime_flipped:
        return "REGIME_FLIP_EXIT"
    if (risk_action or "").upper() == "RISK_REDUCE":
        return "RISK_REDUCE"
    if add_plan_active:
        return "MOMENTUM_ADD"

    # Aggression seviyesi düşükse scout, aksi halde confirmation
    aggression = _g(position, "aggression_level") or _g(_g(position, "aggression_context"), "level")
    if isinstance(aggression, str) and aggression.lower() in ("low", "scout", "tactical"):
        return "SCOUT_ENTRY"
    return "CONFIRMATION_ENTRY"


def classify_candidate_lifecycle(
    *,
    risk_action: str | None,
    block_reason: str | None,
    should_trade: bool,
    aggression_level: str | None = None,
    manual_required: bool = False,
) -> str:
    """Henüz açık olmayan bir aday için lifecycle etiketi.

    paper_trading_service'in pending / manual_ready / candidate sinyalleri için.
    """
    if (risk_action or "").upper() == "KILL_SWITCH":
        return "KILL_SWITCH_EXIT"
    if (risk_action or "").upper() == "RISK_REDUCE":
        return "RISK_REDUCE"
    if block_reason:
        return "WATCH_ONLY"
    if not should_trade:
        return "NO_TRADE"

    if manual_required or (aggression_level or "").lower() in ("low", "scout", "tactical"):
        return "SCOUT_ENTRY"
    return "CONFIRMATION_ENTRY"
