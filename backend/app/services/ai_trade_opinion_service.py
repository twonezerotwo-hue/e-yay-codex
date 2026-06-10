"""
AI Trade Opinion Layer — agent'ın net trade fikri.

Amaç: agent "2 pozisyon var" gibi status cümlesi yerine sistemin tüm stored
verisini okuyup açık görüş üretir: LONG_BIAS / SHORT_BIAS / WAIT / HOLD /
REDUCE / CLOSE_WATCH / AVOID / MANUAL_REVIEW.

Sınırlar:
  • Broker emri YOK; pozisyon otomatik açılmaz/kapanmaz.
  • Paper state mutate edilmez — tüm kaynaklar READ-ONLY.
  • Karar deterministik kurallarla üretilir (LLM yok).
  • execution_mode=PAPER_SAFE, live_execution_allowed=False her zaman.

Output schema: ai_trade_opinion_v1
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

_log = logging.getLogger(__name__)

SCHEMA_VERSION = "ai_trade_opinion_v1"

TRACKED_ASSETS = ("BTCUSD", "XCUUSD", "XAUUSD", "XAGUSD", "BRENT")

# Asset opinion etiketleri
_ASSET_OPINIONS = ("WAIT", "LONG_BIAS", "SHORT_BIAS", "HOLD", "REDUCE", "AVOID",
                   "MANUAL_REVIEW", "WAIT_EVENT_CONFIRMATION")
# Açık pozisyon etiketleri
_POSITION_OPINIONS = ("HOLD", "REDUCE", "CLOSE_WATCH", "ADD_ONLY_IF", "MANUAL_REVIEW")


# ── Context toplama (read-only; her kaynak kendi try/except'iyle) ─────────────

def collect_opinion_context() -> dict[str, Any]:
    """Stored data'yı okur. Hiçbir kaynak yazılmaz; eksik kaynak None/boş olur."""
    ctx: dict[str, Any] = {
        "now": datetime.now(UTC).isoformat(),
        "snapshot": None, "prev_snapshot": None,
        "thesis": None, "thesis_sanity": None,
        "paper_state": None,
        "rechecks": [], "learning_candidates": [], "mistake_memory": [],
        "weekly_calibration": None, "auto_tune_overrides": {},
        "system_health": None,
    }
    try:
        from app.storage.hourly_snapshot_store import (  # noqa: PLC0415
            load_recent_hourly_snapshots,
        )
        snaps = load_recent_hourly_snapshots(limit=2)
        if snaps:
            ctx["snapshot"] = snaps[-1]
            if len(snaps) > 1:
                ctx["prev_snapshot"] = snaps[-2]
    except Exception as exc:  # noqa: BLE001
        _log.debug("opinion ctx: snapshots unavailable: %s", exc)

    try:
        from app.storage.agent_thesis_store import (  # noqa: PLC0415
            load_recent_agent_theses,
        )
        theses = load_recent_agent_theses(limit=1)
        if theses:
            ctx["thesis"] = theses[-1]
    except Exception:  # noqa: BLE001
        pass

    if ctx["thesis"]:
        try:
            from app.services.agent_thesis_sanity import (  # noqa: PLC0415
                validate_agent_thesis,
            )
            ctx["thesis_sanity"] = validate_agent_thesis(ctx["thesis"])
        except Exception:  # noqa: BLE001
            pass

    try:
        from app.services import paper_trading_service as pts  # noqa: PLC0415
        ctx["paper_state"] = pts.get_snapshot()
    except Exception:  # noqa: BLE001
        pass

    for key, loader_path, fn, kw in (
        ("rechecks", "app.storage.position_recheck_store",
         "load_recent_position_rechecks", {"limit": 10}),
        ("learning_candidates", "app.storage.learning_candidate_store",
         "load_recent_learning_candidates", {"limit": 20}),
        ("mistake_memory", "app.storage.mistake_memory_store",
         "load_recent_mistake_memory", {"limit": 30}),
    ):
        try:
            import importlib  # noqa: PLC0415
            mod = importlib.import_module(loader_path)
            ctx[key] = getattr(mod, fn)(**kw) or []
        except Exception:  # noqa: BLE001
            pass

    try:
        from app.storage.weekly_calibration_store import (  # noqa: PLC0415
            load_recent_weekly_calibrations,
        )
        cals = load_recent_weekly_calibrations(limit=1)
        if cals:
            ctx["weekly_calibration"] = cals[-1]
    except Exception:  # noqa: BLE001
        pass

    try:
        from app.services.auto_tune_override_reader import (  # noqa: PLC0415
            load_auto_tune_overrides,
        )
        ctx["auto_tune_overrides"] = load_auto_tune_overrides() or {}
    except Exception:  # noqa: BLE001
        pass

    return ctx


# ── Yardımcılar ───────────────────────────────────────────────────────────────

def _report(ctx: dict) -> dict:
    snap = ctx.get("snapshot") or {}
    return snap.get("report") or {}


def _mtf_for(ctx: dict, asset: str) -> dict:
    snap = ctx.get("snapshot") or {}
    return (snap.get("mtf") or {}).get(asset) or {}


def _signal_for(ctx: dict, asset: str) -> dict:
    for s in _report(ctx).get("asset_signals") or []:
        if isinstance(s, dict) and s.get("asset_code") == asset:
            return s
    return {}


def _structures(mtf: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for tf in ("1h", "4h", "1d"):
        d = mtf.get(tf) or {}
        out[tf] = str(d.get("structure") or "").upper()
    return out


def _memory_penalty(ctx: dict, asset: str) -> int:
    """Mistake memory'de bu pair için kayıt varsa conviction cezası (0-2)."""
    hits = 0
    for m in ctx.get("mistake_memory") or []:
        pair = str(m.get("pair") or m.get("asset") or "")
        if pair == asset:
            hits += 1
    return min(2, hits)


def _conviction_label(score: float, penalty: int) -> str:
    eff = score - penalty * 8
    if eff >= 72:
        return "high"
    if eff >= 58:
        return "medium"
    return "low"


def _news_pressure(ctx: dict) -> bool:
    """Savaş/jeopolitik başlık var mı (event teyit gereksinimi)?"""
    hot = ("war", "strike", "attack", "missile", "iran", "israel", "hormuz")
    for n in _report(ctx).get("news_headlines") or []:
        title = str((n or {}).get("title") or "").lower()
        if any(k in title for k in hot):
            return True
    return False


# ── Asset skoru (0-100, deterministik) ────────────────────────────────────────

def _asset_score(ctx: dict, asset: str) -> tuple[float, list[str], list[str]]:
    """Skor + neden (why) + karşı argüman (against) listeleri."""
    why: list[str] = []
    against: list[str] = []
    score = 50.0

    sig = _signal_for(ctx, asset)
    status = str(sig.get("status") or "").upper()
    if status == "CONFIRMED":
        score += 15
        why.append("Sinyal teyitli (CONFIRMED)")
    elif status == "BLOCKING":
        score -= 18
        against.append("Sinyal BLOCKING durumda")
    elif status == "PENDING":
        against.append("Sinyal henüz teyit edilmedi (PENDING)")

    st = _structures(_mtf_for(ctx, asset))
    for tf, w in (("1h", 5), ("4h", 8), ("1d", 9)):
        if st.get(tf) == "BULLISH":
            score += w
            why.append(f"{tf.upper()} yapı BULLISH")
        elif st.get(tf) == "BEARISH":
            score -= w
            against.append(f"{tf.upper()} yapı BEARISH")

    macro = _report(ctx).get("macro_layer") or {}
    regime = str(macro.get("regime") or "").upper()
    if regime in ("CRISIS", "DEFENSIVE"):
        score -= 6
        against.append(f"Makro rejim {regime} — risk iştahı baskılı")
    elif regime == "RISK_ON":
        score += 4
        why.append("Makro rejim RISK_ON")

    appetite = _report(ctx).get("appetite_layer") or {}
    if str(appetite.get("status") or "").upper() == "WEAK":
        score -= 4
        against.append("Risk iştahı zayıf")

    return max(0.0, min(100.0, score)), why[:4], against[:4]


# ── Asset opinion ─────────────────────────────────────────────────────────────

def _build_asset_opinion(ctx: dict, asset: str, open_pairs: set[str]) -> dict[str, Any]:
    score, why, against = _asset_score(ctx, asset)
    penalty = _memory_penalty(ctx, asset)
    if penalty:
        against.append(f"Mistake memory: {penalty} geçmiş hata kaydı — conviction düşürüldü")

    st  = _structures(_mtf_for(ctx, asset))
    sig = _signal_for(ctx, asset)
    mtf1h = _mtf_for(ctx, asset).get("1h") or {}
    levels = mtf1h.get("levels") or {}
    sup, res = levels.get("support"), levels.get("resistance")

    news_hot = _news_pressure(ctx)
    held = asset in open_pairs

    # Opinion mapping (spec kuralları)
    if held:
        opinion = "HOLD"
    elif score >= 70:
        opinion = "LONG_BIAS" if st.get("1d") != "BEARISH" else "MANUAL_REVIEW"
    elif score >= 55:
        opinion = ("WAIT_EVENT_CONFIRMATION"
                   if news_hot and str(sig.get("status", "")).upper() != "CONFIRMED"
                   else "WAIT")
    elif score >= 50:
        opinion = "MANUAL_REVIEW"
    else:
        opinion = "AVOID"

    trigger = str(sig.get("action_trigger") or "") or (
        f"1H kapanış {res:,.0f} üstü" if isinstance(res, (int, float)) else
        "1H/4H yapı teyidi bekleniyor"
    )
    invalidation = (
        f"1H kapanış {sup:,.0f} altı yapıyı bozar" if isinstance(sup, (int, float))
        else "4H yapı BEARISH'e dönerse fikir geçersiz"
    )

    suggested = {
        "LONG_BIAS":               "manuel long adayı — teyitle birlikte değerlendir",
        "SHORT_BIAS":              "manuel short adayı — teyitle birlikte değerlendir",
        "WAIT":                    "Bekle — teyit gelmeden pozisyon yok",
        "WAIT_EVENT_CONFIRMATION": "Bekle — haber güçlü ama fiyat teyidi yok",
        "HOLD":                    "pozisyonu koru",
        "AVOID":                   "uzak dur — skor zayıf",
        "MANUAL_REVIEW":           "manuel incele — sinyaller karışık",
        "REDUCE":                  "küçültmeyi izle",
    }.get(opinion, "Bekle")

    return {
        "asset":            asset,
        "opinion":          opinion,
        "conviction":       _conviction_label(score, penalty),
        "score":            round(score, 1),
        "why":              why or ["Belirgin destekleyici sinyal yok"],
        "against":          against or ["Belirgin karşı sinyal yok"],
        "trigger_needed":   trigger,
        "invalidation":     invalidation,
        "suggested_action": suggested,
    }


# ── Açık pozisyon opinion ─────────────────────────────────────────────────────

def _position_pnl_pct(pos: dict, mtf: dict) -> float | None:
    pnl = pos.get("pnl_pct")
    if isinstance(pnl, (int, float)):
        return float(pnl)
    entry = pos.get("entry_price")
    cur   = (mtf.get("1h") or {}).get("current_price")
    if not (isinstance(entry, (int, float)) and isinstance(cur, (int, float)) and entry):
        return None
    raw = (cur - entry) / entry * 100.0
    return raw if str(pos.get("side", "")).upper() == "LONG" else -raw


def _build_position_opinion(ctx: dict, pos: dict) -> dict[str, Any]:
    pair = str(pos.get("pair") or "?")
    side = str(pos.get("side") or "?").upper()
    mtf  = _mtf_for(ctx, pair)
    st   = _structures(mtf)
    pnl  = _position_pnl_pct(pos, mtf)
    news_hot = _news_pressure(ctx)
    penalty  = _memory_penalty(ctx, pair)

    losing = pnl is not None and pnl < 0
    # LONG için bozulma = BEARISH; SHORT için tersi
    bad = "BEARISH" if side == "LONG" else "BULLISH"
    short_tf_broken = st.get("1h") == bad and st.get("4h") == bad
    big_tf_support  = st.get("4h") != bad or st.get("1d") != bad

    watch: list[str] = []
    if losing and short_tf_broken:
        opinion, conviction = "CLOSE_WATCH", "medium"
        reason = (f"{pair} {side} zararda ve 1H+4H yapı bozulmuş — "
                  f"kapatma izlemesi gerekli")
    elif losing and big_tf_support:
        opinion, conviction = "HOLD", "medium" if not penalty else "low"
        reason = (f"{pair} {side} zararda ama 4H/1D yapı hâlâ destekliyor — "
                  f"korunabilir, agresif büyütme yok")
    elif not losing and st.get("1h") == bad:
        opinion, conviction = "REDUCE", "medium"
        reason = (f"{pair} {side} kârda ama 1H yapı tersine döndü — "
                  f"kâr koruma için küçültme mantıklı")
    elif pnl is None:
        opinion, conviction = "MANUAL_REVIEW", "low"
        reason = f"{pair} {side} PnL hesaplanamadı — manuel kontrol gerekli"
    else:
        opinion, conviction = "HOLD", "high" if not penalty else "medium"
        reason = f"{pair} {side} kârda ve yapı destekliyor — pozisyon korunabilir"

    if news_hot and pair == "BRENT" and losing:
        conviction = "low"
        reason += "; savaş haberine rağmen fiyat geri çekiliyor — conviction düşük"

    sl = pos.get("stop_loss")
    if isinstance(sl, (int, float)):
        watch.append(f"Stop seviyesi {sl:,.2f} — altı kapanış pozisyonu bitirir")
    watch.append(f"4H yapı ({st.get('4h') or '?'}) — {bad} dönüşü fikri bozar")

    sup = ((mtf.get("4h") or {}).get("levels") or {}).get("support")
    invalidation = (
        f"4H kapanış {sup:,.2f} altı pozisyon tezini geçersiz kılar"
        if isinstance(sup, (int, float))
        else f"1H+4H {bad} kalıcı hale gelirse tez geçersiz"
    )

    return {
        "pair":          pair,
        "side":          side,
        "opinion":       opinion,
        "conviction":    conviction,
        "reason":        reason,
        "what_to_watch": watch[:3],
        "invalidation":  invalidation,
    }


# ── Üst seviye görüş ──────────────────────────────────────────────────────────

def _overall_view(ctx: dict) -> str:
    report = _report(ctx)
    regime = str((report.get("macro_layer") or {}).get("regime") or "").upper()
    appetite = str((report.get("appetite_layer") or {}).get("status") or "").upper()
    # Bugün kritik event var mı?
    for c in report.get("upcoming_catalysts") or []:
        sev = str((c or {}).get("severity") or "").upper()
        when = str((c or {}).get("when") or (c or {}).get("date") or "").lower()
        if sev in ("KRITIK", "CRITICAL", "HIGH") and ("bugün" in when or "today" in when):
            return "event_locked"
    if regime == "CRISIS":
        return "risk_off"
    if regime == "DEFENSIVE":
        return "defensive"
    if regime == "RISK_ON" and appetite in ("STRONG", "NEUTRAL"):
        return "risk_on"
    return "mixed"


def _market_opinion(ctx: dict, asset_ops: list[dict], pos_ops: list[dict],
                    best: dict) -> str:
    """Net, status-cümlesi olmayan piyasa görüşü."""
    parts: list[str] = []
    regime = str((_report(ctx).get("macro_layer") or {}).get("regime") or "?").upper()

    for po in pos_ops[:2]:
        if po["opinion"] == "HOLD":
            parts.append(f"{po['pair']} {po['side']} korunabilir")
        elif po["opinion"] in ("REDUCE", "CLOSE_WATCH"):
            parts.append(f"{po['pair']} {po['side']} için {po['opinion']} — "
                         f"{po['invalidation']}")
        else:
            parts.append(f"{po['pair']} {po['side']}: {po['opinion'].lower()}")

    if best.get("asset") and best["asset"] != "NONE":
        parts.append(f"yeni trade için en iyi aday {best['asset']} "
                     f"({best['bias']}) — {best['trigger']}")
    else:
        waiting = [a["asset"] for a in asset_ops
                   if a["opinion"] in ("WAIT", "WAIT_EVENT_CONFIRMATION")][:2]
        if waiting:
            parts.append(f"{'/'.join(waiting)} teyit gelmeden WAIT")
        else:
            parts.append("uygun yeni setup yok")

    return f"Rejim {regime}: " + "; ".join(parts) + "."


def _best_candidate(asset_ops: list[dict], open_pairs: set[str]) -> tuple[dict, str]:
    candidates = [
        a for a in asset_ops
        if a["asset"] not in open_pairs
        and a["opinion"] in ("LONG_BIAS", "SHORT_BIAS")
        and a["score"] >= 60
    ]
    if not candidates:
        waits = [a for a in asset_ops if a["asset"] not in open_pairs]
        waits.sort(key=lambda a: -a["score"])
        reason = (
            "Hiçbir asset LONG_BIAS/SHORT_BIAS eşiğini (skor≥60 + bias) geçemedi"
            + (f"; en yakın aday {waits[0]['asset']} (skor {waits[0]['score']}) "
               f"— {waits[0]['trigger_needed']}" if waits else "")
        )
        return {
            "asset": "NONE", "bias": "wait",
            "reason": reason,
            "trigger": waits[0]["trigger_needed"] if waits else "",
            "risk": "",
        }, reason

    best = max(candidates, key=lambda a: a["score"])
    return {
        "asset":   best["asset"],
        "bias":    "long" if best["opinion"] == "LONG_BIAS" else "short",
        "reason":  "; ".join(best["why"][:2]) or f"skor {best['score']}",
        "trigger": best["trigger_needed"],
        "risk":    best["invalidation"],
    }, ""


# ── Ana giriş noktası ─────────────────────────────────────────────────────────

def build_ai_trade_opinion(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Tüm stored data'dan deterministik trade opinion üretir.

    READ-ONLY: hiçbir state mutate edilmez, emir gönderilmez.
    `ctx` test için enjekte edilebilir; None ise collect_opinion_context() çağrılır.
    """
    if ctx is None:
        ctx = collect_opinion_context()

    pt = ctx.get("paper_state") or {}
    positions = [p for p in (pt.get("open_positions") or []) if isinstance(p, dict)]
    open_pairs = {str(p.get("pair") or "") for p in positions}

    asset_ops = [_build_asset_opinion(ctx, a, open_pairs) for a in TRACKED_ASSETS]
    pos_ops   = [_build_position_opinion(ctx, p) for p in positions]

    best, no_trade_reason = _best_candidate(asset_ops, open_pairs)
    market_opinion = _market_opinion(ctx, asset_ops, pos_ops, best)

    next_triggers = [a["trigger_needed"] for a in asset_ops
                     if a["opinion"] in ("WAIT", "WAIT_EVENT_CONFIRMATION",
                                         "LONG_BIAS", "SHORT_BIAS")][:3]
    change_mind = [a["invalidation"] for a in asset_ops
                   if a["opinion"] not in ("AVOID",)][:3]
    change_mind += [po["invalidation"] for po in pos_ops[:2]]

    if pos_ops:
        ob_pos = "; ".join(f"{po['pair']} {po['opinion']}" for po in pos_ops[:3])
    else:
        ob_pos = "açık pozisyon yok"
    owner_brief = (
        f"{ob_pos}. "
        + (f"En iyi aday: {best['asset']} ({best['bias']})."
           if best["asset"] != "NONE" else "Yeni trade için uygun setup yok.")
    )

    # ── Ana karar motoru ile uyum (soft modifier için paper trading kullanır)
    decision = str((_report(ctx).get("decision") or {}).get("verdict") or "").upper()
    # System "AL/ARTTIR" → long_bias ile uyumlu; "KAPAT/KÜÇÜLT" → uyumsuz
    long_biased = best.get("bias") == "long"
    short_biased = best.get("bias") == "short"
    agrees = True
    disagreement = 0
    if decision in ("KAPAT", "KÜÇÜLT") and long_biased:
        agrees = False
        disagreement = 70
    elif decision in ("KAPAT", "KÜÇÜLT") and short_biased:
        agrees = True
        disagreement = 10
    elif decision in ("AL", "ARTTIR") and short_biased:
        agrees = False
        disagreement = 60
    elif decision == "BEKLE" and best.get("asset") != "NONE":
        agrees = True
        disagreement = 25

    top_invalidation = (
        best.get("risk") if best.get("asset") != "NONE"
        else (change_mind[0] if change_mind else "")
    )

    return {
        "schema_version":           SCHEMA_VERSION,
        "generated_at":             ctx.get("now") or datetime.now(UTC).isoformat(),
        "execution_mode":           "PAPER_SAFE",
        "live_execution_allowed":   False,
        "overall_view":             _overall_view(ctx),
        "market_opinion":           market_opinion,
        "asset_opinions":           asset_ops,
        "open_position_opinions":   pos_ops,
        "best_candidate":           best,
        "no_trade_reason":          no_trade_reason,
        "next_3_triggers":          [t for t in next_triggers if t],
        "next_triggers":            [t for t in next_triggers if t],
        "what_would_change_my_mind": [c for c in change_mind if c][:5],
        "invalidation":             top_invalidation,
        "owner_brief":              owner_brief,
        "agrees_with_main_decision": agrees,
        "disagreement_score":       disagreement,
    }


# ── Paper-trading entegrasyonu için yardımcılar ───────────────────────────────

def build_trade_opinion_context_for_signal(
    pair: str,
    side: str,
    *,
    opinion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    `_route_new_open_signal` içine yazılacak hafif, deterministik context.

    Dönen alanlar — paper trading bunlardan SADECE size_multiplier ve
    route_recommendation'ı soft modifier olarak kullanır; risk gate / decision
    her zaman üstündür.
    """
    if opinion is None:
        try:
            opinion = build_ai_trade_opinion()
        except Exception:  # noqa: BLE001
            opinion = None
    if not opinion:
        return {
            "available": False,
            "size_multiplier": 1.0,
            "route_recommendation": "proceed",
            "reason": "opinion_unavailable",
        }

    asset_op: dict[str, Any] = {}
    for a in opinion.get("asset_opinions") or []:
        if str(a.get("asset")) == pair:
            asset_op = a
            break

    op_label   = str(asset_op.get("opinion") or "").upper()
    conviction = str(asset_op.get("conviction") or "low").lower()

    # Soft size modifier (max ±0.10)
    multiplier = 1.0
    route      = "proceed"
    reason     = "neutral"

    side_u = side.upper()
    long_bias  = op_label == "LONG_BIAS"  and side_u == "LONG"
    short_bias = op_label == "SHORT_BIAS" and side_u == "SHORT"
    aligned    = long_bias or short_bias

    if aligned and conviction == "high":
        multiplier = 1.10
        reason = f"{op_label} high conviction → +10% soft size"
    elif aligned and conviction == "medium":
        multiplier = 1.05
        reason = f"{op_label} medium conviction → +5% soft size"
    elif op_label == "AVOID":
        multiplier = 0.0
        route = "manual_ready"
        reason = "AVOID — yeni trade önerilmiyor"
    elif conviction == "low" and not aligned:
        multiplier = 0.85
        reason = "Low conviction → -15% soft size"
    elif op_label in ("WAIT", "WAIT_EVENT_CONFIRMATION"):
        multiplier = 0.90
        reason = f"{op_label} → -10% soft size"

    # Position-specific opinion (REDUCE_WATCH / CLOSE_WATCH varsa ek koruma)
    pos_label = ""
    for po in opinion.get("open_position_opinions") or []:
        if str(po.get("pair")) == pair:
            pos_label = str(po.get("opinion") or "").upper()
            break
    if pos_label in ("REDUCE_WATCH", "CLOSE_WATCH"):
        route = "manual_ready"
        multiplier = min(multiplier, 0.0)
        reason = f"Açık pozisyon için {pos_label} — yeni add yok"

    return {
        "available":            True,
        "schema_version":       opinion.get("schema_version"),
        "asset_opinion":        op_label or "NONE",
        "asset_conviction":     conviction,
        "position_opinion":     pos_label or "NONE",
        "size_multiplier":      multiplier,
        "route_recommendation": route,
        "reason":               reason,
        "agrees_with_main_decision": opinion.get("agrees_with_main_decision"),
        "disagreement_score":   opinion.get("disagreement_score"),
        "best_candidate_asset": (opinion.get("best_candidate") or {}).get("asset"),
        "invalidation":         asset_op.get("invalidation"),
    }


def build_position_opinion_view(pair: str, side: str) -> dict[str, Any]:
    """Açık pozisyon için get_snapshot'ta gösterilecek hafif opinion özeti."""
    try:
        opinion = build_ai_trade_opinion()
    except Exception:  # noqa: BLE001
        return {"available": False}
    if not opinion:
        return {"available": False}
    side_u = side.upper()
    for po in opinion.get("open_position_opinions") or []:
        if str(po.get("pair")) == pair and str(po.get("side")) == side_u:
            return {
                "available":   True,
                "opinion":     po.get("opinion"),
                "conviction":  po.get("conviction"),
                "reason":      po.get("reason"),
                "watch":       po.get("what_to_watch") or [],
                "invalidation": po.get("invalidation"),
            }
    return {"available": True, "opinion": "MANUAL_REVIEW", "reason": "kayıt bulunamadı"}


__all__ = [
    "SCHEMA_VERSION",
    "TRACKED_ASSETS",
    "build_ai_trade_opinion",
    "build_position_opinion_view",
    "build_trade_opinion_context_for_signal",
    "collect_opinion_context",
]
