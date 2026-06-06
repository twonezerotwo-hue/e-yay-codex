"""
Paper Trading Engine — agent sinyallerine göre otomatik long/short.

Mekanik:
  • Başlangıç bakiyesi: $100,000
  • 4 parite: BTCUSD, XAUUSD (altın), XAGUSD (gümüş), BRENT
  • Her parite için max 1 açık pozisyon, $25,000 büyüklük
  • Sinyal LONG / SHORT  → pozisyon aç
  • Sinyal AVOID / yön değişimi → pozisyon kapat
  • LONG_AWAIT / SHORT_AWAIT / HOLD / NEUTRAL → dokunma
  • Realized PnL kayıtlı, Unrealized PnL canlı hesaplanır

PAPER_SAFE / NO_EXECUTION — sadece simülasyon, gerçek emir YOK.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

PositionSide = Literal["LONG", "SHORT"]
TradeEvent   = Literal["OPEN", "CLOSE"]

# ── Sabitler ──────────────────────────────────────────────────────────────────

STARTING_BALANCE = 100_000.0
POSITION_SIZE    = 25_000.0   # baz pozisyon büyüklüğü (consensus güveni ile ×0.6 .. ×1.5)
TRADED_PAIRS     = ("BTCUSD", "XAUUSD", "XAGUSD", "BRENT")
MARKET_HOURS_GATED_PAIRS = frozenset({"XAUUSD", "XAGUSD", "BRENT", "XCUUSD"})
MARKET_CLOSE_FRIDAY_UTC_HOUR = 21
MARKET_OPEN_SUNDAY_UTC_HOUR = 22
OPEN_CONFIRMATION_WINDOW_SECONDS = 60
DAILY_LOSS_LIMIT_USD = -5_000.0   # günlük zarar uyarı eşiği

# Consensus-driven karar eşikleri
STRONG_LONG_THR   = 70.0   # consensus + confluence aligned ile → 1.5× pos
LONG_THR          = 60.0   # zayıf bullish → 1.0× pos
SHORT_THR         = 40.0   # zayıf bearish → 1.0× pos
STRONG_SHORT_THR  = 30.0   # consensus + aligned → 1.5× pos


def _action_to_side(asset_action: str) -> PositionSide | Literal["CLOSE"] | None:
    """ESKİ MOD: Agent asset_action sinyalini paper trading aksiyonuna çevir.
       Backward compatibility için tutuluyor."""
    if asset_action == "LONG":
        return "LONG"
    if asset_action == "SHORT":
        return "SHORT"
    if asset_action in ("AVOID",):
        return "CLOSE"
    return None


def _consensus_to_action(
    final_score: float | None,
    final_direction: str | None,
    confluence_status: str | None = None,
) -> tuple[PositionSide | Literal["CLOSE"] | None, float]:
    """
    YENİ MOD: Multi-TF consensus skoru → (action, size_multiplier).

    Returns:
      (action, multiplier) burada:
        action       = "LONG" | "SHORT" | "CLOSE" | None (None=dokunma)
        multiplier   = pozisyon büyüklüğü katsayısı (0.6 .. 1.5)
    """
    if final_score is None or final_direction is None:
        return None, 1.0

    aligned = confluence_status == "aligned"
    opposing = confluence_status == "opposing"

    # Bullish — güven seviyesine göre
    if final_direction == "bullish":
        if final_score >= STRONG_LONG_THR and aligned:
            return "LONG", 1.5
        if final_score >= LONG_THR:
            return "LONG", 1.0
        if final_score >= 55.0:
            return "LONG", 0.6  # zayıf — küçük pozisyon
        return None, 1.0

    # Bearish — güven seviyesine göre
    if final_direction == "bearish":
        if final_score <= STRONG_SHORT_THR and aligned:
            return "SHORT", 1.5
        if final_score <= SHORT_THR:
            return "SHORT", 1.0
        if final_score <= 45.0:
            return "SHORT", 0.6
        return None, 1.0

    # Neutral
    if final_direction == "neutral":
        # Opposing confluence varsa pozisyon kapat (riskten kaç)
        if opposing:
            return "CLOSE", 1.0
        # Saf nötr — yeni açma, mevcut tutma
        return None, 1.0

    return None, 1.0


_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_trading_state.json"
_LOCK = threading.Lock()

# ── Alert deduplication (spam önleme) ────────────────────────────────────────
_MARKET_CLOSE_WARNED: dict[str, str] = {}    # pair → ISO date
_DAILY_LOSS_WARNED_DATES: set[str] = set()   # ISO date


def _try_emit(event_type: str, level: str, title: str, message: str, **kwargs: Any) -> None:
    """Alert event'i güvenli şekilde emit et — hata olursa trading etkilenmez."""
    try:
        from app.services.alert_event_service import emit
        emit(event_type, level, title, message, **kwargs)  # type: ignore[arg-type]
    except Exception:
        pass


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _is_market_open(pair: str, as_of: datetime | None = None) -> bool:
    if pair not in MARKET_HOURS_GATED_PAIRS:
        return True

    now = as_of or _utc_now()
    weekday = now.weekday()
    hour = now.hour

    if weekday == 5:
        return False
    if weekday == 4 and hour >= MARKET_CLOSE_FRIDAY_UTC_HOUR:
        return False
    if weekday == 6 and hour < MARKET_OPEN_SUNDAY_UTC_HOUR:
        return False
    return True


# ── Veri modelleri ────────────────────────────────────────────────────────────

# ── SL/TP sabit yüzdeleri (ATR yoksa) ────────────────────────────────────────
_SL_PCT: dict[str, float] = {
    "BTCUSD": 0.04,
    "XAUUSD": 0.03,
    "XAGUSD": 0.05,
    "BRENT":  0.04,
}
_TP_MULT = 2.0   # TP = SL × TP_MULT  (örn. SL%4 → TP%8 = 2:1 RR)

def _calc_sl_tp(
    side: PositionSide,
    entry: float,
    pair: str,
    atr: float | None = None,
) -> tuple[float, float]:
    """ATR varsa 2×ATR SL / 3×ATR TP, yoksa sabit yüzde kullan."""
    sl_pct = _SL_PCT.get(pair, 0.04)
    if atr and atr > 0:
        risk   = 2.0 * atr
        reward = 3.0 * atr
    else:
        risk   = entry * sl_pct
        reward = entry * sl_pct * _TP_MULT
    if side == "LONG":
        return round(entry - risk, 4), round(entry + reward, 4)
    else:
        return round(entry + risk, 4), round(entry - reward, 4)


@dataclass
class Position:
    pair:        str
    side:        PositionSide
    entry_price: float
    entry_at:    str
    size_usd:    float
    last_signal: str
    stop_loss:   float = 0.0    # otomatik SL seviyesi
    take_profit: float = 0.0    # otomatik TP seviyesi
    # ── Öğrenme için: pozisyon açılırken alınan sinyal snapshot'ı ──
    open_signal: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""        # sinyal imzası (benzer durumları tanıma için)


@dataclass
class PendingOpenOrder:
    pair: str
    side: PositionSide
    requested_at: str
    execute_at: str
    requested_price: float
    size_usd: float
    last_signal: str
    open_signal: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""


@dataclass
class RejectedOpenSignal:
    pair: str
    side: PositionSide
    fingerprint: str
    rejected_at: str


@dataclass
class Trade:
    id:           int
    pair:         str
    side:         PositionSide
    entry_price:  float
    exit_price:   float
    entry_at:     str
    exit_at:      str
    size_usd:     float
    pnl_usd:      float
    pnl_pct:      float
    duration_min: int
    reason:       str
    # ── Öğrenme alanları ──
    open_signal:  dict[str, Any] = field(default_factory=dict)
    exit_signal:  dict[str, Any] = field(default_factory=dict)
    verdict:      str = ""       # "WIN" | "LOSS" | "BREAK_EVEN"
    fingerprint:  str = ""       # benzer trade lookup için


@dataclass
class TradingState:
    starting_balance: float = STARTING_BALANCE
    realized_pnl_usd: float = 0.0
    positions:        dict[str, Position]   = field(default_factory=dict)
    pending_orders:   dict[str, PendingOpenOrder] = field(default_factory=dict)
    rejected_signals: dict[str, RejectedOpenSignal] = field(default_factory=dict)
    trades:           list[Trade]           = field(default_factory=list)
    last_event:       dict[str, Any] | None = None
    last_event_at:    str | None            = None
    # ── Otomatik ağırlık öğrenmesi ──
    weight_adjustments: dict[str, dict[str, float]] = field(default_factory=dict)
    # ↑ {regime_key: {module: delta}} — baseline YAML'a eklenen düzeltmeler
    last_trained_at_trade_count: int = 0
    training_history: list[dict[str, Any]] = field(default_factory=list)
    # ── Tick'in son ürettiği fiyat snapshot'ı — read-only GET için ──
    last_tick_prices: dict[str, float] = field(default_factory=dict)
    last_tick_at:     str | None       = None
    last_tick_signals: dict[str, dict[str, Any]] = field(default_factory=dict)


# ── State persist ─────────────────────────────────────────────────────────────

def _load_state() -> TradingState:
    if not _STATE_PATH.exists():
        return TradingState()
    try:
        raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))

        # Position — eski format default open_signal/fingerprint için backward compatible
        positions = {}
        for k, v in raw.get("positions", {}).items():
            v.setdefault("open_signal", {})
            v.setdefault("fingerprint", "")
            v.setdefault("stop_loss", 0.0)
            v.setdefault("take_profit", 0.0)
            positions[k] = Position(**v)

        pending_orders = {}
        for k, v in raw.get("pending_orders", {}).items():
            v.setdefault("open_signal", {})
            v.setdefault("fingerprint", "")
            pending_orders[k] = PendingOpenOrder(**v)

        rejected_signals = {}
        for k, v in raw.get("rejected_signals", {}).items():
            rejected_signals[k] = RejectedOpenSignal(**v)

        # Trade — eski format
        trades = []
        for t in raw.get("trades", []):
            t.setdefault("open_signal", {})
            t.setdefault("exit_signal", {})
            t.setdefault("verdict", "")
            t.setdefault("fingerprint", "")
            trades.append(Trade(**t))

        st = TradingState(
            starting_balance=raw.get("starting_balance", STARTING_BALANCE),
            realized_pnl_usd=raw.get("realized_pnl_usd", 0.0),
            positions=positions,
            pending_orders=pending_orders,
            rejected_signals=rejected_signals,
            trades=trades,
            last_event=raw.get("last_event"),
            last_event_at=raw.get("last_event_at"),
            weight_adjustments=raw.get("weight_adjustments", {}),
            last_trained_at_trade_count=raw.get("last_trained_at_trade_count", 0),
            training_history=raw.get("training_history", []),
            last_tick_prices=raw.get("last_tick_prices", {}),
            last_tick_at=raw.get("last_tick_at"),
            last_tick_signals=raw.get("last_tick_signals", {}),
        )
        return st
    except Exception:
        return TradingState()


def _save_state(st: TradingState) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "starting_balance": st.starting_balance,
        "realized_pnl_usd": st.realized_pnl_usd,
        "positions": {k: asdict(v) for k, v in st.positions.items()},
        "pending_orders": {k: asdict(v) for k, v in st.pending_orders.items()},
        "rejected_signals": {k: asdict(v) for k, v in st.rejected_signals.items()},
        "trades":    [asdict(t) for t in st.trades],
        "last_event": st.last_event,
        "last_event_at": st.last_event_at,
        "weight_adjustments": st.weight_adjustments,
        "last_trained_at_trade_count": st.last_trained_at_trade_count,
        "training_history": st.training_history,
        "last_tick_prices": st.last_tick_prices,
        "last_tick_at":     st.last_tick_at,
        "last_tick_signals": st.last_tick_signals,
    }
    _STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ── PnL helpers ───────────────────────────────────────────────────────────────

def _unrealized_pnl(p: Position, current_price: float) -> tuple[float, float]:
    """Pozisyonun (USD, %) cinsinden anlık PnL'i."""
    if current_price <= 0 or p.entry_price <= 0:
        return 0.0, 0.0
    if p.side == "LONG":
        pct = (current_price - p.entry_price) / p.entry_price
    else:
        pct = (p.entry_price - current_price) / p.entry_price
    return pct * p.size_usd, pct * 100.0


def _clear_rejected_signal_if_changed(
    st: TradingState,
    pair: str,
    target: PositionSide | Literal["CLOSE"] | None,
    fingerprint: str,
) -> bool:
    rejected = st.rejected_signals.get(pair)
    if rejected is None:
        return False

    if target in ("LONG", "SHORT") and rejected.side == target and rejected.fingerprint == fingerprint:
        return True

    del st.rejected_signals[pair]
    return False


def _queue_pending_open(
    st: TradingState,
    pair: str,
    side: PositionSide,
    price: float,
    size_usd: float,
    last_signal: str,
    signal_snapshot: dict[str, Any],
    fingerprint: str,
    now_dt: datetime,
) -> None:
    requested_at = now_dt.isoformat()
    execute_at = (now_dt + timedelta(seconds=OPEN_CONFIRMATION_WINDOW_SECONDS)).isoformat()
    st.pending_orders[pair] = PendingOpenOrder(
        pair=pair,
        side=side,
        requested_at=requested_at,
        execute_at=execute_at,
        requested_price=price,
        size_usd=size_usd,
        last_signal=last_signal,
        open_signal=signal_snapshot,
        fingerprint=fingerprint,
    )
    _try_emit(
        "pending_trade_created", "ACTION_REQUIRED",
        f"{side} {pair} Bekleyen İşlem",
        f"{OPEN_CONFIRMATION_WINDOW_SECONDS}s içinde {side} {pair} açılacak — reddedilmezse otomatik açılır.",
        pair=pair, side=side, size_usd=size_usd, price=price,
        metadata={"execute_at": execute_at},
    )


def _open_position_from_pending(
    st: TradingState,
    pending: PendingOpenOrder,
    current_price: float,
    opened_at: str,
) -> None:
    st.positions[pending.pair] = Position(
        pair=pending.pair,
        side=pending.side,
        entry_price=current_price,
        entry_at=opened_at,
        size_usd=pending.size_usd,
        last_signal=pending.last_signal,
        open_signal=pending.open_signal,
        fingerprint=pending.fingerprint,
    )
    st.last_event = {
        "type": "OPEN",
        "pair": pending.pair,
        "side": pending.side,
        "price": current_price,
        "size_usd": pending.size_usd,
        "fingerprint": pending.fingerprint,
    }
    st.last_event_at = opened_at
    st.pending_orders.pop(pending.pair, None)
    _try_emit(
        "paper_trade_opened", "TRADE_EVENT",
        f"{pending.side} {pending.pair} Açıldı",
        f"Paper pozisyon açıldı: {pending.side} {pending.pair} @ ${current_price:,.2f}",
        pair=pending.pair, side=pending.side,
        size_usd=pending.size_usd, price=current_price,
    )


# ── Tick (ana mekanizma) ─────────────────────────────────────────────────────

def _tick_consensus_legacy(
    consensus_signals: dict[str, dict[str, Any]],
    current_prices: dict[str, float],
) -> TradingState:
    """
    YENİ MOD: Multi-TF consensus skoruna göre pozisyon aç/kapat.

    Öğrenme entegre:
      • Pozisyon açılırken sinyalin TAM snapshot'ı + fingerprint kaydedilir
      • Açma öncesi: bu fingerprint'in geçmiş win rate'ine bakılır
        - AVOID  → işlem AÇILMAZ (öğrenilmiş hata)
        - BOOST  → pozisyon ×1.3
        - NORMAL → ×1.0
      • Pozisyon kapatılırken PnL + verdict + exit_signal kaydedilir
    """
    from app.services.learning_engine import (
        build_signal_fingerprint, should_avoid_or_boost,
    )

    with _LOCK:
        st = _load_state()
        now_iso = datetime.now(UTC).isoformat()

        for pair in TRADED_PAIRS:
            sig = consensus_signals.get(pair) or {}
            final_score = sig.get("final_score")
            final_direction = sig.get("final_direction")
            confluence = sig.get("confluence") or {}
            confluence_status = confluence.get("status") if isinstance(confluence, dict) else None

            target, base_mult = _consensus_to_action(final_score, final_direction, confluence_status)
            price = current_prices.get(pair, 0.0)
            if price <= 0:
                continue

            # ── ÖĞRENME: açma öncesi avoidance + boost ──
            learning_meta = {}
            final_size_mult = base_mult
            if target in ("LONG", "SHORT"):
                learning_meta = should_avoid_or_boost(sig, st.trades)
                if learning_meta["action"] == "AVOID":
                    # Öğrenilmiş hata — AÇMA
                    target = None
                elif learning_meta["action"] == "BOOST":
                    final_size_mult *= learning_meta["size_multiplier"]

            new_size = round(POSITION_SIZE * final_size_mult, 2)
            atr_val  = sig.get("atr")   # paper_trading.py'den geçirilirse kullanılır
            cur = st.positions.get(pair)

            # ── SL/TP otomatik tetikleme (mevcut pozisyon varsa) ──────────────
            if cur is not None and cur.stop_loss > 0 and cur.take_profit > 0:
                sl_hit = (cur.side == "LONG"  and price <= cur.stop_loss) or \
                         (cur.side == "SHORT" and price >= cur.stop_loss)
                tp_hit = (cur.side == "LONG"  and price >= cur.take_profit) or \
                         (cur.side == "SHORT" and price <= cur.take_profit)
                if sl_hit or tp_hit:
                    pnl_usd, pnl_pct = _unrealized_pnl(cur, price)
                    duration_min = int(
                        (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
                    )
                    close_reason = "SL" if sl_hit else "TP"
                    verdict = "WIN" if tp_hit else "LOSS"
                    trade_id = len(st.trades) + 1
                    st.trades.append(Trade(
                        id=trade_id, pair=pair, side=cur.side,
                        entry_price=cur.entry_price, exit_price=price,
                        entry_at=cur.entry_at, exit_at=now_iso,
                        size_usd=cur.size_usd,
                        pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 2),
                        duration_min=duration_min,
                        reason=close_reason,
                        open_signal=cur.open_signal,
                        exit_signal={"trigger": close_reason, "price": price},
                        verdict=verdict, fingerprint=cur.fingerprint,
                    ))
                    st.realized_pnl_usd += pnl_usd
                    st.last_event = {
                        "type": "CLOSE", "pair": pair, "side": cur.side,
                        "pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2),
                        "price": price, "verdict": verdict, "reason": close_reason,
                    }
                    st.last_event_at = now_iso
                    del st.positions[pair]
                    cur = None
                    _save_state(st)
                    continue   # bu pair için başka işlem yapma

            # ── Pozisyon var ──
            if cur is not None:
                # Aynı yön + skor güçlü → boyut güncellemesi (resize için kapatma)
                if target == cur.side:
                    cur.last_signal = f"{final_direction}@{final_score:.1f}" if final_score else "noop"
                    continue

                # Karşı yön veya CLOSE
                should_close = (
                    target in ("LONG", "SHORT") and target != cur.side
                ) or target == "CLOSE"

                if should_close:
                    pnl_usd, pnl_pct = _unrealized_pnl(cur, price)
                    duration_min = int(
                        (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
                    )
                    if pnl_usd > 5.0:
                        verdict = "WIN"
                    elif pnl_usd < -5.0:
                        verdict = "LOSS"
                    else:
                        verdict = "BREAK_EVEN"

                    trade_id = len(st.trades) + 1
                    trade = Trade(
                        id=trade_id, pair=pair, side=cur.side,
                        entry_price=cur.entry_price, exit_price=price,
                        entry_at=cur.entry_at, exit_at=now_iso,
                        size_usd=cur.size_usd,
                        pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 2),
                        duration_min=duration_min,
                        reason=f"consensus={final_direction}@{final_score:.1f if final_score else 0}",
                        open_signal=cur.open_signal,
                        exit_signal={
                            "final_score":      final_score,
                            "final_direction":  final_direction,
                            "confluence_status": confluence_status,
                            "regime":           sig.get("raw_regime"),
                            "primary_tf":       sig.get("primary_tf"),
                        },
                        verdict=verdict, fingerprint=cur.fingerprint,
                    )
                    st.trades.append(trade)
                    st.realized_pnl_usd += pnl_usd
                    st.last_event = {
                        "type":  "CLOSE", "pair": pair, "side": cur.side,
                        "pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2),
                        "price": price, "verdict": verdict,
                    }
                    st.last_event_at = now_iso
                    del st.positions[pair]
                    cur = None

                    # Karşı yön sinyalinde anında yeni pozisyon aç
                    if target in ("LONG", "SHORT"):
                        new_fp = build_signal_fingerprint(sig)
                        sl, tp = _calc_sl_tp(target, price, pair, atr_val)
                        st.positions[pair] = Position(
                            pair=pair, side=target,
                            entry_price=price, entry_at=now_iso,
                            size_usd=new_size,
                            last_signal=f"{final_direction}@{final_score:.1f}",
                            stop_loss=sl, take_profit=tp,
                            open_signal=sig, fingerprint=new_fp,
                        )
                        st.last_event = {
                            "type": "OPEN", "pair": pair, "side": target,
                            "price": price, "size_usd": new_size,
                            "stop_loss": sl, "take_profit": tp,
                            "learning": learning_meta.get("action", "NORMAL"),
                            "fingerprint": new_fp,
                        }

            # ── Pozisyon yok ──
            else:
                if target in ("LONG", "SHORT"):
                    new_fp = build_signal_fingerprint(sig)
                    sl, tp = _calc_sl_tp(target, price, pair, atr_val)
                    st.positions[pair] = Position(
                        pair=pair, side=target,
                        entry_price=price, entry_at=now_iso,
                        size_usd=new_size,
                        last_signal=f"{final_direction}@{final_score:.1f}",
                        stop_loss=sl, take_profit=tp,
                        open_signal=sig, fingerprint=new_fp,
                    )
                    st.last_event = {
                        "type": "OPEN", "pair": pair, "side": target,
                        "price": price, "size_usd": new_size,
                        "stop_loss": sl, "take_profit": tp,
                        "learning": learning_meta.get("action", "NORMAL"),
                        "fingerprint": new_fp,
                    }
                    st.last_event_at = now_iso

        _save_state(st)
        return st


def _maybe_warn_daily_loss(st: TradingState, now_dt: datetime) -> None:
    """Günlük gerçekleşen zarar DAILY_LOSS_LIMIT_USD'ye ulaşırsa uyar (günde 1 kez)."""
    today = now_dt.date().isoformat()
    if today in _DAILY_LOSS_WARNED_DATES:
        return
    today_pnl = sum(t.pnl_usd for t in st.trades if t.exit_at.startswith(today))
    if today_pnl <= DAILY_LOSS_LIMIT_USD:
        _DAILY_LOSS_WARNED_DATES.add(today)
        _try_emit(
            "daily_loss_limit_warning", "ACTION_REQUIRED",
            "Günlük Zarar Limiti Uyarısı",
            f"Bugün gerçekleşen zarar: ${today_pnl:,.2f}. Uyarı eşiği: ${DAILY_LOSS_LIMIT_USD:,.0f}",
            metadata={"daily_pnl_usd": round(today_pnl, 2), "limit_usd": DAILY_LOSS_LIMIT_USD},
        )


def tick_consensus(
    consensus_signals: dict[str, dict[str, Any]],
    current_prices: dict[str, float],
) -> TradingState:
    """
    Multi-TF consensus skoruna göre pozisyon aç/kapat.

    Yeni açılışlar 60 saniyelik bekleyen onay penceresine girer.
    Kullanıcı reddederse aynı fingerprint tekrar açılmaz; sinyal değişince engel kalkar.
    """
    from app.services.learning_engine import (
        build_signal_fingerprint, should_avoid_or_boost,
    )

    with _LOCK:
        st = _load_state()
        now_dt = _utc_now()
        now_iso = now_dt.isoformat()

        for pair in TRADED_PAIRS:
            sig = consensus_signals.get(pair) or {}
            final_score = sig.get("final_score")
            final_direction = sig.get("final_direction")
            confluence = sig.get("confluence") or {}
            confluence_status = confluence.get("status") if isinstance(confluence, dict) else None

            target, base_mult = _consensus_to_action(final_score, final_direction, confluence_status)
            price = current_prices.get(pair, 0.0)
            if price <= 0:
                continue

            learning_meta: dict[str, Any] = {}
            final_size_mult = base_mult
            signal_fingerprint = ""
            if target in ("LONG", "SHORT"):
                learning_meta = should_avoid_or_boost(sig, st.trades)
                if learning_meta["action"] == "AVOID":
                    target = None
                elif learning_meta["action"] == "BOOST":
                    final_size_mult *= learning_meta["size_multiplier"]
                signal_fingerprint = build_signal_fingerprint(sig)

            if _clear_rejected_signal_if_changed(st, pair, target, signal_fingerprint):
                target = None

            new_size = round(POSITION_SIZE * final_size_mult, 2)
            cur = st.positions.get(pair)
            pending = st.pending_orders.get(pair)

            if pending is not None:
                if cur is not None or target != pending.side or pending.fingerprint != signal_fingerprint:
                    st.pending_orders.pop(pair, None)
                    pending = None
                else:
                    execute_at = datetime.fromisoformat(pending.execute_at)
                    if now_dt >= execute_at:
                        if _is_market_open(pair, now_dt):
                            _open_position_from_pending(st, pending, price, now_iso)
                            cur = st.positions.get(pair)
                        else:
                            _mkt_side = pending.side
                            st.pending_orders.pop(pair, None)
                            _today = now_dt.date().isoformat()
                            if _MARKET_CLOSE_WARNED.get(pair) != _today:
                                _MARKET_CLOSE_WARNED[pair] = _today
                                _try_emit(
                                    "market_closed_trade_blocked", "WARNING",
                                    f"Piyasa Kapalı — {pair}",
                                    f"Bekleyen {_mkt_side} {pair} piyasa kapalı — açılamadı.",
                                    pair=pair, side=_mkt_side,
                                )
                        pending = None

            if cur is not None:
                if target == cur.side:
                    cur.last_signal = f"{final_direction}@{final_score:.1f}" if final_score is not None else "noop"
                    st.pending_orders.pop(pair, None)
                    continue

                should_close = (
                    target in ("LONG", "SHORT") and target != cur.side
                ) or target == "CLOSE"

                if should_close:
                    pnl_usd, pnl_pct = _unrealized_pnl(cur, price)
                    duration_min = int(
                        (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
                    )
                    if pnl_usd > 5.0:
                        verdict = "WIN"
                    elif pnl_usd < -5.0:
                        verdict = "LOSS"
                    else:
                        verdict = "BREAK_EVEN"

                    trade_id = len(st.trades) + 1
                    trade = Trade(
                        id=trade_id,
                        pair=pair,
                        side=cur.side,
                        entry_price=cur.entry_price,
                        exit_price=price,
                        entry_at=cur.entry_at,
                        exit_at=now_iso,
                        size_usd=cur.size_usd,
                        pnl_usd=round(pnl_usd, 2),
                        pnl_pct=round(pnl_pct, 2),
                        duration_min=duration_min,
                        reason=(
                            f"consensus={final_direction}@{final_score:.1f}"
                            if final_score is not None else "consensus=unknown"
                        ),
                        open_signal=cur.open_signal,
                        exit_signal={
                            "final_score": final_score,
                            "final_direction": final_direction,
                            "confluence_status": confluence_status,
                            "regime": sig.get("raw_regime"),
                            "primary_tf": sig.get("primary_tf"),
                        },
                        verdict=verdict,
                        fingerprint=cur.fingerprint,
                    )
                    st.trades.append(trade)
                    st.realized_pnl_usd += pnl_usd
                    st.last_event = {
                        "type": "CLOSE",
                        "pair": pair,
                        "side": cur.side,
                        "pnl_usd": round(pnl_usd, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "price": price,
                        "verdict": verdict,
                    }
                    st.last_event_at = now_iso
                    del st.positions[pair]
                    _try_emit(
                        "paper_trade_closed", "TRADE_EVENT",
                        f"{cur.side} {pair} Kapatıldı",
                        f"Paper pozisyon kapatıldı: {cur.side} {pair} PnL {pnl_usd:+,.2f} USD ({verdict})",
                        pair=pair, side=cur.side, size_usd=cur.size_usd, price=price,
                        reason=(
                            f"consensus={final_direction}@{final_score:.1f}"
                            if final_score is not None else "consensus"
                        ),
                        metadata={"pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2), "verdict": verdict},
                    )

                    if target in ("LONG", "SHORT") and _is_market_open(pair, now_dt):
                        _queue_pending_open(
                            st=st,
                            pair=pair,
                            side=target,
                            price=price,
                            size_usd=new_size,
                            last_signal=f"{final_direction}@{final_score:.1f}" if final_score is not None else "pending",
                            signal_snapshot=sig,
                            fingerprint=signal_fingerprint,
                            now_dt=now_dt,
                        )
                    else:
                        st.pending_orders.pop(pair, None)
                continue

            if target in ("LONG", "SHORT") and pending is None and _is_market_open(pair, now_dt):
                _queue_pending_open(
                    st=st,
                    pair=pair,
                    side=target,
                    price=price,
                    size_usd=new_size,
                    last_signal=f"{final_direction}@{final_score:.1f}" if final_score is not None else "pending",
                    signal_snapshot=sig,
                    fingerprint=signal_fingerprint,
                    now_dt=now_dt,
                )
            elif target in ("LONG", "SHORT") and pending is None and pair in MARKET_HOURS_GATED_PAIRS:
                _today = now_dt.date().isoformat()
                if _MARKET_CLOSE_WARNED.get(pair) != _today:
                    _MARKET_CLOSE_WARNED[pair] = _today
                    _try_emit(
                        "market_closed_trade_blocked", "WARNING",
                        f"Piyasa Kapalı — {pair}",
                        f"{target} {pair} sinyali var ancak piyasa hafta sonu kapalı.",
                        pair=pair, side=target,
                    )

        _maybe_warn_daily_loss(st, now_dt)
        # ── Read-only GET için tick snapshot'ı kaydet ──
        st.last_tick_prices = dict(current_prices)
        st.last_tick_at = now_iso
        st.last_tick_signals = consensus_signals
        _save_state(st)
        return st


def tick(
    agent_signals: dict[str, dict[str, Any]],
    current_prices: dict[str, float],
) -> TradingState:
    """
    Tek tick:
      1. Her parite için son sinyali oku (LONG/SHORT/AVOID/...).
      2. Mevcut pozisyon varsa: yön değişimi/kapatma sinyali geldi mi?
      3. Pozisyon yoksa: LONG/SHORT geldi mi → aç.
      4. State'i diske kaydet, son event'i set et.

    agent_signals:  {"BTCUSD": {"asset_action": "LONG", "value": 60000, ...}, ...}
    current_prices: {"BTCUSD": 60055.5, ...}
    """
    with _LOCK:
        st = _load_state()
        now_iso = datetime.now(UTC).isoformat()

        for pair in TRADED_PAIRS:
            sig = agent_signals.get(pair) or {}
            action = sig.get("asset_action") or "NEUTRAL"
            target = _action_to_side(action)
            price = current_prices.get(pair, 0.0)
            if price <= 0:
                continue

            cur = st.positions.get(pair)

            # ── Pozisyon var ──
            if cur is not None:
                # Aynı yönde sinyal devam ediyorsa dokunma
                if target == cur.side:
                    cur.last_signal = action
                    continue

                # Karşı yön veya CLOSE sinyali → kapat
                should_close = (
                    target in ("LONG", "SHORT") and target != cur.side
                ) or target == "CLOSE"

                if should_close:
                    pnl_usd, pnl_pct = _unrealized_pnl(cur, price)
                    duration_min = int(
                        (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
                    )
                    trade_id = len(st.trades) + 1
                    trade = Trade(
                        id=trade_id,
                        pair=pair,
                        side=cur.side,
                        entry_price=cur.entry_price,
                        exit_price=price,
                        entry_at=cur.entry_at,
                        exit_at=now_iso,
                        size_usd=cur.size_usd,
                        pnl_usd=round(pnl_usd, 2),
                        pnl_pct=round(pnl_pct, 2),
                        duration_min=duration_min,
                        reason=f"signal={action}",
                    )
                    st.trades.append(trade)
                    st.realized_pnl_usd += pnl_usd
                    st.last_event = {
                        "type":   "CLOSE",
                        "pair":   pair,
                        "side":   cur.side,
                        "pnl_usd": round(pnl_usd, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "price":   price,
                    }
                    st.last_event_at = now_iso
                    del st.positions[pair]
                    cur = None  # akış için sıfırla

                    # Karşı yönde sinyal varsa hemen aç (önce kapat, sonra aç)
                    if target in ("LONG", "SHORT"):
                        st.positions[pair] = Position(
                            pair=pair, side=target,
                            entry_price=price, entry_at=now_iso,
                            size_usd=POSITION_SIZE, last_signal=action,
                        )
                        st.last_event = {
                            "type":  "OPEN",
                            "pair":  pair,
                            "side":  target,
                            "price": price,
                            "size_usd": POSITION_SIZE,
                        }

            # ── Pozisyon yok ──
            else:
                if target in ("LONG", "SHORT"):
                    st.positions[pair] = Position(
                        pair=pair, side=target,
                        entry_price=price, entry_at=now_iso,
                        size_usd=POSITION_SIZE, last_signal=action,
                    )
                    st.last_event = {
                        "type":  "OPEN",
                        "pair":  pair,
                        "side":  target,
                        "price": price,
                        "size_usd": POSITION_SIZE,
                    }
                    st.last_event_at = now_iso

        _save_state(st)
        return st


# ── Public read API ────────────────────────────────────────────────────────────

def reject_pending_open(pair: str) -> bool:
    with _LOCK:
        st = _load_state()
        pending = st.pending_orders.pop(pair, None)
        if pending is None:
            return False

        st.rejected_signals[pair] = RejectedOpenSignal(
            pair=pair,
            side=pending.side,
            fingerprint=pending.fingerprint,
            rejected_at=_utc_now().isoformat(),
        )
        _save_state(st)
        pending_side = pending.side

    _try_emit(
        "pending_trade_rejected", "INFO",
        f"{pending_side} {pair} Reddedildi",
        f"Bekleyen {pending_side} {pair} işlemi kullanıcı tarafından reddedildi.",
        pair=pair, side=pending_side,
    )
    return True


def get_snapshot(current_prices: dict[str, float] | None = None) -> dict[str, Any]:
    """Frontend için tek seferlik durum görüntüsü.

    current_prices boş veya None ise state'in last_tick_prices'ından düşülür —
    böylece GET tick yapmadan da geçerli unrealized PnL döner.
    """
    st = _load_state()
    if not current_prices:
        current_prices = dict(st.last_tick_prices)

    # Açık pozisyonların unrealized PnL'i + her birinin fingerprint geçmişi
    open_positions = []
    unrealized_total = 0.0
    from app.services.learning_engine import win_rate_for_fingerprint
    for p in st.positions.values():
        cur_price = current_prices.get(p.pair, p.entry_price)
        pnl_usd, pnl_pct = _unrealized_pnl(p, cur_price)
        unrealized_total += pnl_usd
        # ── Bu pozisyonun fingerprint'inin geçmişi
        fp_history = win_rate_for_fingerprint(p.fingerprint, st.trades) if p.fingerprint else None
        open_positions.append({
            **asdict(p),
            "current_price": cur_price,
            "pnl_usd":  round(pnl_usd, 2),
            "pnl_pct":  round(pnl_pct, 2),
            "fingerprint_history": fp_history,
        })

    equity = st.starting_balance + st.realized_pnl_usd + unrealized_total

    # Günlük PnL — bugün kapatılan trade'lerin sum'ı + bugün açılmış pozisyonların unreal'i
    now_dt = _utc_now()
    today = now_dt.date().isoformat()
    today_realized = sum(
        t.pnl_usd for t in st.trades if t.exit_at.startswith(today)
    )
    today_unreal = sum(
        _unrealized_pnl(p, current_prices.get(p.pair, p.entry_price))[0]
        for p in st.positions.values()
        if p.entry_at.startswith(today)
    )
    daily_pnl = today_realized + today_unreal
    pending_orders = []
    for pending in st.pending_orders.values():
        execute_at = datetime.fromisoformat(pending.execute_at)
        pending_orders.append({
            **asdict(pending),
            "seconds_remaining": max(0, int((execute_at - now_dt).total_seconds())),
            "market_open": _is_market_open(pending.pair, now_dt),
        })
    pending_orders.sort(key=lambda item: (item["execute_at"], item["pair"]))

    # Stale ölçümü — son tick'ten bu yana kaç saniye geçti?
    tick_age_s: float | None = None
    if st.last_tick_at:
        try:
            tick_age_s = (now_dt - datetime.fromisoformat(st.last_tick_at)).total_seconds()
        except Exception:
            tick_age_s = None

    return {
        "starting_balance": st.starting_balance,
        "realized_pnl_usd": round(st.realized_pnl_usd, 2),
        "unrealized_pnl_usd": round(unrealized_total, 2),
        "equity":           round(equity, 2),
        "daily_pnl_usd":    round(daily_pnl, 2),
        "open_positions":   open_positions,
        "pending_orders":   pending_orders,
        "trades":           [asdict(t) for t in st.trades[-20:]],  # son 20 trade
        "trade_count":      len(st.trades),
        "last_event":       st.last_event,
        "last_event_at":    st.last_event_at,
        "last_tick_at":     st.last_tick_at,
        "tick_age_seconds": round(tick_age_s, 1) if tick_age_s is not None else None,
        "traded_pairs":     list(TRADED_PAIRS),
    }


def reset_state() -> None:
    """Tüm trading state'i sıfırla — sadece debug için."""
    with _LOCK:
        _save_state(TradingState())


def force_close_position(pair: str, current_price: float, reason: str = "MANUEL") -> dict[str, Any]:
    """Kullanıcı talebiyle pozisyonu anlık fiyattan kapat (Manuel Kapat). PAPER_SAFE."""
    with _LOCK:
        st = _load_state()
        cur = st.positions.get(pair)
        if cur is None:
            return {"status": "no_position", "pair": pair}

        now_iso = datetime.now(UTC).isoformat()
        pnl_usd, pnl_pct = _unrealized_pnl(cur, current_price)
        duration_min = int(
            (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
        )
        if pnl_usd > 5.0:
            verdict = "WIN"
        elif pnl_usd < -5.0:
            verdict = "LOSS"
        else:
            verdict = "BREAK_EVEN"

        trade_id = len(st.trades) + 1
        st.trades.append(Trade(
            id=trade_id, pair=pair, side=cur.side,
            entry_price=cur.entry_price, exit_price=current_price,
            entry_at=cur.entry_at, exit_at=now_iso,
            size_usd=cur.size_usd,
            pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 2),
            duration_min=duration_min,
            reason=reason,
            open_signal=cur.open_signal,
            exit_signal={"trigger": reason, "price": current_price},
            verdict=verdict, fingerprint=cur.fingerprint,
        ))
        st.realized_pnl_usd += pnl_usd
        st.last_event = {
            "type": "CLOSE", "pair": pair, "side": cur.side,
            "pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2),
            "price": current_price, "verdict": verdict, "reason": reason,
        }
        st.last_event_at = now_iso
        _closed_side = cur.side
        _closed_size = cur.size_usd
        del st.positions[pair]
        _save_state(st)

    _try_emit(
        "paper_trade_closed", "TRADE_EVENT",
        f"{_closed_side} {pair} Manuel Kapatıldı",
        f"Manuel kapatma: {_closed_side} {pair} PnL {pnl_usd:+,.2f} USD ({verdict})",
        pair=pair, side=_closed_side, size_usd=_closed_size, price=current_price,
        reason=reason,
        metadata={"pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2), "verdict": verdict},
    )
    return {
        "status": "closed",
        "pair": pair, "side": _closed_side,
        "entry_price": cur.entry_price, "exit_price": current_price,
        "pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2),
        "verdict": verdict, "reason": reason,
    }


__all__ = [
    "tick", "tick_consensus", "get_snapshot", "reject_pending_open", "reset_state",
    "force_close_position",
    "OPEN_CONFIRMATION_WINDOW_SECONDS", "_is_market_open",
    "TRADED_PAIRS", "STARTING_BALANCE", "POSITION_SIZE",
]
