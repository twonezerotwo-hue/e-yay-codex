"""
GET /api/v1/consensus       → tek varlık için multi-TF consensus + confluence
GET /api/v1/consensus/all   → 4 parite (BTC, XAU, XAG, BRENT) toplu

Mevcut RegimeReport + CapitalRotation + MultiTimeframeTechnical'tan
modül skorları üretir, her TF için consensus, sonra base TF + higher TF'lerde
confluence uygular.

PAPER_SAFE / NO_EXECUTION — final_decision=False.
"""
from __future__ import annotations

import time
from fastapi import APIRouter, Query

from app.api.regime_report import (
    _FakeSession,
    _ensure_repo_root_on_path,
    _get_provider,
)
from app.providers import (
    SourceRegistryBoundProviderAdapter,
    build_provider_source_bindings,
)
from app.providers.capital_rotation_provider import CapitalRotationProvider
from app.providers.multi_tf_technical_provider import (
    MultiTimeframeTechnicalProvider,
    MTF_ASSETS,
)
from app.providers.news_provider import NewsProvider
from app.providers.real_market_provider import RealMarketProvider
from app.providers.technical_provider import TechnicalProvider
from app.services.market_snapshot_service import MarketSnapshotService
from app.services.provider_ingestion_service import ProviderIngestionService
from app.services.regime_report_service import RegimeReportService
from app.services.consensus_engine import build_consensus_signal
from app.services.confluence_engine import apply_multi_tf_confluence
from app.services.eyay_consensus_adapter import (
    build_module_scores,
    get_regime_for_consensus,
)

router = APIRouter(prefix="/consensus", tags=["consensus"])

# Cache — anahtar = (asset)
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 90

TIMEFRAMES_ORDER = ("1h", "4h", "1d")


def _build_pipeline() -> tuple:
    """Tüm katmanları çek ve tek bir tuple (report, rotation, mtf) döndür."""
    _ensure_repo_root_on_path()
    from registry import build_source_registry_entries, load_source_registry

    source_registry = load_source_registry()
    entries = build_source_registry_entries(source_registry)
    base = _get_provider()

    delta_map: dict = {}
    if isinstance(base, RealMarketProvider):
        try:
            delta_map = base.delta_map_by_code
        except Exception:
            delta_map = {}

    provider = SourceRegistryBoundProviderAdapter(
        base, build_provider_source_bindings(entries),
    )
    result = ProviderIngestionService(
        MarketSnapshotService(_FakeSession()), provider
    ).run()
    snapshots = tuple(p.snapshot for p in result.persisted_snapshots)

    news = ()
    try:
        news = NewsProvider().fetch_headlines(max_total=30)
    except Exception:
        pass

    tech: dict = {}
    try:
        tech = TechnicalProvider().compute()
    except Exception:
        pass

    report = RegimeReportService().generate(
        snapshots, news_headlines=news, delta_map=delta_map, tech_insights=tech,
    )

    try:
        rotation = CapitalRotationProvider().compute()
    except Exception:
        rotation = None

    try:
        mtf = MultiTimeframeTechnicalProvider().compute()
    except Exception:
        mtf = {}

    return report, rotation, mtf, snapshots


def _build_full_signal(asset: str, report, rotation, mtf, trained_adjustments=None) -> dict:
    """Tek bir varlık için multi-TF consensus + confluence sinyal üret.

    trained_adjustments verilirse agent'ın öğrendiği ağırlıklar uygulanır.
    """
    raw_regime = get_regime_for_consensus(report)

    # ── Her TF için ayrı consensus skor (eğitilmiş ağırlıklarla) ─
    tf_signals: dict[str, dict] = {}
    for tf in TIMEFRAMES_ORDER:
        module_scores = build_module_scores(
            report, rotation=rotation, asset_code=asset,
            mtf_insights=mtf, timeframe=tf,
        )
        sig = build_consensus_signal(
            symbol=asset,
            timeframe=tf,
            module_scores=module_scores,
            raw_regime=raw_regime,
            trained_adjustments=trained_adjustments,
        )
        tf_signals[tf] = sig

    # ── Base TF rejimin primary_tf'si ─
    primary_tf = tf_signals[TIMEFRAMES_ORDER[0]].get("primary_tf", "1h")
    if primary_tf not in TIMEFRAMES_ORDER:
        primary_tf = "1h"

    base_sig = tf_signals.get(primary_tf, tf_signals[TIMEFRAMES_ORDER[0]])
    base_score = base_sig.get("consensus_score")

    # ── Diğer TF'ler — base hariç hepsi konfirme katkı yapar ─
    # (Aegis "higher TF" sınırlamasını esnetiyoruz: 1d base ise 1h+4h aşağıdan,
    #  1h base ise 4h+1d yukarıdan konfirme eder. Klasik konfirmasyon mantığı.)
    other_scores = {
        tf: tf_signals[tf]["consensus_score"]
        for tf in TIMEFRAMES_ORDER
        if tf != primary_tf and tf_signals.get(tf, {}).get("consensus_score") is not None
    }

    # ── Confluence uygula (base score'u diğer TF'lerle harmanla) ─
    confluence_result = None
    final_score = base_score
    final_direction = base_sig.get("direction")
    if base_score is not None and other_scores:
        confluence_result = apply_multi_tf_confluence(
            base_score=base_score,
            higher_tf_scores=other_scores,
        )
        final_score = confluence_result["adjusted_score"]
        from app.services.consensus_engine import get_direction
        from app.services.regime_weights_engine import get_consensus_config
        dcfg = get_consensus_config().get("direction_band", {})
        final_direction = get_direction(
            final_score,
            bull_thr=float(dcfg.get("bullish_threshold", 55.0)),
            bear_thr=float(dcfg.get("bearish_threshold", 45.0)),
        )

    return {
        "symbol":          asset,
        "raw_regime":      raw_regime,
        "primary_tf":      primary_tf,
        "base":            base_sig,
        "tf_signals":      tf_signals,
        "other_tf_scores": other_scores,
        "confluence":      confluence_result,
        "final_score":     final_score,
        "final_direction": final_direction,
        "decision_permission": "SIGNAL_ONLY_NOT_FINAL",
        "final_decision":  False,
    }


def _get_trained_adjustments() -> dict:
    """Paper trading state'ten agent'ın öğrendiği ağırlık adjustments'ını oku."""
    try:
        from app.services import paper_trading_service as pts
        return pts._load_state().weight_adjustments or {}
    except Exception:
        return {}


@router.get("")
def get_consensus(
    asset: str = Query(default="BTCUSD"),
) -> dict:
    now = time.monotonic()
    cached = _CACHE.get(asset)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    trained_adj = _get_trained_adjustments()
    report, rotation, mtf, raw_snapshots = _build_pipeline()
    signal = _build_full_signal(asset, report, rotation, mtf, trained_adjustments=trained_adj)

    response = {
        "status": "ok",
        "execution_mode": "SIGNAL_ONLY / NO_EXECUTION",
        "signal": signal,
        "trained_adjustments": trained_adj,
    }
    _CACHE[asset] = (now, response)
    return response


@router.get("/all")
def get_consensus_all() -> dict:
    """4 parite (BTCUSD, XAUUSD, XAGUSD, BRENT) için toplu consensus."""
    now = time.monotonic()
    cache_key = "__ALL__"
    cached = _CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    trained_adj = _get_trained_adjustments()
    report, rotation, mtf, raw_snapshots = _build_pipeline()
    signals = {
        asset: _build_full_signal(asset, report, rotation, mtf, trained_adjustments=trained_adj)
        for asset in MTF_ASSETS.keys()
    }

    response = {
        "status": "ok",
        "execution_mode": "SIGNAL_ONLY / NO_EXECUTION",
        "raw_regime": get_regime_for_consensus(report),
        "signals": signals,
    }
    _CACHE[cache_key] = (now, response)
    return response


__all__ = [name for name in globals() if not name.startswith("_")]
