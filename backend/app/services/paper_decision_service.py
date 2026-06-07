"""
Paper Trading Karar Merkezi — Decision Service
─────────────────────────────────────────────────────────────────────────────

Tek bir uçtan tüm karar zincirini birleştirir:

    Data Quality  →  Trigger Engine  →  Risk Engine
                ↘                        ↙
                  Paper Trading Decision
                            │
                ↙           ↓          ↘
        Entry Plan    Exit Plan   Active Positions
                            ↓
                 News-to-Decision Mapping
                            ↓
                     Learning Layer
                            ↓
                       Owner Action

Bu servis kendi karar üretmez — mevcut servislerin çıktısını tek bir frontend
şemasında derler. Karar dili (KÜÇÜLT / KORU / İZLE / İŞLEM YOK / vb.) açık
pozisyonların varlığına ve Risk Engine sonucuna göre disipline edilir:

    - Açık pozisyon YOK + RISK_REDUCE      → "YENİ RİSK AÇMA / BEKLE"
    - Açık pozisyon VAR + RISK_REDUCE      → "KÜÇÜLT"
    - KILL_SWITCH                          → "İŞLEM YOK / SİSTEM DURDU"
    - NO_POSITION_INCREASE                 → "POZİSYON ARTIRMA"
    - WATCH                                → "İZLE"
    - HOLD                                 → "KORU"

PAPER_SAFE · NO_EXECUTION — sadece okuma + analiz. Gerçek emir YOK.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Karar dili sabitleri ────────────────────────────────────────────────────

DECISION_LABEL_NEW_RISK_BLOCK   = "YENİ RİSK AÇMA / BEKLE"
DECISION_LABEL_REDUCE           = "KÜÇÜLT"
DECISION_LABEL_KILL             = "İŞLEM YOK / SİSTEM DURDU"
DECISION_LABEL_NO_INCREASE      = "POZİSYON ARTIRMA"
DECISION_LABEL_WATCH            = "İZLE"
DECISION_LABEL_HOLD             = "KORU"
DECISION_LABEL_FLAT_NEUTRAL     = "POZİSYON YOK · NÖTR İZLEME"

# DQS eşiği — bu skorun altında paper trade açılmamalı
_DQS_MIN_FOR_OPEN = 70.0


# ── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class PaperDecisionPayload:
    """GET /paper/decision/latest cevabının üst gövdesi."""
    generated_at:              str
    execution_status:          str
    owner_action:              str
    decision_label:            str
    decision_reason:           str
    market_interpretation:     dict[str, Any]    = field(default_factory=dict)
    data_quality_status:       dict[str, Any]    = field(default_factory=dict)
    trigger_engine_output:     dict[str, Any]    = field(default_factory=dict)
    risk_engine_verdict:       dict[str, Any]    = field(default_factory=dict)
    paper_trading_decision:    dict[str, Any]    = field(default_factory=dict)
    entry_plan:                dict[str, Any]    = field(default_factory=dict)
    exit_plan:                 dict[str, Any]    = field(default_factory=dict)
    active_paper_positions:    list[dict[str, Any]] = field(default_factory=list)
    news_to_decision_mapping:  list[dict[str, Any]] = field(default_factory=list)
    learning_layer:            dict[str, Any]    = field(default_factory=dict)


# ── Karar dili türeticisi ───────────────────────────────────────────────────

def derive_decision_label(
    *,
    risk_action: str,
    kill_switch_active: bool,
    has_open_positions: bool,
    dqs_decision: str | None = None,
) -> tuple[str, str]:
    """
    Karar dilini Risk Engine sonucu + açık pozisyon durumu + DQS'e göre üret.

    Returns: (decision_label, decision_reason)
    """
    # En üst öncelik: KILL_SWITCH
    if kill_switch_active or risk_action == "KILL_SWITCH":
        return DECISION_LABEL_KILL, "kill_switch_active"

    # DQS FAIL → karar verme
    if dqs_decision == "FAIL_NO_DECISION":
        return DECISION_LABEL_KILL, "dqs_fail_no_decision"

    # RISK_REDUCE — açık pozisyona bağlı
    if risk_action == "RISK_REDUCE":
        if has_open_positions:
            return DECISION_LABEL_REDUCE, "risk_engine_risk_reduce_with_open_positions"
        # Açık pozisyon yoksa KÜÇÜLT denmez!
        return DECISION_LABEL_NEW_RISK_BLOCK, "risk_engine_risk_reduce_but_no_open_positions"

    if risk_action == "NO_POSITION_INCREASE":
        return DECISION_LABEL_NO_INCREASE, "risk_engine_no_position_increase"

    if risk_action == "HEDGE_INCREASE":
        return DECISION_LABEL_WATCH, "risk_engine_hedge_increase"

    if risk_action == "WATCH":
        return DECISION_LABEL_WATCH, "risk_engine_watch"

    if risk_action == "HOLD":
        if has_open_positions:
            return DECISION_LABEL_HOLD, "risk_engine_hold_with_positions"
        return DECISION_LABEL_FLAT_NEUTRAL, "risk_engine_hold_flat"

    # Bilinmeyen → en güvenli: HOLD/BEKLE
    if has_open_positions:
        return DECISION_LABEL_HOLD, "fallback_hold"
    return DECISION_LABEL_FLAT_NEUTRAL, "fallback_flat"


# ── Bölüm derleyicileri (her birinin try/except'i kapalıdır) ────────────────

def _build_market_interpretation(report: Any) -> dict[str, Any]:
    """RegimeReport → market interpretation alanları."""
    if report is None:
        return {"regime": None, "summary": "report_unavailable"}
    macro = getattr(report, "macro_layer", None)
    appetite = getattr(report, "appetite_layer", None)
    regime = getattr(macro, "regime", None) if macro else None

    # Hızlı kategorik özet — score değerleri yoksa label döndür
    risk_on_score  = 0
    risk_off_score = 0
    if regime == "RISK_ON":
        risk_on_score = 75
    elif regime == "TRANSITIONING":
        risk_on_score = 45
        risk_off_score = 35
    elif regime == "DEFENSIVE":
        risk_off_score = 65
    elif regime == "CRISIS":
        risk_off_score = 90

    out: dict[str, Any] = {
        "regime":                    regime,
        "regime_confidence_pct":     getattr(macro, "confidence_pct", None) if macro else None,
        "regime_summary":            getattr(macro, "summary", None) if macro else None,
        "risk_on_score":             risk_on_score,
        "risk_off_score":            risk_off_score,
        "credit_confirmation":       getattr(appetite, "credit_signal", None) if appetite else None,
        "dollar_pressure":           getattr(macro, "dxy_signal", None) if macro else None,
        "energy_pressure":           getattr(macro, "energy_signal", None) if macro else None,
        "crypto_structure":          getattr(appetite, "btc_dominance_signal", None) if appetite else None,
        "silver_copper_confirmation": getattr(appetite, "safe_haven_signal", None) if appetite else None,
    }
    return out


def _build_data_quality_status(raw_snapshots: dict | None) -> dict[str, Any]:
    """DataQualityService → özet + decision_permission."""
    try:
        from app.services.data_quality_service import get_data_quality_summary
    except Exception:
        return {
            "overall_dqs":        None,
            "decision_permission": "UNKNOWN",
            "stale_assets":       [],
            "mock_assets":        [],
            "real_assets":        [],
            "missing_assets":     [],
        }

    snapshots: dict = raw_snapshots or {}
    summary = get_data_quality_summary(snapshots) if snapshots else {
        "total": 0, "fallback_count": 0, "fallback_assets": [],
        "quality_score": 0.0, "decision": "NO_DATA",
    }
    stale_assets   = []
    mock_assets    = []
    real_assets    = []
    for asset, snap in snapshots.items():
        if hasattr(snap, "is_stale") and snap.is_stale:
            stale_assets.append(str(asset))
        # mock/fallback ayrımı: fallback_used → mock benzeri ikinci tier
        if getattr(snap, "fallback_used", False):
            mock_assets.append(str(asset))
        else:
            real_assets.append(str(asset))

    overall_dqs = float(summary.get("quality_score") or 0.0)
    dqs_decision = summary.get("decision", "NO_DATA")

    # decision_permission — paper trade açılabilir mi?
    if dqs_decision == "FAIL_NO_DECISION":
        permission = "BLOCKED"
    elif dqs_decision == "LIMITED_ANALYSIS_ONLY":
        permission = "ANALYSIS_ONLY"
    elif overall_dqs < _DQS_MIN_FOR_OPEN:
        permission = "BELOW_THRESHOLD"
    elif dqs_decision == "PASS":
        permission = "ALLOWED"
    else:
        permission = "DEGRADED_ALLOWED"

    return {
        "overall_dqs":         round(overall_dqs, 2),
        "dqs_decision":        dqs_decision,
        "decision_permission": permission,
        "stale_assets":        stale_assets,
        "mock_assets":         mock_assets,
        "real_assets":         real_assets,
        "missing_assets":      summary.get("fallback_assets", []),
    }


def _build_trigger_engine_output(raw_snapshots: dict | None) -> dict[str, Any]:
    """TriggerEngine değerlendirmesini topla."""
    try:
        from app.services.trigger_engine import (
            TriggerConfirmationStatus,
            TriggerEngine,
        )
    except Exception:
        return {
            "active_triggers":         [],
            "trigger_severity":        "INFO",
            "confirmed_triggers":      [],
            "placeholder_triggers":    [],
            "new_vs_existing_triggers": {"new": 0, "existing": 0},
        }

    snapshots = list((raw_snapshots or {}).values())
    engine = TriggerEngine()
    try:
        results = engine.evaluate(snapshots) if snapshots else ()
    except Exception:
        results = ()

    active = []
    confirmed = []
    placeholder = []
    highest_severity = "INFO"
    sev_order = {"INFO": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}

    for r in results:
        sev = getattr(getattr(r, "severity", None), "value", None) or "INFO"
        status_val = getattr(getattr(r, "confirmation_status", None), "value", None)
        item = {
            "trigger_code":         r.trigger_code,
            "asset":                r.asset_symbol,
            "severity":             sev,
            "is_triggered":         r.is_triggered,
            "confirmation_status":  status_val,
            "message":              r.message,
        }
        if r.is_triggered:
            active.append(item)
        if status_val == TriggerConfirmationStatus.CONFIRMED.value:
            confirmed.append(item)
        elif status_val == TriggerConfirmationStatus.PLACEHOLDER.value:
            placeholder.append(item)
        if sev_order.get(sev, 0) > sev_order.get(highest_severity, 0):
            highest_severity = sev

    return {
        "active_triggers":          active,
        "trigger_severity":         highest_severity,
        "confirmed_triggers":       confirmed,
        "placeholder_triggers":     placeholder,
        "new_vs_existing_triggers": {"new": len(active), "existing": 0},
    }


def _build_risk_engine_verdict(raw_snapshots: dict | None) -> dict[str, Any]:
    """RiskEngine değerlendirmesini al."""
    fallback = {
        "risk_action":         "HOLD",
        "kill_switch_active":  False,
        "reason_codes":        [],
        "risk_softeners":      [],
        "risk_hardeners":      [],
        "summary":             "risk_engine_unavailable",
    }
    try:
        from app.services.data_quality_service import DataQualityService
        from app.services.risk_engine import RiskEngine, SnapshotRiskInput
        from app.services.trigger_engine import TriggerEngine
    except Exception:
        return fallback

    snapshots: dict = raw_snapshots or {}
    if not snapshots:
        return fallback

    try:
        dqs_svc = DataQualityService()
        snapshot_inputs = []
        for asset, snap in snapshots.items():
            if not hasattr(snap, "fallback_used"):
                continue
            dqs_result = dqs_svc.calculate_snapshot_score(snap)
            snapshot_inputs.append(SnapshotRiskInput(
                asset_symbol=str(asset),
                dqs_result=dqs_result,
            ))
        trigger_results = TriggerEngine().evaluate(list(snapshots.values()))
        verdict = RiskEngine().evaluate(snapshot_inputs, trigger_results)
    except Exception as exc:
        logger.debug("risk_engine evaluate failed: %s", exc)
        return fallback

    risk_action = verdict.risk_action.value
    reasons = list(verdict.reason_codes)
    softeners = [r for r in reasons if "WATCH" in r or "PLACEHOLDER" in r]
    hardeners = [
        r for r in reasons
        if any(k in r for k in ("RISK_REDUCE", "RED_ENERGY", "KILL", "STACK"))
    ]
    return {
        "risk_action":         risk_action,
        "kill_switch_active":  verdict.kill_switch_active,
        "reason_codes":        reasons,
        "risk_softeners":      softeners,
        "risk_hardeners":      hardeners,
        "summary":             verdict.summary,
    }


def _build_paper_trading_decision(
    state: Any,
    snapshot: dict | None,
    risk_verdict: dict[str, Any],
    dqs_status: dict[str, Any],
) -> dict[str, Any]:
    """Paper trading kararı + neden açılmıyor / açılırsa hangi varlık-yön."""
    has_open = bool(state and getattr(state, "positions", None))
    last_signals = getattr(state, "last_tick_signals", None) or {}
    last_event   = getattr(state, "last_event", None)

    # Hangi pair açılacaktı?
    would_pair = None
    would_dir  = None
    setup_valid = False
    missing: list[str] = []
    why_no_trade: list[str] = []

    # En yüksek consensus signali bul
    best_score = -1.0
    for pair, sig in last_signals.items():
        if not isinstance(sig, dict):
            continue
        score = float(sig.get("final_score") or 0.0)
        direction = (sig.get("final_direction") or "").upper()
        if direction in ("BULLISH", "BEARISH") and score > best_score:
            best_score = score
            would_pair = pair
            would_dir  = "LONG" if direction == "BULLISH" else "SHORT"

    # Setup validity: skor + direction + dqs + risk_action uyumu
    if would_pair is None:
        why_no_trade.append("no_directional_consensus")
    else:
        if best_score >= 60.0:
            setup_valid = True
        else:
            missing.append(f"consensus_score_below_60 ({best_score:.1f})")

    if dqs_status.get("decision_permission") in ("BLOCKED", "BELOW_THRESHOLD"):
        why_no_trade.append("data_quality_blocks_open")
        setup_valid = False

    risk_action = risk_verdict.get("risk_action", "HOLD")
    if risk_action in ("KILL_SWITCH", "RISK_REDUCE", "NO_POSITION_INCREASE"):
        why_no_trade.append(f"risk_engine_blocks_new:{risk_action}")
        setup_valid = False

    return {
        "paper_mode_status":      "PAPER_SAFE / NO_EXECUTION",
        "latest_paper_decision":  last_event or "no_event",
        "position_intent":        "OPEN" if (setup_valid and not has_open) else "HOLD/FLAT",
        "why_no_trade":           why_no_trade,
        "would_trade_asset":      would_pair,
        "would_trade_direction":  would_dir,
        "setup_validity":         setup_valid,
        "missing_confirmations":  missing,
        "has_open_positions":     has_open,
        "best_consensus_score":   round(best_score, 2) if best_score >= 0 else None,
    }


def _build_entry_plan(
    paper_decision: dict[str, Any],
    market_int: dict[str, Any],
    risk_verdict: dict[str, Any],
) -> dict[str, Any]:
    """Hangi koşullar sağlanırsa giriş yapılır?"""
    pair = paper_decision.get("would_trade_asset")
    direction = paper_decision.get("would_trade_direction")

    conditions: list[str] = []
    if not paper_decision.get("setup_validity"):
        conditions.append("Setup geçerli değil — giriş yok")

    if pair and direction:
        conditions.append(f"{pair} {direction} sinyali ≥60 konsensus skoru")
        conditions.append(f"{pair} fiyatı son tick'ten ±0.3% içinde stabil")
        if direction == "LONG":
            conditions.append(f"{pair} 1H grafiğinde destek korunuyor")
        else:
            conditions.append(f"{pair} 1H grafiğinde direnç tutuyor")

    required_macro = []
    if market_int.get("regime") in ("DEFENSIVE", "CRISIS"):
        required_macro.append("Rejim RISK_ON veya TRANSITIONING'e dönmeli")
    if (market_int.get("dollar_pressure") or "").upper().startswith("DXY YUK"):
        required_macro.append("DXY baskısı gevşemeli")

    required_credit = []
    cs = market_int.get("credit_confirmation")
    if cs and "ZAYIF" in (cs or "").upper():
        required_credit.append("HYG/JNK kredi konfirmasyonu güçlenmeli")

    required_news = []
    if risk_verdict.get("kill_switch_active"):
        required_news.append("KILL_SWITCH koşulu kalkmalı")

    return {
        "conditions_to_enter":             conditions,
        "required_price_levels":           [],
        "required_macro_confirmations":    required_macro,
        "required_credit_confirmations":   required_credit,
        "required_news_confirmations":     required_news,
    }


def _build_exit_plan(active_positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Açık pozisyonlardan birleşik exit planı çıkar."""
    if not active_positions:
        return {
            "stop_loss":               None,
            "target_price":            None,
            "invalidation_conditions": [],
            "time_stop":               None,
            "risk_reduce_conditions":  [],
        }

    sl = [p.get("stop_loss") for p in active_positions if p.get("stop_loss")]
    tp = [p.get("target_price") for p in active_positions if p.get("target_price")]
    inv = []
    rr = []
    for p in active_positions:
        if p.get("close_if"):
            inv.append(f"{p.get('asset')}: {p.get('close_if')}")
        sl_v = p.get("stop_loss")
        if sl_v:
            rr.append(f"{p.get('asset')}: SL {sl_v} altına yaklaşırsa pozisyon küçült")

    return {
        "stop_loss":               sl[0] if sl else None,
        "target_price":            tp[0] if tp else None,
        "invalidation_conditions": inv,
        "time_stop":               "horizon_hours sonu — bkz. position.holding_hours",
        "risk_reduce_conditions":  rr,
    }


def _build_active_positions(snapshot: dict | None) -> list[dict[str, Any]]:
    """get_snapshot()'ın open_positions çıktısını dashboard şemasına çevir."""
    if not snapshot:
        return []
    out: list[dict[str, Any]] = []
    for pos in snapshot.get("open_positions", []) or []:
        out.append({
            "asset":           pos.get("pair"),
            "direction":       pos.get("side"),
            "entry_price":     pos.get("entry_price"),
            "current_price":   pos.get("current_price"),
            "stop_loss":       pos.get("stop_loss"),
            "target_price":    pos.get("take_profit"),
            "position_size":   pos.get("size_usd") or pos.get("qty"),
            "unrealized_pnl":  pos.get("pnl_usd"),
            "unrealized_pnl_pct": pos.get("pnl_pct"),
            "risk_reward":     pos.get("risk_reward"),
            "opened_because":  pos.get("open_reason") or pos.get("rationale"),
            "close_if":        pos.get("invalidation") or pos.get("close_if"),
            "horizon_hours":   pos.get("horizon_hours"),
            "entry_at":        pos.get("entry_at"),
            "fingerprint":     pos.get("fingerprint"),
        })
    return out


def _build_news_to_decision(
    alerts: list[dict[str, Any]] | None,
    paper_decision: dict[str, Any],
) -> list[dict[str, Any]]:
    """Alert event'leri haber→karar map'i biçimine getir."""
    items = alerts or []
    out: list[dict[str, Any]] = []
    intent_dir = paper_decision.get("would_trade_direction")
    pair = paper_decision.get("would_trade_asset")
    for a in items[:10]:
        if not isinstance(a, dict):
            continue
        title = a.get("title") or a.get("event_type") or "alert"
        message = a.get("message", "")
        affected = a.get("pair") or pair or "MULTI"
        out.append({
            "headline":            title,
            "source":              a.get("source") or "internal",
            "claim_status":        a.get("level") or "info",
            "affected_assets":     [affected],
            "expected_direction":  intent_dir if affected == pair else "UNKNOWN",
            "confirmation_status": "internal_alert",
            "decision_impact":     message[:140] if isinstance(message, str) else "",
            "emitted_at":          a.get("ts") or a.get("emitted_at"),
        })
    return out


def _build_learning_layer(
    state: Any,
    decision_label: str,
    paper_decision: dict[str, Any],
    risk_verdict: dict[str, Any],
) -> dict[str, Any]:
    """Her karar için bir prediction_id üret + ne kontrol edileceği."""
    prediction_id = f"pred_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

    pair = paper_decision.get("would_trade_asset")
    direction = paper_decision.get("would_trade_direction")
    expected = "no_action"
    if paper_decision.get("setup_validity") and pair and direction:
        expected = f"{pair} {direction} → 24-72 saat içinde fiyatın setup hedefine doğru hareket etmesi"

    failure_conditions = []
    if direction == "LONG":
        failure_conditions.append(f"{pair} fiyatı SL altına düşerse")
    elif direction == "SHORT":
        failure_conditions.append(f"{pair} fiyatı SL üstüne çıkarsa")
    if risk_verdict.get("risk_action") in ("RISK_REDUCE", "KILL_SWITCH"):
        failure_conditions.append("Risk Engine RISK_REDUCE/KILL_SWITCH'e dönerse")

    return {
        "prediction_id":            prediction_id,
        "decision_logged":          decision_label,
        "what_will_be_checked_later": [
            "24h içinde would_trade_asset fiyat ve consensus skoru",
            "Risk Engine action değişimi",
            "DQS bandı (PASS / DEGRADED)",
        ],
        "expected_outcome":         expected,
        "failure_conditions":       failure_conditions,
        "weekly_learning_tag":      f"week_{datetime.now(UTC).isocalendar().week}",
        "trade_count_so_far":       getattr(state, "trades", None) and len(state.trades) or 0,
    }


# ── Ana entry point ────────────────────────────────────────────────────────

def build_latest_decision() -> PaperDecisionPayload:
    """
    GET /api/v1/paper/decision/latest gövdesini üret.

    Hiç tick çalıştırmaz, hiç state mutate etmez. Tüm bağlı servisler exception
    yakalama altındadır — biri çökse bile diğer bölümler dolu döner.
    """
    # 1) Regime + raw snapshots (consensus pipeline'dan)
    report = None
    raw_snapshots: dict | None = None
    try:
        from app.api.consensus import _build_pipeline
        report, _rotation, _mtf, snapshots_iter = _build_pipeline()
        # _build_pipeline tuple döndürür → dict[asset_symbol → snapshot]
        if isinstance(snapshots_iter, dict):
            raw_snapshots = snapshots_iter
        elif snapshots_iter is not None:
            raw_snapshots = {}
            for s in snapshots_iter:
                key = getattr(s, "asset_symbol", None)
                if key is not None:
                    # AssetCode enum ya da str — string'e indirgeyip kullan
                    raw_snapshots[key] = s
    except Exception as exc:
        logger.debug("consensus pipeline unavailable: %s", exc)

    # 2) Paper trading state + snapshot (read-only)
    state = None
    snapshot = None
    try:
        from app.services import paper_trading_service as pts
        state = pts._load_state()
        snapshot = pts.get_snapshot()
    except Exception as exc:
        logger.debug("paper trading state unavailable: %s", exc)

    # 3) Alerts
    alerts: list[dict[str, Any]] = []
    try:
        from app.services import alert_event_service as alerts_svc
        alerts = alerts_svc.get_recent(10) or []
    except Exception:
        pass

    # 4) Bölümleri derle
    market_int   = _build_market_interpretation(report)
    dqs_status   = _build_data_quality_status(raw_snapshots)
    triggers     = _build_trigger_engine_output(raw_snapshots)
    risk_verdict = _build_risk_engine_verdict(raw_snapshots)
    paper_dec    = _build_paper_trading_decision(state, snapshot, risk_verdict, dqs_status)
    active_pos   = _build_active_positions(snapshot)
    entry_plan   = _build_entry_plan(paper_dec, market_int, risk_verdict)
    exit_plan    = _build_exit_plan(active_pos)
    news_map     = _build_news_to_decision(alerts, paper_dec)

    # 5) Karar dili
    decision_label, decision_reason = derive_decision_label(
        risk_action        = risk_verdict.get("risk_action", "HOLD"),
        kill_switch_active = bool(risk_verdict.get("kill_switch_active")),
        has_open_positions = bool(active_pos),
        dqs_decision       = dqs_status.get("dqs_decision"),
    )

    learning = _build_learning_layer(state, decision_label, paper_dec, risk_verdict)

    # 6) Owner action: report.owner_action varsa onu, yoksa decision_label
    owner_action = getattr(report, "owner_action", None) or decision_label

    # 7) Execution status — her zaman NO_EXECUTION
    execution_status = "PAPER_SAFE / NO_EXECUTION"

    return PaperDecisionPayload(
        generated_at             = datetime.now(UTC).isoformat(),
        execution_status         = execution_status,
        owner_action             = owner_action,
        decision_label           = decision_label,
        decision_reason          = decision_reason,
        market_interpretation    = market_int,
        data_quality_status      = dqs_status,
        trigger_engine_output    = triggers,
        risk_engine_verdict      = risk_verdict,
        paper_trading_decision   = paper_dec,
        entry_plan               = entry_plan,
        exit_plan                = exit_plan,
        active_paper_positions   = active_pos,
        news_to_decision_mapping = news_map,
        learning_layer           = learning,
    )


__all__ = [
    "PaperDecisionPayload",
    "build_latest_decision",
    "derive_decision_label",
    "DECISION_LABEL_NEW_RISK_BLOCK",
    "DECISION_LABEL_REDUCE",
    "DECISION_LABEL_KILL",
    "DECISION_LABEL_NO_INCREASE",
    "DECISION_LABEL_WATCH",
    "DECISION_LABEL_HOLD",
    "DECISION_LABEL_FLAT_NEUTRAL",
]
