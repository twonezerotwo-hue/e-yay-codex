"""
FAZ 2 — Agent Hourly Thesis Service.

build_agent_hourly_thesis(snapshots) → thesis dict veya not_created dict.

Kurallar:
  • Deterministic, rule-based. LLM / AI provider çağrısı YOK.
  • Gerçek hourly snapshot yoksa thesis üretme.
  • Paper trading'e bağlanmaz; pozisyon açma/kapama yok.
  • Thesis içinde trade emri yok.
  • paper_trading_context.can_open_trade = False zorunlu.
  • decision_permission = NO_EXECUTION, execution_mode = PAPER_SAFE zorunlu.

Yorum kuralları (gerçek field yapılarına dayalı):
  confirmation_checklist[].met (bool/str)
  scenarios[].key (bull/base/bear) + probability_pct
  asymmetry.ratio + label
  asset_signals[].status (CONFIRMED/PENDING/NEUTRAL/BLOCKING)
  rotation.primary_flow + conviction
  mtf[asset][tf].structure (BULLISH/BEARISH/NEUTRAL)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

_SCHEMA_VERSION = "agent_hourly_thesis_v1"

# ── Bias seti sabitleri ───────────────────────────────────────────────────────

_BULLISH_REGIME = frozenset({"BULLISH", "RISK_ON", "EXPANSION"})
_BEARISH_REGIME = frozenset({"BEARISH", "RISK_OFF", "CONTRACTION"})
_HIGH_APPETITE  = frozenset({"HIGH", "RISK_ON"})
_LOW_APPETITE   = frozenset({"LOW", "RISK_OFF", "CAUTION", "DEFENSIVE"})

_CONFIRMED_STATUS = frozenset({"CONFIRMED", "BUY", "LONG", "BULLISH"})
_AVOID_STATUS     = frozenset({"BLOCKING", "SELL", "SHORT", "AVOID"})
_PENDING_STATUS   = frozenset({"PENDING", "WATCH", "MONITORING"})


# ── Yardımcı ──────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _str(val: Any, limit: int = 200) -> str:
    return str(val or "")[:limit]


# ── Piyasa görünümü ───────────────────────────────────────────────────────────

def _derive_primary_bias(regime: str, appetite: str) -> str:
    r = (regime or "").upper().strip()
    a = (appetite or "").upper().strip()

    if not r or r in {"UNKNOWN", "DATA_UNAVAILABLE"}:
        return "data_unavailable"

    if r in _BULLISH_REGIME:
        return "risk_on"

    if r in _BEARISH_REGIME:
        return "risk_off" if a in _LOW_APPETITE else "hedge"

    if r == "TRANSITIONING":
        if a in _LOW_APPETITE:
            return "hedge"
        if a in _HIGH_APPETITE:
            return "risk_on"
        return "mixed"  # MODERATE

    return "mixed"


def _build_market_view(report: dict, scenarios: list) -> dict[str, Any]:
    ml = report.get("macro_layer") or {}
    al = report.get("appetite_layer") or {}

    regime   = ml.get("regime", "UNKNOWN")
    appetite = al.get("status", "UNKNOWN")
    conf_pct = ml.get("confidence_pct", 0)
    try:
        confidence = round(float(conf_pct) / 100.0, 2)
    except (TypeError, ValueError):
        confidence = 0.0

    # Scenario özeti
    bull_pct: float = 0.0
    base_pct: float = 0.0
    bear_pct: float = 0.0
    for sc in scenarios:
        if not isinstance(sc, dict):
            continue
        key = (sc.get("key") or "").lower()
        try:
            pct = float(sc.get("probability_pct") or 0)
        except (TypeError, ValueError):
            pct = 0.0
        if key == "bull":
            bull_pct = pct
        elif key == "base":
            base_pct = pct
        elif key == "bear":
            bear_pct = pct

    max_pct = max(bull_pct, base_pct, bear_pct)
    if max_pct == 0:
        scenario_dominant = "unknown"
    elif max_pct == bull_pct:
        scenario_dominant = "bull"
    elif max_pct == base_pct:
        scenario_dominant = "base"
    else:
        scenario_dominant = "bear"

    scenario_summary = (
        f"bull={bull_pct:.0f}% / base={base_pct:.0f}% / bear={bear_pct:.0f}%"
        if max_pct > 0 else ""
    )

    # Asimetri
    asym = report.get("asymmetry") or {}
    asym_ratio  = asym.get("ratio")
    asym_label  = asym.get("label", "")
    asym_note   = f"ratio={asym_ratio} ({asym_label})" if asym_ratio is not None else ""

    return {
        "regime_view":        regime,
        "risk_appetite_view": appetite,
        "primary_bias":       _derive_primary_bias(regime, appetite),
        "confidence":         confidence,
        "scenario_dominant":  scenario_dominant,
        "scenario_summary":   scenario_summary,
        "asymmetry_ratio":    asym_ratio,
        "asymmetry_note":     asym_note,
    }


# ── Asset bias ────────────────────────────────────────────────────────────────

def _extract_mtf_structures(asset_code: str, mtf: dict) -> dict[str, str]:
    """
    Bir asset'in MTF dict'inden TF → structure eşleşmesini çıkarır.
    Sanity gate'in bias-vs-MTF kontrolü için thesis içine gömülür.
    """
    asset_mtf = mtf.get(asset_code) or {}
    structures: dict[str, str] = {}
    for tf, data in asset_mtf.items():
        if not isinstance(data, dict):
            continue
        struct = (data.get("structure") or "").upper()
        if struct and struct not in {"", "UNKNOWN"}:
            structures[tf] = struct
    return structures


def _mtf_contradictions(structures: dict[str, str]) -> list[str]:
    """
    Önceden hesaplanmış TF yapılarından çelişki listesi üretir.
    Tüm TF'ler aynı yöndeyse (BRENT gibi all-BEARISH) liste boş döner —
    bu tutarlı bir sinyal; sanity gate ayrıca bias uyumunu kontrol eder.
    """
    non_neutral = {tf: v for tf, v in structures.items()
                   if v not in {"NEUTRAL", "UNKNOWN"}}
    unique = set(non_neutral.values())
    if len(unique) <= 1:
        return []
    desc = ", ".join(f"{tf}:{v}" for tf, v in sorted(non_neutral.items()))
    return [f"MTF çelişkisi: {desc}"]


def _build_asset_biases(report: dict, mtf: dict) -> dict[str, dict[str, Any]]:
    sigs = report.get("asset_signals") or []
    result: dict[str, dict] = {}
    for sig in sigs:
        if not isinstance(sig, dict):
            continue
        code = sig.get("asset_code", "")
        if not code:
            continue

        status = (sig.get("status") or "").upper()
        reason = _str(sig.get("reason"), 200)

        if status in _CONFIRMED_STATUS:
            bias = "cautious_long"
        elif status in _AVOID_STATUS:
            bias = "avoid"
        elif status in _PENDING_STATUS:
            bias = "watch"
        else:
            bias = "neutral"

        # MTF yapılarını hem çelişki tespiti hem sanity gate için embed et
        mtf_structures = _extract_mtf_structures(code, mtf)
        contradictions = _mtf_contradictions(mtf_structures)

        result[code] = {
            "bias":           bias,
            "reason":         reason or "sinyal kaydı yok",
            "contradictions": contradictions,
            "mtf_structures": mtf_structures,   # sanity gate için
        }
    return result


# ── Teyit listesi ─────────────────────────────────────────────────────────────

def _build_confirmation_health(checklist: list) -> dict[str, Any]:
    passed = 0
    failed = 0
    failed_signals: list[str] = []

    for item in checklist:
        if not isinstance(item, dict):
            continue
        met = item.get("met")
        if isinstance(met, bool):
            is_met = met
        elif isinstance(met, str):
            is_met = met.strip().lower() == "true"
        else:
            continue

        if is_met:
            passed += 1
        else:
            failed += 1
            signal = _str(
                item.get("signal") or item.get("name") or item.get("label") or "",
                100,
            )
            if signal:
                failed_signals.append(signal)

    return {
        "passed":         passed,
        "failed":         failed,
        "total":          passed + failed,
        "failed_signals": failed_signals,
    }


# ── En güçlü nedenler ─────────────────────────────────────────────────────────

def _build_strongest_reasons(
    report: dict,
    rotation: dict,
    market_view: dict,
) -> list[str]:
    reasons: list[str] = []

    # Onaylı / bloklayan asset sinyaller
    for sig in report.get("asset_signals") or []:
        if not isinstance(sig, dict):
            continue
        status = (sig.get("status") or "").upper()
        if status in _CONFIRMED_STATUS | _AVOID_STATUS:
            code   = sig.get("asset_code", "")
            reason = _str(sig.get("reason"), 150)
            if reason:
                reasons.append(f"[{code}] {reason}")
        if len(reasons) >= 3:
            break

    # Makro özeti
    ml_summary = _str(
        (report.get("macro_layer") or {}).get("summary"), 150
    )
    if ml_summary:
        reasons.append(f"[MAKRO] {ml_summary}")

    # Rotation
    flow       = rotation.get("primary_flow") or ""
    conviction = rotation.get("conviction")
    synthesis  = _str(rotation.get("synthesis"), 100)
    if flow and conviction is not None:
        reasons.append(
            f"[ROTATION] {flow} (conviction={conviction}) — {synthesis}"
        )

    # Asimetri
    asym_note = market_view.get("asymmetry_note", "")
    if asym_note:
        asym_brief = _str(
            (report.get("asymmetry") or {}).get("brief"), 100
        )
        line = f"[ASİMETRİ] {asym_note}"
        if asym_brief:
            line += f" — {asym_brief}"
        reasons.append(line)

    return reasons[:5]


# ── Ana çelişkiler ────────────────────────────────────────────────────────────

def _build_main_contradictions(
    report: dict,
    asset_bias: dict,
    confirmation_health: dict,
) -> list[str]:
    contradictions: list[str] = []

    # Teyit listesi — karşılanmayan koşullar
    for sig in confirmation_health.get("failed_signals") or []:
        contradictions.append(f"[TEYIT] {sig}")

    # MTF çelişkileri (asset_bias'ta zaten hesaplandı)
    for code, data in asset_bias.items():
        for c in data.get("contradictions") or []:
            contradictions.append(f"[{code}] {c}")

    # Makro rejim ile asset bias çelişkisi
    regime = (
        (report.get("macro_layer") or {}).get("regime", "")
    ).upper()
    if regime in _BEARISH_REGIME:
        for code, data in asset_bias.items():
            if data.get("bias") == "cautious_long":
                contradictions.append(
                    f"[{code}] macro {regime} iken cautious_long — ihtiyatlı izle"
                )
    elif regime in _BULLISH_REGIME:
        for code, data in asset_bias.items():
            if data.get("bias") == "avoid":
                contradictions.append(
                    f"[{code}] macro {regime} iken avoid sinyali — doğrula"
                )

    return contradictions[:6]


# ── Pozisyon bağlamı (salt-okunur) ───────────────────────────────────────────

def _extract_positions_context(paper_trading: dict) -> list[dict[str, Any]]:
    """
    Açık pozisyonları READ-ONLY olarak bağlam için döndürür.
    Herhangi bir trading aksiyonu yok.
    """
    positions = paper_trading.get("open_positions") or []
    result: list[dict] = []
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        result.append({
            "pair":    pos.get("pair") or pos.get("asset") or "",
            "pnl_pct": pos.get("pnl_pct"),
            "note":    "context_only — no action taken",
        })
    return result


# ── Veri kalitesi değerlendirmesi ─────────────────────────────────────────────

def _assess_data_quality(snapshots: list[dict]) -> dict[str, Any]:
    if not snapshots:
        return {"status": "fail", "notes": ["no_snapshots"]}

    latest  = snapshots[-1]
    missing = [
        f for f in ("report", "rotation", "mtf")
        if not latest.get(f)
    ]
    notes: list[str] = []

    if missing:
        notes.append(f"missing_fields: {missing}")
        status = "degraded" if len(missing) < 3 else "fail"
    else:
        status = "pass"

    # Kaynak snapshot'ın kendi data_quality notlarını ekle
    for note in ((latest.get("data_quality") or {}).get("notes") or []):
        notes.append(f"source_snapshot: {note}")

    return {"status": status, "notes": notes}


# ── Public API ────────────────────────────────────────────────────────────────

def build_agent_hourly_thesis(snapshots: list[dict]) -> dict[str, Any]:
    """
    Gerçek hourly snapshot listesinden deterministic thesis üretir.

    • LLM / AI provider çağrısı YOK.
    • Paper trading state değiştirilmez.
    • Snapshot yoksa veya gerçek veri eksikse not_created döner.

    Args:
        snapshots: load_recent_hourly_snapshots() çıktısı (boş olabilir)

    Returns:
        thesis dict  — schema_version="agent_hourly_thesis_v1"
        not_created  — {"status": "not_created", "reason": ...}
    """
    if not snapshots:
        return {
            "status": "not_created",
            "reason": "no_real_hourly_snapshots",
        }

    latest       = snapshots[-1]
    report       = latest.get("report") or {}
    rotation     = latest.get("rotation") or {}
    mtf          = latest.get("mtf") or {}
    paper_trading = latest.get("paper_trading") or {}

    # En az report veya rotation veya mtf gerekli
    if not report and not rotation and not mtf:
        return {
            "status": "not_created",
            "reason": "no_real_hourly_snapshots",
        }

    source_ids: list[str] = [
        s["snapshot_id"] for s in snapshots if s.get("snapshot_id")
    ]

    scenarios = report.get("scenarios") or []
    checklist = report.get("confirmation_checklist") or []

    market_view          = _build_market_view(report, scenarios)
    asset_bias           = _build_asset_biases(report, mtf)
    confirmation_health  = _build_confirmation_health(checklist)
    strongest_reasons    = _build_strongest_reasons(report, rotation, market_view)
    main_contradictions  = _build_main_contradictions(
        report, asset_bias, confirmation_health
    )
    watchlist            = [
        code for code, d in asset_bias.items() if d.get("bias") == "watch"
    ]
    positions_under_review = _extract_positions_context(paper_trading)
    data_quality           = _assess_data_quality(snapshots)

    thesis: dict[str, Any] = {
        "thesis_id":             str(uuid.uuid4()),
        "created_at":            _utc_now_iso(),
        "schema_version":        _SCHEMA_VERSION,
        "decision_permission":   "NO_EXECUTION",
        "execution_mode":        "PAPER_SAFE",
        "source_snapshot_ids":   source_ids,
        "lookback_hours":        len(snapshots),
        "market_view":           market_view,
        "asset_bias":            asset_bias,
        "confirmation_health":   confirmation_health,
        "strongest_reasons":     strongest_reasons,
        "main_contradictions":   main_contradictions,
        "watchlist":             watchlist,
        "positions_under_review": positions_under_review,
        "data_quality":          data_quality,
        "paper_trading_context": {
            "permission":     "context_only",
            "can_open_trade": False,
            "reason":         "FAZ 2 thesis only; not connected to paper trading",
        },
    }

    # FAZ 2.5 — Sanity / quality gate (lazy import — döngüsel bağımlılık yok)
    from app.services.agent_thesis_sanity import validate_agent_thesis  # noqa: PLC0415
    thesis["thesis_sanity"] = validate_agent_thesis(thesis)

    return thesis
