"""
FAZ 5B — Mistake Memory Service.

build_mistake_memory(closed_trade, matching_candidates, matching_rechecks) -> dict

Amaç:
  Kapanmış paper trade için final öğrenme kaydı üretir.
  is_final=True — pozisyon kapandıktan sonra çalışır.

Kritik garantiler:
  • Trade açma / kapatma / küçültme / add yok.
  • Paper trading karar mantığını değiştirmez.
  • Mock / fake / placeholder veri üretmez.
  • Yalnızca gerçek kapanmış trade + matching candidates/rechecks kullanılır.
  • is_final = True (store tarafından da zorlanır).
  • decision_permission = NO_EXECUTION, execution_mode = PAPER_SAFE.

Final label kuralları:
  1.  bearish_pattern_ignored_confirmed   — candidate: bearish_pattern_ignored + LOSS
  2.  bearish_pattern_ignored_but_trade_won — candidate: bearish_pattern_ignored + WIN
  3.  early_entry_confirmed               — candidate: early_entry_or_failed_1h_signal + LOSS
  4.  confluence_validated                — candidate: confluence_holding_under_pressure + WIN
  5.  temporary_pullback_validated        — candidate: temporary_pullback_possible + WIN
  6.  news_not_confirmed_confirmed        — candidate: news_not_confirmed + LOSS
  7.  stop_too_close_unverified           — candidate: stop_too_close_candidate + exit=stop_loss
      (stop_too_close_confirmed için post-exit recovery verisi gerekir; bu sistemde yok)
  8.  good_trade_no_issue                 — WIN + candidate'larda warning/critical label yoktu
  9.  unexplained_loss                    — LOSS + candidate yok + recheck yok

Severity:
  high   — birden fazla onaylı hata
  medium — tek onaylı hata
  low    — bilgi amaçlı başarı / düşük önem
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

_SCHEMA_VERSION = "mistake_memory_v1"

_BULLISH_DIR = frozenset({"bullish", "long", "buy"})
_BEARISH_DIR = frozenset({"bearish", "short", "sell"})

# Recheck status ağırlık sıraması
_RECHECK_STATUS_ORDER: dict[str, int] = {
    "invalid":   3,
    "weakening": 2,
    "valid":     1,
    "unknown":   0,
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _flabel(
    code: str,
    type_: str,
    severity: str,
    reason: str,
) -> dict[str, Any]:
    return {"code": code, "type": type_, "severity": severity, "reason": reason}


def _trade_fingerprint(trade: dict) -> str:
    """
    Trade için duplicate önleme anahtarı üretir.

    trade_id varsa: "tid_{trade_id}"
    Yoksa: "pair|entry|exit|entry_time|exit_time"
    """
    trade_id = trade.get("trade_id") or trade.get("id")
    if trade_id:
        return f"tid_{trade_id}"
    pair        = str(trade.get("pair") or "")
    entry_price = f"{float(trade.get('entry_price') or 0):.4f}"
    exit_price  = f"{float(trade.get('exit_price') or 0):.4f}"
    entry_time  = str(trade.get("opened_at") or trade.get("entry_time") or "")[:19]
    exit_time   = str(trade.get("closed_at") or trade.get("exit_time") or "")[:19]
    return f"{pair}|{entry_price}|{exit_price}|{entry_time}|{exit_time}"


def _normalize_exit_reason(raw: str) -> str:
    r = raw.lower()
    if "stop" in r:
        return "stop_loss"
    if "tp" in r or "profit" in r or "take" in r:
        return "take_profit"
    if "manual" in r:
        return "manual_close"
    if "timeout" in r or "expir" in r:
        return "timeout"
    return "unknown"


def _determine_result(pnl_pct: float) -> str:
    if pnl_pct > 0.05:
        return "win"
    if pnl_pct < -0.05:
        return "loss"
    return "breakeven"


def _compute_holding_minutes(trade: dict) -> int | None:
    opened_at = trade.get("opened_at") or trade.get("entry_time")
    closed_at = trade.get("closed_at") or trade.get("exit_time")
    if not opened_at or not closed_at:
        return None
    try:
        t1 = datetime.fromisoformat(str(opened_at))
        t2 = datetime.fromisoformat(str(closed_at))
        return max(0, int((t2 - t1).total_seconds() / 60))
    except Exception:  # noqa: BLE001
        return None


# ── Opening context ───────────────────────────────────────────────────────────

def _build_opening_context(trade: dict) -> dict[str, Any]:
    """Trade'in open_signal'ından açılış anındaki audit bağlamını çıkarır."""
    sig        = trade.get("open_signal") or {}
    primary_tf = str(sig.get("primary_tf") or "")
    tf_signals = sig.get("tf_signals") or {}
    confluence = sig.get("confluence") or {}
    td         = sig.get("timeframe_decision") or {}

    primary_data      = tf_signals.get(primary_tf) or {}
    opening_direction = str(
        primary_data.get("direction") or sig.get("final_direction") or ""
    ).lower()

    one_h_data   = tf_signals.get("1h") or {}
    pattern_bias = str(one_h_data.get("direction") or opening_direction or "").lower()

    return {
        "final_score":          sig.get("final_score"),
        "primary_tf":           primary_tf,
        "risk_tf":              str(td.get("selected_timeframe") or ""),
        "confluence_status":    str(confluence.get("status") or "unknown").lower(),
        "opening_direction":    opening_direction,
        "pattern_bias":         pattern_bias,
        "pattern_score":        sig.get("pattern_score"),
        "news_event_present":   bool(
            sig.get("news_event_present") or sig.get("has_news_event") or False
        ),
        "agent_thesis_context": sig.get("agent_thesis_context"),
    }


# ── Recheck severity ──────────────────────────────────────────────────────────

def _worst_recheck_status(rechecks: list[dict]) -> str:
    statuses = [
        str((r.get("summary") or {}).get("status") or "unknown").lower()
        for r in rechecks
    ]
    if not statuses:
        return "unknown"
    return max(statuses, key=lambda s: _RECHECK_STATUS_ORDER.get(s, 0))


# ── Final labels ──────────────────────────────────────────────────────────────

def _build_final_labels(  # noqa: PLR0912
    result: str,
    exit_reason: str,
    labels_seen: set[str],
    matching_candidates: list[dict],
    matching_rechecks: list[dict],
) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []

    # ── 1. bearish_pattern_ignored outcomes ───────────────────────────────────
    if "bearish_pattern_ignored" in labels_seen:
        if result == "loss":
            labels.append(_flabel(
                "bearish_pattern_ignored_confirmed",
                "mistake", "medium",
                "Pattern bearish uyarısı haklı çıktı; trade stop/loss ile kapandı."
                " Pattern sinyali giriş kararında dikkate alınmalıydı.",
            ))
        elif result == "win":
            labels.append(_flabel(
                "bearish_pattern_ignored_but_trade_won",
                "neutral", "low",
                "Pattern bearish uyarısına rağmen trade kazandı."
                " Confluence veya yüksek TF sinyali daha güçlü çalışmış olabilir.",
            ))

    # ── 2. early_entry_confirmed ──────────────────────────────────────────────
    if "early_entry_or_failed_1h_signal" in labels_seen and result == "loss":
        labels.append(_flabel(
            "early_entry_confirmed",
            "mistake", "medium",
            "1H sinyali bozuldu ve trade loss oldu."
            " Daha yüksek TF doğrulaması veya geciktirilmiş giriş daha iyi olurdu.",
        ))

    # ── 3. confluence_validated ───────────────────────────────────────────────
    if "confluence_holding_under_pressure" in labels_seen and result == "win":
        labels.append(_flabel(
            "confluence_validated",
            "success", "low",
            "Negatife giren pozisyon 4H/1D confluence desteğiyle toparlayıp"
            " kâra geçerek kapandı. Confluence analizi doğrulandı.",
        ))

    # ── 4. temporary_pullback_validated ──────────────────────────────────────
    if "temporary_pullback_possible" in labels_seen and result == "win":
        labels.append(_flabel(
            "temporary_pullback_validated",
            "success", "low",
            "Geçici geri çekilme senaryosu doğrulandı;"
            " pozisyon toparlanarak kâr ile kapandı.",
        ))

    # ── 5. news_not_confirmed_confirmed ──────────────────────────────────────
    if "news_not_confirmed" in labels_seen and result == "loss":
        labels.append(_flabel(
            "news_not_confirmed_confirmed",
            "mistake", "low",
            "Haber/event teyidi yokluğu ile birlikte trade loss oldu."
            " News doğrulaması giriş güvencesini artırırdı.",
        ))

    # ── 6. stop_too_close outcomes ────────────────────────────────────────────
    if "stop_too_close_candidate" in labels_seen and exit_reason == "stop_loss":
        # Post-exit recovery verisi bu sistemde yok → her zaman unverified
        labels.append(_flabel(
            "stop_too_close_unverified",
            "neutral", "medium",
            "Stop seviyesine yakın konumdaki pozisyon stop_loss ile kapandı."
            " Fiyatın sonrasında toparladığı doğrulanamadı — stop mesafesi gözden geçirilebilir.",
        ))

    # ── 7. good_trade_no_issue (fallback: win + sadece watch labels) ──────────
    has_warning_candidate_label = any(
        lbl.get("severity") in ("warning", "critical_candidate")
        for c in matching_candidates
        for lbl in (c.get("candidate_labels") or [])
    )
    if result == "win" and not has_warning_candidate_label:
        labels.append(_flabel(
            "good_trade_no_issue",
            "success", "low",
            "Trade belirgin uyarı sinyali olmadan başarılı şekilde kapandı.",
        ))

    # ── 8. unexplained_loss (fallback: loss + hiç kanıt yok) ─────────────────
    if result == "loss" and not matching_candidates and not matching_rechecks:
        labels.append(_flabel(
            "unexplained_loss",
            "neutral", "medium",
            "Kapanan trade için önceki candidate veya recheck kaydı bulunamadı."
            " Öğrenme analizi sınırlı (evidence_quality: limited).",
        ))

    return labels


# ── Final summary ─────────────────────────────────────────────────────────────

def _build_final_summary(
    result: str,
    final_labels: list[dict],
) -> dict[str, Any]:
    mistake_labels = [l for l in final_labels if l.get("type") == "mistake"]
    sev_order = {"high": 2, "medium": 1, "low": 0}

    # should_adjust_weights: loss + en az bir medium/high hata
    high_or_medium = [
        l for l in mistake_labels
        if sev_order.get(l.get("severity", "low"), 0) >= 1
    ]
    should_adjust = result == "loss" and bool(high_or_medium)

    # main_lesson
    if mistake_labels:
        top = max(
            mistake_labels,
            key=lambda l: sev_order.get(l.get("severity", "low"), 0),
        )
        main_lesson = top["reason"]
    else:
        success_labels = [l for l in final_labels if l.get("type") == "success"]
        main_lesson = (
            success_labels[0]["reason"]
            if success_labels
            else "Belirgin öğrenme noktası tespit edilmedi."
        )

    # recommended_review
    codes = {l["code"] for l in final_labels}
    if "bearish_pattern_ignored_confirmed" in codes:
        review = "pattern_weight"
    elif "early_entry_confirmed" in codes:
        review = "entry_timing"
    elif "stop_too_close_confirmed" in codes or "stop_too_close_unverified" in codes:
        review = "stop_distance"
    else:
        review = "no_action"

    return {
        "result":              result,
        "main_lesson":         main_lesson,
        "should_adjust_weights": should_adjust,
        "recommended_review":  review,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def build_mistake_memory(
    closed_trade: dict[str, Any],
    matching_candidates: list[dict[str, Any]],
    matching_rechecks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Kapanmış trade için final mistake memory üretir.

    Args:
        closed_trade:         Kapanmış trade dict (pair, side, entry_price, exit_price,
                              pnl_pct, exit_reason, open_signal içerir).
        matching_candidates:  Bu trade'e ait learning_candidate kayıtları (boş olabilir).
        matching_rechecks:    Bu trade'e ait position_recheck kayıtları (boş olabilir).

    Returns:
        mistake_memory_v1 schema dict,
        veya {"status": "not_created", "reason": ...} (geçersiz giriş).

    Garantiler:
        • Paper trading state'ini okumaz veya mutate etmez.
        • Karar motorunu etkilemez.
        • Mock / fake veri üretmez.
        • is_final = True (store tarafından da zorlanır).
    """
    pair       = str(closed_trade.get("pair") or "").strip()
    side       = str(closed_trade.get("side") or "").upper().strip()
    exit_price = float(closed_trade.get("exit_price") or 0.0)

    if not pair or side not in ("LONG", "SHORT") or exit_price == 0.0:
        return {
            "status": "not_created",
            "reason": "invalid_trade_data",
            "pair":   pair,
        }

    entry_price      = float(closed_trade.get("entry_price") or 0.0)
    pnl_pct          = float(closed_trade.get("pnl_pct") or 0.0)
    pnl_usd          = float(
        closed_trade.get("pnl_usd")
        or closed_trade.get("realized_pnl")
        or 0.0
    )
    raw_exit         = str(closed_trade.get("exit_reason") or "")
    exit_reason_norm = _normalize_exit_reason(raw_exit)
    holding_minutes  = _compute_holding_minutes(closed_trade)
    result           = _determine_result(pnl_pct)
    fingerprint      = _trade_fingerprint(closed_trade)

    # Açılış bağlamı
    opening_ctx = _build_opening_context(closed_trade)

    # Candidate kanıtı
    labels_seen: set[str] = {
        lbl["code"]
        for c in matching_candidates
        for lbl in (c.get("candidate_labels") or [])
    }
    candidate_ids = [
        c.get("candidate_id")
        for c in matching_candidates
        if c.get("candidate_id")
    ]
    candidate_evidence: dict[str, Any] = {
        "candidate_ids":   candidate_ids,
        "labels_seen":     sorted(labels_seen),
        "evidence_quality": "full" if matching_candidates else "limited",
    }

    # Recheck kanıtı
    recheck_ids = [
        r.get("recheck_id")
        for r in matching_rechecks
        if r.get("recheck_id")
    ]
    recheck_evidence: dict[str, Any] = {
        "recheck_ids":          recheck_ids,
        "worst_recheck_status": _worst_recheck_status(matching_rechecks),
    }

    # Final label'lar
    final_labels = _build_final_labels(
        result=result,
        exit_reason=exit_reason_norm,
        labels_seen=labels_seen,
        matching_candidates=matching_candidates,
        matching_rechecks=matching_rechecks,
    )

    # Final özet
    final_summary = _build_final_summary(result, final_labels)

    return {
        "memory_id":               str(uuid.uuid4()),
        "created_at":              _utc_now_iso(),
        "schema_version":          _SCHEMA_VERSION,
        "decision_permission":     "NO_EXECUTION",
        "execution_mode":          "PAPER_SAFE",
        "record_type":             "final_memory",
        "is_final":                True,
        "source_trade_fingerprint": fingerprint,
        "trade": {
            "pair":            pair,
            "side":            side,
            "entry_price":     entry_price,
            "exit_price":      exit_price,
            "pnl_usd":         pnl_usd,
            "pnl_pct":         pnl_pct,
            "exit_reason":     exit_reason_norm,
            "holding_minutes": holding_minutes,
        },
        "opening_context":    opening_ctx,
        "candidate_evidence": candidate_evidence,
        "recheck_evidence":   recheck_evidence,
        "final_labels":       final_labels,
        "final_summary":      final_summary,
    }
