"""
Market Strategist Service & API — test paketi

Tüm testler:
  • _call_llm ve build_context monkeypatch edilir → live ağ çağrısı YOK
  • paper_safe / NO_EXECUTION koruması doğrulanır
  • forbidden-phrase filtresi kontrol edilir
  • abstain mekanizması test edilir
  • API endpoint şema uyumu kontrol edilir

PAPER_SAFE / NO_EXECUTION.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

import app.services.market_strategist_service as mss


# ── Fixtures ────────────────────────────────────────────────────────────────

_CLEAN_RESPONSE = json.dumps({
    "answer": "Mevcut rejim RISK-OFF sinyali veriyor.",
    "market_read": ["BTC konsolidasyon", "Altın güçlü"],
    "cross_asset_map": [{"asset": "XAUUSD", "signal": "bullish bias", "weight": "high"}],
    "actor_perspective_map": [{"actor": "Fed", "incentive": "Enflasyonu kontrol", "implication": "Faiz artışı baskısı"}],
    "headline_scenarios": [{"trigger": "Fed pivot", "scenario": "Risk iştahı artışı", "direction": "up"}],
    "invalidation": ["BTC 58000 altı kapanış"],
    "confidence": {"level": "medium", "score": 65, "reason": "Karışık sinyaller"},
    "evidence_refs": [{"source": "consensus_engine", "detail": "RISK-OFF rejim"}],
    "safety_notice": "PAPER_SAFE / NO_EXECUTION. Tüm kararlar insana aittir.",
    "abstained": False,
    "abstain_reason": None,
    "model_used": "claude-opus-4-7",
})

_MINIMAL_CTX = mss.StrategistContext(
    snapshot_id=None,
    generated_at="2026-06-07T00:00:00+00:00",
    regime="RISK-OFF",
    decision="BEKLE",
    # _has_minimum_context için en az biri dolu olmalı
    consensus_summary=[{"asset": "XAUUSD", "score": 62.0, "direction": "BULLISH"}],
)


def _fake_call_llm(system: str, user: str, *, provider: str = "auto") -> tuple[str, str]:
    # _call_llm gerçek imzası: tuple[str, str] | None — artık `provider` kwarg'ı da alıyor
    return _CLEAN_RESPONSE, "claude-opus-4-7"


def _fake_build_context(symbols=None, snapshot_id=None) -> mss.StrategistContext:
    return _MINIMAL_CTX


# ── 1. paper_safe flag API response ─────────────────────────────────────────

def test_api_paper_safe_flag():
    """POST /chat cevabında paper_safe=True ve execution_side_effects=NO_EXECUTION olmalı."""
    from fastapi.testclient import TestClient
    from app.main import app

    with patch.object(mss, "_call_llm", side_effect=_fake_call_llm), \
         patch.object(mss, "build_context", side_effect=_fake_build_context):
        client = TestClient(app)
        r = client.post(
            "/api/v1/market-strategist/chat",
            json={"question": "Altın nereye gider?"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["paper_safe"] is True
    assert data["execution_side_effects"] == "NO_EXECUTION"
    assert data["mode"] == "MARKET_STRATEGIST"


# ── 2. answer returned ───────────────────────────────────────────────────────

def test_api_answer_in_response():
    """Cevap answer alanını içermeli."""
    from fastapi.testclient import TestClient
    from app.main import app

    with patch.object(mss, "_call_llm", side_effect=_fake_call_llm), \
         patch.object(mss, "build_context", side_effect=_fake_build_context):
        client = TestClient(app)
        r = client.post(
            "/api/v1/market-strategist/chat",
            json={"question": "Piyasa nerede?"},
        )
    data = r.json()
    assert "answer" in data
    assert len(data["answer"]) > 0


# ── 3. NO_EXECUTION guard — forbidden buy/sell language blocked ──────────────

def test_forbidden_execution_phrases_blocked():
    """Modelin 'buy' ya da 'al emri' dönmesi durumunda sanitize edilmeli."""
    bad_response = json.dumps({
        "answer": "Now you should buy BTC immediately.",
        "market_read": [],
        "cross_asset_map": [],
        "actor_perspective_map": [],
        "headline_scenarios": [],
        "invalidation": [],
        "confidence": {"level": "low", "score": 30, "reason": "test"},
        "evidence_refs": [],
        "safety_notice": "test",
        "abstained": False,
        "abstain_reason": None,
        "model_used": "claude-opus-4-7",
    })

    with patch.object(mss, "_call_llm", return_value=(bad_response, "claude-opus-4-7")), \
         patch.object(mss, "build_context", return_value=_MINIMAL_CTX):
        resp, _ctx = mss.answer("test sorusu", language="en")

    # answer, buy içermemeli (sanitized olmalı)
    assert "buy" not in resp.answer.lower(), "Forbidden execution phrase 'buy' should be removed"


# ── 4. Insider phrase blocked ────────────────────────────────────────────────

def test_forbidden_insider_phrases_blocked():
    """İçerden bilgi iddiası içeren cevap sanitize edilmeli."""
    bad_response = json.dumps({
        "answer": "I know what Trump will do next — gizli bilgi edindim.",
        "market_read": [],
        "cross_asset_map": [],
        "actor_perspective_map": [],
        "headline_scenarios": [],
        "invalidation": [],
        "confidence": {"level": "low", "score": 30, "reason": "test"},
        "evidence_refs": [],
        "safety_notice": "test",
        "abstained": False,
        "abstain_reason": None,
        "model_used": "claude-opus-4-7",
    })

    with patch.object(mss, "_call_llm", return_value=(bad_response, "claude-opus-4-7")), \
         patch.object(mss, "build_context", return_value=_MINIMAL_CTX):
        resp, _ctx = mss.answer("insider soru", language="tr")

    assert "gizli bilgi" not in resp.answer.lower()


# ── 5. Abstain when LLM unavailable ─────────────────────────────────────────

def test_abstain_when_llm_unavailable():
    """LLM çağrısı None döndürdüğünde abstain=True döner, exception fırlatılmaz."""
    with patch.object(mss, "_call_llm", return_value=None), \
         patch.object(mss, "build_context", return_value=_MINIMAL_CTX):
        resp, _ctx = mss.answer("test soru")

    assert resp.abstained is True
    assert resp.abstain_reason is not None


# ── 6. Safety notice always present ─────────────────────────────────────────

def test_safety_notice_always_present():
    """Cevap her zaman PAPER_SAFE / NO_EXECUTION safety_notice içermeli."""
    with patch.object(mss, "_call_llm", side_effect=_fake_call_llm), \
         patch.object(mss, "build_context", return_value=_MINIMAL_CTX):
        resp, _ctx = mss.answer("test soru")

    assert resp.safety_notice
    assert "NO_EXECUTION" in resp.safety_notice or "PAPER_SAFE" in resp.safety_notice


# ── 7. Turkish answer — language respected ───────────────────────────────────

def test_language_tr_passed_to_system_prompt():
    """TR dil seçiminde system prompt Türkçe talimat içermeli."""
    captured: dict = {}

    def capturing_call_llm(system: str, user: str, *, provider: str = "auto") -> tuple[str, str]:
        captured["system"] = system
        return _CLEAN_RESPONSE, "claude-opus-4-7"

    with patch.object(mss, "_call_llm", side_effect=capturing_call_llm), \
         patch.object(mss, "build_context", return_value=_MINIMAL_CTX):
        mss.answer("test soru", language="tr")

    assert "system" in captured
    # TR prompt Türkçe kelime içermeli
    assert "Türkçe" in captured["system"] or "türkçe" in captured["system"].lower()


# ── 8. evidence_refs present ─────────────────────────────────────────────────

def test_evidence_refs_field_exists():
    """Cevabın evidence_refs listesi olmalı."""
    with patch.object(mss, "_call_llm", side_effect=_fake_call_llm), \
         patch.object(mss, "build_context", return_value=_MINIMAL_CTX):
        resp, _ctx = mss.answer("test soru")

    assert isinstance(resp.evidence_refs, list)


# ── 9. context_meta in API response ─────────────────────────────────────────

def test_api_context_meta_present():
    """API cevabında context_meta (regime, snapshot_id, missing_data) bulunmalı."""
    from fastapi.testclient import TestClient
    from app.main import app

    with patch.object(mss, "_call_llm", side_effect=_fake_call_llm), \
         patch.object(mss, "build_context", side_effect=_fake_build_context):
        client = TestClient(app)
        r = client.post(
            "/api/v1/market-strategist/chat",
            json={"question": "Rejim ne?", "symbols": ["XAUUSD"]},
        )
    data = r.json()
    assert "context_meta" in data
    assert "regime" in data["context_meta"]
    assert "missing_data" in data["context_meta"]


# ── 10. Invalid question too short ──────────────────────────────────────────

def test_api_question_too_short_rejected():
    """3 karakterden kısa soru 422 döndürmeli."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/v1/market-strategist/chat",
        json={"question": "ab"},
    )
    assert r.status_code == 422
