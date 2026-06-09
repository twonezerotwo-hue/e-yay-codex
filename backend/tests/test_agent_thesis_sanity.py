"""
FAZ 2.5 — agent_thesis_sanity testleri.

Kapsam: her kural için pass/fail/degraded senaryoları.
Mock market data yok; thesis fixture'ları gerçek snapshot alanlarına dayalı.
"""
from __future__ import annotations

import pytest

from app.services.agent_thesis_sanity import validate_agent_thesis


# ── Fixture yardımcıları ──────────────────────────────────────────────────────

def _clean_thesis(**overrides) -> dict:
    """Tüm sanity kurallarını geçen minimum geçerli thesis."""
    t = {
        "thesis_id":           "test-id",
        "created_at":          "2026-06-09T16:00:00Z",
        "schema_version":      "agent_hourly_thesis_v1",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "source_snapshot_ids": ["snap-001"],
        "lookback_hours":      1,
        "market_view": {
            "regime_view":        "TRANSITIONING",
            "risk_appetite_view": "MODERATE",
            "primary_bias":       "mixed",
            "confidence":         0.6,
            "scenario_dominant":  "base",
            "scenario_summary":   "bull=40% / base=44% / bear=16%",
            "asymmetry_ratio":    3.0,
            "asymmetry_note":     "ratio=3.0 (Olumlu)",
        },
        "asset_bias": {
            "BTCUSD": {
                "bias":           "watch",
                "reason":         "Destek-direnç arası",
                "contradictions": [],
                "mtf_structures": {"1h": "BEARISH", "4h": "BULLISH", "1d": "BEARISH"},
            },
        },
        "confirmation_health": {
            "passed": 5, "failed": 1, "total": 6, "failed_signals": [],
        },
        "strongest_reasons":    ["[MAKRO] Geçiş halinde"],
        "main_contradictions":  [],
        "watchlist":            ["BTCUSD"],
        "positions_under_review": [],
        "data_quality":         {"status": "pass", "notes": []},
        "paper_trading_context": {
            "permission":     "context_only",
            "can_open_trade": False,
            "reason":         "FAZ 2 thesis only",
        },
    }
    t.update(overrides)
    return t


# ── 1. Kural 1: thesis yok / not_created ─────────────────────────────────────

def test_fail_when_thesis_none():
    result = validate_agent_thesis({})
    assert result["status"] == "fail"
    assert result["safe_for_context"] is False


def test_fail_when_thesis_not_created():
    result = validate_agent_thesis({"status": "not_created", "reason": "x"})
    assert result["status"] == "fail"
    assert result["score"] == 0


# ── 2. Kural 2: source_snapshot_ids boş ──────────────────────────────────────

def test_fail_when_source_snapshot_ids_empty():
    t = _clean_thesis(source_snapshot_ids=[])
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"
    codes = [i["code"] for i in result["issues"]]
    assert "empty_source_snapshot_ids" in codes


def test_fail_when_source_snapshot_ids_missing():
    t = _clean_thesis()
    del t["source_snapshot_ids"]
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"


# ── 3. Kural 3: decision_permission ──────────────────────────────────────────

def test_fail_when_decision_permission_wrong():
    t = _clean_thesis(decision_permission="LIVE_TRADING")
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"
    codes = [i["code"] for i in result["issues"]]
    assert "invalid_decision_permission" in codes


# ── 4. Kural 4: execution_mode ───────────────────────────────────────────────

def test_fail_when_execution_mode_wrong():
    t = _clean_thesis(execution_mode="REAL_EXECUTION")
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"
    codes = [i["code"] for i in result["issues"]]
    assert "invalid_execution_mode" in codes


# ── 5. Kural 5: can_open_trade ───────────────────────────────────────────────

def test_fail_when_can_open_trade_true():
    t = _clean_thesis()
    t["paper_trading_context"]["can_open_trade"] = True
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"
    codes = [i["code"] for i in result["issues"]]
    assert "can_open_trade_true" in codes


def test_pass_when_can_open_trade_false():
    """clean_thesis already has can_open_trade=False."""
    t = _clean_thesis(main_contradictions=[])
    result = validate_agent_thesis(t)
    # No can_open_trade issue
    codes = [i["code"] for i in result["issues"]]
    assert "can_open_trade_true" not in codes


# ── 6. Kural 6: cautious_long + all BEARISH MTF → critical ───────────────────

def test_critical_cautious_long_all_bearish_mtf():
    """XAGUSD CONFIRMED ama MTF 1h/4h/1d hepsi BEARISH → critical."""
    t = _clean_thesis()
    t["asset_bias"]["XAGUSD"] = {
        "bias":           "cautious_long",
        "reason":         "Silver güçlü",
        "contradictions": [],
        "mtf_structures": {"1h": "BEARISH", "4h": "BEARISH", "1d": "BEARISH"},
    }
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"
    critical_issues = [i for i in result["issues"] if i["severity"] == "critical"]
    assert any(
        i["code"] == "long_bias_against_all_bearish_mtf" and i["asset"] == "XAGUSD"
        for i in critical_issues
    )


def test_critical_cautious_long_all_bearish_message_mentions_asset():
    t = _clean_thesis()
    t["asset_bias"]["XAGUSD"] = {
        "bias": "cautious_long", "reason": "test",
        "contradictions": [],
        "mtf_structures": {"1h": "BEARISH", "4h": "BEARISH", "1d": "BEARISH"},
    }
    result = validate_agent_thesis(t)
    issue = next(
        i for i in result["issues"]
        if i["code"] == "long_bias_against_all_bearish_mtf"
    )
    assert "bearish" in issue["message"].lower()
    assert issue["asset"] == "XAGUSD"


def test_no_critical_when_cautious_long_mixed_mtf():
    """1h:BEARISH, 4h:BULLISH → mixed, kural 6 tetiklenmemeli."""
    t = _clean_thesis()
    t["asset_bias"]["XAGUSD"] = {
        "bias": "cautious_long", "reason": "test",
        "contradictions": ["MTF çelişkisi"],
        "mtf_structures": {"1h": "BEARISH", "4h": "BULLISH", "1d": "BEARISH"},
    }
    result = validate_agent_thesis(t)
    # Kural 6 tetiklenmez (mixed)
    codes = [i["code"] for i in result["issues"]]
    assert "long_bias_against_all_bearish_mtf" not in codes


def test_no_critical_when_cautious_long_no_mtf_data():
    """MTF verisi yoksa kural 6 kontrol edilmez."""
    t = _clean_thesis()
    t["asset_bias"]["HYG"] = {
        "bias": "cautious_long", "reason": "sağlam",
        "contradictions": [], "mtf_structures": {},
    }
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "long_bias_against_all_bearish_mtf" not in codes


def test_no_critical_when_cautious_long_all_bullish_mtf():
    """Tüm MTF BULLISH + cautious_long → uyumlu, kural 6 yok."""
    t = _clean_thesis()
    t["asset_bias"]["HYG"] = {
        "bias": "cautious_long", "reason": "test",
        "contradictions": [],
        "mtf_structures": {"1h": "BULLISH", "4h": "BULLISH", "1d": "BULLISH"},
    }
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "long_bias_against_all_bearish_mtf" not in codes


# ── 7. Kural 7: avoid + all BULLISH MTF → warning ────────────────────────────

def test_warning_avoid_all_bullish_mtf():
    t = _clean_thesis()
    t["asset_bias"]["VIX"] = {
        "bias": "avoid", "reason": "test",
        "contradictions": [],
        "mtf_structures": {"1h": "BULLISH", "4h": "BULLISH", "1d": "BULLISH"},
    }
    result = validate_agent_thesis(t)
    # warning → degraded (no other critical issues)
    assert result["status"] == "degraded"
    codes = [i["code"] for i in result["issues"]]
    assert "avoid_bias_against_all_bullish_mtf" in codes


def test_no_warning_avoid_mixed_mtf():
    t = _clean_thesis()
    t["asset_bias"]["VIX"] = {
        "bias": "avoid", "reason": "test",
        "contradictions": [],
        "mtf_structures": {"1h": "BULLISH", "4h": "BEARISH", "1d": "BULLISH"},
    }
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "avoid_bias_against_all_bullish_mtf" not in codes


# ── 8. Kural 8: risk_on + düşük teyit oranı → warning ────────────────────────

def test_warning_risk_on_low_confirmation():
    t = _clean_thesis()
    t["market_view"]["primary_bias"] = "risk_on"
    t["confirmation_health"] = {"passed": 1, "failed": 5, "total": 6}
    result = validate_agent_thesis(t)
    assert result["status"] == "degraded"
    codes = [i["code"] for i in result["issues"]]
    assert "risk_on_bias_low_confirmation" in codes


def test_no_warning_risk_on_high_confirmation():
    t = _clean_thesis()
    t["market_view"]["primary_bias"] = "risk_on"
    t["confirmation_health"] = {"passed": 5, "failed": 1, "total": 6}
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "risk_on_bias_low_confirmation" not in codes


def test_no_warning_mixed_bias_low_confirmation():
    """primary_bias mixed ise kural 8 tetiklenmez."""
    t = _clean_thesis()
    t["market_view"]["primary_bias"] = "mixed"
    t["confirmation_health"] = {"passed": 1, "failed": 5, "total": 6}
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "risk_on_bias_low_confirmation" not in codes


# ── 9. Kural 9: high confidence + contradictions → warning ───────────────────

def test_warning_high_confidence_with_contradictions():
    t = _clean_thesis()
    t["market_view"]["confidence"] = 0.85
    t["main_contradictions"] = ["BTCUSD MTF çelişkisi", "XAUUSD MTF çelişkisi"]
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "high_confidence_with_contradictions" in codes


def test_no_warning_high_confidence_no_contradictions():
    t = _clean_thesis()
    t["market_view"]["confidence"] = 0.85
    t["main_contradictions"] = []
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "high_confidence_with_contradictions" not in codes


def test_no_warning_low_confidence_with_contradictions():
    """confidence <= 0.75 ise kural 9 tetiklenmez."""
    t = _clean_thesis()
    t["market_view"]["confidence"] = 0.60
    t["main_contradictions"] = ["çelişki 1"]
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "high_confidence_with_contradictions" not in codes


# ── 10. Kural 10: high asymmetry + degraded data → warning ───────────────────

def test_warning_high_asymmetry_degraded_data():
    t = _clean_thesis()
    t["market_view"]["asymmetry_ratio"] = 8.12
    t["data_quality"] = {"status": "degraded", "notes": []}
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "high_asymmetry_degraded_data" in codes


def test_no_warning_high_asymmetry_pass_data():
    t = _clean_thesis()
    t["market_view"]["asymmetry_ratio"] = 8.12
    t["data_quality"] = {"status": "pass", "notes": []}
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "high_asymmetry_degraded_data" not in codes


def test_no_warning_low_asymmetry_degraded_data():
    """ratio <= 5 ise kural 10 tetiklenmez."""
    t = _clean_thesis()
    t["market_view"]["asymmetry_ratio"] = 2.5
    t["data_quality"] = {"status": "degraded", "notes": []}
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "high_asymmetry_degraded_data" not in codes


# ── 11. Kural 11: zararda pozisyonlar + risk_on → warning ────────────────────

def test_warning_positions_in_loss_vs_risk_on():
    t = _clean_thesis()
    t["market_view"]["primary_bias"] = "risk_on"
    t["positions_under_review"] = [
        {"pair": "BTCUSD", "pnl_pct": -1.97, "note": "context_only"},
        {"pair": "XAUUSD", "pnl_pct": -2.50, "note": "context_only"},
    ]
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "positions_in_loss_vs_risk_on_thesis" in codes


def test_no_warning_positions_in_loss_mixed_bias():
    """primary_bias mixed ise kural 11 tetiklenmez."""
    t = _clean_thesis()
    t["market_view"]["primary_bias"] = "mixed"
    t["positions_under_review"] = [
        {"pair": "BTCUSD", "pnl_pct": -3.0, "note": "context_only"},
    ]
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "positions_in_loss_vs_risk_on_thesis" not in codes


def test_no_warning_positions_small_loss():
    """pnl_pct >= -1.0 ise kural 11 tetiklenmez."""
    t = _clean_thesis()
    t["market_view"]["primary_bias"] = "risk_on"
    t["positions_under_review"] = [
        {"pair": "BTCUSD", "pnl_pct": -0.5, "note": "context_only"},
    ]
    result = validate_agent_thesis(t)
    codes = [i["code"] for i in result["issues"]]
    assert "positions_in_loss_vs_risk_on_thesis" not in codes


# ── Sonuç hesaplama ───────────────────────────────────────────────────────────

def test_clean_thesis_passes():
    """Hiçbir kural tetiklenmezse status=pass, score=100."""
    t = _clean_thesis()
    result = validate_agent_thesis(t)
    # BTCUSD has mixed MTF so no critical — should be clean
    # Check no critical issues
    has_critical = any(i["severity"] == "critical" for i in result["issues"])
    assert not has_critical
    assert result["safe_for_context"] is True


def test_score_decreases_per_critical_issue():
    """Her critical issue 20 puan düşürür."""
    t = _clean_thesis(
        decision_permission="WRONG",  # -20
        execution_mode="WRONG",       # -20
    )
    result = validate_agent_thesis(t)
    assert result["score"] <= 60  # 100 - 20 - 20


def test_score_decreases_per_warning():
    """Her warning issue 5 puan düşürür."""
    t = _clean_thesis()
    t["market_view"]["asymmetry_ratio"] = 8.12
    t["data_quality"] = {"status": "degraded", "notes": []}  # -5
    result = validate_agent_thesis(t)
    assert result["score"] == 95  # 100 - 5


def test_score_floored_at_zero():
    """Score 0'ın altına düşmez."""
    t = _clean_thesis(
        decision_permission="WRONG",
        execution_mode="WRONG",
        source_snapshot_ids=[],
    )
    t["paper_trading_context"]["can_open_trade"] = True
    result = validate_agent_thesis(t)
    assert result["score"] >= 0


def test_status_fail_when_critical_present():
    t = _clean_thesis(source_snapshot_ids=[])
    result = validate_agent_thesis(t)
    assert result["status"] == "fail"
    assert result["safe_for_context"] is False


def test_status_degraded_when_only_warnings():
    t = _clean_thesis()
    t["market_view"]["asymmetry_ratio"] = 8.12
    t["data_quality"] = {"status": "degraded", "notes": []}
    result = validate_agent_thesis(t)
    assert result["status"] == "degraded"
    assert result["safe_for_context"] is True  # warning → safe


def test_safe_for_context_false_on_fail():
    t = _clean_thesis(source_snapshot_ids=[])
    result = validate_agent_thesis(t)
    assert result["safe_for_context"] is False


def test_safe_for_context_true_on_pass():
    t = _clean_thesis()
    result = validate_agent_thesis(t)
    assert result["safe_for_context"] is True


def test_safe_for_context_true_on_degraded():
    t = _clean_thesis()
    t["market_view"]["asymmetry_ratio"] = 8.12
    t["data_quality"] = {"status": "degraded", "notes": []}
    result = validate_agent_thesis(t)
    assert result["safe_for_context"] is True


# ── Entegrasyon: thesis içinde thesis_sanity alanı ───────────────────────────

def test_validate_result_has_required_keys():
    result = validate_agent_thesis(_clean_thesis())
    for key in ("status", "score", "issues", "safe_for_context"):
        assert key in result, f"Eksik: {key}"


def test_issues_have_required_fields():
    t = _clean_thesis(source_snapshot_ids=[])
    result = validate_agent_thesis(t)
    for issue in result["issues"]:
        for field in ("severity", "code", "asset", "message"):
            assert field in issue, f"Issue'da eksik: {field}"


def test_severity_values_valid():
    t = _clean_thesis(source_snapshot_ids=[])
    result = validate_agent_thesis(t)
    for issue in result["issues"]:
        assert issue["severity"] in ("critical", "warning")
