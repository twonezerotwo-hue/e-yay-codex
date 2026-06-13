"""
Aşama 6 — Lightweight agent orchestration status (read-only, additive).

Agent'ın "neyi kontrol ettiğini" tek bir salt-okunur durum bloğunda toplar.
Büyük agent framework DEĞİL: mevcut paper snapshot + banner çıktısından ucuz
şekilde türetilir. Canlı market/broker çağrısı yapmaz, state yazmaz, karar
üretmez. Tüm hatalar yutulur — banner'ı / paper akışını ASLA bozmaz.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _status_from_age(age: float | None) -> str:
    """tick/price yaşına göre kaynak durumu."""
    if age is None:
        return "missing"
    if age <= 300:
        return "ok"
    if age <= 900:
        return "stale"
    return "degraded"


def build_orchestration_status(banner: dict[str, Any] | None = None) -> dict[str, Any]:
    """agent_orchestration bloğunu üretir (best-effort)."""
    banner = banner or {}

    snap: dict[str, Any] = {}
    try:
        from app.services.paper_trading_service import get_snapshot  # noqa: PLC0415
        snap = get_snapshot(include_opinion=False) or {}
    except Exception:  # noqa: BLE001
        snap = {}

    pe = snap.get("paper_experiment") or {}
    tick_age = snap.get("tick_age_seconds")

    # ── Data sources: ok / stale / degraded / missing / unknown ──────────────
    data_sources = {
        "price":       _status_from_age(tick_age),
        "paper_state": "ok" if snap else "missing",
        "news":        "ok" if banner.get("news_story") else "unknown",
        "macro":       "ok" if banner.get("market_thought") else "unknown",
        "event":       "ok" if (banner.get("event_story") or banner.get("event_calendar_note")) else "unknown",
    }

    # ── Paper observer ───────────────────────────────────────────────────────
    recent_labels = pe.get("recent_labels") or []
    active_adj = pe.get("active_adjustments") or {}
    paper_observer = {
        "experiment_mode":    bool(pe.get("experiment_mode")),
        "mode":               pe.get("mode", "standard"),
        "recent_labels":      recent_labels[-5:],
        "active_adjustments": active_adj,
        "open_positions":     len(snap.get("open_positions") or []),
        "manual_ready":       len(snap.get("manual_ready_trades") or []),
        "last_event":         snap.get("last_event"),
    }

    # ── Validator ────────────────────────────────────────────────────────────
    stale_inputs   = [k for k, v in data_sources.items() if v in ("stale", "degraded")]
    missing_inputs = [k for k, v in data_sources.items() if v in ("missing", "unknown")]
    conflicts: list[str] = []
    for r in recent_labels:
        if "divergence_experiment" in (r.get("labels") or []):
            conflicts.append(f"{r.get('pair')} {r.get('side')}: sinyal↔görüş çelişkisi")
    validator = {
        "stale_inputs":   stale_inputs,
        "missing_inputs": missing_inputs,
        "conflicts":      conflicts[-3:],
    }

    # ── Strategist context ───────────────────────────────────────────────────
    best_candidate = next(
        (k for k, v in active_adj.items() if v.get("label") == "learning_boost"), "",
    )
    strategist_context = {
        "market_stance": banner.get("main_view") or banner.get("headline") or "",
        "last_decision": banner.get("position_note") or "",
        "best_candidate": best_candidate,
    }

    # ── Risk explainer (kısa Türkçe) ─────────────────────────────────────────
    anomaly = bool((snap.get("state_anomaly") or {}).get("active"))
    if anomaly:
        risk = "Paper state bütünlük uyarısı aktif — yeni işlem dikkatli, reset/repair önerilir."
    elif stale_inputs:
        risk = f"Bazı kaynaklar bayat ({', '.join(stale_inputs)}) — sinyaller temkinli okunmalı."
    elif missing_inputs:
        risk = f"Eksik/teyitsiz kaynak ({', '.join(missing_inputs)}) — açılış sınırlı tutulmalı."
    else:
        risk = "Veri akışı sağlıklı; paper gözlem normal sürüyor (gerçek emir yok)."

    return {
        "generated_at":       _utc_now_iso(),
        "data_sources":       data_sources,
        "paper_observer":     paper_observer,
        "validator":          validator,
        "strategist_context": strategist_context,
        "risk_explainer":     risk,
        "paper_safe":         True,
        "no_execution":       True,
    }


__all__ = ["build_orchestration_status"]
