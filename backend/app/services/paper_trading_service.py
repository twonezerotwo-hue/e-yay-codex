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
from dataclasses import asdict, dataclass, field, fields
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
    """ATR varsa per-asset profilden gelen X×ATR SL / Y×ATR TP, yoksa sabit yüzde.

    Per-asset profile (asset_parameter_profile.ASSET_PROFILES):
      - BTCUSD: SL=1.5×ATR, TP=2.5×ATR (yüksek vol için sıkı)
      - XAU/XCU/BRENT: SL=2.5×ATR, TP=3.0..3.5×ATR (gap riski)
      - default: SL=2.0×ATR, TP=3.0×ATR (eski davranış)
    """
    from app.services.asset_parameter_profile import get_param
    sl_mult = float(get_param(pair, "sl_atr_mult", 2.0) or 2.0)
    tp_mult = float(get_param(pair, "tp_atr_mult", 3.0) or 3.0)

    sl_pct = _SL_PCT.get(pair, 0.04)
    if atr and atr > 0:
        risk   = sl_mult * atr
        reward = tp_mult * atr
    else:
        risk   = entry * sl_pct
        reward = entry * sl_pct * _TP_MULT
    if side == "LONG":
        return round(entry - risk, 4), round(entry + reward, 4)
    else:
        return round(entry + risk, 4), round(entry - reward, 4)


def _build_risk_plan(
    side: PositionSide,
    entry: float,
    pair: str,
    atr: float | None,
    *,
    sl: float,
    tp: float,
) -> dict[str, Any]:
    """SL/TP arkasındaki hikayeyi insan okunaklı yap.

    timeframe    : technical_provider 1D (daily) kullanır
    atr_period   : Wilder ATR(14) → 14 günlük ortalama gerçek aralık
    sl_basis     : "ATR×N · 1D" veya "%X (atr fallback)" — per-asset profile
    horizon_hours: beklenen ortalama tutuş süresi — per-asset profile
    """
    from app.services.asset_parameter_profile import get_param
    sl_mult = float(get_param(pair, "sl_atr_mult", 2.0) or 2.0)
    tp_mult = float(get_param(pair, "tp_atr_mult", 3.0) or 3.0)
    hh_low  = int(get_param(pair, "horizon_hours_low",  48) or 48)
    hh_high = int(get_param(pair, "horizon_hours_high", 144) or 144)

    if atr and atr > 0:
        sl_basis = f"{sl_mult:g}×ATR(14) · 1D"
        tp_basis = f"{tp_mult:g}×ATR(14) · 1D"
        rr = round(tp_mult / sl_mult, 2) if sl_mult > 0 else 1.5
        horizon_hours_low  = hh_low
        horizon_hours_high = hh_high
    else:
        pct = _SL_PCT.get(pair, 0.04) * 100
        sl_basis = f"sabit %{pct:.1f} (1D ATR yok)"
        tp_basis = f"sabit %{pct * _TP_MULT:.1f} (RR 2:1)"
        rr = _TP_MULT
        horizon_hours_low  = max(hh_low + 24, 72)
        horizon_hours_high = max(hh_high + 24, 168)

    sl_pct = round(abs(sl - entry) / entry * 100, 2) if entry else None
    tp_pct = round(abs(tp - entry) / entry * 100, 2) if entry else None

    return {
        "timeframe":         "1D",
        "atr_period_bars":   14,
        "atr_value":         (round(atr, 6) if atr else None),
        "sl_basis":          sl_basis,
        "tp_basis":          tp_basis,
        "risk_reward":       rr,
        "stop_loss_pct":     sl_pct,
        "take_profit_pct":   tp_pct,
        "expected_horizon_hours": {
            "low":  horizon_hours_low,
            "high": horizon_hours_high,
        },
        "asset_profile":     pair,
        "explanation": (
            f"SL ve TP, günlük (1D) mumlar üzerinde Wilder ATR(14) ile hesaplandı. "
            f"SL={sl_mult:g}×ATR, TP={tp_mult:g}×ATR (RR {rr}). "
            f"Beklenen tutuş: ~{horizon_hours_low}-{horizon_hours_high} saat. "
            f"(Profil: {pair})"
            if atr else
            f"ATR verisi yok — sabit %{pct:.1f} SL ve RR {_TP_MULT}:1 kullanıldı. "
            f"Beklenen tutuş: ~{horizon_hours_low}-{horizon_hours_high} saat."
        ),
    }


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
    # ── SL/TP arkasındaki hikaye (timeframe + ATR + beklenen horizon) ──
    risk_plan:   dict[str, Any] = field(default_factory=dict)


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
    # ATR — sonradan pozisyon açılırken risk_plan hesaplaması için
    atr_value: float = 0.0
    # Yinelenen-sinyal tespiti için: bu pending hangi TF'den geldi
    primary_tf: str = ""
    # Yinelenen-sinyal mi (farklı TF/side ile gelen tekrar) — UI gösterimi için
    is_recurring: bool = False


@dataclass
class RejectedOpenSignal:
    pair: str
    side: PositionSide
    fingerprint: str
    rejected_at: str
    # Aynı fingerprint farklı TF'den gelirse "yinelenen sinyal" olarak yeniden sor
    primary_tf: str = ""


@dataclass
class ManualReadyTrade:
    """Kullanıcı 60sn pending'i reddettikten sonra el ile açılabilen işlem.

    `manual_ready_trades[pair]` dict'inde tutulur; banner'da "Açılmaya Hazır
    İşlemler" bölümünde görünür. Kullanıcı `Aç` derse anlık fiyattan açılır,
    `Sil` derse listeden düşer. Yeni bir TF'den sinyal gelirse otomatik
    silinmez — ek olarak 60sn pending banner'ı gönderilir (yinelenen sinyal).

    Fiyat alanları:
      • original_requested_price — reddedildiği anki donmuş fiyat (referans)
      • requested_price — son tick'te güncellenen taze fiyat (silent block
        her tickte refresh eder); 'Aç' butonu bu fiyattan değil, anlık
        last_tick_prices'tan açar
      • open_signal / atr_value — silent block'ta her tick refresh edilir
        ki SL/TP hesabı taze olsun
    """
    pair: str
    side: PositionSide
    requested_at: str          # ilk reddedildiği zaman
    rejected_at: str           # reddedildiği iso ts
    last_signal: str
    size_usd: float
    requested_price: float
    open_signal: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    atr_value: float = 0.0
    primary_tf: str = ""
    original_requested_price: float = 0.0   # ilk önerildiğindeki fiyat (donmuş)
    last_refreshed_at: str = ""             # son güncelleme ts


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
    # ── SL/TP arkasındaki hikaye — kapanmış trade için audit ──
    risk_plan:    dict[str, Any] = field(default_factory=dict)


@dataclass
class TradingState:
    starting_balance: float = STARTING_BALANCE
    realized_pnl_usd: float = 0.0
    positions:        dict[str, Position]   = field(default_factory=dict)
    pending_orders:   dict[str, PendingOpenOrder] = field(default_factory=dict)
    rejected_signals: dict[str, RejectedOpenSignal] = field(default_factory=dict)
    manual_ready_trades: dict[str, "ManualReadyTrade"] = field(default_factory=dict)
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
            v.setdefault("risk_plan", {})
            # Bilinmeyen alanları sessizce at (eski/yeni schema farkına dayanıklı)
            valid = {f.name for f in fields(Position)}
            v = {kk: vv for kk, vv in v.items() if kk in valid}
            positions[k] = Position(**v)

        pending_orders = {}
        for k, v in raw.get("pending_orders", {}).items():
            v.setdefault("open_signal", {})
            v.setdefault("fingerprint", "")
            v.setdefault("atr_value", 0.0)
            v.setdefault("primary_tf", "")
            v.setdefault("is_recurring", False)
            valid = {f.name for f in fields(PendingOpenOrder)}
            v = {kk: vv for kk, vv in v.items() if kk in valid}
            pending_orders[k] = PendingOpenOrder(**v)

        rejected_signals = {}
        for k, v in raw.get("rejected_signals", {}).items():
            v.setdefault("primary_tf", "")
            valid = {f.name for f in fields(RejectedOpenSignal)}
            v = {kk: vv for kk, vv in v.items() if kk in valid}
            rejected_signals[k] = RejectedOpenSignal(**v)

        manual_ready_trades = {}
        for k, v in raw.get("manual_ready_trades", {}).items():
            v.setdefault("open_signal", {})
            v.setdefault("fingerprint", "")
            v.setdefault("atr_value", 0.0)
            v.setdefault("primary_tf", "")
            v.setdefault("original_requested_price", v.get("requested_price", 0.0))
            v.setdefault("last_refreshed_at", v.get("rejected_at", ""))
            valid = {f.name for f in fields(ManualReadyTrade)}
            v = {kk: vv for kk, vv in v.items() if kk in valid}
            manual_ready_trades[k] = ManualReadyTrade(**v)

        # Trade — eski format
        trades = []
        valid_trade = {f.name for f in fields(Trade)}
        for t in raw.get("trades", []):
            t.setdefault("open_signal", {})
            t.setdefault("exit_signal", {})
            t.setdefault("verdict", "")
            t.setdefault("fingerprint", "")
            t.setdefault("risk_plan", {})
            t2 = {kk: vv for kk, vv in t.items() if kk in valid_trade}
            trades.append(Trade(**t2))

        st = TradingState(
            starting_balance=raw.get("starting_balance", STARTING_BALANCE),
            realized_pnl_usd=raw.get("realized_pnl_usd", 0.0),
            positions=positions,
            pending_orders=pending_orders,
            rejected_signals=rejected_signals,
            manual_ready_trades=manual_ready_trades,
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


# Signal attribution — _save_state'da yeni kapanmış trade'leri otomatik kaydet.
# Her _save_state'da set'e bakar, yeni trade.id varsa signal_attribution_service'e gönderir.
# Tüm close path'lere ayrı kanca eklemekten kaçınmak için tek noktada toparlandı.
_ATTRIBUTION_SEEN_IDS: set[int] = set()


def _emit_attributions(st: TradingState) -> None:
    """st.trades'i tara, henüz attribution kaydedilmemiş olanları gönder."""
    try:
        from app.services import signal_attribution_service as sas  # lazy import → circular önle
    except Exception:
        return
    for t in st.trades:
        tid = getattr(t, "id", None)
        if not isinstance(tid, int) or tid in _ATTRIBUTION_SEEN_IDS:
            continue
        try:
            sas.record_trade(t)
        except Exception:
            # Attribution best-effort — paper trading akışını bozmaz
            pass
        finally:
            _ATTRIBUTION_SEEN_IDS.add(tid)


def _save_state(st: TradingState) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "starting_balance": st.starting_balance,
        "realized_pnl_usd": st.realized_pnl_usd,
        "positions": {k: asdict(v) for k, v in st.positions.items()},
        "pending_orders": {k: asdict(v) for k, v in st.pending_orders.items()},
        "rejected_signals": {k: asdict(v) for k, v in st.rejected_signals.items()},
        "manual_ready_trades": {k: asdict(v) for k, v in st.manual_ready_trades.items()},
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
    # Atomic write — kısmen yazılmış dosyayı önler (crash/Ctrl-C safe)
    tmp_path = _STATE_PATH.with_suffix(_STATE_PATH.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(_STATE_PATH)
    # Persist sonrası yeni trade'ler için attribution emit (best-effort, hata yutulur)
    _emit_attributions(st)


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


def _should_silent_block(
    st: TradingState,
    pair: str,
    target: PositionSide | Literal["CLOSE"] | None,
    primary_tf: str,
) -> bool:
    """Bu sinyali sessizce engelle (banner gönderme, pending açma).

    True dönerse: aynı (pair, side, primary_tf) ya zaten reddedilmiş ya da
    'manual_ready' kuyruğunda bekliyor. Fingerprint'in skor/modül oynamasıyla
    değişmesi BLOCK'u kaldırmaz — kullanıcı aynı sinyalden tekrar rahatsız
    edilmez.
    """
    if target not in ("LONG", "SHORT"):
        return False

    def _tf_match(a: str, b: str) -> bool:
        return (not a) or (not b) or (a == b)

    rejected = st.rejected_signals.get(pair)
    if (
        rejected is not None
        and rejected.side == target
        and _tf_match(rejected.primary_tf, primary_tf)
    ):
        return True

    mr = st.manual_ready_trades.get(pair)
    if (
        mr is not None
        and mr.side == target
        and _tf_match(mr.primary_tf, primary_tf)
    ):
        return True

    return False


def _purge_stale_rejection_if_needed(
    st: TradingState,
    pair: str,
    target: PositionSide | Literal["CLOSE"] | None,
    primary_tf: str,
) -> None:
    """Sinyal artık alakasız (yön / TF değişti veya target=None) ve aynı pair
    için 'manual_ready' yoksa eski rejection'ı temizle ki gelecekteki sinyal
    serbestçe karar verebilsin.

    Manual_ready varken rejection KORUNUR — silent block çiftler arası tutarlı
    olsun. Kullanıcı 'Aç' veya 'Sil' diyene kadar block aktif kalır.
    """
    rejected = st.rejected_signals.get(pair)
    if rejected is None:
        return
    # Manual ready aynı pair için duruyorsa rejection'ı koru.
    if pair in st.manual_ready_trades:
        return
    # Aynı side+TF ile hâlâ alakalıysa koru — silent block sürmeli.
    if (
        target in ("LONG", "SHORT")
        and rejected.side == target
        and (not rejected.primary_tf or not primary_tf or rejected.primary_tf == primary_tf)
    ):
        return
    # Yön/TF değişti veya sinyal kayboldu → eski rejection alakasız, temizle.
    del st.rejected_signals[pair]


def _is_recurring_signal(
    st: TradingState,
    pair: str,
    target: PositionSide | Literal["CLOSE"] | None,
    primary_tf: str,
) -> bool:
    """Pair'in 'manual_ready' bekleyişi varken farklı TF veya yönden yeni
    sinyal gelirse 'yinelenen sinyal' sayılır → 60sn pending tekrar gönderilir.
    """
    if target not in ("LONG", "SHORT"):
        return False
    mr = st.manual_ready_trades.get(pair)
    if mr is None:
        return False
    return (mr.side != target) or (bool(primary_tf) and mr.primary_tf != primary_tf)


def _refresh_manual_ready_with_live_signal(
    st: TradingState,
    pair: str,
    *,
    price: float,
    signal_snapshot: dict[str, Any],
    atr_value: float,
    last_signal: str,
) -> None:
    """Silent-block her tick'inde manual_ready[pair] entry'sini taze fiyat,
    sinyal snapshot'ı ve ATR ile günceller. original_requested_price korunur
    (kullanıcı reddettiği fiyat değişmez).

    Kullanıcı 'Aç' deyince:
      - requested_price (güncel) UI'da görünür
      - open_signal + atr_value taze → SL/TP fresh ATR'den hesaplanır
      - Asıl açılış yine state.last_tick_prices'tan yapılır
        (force_open_manual_ready içinde)
    """
    mr = st.manual_ready_trades.get(pair)
    if mr is None or price <= 0:
        return
    mr.requested_price   = price
    mr.atr_value         = atr_value if atr_value > 0 else mr.atr_value
    mr.open_signal       = signal_snapshot or mr.open_signal
    mr.last_signal       = last_signal or mr.last_signal
    mr.last_refreshed_at = _utc_now().isoformat()


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
    atr_value: float = 0.0,
    primary_tf: str = "",
    is_recurring: bool = False,
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
        atr_value=atr_value,
        primary_tf=primary_tf,
        is_recurring=is_recurring,
    )
    if is_recurring:
        _try_emit(
            "recurring_signal_pending", "ACTION_REQUIRED",
            f"Yinelenen sinyal: {side} {pair} (TF: {primary_tf or 'n/a'})",
            f"{pair} için açılmaya hazır işlem dururken farklı TF/yönden yeni sinyal geldi. "
            f"{OPEN_CONFIRMATION_WINDOW_SECONDS}s içinde reddedilmezse otomatik açılır.",
            pair=pair, side=side, size_usd=size_usd, price=price,
            metadata={"execute_at": execute_at, "primary_tf": primary_tf, "recurring": True},
        )
    else:
        _try_emit(
            "pending_trade_created", "ACTION_REQUIRED",
            f"{side} {pair} Bekleyen İşlem",
            f"{OPEN_CONFIRMATION_WINDOW_SECONDS}s içinde {side} {pair} açılacak — reddedilmezse otomatik açılır.",
            pair=pair, side=side, size_usd=size_usd, price=price,
            metadata={"execute_at": execute_at, "primary_tf": primary_tf},
        )


def _open_position_from_pending(
    st: TradingState,
    pending: PendingOpenOrder,
    current_price: float,
    opened_at: str,
) -> None:
    atr_val = pending.atr_value if pending.atr_value > 0 else None
    sl, tp = _calc_sl_tp(pending.side, current_price, pending.pair, atr_val)
    risk_plan = _build_risk_plan(pending.side, current_price, pending.pair, atr_val, sl=sl, tp=tp)
    st.positions[pending.pair] = Position(
        pair=pending.pair,
        side=pending.side,
        entry_price=current_price,
        entry_at=opened_at,
        size_usd=pending.size_usd,
        last_signal=pending.last_signal,
        open_signal=pending.open_signal,
        fingerprint=pending.fingerprint,
        stop_loss=sl,
        take_profit=tp,
        risk_plan=risk_plan,
    )
    st.last_event = {
        "type": "OPEN",
        "pair": pending.pair,
        "side": pending.side,
        "price": current_price,
        "size_usd": pending.size_usd,
        "stop_loss": sl,
        "take_profit": tp,
        "fingerprint": pending.fingerprint,
    }
    st.last_event_at = opened_at
    st.pending_orders.pop(pending.pair, None)
    # Otomatik açıldı: hem manual_ready hem rejection alakasız → temizle.
    st.manual_ready_trades.pop(pending.pair, None)
    st.rejected_signals.pop(pending.pair, None)
    _try_emit(
        "paper_trade_opened", "TRADE_EVENT",
        f"{pending.side} {pending.pair} Açıldı",
        (
            f"Paper pozisyon açıldı: {pending.side} {pending.pair} @ ${current_price:,.2f}\n"
            f"SL: ${sl:,.4f} ({risk_plan.get('stop_loss_pct')}% ) · "
            f"TP: ${tp:,.4f} ({risk_plan.get('take_profit_pct')}% ) · "
            f"TF: {risk_plan.get('timeframe')} · "
            f"Horizon: {risk_plan.get('expected_horizon_hours', {}).get('low')}-"
            f"{risk_plan.get('expected_horizon_hours', {}).get('high')}h"
        ),
        pair=pending.pair, side=pending.side,
        size_usd=pending.size_usd, price=current_price,
        metadata={"risk_plan": risk_plan, "stop_loss": sl, "take_profit": tp},
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
                        risk_plan=cur.risk_plan or {},
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
                        risk_plan = _build_risk_plan(target, price, pair, atr_val, sl=sl, tp=tp)
                        st.positions[pair] = Position(
                            pair=pair, side=target,
                            entry_price=price, entry_at=now_iso,
                            size_usd=new_size,
                            last_signal=f"{final_direction}@{final_score:.1f}",
                            stop_loss=sl, take_profit=tp,
                            open_signal=sig, fingerprint=new_fp,
                            risk_plan=risk_plan,
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
    *,
    dqs_score: int | None = None,
    kill_switch: bool = False,
    trigger_engine: dict[str, Any] | None = None,
) -> TradingState:
    """
    Multi-TF consensus skoruna göre pozisyon aç/kapat.

    Yeni açılışlar 60 saniyelik bekleyen onay penceresine girer.
    Kullanıcı reddederse aynı fingerprint tekrar açılmaz; sinyal değişince engel kalkar.

    Ek parametreler (opsiyonel):
      dqs_score     — Veri kalite skoru (0-100). < MIN_DQS → KILL_SWITCH.
      kill_switch   — Risk engine kill aktifse True → tüm yeni tradeler bloke.
      trigger_engine— Trigger engine çıktısı → ilerleyen sprintte auto_close için.
    """
    from app.services.learning_engine import (
        build_signal_fingerprint, should_avoid_or_boost,
    )
    from app.services.agent_decision_aggregator import aggregate_agent_decision

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
            atr_val_pending = float(sig.get("atr") or 0.0)
            current_primary_tf = str(sig.get("primary_tf") or "")

            # Ham aksiyon — mevcut skor eşiği + confluence mantığı korunuyor
            raw_target, raw_base_mult = _consensus_to_action(
                final_score, final_direction, confluence_status,
            )

            # Çok katmanlı agent kararı:
            #   multi-TF uyum + rejim sizing + DQS gate + trigger auto-close
            decision = aggregate_agent_decision(
                sig, pair,
                base_mult_from_score=raw_base_mult,
                dqs_score=dqs_score,
                kill_switch=kill_switch,
                trigger_engine=trigger_engine,
            )
            # Aggregator blokladıysa side=None, bloklamamışsa ham yönü onaylar
            target = decision.side if decision.side is not None else (
                raw_target if not decision.block_reason else None
            )
            base_mult = decision.size_pct if decision.size_pct > 0.0 else raw_base_mult

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

            # Yinelenen sinyal kontrolü — manual_ready varken farklı TF/side
            # → silent block'u bypass et, yeni 60sn pending'i 'recurring' bayrağıyla kur.
            is_recurring_signal = _is_recurring_signal(st, pair, target, current_primary_tf)

            # Aynı (pair, side, primary_tf) zaten reddedilmiş ya da manual_ready'de
            # → SESSIZ block. Fingerprint kayması (skor/modül oynaması) block'u
            # kaldırmaz. Banner gönderilmez, pending açılmaz.
            if not is_recurring_signal and _should_silent_block(
                st, pair, target, current_primary_tf,
            ):
                # Silent block: yeni pending açma. AMA manual_ready entry'sini
                # taze fiyat + ATR + sinyal ile revize et — kullanıcı "Aç"
                # deyince güncel piyasa fiyatından + taze SL/TP açılsın.
                _refresh_manual_ready_with_live_signal(
                    st, pair,
                    price=price,
                    signal_snapshot=sig,
                    atr_value=atr_val_pending,
                    last_signal=(f"{final_direction}@{final_score:.1f}"
                                 if final_score is not None else "pending"),
                )
                target = None
            else:
                # Rejection eskimiş olabilir (yön/TF tamamen değişti) → temizle.
                _purge_stale_rejection_if_needed(st, pair, target, current_primary_tf)

            new_size = round(POSITION_SIZE * final_size_mult, 2)
            cur = st.positions.get(pair)
            pending = st.pending_orders.get(pair)

            # ── Trigger auto-close (acil kapatma) ────────────────────────────
            # Kritik piyasa olayında (RED trigger) açık pozisyon hemen kapat;
            # yeni trade açılmaz. trigger_engine None ise hiç tetiklenmez.
            if decision.auto_close and cur is not None:
                pnl_usd, pnl_pct = _unrealized_pnl(cur, price)
                verdict = "WIN" if pnl_usd > 5.0 else ("LOSS" if pnl_usd < -5.0 else "BREAK_EVEN")
                duration_min = int(
                    (now_dt - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
                )
                trade = Trade(
                    id=len(st.trades) + 1,
                    pair=pair, side=cur.side,
                    entry_price=cur.entry_price, exit_price=price,
                    entry_at=cur.entry_at, exit_at=now_iso,
                    size_usd=cur.size_usd,
                    pnl_usd=round(pnl_usd, 2),
                    pnl_pct=round(pnl_pct, 2),
                    duration_min=duration_min,
                    reason=f"AUTO_CLOSE: {decision.auto_close_reason}",
                    open_signal=cur.open_signal, exit_signal={},
                    verdict=verdict, fingerprint=cur.fingerprint,
                    risk_plan=cur.risk_plan or {},
                )
                st.trades.append(trade)
                st.realized_pnl_usd += pnl_usd
                del st.positions[pair]
                st.pending_orders.pop(pair, None)
                _try_emit(
                    "auto_close_critical_trigger", "CRITICAL",
                    f"ACİL KAPATMA — {pair}",
                    f"{cur.side} {pair} kritik tetikleyici nedeniyle kapatıldı. "
                    f"PnL {pnl_usd:+,.2f} USD · {decision.auto_close_reason}",
                    pair=pair, side=cur.side, size_usd=cur.size_usd, price=price,
                    metadata={"pnl_usd": round(pnl_usd, 2), "verdict": verdict,
                               "trigger": decision.auto_close_reason},
                )
                continue

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
                        risk_plan=cur.risk_plan or {},
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
                            atr_value=atr_val_pending,
                            primary_tf=current_primary_tf,
                            is_recurring=is_recurring_signal,
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
                    atr_value=atr_val_pending,
                    primary_tf=current_primary_tf,
                    is_recurring=is_recurring_signal,
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
    """Pending'i reddet: silent block (rejected_signals) + manuel açılabilir kuyruğa al.

    Aynı (side, fingerprint, primary_tf) sinyali bir daha sormayız.
    Manuel açılabilir işlem `manual_ready_trades` içinde durur — kullanıcı isterse
    `force_open_manual_ready` ile el ile açar, `dismiss_manual_ready` ile siler.
    """
    with _LOCK:
        st = _load_state()
        pending = st.pending_orders.pop(pair, None)
        if pending is None:
            return False

        rejected_at = _utc_now().isoformat()
        st.rejected_signals[pair] = RejectedOpenSignal(
            pair=pair,
            side=pending.side,
            fingerprint=pending.fingerprint,
            rejected_at=rejected_at,
            primary_tf=pending.primary_tf,
        )
        # Manuel açılabilir olarak hazırda tut. original_requested_price
        # reddedildiği fiyatı dondurur (referans); requested_price ileride
        # silent_block tarafından her tick taze fiyata revize edilir.
        st.manual_ready_trades[pair] = ManualReadyTrade(
            pair=pair,
            side=pending.side,
            requested_at=pending.requested_at,
            rejected_at=rejected_at,
            last_signal=pending.last_signal,
            size_usd=pending.size_usd,
            requested_price=pending.requested_price,
            open_signal=pending.open_signal,
            fingerprint=pending.fingerprint,
            atr_value=pending.atr_value,
            primary_tf=pending.primary_tf,
            original_requested_price=pending.requested_price,
            last_refreshed_at=rejected_at,
        )
        _save_state(st)
        pending_side = pending.side

    _try_emit(
        "pending_trade_rejected", "INFO",
        f"{pending_side} {pair} Reddedildi · Manuel hazırda",
        f"Bekleyen {pending_side} {pair} reddedildi — 'Açılmaya Hazır İşlemler' listesinde manuel açılmaya hazır.",
        pair=pair, side=pending_side,
        metadata={"moved_to": "manual_ready_trades"},
    )
    return True


# ── Manuel açılabilir işlemler ──────────────────────────────────────────────

def force_open_manual_ready(pair: str, current_price: float | None = None) -> dict[str, Any]:
    """Manuel açılabilir kuyruğundan pozisyon aç — anlık fiyattan.

    Returns: {"status": "opened"|"not_found"|"no_price", ...}
    """
    with _LOCK:
        st = _load_state()
        mr = st.manual_ready_trades.get(pair)
        if mr is None:
            return {"status": "not_found", "pair": pair}

        # Anlık fiyat: parametreden veya last_tick_prices'tan
        price = float(current_price or 0.0) or float(st.last_tick_prices.get(pair, 0.0))
        if price <= 0:
            return {"status": "no_price", "pair": pair}

        now_dt = _utc_now()
        now_iso = now_dt.isoformat()
        if not _is_market_open(pair, now_dt):
            return {"status": "market_closed", "pair": pair}

        # Pending-like geçici nesne üzerinden açıyoruz — risk_plan otomatik kurulur.
        pending_obj = PendingOpenOrder(
            pair=mr.pair,
            side=mr.side,
            requested_at=mr.requested_at,
            execute_at=now_iso,
            requested_price=mr.requested_price,
            size_usd=mr.size_usd,
            last_signal=mr.last_signal,
            open_signal=mr.open_signal,
            fingerprint=mr.fingerprint,
            atr_value=mr.atr_value,
            primary_tf=mr.primary_tf,
        )
        _open_position_from_pending(st, pending_obj, price, now_iso)
        # Manuel açıldı: hem manual_ready hem rejected_signals temizlensin
        st.manual_ready_trades.pop(pair, None)
        st.rejected_signals.pop(pair, None)
        _save_state(st)

    _try_emit(
        "manual_ready_opened", "TRADE_EVENT",
        f"Manuel açıldı: {pending_obj.side} {pair}",
        f"Açılmaya hazır {pending_obj.side} {pair} kullanıcı talebiyle ${price:,.2f} fiyatından açıldı.",
        pair=pair, side=pending_obj.side, price=price, size_usd=pending_obj.size_usd,
    )
    return {"status": "opened", "pair": pair, "side": pending_obj.side, "price": price}


def dismiss_manual_ready(pair: str) -> bool:
    """Manuel açılabilir kuyruğundan sil — silent block (rejected_signals) korunur."""
    with _LOCK:
        st = _load_state()
        mr = st.manual_ready_trades.pop(pair, None)
        if mr is None:
            return False
        _save_state(st)

    _try_emit(
        "manual_ready_dismissed", "INFO",
        f"Manuel hazır iptal: {mr.side} {pair}",
        f"Açılmaya hazır {mr.side} {pair} kullanıcı tarafından listeden çıkarıldı.",
        pair=pair, side=mr.side,
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

    # Manuel açılabilir işlemler — reddedilmiş, hazırda bekleyen
    manual_ready_trades = []
    for mr in st.manual_ready_trades.values():
        cur_price = current_prices.get(mr.pair, mr.requested_price)
        manual_ready_trades.append({
            **asdict(mr),
            "current_price": cur_price,
            "market_open":   _is_market_open(mr.pair, now_dt),
        })
    manual_ready_trades.sort(key=lambda it: (it["rejected_at"], it["pair"]))

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
        "manual_ready_trades": manual_ready_trades,
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
        # Attribution seen-set'i de sıfırla → eski trade.id'ler tekrar emit'lenebilir
        _ATTRIBUTION_SEEN_IDS.clear()
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
    "force_open_manual_ready", "dismiss_manual_ready",
    "OPEN_CONFIRMATION_WINDOW_SECONDS", "_is_market_open",
    "TRADED_PAIRS", "STARTING_BALANCE", "POSITION_SIZE",
    "ManualReadyTrade", "PendingOpenOrder", "RejectedOpenSignal",
]
