"""Paylaşılan test fixture'ları."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_neutral_trade_opinion(monkeypatch):
    """AI Trade Opinion soft modifier varsayılan olarak no-op döner.

    build_trade_opinion_context_for_signal() -> build_ai_trade_opinion() ->
    collect_opinion_context() prod disk verisini (hourly snapshots, paper
    state) okur. _route_new_open_signal'ı doğrudan çağıran flow testleri bu
    veriye göre route="manual_ready" veya size_multiplier != 1.0 alıp
    deterministik olmayan şekilde kırılmasın diye varsayılanı nötrledik.
    Soft modifier'ın kendisini test eden test_ai_trade_opinion_paper_*
    dosyaları `opinion=` enjekte ederek bu fixture'ı bypass eder.
    """
    monkeypatch.setattr(
        "app.services.ai_trade_opinion_service.build_trade_opinion_context_for_signal",
        lambda *a, **k: {
            "available": False,
            "size_multiplier": 1.0,
            "route_recommendation": "proceed",
            "reason": "opinion_unavailable",
        },
    )
