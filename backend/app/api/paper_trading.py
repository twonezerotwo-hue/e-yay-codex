"""
GET  /api/v1/trading/state  → Bakiye + açık pozisyonlar + son trade + son event
POST /api/v1/trading/reset  → Tüm state'i sıfırla (debug)

Her GET çağrısında:
  1. Mevcut regime report pipeline'ını çalıştırır (kendi cache'i 3 dk)
  2. asset_signals'tan LONG/SHORT/AVOID kararları alır
  3. paper_trading.tick() ile pozisyon aç/kapat
  4. Snapshot döndürür

PAPER_SAFE / NO_EXECUTION — simülasyon, gerçek emir YOK.
"""
from __future__ import annotations

import time
from fastapi import APIRouter

from app.api.consensus import _build_full_signal, _build_pipeline
from app.providers.multi_tf_technical_provider import MTF_ASSETS
from app.services import paper_trading_service as pts

router = APIRouter(prefix="/trading", tags=["trading"])

# 30 sn'lik mini cache — frontend her sayfa yenilemede çağırsa bile pipeline tekrar koşmasın
_RESPONSE_CACHE: tuple[float, dict] | None = None
_CACHE_TTL = 30


def _invalidate_response_cache() -> None:
    global _RESPONSE_CACHE
    _RESPONSE_CACHE = None


def _consensus_signals_and_prices(report, rotation, mtf, trained_adjustments=None) -> tuple[dict, dict]:
    """4 parite için consensus sinyali + fiyat dict üret.

    trained_adjustments verilirse agent'ın eğitilmiş ağırlıkları kullanılır.
    """
    sigs: dict = {}
    prices: dict = {}

    for asset in MTF_ASSETS.keys():
        if asset not in pts.TRADED_PAIRS:
            continue
        full = _build_full_signal(asset, report, rotation, mtf,
                                   trained_adjustments=trained_adjustments)

        # Full snapshot — fingerprint + learning için tüm bilgi
        sigs[asset] = {
            "symbol":          asset,
            "final_score":     full.get("final_score"),
            "final_direction": full.get("final_direction"),
            "confluence":      full.get("confluence"),
            "raw_regime":      full.get("raw_regime"),
            "primary_tf":      full.get("primary_tf"),
            "base":            full.get("base"),          # consensus contributions burada
            "tf_signals":      full.get("tf_signals"),    # her TF'in skoru
            "other_tf_scores": full.get("other_tf_scores"),
        }

        # Fiyat + ATR — base TF technical provider'dan
        base_tf = full.get("primary_tf", "1h")
        try:
            ti = (mtf.get(asset) or {}).get(base_tf)
            if ti is not None and getattr(ti, "current_price", 0) > 0:
                prices[asset] = float(ti.current_price)
            # ATR — SL/TP otomatik hesabı için
            if ti is not None and hasattr(ti, "levels") and ti.levels is not None:
                atr_val = getattr(ti.levels, "atr", None)
                if atr_val and float(atr_val) > 0:
                    sigs[asset]["atr"] = float(atr_val)
        except Exception:
            pass

        # Yedek: report asset_signals'tan fiyat çek
        if asset not in prices:
            for s in report.asset_signals:
                if s.asset_code == asset and s.value and s.value > 0:
                    prices[asset] = float(s.value)
                    break

    return sigs, prices


@router.get("/state")
def get_state() -> dict:
    global _RESPONSE_CACHE
    now = time.monotonic()
    if _RESPONSE_CACHE and (now - _RESPONSE_CACHE[0]) < _CACHE_TTL:
        return _RESPONSE_CACHE[1]

    try:
        # ── 1) Mevcut state'ten EĞİTİLMİŞ ağırlıkları oku ─
        state = pts._load_state()
        trained_adjustments = state.weight_adjustments

        # ── 2) Multi-TF consensus pipeline'ı (eğitilmiş ağırlıklarla) ─
        report, rotation, mtf, raw_snapshots = _build_pipeline()
        sigs, prices = _consensus_signals_and_prices(
            report, rotation, mtf, trained_adjustments=trained_adjustments,
        )

        # ── 3) Tick: pozisyon aç/kapat ─
        pts.tick_consensus(sigs, prices)

        # ── 4) Otomatik eğitim — her 5 yeni kapanışta tetiklenir ─
        from app.services.auto_weight_trainer import maybe_retrain
        with pts._LOCK:
            state = pts._load_state()
            training_result = maybe_retrain(state)
            if training_result["status"] == "trained":
                pts._save_state(state)

        # ── 5) Veri kalite özeti — raw_snapshots üzerinden fallback uyarısı ─
        from app.services.data_quality_service import get_data_quality_summary
        try:
            asset_snapshots = {
                str(snap.asset_symbol): snap
                for snap in raw_snapshots
                if hasattr(snap, "fallback_used")
            }
            data_quality = get_data_quality_summary(asset_snapshots)
        except Exception:
            data_quality = {"quality_score": None, "decision": "UNKNOWN"}

        snap = pts.get_snapshot(prices)
        snap["status"] = "ok"
        snap["execution_mode"] = "PAPER_SAFE / NO_EXECUTION"
        snap["driver"] = "consensus_multi_tf_self_learning"
        snap["last_signals"] = sigs
        snap["data_quality"] = data_quality
        snap["training"] = {
            "last_result":       training_result.get("status"),
            "trained_at_count":  state.last_trained_at_trade_count,
            "training_runs":     len(state.training_history),
            "active_adjustments": state.weight_adjustments,
        }
    except Exception as exc:
        snap = pts.get_snapshot({})
        snap["status"] = "stale"
        snap["error"] = str(exc)[:200]

    _RESPONSE_CACHE = (now, snap)
    return snap


@router.post("/close/{pair}")
def manual_close(pair: str) -> dict:
    """Manuel kapat — kullanıcı talebiyle anlık fiyattan pozisyonu kapat. PAPER_SAFE."""
    global _RESPONSE_CACHE
    from fastapi import HTTPException
    pair_upper = pair.upper()
    if pair_upper not in pts.TRADED_PAIRS:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen parite: {pair_upper}")

    # Güncel fiyatı pipeline'dan al
    price = 0.0
    try:
        report, rotation, mtf, raw_snapshots = _build_pipeline()
        _, prices = _consensus_signals_and_prices(report, rotation, mtf)
        price = prices.get(pair_upper, 0.0)
    except Exception:
        pass

    # Pipeline başarısız olduysa snapshot'taki son bilinen fiyatı kullan
    if price <= 0:
        snap = pts.get_snapshot({})
        for pos in snap.get("open_positions", []):
            if pos.get("pair") == pair_upper:
                price = float(pos.get("current_price") or pos.get("entry_price") or 0.0)
                break

    result = pts.force_close_position(pair_upper, price, reason="MANUEL")
    _RESPONSE_CACHE = None  # cache'i temizle — bir sonraki GET güncel durumu döndürsün
    return result


@router.post("/reset")
def reset() -> dict:
    pts.reset_state()
    _invalidate_response_cache()
    return {"status": "reset"}


@router.post("/pending/{pair}/reject")
def reject_pending_trade(pair: str) -> dict:
    rejected = pts.reject_pending_open(pair.upper())
    _invalidate_response_cache()
    return {
        "status": "rejected" if rejected else "not_found",
        "pair": pair.upper(),
    }


@router.post("/train")
def force_retrain() -> dict:
    """Manuel olarak otomatik eğitim tetikle (debug için)."""
    from app.services.auto_weight_trainer import maybe_retrain
    with pts._LOCK:
        state = pts._load_state()
        result = maybe_retrain(state, force=True)
        if result["status"] == "trained":
            pts._save_state(state)
    return result


@router.get("/training")
def get_training_status() -> dict:
    """Mevcut eğitim durumu — ağırlık adjustments + son eğitim event'leri."""
    state = pts._load_state()
    return {
        "status": "ok",
        "last_trained_at_trade_count": state.last_trained_at_trade_count,
        "active_adjustments": state.weight_adjustments,
        "training_history": state.training_history[-10:],  # son 10 event
        "thresholds": {
            "min_total_trades":   10,
            "min_regime_trades":  5,
            "training_interval":  5,
            "max_adjustment_per_run":  0.03,
            "max_total_adjustment":    0.10,
            "min_module_weight":       0.02,
        },
    }


@router.get("/learning")
def get_learning_report() -> dict:
    """
    Öğrenme motoru raporu:
      • Her fingerprint'in win rate'i
      • AVOID listesi (öğrenilmiş hatalar)
      • BOOST listesi (güçlü sinyaller)
      • Modül performansları (kazandıran vs kaybettiren skew)
      • Ağırlık revizyon önerileri
    """
    from app.services.learning_engine import build_learning_report
    snap = pts.get_snapshot({})
    state = pts._load_state()
    report = build_learning_report(state.trades)
    return {
        "status": "ok",
        "trade_count": len(state.trades),
        "report": report,
    }


__all__ = [name for name in globals() if not name.startswith("_")]
