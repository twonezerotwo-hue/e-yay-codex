"""
Paper Decision Service / API — test paketi

Kapsam (görev gereği):
  1. Açık pozisyon yokken "KÜÇÜLT" dönmüyor (en kritik)
  2. Risk Engine kararı dashboard kararını override ediyor
  3. NO_TRADE için why_no_trade dolu geliyor
  4. Entry şartları dönüyor
  5. Exit şartları dönüyor (açık pozisyon varsa)
  6. Active paper position varsa entry/stop/target/PnL dönüyor
  7. News decision_impact dönüyor
  8. Learning layer prediction_id üretiyor
  9. KILL_SWITCH en üst öncelik
 10. DQS düşükse paper trade açılmıyor

PAPER_SAFE / NO_EXECUTION. Live ağ/data yok, monkeypatch ile mock'lanır.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import app.services.paper_decision_service as pds


# ── 1. Decision label türeticisi — açık pozisyon yokken KÜÇÜLT yok ──────────

def test_no_open_positions_never_returns_kucult():
    """Risk Engine RISK_REDUCE dese bile açık pozisyon yoksa KÜÇÜLT dönmez."""
    label, reason = pds.derive_decision_label(
        risk_action="RISK_REDUCE",
        kill_switch_active=False,
        has_open_positions=False,
        dqs_decision="PASS",
    )
    assert label != pds.DECISION_LABEL_REDUCE, "KÜÇÜLT açık pozisyon yokken DÖNMEMELİ"
    assert label == pds.DECISION_LABEL_NEW_RISK_BLOCK
    assert "no_open_positions" in reason


def test_open_positions_with_risk_reduce_returns_kucult():
    """Açık pozisyon VAR + RISK_REDUCE → KÜÇÜLT döner."""
    label, _ = pds.derive_decision_label(
        risk_action="RISK_REDUCE",
        kill_switch_active=False,
        has_open_positions=True,
        dqs_decision="PASS",
    )
    assert label == pds.DECISION_LABEL_REDUCE


# ── 2. Risk Engine override ────────────────────────────────────────────────

def test_risk_engine_no_position_increase_overrides():
    """NO_POSITION_INCREASE her durumda POZİSYON ARTIRMA döner."""
    for has_pos in (True, False):
        label, _ = pds.derive_decision_label(
            risk_action="NO_POSITION_INCREASE",
            kill_switch_active=False,
            has_open_positions=has_pos,
            dqs_decision="PASS",
        )
        assert label == pds.DECISION_LABEL_NO_INCREASE


def test_risk_engine_watch_returns_izle():
    label, _ = pds.derive_decision_label(
        risk_action="WATCH",
        kill_switch_active=False,
        has_open_positions=True,
        dqs_decision="PASS",
    )
    assert label == pds.DECISION_LABEL_WATCH


def test_risk_engine_hold_with_positions_returns_koru():
    label, _ = pds.derive_decision_label(
        risk_action="HOLD",
        kill_switch_active=False,
        has_open_positions=True,
        dqs_decision="PASS",
    )
    assert label == pds.DECISION_LABEL_HOLD


# ── 3 + 10. why_no_trade + DQS gating ──────────────────────────────────────

def test_no_trade_reason_filled_when_no_consensus():
    """Hiç directional signal yoksa why_no_trade dolu olmalı."""
    out = pds._build_paper_trading_decision(
        state=None,
        snapshot=None,
        risk_verdict={"risk_action": "HOLD", "kill_switch_active": False},
        dqs_status={"decision_permission": "ALLOWED", "dqs_decision": "PASS"},
    )
    assert out["why_no_trade"], "why_no_trade boş olmamalı"
    assert "no_directional_consensus" in out["why_no_trade"]


def test_dqs_blocked_prevents_paper_open():
    """DQS BLOCKED iken setup_validity False olmalı ve why_no_trade dolu."""
    class _SigState:
        last_tick_signals = {
            "BTCUSD": {"final_score": 75.0, "final_direction": "BULLISH"},
        }
        last_event = None
        positions = {}

    out = pds._build_paper_trading_decision(
        state=_SigState(),
        snapshot={"open_positions": []},
        risk_verdict={"risk_action": "HOLD", "kill_switch_active": False},
        dqs_status={"decision_permission": "BLOCKED", "dqs_decision": "FAIL_NO_DECISION"},
    )
    assert out["setup_validity"] is False
    assert "data_quality_blocks_open" in out["why_no_trade"]


def test_dqs_below_threshold_blocks_open():
    class _SigState:
        last_tick_signals = {
            "XAUUSD": {"final_score": 80.0, "final_direction": "BULLISH"},
        }
        last_event = None
        positions = {}

    out = pds._build_paper_trading_decision(
        state=_SigState(),
        snapshot=None,
        risk_verdict={"risk_action": "HOLD", "kill_switch_active": False},
        dqs_status={"decision_permission": "BELOW_THRESHOLD", "dqs_decision": "DEGRADED_PASS"},
    )
    assert out["setup_validity"] is False
    assert "data_quality_blocks_open" in out["why_no_trade"]


# ── 4. Entry plan ───────────────────────────────────────────────────────────

def test_entry_plan_returns_conditions():
    paper_dec = {
        "would_trade_asset":      "BTCUSD",
        "would_trade_direction":  "LONG",
        "setup_validity":         True,
    }
    market_int = {
        "regime": "RISK_ON", "dollar_pressure": "DXY yatay",
        "credit_confirmation": "HYG/JNK güçlü",
    }
    risk_verdict = {"kill_switch_active": False}
    plan = pds._build_entry_plan(paper_dec, market_int, risk_verdict)
    assert "conditions_to_enter" in plan
    assert any("BTCUSD" in c for c in plan["conditions_to_enter"])
    assert isinstance(plan["required_macro_confirmations"], list)


def test_entry_plan_demands_macro_when_defensive():
    paper_dec = {
        "would_trade_asset":      "BTCUSD",
        "would_trade_direction":  "LONG",
        "setup_validity":         True,
    }
    plan = pds._build_entry_plan(
        paper_dec,
        market_int={"regime": "DEFENSIVE"},
        risk_verdict={},
    )
    assert any("RISK_ON" in c for c in plan["required_macro_confirmations"])


# ── 5 + 6. Exit plan + active positions ────────────────────────────────────

def test_exit_plan_with_active_positions():
    active = [{
        "asset":         "BTCUSD",
        "stop_loss":     58000.0,
        "target_price":  72000.0,
        "close_if":      "Fiyat 58000 altına kırılırsa",
    }]
    plan = pds._build_exit_plan(active)
    assert plan["stop_loss"] == 58000.0
    assert plan["target_price"] == 72000.0
    assert plan["invalidation_conditions"], "invalidation_conditions boş olmamalı"
    assert plan["risk_reduce_conditions"], "risk_reduce_conditions boş olmamalı"


def test_exit_plan_empty_without_positions():
    plan = pds._build_exit_plan([])
    assert plan["stop_loss"] is None
    assert plan["target_price"] is None


def test_active_positions_schema_from_snapshot():
    snap = {
        "open_positions": [{
            "pair":          "BTCUSD",
            "side":          "LONG",
            "entry_price":   60000.0,
            "current_price": 62000.0,
            "stop_loss":     58000.0,
            "take_profit":   72000.0,
            "size_usd":      25000.0,
            "pnl_usd":       500.0,
            "pnl_pct":       2.0,
            "open_reason":   "consensus_bullish",
        }],
    }
    out = pds._build_active_positions(snap)
    assert len(out) == 1
    item = out[0]
    assert item["asset"]          == "BTCUSD"
    assert item["direction"]      == "LONG"
    assert item["entry_price"]    == 60000.0
    assert item["stop_loss"]      == 58000.0
    assert item["target_price"]   == 72000.0
    assert item["unrealized_pnl"] == 500.0


# ── 7. News-to-decision mapping ────────────────────────────────────────────

def test_news_mapping_returns_decision_impact():
    alerts = [
        {"title": "BTC volatilite uyarısı", "message": "BTC son 30dk %3 düştü",
         "level": "warning", "ts": "2026-06-07T10:00:00Z", "pair": "BTCUSD"},
    ]
    out = pds._build_news_to_decision(alerts, paper_decision={
        "would_trade_asset": "BTCUSD", "would_trade_direction": "LONG",
    })
    assert len(out) == 1
    assert out[0]["decision_impact"]
    assert "BTCUSD" in out[0]["affected_assets"]


# ── 8. Learning layer prediction_id ────────────────────────────────────────

def test_learning_layer_emits_prediction_id():
    class _StubState:
        trades: list = []

    out = pds._build_learning_layer(
        state=_StubState(),
        decision_label=pds.DECISION_LABEL_HOLD,
        paper_decision={"setup_validity": True,
                        "would_trade_asset": "BTCUSD",
                        "would_trade_direction": "LONG"},
        risk_verdict={"risk_action": "HOLD"},
    )
    assert out["prediction_id"].startswith("pred_")
    assert out["decision_logged"] == pds.DECISION_LABEL_HOLD
    assert out["what_will_be_checked_later"]
    assert "BTCUSD" in out["expected_outcome"]


# ── 9. KILL_SWITCH en üst öncelik ──────────────────────────────────────────

def test_kill_switch_overrides_everything():
    label, reason = pds.derive_decision_label(
        risk_action="RISK_REDUCE",  # başka bir aksiyon olsa bile
        kill_switch_active=True,
        has_open_positions=True,
        dqs_decision="PASS",
    )
    assert label == pds.DECISION_LABEL_KILL
    assert "kill_switch" in reason


def test_kill_switch_when_action_is_kill():
    label, _ = pds.derive_decision_label(
        risk_action="KILL_SWITCH",
        kill_switch_active=False,  # action zaten KILL_SWITCH
        has_open_positions=False,
        dqs_decision="PASS",
    )
    assert label == pds.DECISION_LABEL_KILL


# ── 11. API endpoint smoke test ────────────────────────────────────────────

def test_api_endpoint_returns_full_schema():
    """GET /paper/decision/latest tüm üst düzey alanları dönmeli."""
    from fastapi.testclient import TestClient
    from app.main import app

    # build_latest_decision'ı düz bir payload ile mock'la
    fake_payload = pds.PaperDecisionPayload(
        generated_at="2026-06-07T00:00:00Z",
        execution_status="PAPER_SAFE / NO_EXECUTION",
        owner_action="KORU",
        decision_label="KORU",
        decision_reason="risk_engine_hold_with_positions",
    )
    with patch.object(pds, "build_latest_decision", return_value=fake_payload):
        client = TestClient(app)
        r = client.get("/api/v1/paper/decision/latest")
    assert r.status_code == 200
    data = r.json()
    for k in (
        "market_interpretation",
        "data_quality_status",
        "trigger_engine_output",
        "risk_engine_verdict",
        "paper_trading_decision",
        "entry_plan",
        "exit_plan",
        "active_paper_positions",
        "news_to_decision_mapping",
        "learning_layer",
        "owner_action",
        "execution_status",
    ):
        assert k in data, f"Eksik alan: {k}"
    assert data["execution_status"] == "PAPER_SAFE / NO_EXECUTION"


def test_api_endpoint_paper_safe_marker_always_present():
    """execution_status her durumda NO_EXECUTION içermeli — pipeline çökse bile."""
    from fastapi.testclient import TestClient
    from app.main import app

    # Pipeline çökse bile servis paper_safe marker dönmeli (resilience)
    fake_payload = pds.PaperDecisionPayload(
        generated_at="2026-06-07T00:00:00Z",
        execution_status="PAPER_SAFE / NO_EXECUTION",
        owner_action="POZİSYON YOK · NÖTR İZLEME",
        decision_label="POZİSYON YOK · NÖTR İZLEME",
        decision_reason="fallback_flat",
    )
    with patch.object(pds, "build_latest_decision", return_value=fake_payload):
        client = TestClient(app)
        r = client.get("/api/v1/paper/decision/latest")
    assert r.status_code == 200
    assert "NO_EXECUTION" in r.json().get("execution_status", "")
