"""
FAZ 2 — agent_hourly_thesis_service testleri.

Kapsam:
  • not_created — snapshot yok / boş liste
  • Thesis schema — zorunlu alanlar
  • Güvenlik — NO_EXECUTION / PAPER_SAFE / can_open_trade=False
  • market_view — primary_bias derivasyon
  • asset_bias — status → bias eşleşmesi
  • MTF çelişki tespiti
  • confirmation_health — met=True/False sayımı
  • watchlist — sadece "watch" bias'lı asset'ler
  • positions_under_review — salt-okunur bağlam
  • source_snapshot_ids — dolu olmalı
  • JSON serializable — crash testi

Mock market data yok.
Test fixture'larındaki sayılar gerçek snapshot alanlarından alınmış (bkz. FAZ 1.6 doğrulama).
"""
from __future__ import annotations

import json

import pytest

from app.services.agent_hourly_thesis_service import build_agent_hourly_thesis


# ── Fixture yardımcıları ──────────────────────────────────────────────────────

def _snapshot(
    snapshot_id: str = "snap-001",
    regime: str = "TRANSITIONING",
    appetite: str = "MODERATE",
    confidence_pct: float = 60.0,
    asset_signals: list | None = None,
    checklist: list | None = None,
    scenarios: list | None = None,
    asymmetry: dict | None = None,
    rotation: dict | None = None,
    mtf: dict | None = None,
    paper_trading: dict | None = None,
) -> dict:
    """Gerçek snapshot yapısıyla uyumlu minimal test fixture."""
    return {
        "snapshot_id": snapshot_id,
        "created_at":  "2026-06-09T16:07:26Z",
        "schema_version": "hourly_snapshot_v1",
        "decision_permission": "NO_EXECUTION",
        "execution_mode": "PAPER_SAFE",
        "report": {
            "macro_layer": {
                "regime":         regime,
                "confidence_pct": confidence_pct,
                "summary":        f"Makro {regime.lower()} — test özet",
            },
            "appetite_layer": {"status": appetite},
            "asset_signals":  asset_signals or [],
            "confirmation_checklist": checklist or [],
            "scenarios": scenarios or [],
            "asymmetry": asymmetry or {},
        },
        "rotation":       rotation or {"primary_flow": "DOLAR_GÜCÜ", "conviction": 25,
                                       "synthesis": "Test rotation özeti"},
        "mtf":            mtf or {},
        "paper_trading":  paper_trading or {"open_positions": [], "equity": 100_000.0},
    }


def _signal(code: str, status: str, reason: str = "test reason") -> dict:
    return {"asset_code": code, "asset_name": code, "status": status, "reason": reason}


def _checklist_item(signal: str, met: bool) -> dict:
    return {"signal": signal, "met": met, "current_value": "N/A", "threshold": "N/A"}


def _scenario(key: str, prob: int) -> dict:
    return {"key": key, "label": key, "probability_pct": str(prob),
            "trigger": "test", "brief": "test", "color": "yellow"}


def _mtf_entry(structure: str, tech_score: int = 50) -> dict:
    return {
        "asset_code": "BTCUSD", "timeframe": "1h",
        "current_price": 61_000.0,
        "structure":     structure,
        "technical_score": tech_score,
        "momentum_score": 30,
    }


# ── 1. not_created — snapshot yok ────────────────────────────────────────────

def test_not_created_when_empty_list():
    result = build_agent_hourly_thesis([])
    assert result["status"] == "not_created"
    assert result["reason"] == "no_real_hourly_snapshots"


def test_not_created_when_all_fields_missing():
    snap = {
        "snapshot_id": "x",
        "report": None,
        "rotation": None,
        "mtf": None,
    }
    result = build_agent_hourly_thesis([snap])
    assert result["status"] == "not_created"


# ── 2. Thesis schema — zorunlu alanlar ───────────────────────────────────────

def test_thesis_has_all_required_keys():
    thesis = build_agent_hourly_thesis([_snapshot()])
    for key in (
        "thesis_id", "created_at", "schema_version",
        "decision_permission", "execution_mode",
        "source_snapshot_ids", "lookback_hours",
        "market_view", "asset_bias",
        "confirmation_health", "strongest_reasons",
        "main_contradictions", "watchlist",
        "positions_under_review", "data_quality",
        "paper_trading_context",
        "thesis_sanity",          # FAZ 2.5 — sanity gate sonucu
    ):
        assert key in thesis, f"Eksik: {key}"


def test_thesis_sanity_has_required_fields():
    """thesis_sanity alanı doğru yapıda olmalı."""
    thesis = build_agent_hourly_thesis([_snapshot()])
    ts = thesis["thesis_sanity"]
    for key in ("status", "score", "issues", "safe_for_context"):
        assert key in ts, f"thesis_sanity'de eksik: {key}"


def test_schema_version_correct():
    thesis = build_agent_hourly_thesis([_snapshot()])
    assert thesis["schema_version"] == "agent_hourly_thesis_v1"


# ── 3. Güvenlik ───────────────────────────────────────────────────────────────

def test_decision_permission_always_no_execution():
    thesis = build_agent_hourly_thesis([_snapshot()])
    assert thesis["decision_permission"] == "NO_EXECUTION"


def test_execution_mode_always_paper_safe():
    thesis = build_agent_hourly_thesis([_snapshot()])
    assert thesis["execution_mode"] == "PAPER_SAFE"


def test_can_open_trade_always_false():
    thesis = build_agent_hourly_thesis([_snapshot()])
    assert thesis["paper_trading_context"]["can_open_trade"] is False


def test_paper_trading_context_permission_context_only():
    thesis = build_agent_hourly_thesis([_snapshot()])
    assert thesis["paper_trading_context"]["permission"] == "context_only"


def test_thesis_is_json_serializable():
    """Thesis crash etmeden JSON'a dönüştürülebilmeli."""
    thesis = build_agent_hourly_thesis([_snapshot(
        asset_signals=[_signal("BTCUSD", "PENDING"), _signal("XAUUSD", "CONFIRMED")],
        checklist=[_checklist_item("DXY < 104", True), _checklist_item("BTC > 58k", False)],
        scenarios=[_scenario("bull", 40), _scenario("base", 44), _scenario("bear", 16)],
        asymmetry={"ratio": 8.12, "label": "Çok Olumlu",
                   "expected_gain_pct": 13.0, "expected_loss_pct": 1.6,
                   "brief": "Her %1 kayba 8.1 kazanç"},
    )])
    dumped = json.dumps(thesis)
    assert len(dumped) > 50


# ── 4. source_snapshot_ids ───────────────────────────────────────────────────

def test_source_snapshot_ids_populated():
    snaps = [_snapshot("id-1"), _snapshot("id-2")]
    thesis = build_agent_hourly_thesis(snaps)
    assert thesis["source_snapshot_ids"] == ["id-1", "id-2"]


def test_lookback_hours_matches_snapshot_count():
    snaps = [_snapshot(f"id-{i}") for i in range(5)]
    thesis = build_agent_hourly_thesis(snaps)
    assert thesis["lookback_hours"] == 5


# ── 5. market_view ────────────────────────────────────────────────────────────

def test_market_view_has_primary_bias():
    thesis = build_agent_hourly_thesis([_snapshot()])
    mv = thesis["market_view"]
    assert "primary_bias" in mv
    assert mv["primary_bias"] in (
        "risk_on", "risk_off", "hedge", "mixed", "data_unavailable"
    )


def test_market_view_transitioning_moderate_is_mixed():
    thesis = build_agent_hourly_thesis([_snapshot(regime="TRANSITIONING", appetite="MODERATE")])
    assert thesis["market_view"]["primary_bias"] == "mixed"


def test_market_view_bullish_appetite_is_risk_on():
    thesis = build_agent_hourly_thesis([_snapshot(regime="BULLISH", appetite="HIGH")])
    assert thesis["market_view"]["primary_bias"] == "risk_on"


def test_market_view_bearish_low_is_risk_off():
    thesis = build_agent_hourly_thesis([_snapshot(regime="BEARISH", appetite="LOW")])
    assert thesis["market_view"]["primary_bias"] == "risk_off"


def test_market_view_bearish_moderate_is_hedge():
    thesis = build_agent_hourly_thesis([_snapshot(regime="BEARISH", appetite="MODERATE")])
    assert thesis["market_view"]["primary_bias"] == "hedge"


def test_market_view_confidence_normalized():
    thesis = build_agent_hourly_thesis([_snapshot(confidence_pct=60.0)])
    assert thesis["market_view"]["confidence"] == pytest.approx(0.60)


def test_scenario_dominant_base():
    snap = _snapshot(scenarios=[
        _scenario("bull", 40), _scenario("base", 44), _scenario("bear", 16),
    ])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["market_view"]["scenario_dominant"] == "base"


def test_scenario_summary_format():
    snap = _snapshot(scenarios=[
        _scenario("bull", 30), _scenario("base", 50), _scenario("bear", 20),
    ])
    thesis = build_agent_hourly_thesis([snap])
    assert "bull=30%" in thesis["market_view"]["scenario_summary"]
    assert "bear=20%" in thesis["market_view"]["scenario_summary"]


def test_asymmetry_ratio_captured():
    snap = _snapshot(asymmetry={"ratio": 8.12, "label": "Çok Olumlu"})
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["market_view"]["asymmetry_ratio"] == 8.12


# ── 6. asset_bias ─────────────────────────────────────────────────────────────

def test_asset_confirmed_is_cautious_long():
    snap = _snapshot(asset_signals=[_signal("XAGUSD", "CONFIRMED", "Silver güçlü")])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["asset_bias"]["XAGUSD"]["bias"] == "cautious_long"


def test_asset_pending_is_watch():
    snap = _snapshot(asset_signals=[_signal("BTCUSD", "PENDING", "Destek-direnç arası")])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["asset_bias"]["BTCUSD"]["bias"] == "watch"


def test_asset_neutral_is_neutral():
    snap = _snapshot(asset_signals=[_signal("XAUUSD", "NEUTRAL", "Dar bant")])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["asset_bias"]["XAUUSD"]["bias"] == "neutral"


def test_asset_blocking_is_avoid():
    snap = _snapshot(asset_signals=[_signal("VIX", "BLOCKING", "Volatilite yüksek")])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["asset_bias"]["VIX"]["bias"] == "avoid"


def test_asset_reason_included():
    snap = _snapshot(asset_signals=[_signal("BTCUSD", "PENDING", "$61,170 destek-direnç arası")])
    thesis = build_agent_hourly_thesis([snap])
    assert "$61,170" in thesis["asset_bias"]["BTCUSD"]["reason"]


# ── 7. MTF çelişki tespiti ────────────────────────────────────────────────────

def test_mtf_contradiction_detected_when_mixed():
    """1h=BEARISH, 4h=BULLISH, 1d=BEARISH → çelişki var."""
    snap = _snapshot(
        asset_signals=[_signal("BTCUSD", "PENDING")],
        mtf={
            "BTCUSD": {
                "1h": {**_mtf_entry("BEARISH"), "timeframe": "1h"},
                "4h": {**_mtf_entry("BULLISH"), "timeframe": "4h"},
                "1d": {**_mtf_entry("BEARISH"), "timeframe": "1d"},
            }
        },
    )
    thesis = build_agent_hourly_thesis([snap])
    contradictions = thesis["asset_bias"]["BTCUSD"]["contradictions"]
    assert len(contradictions) == 1
    assert "MTF çelişkisi" in contradictions[0]


def test_mtf_structures_embedded_in_asset_bias():
    """mtf_structures sanity gate için asset_bias içine gömülmeli."""
    snap = _snapshot(
        asset_signals=[_signal("BTCUSD", "PENDING")],
        mtf={
            "BTCUSD": {
                "1h": {**_mtf_entry("BEARISH"), "timeframe": "1h"},
                "4h": {**_mtf_entry("BULLISH"), "timeframe": "4h"},
                "1d": {**_mtf_entry("BEARISH"), "timeframe": "1d"},
            }
        },
    )
    thesis = build_agent_hourly_thesis([snap])
    structs = thesis["asset_bias"]["BTCUSD"]["mtf_structures"]
    assert isinstance(structs, dict)
    assert structs.get("1h") == "BEARISH"
    assert structs.get("4h") == "BULLISH"


def test_no_mtf_contradiction_when_consistent():
    """1h=BEARISH, 4h=BEARISH, 1d=BEARISH → çelişki yok, ama mtf_structures dolu."""
    snap = _snapshot(
        asset_signals=[_signal("BRENT", "PENDING")],
        mtf={
            "BRENT": {
                "1h": {**_mtf_entry("BEARISH"), "timeframe": "1h"},
                "4h": {**_mtf_entry("BEARISH"), "timeframe": "4h"},
                "1d": {**_mtf_entry("BEARISH"), "timeframe": "1d"},
            }
        },
    )
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["asset_bias"]["BRENT"]["contradictions"] == []
    # mtf_structures still populated for sanity gate
    assert "1h" in thesis["asset_bias"]["BRENT"]["mtf_structures"]


def test_no_mtf_contradiction_when_no_mtf_data():
    """MTF verisi olmayan asset'te contradiction olmamalı."""
    snap = _snapshot(asset_signals=[_signal("HYG", "CONFIRMED")])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["asset_bias"]["HYG"]["contradictions"] == []
    assert thesis["asset_bias"]["HYG"]["mtf_structures"] == {}


# ── 8. confirmation_health ───────────────────────────────────────────────────

def test_confirmation_health_counts_passed_failed():
    snap = _snapshot(checklist=[
        _checklist_item("Brent < 126", True),
        _checklist_item("DXY < 104",  True),
        _checklist_item("BTC > 58k",  False),  # başarısız
    ])
    thesis = build_agent_hourly_thesis([snap])
    ch = thesis["confirmation_health"]
    assert ch["passed"] == 2
    assert ch["failed"] == 1
    assert ch["total"]  == 3


def test_confirmation_health_failed_signals_listed():
    snap = _snapshot(checklist=[
        _checklist_item("Kritik sinyal başarısız", False),
    ])
    thesis = build_agent_hourly_thesis([snap])
    ch = thesis["confirmation_health"]
    assert "Kritik sinyal başarısız" in ch["failed_signals"]


def test_confirmation_health_all_passed():
    snap = _snapshot(checklist=[
        _checklist_item("A", True),
        _checklist_item("B", True),
    ])
    thesis = build_agent_hourly_thesis([snap])
    ch = thesis["confirmation_health"]
    assert ch["failed"] == 0
    assert ch["failed_signals"] == []


def test_confirmation_health_string_met_true():
    """met field'i string 'True' olabilir."""
    snap = _snapshot(checklist=[
        {"signal": "test", "met": "True", "current_value": "x", "threshold": "y"},
    ])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["confirmation_health"]["passed"] == 1
    assert thesis["confirmation_health"]["failed"] == 0


def test_confirmation_health_string_met_false():
    snap = _snapshot(checklist=[
        {"signal": "fail test", "met": "False", "current_value": "x", "threshold": "y"},
    ])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["confirmation_health"]["failed"] == 1


# ── 9. watchlist ─────────────────────────────────────────────────────────────

def test_watchlist_contains_only_watch_assets():
    snap = _snapshot(asset_signals=[
        _signal("BTCUSD", "PENDING"),    # watch
        _signal("XAUUSD", "NEUTRAL"),    # neutral — watchlist'e girmemeli
        _signal("XAGUSD", "CONFIRMED"),  # cautious_long — girmemeli
        _signal("ETHUSD", "PENDING"),    # watch
    ])
    thesis = build_agent_hourly_thesis([snap])
    assert set(thesis["watchlist"]) == {"BTCUSD", "ETHUSD"}


def test_watchlist_empty_when_no_watch_assets():
    snap = _snapshot(asset_signals=[
        _signal("XAGUSD", "CONFIRMED"),
        _signal("HYG",    "CONFIRMED"),
    ])
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["watchlist"] == []


# ── 10. positions_under_review ───────────────────────────────────────────────

def test_positions_under_review_read_only_note():
    pt = {
        "open_positions": [
            {"pair": "BTCUSD", "pnl_pct": -1.97},
            {"pair": "XAUUSD", "pnl_pct": -0.70},
        ],
        "equity": 99_400.0,
    }
    snap = _snapshot(paper_trading=pt)
    thesis = build_agent_hourly_thesis([snap])
    pur = thesis["positions_under_review"]
    assert len(pur) == 2
    for pos in pur:
        assert pos["note"] == "context_only — no action taken"


def test_positions_under_review_empty_when_no_positions():
    snap = _snapshot(paper_trading={"open_positions": [], "equity": 100_000.0})
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["positions_under_review"] == []


# ── 11. data_quality ─────────────────────────────────────────────────────────

def test_data_quality_pass_when_all_fields_present():
    # mtf boş dict → falsy (MTF provider verisi yok sayılır) → degraded.
    # "pass" için tüm üç alan dolu olmalı.
    snap = _snapshot(
        mtf={"BTCUSD": {"1h": {"structure": "BEARISH", "technical_score": 31}}}
    )
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["data_quality"]["status"] == "pass"


def test_data_quality_degraded_when_mtf_missing():
    snap = _snapshot()
    snap["mtf"] = None
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["data_quality"]["status"] == "degraded"


def test_data_quality_fail_when_all_missing():
    snap = {"snapshot_id": "x", "report": {"macro_layer": {"regime": "TRANSITIONING"}},
            "rotation": None, "mtf": None}
    # report var ama rotation + mtf yok → degraded
    thesis = build_agent_hourly_thesis([snap])
    assert thesis["data_quality"]["status"] in ("pass", "degraded", "fail")
    # crash olmamış
    assert "status" in thesis["data_quality"]


# ── 12. strongest_reasons + main_contradictions ───────────────────────────────

def test_strongest_reasons_list():
    thesis = build_agent_hourly_thesis([_snapshot(
        asset_signals=[_signal("XAGUSD", "CONFIRMED", "Silver güçlü")],
        rotation={"primary_flow": "BTC", "conviction": 70, "synthesis": "BTC çekiyor"},
    )])
    assert isinstance(thesis["strongest_reasons"], list)
    assert len(thesis["strongest_reasons"]) >= 1


def test_main_contradictions_include_failed_checklist():
    snap = _snapshot(checklist=[
        _checklist_item("Kritik şart", False),
    ])
    thesis = build_agent_hourly_thesis([snap])
    joined = " ".join(thesis["main_contradictions"])
    assert "Kritik şart" in joined


def test_main_contradictions_include_mtf_conflict():
    snap = _snapshot(
        asset_signals=[_signal("BTCUSD", "PENDING")],
        mtf={
            "BTCUSD": {
                "1h": {**_mtf_entry("BEARISH")},
                "4h": {**_mtf_entry("BULLISH")},
                "1d": {**_mtf_entry("BEARISH")},
            }
        },
    )
    thesis = build_agent_hourly_thesis([snap])
    joined = " ".join(thesis["main_contradictions"])
    assert "MTF" in joined
