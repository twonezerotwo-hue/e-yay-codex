"""
Light tests for the Gradio dashboard module.

- Source-based checks always run (no server started, no gradio required).
- Function-level unit tests run without gradio (callbacks are pure Python).
- Import test skips gracefully when gradio is not installed.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

_DASHBOARD_SRC = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dashboard"
    / "gradio_dashboard.py"
)


# ---------------------------------------------------------------------------
# Source-based checks (always run, no import needed)
# ---------------------------------------------------------------------------


def test_dashboard_source_file_exists():
    assert _DASHBOARD_SRC.exists(), "gradio_dashboard.py not found"


@pytest.fixture(scope="module")
def src() -> str:
    return _DASHBOARD_SRC.read_text(encoding="utf-8")


def test_dashboard_uses_localhost(src: str):
    assert "127.0.0.1" in src


def test_dashboard_uses_port_7867(src: str):
    assert "7867" in src


def test_dashboard_share_false(src: str):
    assert "share=False" in src


def test_dashboard_no_public_host(src: str):
    assert "0.0.0.0" not in src


def test_dashboard_no_public_share(src: str):
    assert "share=True" not in src


def test_dashboard_no_execution_strings(src: str):
    forbidden = [
        "place_order",
        "execute_trade",
        "buy_button",
        "sell_button",
        "broker_api",
        "live_market",
    ]
    for token in forbidden:
        assert token not in src, f"Forbidden string in dashboard source: {token!r}"


def test_dashboard_standalone_only(src: str):
    assert "app.mount" not in src, "Dashboard must not be FastAPI-mounted"


def test_dashboard_launch_config(src: str):
    assert 'server_name="127.0.0.1"' in src
    assert "server_port=7867" in src
    assert "share=False" in src


def test_dashboard_safety_labels(src: str):
    for label in ("PAPER_ONLY", "REPLAY_ONLY", "NO_EXECUTION", "LOCAL_DASHBOARD"):
        assert label in src, f"Safety label missing: {label}"


def test_dashboard_wired_callbacks_present(src: str):
    for name in (
        "_cb_run_replay",
        "_cb_run_rolling_diagnostics",
        "_cb_run_source_diagnostic",
        "_cb_paper_report_preview",
        "_cb_snapshot_browser",
        "_cb_overview",
    ):
        assert name in src, f"Expected callback not found in source: {name}"


def test_dashboard_source_diag_method_map_present(src: str):
    for key in (
        "contract_coverage_drift",
        "rolling_bundle_coverage_drift",
        "group_coverage_drift",
        "surface_count_drift",
        "metadata_completeness_drift",
        "naming_contract_drift",
        "contract_signature_drift",
        "contract_field_set_drift",
        "full_surface_response_field_set_consistency",
    ):
        assert key in src, f"Source diagnostic key missing from source: {key}"


# ---------------------------------------------------------------------------
# Function-level unit tests (no gradio, no server)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dashboard_mod():
    return importlib.import_module("backend.app.dashboard.gradio_dashboard")


def test_cb_replay_empty_returns_error(dashboard_mod):
    result = dashboard_mod._cb_run_replay("")
    assert "error" in result


def test_cb_source_diag_unknown_returns_error(dashboard_mod):
    result = dashboard_mod._cb_run_source_diagnostic("__unknown__", "")
    assert "error" in result


def test_source_diag_method_map_complete(dashboard_mod):
    choices = dashboard_mod._SOURCE_DIAG_CHOICES
    method_map = dashboard_mod._SOURCE_DIAG_METHOD
    for choice in choices:
        assert choice in method_map, f"Missing method mapping for: {choice}"


def test_cb_paper_report_preview_empty_returns_note(dashboard_mod):
    result = dashboard_mod._cb_paper_report_preview("")
    assert "note" in result or "error" in result


def test_to_json_safe_primitives(dashboard_mod):
    fn = dashboard_mod._to_json_safe
    assert fn(None) is None
    assert fn(42) == 42
    assert fn("hello") == "hello"
    assert fn([1, 2]) == [1, 2]
    assert fn((1, 2)) == [1, 2]


def test_latest_backup_name_returns_string(dashboard_mod):
    result = dashboard_mod._latest_backup_name()
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Smoke tests with demo snapshot data (no server, no gradio)
# ---------------------------------------------------------------------------


def _build_demo_store_with_one_snapshot(tmp_path):
    """Create a SnapshotStore with one replayable demo paper snapshot."""
    from app.providers import MockMarketProvider
    from app.providers import SourceRegistryBoundProviderAdapter
    from app.providers import build_provider_source_bindings
    from app.services import MarketSnapshotService
    from app.services import ProviderIngestionService
    from app.storage import SnapshotStore
    from registry import build_source_registry_entries
    from registry import load_source_registry

    class _FakeSession:
        def add(self, _):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

    store = SnapshotStore(tmp_path / "dashboard_smoke.jsonl")
    source_registry_entries = build_source_registry_entries(load_source_registry())
    adapter = SourceRegistryBoundProviderAdapter(
        MockMarketProvider(),
        build_provider_source_bindings(source_registry_entries),
    )
    svc = ProviderIngestionService(MarketSnapshotService(_FakeSession()), adapter)
    result = svc.run()
    svc.persist_ingestion_result(
        result,
        snapshot_store=store,
        snapshot_metadata={
            "snapshot_id": "demo_dashboard_snapshot",
            "source_registry_version": "1.0",
            "feature_registry_version": "1.0",
            "missing_sources": [],
            "stale_sources": [],
            "report_type": "provider_ingestion_paper_snapshot",
            "mode": "PAPER_SAFE",
            "execution_mode": "PAPER_ONLY",
            "audit_source_payload": None,
        },
    )
    return store


def test_cb_snapshot_browser_with_demo_store(tmp_path, monkeypatch, dashboard_mod):
    import app.storage.snapshot_store as _store_mod

    store = _build_demo_store_with_one_snapshot(tmp_path)
    monkeypatch.setattr(_store_mod, "build_local_snapshot_store", lambda: store)
    rows = dashboard_mod._cb_snapshot_browser()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    first = rows[0]
    assert isinstance(first, list)
    assert not first[0].startswith("Error:")
    assert first[0] != "(no snapshots found)"


def test_cb_run_replay_with_demo_snapshot(tmp_path, monkeypatch, dashboard_mod):
    from app.services import SnapshotReplayService

    store = _build_demo_store_with_one_snapshot(tmp_path)
    svc = SnapshotReplayService(snapshot_store=store)
    monkeypatch.setattr(dashboard_mod, "_build_service", lambda: svc)
    result = dashboard_mod._cb_run_replay("demo_dashboard_snapshot")
    assert isinstance(result, dict)
    assert "error" not in result
    assert result.get("snapshot_id") == "demo_dashboard_snapshot"
    assert result.get("paper_safe") is True
    assert result.get("network_calls") is False
    assert result.get("execution_side_effects") == "NO_EXECUTION"


def test_cb_run_rolling_diagnostics_with_demo_store(tmp_path, monkeypatch, dashboard_mod):
    from app.services import SnapshotReplayService

    store = _build_demo_store_with_one_snapshot(tmp_path)
    svc = SnapshotReplayService(snapshot_store=store)
    monkeypatch.setattr(dashboard_mod, "_build_service", lambda: svc)
    result = dashboard_mod._cb_run_rolling_diagnostics("", 10)
    assert isinstance(result, dict)


def test_cb_run_source_diagnostic_contract_field_set_drift_returns_dict(
    tmp_path, monkeypatch, dashboard_mod
):
    from app.services import SnapshotReplayService
    from app.storage import SnapshotStore

    store = SnapshotStore(tmp_path / "empty_store.jsonl")
    svc = SnapshotReplayService(snapshot_store=store)
    monkeypatch.setattr(dashboard_mod, "_build_service", lambda: svc)
    result = dashboard_mod._cb_run_source_diagnostic("contract_field_set_drift", "")
    assert isinstance(result, dict)
    assert "error" not in result


def test_cb_paper_report_preview_with_demo_snapshot(tmp_path, monkeypatch, dashboard_mod):
    from app.services import SnapshotReplayService

    store = _build_demo_store_with_one_snapshot(tmp_path)
    svc = SnapshotReplayService(snapshot_store=store)
    monkeypatch.setattr(dashboard_mod, "_build_service", lambda: svc)
    result = dashboard_mod._cb_paper_report_preview("demo_dashboard_snapshot")
    assert isinstance(result, dict)
    assert "error" not in result
    assert result.get("paper_safe") is True
    assert result.get("network_calls") is False
    assert result.get("execution_side_effects") == "NO_EXECUTION"


# ---------------------------------------------------------------------------
# New source-based checks — 14-tab console redesign
# ---------------------------------------------------------------------------


def test_dashboard_contains_console_name(src: str):
    assert "BrainChain" in src or "Paper Intelligence Console" in src


def test_dashboard_includes_data_sources_tab(src: str):
    assert "Data Sources" in src


def test_dashboard_includes_data_integrity_tab(src: str):
    assert "Data Integrity" in src


def test_dashboard_includes_ingestion_pipeline_tab(src: str):
    assert "Ingestion Pipeline" in src


def test_dashboard_includes_trigger_risk_tab(src: str):
    assert "Kill Switch" in src or "Risk Engine" in src


def test_dashboard_includes_ceo_brief_tab(src: str):
    assert "CEO" in src


def test_dashboard_includes_roadmap_tab(src: str):
    assert "Roadmap" in src


# ---------------------------------------------------------------------------
# New function-level unit tests — 14-tab console callbacks
# ---------------------------------------------------------------------------


def test_cb_stooq_provider_info_returns_string(dashboard_mod):
    result = dashboard_mod._cb_stooq_provider_info()
    assert isinstance(result, str)
    assert len(result) > 0


def test_cb_run_stooq_fixture_ingestion_empty_returns_error(dashboard_mod):
    result = dashboard_mod._cb_run_stooq_fixture_ingestion([])
    assert "error" in result


def test_cb_run_stooq_fixture_ingestion_qqq_returns_result(dashboard_mod):
    result = dashboard_mod._cb_run_stooq_fixture_ingestion(["QQQ"])
    assert isinstance(result, dict)
    assert "error" not in result
    assert result.get("paper_safe") is True
    assert result.get("network_calls") is False
    assert result.get("execution_side_effects") == "NO_EXECUTION"
    assert result.get("source_mode") == "FIXTURE_CSV_ONLY"
    assert result.get("successful_snapshots", 0) >= 1


def test_cb_run_stooq_fixture_ingestion_all_assets_returns_result(dashboard_mod):
    result = dashboard_mod._cb_run_stooq_fixture_ingestion(["QQQ", "HYG", "JNK", "FXI"])
    assert isinstance(result, dict)
    assert "error" not in result
    assert result.get("paper_safe") is True
    assert result.get("network_calls") is False
    assert result.get("total_assets_processed") == 4
    payloads = result.get("payloads", [])
    assert isinstance(payloads, list)
    assert len(payloads) == 4
    source_names = {p["source_name"] for p in payloads}
    assert "stooq_daily_csv" in source_names


def test_cb_load_next_task_returns_string(dashboard_mod):
    result = dashboard_mod._cb_load_next_task()
    assert isinstance(result, str)
    assert len(result) > 0


def test_cb_load_replay_risk_empty_returns_note(dashboard_mod):
    result = dashboard_mod._cb_load_replay_risk("")
    assert isinstance(result, dict)
    assert "note" in result


def test_cb_load_snapshot_metadata_empty_returns_note(dashboard_mod):
    result = dashboard_mod._cb_load_snapshot_metadata("")
    assert isinstance(result, dict)
    assert "note" in result


def test_cb_audit_status_returns_string(dashboard_mod):
    result = dashboard_mod._cb_audit_status()
    assert isinstance(result, str)
    assert "Audit" in result or "backup" in result.lower()


def test_cb_overview_returns_string(dashboard_mod):
    result = dashboard_mod._cb_overview()
    assert isinstance(result, str)
    assert "PAPER_ONLY" in result or "Status" in result


# ---------------------------------------------------------------------------
# Import test (skipped when gradio not installed)
# ---------------------------------------------------------------------------


def test_dashboard_imports_when_gradio_available():
    gradio = pytest.importorskip("gradio", reason="gradio not installed — skipping import test")
    assert gradio is not None

    mod = importlib.import_module("backend.app.dashboard.gradio_dashboard")
    assert hasattr(mod, "build_demo")
    assert hasattr(mod, "_GRADIO_AVAILABLE")
    assert mod._GRADIO_AVAILABLE is True
