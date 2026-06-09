"""hourly_snapshot_builder — FAZ 1.5 builder testleri."""
from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.services.hourly_snapshot_builder import (
    _to_serializable,
    build_hourly_snapshot_payload,
)


# ── Mock dataclass'lar (gerçek import gerekmez) ───────────────────────────────

@dataclasses.dataclass(frozen=True)
class _MockMacroLayer:
    regime: str = "NEUTRAL"
    confidence_pct: float = 72.0
    dxy_signal: str = "nötr"
    energy_signal: str = "nötr"
    yield_curve_signal: str = "nötr"
    m2_signal: str = "nötr"
    summary: str = "Test özet"


@dataclasses.dataclass(frozen=True)
class _MockAssetSignal:
    asset_code: str = "BTC"
    status: str = "CONFIRMED"
    value: float = 61000.0
    reason: str = "test"


@dataclasses.dataclass(frozen=True)
class _MockReport:
    macro_layer: _MockMacroLayer = dataclasses.field(
        default_factory=_MockMacroLayer
    )
    asset_signals: tuple = dataclasses.field(
        default_factory=lambda: (_MockAssetSignal(),)
    )
    confirmation_checklist: tuple = ()
    scenarios: tuple = ()
    flip_conditions: tuple = ()
    news_headlines: tuple = ()
    tech_insights: tuple = ()
    appetite_layer: Any = None
    asymmetry: Any = None
    decision: str = "BEKLE"
    verdict: str = "test verdict"


@dataclasses.dataclass(frozen=True)
class _MockRotation:
    primary_flow: str = "BTC"
    conviction: int = 65
    class_scores: tuple = ()
    correlations: tuple = ()
    synthesis: str = "test"
    error: Any = None


# ── _to_serializable ──────────────────────────────────────────────────────────

def test_to_serializable_dataclass():
    result = _to_serializable(_MockMacroLayer())
    assert isinstance(result, dict)
    assert result["regime"] == "NEUTRAL"
    assert result["confidence_pct"] == 72.0


def test_to_serializable_tuple_of_dataclasses():
    tup = (_MockAssetSignal(), _MockAssetSignal(asset_code="XAU"))
    result = _to_serializable(tup)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["asset_code"] == "BTC"
    assert result[1]["asset_code"] == "XAU"


def test_to_serializable_nested_dict():
    d = {"a": _MockMacroLayer(), "b": 42}
    result = _to_serializable(d)
    assert isinstance(result["a"], dict)
    assert result["b"] == 42


def test_to_serializable_primitives_unchanged():
    assert _to_serializable(None)  is None
    assert _to_serializable(True)  is True
    assert _to_serializable(3.14)  == 3.14
    assert _to_serializable("abc") == "abc"


def test_to_serializable_unknown_type_becomes_str():
    from datetime import date
    result = _to_serializable(date(2026, 6, 9))
    assert isinstance(result, str)


# ── build_hourly_snapshot_payload — zorunlu alan varlığı ─────────────────────

def test_payload_has_all_top_level_keys():
    payload = build_hourly_snapshot_payload()
    for key in ("decision_permission", "execution_mode",
                "report", "rotation", "mtf", "paper_trading", "data_quality"):
        assert key in payload, f"Eksik: {key}"


def test_payload_security_fields_always_set():
    payload = build_hourly_snapshot_payload()
    assert payload["decision_permission"] == "NO_EXECUTION"
    assert payload["execution_mode"]      == "PAPER_SAFE"


# ── Report dönüşümü ───────────────────────────────────────────────────────────

def test_report_dataclass_serialized():
    report = _MockReport()
    payload = build_hourly_snapshot_payload(report=report)
    r = payload["report"]
    assert isinstance(r, dict)
    # macro_layer → dict
    assert isinstance(r["macro_layer"], dict)
    assert r["macro_layer"]["regime"] == "NEUTRAL"


def test_report_asset_signals_tuple_to_list():
    report = _MockReport()
    payload = build_hourly_snapshot_payload(report=report)
    sigs = payload["report"]["asset_signals"]
    assert isinstance(sigs, list)
    assert sigs[0]["asset_code"] == "BTC"


def test_report_missing_fields_get_empty_defaults():
    # None report → tamamen boş default
    payload = build_hourly_snapshot_payload(report=None)
    r = payload["report"]
    assert r["macro_layer"] == {}
    assert r["asset_signals"] == []
    assert r["confirmation_checklist"] == []
    assert r["scenarios"] == []


def test_no_crash_on_none_report():
    payload = build_hourly_snapshot_payload(report=None)
    assert payload["report"] == build_hourly_snapshot_payload()["report"]


# ── Rotation dönüşümü ─────────────────────────────────────────────────────────

def test_rotation_dataclass_serialized():
    rot = _MockRotation()
    payload = build_hourly_snapshot_payload(rotation=rot)
    r = payload["rotation"]
    assert isinstance(r, dict)
    assert r["primary_flow"] == "BTC"
    assert r["conviction"] == 65


def test_rotation_none_gives_empty_dict():
    payload = build_hourly_snapshot_payload(rotation=None)
    assert payload["rotation"] == {}


# ── MTF dönüşümü ─────────────────────────────────────────────────────────────

def test_mtf_dict_serialized():
    mtf = {"BTCUSD": {"1h": {"score": 64.1}, "4h": {"score": 61.0}}}
    payload = build_hourly_snapshot_payload(mtf=mtf)
    m = payload["mtf"]
    assert isinstance(m, dict)
    assert m["BTCUSD"]["1h"]["score"] == 64.1


def test_mtf_none_gives_empty_dict():
    payload = build_hourly_snapshot_payload(mtf=None)
    assert payload["mtf"] == {}


def test_mtf_with_dataclass_values():
    """MTF dict içindeki dataclass değerleri de dönüştürülmeli."""
    ti = _MockMacroLayer(regime="BULLISH")
    mtf = {"XAUUSD": {"1d": ti}}
    payload = build_hourly_snapshot_payload(mtf=mtf)
    assert payload["mtf"]["XAUUSD"]["1d"]["regime"] == "BULLISH"


# ── Paper trading dönüşümü ───────────────────────────────────────────────────

def test_paper_trading_dict_passthrough():
    state = {
        "open_positions":  [{"pair": "BTCUSD", "pnl_pct": -0.5}],
        "equity":          10_500.0,
        "realized_pnl_usd": 200.0,
        "last_tick_at":    "2026-06-09T12:00:00Z",
    }
    payload = build_hourly_snapshot_payload(paper_trading_state=state)
    pt = payload["paper_trading"]
    assert pt["open_positions"][0]["pair"] == "BTCUSD"
    assert pt["equity"] == 10_500.0
    assert pt["realized_pnl"] == 200.0


def test_paper_trading_none_gives_safe_defaults():
    payload = build_hourly_snapshot_payload(paper_trading_state=None)
    pt = payload["paper_trading"]
    assert pt["open_positions"] == []
    assert pt["equity"] is None
    assert pt["realized_pnl"] is None


# ── Data quality ─────────────────────────────────────────────────────────────

def test_data_quality_merged():
    dq = {"quality_score": 85, "decision": "OK"}
    payload = build_hourly_snapshot_payload(data_quality=dq)
    assert payload["data_quality"]["quality_score"] == 85
    assert payload["data_quality"]["status"] == "unknown"  # default setdefault
    assert isinstance(payload["data_quality"]["notes"], list)


def test_data_quality_none_gives_defaults():
    payload = build_hourly_snapshot_payload(data_quality=None)
    dq = payload["data_quality"]
    assert dq["status"] == "unknown"
    assert dq["notes"] == []


# ── Tümü bir arada — crash testi ─────────────────────────────────────────────

def test_no_crash_on_completely_empty_call():
    payload = build_hourly_snapshot_payload()
    assert payload["decision_permission"] == "NO_EXECUTION"
    assert payload["execution_mode"]      == "PAPER_SAFE"
    assert isinstance(payload["report"],        dict)
    assert isinstance(payload["rotation"],      dict)
    assert isinstance(payload["mtf"],           dict)
    assert isinstance(payload["paper_trading"], dict)
    assert isinstance(payload["data_quality"],  dict)


def test_full_mock_pipeline_no_crash():
    payload = build_hourly_snapshot_payload(
        report=_MockReport(),
        rotation=_MockRotation(),
        mtf={"BTCUSD": {"1h": {"score": 64.1}}, "XAUUSD": {"4h": {"score": 71.2}}},
        paper_trading_state={
            "open_positions": [],
            "equity": 10_000.0,
            "realized_pnl_usd": 0.0,
        },
        data_quality={"quality_score": 90, "decision": "OK"},
    )
    # JSON serileştirilebilir mi?
    import json
    dumped = json.dumps(payload)
    assert len(dumped) > 10
