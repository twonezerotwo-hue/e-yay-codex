"""
FAZ 6 — Weekly Calibration testleri.

Kapsam:
  - build_weekly_calibration service (not_created, güvenlik, tüm metrikler)
  - learning_signals (8 sinyal kodu, confidence, note)
  - auto_tune_candidates (kurallar, auto_apply_now, min_sample)
  - lookback filtresi (zaman filtresi, kötü tarih dahil)
  - evidence_quality (full/limited/mixed)
  - recommendations (more_data_needed, future_auto_tune)
  - weekly_calibration_store (save/load/limit/corrupt/güvenlik)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.services.weekly_calibration_service import (
    _MIN_SAMPLE,
    build_weekly_calibration,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _memory(
    pair: str = "BTCUSD",
    side: str = "LONG",
    pnl_pct: float = 1.5,
    result: str = "win",
    final_labels: list | None = None,
    labels_seen: list | None = None,
    primary_tf: str = "1h",
    confluence_status: str = "aligned",
    has_candidates: bool = True,
    has_rechecks: bool = True,
    created_at: str | None = None,
) -> dict:
    """Minimal mistake_memory_v1 kaydı üretir (test kolaylığı)."""
    if final_labels is None:
        final_labels = []
    if labels_seen is None:
        labels_seen = []
    if created_at is None:
        created_at = datetime.now(UTC).isoformat()
    return {
        "memory_id":    str(uuid.uuid4()),
        "created_at":   created_at,
        "schema_version": "mistake_memory_v1",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "record_type": "final_memory",
        "is_final":    True,
        "trade": {
            "pair":       pair,
            "side":       side,
            "pnl_pct":    pnl_pct,
            "exit_reason": "take_profit" if result == "win" else "stop_loss",
        },
        "opening_context": {
            "primary_tf":        primary_tf,
            "confluence_status": confluence_status,
        },
        "candidate_evidence": {
            "labels_seen":      labels_seen,
            "evidence_quality": "full" if has_candidates else "limited",
            "candidate_ids":    ["cid1"] if has_candidates else [],
        },
        "recheck_evidence": {
            "recheck_ids":          ["rid1"] if has_rechecks else [],
            "worst_recheck_status": "valid",
        },
        "final_labels": final_labels,
        "final_summary": {
            "result":                result,
            "main_lesson":           "test",
            "should_adjust_weights": False,
            "recommended_review":    "no_action",
        },
    }


def _flabel(code: str, type_: str = "success", severity: str = "low") -> dict:
    return {"code": code, "type": type_, "severity": severity, "reason": "test"}


# ── not_created ────────────────────────────────────────────────────────────────

class TestNotCreated:
    def test_empty_memories_returns_not_created(self):
        r = build_weekly_calibration([], [], [], lookback_days=7)
        assert r["status"] == "not_created"
        assert r["reason"] == "no_memory_records"

    def test_not_created_has_security_fields(self):
        r = build_weekly_calibration([], [], [], lookback_days=7)
        assert r["decision_permission"] == "NO_EXECUTION"
        assert r["execution_mode"] == "PAPER_SAFE"
        assert r["auto_changes_allowed"] is False

    def test_all_old_records_filtered_returns_not_created(self):
        old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        mems = [_memory(created_at=old)]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["status"] == "not_created"


# ── Güvenlik sabitleri ────────────────────────────────────────────────────────

class TestSecurityConstants:
    def test_decision_permission(self):
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        assert r["decision_permission"] == "NO_EXECUTION"

    def test_execution_mode(self):
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        assert r["execution_mode"] == "PAPER_SAFE"

    def test_auto_changes_allowed_false(self):
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        assert r["auto_changes_allowed"] is False

    def test_schema_version(self):
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        assert r["schema_version"] == "weekly_calibration_v1"

    def test_report_type(self):
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        assert r["report_type"] == "performance_learning_report"


# ── Performance ───────────────────────────────────────────────────────────────

class TestPerformance:
    def test_win_rate_two_wins_one_loss(self):
        mems = [
            _memory(pnl_pct=1.0, result="win"),
            _memory(pnl_pct=2.0, result="win"),
            _memory(pnl_pct=-1.0, result="loss"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert abs(r["performance"]["win_rate"] - 2 / 3) < 0.001

    def test_profit_factor(self):
        mems = [
            _memory(pnl_pct=1.0, result="win"),
            _memory(pnl_pct=2.0, result="win"),
            _memory(pnl_pct=-1.0, result="loss"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        # wins_abs=3.0, losses_abs=1.0 → PF=3.0
        assert abs(r["performance"]["profit_factor"] - 3.0) < 0.001

    def test_expectancy_pct(self):
        mems = [
            _memory(pnl_pct=2.0, result="win"),
            _memory(pnl_pct=-1.0, result="loss"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert abs(r["performance"]["expectancy_pct"] - 0.5) < 0.001

    def test_avg_win_avg_loss(self):
        mems = [
            _memory(pnl_pct=3.0, result="win"),
            _memory(pnl_pct=1.0, result="win"),
            _memory(pnl_pct=-2.0, result="loss"),
            _memory(pnl_pct=-4.0, result="loss"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert abs(r["performance"]["avg_win_pct"] - 2.0) < 0.001
        assert abs(r["performance"]["avg_loss_pct"] - (-3.0)) < 0.001

    def test_max_loss_pct(self):
        mems = [
            _memory(pnl_pct=-1.0, result="loss"),
            _memory(pnl_pct=-5.0, result="loss"),
            _memory(pnl_pct=-2.0, result="loss"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["performance"]["max_loss_pct"] == pytest.approx(-5.0)

    def test_total_pnl_pct(self):
        mems = [
            _memory(pnl_pct=2.0, result="win"),
            _memory(pnl_pct=-1.0, result="loss"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert abs(r["performance"]["total_pnl_pct"] - 1.0) < 0.001

    def test_all_breakeven_no_div_zero(self):
        mems = [_memory(pnl_pct=0.0, result="breakeven") for _ in range(3)]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        perf = r["performance"]
        assert perf["win_rate"] == 0.0
        assert perf["profit_factor"] == 0.0
        assert perf["expectancy_pct"] == 0.0


# ── Gruplama ──────────────────────────────────────────────────────────────────

class TestGroupings:
    def test_by_asset_multiple_pairs(self):
        mems = [
            _memory(pair="BTCUSD", pnl_pct=1.0, result="win"),
            _memory(pair="BTCUSD", pnl_pct=-1.0, result="loss"),
            _memory(pair="XAUUSD", pnl_pct=2.0, result="win"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["by_asset"]["BTCUSD"]["trades"] == 2
        assert r["by_asset"]["XAUUSD"]["trades"] == 1

    def test_by_label_count_and_avg_pnl(self):
        fl = [_flabel("good_trade_no_issue")]
        mems = [
            _memory(pnl_pct=1.0, result="win",  final_labels=fl),
            _memory(pnl_pct=3.0, result="win",  final_labels=fl),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        lbl = r["by_label"]["good_trade_no_issue"]
        assert lbl["count"] == 2
        assert abs(lbl["avg_pnl_pct"] - 2.0) < 0.001

    def test_by_timeframe_grouping(self):
        mems = [
            _memory(primary_tf="1h"),
            _memory(primary_tf="1h"),
            _memory(primary_tf="4h"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["by_timeframe"]["1h"]["trades"] == 2
        assert r["by_timeframe"]["4h"]["trades"] == 1

    def test_by_regime_grouping(self):
        mems = [
            _memory(confluence_status="aligned"),
            _memory(confluence_status="aligned"),
            _memory(confluence_status="partial"),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["by_regime"]["aligned"]["trades"] == 2
        assert r["by_regime"]["partial"]["trades"] == 1


# ── Sample + evidence quality ─────────────────────────────────────────────────

class TestSampleAndEvidence:
    def test_sample_counts(self):
        mems  = [_memory() for _ in range(3)]
        cands = [{"candidate_id": "c1", "created_at": datetime.now(UTC).isoformat()}]
        rcks  = [{"recheck_id": "r1",   "created_at": datetime.now(UTC).isoformat()}] * 2
        r = build_weekly_calibration(mems, cands, rcks, lookback_days=7)
        assert r["sample"]["trades"]     == 3
        assert r["sample"]["memories"]   == 3
        assert r["sample"]["candidates"] == 1
        assert r["sample"]["rechecks"]   == 2

    def test_evidence_quality_full(self):
        mems = [_memory(has_candidates=True, has_rechecks=True) for _ in range(5)]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["sample"]["evidence_quality"] == "full"

    def test_evidence_quality_limited(self):
        mems = [_memory(has_candidates=False, has_rechecks=False) for _ in range(5)]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["sample"]["evidence_quality"] == "limited"

    def test_evidence_quality_mixed(self):
        # 2/5 = 40% both present → mixed (25%–60% aralığı)
        mems = [
            _memory(has_candidates=True,  has_rechecks=True),
            _memory(has_candidates=True,  has_rechecks=True),
            _memory(has_candidates=False, has_rechecks=False),
            _memory(has_candidates=False, has_rechecks=False),
            _memory(has_candidates=False, has_rechecks=False),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["sample"]["evidence_quality"] == "mixed"


# ── Learning signals ──────────────────────────────────────────────────────────

class TestLearningSignals:
    def _get_signal(self, r: dict, code: str) -> dict:
        return next(s for s in r["learning_signals"] if s["code"] == code)

    def test_all_eight_signal_codes_present(self):
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        codes = {s["code"] for s in r["learning_signals"]}
        expected = {
            "bearish_pattern_ignored",
            "early_entry_or_failed_1h_signal",
            "confluence_holding_under_pressure",
            "temporary_pullback_possible",
            "news_not_confirmed",
            "stop_too_close_candidate",
            "good_confluence",
            "unexplained_loss",
            # FAZ 11 — advanced technical
            "low_volume_breakout",
            "ema_stack_against_trade",
            "market_structure_broken",
            "vwap_rejection",
            "candle_close_failed",
        }
        assert codes == expected

    def test_bearish_pattern_ignored_confidence(self):
        # 4 loss, 1 win → confidence = 4/5 = 0.80
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["bearish_pattern_ignored"]) for _ in range(4)
        ] + [
            _memory(pnl_pct=1.0, result="win",
                    labels_seen=["bearish_pattern_ignored"])
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        sig = self._get_signal(r, "bearish_pattern_ignored")
        assert sig["seen"]       == 5
        assert sig["wins"]       == 1
        assert sig["losses"]     == 4
        assert sig["confidence"] == pytest.approx(0.80)

    def test_insufficient_sample_confidence_zero(self):
        # 2 < _MIN_SAMPLE=3 → confidence=0.0 + note
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["bearish_pattern_ignored"]) for _ in range(2)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        sig = self._get_signal(r, "bearish_pattern_ignored")
        assert sig["confidence"] == 0.0
        assert sig.get("note") == "not_enough_data"

    def test_unexplained_loss_from_final_labels(self):
        fl = [_flabel("unexplained_loss", "neutral", "medium")]
        mems = [_memory(pnl_pct=-2.0, result="loss", final_labels=fl) for _ in range(3)]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        sig = self._get_signal(r, "unexplained_loss")
        assert sig["seen"]   == 3
        assert sig["losses"] == 3
        assert abs(sig["avg_pnl_pct"] - (-2.0)) < 0.001

    def test_good_confluence_from_final_labels(self):
        # good_confluence maps to "confluence_validated" final label
        fl = [_flabel("confluence_validated")]
        mems = [_memory(pnl_pct=2.0, result="win", final_labels=fl) for _ in range(3)]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        sig = self._get_signal(r, "good_confluence")
        assert sig["seen"] == 3
        assert sig["wins"] == 3

    def test_signal_not_counted_without_matching_data(self):
        # Memory with no labels_seen and no matching final_labels
        r = build_weekly_calibration([_memory()], [], [], lookback_days=7)
        sig = self._get_signal(r, "bearish_pattern_ignored")
        assert sig["seen"] == 0


# ── Auto tune candidates ──────────────────────────────────────────────────────

class TestAutoTuneCandidates:
    def test_auto_apply_now_always_false(self):
        # 5 losses for multiple signals → forces multiple candidates
        mems = [
            _memory(
                pnl_pct=-1.0, result="loss",
                labels_seen=[
                    "bearish_pattern_ignored",
                    "early_entry_or_failed_1h_signal",
                    "stop_too_close_candidate",
                    "news_not_confirmed",
                ],
            )
            for _ in range(5)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        for cand in r["auto_tune_candidates"]:
            assert cand["auto_apply_now"] is False

    def test_position_size_multiplier_candidate_generated(self):
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["bearish_pattern_ignored"]) for _ in range(4)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        targets = [c["target"] for c in r["auto_tune_candidates"]]
        assert "position_size_multiplier" in targets

    def test_candidate_not_generated_below_min_sample(self):
        # Only 2 losses → no candidate
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["bearish_pattern_ignored"]) for _ in range(2)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        targets = [c["target"] for c in r["auto_tune_candidates"]]
        assert "position_size_multiplier" not in targets

    def test_candidate_type_is_parameter_adjustment(self):
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["bearish_pattern_ignored"]) for _ in range(_MIN_SAMPLE + 1)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        for cand in r["auto_tune_candidates"]:
            assert cand["type"] == "parameter_adjustment_candidate"

    def test_min_sample_met_field_true_when_generated(self):
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["stop_too_close_candidate"]) for _ in range(_MIN_SAMPLE + 1)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        stop_cands = [c for c in r["auto_tune_candidates"]
                      if c["target"] == "stop_distance_multiplier"]
        assert stop_cands
        assert stop_cands[0]["min_sample_met"] is True


# ── Lookback filtresi ─────────────────────────────────────────────────────────

class TestLookbackFilter:
    def test_old_record_excluded(self):
        old_ts    = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        recent_ts = datetime.now(UTC).isoformat()
        mems = [
            _memory(pnl_pct=1.0, result="win",  created_at=old_ts),
            _memory(pnl_pct=2.0, result="win",  created_at=recent_ts),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        assert r["sample"]["trades"] == 1

    def test_lookback_zero_includes_all(self):
        old_ts    = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        recent_ts = datetime.now(UTC).isoformat()
        mems = [
            _memory(created_at=old_ts),
            _memory(created_at=recent_ts),
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=0)
        assert r["sample"]["trades"] == 2

    def test_bad_date_record_included(self):
        bad_m = _memory(pnl_pct=1.0, result="win")
        bad_m["created_at"] = "NOT_A_VALID_DATE"
        recent_m = _memory(pnl_pct=2.0, result="win")
        r = build_weekly_calibration([bad_m, recent_m], [], [], lookback_days=7)
        # Kötü tarihli kayıt atlanmaz → 2 trade
        assert r["sample"]["trades"] == 2


# ── Recommendations ───────────────────────────────────────────────────────────

class TestRecommendations:
    def test_more_data_needed_when_small_sample(self):
        mems = [_memory()]  # 1 < _MIN_SAMPLE=3
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        types = [rec["type"] for rec in r["recommendations"]]
        assert "more_data_needed" in types

    def test_future_auto_tune_recommendation_for_safe_proposal(self):
        # 4 losses with 80% loss rate → safe_to_propose=True
        mems = [
            _memory(pnl_pct=-1.0, result="loss",
                    labels_seen=["bearish_pattern_ignored"]) for _ in range(4)
        ]
        r = build_weekly_calibration(mems, [], [], lookback_days=7)
        types = [rec["type"] for rec in r["recommendations"]]
        assert "future_auto_tune" in types


# ── Store ─────────────────────────────────────────────────────────────────────

class TestWeeklyCalibrationStore:
    def test_save_returns_given_id(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "wc.jsonl")
        cid = store.save_weekly_calibration({"calibration_id": "test-id-123"})
        assert cid == "test-id-123"

    def test_save_generates_uuid_if_missing(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "wc.jsonl")
        cid = store.save_weekly_calibration({})
        assert len(cid) == 36  # UUID4 string uzunluğu

    def test_load_returns_saved_records(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "wc.jsonl")
        store.save_weekly_calibration({"calibration_id": "c1"})
        store.save_weekly_calibration({"calibration_id": "c2"})
        records = store.load_recent_weekly_calibrations(limit=10)
        assert len(records) == 2

    def test_load_respects_limit(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "wc.jsonl")
        for i in range(5):
            store.save_weekly_calibration({"calibration_id": f"c{i}"})
        records = store.load_recent_weekly_calibrations(limit=3)
        assert len(records) == 3

    def test_load_limit_zero_returns_all(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "wc.jsonl")
        for i in range(5):
            store.save_weekly_calibration({"calibration_id": f"c{i}"})
        records = store.load_recent_weekly_calibrations(limit=0)
        assert len(records) == 5

    def test_load_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "nonexistent.jsonl")
        assert store.load_recent_weekly_calibrations() == []

    def test_corrupt_line_skipped(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        p = tmp_path / "wc.jsonl"
        monkeypatch.setattr(store, "_STORE_PATH", p)
        p.write_text(
            '{"calibration_id": "c1"}\nNOT_JSON_AT_ALL\n{"calibration_id": "c2"}\n',
            encoding="utf-8",
        )
        records = store.load_recent_weekly_calibrations(limit=10)
        assert len(records) == 2

    def test_security_fields_forced_on_save(self, tmp_path, monkeypatch):
        import app.storage.weekly_calibration_store as store
        monkeypatch.setattr(store, "_STORE_PATH", tmp_path / "wc.jsonl")
        store.save_weekly_calibration({
            "decision_permission":  "EXECUTE",
            "execution_mode":       "LIVE",
            "auto_changes_allowed": True,
        })
        records = store.load_recent_weekly_calibrations()
        r = records[0]
        assert r["decision_permission"]  == "NO_EXECUTION"
        assert r["execution_mode"]       == "PAPER_SAFE"
        assert r["auto_changes_allowed"] is False
