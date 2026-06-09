"""
FAZ 7 — Safe Auto Apply Engine.

Fonksiyonlar:
  evaluate_proposals() -> dict
  apply_proposals()    -> dict
  rollback_last_adjustment() -> dict

Amaç:
  weekly_calibration'daki güvenli auto_tune_candidates'i değerlendirip
  küçük, sınırlı ve geri alınabilir parametre override'larına çevirir.

Bu fazda:
  • Hiçbir parametre doğrudan paper trading motoruna uygulanmaz.
  • Sadece auto_tune_overrides.json dosyası güncellenir.
  • Paper trading service okunmaz ve mutate edilmez.
  • Broker bağlantısı YOKTUR.
  • Live execution YOKTUR.

Mimari hazırlık (ileride):
  Calibration → Auto Tune Proposal → Auto Tune Override
      ↓
  Paper Trading Override Reader (ileride)
      ↓
  Execution Policy → Broker Adapter → Live Execution (ayrı faz)

Schema alanlarda şimdiden mevcut:
  broker_permission, live_execution_allowed, execution_mode, decision_permission

Bu fazda zorunlu değerleri:
  broker_permission      = BROKER_NOT_CONNECTED
  live_execution_allowed = False
  execution_mode         = PAPER_SAFE
  decision_permission    = NO_EXECUTION

Güvenli sınırlar:
  position_size_multiplier : [0.70, 1.15]  single_change_max=0.15
  stop_distance_multiplier : [0.85, 1.30]  single_change_max=0.20
  entry_confirmation_bars  : [0,    3]     single_change_max=1
  require_news_confirmation: boolean toggle (enable only)
  early_exit_threshold_pct : [-2.0, 0.0]  single_change_max=0.5

Evaluate eligibility (calibration düzeyinde):
  sample.trades   >= 10
  sample.memories >= 5
  evidence_quality != "limited"
  candidate.min_sample_met == True
  candidate.safe_to_propose == True
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.storage.auto_tune_store import (
    load_last_applied_adjustment,
    read_overrides,
    save_adjustment,
    write_overrides,
)
from app.storage.weekly_calibration_store import load_recent_weekly_calibrations

# ── Sabitler ──────────────────────────────────────────────────────────────────

_MIN_TRADES    = 10   # evaluate düzeyi minimum trade sayısı
_MIN_MEMORIES  = 5    # evaluate düzeyi minimum memory sayısı

# Desteklenen parametre hedefleri + güvenli sınırlar
_BOUNDS: dict[str, dict[str, Any]] = {
    "position_size_multiplier": {
        "min": 0.70, "max": 1.15, "single_change_max": 0.15,
    },
    "stop_distance_multiplier": {
        "min": 0.85, "max": 1.30, "single_change_max": 0.20,
    },
    "entry_confirmation_bars": {
        "min": 0, "max": 3, "single_change_max": 1,
    },
    "early_exit_threshold_pct": {
        "min": -2.0, "max": 0.0, "single_change_max": 0.5,
    },
    # require_news_confirmation: özel boolean toggle (aşağıda ayrı işlenir)
}

# Desteklenen tüm hedefler (require_news_confirmation dahil)
_SUPPORTED_TARGETS = frozenset(_BOUNDS.keys()) | {"require_news_confirmation"}

# Her hedef için varsayılan değer (override dosyasında yoksa kullanılır)
_TARGET_DEFAULTS: dict[str, Any] = {
    "position_size_multiplier": 1.0,
    "stop_distance_multiplier": 1.0,
    "entry_confirmation_bars":  0,
    "require_news_confirmation": False,
    "early_exit_threshold_pct": 0.0,
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _security_fields() -> dict[str, Any]:
    return {
        "decision_permission":    "NO_EXECUTION",
        "execution_mode":         "PAPER_SAFE",
        "broker_permission":      "BROKER_NOT_CONNECTED",
        "live_execution_allowed": False,
    }


def _load_latest_calibration() -> dict[str, Any] | None:
    """weekly_calibrations.jsonl dosyasından en son kaydı döndürür."""
    records = load_recent_weekly_calibrations(limit=1)
    return records[0] if records else None


def _check_global_eligibility(
    calibration: dict[str, Any],
) -> tuple[bool, str]:
    """
    Calibration raporu evaluate için yeterince güçlü mü?

    Returns (eligible: bool, reason: str).
    """
    sample = calibration.get("sample") or {}

    if sample.get("trades", 0) < _MIN_TRADES:
        return False, "not_enough_trades"
    if sample.get("memories", 0) < _MIN_MEMORIES:
        return False, "not_enough_memories"
    if sample.get("evidence_quality") == "limited":
        return False, "evidence_limited"

    return True, ""


def _clamp_change(
    target: str,
    suggested: float,
) -> float:
    """single_change_max sınırını uygula."""
    bounds = _BOUNDS[target]
    max_ch = float(bounds["single_change_max"])
    if abs(suggested) > max_ch:
        return max_ch * (1.0 if suggested > 0.0 else -1.0)
    return suggested


def _compute_new_value(
    target: str,
    old_value: Any,
    effective_change: Any,
) -> tuple[Any, Any]:
    """
    (new_value, actual_change) döndürür.

    Değer, hedefin min/max sınırları içinde kalır.
    entry_confirmation_bars integer; require_news_confirmation boolean; diğerleri float.
    """
    if target == "require_news_confirmation":
        new_value     = True   # sadece "enable" destekleniyor
        actual_change = 1 if not old_value else 0
        return new_value, actual_change

    if target == "entry_confirmation_bars":
        bounds   = _BOUNDS[target]
        change   = int(effective_change)
        new_val  = int(old_value) + change
        new_val  = max(int(bounds["min"]), min(int(bounds["max"]), new_val))
        return new_val, new_val - int(old_value)

    # Float hedefler
    bounds   = _BOUNDS[target]
    new_val  = float(old_value) + float(effective_change)
    new_val  = max(float(bounds["min"]), min(float(bounds["max"]), new_val))
    new_val  = round(new_val, 4)
    actual   = round(new_val - float(old_value), 4)
    return new_val, actual


def _build_proposal(cand: dict[str, Any]) -> dict[str, Any] | None:
    """
    auto_tune_candidate'dan evaluate proposal üretir.
    Desteklenmeyen hedef → None.
    single_change_max aşıldıysa efektif değişim kırpılır.
    """
    target = cand.get("target", "")
    if target not in _SUPPORTED_TARGETS:
        return None

    suggested = cand.get("suggested_change", 0)

    if target == "require_news_confirmation":
        effective_change = "enable"
        max_allowed      = None
    else:
        effective_change = _clamp_change(target, float(suggested))
        max_allowed      = float(_BOUNDS[target]["single_change_max"])

    return {
        "candidate_id":        cand.get("candidate_id"),
        "target":              target,
        "condition":           cand.get("condition", ""),
        "suggested_change":    suggested,
        "effective_change":    effective_change,
        "max_allowed_change":  max_allowed,
        "risk":                "low",
        "paper_safe":          True,
        "execution_mode":      "PAPER_SAFE",
        "broker_permission":   "BROKER_NOT_CONNECTED",
        "broker_action":       "none",
        "live_execution_allowed": False,
        "reason":              cand.get("reason", ""),
    }


def _get_eligible_proposals(
    calibration: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    calibration'daki auto_tune_candidates'ten geçerli proposal'ları filtreler.
    """
    proposals: list[dict[str, Any]] = []

    for cand in (calibration.get("auto_tune_candidates") or []):
        if not cand.get("min_sample_met"):
            continue
        if not cand.get("safe_to_propose"):
            continue

        proposal = _build_proposal(cand)
        if proposal is not None:
            proposals.append(proposal)

    return proposals


def _apply_to_overrides(
    proposals: list[dict[str, Any]],
    calibration_id: str,
) -> list[dict[str, Any]]:
    """
    Proposal listesini overrides.json'a uygular ve her biri için JSONL log yazar.

    Returns: uygulanan adjustment sonuçlarının listesi.
    """
    current_overrides = read_overrides()
    overrides_map     = current_overrides.setdefault("overrides", {})

    applied: list[dict[str, Any]] = []

    for proposal in proposals:
        target    = proposal["target"]
        condition = proposal["condition"]
        eff_ch    = proposal["effective_change"]

        # Mevcut değeri oku (yoksa varsayılan)
        default   = _TARGET_DEFAULTS.get(target, 0)
        old_value = overrides_map.get(target, {}).get(condition, default)

        new_value, actual_change = _compute_new_value(target, old_value, eff_ch)

        # Override'ı güncelle
        if target not in overrides_map:
            overrides_map[target] = {}
        overrides_map[target][condition] = new_value

        # Adjustment log
        adj_id = save_adjustment({
            "status":                "applied",
            "target":                target,
            "condition":             condition,
            "old_value":             old_value,
            "new_value":             new_value,
            "change":                actual_change,
            "source_calibration_id": calibration_id,
            "rollback_available":    True,
        })

        applied.append({
            "adjustment_id": adj_id,
            "target":        target,
            "condition":     condition,
            "old_value":     old_value,
            "new_value":     new_value,
            "change":        actual_change,
        })

    # Override dosyasını güncelle
    current_overrides["updated_at"] = _utc_now_iso()
    write_overrides(current_overrides)

    return applied


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_proposals() -> dict[str, Any]:
    """
    En son calibration raporunu değerlendirir; uygulanabilir proposal'ları döndürür.

    Hiçbir şeyi değiştirmez — sadece okur ve analiz eder.

    Returns:
        {"status": "not_eligible", "reason": "...", ...}
        veya
        {"status": "eligible", "calibration_id": "...", "proposals": [...], ...}
    """
    base = _security_fields()

    calibration = _load_latest_calibration()
    if not calibration:
        return {**base, "status": "not_eligible", "reason": "no_calibration"}

    eligible, reason = _check_global_eligibility(calibration)
    if not eligible:
        return {**base, "status": "not_eligible", "reason": reason,
                "calibration_id": calibration.get("calibration_id")}

    proposals = _get_eligible_proposals(calibration)
    if not proposals:
        return {
            **base,
            "status":           "not_eligible",
            "reason":           "no_safe_candidates",
            "calibration_id":   calibration.get("calibration_id"),
        }

    return {
        **base,
        "status":           "eligible",
        "calibration_id":   calibration.get("calibration_id"),
        "proposal_count":   len(proposals),
        "proposals":        proposals,
    }


def apply_proposals() -> dict[str, Any]:
    """
    Uygun proposal'ları değerlendirir ve auto_tune_overrides.json'a uygular.

    • Paper trading state'ini okumaz veya mutate etmez.
    • Broker bağlantısı gerektirmez.
    • Sadece override JSON dosyasını günceller.
    • Her uygulama için JSONL adjustment log yazılır.

    Returns:
        {"status": "not_eligible", "reason": "...", ...}
        veya
        {"status": "applied", "count": N, "adjustments": [...], ...}
    """
    eval_result = evaluate_proposals()

    if eval_result.get("status") != "eligible":
        return eval_result

    calibration_id = eval_result["calibration_id"]
    proposals      = eval_result["proposals"]

    applied = _apply_to_overrides(proposals, calibration_id)

    return {
        **_security_fields(),
        "status":             "applied",
        "count":              len(applied),
        "calibration_id":     calibration_id,
        "adjustments":        applied,
    }


def rollback_last_adjustment() -> dict[str, Any]:
    """
    Henüz geri alınmamış en son applied adjustment'ı geri alır.

    Overrides.json güncellenir; JSONL'e 'rolled_back' kaydı eklenir.

    Returns:
        {"status": "not_available", "reason": "no_applied_adjustment"}
        veya
        {"status": "rolled_back", "adjustment_id": "...", "target": "...",
         "condition": "...", "old_value_restored": ...}
    """
    base = _security_fields()

    last_adj = load_last_applied_adjustment()
    if not last_adj:
        return {**base, "status": "not_available", "reason": "no_applied_adjustment"}

    target    = last_adj["target"]
    condition = last_adj["condition"]
    restore   = last_adj["old_value"]      # eski (orijinal) değer → geri yüklenecek
    was_new   = last_adj["new_value"]      # uygulanan değer → geri alınıyor

    # Overrides'ı güncelle
    current_overrides = read_overrides()
    overrides_map     = current_overrides.setdefault("overrides", {})

    if target in overrides_map and condition in overrides_map[target]:
        overrides_map[target][condition] = restore
    else:
        # Override kaydı artık yoksa bile log yaz (tutarlılık)
        overrides_map.setdefault(target, {})[condition] = restore

    current_overrides["updated_at"] = _utc_now_iso()
    write_overrides(current_overrides)

    # Rollback kaydı yaz
    rb_id = save_adjustment({
        "status":                    "rolled_back",
        "target":                    target,
        "condition":                 condition,
        "old_value":                 was_new,    # bu kayıttaki "eski" değer = uygulanmış değer
        "new_value":                 restore,    # geri yüklenen değer
        "change":                    (restore - was_new)
                                     if isinstance(restore, (int, float))
                                     and isinstance(was_new, (int, float))
                                     else None,
        "source_calibration_id":     last_adj.get("source_calibration_id"),
        "rollback_available":        False,
        "rollback_of_adjustment_id": last_adj["adjustment_id"],
    })

    return {
        **base,
        "status":              "rolled_back",
        "adjustment_id":       rb_id,
        "target":              target,
        "condition":           condition,
        "old_value_restored":  restore,
    }
