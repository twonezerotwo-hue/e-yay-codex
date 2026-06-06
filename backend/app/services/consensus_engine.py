"""
5-Modül Consensus Engine — E-YAY × Aegis (REVİZE).

Aegis kaynak: aegis_core/engine/consensus.py

REVİZELER (Aegis'in 4 hatasını düzeltir):
  1. Skor normalize → her modül kendi range'ini söyler (0..100, 0..1, -1..+1)
  2. Eksik modül → ağırlığı diğerlerine YENİDEN DAĞIT (redistribute)
     yerine 50 nötr fallback. AGENTS.md "no silent fallback" uyumlu.
  3. min_modules_required eşiği — yetmezse INSUFFICIENT_DATA
  4. Direction band (45-55 nötr zone) — tek 50.0 eşiği bug'ı yok
"""
from __future__ import annotations

from typing import Literal, Optional

from app.services.regime_weights_engine import (
    get_consensus_config,
    get_weights_for_regime,
)

CANONICAL_MODULES = ("touche", "fundamental", "news", "sentinel", "quantum", "chart_pattern")

# E-YAY için sade alias mapping
MODULE_ALIASES = {
    "touche": "touche",
    "technical": "touche",
    "tech": "touche",
    "fundamental": "fundamental",
    "checklist": "fundamental",
    "news": "news",
    "sentiment": "news",
    "sentinel": "sentinel",
    "macro": "sentinel",       # NOT: bilinçli kabul — E-YAY'da makro + rejim sentinel'de
    "regime": "sentinel",
    "quantum": "quantum",
    "rotation": "quantum",     # CapitalRotation conviction = quantum sinyali
    "flow": "quantum",
}


def _canonical_module_name(raw_key: str) -> str:
    return MODULE_ALIASES.get(str(raw_key).strip().lower(), str(raw_key).strip().lower())


# ── Skor normalize (REVİZE: range explicit) ──────────────────────────────────

ScoreRange = Literal[
    "pct_0_100", "ratio_0_1", "signed_neg1_pos1", "signed_neg15_pos15",
    "signed_neg100_pos100",
]


def _normalize_score(raw_score: float, score_range: ScoreRange = "pct_0_100") -> float:
    """Skoru 0-100 ölçeğine çevir — range'i bilerek (Aegis'in tahmin bug'ı düzeltildi)."""
    v = float(raw_score)

    if score_range == "pct_0_100":
        return max(0.0, min(100.0, v))

    if score_range == "ratio_0_1":
        return max(0.0, min(100.0, v * 100.0))

    if score_range == "signed_neg1_pos1":
        # -1 (tam bearish) → 0, 0 (nötr) → 50, +1 (tam bullish) → 100
        return max(0.0, min(100.0, (v + 1.0) * 50.0))

    if score_range == "signed_neg15_pos15":
        # -1.5 → 0, 0 → 50, +1.5 → 100
        return max(0.0, min(100.0, (v + 1.5) * (100.0 / 3.0)))

    if score_range == "signed_neg100_pos100":
        # -100 (tam bearish) → 0, 0 (nötr) → 50, +100 (tam bullish) → 100
        # chart_pattern modülü bu range'i kullanır
        return max(0.0, min(100.0, v * 0.5 + 50.0))

    return max(0.0, min(100.0, v))


# ── Direction band (REVİZE: tek 50.0 eşik bug'ı yok) ──────────────────────────

def get_direction(score: float, bull_thr: float = 55.0, bear_thr: float = 45.0) -> Literal["bullish", "bearish", "neutral"]:
    if score > bull_thr:
        return "bullish"
    if score < bear_thr:
        return "bearish"
    return "neutral"


# ── Module score normalization ───────────────────────────────────────────────

def _normalize_module_scores(
    module_scores: dict,
) -> tuple[dict[str, float], list[str]]:
    """
    module_scores formatı:
      • {"touche": 75.0}                                # implicit pct_0_100
      • {"touche": {"value": 0.8, "range": "ratio_0_1"}}  # explicit
      • {"quantum": {"value": -0.5, "range": "signed_neg1_pos1"}}
    """
    normalized: dict[str, float] = {}
    warnings: list[str] = []

    if not isinstance(module_scores, dict):
        return {}, ["module_scores bir dict olmalı."]

    for raw_key, raw_value in module_scores.items():
        canonical = _canonical_module_name(raw_key)
        if canonical not in CANONICAL_MODULES:
            warnings.append(f"Tanınmayan modül '{raw_key}' yok sayıldı.")
            continue

        try:
            if isinstance(raw_value, dict):
                v     = raw_value.get("value")
                rng   = raw_value.get("range", "pct_0_100")
                if v is None:
                    warnings.append(f"Modül '{raw_key}' value eksik.")
                    continue
                normalized[canonical] = round(_normalize_score(v, rng), 4)
            else:
                normalized[canonical] = round(_normalize_score(raw_value, "pct_0_100"), 4)
        except (TypeError, ValueError) as exc:
            warnings.append(f"Modül '{raw_key}' skoru sayı değil: {exc}")

    return normalized, warnings


# ── Weight handling ──────────────────────────────────────────────────────────

def _redistribute_weights(
    weights: dict[str, float],
    available_modules: set[str],
) -> tuple[dict[str, float], list[str]]:
    """
    REVİZE: Eksik modül için 50 nötr fallback YERİNE,
    eksik modülün ağırlığını mevcutlara redistribute et.

    Örnek: 5 modülün 2'si eksikse, 3 modüle eşit-oranlı dağıt.
    """
    warnings: list[str] = []
    missing = [m for m in CANONICAL_MODULES if m not in available_modules]
    if not missing:
        return weights, warnings

    missing_weight = sum(weights.get(m, 0.0) for m in missing)
    if missing_weight <= 0:
        return weights, warnings  # eksik modülün ağırlığı zaten 0

    available_total = sum(weights.get(m, 0.0) for m in available_modules)
    if available_total <= 0:
        # Mevcutların hepsi 0 ağırlık — eşit dağıt
        equal = 1.0 / len(available_modules) if available_modules else 0.0
        new_weights = {m: equal if m in available_modules else 0.0 for m in CANONICAL_MODULES}
    else:
        # Mevcutlara orantısal yeniden dağıt
        new_weights = {}
        for m in CANONICAL_MODULES:
            if m in available_modules:
                base = weights.get(m, 0.0)
                share = missing_weight * (base / available_total)
                new_weights[m] = round(base + share, 6)
            else:
                new_weights[m] = 0.0

    warnings.append(
        f"Eksik modül(ler) {missing} için ağırlık yeniden dağıtıldı (redistribute) — "
        f"50 nötr fallback YOK."
    )
    return new_weights, warnings


# ── Ana hesap ────────────────────────────────────────────────────────────────

def calculate_consensus_score(
    module_scores: dict,
    weights: dict,
    min_modules_required: int = 3,
) -> dict:
    """
    Ağırlıklı consensus skoru üret.

    Dönüş:
      {
        "consensus_score":   float | None,    # None ise INSUFFICIENT_DATA
        "status":            "OK" | "INSUFFICIENT_DATA",
        "direction":         "bullish" | "bearish" | "neutral" | None,
        "normalized_scores": dict,
        "weights_used":      dict,
        "contributions":     dict,
        "missing_modules":   list,
        "warnings":          list,
      }
    """
    normalized_scores, score_warnings = _normalize_module_scores(module_scores)

    # ── REVİZE 3: min_modules eşiği ─
    available_modules = set(normalized_scores.keys())
    if len(available_modules) < min_modules_required:
        return {
            "consensus_score":   None,
            "status":            "INSUFFICIENT_DATA",
            "direction":         None,
            "normalized_scores": normalized_scores,
            "weights_used":      {},
            "contributions":     {},
            "missing_modules":   [m for m in CANONICAL_MODULES if m not in available_modules],
            "warnings": score_warnings + [
                f"En az {min_modules_required} modül gerekli, sadece {len(available_modules)} var."
            ],
        }

    # ── REVİZE 2: redistribute weights for missing modules ─
    raw_weights = weights.get("weights", weights) if isinstance(weights, dict) else {}
    if not isinstance(raw_weights, dict):
        raw_weights = {}
    weights_dict = {m: float(raw_weights.get(m, 0.0)) for m in CANONICAL_MODULES}

    final_weights, redistribute_warnings = _redistribute_weights(weights_dict, available_modules)

    # Toplam normalize (1.0)
    total = sum(final_weights.values())
    if total <= 0:
        return {
            "consensus_score":   None,
            "status":            "INSUFFICIENT_DATA",
            "direction":         None,
            "normalized_scores": normalized_scores,
            "weights_used":      final_weights,
            "contributions":     {},
            "missing_modules":   [m for m in CANONICAL_MODULES if m not in available_modules],
            "warnings": score_warnings + redistribute_warnings + ["Tüm ağırlıklar 0."],
        }
    final_weights = {k: round(v / total, 6) for k, v in final_weights.items()}

    # ── Ağırlıklı toplam ─
    contributions: dict[str, dict] = {}
    consensus_score = 0.0
    for module in CANONICAL_MODULES:
        w = final_weights[module]
        if module in normalized_scores:
            s = normalized_scores[module]
            source = "provided"
            contribution = s * w
            consensus_score += contribution
        else:
            s = 0.0
            source = "missing_redistributed"
            contribution = 0.0
        contributions[module] = {
            "score": round(s, 4),
            "weight": round(w, 6),
            "weighted_score": round(contribution, 4),
            "source": source,
        }

    direction = get_direction(consensus_score)

    return {
        "consensus_score":   round(consensus_score, 4),
        "status":            "OK",
        "direction":         direction,
        "normalized_scores": normalized_scores,
        "weights_used":      final_weights,
        "contributions":     contributions,
        "missing_modules":   [m for m in CANONICAL_MODULES if m not in available_modules],
        "warnings":          score_warnings + redistribute_warnings,
    }


# ── Public — sinyal builder ──────────────────────────────────────────────────

def build_consensus_signal(
    symbol: str,
    timeframe: str,
    module_scores: dict,
    raw_regime: str,
    confluence: Optional[dict] = None,
    trained_adjustments: Optional[dict[str, dict[str, float]]] = None,
) -> dict:
    """E-YAY Consensus sinyal kontratı — Aegis build_aegis_signal'in revize hali.

    trained_adjustments verilirse baseline ağırlıklar agent öğrenmesiyle düzeltilir.
    """
    warnings: list[str] = []

    regime_result = get_weights_for_regime(raw_regime)
    warnings.extend(regime_result["warnings"])

    # ── Eğitilmiş ağırlıkları uygula (varsa) ──
    weights_for_consensus = regime_result["weights"]
    is_trained = False
    if trained_adjustments:
        from app.services.auto_weight_trainer import get_effective_weights
        weights_for_consensus = get_effective_weights(raw_regime, trained_adjustments)
        # Adjustments tatbik edildi mi gerçekten?
        if any(
            abs(weights_for_consensus.get(m, 0) - regime_result["weights"].get(m, 0)) > 1e-6
            for m in CANONICAL_MODULES
        ):
            is_trained = True
            warnings.append("Eğitilmiş ağırlıklar uygulandı (baseline + agent learning).")

    cfg = get_consensus_config()
    min_modules = int(cfg.get("min_modules_required", 3))

    consensus = calculate_consensus_score(
        module_scores, weights_for_consensus, min_modules_required=min_modules,
    )
    warnings.extend(consensus["warnings"])

    signal: dict = {
        "source_engine":      "E-YAY × Aegis",
        "source_version":     "1.0_revised",
        "symbol":             symbol,
        "timeframe":          timeframe,
        "raw_regime":         raw_regime,
        "weight_key":         regime_result["weight_key"],
        "primary_tf":         regime_result["primary_tf"],
        "weights_used":       consensus["weights_used"],
        "weights_trained":    is_trained,
        "module_scores":      consensus["normalized_scores"],
        "consensus_score":    consensus["consensus_score"],
        "direction":          consensus["direction"],
        "status":             consensus["status"],
        "missing_modules":    consensus["missing_modules"],
        "contributions":      consensus["contributions"],
        "decision_permission": "SIGNAL_ONLY_NOT_FINAL",
        "final_decision":     False,
        "warnings":           warnings,
    }

    if isinstance(confluence, dict):
        signal["confluence"] = confluence

    return signal


__all__ = [
    "CANONICAL_MODULES",
    "calculate_consensus_score",
    "build_consensus_signal",
    "get_direction",
]
