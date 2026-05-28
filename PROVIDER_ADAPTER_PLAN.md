# PROVIDER_ADAPTER_PLAN.md

## Summary

First concrete read-only provider adapter for the E-YAY local paper/replay system.
Chosen source: **Stooq daily CSV** (free, no API key, no registration, daily cadence).
Status: **registry-bound adapter wired and integration-tested**. Pipeline integration
complete for QQQ/HYG/JNK/FXI. Source registry YAML unchanged (see §Registry YAML note).

---

## Chosen Provider: Stooq Daily CSV

**Why Stooq:**
- Free public daily OHLCV data, no API key required.
- Simple, stable CSV format with Date/Open/High/Low/Close/Volume columns.
- Covers US ETFs (QQQ, HYG, JNK, FXI) that map directly to existing AssetCode values.
- Daily cadence is appropriate for paper/replay use — no realtime constraints.
- Failure mode is graceful: HTTP error or bad CSV → ValueError, never silently wrong.

**Why not CoinGecko first:**
- Rate limits on free tier without auth; Stooq has no such constraint for daily data.
- Stooq ETF coverage maps more directly to existing credit/equity AssetCodes.

---

## Architecture Fit

```
StooqDailyProvider(MarketProvider)
    ↓  get_asset_data(asset_code)
    ↓  → MarketProviderPayload
    
    wrapped by existing:
SourceRegistryBoundProviderAdapter(VerifiedProviderAdapter)
    ↓  get_asset_data(asset_code)
    ↓  → VerifiedProviderPayload
    
    consumed by existing:
ProviderIngestionService.run()
    ↓  → ProviderIngestionResult → SnapshotStore
```

`StooqDailyProvider` is a `MarketProvider` only — it does not implement `VerifiedProviderAdapter`.
To use it in ingestion, wrap it in `SourceRegistryBoundProviderAdapter` with the appropriate
bindings from the source registry. That wiring is intentionally deferred.

---

## Supported Assets

| AssetCode | Stooq Symbol | Unit          | Category       |
|-----------|-------------|---------------|----------------|
| QQQ       | `qqq.us`    | usd_per_share | equities_us    |
| HYG       | `hyg.us`    | usd_per_share | credit         |
| JNK       | `jnk.us`    | usd_per_share | credit         |
| FXI       | `fxi.us`    | usd_per_share | equities_china |

For all other AssetCodes, `get_asset_data()` raises `ValueError` immediately.
Units match `AssetDefinition.unit` exactly so `MarketSnapshot` validation passes.

---

## Stooq CSV Format

URL template: `https://stooq.com/q/d/l/?s={symbol}&i=d`

Example response:
```
Date,Open,High,Low,Close,Volume
2026-05-26,480.10,485.30,479.00,483.25,54312000
2026-05-27,483.50,488.00,482.00,486.75,61234000
```

Parsing rule: take the **last row** (most recent trading day), extract `Date` and `Close`.

---

## Field Mapping: Stooq CSV → MarketProviderPayload

| MarketProviderPayload field | Source                          |
|-----------------------------|---------------------------------|
| asset_symbol                | AssetCode argument              |
| value                       | `float(Close)`                  |
| unit                        | per-asset mapping (usd_per_share) |
| source_name                 | `"stooq_daily_csv"`             |
| source_tier                 | `SourceTier.SECONDARY`          |
| observed_at                 | `datetime.strptime(Date, "%Y-%m-%d").replace(tzinfo=UTC)` |
| available_at                | same as observed_at             |
| stored_at                   | `datetime.now(UTC)` at call time |
| fallback_used               | `False`                         |
| raw_payload_ref             | `"stooq://daily/{stooq_symbol}"` |

---

## Timestamp Handling

- `observed_at`: Stooq Date field parsed to midnight UTC of the trading day.
- `available_at`: Same as `observed_at` (data is available on close of that day).
- `stored_at`: Current wall-clock UTC at ingestion time.
- Invariant guaranteed: `stored_at >= available_at >= observed_at` (today >= past date). ✓

---

## Failure Modes

| Condition                         | Behaviour                            |
|-----------------------------------|--------------------------------------|
| Asset not in supported set        | `ValueError` — clear message         |
| Network error (live fetch)        | Propagated from `fetch_fn`           |
| Empty CSV body                    | `ValueError: empty or unrecognised`  |
| CSV has no data rows (header only)| `ValueError: empty or unrecognised`  |
| Missing Date or Close column      | `ValueError: missing expected column`|
| Non-numeric Close value           | `ValueError: non-numeric Close`      |
| Blank Date or Close field         | `ValueError: blank Date or Close`    |

All failures propagate to `ProviderIngestionService` which counts them as `failed_snapshots`.
No silent fallbacks, no partial data, no default values on error.

---

## Test Strategy: No-Network

`StooqDailyProvider` accepts an injectable `fetch_fn: Callable[[str], str]`.
Default is `_default_fetch` (uses `urllib.request`).
All tests pass a local lambda: `lambda _url: <fixture_csv_string>`.

Tests cover:
- Correct parse from fixture CSV (value, unit, timestamps, source attribution)
- Multi-row CSV: last row selected
- Per-asset correct unit returned
- Unsupported asset: ValueError
- Empty CSV: ValueError
- Header-only CSV: ValueError
- Missing column: ValueError
- Non-numeric Close: ValueError
- Source URL template includes expected stooq symbol
- stored_at is current UTC wall-clock (within test duration)

No test touches the network. The default `_default_fetch` is only used for live runs.

---

## Pipeline Integration Map

### Current state (after wiring task)

**Wired and tested:**
- `build_stooq_source_bindings()` — programmatic `ProviderSourceBinding` dicts for
  QQQ/HYG/JNK/FXI (simulation_only, paper_safe=True, active=True).
- `build_stooq_registry_bound_adapter(fetch_fn)` — factory wrapping `StooqDailyProvider`
  in `SourceRegistryBoundProviderAdapter` with the 4 Stooq bindings.
- Both exported from `app.providers`.
- `ProviderIngestionService.run(assets=stooq_assets)` produces a complete
  `ProviderIngestionResult` with `paper_safe_sources=4`, `simulation_only_sources=4`.
- Can persist to a `SnapshotStore` (e.g., `stooq_paper_snapshots.jsonl`).
- 19 integration tests in `backend/tests/test_stooq_ingestion.py` — all offline.

**Registry YAML note:** `config/source_registry_v1.0.yaml` is intentionally NOT modified.
The existing test `test_unverified_registry_entries_are_simulation_only` asserts exactly
`{BTCXAUK, XAUUSDK, XAGUSDK}` for unverified entries, and
`test_source_freshness_and_feature_diagnostics_flag_stale_sources` asserts
`total_active_sources == total_sources`. Adding inactive Stooq entries would
fail both tests. Bindings are kept programmatic — equally functional and safer.

### How to run Stooq ingestion (live, paper only)

```python
from app.providers import build_stooq_registry_bound_adapter
from app.domain.assets import get_asset_definition
from app.domain import AssetCode
from app.services import MarketSnapshotService, ProviderIngestionService
from app.storage import SnapshotStore

# Supply a real database session instead of FakeSession
adapter = build_stooq_registry_bound_adapter()  # uses urllib (live)
assets = tuple(get_asset_definition(c) for c in (
    AssetCode.QQQ, AssetCode.HYG, AssetCode.JNK, AssetCode.FXI
))
result = ProviderIngestionService(
    MarketSnapshotService(session), adapter
).run(
    assets=assets,
    persist_result=True,
    snapshot_store=SnapshotStore("backend/storage_data/stooq_paper_snapshots.jsonl"),
    snapshot_metadata={
        "source_registry_version": "1.0",
        "mode": "PAPER_SAFE",
        "execution_mode": "PAPER_ONLY",
        ...
    },
)
```

### Future wiring (still deferred)
- Provider factory / registry lookup by string name.
- Add Stooq sources to `source_registry_v1.0.yaml` when a multi-source-per-asset
  index strategy is in place (so existing `build_provider_source_bindings()` can
  handle multiple sources per asset without overwriting).
- Dashboard button to trigger Stooq fetch — not safe without explicit user action.

---

## What Is NOT Implemented

- Source registry YAML entries for Stooq (intentional — see Registry YAML note above).
- Provider factory / registry lookup by string provider name.
- Realtime or intraday data (Stooq daily only).
- XAUUSD, XAGUSD via Stooq (Stooq tickers for spot metals are uncertain; deferred).
- Rate limiting / backoff / retry logic (out of scope for skeleton).
- Auth / API key (Stooq needs none for daily CSV).
- End-to-end snapshot replay of a Stooq-sourced snapshot (deferred — next task).
- Dashboard button to trigger live Stooq fetch (not safe without explicit user action).

---

## Files Created / Modified

| File                                          | Action   |
|-----------------------------------------------|----------|
| `PROVIDER_ADAPTER_PLAN.md`                    | Created  |
| `backend/app/providers/stooq_adapter.py`      | Created + Updated (bindings + factory) |
| `backend/tests/test_stooq_adapter.py`         | Created  |
| `backend/app/providers/__init__.py`           | Updated (3× new exports) |
| `backend/tests/test_stooq_ingestion.py`       | Created (19 integration tests) |
| `config/source_registry_v1.0.yaml`            | NOT modified (intentional) |
