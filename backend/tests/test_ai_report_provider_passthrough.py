"""ai_report endpoint — LLM `provider` query param shadowing regresyon testi.

Daha önce `provider` (auto|groq|claude) market adapter objesiyle shadow'lanıyor,
generate_ai_report'a string yerine adapter gidiyordu → manuel sağlayıcı seçimi
sessizce "auto"ya düşüyordu. Bu test seçimin string olarak geçtiğini sabitler.

Ağ bağımlılıkları (gerçek provider, FRED makro, haber, rotasyon) stub'lanır;
test offline ve hızlı çalışır.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers import MockMarketProvider
from app.services.ai_analyst_service import AIAnalystReport
from app.services.regime_report_service import (
    AssetSignal,
    MacroLayer,
    RiskAppetiteLayer,
)


def _stub_report() -> SimpleNamespace:
    macro = MacroLayer(
        regime="RISK_ON", confidence_pct=65, dxy_signal="-", energy_signal="-",
        yield_curve_signal="-", m2_signal="-", summary="stub",
    )
    appetite = RiskAppetiteLayer(
        status="STRONG", credit_signal="-", btc_dominance_signal="-",
        usdt_dominance_signal="-", safe_haven_signal="-", summary="stub",
    )
    asset = AssetSignal(
        asset_code="BTCUSD", asset_name="Bitcoin", status="CONFIRMED",
        reason="stub", value=60000.0, unit="$",
    )
    return SimpleNamespace(
        macro_layer=macro, appetite_layer=appetite,
        asset_signals=[asset], confirmation_checklist=[],
        decision="AÇIL", verdict="stub verdict",
    )


@pytest.fixture
def _spy(monkeypatch):
    captured: dict = {}

    def spy(*args, **kwargs):
        captured["provider"] = kwargs.get("provider")
        return AIAnalystReport(
            generated_at="2026-06-11T00:00:00Z",
            model="groq/llama-3.3-70b-versatile", cached=False,
            narrative="x", key_signals=["a"], verdict="v",
            confidence_note="c", error=None,
        )

    class _FakeIngestion:
        def __init__(self, *a, **k): ...
        def run(self):
            return SimpleNamespace(persisted_snapshots=[])

    class _FakeRegime:
        def generate(self, *a, **k):
            return _stub_report()

    class _FakeGeo:
        def fetch(self, *a, **k):
            return ()

    class _FakeRotation:
        def compute(self, *a, **k):
            return None

    monkeypatch.setattr("app.api.ai_report._get_provider", lambda: MockMarketProvider())
    monkeypatch.setattr("app.services.ProviderIngestionService", _FakeIngestion)
    monkeypatch.setattr("app.services.regime_report_service.RegimeReportService", _FakeRegime)
    monkeypatch.setattr("app.providers.geo_news_provider.GeoNewsProvider", _FakeGeo)
    monkeypatch.setattr("app.providers.capital_rotation_provider.CapitalRotationProvider", _FakeRotation)
    monkeypatch.setattr("app.services.ai_analyst_service.generate_ai_report", spy)
    return captured


def test_provider_groq_passes_through(_spy):
    from app.api.ai_report import get_ai_report
    get_ai_report(force_refresh=True, persona=None, provider="groq")
    assert _spy["provider"] == "groq"


def test_provider_claude_passes_through(_spy):
    from app.api.ai_report import get_ai_report
    get_ai_report(force_refresh=True, persona=None, provider="claude")
    assert _spy["provider"] == "claude"


def test_provider_none_passes_through(_spy):
    from app.api.ai_report import get_ai_report
    get_ai_report(force_refresh=True, persona=None, provider=None)
    # None → generate_ai_report kendi içinde "auto"ya normalize eder; burada
    # endpoint'in adapter objesi GÖNDERMEDİĞİNİ doğrularız (None geçmeli).
    assert _spy["provider"] is None
