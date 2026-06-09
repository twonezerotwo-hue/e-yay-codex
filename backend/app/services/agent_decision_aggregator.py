"""
Agent Decision Aggregator — Paper Trading için Çok Katmanlı Karar Motoru.

Mevcut _consensus_to_action'ın yerini alır; şu 4 yeni katmanı ekler:

  1. Multi-TF Alignment
     tf_signals içindeki 1h / 4h / 1d sinyallerinin uyumuna bakılır.
     Karşıt TF'ler varsa (divergent) trade bloke edilir.
     Güçlü uyum size_pct'yi artırır, zayıf uyum azaltır.

  2. Regime-Based Sizing
     raw_regime (OFFENSIVE / NEUTRAL / DEFENSIVE / CRISIS) konuma göre
     pozisyon büyüklüğü ölçeklenir. CRISIS'te küçük lot, OFFENSIVE'de tam.

  3. DQS Gate
     Veri kalitesi skoru (0-100) eşiğin altındaysa (< MIN_DQS) trade yok.

  4. Trigger Auto-Close (Pasif — ilerleyen sprint aktifleşecek)
     RED seviyesi critical trigger tetiklendiğinde auto_close=True döner;
     tick_consensus bu bayrağı görünce açık pozisyonu kapatır.

Çıktı: AgentTradeDecision — side, size_pct, confidence, block_reason, auto_close

PAPER_SAFE / NO_EXECUTION
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.aggression_awareness import (
    AgentCommand,
    AggressionContext,
    PositionSizingDecision,
    StopDecision,
    TimeframeDecision,
    aggression_sizing,
    aggression_to_dict,
    build_take_profit_plan,
    choose_stop,
    choose_timeframe,
    derive_contradiction_score,
    derive_event_risk_fallback,
    derive_high_volatility_fallback,
    maybe_promote_command,
    pick_command,
    score_aggression,
)

PositionSide = Literal["LONG", "SHORT"]
TradeSignal = Literal["LONG", "SHORT", "CLOSE", None]

# ── Eşik değerleri ────────────────────────────────────────────────────────────

# Minimum final_score — bu altında yön tespiti yapılmaz
MIN_SCORE_THRESHOLD: float = 58.0   # Mevcut LONG_THR=60 / SHORT_THR=40'la uyumlu

# Confidence gate — bu altında trade bloke
MIN_TRADE_CONFIDENCE: float = 56.0

# DQS kill — data kalitesi bu altında → yeni trade yok
MIN_DQS: int = 55

# ── Rejim tabloları ───────────────────────────────────────────────────────────

# Rejime göre temel pozisyon büyüklüğü katsayısı
REGIME_BASE_MULT: dict[str, float] = {
    "OFFENSIVE": 1.00,    # En yüksek risk iştahı — tam pozisyon
    "NEUTRAL":   0.85,
    "DEFENSIVE": 0.65,    # Temkinli — küçük pozisyon
    "CRISIS":    0.35,    # Pozisyon al ama çok küçük
}

# TF alignment → confidence'a eklenen delta (puan)
TF_ALIGNMENT_CONF_DELTA: dict[str, float] = {
    "strong":    +12.0,   # ≥3 TF aynı yön, ort skor ≥65
    "moderate":  +5.0,    # 2 TF uyumlu
    "weak":      -8.0,    # Sadece primary uyumlu
    "divergent": -30.0,   # Karşıt TF → pratikte her zaman bloke
    "none":       0.0,    # TF verisi yok → pas geç
}

# TF alignment → size_pct çarpanı (rejim katsayısına ek)
TF_ALIGNMENT_SIZE_MULT: dict[str, float] = {
    "strong":    1.00,
    "moderate":  0.85,
    "weak":      0.60,
    "divergent": 0.00,    # Divergent → trade yok
    "none":      0.75,    # TF verisi yoksa biraz ihtiyatlı
}

# Kritik trigger kodu → auto_close tetikler
AUTO_CLOSE_TRIGGER_CODES: frozenset[str] = frozenset({
    "RED_ENERGY_SHOCK",
    "BTC_RISK_OFF_WARNING",
    "SYSTEMIC_RISK_RED",
    "LIQUIDITY_CRISIS",
    "MACRO_SHOCK_RED",
})


# ── Dataclass'lar ─────────────────────────────────────────────────────────────

@dataclass
class TFAlignment:
    label: str           # "strong" / "moderate" / "weak" / "divergent" / "none"
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    total_tfs: int = 0
    avg_score: float = 0.0
    detail: str = ""


@dataclass
class AgentTradeDecision:
    """Tick başına üretilen trade kararı — tüm katmanların sentezi."""
    pair: str
    side: TradeSignal          # "LONG" / "SHORT" / "CLOSE" / None
    confidence: float          # 0-100 (hesaplanmış)
    size_pct: float            # 0.0-1.5 (POSITION_SIZE çarpanı — mevcut ×0.6..×1.5 ile uyumlu)
    primary_tf: str
    tf_alignment: TFAlignment
    regime: str
    base_score: float          # raw final_score
    risk_action: str           # "HOLD" / "KILL_SWITCH" / "RISK_REDUCE" / "NO_POSITION_INCREASE"
    should_trade: bool
    block_reason: str          # Neden trade yok (boş = trade var)
    reasons: list[str] = field(default_factory=list)
    auto_close: bool = False   # Trigger'dan kaynaklanan acil kapanış
    auto_close_reason: str = ""
    # ── Controlled-Aggressive Decision Layer ──
    # Aggregator hard-block GEÇMİŞ adaylar için aggression_awareness modülünden
    # gelen profil; UI ve paper_trading_service tarafından okunur.
    command: AgentCommand = "WAIT"
    contradiction_score: int = 0
    aggression: AggressionContext | None = None
    sizing_decision: PositionSizingDecision | None = None
    timeframe_decision: TimeframeDecision | None = None
    stop_decision: StopDecision | None = None
    # ── FAZ 2: event risk + volatility + take profit plan + promotion audit ──
    event_risk_context: dict[str, Any] = field(default_factory=dict)
    volatility_context: dict[str, Any] = field(default_factory=dict)
    take_profit_plan: dict[str, Any] = field(default_factory=dict)
    controlled_aggressive_promotion: dict[str, Any] = field(default_factory=dict)


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _compute_tf_alignment(
    tf_signals: dict[str, Any],
    side: TradeSignal,
) -> TFAlignment:
    """tf_signals dict'inden multi-TF uyum derecesi hesapla.

    tf_signals formatı: {"1h": {"direction": "bullish", "score": 72.4}, ...}
    Hem `direction`/`score` hem `final_direction`/`final_score` anahtarlarını destekler.
    """
    if not tf_signals or side not in ("LONG", "SHORT"):
        return TFAlignment(label="none", detail="TF verisi yok veya LONG/SHORT değil")

    expected = "bullish" if side == "LONG" else "bearish"
    bullish = bearish = neutral = 0
    scores: list[float] = []

    for tf_data in tf_signals.values():
        if not isinstance(tf_data, dict):
            continue
        dir_ = (
            tf_data.get("direction")
            or tf_data.get("final_direction")
            or ""
        ).lower()
        raw_score = tf_data.get("score") or tf_data.get("final_score") or 0.0
        try:
            scores.append(float(raw_score))
        except (TypeError, ValueError):
            pass

        if dir_ in ("bullish", "strong_bullish"):
            bullish += 1
        elif dir_ in ("bearish", "strong_bearish"):
            bearish += 1
        else:
            neutral += 1

    total = bullish + bearish + neutral
    if total == 0:
        return TFAlignment(label="none", detail="TF sinyalleri boş/parselenamadı")

    avg = sum(scores) / len(scores) if scores else 0.0
    aligned  = bullish if expected == "bullish" else bearish
    opposed  = bearish if expected == "bullish" else bullish

    if opposed > aligned:
        label  = "divergent"
        detail = f"{aligned}/{total} uyumlu, {opposed} KARŞIT — DIVERGENT"
    elif aligned >= 3 and avg >= 65:
        label  = "strong"
        detail = f"{aligned}/{total} TF uyumlu, ort {avg:.0f}"
    elif aligned >= 2:
        label  = "moderate"
        detail = f"{aligned}/{total} TF uyumlu, ort {avg:.0f}"
    elif aligned == 1:
        label  = "weak"
        detail = f"1/{total} TF uyumlu, {neutral} nötr/karşıt"
    else:
        label  = "none"
        detail = "TF uyumu bulunamadı"

    return TFAlignment(
        label=label,
        bullish_count=bullish,
        bearish_count=bearish,
        neutral_count=neutral,
        total_tfs=total,
        avg_score=round(avg, 1),
        detail=detail,
    )


def _get_risk_action(
    regime: str,
    dqs_score: int | None,
    kill_switch: bool,
) -> str:
    """Lightweight risk verdict — tam risk engine çağırmadan kural tabanlı."""
    if kill_switch:
        return "KILL_SWITCH"
    if dqs_score is not None and dqs_score < MIN_DQS:
        return "KILL_SWITCH"   # Veri kalitesi yetersiz → sıfır işlem
    if regime == "CRISIS":
        return "RISK_REDUCE"
    if regime == "DEFENSIVE":
        return "NO_POSITION_INCREASE"
    return "HOLD"


def _check_trigger_auto_close(
    trigger_engine: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Kritik trigger tetiklenmiş mi?

    trigger_engine = {"trigger_severity": "RED", "confirmed_triggers": [...]}
    Şu an pasif — paper_decision_service entegrasyonunda aktifleşecek.
    """
    if not trigger_engine:
        return False, ""
    severity = (trigger_engine.get("trigger_severity") or "").upper()
    if severity != "RED":
        return False, ""
    confirmed = trigger_engine.get("confirmed_triggers") or []
    fired = {
        t.get("trigger_code")
        for t in confirmed
        if isinstance(t, dict) and t.get("trigger_code")
    }
    matched = fired & AUTO_CLOSE_TRIGGER_CODES
    if matched:
        return True, f"Kritik tetikleyici: {', '.join(sorted(matched))}"
    return False, ""


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def aggregate_agent_decision(
    sig: dict[str, Any],
    pair: str,
    *,
    base_mult_from_score: float = 1.0,
    dqs_score: int | None = None,
    kill_switch: bool = False,
    trigger_engine: dict[str, Any] | None = None,
) -> AgentTradeDecision:
    """
    Consensus sinyalini çok katmanlı analize tabi tutarak trade kararı döndür.

    Parametreler
    -----------
    sig                : _build_full_signal çıktısı — final_score, tf_signals,
                         raw_regime, final_direction, confluence, primary_tf, atr.
    pair               : "BTCUSD" / "XAUUSD" vb.
    base_mult_from_score: _consensus_to_action'ın döndürdüğü ham çarpan (0.6/1.0/1.5).
                         Aggregator bunu rejim + TF katmanlarıyla ezer/değiştirir.
    dqs_score          : Veri kalite skoru (0-100). None → gate pasif.
    kill_switch        : Risk engine kill_switch aktifse True.
    trigger_engine     : Trigger engine çıktısı — ilerleyen sprintte aktif.

    Çıktı
    -----
    AgentTradeDecision.side       → tick'teki `target` değişkeni olur
    AgentTradeDecision.size_pct   → tick'teki `base_mult` / `final_size_mult` olur
    AgentTradeDecision.auto_close → True ise tick açık pozisyonu acil kapatır
    """
    final_score     = float(sig.get("final_score") or 0.0)
    final_direction = (sig.get("final_direction") or "").lower()
    raw_regime      = (sig.get("raw_regime") or "NEUTRAL").upper()
    primary_tf      = str(sig.get("primary_tf") or "")
    tf_signals      = sig.get("tf_signals") or {}
    confluence      = sig.get("confluence") or {}
    conf_status     = (
        confluence.get("status") if isinstance(confluence, dict) else confluence
    ) or ""

    # ── 1. Ham yön tespiti (mevcut _consensus_to_action mantığını KORUR) ──────
    # side=None ise aggregator zaten çıktı vermez; downstream None olarak kalır.
    if final_direction == "bullish" and final_score >= MIN_SCORE_THRESHOLD:
        raw_side: TradeSignal = "LONG"
    elif final_direction == "bearish" and final_score <= (100 - MIN_SCORE_THRESHOLD):
        # Bearish score ölçeği: 100-MIN_SCORE_THRESHOLD → ~42 eşiği
        raw_side = "SHORT"
    else:
        raw_side = None

    # ── 2. Multi-TF Alignment ─────────────────────────────────────────────────
    tf_align = _compute_tf_alignment(tf_signals, raw_side)

    # ── 3. Risk verdict ───────────────────────────────────────────────────────
    risk_action = _get_risk_action(raw_regime, dqs_score, kill_switch)

    # ── 4. Trigger auto-close ─────────────────────────────────────────────────
    auto_close, auto_close_reason = _check_trigger_auto_close(trigger_engine)

    # ── 5. Confidence hesapla ─────────────────────────────────────────────────
    # Bearish sinyalde skor düşük olur (örn. 38) ama güven aynı ölçekte ölçülmeli.
    # SHORT için normalize: 100 - final_score → 38 → strength 62
    tf_delta = TF_ALIGNMENT_CONF_DELTA.get(tf_align.label, 0.0)
    if raw_side == "SHORT":
        normalized_score = 100.0 - final_score
    else:
        normalized_score = final_score
    confidence = min(100.0, max(0.0, normalized_score + tf_delta))

    # ── 6. Size çarpanı hesapla ───────────────────────────────────────────────
    # Temel: _consensus_to_action'ın hesapladığı çarpan (0.6 / 1.0 / 1.5)
    # Üzeri: rejim katsayısı × TF uyum katsayısı
    regime_m   = REGIME_BASE_MULT.get(raw_regime, 0.75)
    tf_m       = TF_ALIGNMENT_SIZE_MULT.get(tf_align.label, 0.75)
    size_pct   = base_mult_from_score * regime_m * tf_m

    # ── 7. Block kuralları ────────────────────────────────────────────────────
    reasons: list[str] = []
    block_reason = ""

    if risk_action == "KILL_SWITCH":
        dqs_info = f"DQS={dqs_score}" if dqs_score is not None else "risk_engine"
        block_reason = f"KILL_SWITCH ({dqs_info} / rejim={raw_regime})"
        raw_side = None
        size_pct = 0.0
    elif tf_align.label == "divergent":
        block_reason = f"TF karşıt: {tf_align.detail}"
        raw_side = None
        size_pct = 0.0
    elif raw_side is not None and confidence < MIN_TRADE_CONFIDENCE:
        block_reason = (
            f"Güven düşük: {confidence:.1f} < {MIN_TRADE_CONFIDENCE} "
            f"(skor {final_score:.1f}, TF={tf_align.label})"
        )
        raw_side = None
        size_pct = 0.0

    # ── 8. Reason toplama ─────────────────────────────────────────────────────
    if raw_side is not None:
        reasons.append(f"{raw_side} @ {final_score:.1f} ({final_direction})")
        reasons.append(f"TF uyum: {tf_align.label} · {tf_align.detail}")
        reasons.append(f"Rejim: {raw_regime} → {size_pct:.0%}")
        if risk_action != "HOLD":
            reasons.append(f"Risk kısıt: {risk_action}")
        if conf_status:
            reasons.append(f"Confluence: {conf_status}")
    else:
        reasons.append(f"PASS: {block_reason or 'skor/yön yetersiz'}")

    # ── 9. Aggression Awareness Layer ─────────────────────────────────────────
    # Hard-block geçmiş tüm adaylar için (LONG/SHORT) controlled-aggressive
    # profil çıkar; size_pct'yi agresifliğe göre yumuşatarak (aşağı yönlü) ezer.
    # Mevcut block_reason'lara DOKUNMAZ — sadece sizing/timeframe/stop planı.
    appetite_code = ""
    appetite_obj = sig.get("risk_appetite") or sig.get("appetite") or {}
    if isinstance(appetite_obj, dict):
        appetite_code = str(
            appetite_obj.get("status")
            or appetite_obj.get("code")
            or ""
        ).upper()
    elif isinstance(appetite_obj, str):
        appetite_code = appetite_obj.upper()

    contradiction = derive_contradiction_score(
        sig, tf_alignment_label=tf_align.label, regime=raw_regime,
    )

    aggression = score_aggression(
        sig,
        pair=pair,
        side=raw_side,
        tf_alignment_label=tf_align.label,
        regime=raw_regime,
        appetite=appetite_code,
        dqs_score=dqs_score,
        contradiction_score=contradiction,
    )

    # ── FAZ 2: event risk + volatility fallback (gerçek news/VIX wiring değil) ─
    # Aggregator artık sig + rejim + risk_appetite'tan fallback heuristik üretir.
    # Aşağıdaki sizing/promotion adımları bu gerçek değerleri kullanır.
    atr_value = float(sig.get("atr") or 0.0)
    price_hint = float(sig.get("last_price") or sig.get("price") or 0.0)
    event_ctx = derive_event_risk_fallback(
        pair, sig,
        regime=raw_regime, appetite=appetite_code,
        side=raw_side,
    )
    vol_ctx = derive_high_volatility_fallback(
        pair, sig, atr_value=atr_value, entry_price=price_hint,
    )

    # Event risk YÖNE TERS ise (örn. LONG BTCUSD + CRISIS): hard-block değil,
    # mevcut soft path'e bırak (size küçülür, sizing 0.65× ile ezilir).
    # Ama event risk DESTEKLİYORSA agg sizing içinde event_m=1.0 kalır.
    event_risk_high = bool(event_ctx.get("event_risk_high"))
    event_risk_direction = str(event_ctx.get("event_risk_direction") or "neutral_or_unknown")
    if event_risk_direction == "against_trade":
        # Sizing'de 0.65× çarpan uygulansın
        event_risk_for_sizing = True
    else:
        # Asset yöne destek veriyorsa veya bilinmiyorsa, sadece event_risk_high'a göre
        event_risk_for_sizing = event_risk_high
    high_volatility = bool(vol_ctx.get("high_volatility"))

    # Yön + blok yoksa → aggression-aware sizing devreye girer (sadece aşağı çekebilir)
    sizing_dec: PositionSizingDecision | None = None
    timeframe_dec: TimeframeDecision | None = None
    stop_dec: StopDecision | None = None
    tp_plan: dict[str, Any] = {}
    if raw_side in ("LONG", "SHORT") and not block_reason:
        sizing_dec = aggression_sizing(
            base_size_multiplier=base_mult_from_score,
            regime=raw_regime,
            aggression=aggression,
            contradiction_score=contradiction,
            event_risk_high=event_risk_for_sizing,
            high_volatility=high_volatility,
        )
        # Aggression-aware sonuç MEVCUT size_pct'den DAHA KÜÇÜK ise ezer
        # (controlled-aggressive guard: hiçbir zaman büyütmez).
        new_size = min(size_pct, sizing_dec.final_size_multiplier)
        if new_size != size_pct:
            reasons.append(
                f"Aggression={aggression.aggression_level} (score {aggression.aggression_score}) "
                f"→ size küçültüldü: {size_pct:.4f} → {new_size:.4f}"
            )
            size_pct = round(new_size, 4)

        timeframe_dec = choose_timeframe(aggression, primary_tf)
        # primary_tf score'undan support tahmini yapmıyoruz (None) — paper service
        # mevcut ATR-bazlı SL'i kullanır; bu sadece audit/UI bilgisi
        stop_dec = choose_stop(
            aggression,
            side=raw_side,
            price=price_hint,
            atr_value=atr_value,
            support_level=None,
        )

        # Take profit plan — entry/stop fiyatları aggregator zamanında bilinmediği
        # için stop_distance_pct üzerinden tahmini SL fiyatı kuruyoruz; paper
        # trading service açılış anında entry ile yeniden hesaplayabilir.
        if price_hint > 0 and stop_dec.stop_distance_pct > 0:
            estimated_stop_price = (
                price_hint * (1 - stop_dec.stop_distance_pct / 100.0)
                if raw_side == "LONG"
                else price_hint * (1 + stop_dec.stop_distance_pct / 100.0)
            )
        else:
            estimated_stop_price = 0.0
        tp_plan = build_take_profit_plan(
            aggression, stop_dec,
            side=raw_side,
            entry_price=price_hint,
            stop_price=estimated_stop_price,
        )

    command = pick_command(
        side=raw_side,
        confidence=confidence,
        aggression_level=aggression.aggression_level,
        contradiction_score=contradiction,
        block_reason=block_reason,
        risk_action=risk_action,
    )

    # ── Controlled-Aggressive Promotion ──────────────────────────────────────
    # AGGRESSIVE_WATCH komutu uygun koşullarda SCALP_LONG_SETUP'a yükseltilir
    # ve trade küçük boyutla açılır. Paper mode kontrol edilir.
    paper_mode = __import__("os").environ.get(
        "PAPER_TRADING_MODE", "controlled_aggressive",
    ).lower()
    # side_hint: command AGGRESSIVE_WATCH iken side=None olabilir; sig'den çek
    side_hint = raw_side
    if side_hint is None:
        if final_direction == "bullish" and final_score >= MIN_SCORE_THRESHOLD - 6.0:
            side_hint = "LONG"
        elif final_direction == "bearish" and final_score <= (100 - MIN_SCORE_THRESHOLD + 6.0):
            side_hint = "SHORT"
    promotion = maybe_promote_command(
        paper_mode=paper_mode,
        command=command,
        side_hint=side_hint,
        aggression=aggression,
        contradiction_score=contradiction,
        block_reason=block_reason,
        risk_action=risk_action,
        dqs_score=dqs_score,
        tf_alignment_label=tf_align.label,
        atr_value=atr_value,
        event_risk_direction=event_risk_direction,
    )
    if promotion.get("promoted"):
        # Promotion: command'ı SCALP'e çevir, side'ı geri kazandır, size cap uygula
        command = promotion["to"]
        if side_hint in ("LONG", "SHORT"):
            raw_side = side_hint
        # Promotion size cap (default 0.25) — daha küçükse sizing_dec'i kabul et
        promo_cap = float(promotion.get("new_size_cap") or 0.0)
        if promo_cap > 0:
            # Promotion sırasında size'ı en fazla cap kadar açar (sizing_dec'i yeniden hesapla)
            if sizing_dec is None:
                sizing_dec = aggression_sizing(
                    base_size_multiplier=base_mult_from_score,
                    regime=raw_regime,
                    aggression=aggression,
                    contradiction_score=contradiction,
                    event_risk_high=event_risk_for_sizing,
                    high_volatility=high_volatility,
                )
            promoted_size = min(promo_cap, sizing_dec.final_size_multiplier)
            size_pct = round(promoted_size, 4)
            # Soft block kalktı — trade açılır
            if block_reason:
                reasons.append(f"Promotion: '{block_reason}' soft-blok kaldırıldı")
                block_reason = ""
            reasons.append(promotion.get("reason", "Promotion uygulandı"))
            # Timeframe/stop/tp planını promotion ile yeniden hesapla (henüz yoksa)
            if timeframe_dec is None:
                timeframe_dec = choose_timeframe(aggression, primary_tf)
            if stop_dec is None:
                stop_dec = choose_stop(
                    aggression, side=raw_side, price=price_hint,
                    atr_value=atr_value, support_level=None,
                )
            if not tp_plan and stop_dec is not None and price_hint > 0:
                estimated_stop_price = (
                    price_hint * (1 - stop_dec.stop_distance_pct / 100.0)
                    if raw_side == "LONG"
                    else price_hint * (1 + stop_dec.stop_distance_pct / 100.0)
                )
                tp_plan = build_take_profit_plan(
                    aggression, stop_dec, side=raw_side,
                    entry_price=price_hint, stop_price=estimated_stop_price,
                )

    should_trade = (
        raw_side in ("LONG", "SHORT")
        and size_pct > 0.0
        and not block_reason
    )

    return AgentTradeDecision(
        pair=pair,
        side=raw_side,
        confidence=round(confidence, 1),
        size_pct=round(size_pct, 4),
        primary_tf=primary_tf,
        tf_alignment=tf_align,
        regime=raw_regime,
        base_score=round(final_score, 1),
        risk_action=risk_action,
        should_trade=should_trade,
        block_reason=block_reason,
        reasons=reasons,
        auto_close=auto_close,
        auto_close_reason=auto_close_reason,
        command=command,
        contradiction_score=contradiction,
        aggression=aggression,
        sizing_decision=sizing_dec,
        timeframe_decision=timeframe_dec,
        stop_decision=stop_dec,
        event_risk_context=event_ctx,
        volatility_context=vol_ctx,
        take_profit_plan=tp_plan,
        controlled_aggressive_promotion=promotion,
    )


# ── open_signal helper'ı ─────────────────────────────────────────────────────

def decision_to_open_signal_extras(decision: AgentTradeDecision) -> dict[str, Any]:
    """AgentTradeDecision'dan open_signal'a yazılacak controlled-aggressive blok.

    paper_trading_service yeni açılan pozisyonun open_signal'ına ekler:
      open_signal["aggression_context"]   — full aggression profili
      open_signal["agent_command"]        — komut etiketi
      open_signal["contradiction_score"]  — 0-100
      open_signal["timeframe_decision"]   — TF + holding + recheck
      open_signal["stop_decision"]        — agresif stop planı (referans)
    """
    out: dict[str, Any] = {
        "agent_command":       decision.command,
        "contradiction_score": decision.contradiction_score,
    }
    if decision.aggression is not None:
        out["aggression_context"] = aggression_to_dict(decision.aggression)
    if decision.timeframe_decision is not None:
        td = decision.timeframe_decision
        out["timeframe_decision"] = {
            "selected_timeframe":       td.selected_timeframe,
            "reason":                   td.reason,
            "max_holding_time":         td.max_holding_time,
            "recheck_interval_minutes": td.recheck_interval_minutes,
        }
    if decision.stop_decision is not None:
        sd = decision.stop_decision
        out["stop_decision"] = {
            "stop_distance_pct":  sd.stop_distance_pct,
            "atr_multiplier":     sd.atr_multiplier,
            "stop_type":          sd.stop_type,
            "why_this_stop":      sd.why_this_stop,
            "hard_invalidation":  list(sd.hard_invalidation),
        }
    if decision.sizing_decision is not None:
        szd = decision.sizing_decision
        out["sizing_decision"] = {
            "base_size_multiplier":       szd.base_size_multiplier,
            "aggression_multiplier":      szd.aggression_multiplier,
            "regime_multiplier":          szd.regime_multiplier,
            "contradiction_multiplier":   szd.contradiction_multiplier,
            "event_risk_multiplier":      szd.event_risk_multiplier,
            "volatility_multiplier":      szd.volatility_multiplier,
            "final_size_multiplier":      szd.final_size_multiplier,
            "reason":                     szd.reason,
        }
    # FAZ 2: TP planı, event risk + volatility fallback, promotion audit
    if decision.take_profit_plan:
        out["take_profit_plan"] = dict(decision.take_profit_plan)
    if decision.event_risk_context:
        out["event_risk_context"] = dict(decision.event_risk_context)
    if decision.volatility_context:
        out["volatility_context"] = dict(decision.volatility_context)
    if decision.controlled_aggressive_promotion:
        out["controlled_aggressive_promotion"] = dict(decision.controlled_aggressive_promotion)
    return out
