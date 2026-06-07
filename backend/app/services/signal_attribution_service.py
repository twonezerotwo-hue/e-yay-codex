"""
Signal Attribution Service
─────────────────────────────────────────────────────────────────────────────

Her paper trade kapandığında, açılış sinyalindeki modül katkılarına göre PnL'i
modüller arasında dağıtır ve toplam istatistik tutar.

Amaç: "Hangi modül para kazandırıyor / kaybettiriyor?" sorusunu cevaplamak.

PAPER_SAFE · NO_EXECUTION — sadece analiz, gerçek emir yok.

Veri akışı:
    Trade (paper_trading_service) ─┐
                                    │
                                    ▼
                          record_trade(trade)
                                    │
                                    ▼
      open_signal.base.contributions[module].weighted_score
                                    │
                                    ▼
           module_share = ws / Σws  (normalize)
                                    │
                                    ▼
              pnl_share = pnl_usd × module_share
                                    │
                                    ▼
          AttributionState (JSONL persisted ring)
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# ── Persistence ────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_JSONL_PATH = _DATA_DIR / "signal_attribution.jsonl"
_MAX_RING = 2000  # son N trade attribution kaydı bellekte tut

# Canonical modules — consensus_engine.CANONICAL_MODULES ile aynı sıra
CANONICAL_MODULES = ("touche", "fundamental", "news", "sentinel", "quantum", "chart_pattern")


# ── State dataclasses ─────────────────────────────────────────────────────

@dataclass
class TradeAttribution:
    """Tek trade için modül bazlı PnL dağılımı."""
    trade_id:        int
    pair:            str
    side:            str
    pnl_usd:         float
    pnl_pct:         float
    verdict:         str           # "WIN" | "LOSS" | "BREAK_EVEN"
    closed_at:       str
    entry_score:     float | None
    entry_direction: str | None
    # module → {weighted_score, share, pnl_share}
    module_shares:   dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class ModuleStats:
    """Tek modül için kümülatif istatistik."""
    module:           str
    trade_count:      int   = 0
    wins:             int   = 0
    losses:           int   = 0
    break_even:       int   = 0
    total_pnl_share:  float = 0.0
    total_abs_pnl:    float = 0.0   # |pnl_share| toplamı — etki büyüklüğü
    sum_weighted_score: float = 0.0  # ortalama katkı puanı için

    @property
    def win_rate(self) -> float:
        decided = self.wins + self.losses
        return round(self.wins / decided * 100, 2) if decided else 0.0

    @property
    def avg_pnl_per_trade(self) -> float:
        return round(self.total_pnl_share / self.trade_count, 4) if self.trade_count else 0.0

    @property
    def avg_weighted_score(self) -> float:
        return round(self.sum_weighted_score / self.trade_count, 2) if self.trade_count else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "module":              self.module,
            "trade_count":         self.trade_count,
            "wins":                self.wins,
            "losses":              self.losses,
            "break_even":          self.break_even,
            "win_rate":            self.win_rate,
            "total_pnl_share":     round(self.total_pnl_share, 2),
            "total_abs_pnl":       round(self.total_abs_pnl, 2),
            "avg_pnl_per_trade":   self.avg_pnl_per_trade,
            "avg_weighted_score":  self.avg_weighted_score,
        }


# ── In-memory ring + lock ─────────────────────────────────────────────────

_LOCK = threading.RLock()
_RING: list[TradeAttribution] = []
_LOADED = False


def _atomic_append(record: dict[str, Any]) -> None:
    try:
        with _JSONL_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("attribution jsonl yazılamadı: %s", exc)


def _ensure_loaded() -> None:
    """JSONL'den son _MAX_RING kaydı belleğe çek (one-shot)."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    if not _JSONL_PATH.exists():
        return
    try:
        lines = _JSONL_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines[-_MAX_RING:]:
            try:
                d = json.loads(line)
                _RING.append(TradeAttribution(**d))
            except (json.JSONDecodeError, TypeError):
                continue
    except OSError as exc:
        logger.warning("attribution jsonl okunamadı: %s", exc)


# ── Core: extract contribution from open_signal ───────────────────────────

def _extract_contributions(open_signal: dict[str, Any]) -> dict[str, float]:
    """
    open_signal.base.contributions[module].weighted_score değerlerini çıkar.

    Beklenen format:
      {"base": {"contributions": {"touche": {"weighted_score": 12.5}, ...}}}

    Tüm modül skoları pozitif sayı kabul edilir; mutlak değer döner.
    Eksik modül ya da yanlış format → boş dict.
    """
    if not isinstance(open_signal, dict):
        return {}
    base = open_signal.get("base") or {}
    contribs = base.get("contributions") or {}
    if not isinstance(contribs, dict):
        return {}

    out: dict[str, float] = {}
    for mod, payload in contribs.items():
        if mod not in CANONICAL_MODULES:
            continue
        ws = 0.0
        if isinstance(payload, dict):
            ws = float(payload.get("weighted_score") or 0.0)
        elif isinstance(payload, (int, float)):
            ws = float(payload)
        out[mod] = abs(ws)
    return out


def _compute_shares(contributions: dict[str, float]) -> dict[str, float]:
    """Toplam ağırlıklı skora göre normalize edilmiş paylar (0..1)."""
    total = sum(contributions.values())
    if total <= 0:
        return {}
    return {mod: round(ws / total, 6) for mod, ws in contributions.items()}


# ── Public API ────────────────────────────────────────────────────────────

def record_trade(trade: Any) -> TradeAttribution | None:
    """
    Paper trade kapandığında çağrılır. Modül bazlı PnL dağılımını üretir,
    belleğe + JSONL'e yazar, sonucu döner.

    `trade` parametresi `Trade` dataclass'ı ya da uyumlu dict olmalı.
    Aşağıdaki alanlar okunur:
       id, pair, side, pnl_usd, pnl_pct, verdict, exit_at, open_signal
    """
    _ensure_loaded()
    with _LOCK:
        try:
            if hasattr(trade, "__dataclass_fields__"):
                t = asdict(trade)
            elif isinstance(trade, dict):
                t = trade
            else:
                logger.warning("record_trade: desteklenmeyen trade tipi: %s", type(trade))
                return None

            open_signal = t.get("open_signal") or {}
            contribs    = _extract_contributions(open_signal)
            shares      = _compute_shares(contribs)
            pnl_usd     = float(t.get("pnl_usd") or 0.0)

            module_shares: dict[str, dict[str, float]] = {}
            for mod, share in shares.items():
                module_shares[mod] = {
                    "weighted_score": round(contribs.get(mod, 0.0), 4),
                    "share":          share,
                    "pnl_share":      round(pnl_usd * share, 4),
                }

            attribution = TradeAttribution(
                trade_id        = int(t.get("id") or 0),
                pair            = str(t.get("pair") or ""),
                side            = str(t.get("side") or ""),
                pnl_usd         = round(pnl_usd, 4),
                pnl_pct         = round(float(t.get("pnl_pct") or 0.0), 4),
                verdict         = str(t.get("verdict") or ""),
                closed_at       = str(t.get("exit_at") or datetime.now(UTC).isoformat()),
                entry_score     = (float(open_signal.get("final_score"))
                                   if open_signal.get("final_score") is not None else None),
                entry_direction = open_signal.get("final_direction"),
                module_shares   = module_shares,
            )

            _RING.append(attribution)
            if len(_RING) > _MAX_RING:
                del _RING[: len(_RING) - _MAX_RING]
            _atomic_append(asdict(attribution))
            return attribution
        except Exception as exc:
            logger.exception("record_trade hatası: %s", exc)
            return None


def get_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Son N attribution kaydı (yeni → eski)."""
    _ensure_loaded()
    with _LOCK:
        if limit <= 0:
            return []
        slice_ = _RING[-limit:][::-1]
        return [asdict(a) for a in slice_]


def get_module_stats(
    *,
    pair_filter: str | None = None,
    side_filter: str | None = None,
    last_n: int | None = None,
) -> list[dict[str, Any]]:
    """
    Tüm trade'ler boyunca modül bazlı toplu istatistik döndürür.

    pair_filter / side_filter verilirse sadece eşleşen trade'ler hesaba katılır.
    last_n verilirse sadece son N trade.
    """
    _ensure_loaded()
    with _LOCK:
        stats: dict[str, ModuleStats] = {m: ModuleStats(module=m) for m in CANONICAL_MODULES}

        records: Iterable[TradeAttribution] = _RING
        if last_n and last_n > 0:
            records = _RING[-last_n:]

        for a in records:
            if pair_filter and a.pair != pair_filter:
                continue
            if side_filter and a.side != side_filter:
                continue
            for mod, payload in a.module_shares.items():
                if mod not in stats:
                    continue
                s = stats[mod]
                s.trade_count       += 1
                s.total_pnl_share   += payload.get("pnl_share", 0.0)
                s.total_abs_pnl     += abs(payload.get("pnl_share", 0.0))
                s.sum_weighted_score += payload.get("weighted_score", 0.0)
                if a.verdict == "WIN":
                    s.wins += 1
                elif a.verdict == "LOSS":
                    s.losses += 1
                else:
                    s.break_even += 1

        return [s.to_dict() for s in stats.values() if s.trade_count > 0]


def summary() -> dict[str, Any]:
    """Üst düzey özet — toplam trade, tüm modüller, en iyi/en kötü."""
    _ensure_loaded()
    with _LOCK:
        modules = get_module_stats()
        if not modules:
            return {
                "execution_mode":  "PAPER_SAFE / NO_EXECUTION",
                "trade_count":     len(_RING),
                "modules":         [],
                "best_module":     None,
                "worst_module":    None,
            }

        # En çok kazandıran / en çok kaybettiren
        ranked = sorted(modules, key=lambda m: m["total_pnl_share"], reverse=True)
        return {
            "execution_mode":  "PAPER_SAFE / NO_EXECUTION",
            "trade_count":     len(_RING),
            "modules":         ranked,
            "best_module":     ranked[0]["module"] if ranked else None,
            "worst_module":    ranked[-1]["module"] if ranked else None,
        }


def reset() -> None:
    """Test/diagnostic için ring + dosya sıfırla."""
    global _LOADED
    with _LOCK:
        _RING.clear()
        _LOADED = True  # boş kabul, JSONL'i yeniden yüklemesin
        try:
            if _JSONL_PATH.exists():
                _JSONL_PATH.unlink()
        except OSError:
            pass


__all__ = [
    "CANONICAL_MODULES",
    "TradeAttribution",
    "ModuleStats",
    "record_trade",
    "get_recent",
    "get_module_stats",
    "summary",
    "reset",
]
