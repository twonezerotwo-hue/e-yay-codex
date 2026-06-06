"""
Paper Trading Öğrenme Motoru.

Mekanik:
  1. SIGNAL FINGERPRINT — her sinyalin bir "imzası" var (regime + direction +
     score bucket + confluence_status + dominant_module). Aynı imzalı sinyaller
     "aynı durum" sayılır.

  2. HISTORY LOOKUP — geçmiş trade'ler arasından aynı imzalı olanları bul.
     Win rate hesapla, ortalama PnL'i çıkar.

  3. AVOIDANCE — eğer imzanın win rate'i ÇOK düşük (örn. %30 altı + min 3 örnek),
     bu sinyal kümesinde işlem AÇMA. "Öğrenilmiş hata".

  4. BOOST — win rate çok yüksekse (örn. %70 üzeri), pozisyon büyüt.

  5. MODULE PERFORMANCE — her modülün kazanan vs kaybeden trade'lerdeki katkısı.
     Negatif skew olan modülün ağırlığı düşürülmeli (gelecek revizyon önerisi).
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any


# ── Sabitler ──────────────────────────────────────────────────────────────────

# Skor bucket'ları — yakın skorları aynı kümede grupla
SCORE_BUCKETS: list[tuple[float, float, str]] = [
    (0, 30, "extreme_bear"),
    (30, 40, "strong_bear"),
    (40, 45, "weak_bear"),
    (45, 55, "neutral"),
    (55, 60, "weak_bull"),
    (60, 70, "strong_bull"),
    (70, 100, "extreme_bull"),
]

# Avoidance eşikleri
MIN_SAMPLES_FOR_LEARNING = 3   # en az 3 örnek olmadan karar verme
AVOID_WIN_RATE_THRESHOLD  = 0.30  # %30 altı win rate → avoid
BOOST_WIN_RATE_THRESHOLD  = 0.70  # %70 üzeri win rate → boost (×1.3)
BOOST_MULTIPLIER          = 1.3


def _score_to_bucket(score: float) -> str:
    """Skor → bucket etiketi."""
    for lo, hi, label in SCORE_BUCKETS:
        if lo <= score < hi:
            return label
    return "extreme_bull" if score >= 100 else "extreme_bear"


def _dominant_module(contributions: dict[str, dict]) -> str:
    """En büyük katkılı modül adı."""
    if not contributions:
        return "unknown"
    sorted_mods = sorted(
        contributions.items(),
        key=lambda kv: kv[1].get("weighted_score", 0),
        reverse=True,
    )
    return sorted_mods[0][0] if sorted_mods else "unknown"


# ── Public — Fingerprint ──────────────────────────────────────────────────────

def build_signal_fingerprint(signal: dict[str, Any]) -> str:
    """
    Sinyalin imzasını üret. Aynı durumda aynı imza döner.

    Format: "{asset}|{regime}|{direction}|{score_bucket}|{confluence_status}|{dominant_module}"
    """
    asset             = signal.get("symbol", "")
    regime            = signal.get("raw_regime", "")
    direction         = signal.get("final_direction") or "neutral"
    score             = signal.get("final_score") or 50.0
    score_bucket      = _score_to_bucket(float(score))

    confluence        = signal.get("confluence") or {}
    confluence_status = confluence.get("status", "none") if isinstance(confluence, dict) else "none"

    contributions = (signal.get("base") or {}).get("contributions", {}) or {}
    dominant = _dominant_module(contributions)

    parts = [asset, regime, direction, score_bucket, confluence_status, dominant]
    return "|".join(parts)


# ── History lookup ───────────────────────────────────────────────────────────

def find_similar_trades(
    fingerprint: str,
    trades: list[Any],
    limit: int = 20,
) -> list[Any]:
    """Aynı fingerprint'li tarihteki trade'leri döndür (en yeni → en eski)."""
    matching = [t for t in trades if getattr(t, "fingerprint", "") == fingerprint]
    matching.sort(key=lambda t: getattr(t, "exit_at", ""), reverse=True)
    return matching[:limit]


def win_rate_for_fingerprint(
    fingerprint: str,
    trades: list[Any],
) -> dict[str, Any]:
    """
    Bir imzanın geçmiş performansı.

    Returns:
      {
        "fingerprint": str,
        "total":       int,
        "wins":        int,
        "losses":      int,
        "win_rate":    float (0-1),
        "avg_pnl":     float,
        "total_pnl":   float,
        "decision":    "AVOID" | "BOOST" | "NORMAL" | "INSUFFICIENT_DATA",
        "reason":      str,
      }
    """
    similar = find_similar_trades(fingerprint, trades)
    total = len(similar)

    if total < MIN_SAMPLES_FOR_LEARNING:
        return {
            "fingerprint":  fingerprint,
            "total":        total,
            "wins":         sum(1 for t in similar if t.verdict == "WIN"),
            "losses":       sum(1 for t in similar if t.verdict == "LOSS"),
            "win_rate":     None,
            "avg_pnl":      None,
            "total_pnl":    sum(t.pnl_usd for t in similar) if similar else 0.0,
            "decision":     "INSUFFICIENT_DATA",
            "reason":       f"Sadece {total} örnek var (min {MIN_SAMPLES_FOR_LEARNING}).",
        }

    wins   = sum(1 for t in similar if t.verdict == "WIN")
    losses = sum(1 for t in similar if t.verdict == "LOSS")
    win_rate = wins / total if total > 0 else 0.0
    total_pnl = sum(t.pnl_usd for t in similar)
    avg_pnl   = total_pnl / total

    if win_rate < AVOID_WIN_RATE_THRESHOLD:
        decision = "AVOID"
        reason   = f"Geçmişte {total} işlem, win rate %{win_rate*100:.0f} (eşik %{AVOID_WIN_RATE_THRESHOLD*100:.0f})."
    elif win_rate > BOOST_WIN_RATE_THRESHOLD:
        decision = "BOOST"
        reason   = f"Güçlü performans: {total} işlem, win rate %{win_rate*100:.0f}."
    else:
        decision = "NORMAL"
        reason   = f"Ortalama performans: {total} işlem, win rate %{win_rate*100:.0f}."

    return {
        "fingerprint":  fingerprint,
        "total":        total,
        "wins":         wins,
        "losses":       losses,
        "win_rate":     round(win_rate, 3),
        "avg_pnl":      round(avg_pnl, 2),
        "total_pnl":    round(total_pnl, 2),
        "decision":     decision,
        "reason":       reason,
    }


# ── Avoidance check (tick öncesi çağrılır) ────────────────────────────────────

def should_avoid_or_boost(
    signal: dict[str, Any],
    trades: list[Any],
) -> dict[str, Any]:
    """
    Tick öncesi check: bu sinyal kümesinde işlem açmalı mıyız?

    Returns:
      {
        "fingerprint":      str,
        "action":           "AVOID" | "BOOST" | "NORMAL" | "INSUFFICIENT_DATA",
        "size_multiplier":  float (default 1.0, BOOST → BOOST_MULTIPLIER),
        "reason":           str,
        "history":          dict (win_rate_for_fingerprint çıktısı),
      }
    """
    fp = build_signal_fingerprint(signal)
    history = win_rate_for_fingerprint(fp, trades)

    if history["decision"] == "AVOID":
        return {
            "fingerprint":     fp,
            "action":          "AVOID",
            "size_multiplier": 0.0,
            "reason":          history["reason"],
            "history":         history,
        }
    if history["decision"] == "BOOST":
        return {
            "fingerprint":     fp,
            "action":          "BOOST",
            "size_multiplier": BOOST_MULTIPLIER,
            "reason":          history["reason"],
            "history":         history,
        }
    return {
        "fingerprint":     fp,
        "action":          history["decision"],   # NORMAL veya INSUFFICIENT_DATA
        "size_multiplier": 1.0,
        "reason":          history["reason"],
        "history":         history,
    }


# ── Module performance — ağırlık revizyonu için ──────────────────────────────

def analyze_module_performance(trades: list[Any]) -> dict[str, Any]:
    """
    Her modülün kazanan vs kaybeden trade'lerdeki ortalama katkısını çıkar.

    Pozitif skew olan modül (kazananlarda daha yüksek katkı) → ağırlığı artırılabilir.
    Negatif skew → ağırlığı düşürülmeli.

    Returns:
      {
        "touche":      {"in_winners": x, "in_losers": y, "skew": z, "samples": n},
        "fundamental": {...},
        ...
        "weight_revision_suggestions": {...}
      }
    """
    from app.services.consensus_engine import CANONICAL_MODULES

    closed = [t for t in trades if t.verdict in ("WIN", "LOSS")]
    if not closed:
        return {"status": "no_data", "samples": 0}

    perf: dict[str, dict] = {m: {"in_winners": [], "in_losers": []} for m in CANONICAL_MODULES}

    for t in closed:
        signal = getattr(t, "open_signal", {}) or {}
        contributions = (signal.get("base") or {}).get("contributions", {}) or {}
        for module in CANONICAL_MODULES:
            contrib = (contributions.get(module) or {}).get("weighted_score", 0.0)
            try:
                contrib = float(contrib)
            except (TypeError, ValueError):
                contrib = 0.0
            if t.verdict == "WIN":
                perf[module]["in_winners"].append(contrib)
            else:
                perf[module]["in_losers"].append(contrib)

    summary: dict[str, Any] = {}
    for module in CANONICAL_MODULES:
        w = perf[module]["in_winners"]
        l = perf[module]["in_losers"]
        avg_w = sum(w) / len(w) if w else 0.0
        avg_l = sum(l) / len(l) if l else 0.0
        skew = avg_w - avg_l   # pozitif = kazandıran modül, negatif = kaybettiren
        summary[module] = {
            "avg_contribution_in_winners": round(avg_w, 3),
            "avg_contribution_in_losers":  round(avg_l, 3),
            "skew":                        round(skew, 3),
            "samples":                     {"winners": len(w), "losers": len(l)},
        }

    # ── Ağırlık revizyon önerileri ─
    suggestions = []
    for module, data in summary.items():
        if data["samples"]["winners"] + data["samples"]["losers"] < 5:
            continue
        skew = data["skew"]
        if skew > 3:
            suggestions.append({
                "module":     module,
                "action":     "INCREASE_WEIGHT",
                "skew":       skew,
                "reason":     f"Kazananlarda ortalama +{skew:.1f} daha fazla katkı.",
            })
        elif skew < -3:
            suggestions.append({
                "module":     module,
                "action":     "DECREASE_WEIGHT",
                "skew":       skew,
                "reason":     f"Kaybettirenlerde ortalama {abs(skew):.1f} daha fazla katkı.",
            })

    return {
        "status":  "ok",
        "samples": {"wins": sum(1 for t in closed if t.verdict == "WIN"),
                    "losses": sum(1 for t in closed if t.verdict == "LOSS"),
                    "total": len(closed)},
        "by_module": summary,
        "weight_revision_suggestions": suggestions,
    }


# ── Genel öğrenme raporu ──────────────────────────────────────────────────────

def build_learning_report(trades: list[Any]) -> dict[str, Any]:
    """Tüm öğrenme verilerini tek raporda topla — UI / endpoint için."""
    closed = [t for t in trades if t.verdict in ("WIN", "LOSS")]

    # Her fingerprint için win rate
    fp_groups: dict[str, list] = {}
    for t in closed:
        fp = getattr(t, "fingerprint", "") or ""
        if not fp:
            continue
        fp_groups.setdefault(fp, []).append(t)

    fp_stats: list[dict[str, Any]] = []
    for fp, group in fp_groups.items():
        wins   = sum(1 for t in group if t.verdict == "WIN")
        losses = sum(1 for t in group if t.verdict == "LOSS")
        total  = len(group)
        win_rate = wins / total if total > 0 else 0.0
        total_pnl = sum(t.pnl_usd for t in group)
        fp_stats.append({
            "fingerprint": fp,
            "total":       total,
            "wins":        wins,
            "losses":      losses,
            "win_rate":    round(win_rate, 3),
            "total_pnl":   round(total_pnl, 2),
            "decision":    (
                "AVOID" if total >= MIN_SAMPLES_FOR_LEARNING and win_rate < AVOID_WIN_RATE_THRESHOLD
                else "BOOST" if total >= MIN_SAMPLES_FOR_LEARNING and win_rate > BOOST_WIN_RATE_THRESHOLD
                else "NORMAL" if total >= MIN_SAMPLES_FOR_LEARNING
                else "INSUFFICIENT_DATA"
            ),
        })

    fp_stats.sort(key=lambda x: x["total"], reverse=True)

    return {
        "module_performance":  analyze_module_performance(trades),
        "fingerprint_stats":   fp_stats,
        "avoid_count":         sum(1 for s in fp_stats if s["decision"] == "AVOID"),
        "boost_count":         sum(1 for s in fp_stats if s["decision"] == "BOOST"),
        "thresholds": {
            "min_samples":    MIN_SAMPLES_FOR_LEARNING,
            "avoid_win_rate": AVOID_WIN_RATE_THRESHOLD,
            "boost_win_rate": BOOST_WIN_RATE_THRESHOLD,
            "boost_multiplier": BOOST_MULTIPLIER,
        },
    }


__all__ = [
    "build_signal_fingerprint",
    "find_similar_trades",
    "win_rate_for_fingerprint",
    "should_avoid_or_boost",
    "analyze_module_performance",
    "build_learning_report",
]
