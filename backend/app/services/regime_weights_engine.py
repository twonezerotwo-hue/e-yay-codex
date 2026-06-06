"""
Regime-aware weight loading — E-YAY × Aegis (REVİZE).

Aegis kaynak: aegis_core/engine/regime_weights.py

REVİZELER:
  • E-YAY rejim kodları için mapping (RISK_ON, TRANSITIONING, DEFENSIVE, CRISIS)
  • Eksik weight = ValueError (silent fallback YOK — AGENTS.md kuralı)
  • Config yolu E-YAY dizinine uyarlandı
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "consensus_weights.yaml"

# ── Rejim adı eşleme (E-YAY + Aegis + alias'lar) ──────────────────────────────
REGIME_MAP: dict[str, str] = {
    # E-YAY rejim kodları (öncelikli)
    "RISK_ON":       "mega_bull",
    "TRANSITIONING": "default",
    "DEFENSIVE":     "bear_2022",
    "CRISIS":        "bear_2022_aggressive",
    # Aegis kalıtım kodları (geriye uyum)
    "LIQUIDITY_EXPANSION": "mega_bull",
    "NORMALIZATION":       "bull",
    "RISK_OFF":            "bear_2022",
    "ACCUMULATION":        "accumulation",
    # YAML key'leri (direkt kullanım)
    "BULL":                  "bull",
    "MEGA_BULL":             "mega_bull",
    "BEAR_2022":             "bear_2022",
    "BEAR_2022_AGGRESSIVE":  "bear_2022_aggressive",
    "DEFAULT":               "default",
}

WEIGHT_FIELDS: dict[str, str] = {
    "touche_weight":        "touche",
    "fundamental_weight":   "fundamental",
    "news_weight":          "news",
    "sentinel_weight":      "sentinel",
    "quantum_weight":       "quantum",
    "chart_pattern_weight": "chart_pattern",
}


def _resolve_config_path(path: Optional[str] = None) -> Path:
    return Path(path).resolve() if path else _DEFAULT_CONFIG_PATH


def load_consensus_weights(path: Optional[str] = None) -> dict:
    """Konsensüs ağırlıklarını YAML'dan oku — silent fallback YOK."""
    config_path = _resolve_config_path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Consensus weights config bulunamadı: {config_path}")

    with config_path.open("r", encoding="utf-8") as h:
        loaded = yaml.safe_load(h) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Config bir mapping olmalı: {config_path}")
    return loaded


def map_regime_to_weight_key(raw_regime: str) -> tuple[str, list[str]]:
    """E-YAY/Aegis rejim adını YAML key'ine çevir, warning üret."""
    warnings: list[str] = []
    normalized = (raw_regime or "").strip().upper()

    if normalized in REGIME_MAP:
        return REGIME_MAP[normalized], warnings

    warnings.append(
        f"Tanınmayan rejim '{raw_regime}' — varsayılan 'default' ağırlığa düşülüyor."
    )
    return "default", warnings


def _extract_weights(regime_config: dict, regime_key: str) -> tuple[dict[str, float], list[str]]:
    """REVİZE: Eksik weight için silent 0 YERİNE warning üret."""
    weights: dict[str, float] = {}
    warnings: list[str] = []
    for source_key, target_key in WEIGHT_FIELDS.items():
        if source_key not in regime_config:
            warnings.append(
                f"Rejim '{regime_key}': '{source_key}' eksik — 0 olarak alındı (silent değil)."
            )
            weights[target_key] = 0.0
        else:
            try:
                weights[target_key] = float(regime_config[source_key])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Rejim '{regime_key}': '{source_key}' sayı olmalı: {exc}"
                ) from exc
    return weights, warnings


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Ağırlıkları 1.0'a normalize et."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Rejim ağırlıkları toplamı pozitif olmalı.")
    return {k: round(v / total, 6) for k, v in weights.items()}


def get_weights_for_regime(raw_regime: str, path: Optional[str] = None) -> dict:
    """Verilen rejim için ağırlıkları + warning'ler + meta veri döndür."""
    config_path = _resolve_config_path(path)
    config = load_consensus_weights(str(config_path))
    warnings: list[str] = []

    weight_key, map_warnings = map_regime_to_weight_key(raw_regime)
    warnings.extend(map_warnings)

    regime_weights = config.get("regime_weights")
    if not isinstance(regime_weights, dict) or not regime_weights:
        raise ValueError(f"Config'te 'regime_weights' bloğu eksik: {config_path}")

    regime_config = regime_weights.get(weight_key)
    resolved_key = weight_key

    if not isinstance(regime_config, dict):
        warnings.append(
            f"Rejim key '{weight_key}' config'te yok — 'default' ağırlığa düşülüyor."
        )
        resolved_key = "default"
        regime_config = regime_weights.get("default")

    if not isinstance(regime_config, dict):
        raise ValueError(f"'default' rejim ağırlıkları eksik: {config_path}")

    raw_weights, extract_warnings = _extract_weights(regime_config, resolved_key)
    warnings.extend(extract_warnings)

    total = sum(raw_weights.values())
    if abs(total - 1.0) > 1e-9:
        warnings.append(
            f"Rejim '{resolved_key}' ağırlıkları toplamı {total:.6f} — 1.0'a normalize edildi."
        )
    weights = _normalize_weights(raw_weights)

    return {
        "weight_key": resolved_key,
        "weights":    weights,
        "primary_tf": regime_config.get("primary_tf", "1h"),
        "warnings":   warnings,
        "source_config": {
            "path": str(config_path),
            "raw_regime": raw_regime,
            "resolved_weight_key": resolved_key,
        },
    }


def get_consensus_config(path: Optional[str] = None) -> dict:
    """consensus_config bloğunu (min_modules, direction_band, confluence) döndür."""
    config = load_consensus_weights(path)
    return config.get("consensus_config", {})


__all__ = [
    "load_consensus_weights",
    "map_regime_to_weight_key",
    "get_weights_for_regime",
    "get_consensus_config",
    "REGIME_MAP",
]
