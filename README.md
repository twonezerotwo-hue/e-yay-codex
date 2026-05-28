# E-yAy BrainChain

This repository contains the clean bootstrap of the E-yAy / BrainChain decision-support system.

## Clean Backup

Run the clean backup flow from the repository root:

```powershell
python scripts/verify_and_snapshot.py
```

The script first runs repo root `pytest` and then validates `docker compose config`. A clean ZIP backup is created only when both checks succeed.

Backups are written into `clean_backups/` with names like `eyay_clean_YYYYMMDDTHHMMSSZ.zip`. After a new clean backup is validated, the previous `eyay_clean_*.zip` backup is removed automatically. Non-clean ZIP files are left untouched.

To restore, unpack the latest clean backup into a fresh working directory and continue from that snapshot state.

## Phase 1 Deterministic Daily Report Core

Phase 1 introduces a deterministic daily report foundation with:
- YAML config registries in `config/`
- Source Registry config in `config/source_registry_v1.0.yaml`
- JSON schema validation in `schemas/`
- normalization, scoring, regime, and risk logic in `engine/`
- main asset enum/model foundation in `models/`
- source registry loading and mapping in `registry/`
- report construction in `reports/`
- audit record helpers in `audit/`

The report core is simulation-safe by default:
- verified data unavailable -> simulation or hypothetical output only
- Data Quality Score below `50` -> `NO_TRADE`
- critical missing data -> `NO_POSITION_INCREASE`
- Risk Engine remains the final gate

The Source Registry foundation enforces deterministic source binding rules:
- approved assets are enumerated explicitly
- every source is mapped to a known asset category
- unverified sources are limited to `simulation_only`
- verified-required sources remain the default for decision support inputs

## Paper-Safe Snapshot Persistence

Provider-backed ingestion can now persist reusable paper-safe input snapshots to a local JSONL store:
- storage lives in `backend/app/storage/snapshot_store.py`
- persistence is local-only and introduces no network or live execution behavior
- snapshot IDs are deterministic from `created_at`, `report_type`, and the bound source set unless an explicit ID is supplied
- saved payloads carry `NO_EXECUTION` decision permission and `PAPER_ONLY` or `NO_EXECUTION` execution mode
- saved payloads include source observations, audit/source-binding summaries, diagnostics inputs, and serialized report input snapshots for later replay or backtest use

The CEO report demo endpoint remains safe by default:
- `GET /api/v1/ceo-report/demo` stays simulation-only and does not persist by default
- `GET /api/v1/ceo-report/demo?persist_snapshot=true` may persist the report input snapshot locally
- if snapshot persistence fails, the endpoint returns safe diagnostics instead of crashing or escalating to execution

Saved paper-safe snapshots can now be replayed deterministically for paper/backtest reuse:
- `backend/app/services/snapshot_replay_service.py` reloads saved snapshot payloads from the local JSONL store
- replay reconstructs stored market snapshots and their saved DQS outputs before re-running trigger, risk, and CEO report generation
- replay rejects any payload that tries to bypass `NO_EXECUTION`, `PAPER_ONLY`, or `SIMULATION/PAPER_SAFE` constraints
- the backtest runner can iterate over saved snapshot IDs or the latest stored snapshots without introducing network or live execution behavior

API access is now available for saved paper snapshots:
- `GET /api/v1/snapshots/{snapshot_id}/replay` returns a deterministic replay of one saved snapshot with trigger, risk, and CEO report outputs
- `GET /api/v1/snapshots/backtest/summary` returns a paper-safe aggregate summary over saved snapshots
- both endpoints keep `NO_EXECUTION` semantics, return controlled failures for missing or unsafe payloads, and stay local/no-network

Replay API serialization is now split into dedicated modules:
- `backend/app/api/snapshot_replay.py` remains the route layer and request/error mapping entrypoint
- `backend/app/api/snapshot_replay_serializers.py` contains shared replay, comparison, backtest, and rolling-diagnostics serializers
- `backend/app/api/snapshot_replay_source_serializers.py` contains source-diagnostic and source-quality serializer functions
- response field names and paper-safe replay contracts remain unchanged

Replay analysis endpoints now support snapshot-to-snapshot diagnostics:
- `GET /api/v1/snapshots/compare` compares two saved paper snapshots and highlights deterministic trigger, risk, and source-status deltas
- `GET /api/v1/snapshots/backtest/rolling-diagnostics` walks saved paper snapshots in chronological order and summarizes rolling risk-action transitions
- comparison and rolling diagnostics remain replay-only analysis paths and never introduce execution or network side effects

Drift and anomaly diagnostics are now part of replay analysis:
- snapshot comparison now classifies drift deterministically with stable severity labels and anomaly flags
- rolling diagnostics now produce an anomaly watchlist over repeated replay transitions
- watchlist output stays paper-safe and is derived only from local replay state, source-status deltas, and deterministic risk/trigger transitions

Trend and regime summaries are now included in rolling replay diagnostics:
- drift trend scoring classifies replay direction as `improving`, `deteriorating`, `stable`, or `insufficient_data`
- each rolling replay batch now exposes a deterministic trend score and severity bucket
- replay regime summary reports dominant saved regime, transition count, mixed or unstable distribution, and safe diagnostics when regime metadata is missing
- rolling replay batches now also expose a deterministic drift trend leaderboard for repeated drift codes
- rolling replay batches now expose a deterministic trigger persistence leaderboard for repeated active trigger types
- rolling replay batches now expose a deterministic source gap recurrence leaderboard for repeated missing or stale source IDs
- rolling replay batches now expose a deterministic source freshness decay timeline for fresh, degraded, stale, and missing-freshness paths
- rolling replay batches now expose deterministic fallback-provider recurrence diagnostics with timeline visibility, provider ranking, and severity scoring
- rolling replay batches now expose raw payload reference completeness diagnostics with complete, partial, degraded, and invalid classification
- rolling replay batches now expose deterministic source observation cadence drift diagnostics with stable, irregular, degraded, and insufficient-data classification
- rolling replay batches now expose source record completeness diagnostics with missing-field visibility for persisted source observation records
- rolling replay batches now expose source registry binding drift diagnostics with registry-version, provider-binding, and asset-binding mismatch visibility
- rolling replay batches now expose source decision-usage consistency diagnostics with registry mismatch, unsafe paper-safe usage, and missing decision-usage visibility
- rolling replay batches now expose source verification drift diagnostics with stable, degrading, improving, mixed, and insufficient-data classification
- rolling replay batches now expose paper-safe source flag consistency diagnostics with unsafe, missing, malformed, and contradictory source flag visibility
- rolling replay batches now expose source observation summary drift diagnostics with expected-count baselines, normalization drift visibility, and stable/degrading/improving/mixed classification
- rolling replay batches now expose provider adapter contract consistency diagnostics with persisted contract alignment, missing metadata visibility, and bound-source count mismatch detection
- rolling replay batches now expose source observation timestamp integrity drift diagnostics with ordering regressions, missing timestamp visibility, and mapped-at regression detection
- rolling replay batches now expose source observation record/summary reconciliation diagnostics with persisted count mismatch and missing-summary-field visibility
- rolling replay batches now expose source observation normalization mode drift diagnostics with stable, drifting, degraded, and insufficient-data classification
- rolling replay batches now expose mapped-at alignment consistency diagnostics with batch-anchor, per-source alignment, and persisted source-observation map divergence visibility
- rolling replay batches now expose source observation confidence drift diagnostics with stable, degrading, improving, mixed, and insufficient-data classification
- rolling replay batches now expose verified-source coverage reconciliation diagnostics with expected verified source coverage, missing verified IDs, and unexpected verified-source visibility
- rolling replay batches now expose source observation availability-lag drift diagnostics with stable, degrading, improving, mixed, and insufficient-data classification
- rolling replay batches now expose source freshness summary reconciliation diagnostics with record-level freshness alignment, stale-source summary divergence, and missing freshness visibility
- rolling replay batches now expose source observation freshness-seconds drift diagnostics with deterministic worsening/improving timing deltas over persisted paper snapshots
- rolling replay batches now expose source freshness-status threshold reconciliation diagnostics that compare persisted freshness statuses against deterministic freshness-seconds threshold bands
- rolling replay batches now expose source diagnostics high-severity drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted severity-ranking pressure
- rolling replay batches now expose source diagnostics warning-feature drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted warning-level pressure
- rolling replay batches now expose source diagnostics info-feature drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted info-level pressure
- rolling replay batches now expose source diagnostics zero-rank drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted zero-rank pressure
- rolling replay batches now expose source diagnostics severity-label drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted severity-level pressure
- rolling replay batches now expose source diagnostics severity-rank drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted severity-ranking pressure
- rolling replay batches now expose source diagnostics severity-rank density drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted average severity-ranking pressure per actionable feature
- rolling replay batches now expose source diagnostics severity-rank spread drift diagnostics with degrading, improving, mixed, and insufficient-data classification over persisted severity-ranking range width
- rolling replay batches now expose source diagnostics severity-ranking critical-count reconciliation diagnostics that compare persisted critical flags against deterministic critical-severity derivation
- rolling replay batches now expose source diagnostics severity-ranking warning-count reconciliation diagnostics that compare persisted warning labels against deterministic warning-severity derivation
- rolling replay batches now expose source diagnostics severity-ranking info-count reconciliation diagnostics that compare persisted info labels against deterministic info-severity derivation
- rolling replay batches now expose source diagnostics severity-ranking non-actionable-count reconciliation diagnostics that compare persisted info labels against deterministic zero-rank derivation
- rolling replay batches now expose source diagnostics severity-ranking rank/label consistency reconciliation diagnostics that compare persisted severity labels against deterministic rank-derived severity labels
- rolling replay batches now expose source diagnostics severity-ranking rank-order continuity reconciliation diagnostics that compare persisted ranking order against deterministic descending severity-rank order
- rolling replay batches now expose source diagnostics severity-ranking rank-gap continuity reconciliation diagnostics that compare persisted adjacent rank gaps against deterministic descending severity-rank gap sequences
- rolling replay batches now expose source diagnostics severity-ranking rank-gap magnitude reconciliation diagnostics that compare persisted adjacent rank-gap magnitudes against deterministic descending severity-rank gap magnitudes
- rolling replay batches now expose a replay regime timeline with dominant-regime matching and safe missing-regime diagnostics per snapshot
- rolling replay batches now expose a DQS stability summary for stable, improving, deteriorating, mixed, or insufficient-data quality paths
- rolling replay batches now expose a risk action stability summary for stable, tightening, relaxing, volatile, or insufficient-data paths
- rolling replay batches now expose a NO_EXECUTION guardrail consistency view that flags unsafe persisted permissions without executing anything

Replay diagnostics also expose focused leaderboard and timeline API routes:
- `GET /api/v1/snapshots/backtest/source-gap-recurrence-leaderboard` returns paper-safe ranked missing or stale source-gap recurrence entries over saved snapshots
- `GET /api/v1/snapshots/backtest/source-freshness-decay-timeline` returns paper-safe freshness decay timeline entries and stable/degrading/improving classification over saved snapshots
- `GET /api/v1/snapshots/backtest/fallback-usage-recurrence` returns paper-safe fallback-provider recurrence diagnostics with deterministic ranking and timeline visibility
- `GET /api/v1/snapshots/backtest/raw-payload-reference-completeness` returns paper-safe raw payload reference completeness diagnostics and malformed-reference visibility over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-cadence-drift` returns paper-safe source observation cadence drift diagnostics and cadence-gap visibility over saved snapshots
- `GET /api/v1/snapshots/backtest/source-record-completeness` returns paper-safe persisted source record completeness diagnostics and missing-field visibility over saved snapshots
- `GET /api/v1/snapshots/backtest/source-registry-binding-drift` returns paper-safe source registry binding drift diagnostics and highlights source/provider/asset binding mismatches over saved snapshots
- `GET /api/v1/snapshots/backtest/source-decision-usage-consistency` returns paper-safe source decision-usage consistency diagnostics and highlights unsafe or registry-mismatched decision usage over saved snapshots
- `GET /api/v1/snapshots/backtest/source-verification-drift` returns paper-safe source verification drift diagnostics and highlights degrading, improving, mixed, or insufficient verification paths over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-contract-coverage-drift` returns paper-safe source diagnostic contract coverage drift diagnostics and nested endpoint coverage consistency for missing service builder, API route, or serializer coverage gaps over saved snapshots
- `GET /api/v1/snapshots/backtest/rolling-source-diagnostic-bundle-coverage-drift` returns paper-safe rolling source diagnostic bundle coverage drift diagnostics and nested dedicated-versus-rolling consistency for missing rolling bundle, dedicated endpoint, or serializer coverage gaps over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostic-group-coverage-drift` returns paper-safe source diagnostic group coverage drift diagnostics and nested group alignment consistency for missing service, route, serializer, contract-registry, or rolling bundle group coverage over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostic-surface-count-drift` returns paper-safe source diagnostic surface count drift diagnostics and nested contract surface count consistency for contract-registry, service-builder, route, serializer, rolling-bundle, and group-count mismatches over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostic-metadata-completeness-drift` returns paper-safe source diagnostic metadata completeness drift diagnostics and nested contract metadata normalization consistency for missing, invalid, duplicated, or conflicting contract-registry, builder, route, serializer, rolling-bundle, and rolling-serializer metadata over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostic-naming-contract-drift` returns paper-safe source diagnostic naming contract drift diagnostics and nested builder/serializer/route naming consistency for invalid, mismatched, duplicated, or conflicting diagnostic-key, builder, route, serializer, rolling-bundle, and rolling-serializer names over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostic-contract-signature-drift` returns paper-safe source diagnostic contract signature drift diagnostics and nested full-surface contract signature consistency for missing, invalid, mismatched, duplicated, or conflicting contract, builder, route, serializer, rolling-bundle, and rolling-serializer signatures over saved snapshots
- `GET /api/v1/snapshots/backtest/paper-safe-source-flag-consistency` returns paper-safe source flag consistency diagnostics and highlights unsafe, missing, malformed, or contradictory paper-safe flags over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-summary-drift` returns paper-safe source observation summary drift diagnostics and highlights summary-score, count-delta, and normalization drift paths over saved snapshots
- `GET /api/v1/snapshots/backtest/provider-adapter-contract-consistency` returns paper-safe provider adapter contract consistency diagnostics and highlights contract mismatches, missing metadata, and bound-source count drift over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-timestamp-integrity-drift` returns paper-safe source observation timestamp integrity drift diagnostics and highlights ordering regressions, missing timestamps, and mapped-at regressions over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-record-summary-reconciliation` returns paper-safe source observation record/summary reconciliation diagnostics and highlights persisted summary count mismatches and missing summary fields over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-normalization-mode-drift` returns paper-safe source observation normalization mode drift diagnostics and highlights persisted normalization-mode transitions over saved snapshots
- `GET /api/v1/snapshots/backtest/mapped-at-alignment-consistency` returns paper-safe mapped-at alignment consistency diagnostics and highlights normalization-anchor, stored-at, and source-observation-map divergence over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-confidence-drift` returns paper-safe source observation confidence drift diagnostics and highlights degrading, improving, mixed, or insufficient confidence paths over saved snapshots
- `GET /api/v1/snapshots/backtest/verified-source-coverage-reconciliation` returns paper-safe verified-source coverage reconciliation diagnostics and highlights missing or unexpected verified source IDs over saved snapshots
- `GET /api/v1/snapshots/backtest/source-observation-availability-lag-drift` returns paper-safe source observation availability-lag drift diagnostics and highlights worsening or improving observed-to-available timing over saved snapshots
- `GET /api/v1/snapshots/backtest/source-freshness-summary-reconciliation` returns paper-safe source freshness summary reconciliation diagnostics and highlights stale-source summary mismatches and missing freshness metadata over saved snapshots
- `GET /api/v1/snapshots/backtest/source-freshness-policy-drift` returns paper-safe source freshness policy drift diagnostics and highlights stable, degrading, improving, or mixed policy coverage over saved snapshots
- `GET /api/v1/snapshots/backtest/stale-source-list-threshold-reconciliation` returns paper-safe stale-source list threshold reconciliation diagnostics and highlights mismatches between persisted stale source IDs and deterministic freshness-policy evaluation
- `GET /api/v1/snapshots/backtest/source-diagnostics-freshness-evaluation-mode-drift` returns paper-safe source diagnostics freshness-evaluation-mode drift diagnostics and highlights stable, drifting, degraded, or insufficient-data summary mode behavior over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-stale-asset-count-reconciliation` returns paper-safe source diagnostics stale-asset count reconciliation diagnostics and highlights mismatches between persisted stale-asset summary counts and persisted severity ranking breakdowns
- `GET /api/v1/snapshots/backtest/source-diagnostics-average-coverage-drift` returns paper-safe source diagnostics average-coverage drift diagnostics and highlights degrading, improving, mixed, or insufficient-data coverage movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-minimum-coverage-floor-reconciliation` returns paper-safe source diagnostics minimum-coverage floor reconciliation diagnostics and highlights mismatches between persisted summary floors and deterministic severity-ranking or ready-feature derivation
- `GET /api/v1/snapshots/backtest/source-diagnostics-ready-feature-drift` returns paper-safe source diagnostics ready-feature drift diagnostics and highlights degrading, improving, mixed, or insufficient-data ready-feature movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-stale-feature-drift` returns paper-safe source diagnostics stale-feature drift diagnostics and highlights degrading, improving, mixed, or insufficient-data stale-feature movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-critical-feature-drift` returns paper-safe source diagnostics critical-feature drift diagnostics and highlights degrading, improving, mixed, or insufficient-data critical-feature movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-feature-count-reconciliation` returns paper-safe source diagnostics severity-ranking feature-count reconciliation diagnostics and highlights mismatches between persisted ranking counts and deterministic actionable-entry counts
- `GET /api/v1/snapshots/backtest/source-diagnostics-high-severity-drift` returns paper-safe source diagnostics high-severity drift diagnostics and highlights degrading, improving, mixed, or insufficient-data high-severity movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-warning-feature-drift` returns paper-safe source diagnostics warning-feature drift diagnostics and highlights degrading, improving, mixed, or insufficient-data warning-feature movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-info-feature-drift` returns paper-safe source diagnostics info-feature drift diagnostics and highlights degrading, improving, mixed, or insufficient-data info-feature movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-zero-rank-drift` returns paper-safe source diagnostics zero-rank drift diagnostics and highlights degrading, improving, mixed, or insufficient-data zero-rank movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-label-drift` returns paper-safe source diagnostics severity-label drift diagnostics and highlights degrading, improving, mixed, or insufficient-data severity-level movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-rank-drift` returns paper-safe source diagnostics severity-rank drift diagnostics and highlights degrading, improving, mixed, or insufficient-data severity-ranking movement over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-rank-density-drift` returns paper-safe source diagnostics severity-rank density drift diagnostics and highlights degrading, improving, mixed, or insufficient-data average rank pressure per actionable feature over saved snapshots
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-rank-spread-drift` returns paper-safe source diagnostics severity-rank spread drift diagnostics and highlights degrading, improving, mixed, or insufficient-data severity-ranking range-width movement over saved snapshots
- snapshot replay source quality drift internals are now split across focused summary and severity submodules while preserving existing response contracts and replay behavior
- snapshot replay source quality drift severity internals are now split across focused basic and rank-oriented submodules while preserving existing response contracts and replay behavior
- snapshot replay source quality drift severity basic internals are now split across focused feature-oriented and basic rank/label submodules while preserving existing response contracts and replay behavior
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-critical-count-reconciliation` returns paper-safe source diagnostics severity-ranking critical-count reconciliation diagnostics and highlights mismatches between persisted critical flags and deterministic critical-severity derivation
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-warning-count-reconciliation` returns paper-safe source diagnostics severity-ranking warning-count reconciliation diagnostics and highlights mismatches between persisted warning labels and deterministic warning-severity derivation
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-info-count-reconciliation` returns paper-safe source diagnostics severity-ranking info-count reconciliation diagnostics and highlights mismatches between persisted info labels and deterministic info-severity derivation
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-non-actionable-count-reconciliation` returns paper-safe source diagnostics severity-ranking non-actionable-count reconciliation diagnostics and highlights mismatches between persisted info labels and deterministic zero-rank derivation
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-label-consistency-reconciliation` returns paper-safe source diagnostics severity-ranking rank/label consistency reconciliation diagnostics and highlights mismatches between persisted severity labels and deterministic rank-derived severity labels
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-order-continuity-reconciliation` returns paper-safe source diagnostics severity-ranking rank-order continuity reconciliation diagnostics and highlights mismatches between persisted ranking order and deterministic descending severity-rank order
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-gap-continuity-reconciliation` returns paper-safe source diagnostics severity-ranking rank-gap continuity reconciliation diagnostics and highlights mismatches between persisted adjacent rank gaps and deterministic descending severity-rank gap sequences
- `GET /api/v1/snapshots/backtest/source-diagnostics-severity-ranking-rank-gap-magnitude-reconciliation` returns paper-safe source diagnostics severity-ranking rank-gap magnitude reconciliation diagnostics and highlights mismatches between persisted adjacent rank-gap magnitudes and deterministic descending severity-rank gap magnitudes
- snapshot replay source quality reconciliation internals are now split across focused submodules for core consistency checks, count-based reconciliations, and severity-ranking order reconciliations while preserving existing response contracts
- `GET /api/v1/snapshots/backtest/source-diagnostics-missing-source-feature-count-reconciliation` returns paper-safe source diagnostics missing-source feature-count reconciliation diagnostics and highlights mismatches between persisted missing-source feature counts and persisted severity ranking breakdowns
- `GET /api/v1/snapshots/backtest/source-diagnostics-missing-asset-count-reconciliation` returns paper-safe source diagnostics missing-asset count reconciliation diagnostics and highlights mismatches between persisted missing-asset summary counts and persisted severity ranking breakdowns
- snapshot replay source quality reconciliation count internals are now split across focused basic and severity-ranking submodules while preserving existing response contracts and replay behavior
- `GET /api/v1/snapshots/backtest/source-observation-freshness-seconds-drift` returns paper-safe source observation freshness-seconds drift diagnostics and highlights worsening or improving persisted freshness timing over saved snapshots
- `GET /api/v1/snapshots/backtest/source-freshness-status-threshold-reconciliation` returns paper-safe freshness-status threshold reconciliation diagnostics and highlights mismatches between persisted freshness statuses and deterministic freshness-seconds threshold bands
- snapshot replay source timing internals are now split across focused observation and freshness submodules while preserving existing response contracts and replay behavior
- snapshot replay source timing freshness internals are now split across focused decay/policy and freshness-status submodules while preserving existing response contracts and replay behavior
- snapshot replay source timing observation internals are now split across focused cadence/availability-lag and integrity/alignment submodules while preserving existing response contracts and replay behavior
- snapshot replay source quality serializers are now split across focused common, completeness, reconciliation, and drift modules while preserving existing endpoint paths, field names, and replay behavior
- snapshot replay source quality drift severity feature internals are now split across focused stale, alert, and info submodules while preserving existing response contracts and replay behavior
- snapshot replay source registry internals are now split across focused verification, contract-coverage, and rolling-coverage submodules while preserving existing response contracts and replay behavior
- snapshot replay source registry contract diagnostics internals are now split across focused contract-coverage, group-coverage, surface-count, and metadata-consistency submodules while preserving existing response contracts and replay behavior
- `GET /api/v1/snapshots/backtest/trigger-persistence-leaderboard` returns paper-safe ranked trigger persistence entries over saved snapshots
- `GET /api/v1/snapshots/backtest/drift-trend-leaderboard` returns paper-safe ranked drift trend entries over saved snapshots
- `GET /api/v1/snapshots/backtest/dqs-stability` returns paper-safe aggregate DQS decision stability diagnostics over saved snapshots
- `GET /api/v1/snapshots/backtest/risk-action-stability` returns paper-safe risk action stability diagnostics over saved snapshots
- `GET /api/v1/snapshots/backtest/regime-timeline` returns paper-safe saved regime chronology, transition flags, and missing-regime diagnostics
- `GET /api/v1/snapshots/backtest/no-execution-guardrail-consistency` returns paper-safe persisted-permission consistency diagnostics and violation payloads for saved snapshots
- both routes remain replay-only, local-only, and keep `NO_EXECUTION` behavior intact
- snapshot replay source serializers are now split across focused quality, timing, and registry serializer modules while preserving existing endpoint paths, field names, and replay behavior
- snapshot replay model dataclasses are now split across focused core, source quality, source drift, source timing, and source registry model modules while preserving existing import compatibility through `snapshot_replay_models.py`
- snapshot replay route handlers are now split across focused core, source quality, source timing, and source registry route modules while preserving existing endpoint paths, field names, service calls, and replay behavior

The daily report now includes deterministic `source_binding` coverage:
- every asset in the main asset catalog appears in the report binding section
- coverage is explicit as `covered` or `missing`
- source IDs are attached per asset in a stable order
- live eligibility stays `false` unless an active verified-required source exists
- simulation-only assets remain visible without being promoted to live-decision inputs

Feature-level source diagnostics are also enforced:
- each feature declares its required assets in the versioned feature registry
- minimum decision-usage requirements are schema-validated
- the report exposes missing or insufficient source coverage per feature
- diagnostics stay deterministic and explain why a feature is or is not source-ready

Source freshness policy is now part of the deterministic report path:
- the versioned Source Registry defines max source age per cadence
- stale or timestamp-missing sources are reported explicitly
- feature diagnostics surface stale required assets separately from missing assets
- freshness checks stay observational and never bypass the Risk Engine

Feature diagnostics now include deterministic scoring and ranking:
- each feature receives a stable coverage score between `0` and `100`
- missing sources, insufficient decision usage, and stale sources reduce coverage score predictably
- diagnostics are ranked by deterministic severity rules
- severity ordering remains reproducible across runs and surfaces the most urgent source issues first

Run the full project test suite from the repository root:

```powershell
pytest
```

## Local Gradio Dashboard

The E-YAY local paper dashboard is a standalone Gradio admin panel for replay, diagnostics, snapshot inspection, and validation.

**Safety:** `PAPER_ONLY | REPLAY_ONLY | NO_EXECUTION | LOCAL_DASHBOARD`
No live data. No trading. No broker integration. No execution buttons. Local-only (`127.0.0.1`).

### Install dashboard dependency

```powershell
python -m pip install -r requirements-dashboard.txt
```

Or directly:

```powershell
python -m pip install gradio
```

### Run the dashboard

```powershell
python -m backend.app.dashboard.gradio_dashboard
```

### Access

URL: `http://127.0.0.1:7867`

### Dashboard tabs

| Tab | Description |
|---|---|
| Executive Overview | Latest backup, snapshot count, safety label, next task |
| Snapshot Replay | Replay any saved paper snapshot by ID — returns risk action, CEO report, triggers |
| Rolling Diagnostics | Rolling backtest over saved paper snapshots — drift trend, anomaly watchlist, regime timeline |
| Source Diagnostics | 9 source-level contract/field-set/naming/registry diagnostics |
| Snapshot Browser | Lists saved local paper snapshots with metadata |
| Paper Report Preview | Plain-language CEO report from any saved snapshot |
| Validation | Run ruff, pytest, verify_and_snapshot locally |

### Notes

- Dashboard does not mount into FastAPI — standalone only.
- `share=False` — never exposed beyond localhost.
- No `0.0.0.0` host — bound to `127.0.0.1` only.
- All outputs are paper-safe replay results from local stored snapshots.
- No live market data is fetched.
