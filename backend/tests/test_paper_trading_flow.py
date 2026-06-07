from __future__ import annotations

import sys
import types
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.modules.setdefault("numpy", types.SimpleNamespace())

from app.api import paper_trading
from app.main import app
from app.services import auto_weight_trainer
from app.services import paper_trading_service as pts


client = TestClient(app)


def _set_tmp_state(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pts, "_STATE_PATH", tmp_path / "paper_trading_state.json")
    pts.reset_state()
    # Eski _RESPONSE_CACHE backward-compat — kaldırıldı, monkey-patch sessiz geçsin
    if hasattr(paper_trading, "_RESPONSE_CACHE"):
        monkeypatch.setattr(paper_trading, "_RESPONSE_CACHE", None)


def _consensus_signal(
    pair: str,
    *,
    score: float = 75.0,
    direction: str = "bullish",
    regime: str = "CRISIS",
    confluence_status: str = "aligned",
    dominant_module: str = "fundamental",
) -> dict[str, object]:
    return {
        "symbol": pair,
        "final_score": score,
        "final_direction": direction,
        "confluence": {"status": confluence_status},
        "raw_regime": regime,
        "primary_tf": "1h",
        "base": {"contributions": {dominant_module: {"weighted_score": 2.0}}},
        "tf_signals": {},
        "other_tf_scores": {},
    }


def test_tick_consensus_blocks_weekend_open_for_gated_markets(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    closed_at = datetime(2026, 6, 5, 21, 30, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: closed_at)

    state = pts.tick_consensus(
        {
            "XAUUSD": _consensus_signal("XAUUSD"),
            "XAGUSD": _consensus_signal("XAGUSD"),
            "BRENT": _consensus_signal("BRENT"),
        },
        {
            "XAUUSD": 3350.0,
            "XAGUSD": 34.0,
            "BRENT": 82.0,
        },
    )

    assert state.positions == {}
    assert state.pending_orders == {}
    snapshot = pts.get_snapshot({"XAUUSD": 3350.0, "XAGUSD": 34.0, "BRENT": 82.0})
    assert snapshot["pending_orders"] == []


def test_tick_consensus_queues_then_opens_after_confirmation_window(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    start_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: start_at)

    initial_state = pts.tick_consensus(
        {"XAUUSD": _consensus_signal("XAUUSD")},
        {"XAUUSD": 3345.0},
    )

    assert initial_state.positions == {}
    assert "XAUUSD" in initial_state.pending_orders
    pending = initial_state.pending_orders["XAUUSD"]
    assert pending.side == "LONG"

    monkeypatch.setattr(pts, "_utc_now", lambda: start_at + timedelta(seconds=61))
    final_state = pts.tick_consensus(
        {"XAUUSD": _consensus_signal("XAUUSD")},
        {"XAUUSD": 3351.0},
    )

    assert "XAUUSD" in final_state.positions
    assert final_state.positions["XAUUSD"].side == "LONG"
    assert final_state.positions["XAUUSD"].entry_price == 3351.0
    assert final_state.pending_orders == {}


def test_expired_pending_open_is_canceled_if_market_is_closed_at_execution(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    start_at = datetime(2026, 6, 5, 20, 59, 30, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: start_at)

    pts.tick_consensus({"XAUUSD": _consensus_signal("XAUUSD")}, {"XAUUSD": 3345.0})

    monkeypatch.setattr(pts, "_utc_now", lambda: start_at + timedelta(seconds=61))
    final_state = pts.tick_consensus(
        {"XAUUSD": _consensus_signal("XAUUSD")},
        {"XAUUSD": 3351.0},
    )

    assert final_state.positions == {}
    assert final_state.pending_orders == {}


def test_rejected_pending_open_is_ignored_while_signal_fingerprint_is_unchanged(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    start_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: start_at)

    pts.tick_consensus({"XAUUSD": _consensus_signal("XAUUSD")}, {"XAUUSD": 3345.0})
    assert pts.reject_pending_open("XAUUSD") is True

    monkeypatch.setattr(pts, "_utc_now", lambda: start_at + timedelta(seconds=61))
    final_state = pts.tick_consensus(
        {"XAUUSD": _consensus_signal("XAUUSD")},
        {"XAUUSD": 3351.0},
    )

    assert final_state.positions == {}
    assert final_state.pending_orders == {}
    assert "XAUUSD" in final_state.rejected_signals


def test_trading_state_endpoint_exposes_pending_orders_and_reject_flow(monkeypatch, tmp_path) -> None:
    _set_tmp_state(monkeypatch, tmp_path)
    now_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(pts, "_utc_now", lambda: now_at)
    monkeypatch.setattr(auto_weight_trainer, "maybe_retrain", lambda state, force=False: {"status": "skipped"})

    prices = {
        "BTCUSD": 65000.0,
        "XAUUSD": 3345.0,
        "XAGUSD": 34.0,
        "BRENT": 82.0,
    }

    def fake_build_pipeline():
        report = SimpleNamespace(
            asset_signals=[SimpleNamespace(asset_code=pair, value=price) for pair, price in prices.items()]
        )
        rotation = SimpleNamespace()
        mtf = {
            pair: {"1h": SimpleNamespace(current_price=price)}
            for pair, price in prices.items()
        }
        raw_snapshots = ()  # pipeline'a 4. tuple eklendi — snapshot evidence için
        return report, rotation, mtf, raw_snapshots

    def fake_build_full_signal(asset, report, rotation, mtf, trained_adjustments=None):
        if asset == "XAUUSD":
            return _consensus_signal("XAUUSD")
        return _consensus_signal(asset, score=50.0, direction="neutral", regime="DEFENSIVE", confluence_status="none")

    monkeypatch.setattr(paper_trading, "_build_pipeline", fake_build_pipeline)
    monkeypatch.setattr(paper_trading, "_build_full_signal", fake_build_full_signal)

    # GET artık read-only — pipeline tick'i POST /trading/tick ile tetiklenir.
    tick_response = client.post("/api/v1/trading/tick")
    assert tick_response.status_code == 200

    response = client.get("/api/v1/trading/state")
    body = response.json()

    assert response.status_code == 200
    assert body["execution_mode"] == "PAPER_SAFE / NO_EXECUTION"
    assert len(body["pending_orders"]) == 1
    assert body["pending_orders"][0]["pair"] == "XAUUSD"
    assert body["pending_orders"][0]["seconds_remaining"] <= 60

    reject_response = client.post("/api/v1/trading/pending/XAUUSD/reject")
    reject_body = reject_response.json()
    assert reject_response.status_code == 200
    # Yeni davranış: reject pending'i 'manual_ready_trades' kuyruğuna taşır.
    assert reject_body["status"]            == "rejected"
    assert reject_body["pair"]              == "XAUUSD"
    assert reject_body.get("moved_to")      == "manual_ready_trades"

    refreshed = client.get("/api/v1/trading/state").json()
    assert refreshed["pending_orders"] == []
    # manual_ready_trades artık snapshot'ta görünmeli
    mr_list = refreshed.get("manual_ready_trades", [])
    assert any(it.get("pair") == "XAUUSD" for it in mr_list), \
        "Reddedilen XAUUSD manual_ready_trades'te olmalı"
