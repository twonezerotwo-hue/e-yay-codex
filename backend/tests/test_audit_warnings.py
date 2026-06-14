"""PHASE 4 — best-effort enrichment hataları audit warning olarak görünür.

Invariant: enrichment fail olursa endpoint/snapshot ÇALIŞMAYA DEVAM eder (default'a
düşer) AMA hata sessizce yutulmaz; audit_warnings içinde görünür + loglanır.
Paper state bozulmaz.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from app.core.audit_warnings import make_audit_warning
from app.services import paper_trading_service as pts


# ── Helper format ─────────────────────────────────────────────────────────────

def test_make_audit_warning_format():
    w = make_audit_warning("src.x", "reason_y", "something failed")
    assert w == {
        "source": "src.x", "severity": "warning", "reason": "reason_y",
        "message": "something failed", "recoverable": True,
    }


def test_make_audit_warning_overrides_and_truncation():
    w = make_audit_warning("s", "r", "m", severity="error", recoverable=False)
    assert w["severity"] == "error"
    assert w["recoverable"] is False
    assert len(make_audit_warning("s", "r", "x" * 500)["message"]) == 300


# ── get_snapshot: enrichment fail → warning görünür, snapshot sağ kalır ───────

def _raise(*_a, **_k):
    raise RuntimeError("enrichment boom")


def _state_with_position() -> "pts.TradingState":
    pos = pts.Position(
        pair="BTCUSD", side="LONG", entry_price=60000.0,
        entry_at="2026-06-14T00:00:00+00:00", size_usd=25000.0, last_signal="t",
    )
    st = pts.TradingState()
    st.positions["BTCUSD"] = pos
    return st


def test_snapshot_surfaces_enrichment_failures(monkeypatch):
    monkeypatch.setattr(pts, "_load_state", lambda: _state_with_position())
    monkeypatch.setattr(
        "app.services.position_management_service.build_opening_explanation", _raise,
    )
    monkeypatch.setattr(
        "app.services.ai_trade_opinion_service.build_position_opinion_view", _raise,
    )

    snap = pts.get_snapshot(current_prices={"BTCUSD": 64000.0})

    # Snapshot çalışmaya devam etti (endpoint 200 eşdeğeri) + pozisyon korundu
    assert isinstance(snap, dict)
    assert len(snap["open_positions"]) == 1
    assert snap["open_positions"][0]["pair"] == "BTCUSD"

    # Hatalar artık görünür
    aw = snap["audit_warnings"]
    assert isinstance(aw, list) and len(aw) >= 2
    sources = {w["source"] for w in aw}
    assert "paper_snapshot.opening_explanation" in sources
    assert "paper_snapshot.agent_trade_opinion" in sources
    for w in aw:
        assert {"source", "severity", "reason", "message", "recoverable"} <= set(w)
        assert w["severity"] == "warning"
        assert w["recoverable"] is True
        assert "boom" in w["message"]

    # Default davranış korundu (sessiz yutmadaki değerlerle aynı)
    assert snap["open_positions"][0]["opening_explanation"] == {}
    assert snap["open_positions"][0]["agent_trade_opinion"] == {"available": False}


def test_snapshot_clean_path_has_empty_warnings(monkeypatch):
    monkeypatch.setattr(pts, "_load_state", lambda: pts.TradingState())
    snap = pts.get_snapshot(current_prices={})
    assert snap["audit_warnings"] == []
