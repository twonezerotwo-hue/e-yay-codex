"""
E-YAY / BrainChain Paper Intelligence Console — standalone Gradio admin panel.

Safety: PAPER_ONLY | REPLAY_ONLY | NO_EXECUTION | LOCAL_DASHBOARD

Name:     E-YAY / BrainChain Paper Intelligence Console
Subtitle: Local paper-safe replay, source diagnostics, risk control, and owner briefing.

Run:
    python -m backend.app.dashboard.gradio_dashboard

Port: 7867  Host: 127.0.0.1  share=False
No FastAPI mount. No live data. No trading. No execution.

Tabs:
   1.  Executive Command Center
   2.  Data Sources & Provider Layer
   3.  Data Integrity Gate
   4.  Ingestion Pipeline
   5.  Snapshot Store
   6.  Snapshot Replay
   7.  Trigger & Risk Engine
   8.  Source & Contract Diagnostics
   9.  Claim Validation & Geopolitical Engine  [ROADMAP]
  10.  Strategic Asset Engines               [ROADMAP]
  11.  CEO / Owner Brief
  12.  Learning & Audit
  13.  Validation & Backup
  14.  Roadmap / Next Task

AI karar vermez. AI açıklar.
Decision Core deterministiktir. Risk Engine final kapıdır.
Execution varsayılan OFF / NO_EXECUTION'dır.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import gradio as gr

    _GRADIO_AVAILABLE = True
except ImportError:
    _GRADIO_AVAILABLE = False

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NEXT_TASK_FILE = _REPO_ROOT / "NEXT_TASK.md"
_CLEAN_BACKUPS_DIR = _REPO_ROOT / "clean_backups"
_SUBPROCESS_TIMEOUT = 120

_SAFETY_LABEL = "PAPER_ONLY | REPLAY_ONLY | NO_EXECUTION | LOCAL_DASHBOARD"

_SNAPSHOT_COLUMNS = [
    "snapshot_id",
    "created_at",
    "report_type",
    "mode",
    "execution_mode",
    "source_registry_version",
    "feature_registry_version",
]

_SOURCE_DIAG_CHOICES = [
    "contract_coverage_drift",
    "rolling_bundle_coverage_drift",
    "group_coverage_drift",
    "surface_count_drift",
    "metadata_completeness_drift",
    "naming_contract_drift",
    "contract_signature_drift",
    "contract_field_set_drift",
    "full_surface_response_field_set_consistency",
]

_SOURCE_DIAG_METHOD: dict[str, str] = {
    "contract_coverage_drift": "build_source_diagnostics_contract_coverage_drift",
    "rolling_bundle_coverage_drift": "build_rolling_source_diagnostic_bundle_coverage_drift",
    "group_coverage_drift": "build_source_diagnostic_group_coverage_drift",
    "surface_count_drift": "build_source_diagnostic_surface_count_drift",
    "metadata_completeness_drift": "build_source_diagnostic_metadata_completeness_drift",
    "naming_contract_drift": "build_source_diagnostic_naming_contract_drift",
    "contract_signature_drift": "build_source_diagnostic_contract_signature_drift",
    "contract_field_set_drift": "build_source_diagnostic_contract_field_set_drift",
    "full_surface_response_field_set_consistency": "build_full_surface_response_field_set_consistency",
}

_STOOQ_FIXTURE_CSV = """\
Date,Open,High,Low,Close,Volume
2026-05-27,483.50,488.00,482.00,486.75,61234000
"""

_STOOQ_ASSET_CHOICES = ["QQQ", "HYG", "JNK", "FXI"]

# ---------------------------------------------------------------------------
# Architecture reference constants (static display — no fake data)
# ---------------------------------------------------------------------------

_DQS_FORMULA_MD = """\
### Data Quality Score (DQS) Formula

```
DQS =  0.25 × Freshness
     + 0.20 × Source Tier
     + 0.20 × Cross-Provider Agreement
     + 0.15 × Completeness
     + 0.10 × Timestamp Integrity
     + 0.10 × Anomaly Consistency
```

| Score Range | Decision |
|---|---|
| 90 – 100 | ✅ `PASS` |
| 70 – 89  | 🟡 `DEGRADED_PASS` |
| 50 – 69  | 🟠 `LIMITED_ANALYSIS_ONLY` |
| 0  – 49  | 🔴 `FAIL_NO_DECISION` |

> **Status:** PARTIAL — `Freshness`, `Source Tier`, `Completeness`, and `Timestamp Integrity`
> are computed in `MarketSnapshotService`. Cross-provider agreement and anomaly consistency
> are **ROADMAP**.
"""

_DQS_FIELDS_MD = """\
### Expected Fields Per Snapshot Record

| Field | Type | Notes |
|---|---|---|
| `asset_symbol` | str | AssetCode enum value |
| `value` | float | Market value |
| `unit` | str | Must match AssetDefinition.unit exactly |
| `source_name` | str | Data source identifier |
| `source_tier` | str | primary / secondary / fallback / reference |
| `observed_at` | datetime (UTC) | When value was observed at source |
| `available_at` | datetime (UTC) | When data became available |
| `stored_at` | datetime (UTC) | When stored in snapshot |
| `freshness_seconds` | int | Age at storage time |
| `is_stale` | bool | Staleness flag |
| `fallback_used` | bool | Whether fallback path was used |
| `data_quality_score` | float (0–100) | DQS total |
| `raw_payload_ref` | str | Source trace reference URI |
"""

_TRIGGER_ARCH_MD = """\
### Trigger Engine — Architecture Reference

All triggers are deterministic threshold rules. No AI decision. AI explains only.

| Trigger Code | Condition | Direction |
|---|---|---|
| `RED_ENERGY_SHOCK` | BRENT > 120 | Risk-off |
| `BTC_RISK_OFF_WARNING` | BTCUSD < 75 000 | Risk-off |
| `BTC_RISK_ON_CANDIDATE` | BTCUSD > 80 000 + HYG/JNK recovery | Risk-on candidate |
| `GOLD_HEDGE_BREAKOUT` | XAUUSD > 4 660 | Hedge |
| `SILVER_STRATEGIC_METALS_REGIME` | XAGUSD > 65 | Strategic metals |
| `CREDIT_STRESS_CONFIRMATION` | HYG / JNK breakdown | Credit stress |

### Risk Engine — Action Enum

| Risk Action | Meaning |
|---|---|
| `WATCH` | Monitor — no position change |
| `HOLD` | Hold current positions |
| `NO_POSITION_INCREASE` | Do not add to positions |
| `RISK_REDUCE` | Reduce risk exposure |
| `HEDGE_INCREASE` | Increase hedge allocation |
| `KILL_SWITCH` | Full exit — all positions closed |

### Kill Switch — Final Gate

Kill Switch is the **final** gate. It is a **hard stop** — not a suggestion.
Default state: **OFF / NO_EXECUTION**.
Kill Switch state can only change via explicit deterministic trigger, never by AI.
"""

_CLAIM_ARCH_MD = """\
### Claim Validation Engine — Architecture Target

**NOT WIRED YET — ROADMAP**

| Output State | Meaning |
|---|---|
| `VERIFIED` | Claim confirmed by primary source |
| `VERIFIED_WITH_CONTEXT` | Confirmed with additional context required |
| `PARTIALLY_SUPPORTED` | Partial evidence only |
| `UNVERIFIED` | No supporting evidence found |
| `CONFLICTED` | Conflicting sources |
| `OPINION_ONLY` | No verifiable factual basis |

### Geopolitical / Sovereign Engine — ROADMAP
Tracks sanctions, supply disruptions, sovereign risk events, and OPEC decisions.
Not implemented. No fake data.

### Event-Asset Impact Engine — ROADMAP
Maps news events to asset impact vectors.
Not implemented. No fake data.

### News / Official Statement Validation — ROADMAP
Validates official statements against verifiable sources.
Not implemented. No fake data.
"""

_STRATEGIC_ENGINES_MD = """\
### Strategic Asset Engines — Architecture Target

| Engine | Status | Notes |
|---|---|---|
| Brent / Energy Shock Engine | ⬜ ROADMAP | Trigger: `RED_ENERGY_SHOCK` |
| Gold Hedge Engine | ⬜ ROADMAP | Trigger: `GOLD_HEDGE_BREAKOUT` |
| Silver Strategic Metals Engine | ⬜ ROADMAP | Multi-role: hedge + industrial + AI-grid |
| BTC / Crypto Risk Engine | ⬜ ROADMAP | Triggers: `BTC_RISK_OFF_WARNING`, `BTC_RISK_ON_CANDIDATE` |
| Credit Confirmation Engine | ⬜ ROADMAP | Trigger: `CREDIT_STRESS_CONFIRMATION` |
| Dollar / Rates Engine | ⬜ ROADMAP | DXY, US02Y, US10Y, US20Y |
| China / Industrial Engine | ⬜ ROADMAP | FXI, SHANGHAI_COMPOSITE, XCUUSD |
| AI Energy Infrastructure Engine | ⬜ ROADMAP | Silver + AI-grid demand model |

### Silver Engine — Architecture Logic (Reference)

```
Silver = hedge_metal
       + industrial_metal
       + AI_grid_electrification_metal
       + high_beta_squeeze_asset
```

Silver is the only asset playing all four roles simultaneously.
This makes it a strategic target in energy-transition regimes.
Engine status: architecture target — not implemented.
"""

# ---------------------------------------------------------------------------
# Path / service helpers
# ---------------------------------------------------------------------------


def _ensure_backend_on_path() -> None:
    backend_root = str(_REPO_ROOT / "backend")
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)


def _build_service() -> Any:
    _ensure_backend_on_path()
    from app.services.snapshot_replay_service import SnapshotReplayService  # noqa: PLC0415
    from app.storage.snapshot_store import build_local_snapshot_store  # noqa: PLC0415

    return SnapshotReplayService(snapshot_store=build_local_snapshot_store())


def _to_json_safe(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_json_safe(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


# ---------------------------------------------------------------------------
# Small data helpers
# ---------------------------------------------------------------------------


def _latest_backup_name() -> str:
    if not _CLEAN_BACKUPS_DIR.exists():
        return "[not found]"
    zips = sorted(_CLEAN_BACKUPS_DIR.glob("*.zip"), reverse=True)
    return zips[0].name if zips else "[none]"


def _snapshot_count() -> str:
    try:
        _ensure_backend_on_path()
        from app.storage.snapshot_store import build_local_snapshot_store  # noqa: PLC0415

        store = build_local_snapshot_store()
        return str(len(store.list_snapshots(limit=9999)))
    except Exception as exc:
        return f"error: {exc}"


def _next_task_summary() -> str:
    try:
        lines = _NEXT_TASK_FILE.read_text(encoding="utf-8").strip().splitlines()
        content = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
        return content[0] if content else "(empty)"
    except FileNotFoundError:
        return "[NEXT_TASK.md not found]"
    except Exception as exc:
        return f"[error: {exc}]"


def _run_command(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            cwd=str(_REPO_ROOT),
        )
        parts: list[str] = [f"Exit code: {result.returncode}"]
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if stdout:
            parts += ["--- stdout ---", stdout[:4000]]
        if stderr:
            parts += ["--- stderr ---", stderr[:1000]]
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT after {_SUBPROCESS_TIMEOUT}s]"
    except Exception as exc:
        return f"[error: {exc}]"


# ---------------------------------------------------------------------------
# Tab callbacks
# ---------------------------------------------------------------------------


def _cb_overview() -> str:
    backup = _latest_backup_name()
    count = _snapshot_count()
    next_task = _next_task_summary()
    return (
        "## System Mode\n\n"
        "| Mode | Status |\n"
        "|---|---|\n"
        "| PAPER_ONLY | ✅ Active |\n"
        "| REPLAY_ONLY | ✅ Active |\n"
        "| NO_EXECUTION | ✅ Active |\n"
        "| LOCAL_ONLY | ✅ Active |\n"
        "\n"
        "## Status\n\n"
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Latest backup | `{backup}` |\n"
        f"| Snapshots in store | {count} |\n"
        "| Provider | ✅ Stooq (fixture mode — no live network) |\n"
        "| Live network | ❌ Disabled |\n"
        "| Execution | ❌ OFF / NO_EXECUTION |\n"
        "| Broker integration | ❌ None |\n"
        f"| Next task | {next_task} |\n"
        "\n"
        "> **Caveat:** No live provider mode is active. "
        "No price data should be treated as current without a verified timestamp."
    )


def _cb_stooq_provider_info() -> str:
    """Return Stooq provider status as Markdown. No network calls."""
    try:
        _ensure_backend_on_path()
        from app.domain import AssetCode  # noqa: PLC0415
        from app.providers.stooq_adapter import (  # noqa: PLC0415
            StooqDailyProvider,
            build_stooq_source_bindings,
        )

        bindings = build_stooq_source_bindings()
        supported = sorted(a.value for a in StooqDailyProvider.supported_assets())

        try:
            url_template = StooqDailyProvider.source_url_for(AssetCode.QQQ).replace(
                "qqq.us", "{symbol}"
            )
        except Exception:
            url_template = "https://stooq.com/q/d/l/?s={symbol}&i=d"

        lines = [
            "**Status:** ✅ Available — fixture mode (no live network in tests)",
            f"**Supported assets:** `{', '.join(supported)}`",
            f"**URL template:** `{url_template}`",
            "",
            "| Asset | Source ID | Provider | Verified | Usage | Paper Safe | Active |",
            "|---|---|---|---|---|---|---|",
        ]
        for asset_val in sorted(bindings.keys()):
            b = bindings[asset_val]
            verified_icon = "✅" if b.verified else "❌"
            paper_icon = "✅" if b.paper_safe else "❌"
            lines.append(
                f"| `{b.asset_symbol.value}` | `{b.source_id}` "
                f"| `{b.registry_provider}` "
                f"| {verified_icon} {b.verified} "
                f"| `{b.decision_usage}` "
                f"| {paper_icon} {b.paper_safe} "
                f"| {b.active} |"
            )
        lines += [
            "",
            "> `config/source_registry_v1.0.yaml` is intentionally unchanged.",
            "> Stooq bindings are programmatic via `build_stooq_source_bindings()`.",
            "> All tests run in fixture mode — no live network calls.",
        ]
        return "\n".join(lines)
    except Exception as exc:
        return f"**Error loading Stooq provider info:** `{exc}`"


def _cb_run_stooq_fixture_ingestion(selected_assets: list[str]) -> dict[str, Any]:
    """Run Stooq fixture ingestion for selected assets. No network calls."""
    if not selected_assets:
        return {"error": "Select at least one asset."}
    try:
        _ensure_backend_on_path()
        from app.domain import AssetCode  # noqa: PLC0415
        from app.domain.assets import get_asset_definition  # noqa: PLC0415
        from app.providers.stooq_adapter import build_stooq_registry_bound_adapter  # noqa: PLC0415
        from app.services import MarketSnapshotService, ProviderIngestionService  # noqa: PLC0415

        class _FakeSession:
            def add(self, _: object) -> None:
                pass

            def commit(self) -> None:
                pass

            def rollback(self) -> None:
                pass

        adapter = build_stooq_registry_bound_adapter(
            fetch_fn=lambda _url: _STOOQ_FIXTURE_CSV
        )

        asset_defs = []
        invalid: list[str] = []
        for name in selected_assets:
            try:
                asset_defs.append(get_asset_definition(AssetCode(name)))
            except (ValueError, KeyError):
                invalid.append(name)

        if not asset_defs:
            return {"error": f"No valid asset codes found: {selected_assets}"}

        result = ProviderIngestionService(
            MarketSnapshotService(_FakeSession()), adapter
        ).run(assets=tuple(asset_defs))

        payloads_out = [
            {
                "asset_symbol": p.asset_symbol.value,
                "value": p.value,
                "unit": p.unit,
                "source_name": p.source_name,
                "source_id": p.source_id,
                "registry_provider": p.registry_provider,
                "verified": p.verified,
                "decision_usage": p.decision_usage,
                "paper_safe": p.paper_safe,
                "observed_at": str(p.observed_at),
                "raw_payload_ref": p.raw_payload_ref,
            }
            for p in result.provider_payloads
        ]

        return {
            "paper_safe": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
            "source_mode": "FIXTURE_CSV_ONLY",
            "total_assets_processed": result.total_assets_processed,
            "successful_snapshots": result.successful_snapshots,
            "failed_snapshots": result.failed_snapshots,
            "failed_assets": list(result.failed_assets),
            "invalid_input": invalid,
            "payloads": payloads_out,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _cb_run_replay(snapshot_id: str) -> dict[str, Any]:
    sid = snapshot_id.strip()
    if not sid:
        return {"error": "Enter a snapshot_id."}
    try:
        service = _build_service()
        result = service.replay_snapshot(sid)
        r = result.risk_engine_result
        c = result.ceo_report
        active = [t.trigger_code for t in result.trigger_results if t.is_triggered]
        return {
            "snapshot_id": result.snapshot_id,
            "created_at": result.created_at,
            "report_type": result.report_type,
            "mode": result.mode,
            "execution_mode": result.execution_mode,
            "decision_permission": result.decision_permission,
            "paper_safe": (
                result.mode in ("PAPER_SAFE", "SIMULATION")
                and result.execution_mode in ("PAPER_ONLY", "NO_EXECUTION")
                and result.decision_permission == "NO_EXECUTION"
            ),
            "network_calls": False,
            "execution_side_effects": result.decision_permission,
            "replay_regime": result.replay_regime,
            "replay_regime_diagnostic": result.replay_regime_diagnostic,
            "missing_sources": list(result.missing_sources),
            "stale_sources": list(result.stale_sources),
            "active_triggers": active,
            "risk_action": (
                r.risk_action.value if hasattr(r.risk_action, "value") else str(r.risk_action)
            ),
            "kill_switch_active": r.kill_switch_active,
            "risk_summary": r.summary,
            "reason_codes": list(r.reason_codes),
            "ceo_report": {
                "report_title": c.report_title,
                "regime_summary": c.regime_summary,
                "owner_action": c.owner_action,
                "execution_status": c.execution_status,
                "risk_action": (
                    c.risk_action.value
                    if hasattr(c.risk_action, "value")
                    else str(c.risk_action)
                ),
                "key_triggers": list(c.key_triggers),
                "short_report": list(c.short_report_sentences),
            },
        }
    except KeyError:
        return {"error": f"Snapshot not found: {sid!r}"}
    except Exception as exc:
        return {"error": str(exc)}


def _cb_load_replay_risk(snapshot_id: str) -> dict[str, Any]:
    """Extract risk engine fields from a snapshot replay."""
    sid = snapshot_id.strip()
    if not sid:
        return {"note": "Enter a snapshot_id to load risk data."}
    full = _cb_run_replay(sid)
    if "error" in full:
        return full
    return {
        "paper_safe": full.get("paper_safe"),
        "network_calls": full.get("network_calls"),
        "execution_side_effects": full.get("execution_side_effects"),
        "risk_action": full.get("risk_action"),
        "kill_switch_active": full.get("kill_switch_active"),
        "reason_codes": full.get("reason_codes"),
        "active_triggers": full.get("active_triggers"),
        "risk_summary": full.get("risk_summary"),
        "replay_regime": full.get("replay_regime"),
        "missing_sources": full.get("missing_sources"),
        "stale_sources": full.get("stale_sources"),
    }


def _cb_run_rolling_diagnostics(snapshot_ids_raw: str, limit: float) -> dict[str, Any]:
    snap_ids = [s.strip() for s in snapshot_ids_raw.split(",") if s.strip()] or None
    try:
        service = _build_service()
        result = service.build_rolling_backtest_diagnostics(
            snapshot_ids=snap_ids,
            limit=int(limit),
        )
        return _to_json_safe(result)
    except Exception as exc:
        return {"error": str(exc)}


def _cb_run_source_diagnostic(diag_name: str, snapshot_ids_raw: str) -> dict[str, Any]:
    method_name = _SOURCE_DIAG_METHOD.get(diag_name)
    if not method_name:
        return {"error": f"Unknown diagnostic: {diag_name!r}"}
    snap_ids = [s.strip() for s in snapshot_ids_raw.split(",") if s.strip()] or None
    try:
        service = _build_service()
        method = getattr(service, method_name)
        result = method(snapshot_ids=snap_ids)
        return _to_json_safe(result)
    except Exception as exc:
        return {"error": str(exc)}


def _cb_snapshot_browser() -> list[list[str]]:
    try:
        _ensure_backend_on_path()
        from app.storage.snapshot_store import build_local_snapshot_store  # noqa: PLC0415

        store = build_local_snapshot_store()
        snapshots = store.list_snapshots(limit=100)
    except Exception as exc:
        return [[f"Error: {exc}"] + [""] * (len(_SNAPSHOT_COLUMNS) - 1)]
    if not snapshots:
        return [["(no snapshots found)"] + [""] * (len(_SNAPSHOT_COLUMNS) - 1)]
    return [[str(snap.get(col, "")) for col in _SNAPSHOT_COLUMNS] for snap in snapshots]


def _cb_load_snapshot_metadata(snapshot_id: str) -> dict[str, Any]:
    """Load a specific snapshot's full metadata from the local store."""
    sid = snapshot_id.strip()
    if not sid:
        return {"note": "Enter a snapshot_id to load metadata."}
    try:
        _ensure_backend_on_path()
        from app.storage.snapshot_store import build_local_snapshot_store  # noqa: PLC0415

        store = build_local_snapshot_store()
        return store.load_snapshot(sid)
    except KeyError:
        return {"error": f"Snapshot not found: {sid!r}"}
    except Exception as exc:
        return {"error": str(exc)}


def _cb_paper_report_preview(snapshot_id: str) -> dict[str, Any]:
    sid = snapshot_id.strip()
    if not sid:
        return {"note": "Enter a snapshot_id to generate a paper report preview."}
    try:
        service = _build_service()
        result = service.replay_snapshot(sid)
        c = result.ceo_report
        return {
            "paper_safe": True,
            "network_calls": False,
            "execution_side_effects": "NO_EXECUTION",
            "report_title": c.report_title,
            "regime_summary": c.regime_summary,
            "owner_action": c.owner_action,
            "execution_status": c.execution_status,
            "risk_action": (
                c.risk_action.value if hasattr(c.risk_action, "value") else str(c.risk_action)
            ),
            "key_triggers": list(c.key_triggers),
            "short_report": list(c.short_report_sentences),
            "snapshot_id": result.snapshot_id,
            "created_at": result.created_at,
        }
    except KeyError:
        return {"error": f"Snapshot not found: {sid!r}"}
    except Exception as exc:
        return {"error": str(exc)}


def _cb_audit_status() -> str:
    backup = _latest_backup_name()
    return (
        "## Audit & Governance Status\n\n"
        "| Item | Status |\n"
        "|---|---|\n"
        f"| Latest clean backup | `{backup}` |\n"
        "| verify_and_snapshot | ✅ Run via Validation & Backup tab |\n"
        "| Snapshot trace | ✅ Available — SnapshotStore JSONL |\n"
        "| Source trace | ✅ Available — source_observations per snapshot |\n"
        "| Decision trace | 🟡 PARTIAL — available via replay result |\n"
        "| Prediction log | ⬜ ROADMAP |\n"
        "| Outcome log | ⬜ ROADMAP |\n"
        "| Weekly review | ⬜ ROADMAP |\n"
        "| Error attribution | ⬜ ROADMAP |\n"
        "| Correlation drift | ⬜ ROADMAP |\n"
        "| Strategy proposal | ⬜ ROADMAP |\n"
    )


def _cb_load_next_task() -> str:
    """Read NEXT_TASK.md content."""
    try:
        return _NEXT_TASK_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "[NEXT_TASK.md not found]"
    except Exception as exc:
        return f"[error: {exc}]"


def _cb_run_ruff() -> str:
    return _run_command(["ruff", "check", "backend", "tests"])


def _cb_run_pytest() -> str:
    return _run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            r"--basetemp=.pytest_tmp\basetemp",
        ]
    )


def _cb_run_verify_snapshot() -> str:
    return _run_command([sys.executable, "scripts/verify_and_snapshot.py"])


# ---------------------------------------------------------------------------
# UI builder
# ---------------------------------------------------------------------------


def build_demo() -> Any:  # noqa: PLR0915
    css = """
    .eyay-header {
        background: #1a1a2e; padding: 14px 20px;
        border-radius: 8px; margin-bottom: 10px;
    }
    .eyay-badge {
        display: inline-block; background: #16213e; color: #e94560;
        padding: 3px 10px; border-radius: 4px;
        margin: 2px 4px 2px 0; font-size: 0.82em; font-weight: bold;
    }
    .eyay-card {
        background: #1e1e2e; border: 1px solid #3a3a5a;
        border-radius: 8px; padding: 12px 16px; margin: 6px 0;
    }
    .eyay-card-green {
        background: #1a2e1a; border: 1px solid #2a4a2a;
        border-radius: 8px; padding: 12px 16px; margin: 6px 0;
    }
    .eyay-card-yellow {
        background: #2e2a1a; border: 1px solid #4a3a1a;
        border-radius: 8px; padding: 12px 16px; margin: 6px 0;
    }
    .eyay-label {
        font-weight: bold; color: #888; font-size: 0.8em;
        text-transform: uppercase; letter-spacing: 0.05em;
    }
    """
    with gr.Blocks(
        title="E-YAY / BrainChain Paper Intelligence Console",
        css=css,
        theme=gr.themes.Base(),
    ) as demo:

        gr.HTML("""
        <div class="eyay-header">
          <h2 style="color:#e0e0e0;margin:0 0 4px 0">
            E-YAY / BrainChain Paper Intelligence Console
          </h2>
          <p style="color:#aaa;margin:0 0 10px 0;font-size:0.9em">
            Local paper-safe replay, source diagnostics, risk control, and owner briefing.
          </p>
          <span class="eyay-badge">PAPER_ONLY</span>
          <span class="eyay-badge">REPLAY_ONLY</span>
          <span class="eyay-badge">NO_EXECUTION</span>
          <span class="eyay-badge">LOCAL_DASHBOARD</span>
          <br/>
          <span style="color:#555;font-size:0.78em;">
            AI karar vermez. AI açıklar. &nbsp;|&nbsp;
            Decision Core deterministiktir. &nbsp;|&nbsp;
            Risk Engine final kapıdır. &nbsp;|&nbsp;
            Execution varsayılan OFF.
          </span>
        </div>
        """)

        with gr.Tabs():

            # ------------------------------------------------------------------
            # Tab 1 — Executive Command Center
            # ------------------------------------------------------------------
            with gr.Tab("Executive Command Center"):
                gr.Markdown("### Owner Status — One Screen Summary")
                overview_md = gr.Markdown(value=_cb_overview())
                refresh_ov_btn = gr.Button("Refresh")
                refresh_ov_btn.click(fn=_cb_overview, inputs=[], outputs=[overview_md])

            # ------------------------------------------------------------------
            # Tab 2 — Data Sources & Provider Layer
            # ------------------------------------------------------------------
            with gr.Tab("Data Sources & Provider Layer"):
                gr.Markdown("### Active Provider: Stooq Daily CSV")
                provider_md = gr.Markdown(value=_cb_stooq_provider_info())
                refresh_prov_btn = gr.Button("Refresh Provider Info")
                refresh_prov_btn.click(
                    fn=_cb_stooq_provider_info, inputs=[], outputs=[provider_md]
                )

                with gr.Accordion("Roadmap — Additional Data Sources", open=False):
                    gr.Markdown("""\
**NOT WIRED YET — ROADMAP**

| Source | Assets | Status |
|---|---|---|
| FRED (Federal Reserve) | US02Y, US10Y, US20Y, USCPI, USPPI, M2SL | ⬜ ROADMAP |
| CoinGecko | BTCUSD, BTC.D, USDT.D, TOTAL, TOTAL2 | ⬜ ROADMAP |
| Stooq extended | BRENT, XCUUSD, DXY, NASDAQ, SP500 | ⬜ ROADMAP |
| LBMA / Metals | XAUUSD, XAGUSD, XAUXAG | ⬜ ROADMAP |
| News / official statements | Geopolitical context | ⬜ ROADMAP |
| AI-energy-grid demand | XCUUSD, XAGUSD, AI capacity | ⬜ ROADMAP |
""")

            # ------------------------------------------------------------------
            # Tab 3 — Data Integrity Gate
            # ------------------------------------------------------------------
            with gr.Tab("Data Integrity Gate"):
                gr.Markdown("### DQS — Data Quality Score Architecture")
                with gr.Accordion("DQS Formula & Thresholds", open=True):
                    gr.Markdown(_DQS_FORMULA_MD)
                with gr.Accordion("Expected Snapshot Record Fields", open=False):
                    gr.Markdown(_DQS_FIELDS_MD)

            # ------------------------------------------------------------------
            # Tab 4 — Ingestion Pipeline
            # ------------------------------------------------------------------
            with gr.Tab("Ingestion Pipeline"):
                gr.Markdown(
                    "### Stooq Fixture Ingestion\n"
                    "*Fixture mode only — no network calls. "
                    "Uses static CSV for deterministic paper-safe output.*"
                )
                ingest_assets = gr.CheckboxGroup(
                    choices=_STOOQ_ASSET_CHOICES,
                    value=_STOOQ_ASSET_CHOICES,
                    label="Assets to ingest (fixture CSV mode)",
                )
                gr.Markdown(
                    "> `paper_safe=True` · `network_calls=False` · "
                    "`execution_side_effects=NO_EXECUTION` · `source_mode=FIXTURE_CSV_ONLY`"
                )
                ingest_btn = gr.Button("Run Local Fixture Ingestion", variant="primary")
                ingest_out = gr.JSON(label="Ingestion Result")
                ingest_btn.click(
                    fn=_cb_run_stooq_fixture_ingestion,
                    inputs=[ingest_assets],
                    outputs=[ingest_out],
                )

            # ------------------------------------------------------------------
            # Tab 5 — Snapshot Store
            # ------------------------------------------------------------------
            with gr.Tab("Snapshot Store"):
                gr.Markdown(
                    "### Local Snapshot Metadata\n"
                    "*Reads local JSONL storage only. No live source calls.*"
                )
                snap_df = gr.Dataframe(
                    headers=_SNAPSHOT_COLUMNS,
                    value=_cb_snapshot_browser(),
                    interactive=False,
                    wrap=False,
                )
                refresh_snap_btn = gr.Button("Refresh")
                refresh_snap_btn.click(fn=_cb_snapshot_browser, inputs=[], outputs=[snap_df])

                gr.Markdown("---\n### Load Snapshot Metadata")
                load_snap_id = gr.Textbox(
                    label="Snapshot ID",
                    placeholder="Paste or type snapshot_id from table above",
                )
                load_snap_btn = gr.Button("Load Snapshot Metadata")
                load_snap_out = gr.JSON(label="Snapshot Metadata")
                load_snap_btn.click(
                    fn=_cb_load_snapshot_metadata,
                    inputs=[load_snap_id],
                    outputs=[load_snap_out],
                )

            # ------------------------------------------------------------------
            # Tab 6 — Snapshot Replay
            # ------------------------------------------------------------------
            with gr.Tab("Snapshot Replay"):
                gr.Markdown(
                    "### Paper-Safe Snapshot Replay\n"
                    "*No live data. No execution. PAPER_ONLY / NO_EXECUTION.*"
                )
                replay_id_input = gr.Textbox(
                    label="Snapshot ID",
                    placeholder="e.g. provider_ingestion_paper_snapshot_20260528...",
                )
                replay_btn = gr.Button("Run Replay", variant="primary")
                replay_out = gr.JSON(label="Replay Result")
                replay_btn.click(
                    fn=_cb_run_replay,
                    inputs=[replay_id_input],
                    outputs=[replay_out],
                )

            # ------------------------------------------------------------------
            # Tab 7 — Trigger & Risk Engine
            # ------------------------------------------------------------------
            with gr.Tab("Trigger & Risk Engine"):
                gr.Markdown("### Deterministic Trigger & Risk Architecture")
                with gr.Accordion("Trigger Engine — Reference", open=True):
                    gr.Markdown(_TRIGGER_ARCH_MD)

                gr.Markdown("---\n### Load Risk Data from Replay")
                risk_snap_id = gr.Textbox(
                    label="Snapshot ID (leave blank for note)",
                    placeholder="Enter snapshot_id to load live risk values",
                )
                risk_btn = gr.Button("Load Risk Engine Output", variant="primary")
                risk_out = gr.JSON(label="Risk Engine Result")
                risk_btn.click(
                    fn=_cb_load_replay_risk,
                    inputs=[risk_snap_id],
                    outputs=[risk_out],
                )

            # ------------------------------------------------------------------
            # Tab 8 — Source & Contract Diagnostics
            # ------------------------------------------------------------------
            with gr.Tab("Source & Contract Diagnostics"):
                gr.Markdown(
                    "### Source Diagnostic Contract Drift\n"
                    "*Reads saved paper snapshots only. No network calls.*"
                )
                src_diag_choice = gr.Dropdown(
                    choices=_SOURCE_DIAG_CHOICES,
                    value=_SOURCE_DIAG_CHOICES[0],
                    label="Contract Diagnostic",
                )
                src_ids_input = gr.Textbox(
                    label="Snapshot IDs (comma-separated, blank = default)",
                    placeholder="Leave blank to use the most recent snapshots",
                )
                src_diag_btn = gr.Button("Run Contract Diagnostic", variant="primary")
                src_diag_out = gr.JSON(label="Diagnostic Result")
                src_diag_btn.click(
                    fn=_cb_run_source_diagnostic,
                    inputs=[src_diag_choice, src_ids_input],
                    outputs=[src_diag_out],
                )

                gr.Markdown("---\n### Rolling Backtest Diagnostics")
                roll_ids_input = gr.Textbox(
                    label="Snapshot IDs (comma-separated, blank = default)",
                    placeholder="Leave blank to use the most recent snapshots",
                )
                roll_limit = gr.Slider(minimum=2, maximum=50, step=1, value=10, label="Limit")
                roll_btn = gr.Button("Run Rolling Diagnostics", variant="primary")
                roll_out = gr.JSON(label="Rolling Diagnostics Result")
                roll_btn.click(
                    fn=_cb_run_rolling_diagnostics,
                    inputs=[roll_ids_input, roll_limit],
                    outputs=[roll_out],
                )

            # ------------------------------------------------------------------
            # Tab 9 — Claim Validation & Geopolitical Engine [ROADMAP]
            # ------------------------------------------------------------------
            with gr.Tab("Claim Validation & Geopolitical"):
                gr.Markdown(
                    "### Claim Validation & Geopolitical Engine\n"
                    "> **NOT WIRED YET — Architecture Target**"
                )
                with gr.Accordion("Claim Validation Architecture", open=True):
                    gr.Markdown(_CLAIM_ARCH_MD)

            # ------------------------------------------------------------------
            # Tab 10 — Strategic Asset Engines [ROADMAP]
            # ------------------------------------------------------------------
            with gr.Tab("Strategic Asset Engines"):
                gr.Markdown(
                    "### Strategic Asset Engines\n"
                    "> **NOT WIRED YET — Architecture Target**"
                )
                with gr.Accordion("Engine Status & Architecture", open=True):
                    gr.Markdown(_STRATEGIC_ENGINES_MD)

            # ------------------------------------------------------------------
            # Tab 11 — CEO / Owner Brief
            # ------------------------------------------------------------------
            with gr.Tab("CEO / Owner Brief"):
                gr.Markdown(
                    "### Paper-Safe CEO Report Preview\n"
                    "*Replays a saved snapshot and extracts the CEO report. "
                    "No live data. No execution. No trade instruction.*"
                )
                prev_id_input = gr.Textbox(
                    label="Snapshot ID",
                    placeholder="Enter snapshot_id to generate report preview",
                )
                prev_btn = gr.Button("Generate Owner Brief", variant="primary")
                prev_out = gr.JSON(label="CEO / Owner Brief")
                prev_btn.click(
                    fn=_cb_paper_report_preview,
                    inputs=[prev_id_input],
                    outputs=[prev_out],
                )

            # ------------------------------------------------------------------
            # Tab 12 — Learning & Audit
            # ------------------------------------------------------------------
            with gr.Tab("Learning & Audit"):
                audit_md = gr.Markdown(value=_cb_audit_status())
                refresh_audit_btn = gr.Button("Refresh")
                refresh_audit_btn.click(fn=_cb_audit_status, inputs=[], outputs=[audit_md])

            # ------------------------------------------------------------------
            # Tab 13 — Validation & Backup
            # ------------------------------------------------------------------
            with gr.Tab("Validation & Backup"):
                gr.Markdown(
                    "### Validation Commands\n"
                    "*No command runs automatically. Click to execute.*"
                )
                with gr.Row():
                    ruff_btn = gr.Button("Run Ruff Check", variant="primary")
                    pytest_btn = gr.Button("Run Full Pytest", variant="primary")
                    verify_btn = gr.Button("Run Verify Snapshot", variant="primary")
                val_out = gr.Textbox(
                    label="Output",
                    lines=28,
                    interactive=False,
                    placeholder="Output appears here after clicking a button.",
                )
                ruff_btn.click(fn=_cb_run_ruff, inputs=[], outputs=[val_out])
                pytest_btn.click(fn=_cb_run_pytest, inputs=[], outputs=[val_out])
                verify_btn.click(fn=_cb_run_verify_snapshot, inputs=[], outputs=[val_out])

            # ------------------------------------------------------------------
            # Tab 14 — Roadmap / Next Task
            # ------------------------------------------------------------------
            with gr.Tab("Roadmap / Next Task"):
                gr.Markdown("### Current Roadmap & Next Task")
                next_task_md = gr.Textbox(
                    label="NEXT_TASK.md",
                    value=_cb_load_next_task(),
                    lines=30,
                    interactive=False,
                )
                refresh_nt_btn = gr.Button("Refresh")
                refresh_nt_btn.click(fn=_cb_load_next_task, inputs=[], outputs=[next_task_md])

    return demo


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not _GRADIO_AVAILABLE:
        print("Gradio is not installed.")
        print("Install with:  python -m pip install gradio")
        sys.exit(1)

    demo = build_demo()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7867,
        share=False,
    )
