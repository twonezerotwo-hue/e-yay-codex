# ARCHITECTURE_GAP_ANALYSIS.md
## E-YAY Snapshot Replay — Architecture vs. Code Gap Analysis
Date: 2026-05-28

---

## Audit Scope

Checked architecture assumptions against live code across:
- Service layer: snapshot_replay_service.py, mixin hierarchy
- Model layer: all 4 source model sub-modules
- Contract layer: snapshot_replay_source_diagnostic_contracts.py
- API layer: routes + serializers
- Dashboard: gradio_dashboard.py
- Tests: test_snapshot_replay_service.py, test_snapshot_replay_api.py, test_dashboard.py

---

## Gap Table

| ID  | Priority | Area           | Gap Description                                              | Status         |
|-----|----------|----------------|--------------------------------------------------------------|----------------|
| G01 | P0       | Models/Service | SnapshotReplaySourceDiagnosticContractFieldSetDrift missing  | IMPLEMENTING   |
| G02 | P0       | Models/Service | SnapshotReplayFullSurfaceResponseFieldSetConsistency missing  | IMPLEMENTING   |
| G03 | P0       | Contracts      | SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET not defined             | IMPLEMENTING   |
| G04 | P0       | Service        | No mixin for field-set drift / full-surface consistency       | IMPLEMENTING   |
| G05 | P0       | API            | No routes for field-set drift or full-surface consistency     | IMPLEMENTING   |
| G06 | P0       | Dashboard      | _SOURCE_DIAG_CHOICES missing 2 new diagnostics               | IMPLEMENTING   |
| G07 | P1       | Tests          | No tests for field-set drift or full-surface consistency      | IMPLEMENTING   |

---

## Architecture Assumptions Verified

- ✓ Registry-level diagnostics do NOT belong in SOURCE_DIAGNOSTIC_SERVICE_SLUGS
- ✓ Static field-set inspection uses dataclasses.fields(ModelClass) — no snapshot data needed
- ✓ Standard field set: {total_snapshots_requested, entries, failures, diagnostics, paper_safe, network_calls, execution_side_effects}
- ✓ All 49 source diagnostic slugs map to model classes in quality/drift/timing/registry sub-modules
- ✓ New mixin SnapshotReplaySourceRegistryFieldSetsMixin wires into SnapshotReplaySourceRegistryContractsMixin
- ✓ Re-export chain: models_source_registry → snapshot_replay_models → snapshot_replay_service __all__ → services/__init__
- ✓ Serializer chain: serializers_registry → serializers (hub) → routes

---

## Implementation Plan — P0 Items (This Session)

### Step 1: Models (snapshot_replay_models_source_registry.py)
Add 4 new frozen dataclasses:
- SnapshotReplaySourceDiagnosticContractFieldSetDriftEntry
- SnapshotReplaySourceDiagnosticContractFieldSetDrift
- SnapshotReplayFullSurfaceResponseFieldSetConsistencyEntry
- SnapshotReplayFullSurfaceResponseFieldSetConsistency

### Step 2: Contracts (snapshot_replay_source_diagnostic_contracts.py)
Add SOURCE_DIAGNOSTIC_STANDARD_FIELD_SET tuple.

### Step 3: New Mixin (snapshot_replay_source_registry_field_sets.py — CREATE)
SnapshotReplaySourceRegistryFieldSetsMixin with:
- build_source_diagnostic_contract_field_set_drift(self, *, snapshot_ids=None)
- build_full_surface_response_field_set_consistency(self, *, snapshot_ids=None)

### Step 4: Wire Mixin (snapshot_replay_source_registry_contracts.py)
Add SnapshotReplaySourceRegistryFieldSetsMixin to inheritance chain.

### Step 5: Re-export Chain
- snapshot_replay_source_common.py: add new model re-exports
- snapshot_replay_models.py: add new imports + __all__ entries
- snapshot_replay_service.py: add to __all__
- services/__init__.py: add imports

### Step 6: Serializers
- snapshot_replay_source_serializers_registry.py: add 2 serializer functions
- snapshot_replay_source_serializers.py: re-export 2 new serializers

### Step 7: API Routes (snapshot_replay_routes_source_registry.py)
Add 2 new GET routes:
- GET /backtest/source-diagnostic-contract-field-set-drift
- GET /backtest/full-surface-response-field-set-consistency

### Step 8: Dashboard (gradio_dashboard.py)
Add to _SOURCE_DIAG_CHOICES and _SOURCE_DIAG_METHOD.

### Step 9: Tests
Add tests to test_snapshot_replay_service.py and test_snapshot_replay_api.py.

---

## Architecture Confirmed Stable

- Route prefix: /api/v1/snapshots (correct)
- Wildcard imports: none in service or API layer
- Public re-exports (__all__): intact
- Safety flags: PAPER_ONLY / REPLAY_ONLY / NO_EXECUTION enforced
- 49-slug SOURCE_DIAGNOSTIC_SERVICE_SLUGS: unchanged
- Rolling bundle: unchanged
