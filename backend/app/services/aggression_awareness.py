"""
Aggression Awareness Layer — Controlled-Aggressive paper trading.

Sistemi defansif/yılda-1-işlem moduna düşürmek YERINE, agent'ın açtığı
trade'in ne kadar agresif olduğunu ölçen ve buna göre size/stop/timeframe/
holding/recheck planını ayarlayan saf-fonksiyon modülü.

Ana prensip:
  "Risk varsa otomatik işlem yok" DEĞİL.
  "Risk varsa agresiflik seviyesi tanımlanır; pozisyon boyutu, stop mesafesi,
   timeframe ve holding süresi buna göre ayarlanır."

Bu modül HİÇBİR I/O yapmaz; agent_decision_aggregator ve paper_trading_service
tarafından çağrılır. Tüm hard-block kuralları (DQS<50, kill switch, divergent
TF, asset-adverse event risk) aggregator'da kalmaya devam eder — bu modül
yalnızca aggregator BLOCK demediği zaman devreye girer.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

# ── Tip tanımları ────────────────────────────────────────────────────────────

AggressionLevel = Literal["low", "medium", "high", "extreme"]
RecommendedTimeframe = Literal["15m", "30m", "1h", "4h", "1d"]
StopStyle = Literal["tight_atr", "structure_based", "hybrid_tight", "no_trade"]
PaperTradingMode = Literal["conservative", "balanced", "controlled_aggressive"]

AgentCommand = Literal[
    "WAIT",
    "WATCH",
    "AGGRESSIVE_WATCH",
    "SCALP_LONG_SETUP",
    "TACTICAL_LONG_SETUP",
    "LONG_SETUP",
    "LONG_CONFIRMED",
    "NEUTRAL",
    "RISK_REDUCE",
    "BLOCKED",
]


@dataclass
class AggressionContext:
    aggression_level: AggressionLevel
    aggression_score: int            # 0-100
    why_aggressive: list[str]
    allowed_if_aggressive: bool
    required_adjustments: dict[str, bool]
    recommended_timeframe: RecommendedTimeframe
    max_holding_time: str
    recheck_interval_minutes: int
    stop_style: StopStyle
    summary: str


@dataclass
class TimeframeDecision:
    selected_timeframe: RecommendedTimeframe
    reason: str
    max_holding_time: str
    recheck_interval_minutes: int


@dataclass
class StopDecision:
    stop_distance_pct: float         # % (örn. 1.4 → fiyatın %1.4 altı/üstü)
    atr_multiplier: float            # 1.0 / 1.5 / 2.0 / 2.5 ...
    stop_type: Literal["atr", "structure", "hybrid"]
    why_this_stop: str
    hard_invalidation: list[str]


@dataclass
class PositionSizingDecision:
    base_size_multiplier: float
    aggression_multiplier: float
    regime_multiplier: float
    contradiction_multiplier: float
    event_risk_multiplier: float
    volatility_multiplier: float
    final_size_multiplier: float
    reason: str


# ── Sabitler ─────────────────────────────────────────────────────────────────

# Agresiflik seviyesine göre maksimum boyut çarpanı (final_size_multiplier üst sınırı)
AGGRESSION_MAX_SIZE: dict[AggressionLevel, float] = {
    "low":     1.00,     # Normal rejim bazlı sizing
    "medium":  0.70,     # Seçici taktik
    "high":    0.40,     # Küçük, yakın stop
    "extreme": 0.20,     # Çok küçük, çok yakın stop
}

# Agresiflik → ATR çarpanı (stop mesafesi için)
AGGRESSION_ATR_MULT: dict[AggressionLevel, float] = {
    "low":     2.50,
    "medium":  1.80,
    "high":    1.20,
    "extreme": 1.00,
}

# Agresiflik → önerilen timeframe (primary)
AGGRESSION_TIMEFRAME: dict[AggressionLevel, RecommendedTimeframe] = {
    "low":     "1d",
    "medium":  "4h",
    "high":    "1h",
    "extreme": "30m",
}

# Agresiflik → max holding (insan-okur)
AGGRESSION_HOLDING: dict[AggressionLevel, str] = {
    "low":     "48h",
    "medium":  "24h",
    "high":    "6h",
    "extreme": "2h",
}

# Agresiflik → recheck interval (dakika)
AGGRESSION_RECHECK_MIN: dict[AggressionLevel, int] = {
    "low":     240,    # 4h
    "medium":  120,    # 2h
    "high":    30,
    "extreme": 15,
}

# Agresiflik → stop stili
AGGRESSION_STOP_STYLE: dict[AggressionLevel, StopStyle] = {
    "low":     "structure_based",
    "medium":  "structure_based",
    "high":    "hybrid_tight",
    "extreme": "tight_atr",
}

# Hızlı hareket eden, momentum-erken-yakalama uygun assetler
FAST_MOVING_ASSETS: frozenset[str] = frozenset({
    "BRENT", "BTCUSD", "XAGUSD", "XCUUSD", "ETHUSD",
})

# Event-sensitive assetler (haber-yoğun) — event_risk_high olsa bile tactical
# açabilen; YÖN aleyhineyse aggregator zaten bloklar
EVENT_SENSITIVE_ASSETS: frozenset[str] = frozenset({
    "BRENT", "XAUUSD", "XAGUSD",
})


# ── Contradiction scoring ────────────────────────────────────────────────────

def derive_contradiction_score(
    sig: dict[str, Any],
    *,
    tf_alignment_label: str,
    regime: str,
) -> int:
    """0-100 contradiction score — mevcut sig alanlarından türetilir.

    Yüksek = makro/teknik/TF/news kaynakları birbiriyle çelişiyor (örn. teknik
    long sinyali var ama makro defensive ve TF zayıf uyumlu). Düşük = tüm
    katmanlar aynı yönü destekliyor.

    Bu skor agresiflik seviyesinin ana girdisidir; aggregator'da hiçbir hard
    blok değildir — yalnızca TACTICAL/SCALP/AGGRESSIVE_WATCH'a yönlendirir.
    """
    score = 0

    # 1. Teknik yön vs makro rejim çelişkisi (en güçlü sinyal)
    direction = (sig.get("final_direction") or "").lower()
    if direction == "bullish":
        if regime in ("CRISIS",):
            score += 50
        elif regime in ("DEFENSIVE", "RISK_OFF"):
            score += 30
        elif regime in ("TRANSITIONING", "NEUTRAL"):
            score += 18
    elif direction == "bearish":
        if regime in ("RISK_ON", "AGGRESSIVE_RISK_ON", "OFFENSIVE"):
            score += 30
        elif regime in ("TRANSITIONING", "NEUTRAL"):
            score += 15

    # 2. TF uyum seviyesi
    tf_penalty = {
        "strong":    0,
        "moderate":  10,
        "weak":      25,
        "none":      15,    # bilinmiyor → temkinli
        "divergent": 60,    # aggregator zaten bloklar ama yine de yansıt
    }
    score += tf_penalty.get(tf_alignment_label, 15)

    # 3. Confluence durumu
    confluence = sig.get("confluence") or {}
    conf_status = (
        confluence.get("status") if isinstance(confluence, dict) else confluence
    ) or ""
    conf_lower = str(conf_status).lower()
    if "weak" in conf_lower or "diverg" in conf_lower or "conflict" in conf_lower:
        score += 12
    elif "aligned" in conf_lower or "strong" in conf_lower:
        score -= 8

    # 4. Skor "ortalama" mı yoksa keskin mi?
    final_score = float(sig.get("final_score") or 0.0)
    if direction == "bullish":
        # 60-70 → orta keskinlik (+10), 80+ → keskin (-5)
        if 58.0 <= final_score < 70.0:
            score += 10
        elif final_score >= 80.0:
            score -= 5
    elif direction == "bearish":
        if 30.0 < final_score <= 42.0:
            score += 10
        elif final_score <= 20.0:
            score -= 5

    return max(0, min(100, score))


# ── Aggression scoring ───────────────────────────────────────────────────────

def score_aggression(
    sig: dict[str, Any],
    *,
    pair: str,
    side: str | None,
    tf_alignment_label: str,
    regime: str,
    appetite: str | None,
    dqs_score: int | None,
    contradiction_score: int,
) -> AggressionContext:
    """Bir trade adayının kontrollü-agresif profilini çıkar.

    Aggregator tarafından SADECE hard-block geçmiş (DQS>=55, kill_switch=False,
    TF divergent değil) adaylar için çağrılır. Çıktısı yalnızca size/stop/
    timeframe/holding/recheck planını belirler — kararı engellemez.
    """
    why: list[str] = []
    score = 0

    # 1. Makro rejim katkısı
    if regime in ("TRANSITIONING", "NEUTRAL"):
        score += 18
        why.append("Makro rejim tam risk-on değil")
    elif regime in ("DEFENSIVE", "RISK_OFF"):
        score += 32
        why.append("Makro rejim defansif zeminde")
    elif regime == "CRISIS":
        score += 55
        why.append("Makro rejim kriz modunda — yalnızca asset-uygun tactical")
    # RISK_ON / OFFENSIVE / AGGRESSIVE_RISK_ON → 0

    # 2. Risk iştahı katkısı
    appetite_u = (appetite or "").upper()
    if appetite_u in ("MODERATE", "MEDIUM"):
        score += 15
        why.append("Risk iştahı seçici")
    elif appetite_u in ("WEAK", "DEFENSIVE"):
        score += 28
        why.append("Risk iştahı zayıf")
    elif appetite_u in ("CRISIS", "PANIC"):
        score += 45
        why.append("Risk iştahı panik")

    # 3. TF uyumu katkısı
    if tf_alignment_label == "weak":
        score += 18
        why.append("TF uyumu zayıf — sadece primary destekliyor")
    elif tf_alignment_label == "moderate":
        score += 8
        why.append("TF uyumu orta seviyede")
    elif tf_alignment_label == "none":
        score += 12
        why.append("TF sinyal verisi yetersiz")

    # 4. Contradiction katkısı
    if contradiction_score >= 60:
        score += 22
        why.append(f"Yüksek contradiction ({contradiction_score})")
    elif contradiction_score >= 40:
        score += 12
        why.append(f"Orta contradiction ({contradiction_score})")

    # 5. DQS — geçer ama mükemmel değil
    if dqs_score is not None and 55 <= dqs_score < 70:
        score += 8
        why.append(f"DQS sınırda ({dqs_score})")

    # 6. Hızlı hareket eden asset → momentum erken yakalama isteği
    if pair in FAST_MOVING_ASSETS:
        score += 5
        why.append(f"{pair} hızlı hareket eden asset — momentum erken setup")

    # 7. Skorun keskinliği — orta skor (62-68 / 32-38) erken setup işareti
    final_score = float(sig.get("final_score") or 0.0)
    direction = (sig.get("final_direction") or "").lower()
    if direction == "bullish" and 58.0 <= final_score < 68.0:
        score += 8
        why.append(f"Bullish skor orta-keskinlikte ({final_score:.0f}) — erken setup")
    elif direction == "bearish" and 32.0 < final_score <= 42.0:
        score += 8
        why.append(f"Bearish skor orta-keskinlikte ({final_score:.0f}) — erken setup")

    score = max(0, min(100, score))

    # ── Seviyeye haritala ────────────────────────────────────────────────────
    if score >= 70:
        level: AggressionLevel = "extreme"
    elif score >= 50:
        level = "high"
    elif score >= 25:
        level = "medium"
    else:
        level = "low"

    if not why:
        why.append("Tüm katmanlar aynı yönde — normal sizing")

    required = {
        "smaller_size":        level in ("medium", "high", "extreme"),
        "tighter_stop":        level in ("high", "extreme"),
        "shorter_timeframe":   level in ("high", "extreme"),
        "faster_recheck":      level in ("high", "extreme"),
        "partial_take_profit": level in ("medium", "high", "extreme"),
        "hard_invalidation":   level in ("high", "extreme"),
    }

    summary = _build_aggression_summary(level, side, pair, score)

    return AggressionContext(
        aggression_level=level,
        aggression_score=score,
        why_aggressive=why,
        allowed_if_aggressive=True,  # blok aggregator'da; bu modül sadece profil
        required_adjustments=required,
        recommended_timeframe=AGGRESSION_TIMEFRAME[level],
        max_holding_time=AGGRESSION_HOLDING[level],
        recheck_interval_minutes=AGGRESSION_RECHECK_MIN[level],
        stop_style=AGGRESSION_STOP_STYLE[level],
        summary=summary,
    )


def _build_aggression_summary(
    level: AggressionLevel, side: str | None, pair: str, score: int,
) -> str:
    side_str = side or "trade"
    if level == "low":
        return f"{pair} {side_str}: normal sizing — tüm katmanlar destekliyor (score {score})."
    if level == "medium":
        return (
            f"{pair} {side_str}: taktik setup — seçici sizing, yakın stop, kısa "
            f"holding (score {score})."
        )
    if level == "high":
        return (
            f"{pair} {side_str}: agresif setup — küçük boyut, yakın stop, "
            f"kısa timeframe, sık recheck (score {score})."
        )
    return (
        f"{pair} {side_str}: çok agresif setup — minimum boyut, çok yakın stop, "
        f"hard invalidation (score {score})."
    )


# ── Komut seçimi ─────────────────────────────────────────────────────────────

def pick_command(
    *,
    side: str | None,
    confidence: float,
    aggression_level: AggressionLevel,
    contradiction_score: int,
    block_reason: str,
    risk_action: str,
) -> AgentCommand:
    """Aggregator çıktısı + aggression seviyesini AgentCommand'a haritala.

    HARD blok (DQS<55 / kill_switch / TF divergent / contradiction>80) → BLOCKED.
    SOFT blok (sadece "Güven düşük" tipi gate'ler) + aggression high/extreme →
    AGGRESSIVE_WATCH (trade açılmaz ama "çok yakından izle" olarak işaretlenir).
    """
    # Risk engine kill switch → her zaman hard block
    if risk_action == "KILL_SWITCH":
        return "BLOCKED"

    # Hard block sinyalleri: KILL_SWITCH, TF divergent
    HARD_BLOCK_TOKENS = ("KILL_SWITCH", "TF karşıt")
    if block_reason and any(tok in block_reason for tok in HARD_BLOCK_TOKENS):
        return "BLOCKED"

    # Soft block (örn. confidence gate) + yüksek agresiflik → AGGRESSIVE_WATCH
    if block_reason and aggression_level in ("high", "extreme"):
        return "AGGRESSIVE_WATCH"
    if block_reason:
        return "BLOCKED"

    if side is None:
        # Yön yok ama hard block da yok → izleme
        if aggression_level in ("high", "extreme"):
            return "AGGRESSIVE_WATCH"
        if contradiction_score >= 40:
            return "WATCH"
        return "WAIT"

    # Side var, blok yok → controlled-aggressive komut matrisi
    if contradiction_score >= 60:
        # Üst orta-yüksek contradiction → minik scalp / agresif izleme
        if aggression_level == "extreme":
            return "AGGRESSIVE_WATCH"
        return "SCALP_LONG_SETUP" if side == "LONG" else "SCALP_LONG_SETUP"
    if contradiction_score >= 40:
        return "TACTICAL_LONG_SETUP"
    # Düşük contradiction → confidence'a göre LONG_SETUP veya LONG_CONFIRMED
    if confidence >= 72.0 and aggression_level == "low":
        return "LONG_CONFIRMED"
    return "LONG_SETUP"


# ── Timeframe seçimi ─────────────────────────────────────────────────────────

def choose_timeframe(
    aggression: AggressionContext,
    primary_tf: str,
) -> TimeframeDecision:
    """Agresiflik seviyesine göre timeframe + holding + recheck."""
    selected = aggression.recommended_timeframe
    return TimeframeDecision(
        selected_timeframe=selected,
        reason=(
            f"Aggression {aggression.aggression_level} (score {aggression.aggression_score}) "
            f"→ {selected}. Primary TF: {primary_tf or '?'}."
        ),
        max_holding_time=aggression.max_holding_time,
        recheck_interval_minutes=aggression.recheck_interval_minutes,
    )


# ── Stop seçimi ──────────────────────────────────────────────────────────────

def choose_stop(
    aggression: AggressionContext,
    *,
    side: str | None,
    price: float,
    atr_value: float,
    support_level: float | None = None,
) -> StopDecision:
    """Aggression-aware stop hesaplama.

    Sadece mesafeyi (ATR çarpanı + %) döndürür; paper_trading_service mevcut
    SL/TP hesabını korur ve bu sonucu opsiyonel olarak risk_plan'a yazar.
    """
    atr_mult = AGGRESSION_ATR_MULT[aggression.aggression_level]

    if atr_value > 0 and price > 0:
        stop_distance_pct = (atr_value * atr_mult / price) * 100.0
    else:
        # ATR yok → agresifliğe göre sabit %
        stop_distance_pct = {
            "low":     1.50,
            "medium":  1.00,
            "high":    0.65,
            "extreme": 0.40,
        }[aggression.aggression_level]

    # Structure-aware: support biliniyorsa ve yakınsa structure-based
    stop_type: Literal["atr", "structure", "hybrid"] = "atr"
    if support_level is not None and side == "LONG" and price > 0:
        struct_dist_pct = ((price - support_level) / price) * 100.0
        if 0 < struct_dist_pct < stop_distance_pct * 1.5:
            stop_type = "hybrid" if aggression.aggression_level in ("high", "extreme") else "structure"
            stop_distance_pct = min(stop_distance_pct, struct_dist_pct + 0.05)

    invalidation: list[str] = []
    if aggression.aggression_level in ("high", "extreme"):
        invalidation.append("Fiyat stop seviyesinin altına/üstüne kapanırsa pozisyon kapatılır.")
        invalidation.append("Primary TF trendi tersine dönerse hard invalidation.")
    else:
        invalidation.append("ATR-bazlı normal SL — trailing stop devreye girer.")

    return StopDecision(
        stop_distance_pct=round(stop_distance_pct, 4),
        atr_multiplier=atr_mult,
        stop_type=stop_type,
        why_this_stop=(
            f"Aggression {aggression.aggression_level} → ATR×{atr_mult} "
            f"({stop_distance_pct:.2f}% mesafe, tip={stop_type})"
        ),
        hard_invalidation=invalidation,
    )


# ── Position sizing ──────────────────────────────────────────────────────────

def aggression_sizing(
    *,
    base_size_multiplier: float,
    regime: str,
    aggression: AggressionContext,
    contradiction_score: int,
    event_risk_high: bool = False,
    high_volatility: bool = False,
) -> PositionSizingDecision:
    """Mevcut base_mult × rejim × agresif sınır × contradiction × event × vol.

    Geriye dönük uyum: aggression='low' + diğer hepsi nötr ise eski size_pct
    ile aynı sonucu verir (regime_mult haricinde) — yani agresiflik bilgisi
    yoksa sistem mevcut davranışı korur.
    """
    # Rejim çarpanı (agg awareness, regime_base_mult'tan biraz daha tolerant)
    regime_m = {
        "OFFENSIVE":          1.00,
        "AGGRESSIVE_RISK_ON": 1.00,
        "RISK_ON":            1.00,
        "CONTROLLED_RISK_ON": 0.90,
        "NEUTRAL":            0.85,
        "TRANSITIONING":      0.75,
        "DEFENSIVE":          0.55,
        "RISK_OFF":           0.55,
        "CRISIS":             0.30,
    }.get(regime, 0.75)

    # Agresiflik çarpanı — max_size üst sınırı
    agg_m = AGGRESSION_MAX_SIZE[aggression.aggression_level]

    # Contradiction çarpanı
    if contradiction_score >= 70:
        cont_m = 0.55
    elif contradiction_score >= 50:
        cont_m = 0.75
    elif contradiction_score >= 30:
        cont_m = 0.90
    else:
        cont_m = 1.00

    # Event risk (asset doğrudan event asset'i ve event_risk_high)
    event_m = 0.65 if event_risk_high else 1.00

    # Volatilite çarpanı
    vol_m = 0.80 if high_volatility else 1.00

    final = base_size_multiplier * regime_m * agg_m * cont_m * event_m * vol_m

    return PositionSizingDecision(
        base_size_multiplier=round(base_size_multiplier, 4),
        aggression_multiplier=round(agg_m, 4),
        regime_multiplier=round(regime_m, 4),
        contradiction_multiplier=round(cont_m, 4),
        event_risk_multiplier=round(event_m, 4),
        volatility_multiplier=round(vol_m, 4),
        final_size_multiplier=round(max(0.0, final), 4),
        reason=(
            f"base={base_size_multiplier:.2f} × regime({regime})={regime_m:.2f} × "
            f"agg({aggression.aggression_level})={agg_m:.2f} × cont({contradiction_score})={cont_m:.2f} × "
            f"event={event_m:.2f} × vol={vol_m:.2f} = {final:.4f}"
        ),
    )


# ── Serialization helpers ────────────────────────────────────────────────────

def aggression_to_dict(ctx: AggressionContext) -> dict[str, Any]:
    """open_signal içine yazmak için serileştir."""
    return {
        "aggression_level":         ctx.aggression_level,
        "aggression_score":         ctx.aggression_score,
        "why_aggressive":           list(ctx.why_aggressive),
        "allowed_if_aggressive":    ctx.allowed_if_aggressive,
        "required_adjustments":     dict(ctx.required_adjustments),
        "recommended_timeframe":    ctx.recommended_timeframe,
        "max_holding_time":         ctx.max_holding_time,
        "recheck_interval_minutes": ctx.recheck_interval_minutes,
        "stop_style":               ctx.stop_style,
        "summary":                  ctx.summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FAZ 2 — Aggression Execution Integration helpers (pure functions, no I/O)
# ─────────────────────────────────────────────────────────────────────────────

# Minimum kabul edilebilir risk/reward — bu altındaki TP planı trade'i WATCH'a çekmeli
MIN_RR_THRESHOLD: float = 1.2

# Agresiflik → R/R hedefi (TP planı)
# Tüm değerler MIN_RR_THRESHOLD üzerinde tutuldu — extreme bile 1.2'nin altına düşmez.
AGGRESSION_RR_TARGET: dict[AggressionLevel, float] = {
    "low":     2.80,
    "medium":  2.20,
    "high":    1.80,
    "extreme": 1.20,
}

# Agresiflik → partial TP @ R çarpanı (None = partial TP yok)
AGGRESSION_PARTIAL_TP_AT_R: dict[AggressionLevel, float | None] = {
    "low":     None,
    "medium":  None,
    "high":    1.00,
    "extreme": 0.80,
}

# Pozisyon süresine bağlı maks recheck sayısı — promotion sırasında kullanılır
AGGRESSION_MAX_RECHECKS: dict[AggressionLevel, int] = {
    "low":     12,    # 4h × 12 = 48h
    "medium":  12,
    "high":    12,    # 30m × 12 = 6h
    "extreme": 8,     # 15m × 8 = 2h
}

# Controlled-aggressive promotion için kapsanan agresiflik skor aralığı
PROMOTION_SCORE_RANGE: tuple[int, int] = (60, 80)
PROMOTION_MAX_SIZE: float = 0.25     # promotion sonucu pozisyon < 0.25× tutar
PROMOTION_MIN_DQS: int = 55


# ── Event Risk / Volatility fallback derivers ────────────────────────────────

def derive_event_risk_fallback(
    pair: str,
    sig: dict[str, Any],
    *,
    regime: str,
    appetite: str,
    side: str | None,
) -> dict[str, Any]:
    """Mevcut sig + rejim + risk iştahı + asset cinsinden event risk türet.

    News service'e bağlanmaz — fallback heuristik. Çıktı `aggression_sizing`
    içine geçirilir ve `open_signal.event_risk_context` olarak audit edilir.
    """
    reasons: list[str] = []
    high = False
    direction = "neutral_or_unknown"

    # 1. Makro rejim
    if regime in ("CRISIS",):
        high = True
        reasons.append("Makro rejim CRISIS")
    elif regime == "DEFENSIVE":
        # Sadece event-sensitive asset'lerde DEFENSIVE → event_risk_high
        if pair in EVENT_SENSITIVE_ASSETS:
            high = True
            reasons.append(f"{pair} event-sensitive ve rejim DEFENSIVE")

    # 2. Risk iştahı
    appetite_u = (appetite or "").upper()
    if appetite_u in ("CRISIS", "PANIC"):
        high = True
        reasons.append("Risk iştahı PANIC/CRISIS")
    elif appetite_u in ("WEAK", "DEFENSIVE") and pair in EVENT_SENSITIVE_ASSETS:
        high = True
        reasons.append(f"Risk iştahı zayıf + {pair} event-sensitive")

    # 3. Confluence/reason metinlerinde anahtar kelime
    confluence = sig.get("confluence") or {}
    reason_blob = " ".join([
        str(confluence.get("status") if isinstance(confluence, dict) else confluence or ""),
        str(confluence.get("reason") if isinstance(confluence, dict) else ""),
        str(sig.get("note") or ""),
        str(sig.get("event_hint") or ""),
    ]).lower()
    EVENT_TOKENS = ("war", "shock", "geopolitical", "energy", "oil", "embargo", "sanction")
    matched_tokens = [tok for tok in EVENT_TOKENS if tok in reason_blob]
    if matched_tokens:
        high = True
        reasons.append(f"Event token: {', '.join(matched_tokens)}")

    # 4. Yön (asset bazlı sezgi — fallback olduğu için kaba)
    if high and side in ("LONG", "SHORT"):
        if pair == "BRENT" and side == "LONG":
            direction = "supports_trade"   # Enerji şoku → Brent yukarı
        elif pair in ("XAUUSD", "XAGUSD") and side == "LONG":
            direction = "supports_trade"   # Risk-off → safe haven yukarı
        elif pair == "BTCUSD" and side == "LONG" and regime in ("CRISIS", "DEFENSIVE"):
            direction = "against_trade"    # Risk-off BTC LONG için zorlu
        elif side == "SHORT" and regime in ("RISK_ON",):
            direction = "against_trade"

    if not reasons:
        reasons.append("Fallback heuristic: event risk göstergesi yok")

    return {
        "event_risk_high":      bool(high),
        "event_risk_direction": direction,
        "reason":               " · ".join(reasons),
    }


def derive_high_volatility_fallback(
    pair: str,
    sig: dict[str, Any],
    *,
    atr_value: float,
    entry_price: float,
) -> dict[str, Any]:
    """ATR / fiyat oranı ve fast-moving asset üyeliğine göre fallback."""
    reasons: list[str] = []
    high = False

    atr_pct = 0.0
    if atr_value > 0 and entry_price > 0:
        atr_pct = (atr_value / entry_price) * 100.0

    # 1. ATR çok yüksek
    if atr_pct >= 3.0:
        high = True
        reasons.append(f"ATR/fiyat oranı yüksek ({atr_pct:.2f}%)")
    elif pair in FAST_MOVING_ASSETS and atr_pct >= 2.0:
        high = True
        reasons.append(f"{pair} hızlı hareket eden asset, ATR {atr_pct:.2f}%")

    # 2. sig içinde explicit volatility hint var mı (opsiyonel)
    vol_hint = sig.get("volatility_state") or sig.get("vol_level") or ""
    if isinstance(vol_hint, str) and vol_hint.lower() in ("high", "elevated", "extreme"):
        high = True
        reasons.append(f"Sig vol hint: {vol_hint}")

    if not reasons:
        reasons.append("Fallback heuristic: volatilite normal aralıkta")

    return {
        "high_volatility": bool(high),
        "atr_pct":         round(atr_pct, 4),
        "reason":          " · ".join(reasons),
    }


# ── Take Profit Plan ─────────────────────────────────────────────────────────

def build_take_profit_plan(
    aggression: AggressionContext,
    stop_decision: StopDecision | None,
    *,
    side: str | None,
    entry_price: float,
    stop_price: float,
) -> dict[str, Any]:
    """Agresiflik seviyesine göre TP planı.

    Çıktı open_signal["take_profit_plan"] olarak yazılır + paper_trading
    actual TP seviyesini bu plana göre kurar.
    """
    level = aggression.aggression_level
    rr_target = AGGRESSION_RR_TARGET[level]
    partial_at_r = AGGRESSION_PARTIAL_TP_AT_R[level]

    stop_distance = abs(entry_price - stop_price) if entry_price and stop_price else 0.0
    final_tp_price: float | None = None
    partial_tp_price: float | None = None
    rr_below_min = rr_target < MIN_RR_THRESHOLD

    if stop_distance > 0 and side in ("LONG", "SHORT") and entry_price > 0:
        if side == "LONG":
            final_tp_price = round(entry_price + (stop_distance * rr_target), 4)
            if partial_at_r is not None:
                partial_tp_price = round(entry_price + (stop_distance * partial_at_r), 4)
        else:
            final_tp_price = round(entry_price - (stop_distance * rr_target), 4)
            if partial_at_r is not None:
                partial_tp_price = round(entry_price - (stop_distance * partial_at_r), 4)

    reasons = {
        "low":     "Normal sizing — geniş hedef, partial TP zorunlu değil.",
        "medium":  "Taktik trade — orta hedef, partial TP opsiyonel.",
        "high":    "Agresif trade — kısa hedef + partial TP zorunlu.",
        "extreme": "Çok agresif trade — minimum hedef, kısa partial TP zorunlu.",
    }

    return {
        "rr_target":          rr_target,
        "partial_tp_enabled": partial_at_r is not None,
        "partial_tp_at_r":    partial_at_r,
        "final_tp_at_r":      rr_target,
        "partial_tp_price":   partial_tp_price,
        "final_tp_price":     final_tp_price,
        "stop_distance":      round(stop_distance, 4) if stop_distance else 0.0,
        "rr_below_min":       rr_below_min,
        "min_rr":             MIN_RR_THRESHOLD,
        "reason":             reasons[level],
        "stop_type":          stop_decision.stop_type if stop_decision else "atr",
    }


# ── Recheck Plan ─────────────────────────────────────────────────────────────

def build_recheck_plan(
    aggression: AggressionContext,
    opened_at_iso: str,
) -> dict[str, Any]:
    """Pozisyon açılışında recheck planı — paper_trading_service her tick'te
    `next_recheck_at` ulaşılınca yeniden değerlendirir (ilk fazda otomatik
    close yapmaz, sadece audit/flag yazar)."""
    interval = aggression.recheck_interval_minutes
    max_rechecks = AGGRESSION_MAX_RECHECKS[aggression.aggression_level]
    next_iso = ""
    try:
        opened_dt = datetime.fromisoformat(opened_at_iso)
        next_iso = (opened_dt + timedelta(minutes=interval)).isoformat()
    except (TypeError, ValueError):
        next_iso = ""

    return {
        "recheck_interval_minutes": interval,
        "next_recheck_at":          next_iso,
        "last_recheck_at":          None,
        "recheck_count":            0,
        "max_rechecks":             max_rechecks,
        "last_recheck_result":      None,   # "ok"|"warning"|"reduce_flag"|"exit_flag"
        "last_recheck_reason":      "",
    }


# ── Holding Plan ─────────────────────────────────────────────────────────────

def build_holding_plan(
    aggression: AggressionContext,
    opened_at_iso: str,
) -> dict[str, Any]:
    """Pozisyon açılışında max holding planı.

    İlk fazda otomatik close yapılmaz; süresi dolunca holding_status
    'expired_needs_review' olur ve audit'e yazılır.
    """
    holding = aggression.max_holding_time   # "2h" | "6h" | "24h" | "48h"
    hours_map = {"2h": 2, "6h": 6, "24h": 24, "48h": 48}
    hours = hours_map.get(holding, 24)
    until_iso = ""
    try:
        opened_dt = datetime.fromisoformat(opened_at_iso)
        until_iso = (opened_dt + timedelta(hours=hours)).isoformat()
    except (TypeError, ValueError):
        until_iso = ""

    return {
        "max_holding_time":   holding,
        "max_holding_until":  until_iso,
        "extension_allowed":  True,
        "extension_requires": [
            "confidence >= 72", "contradiction < 40", "risk_gate ALLOW",
        ],
        "holding_status":     "active",   # "active"|"expired_needs_review"|"extended"
    }


# ── Aggression-aware SL/TP ───────────────────────────────────────────────────

def calc_aggression_aware_sl_tp(
    side: str,
    entry_price: float,
    pair: str,
    atr_value: float | None,
    open_signal: dict[str, Any] | None,
) -> tuple[float, float, dict[str, Any]] | None:
    """open_signal.stop_decision varsa aggression-aware SL/TP hesapla.

    Yoksa None döner → caller fallback (_calc_sl_tp) kullanır.

    Çıktı: (sl, tp, meta) — meta open_signal'a yazılır.
    """
    if not isinstance(open_signal, dict):
        return None

    stop_meta = open_signal.get("stop_decision") or {}
    if not stop_meta:
        return None

    atr_mult = float(stop_meta.get("atr_multiplier") or 0.0)
    stop_type = str(stop_meta.get("stop_type") or "atr")
    if atr_mult <= 0:
        return None

    if atr_value is None or atr_value <= 0:
        # ATR olmadan aggression-aware hesap güvenilir değil — fallback'e bırak.
        return None
    if side not in ("LONG", "SHORT"):
        return None
    if entry_price <= 0:
        return None

    # Stop mesafesi
    risk = atr_mult * atr_value

    # Hybrid: structure-based stop varsa daha sıkı olanı seç
    if stop_type == "hybrid":
        # paper_trading_service ileride support/resistance geçirebilir; şu an
        # stop_decision.stop_distance_pct içinden alıyoruz (aggregator zaten
        # support_level=None ile çağırıyor; ileride bağlanabilir)
        stop_distance_pct = float(stop_meta.get("stop_distance_pct") or 0.0)
        if stop_distance_pct > 0:
            structure_risk = entry_price * (stop_distance_pct / 100.0)
            # En sıkı stop'u tut (gürültüye dayanıklı): max(structure, atr×0.8)
            risk = max(min(risk, structure_risk), atr_value * 0.8)

    # Aggression context'inden TP planı (R/R)
    agg = open_signal.get("aggression_context") or {}
    level = str(agg.get("aggression_level") or "low")
    if level not in AGGRESSION_RR_TARGET:
        level = "low"
    rr_target = AGGRESSION_RR_TARGET[level]
    reward = risk * rr_target

    if side == "LONG":
        sl = round(entry_price - risk, 4)
        tp = round(entry_price + reward, 4)
    else:
        sl = round(entry_price + risk, 4)
        tp = round(entry_price - reward, 4)

    sl_pct = round((risk / entry_price) * 100.0, 4) if entry_price else 0.0
    tp_pct = round((reward / entry_price) * 100.0, 4) if entry_price else 0.0

    meta = {
        "source":          "aggression",
        "atr_multiplier":  atr_mult,
        "stop_type":       stop_type,
        "rr_target":       rr_target,
        "rr_below_min":    rr_target < MIN_RR_THRESHOLD,
        "sl_pct":          sl_pct,
        "tp_pct":          tp_pct,
        "atr_used":        atr_value,
        "aggression_level": level,
        "pair":            pair,
        "reason": (
            f"Aggression {level} → SL=ATR×{atr_mult:g} ({sl_pct:.2f}%), "
            f"TP=R/R {rr_target:g} ({tp_pct:.2f}%) · type={stop_type}"
        ),
    }
    return sl, tp, meta


# ── Controlled-Aggressive Promotion ──────────────────────────────────────────

def maybe_promote_command(
    *,
    paper_mode: str,
    command: str,
    side_hint: str | None,
    aggression: AggressionContext,
    contradiction_score: int,
    block_reason: str,
    risk_action: str,
    dqs_score: int | None,
    tf_alignment_label: str,
    atr_value: float,
    event_risk_direction: str,
) -> dict[str, Any]:
    """Controlled-aggressive modda uygun AGGRESSIVE_WATCH → SCALP_LONG_SETUP.

    Promotion yalnızca tüm koşullar sağlandığında olur:
      - paper_mode == controlled_aggressive
      - command == AGGRESSIVE_WATCH
      - aggression_score 60-80 aralığı
      - contradiction_score < 80
      - DQS >= 55
      - TF divergent değil
      - risk_action KILL_SWITCH değil
      - block_reason'da hard token (KILL_SWITCH/TF karşıt) YOK
      - ATR > 0 (stop hesaplanabilir)
      - side_hint mevcut (yön belirsiz değil)
      - event_risk_direction "against_trade" değil

    Returns dict (her zaman) — promoted=False ise diğer alanlar default.
    """
    out = {
        "promoted":     False,
        "from":         command,
        "to":           command,
        "new_size_cap": 0.0,
        "reason":       "",
    }

    if paper_mode != "controlled_aggressive":
        out["reason"] = "Promotion devre dışı: paper_mode değil controlled_aggressive"
        return out
    if command != "AGGRESSIVE_WATCH":
        out["reason"] = f"Promotion uygulanmaz: command={command}"
        return out
    score = aggression.aggression_score
    lo, hi = PROMOTION_SCORE_RANGE
    if not (lo <= score <= hi):
        out["reason"] = f"Aggression score {score} aralık dışı [{lo}, {hi}]"
        return out
    if contradiction_score >= 80:
        out["reason"] = f"Contradiction çok yüksek ({contradiction_score})"
        return out
    if dqs_score is not None and dqs_score < PROMOTION_MIN_DQS:
        out["reason"] = f"DQS düşük ({dqs_score})"
        return out
    if tf_alignment_label == "divergent":
        out["reason"] = "TF divergent — promotion yok"
        return out
    if risk_action == "KILL_SWITCH":
        out["reason"] = "KILL_SWITCH aktif"
        return out
    HARD_TOKENS = ("KILL_SWITCH", "TF karşıt")
    if block_reason and any(tok in block_reason for tok in HARD_TOKENS):
        out["reason"] = f"Hard block: {block_reason}"
        return out
    if atr_value <= 0:
        out["reason"] = "ATR yok — stop hesaplanamıyor"
        return out
    if side_hint not in ("LONG", "SHORT"):
        out["reason"] = "Yön belirsiz"
        return out
    if event_risk_direction == "against_trade":
        out["reason"] = "Event risk trade yönüne ters"
        return out

    # Tüm koşullar sağlandı → promote
    new_size = min(PROMOTION_MAX_SIZE, AGGRESSION_MAX_SIZE[aggression.aggression_level])
    out.update({
        "promoted":     True,
        "to":           "SCALP_LONG_SETUP" if side_hint == "LONG" else "SCALP_LONG_SETUP",
        "new_size_cap": round(new_size, 4),
        "reason": (
            f"Controlled-aggressive promotion: aggression_score {score}, "
            f"contradiction {contradiction_score}, DQS {dqs_score} — scalp setup açılır "
            f"(size ≤ {new_size:.2f}, stop tight, recheck {aggression.recheck_interval_minutes}dk)"
        ),
    })
    return out
