from app.domain import AssetCode
from app.domain import list_main_assets
from app.providers import MockMarketProvider
from app.services import MockSnapshotPipeline
from app.services import MarketSnapshotService


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


class FailingMockMarketProvider(MockMarketProvider):
    def get_asset_data(self, asset_symbol: AssetCode | str):
        asset_code = asset_symbol if isinstance(asset_symbol, AssetCode) else AssetCode(asset_symbol)
        if asset_code == AssetCode.BTCUSD:
            raise RuntimeError("mock provider failure")
        return super().get_asset_data(asset_code)


def test_pipeline_processes_all_27_assets() -> None:
    session = FakeSession()
    pipeline = MockSnapshotPipeline(MarketSnapshotService(session))

    result = pipeline.run()

    assert len(list_main_assets()) == 27
    assert result.total_assets_processed == 27
    assert result.successful_snapshots == 27
    assert result.failed_snapshots == 0
    assert len(session.added) == 27
    assert session.commit_calls == 27


def test_pipeline_returns_dqs_decision_counts() -> None:
    session = FakeSession()
    pipeline = MockSnapshotPipeline(MarketSnapshotService(session))

    result = pipeline.run()

    assert result.dqs_decision_counts == {
        "PASS": 24,
        "DEGRADED_PASS": 3,
        "LIMITED_ANALYSIS_ONLY": 0,
        "FAIL_NO_DECISION": 0,
    }


def test_pipeline_handles_failing_asset_without_crashing() -> None:
    session = FakeSession()
    pipeline = MockSnapshotPipeline(
        MarketSnapshotService(session),
        provider=FailingMockMarketProvider(),
    )

    result = pipeline.run()

    assert result.total_assets_processed == 27
    assert result.successful_snapshots == 26
    assert result.failed_snapshots == 1
    assert sum(result.dqs_decision_counts.values()) == 26
    assert session.commit_calls == 26

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
