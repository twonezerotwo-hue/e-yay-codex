"""
Agent Tool Registry — Sprint 6 / Item 6 (puan 92).

Agent'in çağırabileceği araçların tek katalog noktası.

Tasarım:
  • Her araç bir AgentTool — name, description, input_schema (JSON schema),
    handler (Python callable). PAPER_SAFE — execution değil veri/analiz.
  • LLM provider'a verilebilir Anthropic tool format'ına `to_anthropic_tools()`.
  • Direkt çağrı: `invoke(name, params)` → dict (no exception unless invalid).
  • Audit: her invoke audit log'a `tool.<name>` endpoint'i olarak yazılır.

Şu an kayıtlı (V1) araçlar:
  • get_market_snapshots — son fiyat snapshot'ları
  • get_geo_news        — jeopolitik başlıklar
  • get_technical       — teknik göstergeler
  • get_capital_rotation — sermaye rotasyonu
  • get_regime_report   — full regime rapor (özet)
  • get_chart_patterns  — pattern listesi
  • get_recent_audit    — son agent kararları
  • get_recent_evals    — son eval sonuçları
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from app.services import agent_audit_log


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., dict[str, Any]]
    category: str = "data"
    paper_safe: bool = True

    def to_anthropic(self) -> dict[str, Any]:
        """Anthropic Messages API tool format."""
        return {
            "name":         self.name,
            "description":  self.description,
            "input_schema": self.input_schema,
        }


_REGISTRY: dict[str, AgentTool] = {}


def register(tool: AgentTool) -> None:
    _REGISTRY[tool.name] = tool


def list_tools() -> list[dict[str, Any]]:
    return [
        {
            "name":         t.name,
            "description":  t.description,
            "category":     t.category,
            "paper_safe":   t.paper_safe,
            "input_schema": t.input_schema,
        }
        for t in _REGISTRY.values()
    ]


def get_tool(name: str) -> AgentTool | None:
    return _REGISTRY.get(name)


def to_anthropic_tools() -> list[dict[str, Any]]:
    """LLM provider'a verilecek tool array."""
    return [t.to_anthropic() for t in _REGISTRY.values()]


def invoke(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Aracı çağır. Audit log'a kayıt + hata yakalama."""
    params = params or {}
    tool = _REGISTRY.get(name)
    start = time.monotonic()
    if tool is None:
        return {"status": "error", "tool": name, "error": "tool_not_found"}
    try:
        result = tool.handler(**params)
        if not isinstance(result, dict):
            result = {"value": result}
        out = {"status": "ok", "tool": name, "result": result}
    except TypeError as exc:
        out = {"status": "error", "tool": name, "error": f"bad_params: {exc!s:.180}"}
    except Exception as exc:  # noqa: BLE001
        out = {"status": "error", "tool": name, "error": f"handler_failed: {exc!s:.180}"}

    duration_ms = (time.monotonic() - start) * 1000.0
    try:
        agent_audit_log.record(
            endpoint=f"tool.{name}",
            input_payload={"params": params},
            output_payload={"status": out.get("status")},
            model="tool-registry",
            tool_calls=[name],
            duration_ms=duration_ms,
        )
    except Exception:
        pass
    return out


# ────────────────────────────────────────────────────────────────────────────
# Lazy handler'lar — pahalı import'ları çalıştırma anına ertele
# ────────────────────────────────────────────────────────────────────────────

def _h_market_snapshots(symbols: list[str] | None = None) -> dict[str, Any]:
    from app.providers.real_market_provider import RealMarketProvider
    snaps = RealMarketProvider().fetch_market_snapshots()
    out = []
    wanted = {s.upper() for s in symbols} if symbols else None
    for s in snaps:
        sym = getattr(s, "asset_symbol", None) or getattr(s, "symbol", None)
        if wanted and str(sym).upper() not in wanted:
            continue
        out.append({
            "symbol": sym,
            "value":  getattr(s, "value", None) or getattr(s, "price", None),
            "unit":   getattr(s, "unit", None),
            "as_of":  getattr(s, "as_of", None) or getattr(s, "captured_at", None),
        })
    return {"count": len(out), "items": out}


def _h_geo_news(max_total: int = 10) -> dict[str, Any]:
    from app.providers.geo_news_provider import GeoNewsProvider
    items = GeoNewsProvider().fetch(max_total=int(max_total))
    out = []
    for h in items:
        out.append({
            "title":     getattr(h, "title", None) or getattr(h, "headline", None),
            "source":    getattr(h, "source", None),
            "published": getattr(h, "published_at", None) or getattr(h, "ts", None),
            "score":     getattr(h, "score", None),
        })
    return {"count": len(out), "items": out}


def _h_technical(symbol: str | None = None) -> dict[str, Any]:
    from app.providers.technical_provider import TechnicalProvider
    data = TechnicalProvider().compute()
    if symbol:
        v = data.get(symbol) or data.get(symbol.upper())
        return {"symbol": symbol, "data": v}
    return {"count": len(data) if isinstance(data, dict) else 0, "data": data}


def _h_capital_rotation() -> dict[str, Any]:
    from app.providers.capital_rotation_provider import CapitalRotationProvider
    r = CapitalRotationProvider().compute()
    if r is None:
        return {"status": "no_data"}
    import dataclasses
    if dataclasses.is_dataclass(r):
        return dataclasses.asdict(r)
    return {"value": str(r)}


def _h_regime_report() -> dict[str, Any]:
    """Regime özet — ağır pipeline, ufak özetle döner."""
    from app.api.regime_report import get_regime_report
    try:
        rep = get_regime_report()
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:180]}
    if not isinstance(rep, dict):
        try:
            import json
            rep = json.loads(bytes(rep.body).decode("utf-8"))
        except Exception:
            return {"status": "error", "error": "report_decode_failed"}
    # Slim
    macro = rep.get("macro_layer") or {}
    appetite = rep.get("appetite_layer") or {}
    return {
        "decision":  rep.get("decision"),
        "verdict":   rep.get("verdict"),
        "regime":    macro.get("regime"),
        "macro_confidence_pct": macro.get("confidence_pct"),
        "appetite":  appetite.get("status"),
        "assets_count": len(rep.get("asset_signals") or []),
    }


def _h_chart_patterns() -> dict[str, Any]:
    from app.api.chart_patterns import list_chart_patterns
    return list_chart_patterns() or {}


def _h_recent_audit(limit: int = 10, endpoint: str | None = None) -> dict[str, Any]:
    items = agent_audit_log.get_recent(limit=int(limit), endpoint=endpoint)
    return {"count": len(items), "items": items}


def _h_recent_evals(limit: int = 10) -> dict[str, Any]:
    from app.services import agent_eval_service
    items = agent_eval_service.get_recent_evals(limit=int(limit))
    return {"count": len(items), "items": items}


def _h_read_chart(symbol: str, timeframes: list[str] | None = None) -> dict[str, Any]:
    from app.services import agent_chart_reader_service as cr
    tfs = timeframes if timeframes else ["1h", "4h", "1d"]
    reading = cr.read_chart(symbol, timeframes=tfs)
    return cr.reading_to_dict(reading)


# ────────────────────────────────────────────────────────────────────────────
# Schema'lar
# ────────────────────────────────────────────────────────────────────────────

_OBJ = {"type": "object"}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    s: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        s["required"] = required
    return s


# ────────────────────────────────────────────────────────────────────────────
# V1 kayıt
# ────────────────────────────────────────────────────────────────────────────

register(AgentTool(
    name="get_market_snapshots",
    description="Son piyasa fiyat snapshot'larını döndürür (BTC, XAU, indeksler vb).",
    input_schema=_schema({
        "symbols": {
            "type":  "array",
            "items": {"type": "string"},
            "description": "İsteğe bağlı; verilen sembollerle filtrele.",
        },
    }),
    handler=_h_market_snapshots,
    category="data",
))

register(AgentTool(
    name="get_geo_news",
    description="Son jeopolitik haber başlıklarını döndürür.",
    input_schema=_schema({
        "max_total": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
    }),
    handler=_h_geo_news,
    category="data",
))

register(AgentTool(
    name="get_technical",
    description="Teknik göstergeleri (destek/direnç, momentum) döndürür.",
    input_schema=_schema({
        "symbol": {"type": "string", "description": "İsteğe bağlı tek sembol filtresi."},
    }),
    handler=_h_technical,
    category="analysis",
))

register(AgentTool(
    name="get_capital_rotation",
    description="Sermaye rotasyon sinyalini döndürür (defansif/risk-on vb).",
    input_schema=_OBJ,
    handler=_h_capital_rotation,
    category="analysis",
))

register(AgentTool(
    name="get_regime_report",
    description="Rejim raporunun özetini döndürür (decision, verdict, makro güven).",
    input_schema=_OBJ,
    handler=_h_regime_report,
    category="analysis",
))

register(AgentTool(
    name="get_chart_patterns",
    description="Tespit edilen chart pattern'lerin listesini döndürür.",
    input_schema=_OBJ,
    handler=_h_chart_patterns,
    category="analysis",
))

register(AgentTool(
    name="get_recent_audit",
    description="Son agent karar kayıtlarını döndürür.",
    input_schema=_schema({
        "limit":    {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
        "endpoint": {"type": "string", "description": "İsteğe bağlı endpoint filtresi."},
    }),
    handler=_h_recent_audit,
    category="introspection",
))

register(AgentTool(
    name="get_recent_evals",
    description="Son agent eval skorlarını döndürür (geriye dönük doğruluk).",
    input_schema=_schema({
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
    }),
    handler=_h_recent_evals,
    category="introspection",
))

register(AgentTool(
    name="read_chart",
    description=(
        "Çoklu timeframe grafik okuma: 1h/4h/1d için trend, destek-direnç, ATR, "
        "RSI(14), TF hizalama özeti. yfinance üzerinden anlık çeker."
    ),
    input_schema=_schema({
        "symbol": {
            "type": "string",
            "description": "BTCUSD, XAUUSD, XAGUSD, XCUUSD, BRENT, SP500, DXY, VIX, ETHUSD vb.",
        },
        "timeframes": {
            "type": "array",
            "items": {"type": "string", "enum": ["1h", "4h", "1d", "1wk"]},
            "description": "Varsayılan: [\"1h\",\"4h\",\"1d\"]",
        },
    }, required=["symbol"]),
    handler=_h_read_chart,
    category="analysis",
))


__all__ = [
    "AgentTool",
    "register",
    "list_tools",
    "get_tool",
    "to_anthropic_tools",
    "invoke",
]
