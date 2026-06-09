"""
FAZ 6 — Weekly Calibration / Auto Learning Engine.

build_weekly_calibration(memories, candidates, rechecks, lookback_days) -> dict

Amaç:
  Kapanmış trade'lerden (mistake_memory), candidate ve recheck verilerinden
  structured calibration raporu ve learning signal'lar üretir.

  Bu fazda hiçbir parametre değiştirilmez.
  Sadece learning_signals ve auto_tune_candidates üretilir.
  auto_apply_now her zaman False — bir sonraki FAZ'da safe-apply için kullanılacak.

Kritik garantiler:
  • Paper trading state mutate edilmez.
  • Karar motorunu etkilemez.
  • Mock / fake / placeholder veri üretmez.
  • auto_apply_now    = False (her zaman zorlanır).
  • auto_changes_allowed = False.
  • decision_permission = NO_EXECUTION, execution_mode = PAPER_SAFE.

Learning signal kaynakları (mistake_memory kayıtlarından):
  candidate-based (candidate_evidence.labels_seen):
    - bearish_pattern_ignored
    - early_entry_or_failed_1h_signal
    - confluence_holding_under_pressure
    - temporary_pullback_possible
    - news_not_confirmed
    - stop_too_close_candidate
  final-label-based (final_labels[].code):
    - good_confluence   (← confluence_validated)
    - unexplained_loss

Auto tune candidate üretim kuralları:
  • Minimum sample (_MIN_SAMPLE = 3) karşılanmalı.
  • auto_apply_now HER ZAMAN False — bu fazda hiçbir parametre değişmez.
  • safe_to_propose: ilgili sinyal eşiğini geçmişse True.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

_SCHEMA_VERSION = "weekly_calibration_v1"

# Minimum sample size to generate an auto_tune_candidate
_MIN_SAMPLE = 3

# Confidence thresholds
_MISTAKE_CONF_THRESHOLD = 0.50   # > %50 kayıp oranı → öneri üret
_SUCCESS_CONF_THRESHOLD = 0.60   # > %60 kazanç oranı → öneri üret
_NEWS_CONF_THRESHOLD    = 0.60   # news gate için daha yüksek eşik
_STOP_CONF_THRESHOLD    = 0.40   # stop mesafesi için daha düşük eşik (risk konusu)

# candidate-based signals (candidate_evidence.labels_seen'den okunur)
_CANDIDATE_SIGNALS = frozenset({
    "bearish_pattern_ignored",
    "early_entry_or_failed_1h_signal",
    "confluence_holding_under_pressure",
    "temporary_pullback_possible",
    "news_not_confirmed",
    "stop_too_close_candidate",
    # FAZ 11 — advanced technical
    "low_volume_breakout",
    "ema_stack_against_trade",
    "market_structure_broken",
    "vwap_rejection",
    "candle_close_failed",
})

# final-label-based signals → gerçek final_label kodu
_FINAL_LABEL_MAP: dict[str, str] = {
    "good_confluence":  "confluence_validated",
    "unexplained_loss": "unexplained_loss",
}

# Mistake-oriented signals (yüksek kayıp oranı = sinyal sorunlu)
_MISTAKE_SIGNALS = frozenset({
    "bearish_pattern_ignored",
    "early_entry_or_failed_1h_signal",
    "news_not_confirmed",
    "stop_too_close_candidate",
    "unexplained_loss",
    # FAZ 11 — advanced technical
    "low_volume_breakout",
    "ema_stack_against_trade",
    "market_structure_broken",
    "vwap_rejection",
    "candle_close_failed",
})

# Success-oriented signals (yüksek kazanç oranı = sinyal işe yarıyor)
_SUCCESS_SIGNALS = frozenset({
    "good_confluence",
})

# Tüm signal kodları (deterministik sıra)
_ALL_SIGNAL_CODES: list[str] = sorted(
    _CANDIDATE_SIGNALS | frozenset(_FINAL_LABEL_MAP.keys())
)

# Her signal için önerilen aksiyon
_SUGGESTED_ACTIONS: dict[str, str] = {
    "bearish_pattern_ignored":           "reduce_size_when_pattern_bearish",
    "early_entry_or_failed_1h_signal":   "wait_for_1h_reconfirmation",
    "confluence_holding_under_pressure": "hold_if_higher_tf_valid",
    "temporary_pullback_possible":       "hold_if_structure_intact",
    "news_not_confirmed":                "require_news_confirmation_before_entry",
    "stop_too_close_candidate":          "widen_stop_distance",
    "good_confluence":                   "maintain_entry_standards",
    "unexplained_loss":                  "improve_candidate_recheck_coverage",
    # FAZ 11 — advanced technical aksiyonları
    "low_volume_breakout":               "require_volume_confirmation_before_entry",
    "ema_stack_against_trade":           "require_ema_alignment_before_entry",
    "market_structure_broken":           "wait_for_structure_reset",
    "vwap_rejection":                    "require_vwap_alignment_before_entry",
    "candle_close_failed":               "require_candle_close_confirmation",
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_created_at(record: dict) -> datetime | None:
    raw = record.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None


# ── Lookback filtresi ─────────────────────────────────────────────────────────

def _filter_by_lookback(
    records: list[dict],
    lookback_days: int,
) -> list[dict]:
    """
    Son `lookback_days` gün içinde oluşturulmuş kayıtları filtreler.

    lookback_days <= 0 → tüm kayıtlar döner.
    created_at parse edilemiyorsa kayıt dahil edilir (atlanmaz).
    """
    if lookback_days <= 0:
        return list(records)

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    result: list[dict] = []

    for r in records:
        ts = _parse_created_at(r)
        if ts is None:
            # Parse edilemedi → dahil et (spec: unknown bucket'a al, atma)
            result.append(r)
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts >= cutoff:
            result.append(r)

    return result


# ── Evidence quality ──────────────────────────────────────────────────────────

def _compute_evidence_quality(memories: list[dict]) -> str:
    """
    full   — ≥60% memories'de hem candidate hem recheck kanıtı var.
    limited — ≤25% memories'de her ikisi de var.
    mixed  — arada.
    """
    if not memories:
        return "limited"

    both_count = 0
    for m in memories:
        cand_ev  = m.get("candidate_evidence") or {}
        rchk_ev  = m.get("recheck_evidence") or {}
        has_cand = cand_ev.get("evidence_quality") == "full"
        has_rchk = bool(rchk_ev.get("recheck_ids"))
        if has_cand and has_rchk:
            both_count += 1

    ratio = both_count / len(memories)
    if ratio >= 0.60:
        return "full"
    if ratio <= 0.25:
        return "limited"
    return "mixed"


# ── Sample ────────────────────────────────────────────────────────────────────

def _compute_sample(
    memories: list[dict],
    candidates: list[dict],
    rechecks: list[dict],
) -> dict[str, Any]:
    return {
        "trades":           len(memories),
        "memories":         len(memories),
        "candidates":       len(candidates),
        "rechecks":         len(rechecks),
        "evidence_quality": _compute_evidence_quality(memories),
    }


# ── Performance ───────────────────────────────────────────────────────────────

def _compute_performance(memories: list[dict]) -> dict[str, Any]:
    _zero: dict[str, Any] = {
        "win_rate":       0.0,
        "profit_factor":  0.0,
        "expectancy_pct": 0.0,
        "avg_win_pct":    0.0,
        "avg_loss_pct":   0.0,
        "max_loss_pct":   0.0,
        "total_pnl_pct":  0.0,
    }
    if not memories:
        return _zero

    wins:    list[float] = []
    losses:  list[float] = []
    all_pnl: list[float] = []

    for m in memories:
        result  = (m.get("final_summary") or {}).get("result", "")
        pnl_pct = float((m.get("trade") or {}).get("pnl_pct") or 0.0)
        all_pnl.append(pnl_pct)
        if result == "win":
            wins.append(pnl_pct)
        elif result == "loss":
            losses.append(pnl_pct)

    n_wins   = len(wins)
    n_losses = len(losses)
    denominator = n_wins + n_losses

    win_rate      = (n_wins / denominator) if denominator > 0 else 0.0
    total_win_abs = sum(abs(w) for w in wins)
    total_loss_abs = sum(abs(l) for l in losses)
    profit_factor  = (total_win_abs / total_loss_abs) if total_loss_abs > 0 else 0.0
    expectancy_pct = sum(all_pnl) / len(all_pnl)
    avg_win_pct    = sum(wins)   / len(wins)   if wins   else 0.0
    avg_loss_pct   = sum(losses) / len(losses) if losses else 0.0
    max_loss_pct   = min(losses) if losses else 0.0
    total_pnl_pct  = sum(all_pnl)

    return {
        "win_rate":       round(win_rate, 4),
        "profit_factor":  round(profit_factor, 4),
        "expectancy_pct": round(expectancy_pct, 4),
        "avg_win_pct":    round(avg_win_pct, 4),
        "avg_loss_pct":   round(avg_loss_pct, 4),
        "max_loss_pct":   round(max_loss_pct, 4),
        "total_pnl_pct":  round(total_pnl_pct, 4),
    }


# ── By asset ──────────────────────────────────────────────────────────────────

def _compute_by_asset(memories: list[dict]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0, "_pnl": []}
    )

    for m in memories:
        pair    = str((m.get("trade") or {}).get("pair") or "UNKNOWN")
        result  = (m.get("final_summary") or {}).get("result", "")
        pnl_pct = float((m.get("trade") or {}).get("pnl_pct") or 0.0)
        b = buckets[pair]
        b["trades"] += 1
        b["_pnl"].append(pnl_pct)
        if result == "win":
            b["wins"] += 1
        elif result == "loss":
            b["losses"] += 1

    out: dict[str, Any] = {}
    for pair, b in buckets.items():
        nw = b["wins"]
        nl = b["losses"]
        wrate = (nw / (nw + nl)) if (nw + nl) > 0 else 0.0
        pnl   = (sum(b["_pnl"]) / len(b["_pnl"])) if b["_pnl"] else 0.0
        out[pair] = {
            "trades":   b["trades"],
            "wins":     nw,
            "losses":   nl,
            "win_rate": round(wrate, 4),
            "pnl_pct":  round(pnl, 4),
        }
    return out


# ── By label ──────────────────────────────────────────────────────────────────

def _compute_by_label(memories: list[dict]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "_pnl": []}
    )

    for m in memories:
        pnl_pct = float((m.get("trade") or {}).get("pnl_pct") or 0.0)
        for lbl in (m.get("final_labels") or []):
            code = lbl.get("code")
            if not code:
                continue
            b = buckets[code]
            b["count"] += 1
            b["_pnl"].append(pnl_pct)

    return {
        code: {
            "count":       b["count"],
            "avg_pnl_pct": round(sum(b["_pnl"]) / len(b["_pnl"]), 4)
            if b["_pnl"] else 0.0,
        }
        for code, b in buckets.items()
    }


# ── By timeframe ──────────────────────────────────────────────────────────────

def _compute_by_timeframe(memories: list[dict]) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0}
    )

    for m in memories:
        tf     = str((m.get("opening_context") or {}).get("primary_tf") or "unknown")
        result = (m.get("final_summary") or {}).get("result", "")
        b = buckets[tf]
        b["trades"] += 1
        if result == "win":
            b["wins"] += 1
        elif result == "loss":
            b["losses"] += 1

    out: dict[str, Any] = {}
    for tf, b in buckets.items():
        nw = b["wins"]
        nl = b["losses"]
        out[tf] = {
            "trades":   b["trades"],
            "wins":     nw,
            "losses":   nl,
            "win_rate": round(nw / (nw + nl), 4) if (nw + nl) > 0 else 0.0,
        }
    return out


# ── By regime ─────────────────────────────────────────────────────────────────

def _compute_by_regime(memories: list[dict]) -> dict[str, Any]:
    """Açılış anındaki confluence_status'a göre piyasa rejimi gruplaması."""
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trades": 0, "wins": 0, "losses": 0}
    )

    for m in memories:
        regime = str(
            (m.get("opening_context") or {}).get("confluence_status") or "unknown"
        )
        result = (m.get("final_summary") or {}).get("result", "")
        b = buckets[regime]
        b["trades"] += 1
        if result == "win":
            b["wins"] += 1
        elif result == "loss":
            b["losses"] += 1

    out: dict[str, Any] = {}
    for regime, b in buckets.items():
        nw = b["wins"]
        nl = b["losses"]
        out[regime] = {
            "trades":   b["trades"],
            "wins":     nw,
            "losses":   nl,
            "win_rate": round(nw / (nw + nl), 4) if (nw + nl) > 0 else 0.0,
        }
    return out


# ── Signal varlık tespiti ──────────────────────────────────────────────────────

def _signal_present(signal_code: str, memory: dict) -> bool:
    """Bu memory kaydında belirtilen sinyal mevcut mu?"""
    if signal_code in _FINAL_LABEL_MAP:
        target_code = _FINAL_LABEL_MAP[signal_code]
        return any(
            l.get("code") == target_code
            for l in (memory.get("final_labels") or [])
        )
    # candidate-based: candidate_evidence.labels_seen listesinden kontrol
    labels_seen = (
        (memory.get("candidate_evidence") or {}).get("labels_seen") or []
    )
    return signal_code in labels_seen


# ── Learning signals ──────────────────────────────────────────────────────────

def _compute_learning_signals(memories: list[dict]) -> list[dict[str, Any]]:
    """
    Her signal kodu için seen/wins/losses/avg_pnl/confidence hesaplar.

    confidence:
      mistake signals → kayıp oranı (losses / seen)
      success signals → kazanç oranı (wins / seen)
      mixed signals   → dominant yön oranı
      sample < _MIN_SAMPLE → 0.0 + note="not_enough_data"
    """
    signals: list[dict[str, Any]] = []

    for code in _ALL_SIGNAL_CODES:
        seen_mems = [m for m in memories if _signal_present(code, m)]
        wins_mems  = [m for m in seen_mems
                      if (m.get("final_summary") or {}).get("result") == "win"]
        loss_mems  = [m for m in seen_mems
                      if (m.get("final_summary") or {}).get("result") == "loss"]
        all_pnl    = [
            float((m.get("trade") or {}).get("pnl_pct") or 0.0)
            for m in seen_mems
        ]

        n_seen   = len(seen_mems)
        n_wins   = len(wins_mems)
        n_losses = len(loss_mems)
        avg_pnl  = round(sum(all_pnl) / n_seen, 4) if seen_mems else 0.0

        if n_seen < _MIN_SAMPLE:
            confidence = 0.0
            note: str | None = "not_enough_data"
        elif code in _MISTAKE_SIGNALS:
            confidence = round(n_losses / n_seen, 2)
            note = None
        elif code in _SUCCESS_SIGNALS:
            confidence = round(n_wins / n_seen, 2)
            note = None
        else:
            # Mixed signal — dominant yön oranı
            confidence = round(max(n_wins, n_losses) / n_seen, 2)
            note = None

        entry: dict[str, Any] = {
            "code":                    code,
            "seen":                    n_seen,
            "wins":                    n_wins,
            "losses":                  n_losses,
            "avg_pnl_pct":             avg_pnl,
            "confidence":              confidence,
            "suggested_future_action": _SUGGESTED_ACTIONS.get(code, "review_required"),
        }
        if note:
            entry["note"] = note

        signals.append(entry)

    return signals


# ── Auto tune candidates ───────────────────────────────────────────────────────

def _compute_auto_tune_candidates(
    learning_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Learning signal'lardan parameter_adjustment_candidate'lar üretir.

    Kurallar:
      • min_sample_met: seen >= _MIN_SAMPLE
      • safe_to_propose: ilgili rate eşiğini geçiyorsa True
      • auto_apply_now: HER ZAMAN False — bu fazda parametre değişmez
    """
    candidates: list[dict[str, Any]] = []
    by_code = {s["code"]: s for s in learning_signals}

    # ── Rule 1: bearish_pattern_ignored → position_size_multiplier ────────────
    sig = by_code.get("bearish_pattern_ignored")
    if sig and sig["seen"] >= _MIN_SAMPLE:
        loss_rate = sig["losses"] / sig["seen"]
        candidates.append({
            "candidate_id":    str(uuid.uuid4()),
            "type":            "parameter_adjustment_candidate",
            "target":          "position_size_multiplier",
            "condition":       "LONG + pattern_bearish OR SHORT + pattern_bullish",
            "suggested_change": -0.15,
            "reason": (
                f"bearish_pattern_ignored {sig['seen']} kez gözlemlendi; "
                f"kayıp oranı {loss_rate:.0%}. "
                "Karşı-pattern girişlerde pozisyon boyutu azaltılabilir."
            ),
            "min_sample_met":  True,
            "safe_to_propose": loss_rate > _MISTAKE_CONF_THRESHOLD,
            "auto_apply_now":  False,
        })

    # ── Rule 2: early_entry → entry_confirmation_bars ─────────────────────────
    sig = by_code.get("early_entry_or_failed_1h_signal")
    if sig and sig["seen"] >= _MIN_SAMPLE:
        loss_rate = sig["losses"] / sig["seen"]
        candidates.append({
            "candidate_id":    str(uuid.uuid4()),
            "type":            "parameter_adjustment_candidate",
            "target":          "entry_confirmation_bars",
            "condition":       "primary_tf=1h + 1h_signal_inversion_detected",
            "suggested_change": 1,
            "reason": (
                f"early_entry_or_failed_1h_signal {sig['seen']} kez gözlemlendi; "
                f"kayıp oranı {loss_rate:.0%}. "
                "1H giriş için ek doğrulama barı gerektirebilir."
            ),
            "min_sample_met":  True,
            "safe_to_propose": loss_rate > _MISTAKE_CONF_THRESHOLD,
            "auto_apply_now":  False,
        })

    # ── Rule 3: stop_too_close → stop_distance_multiplier ────────────────────
    sig = by_code.get("stop_too_close_candidate")
    if sig and sig["seen"] >= _MIN_SAMPLE:
        loss_rate = sig["losses"] / sig["seen"]
        candidates.append({
            "candidate_id":    str(uuid.uuid4()),
            "type":            "parameter_adjustment_candidate",
            "target":          "stop_distance_multiplier",
            "condition":       "stop_proximity_ratio < 0.30",
            "suggested_change": 0.20,
            "reason": (
                f"stop_too_close_candidate {sig['seen']} kez gözlemlendi; "
                f"kayıp oranı {loss_rate:.0%}. "
                "Stop mesafesi %%20 artırılabilir."
            ),
            "min_sample_met":  True,
            "safe_to_propose": loss_rate > _STOP_CONF_THRESHOLD,
            "auto_apply_now":  False,
        })

    # ── Rule 4: news_not_confirmed → require_news_confirmation ────────────────
    sig = by_code.get("news_not_confirmed")
    if sig and sig["seen"] >= _MIN_SAMPLE:
        loss_rate = sig["losses"] / sig["seen"]
        candidates.append({
            "candidate_id":    str(uuid.uuid4()),
            "type":            "parameter_adjustment_candidate",
            "target":          "require_news_confirmation",
            "condition":       "entry_without_news_event",
            "suggested_change": "enable",
            "reason": (
                f"news_not_confirmed {sig['seen']} kez gözlemlendi; "
                f"kayıp oranı {loss_rate:.0%}. "
                "Haber olmadan açılan pozisyonlar için news gate aktif edilebilir."
            ),
            "min_sample_met":  True,
            "safe_to_propose": loss_rate > _NEWS_CONF_THRESHOLD,
            "auto_apply_now":  False,
        })

    # ── Rule 5: confluence_holding_under_pressure → early_exit_threshold ──────
    sig = by_code.get("confluence_holding_under_pressure")
    if sig and sig["seen"] >= _MIN_SAMPLE:
        win_rate = sig["wins"] / sig["seen"]
        candidates.append({
            "candidate_id":    str(uuid.uuid4()),
            "type":            "parameter_adjustment_candidate",
            "target":          "early_exit_threshold_pct",
            "condition":       "confluence_aligned + higher_tf_bullish + pullback",
            "suggested_change": -0.5,
            "reason": (
                f"confluence_holding_under_pressure {sig['seen']} kez gözlemlendi; "
                f"kazanç oranı {win_rate:.0%}. "
                "Confluence baskı altındayken erken çıkış eşiği düşürülebilir (daha uzun tut)."
            ),
            "min_sample_met":  True,
            "safe_to_propose": win_rate > _SUCCESS_CONF_THRESHOLD,
            "auto_apply_now":  False,
        })

    return candidates


# ── Risk notları ──────────────────────────────────────────────────────────────

def _compute_risk_notes(
    memories: list[dict],
    evidence_quality: str,
) -> list[str]:
    notes: list[str] = []

    if evidence_quality == "limited":
        notes.append(
            "Evidence limited: eski trade'lerin büyük bölümünde candidate/recheck kaydı yok."
            " Daha sağlıklı calibration için ilerideki trade'lerin"
            " candidate + recheck verisi toplanmalı."
        )
    elif evidence_quality == "mixed":
        notes.append(
            "Evidence mixed: bazı trade'lerde candidate/recheck kanıtı eksik."
            " Sinyal yorumları ihtiyatla değerlendirilmeli."
        )

    n = len(memories)
    if n < _MIN_SAMPLE:
        notes.append(
            f"Sample çok küçük ({n} memory). "
            f"Güvenilir calibration için en az {_MIN_SAMPLE} kapanmış trade gerekli."
        )
    elif n < 10:
        notes.append(
            f"Sample {n} memory ile sınırlı."
            " Daha fazla trade kapandıkça sinyal güvenilirliği artacak."
        )

    return notes


# ── Öneriler ──────────────────────────────────────────────────────────────────

def _compute_recommendations(
    memories: list[dict],
    learning_signals: list[dict[str, Any]],
    auto_tune_candidates: list[dict[str, Any]],
    evidence_quality: str,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    n = len(memories)

    # Yetersiz sample → erken dön
    if n < _MIN_SAMPLE:
        recommendations.append({
            "type":    "more_data_needed",
            "target":  "overall",
            "message": (
                f"Calibration için yeterli veri yok ({n} memory). "
                f"En az {_MIN_SAMPLE} kapanmış trade ile anlamlı sinyal üretilebilir."
            ),
        })
        return recommendations

    if evidence_quality == "limited":
        recommendations.append({
            "type":    "review_only",
            "target":  "data_collection",
            "message": (
                "Daha sağlıklı calibration için candidate/recheck verisiyle"
                " kapanan daha fazla trade bekle."
            ),
        })

    # safe_to_propose olan auto tune adaylarını öneri olarak ekle
    for atc in auto_tune_candidates:
        if atc.get("safe_to_propose"):
            recommendations.append({
                "type":    "future_auto_tune",
                "target":  atc["target"],
                "message": atc["reason"],
            })

    # Güçlü negatif sinyal yoksa pozitif not ekle
    safe_proposals = [atc for atc in auto_tune_candidates if atc.get("safe_to_propose")]
    if not safe_proposals:
        high_conf = [
            s for s in learning_signals
            if s["code"] in _MISTAKE_SIGNALS
            and s["confidence"] >= _MISTAKE_CONF_THRESHOLD
            and s["seen"] > 0
        ]
        if not high_conf:
            recommendations.append({
                "type":    "review_only",
                "target":  "overall",
                "message": (
                    "Güçlü negatif sinyal tespit edilmedi."
                    " Mevcut strateji kapsamlı revizyon gerektirmiyor."
                ),
            })

    return recommendations


# ── Public API ────────────────────────────────────────────────────────────────

def build_weekly_calibration(
    memories: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    rechecks: list[dict[str, Any]],
    lookback_days: int = 7,
) -> dict[str, Any]:
    """
    Haftalık calibration raporu ve learning signal'lar üretir.

    Args:
        memories:      load_recent_mistake_memory() çıktısı (final_memory kayıtları).
        candidates:    load_recent_learning_candidates() çıktısı.
        rechecks:      load_recent_position_rechecks() çıktısı.
        lookback_days: Kaç günlük veri bakılacak (0 = tümü).

    Returns:
        weekly_calibration_v1 schema dict,
        veya {"status": "not_created", "reason": "no_memory_records"}.

    Garantiler:
        • Paper trading state'ini okumaz veya mutate etmez.
        • Karar motorunu etkilemez.
        • Mock / fake veri üretmez.
        • auto_apply_now = False (her zaman).
        • auto_changes_allowed = False.
    """
    filtered_memories   = _filter_by_lookback(memories,   lookback_days)
    filtered_candidates = _filter_by_lookback(candidates, lookback_days)
    filtered_rechecks   = _filter_by_lookback(rechecks,   lookback_days)

    if not filtered_memories:
        return {
            "status":              "not_created",
            "reason":              "no_memory_records",
            "decision_permission": "NO_EXECUTION",
            "execution_mode":      "PAPER_SAFE",
            "auto_changes_allowed": False,
        }

    sample           = _compute_sample(
        filtered_memories, filtered_candidates, filtered_rechecks
    )
    evidence_quality = sample["evidence_quality"]
    performance      = _compute_performance(filtered_memories)
    by_asset         = _compute_by_asset(filtered_memories)
    by_label         = _compute_by_label(filtered_memories)
    by_timeframe     = _compute_by_timeframe(filtered_memories)
    by_regime        = _compute_by_regime(filtered_memories)
    learning_signals = _compute_learning_signals(filtered_memories)
    auto_tune_cands  = _compute_auto_tune_candidates(learning_signals)
    risk_notes       = _compute_risk_notes(filtered_memories, evidence_quality)
    recommendations  = _compute_recommendations(
        filtered_memories, learning_signals, auto_tune_cands, evidence_quality
    )

    return {
        "calibration_id":       str(uuid.uuid4()),
        "created_at":           _utc_now_iso(),
        "schema_version":       _SCHEMA_VERSION,
        "decision_permission":  "NO_EXECUTION",
        "execution_mode":       "PAPER_SAFE",
        "report_type":          "performance_learning_report",
        "auto_changes_allowed": False,
        "lookback_days":        lookback_days,
        "sample":               sample,
        "performance":          performance,
        "by_asset":             by_asset,
        "by_label":             by_label,
        "by_timeframe":         by_timeframe,
        "by_regime":            by_regime,
        "learning_signals":     learning_signals,
        "auto_tune_candidates": auto_tune_cands,
        "risk_notes":           risk_notes,
        "recommendations":      recommendations,
    }
