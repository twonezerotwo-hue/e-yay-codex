"""Panel audit + replay status endpoint testleri."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.providers import MockMarketProvider
from app.services.regime_report_service import (
    AssetSignal, AsymmetrySignal, MacroLayer, RegimeReport, RiskAppetiteLayer,
)


def _stub_report(decision: str = "AÇIL") -> RegimeReport:
    macro = MacroLayer(
        regime="RISK_ON", confidence_pct=65,
        dxy_signal="-", energy_signal="-", yield_curve_signal="-",
        m2_signal="-", summary="stub",
    )
    appetite = RiskAppetiteLayer(
        status="STRONG", credit_signal="-",
        btc_dominance_signal="-", usdt_dominance_signal="-",
        safe_haven_signal="-", summary="stub",
    )
    asset = AssetSignal(
        asset_code="BTCUSD", asset_name="Bitcoin", status="CONFIRMED",
        reason="stub", value=60000.0, unit="$",
    )
    asym = AsymmetrySignal(
        expected_gain_pct=5.0, expected_loss_pct=3.0, ratio=1.67,
        label="Dengeli", color="yellow", brief="stub",
    )
    return RegimeReport(
        generated_at="2026-06-11T00:00:00Z",
        execution_mode="OFF / NO_EXECUTION",
        macro_layer=macro, appetite_layer=appetite,
        asset_signals=(asset,), confirmation_checklist=(),
        decision=decision, owner_action="-", verdict="ok",
        scenarios=(), asymmetry=asym,
        owner_actions=(), flip_conditions=(),
        news_headlines=(), upcoming_catalysts=(),
        blocking_count=0, confirmed_count=1, pending_count=0,
    )


@pytest.fixture
def _offline_pipeline(monkeypatch):
    from app.market_state import canonical_state as cs
    monkeypatch.setattr(cs, "_cached", None)
    monkeypatch.setattr(cs, "_cached_at", 0.0)

    monkeypatch.setattr("app.api.regime_report._get_provider", lambda: MockMarketProvider())

    class _FakeIngestion:
        def __init__(self, *a, **k): ...
        def run(self): return SimpleNamespace(persisted_snapshots=[])

    class _FakeRegime:
        def generate(self, *a, **k): return _stub_report()

    class _FakeNews:
        def fetch_headlines(self, *a, **k): return ()

    class _FakeGeo:
        def fetch(self, *a, **k): return ()

    class _FakeRotation:
        def compute(self): return None

    class _FakeTech:
        def compute(self): return {}

    class _FakeCal:
        def fetch_upcoming(self, *a, **k): return ()

    monkeypatch.setattr("app.services.ProviderIngestionService", _FakeIngestion)
    monkeypatch.setattr("app.services.regime_report_service.RegimeReportService", _FakeRegime)
    monkeypatch.setattr("app.providers.news_provider.NewsProvider", _FakeNews)
    monkeypatch.setattr("app.providers.geo_news_provider.GeoNewsProvider", _FakeGeo)
    monkeypatch.setattr("app.providers.capital_rotation_provider.CapitalRotationProvider", _FakeRotation)
    monkeypatch.setattr("app.providers.technical_provider.TechnicalProvider", _FakeTech)
    monkeypatch.setattr("app.services.event_calendar_service.EventCalendarService", _FakeCal)
    monkeypatch.setattr(
        "app.services.paper_trading_service.get_snapshot",
        lambda *a, **k: {"open_positions": [], "realized_pnl_usd": 0.0},
    )


# ── Replay status ────────────────────────────────────────────────────────────


def test_replay_status_is_reserved() -> None:
    from app.api.replay_status import get_replay_status
    result = get_replay_status("snap-2026-06-10T12:00")
    assert result["status"] == "reserved_not_active"
    assert result["paper_safe"] is True
    assert result["execution_side_effects"] == "NO_EXECUTION"
    assert result["snapshot_id"] == "snap-2026-06-10T12:00"


# ── Panel audit ──────────────────────────────────────────────────────────────


def _audit() -> dict:
    from app.api.panel_audit import get_panel_audit
    resp = get_panel_audit()
    return json.loads(bytes(resp.body).decode("utf-8"))


def test_panel_audit_ok_with_clean_state(_offline_pipeline) -> None:
    data = _audit()
    assert data["overall_status"] in ("OK", "WARNING")  # warnings stub'lardan gelebilir
    assert data["paper_safe"] is True
    assert isinstance(data["issues"], list)
    assert data["snapshot_id"].startswith("dash::")


def test_panel_audit_severities_have_correct_priority(_offline_pipeline) -> None:
    data = _audit()
    severities = {i["severity"] for i in data["issues"]}
    expected = "ERROR" if "ERROR" in severities else ("WARNING" if "WARNING" in severities else "OK")
    assert data["overall_status"] == expected
