"""GET /api/v1/dashboard/state — Canonical State endpoint testleri.

Tek snapshot_id, ortak veri kaynağı, PAPER_SAFE garantisini sabitler. Ağ
bağımlılıkları stub'lanır → test offline ve hızlı.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.providers import MockMarketProvider
from app.services.regime_report_service import (
    AssetSignal, MacroLayer, RegimeReport, RiskAppetiteLayer,
)


def _stub_report() -> RegimeReport:
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
    from app.services.regime_report_service import AsymmetrySignal
    asym = AsymmetrySignal(
        expected_gain_pct=5.0, expected_loss_pct=3.0, ratio=1.67,
        label="Dengeli", color="yellow", brief="stub",
    )
    return RegimeReport(
        generated_at="2026-06-11T00:00:00Z",
        execution_mode="OFF / NO_EXECUTION",
        macro_layer=macro, appetite_layer=appetite,
        asset_signals=(asset,), confirmation_checklist=(),
        decision="AÇIL", owner_action="-", verdict="ok",
        scenarios=(), asymmetry=asym,
        owner_actions=(), flip_conditions=(),
        news_headlines=(), upcoming_catalysts=(),
        blocking_count=0, confirmed_count=1, pending_count=0,
    )


@pytest.fixture
def _offline(monkeypatch):
    """Pipeline ağ çağrılarını stub'la — test offline ve hızlı."""
    from app.market_state import canonical_state as cs

    # Cache temizle (state monkeypatch'lerinden etkilenmesin)
    monkeypatch.setattr(cs, "_cached", None)
    monkeypatch.setattr(cs, "_cached_at", 0.0)

    # Provider
    monkeypatch.setattr("app.api.regime_report._get_provider", lambda: MockMarketProvider())

    class _FakeIngestion:
        def __init__(self, *a, **k): ...
        def run(self):
            return SimpleNamespace(persisted_snapshots=[])

    class _FakeRegime:
        def generate(self, *a, **k):
            return _stub_report()

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


def _call_endpoint() -> dict:
    from app.api.dashboard_state import get_dashboard_state
    resp = get_dashboard_state(force_refresh=True, include_paper=True, include_news=True)
    return json.loads(bytes(resp.body).decode("utf-8"))


def test_endpoint_paper_safe(_offline) -> None:
    data = _call_endpoint()
    assert data["status"] == "ok"
    assert data["paper_safe"] is True
    assert data["execution_side_effects"] == "NO_EXECUTION"


def test_endpoint_has_snapshot_id(_offline) -> None:
    data = _call_endpoint()
    assert isinstance(data["snapshot_id"], str)
    assert data["snapshot_id"].startswith("dash::")
    assert data["state"]["snapshot_id"] == data["snapshot_id"]


def test_endpoint_has_core_panels(_offline) -> None:
    data = _call_endpoint()
    s = data["state"]
    assert "regime_report"     in s
    assert "asset_signals"     in s and len(s["asset_signals"]) >= 1
    assert "macro_layer"       in s
    assert "appetite_layer"    in s
    assert "module_health"     in s
    assert "data_quality"      in s
    assert "risk_gate"         in s
    assert "agent_votes"       in s and isinstance(s["agent_votes"], list)
    assert "position_checks"   in s
    assert "warnings"          in s


def test_endpoint_risk_gate_structured(_offline) -> None:
    data = _call_endpoint()
    g = data["state"]["risk_gate"]
    assert g["status"] in ("PASS", "CAUTION", "BLOCK")
    assert g["source_risk_action"] in ("HOLD", "RISK_REDUCE", "NO_POSITION_INCREASE", "KILL_SWITCH")
    # Risk gate kontrat alanları
    for key in ("hard_blockers", "soft_warnings", "evidence",
                "kill_switch_active", "no_position_increase", "risk_reduce"):
        assert key in g


def test_endpoint_agent_votes_have_risk_and_dqs(_offline) -> None:
    data = _call_endpoint()
    names = {v["agent_name"] for v in data["state"]["agent_votes"]}
    assert "RiskAgent" in names
    assert "DataQualityAgent" in names


def test_endpoint_cache_returns_same_snapshot_id(_offline) -> None:
    """Aynı snapshot_id cache hit'te de tutarlı kalmalı."""
    d1 = _call_endpoint()
    # Cache zaten dolu → force_refresh=False ile aynı snapshot dönmeli
    from app.api.dashboard_state import get_dashboard_state
    resp = get_dashboard_state(force_refresh=False)
    d2 = json.loads(bytes(resp.body).decode("utf-8"))
    assert d2["snapshot_id"] == d1["snapshot_id"]
    assert d2["cached"] is True


def test_endpoint_decision_kapat_maps_to_risk_reduce(_offline, monkeypatch) -> None:
    """Decision=KAPAT iken canonical risk_gate kill_switch + RISK_REDUCE'e gitmeli."""
    from app.market_state import canonical_state as cs
    monkeypatch.setattr(cs, "_cached", None)
    monkeypatch.setattr(cs, "_cached_at", 0.0)

    crisis_report = _stub_report()
    # decision'ı KAPAT'a çevir (RegimeReport frozen olduğu için yeni instance)
    import dataclasses as _dc
    crisis_report = _dc.replace(crisis_report, decision="KAPAT")

    class _FakeRegime2:
        def generate(self, *a, **k):
            return crisis_report
    monkeypatch.setattr("app.services.regime_report_service.RegimeReportService", _FakeRegime2)

    data = _call_endpoint()
    g = data["state"]["risk_gate"]
    # KAPAT → kill_switch_active True + status BLOCK
    assert g["kill_switch_active"] is True
    assert g["status"] == "BLOCK"
