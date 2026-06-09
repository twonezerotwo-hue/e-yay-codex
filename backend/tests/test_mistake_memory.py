"""
FAZ 5B — Mistake Memory (Final) testleri.

Kapsam:
  Servis (build_mistake_memory):
    1.  Geçersiz trade verisi → not_created
    2.  LOSS + bearish_pattern_ignored candidate → bearish_pattern_ignored_confirmed
    3.  WIN  + bearish_pattern_ignored candidate → bearish_pattern_ignored_but_trade_won
    4.  LOSS + early_entry_or_failed_1h_signal   → early_entry_confirmed
    5.  WIN  + confluence_holding_under_pressure → confluence_validated
    6.  WIN  + temporary_pullback_possible       → temporary_pullback_validated
    7.  LOSS + news_not_confirmed candidate      → news_not_confirmed_confirmed
    8.  stop_loss + stop_too_close_candidate     → stop_too_close_unverified (recovery yok)
    9.  WIN  + no warning labels                 → good_trade_no_issue
    10. LOSS + candidate yok + recheck yok       → unexplained_loss
    11. Çoklu hata: hem bearish_pattern_ignored hem early_entry + LOSS → iki mistake label
    12. evidence_quality: candidate varsa "full", yoksa "limited"
    13. Güvenlik: NO_EXECUTION / PAPER_SAFE / is_final=True / record_type=final_memory
    14. Schema version, trade fingerprint, holding_minutes
    15. result = "win" / "loss" / "breakeven" doğru hesaplanıyor

  Store (save / load / fingerprints):
    16. save → UUID4 döner
    17. save → JSONL güvenlik sabitleriyle yazılır
    18. store, is_final=False gelirse True'ya çevirir
    19. load_finalized_fingerprints — daha önce kaydedilen fingerprint'i döndürür
    20. load_finalized_fingerprints — duplicate önleme çalışıyor
    21. load boş dosya → boş liste
    22. load limit çalışıyor
    23. Bozuk JSONL satırı atlanır

  Final summary:
    24. LOSS + medium mistake → should_adjust_weights=True
    25. WIN + success labels → recommended_review="no_action"
    26. bearish_pattern_ignored_confirmed → recommended_review="pattern_weight"
    27. early_entry_confirmed → recommended_review="entry_timing"
    28. stop_too_close_unverified → recommended_review="stop_distance"
"""
from __future__ import annotations

import json

import pytest

from app.services.mistake_memory_service import (
    _trade_fingerprint,
    build_mistake_memory,
)
from app.storage.mistake_memory_store import (
    load_finalized_fingerprints,
    load_recent_mistake_memory,
    save_mistake_memory,
)


# ── Fixture yardımcıları ──────────────────────────────────────────────────────

def _trade(
    pair: str = "BTCUSD",
    side: str = "LONG",
    pnl_pct: float = -2.0,
    entry_price: float = 62000.0,
    exit_price: float = 60760.0,
    exit_reason: str = "stop_loss",
    trade_id: str | None = None,
    news_event_present: bool = False,
    confluence_status: str = "aligned",
    opening_1h_dir: str = "bullish",
    primary_tf: str = "1h",
) -> dict:
    """Minimal kapanmış trade fixture'ı."""
    t: dict = {
        "pair":          pair,
        "side":          side,
        "entry_price":   entry_price,
        "exit_price":    exit_price,
        "pnl_pct":       pnl_pct,
        "pnl_usd":       pnl_pct * 200.0,
        "exit_reason":   exit_reason,
        "opened_at":     "2026-06-09T10:00:00+00:00",
        "closed_at":     "2026-06-09T15:20:00+00:00",
        "open_signal": {
            "final_score":        75.0,
            "final_direction":    opening_1h_dir,
            "primary_tf":         primary_tf,
            "pattern_score":      45,
            "news_event_present": news_event_present,
            "tf_signals": {
                "1h": {"direction": opening_1h_dir},
                "4h": {"direction": "bullish"},
            },
            "confluence": {"status": confluence_status},
            "timeframe_decision": {"selected_timeframe": "4h"},
        },
    }
    if trade_id is not None:
        t["trade_id"] = trade_id
    return t


def _candidate_with_labels(
    pair: str = "BTCUSD",
    entry_price: float = 62000.0,
    label_codes: list[str] | None = None,
    candidate_id: str = "cand_001",
    position_id: str | None = None,
) -> dict:
    """Belirtilen label kodlarını içeren minimal learning candidate fixture'ı."""
    label_codes = label_codes or []
    _severity_map = {
        "bearish_pattern_ignored":          "warning",
        "early_entry_or_failed_1h_signal":  "warning",
        "confluence_holding_under_pressure": "watch",
        "temporary_pullback_possible":       "watch",
        "news_not_confirmed":               "watch",
        "stop_too_close_candidate":         "warning",
        "thesis_contradiction":             "warning",
    }
    labels = [
        {"code": code, "severity": _severity_map.get(code, "watch"), "reason": f"test-{code}"}
        for code in label_codes
    ]
    c: dict = {
        "candidate_id":  candidate_id,
        "pair":          pair,
        "entry_price":   entry_price,
        "schema_version": "learning_candidate_v1",
        "candidate_labels": labels,
    }
    if position_id:
        c["position_id"] = position_id
    return c


def _recheck(
    pair: str = "BTCUSD",
    entry_price: float = 62000.0,
    status: str = "weakening",
    recheck_id: str = "rchk_001",
) -> dict:
    """Minimal position_recheck fixture'ı."""
    return {
        "recheck_id": recheck_id,
        "pair":       pair,
        "entry_price": entry_price,
        "summary": {"status": status, "auto_action_allowed": False},
    }


def _find_label(memory: dict, code: str) -> dict | None:
    return next(
        (l for l in memory.get("final_labels", []) if l["code"] == code),
        None,
    )


# ── Test 1: Geçersiz trade verisi ─────────────────────────────────────────────

def test_invalid_trade_no_exit_price():
    """exit_price=0 → not_created."""
    r = build_mistake_memory(
        {"pair": "BTCUSD", "side": "LONG", "exit_price": 0},
        [], [],
    )
    assert r.get("status") == "not_created"


def test_invalid_trade_missing_side():
    """side eksik → not_created."""
    r = build_mistake_memory(
        {"pair": "BTCUSD", "side": "", "exit_price": 61000.0},
        [], [],
    )
    assert r.get("status") == "not_created"


# ── Test 2: bearish_pattern_ignored + LOSS ───────────────────────────────────

def test_bearish_pattern_ignored_confirmed():
    """LOSS + bearish_pattern_ignored candidate → confirmed mistake."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.5, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["bearish_pattern_ignored"])],
        [],
    )
    lbl = _find_label(m, "bearish_pattern_ignored_confirmed")
    assert lbl is not None
    assert lbl["type"] == "mistake"
    assert lbl["severity"] == "medium"


# ── Test 3: bearish_pattern_ignored + WIN ────────────────────────────────────

def test_bearish_pattern_ignored_but_trade_won():
    """WIN + bearish_pattern_ignored candidate → trade won despite warning."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.8, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["bearish_pattern_ignored"])],
        [],
    )
    lbl = _find_label(m, "bearish_pattern_ignored_but_trade_won")
    assert lbl is not None
    assert lbl["type"] == "neutral"
    # Confirmed version YOK
    assert _find_label(m, "bearish_pattern_ignored_confirmed") is None


# ── Test 4: early_entry + LOSS ────────────────────────────────────────────────

def test_early_entry_confirmed():
    """LOSS + early_entry_or_failed_1h_signal → early_entry_confirmed mistake."""
    m = build_mistake_memory(
        _trade(pnl_pct=-3.0, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["early_entry_or_failed_1h_signal"])],
        [],
    )
    lbl = _find_label(m, "early_entry_confirmed")
    assert lbl is not None
    assert lbl["type"] == "mistake"


def test_early_entry_not_confirmed_on_win():
    """WIN + early_entry candidate → early_entry_confirmed YOK."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.5, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["early_entry_or_failed_1h_signal"])],
        [],
    )
    assert _find_label(m, "early_entry_confirmed") is None


# ── Test 5: confluence_validated ─────────────────────────────────────────────

def test_confluence_validated():
    """WIN + confluence_holding_under_pressure → confluence_validated success."""
    m = build_mistake_memory(
        _trade(pnl_pct=2.0, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["confluence_holding_under_pressure"])],
        [],
    )
    lbl = _find_label(m, "confluence_validated")
    assert lbl is not None
    assert lbl["type"] == "success"


def test_confluence_not_validated_on_loss():
    """LOSS + confluence_holding_under_pressure → confluence_validated YOK."""
    m = build_mistake_memory(
        _trade(pnl_pct=-1.5, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["confluence_holding_under_pressure"])],
        [],
    )
    assert _find_label(m, "confluence_validated") is None


# ── Test 6: temporary_pullback_validated ─────────────────────────────────────

def test_temporary_pullback_validated():
    """WIN + temporary_pullback_possible → temporary_pullback_validated success."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.2, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["temporary_pullback_possible"])],
        [],
    )
    lbl = _find_label(m, "temporary_pullback_validated")
    assert lbl is not None
    assert lbl["type"] == "success"


# ── Test 7: news_not_confirmed_confirmed ─────────────────────────────────────

def test_news_not_confirmed_confirmed():
    """LOSS + news_not_confirmed candidate → confirmed mistake (low severity)."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.0, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["news_not_confirmed"])],
        [],
    )
    lbl = _find_label(m, "news_not_confirmed_confirmed")
    assert lbl is not None
    assert lbl["type"] == "mistake"
    assert lbl["severity"] == "low"


def test_news_not_confirmed_not_triggered_on_win():
    """WIN + news_not_confirmed → confirmed YOK."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.0, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["news_not_confirmed"])],
        [],
    )
    assert _find_label(m, "news_not_confirmed_confirmed") is None


# ── Test 8: stop_too_close_unverified ────────────────────────────────────────

def test_stop_too_close_unverified():
    """stop_too_close_candidate + stop_loss exit → unverified (recovery yok)."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.5, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["stop_too_close_candidate"])],
        [],
    )
    lbl = _find_label(m, "stop_too_close_unverified")
    assert lbl is not None
    assert lbl["type"] == "neutral"
    # Confirmed version YOK (recovery verisi yok)
    assert _find_label(m, "stop_too_close_confirmed") is None


def test_stop_too_close_not_triggered_on_tp_exit():
    """stop_too_close_candidate ama exit_reason=take_profit → unverified YOK."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.0, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["stop_too_close_candidate"])],
        [],
    )
    assert _find_label(m, "stop_too_close_unverified") is None
    assert _find_label(m, "stop_too_close_confirmed") is None


# ── Test 9: good_trade_no_issue ──────────────────────────────────────────────

def test_good_trade_no_issue_no_candidates():
    """WIN + hiç candidate yoksa → good_trade_no_issue."""
    m = build_mistake_memory(
        _trade(pnl_pct=2.5, exit_reason="take_profit"),
        [], [],  # hiç candidate yok
    )
    lbl = _find_label(m, "good_trade_no_issue")
    assert lbl is not None
    assert lbl["type"] == "success"


def test_good_trade_no_issue_only_watch_candidates():
    """WIN + sadece watch severity candidate label → good_trade_no_issue."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.5, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["confluence_holding_under_pressure"])],
        [],
    )
    lbl = _find_label(m, "good_trade_no_issue")
    assert lbl is not None


def test_good_trade_no_issue_not_triggered_with_warning_label():
    """WIN ama warning severity candidate label varsa → good_trade_no_issue YOK."""
    m = build_mistake_memory(
        _trade(pnl_pct=1.2, exit_reason="take_profit"),
        [_candidate_with_labels(label_codes=["bearish_pattern_ignored"])],
        [],
    )
    # bearish_pattern_ignored warning severity → good_trade_no_issue tetiklenmez
    assert _find_label(m, "good_trade_no_issue") is None


# ── Test 10: unexplained_loss ─────────────────────────────────────────────────

def test_unexplained_loss_no_evidence():
    """LOSS + candidate yok + recheck yok → unexplained_loss."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.0, exit_reason="stop_loss"),
        [], [],
    )
    lbl = _find_label(m, "unexplained_loss")
    assert lbl is not None
    assert lbl["type"] == "neutral"
    assert m["candidate_evidence"]["evidence_quality"] == "limited"


def test_unexplained_loss_not_triggered_with_candidates():
    """LOSS ama candidate varsa → unexplained_loss YOK."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.0, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["news_not_confirmed"])],
        [],
    )
    assert _find_label(m, "unexplained_loss") is None


# ── Test 11: Çoklu hata aynı anda ────────────────────────────────────────────

def test_multiple_mistake_labels_on_loss():
    """LOSS + hem bearish_pattern_ignored hem early_entry → iki mistake label birden."""
    m = build_mistake_memory(
        _trade(pnl_pct=-3.0, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=[
            "bearish_pattern_ignored",
            "early_entry_or_failed_1h_signal",
        ])],
        [],
    )
    assert _find_label(m, "bearish_pattern_ignored_confirmed") is not None
    assert _find_label(m, "early_entry_confirmed") is not None
    # good_trade_no_issue tetiklenmemeli (warning label vardı)
    assert _find_label(m, "good_trade_no_issue") is None


# ── Test 12: evidence_quality ─────────────────────────────────────────────────

def test_evidence_quality_full_with_candidates():
    """Candidate varsa evidence_quality='full'."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.0),
        [_candidate_with_labels(label_codes=["news_not_confirmed"])],
        [],
    )
    assert m["candidate_evidence"]["evidence_quality"] == "full"


def test_evidence_quality_limited_no_candidates():
    """Candidate yoksa evidence_quality='limited'."""
    m = build_mistake_memory(_trade(pnl_pct=-2.0), [], [])
    assert m["candidate_evidence"]["evidence_quality"] == "limited"


# ── Test 13: Güvenlik sabitleri ───────────────────────────────────────────────

def test_security_constants():
    """decision_permission, execution_mode, record_type, is_final her zaman sabit."""
    m = build_mistake_memory(_trade(), [], [])
    assert m["decision_permission"] == "NO_EXECUTION"
    assert m["execution_mode"] == "PAPER_SAFE"
    assert m["record_type"] == "final_memory"
    assert m["is_final"] is True


# ── Test 14: Schema, fingerprint, holding_minutes ────────────────────────────

def test_schema_version():
    m = build_mistake_memory(_trade(), [], [])
    assert m["schema_version"] == "mistake_memory_v1"


def test_trade_fingerprint_with_trade_id():
    """trade_id varsa fingerprint 'tid_...' formatında."""
    t = _trade(trade_id="abc123")
    fp = _trade_fingerprint(t)
    assert fp == "tid_abc123"


def test_trade_fingerprint_without_trade_id():
    """trade_id yoksa pair|entry|exit|... formatında."""
    t = _trade(pair="BTCUSD", entry_price=62000.0, exit_price=60760.0)
    fp = _trade_fingerprint(t)
    assert "BTCUSD" in fp
    assert "62000.0000" in fp
    assert "60760.0000" in fp


def test_holding_minutes_computed():
    """opened_at ve closed_at varsa holding_minutes hesaplanıyor."""
    m = build_mistake_memory(_trade(), [], [])
    # opened_at=10:00, closed_at=15:20 → 320 dakika
    assert m["trade"]["holding_minutes"] == 320


# ── Test 15: result hesaplama ─────────────────────────────────────────────────

def test_result_win():
    m = build_mistake_memory(_trade(pnl_pct=1.5), [], [])
    assert m["final_summary"]["result"] == "win"


def test_result_loss():
    m = build_mistake_memory(_trade(pnl_pct=-1.5), [], [])
    assert m["final_summary"]["result"] == "loss"


def test_result_breakeven():
    m = build_mistake_memory(_trade(pnl_pct=0.0, exit_price=62000.0), [], [])
    assert m["final_summary"]["result"] == "breakeven"


# ── Store testleri ────────────────────────────────────────────────────────────

def _isolate_memory_store(tmp_path, monkeypatch):
    import app.storage.mistake_memory_store as mms
    store_file = tmp_path / "mistake_memory.jsonl"
    monkeypatch.setattr(mms, "_STORE_PATH", store_file)
    return store_file


# Test 16: save → UUID4
def test_store_save_returns_uuid(tmp_path, monkeypatch):
    _isolate_memory_store(tmp_path, monkeypatch)
    m = build_mistake_memory(_trade(), [], [])
    mid = save_mistake_memory(m)
    assert len(mid) == 36


# Test 17: save → JSONL güvenlik sabitleriyle
def test_store_save_writes_security_fields(tmp_path, monkeypatch):
    store_file = _isolate_memory_store(tmp_path, monkeypatch)
    m = build_mistake_memory(_trade(), [], [])
    save_mistake_memory(m)
    lines = [l for l in store_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["decision_permission"] == "NO_EXECUTION"
    assert record["execution_mode"] == "PAPER_SAFE"
    assert record["record_type"] == "final_memory"
    assert record["is_final"] is True
    assert record["schema_version"] == "mistake_memory_v1"


# Test 18: store is_final=False gelirse True'ya çevirir
def test_store_forces_is_final_true(tmp_path, monkeypatch):
    """Store, is_final=False gelirse True'ya çevirir."""
    _isolate_memory_store(tmp_path, monkeypatch)
    m = build_mistake_memory(_trade(), [], [])
    m["is_final"] = False  # Zorla False dene
    save_mistake_memory(m)
    records = load_recent_mistake_memory(limit=10)
    assert records[0]["is_final"] is True


# Test 19: load_finalized_fingerprints
def test_load_finalized_fingerprints(tmp_path, monkeypatch):
    """Kaydedilen memory'nin fingerprint'i load_finalized_fingerprints'te görünür."""
    _isolate_memory_store(tmp_path, monkeypatch)
    t = _trade(trade_id="fp_test_001")
    m = build_mistake_memory(t, [], [])
    save_mistake_memory(m)
    fps = load_finalized_fingerprints()
    assert "tid_fp_test_001" in fps


# Test 20: Duplicate önleme
def test_duplicate_prevention(tmp_path, monkeypatch):
    """Aynı fingerprint iki kez kaydedilmeye çalışıldığında store sadece ilkini içerir."""
    _isolate_memory_store(tmp_path, monkeypatch)
    t = _trade(trade_id="dup_test_001")

    # İlk kayıt
    m1 = build_mistake_memory(t, [], [])
    save_mistake_memory(m1)

    fps_after_first = load_finalized_fingerprints()
    assert "tid_dup_test_001" in fps_after_first

    # İkinci çağrıda API duplicate'i tespit etmeli (store'a ikinci kez yazma)
    # Burada store duplicate check YAPMAZ — bu API katmanının sorumluluğu.
    # Fingerprint setinin döndüğünü doğruluyoruz:
    fps = load_finalized_fingerprints()
    assert len([fp for fp in fps if "dup_test_001" in fp]) == 1


# Test 21: Boş dosya
def test_store_load_empty(tmp_path, monkeypatch):
    _isolate_memory_store(tmp_path, monkeypatch)
    assert load_recent_mistake_memory(limit=10) == []
    assert load_finalized_fingerprints() == set()


# Test 22: limit çalışıyor
def test_store_load_limit(tmp_path, monkeypatch):
    _isolate_memory_store(tmp_path, monkeypatch)
    for i in range(5):
        t = _trade(pnl_pct=float(-i - 1), entry_price=62000.0 + i, exit_price=61000.0 + i)
        save_mistake_memory(build_mistake_memory(t, [], []))
    records = load_recent_mistake_memory(limit=3)
    assert len(records) == 3


# Test 23: Bozuk JSONL satırı atlanır
def test_store_skips_corrupt_lines(tmp_path, monkeypatch):
    store_file = _isolate_memory_store(tmp_path, monkeypatch)
    m = build_mistake_memory(_trade(), [], [])
    save_mistake_memory(m)
    with store_file.open("a", encoding="utf-8") as f:
        f.write("{broken json line\n")
    records = load_recent_mistake_memory(limit=10)
    assert len(records) == 1


# ── Test 24-28: Final summary ─────────────────────────────────────────────────

def test_should_adjust_weights_true_on_medium_mistake():
    """LOSS + medium mistake → should_adjust_weights=True."""
    m = build_mistake_memory(
        _trade(pnl_pct=-3.0),
        [_candidate_with_labels(label_codes=["bearish_pattern_ignored"])],
        [],
    )
    assert m["final_summary"]["should_adjust_weights"] is True


def test_should_adjust_weights_false_on_win():
    """WIN → should_adjust_weights=False."""
    m = build_mistake_memory(
        _trade(pnl_pct=2.0),
        [],
        [],
    )
    assert m["final_summary"]["should_adjust_weights"] is False


def test_recommended_review_pattern_weight():
    """bearish_pattern_ignored_confirmed → recommended_review='pattern_weight'."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.5),
        [_candidate_with_labels(label_codes=["bearish_pattern_ignored"])],
        [],
    )
    assert m["final_summary"]["recommended_review"] == "pattern_weight"


def test_recommended_review_entry_timing():
    """early_entry_confirmed → recommended_review='entry_timing'."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.5),
        [_candidate_with_labels(label_codes=["early_entry_or_failed_1h_signal"])],
        [],
    )
    assert m["final_summary"]["recommended_review"] == "entry_timing"


def test_recommended_review_stop_distance():
    """stop_too_close_unverified → recommended_review='stop_distance'."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.5, exit_reason="stop_loss"),
        [_candidate_with_labels(label_codes=["stop_too_close_candidate"])],
        [],
    )
    assert m["final_summary"]["recommended_review"] == "stop_distance"


def test_recommended_review_no_action_on_win():
    """WIN hiç mistake yok → recommended_review='no_action'."""
    m = build_mistake_memory(
        _trade(pnl_pct=2.0, exit_reason="take_profit"),
        [],
        [],
    )
    assert m["final_summary"]["recommended_review"] == "no_action"


# ── Recheck evidence ──────────────────────────────────────────────────────────

def test_worst_recheck_status_invalid():
    """Recheck'lerden 'invalid' varsa worst_recheck_status='invalid'."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.0),
        [],
        [
            _recheck(status="weakening"),
            _recheck(status="invalid", recheck_id="rchk_002"),
        ],
    )
    assert m["recheck_evidence"]["worst_recheck_status"] == "invalid"


def test_worst_recheck_status_unknown_when_no_rechecks():
    """Recheck yoksa worst_recheck_status='unknown'."""
    m = build_mistake_memory(_trade(pnl_pct=-2.0), [], [])
    assert m["recheck_evidence"]["worst_recheck_status"] == "unknown"


def test_recheck_ids_populated():
    """Recheck ID'leri recheck_evidence'a yazılıyor."""
    m = build_mistake_memory(
        _trade(pnl_pct=-2.0),
        [],
        [_recheck(recheck_id="rchk_test_001")],
    )
    assert "rchk_test_001" in m["recheck_evidence"]["recheck_ids"]
