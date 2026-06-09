"""
FAZ 2.5 — Agent Thesis Sanity / Quality Gate.

validate_agent_thesis(thesis: dict) -> dict

Thesis'i güvenlik + mantık + veri kalitesi açısından kontrol eder.

Kurallar:
  1.  Thesis yok / not_created → fail
  2.  source_snapshot_ids boş → critical
  3.  decision_permission ≠ NO_EXECUTION → critical
  4.  execution_mode ≠ PAPER_SAFE → critical
  5.  can_open_trade = True → critical
  6.  cautious_long + all MTF BEARISH → critical
  7.  avoid + all MTF BULLISH → warning
  8.  primary_bias risk_on + confirmation oranı < 0.5 → warning
  9.  confidence > 0.75 + main_contradictions dolu → warning
  10. asymmetry_ratio > 5 + data_quality ≠ pass → warning
  11. Pozisyonlar zararda + primary_bias risk_on → warning

Garantiler:
  • Thesis'i değiştirmez.
  • Paper trading'e bağlanmaz.
  • Snapshot üretmez / kaydetmez.
  • Mock / fake veri kullanmaz.
"""
from __future__ import annotations

from typing import Any

_MAX_ISSUES = 10


# ── Issue yardımcıları ────────────────────────────────────────────────────────

def _issue(severity: str, code: str, asset: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "asset": asset, "message": message}


def _critical(code: str, asset: str, message: str) -> dict[str, Any]:
    return _issue("critical", code, asset, message)


def _warning(code: str, asset: str, message: str) -> dict[str, Any]:
    return _issue("warning", code, asset, message)


# ── Sanity kontrolleri ────────────────────────────────────────────────────────

def _check_security(thesis: dict, issues: list) -> None:
    """Kural 2-5: Güvenlik sabitleri."""

    # Kural 2
    if not thesis.get("source_snapshot_ids"):
        issues.append(_critical(
            "empty_source_snapshot_ids", "",
            "source_snapshot_ids boş — gerçek veri kaynağı yok",
        ))

    # Kural 3
    if thesis.get("decision_permission") != "NO_EXECUTION":
        issues.append(_critical(
            "invalid_decision_permission", "",
            f"decision_permission={thesis.get('decision_permission')!r} — NO_EXECUTION olmalı",
        ))

    # Kural 4
    if thesis.get("execution_mode") != "PAPER_SAFE":
        issues.append(_critical(
            "invalid_execution_mode", "",
            f"execution_mode={thesis.get('execution_mode')!r} — PAPER_SAFE olmalı",
        ))

    # Kural 5
    ptc = thesis.get("paper_trading_context") or {}
    if ptc.get("can_open_trade") is True:
        issues.append(_critical(
            "can_open_trade_true", "",
            "can_open_trade True — thesis paper trading'e otomatik bağlanamaz",
        ))


def _check_bias_vs_mtf(asset_bias: dict, issues: list) -> None:
    """Kural 6-7: Asset bias ile MTF yapısı tutarlılığı."""
    for code, data in asset_bias.items():
        structs: dict[str, str] = data.get("mtf_structures") or {}
        non_neutral = [
            v for v in structs.values()
            if v and v not in ("NEUTRAL", "UNKNOWN")
        ]

        if non_neutral:
            # Kural 6: cautious_long / long + all BEARISH → critical
            if data.get("bias") in ("cautious_long", "long"):
                if all(v == "BEARISH" for v in non_neutral):
                    tf_str = "/".join(sorted(structs.keys()))
                    issues.append(_critical(
                        "long_bias_against_all_bearish_mtf", code,
                        f"Asset cautious_long ama {tf_str} MTF tamamı bearish.",
                    ))

            # Kural 7: avoid + all BULLISH → warning
            elif data.get("bias") == "avoid":
                if all(v == "BULLISH" for v in non_neutral):
                    tf_str = "/".join(sorted(structs.keys()))
                    issues.append(_warning(
                        "avoid_bias_against_all_bullish_mtf", code,
                        f"Asset avoid ama {tf_str} MTF tamamı bullish — sinyal tutarsız.",
                    ))

        # ── FAZ 11 — Advanced technical bias çelişkileri ────────────────────
        # asset_bias[code].advanced_technical varsa (thesis builder eklerse)
        # cautious_long ama EMA bearish + structure bearish ise critical
        adv = data.get("advanced_technical") or {}
        if adv:
            ema    = str(adv.get("ema_stack") or "unavailable")
            ms     = str(adv.get("market_structure") or "unavailable")
            vol_cf = str(adv.get("volume_confirmation") or "unavailable")
            candle = str(adv.get("candle_close_confirmation") or "unavailable")
            bias   = data.get("bias")

            # cautious_long / long + EMA bearish + structure LH_LL → critical
            if bias in ("cautious_long", "long") and ema == "bearish" and ms == "LH_LL":
                issues.append(_critical(
                    "long_bias_against_ema_and_structure", code,
                    f"{bias} bias ama EMA bearish + structure LH/LL — çelişki.",
                ))

            # bullish thesis bias + volume confirmation yok/weak → warning
            if bias in ("long", "cautious_long") and vol_cf in ("weak", "warning"):
                issues.append(_warning(
                    "bullish_bias_without_volume_confirmation", code,
                    f"{bias} bias ama hacim teyidi {vol_cf} — düşük güven.",
                ))

            # breakout senaryosu ama candle close fakeout → warning
            if candle == "fakeout":
                issues.append(_warning(
                    "breakout_candle_close_failed", code,
                    "Candle close teyidi yok (fakeout). Breakout güvenilmez.",
                ))


def _check_logic(thesis: dict, issues: list) -> None:
    """Kural 8-11: Mantık ve kalite kontrolleri."""
    mv = thesis.get("market_view") or {}
    ch = thesis.get("confirmation_health") or {}
    primary_bias = mv.get("primary_bias", "")
    confidence   = 0.0
    try:
        confidence = float(mv.get("confidence") or 0)
    except (TypeError, ValueError):
        pass

    # Kural 8: risk_on + düşük teyit oranı
    if primary_bias == "risk_on":
        total  = ch.get("total", 0)
        passed = ch.get("passed", 0)
        if total > 0 and (passed / total) < 0.5:
            issues.append(_warning(
                "risk_on_bias_low_confirmation", "",
                f"primary_bias risk_on ama teyit oranı düşük ({passed}/{total})",
            ))

    # Kural 9: yüksek confidence + çelişkiler dolu
    contradictions = thesis.get("main_contradictions") or []
    if confidence > 0.75 and contradictions:
        issues.append(_warning(
            "high_confidence_with_contradictions", "",
            f"confidence={confidence} yüksek ama {len(contradictions)} çelişki var",
        ))

    # Kural 10: yüksek asimetri + bozulmuş veri kalitesi
    asym_ratio = mv.get("asymmetry_ratio")
    dq = thesis.get("data_quality") or {}
    if asym_ratio is not None:
        try:
            ratio_val = float(asym_ratio)
        except (TypeError, ValueError):
            ratio_val = 0.0
        if ratio_val > 5.0 and dq.get("status") != "pass":
            issues.append(_warning(
                "high_asymmetry_degraded_data", "",
                f"asymmetry_ratio={asym_ratio} yüksek ama data_quality={dq.get('status')!r} "
                "— sonuç güvenilir olmayabilir",
            ))

    # Kural 11: pozisyonlar zararda + thesis risk_on
    pur = thesis.get("positions_under_review") or []
    if pur:
        pnl_values = [
            p["pnl_pct"] for p in pur
            if isinstance(p, dict) and p.get("pnl_pct") is not None
        ]
        if pnl_values and all(v < -1.0 for v in pnl_values):
            if primary_bias == "risk_on":
                issues.append(_warning(
                    "positions_in_loss_vs_risk_on_thesis", "",
                    "Açık pozisyonlar zararda ama thesis risk_on — ihtiyatlı izle",
                ))


# ── Public API ────────────────────────────────────────────────────────────────

def validate_agent_thesis(thesis: dict) -> dict[str, Any]:
    """
    Thesis'i sanity / quality gate ile değerlendirir.

    Returns:
        {
            "status":          "pass" | "degraded" | "fail",
            "score":           0-100,
            "issues":          [{"severity", "code", "asset", "message"}, ...],
            "safe_for_context": bool
        }
    """
    # Kural 1: thesis yok / not_created
    if not thesis or thesis.get("status") == "not_created":
        return {
            "status":           "fail",
            "score":            0,
            "issues":           [_critical("no_thesis", "", "Thesis yok veya üretilemedi")],
            "safe_for_context": False,
        }

    issues: list[dict] = []

    _check_security(thesis, issues)
    _check_bias_vs_mtf(thesis.get("asset_bias") or {}, issues)
    _check_logic(thesis, issues)

    # ── Sonuç ─────────────────────────────────────────────────────────────────
    has_critical = any(i["severity"] == "critical" for i in issues)

    score = 100
    for issue in issues:
        score -= 20 if issue["severity"] == "critical" else 5
    score = max(0, score)

    if has_critical:
        status = "fail"
    elif issues:
        status = "degraded"
    else:
        status = "pass"

    return {
        "status":           status,
        "score":            score,
        "issues":           issues[:_MAX_ISSUES],
        "safe_for_context": not has_critical,
    }
