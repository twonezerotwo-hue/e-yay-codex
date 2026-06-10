"""
FAZ 14 — Capital Rotation Visual Adapter testleri.

Kapsam:
  1. Valid rotation → status=ok, nodes+flows üretir
  2. Positive return → direction=in
  3. Negative return → direction=out
  4. Near-zero return → direction=neutral
  5. Identical returns → status=degraded
  6. Empty class_scores → status=degraded
  7. NO_EXECUTION / PAPER_SAFE her zaman zorlanır
  8. error alanı set → status=degraded
  9. Out-only (in node yok) → CASH_PROXY hedef
  10. Strength normalization (cap at 1.0)
  11. Endpoint read-only: GET döner, conviction int
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services.capital_rotation_visual_adapter import (
    SCHEMA_VERSION,
    build_visual_payload,
)


# ── Fake rotation objesi ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class FakeScore:
    name: str
    score: float
    momentum_30d: float
    direction: str


@dataclass(frozen=True)
class FakeRotation:
    primary_flow: str
    secondary_flow: str | None
    conviction: int
    class_scores: tuple
    error: str | None


def _mk_rotation(scores: list[FakeScore], conviction: int = 40,
                 primary: str = "ALTIN", error: str | None = None) -> FakeRotation:
    return FakeRotation(
        primary_flow=primary,
        secondary_flow=None,
        conviction=conviction,
        class_scores=tuple(scores),
        error=error,
    )


# ── 1. Valid rotation üretiyor ───────────────────────────────────────────────

def test_valid_rotation_produces_nodes_and_flows():
    rot = _mk_rotation([
        FakeScore("ALTIN",      1.0,  5.2, "GİRİŞ"),
        FakeScore("BTC",       -0.8, -8.1, "ÇIKIŞ"),
        FakeScore("TAHVİL",     0.4,  1.2, "GİRİŞ"),
        FakeScore("HİSSE",     -0.3, -2.5, "ÇIKIŞ"),
    ])
    payload = build_visual_payload(rot)

    assert payload["status"] == "ok"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert len(payload["nodes"]) == 4
    assert len(payload["flows"]) >= 1
    assert payload["fallback_reason"] is None


# ── 2. Positive return → in ──────────────────────────────────────────────────

def test_positive_return_direction_in():
    rot = _mk_rotation([FakeScore("ALTIN", 1.0, 6.0, "GİRİŞ")])
    payload = build_visual_payload(rot)
    assert payload["nodes"][0]["direction"] == "in"
    assert payload["nodes"][0]["value_pct"] == 6.0


# ── 3. Negative return → out ─────────────────────────────────────────────────

def test_negative_return_direction_out():
    rot = _mk_rotation([
        FakeScore("BTC",   -0.9, -12.0, "ÇIKIŞ"),
        FakeScore("ALTIN",  0.5,   3.0, "GİRİŞ"),
    ])
    payload = build_visual_payload(rot)
    btc = next(n for n in payload["nodes"] if n["id"] == "BTC")
    assert btc["direction"] == "out"
    assert btc["value_pct"] == -12.0


# ── 4. Near-zero → neutral ───────────────────────────────────────────────────

def test_near_zero_direction_neutral():
    rot = _mk_rotation([
        FakeScore("ALTIN", 0.0,  0.1, "NÖTR"),
        FakeScore("BTC",  -0.5, -3.0, "ÇIKIŞ"),
    ])
    payload = build_visual_payload(rot)
    altin = next(n for n in payload["nodes"] if n["id"] == "GLD")
    assert altin["direction"] == "neutral"


# ── 5. Identical returns → degraded ──────────────────────────────────────────

def test_identical_returns_degraded():
    rot = _mk_rotation([
        FakeScore("ALTIN",  0.5, 2.0, "GİRİŞ"),
        FakeScore("BTC",    0.5, 2.0, "GİRİŞ"),
        FakeScore("TAHVİL", 0.5, 2.0, "GİRİŞ"),
    ])
    payload = build_visual_payload(rot)
    assert payload["status"] == "degraded"
    assert payload["fallback_reason"] == "identical_returns"
    assert payload["nodes"] == []
    assert payload["flows"] == []


# ── 6. Empty class_scores → degraded ─────────────────────────────────────────

def test_empty_class_scores_degraded():
    rot = _mk_rotation([])
    payload = build_visual_payload(rot)
    assert payload["status"] == "degraded"
    assert payload["fallback_reason"] == "class_scores_empty"


# ── 7. PAPER_SAFE / NO_EXECUTION her zaman ──────────────────────────────────

def test_paper_safe_always_enforced():
    # ok case
    rot = _mk_rotation([
        FakeScore("ALTIN", 0.8, 4.0, "GİRİŞ"),
        FakeScore("BTC",  -0.5, -3.0, "ÇIKIŞ"),
    ])
    ok = build_visual_payload(rot)
    assert ok["decision_permission"] == "NO_EXECUTION"
    assert ok["execution_mode"] == "PAPER_SAFE"
    assert ok["visual_mode"] == "animated_flow"

    # degraded case
    deg = build_visual_payload(None)
    assert deg["decision_permission"] == "NO_EXECUTION"
    assert deg["execution_mode"] == "PAPER_SAFE"


# ── 8. error alanı set ise degraded ──────────────────────────────────────────

def test_error_field_propagates_degraded():
    rot = _mk_rotation(
        [FakeScore("ALTIN", 0.5, 2.0, "GİRİŞ")],
        error="data_insufficient",
    )
    payload = build_visual_payload(rot)
    assert payload["status"] == "degraded"
    assert "data_insufficient" in (payload["fallback_reason"] or "")


# ── 9. Out-only → CASH_PROXY ─────────────────────────────────────────────────

def test_out_only_routes_to_cash_proxy():
    rot = _mk_rotation([
        FakeScore("BTC",   -0.9, -7.0, "ÇIKIŞ"),
        FakeScore("ALTIN", -0.3, -1.0, "ÇIKIŞ"),
    ])
    payload = build_visual_payload(rot)
    assert payload["status"] == "ok"
    assert all(f["to"] == "CASH_PROXY" for f in payload["flows"])
    assert len(payload["flows"]) == 2


# ── 10. Strength cap at 1.0 ─────────────────────────────────────────────────

def test_strength_capped_at_one():
    rot = _mk_rotation([
        FakeScore("BTC",   -1.5, -45.0, "ÇIKIŞ"),
        FakeScore("ALTIN",  1.5,  60.0, "GİRİŞ"),
    ])
    payload = build_visual_payload(rot)
    for n in payload["nodes"]:
        assert 0 <= n["strength"] <= 1.0


# ── 11. Endpoint read-only ───────────────────────────────────────────────────

def test_endpoint_read_only(monkeypatch):
    """GET endpoint çalışmalı; POST/PUT/DELETE 405 dönmeli."""
    from app.main import app
    import app.api.capital_rotation_visual as mod

    # Provider'ı stub'la — gerçek yfinance çağrısı yapma
    class _StubProvider:
        def compute(self):
            return _mk_rotation([
                FakeScore("ALTIN", 0.7, 4.5, "GİRİŞ"),
                FakeScore("BTC",  -0.6, -5.0, "ÇIKIŞ"),
            ])

    # Provider import içeride lazy yapılıyor → modül-scope cache temizle
    mod._CACHE = None
    monkeypatch.setattr(
        "app.providers.capital_rotation_provider.CapitalRotationProvider",
        _StubProvider,
    )

    client = TestClient(app)
    r = client.get("/api/v1/capital-rotation/visual")
    assert r.status_code == 200
    data = r.json()
    assert data["schema_version"] == SCHEMA_VERSION
    assert isinstance(data["conviction"], int)
    assert data["decision_permission"] == "NO_EXECUTION"

    # POST/PUT/DELETE reddedilmeli
    assert client.post("/api/v1/capital-rotation/visual").status_code in (404, 405)
    assert client.put("/api/v1/capital-rotation/visual").status_code in (404, 405)
    assert client.delete("/api/v1/capital-rotation/visual").status_code in (404, 405)


# ── 12. None rotation → degraded ─────────────────────────────────────────────

def test_none_rotation_degraded():
    payload = build_visual_payload(None)
    assert payload["status"] == "degraded"
    assert payload["fallback_reason"] == "rotation_unavailable"
