"""Capital Rotation timeframe (1d/7d/30d) seçimi — windowed momentum testleri.

Kapsam:
  1. _momentum_window pure fonksiyonu (1/7/30 bar + yetersiz veri)
  2. compute_window_rotation: veri varken window_available=True + class_scores
  3. compute_window_rotation: veri yokken insufficient_history (fake skor YOK)
  4. compute_window_rotation: bilinmeyen window
  5. Endpoint ?timeframe=1d → timeframe + timeframe_available alanları
  6. Endpoint timeframe veri yok → status=ok ama timeframe_available=False
     (klasik görünüme düşürmez)
  7. Endpoint geçersiz timeframe → 30d'ye düşer (regression yok)
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.providers import capital_rotation_provider as crp
from app.services.capital_rotation_visual_adapter import SCHEMA_VERSION


# ── 1. _momentum_window ───────────────────────────────────────────────────────

def test_momentum_window_basic():
    s = np.array([100.0, 101.0, 102.0, 110.0])
    assert crp._momentum_window(s, 1) == pytest.approx(7.84, abs=0.01)   # 110 vs 102
    assert crp._momentum_window(s, 3) == 10.0                            # 110 vs 100
    assert crp._momentum_window(s, 10) is None                           # yetersiz veri
    assert crp._momentum_window(None, 1) is None
    assert crp._momentum_window(np.array([0.0, 100.0]), 1) is None       # old <= 0


# ── 2/3/4. compute_window_rotation ────────────────────────────────────────────

def _synthetic_closes() -> dict[str, np.ndarray]:
    base = {"GLD": 100.0, "XAG": 50.0, "TLT": 90.0, "BTC": 60000.0,
            "SPY": 500.0, "DXY": 104.0, "OIL": 80.0}
    return {k: np.linspace(v * 0.9, v, 40) for k, v in base.items()}


def test_compute_window_rotation_available(monkeypatch):
    monkeypatch.setattr(crp, "_get_closes_cached", lambda *a, **k: _synthetic_closes())
    wr = crp.compute_window_rotation("7d")
    assert wr["window_available"] is True
    assert wr["reason"] is None
    names = {c["name"] for c in wr["class_scores"]}
    assert {"ALTIN", "BTC", "DOLAR_GÜCÜ"} <= names
    assert isinstance(wr["conviction"], int)
    for c in wr["class_scores"]:
        assert isinstance(c["momentum_30d"], float)  # window momentum, numeric


def test_compute_window_rotation_insufficient(monkeypatch):
    monkeypatch.setattr(crp, "_get_closes_cached", lambda *a, **k: {})
    wr = crp.compute_window_rotation("1d")
    assert wr["window_available"] is False
    assert wr["reason"] == "insufficient_history"
    assert wr["class_scores"] == []


def test_compute_window_rotation_unknown_window():
    wr = crp.compute_window_rotation("99x")
    assert wr["window_available"] is False
    assert wr["reason"] == "unknown_window"


# ── 5/6/7. Endpoint ──────────────────────────────────────────────────────────

def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


def _reset_cache():
    import app.api.capital_rotation_visual as mod
    mod._CACHE = None


def test_endpoint_timeframe_1d_available(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(
        "app.providers.capital_rotation_provider.compute_window_rotation",
        lambda window: {
            "error": None, "window_available": True, "reason": None,
            "primary_flow": "BTC", "secondary_flow": None, "conviction": 30,
            "class_scores": [
                {"name": "BTC",   "momentum_30d": 4.0,  "score": 0.8,  "direction": "GİRİŞ"},
                {"name": "ALTIN", "momentum_30d": -2.0, "score": -0.4, "direction": "ÇIKIŞ"},
            ],
        },
    )
    r = _client().get("/api/v1/capital-rotation/visual?timeframe=1d")
    assert r.status_code == 200
    d = r.json()
    assert d["schema_version"] == SCHEMA_VERSION
    assert d["timeframe"] == "1d"
    assert d["timeframe_available"] is True
    assert d["status"] == "ok"
    assert len(d["nodes"]) == 2


def test_endpoint_timeframe_unavailable_stays_ok(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(
        "app.providers.capital_rotation_provider.compute_window_rotation",
        lambda window: {"error": None, "window_available": False,
                        "reason": "insufficient_history", "class_scores": []},
    )
    r = _client().get("/api/v1/capital-rotation/visual?timeframe=7d")
    assert r.status_code == 200
    d = r.json()
    assert d["timeframe"] == "7d"
    assert d["timeframe_available"] is False
    # status=ok → frontend klasik görünüme DÜŞMEZ, inline "veri yok" gösterir
    assert d["status"] == "ok"
    assert d["nodes"] == []
    assert d["fallback_reason"] == "insufficient_history"


def test_endpoint_invalid_timeframe_defaults_30d(monkeypatch):
    _reset_cache()

    class _StubProvider:
        def compute(self):
            return SimpleNamespace(
                primary_flow="ALTIN", secondary_flow=None, conviction=40,
                class_scores=[
                    {"name": "ALTIN", "momentum_30d": 4.5,  "score": 0.7,  "direction": "GİRİŞ"},
                    {"name": "BTC",   "momentum_30d": -5.0, "score": -0.6, "direction": "ÇIKIŞ"},
                ],
                error=None,
            )

    monkeypatch.setattr(
        "app.providers.capital_rotation_provider.CapitalRotationProvider",
        _StubProvider,
    )
    r = _client().get("/api/v1/capital-rotation/visual?timeframe=bogus")
    assert r.status_code == 200
    d = r.json()
    assert d["timeframe"] == "30d"           # geçersiz → 30d
    assert d["timeframe_available"] is True
    assert d["status"] == "ok"
