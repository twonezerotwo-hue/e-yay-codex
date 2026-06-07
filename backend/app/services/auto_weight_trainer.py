"""
Otomatik Ağırlık Eğitim Motoru.

Mekanik:
  • Her 5 kapalı trade'de bir tetiklenir
  • Rejime göre trade'leri grupla (bear_2022, mega_bull, default vs)
  • Her rejim için modül performans analizi (skew)
  • Skew bazlı ağırlık ayarı:
      - skew > +3  → modül ağırlığı +3 puan (×0.03 göreceli)
      - skew < -3  → modül ağırlığı -3 puan (×-0.03 göreceli)
  • Adjustments paper_trading_state.json'da saklanır (YAML değişmez)
  • Sonraki tick'te effective_weights = baseline + adjustments

Güvenlik:
  • Min trade sayısı 10 (rejim başına 5)
  • Maks adjustment %±10 (stabilite)
  • Min weight floor 2% (her modülün söz hakkı)
  • Sum normalize 1.0 (her zaman)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.services.consensus_engine import CANONICAL_MODULES
from app.services.learning_engine import analyze_module_performance
from app.services.regime_weights_engine import REGIME_MAP, load_consensus_weights

logger = logging.getLogger(__name__)

# ── Eğitim parametreleri ──────────────────────────────────────────────────────

MIN_TOTAL_TRADES        = 10   # toplam en az 10 kapalı trade
MIN_REGIME_TRADES       = 5    # rejim başına en az 5
TRAINING_INTERVAL       = 5    # her 5 yeni kapanışta tetik
MAX_ADJUSTMENT_PER_RUN  = 0.03  # tek tetikte modül başına max ±0.03 (3 puan)
MAX_TOTAL_ADJUSTMENT    = 0.10  # toplam (her run'lar dahil) max ±0.10
MIN_MODULE_WEIGHT       = 0.02  # her modül en az %2
SKEW_THRESHOLD          = 3.0   # bu eşiğin üstündeki skew için ayar


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _trade_to_regime_key(trade: Any) -> str:
    """Trade'in açıldığı zamandaki rejimden YAML key'i bul."""
    regime = (trade.open_signal or {}).get("raw_regime", "")
    return REGIME_MAP.get(str(regime).strip().upper(), "default")


def _compute_adjustment(skew: float) -> float:
    """Skew → ağırlık delta. Doyumlu fonksiyon."""
    if abs(skew) < SKEW_THRESHOLD:
        return 0.0
    # Skew'i [SKEW_THRESHOLD, 15+] aralığında [0, MAX_ADJUSTMENT] aralığına eşle
    magnitude = min(1.0, (abs(skew) - SKEW_THRESHOLD) / 12.0)
    delta = magnitude * MAX_ADJUSTMENT_PER_RUN
    return delta if skew > 0 else -delta


def _clip_adjustments(
    existing: dict[str, float],
    proposed: dict[str, float],
) -> dict[str, float]:
    """Mevcut adjustment'lara yeni delta'ları ekle, max total ile clip et."""
    out = dict(existing)
    for m in CANONICAL_MODULES:
        cur = float(out.get(m, 0.0))
        add = float(proposed.get(m, 0.0))
        new = max(-MAX_TOTAL_ADJUSTMENT, min(MAX_TOTAL_ADJUSTMENT, cur + add))
        out[m] = round(new, 4)
    return out


# ── Public — eğitim tetikleyici ──────────────────────────────────────────────

def maybe_retrain(
    state: Any,
    force: bool = False,
) -> dict[str, Any]:
    """
    Trade history'ye bakarak rejim başına ağırlık adjustment'larını günceller.
    state'in alanları okunur+yazılır:
      • trades, weight_adjustments, last_trained_at_trade_count, training_history

    Returns:
      {"status": "trained" | "skipped" | "no_data", "reason": str, "updates": [...]}
    """
    closed = [t for t in state.trades if t.verdict in ("WIN", "LOSS")]
    total_closed = len(closed)
    pending = total_closed - state.last_trained_at_trade_count

    if not force:
        if total_closed < MIN_TOTAL_TRADES:
            return {
                "status": "skipped",
                "reason": f"Toplam {total_closed}/{MIN_TOTAL_TRADES} kapanış gerek.",
            }
        if pending < TRAINING_INTERVAL:
            return {
                "status": "skipped",
                "reason": f"Son eğitimden bu yana {pending}/{TRAINING_INTERVAL} yeni kapanış.",
            }

    # ── Rejime göre grupla ─
    by_regime: dict[str, list] = {}
    for t in closed:
        rk = _trade_to_regime_key(t)
        by_regime.setdefault(rk, []).append(t)

    baseline = load_consensus_weights().get("regime_weights", {})

    updates: list[dict] = []
    new_adjustments = dict(state.weight_adjustments or {})

    for regime_key, regime_trades in by_regime.items():
        if len(regime_trades) < MIN_REGIME_TRADES:
            continue

        perf = analyze_module_performance(regime_trades)
        if perf.get("status") != "ok":
            continue

        by_module = perf.get("by_module", {})
        if not by_module:
            continue

        # Her modül için skew → delta
        proposed_delta: dict[str, float] = {}
        for module in CANONICAL_MODULES:
            data = by_module.get(module, {})
            skew = float(data.get("skew", 0.0))
            samples = (data.get("samples", {}).get("winners", 0)
                       + data.get("samples", {}).get("losers", 0))
            if samples < 3:
                proposed_delta[module] = 0.0
                continue
            proposed_delta[module] = _compute_adjustment(skew)

        if all(abs(d) < 1e-6 for d in proposed_delta.values()):
            continue  # bu rejim için anlamlı değişiklik yok

        # Mevcut adjustment'larla birleştir + clip
        existing = new_adjustments.get(regime_key, {})
        clipped = _clip_adjustments(existing, proposed_delta)

        # Floor + normalize ile baseline + adjusted ağırlıklarını üret
        baseline_w = _extract_weights(baseline.get(regime_key, {}))
        effective = _apply_adjustments(baseline_w, clipped)

        updates.append({
            "regime_key":      regime_key,
            "trades_used":     len(regime_trades),
            "delta_applied":   {m: round(proposed_delta[m], 4) for m in CANONICAL_MODULES},
            "total_adjustment": clipped,
            "effective_weights": effective,
            "skews": {m: by_module.get(m, {}).get("skew", 0.0) for m in CANONICAL_MODULES},
        })

        new_adjustments[regime_key] = clipped

    if not updates:
        return {
            "status": "no_data",
            "reason": "Rejim başına ≥5 kapanış olan grup yok veya skewler nötr.",
            "total_closed": total_closed,
        }

    # ── State'i güncelle ─
    state.weight_adjustments = new_adjustments
    state.last_trained_at_trade_count = total_closed

    training_event = {
        "trained_at":    datetime.now(UTC).isoformat(),
        "total_closed":  total_closed,
        "updates":       updates,
    }
    state.training_history = (state.training_history or []) + [training_event]
    if len(state.training_history) > 50:
        state.training_history = state.training_history[-50:]

    logger.info(
        "Auto-trained weights: %d rejim güncellendi (toplam %d kapanış).",
        len(updates), total_closed,
    )

    return {
        "status":       "trained",
        "total_closed": total_closed,
        "updates":      updates,
    }


# ── Effective weights — consensus_engine için ─────────────────────────────────

def _extract_weights(regime_cfg: dict) -> dict[str, float]:
    """YAML key'lerinden modül adına çevir + normalize."""
    raw = {
        "touche":      float(regime_cfg.get("touche_weight",      0.0)),
        "fundamental": float(regime_cfg.get("fundamental_weight", 0.0)),
        "news":        float(regime_cfg.get("news_weight",        0.0)),
        "sentinel":    float(regime_cfg.get("sentinel_weight",    0.0)),
        "quantum":     float(regime_cfg.get("quantum_weight",     0.0)),
    }
    total = sum(raw.values())
    if total <= 0:
        return {m: 1.0 / 5 for m in CANONICAL_MODULES}
    return {m: v / total for m, v in raw.items()}


def _apply_adjustments(
    baseline: dict[str, float],
    adjustments: dict[str, float],
) -> dict[str, float]:
    """Baseline ağırlıklara adjustments ekle, floor + normalize."""
    out: dict[str, float] = {}
    for m in CANONICAL_MODULES:
        b = float(baseline.get(m, 0.2))
        a = float(adjustments.get(m, 0.0))
        out[m] = max(MIN_MODULE_WEIGHT, b + a)

    total = sum(out.values())
    if total <= 0:
        return baseline
    return {m: round(v / total, 6) for m, v in out.items()}


def get_effective_weights(
    raw_regime: str,
    adjustments: dict[str, dict[str, float]] | None = None,
) -> dict[str, float]:
    """
    Verilen rejim için **eğitilmiş** ağırlıkları döndür.

    Eğer adjustments boş veya rejim yoksa → baseline (YAML) ağırlıkları.
    Aksi halde baseline + delta + floor + normalize.
    """
    from app.services.regime_weights_engine import (
        map_regime_to_weight_key,
    )
    weight_key, _ = map_regime_to_weight_key(raw_regime)

    config = load_consensus_weights().get("regime_weights", {})
    baseline = _extract_weights(config.get(weight_key, config.get("default", {})))

    if not adjustments:
        return baseline

    regime_adj = adjustments.get(weight_key, {})
    if not regime_adj:
        return baseline

    return _apply_adjustments(baseline, regime_adj)


__all__ = [
    "maybe_retrain",
    "get_effective_weights",
    "MIN_TOTAL_TRADES",
    "TRAINING_INTERVAL",
]
