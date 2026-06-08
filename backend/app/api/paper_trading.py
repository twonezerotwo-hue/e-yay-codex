"""
Paper Trading API — Sprint 1 sonrası temiz ayrım.

Endpoint semantiği:
  GET  /trading/state             → SADECE okur (state diskten + last_tick snapshot)
  POST /trading/tick               → pipeline + consensus tick + (gerekirse) eğitim
  POST /trading/close/{pair}       → manuel kapat (PAPER_SAFE guard)
  POST /trading/reset              → state sıfırla
  POST /trading/pending/{pair}/reject → bekleyen emri reddet
  POST /trading/train              → manuel auto_weight_trainer
  GET  /trading/training           → eğitim raporu (read-only)
  GET  /trading/learning           → öğrenme raporu (read-only)

Background scheduler (main.py) her ~30 sn'de bir POST /tick çağırır; GET artık
state mutasyonu YAPMAZ.

PAPER_SAFE / NO_EXECUTION — gerçek emir YOK.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.consensus import _build_full_signal, _build_pipeline
from app.core.execution_boundary import boundary_status, require_paper_safe
from app.providers.multi_tf_technical_provider import MTF_ASSETS
from app.services import paper_trading_service as pts

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/trading", tags=["trading"])

# State response cache (pure read) — 15s.
_STATE_CACHE: tuple[float, dict] | None = None
_STATE_CACHE_TTL = 15

# Tick response cache — son tick sonucu (POST /tick re-entry korumalı).
_TICK_CACHE: tuple[float, dict] | None = None
_TICK_CACHE_TTL = 25


def _invalidate_caches() -> None:
    global _STATE_CACHE, _TICK_CACHE
    _STATE_CACHE = None
    _TICK_CACHE = None


# ── Pipeline helpers ────────────────────────────────────────────────────────

def _consensus_signals_and_prices(report, rotation, mtf, trained_adjustments=None) -> tuple[dict, dict]:
    """4 parite için consensus sinyali + fiyat dict üret."""
    sigs: dict = {}
    prices: dict = {}

    for asset in MTF_ASSETS.keys():
        if asset not in pts.TRADED_PAIRS:
            continue
        full = _build_full_signal(asset, report, rotation, mtf,
                                   trained_adjustments=trained_adjustments)

        sigs[asset] = {
            "symbol":          asset,
            "final_score":     full.get("final_score"),
            "final_direction": full.get("final_direction"),
            "confluence":      full.get("confluence"),
            "raw_regime":      full.get("raw_regime"),
            "primary_tf":      full.get("primary_tf"),
            "base":            full.get("base"),
            "tf_signals":      full.get("tf_signals"),
            "other_tf_scores": full.get("other_tf_scores"),
        }

        base_tf = full.get("primary_tf", "1h")
        try:
            ti = (mtf.get(asset) or {}).get(base_tf)
            if ti is not None and getattr(ti, "current_price", 0) > 0:
                prices[asset] = float(ti.current_price)
            if ti is not None and hasattr(ti, "levels") and ti.levels is not None:
                atr_val = getattr(ti.levels, "atr", None)
                if atr_val and float(atr_val) > 0:
                    sigs[asset]["atr"] = float(atr_val)
        except Exception:
            pass

        if asset not in prices:
            for s in report.asset_signals:
                if s.asset_code == asset and s.value and s.value > 0:
                    prices[asset] = float(s.value)
                    break

    return sigs, prices


def _run_tick_pipeline() -> dict[str, Any]:
    """Heavy pipeline + consensus tick + training. State MUTATE eder.

    Sadece POST /trading/tick veya background scheduler tarafından çağrılır.
    """
    try:
        state = pts._load_state()
        trained_adjustments = state.weight_adjustments

        report, rotation, mtf, raw_snapshots = _build_pipeline()
        sigs, prices = _consensus_signals_and_prices(
            report, rotation, mtf, trained_adjustments=trained_adjustments,
        )

        # Veri kalitesi — tick'ten ÖNCE hesapla; aggregator DQS gate için kullanır.
        # NO_DATA (boş snapshot) → tick_dqs=None → gate pasif (veri yoksa engelleme).
        # Sadece gerçek veri varken score < MIN_DQS ise KILL_SWITCH tetiklenir.
        try:
            from app.services.data_quality_service import get_data_quality_summary
            asset_snapshots_early = {
                str(snap.asset_symbol): snap
                for snap in raw_snapshots
                if hasattr(snap, "fallback_used")
            }
            dq_early = get_data_quality_summary(asset_snapshots_early)
            _qs = dq_early.get("quality_score")
            _has_data = dq_early.get("total", 0) > 0
            # Snapshot boş (NO_DATA) → kalite bilinmiyor → KILL_SWITCH (yeni trade yok)
            # NOT: unit testler tick_consensus'u doğrudan çağırır (dqs_score=None), etkilenmez.
            if not _has_data:
                tick_dqs: int | None = 0        # boş snapshot → block
            elif _qs is not None and _qs > 0:
                tick_dqs = int(_qs)             # gerçek skor
            else:
                tick_dqs = None                 # skor hesaplanamadı → gate pasif
        except Exception:
            dq_early = {"quality_score": None, "decision": "UNKNOWN"}
            tick_dqs = None

        # Consensus tick — aggregator (multi-TF + rejim + DQS) ile güçlendirilmiş
        pts.tick_consensus(sigs, prices, dqs_score=tick_dqs)

        # Auto-weight training (her 5 yeni kapanışta)
        from app.services.auto_weight_trainer import maybe_retrain
        with pts._LOCK:
            state = pts._load_state()
            training_result = maybe_retrain(state)
            if training_result["status"] == "trained":
                pts._save_state(state)

        # Veri kalitesi — tick öncesi hesaplandı; sonucu yeniden kullan
        data_quality = dq_early if tick_dqs is not None else {"quality_score": None, "decision": "UNKNOWN"}

        return {
            "status": "ok",
            "tick_at": state.last_tick_at if hasattr(state, "last_tick_at") else None,
            "signals_count": len(sigs),
            "prices_count":  len(prices),
            "training":      training_result,
            "data_quality":  data_quality,
        }
    except Exception as exc:
        _log.exception("tick pipeline failed")
        return {
            "status": "error",
            "error":  str(exc)[:200],
        }


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/state")
def get_state() -> dict:
    """SADECE OKUR. State'i diskten yükler, son tick fiyatlarını kullanır.

    Pipeline çalıştırmaz, tick yapmaz, training tetiklemez.
    Background scheduler tick'i tutarken bu endpoint stale değildir.
    """
    global _STATE_CACHE
    now = time.monotonic()
    if _STATE_CACHE and (now - _STATE_CACHE[0]) < _STATE_CACHE_TTL:
        return _STATE_CACHE[1]

    try:
        # last_tick_prices'ı kullan — get_snapshot None geçince state'ten çeker
        state = pts._load_state()
        snap = pts.get_snapshot()  # prices=None → state.last_tick_prices fallback
        snap["status"]         = "ok"
        snap["execution_mode"] = "PAPER_SAFE / NO_EXECUTION"
        snap["read_only"]      = True
        snap["driver"]         = "consensus_multi_tf_self_learning"
        snap["boundary"]       = boundary_status()
        snap["last_signals"]   = state.last_tick_signals
        snap["training"] = {
            "trained_at_count":   state.last_trained_at_trade_count,
            "training_runs":      len(state.training_history),
            "active_adjustments": state.weight_adjustments,
        }
    except Exception as exc:
        _log.exception("state read failed")
        snap = pts.get_snapshot()
        snap["status"] = "stale"
        snap["error"]  = str(exc)[:200]

    _STATE_CACHE = (now, snap)
    return snap


@router.post("/tick", dependencies=[Depends(require_paper_safe)])
def run_tick() -> dict:
    """Pipeline + consensus tick'i ŞIMDI çalıştır. State MUTATE eder."""
    global _TICK_CACHE
    now = time.monotonic()
    if _TICK_CACHE and (now - _TICK_CACHE[0]) < _TICK_CACHE_TTL:
        cached = dict(_TICK_CACHE[1])
        cached["from_cache"] = True
        return cached

    result = _run_tick_pipeline()
    result["boundary"] = boundary_status()
    _TICK_CACHE = (now, result)
    _STATE_CACHE = None  # state'i bayatlatma
    globals()["_STATE_CACHE"] = None
    return result


@router.post("/close/{pair}", dependencies=[Depends(require_paper_safe)])
def manual_close(pair: str) -> dict:
    """Manuel kapat — kullanıcı talebiyle anlık fiyattan pozisyonu kapat."""
    pair_upper = pair.upper()
    if pair_upper not in pts.TRADED_PAIRS:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen parite: {pair_upper}")

    # Önce state'in son bilinen fiyatına bak (read-only, pipeline yok)
    state = pts._load_state()
    price = float(state.last_tick_prices.get(pair_upper, 0.0))

    # Yoksa pozisyondaki entry_price/current'tan düş
    if price <= 0:
        snap = pts.get_snapshot()
        for pos in snap.get("open_positions", []):
            if pos.get("pair") == pair_upper:
                price = float(pos.get("current_price") or pos.get("entry_price") or 0.0)
                break

    result = pts.force_close_position(pair_upper, price, reason="MANUEL")
    _invalidate_caches()
    return result


@router.post("/reset", dependencies=[Depends(require_paper_safe)])
def reset() -> dict:
    pts.reset_state()
    _invalidate_caches()
    return {"status": "reset"}


@router.post("/reset-trades", dependencies=[Depends(require_paper_safe)])
def reset_trades() -> dict:
    """İşlem geçmişini, pozisyonları ve sinyalleri sıfırla.

    Öğrenilmiş ağırlıklar (weight_adjustments, training_history) KORUNUR.
    trades, positions, pending_orders, realized_pnl, tick snapshot sıfırlanır.
    """
    pts.reset_trades_only()
    _invalidate_caches()
    return {"status": "trades_reset", "message": "İşlem geçmişi temizlendi, öğrenmeler korundu"}


@router.post("/pending/{pair}/reject", dependencies=[Depends(require_paper_safe)])
def reject_pending_trade(pair: str) -> dict:
    """Bekleyen pending'i reddet → 'Açılmaya Hazır İşlemler' listesine taşı.

    Aynı (side, fingerprint, primary_tf) sinyali bir daha sorulmaz. Farklı
    TF/yönden gelen yeni sinyal 'yinelenen' olarak yeni 60sn pending açar.
    """
    rejected = pts.reject_pending_open(pair.upper())
    _invalidate_caches()
    return {
        "status": "rejected" if rejected else "not_found",
        "pair":   pair.upper(),
        "moved_to": "manual_ready_trades" if rejected else None,
    }


@router.post("/manual-ready/{pair}/open", dependencies=[Depends(require_paper_safe)])
def open_manual_ready(pair: str) -> dict:
    """Açılmaya hazır işlemi kullanıcı talebiyle anlık fiyattan aç."""
    pair_upper = pair.upper()
    if pair_upper not in pts.TRADED_PAIRS:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen parite: {pair_upper}")
    # Anlık fiyat — state'in last_tick_prices'ından gelsin
    state = pts._load_state()
    price = float(state.last_tick_prices.get(pair_upper, 0.0))
    result = pts.force_open_manual_ready(pair_upper, current_price=price if price > 0 else None)
    _invalidate_caches()
    return result


@router.post("/manual-ready/{pair}/dismiss", dependencies=[Depends(require_paper_safe)])
def dismiss_manual_ready_route(pair: str) -> dict:
    """Açılmaya hazır işlemi listeden çıkar (silent block hâlâ devam eder)."""
    dismissed = pts.dismiss_manual_ready(pair.upper())
    _invalidate_caches()
    return {
        "status": "dismissed" if dismissed else "not_found",
        "pair":   pair.upper(),
    }


@router.post("/train", dependencies=[Depends(require_paper_safe)])
def force_retrain() -> dict:
    """Manuel olarak otomatik eğitim tetikle (debug için)."""
    from app.services.auto_weight_trainer import maybe_retrain
    with pts._LOCK:
        state = pts._load_state()
        result = maybe_retrain(state, force=True)
        if result["status"] == "trained":
            pts._save_state(state)
    _invalidate_caches()
    return result


@router.get("/training")
def get_training_status() -> dict:
    """Mevcut eğitim durumu — READ-ONLY."""
    state = pts._load_state()
    return {
        "status": "ok",
        "last_trained_at_trade_count": state.last_trained_at_trade_count,
        "active_adjustments":          state.weight_adjustments,
        "training_history":            state.training_history[-10:],
        "thresholds": {
            "min_total_trades":        10,
            "min_regime_trades":       5,
            "training_interval":       5,
            "max_adjustment_per_run":  0.03,
            "max_total_adjustment":    0.10,
            "min_module_weight":       0.02,
        },
    }


@router.get("/learning")
def get_learning_report() -> dict:
    """Öğrenme motoru raporu — READ-ONLY."""
    from app.services.learning_engine import build_learning_report
    state = pts._load_state()
    report = build_learning_report(state.trades)
    return {
        "status":      "ok",
        "trade_count": len(state.trades),
        "report":      report,
    }


@router.get("/boundary")
def get_boundary() -> dict:
    """Execution boundary durumu — READ-ONLY."""
    return {"status": "ok", **boundary_status()}


__all__ = [name for name in globals() if not name.startswith("_")]
