"""
FAZ 4 — Position Recheck Service.

build_position_recheck(position, latest_snapshot, latest_safe_thesis) -> dict

Amaç:
  Açık pozisyon için "açılış sebebi hâlâ geçerli mi?" audit kontrolü üretir.

Kritik garantiler:
  • Otomatik kapatma yok.
  • Otomatik küçültme / büyütme yok.
  • Paper trading karar mantığını değiştirmez.
  • Mock / fake / placeholder veri üretmez.
  • Snapshot veya thesis yoksa fake veri üretmez — unknown/not_created döner.
  • summary.auto_action_allowed = False (store tarafından da zorlanır).
  • decision_permission = NO_EXECUTION, execution_mode = PAPER_SAFE.

Kontrol kuralları:
  1. one_hour_structure     — LONG açılış bullish + 1H BEARISH → fail
  2. higher_tf_alignment    — Confluence aligned + 4H/1D tersine döndü → warn
  3. pattern_vs_pnl         — Açılışta ters pattern + PnL negatif → warn
  4. (summary mod) hold_watch — PnL negatif ama 4H/1D hâlâ destekliyor → hold_watch
  5. multi_tf_in_loss        — PnL negatif + 1H bearish + 4H bearish → fail (kural 5)
  6. thesis_pair_context     — Safe thesis 'avoid' bias'ı → warn (kural 6)
  7. thesis_pair_context     — Thesis yok → unknown (kural 7)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

_SCHEMA_VERSION = "position_recheck_v1"

_BULLISH_DIR = frozenset({"bullish", "long", "buy"})
_BEARISH_DIR = frozenset({"bearish", "short", "sell"})


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _check(code: str, status: str, message: str) -> dict[str, Any]:
    return {"code": code, "status": status, "message": message}


def _get_current_mtf(pair: str, snapshot: dict) -> dict[str, str]:
    """Snapshot'tan pair'in MTF yapı haritasını çıkarır. BULLISH/BEARISH/NEUTRAL."""
    mtf = snapshot.get("mtf") or {}
    pair_mtf = mtf.get(pair) or {}
    result: dict[str, str] = {}
    for tf, data in pair_mtf.items():
        if not isinstance(data, dict):
            continue
        struct = (data.get("structure") or "").upper()
        if struct:
            result[tf] = struct
    return result


# ── Opening context ───────────────────────────────────────────────────────────

def _build_opening_context(position: dict) -> dict[str, Any]:
    """open_signal'dan açılış anındaki audit bilgisini çıkarır."""
    sig = position.get("open_signal") or {}
    primary_tf   = str(sig.get("primary_tf") or "")
    tf_signals   = sig.get("tf_signals") or {}
    confluence   = sig.get("confluence") or {}
    td           = sig.get("timeframe_decision") or {}

    # Açılış yönü: primary_tf sinyali veya final_direction
    primary_data = tf_signals.get(primary_tf) or {}
    opening_direction = str(
        primary_data.get("direction") or sig.get("final_direction") or ""
    ).lower()

    # Pattern bias: 1H sinyal yönü (higher TF confluence'tan ayrışabilir)
    one_h_data   = tf_signals.get("1h") or {}
    pattern_bias = str(one_h_data.get("direction") or opening_direction or "").lower()

    return {
        "final_score":          sig.get("final_score"),
        "primary_tf":           primary_tf,
        "risk_tf":              str(td.get("selected_timeframe") or ""),
        "opening_direction":    opening_direction,
        "confluence_status":    str(confluence.get("status") or "unknown").lower(),
        "pattern_bias":         pattern_bias,
        "agent_thesis_context": sig.get("agent_thesis_context"),
        # FAZ 11 — açılış anındaki ileri seviye teknik
        "advanced_technical":   sig.get("advanced_technical") or {},
    }


# ── Current context ───────────────────────────────────────────────────────────

def _build_current_context(
    pair: str,
    snapshot: dict,
    thesis: dict | None,
) -> dict[str, Any]:
    """Güncel snapshot + thesis'ten mevcut piyasa bağlamını çıkarır."""
    mtf_structures = _get_current_mtf(pair, snapshot)

    report = snapshot.get("report") or {}
    ml     = report.get("macro_layer") or {}
    al     = report.get("appetite_layer") or {}

    # Asset sinyal durumu
    asset_sigs = report.get("asset_signals") or []
    asset_sig  = next(
        (s for s in asset_sigs if isinstance(s, dict) and s.get("asset_code") == pair),
        {},
    )
    asset_signal_status = str(asset_sig.get("status") or "UNKNOWN").upper()

    # Thesis'ten pair bias
    asset_bias_str = "unknown"
    if thesis is not None:
        ab        = thesis.get("asset_bias") or {}
        pair_data = ab.get(pair) or {}
        asset_bias_str = str(pair_data.get("bias") or "unknown")

    return {
        "latest_snapshot_id": snapshot.get("snapshot_id"),
        "latest_thesis_id":   (thesis or {}).get("thesis_id"),
        "mtf":                mtf_structures,
        "asset_signal_status": asset_signal_status,
        "asset_bias":         asset_bias_str,
        "risk_appetite":      str(al.get("status") or "UNKNOWN").upper(),
        "macro_regime":       str(ml.get("regime") or "UNKNOWN").upper(),
    }


def _unknown_current_context() -> dict[str, Any]:
    """Snapshot yokken kullanılır — fake veri üretmez."""
    return {
        "latest_snapshot_id": None,
        "latest_thesis_id":   None,
        "mtf":                {},
        "asset_signal_status": "UNKNOWN",
        "asset_bias":         "unknown",
        "risk_appetite":      "UNKNOWN",
        "macro_regime":       "UNKNOWN",
    }


# ── Check kuralları ───────────────────────────────────────────────────────────

def _run_checks(
    pair: str,
    side: str,
    pnl_pct: float,
    opening_ctx: dict,
    current_ctx: dict,
    has_snapshot: bool,
    thesis: dict | None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    mtf     = current_ctx.get("mtf") or {}
    cur_1h  = mtf.get("1h", "UNKNOWN")
    cur_4h  = mtf.get("4h", "UNKNOWN")
    cur_1d  = mtf.get("1d", "UNKNOWN")

    opening_dir   = opening_ctx.get("opening_direction", "").lower()
    conf_status   = opening_ctx.get("confluence_status", "").lower()
    pattern_bias  = opening_ctx.get("pattern_bias", "").lower()

    # ── Kural 1: one_hour_structure ─────────────────────────────────────────
    if not has_snapshot:
        checks.append(_check(
            "one_hour_structure", "unknown",
            "Snapshot yok — 1H yapısı bilinmiyor.",
        ))
    elif side == "LONG":
        if opening_dir in _BULLISH_DIR and cur_1h == "BEARISH":
            checks.append(_check(
                "one_hour_structure", "fail",
                "1H BEARISH'e döndü — açılışta bullish. Ana TF tersine döndü.",
            ))
        else:
            checks.append(_check(
                "one_hour_structure", "pass",
                f"1H yapısı kabul edilebilir: current_1h={cur_1h}.",
            ))
    elif side == "SHORT":
        if opening_dir in _BEARISH_DIR and cur_1h == "BULLISH":
            checks.append(_check(
                "one_hour_structure", "fail",
                "1H BULLISH'e döndü — açılışta bearish. Ana TF tersine döndü.",
            ))
        else:
            checks.append(_check(
                "one_hour_structure", "pass",
                f"1H yapısı kabul edilebilir: current_1h={cur_1h}.",
            ))
    else:
        checks.append(_check(
            "one_hour_structure", "unknown",
            f"Bilinmeyen side={side!r} — 1H kontrolü yapılamadı.",
        ))

    # ── Kural 2: higher_tf_alignment ────────────────────────────────────────
    if not has_snapshot:
        checks.append(_check(
            "higher_tf_alignment", "unknown",
            "Snapshot yok — yüksek TF bilgisi yok.",
        ))
    elif conf_status == "aligned":
        if side == "LONG":
            if cur_4h == "BEARISH" or cur_1d == "BEARISH":
                checks.append(_check(
                    "higher_tf_alignment", "warn",
                    f"Açılışta confluence aligned ama yüksek TF zayıfladı:"
                    f" 4H={cur_4h}, 1D={cur_1d}.",
                ))
            else:
                checks.append(_check(
                    "higher_tf_alignment", "pass",
                    f"Yüksek TF LONG'u destekliyor: 4H={cur_4h}, 1D={cur_1d}.",
                ))
        elif side == "SHORT":
            if cur_4h == "BULLISH" or cur_1d == "BULLISH":
                checks.append(_check(
                    "higher_tf_alignment", "warn",
                    f"Açılışta confluence aligned ama yüksek TF zayıfladı:"
                    f" 4H={cur_4h}, 1D={cur_1d}.",
                ))
            else:
                checks.append(_check(
                    "higher_tf_alignment", "pass",
                    f"Yüksek TF SHORT'u destekliyor: 4H={cur_4h}, 1D={cur_1d}.",
                ))
        else:
            checks.append(_check(
                "higher_tf_alignment", "unknown",
                f"Bilinmeyen side={side!r}.",
            ))
    else:
        # Açılışta confluence aligned değildi → yüksek TF beklentisi yok
        checks.append(_check(
            "higher_tf_alignment", "pass",
            f"Açılışta confluence aligned değildi (status={conf_status!r})"
            " — yüksek TF beklentisi yok.",
        ))

    # ── Kural 3: pattern_vs_pnl ─────────────────────────────────────────────
    if side == "LONG" and pattern_bias in _BEARISH_DIR and pnl_pct < 0:
        checks.append(_check(
            "pattern_vs_pnl", "warn",
            f"Açılışta 1H bearish pattern vardı, PnL negatif"
            f" ({pnl_pct:.2f}%). Pattern geçerli olabilir.",
        ))
    elif side == "SHORT" and pattern_bias in _BULLISH_DIR and pnl_pct < 0:
        checks.append(_check(
            "pattern_vs_pnl", "warn",
            f"Açılışta 1H bullish pattern vardı, PnL negatif"
            f" ({pnl_pct:.2f}%). Pattern geçerli olabilir.",
        ))
    else:
        checks.append(_check(
            "pattern_vs_pnl", "pass",
            f"Pattern-PnL çelişkisi yok (pattern_bias={pattern_bias!r},"
            f" pnl={pnl_pct:.2f}%).",
        ))

    # ── Kural 5: multi_tf_in_loss ────────────────────────────────────────────
    if not has_snapshot:
        checks.append(_check(
            "multi_tf_in_loss", "unknown",
            "Snapshot yok — MTF-PnL kontrolü yapılamadı.",
        ))
    elif side == "LONG" and pnl_pct < 0 and cur_1h == "BEARISH" and cur_4h == "BEARISH":
        checks.append(_check(
            "multi_tf_in_loss", "fail",
            f"PnL negatif ({pnl_pct:.2f}%) + 1H ve 4H ikisi de BEARISH."
            " Manuel gözden geçirme önerilir.",
        ))
    elif side == "SHORT" and pnl_pct < 0 and cur_1h == "BULLISH" and cur_4h == "BULLISH":
        checks.append(_check(
            "multi_tf_in_loss", "fail",
            f"PnL negatif ({pnl_pct:.2f}%) + 1H ve 4H ikisi de BULLISH."
            " Manuel gözden geçirme önerilir.",
        ))
    else:
        checks.append(_check(
            "multi_tf_in_loss", "pass",
            f"Çoklu TF olumsuz senaryo yok: 1H={cur_1h}, 4H={cur_4h},"
            f" pnl={pnl_pct:.2f}%.",
        ))

    # ── Kural 6 + 7: thesis_pair_context ────────────────────────────────────
    if thesis is None:
        checks.append(_check(
            "thesis_pair_context", "unknown",
            "Güvenli thesis yok — thesis karşılaştırması yapılamadı.",
        ))
    else:
        ab        = thesis.get("asset_bias") or {}
        pair_data = ab.get(pair) or {}
        pair_bias = str(pair_data.get("bias") or "unknown")
        if pair_bias == "avoid":
            checks.append(_check(
                "thesis_pair_context", "warn",
                f"Güncel thesis '{pair}' için 'avoid' bias'ı gösteriyor."
                " Açık pozisyon thesis'e aykırı.",
            ))
        else:
            checks.append(_check(
                "thesis_pair_context", "pass",
                f"Thesis pair bias: {pair_bias!r} — pozisyonla uyumlu.",
            ))

    # ── FAZ 11 — Advanced technical değişim kontrolleri ─────────────────────
    adv_open = opening_ctx.get("advanced_technical") or {}
    if adv_open.get("available"):
        # Açılışta bullish EMA + LONG iken şu an cur_1h BEARISH → uyarı
        ema_open = str(adv_open.get("ema_stack") or "unavailable")
        ms_open  = str(adv_open.get("market_structure") or "unavailable")
        candle   = str(adv_open.get("candle_close_confirmation") or "unavailable")
        vol_cf   = str(adv_open.get("volume_confirmation") or "unavailable")

        mtf = current_ctx.get("mtf") or {}
        cur_1h = str(mtf.get("1h") or "UNKNOWN").upper()

        # EMA flip
        if side == "LONG" and ema_open == "bullish" and cur_1h == "BEARISH":
            checks.append(_check(
                "ema_stack_flipped", "warn",
                "Açılışta EMA bullish idi; şimdi 1H BEARISH'e döndü."
                " EMA yapısı zayıflıyor.",
            ))
        elif side == "SHORT" and ema_open == "bearish" and cur_1h == "BULLISH":
            checks.append(_check(
                "ema_stack_flipped", "warn",
                "Açılışta EMA bearish idi; şimdi 1H BULLISH'e döndü."
                " EMA yapısı zayıflıyor.",
            ))

        # Structure flip
        if side == "LONG" and ms_open == "HH_HL" and cur_1h == "BEARISH":
            checks.append(_check(
                "market_structure_broken", "warn",
                "Açılışta yapı HH/HL idi; 1H şu an BEARISH. Yapı bozuluyor.",
            ))
        elif side == "SHORT" and ms_open == "LH_LL" and cur_1h == "BULLISH":
            checks.append(_check(
                "market_structure_broken", "warn",
                "Açılışta yapı LH/LL idi; 1H şu an BULLISH. Yapı bozuluyor.",
            ))

        # Candle close fakeout uyarısı
        if candle == "fakeout":
            checks.append(_check(
                "candle_close_fakeout", "warn",
                "Açılışta candle close teyidi yoktu (fakeout) — sahte kırılım riski.",
            ))

        # Düşük hacim teyidi
        if vol_cf in ("weak", "warning"):
            checks.append(_check(
                "volume_confirmation_weak", "warn",
                f"Açılışta hacim teyidi zayıf ({vol_cf}). Düşük güven."
            ))

    return checks


# ── Summary ───────────────────────────────────────────────────────────────────

def _build_summary(
    checks: list[dict],
    side: str,
    pnl_pct: float,
    current_ctx: dict,
) -> dict[str, Any]:
    has_fail          = any(c["status"] == "fail" for c in checks)
    has_warn          = any(c["status"] == "warn" for c in checks)
    has_non_unknown   = any(c["status"] != "unknown" for c in checks)
    has_multi_tf_fail = any(
        c["code"] == "multi_tf_in_loss" and c["status"] == "fail"
        for c in checks
    )

    # Kural 4: PnL negatif ama yüksek TF hâlâ destekliyor → hold_watch
    mtf    = current_ctx.get("mtf") or {}
    cur_4h = mtf.get("4h", "UNKNOWN")
    cur_1d = mtf.get("1d", "UNKNOWN")

    if side == "LONG":
        higher_tf_supports = cur_4h != "BEARISH" and cur_1d != "BEARISH"
    elif side == "SHORT":
        higher_tf_supports = cur_4h != "BULLISH" and cur_1d != "BULLISH"
    else:
        higher_tf_supports = False

    pnl_neg_higher_ok = pnl_pct < 0 and higher_tf_supports

    # Karar
    if not has_non_unknown:
        status = "unknown"
        action = "no_action"
    elif has_multi_tf_fail:
        status = "invalid"
        action = "consider_manual_review"
    elif has_fail:
        status = "weakening"
        # Kural 4: eğer yüksek TF hâlâ destekliyorsa hold_watch, aksi hâlde review
        action = "hold_watch" if pnl_neg_higher_ok else "consider_manual_review"
    elif has_warn:
        status = "weakening"
        action = "hold_watch" if pnl_neg_higher_ok else "consider_manual_review"
    else:
        status = "valid"
        action = "no_action"

    return {
        "status":              status,
        "recommended_action":  action,
        "auto_action_allowed": False,   # store tarafından da zorlanır
        "reason": "Audit-only recheck; no automatic trading action.",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def build_position_recheck(
    position: dict[str, Any],
    latest_snapshot: dict[str, Any] | None,
    latest_safe_thesis: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Açık pozisyon için audit-only recheck üretir.

    Args:
        position:            open_positions[i] dict (pair, side, entry_price,
                             current_price, pnl_pct, open_signal içerir).
        latest_snapshot:     load_recent_hourly_snapshots(limit=1)[-1] veya None.
        latest_safe_thesis:  load_latest_safe_thesis() veya None.

    Returns:
        position_recheck_v1 schema dict,
        veya {"status": "not_created", "reason": ...} (geçersiz giriş).

    Garantiler:
        • Paper trading state'ini okumaz veya mutate etmez.
        • Karar motorunu etkilemez.
        • Mock / fake veri üretmez.
        • summary.auto_action_allowed = False (zorunlu).
    """
    pair = str(position.get("pair") or "").strip()
    side = str(position.get("side") or "").upper().strip()

    # Kural 8: geçersiz pozisyon verisi
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

    opening_ctx = _build_opening_context(position)

    has_snapshot = latest_snapshot is not None
    if has_snapshot:
        current_ctx = _build_current_context(pair, latest_snapshot, latest_safe_thesis)
    else:
        current_ctx = _unknown_current_context()

    checks  = _run_checks(
        pair, side, pnl_pct,
        opening_ctx, current_ctx,
        has_snapshot, latest_safe_thesis,
    )
    summary = _build_summary(checks, side, pnl_pct, current_ctx)

    return {
        "recheck_id":         str(uuid.uuid4()),
        "created_at":         _utc_now_iso(),
        "schema_version":     _SCHEMA_VERSION,
        "decision_permission": "NO_EXECUTION",
        "execution_mode":     "PAPER_SAFE",
        "pair":               pair,
        "side":               side,
        "entry_price":        entry_price,
        "current_price":      current_price,
        "pnl_pct":            pnl_pct,
        "opening_context":    opening_ctx,
        "current_context":    current_ctx,
        "checks":             checks,
        "summary":            summary,
    }
