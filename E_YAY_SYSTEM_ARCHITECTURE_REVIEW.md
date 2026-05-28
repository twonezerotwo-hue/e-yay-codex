# E-YAY System Architecture Review

**Date:** 2026-05-28
**Status:** Paper-safe stable. No execution. No live data.
**Audit basis:** AI_CONTEXT.md, AI_RULES.md, ARCHITECTURE_GAP_ANALYSIS.md, source inspection of key modules.

---

## 1. Executive Summary

E-YAY is a **local, paper-safe, snapshot-replay and source-quality diagnostic system** for a single owner. It is designed to replay saved market snapshots, evaluate source data quality across multiple diagnostic dimensions, classify risk posture, and generate plain-language briefings.

**What it is:**
- A local paper replay engine for saved market snapshots.
- A 49-diagnostic-surface source quality monitor.
- A deterministic risk/trigger classification engine.
- A CEO/owner briefing generator based on replayed paper data.
- A self-contained diagnostic and audit platform with strong test coverage.

**What it is not:**
- Not a live trading system.
- Not a real-time market intelligence engine.
- Not connected to live provider data (no concrete adapter implemented).
- Not a production deployment (no auth, no scheduler, no packaging).
- Not a research platform with backtest-vs-actual validation.

**The honest baseline:** The system is architecturally complete at the paper-replay layer. The ingestion pipeline exists but cannot be used without implementing concrete `VerifiedProviderAdapter` subclasses for real data sources. All current replay is over a local JSONL snapshot file (`ceo_report_demo_snapshots.jsonl`) that contains demo/test data. The diagnostic surface is sophisticated but primarily self-checking rather than owner-value-producing at this stage.

---

## 2. What E-YAY Is For

E-YAY is designed to be a **paper-safe macro/risk intelligence platform** for a single owner. Its intended use case:

- **Snapshot-based replay:** Load saved market snapshots, replay them through risk and trigger engines, observe how the system would have classified each situation.
- **Source quality monitoring:** Detect stale, missing, degraded, or inconsistent data sources across replayed snapshots.
- **Deterministic diagnostics:** Generate structured, reproducible diagnostic outputs for every snapshot batch — no randomness, no live API calls.
- **Risk posture classification:** Produce a discrete risk action (HOLD / WATCH / NO_POSITION_INCREASE / RISK_REDUCE / HEDGE_INCREASE / KILL_SWITCH) based on trigger state.
- **CEO/owner briefing:** Plain-language briefing summarizing regime, key triggers, and recommended owner action.
- **Audit-friendly:** All outputs are frozen dataclasses, all safety flags are explicit, all routes enforce paper/no-execution mode.

**The owner's market universe:**
27 assets across macro/crypto/commodities — BTC, ETH dominance, Brent crude, gold, silver, DXY, HYG, JNK, NASDAQ, S&P500, QQQ, US rates (2Y/10Y/20Y), CPI, PPI, M2, FXI, Shanghai Composite, copper. This is a specific macro-intelligence configuration, not a general-purpose trading system.

**The 8 named triggers:**
`RED_ENERGY_SHOCK`, `BTC_RISK_OFF_WARNING`, `BTC_RISK_ON_CANDIDATE`, `GOLD_HEDGE_BREAKOUT`, `SILVER_STRATEGIC_METALS_REGIME`, `SILVER_MOMENTUM_ACCELERATION`, `SILVER_EXHAUSTION_WATCH`, `HYG_JNK_BREAKDOWN_WATCH`. These are clearly domain-specific for a macro/crypto/metals intelligence view.

---

## 3. Current Architecture Map

| Area | Current Role | Key Files | Status |
|---|---|---|---|
| **Domain** | Asset universe (27 assets), market snapshot model | `domain/assets.py`, `domain/market_snapshot.py` | Stable |
| **Provider Layer** | Abstract `VerifiedProviderAdapter` ABC + mock | `providers/verified_adapter.py`, `providers/mock_market_provider.py` | Architecture ready; no live adapter |
| **Snapshot Store** | JSONL flat-file local storage; validates PAPER_SAFE/NO_EXECUTION | `storage/snapshot_store.py` | Stable; demo data only |
| **Ingestion Pipeline** | `ProviderIngestionService` orchestrates provider → snapshot store | `services/provider_ingestion_service.py` | Ready but unconnected (mock only) |
| **Mock Pipeline** | `MockSnapshotPipeline` with `MockMarketProvider` | `services/mock_snapshot_pipeline.py` | Used in tests only |
| **Source Observation** | `SourceObservationRecord` from provider payloads | `services/source_observation_service.py` | Stable |
| **Data Quality Service** | DQS scoring (decision: PASS/WARN/FAIL/MISSING) | `services/data_quality_service.py` | Stable |
| **Trigger Engine** | 8 named market/regime triggers | `services/trigger_engine.py` | Stable; domain-specific |
| **Risk Engine** | Risk action classifier (6 levels) | `services/risk_engine.py` | Stable |
| **Market Snapshot Service** | Assembles snapshot from DQS + triggers + provider data | `services/market_snapshot_service.py` | Stable |
| **CEO Report Service** | Generates plain-language briefing from risk/trigger output | `services/ceo_report_service.py` | Stable; lightweight interpretation |
| **Audit Service** | Audit log | `services/audit_service.py` | Present |
| **Snapshot Replay Core** | Loads + replays frozen snapshots through risk/trigger engines | `services/snapshot_replay_core.py` | Stable |
| **Snapshot Replay Service** | Main service: 810 lines, inherits 3 mixin stacks, 49+ diagnostic methods | `services/snapshot_replay_service.py` | Stable; growing complexity |
| **Source Diagnostics — Quality** | 30+ quality/completeness/drift/reconciliation diagnostics | `services/snapshot_replay_source_quality*.py` | Stable |
| **Source Diagnostics — Registry** | 9 registry-level contract/field-set/naming diagnostics | `services/snapshot_replay_source_registry*.py` | Stable (field-set gap fixed) |
| **Source Diagnostics — Timing** | Freshness decay, cadence, observation integrity, normalization | `services/snapshot_replay_source_timing*.py` | Stable |
| **Source Diagnostics — Recurrence** | Fallback usage recurrence, freshness timeline | `services/snapshot_replay_source_recurrence.py` | Stable (fields fixed) |
| **Regime Diagnostics** | Regime stability, DQS stability | `services/snapshot_replay_regime_diagnostics.py` | Stable |
| **Transition Diagnostics** | Replay comparison, drift classification, anomaly watchlist | `services/snapshot_replay_transition_diagnostics.py` | Stable |
| **API Routes — Core** | Backtest summary, replay, rolling diagnostics, DQS stability | `api/snapshot_replay_routes_core.py` | Stable |
| **API Routes — Quality** | 30+ source quality endpoints | `api/snapshot_replay_routes_source_quality.py` | Stable |
| **API Routes — Registry** | 9 registry/field-set endpoints | `api/snapshot_replay_routes_source_registry.py` | Stable |
| **API Routes — Timing** | Freshness/cadence/observation endpoints | `api/snapshot_replay_routes_source_timing.py` | Stable |
| **Serializers** | One serializer function per diagnostic model | `api/snapshot_replay_source_serializers*.py` | Stable |
| **CEO Report API** | Single CEO report endpoint | `api/ceo_report.py` | Present |
| **Dashboard** | Standalone Gradio, 7 tabs, wired to service | `dashboard/gradio_dashboard.py` | Foundation ready; Gradio not installed |
| **Source Diagnostic Contracts** | 49-slug contract registry + standard 7-field set | `services/snapshot_replay_source_diagnostic_contracts.py` | Stable; 49/49 consistent |
| **Tests** | 375 tests across 23 files | `tests/test_*.py` | Strong coverage |
| **Backup/Verification** | `verify_and_snapshot.py` creates clean ZIP backups | `scripts/verify_and_snapshot.py` | Working |
| **AI Coordination** | AI_CONTEXT.md, AI_RULES.md, AI_TASK_LOG.md, NEXT_TASK.md | Root markdown files | Working |

---

## 4. Current Strengths

**Architecture discipline:**
- Frozen dataclasses throughout — all diagnostic outputs are immutable, deterministic, and comparable.
- Explicit paper-safe flags (`paper_safe=True`, `network_calls=False`, `execution_side_effects="NO_EXECUTION"`) on every diagnostic model.
- Standard 7-field contract enforced across all 49 source diagnostic models (just verified 49/49).
- No wildcard imports. Explicit `__all__` re-export chains maintained.
- Route prefix enforced at `/api/v1/snapshots` — no double-prefix bugs.
- No circular imports.

**Test coverage:**
- 375 tests covering domain, services, API, storage, dashboard.
- Targeted + full test runs working cleanly.
- Ruff passes clean with no linting issues.

**Diagnostic surface breadth:**
- 49 named source diagnostics covering: field-set drift, naming contracts, registry binding, verification consistency, freshness decay, cadence, observation integrity, normalization, confidence drift, coverage reconciliation, severity ranking, fallback usage recurrence, and more.
- Rolling backtest diagnostics that compare snapshots over time and flag anomalies.

**Safety boundary:**
- No execution path anywhere in the codebase.
- No broker integration, no order placement, no portfolio mutation.
- Dashboard explicitly blocks `0.0.0.0`, `share=True`, `place_order`, `execute_trade`, `broker_api`, `live_market`.
- SnapshotStore rejects non-PAPER_SAFE, non-NO_EXECUTION payloads at persistence time.

**AI coordination workflow:**
- AI_CONTEXT.md, AI_RULES.md, AI_TASK_LOG.md, NEXT_TASK.md provide a clean low-token handoff protocol for continued AI-assisted development.
- verify_and_snapshot.py creates clean timestamped ZIP backups after every successful task.

**Mixin architecture:**
- `SnapshotReplayService` is cleanly split into mixin stacks: source quality, registry, timing, recurrence, regime, transition. Each mixin is independently testable.

---

## 5. Current Weaknesses / Missing Pieces

### 5.1 No live data — the fundamental gap

The system cannot ingest real market data without implementing concrete `VerifiedProviderAdapter` subclasses. The provider layer is an abstract ABC. The only provider is `MockMarketProvider`, which generates synthetic data. All current snapshots are from `ceo_report_demo_snapshots.jsonl` — a demo/test file.

**This means:** Everything the system diagnoses is based on demo data. The system is currently checking the quality of its own test data.

### 5.2 Diagnostic surface is primarily self-checking

The 49 source diagnostics mostly check whether the system's own code produces consistent field sets, correct naming conventions, proper contract coverage, and registry consistency. This is valuable for code quality assurance, but it is not yet producing market intelligence or source quality insights from real provider data.

A user running the dashboard today would see diagnostics about the system's own architectural consistency — not insights about market data quality.

### 5.3 CEO report is a template engine, not intelligence

`CEOReportService` produces plain-language output using string templates and hardcoded trigger labels. The quality of the output depends entirely on the trigger and risk engine inputs — which in turn depend on real provider data. On demo snapshots the report produces plausible-looking but demo-data-driven output. There is no interpretation intelligence beyond the template.

### 5.4 No scheduler or automated ingestion

There is no cron, task queue, or periodic job for ingesting snapshots. Ingestion requires manual execution of the provider pipeline. No real-time update mechanism exists.

### 5.5 Dashboard is foundationally ready but operationally unverified

Gradio is listed as a `pip install` manual step — it is not in a requirements file. The dashboard has not been verified end-to-end with real (non-demo) snapshot data. The validation buttons run subprocess commands which is correct and safe but adds subprocess dependency for basic operations.

### 5.6 No scenario simulation or backtest-vs-actual comparison

The system can replay saved snapshots but cannot:
- Generate synthetic alternative scenarios.
- Compare what the system predicted with what actually happened.
- Evaluate trigger accuracy over historical periods.
- Score the quality of risk actions over time.

### 5.7 No economic/news/calendar context layer

Triggers are based purely on asset price/quality data. No macro calendar events, no news sentiment, no economic release impact layer exists.

### 5.8 No deployment packaging, auth, or multi-user support

The system is single-user local. No authentication, no deployment configuration, no Docker/packaging, no HTTPS.

### 5.9 NEXT_TASK.md is stale

The current NEXT_TASK.md lists a task that was already completed. It needs updating to the next genuine work item.

---

## 6. Architecture vs. Product Value Gap

### Infrastructure (what currently exists):
- Storage, replay, risk engine, trigger engine, DQS, source observation.
- 49-diagnostic structural consistency surface.
- Clean API surface (FastAPI routes + serializers).
- Dashboard admin panel foundation.
- Strong test suite.

### Real user value (what currently works end-to-end):
- Replay any saved snapshot and get a risk/trigger classification + CEO briefing — **works on demo data**.
- Run rolling backtest diagnostics and see drift trend, anomaly watchlist, regime timeline — **works on demo data**.
- View snapshot browser in dashboard — **works if snapshots exist locally**.
- Verify code health (ruff, pytest, backup) via dashboard validation tab — **works**.

### What is still "system checking itself":
- All 49 source diagnostic endpoints — they verify internal code consistency (field sets, naming, registry bindings), not real source data quality.
- Contract coverage drift, field-set drift, surface count drift — these are architecture tests exposed as API endpoints.
- The rolling bundle coverage and group coverage diagnostics check whether the system's own contract registry is complete.

### To produce real insight, these things must happen first:
1. A real `VerifiedProviderAdapter` must be implemented for at least one live data source.
2. Real provider data must be ingested into the snapshot store.
3. The diagnostic surface can then be applied to real snapshots instead of demo ones.
4. The CEO report then reflects actual market state rather than demo output.

The gap is not in the architecture — it is in the data. The architecture is ready. The data pipeline is not connected.

---

## 7. Safety Boundary Review

**Confirmed safe:**
- `PAPER_ONLY` enforced via `SnapshotStore.ALLOWED_EXECUTION_MODES`.
- `REPLAY_ONLY` — no live ingestion endpoint exposed.
- `NO_EXECUTION` — no broker/order/execution code exists anywhere.
- Dashboard: `server_name="127.0.0.1"`, `share=False`, no `0.0.0.0`.
- All diagnostic models carry `paper_safe=True`, `network_calls=False`, `execution_side_effects="NO_EXECUTION"` explicitly.
- Dashboard source checks explicitly block: `place_order`, `execute_trade`, `buy_button`, `sell_button`, `broker_api`, `live_market`.
- No FastAPI mount of the dashboard (standalone only).

**Low-level risks to note (not currently violated, but worth tracking):**
- Dashboard validation buttons run `subprocess` to execute ruff/pytest/verify_and_snapshot. This is safe and local-only, but the subprocess execution surface should not be extended to run arbitrary commands.
- If Gradio is installed and the dashboard is exposed beyond localhost (which is currently blocked), the validation buttons could run system commands in a networked context. The current block is correct.
- `ceo_report_demo_snapshots.jsonl` in the name implies demo data; if real snapshots are later saved to this same file, there should be a clear naming/path separation to avoid confusion.

---

## 8. Missing Capabilities for a Strong E-YAY v1

### P0 — Keep the system stable and operationally verified
- Keep ruff/pytest/verify passing.
- Ensure dashboard works end-to-end with local snapshot data.
- Update NEXT_TASK.md.
- Complete end-to-end smoke test: load demo snapshots → replay → view CEO report in dashboard → verify all 7 tabs render correctly.
- Add requirements file (at minimum `fastapi`, `uvicorn`, `pydantic`) so the project is installable.

### P1 — Connect real data and make diagnostics meaningful
- Implement at least one concrete `VerifiedProviderAdapter` for a real, free data source (e.g., Yahoo Finance, CoinGecko, FRED API).
- Ingest real snapshots and separate real data from demo data.
- Apply source freshness diagnostics to real provider data — verify they surface actual staleness.
- Improve CEO report interpretation: move from string templates toward structured classification of regime state.
- Source freshness dashboard tab: show actual data quality across sources in real time.

### P2 — Improve replay intelligence
- Scenario simulation: generate variant snapshots with modified asset values.
- Paper backtest comparison: compare what the risk engine said at time T with subsequent market movement.
- Forecast accuracy log: track trigger activations over time.
- Economic/news/calendar integration (paper-safe read-only).
- Regime intelligence that does not depend only on asset price — add macro context layer.

### P3 — Operationalize the system
- Scheduled local ingestion (e.g., a simple cron or Windows Task Scheduler script).
- Exportable PDF/HTML reports.
- Better frontend (replace Gradio with a lightweight HTML dashboard if needed).
- User authentication if deployed beyond single machine.
- Deployment packaging (Docker, portable script).

---

## 9. Suggested Development Roadmap

### Phase 1: Stabilize and verify the local paper system (1–2 sessions)

**Goal:** Confirm the system works end-to-end with real local snapshots. Ensure every dashboard tab shows meaningful output. Fix NEXT_TASK.md. Add a requirements file.

**Tasks:**
- Update NEXT_TASK.md to the first meaningful next item.
- Create `requirements.txt` with minimum dependencies.
- Run dashboard manually, verify all 7 tabs with demo snapshots.
- Confirm snapshot browser shows snapshots from the local JSONL store.
- Confirm snapshot replay tab returns a CEO report.
- Confirm source diagnostics tab returns at least one structural diagnostic result.
- Confirm paper report preview shows CEOReport fields.

**Success criteria:** Dashboard runs cleanly with demo data; all tabs show non-empty output; no import errors.
**Tests required:** No new tests; confirm existing 375 pass.

---

### Phase 2: Make the dashboard genuinely useful (2–4 sessions)

**Goal:** The dashboard should show something the owner actually wants to look at — not just system health, but source quality status, regime snapshot, and briefing.

**Tasks:**
- Executive overview tab: add live snapshot count, last ingestion time, latest risk action from most recent replay, dominant regime.
- Source diagnostics tab: promote freshness decay timeline and fallback usage recurrence to first-class visual — show a simple table of which sources are stale/fresh.
- Paper report preview: improve CEOReport rendering — structured layout, not raw JSON.
- Snapshot browser: show diff between consecutive snapshots when two are selected.
- Validation tab: show last known ruff/pytest state, not just a button.

**Success criteria:** Owner opens dashboard and sees current regime, risk action, source health, and briefing — all from most recent local snapshot.
**Tests required:** Extended `test_dashboard.py` tests covering rendering callbacks.

---

### Phase 3: Connect real data ingestion (3–5 sessions)

**Goal:** Implement at least one concrete `VerifiedProviderAdapter` for a free, real data source. Ingest real snapshots.

**Tasks:**
- Choose one source (e.g., CoinGecko for BTC; FRED for US10Y, M2SL, CPI; Yahoo Finance for XAUUSD, BRENT).
- Implement a `VerifiedProviderAdapter` subclass for that source.
- Add a paper-safe ingestion script that runs the pipeline and saves to a separate `real_snapshots.jsonl` (not the demo file).
- Verify source observation records are correct for real payloads.
- Run freshness diagnostics on real snapshots — confirm they detect actual staleness.
- Update CEO report to show actual market state.

**Success criteria:** Ingestion script runs, saves real snapshot, dashboard shows real data. At least one source shows staleness or fallback correctly.
**Tests required:** Integration tests for the new adapter (with response fixtures, not live calls). Existing 375 tests unchanged.

---

### Phase 4: Add interpretation and report intelligence (3–5 sessions)

**Goal:** CEO report and dashboard show interpreted intelligence, not just classification labels.

**Tasks:**
- Regime narrative: generate a plain-language summary of the current macro regime based on trigger pattern (what does SILVER_EXHAUSTION + RED_ENERGY_SHOCK together mean?).
- Risk action explanation: for each risk action, explain which trigger combination drove it and whether the combination has appeared before in local replay history.
- Source quality score: produce a single composite source quality score per snapshot (e.g., 0–100 based on freshness, coverage, verification rate).
- Historical context: show how today's risk action compares to the last 10 replay results.
- Alert summary: highlight any new triggers that appeared since the last snapshot.

**Success criteria:** Dashboard shows a narrative briefing that an owner could read without understanding the codebase.
**Tests required:** Tests for narrative generation logic. CEOReport extended fields tested.

---

### Phase 5: Add learning loop and scenario evaluation (5+ sessions)

**Goal:** The system can evaluate its own past decisions and run scenario variants.

**Tasks:**
- Backtest-vs-outcome log: for each saved snapshot, record the risk action taken and tag it with what actually happened in the market (user-supplied label: VALIDATED / MISSED / FALSE_POSITIVE).
- Accuracy dashboard: show trigger hit rate, false positive rate, missed risk events over N snapshots.
- Scenario simulation: let owner modify one asset value and see how the risk action changes — fully paper-safe, no execution.
- Regime calendar: show historical regime classifications over time as a timeline.
- Minimum coverage floor alerts: alert when a required-for-core-report asset has been stale for >N snapshots.

**Success criteria:** Owner can load 90 days of snapshots, see trigger accuracy stats, and run a "what if BRENT was $120" scenario.
**Tests required:** New tests for scenario simulation (deterministic), backtest log model, accuracy calculations.

---

## 10. Recommended NEXT_TASK

**Recommended next task:**
> E-YAY dashboard end-to-end smoke test + operational verification: load demo snapshots, confirm all 7 tabs render meaningful output, add `requirements.txt`, update NEXT_TASK.md.

**Why:** The dashboard is wired but has never been verified with real data end-to-end in a documented test. Before adding any new features, confirm the current system actually works in practice — not just in unit tests. This is the lowest-risk, highest-confidence step before touching provider adapters or the interpretation layer.

**NEXT_TASK.md should be updated** with this task (it is currently stale, pointing to a completed task).

**Concrete NEXT_TASK.md content to write:**
```
Next task: Dashboard end-to-end smoke test + requirements.txt.
1. Pip install gradio.
2. Run: python -m backend.app.dashboard.gradio_dashboard
3. Verify all 7 tabs render with demo snapshots.
4. Document which tabs show empty output vs. meaningful output.
5. Add requirements.txt (fastapi, uvicorn, pydantic, gradio).
6. Update AI_CONTEXT.md + AI_TASK_LOG.md.
7. Update NEXT_TASK.md to next item.
```

---

## 11. Minimal-Token Claude Workflow Recommendation

Future Claude sessions should follow this protocol to avoid context bloat and redundant scanning:

**Start of every session:**
1. Read `AI_CONTEXT.md` — current checkpoint, completed task, active task.
2. Read `AI_RULES.md` — safety constraints, code rules, validation commands.
3. Read `AI_TASK_LOG.md` only if history of a specific prior decision is needed.
4. Read `NEXT_TASK.md` if the task is task-selection.
5. Read only files directly related to the task. Do not scan the whole repo.

**During implementation:**
- Make targeted changes to the minimum number of files.
- Run `ruff check backend tests` after every edit batch.
- Run targeted pytest (`-k "relevant_test_name"`) before full suite.
- Run full suite only to confirm final state.
- Run `python scripts/verify_and_snapshot.py` to create backup.

**After every successful task:**
- Update `AI_CONTEXT.md`: completed task, files edited, ruff/pytest/verify results, new backup path, next task.
- Append short summary to `AI_TASK_LOG.md`.
- Update `NEXT_TASK.md` with the next item.

**What to never do:**
- Do not scan the whole repo blindly.
- Do not re-read old chat history.
- Do not add features beyond what the task specifies.
- Do not remove existing tests or re-exports.
- Do not add wildcard imports.
- Do not expose any execution, trading, or broker surface.

---

## Appendix: Key File Counts (as of 2026-05-28)

| Module | Lines |
|---|---|
| `snapshot_replay_service.py` | 810 |
| `snapshot_replay_source_common.py` | 302 |
| `snapshot_replay_source_recurrence.py` | ~680 |
| `snapshot_replay_source_diagnostic_contracts.py` | ~60 |
| `gradio_dashboard.py` | ~500 (estimated) |
| `snapshot_replay_models.py` | ~160 (re-export hub) |
| Provider service files (30+ mixin files) | 50–200 each |
| Test files | 23 files, 375 tests total |

**Test-to-source ratio:** Good. The project has comprehensive test coverage relative to its size.

**Source diagnostic model count:** 49 models (all 7-field standard compliant as of 2026-05-28).

**API route count (snapshot replay):** ~55 GET endpoints across 4 router files.

---

*Report created by Claude Code (Sonnet 4.6) on 2026-05-28. Paper-safe audit only. No runtime code was edited.*
