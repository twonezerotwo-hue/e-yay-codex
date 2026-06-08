"""
POST /api/v1/market-strategist/chat

Üst-düzey piyasa stratejisti perspektif analizi.

Kullanıcı sorusunu alır; mevcut sistem verilerini (rejim, konsensus, teknik
sinyaller, chart pattern, S/R kalitesi, attribution istatistikleri ve uyarılar)
tek bir bağlam paketi hâline getirip Claude'a iletir; yapılandırılmış JSON
cevap döner.

PAPER_SAFE / NO_EXECUTION — saf analiz, gerçek emir / broker entegrasyonu YOK.
Tüm kararlar insana aittir.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import market_strategist_service as mss

router = APIRouter(prefix="/market-strategist", tags=["market-strategist"])

_PAPER_SAFE_NOTICE = "PAPER_SAFE / NO_EXECUTION — tüm kararlar insana aittir."


# ── Request / Response schemas ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    question:    str             = Field(..., min_length=3, max_length=2000,
                                         description="Kullanıcının stratejik sorusu")
    symbols:     list[str] | None = Field(default=None,
                                          description="İlgili varlık kodları (BTCUSD, XAUUSD …)")
    snapshot_id: str | None      = Field(default=None,
                                          description="Belirli snapshot ID, yoksa güncel veri")
    language:    str             = Field(default="tr",
                                          description="Cevap dili: 'tr' veya 'en'")
    provider:    str | None      = Field(default=None,
                                          description="Manuel sağlayıcı seçimi: auto (varsayılan, Groq→Claude) | groq | claude")


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/chat")
def market_strategist_chat(body: ChatRequest) -> dict:
    """
    Piyasa stratejisti perspektif analizi.

    • Kamuya açık sinyallere dayalı senaryo ve aktör perspektif analizi üretir.
    • İçerden bilgi, gizli plan veya emir dili içermez.
    • `abstained: true` ise model çağrısı olmadan statik çerçeve döner.
    """
    try:
        response, ctx = mss.answer(
            question    = body.question,
            symbols     = body.symbols,
            snapshot_id = body.snapshot_id,
            language    = body.language,
            provider    = body.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    resp_dict = asdict(response)

    return {
        "status":               "ok",
        "mode":                 "MARKET_STRATEGIST",
        "paper_safe":           True,
        "execution_side_effects": "NO_EXECUTION",
        "safety_notice":        _PAPER_SAFE_NOTICE,
        # context meta (no raw internal data)
        "context_meta": {
            "snapshot_id":   ctx.snapshot_id,
            "generated_at":  ctx.generated_at,
            "regime":        ctx.regime,
            "decision":      ctx.decision,
            "missing_data":  ctx.missing_data,
            "symbols":       body.symbols or list(mss._DEFAULT_SYMBOLS),
        },
        # strategist output
        "answer":                 resp_dict["answer"],
        "market_read":            resp_dict["market_read"],
        "cross_asset_map":        resp_dict["cross_asset_map"],
        "actor_perspective_map":  resp_dict["actor_perspective_map"],
        "headline_scenarios":     resp_dict["headline_scenarios"],
        "invalidation":           resp_dict["invalidation"],
        "confidence":             resp_dict["confidence"],
        "evidence_refs":          resp_dict["evidence_refs"],
        "abstained":              resp_dict["abstained"],
        "abstain_reason":         resp_dict["abstain_reason"],
        "model_used":             resp_dict["model_used"],
    }


__all__ = ["router"]
