"""
FAZ 7 — Auto Tune testleri.

Kapsam:
  - evaluate: not_eligible (5 durum)
  - evaluate + apply: eligible, proposal üretimi, override yazımı
  - apply: güvenli sınır zorlama (clamp), min/max koruması
  - require_news_confirmation: güvenli şart kontrolü
  - rollback: eski değer geri yükleme, not_available
  - JSONL log: adjustment kaydı
  - Store güvenlik sabitleri: NO_EXECUTION, PAPER_SAFE, BROKER_NOT_CONNECTED
  - Paper trading state: import edilmez
  - Calibration store'dan gerçek kayıt okunur
"""
from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime

import pytest

# ── Calibration kayıt yardımcısı ──────────────────────────────────────────────

def _candidate(
    target: str = "position_size_multiplier",
    condition: str = "LONG + pattern_bearish",
    suggested_change: float | int | str = -0.15,
    min_sample_met: bool = True,
    safe_to_propose: bool = True,
) -> dict:
    return {
        "candidate_id":    str(uuid.uuid4()),
        "type":            "parameter_adjustment_candidate",
        "target":          target,
        "condition":       condition,
        "suggested_change": suggested_change,
        "reason":          f"test candidate for {target}",
        "min_sample_met":  min_sample_met,
        "safe_to_propose": safe_to_propose,
        "auto_apply_now":  False,
    }


def _write_calibration(
    *,
    trades: int = 12,
    memories: int = 12,
    evidence: str = "full",
    candidates: list | None = None,
) -> str:
    """Temp store'a gerçek calibration kaydı yazar; calibration_id döndürür."""
    import app.storage.weekly_calibration_store as wcs

    cid = str(uuid.uuid4())
    record = {
        "calibration_id":      cid,
        "created_at":          datetime.now(UTC).isoformat(),
        "schema_version":      "weekly_calibration_v1",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "auto_changes_allowed": False,
        "report_type":         "performance_learning_report",
        "lookback_days":       7,
        "sample": {
            "trades":           trades,
            "memories":         memories,
            "candidates":       3,
            "rechecks":         2,
            "evidence_quality": evidence,
        },
        "performance": {
            "win_rate": 0.5, "profit_factor": 1.2, "expectancy_pct": 0.3,
            "avg_win_pct": 2.0, "avg_loss_pct": -1.5,
            "max_loss_pct": -3.0, "total_pnl_pct": 4.0,
        },
        "by_asset": {}, "by_label": {}, "by_timeframe": {}, "by_regime": {},
        "learning_signals": [],
        "auto_tune_candidates": candidates or [],
        "risk_notes": [],
        "recommendations": [],
    }
    wcs.save_weekly_calibration(record)
    return cid


@pytest.fixture(autouse=True)
def tmp_stores(tmp_path, monkeypatch):
    """Tüm store yollarını tmp_path'e yönlendir — test izolasyonu."""
    import app.storage.auto_tune_store as ats
    import app.storage.weekly_calibration_store as wcs

    monkeypatch.setattr(ats, "_ADJ_STORE_PATH", tmp_path / "adj.jsonl")
    monkeypatch.setattr(ats, "_OVERRIDES_PATH", tmp_path / "overrides.json")
    monkeypatch.setattr(wcs, "_STORE_PATH", tmp_path / "calibrations.jsonl")

    return tmp_path


# ── Not-eligible durumları ─────────────────────────────────────────────────────

class TestNotEligible:
    def test_no_calibration_not_eligible(self):
        from app.services.auto_tune_service import evaluate_proposals

        r = evaluate_proposals()
        assert r["status"] == "not_eligible"
        assert r["reason"] == "no_calibration"

    def test_low_trades_not_eligible(self):
        from app.services.auto_tune_service import evaluate_proposals

        _write_calibration(trades=8, memories=8)
        r = evaluate_proposals()
        assert r["status"] == "not_eligible"
        assert r["reason"] == "not_enough_trades"

    def test_low_memories_not_eligible(self):
        from app.services.auto_tune_service import evaluate_proposals

        _write_calibration(trades=10, memories=4)
        r = evaluate_proposals()
        assert r["status"] == "not_eligible"
        assert r["reason"] == "not_enough_memories"

    def test_limited_evidence_not_eligible(self):
        from app.services.auto_tune_service import evaluate_proposals

        _write_calibration(trades=12, memories=12, evidence="limited")
        r = evaluate_proposals()
        assert r["status"] == "not_eligible"
        assert r["reason"] == "evidence_limited"

    def test_safe_to_propose_false_not_eligible(self):
        from app.services.auto_tune_service import evaluate_proposals

        cand = _candidate(safe_to_propose=False)
        _write_calibration(candidates=[cand])
        r = evaluate_proposals()
        assert r["status"] == "not_eligible"
        assert r["reason"] == "no_safe_candidates"


# ── Evaluate: eligible ────────────────────────────────────────────────────────

class TestEvaluateEligible:
    def test_bearish_pattern_eligible_returns_proposal(self):
        from app.services.auto_tune_service import evaluate_proposals

        cand = _candidate(
            target="position_size_multiplier",
            suggested_change=-0.15,
            safe_to_propose=True,
        )
        cid = _write_calibration(candidates=[cand])
        r = evaluate_proposals()

        assert r["status"] == "eligible"
        assert r["calibration_id"] == cid
        assert r["proposal_count"] == 1
        proposal = r["proposals"][0]
        assert proposal["target"] == "position_size_multiplier"
        assert proposal["paper_safe"] is True
        assert proposal["broker_action"] == "none"
        assert proposal["live_execution_allowed"] is False

    def test_evaluate_security_fields_in_eligible_response(self):
        from app.services.auto_tune_service import evaluate_proposals

        _write_calibration(candidates=[_candidate()])
        r = evaluate_proposals()

        assert r["decision_permission"]    == "NO_EXECUTION"
        assert r["execution_mode"]         == "PAPER_SAFE"
        assert r["broker_permission"]      == "BROKER_NOT_CONNECTED"
        assert r["live_execution_allowed"] is False

    def test_evaluate_reads_from_calibration_store(self):
        from app.services.auto_tune_service import evaluate_proposals

        # Gerçek calibration kaydı store'a yaz → evaluate onu okumalı
        cid = _write_calibration(candidates=[_candidate(safe_to_propose=True)])
        r = evaluate_proposals()

        assert r["status"] == "eligible"
        assert r["calibration_id"] == cid


# ── Apply: override yazımı ────────────────────────────────────────────────────

class TestApply:
    def test_apply_writes_override_file(self, tmp_path):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides

        _write_calibration(candidates=[_candidate()])
        r = apply_proposals()

        assert r["status"] == "applied"
        assert r["count"] == 1

        overrides = read_overrides()
        assert "position_size_multiplier" in overrides["overrides"]

    def test_apply_override_value_is_within_bounds(self, tmp_path):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides

        cand = _candidate(suggested_change=-0.15)
        _write_calibration(candidates=[cand])
        apply_proposals()

        overrides = read_overrides()
        val = list(overrides["overrides"]["position_size_multiplier"].values())[0]
        # 1.0 + (-0.15) = 0.85 → min=0.70, so 0.85 is within bounds
        assert 0.70 <= val <= 1.15

    def test_single_change_clamped_to_max(self):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides

        # suggested_change=-0.50 fakat max=0.15 → effective=-0.15 → new=0.85
        cand = _candidate(suggested_change=-0.50)
        _write_calibration(candidates=[cand])
        apply_proposals()

        overrides = read_overrides()
        val = list(overrides["overrides"]["position_size_multiplier"].values())[0]
        # old=1.0, effective=-0.15 (clamped) → new=0.85
        assert val == pytest.approx(0.85)

    def test_position_size_multiplier_min_not_exceeded(self):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides, write_overrides

        # Override'ı önce 0.72'ye çek (neredeyse min=0.70)
        initial_overrides = read_overrides()
        initial_overrides["overrides"]["position_size_multiplier"] = {
            "LONG + pattern_bearish": 0.72
        }
        write_overrides(initial_overrides)

        # -0.15 change → 0.72 - 0.15 = 0.57 < min=0.70 → clamp to 0.70
        cand = _candidate(suggested_change=-0.15)
        _write_calibration(candidates=[cand])
        apply_proposals()

        overrides = read_overrides()
        val = overrides["overrides"]["position_size_multiplier"]["LONG + pattern_bearish"]
        assert val >= 0.70

    def test_stop_distance_multiplier_max_not_exceeded(self):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides, write_overrides

        # Override'ı önce 1.25'e çek (max=1.30'a yakın)
        initial = read_overrides()
        initial["overrides"]["stop_distance_multiplier"] = {
            "stop_proximity_ratio < 0.30": 1.25
        }
        write_overrides(initial)

        # +0.20 change → 1.25 + 0.20 = 1.45 > max=1.30 → clamp to 1.30
        cand = _candidate(
            target="stop_distance_multiplier",
            condition="stop_proximity_ratio < 0.30",
            suggested_change=0.20,
        )
        _write_calibration(candidates=[cand])
        apply_proposals()

        overrides = read_overrides()
        val = overrides["overrides"]["stop_distance_multiplier"][
            "stop_proximity_ratio < 0.30"
        ]
        assert val <= 1.30

    def test_entry_confirmation_bars_max_not_exceeded(self):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides, write_overrides

        # Override'ı önce 3'e çek (max=3)
        initial = read_overrides()
        initial["overrides"]["entry_confirmation_bars"] = {
            "primary_tf=1h + 1h_signal_inversion_detected": 3
        }
        write_overrides(initial)

        cand = _candidate(
            target="entry_confirmation_bars",
            condition="primary_tf=1h + 1h_signal_inversion_detected",
            suggested_change=1,
        )
        _write_calibration(candidates=[cand])
        apply_proposals()

        overrides = read_overrides()
        val = overrides["overrides"]["entry_confirmation_bars"][
            "primary_tf=1h + 1h_signal_inversion_detected"
        ]
        assert val <= 3

    def test_require_news_confirmation_requires_safe_conditions(self):
        from app.services.auto_tune_service import evaluate_proposals

        # trades=8 < 10 → eligible değil; news_confirmation uygulanmamalı
        cand = _candidate(
            target="require_news_confirmation",
            condition="entry_without_news_event",
            suggested_change="enable",
            safe_to_propose=True,
        )
        _write_calibration(trades=8, memories=8, candidates=[cand])
        r = evaluate_proposals()
        assert r["status"] == "not_eligible"

    def test_require_news_confirmation_applied_when_eligible(self):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import read_overrides

        cand = _candidate(
            target="require_news_confirmation",
            condition="entry_without_news_event",
            suggested_change="enable",
            safe_to_propose=True,
        )
        _write_calibration(trades=12, memories=12, candidates=[cand])
        r = apply_proposals()

        assert r["status"] == "applied"
        overrides = read_overrides()
        val = overrides["overrides"]["require_news_confirmation"][
            "entry_without_news_event"
        ]
        assert val is True

    def test_apply_security_fields(self):
        from app.services.auto_tune_service import apply_proposals

        _write_calibration(candidates=[_candidate()])
        r = apply_proposals()

        assert r["decision_permission"]    == "NO_EXECUTION"
        assert r["execution_mode"]         == "PAPER_SAFE"
        assert r["broker_permission"]      == "BROKER_NOT_CONNECTED"
        assert r["live_execution_allowed"] is False


# ── Rollback ──────────────────────────────────────────────────────────────────

class TestRollback:
    def test_rollback_restores_old_value(self):
        from app.services.auto_tune_service import apply_proposals, rollback_last_adjustment
        from app.storage.auto_tune_store import read_overrides

        _write_calibration(candidates=[_candidate(suggested_change=-0.15)])
        apply_proposals()

        # Override değeri şu an 0.85 olmalı
        after_apply = read_overrides()
        applied_val = list(
            after_apply["overrides"]["position_size_multiplier"].values()
        )[0]
        assert applied_val == pytest.approx(0.85)

        # Rollback
        rb = rollback_last_adjustment()
        assert rb["status"]             == "rolled_back"
        assert rb["old_value_restored"] == pytest.approx(1.0)  # default geri geldi

        # Override dosyasında değer 1.0 (default) olmalı
        after_rb = read_overrides()
        restored_val = list(
            after_rb["overrides"]["position_size_multiplier"].values()
        )[0]
        assert restored_val == pytest.approx(1.0)

    def test_rollback_not_available_when_no_applied(self):
        from app.services.auto_tune_service import rollback_last_adjustment

        r = rollback_last_adjustment()
        assert r["status"] == "not_available"
        assert r["reason"] == "no_applied_adjustment"

    def test_rollback_after_rollback_returns_not_available(self):
        from app.services.auto_tune_service import apply_proposals, rollback_last_adjustment

        _write_calibration(candidates=[_candidate()])
        apply_proposals()
        rollback_last_adjustment()  # first rollback

        # Second rollback — nothing left to roll back
        r = rollback_last_adjustment()
        assert r["status"] == "not_available"

    def test_rollback_security_fields(self):
        from app.services.auto_tune_service import apply_proposals, rollback_last_adjustment

        _write_calibration(candidates=[_candidate()])
        apply_proposals()
        r = rollback_last_adjustment()

        assert r["decision_permission"]    == "NO_EXECUTION"
        assert r["execution_mode"]         == "PAPER_SAFE"
        assert r["broker_permission"]      == "BROKER_NOT_CONNECTED"
        assert r["live_execution_allowed"] is False


# ── JSONL log ─────────────────────────────────────────────────────────────────

class TestAdjustmentLog:
    def test_apply_writes_adjustment_to_jsonl(self):
        from app.services.auto_tune_service import apply_proposals
        from app.storage.auto_tune_store import load_recent_adjustments

        _write_calibration(candidates=[_candidate()])
        apply_proposals()

        records = load_recent_adjustments()
        assert len(records) == 1
        assert records[0]["status"] == "applied"
        assert records[0]["target"] == "position_size_multiplier"

    def test_rollback_appends_rolled_back_record(self):
        from app.services.auto_tune_service import apply_proposals, rollback_last_adjustment
        from app.storage.auto_tune_store import load_recent_adjustments

        _write_calibration(candidates=[_candidate()])
        apply_proposals()
        rollback_last_adjustment()

        records = load_recent_adjustments()
        assert len(records) == 2
        statuses = [r["status"] for r in records]
        assert "applied"     in statuses
        assert "rolled_back" in statuses


# ── Store güvenlik sabitleri ──────────────────────────────────────────────────

class TestStoreSecurityConstants:
    def test_save_adjustment_forces_no_execution(self, tmp_path):
        from app.storage.auto_tune_store import load_recent_adjustments, save_adjustment

        save_adjustment({
            "decision_permission": "EXECUTE",
            "execution_mode":      "LIVE",
            "status":              "applied",
        })
        records = load_recent_adjustments()
        assert records[0]["decision_permission"] == "NO_EXECUTION"
        assert records[0]["execution_mode"]      == "PAPER_SAFE"

    def test_save_adjustment_forces_broker_not_connected(self, tmp_path):
        from app.storage.auto_tune_store import load_recent_adjustments, save_adjustment

        save_adjustment({
            "broker_permission":      "CONNECTED",
            "live_execution_allowed": True,
            "status":                 "applied",
        })
        records = load_recent_adjustments()
        assert records[0]["broker_permission"]      == "BROKER_NOT_CONNECTED"
        assert records[0]["live_execution_allowed"] is False

    def test_write_overrides_forces_security_fields(self, tmp_path):
        from app.storage.auto_tune_store import read_overrides, write_overrides

        write_overrides({
            "decision_permission":    "EXECUTE",
            "execution_mode":         "LIVE",
            "broker_permission":      "CONNECTED",
            "live_execution_allowed": True,
            "overrides":              {},
        })
        r = read_overrides()
        assert r["decision_permission"]    == "NO_EXECUTION"
        assert r["execution_mode"]         == "PAPER_SAFE"
        assert r["broker_permission"]      == "BROKER_NOT_CONNECTED"
        assert r["live_execution_allowed"] is False


# ── Paper trading etkilenmez ──────────────────────────────────────────────────

class TestPaperTradingUnaffected:
    def test_auto_tune_service_does_not_import_paper_trading(self):
        import app.services.auto_tune_service as svc

        source = inspect.getsource(svc)
        assert "paper_trading_service" not in source
        assert "open_positions"         not in source
        assert "get_snapshot"           not in source
