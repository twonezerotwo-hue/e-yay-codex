"""
FAZ 4 — Position Recheck testleri.

Kapsam:
  Servis (build_position_recheck):
    Kural 1: one_hour_structure — LONG bullish açılış + 1H BEARISH → fail
    Kural 2: higher_tf_alignment — confluence aligned + 4H/1D tersine → warn
    Kural 3: pattern_vs_pnl — ters pattern + PnL negatif → warn
    Kural 4: hold_watch modifier — PnL negatif ama 4H/1D destekliyor
    Kural 5: multi_tf_in_loss — PnL negatif + 1H+4H bearish → fail
    Kural 6: thesis_pair_context — avoid bias → warn
    Kural 7: thesis_pair_context — thesis yok → unknown
    Kural 8: snapshot yok → current_context unknown, fake veri yok
    Kural 9+10: auto_action_allowed = False zorunlu
    Güvenlik: NO_EXECUTION / PAPER_SAFE
  Store (save/load):
    Kayıt format, append, limit, bozuk satır, güvenlik zorlaması
"""
from __future__ import annotations

import json

import pytest

from app.services.position_recheck_service import build_position_recheck
from app.storage.position_recheck_store import (
    load_recent_position_rechecks,
    save_position_recheck,
)


# ── Fixture yardımcıları ──────────────────────────────────────────────────────

def _pos(
    pair: str = "BTCUSD",
    side: str = "LONG",
    pnl_pct: float = -1.5,
    entry_price: float = 62000.0,
    current_price: float = 61000.0,
    opening_1h_dir: str = "bullish",
    opening_4h_dir: str = "bullish",
    confluence_status: str = "aligned",
) -> dict:
    """Minimal açık pozisyon fixture'ı."""
    return {
        "pair":          pair,
        "side":          side,
        "entry_price":   entry_price,
        "current_price": current_price,
        "pnl_pct":       pnl_pct,
        "size_usd":      19000.0,
        "open_signal": {
            "final_score":     75.0,
            "final_direction": opening_1h_dir,
            "primary_tf":      "1h",
            "tf_signals": {
                "1h": {"direction": opening_1h_dir},
                "4h": {"direction": opening_4h_dir},
                "1d": {"direction": opening_4h_dir},
            },
            "confluence": {
                "status":       confluence_status,
                "tf_directions": {"4h": opening_4h_dir, "1d": opening_4h_dir},
            },
            "timeframe_decision": {"selected_timeframe": "4h"},
        },
    }


def _snap(
    pair: str = "BTCUSD",
    tf_1h: str = "BULLISH",
    tf_4h: str = "BULLISH",
    tf_1d: str = "BULLISH",
    asset_status: str = "PENDING",
    regime: str = "TRANSITIONING",
    appetite: str = "MODERATE",
) -> dict:
    """Minimal hourly snapshot fixture'ı."""
    return {
        "snapshot_id": "snap_test_001",
        "report": {
            "macro_layer":    {"regime": regime},
            "appetite_layer": {"status": appetite},
            "asset_signals":  [{"asset_code": pair, "status": asset_status, "reason": "test"}],
        },
        "mtf": {
            pair: {
                "1h": {"structure": tf_1h, "technical_score": 50},
                "4h": {"structure": tf_4h, "technical_score": 50},
                "1d": {"structure": tf_1d, "technical_score": 50},
            }
        },
    }


def _thesis(
    pair: str = "BTCUSD",
    bias: str = "watch",
    safe_for_context: bool = True,
) -> dict:
    """Minimal safe thesis fixture'ı."""
    return {
        "thesis_id":           "thesis_test_001",
        "created_at":          "2026-06-09T00:00:00+00:00",
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "source_snapshot_ids": ["snap1"],
        "market_view": {
            "primary_bias":       "mixed",
            "regime_view":        "TRANSITIONING",
            "risk_appetite_view": "MODERATE",
        },
        "asset_bias": {
            pair: {
                "bias":           bias,
                "reason":         "test",
                "contradictions": [],
                "mtf_structures": {},
            }
        },
        "paper_trading_context": {"permission": "context_only", "can_open_trade": False},
        "thesis_sanity": {
            "status":           "pass" if safe_for_context else "fail",
            "score":            100 if safe_for_context else 0,
            "issues":           [],
            "safe_for_context": safe_for_context,
        },
    }


def _find_check(recheck: dict, code: str) -> dict | None:
    return next((c for c in recheck.get("checks", []) if c["code"] == code), None)


# ── Kural 1: one_hour_structure ───────────────────────────────────────────────

def test_long_bullish_open_1h_bearish_fails():
    """LONG açılış bullish + 1H şimdi BEARISH → one_hour_structure=fail."""
    r = build_position_recheck(
        _pos(side="LONG", pnl_pct=-1.5, opening_1h_dir="bullish"),
        _snap(tf_1h="BEARISH"),
        None,
    )
    chk = _find_check(r, "one_hour_structure")
    assert chk is not None
    assert chk["status"] == "fail"


def test_long_bullish_open_1h_still_bullish_passes():
    """LONG açılış bullish + 1H hâlâ BULLISH → one_hour_structure=pass."""
    r = build_position_recheck(
        _pos(side="LONG", pnl_pct=0.5, opening_1h_dir="bullish"),
        _snap(tf_1h="BULLISH"),
        None,
    )
    chk = _find_check(r, "one_hour_structure")
    assert chk is not None
    assert chk["status"] == "pass"


def test_short_bearish_open_1h_bullish_fails():
    """SHORT açılış bearish + 1H şimdi BULLISH → one_hour_structure=fail."""
    r = build_position_recheck(
        _pos(side="SHORT", pnl_pct=-2.0, opening_1h_dir="bearish"),
        _snap(tf_1h="BULLISH"),
        None,
    )
    chk = _find_check(r, "one_hour_structure")
    assert chk is not None
    assert chk["status"] == "fail"


# ── Kural 2: higher_tf_alignment ─────────────────────────────────────────────

def test_confluence_aligned_4h_bearish_warns():
    """Açılışta confluence aligned + 4H şimdi BEARISH → higher_tf_alignment=warn."""
    r = build_position_recheck(
        _pos(side="LONG", confluence_status="aligned"),
        _snap(tf_4h="BEARISH", tf_1d="BULLISH"),
        None,
    )
    chk = _find_check(r, "higher_tf_alignment")
    assert chk is not None
    assert chk["status"] == "warn"


def test_confluence_aligned_4h_1d_bullish_passes():
    """Açılışta confluence aligned + 4H ve 1D hâlâ BULLISH → higher_tf_alignment=pass."""
    r = build_position_recheck(
        _pos(side="LONG", confluence_status="aligned"),
        _snap(tf_4h="BULLISH", tf_1d="BULLISH"),
        None,
    )
    chk = _find_check(r, "higher_tf_alignment")
    assert chk is not None
    assert chk["status"] == "pass"


def test_confluence_not_aligned_skips_higher_tf_check():
    """Açılışta confluence aligned değildi → higher_tf_alignment=pass (beklenti yok)."""
    r = build_position_recheck(
        _pos(side="LONG", confluence_status="partial"),
        _snap(tf_4h="BEARISH"),
        None,
    )
    chk = _find_check(r, "higher_tf_alignment")
    assert chk is not None
    assert chk["status"] == "pass"


# ── Kural 3: pattern_vs_pnl ──────────────────────────────────────────────────

def test_bearish_pattern_pnl_negative_warns():
    """LONG açılış ama 1H signal bearish (ters pattern) + PnL negatif → warn."""
    pos = _pos(side="LONG", pnl_pct=-2.5, opening_1h_dir="bearish", opening_4h_dir="bullish")
    # opening_1h_dir='bearish' → pattern_bias='bearish' for LONG → rule 3 triggers
    r = build_position_recheck(pos, _snap(tf_1h="BEARISH"), None)
    chk = _find_check(r, "pattern_vs_pnl")
    assert chk is not None
    assert chk["status"] == "warn"


def test_bearish_pattern_pnl_positive_no_warn():
    """LONG açılış bearish pattern ama PnL pozitif → pattern_vs_pnl=pass."""
    pos = _pos(side="LONG", pnl_pct=1.5, opening_1h_dir="bearish", opening_4h_dir="bullish")
    r = build_position_recheck(pos, _snap(tf_1h="BEARISH"), None)
    chk = _find_check(r, "pattern_vs_pnl")
    assert chk is not None
    assert chk["status"] == "pass"


# ── Kural 4: hold_watch modifier ─────────────────────────────────────────────

def test_pnl_negative_4h_1d_support_hold_watch():
    """PnL negatif ama 4H ve 1D BULLISH → recommended_action=hold_watch (kural 4)."""
    r = build_position_recheck(
        # 1H bearish tetikler fail, ama 4H+1D bullish → hold_watch
        _pos(side="LONG", pnl_pct=-1.0, opening_1h_dir="bullish"),
        _snap(tf_1h="BEARISH", tf_4h="BULLISH", tf_1d="BULLISH"),
        None,
    )
    assert r["summary"]["recommended_action"] == "hold_watch"
    assert r["summary"]["auto_action_allowed"] is False


def test_pnl_negative_1d_bearish_consider_review():
    """PnL negatif + 1D BEARISH → 4H/1D tam destek değil → consider_manual_review."""
    r = build_position_recheck(
        _pos(side="LONG", pnl_pct=-2.0, opening_1h_dir="bullish"),
        _snap(tf_1h="BEARISH", tf_4h="BULLISH", tf_1d="BEARISH"),
        None,
    )
    assert r["summary"]["recommended_action"] == "consider_manual_review"


# ── Kural 5: multi_tf_in_loss ────────────────────────────────────────────────

def test_multi_tf_bearish_in_loss_fails():
    """PnL negatif + 1H BEARISH + 4H BEARISH → multi_tf_in_loss=fail + invalid."""
    r = build_position_recheck(
        _pos(side="LONG", pnl_pct=-3.0, opening_1h_dir="bullish"),
        _snap(tf_1h="BEARISH", tf_4h="BEARISH", tf_1d="NEUTRAL"),
        None,
    )
    chk = _find_check(r, "multi_tf_in_loss")
    assert chk is not None
    assert chk["status"] == "fail"
    assert r["summary"]["status"] == "invalid"
    assert r["summary"]["recommended_action"] == "consider_manual_review"


def test_pnl_negative_4h_neutral_no_multi_tf_fail():
    """PnL negatif + 1H BEARISH ama 4H NEUTRAL → multi_tf_in_loss=pass."""
    r = build_position_recheck(
        _pos(side="LONG", pnl_pct=-1.5, opening_1h_dir="bullish"),
        _snap(tf_1h="BEARISH", tf_4h="NEUTRAL"),
        None,
    )
    chk = _find_check(r, "multi_tf_in_loss")
    assert chk is not None
    assert chk["status"] == "pass"


# ── Kural 6 + 7: thesis_pair_context ─────────────────────────────────────────

def test_thesis_avoid_pair_warns():
    """Safe thesis 'avoid' bias → thesis_pair_context=warn."""
    r = build_position_recheck(
        _pos(pair="BTCUSD"),
        _snap(),
        _thesis(pair="BTCUSD", bias="avoid"),
    )
    chk = _find_check(r, "thesis_pair_context")
    assert chk is not None
    assert chk["status"] == "warn"


def test_thesis_watch_pair_passes():
    """Safe thesis 'watch' bias → thesis_pair_context=pass."""
    r = build_position_recheck(
        _pos(pair="BTCUSD"),
        _snap(),
        _thesis(pair="BTCUSD", bias="watch"),
    )
    chk = _find_check(r, "thesis_pair_context")
    assert chk is not None
    assert chk["status"] == "pass"


def test_no_thesis_context_unknown():
    """Thesis yok → thesis_pair_context=unknown (fail değil)."""
    r = build_position_recheck(_pos(), _snap(), None)
    chk = _find_check(r, "thesis_pair_context")
    assert chk is not None
    assert chk["status"] == "unknown"
    # unknown tek başına summary'i fail yapmamalı
    assert r["summary"]["status"] != "invalid"


# ── Kural 8: snapshot yok ────────────────────────────────────────────────────

def test_no_snapshot_current_context_unknown():
    """Snapshot yok → current_context fields hepsi unknown — fake veri üretilmez."""
    r = build_position_recheck(_pos(), None, None)
    assert r.get("status") != "not_created"   # recheck üretildi ama
    ctx = r["current_context"]
    assert ctx["latest_snapshot_id"] is None
    assert ctx["mtf"] == {}
    assert ctx["macro_regime"] == "UNKNOWN"
    assert ctx["risk_appetite"] == "UNKNOWN"


def test_no_snapshot_all_checks_unknown():
    """Snapshot yok → MTF içeren tüm check'ler unknown."""
    r = build_position_recheck(_pos(), None, None)
    for code in ("one_hour_structure", "higher_tf_alignment", "multi_tf_in_loss"):
        chk = _find_check(r, code)
        assert chk is not None, f"{code} check eksik"
        assert chk["status"] == "unknown", f"{code} unknown olmalıydı, {chk['status']!r} geldi"


def test_invalid_position_returns_not_created():
    """Pair veya side yoksa not_created döner."""
    r = build_position_recheck({"pair": "", "side": "LONG"}, None, None)
    assert r.get("status") == "not_created"

    r2 = build_position_recheck({"pair": "BTCUSD", "side": "UNKNOWN"}, None, None)
    assert r2.get("status") == "not_created"


# ── Kural 9 + 10: auto_action_allowed = False ────────────────────────────────

def test_auto_action_always_false_in_service():
    """build_position_recheck: summary.auto_action_allowed her zaman False."""
    for scenario in [
        _pos(side="LONG", pnl_pct=2.0),        # kârlı
        _pos(side="LONG", pnl_pct=-5.0),       # zararlı
        _pos(side="SHORT", pnl_pct=-1.0),      # short zararlı
    ]:
        r = build_position_recheck(scenario, _snap(), _thesis())
        assert r["summary"]["auto_action_allowed"] is False


# ── Güvenlik: NO_EXECUTION / PAPER_SAFE ──────────────────────────────────────

def test_security_constants_in_recheck():
    """decision_permission ve execution_mode her zaman sabit."""
    r = build_position_recheck(_pos(), _snap(), _thesis())
    assert r["decision_permission"] == "NO_EXECUTION"
    assert r["execution_mode"] == "PAPER_SAFE"


def test_schema_version():
    r = build_position_recheck(_pos(), _snap(), None)
    assert r["schema_version"] == "position_recheck_v1"


# ── Store: save / load ────────────────────────────────────────────────────────

def _isolate_recheck_store(tmp_path, monkeypatch):
    import app.storage.position_recheck_store as rcs
    store_file = tmp_path / "position_rechecks.jsonl"
    monkeypatch.setattr(rcs, "_STORE_PATH", store_file)
    return store_file


def test_store_save_returns_uuid(tmp_path, monkeypatch):
    _isolate_recheck_store(tmp_path, monkeypatch)
    recheck = build_position_recheck(_pos(), _snap(), None)
    rid = save_position_recheck(recheck)
    assert len(rid) == 36  # UUID4


def test_store_save_writes_jsonl(tmp_path, monkeypatch):
    store_file = _isolate_recheck_store(tmp_path, monkeypatch)
    recheck = build_position_recheck(_pos(), _snap(), None)
    save_position_recheck(recheck)
    lines = [l for l in store_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["schema_version"] == "position_recheck_v1"
    assert record["decision_permission"] == "NO_EXECUTION"
    assert record["execution_mode"] == "PAPER_SAFE"


def test_store_forces_auto_action_false(tmp_path, monkeypatch):
    """Store, auto_action_allowed=True gelirse False'a çevirir."""
    _isolate_recheck_store(tmp_path, monkeypatch)
    recheck = build_position_recheck(_pos(), _snap(), None)
    # Zorla True dene (olmamalı ama store koruması)
    recheck["summary"]["auto_action_allowed"] = True
    save_position_recheck(recheck)
    records = load_recent_position_rechecks(limit=10)
    assert records[0]["summary"]["auto_action_allowed"] is False


def test_store_load_empty_returns_list(tmp_path, monkeypatch):
    _isolate_recheck_store(tmp_path, monkeypatch)
    assert load_recent_position_rechecks(limit=10) == []


def test_store_load_limit(tmp_path, monkeypatch):
    _isolate_recheck_store(tmp_path, monkeypatch)
    for i in range(5):
        pos = _pos(pair="BTCUSD", pnl_pct=float(-i))
        save_position_recheck(build_position_recheck(pos, _snap(), None))
    records = load_recent_position_rechecks(limit=3)
    assert len(records) == 3


def test_store_skips_corrupt_lines(tmp_path, monkeypatch):
    import app.storage.position_recheck_store as rcs
    store_file = _isolate_recheck_store(tmp_path, monkeypatch)
    recheck = build_position_recheck(_pos(), _snap(), None)
    save_position_recheck(recheck)
    # Corrupt satır ekle
    with store_file.open("a", encoding="utf-8") as f:
        f.write("{broken json\n")
    records = load_recent_position_rechecks(limit=10)
    assert len(records) == 1  # bozuk satır atlandı
