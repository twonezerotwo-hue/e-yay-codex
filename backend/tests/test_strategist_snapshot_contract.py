"""Market Strategist snapshot_id kontrat dürüstlüğü testi.

snapshot_id replay'e bağlı DEĞİL: kullanıcı ID gönderse bile veri güncel
pipeline'dan gelir. Bu test, kontratın bunu açıkça raporladığını sabitler
(context_source="current", snapshot_id_status="reserved_not_active").

Ağ-yoğun pipeline parçaları stub'lanır → test hızlı ve offline.
"""
from __future__ import annotations

import pytest

from app.services import market_strategist_service as mss


@pytest.fixture
def _offline(monkeypatch):
    """build_context içindeki ağ çağrılarını nötrle — kontrat alanlarını izole et."""
    def _raise(*a, **k):
        raise RuntimeError("offline stub")

    monkeypatch.setattr("app.api.consensus._build_pipeline", _raise)
    monkeypatch.setattr("app.api.chart_patterns._build_all_patterns", lambda *a, **k: {})
    monkeypatch.setattr("app.services.agent_chart_reader_service.read_chart", _raise)
    monkeypatch.setattr("app.providers.news_provider.NewsProvider.fetch_headlines",
                        lambda self, *a, **k: ())


def test_context_defaults_are_current() -> None:
    ctx = mss.StrategistContext(snapshot_id=None, generated_at="t", regime=None, decision=None)
    assert ctx.context_source == "current"
    assert ctx.snapshot_id_status is None


def test_no_snapshot_id_status_none(_offline) -> None:
    ctx = mss.build_context(symbols=["BTCUSD"], snapshot_id=None)
    assert ctx.context_source == "current"
    assert ctx.snapshot_id_status is None
    assert "snapshot_replay:reserved_not_active" not in ctx.missing_data


def test_snapshot_id_marked_reserved(_offline) -> None:
    ctx = mss.build_context(symbols=["BTCUSD"], snapshot_id="snap-2026-06-10T12:00")
    # Veri yine güncel kaynaktan — replay yapılmıyor
    assert ctx.context_source == "current"
    # Ama kontrat dürüst: ID rezerve, aktif değil
    assert ctx.snapshot_id_status == "reserved_not_active"
    assert "snapshot_replay:reserved_not_active" in ctx.missing_data
    # snapshot_id yine echo'lanır (referans için)
    assert ctx.snapshot_id == "snap-2026-06-10T12:00"
