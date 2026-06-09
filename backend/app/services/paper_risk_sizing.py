"""
FAZ 12 — Paper Risk Sizing.

compute_paper_risk_size(size_usd, signal_snapshot, side) -> tuple[float, dict]

Öğrenme verisi üretimi için paper trading boyutunu kontrollü artırır.
Hard gate / karar motoru / SL/TP / anomaly guard DEĞİŞMEZ.
Yalnızca hard gate geçtikten sonra çağrılır (inside _route_new_open_signal).

Sabitler:
  _BASE_BOOST  = 1.20  (+%20 taban artış — paper learning)
  _HIGH_BOOST  = 1.15  (high conviction ek +%15)
  _LOW_REDUCE  = 0.85  (low conviction -%15)
  _ADV_EACH    = 0.90  (advanced tech uyarısı başına -%10)
  _ADV_FLOOR   = 0.70  (advanced tech birleşik indirim tabanı)
  _PAPER_MAX   = 37_500.0  (mevcut max cap = POSITION_SIZE×1.5, sabit)

Güvenceler:
  • Hard gate değişmez — bu fonksiyon yalnızca gate geçince çalışır.
  • Max position cap aşılmaz (_PAPER_MAX).
  • Soft modifier'lar block/reject üretmez.
  • Decision motoru (side/direction/final_score) etkilenmez.
"""
from __future__ import annotations

_BASE_BOOST  = 1.20   # taban paper learning artışı
_HIGH_BOOST  = 1.15   # high conviction ek boost
_LOW_REDUCE  = 0.85   # low conviction indirim
_ADV_EACH    = 0.90   # advanced tech uyarısı başına çarpan
_ADV_FLOOR   = 0.70   # advanced tech indirim tabanı (bu altına düşülmez)
_PAPER_MAX   = 37_500.0  # orijinal max cap (POSITION_SIZE * 1.5)
_PAPER_BASE  = 25_000.0  # referans baz (sadece multiplier hesabı için)


def _conviction_tier(signal_snapshot: dict, side: str) -> tuple[str, list[str]]:
    """
    Sinyalin conviction katmanını belirle.

    Returns:
        (tier, reasons)
        tier = "high" | "medium" | "low"
    """
    score       = signal_snapshot.get("final_score")
    confluence  = signal_snapshot.get("confluence") or {}
    conf_status = (
        confluence.get("status") if isinstance(confluence, dict) else None
    ) or ""
    contradiction = signal_snapshot.get("contradiction_score")

    # Numeric güvenlik
    score_f = float(score) if score is not None else 50.0
    contra_f = float(contradiction) if contradiction is not None else 0.0

    event_ctx = signal_snapshot.get("event_risk_context") or {}
    event_high = bool(event_ctx.get("event_risk_high"))

    reasons: list[str] = []

    # ── High conviction ──────────────────────────────────────────────────────
    if (
        score_f >= 70.0
        and conf_status == "aligned"
        and contra_f < 30.0
    ):
        reasons.append(f"score={score_f:.1f}>=70")
        reasons.append("confluence=aligned")
        if contra_f < 30.0:
            reasons.append(f"contradiction={contra_f:.1f}<30")
        return "high", reasons

    # ── Low conviction ───────────────────────────────────────────────────────
    # Düşük skor + zayıf uyum + event/contradiction baskısı
    if (
        50.0 <= score_f <= 60.0
        and conf_status not in ("aligned",)
        and (event_high or contra_f > 50.0)
    ):
        reasons.append(f"score={score_f:.1f} in [50,60]")
        if conf_status:
            reasons.append(f"confluence={conf_status}")
        if event_high:
            reasons.append("event_risk_high")
        if contra_f > 50.0:
            reasons.append(f"contradiction={contra_f:.1f}>50")
        return "low", reasons

    return "medium", [f"score={score_f:.1f}", f"confluence={conf_status}"]


def _advanced_tech_modifiers(signal_snapshot: dict, side: str) -> list[str]:
    """
    Advanced technical context'e göre soft modifier listesi döndür.
    Her modifier -%10 demek (birleşik _ADV_FLOOR tabanıyla kısıtlı).
    Block/reject üretmez.

    Returns:
        list of modifier strings (boş → uyarı yok)
    """
    adv = signal_snapshot.get("advanced_technical") or {}
    if not adv.get("available"):
        return []

    mods: list[str] = []
    side_up = (side or "").upper()

    # Volume weak
    if adv.get("volume_confirmation") in ("weak", "warning"):
        mods.append(f"volume={adv.get('volume_confirmation')}")

    # EMA stack yönü karşı
    ema = adv.get("ema_stack") or ""
    if side_up == "LONG" and ema == "bearish":
        mods.append("ema_stack=bearish(against_long)")
    elif side_up == "SHORT" and ema == "bullish":
        mods.append("ema_stack=bullish(against_short)")

    # VWAP yönü karşı
    vwap = adv.get("vwap_position") or ""
    if side_up == "LONG" and vwap == "below":
        mods.append("vwap=below(against_long)")
    elif side_up == "SHORT" and vwap == "above":
        mods.append("vwap=above(against_short)")

    # Candle close teyidi yok
    candle = adv.get("candle_close_confirmation") or ""
    if candle in ("fakeout", "no_breakout"):
        mods.append(f"candle_close={candle}")

    return mods


def compute_paper_risk_size(
    size_usd: float,
    signal_snapshot: dict,
    side: str,
) -> tuple[float, dict]:
    """
    Paper trading boyutunu öğrenme için kontrollü artır.

    Args:
        size_usd:         Mevcut hesaplanmış pozisyon büyüklüğü (USD).
        signal_snapshot:  Sinyal dict (final_score, confluence, advanced_technical vs.).
        side:             "LONG" | "SHORT"

    Returns:
        (adjusted_size_usd, paper_risk_sizing_context)
    """
    base_before = round(size_usd / _PAPER_BASE, 4)

    # ── 1. Taban artış (+%20) ────────────────────────────────────────────────
    after = size_usd * _BASE_BOOST

    # ── 2. Conviction katmanı ────────────────────────────────────────────────
    tier, tier_reasons = _conviction_tier(signal_snapshot, side)
    soft_mods: list[str] = [f"conviction={tier}"] + tier_reasons

    if tier == "high":
        after *= _HIGH_BOOST
        soft_mods.append(f"high_conviction_boost=+{(_HIGH_BOOST-1)*100:.0f}%")
    elif tier == "low":
        after *= _LOW_REDUCE
        soft_mods.append(f"low_conviction_reduce=-{(1-_LOW_REDUCE)*100:.0f}%")

    # ── 3. Advanced technical soft modifier'lar ──────────────────────────────
    adv_mods = _advanced_tech_modifiers(signal_snapshot, side)
    if adv_mods:
        # Birleşik çarpan (her uyarı ×0.90, minimum _ADV_FLOOR)
        raw_adv = _ADV_EACH ** len(adv_mods)
        clamped_adv = max(raw_adv, _ADV_FLOOR)
        after *= clamped_adv
        for m in adv_mods:
            soft_mods.append(f"adv_tech:{m}")
        soft_mods.append(
            f"adv_combined={clamped_adv:.3f}"
            + (" [floor]" if raw_adv < _ADV_FLOOR else "")
        )

    # ── 4. Max cap ────────────────────────────────────────────────────────────
    capped = after > _PAPER_MAX
    after = min(after, _PAPER_MAX)
    if capped:
        soft_mods.append(f"capped_at={_PAPER_MAX:.0f}")

    adjusted = round(after, 2)
    base_after = round(adjusted / _PAPER_BASE, 4)

    context: dict = {
        "base_multiplier_before": base_before,
        "base_multiplier_after":  base_after,
        "conviction_tier":        tier,
        "soft_modifiers":         soft_mods,
        "final_size_usd":         adjusted,
        "reason":                 "paper risk increased for learning, hard gates preserved",
    }

    return adjusted, context
