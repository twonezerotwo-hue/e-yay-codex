"""
FAZ 14 — Capital Rotation 3D Visual Adapter.

Mevcut CapitalRotation çıktısını "animated flow" UI için node/flow modeline
çevirir. KARAR ÜRETMEZ — sadece görsel katman.

Garantiler:
  - Read-only.
  - PAPER_SAFE / NO_EXECUTION.
  - Paper trading / agent / auto tune / risk gate / core rotation logic
    bu modülü kullanmaz.
  - Hatalı/bozuk/identical input → status="degraded", nodes=[], flows=[].
  - Mock/synthetic veri yok.

Output schema:
  {
    "status":              "ok" | "degraded",
    "schema_version":      "capital_rotation_visual_v1",
    "source":              "capital_rotation_provider",
    "decision_permission": "NO_EXECUTION",
    "execution_mode":      "PAPER_SAFE",
    "visual_mode":         "animated_flow",
    "conviction":          int,
    "primary_flow":        str,
    "nodes":               [{id, label, asset_class, value_pct, direction, strength}, ...],
    "flows":               [{from, to, strength, reason}, ...],
    "fallback_reason":     str | None,
  }
"""
from __future__ import annotations

from typing import Any

# ── Sabitler ──────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "capital_rotation_visual_v1"
SOURCE         = "capital_rotation_provider"
VISUAL_MODE    = "animated_flow"

# Dahili sınıf adı → UI node id + label + asset_class
_CLASS_TO_NODE: dict[str, dict[str, str]] = {
    "DOLAR_GÜCÜ": {"id": "DXY", "label": "DOLAR GÜCÜ", "asset_class": "dollar"},
    "TAHVİL":     {"id": "TLT", "label": "TAHVİL",     "asset_class": "bonds"},
    "ALTIN":      {"id": "GLD", "label": "ALTIN",      "asset_class": "gold"},
    "GÜMÜŞ":      {"id": "XAG", "label": "GÜMÜŞ",      "asset_class": "silver"},
    "PETROL":     {"id": "OIL", "label": "PETROL",     "asset_class": "energy"},
    "BTC":        {"id": "BTC", "label": "BTC",        "asset_class": "crypto"},
    "HİSSE":      {"id": "SPY", "label": "HİSSE",      "asset_class": "equity"},
    "HYG":        {"id": "HYG", "label": "HYG",        "asset_class": "credit"},
}

_NEUTRAL_BAND = 0.5    # |momentum_30d| < 0.5% → neutral
_STRENGTH_CAP = 30.0   # 30%+ momentum → full strength


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _direction_for(momentum_pct: float) -> str:
    if momentum_pct > _NEUTRAL_BAND:
        return "in"
    if momentum_pct < -_NEUTRAL_BAND:
        return "out"
    return "neutral"


def _strength_for(momentum_pct: float) -> float:
    s = abs(momentum_pct) / _STRENGTH_CAP
    if s > 1.0:
        s = 1.0
    return round(s, 3)


def _degraded(reason: str) -> dict[str, Any]:
    return {
        "status":              "degraded",
        "schema_version":      SCHEMA_VERSION,
        "source":              SOURCE,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "visual_mode":         VISUAL_MODE,
        "conviction":          0,
        "primary_flow":        "",
        "nodes":               [],
        "flows":               [],
        "fallback_reason":     reason,
    }


def _rotation_to_dict(rotation: Any) -> dict[str, Any]:
    """CapitalRotation dataclass veya dict'i normalize et."""
    if rotation is None:
        return {}
    if isinstance(rotation, dict):
        return rotation
    out: dict[str, Any] = {}
    for k in ("primary_flow", "secondary_flow", "conviction",
              "class_scores", "error"):
        if hasattr(rotation, k):
            out[k] = getattr(rotation, k)
    return out


def _normalize_scores(class_scores: Any) -> list[dict[str, Any]]:
    """class_scores tuple/list → list[dict] (name/score/momentum_30d/direction)."""
    out: list[dict[str, Any]] = []
    if not class_scores:
        return out
    for cs in class_scores:
        if isinstance(cs, dict):
            name = str(cs.get("name") or "")
            mom  = cs.get("momentum_30d")
            sc   = cs.get("score")
            d    = str(cs.get("direction") or "")
        else:
            name = str(getattr(cs, "name", "") or "")
            mom  = getattr(cs, "momentum_30d", None)
            sc   = getattr(cs, "score", None)
            d    = str(getattr(cs, "direction", "") or "")
        if not name:
            continue
        try:
            mom_f = float(mom) if mom is not None else 0.0
            sc_f  = float(sc) if sc is not None else 0.0
        except (TypeError, ValueError):
            continue
        out.append({
            "name":         name,
            "momentum_30d": mom_f,
            "score":        sc_f,
            "direction":    d,
        })
    return out


def _all_identical(values: list[float], tol: float = 1e-6) -> bool:
    if len(values) < 2:
        return False
    return max(values) - min(values) < tol


# ── Ana adapter ───────────────────────────────────────────────────────────────

def build_visual_payload(rotation: Any) -> dict[str, Any]:
    """
    CapitalRotation → animated_flow visual payload.
    Karar üretmez. Read-only.
    """
    # 1. Veri normalize
    rd = _rotation_to_dict(rotation)
    if not rd:
        return _degraded("rotation_unavailable")
    err = rd.get("error")
    if err:
        return _degraded(f"rotation_error: {err}")

    scores = _normalize_scores(rd.get("class_scores"))
    if not scores:
        return _degraded("class_scores_empty")

    momenta = [s["momentum_30d"] for s in scores]
    if _all_identical(momenta):
        return _degraded("identical_returns")

    # 2. Node listesi
    nodes: list[dict[str, Any]] = []
    for s in scores:
        meta = _CLASS_TO_NODE.get(s["name"])
        if not meta:
            continue
        mom = s["momentum_30d"]
        nodes.append({
            "id":          meta["id"],
            "label":       meta["label"],
            "asset_class": meta["asset_class"],
            "value_pct":   round(mom, 2),
            "direction":   _direction_for(mom),
            "strength":    _strength_for(mom),
        })

    if not nodes:
        return _degraded("no_mappable_nodes")

    # 3. Flow inşası: out node'lar → en güçlü in node(lar)
    in_nodes  = [n for n in nodes if n["direction"] == "in"]
    out_nodes = [n for n in nodes if n["direction"] == "out"]

    flows: list[dict[str, Any]] = []
    if out_nodes and in_nodes:
        in_sorted = sorted(in_nodes, key=lambda n: n["strength"], reverse=True)
        primary_in_id = in_sorted[0]["id"]
        for o in sorted(out_nodes, key=lambda n: n["strength"], reverse=True):
            target = primary_in_id
            flows.append({
                "from":     o["id"],
                "to":       target,
                "strength": round(max(o["strength"], 0.05), 3),
                "reason":   f"{o['label']} çıkış, {in_sorted[0]['label']} giriş",
            })
    elif out_nodes and not in_nodes:
        # Belirgin giriş yok → CASH_PROXY
        for o in out_nodes:
            flows.append({
                "from":     o["id"],
                "to":       "CASH_PROXY",
                "strength": round(max(o["strength"], 0.05), 3),
                "reason":   f"{o['label']} çıkış, belirgin giriş hedefi yok",
            })

    # 4. Conviction: 0-100 (provider) → 0-5 ölçeğine indir (UI yoğunluk için)
    raw_conv = rd.get("conviction") or 0
    try:
        raw_conv = int(raw_conv)
    except (TypeError, ValueError):
        raw_conv = 0
    conviction_ui = max(0, min(5, round(raw_conv / 20)))

    primary_flow = str(rd.get("primary_flow") or "")

    return {
        "status":              "ok",
        "schema_version":      SCHEMA_VERSION,
        "source":              SOURCE,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "visual_mode":         VISUAL_MODE,
        "conviction":          conviction_ui,
        "primary_flow":        primary_flow,
        "nodes":               nodes,
        "flows":               flows,
        "fallback_reason":     None,
    }
