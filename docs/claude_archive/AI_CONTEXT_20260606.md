# AI_CONTEXT.md

Token note: this is a long historical archive. Claude should read `CLAUDE.md` first and open this file only when task history is explicitly needed.

## Current Stable Checkpoint
- Repo: C:\Users\twone\Desktop\E_YAY CODEX
- Latest clean backup: C:\Users\twone\Desktop\E_YAY CODEX\clean_backups\eyay_clean_20260528T135613Z.zip
- Ruff: All checks passed
- Full pytest: 462 passed
- verify_and_snapshot.py: Success

## Current System Status
- E-YAY local paper/replay system is stable.
- Snapshot replay imports are repaired.
- Public re-exports are restored.
- snapshot_replay_source_common.py is restored as a re-export hub.
- snapshot_replay_service.py re-exports are restored.
- snapshot_replay_source_serializers_quality.py is restored as serializer aggregator.
- Snapshot replay route prefix is fixed.
  - Correct: /api/v1/snapshots
  - Wrong: /api/v1/api/v1/snapshots

## System Mode
- PAPER_ONLY
- REPLAY_ONLY
- NO_EXECUTION
- LOCAL_ONLY
- No live market data
- No trading execution
- No broker integration

## Completed Task
One-click Stooq demo snapshot flow — dashboard + end-to-end replay (2026-05-28).

Files edited:
- backend/app/dashboard/gradio_dashboard.py
  - Added constants: _STOOQ_ALL_ASSETS, _DEMO_SNAPSHOT_STORE_FILENAME
  - Added helpers: _build_demo_store(), _latest_demo_snapshot_id()
  - Added callbacks: _cb_create_stooq_demo_snapshot(),
    _cb_create_stooq_demo_snapshot_with_id(), _cb_get_latest_demo_snapshot_id(),
    _cb_create_and_replay_demo_snapshot()
  - Tab 4 (Ingestion Pipeline): added "Create Local Stooq Demo Snapshot" section with
    snapshot_id output textbox, ingestion summary JSON, two buttons
    ("Create Local Stooq Demo Snapshot", "Create + Replay Demo Snapshot")
  - Tab 5 (Snapshot Store): added "Load Latest Demo Snapshot ID" helper button
  - Tab 11 (CEO / Owner Brief): added "Load Latest Demo Snapshot ID" helper button

Files created:
- backend/tests/test_stooq_replay.py (28 tests)
  - Ingestion → persistence: snapshot_id, paper_safe, 4 assets, source_name, loadable, list
  - Replay: succeeds, paper_safe, network_calls=False, NO_EXECUTION, source_name in obs,
    risk engine result, CEO report
  - Rolling diagnostics: build_rolling_backtest_diagnostics passes
  - Dashboard callbacks: _cb_create_stooq_demo_snapshot (7 tests),
    _cb_create_stooq_demo_snapshot_with_id, _cb_create_and_replay_demo_snapshot (5 tests),
    _cb_get_latest_demo_snapshot_id (2 tests)

Demo flow:
Stooq fixture CSV → StooqDailyProvider → SourceRegistryBoundProviderAdapter
→ ProviderIngestionService → SnapshotStore (stooq_demo_snapshots.jsonl)
→ SnapshotReplayService.replay_snapshot() → CEO / Owner Brief → Dashboard output

Safety preserved:
- PAPER_ONLY | FIXTURE_DATA | REPLAY_ONLY | NO_EXECUTION
- paper_safe=True, network_calls=False, execution_side_effects="NO_EXECUTION"
- data_mode="FIXTURE_DATA" in all new callback outputs
- No network calls. No live data. No execution buttons.
- Demo store: stooq_demo_snapshots.jsonl (separate from default ceo_report_demo_snapshots.jsonl)

## Prior Completed Task
Dashboard redesign — E-YAY / BrainChain Paper Intelligence Console (2026-05-28).

Files rewritten:
- backend/app/dashboard/gradio_dashboard.py (full rewrite — 14-tab console)

Files edited:
- backend/tests/test_dashboard.py (+16 new tests: 7 source-based + 9 function-level)

New dashboard:
- Name: "E-YAY / BrainChain Paper Intelligence Console"
- 14 tabs: Executive Command Center, Data Sources & Provider Layer, Data Integrity Gate,
  Ingestion Pipeline, Snapshot Store, Snapshot Replay, Trigger & Risk Engine,
  Source & Contract Diagnostics, Claim Validation & Geopolitical [ROADMAP],
  Strategic Asset Engines [ROADMAP], CEO / Owner Brief, Learning & Audit,
  Validation & Backup, Roadmap / Next Task
- All 6 pre-existing callbacks preserved
- New callbacks: _cb_stooq_provider_info, _cb_run_stooq_fixture_ingestion,
  _cb_load_replay_risk, _cb_load_snapshot_metadata, _cb_audit_status,
  _cb_load_next_task
- Safety: PAPER_ONLY | REPLAY_ONLY | NO_EXECUTION | LOCAL_DASHBOARD
- server_name="127.0.0.1", server_port=7867, share=False
- DQS formula, trigger arch, risk action enum, claim validation states shown as
  static architecture reference — no fake data
- ROADMAP tabs clearly labeled — no invented outputs

## Prior Completed Task
Stooq registry-bound adapter wiring (2026-05-28).

Files edited:
- backend/app/providers/stooq_adapter.py (added build_stooq_source_bindings() + build_stooq_registry_bound_adapter(); added ProviderSourceBinding + SourceRegistryBoundProviderAdapter imports)
- backend/app/providers/__init__.py (added build_stooq_source_bindings, build_stooq_registry_bound_adapter exports)

Files created:
- backend/tests/test_stooq_ingestion.py (19 integration tests — registry binding construction, VerifiedProviderPayload output, ingestion pipeline, snapshot store persistence, graceful failure, no-network guarantee)

config/source_registry_v1.0.yaml: intentionally NOT modified — existing tests assert exact unverified entry set and active/total counts.
Bindings implemented programmatically via build_stooq_source_bindings() instead.

Integration achieved:
- StooqDailyProvider → SourceRegistryBoundProviderAdapter (via build_stooq_registry_bound_adapter)
- ProviderIngestionService.run(assets=[QQQ,HYG,JNK,FXI]) → 4 successful paper-safe results
- Persists to SnapshotStore (e.g. stooq_paper_snapshots.jsonl)
- paper_safe=True, verified=False, decision_usage="simulation_only" for all 4 assets

## Prior Completed Task
Stooq daily CSV provider adapter skeleton (2026-05-28).

Files created:
- PROVIDER_ADAPTER_PLAN.md (full plan: asset mapping, field mapping, timestamp handling, failure modes, test strategy, pipeline integration map)
- backend/app/providers/stooq_adapter.py (StooqDailyProvider — injectable fetch_fn, paper-safe, no execution)
- backend/tests/test_stooq_adapter.py (19 tests — all use fixture CSV, no network)

Files edited:
- backend/app/providers/__init__.py (added StooqDailyProvider to imports and __all__)

Supported assets: QQQ, HYG, JNK, FXI (all usd_per_share, stooq ETF tickers).
Not wired into production ingestion (ProviderIngestionService) by default.
Source registry NOT updated (deferred — see PROVIDER_ADAPTER_PLAN.md §Pipeline Integration Map).

## Prior Completed Task
Dashboard smoke test + requirements-dashboard.txt (2026-05-28).

Files created:
- requirements-dashboard.txt (gradio)

Files edited:
- README.md (Local Gradio Dashboard section added)
- NEXT_TASK.md (updated to reflect completion + next recommended task)
- backend/tests/test_dashboard.py (5 new smoke tests added)

New smoke tests:
- test_cb_snapshot_browser_with_demo_store
- test_cb_run_replay_with_demo_snapshot
- test_cb_run_rolling_diagnostics_with_demo_store
- test_cb_run_source_diagnostic_contract_field_set_drift_returns_dict
- test_cb_paper_report_preview_with_demo_snapshot

All smoke tests use real local snapshot data via monkeypatched _build_service.
No live data. No network calls. No gradio server launched.
Gradio confirmed installed (import test passed).

## Prior Completed Task
Field-set gap fix (2026-05-28).

Models fixed:
- SnapshotFallbackUsageRecurrence: added `entries: tuple[SnapshotFallbackUsageRecurrenceEntry, ...]`
- SnapshotSourceFreshnessDecayTimeline: added `failures: tuple[dict[str, str], ...]` and `total_snapshots_requested: int`

Files edited:
- backend/app/services/snapshot_replay_models_source_registry.py (entries field added)
- backend/app/services/snapshot_replay_models_source_timing.py (failures + total_snapshots_requested added)
- backend/app/services/snapshot_replay_source_recurrence.py (builder signature + 5 constructor call sites updated)
- backend/app/services/snapshot_replay_source_diagnostics.py (public builder passes failures + total_snapshots_requested)
- backend/app/services/snapshot_replay_service.py (rolling diagnostics builder also passes failures + total_snapshots_requested)
- backend/app/api/snapshot_replay_source_serializers_quality_common.py (entries serialized)
- backend/app/api/snapshot_replay_source_serializers_timing.py (failures + total_snapshots_requested serialized)
- backend/tests/test_snapshot_replay_api.py (2 existing tests updated to include new fields)

Diagnostic result after fix:
- 49/49 source diagnostic models now have all standard fields (100% consistent)

## Active Near-Term Task
Next safe options (in order of value):
1. Add a second fixture multi-day CSV to test multi-snapshot rolling diagnostics properly.
2. Wire a real data-fetch button behind an explicit confirmation gate (separate from fixture mode).
3. Add scheduler/cron task for periodic Stooq fixture snapshot creation (review only, no execution).
4. Extend source_registry_v1.0.yaml safely by separating multi-source-per-asset indexing
   (currently blocked by existing tests asserting exact entry set + active/total equality).

## Validation Commands
ruff check backend tests

pytest -p no:cacheprovider --basetemp=".pytest_tmp\basetemp"

python scripts/verify_and_snapshot.py

## Update Rule
After every successful task:
- Update this file with:
  - completed task
  - files edited
  - new ruff result
  - new pytest result
  - new verify_and_snapshot result
  - new backup path
  - next recommended task
