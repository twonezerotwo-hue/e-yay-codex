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
    )
