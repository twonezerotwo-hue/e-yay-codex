"""
Agent Insight × Paper Decision sentezi — testler.

Burada doğrulanan: paper_decision payload'ı agent'a verildiğinde, kullanıcıya
gösterilebilir disiplinli insight'lar üretir, ham bloklar sızdırılmaz.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from app.services.agent_insight_service import (
    AgentInsight,
    derive_paper_decision_label_safely,
    synthesize_paper_decision_insights,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _payload(
    *,
    label="POZİSYON YOK · NÖTR İZLEME",
    risk_action="HOLD",
    kill_switch=False,
    dqs_decision="PASS",
    dqs_perm="ALLOWED",
    dqs=85,
    has_open=False,
    setup_valid=False,
    would_pair=None,
    would_dir=None,
    consensus=None,
    why_no_trade=None,
    confirmed=None,
    severity="INFO",
    prediction_id="pred_test",
) -> dict:
    return {
        "decision_label":         label,
        "risk_engine_verdict":    {
            "risk_action":        risk_action,
            "kill_switch_active": kill_switch,
        },
        "data_quality_status":    {
            "dqs_decision":        dqs_decision,
            "decision_permission": dqs_perm,
            "overall_dqs":         dqs,
        },
        "paper_trading_decision": {
            "has_open_positions":   has_open,
            "setup_validity":       setup_valid,
            "would_trade_asset":    would_pair,
            "would_trade_direction": would_dir,
            "best_consensus_score": consensus,
            "why_no_trade":         why_no_trade or [],
        },
        "trigger_engine_output":  {
            "confirmed_triggers": confirmed or [],
            "trigger_severity":   severity,
        },
        "learning_layer":         {"prediction_id": prediction_id},
    }


def _severities(insights: list[AgentInsight]) -> list[str]:
    return [i.severity for i in insights]


# ── 1. KILL_SWITCH en üst sırada CRITICAL üretir ────────────────────────────

def test_kill_switch_emits_critical():
    out = synthesize_paper_decision_insights(_payload(
        label="İŞLEM YOK / SİSTEM DURDU",
        risk_action="KILL_SWITCH",
        kill_switch=True,
    ))
    assert any(i.severity == "CRITICAL" and "KILL_SWITCH" in i.headline for i in out)


# ── 2. DQS FAIL → CRITICAL ──────────────────────────────────────────────────

def test_dqs_fail_emits_critical():
    out = synthesize_paper_decision_insights(_payload(
        dqs_decision="FAIL_NO_DECISION",
        dqs_perm="BLOCKED",
        dqs=42,
    ))
    crits = [i for i in out if i.severity == "CRITICAL"]
    assert crits, "DQS FAIL CRITICAL üretmeli"
    assert any("veri kalitesi" in c.headline.lower() for c in crits)


# ── 3. RISK_REDUCE + flat → 'KÜÇÜLT' DEMEZ, yeni risk açmıyorum der ─────────

def test_risk_reduce_without_positions_does_not_say_kucult():
    out = synthesize_paper_decision_insights(_payload(
        label="YENİ RİSK AÇMA / BEKLE",
        risk_action="RISK_REDUCE",
        has_open=False,
    ))
    # Hiçbir insight 'küçült' (case-insensitive) talimatı içermemeli
    for i in out:
        text = f"{i.headline} {i.detail}".lower()
        # "küçültme" sözcüğü olabilir ama imperatif "küçült" emri olmamalı
        # daha açık: "açık pozisyonları küçült" insight'ı flat'te emit edilmemeli
        if "açık pozisyonları küçült" in text:
            assert False, "Flat iken 'KÜÇÜLT' insight'ı verilmemeli"
    # Yeni risk açma uyarısı verilmeli
    assert any("yeni risk" in i.headline.lower() for i in out)


# ── 4. RISK_REDUCE + açık pozisyon → 'küçültme' WARNING ─────────────────────

def test_risk_reduce_with_positions_emits_kucult_warning():
    out = synthesize_paper_decision_insights(_payload(
        label="KÜÇÜLT",
        risk_action="RISK_REDUCE",
        has_open=True,
    ))
    assert any(
        i.severity == "WARNING"
        and "küçült" in (i.headline + i.detail).lower()
        for i in out
    )


# ── 5. NO_POSITION_INCREASE → WARNING ───────────────────────────────────────

def test_no_position_increase_warning():
    out = synthesize_paper_decision_insights(_payload(
        risk_action="NO_POSITION_INCREASE",
    ))
    assert any(
        i.severity == "WARNING" and "pozisyon artırma" in i.headline.lower()
        for i in out
    )


# ── 6. Setup valid + flat → OPPORTUNITY ─────────────────────────────────────

def test_setup_valid_flat_emits_opportunity():
    out = synthesize_paper_decision_insights(_payload(
        risk_action="HOLD",
        has_open=False,
        setup_valid=True,
        would_pair="BTCUSD",
        would_dir="LONG",
        consensus=74.5,
    ))
    opps = [i for i in out if i.severity == "OPPORTUNITY"]
    assert opps, "Setup hazırsa OPPORTUNITY üretilmeli"
    assert "BTCUSD" in opps[0].headline
    assert "LONG" in opps[0].headline


# ── 7. why_no_trade → OBSERVATION ile şeffaf bekleyiş sebebi ────────────────

def test_why_no_trade_observation():
    out = synthesize_paper_decision_insights(_payload(
        why_no_trade=["no_directional_consensus"],
    ))
    obs = [i for i in out if i.severity == "OBSERVATION"]
    assert obs, "why_no_trade dolu → OBSERVATION beklenir"
    # Türkçe çevrilmiş olmalı
    assert any("Yönlü konsensus" in i.detail for i in obs)


# ── 8. Confirmed çoklu trigger → WARNING ───────────────────────────────────

def test_multiple_confirmed_triggers_warning():
    out = synthesize_paper_decision_insights(_payload(
        severity="ORANGE",
        confirmed=[
            {"trigger_code": "RED_ENERGY_SHOCK", "asset": "BRENT"},
            {"trigger_code": "BTC_RISK_OFF_WARNING", "asset": "BTCUSD"},
        ],
    ))
    assert any(
        i.severity == "WARNING" and "tetikleyici" in i.headline.lower()
        for i in out
    )


# ── 9. Learning layer prediction_id log'lanıyor ─────────────────────────────

def test_prediction_id_logged_as_observation():
    out = synthesize_paper_decision_insights(_payload(
        prediction_id="pred_20260607_abc",
    ))
    assert any("pred_20260607_abc" in i.detail for i in out)


# ── 10. derive_paper_decision_label_safely defensive ───────────────────────

def test_label_helper_handles_missing_field():
    assert derive_paper_decision_label_safely({}) == ""
    assert derive_paper_decision_label_safely({"decision_label": "KORU"}) == "KORU"
    assert derive_paper_decision_label_safely(None) == ""  # type: ignore[arg-type]


# ── 11. Boş / bozuk input → boş liste ──────────────────────────────────────

def test_invalid_payload_returns_empty():
    assert synthesize_paper_decision_insights(None) == []        # type: ignore[arg-type]
    assert synthesize_paper_decision_insights("string") == []    # type: ignore[arg-type]
    assert synthesize_paper_decision_insights([]) == []          # type: ignore[arg-type]


# ── 12. Hiçbir insight ham veri (DQS sayı, reason kod) sızdırmamalı ────────

def test_no_raw_block_leakage():
    """Ham blok adları (reason_codes, hardeners, softeners, trigger_code listesi)
    insight metinlerinde geçmemeli — agent SADECE sentezlenmiş cümle üretmeli."""
    out = synthesize_paper_decision_insights(_payload(
        risk_action="RISK_REDUCE",
        has_open=True,
        confirmed=[
            {"trigger_code": "MULTI_SEVERE_TRIGGER_STACK", "asset": "MULTI"},
        ],
        severity="RED",
    ))
    forbidden_tokens = (
        "reason_codes", "risk_hardeners", "risk_softeners",
        "MULTI_SEVERE_TRIGGER_STACK", "decision_permission",
    )
    for i in out:
        text = i.headline + " " + i.detail
        for tok in forbidden_tokens:
            assert tok not in text, f"Ham token '{tok}' insight'a sızmış: {text}"
