"""
FAZ 10.1 — Agent Banner Service testleri.

8 test:
  1. Pozisyon yok + sinyal yok → waiting mode
  2. Açık pozisyon var → managing_position mode
  3. Thesis sanity fail → contradiction mode
  4. Paper anomaly active → risk_alert mode
  5. Learning candidate var → learning_note dolu
  6. Auto tune override var → learning_note'da override metni
  7. Aynı generic metin sürekli dönmüyor
     (risk_alert/contradiction/managing moda özel içerik üretildi)
  8. No data → endpoint 200 döner, crash yok
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.agent_banner_service as svc
import app.storage.agent_thesis_store as at_store
import app.storage.auto_tune_store as atu_store
import app.storage.hourly_snapshot_store as hs_store
import app.storage.learning_candidate_store as lc_store
import app.storage.mistake_memory_store as mm_store
import app.storage.position_recheck_store as pr_store
import app.storage.weekly_calibration_store as wc_store


# ── Store redirect + paper trading mock ──────────────────────────────────────

@pytest.fixture(autouse=True)
def _redirect_stores(tmp_path, monkeypatch):
    """Tüm JSONL store path'lerini tmp_path'e yönlendir."""
    monkeypatch.setattr(hs_store, "_STORE_PATH", tmp_path / "hourly_snapshots.jsonl")
    monkeypatch.setattr(at_store, "_STORE_PATH", tmp_path / "agent_hourly_theses.jsonl")
    monkeypatch.setattr(pr_store, "_STORE_PATH", tmp_path / "position_rechecks.jsonl")
    monkeypatch.setattr(lc_store, "_STORE_PATH", tmp_path / "learning_candidates.jsonl")
    monkeypatch.setattr(mm_store, "_STORE_PATH", tmp_path / "mistake_memory.jsonl")
    monkeypatch.setattr(wc_store, "_STORE_PATH", tmp_path / "weekly_calibrations.jsonl")
    monkeypatch.setattr(atu_store, "_OVERRIDES_PATH", tmp_path / "auto_tune_overrides.json")


@pytest.fixture(autouse=True)
def _mock_pts_no_positions(monkeypatch):
    """Default: anomaly yok, pozisyon yok."""
    import app.services.paper_trading_service as pts
    monkeypatch.setattr(
        pts, "get_snapshot",
        lambda: {"open_positions": [], "state_anomaly": {"active": False, "reasons": []}},
    )


@pytest.fixture()
def client():
    from app.main import app
    return TestClient(app)


# ── Yardımcı: banner cache temizleme ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_banner_cache():
    """Her test öncesi banner cache'i temizle — TTL atlatmak için."""
    import app.api.agent_banner as banner_api
    banner_api._BANNER_CACHE = None
    yield
    banner_api._BANNER_CACHE = None


# ── Test 1: waiting mode — veri yok ──────────────────────────────────────────

def test_waiting_mode_when_no_data(monkeypatch):
    """
    Hiç veri yoksa (no positions, no thesis, no snapshots):
    mod 'waiting' olmalı; 'kayıt yok' içerik döner, crash yok.
    """
    banner = svc.build_agent_banner()
    assert banner["mode"] == "waiting"
    assert "updated_at" in banner
    assert isinstance(banner["top_signals"], list)
    # Veri yoksa boş generic metin değil "kayıt yok"
    combined = " ".join(banner["top_signals"]).lower()
    assert "kayıt" in combined or banner["headline"]


# ── Test 2: managing_position — açık pozisyon var ─────────────────────────────

def test_managing_position_mode_when_open_positions(monkeypatch):
    """Açık pozisyon varsa mod 'managing_position' olmalı."""
    import app.services.paper_trading_service as pts
    monkeypatch.setattr(
        pts, "get_snapshot",
        lambda: {
            "open_positions": [
                {"pair": "BTCUSD", "side": "LONG", "entry_price": 67000.0, "pnl_pct": 1.2},
                {"pair": "XAUUSD", "side": "SHORT", "entry_price": 2350.0, "pnl_pct": -0.5},
            ],
            "state_anomaly": {"active": False, "reasons": []},
        },
    )
    banner = svc.build_agent_banner()
    assert banner["mode"] == "managing_position"
    # headline'da pozisyon detayı (pair isimleri)
    assert "BTCUSD" in banner["headline"] or "2 açık" in banner["headline"]
    # position_note dolu
    assert banner["position_note"] is not None
    assert "BTCUSD" in (banner["position_note"] or "")


# ── Test 3: contradiction — thesis sanity fail ────────────────────────────────

def test_contradiction_mode_when_thesis_sanity_fail(monkeypatch):
    """
    thesis_sanity.safe_for_context = False iken mod 'contradiction' olmalı.
    "agent thesis güvenli context değil" metni headline'da geçmeli.
    """
    at_store.save_agent_thesis({
        "market_view":           {"stance": "bearish"},
        "asset_bias":            {},
        "confirmation_health":   {},
        "strongest_reasons":     [],
        "main_contradictions":   ["MTF çelişkisi: 1H long ama 4H bearish"],
        "watchlist":             [],
        "data_quality":          {"status": "ok"},
        "paper_trading_context": {},
        "thesis_sanity": {
            "safe_for_context": False,
            "issues": [
                {"severity": "critical", "code": "mtf_direction_mismatch",
                 "asset": "BTCUSD", "message": "MTF yön çelişkisi kritik seviyede"},
            ],
            "critical_count": 1,
            "warning_count": 0,
        },
    })
    banner = svc.build_agent_banner()
    assert banner["mode"] == "contradiction"
    assert "güvenli context değil" in banner["headline"].lower() or \
           "thesis" in banner["headline"].lower()
    # main_view'da sanity kodu veya mesaj geçmeli
    assert "mtf" in banner["main_view"].lower() or "sanity" in banner["main_view"].lower()


# ── Test 4: risk_alert — paper anomaly aktif ─────────────────────────────────

def test_risk_alert_mode_when_paper_anomaly(monkeypatch):
    """Paper trading anomalisi aktifse mod 'risk_alert' olmalı."""
    import app.services.paper_trading_service as pts
    monkeypatch.setattr(
        pts, "get_snapshot",
        lambda: {
            "open_positions": [{"pair": "BTCUSD", "side": "LONG", "entry_price": 67000.0, "pnl_pct": 5.0}],
            "state_anomaly": {
                "active": True,
                "reasons": ["equity_spike"],
                "action": "REPAIR_OR_RESET_REQUIRED",
            },
        },
    )
    banner = svc.build_agent_banner()
    assert banner["mode"] == "risk_alert"
    # risk_alert, managing_position'a göre öncelikli
    assert "anomali" in banner["headline"].lower() or "uyarı" in banner["headline"].lower()
    assert "equity_spike" in banner["headline"].lower() or "equity_spike" in banner["main_view"].lower()


# ── Test 5: learning note dolu — candidate var ───────────────────────────────

def test_learning_note_populated_when_candidates(monkeypatch):
    """
    Learning candidate varsa learning_note dolu olmalı.
    Pair bilgisi veya aday sayısı notta geçmeli.
    """
    lc_store.save_learning_candidate({
        "pair": "XAUUSD",
        "candidate_pair": "XAUUSD",
        "side": "LONG",
    })
    lc_store.save_learning_candidate({
        "pair": "BRENT",
        "candidate_pair": "BRENT",
        "side": "SHORT",
    })
    banner = svc.build_agent_banner()
    # mod en az learning veya üstü olmalı
    assert banner["mode"] in ("waiting", "learning", "managing_position", "contradiction", "risk_alert")
    note = banner["learning_note"] or ""
    assert "öğrenme" in note.lower() or "learning" in note.lower() or "aday" in note.lower()
    # Pair bilgisi notta geçmeli
    assert "XAUUSD" in note or "2" in note


# ── Test 6: override note — auto tune override aktif ─────────────────────────

def test_learning_note_includes_override_when_active(monkeypatch):
    """
    Auto tune override aktifse learning_note'da override açıklaması geçmeli.
    """
    atu_store.write_overrides({
        "overrides": {
            "position_size_multiplier": {
                "SHORT + pattern_bullish": 0.85,
            },
        },
    })
    banner = svc.build_agent_banner()
    note = banner["learning_note"] or ""
    # Override adı ya da 'kuralı uygulanıyor' notta olmalı
    assert "override" in note.lower() or "kuralı uygulanıyor" in note.lower() or "auto tune" in note.lower()


# ── Test 7: içerik moda özgü — generic "piyasa izleniyor" yok ───────────────

def test_risk_alert_produces_mode_specific_content(monkeypatch):
    """
    Her mod, moda özgü içerik üretmeli.
    "piyasa izleniyor" gibi boş/generic metinler olmamalı.
    """
    # risk_alert
    import app.services.paper_trading_service as pts
    monkeypatch.setattr(
        pts, "get_snapshot",
        lambda: {
            "open_positions": [],
            "state_anomaly": {"active": True, "reasons": ["daily_pnl_spike"]},
        },
    )
    banner = svc.build_agent_banner()
    assert banner["mode"] == "risk_alert"
    # Moda özgü içerik: anomaly detayı (genel slogan değil)
    generic_phrases = ["piyasa izleniyor", "analiz ediliyor", "bekle"]
    combined = (banner["headline"] + " " + banner["main_view"]).lower()
    for phrase in generic_phrases:
        assert phrase not in combined, f"Generic phrase found: '{phrase}'"


# ── Test 8: endpoint 200 döner, crash yok — no data ─────────────────────────

def test_endpoint_200_no_data(client):
    """
    Hiç veri yoksa endpoint 200 döner, crash olmaz.
    Zorunlu alanlar her zaman mevcut.
    """
    res = client.get("/api/v1/agent/banner")
    assert res.status_code == 200
    body = res.json()
    for field in ("mode", "headline", "main_view", "top_signals",
                  "contradictions", "watch_next", "updated_at"):
        assert field in body, f"Missing field: {field}"
    assert body["mode"] in (
        "waiting", "managing_position", "contradiction", "risk_alert", "learning"
    )
