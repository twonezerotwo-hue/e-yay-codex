"""RiskGate / AgentVote / PositionCheck ViewModels.

Mevcut risk motoru (agent_decision_aggregator, position_management_service)
çıktılarını standart, panel-friendly görünüme çevirir. Motoru YENİDEN YAZMAZ;
sadece okur ve mapler. Kill switch, DQS veto, RR check, contradiction gate,
stop-proximity gate gibi kurallar olduğu gibi korunur.

Sözleşmeler:
  RiskGateViewModel.status:  PASS | CAUTION | BLOCK
  AgentVoteViewModel.vote:   ALLOW | CAUTION | BLOCK | ABSTAIN
  PositionCheckViewModel.severity: INFO | WARNING | BLOCKER
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# ── ViewModels ───────────────────────────────────────────────────────────────


@dataclass
class RiskGateViewModel:
    """Karar verme öncesi son güvenlik kapısı — agregat sonuç."""
    status:               str                = "PASS"      # PASS | CAUTION | BLOCK
    source_risk_action:   str                = "HOLD"      # HOLD | KILL_SWITCH | RISK_REDUCE | NO_POSITION_INCREASE
    reason:               str                = ""
    hard_blockers:        list[str]          = field(default_factory=list)
    soft_warnings:        list[str]          = field(default_factory=list)
    dqs_score:            float | None       = None
    dqs_passed:           bool | None        = None
    kill_switch_active:   bool               = False
    no_position_increase: bool               = False
    risk_reduce:          bool               = False
    evidence:             list[dict]         = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentVoteViewModel:
    """Bir agent'ın o anki kararı — standart oy formatı."""
    agent_name:   str
    vote:         str                # ALLOW | CAUTION | BLOCK | ABSTAIN
    confidence:   float | None  = None
    direction:    str | None    = None
    reason:       str           = ""
    evidence:     list[dict]    = field(default_factory=list)
    invalidation: str | None    = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PositionCheckViewModel:
    """Tek bir pozisyon yönetimi kontrolü (size/RR/stop/DQS/...)."""
    check_name: str
    passed:     bool
    severity:   str                       # INFO | WARNING | BLOCKER
    reason:     str             = ""
    value:      float | str | None = None
    threshold:  float | str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Risk gate mapping ────────────────────────────────────────────────────────

_RISK_ACTION_TO_STATUS: dict[str, str] = {
    "KILL_SWITCH":          "BLOCK",
    "RISK_REDUCE":          "CAUTION",
    "NO_POSITION_INCREASE": "CAUTION",
    "HOLD":                 "PASS",
}


def _safe_get(d: Any, key: str, default: Any = None) -> Any:
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)


def build_risk_gate(
    *,
    risk_action: str | None,
    dqs_score: float | None = None,
    kill_switch: bool = False,
    block_reason: str | None = None,
    contradiction_score: float | None = None,
    extra_warnings: Iterable[str] | None = None,
    regime: str | None = None,
) -> RiskGateViewModel:
    """Mevcut risk_action çıktısından RiskGate görünümü üretir.

    `risk_action` agent_decision_aggregator._get_risk_action() çıktısıdır
    ({HOLD, KILL_SWITCH, RISK_REDUCE, NO_POSITION_INCREASE}). Mevcut anlamı
    KORUNUR; sadece panel için PASS/CAUTION/BLOCK üç-değerli skalaya çevrilir.
    """
    src = (risk_action or "HOLD").upper()
    status = _RISK_ACTION_TO_STATUS.get(src, "PASS")

    hard: list[str] = []
    soft: list[str] = list(extra_warnings or [])
    evidence: list[dict] = []

    kill_active = bool(kill_switch) or src == "KILL_SWITCH"
    if kill_active:
        hard.append("Kill switch aktif")
        evidence.append({"type": "kill_switch", "active": True})

    # DQS veto — mevcut _evaluate_add_risk eşiği (55) ve aggregator MIN_DQS uyumlu
    dqs_passed: bool | None = None
    if dqs_score is not None:
        try:
            dqs_passed = float(dqs_score) >= 55.0
        except (TypeError, ValueError):
            dqs_passed = None
        if dqs_passed is False:
            hard.append(f"DQS düşük ({dqs_score:.0f} < 55)")
            evidence.append({"type": "dqs", "score": dqs_score, "threshold": 55})
            status = "BLOCK"

    if contradiction_score is not None:
        try:
            cs = float(contradiction_score)
        except (TypeError, ValueError):
            cs = None
        if cs is not None and cs >= 80:
            hard.append(f"Çelişki yüksek ({cs:.0f})")
            evidence.append({"type": "contradiction", "score": cs, "threshold": 80})
            if status != "BLOCK":
                status = "CAUTION"

    if block_reason:
        hard.append(block_reason)
        evidence.append({"type": "block_reason", "text": block_reason})
        # Mevcut block_reason zaten "trade yok" anlamına geliyor → BLOCK üst sınır
        if src not in ("KILL_SWITCH",):
            # KILL_SWITCH zaten BLOCK; başka durumda block_reason varsa CAUTION'a çıkar
            if status == "PASS":
                status = "CAUTION"

    if regime:
        evidence.append({"type": "regime", "value": str(regime).upper()})

    no_pos_inc = src == "NO_POSITION_INCREASE"
    risk_red   = src == "RISK_REDUCE"

    # Açıklayıcı tek-cümle reason
    if hard:
        reason = "; ".join(hard)
    elif soft:
        reason = "Uyarı: " + "; ".join(soft)
    else:
        reason = "Hard blocker yok; mevcut risk kuralları sağlandı."

    return RiskGateViewModel(
        status=status,
        source_risk_action=src,
        reason=reason,
        hard_blockers=hard,
        soft_warnings=soft,
        dqs_score=float(dqs_score) if dqs_score is not None else None,
        dqs_passed=dqs_passed,
        kill_switch_active=kill_active,
        no_position_increase=no_pos_inc,
        risk_reduce=risk_red,
        evidence=evidence,
    )


# ── Agent votes ──────────────────────────────────────────────────────────────


def _direction_from_side(side: str | None) -> str | None:
    if not side:
        return None
    s = str(side).upper()
    if s == "LONG":
        return "LONG_BIAS"
    if s == "SHORT":
        return "SHORT_BIAS"
    return None


def build_agent_votes(
    *,
    risk_action: str | None,
    kill_switch: bool = False,
    dqs_score: float | None = None,
    tf_alignment_label: str | None = None,
    tf_alignment_detail: str | None = None,
    contradiction_score: float | None = None,
    block_reason: str | None = None,
    side: str | None = None,
    confidence: float | None = None,
    regime: str | None = None,
) -> list[AgentVoteViewModel]:
    """Mevcut motor çıktısını standart agent-vote listesine map'le.

    Sıfırdan vote üretmez; sadece var olan sinyalleri yeniden paketler.
    """
    votes: list[AgentVoteViewModel] = []
    src = (risk_action or "HOLD").upper()

    # RiskAgent — kill switch + risk_action
    if kill_switch or src == "KILL_SWITCH":
        votes.append(AgentVoteViewModel(
            agent_name="RiskAgent",
            vote="BLOCK",
            reason=block_reason or "Kill switch / kritik risk aktif",
            evidence=[{"risk_action": src, "kill_switch": True}],
        ))
    elif src == "RISK_REDUCE":
        votes.append(AgentVoteViewModel(
            agent_name="RiskAgent",
            vote="CAUTION",
            reason="Rejim kriz/defansif — pozisyon azalt",
            evidence=[{"risk_action": src, "regime": regime}],
        ))
    elif src == "NO_POSITION_INCREASE":
        votes.append(AgentVoteViewModel(
            agent_name="RiskAgent",
            vote="CAUTION",
            reason="Yeni pozisyon açma — sadece mevcut yönet",
            evidence=[{"risk_action": src, "regime": regime}],
        ))
    else:
        votes.append(AgentVoteViewModel(
            agent_name="RiskAgent",
            vote="ALLOW",
            reason="Risk kısıtı yok",
            evidence=[{"risk_action": src}],
        ))

    # DataQualityAgent
    if dqs_score is not None:
        try:
            dq = float(dqs_score)
        except (TypeError, ValueError):
            dq = None
        if dq is None:
            votes.append(AgentVoteViewModel(
                agent_name="DataQualityAgent", vote="ABSTAIN",
                reason="DQS hesaplanamadı",
            ))
        elif dq < 55:
            votes.append(AgentVoteViewModel(
                agent_name="DataQualityAgent", vote="BLOCK",
                confidence=dq,
                reason=f"DQS={dq:.0f} (eşik 55)",
                evidence=[{"score": dq, "threshold": 55}],
            ))
        elif dq < 70:
            votes.append(AgentVoteViewModel(
                agent_name="DataQualityAgent", vote="CAUTION",
                confidence=dq, reason=f"DQS={dq:.0f} — düşük",
            ))
        else:
            votes.append(AgentVoteViewModel(
                agent_name="DataQualityAgent", vote="ALLOW",
                confidence=dq, reason=f"DQS={dq:.0f} — yeterli",
            ))
    else:
        votes.append(AgentVoteViewModel(
            agent_name="DataQualityAgent", vote="ABSTAIN",
            reason="DQS skoru sağlanmadı",
        ))

    # TechnicalAgent — TF alignment
    if tf_alignment_label:
        lbl = tf_alignment_label.lower()
        direction = _direction_from_side(side)
        if lbl == "divergent":
            votes.append(AgentVoteViewModel(
                agent_name="TechnicalAgent", vote="BLOCK",
                direction=direction,
                reason=tf_alignment_detail or "TF karşıt",
                evidence=[{"tf_alignment": lbl}],
            ))
        elif lbl == "none":
            votes.append(AgentVoteViewModel(
                agent_name="TechnicalAgent", vote="ABSTAIN",
                direction=direction,
                reason=tf_alignment_detail or "TF verisi yok",
            ))
        elif lbl == "weak":
            votes.append(AgentVoteViewModel(
                agent_name="TechnicalAgent", vote="CAUTION",
                direction=direction,
                reason=tf_alignment_detail or "TF zayıf",
            ))
        else:  # strong / moderate
            votes.append(AgentVoteViewModel(
                agent_name="TechnicalAgent", vote="ALLOW",
                direction=direction, confidence=confidence,
                reason=tf_alignment_detail or f"TF {lbl}",
            ))

    # ContradictionAgent — sadece yüksek çelişki uyarısı
    if contradiction_score is not None:
        try:
            cs = float(contradiction_score)
        except (TypeError, ValueError):
            cs = None
        if cs is not None and cs >= 80:
            votes.append(AgentVoteViewModel(
                agent_name="ContradictionAgent", vote="BLOCK",
                reason=f"Çelişki yüksek ({cs:.0f} ≥ 80)",
                evidence=[{"score": cs, "threshold": 80}],
            ))
        elif cs is not None and cs >= 50:
            votes.append(AgentVoteViewModel(
                agent_name="ContradictionAgent", vote="CAUTION",
                reason=f"Çelişki orta ({cs:.0f})",
            ))

    return votes


# ── Position checks ─────────────────────────────────────────────────────────

# position_management_service _evaluate_add_risk içindeki hard_fail_keys ile uyumlu
_HARD_FAIL_CHECKS = frozenset({
    "max_position_size_passed", "kill_switch_off", "dqs_passed",
    "not_too_close_to_stop",  "average_entry_valid", "rr_after_add_valid",
    "contradiction_acceptable", "paper_mode_allowed",
})

_CHECK_REASONS_TR: dict[str, str] = {
    "max_position_size_passed": "Maks pozisyon sınırı",
    "kill_switch_off":          "Kill switch kapalı",
    "dqs_passed":               "DQS yeterli",
    "stop_distance_safe":       "Stop'a güvenli mesafe",
    "not_too_close_to_stop":    "Stop'a çok yakın değil",
    "average_entry_valid":      "Ortalama entry geçerli",
    "rr_after_add_valid":       "Ekleme sonrası R/R yeterli",
    "contradiction_acceptable": "Çelişki kabul edilebilir",
    "paper_mode_allowed":       "Paper mode bu ekleme için açık",
}


def build_position_checks(checks: dict[str, bool] | None) -> list[PositionCheckViewModel]:
    """position_management_service `checks` dict'ini ViewModel listesine çevir."""
    if not checks:
        return []
    out: list[PositionCheckViewModel] = []
    for name, passed in checks.items():
        severity = "BLOCKER" if (name in _HARD_FAIL_CHECKS and not passed) else (
            "WARNING" if not passed else "INFO"
        )
        out.append(PositionCheckViewModel(
            check_name=name,
            passed=bool(passed),
            severity=severity,
            reason=_CHECK_REASONS_TR.get(name, name),
        ))
    return out
