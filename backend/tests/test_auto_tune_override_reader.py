"""
FAZ 7.5 — Auto Tune Override Reader testleri.

12 test:
  1.  load — dosya yok → boş dict
  2.  load — geçerli dosya → dict döner
  3.  load — bozuk JSON → boş dict
  4.  validate_security_fields — tüm alanlar doğru → True
  5.  validate_security_fields — hatalı decision_permission → False
  6.  validate_security_fields — live_execution_allowed True → False
  7.  apply — override dosyası yok → applied=False, size_pct değişmez
  8.  apply — LONG + pattern_bearish eşleşmesi → çarpan uygulanır
  9.  apply — SHORT + pattern_bullish eşleşmesi → çarpan uygulanır
  10. apply — eşleşme yok → applied=False, size_pct değişmez
  11. apply — sonuç PSM_MIN'in altına düşüyorsa kırpılır
  12. apply — güvenlik doğrulama başarısız → applied=False, size_pct değişmez
  (bonus: paper_trading_service import edilmemiş — dairesel import yok)
"""
from __future__ import annotations

import inspect
import json
import textwrap
from pathlib import Path

import pytest

import app.services.auto_tune_override_reader as reader_mod
from app.services.auto_tune_override_reader import (
    _validate_security_fields,
    apply_auto_tune_modifiers,
    build_auto_tune_context,
    load_auto_tune_overrides,
)

# ── Yardımcılar ───────────────────────────────────────────────────────────────

_VALID_SECURITY = {
    "decision_permission":    "NO_EXECUTION",
    "execution_mode":         "PAPER_SAFE",
    "broker_permission":      "BROKER_NOT_CONNECTED",
    "live_execution_allowed": False,
}


def _make_overrides(conditions: dict | None = None) -> dict:
    """Güvenli sınırlı, geçerli overrides.json içeriği üretir."""
    return {
        **_VALID_SECURITY,
        "schema_version": "auto_tune_overrides_v1",
        "overrides": {
            "position_size_multiplier": conditions or {},
        },
    }


def _make_signal(
    tf_1h_dir: str | None = None,
    final_direction: str | None = None,
) -> dict:
    """Minimal consensus sinyal snapshot'ı üretir."""
    sig: dict = {}
    if tf_1h_dir is not None:
        sig["tf_signals"] = {"1h": {"direction": tf_1h_dir}}
    if final_direction is not None:
        sig["final_direction"] = final_direction
    return sig


def _write_overrides(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── Test 1: load — dosya yok ──────────────────────────────────────────────────

def test_load_overrides_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", tmp_path / "nonexistent.json")
    result = load_auto_tune_overrides()
    assert result == {}


# ── Test 2: load — geçerli dosya ─────────────────────────────────────────────

def test_load_overrides_valid_file(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    data = _make_overrides({"LONG + pattern_bearish": 0.85})
    _write_overrides(path, data)
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    result = load_auto_tune_overrides()
    assert result["overrides"]["position_size_multiplier"]["LONG + pattern_bearish"] == 0.85


# ── Test 3: load — bozuk JSON ─────────────────────────────────────────────────

def test_load_overrides_corrupt_json(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    path.write_text("{ not valid json }", encoding="utf-8")
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    result = load_auto_tune_overrides()
    assert result == {}


# ── Test 4: validate — tüm alanlar doğru ─────────────────────────────────────

def test_validate_security_fields_all_correct():
    assert _validate_security_fields(_VALID_SECURITY) is True


# ── Test 5: validate — hatalı decision_permission ────────────────────────────

def test_validate_security_fields_wrong_decision_permission():
    bad = {**_VALID_SECURITY, "decision_permission": "EXECUTE"}
    assert _validate_security_fields(bad) is False


# ── Test 6: validate — live_execution_allowed True ───────────────────────────

def test_validate_security_fields_live_execution_true():
    bad = {**_VALID_SECURITY, "live_execution_allowed": True}
    assert _validate_security_fields(bad) is False


# ── Test 7: apply — override dosyası yok ─────────────────────────────────────

def test_apply_no_overrides_file(tmp_path, monkeypatch):
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", tmp_path / "nonexistent.json")
    sig = _make_signal(tf_1h_dir="bearish")
    result = apply_auto_tune_modifiers(sig, "LONG", 0.80)

    assert result["size_pct"] == 0.80
    ctx = result["auto_tune_context"]
    assert ctx["applied"] is False
    assert ctx["available"] is False
    assert ctx["reason"] == "no_overrides"


# ── Test 8: apply — LONG + pattern_bearish eşleşmesi ─────────────────────────

def test_apply_long_pattern_bearish_match(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    _write_overrides(path, _make_overrides({"LONG + pattern_bearish": 0.85}))
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    # base=0.90, multiplier=0.85 → 0.765 (PSM_MIN 0.70'in üzerinde, kırpılmaz)
    sig = _make_signal(tf_1h_dir="bearish")
    result = apply_auto_tune_modifiers(sig, "LONG", 0.90)

    assert result["size_pct"] == pytest.approx(0.765, abs=0.001)
    ctx = result["auto_tune_context"]
    assert ctx["applied"] is True
    assert ctx["available"] is True
    assert ctx["target"] == "position_size_multiplier"
    assert ctx["condition"] == "LONG + pattern_bearish"
    assert ctx["old_size_pct"] == pytest.approx(0.90)
    assert ctx["new_size_pct"] == pytest.approx(0.765, abs=0.001)
    assert ctx["multiplier"] == pytest.approx(0.85)
    assert ctx["decision_permission"] == "NO_EXECUTION"
    assert ctx["execution_mode"] == "PAPER_SAFE"
    assert ctx["broker_permission"] == "BROKER_NOT_CONNECTED"
    assert ctx["live_execution_allowed"] is False


# ── Test 9: apply — SHORT + pattern_bullish eşleşmesi ────────────────────────

def test_apply_short_pattern_bullish_match(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    _write_overrides(path, _make_overrides({"SHORT + pattern_bullish": 0.90}))
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    # base=0.90, multiplier=0.90 → 0.81 (PSM_MIN 0.70'in üzerinde, kırpılmaz)
    sig = _make_signal(tf_1h_dir="bullish")
    result = apply_auto_tune_modifiers(sig, "SHORT", 0.90)

    assert result["size_pct"] == pytest.approx(0.81, abs=0.001)
    ctx = result["auto_tune_context"]
    assert ctx["applied"] is True
    assert ctx["condition"] == "SHORT + pattern_bullish"
    assert ctx["multiplier"] == pytest.approx(0.90)


# ── Test 10: apply — eşleşme yok ──────────────────────────────────────────────

def test_apply_no_matching_condition(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    # Koşul var ama sinyal eşleşmiyor (LONG + bullish 1h)
    _write_overrides(path, _make_overrides({"LONG + pattern_bearish": 0.85}))
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    sig = _make_signal(tf_1h_dir="bullish")
    result = apply_auto_tune_modifiers(sig, "LONG", 0.80)

    assert result["size_pct"] == 0.80
    ctx = result["auto_tune_context"]
    assert ctx["applied"] is False
    assert ctx["available"] is True
    assert ctx["reason"] == "no_matching_override"


# ── Test 11: apply — PSM_MIN kırpması ────────────────────────────────────────

def test_apply_clamps_to_psm_min(tmp_path, monkeypatch):
    """
    base_size_pct=0.75 × multiplier=0.80 = 0.60, PSM_MIN=0.70'in altında.
    Sonuç 0.70'e kırpılmalı.
    """
    path = tmp_path / "auto_tune_overrides.json"
    _write_overrides(path, _make_overrides({"LONG + pattern_bearish": 0.80}))
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    sig = _make_signal(tf_1h_dir="bearish")
    result = apply_auto_tune_modifiers(sig, "LONG", 0.75)

    assert result["size_pct"] == pytest.approx(0.70)
    ctx = result["auto_tune_context"]
    assert ctx["applied"] is True
    assert ctx["new_size_pct"] == pytest.approx(0.70)


# ── Test 12: apply — güvenlik doğrulama başarısız ────────────────────────────

def test_apply_security_validation_failed(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    bad_overrides = _make_overrides({"LONG + pattern_bearish": 0.85})
    bad_overrides["decision_permission"] = "EXECUTE"   # güvenlik ihlali
    _write_overrides(path, bad_overrides)
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    sig = _make_signal(tf_1h_dir="bearish")
    result = apply_auto_tune_modifiers(sig, "LONG", 0.80)

    assert result["size_pct"] == 0.80
    ctx = result["auto_tune_context"]
    assert ctx["applied"] is False
    assert ctx["available"] is False
    assert ctx["reason"] == "security_validation_failed"


# ── Bonus: paper_trading_service import edilmemiş ─────────────────────────────

def test_paper_trading_service_not_imported():
    """
    auto_tune_override_reader.py, paper_trading_service'i import etmemelidir.
    Dairesel import ve sistem sınırı kuralı.
    Import satırı (from ... import veya import ...) dosyada bulunmamalıdır.
    """
    src = inspect.getsource(reader_mod)
    assert "from app.services.paper_trading_service" not in src
    assert "import paper_trading_service" not in src


# ── build_auto_tune_context: temel kontrol ────────────────────────────────────

def test_build_context_no_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", tmp_path / "none.json")
    ctx = build_auto_tune_context("BTCUSD", {}, "LONG")
    assert ctx["applied"] is False
    assert ctx["available"] is False


def test_build_context_match_returns_context(tmp_path, monkeypatch):
    path = tmp_path / "auto_tune_overrides.json"
    _write_overrides(path, _make_overrides({"LONG + pattern_bearish": 0.85}))
    monkeypatch.setattr(reader_mod, "_OVERRIDES_PATH", path)

    sig = _make_signal(tf_1h_dir="short")   # "short" ∈ _BEARISH_DIR
    ctx = build_auto_tune_context("BTCUSD", sig, "LONG")

    assert ctx["available"] is True
    assert ctx["applied"] is False          # context-only; gerçek apply başka fonksiyonda
    assert ctx["condition"] == "LONG + pattern_bearish"
    assert ctx["decision_permission"] == "NO_EXECUTION"
