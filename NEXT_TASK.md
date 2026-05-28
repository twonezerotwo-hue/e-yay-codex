# NEXT TASK

Completed in this session:
- Dashboard redesigned as "E-YAY / BrainChain Paper Intelligence Console" (14 tabs)
  - Tab 2: Data Sources & Provider Layer (Stooq bindings, ROADMAP accordion)
  - Tab 3: Data Integrity Gate (DQS formula + field spec — static architecture reference)
  - Tab 4: Ingestion Pipeline (fixture ingestion via CheckboxGroup — no network)
  - Tab 5: Snapshot Store (browser + metadata loader)
  - Tab 7: Trigger & Risk Engine (architecture reference + risk field extraction)
  - Tab 9: Claim Validation & Geopolitical [ROADMAP] — no fake data
  - Tab 10: Strategic Asset Engines [ROADMAP] — Silver logic, engine status table
  - Tab 12: Learning & Audit (_cb_audit_status + ROADMAP items)
  - Tab 14: Roadmap / Next Task (reads NEXT_TASK.md live)
- New callbacks: _cb_stooq_provider_info, _cb_run_stooq_fixture_ingestion,
  _cb_load_replay_risk, _cb_load_snapshot_metadata, _cb_audit_status, _cb_load_next_task
- backend/tests/test_dashboard.py: +16 new tests (40 total, all pass)
- Ruff: All checks passed
- Pytest: 434 passed (was 418)
- verify_and_snapshot.py: eyay_clean_20260528T073924Z.zip

Recommended next task:
Create one local paper snapshot from Stooq fixture data and replay it end-to-end.

Steps:
1. Use build_stooq_registry_bound_adapter(fetch_fn=fixture_fn) + ProviderIngestionService to
   write a snapshot to a tmp stooq_paper_snapshots.jsonl (4 assets: QQQ, HYG, JNK, FXI).
2. Load it into SnapshotReplayService.
3. Call replay_snapshot(snapshot_id) and verify:
   - paper_safe=True
   - network_calls=False
   - execution_side_effects="NO_EXECUTION"
   - source_name="stooq_daily_csv" in the replayed observations
4. Call build_rolling_backtest_diagnostics() on the store.
5. Write a new test file backend/tests/test_stooq_replay.py covering the above.
6. Do NOT require network in tests. Do NOT modify existing replay service or API routes.
