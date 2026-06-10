"""GET /api/v1/dashboard/panel-audit — panel tutarlılık denetimi.

Canonical state üzerinde otomatik kontroller koşar; eksik/çelişkili veriyi
issue listesi olarak döner. Karar motoruna dokunmaz, sadece okur.

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.market_state.canonical_state import get_cached_state

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _issue(panel: str, severity: str, issue: str, recommendation: str = "") -> dict[str, Any]:
    return {"panel": panel, "severity": severity, "issue": issue, "recommendation": recommendation}


@router.get("/panel-audit")
def get_panel_audit() -> JSONResponse:
    """Canonical state üzerinde tutarlılık kontrolleri."""
    try:
        state, _ = get_cached_state(force_refresh=False)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(content={
            "overall_status": "ERROR",
            "issues": [{
                "panel": "canonical_state",
                "severity": "ERROR",
                "issue":   f"{type(exc).__name__}: {exc}",
                "recommendation": "Pipeline error — check warnings",
            }],
            "paper_safe": True,
            "execution_side_effects": "NO_EXECUTION",
        })

    issues: list[dict[str, Any]] = []

    # 1. Pipeline warning'leri otomatik issue'ya çevir
    for w in state.warnings or []:
        issues.append(_issue("pipeline", "WARNING", f"Pipeline warning: {w}",
                             "Bağımlı modülün hata logunu kontrol et"))

    # 2. Asset signals var ama module_health.signals LOW mu?
    signals_health = state.module_health.get("signals", {}).get("score", "")
    if state.asset_signals and signals_health == "LOW":
        issues.append(_issue("situation_room", "WARNING",
                             "module_health.signals=LOW olduğu halde asset_signals dolu",
                             "Blocking sayısını panelde belirgin göster"))

    # 3. DQS düşükken trade candidate var mı?
    dqs = state.data_quality.get("score")
    if (state.paper_trading and isinstance(state.paper_trading, dict)
            and state.paper_trading.get("open_positions")):
        if dqs is not None and dqs < 55:
            issues.append(_issue("paper_trading", "ERROR",
                                 f"Açık pozisyon var ama DQS={dqs:.0f} (eşik 55)",
                                 "RiskGate BLOCK uyarısını panele bas; learning'e işle"))

    # 4. Kill switch aktif ama risk_gate panelinde gösteriliyor mu?
    rg = state.risk_gate or {}
    if rg.get("kill_switch_active") and rg.get("status") != "BLOCK":
        issues.append(_issue("risk_gate", "ERROR",
                             "Kill switch aktif ama gate.status BLOCK değil",
                             "build_risk_gate map'ini gözden geçir"))

    # 5. snapshot_id panellerde tutarlı mı? (canonical state tek snapshot_id veriyor → OK)
    if not state.snapshot_id or not state.snapshot_id.startswith("dash::"):
        issues.append(_issue("canonical_state", "ERROR",
                             "Geçersiz snapshot_id",
                             "_snapshot_id helper'ı kontrol et"))

    # 6. Risk gate yokken paper trade gösteriliyor mu?
    if state.paper_trading and not rg:
        issues.append(_issue("paper_trading", "ERROR",
                             "Paper trading state var ama risk_gate ViewModel yok",
                             "canonical_state.build_canonical_state risk_gate üretmeli"))

    # 7. Agent votes yokken decision gösteriliyor mu?
    decision = (state.regime_report or {}).get("decision")
    if decision and not state.agent_votes:
        issues.append(_issue("decision", "WARNING",
                             "Karar var ama agent_votes boş",
                             "build_agent_votes en az RiskAgent + DataQualityAgent üretmeli"))

    # 8. Scenario panelinde "olasılık" gibi yanlış temsil var mı? (label kontratı)
    # Canonical state senaryo wording'ini etkilemez; bu kontrol değişen UI label'larını
    # düzenli denetlemek için placeholder olarak kalır.

    # Genel status — en yüksek severity
    severities = {i["severity"] for i in issues}
    if "ERROR" in severities:
        overall = "ERROR"
    elif "WARNING" in severities:
        overall = "WARNING"
    else:
        overall = "OK"

    return JSONResponse(content={
        "overall_status":         overall,
        "issues":                 issues,
        "snapshot_id":            state.snapshot_id,
        "paper_safe":             True,
        "execution_side_effects": "NO_EXECUTION",
    })


__all__ = ["router"]
