"""
FAZ 1.5 — Saatlik snapshot payload builder.

Görev: RegimeReport / rotation / mtf / paper_trading_state objelerini
JSON-serializable dict'e çevirerek hourly_snapshot_store.save_hourly_snapshot()
için standart payload üretir.

Store ile ayrık: builder sadece payload döner; diske yazmaz.
Pipeline'a bu fazda otomatik bağlanmaz; çağıran taraf bağlar.

Güvenlik:
  decision_permission = "NO_EXECUTION"
  execution_mode      = "PAPER_SAFE"
"""
from __future__ import annotations

import dataclasses
from typing import Any


# ── Dahili seri dönüştürücü ────────────────────────────────────────────────────

def _to_serializable(obj: Any) -> Any:
    """
    Herhangi bir nesneyi JSON-serializable Python primitive'ine çevirir.

    Desteklenler:
      - frozen/mutable dataclass    → dict (dataclasses.asdict recursive)
      - tuple / list                → list (her eleman özyinelemeli)
      - dict                        → dict (her değer özyinelemeli)
      - int / float / str / bool / None → olduğu gibi
      - Diğer (datetime, Enum, …)  → str(obj)
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        # dataclasses.asdict: nested dataclass + tuple → dict + list
        try:
            return dataclasses.asdict(obj)
        except Exception:
            # Nadir durum: asdict başarısız olursa manuel fallback
            return {
                f.name: _to_serializable(getattr(obj, f.name, None))
                for f in dataclasses.fields(obj)
            }
    if isinstance(obj, dict):
        return {str(k): _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(i) for i in obj]
    # Enum, datetime, set, custom class …
    return str(obj)


def _safe_get(obj: Any, *attrs: str, default: Any = None) -> Any:
    """İç içe attr erişimi; her adımda güvenli getattr + _to_serializable."""
    cur = obj
    for attr in attrs:
        try:
            cur = getattr(cur, attr)
        except AttributeError:
            return default
    return _to_serializable(cur) if cur is not None else default


# ── Report dönüştürücüsü ───────────────────────────────────────────────────────

def _serialize_report(report: Any) -> dict[str, Any]:
    """RegimeReport dataclass'ını standart dict'e çevirir. None → boş default."""
    if report is None:
        return _empty_report()

    result: dict[str, Any] = {}

    # Dataclass alanları — her biri için güvenli dönüşüm
    for field_name, default in (
        ("macro_layer",           {}),
        ("appetite_layer",        {}),
        ("asset_signals",         []),
        ("confirmation_checklist", []),
        ("scenarios",             []),
        ("flip_conditions",       []),
        ("news_headlines",        []),
        ("tech_insights",         []),
    ):
        raw = getattr(report, field_name, None)
        result[field_name] = _to_serializable(raw) if raw is not None else default

    # Basit skaler alanlar
    for scalar in ("regime", "decision", "verdict", "owner_action",
                   "blocking_count", "confirmed_count", "pending_count",
                   "generated_at", "execution_mode"):
        val = getattr(report, scalar, None)
        if val is not None:
            result[scalar] = _to_serializable(val)

    # asymmetry — mevcut ise ekle
    asym = getattr(report, "asymmetry", None)
    result["asymmetry"] = _to_serializable(asym) if asym is not None else {}

    return result


def _empty_report() -> dict[str, Any]:
    return {
        "macro_layer":            {},
        "appetite_layer":         {},
        "asset_signals":          [],
        "confirmation_checklist": [],
        "scenarios":              [],
        "asymmetry":              {},
        "flip_conditions":        [],
        "news_headlines":         [],
        "tech_insights":          [],
    }


# ── Rotation dönüştürücüsü ────────────────────────────────────────────────────

def _serialize_rotation(rotation: Any) -> dict[str, Any]:
    """CapitalRotation dataclass → dict. None → {}."""
    if rotation is None:
        return {}
    return _to_serializable(rotation) if dataclasses.is_dataclass(rotation) else {}


# ── MTF dönüştürücüsü ─────────────────────────────────────────────────────────

def _serialize_mtf(mtf: Any) -> dict[str, Any]:
    """
    MultiTimeframeTechnicalProvider çıktısı:
      dict[asset_code: str, dict[timeframe: str, TechnicalInsight | dict]]
    """
    if not mtf or not isinstance(mtf, dict):
        return {}
    return _to_serializable(mtf)


# ── Paper trading dönüştürücüsü ───────────────────────────────────────────────

def _serialize_paper_trading(state: dict | None) -> dict[str, Any]:
    """
    paper_trading_service.get_snapshot() çıktısı zaten dict.
    Sadece güvenli kopyala; fazladan büyük alanları sil.
    """
    if not state or not isinstance(state, dict):
        return {"open_positions": [], "equity": None,
                "realized_pnl": None, "unrealized_pnl": None}

    # get_snapshot çıktısındaki minimal alanlar
    return {
        "open_positions":    _to_serializable(state.get("open_positions", [])),
        "equity":            state.get("equity"),
        "realized_pnl":      state.get("realized_pnl_usd") or state.get("realized_pnl"),
        "unrealized_pnl":    state.get("unrealized_pnl_usd") or state.get("unrealized_pnl"),
        "open_count":        state.get("open_count", len(state.get("open_positions", []))),
        "last_tick_at":      state.get("last_tick_at"),
        "anomaly":           state.get("anomaly"),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def build_hourly_snapshot_payload(
    report: Any = None,
    rotation: Any = None,
    mtf: Any = None,
    paper_trading_state: dict | None = None,
    data_quality: dict | None = None,
) -> dict[str, Any]:
    """
    Pipeline objeleri → hourly_snapshot_store için standart payload.

    Dönüş: save_hourly_snapshot()'a doğrudan geçirilebilecek dict.
    Eksik girdi: crash etmez; ilgili alan boş default alır.
    """
    dq: dict[str, Any] = dict(data_quality or {})
    dq.setdefault("status", "unknown")
    dq.setdefault("notes", [])

    return {
        # Güvenlik sabitleri — store tarafında da zorlanır; burada da set edilir
        "decision_permission": "NO_EXECUTION",
        "execution_mode":      "PAPER_SAFE",
        # Pipeline alanları
        "report":        _serialize_report(report),
        "rotation":      _serialize_rotation(rotation),
        "mtf":           _serialize_mtf(mtf),
        "paper_trading": _serialize_paper_trading(paper_trading_state),
        "data_quality":  dq,
    }
