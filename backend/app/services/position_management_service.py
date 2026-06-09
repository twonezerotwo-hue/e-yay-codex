"""
Position Management Service — parçalı alım + manuel SL/TP override + işlem açılma açıklaması.

FAZ 3: Açık paper pozisyonlarda kullanıcı aktif yönetim yapabilsin:
  • add_to_position(pair, size, reason, mode)       → parçalı alım (risk gate ile)
  • set_manual_risk_override(pair, new_sl, new_tp)  → SL/TP elle değiştir
  • reset_to_auto_risk_plan(pair)                    → otomatik plana dön
  • build_opening_explanation(open_signal, pair)    → "neden açıldı" açıklaması
  • initialize_default_add_plan(position, ...)      → ilk okunduğunda default plan

PAPER_SAFE / NO_EXECUTION — gerçek emir YOK, sadece paper position state güncellenir.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

# ── Sabitler ─────────────────────────────────────────────────────────────────

# Maksimum izin verilen pozisyon boyutu (parçalı alımlar dahil) — POSITION_SIZE × 1.2
MAX_POSITION_MULTIPLIER: float = 1.2

# Manuel onay gereken stop yakınlık eşiği — pozisyon stop'a %X'den yakınsa manuel onay
STOP_PROXIMITY_THRESHOLD_PCT: float = 1.5   # entry'den stop'a kalan mesafe %

# Add işlemi sonrası minimum R/R
MIN_RR_AFTER_ADD: float = 1.0

# Add işlemi sonrası warning eşiği — RR düşüşü
RR_WARNING_DROP: float = 0.3

AddMode = Literal["off", "manual", "paper_auto"]
AddStatus = Literal["allowed", "manual_required", "blocked", "risk_warning"]


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _compute_rr(side: str, entry: float, sl: float, tp: float) -> float:
    """Risk/reward oranı — long/short uyumlu."""
    if entry <= 0 or sl <= 0 or tp <= 0:
        return 0.0
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0:
        return 0.0
    return round(reward / risk, 4)


def _compute_average_entry(
    current_avg: float, current_size: float,
    add_price: float, add_size: float,
) -> float:
    """Yeni ortalama entry — size-weighted."""
    total_size = current_size + add_size
    if total_size <= 0:
        return current_avg
    return round(
        (current_avg * current_size + add_price * add_size) / total_size,
        6,
    )


def initialize_default_add_plan(
    current_size_usd: float,
    *,
    position_size_constant: float,
    average_entry: float,
) -> dict[str, Any]:
    """Pozisyon ilk okunduğunda default add_plan üret.

    Mod = 'manual', boş ekleme seviyeleri, kalan kapasite = max - current.
    """
    max_pos = round(position_size_constant * MAX_POSITION_MULTIPLIER, 2)
    remaining = max(0.0, round(max_pos - current_size_usd, 2))
    return {
        "mode":                          "manual",
        "current_size_usd":              round(current_size_usd, 2),
        "max_position_size_usd":         max_pos,
        "remaining_add_capacity_usd":    remaining,
        "average_entry_price":           round(average_entry, 6),
        "add_levels":                    [],
        "last_control_result":           None,
        "created_at":                    _now_iso(),
    }


# ── Risk gate (AddToPositionControl) ─────────────────────────────────────────

def _evaluate_add_risk(
    *,
    pair: str,
    side: str,
    add_size_usd: float,
    current_size_usd: float,
    max_position_size_usd: float,
    average_entry: float,
    add_price: float,
    stop_loss: float,
    take_profit: float,
    manual_risk_override: dict[str, Any] | None,
    dqs_score: int | None,
    kill_switch: bool,
    paper_mode: str,
    contradiction_score: int | None,
    mode: str,
) -> dict[str, Any]:
    """Tek bir ekleme adayı için tüm risk kontrollerini çalıştır.

    Returns AddToPositionControl dict (allowed / manual_required / blocked / risk_warning).
    """
    checks: dict[str, bool] = {}
    reasons: list[str] = []
    warnings: list[str] = []

    # 1. Max size
    new_size = current_size_usd + add_size_usd
    checks["max_position_size_passed"] = new_size <= max_position_size_usd + 0.01
    if not checks["max_position_size_passed"]:
        reasons.append(
            f"Maks pozisyon aşılır ({new_size:.0f} > {max_position_size_usd:.0f})"
        )

    # 2. Kill switch
    checks["kill_switch_off"] = not kill_switch
    if kill_switch:
        reasons.append("Kill switch aktif")

    # 3. DQS
    checks["dqs_passed"] = (dqs_score is None) or (dqs_score >= 55)
    if dqs_score is not None and dqs_score < 55:
        reasons.append(f"DQS düşük ({dqs_score} < 55)")

    # 4. Stop mesafesi güvenli mi (entry ile add_price arası mantıklı + stop'tan uzak)
    if stop_loss > 0 and add_price > 0:
        if side == "LONG":
            stop_distance_pct = ((add_price - stop_loss) / add_price) * 100.0
        else:
            stop_distance_pct = ((stop_loss - add_price) / add_price) * 100.0
        checks["stop_distance_safe"] = stop_distance_pct >= STOP_PROXIMITY_THRESHOLD_PCT
        checks["not_too_close_to_stop"] = stop_distance_pct >= 0.5
        if not checks["not_too_close_to_stop"]:
            reasons.append(f"Fiyat stop'a çok yakın ({stop_distance_pct:.2f}%)")
        elif not checks["stop_distance_safe"]:
            warnings.append(f"Stop'a yakın ({stop_distance_pct:.2f}% < {STOP_PROXIMITY_THRESHOLD_PCT}%)")
    else:
        checks["stop_distance_safe"] = True
        checks["not_too_close_to_stop"] = True

    # 5. Average entry geçerli mi
    new_avg = _compute_average_entry(
        average_entry, current_size_usd, add_price, add_size_usd,
    )
    checks["average_entry_valid"] = new_avg > 0
    if not checks["average_entry_valid"]:
        reasons.append("Yeni ortalama entry hesaplanamadı")

    # 6. R/R ekleme sonrası
    rr_before = _compute_rr(side, average_entry, stop_loss, take_profit)
    rr_after = _compute_rr(side, new_avg, stop_loss, take_profit)
    checks["rr_after_add_valid"] = rr_after >= MIN_RR_AFTER_ADD
    if not checks["rr_after_add_valid"]:
        reasons.append(f"Ekleme sonrası R/R çok düşük ({rr_after:.2f} < {MIN_RR_AFTER_ADD})")
    if rr_before > 0 and (rr_before - rr_after) >= RR_WARNING_DROP:
        warnings.append(f"R/R düşüyor: {rr_before:.2f} → {rr_after:.2f}")

    # 7. Contradiction
    if contradiction_score is None:
        checks["contradiction_acceptable"] = True
    else:
        checks["contradiction_acceptable"] = contradiction_score < 80
        if contradiction_score >= 80:
            reasons.append(f"Contradiction yüksek ({contradiction_score})")

    # 8. Paper mode
    checks["paper_mode_allowed"] = mode != "off" and paper_mode != "conservative"
    if mode == "off":
        reasons.append("Ekleme modu kapalı")
    elif paper_mode == "conservative" and mode == "paper_auto":
        reasons.append("Conservative paper mode → paper_auto add devre dışı")
        checks["paper_mode_allowed"] = False

    # Maks kayıp hesabı
    max_loss_before = None
    max_loss_after = None
    if stop_loss > 0 and average_entry > 0:
        max_loss_before = round((current_size_usd / average_entry) * abs(average_entry - stop_loss), 2)
    if stop_loss > 0 and new_avg > 0:
        max_loss_after = round((new_size / new_avg) * abs(new_avg - stop_loss), 2)

    # ── Status karar matrisi ────────────────────────────────────────────────
    hard_fail_keys = (
        "max_position_size_passed", "kill_switch_off", "dqs_passed",
        "not_too_close_to_stop", "average_entry_valid", "rr_after_add_valid",
        "contradiction_acceptable", "paper_mode_allowed",
    )
    hard_failed = any(not checks[k] for k in hard_fail_keys)
    needs_manual = not checks["stop_distance_safe"]
    has_warning = bool(warnings)

    if hard_failed:
        status: AddStatus = "blocked"
        allowed = False
    elif needs_manual or (mode == "manual"):
        # Manuel modda her ekleme manuel onay sayılır (UI butonu zaten manuel)
        # paper_auto modda stop yakınlığı manuel onaya düşürür
        if mode == "paper_auto" and not checks["stop_distance_safe"]:
            status = "manual_required"
            allowed = False
        elif mode == "paper_auto":
            status = "risk_warning" if has_warning else "allowed"
            allowed = True
        else:
            status = "allowed"   # manuel modda kullanıcı zaten onayladı
            allowed = True
    elif has_warning:
        status = "risk_warning"
        allowed = True
    else:
        status = "allowed"
        allowed = True

    reason_text = " · ".join(reasons) if reasons else (
        " · ".join(warnings) if warnings else "Tüm kontroller temiz"
    )

    return {
        "allowed":     allowed,
        "status":      status,
        "reason":      reason_text,
        "risk_checks": checks,
        "warnings":    warnings,
        "before_add": {
            "size_usd":      round(current_size_usd, 2),
            "average_entry": round(average_entry, 6),
            "stop_loss":     stop_loss,
            "take_profit":   take_profit,
            "rr":            rr_before,
            "max_loss_usd":  max_loss_before,
        },
        "after_add_preview": {
            "size_usd":      round(new_size, 2),
            "average_entry": round(new_avg, 6),
            "stop_loss":     stop_loss,
            "take_profit":   take_profit,
            "rr":            rr_after,
            "max_loss_usd":  max_loss_after,
        },
        "manual_risk_override_active": bool(
            manual_risk_override and manual_risk_override.get("is_manual_override")
        ),
        "evaluated_at": _now_iso(),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def preview_add(
    pair: str,
    add_size_usd: float,
    *,
    add_price: float | None = None,
    mode: str = "manual",
) -> dict[str, Any]:
    """Eklemeyi gerçekleştirmeden risk gate çıktısı dön — UI önizleme için."""
    from app.services import paper_trading_service as pts

    with pts._LOCK:
        st = pts._load_state()
        pos = st.positions.get(pair)
        if pos is None:
            return {"status": "not_found", "pair": pair}

        price = float(add_price or st.last_tick_prices.get(pair, 0.0) or pos.entry_price)
        avg_entry = pos.average_entry_price or pos.entry_price
        plan = pos.add_plan or initialize_default_add_plan(
            pos.size_usd,
            position_size_constant=pts.POSITION_SIZE,
            average_entry=avg_entry,
        )
        manual_override = pos.manual_risk_override or {}
        contradiction = None
        if isinstance(pos.open_signal, dict):
            cs = pos.open_signal.get("contradiction_score")
            if isinstance(cs, (int, float)):
                contradiction = int(cs)

        paper_mode = (
            __import__("os").environ.get("PAPER_TRADING_MODE", "controlled_aggressive").lower()
        )

        control = _evaluate_add_risk(
            pair=pair, side=pos.side,
            add_size_usd=add_size_usd,
            current_size_usd=pos.size_usd,
            max_position_size_usd=plan.get("max_position_size_usd")
                or round(pts.POSITION_SIZE * MAX_POSITION_MULTIPLIER, 2),
            average_entry=avg_entry,
            add_price=price,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            manual_risk_override=manual_override,
            dqs_score=None,         # preview anında DQS sig'inden okunmuyor
            kill_switch=False,      # preview'de kill switch sig'inden okunmuyor
            paper_mode=paper_mode,
            contradiction_score=contradiction,
            mode=mode,
        )
        return {
            "status": "ok",
            "pair":   pair,
            "control": control,
            "add_price": price,
            "mode": mode,
        }


def add_to_position(
    pair: str,
    add_size_usd: float,
    *,
    reason: str,
    mode: str = "manual",
    add_price: float | None = None,
    dqs_score: int | None = None,
    kill_switch: bool = False,
) -> dict[str, Any]:
    """Parçalı alım gerçekleştir — risk gate'i geçerse position state'i güncelle.

    PAPER_SAFE: Sadece state.positions[pair].size_usd ve average_entry_price
    güncellenir. Gerçek emir YOK.
    """
    from app.services import paper_trading_service as pts

    with pts._LOCK:
        st = pts._load_state()
        pos = st.positions.get(pair)
        if pos is None:
            return {"status": "not_found", "pair": pair}
        if add_size_usd <= 0:
            return {"status": "invalid_size", "pair": pair, "reason": "add_size_usd > 0 olmalı"}

        price = float(add_price or st.last_tick_prices.get(pair, 0.0) or pos.entry_price)
        if price <= 0:
            return {"status": "no_price", "pair": pair}

        avg_entry = pos.average_entry_price or pos.entry_price
        plan = pos.add_plan or initialize_default_add_plan(
            pos.size_usd,
            position_size_constant=pts.POSITION_SIZE,
            average_entry=avg_entry,
        )
        manual_override = pos.manual_risk_override or {}
        contradiction = None
        if isinstance(pos.open_signal, dict):
            cs = pos.open_signal.get("contradiction_score")
            if isinstance(cs, (int, float)):
                contradiction = int(cs)

        paper_mode = (
            __import__("os").environ.get("PAPER_TRADING_MODE", "controlled_aggressive").lower()
        )

        control = _evaluate_add_risk(
            pair=pair, side=pos.side,
            add_size_usd=add_size_usd,
            current_size_usd=pos.size_usd,
            max_position_size_usd=plan.get("max_position_size_usd")
                or round(pts.POSITION_SIZE * MAX_POSITION_MULTIPLIER, 2),
            average_entry=avg_entry,
            add_price=price,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            manual_risk_override=manual_override,
            dqs_score=dqs_score,
            kill_switch=kill_switch,
            paper_mode=paper_mode,
            contradiction_score=contradiction,
            mode=mode,
        )

        # Audit her durumda yazılır
        plan["last_control_result"] = control

        if not control["allowed"]:
            pos.add_plan = plan
            pts._save_state(st)
            return {
                "status": "rejected",
                "pair":   pair,
                "control": control,
            }

        # ── Eklemeyi uygula ─────────────────────────────────────────────────
        new_size = pos.size_usd + add_size_usd
        new_avg = _compute_average_entry(avg_entry, pos.size_usd, price, add_size_usd)
        pos.size_usd = round(new_size, 2)
        pos.average_entry_price = new_avg
        now_iso = _now_iso()
        pos.add_history.append({
            "added_at":   now_iso,
            "add_size_usd": round(add_size_usd, 2),
            "add_price":   price,
            "reason":      reason,
            "mode":        mode,
            "new_size_usd": pos.size_usd,
            "new_average_entry": new_avg,
        })

        # add_plan güncelle: remaining_add_capacity, current_size, average_entry
        plan["current_size_usd"] = pos.size_usd
        plan["average_entry_price"] = new_avg
        max_pos = plan.get("max_position_size_usd") or round(pts.POSITION_SIZE * MAX_POSITION_MULTIPLIER, 2)
        plan["remaining_add_capacity_usd"] = max(0.0, round(max_pos - pos.size_usd, 2))
        pos.add_plan = plan

        # Eğer manuel risk override aktifse uyarı bayrağı set et (UI'da gösterilir)
        if manual_override and manual_override.get("is_manual_override"):
            manual_override["last_position_change_at"] = now_iso
            manual_override["last_change_reason"] = "add_to_position"
            pos.manual_risk_override = manual_override

        pts._save_state(st)

        # Audit event
        try:
            pts._try_emit(
                "paper_position_added", "TRADE_EVENT",
                f"Pozisyona Ekleme — {pair}",
                f"{pos.side} {pair} pozisyonuna +${add_size_usd:,.0f} eklendi · "
                f"yeni boyut ${pos.size_usd:,.0f} · ortalama entry {new_avg:.4f} · sebep: {reason}",
                pair=pair, side=pos.side, price=price, size_usd=add_size_usd,
                reason=reason,
                metadata={"new_size_usd": pos.size_usd, "new_average_entry": new_avg,
                          "mode": mode, "manual_override_active": bool(manual_override)},
            )
        except Exception:
            pass

        return {
            "status": "added",
            "pair":   pair,
            "control": control,
            "new_size_usd": pos.size_usd,
            "new_average_entry": new_avg,
            "add_price": price,
        }


def update_add_plan(
    pair: str,
    *,
    mode: AddMode | None = None,
    max_position_size_usd: float | None = None,
    add_levels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add planını güncelle — mod, max size, kademe seviyeleri."""
    from app.services import paper_trading_service as pts

    with pts._LOCK:
        st = pts._load_state()
        pos = st.positions.get(pair)
        if pos is None:
            return {"status": "not_found", "pair": pair}

        avg_entry = pos.average_entry_price or pos.entry_price
        plan = pos.add_plan or initialize_default_add_plan(
            pos.size_usd,
            position_size_constant=pts.POSITION_SIZE,
            average_entry=avg_entry,
        )
        if mode is not None:
            if mode not in ("off", "manual", "paper_auto"):
                return {"status": "invalid_mode", "pair": pair}
            plan["mode"] = mode
        if max_position_size_usd is not None:
            if max_position_size_usd < pos.size_usd:
                return {
                    "status": "invalid_max_size",
                    "pair": pair,
                    "reason": "max_position_size_usd mevcut boyuttan küçük olamaz",
                }
            plan["max_position_size_usd"] = round(float(max_position_size_usd), 2)
            plan["remaining_add_capacity_usd"] = max(
                0.0, round(plan["max_position_size_usd"] - pos.size_usd, 2),
            )
        if add_levels is not None:
            sanitized = []
            for lv in add_levels:
                if not isinstance(lv, dict):
                    continue
                sanitized.append({
                    "id":                          str(lv.get("id") or f"lv_{len(sanitized)+1}"),
                    "trigger_type":                str(lv.get("trigger_type") or "manual"),
                    "trigger_price":               (float(lv["trigger_price"])
                                                    if lv.get("trigger_price") is not None else None),
                    "trigger_pnl_pct":             (float(lv["trigger_pnl_pct"])
                                                    if lv.get("trigger_pnl_pct") is not None else None),
                    "add_size_usd":                float(lv.get("add_size_usd") or 0.0),
                    "condition_text":              str(lv.get("condition_text") or ""),
                    "status":                      str(lv.get("status") or "waiting"),
                    "requires_manual_confirmation": bool(lv.get("requires_manual_confirmation", False)),
                    "created_at":                  str(lv.get("created_at") or _now_iso()),
                    "filled_at":                   lv.get("filled_at"),
                })
            plan["add_levels"] = sanitized

        pos.add_plan = plan
        pts._save_state(st)
        return {"status": "updated", "pair": pair, "add_plan": plan}


# ── Manuel SL/TP Override ────────────────────────────────────────────────────

def set_manual_risk_override(
    pair: str,
    *,
    new_stop_loss: float,
    new_take_profit: float,
    reason: str = "",
) -> dict[str, Any]:
    """SL/TP'yi elle değiştir — otomatik plan backup olarak saklanır."""
    from app.services import paper_trading_service as pts

    with pts._LOCK:
        st = pts._load_state()
        pos = st.positions.get(pair)
        if pos is None:
            return {"status": "not_found", "pair": pair}
        if new_stop_loss <= 0 or new_take_profit <= 0:
            return {"status": "invalid_values", "pair": pair}

        # SL/TP yön doğrulaması (LONG: SL<entry<TP, SHORT: TP<entry<SL)
        entry = pos.average_entry_price or pos.entry_price
        if pos.side == "LONG":
            if not (new_stop_loss < entry < new_take_profit):
                return {
                    "status": "invalid_direction",
                    "pair": pair,
                    "reason": f"LONG için SL<entry<TP gerekli (entry={entry})",
                }
        else:
            if not (new_take_profit < entry < new_stop_loss):
                return {
                    "status": "invalid_direction",
                    "pair": pair,
                    "reason": f"SHORT için TP<entry<SL gerekli (entry={entry})",
                }

        prev_sl = pos.stop_loss
        prev_tp = pos.take_profit
        prev_rr = _compute_rr(pos.side, entry, prev_sl, prev_tp)
        new_rr = _compute_rr(pos.side, entry, new_stop_loss, new_take_profit)
        now_iso = _now_iso()

        # Mevcut override varsa backup'ı koru, yoksa şu anki otomatik planı backup'la
        existing_override = pos.manual_risk_override or {}
        auto_backup = existing_override.get("auto_plan_backup")
        if not auto_backup:
            auto_backup = {
                "stop_loss":      prev_sl,
                "take_profit":    prev_tp,
                "rr":             prev_rr,
                "atr_multiplier": (pos.risk_plan or {}).get("aggression", {}).get("atr_multiplier")
                                  or (pos.risk_plan or {}).get("aggression_multiplier")
                                  or None,
            }

        warnings: list[str] = []
        if pos.side == "LONG":
            sl_pct = ((entry - new_stop_loss) / entry) * 100.0
            tp_pct = ((new_take_profit - entry) / entry) * 100.0
        else:
            sl_pct = ((new_stop_loss - entry) / entry) * 100.0
            tp_pct = ((entry - new_take_profit) / entry) * 100.0
        if sl_pct < 0.5:
            warnings.append(f"Stop entry'ye çok yakın (%{sl_pct:.2f})")
        if tp_pct < 0.5:
            warnings.append(f"TP entry'ye çok yakın (%{tp_pct:.2f})")
        if new_rr < 1.0:
            warnings.append(f"Yeni R/R çok düşük ({new_rr:.2f} < 1.0)")

        pos.stop_loss = round(float(new_stop_loss), 4)
        pos.take_profit = round(float(new_take_profit), 4)
        pos.manual_risk_override = {
            "is_manual_override":  True,
            "previous_stop_loss":  prev_sl,
            "previous_take_profit": prev_tp,
            "new_stop_loss":       pos.stop_loss,
            "new_take_profit":     pos.take_profit,
            "previous_rr":         prev_rr,
            "new_rr":              new_rr,
            "changed_at":          now_iso,
            "changed_by":          "user",
            "reason":              reason,
            "auto_plan_backup":    auto_backup,
            "warnings":            warnings,
        }
        pts._save_state(st)

        try:
            pts._try_emit(
                "manual_risk_override_set", "TRADE_EVENT",
                f"Manuel Risk Planı — {pair}",
                f"{pos.side} {pair} SL/TP elle değiştirildi: SL {prev_sl} → {pos.stop_loss}, "
                f"TP {prev_tp} → {pos.take_profit} (R/R {prev_rr:.2f} → {new_rr:.2f}) · sebep: {reason}",
                pair=pair, side=pos.side,
                metadata={"warnings": warnings, "new_rr": new_rr},
            )
        except Exception:
            pass

        return {
            "status": "overridden",
            "pair":   pair,
            "override": pos.manual_risk_override,
        }


def reset_to_auto_risk_plan(pair: str) -> dict[str, Any]:
    """Manuel override'ı kaldır, otomatik plana geri dön."""
    from app.services import paper_trading_service as pts

    with pts._LOCK:
        st = pts._load_state()
        pos = st.positions.get(pair)
        if pos is None:
            return {"status": "not_found", "pair": pair}
        override = pos.manual_risk_override or {}
        if not override.get("is_manual_override"):
            return {"status": "no_override", "pair": pair}
        backup = override.get("auto_plan_backup") or {}
        if backup.get("stop_loss"):
            pos.stop_loss = float(backup["stop_loss"])
        if backup.get("take_profit"):
            pos.take_profit = float(backup["take_profit"])
        pos.manual_risk_override = {}
        pts._save_state(st)

        try:
            pts._try_emit(
                "manual_risk_override_reset", "INFO",
                f"Otomatik Risk Planı — {pair}",
                f"{pos.side} {pair} otomatik SL/TP planına geri döndü.",
                pair=pair, side=pos.side,
            )
        except Exception:
            pass

        return {
            "status": "reset",
            "pair":   pair,
            "stop_loss":   pos.stop_loss,
            "take_profit": pos.take_profit,
        }


# ── Opening Explanation ──────────────────────────────────────────────────────

def build_opening_explanation(
    open_signal: dict[str, Any] | None,
    *,
    pair: str,
    side: str,
) -> dict[str, Any]:
    """open_signal içindeki katmanlardan "neden açıldı" açıklaması üret.

    Eksik alanlar varsa fallback açıklama üretir — "Bu işlem neden açıldı?"
    sorusu her zaman cevaplanır.
    """
    if not isinstance(open_signal, dict):
        open_signal = {}

    # Pattern bilgisi
    pattern_score = open_signal.get("pattern_score")
    pattern_bias = open_signal.get("pattern_bias") or open_signal.get("pattern", {}).get("bias")
    pattern_active = (
        open_signal.get("pattern_active_patterns")
        or open_signal.get("pattern", {}).get("active_patterns")
        or []
    )
    pattern_weight = open_signal.get("pattern_weight")

    pattern_summary_parts = []
    if pattern_bias:
        pattern_summary_parts.append(f"Pattern bias: {pattern_bias}")
    if pattern_score is not None:
        pattern_summary_parts.append(f"skor {pattern_score:+.1f}/100" if isinstance(pattern_score, (int, float)) else f"skor {pattern_score}")
    if pattern_active:
        active_text = ", ".join(str(p) for p in pattern_active[:4])
        pattern_summary_parts.append(active_text)
    pattern_summary = " · ".join(pattern_summary_parts) if pattern_summary_parts else "Pattern verisi yok"

    # Pattern ana sebep miydi?
    pattern_is_primary = False
    if pattern_bias and side in ("LONG", "SHORT"):
        if side == "LONG" and str(pattern_bias).upper() in ("BULLISH", "STRONG_BULLISH"):
            pattern_is_primary = True
        elif side == "SHORT" and str(pattern_bias).upper() in ("BEARISH", "STRONG_BEARISH"):
            pattern_is_primary = True
    if pattern_weight is not None and float(pattern_weight) == 0:
        pattern_is_primary = False

    # Destekleyen katmanlar
    supporting: dict[str, str] = {}
    raw_regime = (open_signal.get("raw_regime") or "").upper()
    if raw_regime:
        if raw_regime in ("RISK_ON", "OFFENSIVE", "AGGRESSIVE_RISK_ON"):
            supporting["macro"] = f"Makro zemin destekleyici ({raw_regime})"
        elif raw_regime in ("NEUTRAL", "TRANSITIONING"):
            supporting["macro"] = f"Makro zemin nötr/geçiş ({raw_regime}) — hafif destek"
        elif raw_regime in ("DEFENSIVE", "RISK_OFF"):
            supporting["macro"] = f"Makro zemin defansif ({raw_regime}) — pozisyon küçük tutulmuş olmalı"
        else:
            supporting["macro"] = f"Makro zemin: {raw_regime}"

    appetite = open_signal.get("risk_appetite") or {}
    appetite_status = ""
    if isinstance(appetite, dict):
        appetite_status = str(appetite.get("status") or "").upper()
    elif isinstance(appetite, str):
        appetite_status = appetite.upper()
    if appetite_status:
        if appetite_status in ("STRONG",):
            supporting["risk_appetite"] = f"Risk iştahı güçlü ({appetite_status})"
        elif appetite_status in ("MODERATE", "MEDIUM"):
            supporting["risk_appetite"] = f"Risk iştahı seçici/orta ({appetite_status}) — tam boy değil"
        elif appetite_status in ("WEAK", "DEFENSIVE"):
            supporting["risk_appetite"] = f"Risk iştahı zayıf ({appetite_status}) — küçük denemeye uygun"
        else:
            supporting["risk_appetite"] = f"Risk iştahı: {appetite_status}"

    final_score = open_signal.get("final_score")
    final_direction = open_signal.get("final_direction")
    if final_score is not None and final_direction:
        supporting["consensus"] = (
            f"Agent consensus skoru işlem eşiğini geçti ({final_direction} @ {float(final_score):.1f})"
        )

    aggression_ctx = open_signal.get("aggression_context") or {}
    if aggression_ctx:
        level = aggression_ctx.get("aggression_level")
        recommended_tf = aggression_ctx.get("recommended_timeframe")
        if level:
            supporting["aggression"] = (
                f"Aggression awareness layer: {level}" +
                (f" / {recommended_tf}" if recommended_tf else "") +
                f" → kontrollü-agresif paper mode altında {('küçük' if level in ('high','extreme') else 'orta')} boyut, yakın stop ile açıldı."
            )

    risk_plan = open_signal.get("risk_plan") or {}
    if risk_plan.get("sl_basis"):
        supporting["risk_plan"] = (
            f"Risk planı kurulabildi: {risk_plan.get('sl_basis')}"
        )
    elif open_signal.get("stop_decision"):
        sd = open_signal["stop_decision"]
        supporting["technical"] = (
            f"Stop seviyesi yakın kurulabildi (ATR×{sd.get('atr_multiplier')}, tip={sd.get('stop_type')})"
        )

    # Karşı çıkan sinyaller
    opposing: list[str] = []
    if pattern_bias and not pattern_is_primary:
        if str(pattern_bias).upper() in ("BEARISH", "STRONG_BEARISH") and side == "LONG":
            opposing.append("Pattern bearish — LONG yönünü teyit etmiyor")
        elif str(pattern_bias).upper() in ("BULLISH", "STRONG_BULLISH") and side == "SHORT":
            opposing.append("Pattern bullish — SHORT yönünü teyit etmiyor")
        elif str(pattern_bias).upper() == "NEUTRAL":
            opposing.append("Pattern nötr — yön teyidi vermiyor")
    if isinstance(pattern_score, (int, float)) and pattern_score < 0 and side == "LONG":
        opposing.append(f"Pattern skoru negatif ({pattern_score:+.1f}/100)")
    if isinstance(pattern_score, (int, float)) and pattern_score > 0 and side == "SHORT":
        opposing.append(f"Pattern skoru pozitif ama SHORT açıldı ({pattern_score:+.1f}/100)")
    # TF karşı sinyaller
    tf_signals = open_signal.get("tf_signals") or {}
    if isinstance(tf_signals, dict):
        for tf, data in tf_signals.items():
            if not isinstance(data, dict):
                continue
            dir_ = str(data.get("direction") or "").lower()
            if side == "LONG" and dir_ in ("bearish", "strong_bearish"):
                opposing.append(f"{tf}: {dir_} — kısa vadeli karşı baskı")
            elif side == "SHORT" and dir_ in ("bullish", "strong_bullish"):
                opposing.append(f"{tf}: {dir_} — kısa vadeli karşı baskı")
    # Contradiction
    cs = open_signal.get("contradiction_score")
    if isinstance(cs, (int, float)) and cs >= 40:
        opposing.append(f"Contradiction skoru orta-yüksek ({cs}/100)")

    # Ana sebep
    if pattern_is_primary:
        primary_reason = (
            f"Pattern yön teyidi verdi ({pattern_bias}) — bu işlemin ana açılış sebebi pattern teknik onayıydı."
        )
    elif final_score is not None and final_direction:
        primary_reason = (
            f"Agent consensus skoru ({float(final_score):.1f}) işlem eşiğini geçti; "
            f"risk gate bloklamadı ve risk planı kurulabildi. "
            f"Pattern bu işlemin ana sebebi DEĞİLDİ."
        )
    elif aggression_ctx.get("aggression_level"):
        primary_reason = (
            f"Aggregator controlled-aggressive paper mode altında {aggression_ctx['aggression_level']} "
            f"agresiflik seviyesinde tactical deneme olarak açıldı. "
            f"Pattern bu işlemin ana sebebi değildi."
        )
    else:
        primary_reason = (
            f"{side} {pair}: open_signal içinde net bir ana sebep alanı bulunamadı; "
            f"işlem agent sinyaliyle açılmış (pattern/aggregator ayrıntıları eksik)."
        )

    # Pattern ek notlar
    pattern_notes: list[str] = []
    if pattern_weight is not None and float(pattern_weight) == 0:
        pattern_notes.append("Pattern modülü final skora katkı vermedi (ağırlık 0).")
    if not pattern_is_primary and pattern_bias:
        pattern_notes.append("Pattern bu işlemin ana açılış sebebi değildi.")
    if isinstance(pattern_score, (int, float)) and pattern_score < 0 and side == "LONG":
        pattern_notes.append("Pattern karara karşı çıkan sinyallerden biri olarak kaydedildi.")

    # Neden yine açıldı
    why_anyway_parts = []
    if aggression_ctx.get("aggression_level"):
        level = aggression_ctx["aggression_level"]
        why_anyway_parts.append(
            f"Sistem bunu 'confirmed trend' değil, paper trading içinde {level} agresiflikte "
            f"tactical/kontrollü deneme olarak sınıflandırdı."
        )
    if opposing:
        why_anyway_parts.append(
            "Karşı sinyaller mevcut → pozisyon küçük tutulmuş, stop yakın, holding kısa olmalı."
        )
    if not why_anyway_parts:
        why_anyway_parts.append(
            "Risk gate bloklamadığı için sinyal eşiğini geçen sinyaller işleme alındı."
        )
    why_trade_opened_anyway = " ".join(why_anyway_parts)

    # Invalidation
    invalidation: list[str] = ["Stop Loss kırılırsa pozisyon kapanır"]
    if opposing:
        invalidation.append("Karşı çıkan sinyaller güçlenir ve yeni dip/tepe gelirse")
    if appetite_status in ("WEAK", "DEFENSIVE", "CRISIS"):
        invalidation.append("Risk iştahı daha da zayıflarsa")
    invalidation.append("DQS veya risk gate bozulursa")

    return {
        "primary_reason":          primary_reason,
        "was_pattern_primary_reason": pattern_is_primary,
        "pattern_summary":         pattern_summary,
        "pattern_notes":           pattern_notes,
        "supporting_layers":       supporting,
        "opposing_signals":        opposing,
        "why_trade_opened_anyway": why_trade_opened_anyway,
        "invalidation_summary":    invalidation,
        "generated_at":            _now_iso(),
    }
