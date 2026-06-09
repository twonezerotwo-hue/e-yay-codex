"""
FAZ 5A — Learning Candidate Service.

build_learning_candidate(position, latest_recheck, latest_snapshot, latest_safe_thesis)
  -> dict (learning_candidate_v1 schema veya {"status": "not_created", ...})

Amaç:
  Açık pozisyon için "açılış kararında öğrenme adayı var mı?" audit kaydı üretir.
  Pozisyon kapanmadan kesin öğrenme yazılmaz — is_final=False, record_type="candidate".

Kritik garantiler:
  • Otomatik kapatma / küçültme / add yok.
  • Paper trading karar mantığını değiştirmez.
  • Mock / fake / placeholder veri üretmez.
  • Snapshot veya thesis yoksa fake veri üretmez — unknown döner.
  • is_final = False (store tarafından da zorlanır).
  • decision_permission = NO_EXECUTION, execution_mode = PAPER_SAFE.

Candidate label kuralları:
  1. bearish_pattern_ignored     — LONG + pattern bearish + PnL negatif
  2. early_entry_or_failed_1h_signal — açılış 1H bullish + şimdi 1H BEARISH
  3. confluence_holding_under_pressure — confluence aligned + PnL negatif + 4H/1D hâlâ bullish
  4. temporary_pullback_possible  — PnL negatif + şimdi 4H+1D bullish
  5. thesis_contradiction          — LONG + thesis 'avoid' bias
  6. news_not_confirmed            — açılışta news yok + PnL negatif (düşük severity)
  7. stop_too_close_candidate      — stop_price varsa yakınlık; yoksa PnL < -3% heuristic

Severity:
  watch            — izleme notu
  warning          — PnL negatif + bir çelişki
  critical_candidate — PnL negatif + 1H+4H BEARISH, veya recheck invalid
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

_SCHEMA_VERSION = "learning_candidate_v1"

_BULLISH_DIR = frozenset({"bullish", "long", "buy"})
_BEARISH_DIR = frozenset({"bearish", "short", "sell"})

# stop_too_close: stop'a kalan mesafe orijinal stop distance'ın bu oranından azsa tetiklenir
_STOP_CLOSE_RATIO = 0.30
# stop_too_close heuristic: explicit stop_price yoksa PnL bu eşiğin altındaysa tetiklenir
_STOP_HEURISTIC_PNL = -3.0


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _label(code: str, severity: str, reason: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "reason": reason}


# ── Opening evidence ──────────────────────────────────────────────────────────

def _build_opening_evidence(position: dict) -> dict[str, Any]:
    """open_signal'dan açılış anındaki audit kanıtını çıkarır."""
    sig        = position.get("open_signal") or {}
    primary_tf = str(sig.get("primary_tf") or "")
    tf_signals = sig.get("tf_signals") or {}
    confluence = sig.get("confluence") or {}
    td         = sig.get("timeframe_decision") or {}

    # Opening direction: primary_tf sinyal yönü veya final_direction
    primary_data      = tf_signals.get(primary_tf) or {}
    opening_direction = str(
        primary_data.get("direction") or sig.get("final_direction") or ""
    ).lower()

    # Pattern bias: açılış anındaki 1H sinyal yönü
    one_h_data   = tf_signals.get("1h") or {}
    pattern_bias = str(one_h_data.get("direction") or opening_direction or "").lower()

    # News / event bilgisi
    news_event_present = bool(
        sig.get("news_event_present") or sig.get("has_news_event") or False
    )

    # FAZ 11 — advanced technical audit
    adv_tech = sig.get("advanced_technical") or {}

    return {
        "final_score":          sig.get("final_score"),
        "primary_tf":           primary_tf,
        "risk_tf":              str(td.get("selected_timeframe") or ""),
        "confluence_status":    str(confluence.get("status") or "unknown").lower(),
        "opening_direction":    opening_direction,
        "pattern_bias":         pattern_bias,
        "pattern_score":        sig.get("pattern_score"),
        "news_event_present":   news_event_present,
        "agent_thesis_context": sig.get("agent_thesis_context"),
        # ── FAZ 11 — açılış anındaki ileri seviye teknik snapshot
        "advanced_technical":   adv_tech if isinstance(adv_tech, dict) else {},
    }


# ── Current evidence ──────────────────────────────────────────────────────────

def _build_current_evidence(
    pair: str,
    latest_recheck: dict | None,
    latest_snapshot: dict | None,
    latest_safe_thesis: dict | None,
) -> dict[str, Any]:
    """Güncel MTF yapısını recheck > snapshot sıralamasıyla çıkarır."""
    # MTF: recheck varsa oradan al (daha taze hesaplanmış), yoksa snapshot'tan
    if latest_recheck is not None:
        mtf    = (latest_recheck.get("current_context") or {}).get("mtf") or {}
        cur_1h = str(mtf.get("1h") or "UNKNOWN").upper()
        cur_4h = str(mtf.get("4h") or "UNKNOWN").upper()
        cur_1d = str(mtf.get("1d") or "UNKNOWN").upper()
    elif latest_snapshot is not None:
        pair_mtf = (latest_snapshot.get("mtf") or {}).get(pair) or {}
        cur_1h   = str(((pair_mtf.get("1h") or {}).get("structure") or "UNKNOWN")).upper()
        cur_4h   = str(((pair_mtf.get("4h") or {}).get("structure") or "UNKNOWN")).upper()
        cur_1d   = str(((pair_mtf.get("1d") or {}).get("structure") or "UNKNOWN")).upper()
    else:
        cur_1h = cur_4h = cur_1d = "UNKNOWN"

    # Recheck summary status
    recheck_summary = "unknown"
    if latest_recheck is not None:
        recheck_summary = str(
            (latest_recheck.get("summary") or {}).get("status") or "unknown"
        ).lower()

    # Asset bias from thesis
    asset_bias_str = "unknown"
    if latest_safe_thesis is not None:
        ab        = latest_safe_thesis.get("asset_bias") or {}
        pair_data = ab.get(pair) or {}
        asset_bias_str = str(pair_data.get("bias") or "unknown")

    return {
        "recheck_summary":  recheck_summary,
        "one_hour_status":  cur_1h,
        "four_hour_status": cur_4h,
        "one_day_status":   cur_1d,
        "asset_bias":       asset_bias_str,
    }


# ── Source block ──────────────────────────────────────────────────────────────

def _build_source(
    position: dict,
    latest_recheck: dict | None,
    latest_snapshot: dict | None,
    latest_safe_thesis: dict | None,
) -> dict[str, Any]:
    return {
        "open_signal_present": bool(position.get("open_signal")),
        "latest_recheck_id":   (latest_recheck or {}).get("recheck_id"),
        "latest_snapshot_id":  (latest_snapshot or {}).get("snapshot_id"),
        "latest_thesis_id":    (latest_safe_thesis or {}).get("thesis_id"),
        "evidence_quality":    "full" if latest_recheck is not None else "limited",
    }


# ── Candidate labels ──────────────────────────────────────────────────────────

def _build_labels(  # noqa: PLR0912, PLR0913
    side: str,
    pnl_pct: float,
    entry_price: float,
    current_price: float,
    stop_price: float | None,
    opening_ev: dict,
    current_ev: dict,
    latest_safe_thesis: dict | None,
) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []

    pattern_bias      = opening_ev.get("pattern_bias", "").lower()
    confluence_status = opening_ev.get("confluence_status", "").lower()
    opening_direction = opening_ev.get("opening_direction", "").lower()
    primary_tf        = opening_ev.get("primary_tf", "").lower()
    news_present      = bool(opening_ev.get("news_event_present"))

    cur_1h     = current_ev.get("one_hour_status", "UNKNOWN")
    cur_4h     = current_ev.get("four_hour_status", "UNKNOWN")
    cur_1d     = current_ev.get("one_day_status", "UNKNOWN")
    asset_bias = current_ev.get("asset_bias", "unknown")

    # ── Label 1: bearish_pattern_ignored ─────────────────────────────────────
    if side == "LONG" and pattern_bias in _BEARISH_DIR and pnl_pct < 0:
        labels.append(_label(
            "bearish_pattern_ignored",
            "warning",
            f"Pattern bearish iken LONG açıldı; pozisyon şu an negatif"
            f" ({pnl_pct:.2f}%). Kapanış sonucu bekleniyor.",
        ))
    elif side == "SHORT" and pattern_bias in _BULLISH_DIR and pnl_pct < 0:
        labels.append(_label(
            "bearish_pattern_ignored",
            "warning",
            f"Pattern bullish iken SHORT açıldı; pozisyon şu an negatif"
            f" ({pnl_pct:.2f}%). Kapanış sonucu bekleniyor.",
        ))

    # ── Label 2: early_entry_or_failed_1h_signal ─────────────────────────────
    if (
        side == "LONG"
        and primary_tf == "1h"
        and opening_direction in _BULLISH_DIR
        and cur_1h == "BEARISH"
    ):
        labels.append(_label(
            "early_entry_or_failed_1h_signal",
            "warning",
            "Açılışta 1H bullish sinyal verildi; 1H yapısı şimdi BEARISH'e döndü."
            " Erken giriş veya bozulan sinyal olabilir.",
        ))
    elif (
        side == "SHORT"
        and primary_tf == "1h"
        and opening_direction in _BEARISH_DIR
        and cur_1h == "BULLISH"
    ):
        labels.append(_label(
            "early_entry_or_failed_1h_signal",
            "warning",
            "Açılışta 1H bearish sinyal verildi; 1H yapısı şimdi BULLISH'e döndü."
            " Erken giriş veya bozulan sinyal olabilir.",
        ))

    # ── Label 3: confluence_holding_under_pressure ───────────────────────────
    # Açılışta confluence aligned + PnL negatif ama yüksek TF hâlâ destekliyor
    if pnl_pct < 0 and confluence_status == "aligned":
        if side == "LONG" and cur_4h != "BEARISH" and cur_1d != "BEARISH":
            labels.append(_label(
                "confluence_holding_under_pressure",
                "watch",
                f"Açılışta 4H/1D confluence aligned; pozisyon negatif"
                f" ({pnl_pct:.2f}%) ama yüksek TF hâlâ destekliyor"
                f" (4H={cur_4h}, 1D={cur_1d}). İzleme adayı.",
            ))
        elif side == "SHORT" and cur_4h != "BULLISH" and cur_1d != "BULLISH":
            labels.append(_label(
                "confluence_holding_under_pressure",
                "watch",
                f"Açılışta 4H/1D confluence aligned; pozisyon negatif"
                f" ({pnl_pct:.2f}%) ama yüksek TF hâlâ destekliyor"
                f" (4H={cur_4h}, 1D={cur_1d}). İzleme adayı.",
            ))

    # ── Label 4: temporary_pullback_possible ─────────────────────────────────
    # PnL negatif ama 4H+1D tam bullish (confluence gerekmiyor)
    if pnl_pct < 0:
        if side == "LONG" and cur_4h == "BULLISH" and cur_1d == "BULLISH":
            labels.append(_label(
                "temporary_pullback_possible",
                "watch",
                f"PnL negatif ({pnl_pct:.2f}%) ama 4H ve 1D BULLISH;"
                " geçici geri çekilme olabilir. Stop kırılmadıysa izleme devam eder.",
            ))
        elif side == "SHORT" and cur_4h == "BEARISH" and cur_1d == "BEARISH":
            labels.append(_label(
                "temporary_pullback_possible",
                "watch",
                f"PnL negatif ({pnl_pct:.2f}%) ama 4H ve 1D BEARISH;"
                " geçici geri çekilme olabilir. Stop kırılmadıysa izleme devam eder.",
            ))

    # ── Label 5: thesis_contradiction ────────────────────────────────────────
    if latest_safe_thesis is not None:
        if side == "LONG" and asset_bias == "avoid":
            labels.append(_label(
                "thesis_contradiction",
                "warning",
                "LONG pozisyon açık iken güncel thesis asset_bias='avoid' gösteriyor."
                " Pozisyon thesis'e aykırı.",
            ))
        elif side == "SHORT" and asset_bias in _BULLISH_DIR:
            labels.append(_label(
                "thesis_contradiction",
                "warning",
                "SHORT pozisyon açık iken güncel thesis bullish bias gösteriyor."
                " Pozisyon thesis'e aykırı.",
            ))

    # ── Label 6: news_not_confirmed ──────────────────────────────────────────
    # Düşük severity; tek başına kritik değil
    if not news_present and pnl_pct < 0:
        labels.append(_label(
            "news_not_confirmed",
            "watch",
            f"Açılışta news/event bilgisi yoktu ve pozisyon şu an negatif"
            f" ({pnl_pct:.2f}%). Düşük önem; tek başına kritik değil.",
        ))

    # ── Label 7: stop_too_close_candidate ────────────────────────────────────
    stop_triggered = False
    if (
        stop_price is not None
        and stop_price > 0
        and entry_price > 0
        and current_price > 0
    ):
        if side == "LONG" and current_price > stop_price:
            orig_dist = entry_price - stop_price
            remaining = current_price - stop_price
            if orig_dist > 0 and (remaining / orig_dist) < _STOP_CLOSE_RATIO:
                stop_triggered = True
                labels.append(_label(
                    "stop_too_close_candidate",
                    "warning",
                    f"LONG pozisyon stop seviyesine çok yaklaştı"
                    f" (kalan mesafe oranı: {remaining / orig_dist * 100:.1f}%)."
                    f" current={current_price:.4f}, stop={stop_price:.4f}. Aday kaydı.",
                ))
        elif side == "SHORT" and current_price < stop_price:
            orig_dist = stop_price - entry_price
            remaining = stop_price - current_price
            if orig_dist > 0 and (remaining / orig_dist) < _STOP_CLOSE_RATIO:
                stop_triggered = True
                labels.append(_label(
                    "stop_too_close_candidate",
                    "warning",
                    f"SHORT pozisyon stop seviyesine çok yaklaştı"
                    f" (kalan mesafe oranı: {remaining / orig_dist * 100:.1f}%)."
                    f" current={current_price:.4f}, stop={stop_price:.4f}. Aday kaydı.",
                ))

    # stop_price yoksa PnL heuristic
    if not stop_triggered and pnl_pct <= _STOP_HEURISTIC_PNL:
        labels.append(_label(
            "stop_too_close_candidate",
            "warning",
            f"Stop bilgisi yok ama PnL {pnl_pct:.2f}% (≤{_STOP_HEURISTIC_PNL}%);"
            " stop yaklaşıyor olabilir. Aday kaydı — kesin karar kapanışta verilecek.",
        ))

    # ── FAZ 11 — Advanced technical labels ──────────────────────────────────
    adv = opening_ev.get("advanced_technical") or {}
    if pnl_pct < 0 and adv.get("available"):
        ema_st  = str(adv.get("ema_stack") or "unavailable")
        ms      = str(adv.get("market_structure") or "unavailable")
        vol_cf  = str(adv.get("volume_confirmation") or "unavailable")
        vwap_p  = str(adv.get("vwap_position") or "unavailable")
        candle  = str(adv.get("candle_close_confirmation") or "unavailable")

        # low_volume_breakout
        if vol_cf in ("weak", "warning"):
            labels.append(_label(
                "low_volume_breakout",
                "warning",
                f"Açılışta hacim teyidi zayıf ({vol_cf}); PnL {pnl_pct:.2f}%."
                " Düşük hacimli giriş olabilir.",
            ))

        # ema_stack_against_trade
        if (side == "LONG" and ema_st == "bearish") or (side == "SHORT" and ema_st == "bullish"):
            labels.append(_label(
                "ema_stack_against_trade",
                "warning",
                f"{side} açılırken EMA stack {ema_st} idi; PnL {pnl_pct:.2f}%."
                " Trend yapısına aykırı giriş.",
            ))

        # market_structure_broken — açılış HH/HL iken şimdi LH/LL (veya tersi)
        cur_1h = current_ev.get("one_hour_status", "UNKNOWN")
        if (side == "LONG" and ms == "HH_HL" and cur_1h == "BEARISH") or \
           (side == "SHORT" and ms == "LH_LL" and cur_1h == "BULLISH"):
            labels.append(_label(
                "market_structure_broken",
                "warning",
                f"Açılışta yapı {ms} idi; şimdi 1H={cur_1h}. Yapı bozuldu.",
            ))

        # vwap_rejection
        if (side == "LONG" and vwap_p == "below") or (side == "SHORT" and vwap_p == "above"):
            labels.append(_label(
                "vwap_rejection",
                "warning",
                f"{side} açılırken VWAP {vwap_p} idi; PnL {pnl_pct:.2f}%."
                " VWAP reddi olabilir.",
            ))

        # candle_close_failed
        if candle == "fakeout":
            labels.append(_label(
                "candle_close_failed",
                "warning",
                "Açılışta candle close teyidi yoktu (fakeout);"
                f" PnL {pnl_pct:.2f}%. Sahte kırılım olabilir.",
            ))

    return labels


# ── Candidate summary ─────────────────────────────────────────────────────────

def _build_candidate_summary(
    labels: list[dict],
    side: str,
    pnl_pct: float,
    current_ev: dict,
    latest_recheck: dict | None,
) -> dict[str, Any]:
    cur_1h = current_ev.get("one_hour_status", "UNKNOWN")
    cur_4h = current_ev.get("four_hour_status", "UNKNOWN")

    # critical_candidate: recheck invalid VEYA PnL negatif + 1H+4H bearish
    recheck_invalid = (
        latest_recheck is not None
        and (latest_recheck.get("summary") or {}).get("status") == "invalid"
    )
    multi_tf_bearish = (
        pnl_pct < 0
        and side == "LONG"
        and cur_1h == "BEARISH"
        and cur_4h == "BEARISH"
    )
    multi_tf_bullish = (
        pnl_pct < 0
        and side == "SHORT"
        and cur_1h == "BULLISH"
        and cur_4h == "BULLISH"
    )

    is_critical = recheck_invalid or multi_tf_bearish or multi_tf_bullish

    if is_critical:
        status = "critical_candidate"
    else:
        _order = {"critical_candidate": 2, "warning": 1, "watch": 0}
        severities = [_order.get(lbl.get("severity", "watch"), 0) for lbl in labels]
        max_sev = max(severities, default=0)
        status = ("critical_candidate" if max_sev >= 2
                  else "warning" if max_sev == 1
                  else "watch")

    return {
        "status":               status,
        "message":              (
            "Pozisyon açık olduğu için kesin öğrenme yazılmadı;"
            " kapanış sonucu bekleniyor."
        ),
        "finalization_trigger": "position_closed",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def build_learning_candidate(
    position: dict[str, Any],
    latest_recheck: dict[str, Any] | None,
    latest_snapshot: dict[str, Any] | None,
    latest_safe_thesis: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Açık pozisyon için audit-only learning candidate üretir.

    Args:
        position:            open_positions[i] dict.
        latest_recheck:      Bu pair için en son position_recheck veya None.
        latest_snapshot:     load_recent_hourly_snapshots(limit=1)[-1] veya None.
        latest_safe_thesis:  load_latest_safe_thesis() veya None.

    Returns:
        learning_candidate_v1 schema dict,
        veya {"status": "not_created", "reason": ...} (geçersiz giriş).

    Garantiler:
        • Paper trading state'ini okumaz veya mutate etmez.
        • Karar motorunu etkilemez.
        • Mock / fake veri üretmez.
        • is_final = False (store tarafından da zorlanır).
    """
    pair = str(position.get("pair") or "").strip()
    side = str(position.get("side") or "").upper().strip()

    if not pair or side not in ("LONG", "SHORT"):
        return {
            "status": "not_created",
            "reason": "invalid_position_data",
            "pair":   pair,
            "side":   side,
        }

    entry_price   = float(position.get("entry_price") or 0.0)
    current_price = float(position.get("current_price") or 0.0)
    pnl_pct       = float(position.get("pnl_pct") or 0.0)
    position_id   = position.get("position_id")

    # stop_price: pozisyon dict'inde varsa kullan
    raw_stop = position.get("stop_price") or position.get("stop_loss_price")
    stop_price: float | None = float(raw_stop) if raw_stop is not None else None

    opening_ev  = _build_opening_evidence(position)
    current_ev  = _build_current_evidence(
        pair, latest_recheck, latest_snapshot, latest_safe_thesis
    )
    source      = _build_source(
        position, latest_recheck, latest_snapshot, latest_safe_thesis
    )

    labels  = _build_labels(
        side, pnl_pct, entry_price, current_price, stop_price,
        opening_ev, current_ev, latest_safe_thesis,
    )
    summary = _build_candidate_summary(
        labels, side, pnl_pct, current_ev, latest_recheck
    )

    return {
        "candidate_id":        str(uuid.uuid4()),
        "created_at":          _utc_now_iso(),
        "schema_version":      _SCHEMA_VERSION,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        "record_type":         "candidate",
        "is_final":            False,
        "pair":                pair,
        "side":                side,
        "position_id":         position_id,
        "entry_price":         entry_price,
        "current_price":       current_price,
        "pnl_pct":             pnl_pct,
        "source":              source,
        "opening_evidence":    opening_ev,
        "current_evidence":    current_ev,
        "candidate_labels":    labels,
        "candidate_summary":   summary,
    }
