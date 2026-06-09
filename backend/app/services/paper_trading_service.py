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
import logging
import threading
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

PositionSide = Literal["LONG", "SHORT"]
TradeEvent   = Literal["OPEN", "CLOSE"]

# ── Sabitler ──────────────────────────────────────────────────────────────────

STARTING_BALANCE = 100_000.0
POSITION_SIZE    = 25_000.0   # baz pozisyon büyüklüğü (consensus güveni ile ×0.6 .. ×1.5)
TRADED_PAIRS     = ("BTCUSD", "XAUUSD", "XAGUSD", "BRENT")
MARKET_HOURS_GATED_PAIRS = frozenset({"XAUUSD", "XAGUSD", "BRENT", "XCUUSD"})

# ── Fiyat mantık sınırları (price sanity guard) ──────────────────────────────
# Veri kaynağı (yfinance/pipeline) arızalandığında saçma fiyatlar pair'ler
# arasında karışıyor (BTC için $7405, BRENT için $284, XAUUSD için $716 vs.).
# Sınırları 2026 piyasa aralığına yakın tut — geniş kalsa bile cross-pair
# karışmayı (örn. XAUUSD'ye XAGUSD fiyatı gelmesi) yine kaçırır, o yüzden
# bu absolute bounds + price-jump guard (önceki sane fiyata göre %30 sapma)
# BİRLİKTE kullanılır.
PRICE_SANITY_BOUNDS: dict[str, tuple[float, float]] = {
    "BTCUSD": (20_000.0, 500_000.0),
    "XAUUSD": (1_500.0, 7_000.0),
    "XAGUSD": (15.0, 150.0),
    "BRENT":  (30.0, 200.0),
}

# Önceki sane tick fiyatına göre maksimum izin verilen sapma. Cross-pair
# kontaminasyon (BTC→7405) anomaly'sini absolute bounds yakalayamayabiliyor,
# çünkü 7405 BTC'nin tarihi-makul aralığındadır. Ama önceki tick BTC=64000 ise
# %88'lik düşüş → kabul edilemez. ±%30 limit gerçek piyasada hiçbir tick için
# aşılmaz; aşılırsa kesin veri arızasıdır.
PRICE_MAX_JUMP_PCT: float = 30.0

# ── State anomaly guard ───────────────────────────────────────────────────────
# Bozuk fiyat verisi state'e zaten yazılmışsa (geçmiş trade'ler) realized_pnl/
# equity başlangıç bakiyesinin kat kat üzerine çıkar. Böyle bir durumda yeni
# paper trade açılışını durdurup kullanıcıyı UI'da uyarmak için kullanılır —
# mevcut pozisyonları kapatmak/yönetmek ENGELLENMEZ.
ANOMALY_EQUITY_MULTIPLIER = 3.0
ANOMALY_DAILY_PNL_FRACTION = 0.5


def _is_price_sane(
    pair: str,
    price: float,
    *,
    previous_price: float | None = None,
) -> bool:
    """Fiyat mantıklı bir aralıkta mı? Değilse pozisyon aç/kapat/yönet'e girmez.

    İki kademeli kontrol:
      1) Absolute bounds: PRICE_SANITY_BOUNDS içindeki [lo, hi] aralığı.
         Sınır tanımlı olmayan pariteler için sadece pozitiflik kontrolü.
      2) Price-jump guard: Opsiyonel previous_price verildiyse, yeni fiyat
         önceki fiyata göre PRICE_MAX_JUMP_PCT'den fazla sapıyorsa reddet.
         Cross-pair contamination yakalama amaçlı (BTC→7405 ABS-makul ama
         önceki tick'e göre saçma).
    """
    if price <= 0:
        return False
    bounds = PRICE_SANITY_BOUNDS.get(pair)
    if bounds is not None:
        lo, hi = bounds
        if not (lo <= price <= hi):
            return False
    if previous_price is not None and previous_price > 0:
        pct = abs(price - previous_price) / previous_price * 100.0
        if pct > PRICE_MAX_JUMP_PCT:
            return False
    return True


def _detect_state_anomaly(
    st: "TradingState",
    *,
    equity: float | None = None,
    daily_pnl: float | None = None,
) -> dict[str, Any]:
    """Gerçekçi olmayan realized_pnl/equity/daily_pnl tespiti.

    Kaynak veri (fiyat akışı) bozulduğunda realized_pnl/equity başlangıç
    bakiyesinin kat kat üzerine çıkabilir. Tespit edilirse çağıran taraf
    (tick_consensus) yeni trade açılışını durdurur, get_snapshot ise UI'da
    uyarı banner'ı için sebepleri döner.
    """
    reasons: list[str] = []
    base = st.starting_balance
    if base > 0:
        if abs(st.realized_pnl_usd) > base * ANOMALY_EQUITY_MULTIPLIER:
            reasons.append(
                f"Realized PnL (${st.realized_pnl_usd:,.2f}) başlangıç bakiyenin "
                f"{ANOMALY_EQUITY_MULTIPLIER:.0f} katını aşıyor (${base:,.2f})"
            )
        if equity is not None and equity > base * ANOMALY_EQUITY_MULTIPLIER:
            reasons.append(
                f"Equity (${equity:,.2f}) başlangıç bakiyenin "
                f"{ANOMALY_EQUITY_MULTIPLIER:.0f} katını aşıyor (${base:,.2f})"
            )
        if daily_pnl is not None and abs(daily_pnl) > base * ANOMALY_DAILY_PNL_FRACTION:
            reasons.append(
                f"Günlük PnL (${daily_pnl:,.2f}) başlangıç bakiyenin "
                f"%{ANOMALY_DAILY_PNL_FRACTION * 100:.0f}'ini aşıyor"
            )
    return {"detected": bool(reasons), "reasons": reasons}
MARKET_CLOSE_FRIDAY_UTC_HOUR = 21
MARKET_OPEN_SUNDAY_UTC_HOUR = 22
OPEN_CONFIRMATION_WINDOW_SECONDS = 60
DAILY_LOSS_LIMIT_USD = -5_000.0   # günlük zarar uyarı eşiği

# ── Paper Trading Mode (Controlled-Aggressive) ───────────────────────────────
# "conservative"          → eski davranış (yalnızca tam confirmed setup)
# "balanced"              → orta — confidence yüksekse açar
# "controlled_aggressive" → varsayılan: TACTICAL/SCALP setup'larını da açar
#                           ama küçük boyut + yakın stop + kısa holding ile
# Mod, sadece aggregator BLOCK demediği zaman aktiftir; DQS<55, kill_switch,
# divergent TF, asset-adverse event gibi hard blok kuralları HER zaman geçerli.
PAPER_TRADING_MODE: str = (
    __import__("os").environ.get("PAPER_TRADING_MODE", "controlled_aggressive").lower()
)

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
    stop_loss:   float = 0.0    # aktif SL seviyesi (trailing stop günceller)
    take_profit: float = 0.0    # aktif TP seviyesi (TP2 = tam kapat)
    # ── Öğrenme için: pozisyon açılırken alınan sinyal snapshot'ı ──
    open_signal: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""        # sinyal imzası (benzer durumları tanıma için)
    # ── SL/TP arkasındaki hikaye (timeframe + ATR + beklenen horizon) ──
    risk_plan:   dict[str, Any] = field(default_factory=dict)
    # ── S1: Trailing Stop (ATR-based) ──
    trailing_stop_active: bool = False   # Break-even veya daha iyi SL aktif
    peak_favorable_price: float = 0.0   # LONG: görülen max fiyat / SHORT: min fiyat
    # ── S2: Partial Take-Profit ──
    partial_tp_taken: bool = False       # TP1 (%50 lot) realize edildi mi
    original_size_usd: float = 0.0      # Partial TP öncesi lot (0 = alınmadı)
    # ── UI ayrımı için: pozisyonu kim açtı? ──
    # "PAPER"  = otomatik pending → 60sn'lik onay penceresi sonunda açıldı
    # "MANUAL" = kullanıcı 'Açılmaya Hazır' kuyruğundan elle açtı (force_open_manual_ready)
    opened_by:   str = "PAPER"           # backward compat: eski state'lerde alan yoksa PAPER varsayılır
    # ── FAZ 2: Aggression Execution Integration ──
    # recheck_plan: pozisyon her N dakikada yeniden değerlendirilir; bu fazda
    # otomatik close DEĞIL, sadece audit/flag/review yazılır.
    # holding_plan: max_holding_until geldiğinde holding_status değişir; bu
    # fazda otomatik close DEĞİL — sadece UI/audit "expired_needs_review".
    recheck_plan: dict[str, Any] = field(default_factory=dict)
    holding_plan: dict[str, Any] = field(default_factory=dict)
    # ── FAZ 3: Position Management (parçalı alım + manuel SL/TP override) ──
    # add_plan: parçalı alım planı — mod, max size, kademe seviyeleri, durum.
    # manual_risk_override: kullanıcı SL/TP'yi elle değiştirdiyse; auto_plan_backup
    # otomatik planı sakar, "Otomatik Plana Geri Dön" ile geri yüklenir.
    # opening_explanation: işlemin neden açıldığına dair derive edilmiş açıklama.
    add_plan: dict[str, Any] = field(default_factory=dict)
    manual_risk_override: dict[str, Any] = field(default_factory=dict)
    opening_explanation: dict[str, Any] = field(default_factory=dict)
    # add_history: gerçekleşen parçalı alımlar (audit) — entry_price, size_usd, reason, ts
    add_history: list[dict[str, Any]] = field(default_factory=list)
    # average_entry_price: parçalı alım sonrası güncellenen ortalama giriş; entry_price ile birlikte tutulur
    average_entry_price: float = 0.0


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
    # ── Veri kalitesi bayrağı — repair sonrası ayıklama için ──
    # "" = sağlıklı; "price_anomaly" = entry/exit fiyatı mantık dışı sınırlarda,
    # repair script tarafından işaretlenmiştir, PnL audit için tutulur ama
    # realized_pnl/equity hesabına dahil edilmez.
    data_quality_flag: str = ""


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
            # S1/S2: Trailing stop + partial TP alanları (backward compat)
            v.setdefault("trailing_stop_active", False)
            v.setdefault("peak_favorable_price", 0.0)
            v.setdefault("partial_tp_taken", False)
            v.setdefault("original_size_usd", 0.0)
            v.setdefault("opened_by", "PAPER")
            # FAZ 2: recheck/holding plan defaults (eski state için)
            v.setdefault("recheck_plan", {})
            v.setdefault("holding_plan", {})
            # FAZ 3: position management defaults (eski state için)
            v.setdefault("add_plan", {})
            v.setdefault("manual_risk_override", {})
            v.setdefault("opening_explanation", {})
            v.setdefault("add_history", [])
            v.setdefault("average_entry_price", v.get("entry_price", 0.0))
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
            t.setdefault("data_quality_flag", "")
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


# Riskli rejimlerde otomatik açılış kapalı — kullanıcı 'Aç' demeden açılmaz.
_MANUAL_APPROVAL_REGIMES = {"DEFENSIVE", "CRISIS"}


def _route_new_open_signal(
    st: TradingState,
    *,
    pair: str,
    side: PositionSide,
    price: float,
    size_usd: float,
    last_signal: str,
    signal_snapshot: dict[str, Any],
    fingerprint: str,
    now_dt: datetime,
    atr_value: float,
    primary_tf: str,
    is_recurring: bool,
    raw_regime: str,
) -> None:
    """Yeni LONG/SHORT adayını rejime göre yönlendirir.

    DEFENSIVE/CRISIS → 60sn otomatik açılış YOK; aday doğrudan 'Açılmaya
    Hazır İşlemler' kuyruğuna düşer (kullanıcı 'Aç' demeden açılmaz).
    Aynı (side, primary_tf) aday zaten kuyruktaysa dokunulmaz — genel
    per-tick refresh (yukarıda) zaten taze fiyat/sinyal ile günceller ve
    original_requested_price donmuş kalır. Farklı yön/TF gelirse mevcut
    adayın üzerine taze sinyalle yazılır + kullanıcıya bildirim gider.

    NEUTRAL/OFFENSIVE → eski davranış: 60sn pending banner, reddedilmezse açılır.
    """
    # FAZ 3 — Audit: agent thesis context (read-only; karar motorunu etkilemez)
    from app.services.agent_thesis_context import (  # noqa: PLC0415
        build_thesis_trade_context as _build_ctx,
        load_latest_safe_thesis as _load_safe,
    )
    try:
        signal_snapshot = {
            **signal_snapshot,
            "agent_thesis_context": _build_ctx(pair, _load_safe()),
        }
    except Exception:  # noqa: BLE001
        pass  # audit enrichment hatası trade açılışını bloke etmez

    # FAZ 10.2 — Similar Trade Memory (audit only; karar motorunu etkilemez)
    try:
        from app.services.similar_trade_memory import (  # noqa: PLC0415
            find_similar_trade_memories as _find_similar,
        )
        signal_snapshot = {
            **signal_snapshot,
            "similar_memory_context": _find_similar(signal_snapshot, pair, side),
        }
    except Exception:  # noqa: BLE001
        pass  # audit enrichment hatası trade açılışını bloke etmez

    if raw_regime in _MANUAL_APPROVAL_REGIMES:
        existing = st.manual_ready_trades.get(pair)
        is_same_candidate = (
            existing is not None
            and existing.side == side
            and (not primary_tf or not existing.primary_tf or existing.primary_tf == primary_tf)
        )
        if is_same_candidate:
            return

        now_iso = now_dt.isoformat()
        st.pending_orders.pop(pair, None)
        st.manual_ready_trades[pair] = ManualReadyTrade(
            pair=pair,
            side=side,
            requested_at=now_iso,
            rejected_at=now_iso,
            last_signal=last_signal,
            size_usd=size_usd,
            requested_price=price,
            open_signal=signal_snapshot,
            fingerprint=fingerprint,
            atr_value=atr_value,
            primary_tf=primary_tf,
            original_requested_price=price,
            last_refreshed_at=now_iso,
        )
        _try_emit(
            "manual_approval_required", "ACTION_REQUIRED",
            f"{side} {pair} — Manuel Onay Gerekli (Rejim: {raw_regime})",
            f"{raw_regime} rejiminde otomatik açılış devre dışı. {side} {pair} adayı "
            f"'Açılmaya Hazır İşlemler' kuyruğuna eklendi — açmak için 'Aç' demelisin.",
            pair=pair, side=side, size_usd=size_usd, price=price,
            metadata={"regime": raw_regime, "manual_approval": True, "primary_tf": primary_tf},
        )
        return

    _queue_pending_open(
        st=st, pair=pair, side=side, price=price, size_usd=size_usd,
        last_signal=last_signal, signal_snapshot=signal_snapshot,
        fingerprint=fingerprint, now_dt=now_dt, atr_value=atr_value,
        primary_tf=primary_tf, is_recurring=is_recurring,
    )


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


# ── S1: Trailing Stop + Break-Even / S2: Partial Take-Profit ─────────────────

def _get_atr_for_position(cur: "Position") -> float:
    """Pozisyon açılışındaki ATR değerini risk_plan veya open_signal'dan çıkar."""
    return float(
        cur.risk_plan.get("atr_used")
        or cur.open_signal.get("atr")
        or 0.0
    )


def _close_open_position(
    st: "TradingState",
    cur: "Position",
    pair: str,
    price: float,
    now_iso: str,
    reason: str,
) -> None:
    """Açık pozisyonu kapat; Trade kaydı + realize_pnl + emit.

    Sadece SL/TP/trailing kapatmaları için kullanılır.
    Signal-reversal close'ları mevcut tick loop kodunu kullanmaya devam eder.
    """
    pnl_usd, pnl_pct = _unrealized_pnl(cur, price)
    verdict = "WIN" if pnl_usd > 5.0 else ("LOSS" if pnl_usd < -5.0 else "BREAK_EVEN")
    duration_min = int(
        (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
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
        reason=reason,
        open_signal=cur.open_signal,
        exit_signal={"price": price, "reason": reason},
        verdict=verdict,
        fingerprint=cur.fingerprint,
        risk_plan=cur.risk_plan or {},
    )
    st.trades.append(trade)
    st.realized_pnl_usd += pnl_usd
    st.last_event = {
        "type": "CLOSE", "pair": pair, "side": cur.side,
        "pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2),
        "price": price, "verdict": verdict, "reason": reason,
    }
    st.last_event_at = now_iso
    del st.positions[pair]
    _try_emit(
        "paper_trade_closed", "TRADE_EVENT",
        f"{cur.side} {pair} Kapatıldı — {reason}",
        f"{cur.side} {pair} {reason} ile kapandı: PnL {pnl_usd:+,.2f} USD ({verdict})",
        pair=pair, side=cur.side, size_usd=cur.size_usd, price=price, reason=reason,
        metadata={"pnl_usd": round(pnl_usd, 2), "pnl_pct": round(pnl_pct, 2), "verdict": verdict},
    )


def _realize_partial_tp(
    st: "TradingState",
    cur: "Position",
    pair: str,
    price: float,
    now_iso: str,
) -> None:
    """TP1 eşiğinde lot'un %50'sini realize et; kalan %50 için SL = entry (break-even).

    Çağrı şartı: cur.partial_tp_taken == False ve price TP1'i geçmiş.
    """
    half_size = cur.size_usd / 2.0
    pnl_full, pnl_pct = _unrealized_pnl(cur, price)
    pnl_half = pnl_full / 2.0
    duration_min = int(
        (datetime.fromisoformat(now_iso) - datetime.fromisoformat(cur.entry_at)).total_seconds() / 60
    )
    trade = Trade(
        id=len(st.trades) + 1,
        pair=pair, side=cur.side,
        entry_price=cur.entry_price, exit_price=price,
        entry_at=cur.entry_at, exit_at=now_iso,
        size_usd=round(half_size, 2),
        pnl_usd=round(pnl_half, 2),
        pnl_pct=round(pnl_pct, 2),
        duration_min=duration_min,
        reason="PARTIAL_TP1",
        open_signal=cur.open_signal,
        exit_signal={"price": price, "reason": "PARTIAL_TP1"},
        verdict="WIN",
        fingerprint=cur.fingerprint,
        risk_plan=cur.risk_plan or {},
    )
    st.trades.append(trade)
    st.realized_pnl_usd += pnl_half

    # Pozisyonu yarıya indir; SL → entry (break-even garantisi)
    if cur.original_size_usd == 0.0:
        cur.original_size_usd = cur.size_usd
    cur.size_usd = round(half_size, 2)
    cur.partial_tp_taken = True
    # SL en az break-even (entry) seviyesine çekil — ama daha iyi bir SL varsa koru
    is_long = (cur.side == "LONG")
    be_sl = cur.entry_price
    if is_long:
        cur.stop_loss = max(cur.stop_loss, be_sl)  # LONG: SL yukarı gidebilir
    else:
        cur.stop_loss = min(cur.stop_loss, be_sl) if cur.stop_loss > 0 else be_sl
    cur.trailing_stop_active = True    # Break-even aktif

    _try_emit(
        "partial_tp1_taken", "TRADE_EVENT",
        f"Kısmi Kâr — {pair}",
        f"{cur.side} {pair} TP1 tetiklendi: %50 lot @ ${price:,.2f} · "
        f"PnL {pnl_half:+,.2f} USD · Kalan: ${half_size:,.0f} SL=entry",
        pair=pair, side=cur.side, price=price,
        metadata={"pnl_half": round(pnl_half, 2), "remaining_size": half_size, "tp": "TP1"},
    )


def _apply_recheck_and_holding_review(
    cur: "Position",
    pair: str,
    sig: dict[str, Any] | None,
    now_dt: datetime,
    *,
    dqs_score: int | None,
    kill_switch: bool,
) -> None:
    """FAZ 2: Pozisyon recheck + max holding kontrolü.

    Otomatik close YAPMAZ — sadece audit/flag/review yazar. Mevcut SL/TP
    mekanizması bağımsız çalışmaya devam eder (kill switch ON ise burada
    'exit_flag' işaretler ama actual close downstream'de).
    """
    plan = cur.recheck_plan or {}
    holding = cur.holding_plan or {}

    # ── Recheck kontrolü ───────────────────────────────────────────────────
    next_iso = plan.get("next_recheck_at") or ""
    if next_iso:
        try:
            next_dt = datetime.fromisoformat(next_iso)
        except (TypeError, ValueError):
            next_dt = None
        if next_dt is not None and now_dt >= next_dt:
            # Yeniden değerlendir
            result = "ok"
            reasons: list[str] = []

            if kill_switch:
                result = "exit_flag"
                reasons.append("KILL_SWITCH aktif")
            if dqs_score is not None and dqs_score < 55:
                result = "exit_flag" if result != "exit_flag" else result
                reasons.append(f"DQS düşük ({dqs_score})")

            # Sig kontrolleri (varsa)
            if isinstance(sig, dict):
                # Yön karşıt mı?
                sig_dir = (sig.get("final_direction") or "").lower()
                if sig_dir == "bullish" and cur.side == "SHORT":
                    result = "reduce_flag" if result == "ok" else result
                    reasons.append("Sinyal yönü tersine döndü (bullish vs SHORT)")
                elif sig_dir == "bearish" and cur.side == "LONG":
                    result = "reduce_flag" if result == "ok" else result
                    reasons.append("Sinyal yönü tersine döndü (bearish vs LONG)")

                # Contradiction yüksek mi?
                contradiction = sig.get("contradiction_score")
                if isinstance(contradiction, (int, float)) and contradiction >= 80:
                    result = "warning" if result == "ok" else result
                    reasons.append(f"Contradiction yüksek ({contradiction})")

                # Aggregator BLOCKED mu?
                cmd = sig.get("agent_command") or ""
                if cmd == "BLOCKED":
                    result = "exit_flag"
                    reasons.append("Aggregator BLOCKED")

            # Plan'ı ileri al
            interval = int(plan.get("recheck_interval_minutes") or 60)
            plan["last_recheck_at"]    = now_dt.isoformat()
            plan["last_recheck_result"] = result
            plan["last_recheck_reason"] = " · ".join(reasons) if reasons else "Tüm gateler temiz"
            plan["recheck_count"]      = int(plan.get("recheck_count") or 0) + 1
            plan["next_recheck_at"]    = (now_dt + timedelta(minutes=interval)).isoformat()
            cur.recheck_plan = plan

            if result in ("reduce_flag", "exit_flag", "warning"):
                _try_emit(
                    "position_recheck_flag", "INFO",
                    f"Recheck — {pair}",
                    f"{cur.side} {pair} recheck sonucu: {result.upper()} · {plan['last_recheck_reason']}",
                    pair=pair, side=cur.side, metadata={"recheck_result": result},
                )

    # ── Max holding kontrolü ──────────────────────────────────────────────
    until_iso = holding.get("max_holding_until") or ""
    status = holding.get("holding_status") or "active"
    if until_iso and status == "active":
        try:
            until_dt = datetime.fromisoformat(until_iso)
        except (TypeError, ValueError):
            until_dt = None
        if until_dt is not None and now_dt >= until_dt:
            holding["holding_status"] = "expired_needs_review"
            cur.holding_plan = holding
            _try_emit(
                "position_max_holding_expired", "INFO",
                f"Max Holding Doldu — {pair}",
                f"{cur.side} {pair} max holding süresi doldu ({holding.get('max_holding_time')}). "
                f"Pozisyon kapatılmadı; inceleme/uzatma için işaretlendi.",
                pair=pair, side=cur.side,
                metadata={"holding_status": "expired_needs_review"},
            )


def _apply_risk_management(
    st: "TradingState",
    cur: "Position",
    pair: str,
    price: float,
    now_iso: str,
) -> bool:
    """SL / TP / Trailing Stop / Partial TP uygula.

    Sıra:
      1. Trailing stop güncelle (break-even @ entry+1×ATR, trail @ entry+2×ATR)
      2. Partial TP al (TP1 = entry ± 1×ATR → %50 lot realize et)
      3. SL tetiklendiyse kapat
      4. TP tetiklendiyse (tam) kapat

    Returns True → pozisyon kapatıldı, caller `continue` etmeli.
    """
    atr = _get_atr_for_position(cur)
    entry = cur.entry_price
    is_long = (cur.side == "LONG")

    # ── 1. Trailing Stop Güncelle ──────────────────────────────────────────────
    if atr > 0:
        be_level   = entry + atr if is_long else entry - atr     # +1×ATR break-even
        trail_level = entry + 2 * atr if is_long else entry - 2 * atr  # +2×ATR trail

        if is_long:
            # Peak fiyat takibi
            cur.peak_favorable_price = max(cur.peak_favorable_price or price, price)

            # Break-even eşiği geçildi → SL en azından entry'e çek
            if price >= be_level and not cur.trailing_stop_active:
                new_sl = max(cur.stop_loss, entry)
                if new_sl > cur.stop_loss:
                    cur.stop_loss = round(new_sl, 2)
                cur.trailing_stop_active = True

            # Trailing faz: SL → price - 1.5×ATR (kâr kilidi)
            if price >= trail_level:
                trail_sl = price - 1.5 * atr
                if trail_sl > cur.stop_loss:
                    cur.stop_loss = round(trail_sl, 2)
        else:  # SHORT
            cur.peak_favorable_price = min(
                cur.peak_favorable_price if cur.peak_favorable_price > 0 else price, price
            )

            if price <= be_level and not cur.trailing_stop_active:
                new_sl = min(cur.stop_loss, entry) if cur.stop_loss > 0 else entry
                if cur.stop_loss == 0 or new_sl < cur.stop_loss:
                    cur.stop_loss = round(new_sl, 2)
                cur.trailing_stop_active = True

            if price <= trail_level:
                trail_sl = price + 1.5 * atr
                if cur.stop_loss == 0 or trail_sl < cur.stop_loss:
                    cur.stop_loss = round(trail_sl, 2)

    # ── 2. Partial TP — FAZ 3: take_profit_plan ÖNCELİKLİ, ATR fallback ────
    if not cur.partial_tp_taken:
        # FAZ 3: open_signal.take_profit_plan.partial_tp_price varsa onu kullan.
        # Aggregator bunu açılış anında (aggression-aware) finalize ediyor.
        tp_plan = (
            cur.open_signal.get("take_profit_plan")
            if isinstance(cur.open_signal, dict) else None
        ) or {}
        plan_partial_price = tp_plan.get("partial_tp_price")
        plan_partial_enabled = tp_plan.get("partial_tp_enabled")

        used_plan_partial = False
        if (
            plan_partial_enabled is True
            and isinstance(plan_partial_price, (int, float))
            and plan_partial_price > 0
        ):
            plan_hit = (
                (is_long and price >= plan_partial_price)
                or (not is_long and price <= plan_partial_price)
            )
            if plan_hit:
                _realize_partial_tp(st, cur, pair, price, now_iso)
                # Audit: hangi kaynak tetikledi (plan vs fallback)
                cur.open_signal["partial_tp_execution"] = {
                    "source":          "take_profit_plan",
                    "partial_tp_price": plan_partial_price,
                    "executed_at":     now_iso,
                    "executed_price":  price,
                    "reason":          "Aggression-aware partial TP target reached.",
                }
                used_plan_partial = True

        # Fallback: take_profit_plan yoksa veya enabled=False ise eski ATR mantığı
        if not used_plan_partial and atr > 0 and not cur.partial_tp_taken:
            tp1 = (entry + atr) if is_long else (entry - atr)
            tp1_hit = (is_long and price >= tp1) or (not is_long and price <= tp1)
            if tp1_hit:
                _realize_partial_tp(st, cur, pair, price, now_iso)
                if isinstance(cur.open_signal, dict):
                    cur.open_signal["partial_tp_execution"] = {
                        "source":          "atr_fallback",
                        "partial_tp_price": round(tp1, 4),
                        "executed_at":     now_iso,
                        "executed_price":  price,
                        "reason":          "Legacy entry±ATR partial TP target reached (no take_profit_plan).",
                    }
            # cur.stop_loss artık entry → trailing da aktif

    # ── 3. SL Kontrolü ────────────────────────────────────────────────────────
    sl = cur.stop_loss
    if sl > 0:
        sl_hit = (is_long and price <= sl) or (not is_long and price >= sl)
        if sl_hit:
            reason = "TRAILING_SL" if cur.trailing_stop_active else "SL_HIT"
            _close_open_position(st, cur, pair, price, now_iso, reason=reason)
            return True

    # ── 4. TP Kontrolü (kalan lot tam kapat) ─────────────────────────────────
    tp = cur.take_profit
    if tp > 0:
        tp_hit = (is_long and price >= tp) or (not is_long and price <= tp)
        if tp_hit:
            _close_open_position(st, cur, pair, price, now_iso, reason="TP_HIT")
            return True

    return False


def _open_position_from_pending(
    st: TradingState,
    pending: PendingOpenOrder,
    current_price: float,
    opened_at: str,
) -> None:
    from app.services.aggression_awareness import (
        build_holding_plan,
        build_recheck_plan,
        build_take_profit_plan,
        calc_aggression_aware_sl_tp,
    )
    atr_val = pending.atr_value if pending.atr_value > 0 else None
    open_signal = dict(pending.open_signal) if isinstance(pending.open_signal, dict) else {}

    # FAZ 2: aggression-aware SL/TP — open_signal.stop_decision varsa kullan
    agg_sl_tp = calc_aggression_aware_sl_tp(
        pending.side, current_price, pending.pair, atr_val, open_signal,
    )
    if agg_sl_tp is not None:
        sl, tp, sl_meta = agg_sl_tp
        risk_plan = _build_risk_plan(pending.side, current_price, pending.pair, atr_val, sl=sl, tp=tp)
        # Aggression meta'yı risk_plan üzerine merge et (audit için)
        risk_plan["aggression"] = sl_meta
    else:
        sl, tp = _calc_sl_tp(pending.side, current_price, pending.pair, atr_val)
        risk_plan = _build_risk_plan(pending.side, current_price, pending.pair, atr_val, sl=sl, tp=tp)

    # FAZ 2: open_signal'a finalized TP planını (gerçek entry/stop ile) yaz —
    # aggregator zamanında price_hint vardı; şimdi gerçek entry biliniyor.
    agg_block = open_signal.get("aggression_context") or {}
    if isinstance(agg_block, dict) and agg_block.get("aggression_level"):
        # Pure-function helper'lar için minimal ctx objesi taklit — aggression_context
        # zaten dict; build_take_profit_plan ctx istiyor → AggressionContext oluştur
        from app.services.aggression_awareness import AggressionContext
        ctx_for_plan = AggressionContext(
            aggression_level=str(agg_block.get("aggression_level") or "low"),  # type: ignore[arg-type]
            aggression_score=int(agg_block.get("aggression_score") or 0),
            why_aggressive=list(agg_block.get("why_aggressive") or []),
            allowed_if_aggressive=bool(agg_block.get("allowed_if_aggressive", True)),
            required_adjustments=dict(agg_block.get("required_adjustments") or {}),
            recommended_timeframe=str(agg_block.get("recommended_timeframe") or "1d"),  # type: ignore[arg-type]
            max_holding_time=str(agg_block.get("max_holding_time") or "48h"),
            recheck_interval_minutes=int(agg_block.get("recheck_interval_minutes") or 240),
            stop_style=str(agg_block.get("stop_style") or "structure_based"),  # type: ignore[arg-type]
            summary=str(agg_block.get("summary") or ""),
        )
        # Final TP planı — entry & stop fiyatları artık gerçek
        tp_plan_final = build_take_profit_plan(
            ctx_for_plan, None,
            side=pending.side, entry_price=current_price, stop_price=sl,
        )
        open_signal["take_profit_plan"] = tp_plan_final
        # Recheck + holding planları — gerçek opened_at ile
        recheck_plan = build_recheck_plan(ctx_for_plan, opened_at)
        holding_plan = build_holding_plan(ctx_for_plan, opened_at)
    else:
        # Eski/legacy pozisyon → recheck/holding plan kurmuyoruz (backward compat)
        recheck_plan = {}
        holding_plan = {}

    # FAZ 3: opening_explanation + default add_plan kur — açılış anında
    try:
        from app.services.position_management_service import (
            build_opening_explanation,
            initialize_default_add_plan,
        )
        opening_expl = build_opening_explanation(
            open_signal, pair=pending.pair, side=pending.side,
        )
        default_add_plan = initialize_default_add_plan(
            pending.size_usd,
            position_size_constant=POSITION_SIZE,
            average_entry=current_price,
        )
    except Exception:
        opening_expl = {}
        default_add_plan = {}

    st.positions[pending.pair] = Position(
        pair=pending.pair,
        side=pending.side,
        entry_price=current_price,
        entry_at=opened_at,
        size_usd=pending.size_usd,
        last_signal=pending.last_signal,
        open_signal=open_signal,
        fingerprint=pending.fingerprint,
        stop_loss=sl,
        take_profit=tp,
        risk_plan=risk_plan,
        recheck_plan=recheck_plan,
        holding_plan=holding_plan,
        add_plan=default_add_plan,
        opening_explanation=opening_expl,
        average_entry_price=current_price,
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
    from app.services.agent_decision_aggregator import (
        aggregate_agent_decision,
        decision_to_open_signal_extras,
    )
    from app.services.auto_tune_override_reader import apply_auto_tune_modifiers

    with _LOCK:
        st = _load_state()
        now_dt = _utc_now()
        now_iso = now_dt.isoformat()

        # ── State anomaly guard ──────────────────────────────────────────
        # Realized PnL / equity başlangıç bakiyenin kat kat üzerine çıktıysa
        # state corrupt sayılır → YENİ pozisyon açma tamamen durur. Mevcut
        # pozisyonların yönetimi (SL/TP/auto-close) çalışmaya devam eder,
        # böylece kullanıcı reset/repair yapana kadar daha fazla bozulma
        # birikmez ama hâlâ açık pozisyon güvenli kapatılabilir.
        _anomaly_guard = _detect_state_anomaly(st)
        _block_new_opens = bool(_anomaly_guard.get("detected"))

        for pair in TRADED_PAIRS:
            sig = consensus_signals.get(pair) or {}
            final_score = sig.get("final_score")
            final_direction = sig.get("final_direction")
            confluence = sig.get("confluence") or {}
            confluence_status = confluence.get("status") if isinstance(confluence, dict) else None
            atr_val_pending = float(sig.get("atr") or 0.0)
            current_primary_tf = str(sig.get("primary_tf") or "")
            raw_regime = (sig.get("raw_regime") or "NEUTRAL").upper()
            requires_manual_approval = raw_regime in _MANUAL_APPROVAL_REGIMES

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

            # Controlled-Aggressive: aggression/command/timeframe/stop bloğunu
            # sig snapshot'ına ekle — _route_new_open_signal / _queue_pending_open
            # / _refresh_manual_ready bu zenginleşmiş snapshot'ı open_signal'a yazar.
            # Block durumunda bile aggregator BLOCKED komutu üretir; audit için yine yazılır.
            sig.update(decision_to_open_signal_extras(decision))

            price = current_prices.get(pair, 0.0)
            # Fiyat mantık kontrolü: veri kaynağı bozulduğunda gelen saçma
            # fiyatlar (örn. BTC için $7405, XAUUSD için $716) realized_pnl/
            # equity'i bozar. İki kademeli kontrol: absolute bounds + önceki
            # sane tick fiyatına göre %30 max sapma.
            _prev = (st.last_tick_prices or {}).get(pair, 0.0)
            if not _is_price_sane(pair, price, previous_price=_prev):
                if price > 0:
                    logger.warning(
                        "paper_trading: %s için mantık dışı fiyat reddedildi: %.4f"
                        " (sınır: %s, önceki: %.4f)",
                        pair, price, PRICE_SANITY_BOUNDS.get(pair), _prev,
                    )
                continue

            # Açılmaya hazır (manual_ready) bir kayıt varsa HER tick'te taze
            # fiyat + sinyal + ATR ile revize et — sinyal yön/TF değişip silent
            # block tetiklenmese bile entry asla bayat fiyatta kalmamalı.
            # (original_requested_price korunur; yalnızca requested_price/
            # open_signal/atr_value/last_signal güncellenir.)
            if pair in st.manual_ready_trades:
                _refresh_manual_ready_with_live_signal(
                    st, pair,
                    price=price,
                    signal_snapshot=sig,
                    atr_value=atr_val_pending,
                    last_signal=(f"{final_direction}@{final_score:.1f}"
                                 if final_score is not None else "pending"),
                )

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

            # DEFENSIVE/CRISIS: otomatik açılış akışı (60sn pending / yinelenen
            # sinyal / silent-block) tamamen devre dışı — _route_new_open_signal
            # adayı doğrudan manuel onay kuyruğuna yönlendirir (target=None
            # ile burada pozisyon/pending mantığını es geçeriz).
            is_recurring_signal = False
            if not requires_manual_approval:
                # Yinelenen sinyal kontrolü — manual_ready varken farklı TF/side
                # → silent block'u bypass et, yeni 60sn pending'i 'recurring' bayrağıyla kur.
                is_recurring_signal = _is_recurring_signal(st, pair, target, current_primary_tf)

                # Aynı (pair, side, primary_tf) zaten reddedilmiş ya da manual_ready'de
                # → SESSIZ block. Fingerprint kayması (skor/modül oynaması) block'u
                # kaldırmaz. Banner gönderilmez, pending açılmaz.
                if not is_recurring_signal and _should_silent_block(
                    st, pair, target, current_primary_tf,
                ):
                    # Silent block: yeni pending açma (manual_ready zaten her
                    # tick'te yukarıda taze fiyat/sinyal ile revize edildi).
                    target = None
                else:
                    # Rejection eskimiş olabilir (yön/TF tamamen değişti) → temizle.
                    _purge_stale_rejection_if_needed(st, pair, target, current_primary_tf)

            new_size = round(POSITION_SIZE * final_size_mult, 2)

            # FAZ 7.5 — Auto-tune override (position_size_multiplier only)
            # Override = küçük çarpan; side/direction değişmez; trade açmaz.
            if target in ("LONG", "SHORT"):
                try:
                    _at = apply_auto_tune_modifiers(sig, target, final_size_mult)
                    sig["auto_tune_context"] = _at["auto_tune_context"]
                    if _at["auto_tune_context"].get("applied"):
                        final_size_mult = _at["size_pct"]
                        new_size = round(POSITION_SIZE * final_size_mult, 2)
                except Exception:
                    logger.exception("auto_tune_override: failed (ignored)")

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
                # FAZ 2: Recheck + max holding review — audit/flag only (otomatik close YOK)
                _apply_recheck_and_holding_review(
                    cur, pair, sig, now_dt,
                    dqs_score=dqs_score, kill_switch=kill_switch,
                )

                # ── S1/S2: SL / TP / Trailing Stop / Partial TP ──────────────
                # Fiyat SL veya TP'ye dokunmuşsa otomatik kapat.
                # Break-even + trailing stop güncelle.
                # Partial TP1 (entry±ATR) tetiklendiyse %50 realize et.
                if _apply_risk_management(st, cur, pair, price, now_iso):
                    continue   # pozisyon kapatıldı → sonraki pair

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

                    if (
                        target in ("LONG", "SHORT")
                        and not _block_new_opens
                        and _is_market_open(pair, now_dt)
                    ):
                        _route_new_open_signal(
                            st,
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
                            raw_regime=raw_regime,
                        )
                    else:
                        st.pending_orders.pop(pair, None)
                continue

            if (
                target in ("LONG", "SHORT")
                and pending is None
                and not _block_new_opens
                and _is_market_open(pair, now_dt)
            ):
                _route_new_open_signal(
                    st,
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
                    raw_regime=raw_regime,
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
        # Sadece mantıklı fiyatları persiste et — bozuk fiyat eski iyi
        # değerleri ezmesin (sonraki tick yine garbage'la başlamamalı).
        # Jump guard burada da uygulanır — abs bounds geçen ama önceki
        # sane fiyattan %30+ sapan fiyat last_tick_prices'a yazılmaz.
        prev_prices = dict(st.last_tick_prices or {})
        for _p, _v in current_prices.items():
            if _is_price_sane(_p, _v, previous_price=prev_prices.get(_p)):
                prev_prices[_p] = _v
        st.last_tick_prices = prev_prices
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
        # UI ayrımı için pozisyonu MANUAL olarak işaretle — pending'lerden açılan
        # pozisyonlar default "PAPER" kalır; sadece bu kullanıcı-tetiklemeli yol MANUAL.
        opened_pos = st.positions.get(pair)
        if opened_pos is not None:
            opened_pos.opened_by = "MANUAL"
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
    # FAZ 3: position_management_service lazy import — circular avoidance
    try:
        from app.services.position_management_service import (
            build_opening_explanation,
            initialize_default_add_plan,
        )
    except Exception:
        build_opening_explanation = None  # type: ignore[assignment]
        initialize_default_add_plan = None  # type: ignore[assignment]

    for p in st.positions.values():
        cur_price = current_prices.get(p.pair, p.entry_price)
        pnl_usd, pnl_pct = _unrealized_pnl(p, cur_price)
        unrealized_total += pnl_usd
        # ── Bu pozisyonun fingerprint'inin geçmişi
        fp_history = win_rate_for_fingerprint(p.fingerprint, st.trades) if p.fingerprint else None

        # FAZ 3: snapshot-only enrichment (state'i mutate ETMEZ).
        # Eski pozisyonlarda add_plan/opening_explanation yoksa default doldur.
        avg_entry = p.average_entry_price or p.entry_price
        add_plan_view = p.add_plan
        if (not add_plan_view) and initialize_default_add_plan is not None:
            add_plan_view = initialize_default_add_plan(
                p.size_usd,
                position_size_constant=POSITION_SIZE,
                average_entry=avg_entry,
            )
        opening_view = p.opening_explanation
        if (not opening_view) and build_opening_explanation is not None:
            try:
                opening_view = build_opening_explanation(
                    p.open_signal, pair=p.pair, side=p.side,
                )
            except Exception:
                opening_view = {}

        open_positions.append({
            **asdict(p),
            "current_price": cur_price,
            "pnl_usd":  round(pnl_usd, 2),
            "pnl_pct":  round(pnl_pct, 2),
            "fingerprint_history": fp_history,
            # Snapshot-only override'lar — state dosyasına yazılmaz
            "add_plan":            add_plan_view,
            "opening_explanation": opening_view,
            "average_entry_price": avg_entry,
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

    # State corruption / accounting anomaly tespiti — UI burada banner basar,
    # tick_consensus yeni trade açılışını burdaki guard ile aynı eşiklerden
    # bağımsız hesaplar (orada starting_balance + realized_pnl_usd yeter,
    # equity/daily_pnl burada zaten elde olduğu için ekstra teyit ekleniyor).
    anomaly = _detect_state_anomaly(st, equity=equity, daily_pnl=daily_pnl)

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
        "state_anomaly":    {
            "active":  anomaly["detected"],
            "reasons": anomaly["reasons"],
            "action":  "REPAIR_OR_RESET_REQUIRED" if anomaly["detected"] else "OK",
        },
    }


def reset_state() -> None:
    """Trade geçmişi + pozisyonları sıfırla, hesabı 100k bakiyeden yeniden başlat.

    weight_adjustments / training_history / last_trained_at_trade_count
    KORUNUR — bunlar agent'ın geçmiş trade'lerden öğrendiği ayarlamalardır,
    hesap sıfırlamasıyla silinmemeli (signal_attribution.jsonl de ayrı bir
    dosyada tutulduğu için zaten etkilenmiyor).
    """
    with _LOCK:
        st = _load_state()
        # Attribution seen-set'i de sıfırla → eski trade.id'ler tekrar emit'lenebilir
        _ATTRIBUTION_SEEN_IDS.clear()
        fresh = TradingState(
            weight_adjustments=st.weight_adjustments,
            training_history=st.training_history,
        )
        _save_state(fresh)


def _backup_state_file(reason: str = "manual") -> str | None:
    """State dosyasını timestamp'li backup'a kopyalar. Path'i döner."""
    if not _STATE_PATH.exists():
        return None
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = _STATE_PATH.with_name(
        f"{_STATE_PATH.stem}_backup_{reason}_{ts}{_STATE_PATH.suffix}"
    )
    try:
        backup_path.write_bytes(_STATE_PATH.read_bytes())
    except OSError as exc:
        logger.warning("paper_trading: state backup başarısız: %s", exc)
        return None
    return str(backup_path)


def hard_reset_state(reason: str = "corrupt_state_manual_reset") -> dict[str, Any]:
    """Bozuk state'i temizle: önce backup, sonra TAM sıfırla.

    `reset_state()` weight_adjustments / training_history KORUR — corruption
    durumunda bunlar da bozuk olabileceğinden hard_reset HEPSİNİ sıfırlar.
    PAPER_SAFE / NO_EXECUTION — gerçek emir YOK.
    """
    with _LOCK:
        backup_path = _backup_state_file(reason=reason)
        _ATTRIBUTION_SEEN_IDS.clear()
        fresh = TradingState()
        _save_state(fresh)
        return {
            "status": "reset",
            "reason": reason,
            "backup_path": backup_path,
            "starting_balance": fresh.starting_balance,
            "equity": fresh.starting_balance,
            "realized_pnl_usd": 0.0,
            "open_positions": 0,
            "trade_count": 0,
        }


def _compute_corrected_realized_pnl(
    trades: list[Trade],
) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
    """Trade history'den realized_pnl'i sağlıklı kayıtlardan yeniden hesapla.

    Dönen:
      (corrected_realized_pnl, sane_trades_summary, anomalous_trades_summary)

    Bir trade'in entry/exit fiyatı PRICE_SANITY_BOUNDS dışındaysa "anomalous"
    sayılır, realized_pnl toplamına dahil EDİLMEZ ve audit için döner.
    """
    sane: list[dict[str, Any]] = []
    anomalous: list[dict[str, Any]] = []
    corrected = 0.0
    for t in trades:
        entry_ok = _is_price_sane(t.pair, t.entry_price)
        exit_ok = _is_price_sane(t.pair, t.exit_price)
        if entry_ok and exit_ok:
            corrected += float(t.pnl_usd)
            sane.append({"id": t.id, "pair": t.pair, "pnl_usd": t.pnl_usd})
        else:
            anomalous.append({
                "id": t.id,
                "pair": t.pair,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_usd": t.pnl_usd,
                "reasons": [
                    *(["entry_out_of_bounds"] if not entry_ok else []),
                    *(["exit_out_of_bounds"] if not exit_ok else []),
                ],
            })
    return corrected, sane, anomalous


def repair_state(*, dry_run: bool = True) -> dict[str, Any]:
    """Bozuk realized_pnl'i sağlıklı trade'lerden yeniden hesapla.

    Mantık:
      * Trade history'deki her trade'in entry/exit fiyatı PRICE_SANITY_BOUNDS'a
        karşı kontrol edilir.
      * Sınır dışı trade'ler realized_pnl toplamına dahil edilmez ve
        data_quality_flag="price_anomaly" ile işaretlenir (apply modunda).
      * Eğer sağlıklı trade hiç kalmıyorsa repair güvenilir değildir; reset
        önerilir.
      * Açık pozisyonlar ESNEK BIRAKIR — repair burada pozisyon silmez, çünkü
        canlı pozisyonlar tick'te yönetiliyor; corruption düzeldiğinde
        anomaly guard otomatik kalkar.
    PAPER_SAFE / NO_EXECUTION.
    """
    with _LOCK:
        st = _load_state()
        old_realized = float(st.realized_pnl_usd)
        corrected_realized, sane, anomalous = _compute_corrected_realized_pnl(
            st.trades
        )
        unrealized_total = 0.0
        last_prices = st.last_tick_prices or {}
        for p in st.positions.values():
            cur = float(last_prices.get(p.pair, p.entry_price))
            if _is_price_sane(p.pair, cur):
                u, _ = _unrealized_pnl(p, cur)
                unrealized_total += u
        new_equity = st.starting_balance + corrected_realized + unrealized_total

        if not sane and st.trades:
            return {
                "status": "repair_not_safe",
                "reason": "closed_trade_records_corrupt",
                "recommendation": "reset",
                "old_realized_pnl": old_realized,
                "anomalous_trades": len(anomalous),
                "sane_trades": 0,
            }

        report = {
            "status": "dry_run" if dry_run else "applied",
            "old_realized_pnl": round(old_realized, 2),
            "corrected_realized_pnl": round(corrected_realized, 2),
            "delta": round(corrected_realized - old_realized, 2),
            "new_equity": round(new_equity, 2),
            "new_unrealized_pnl": round(unrealized_total, 2),
            "starting_balance": st.starting_balance,
            "sane_trade_count": len(sane),
            "anomalous_trade_count": len(anomalous),
            "anomalous_sample": anomalous[:10],
            "backup_path": None,
        }

        if dry_run:
            return report

        backup_path = _backup_state_file(reason="repair")
        for t in st.trades:
            entry_ok = _is_price_sane(t.pair, t.entry_price)
            exit_ok = _is_price_sane(t.pair, t.exit_price)
            if not (entry_ok and exit_ok):
                t.data_quality_flag = "price_anomaly"
        st.realized_pnl_usd = corrected_realized
        _save_state(st)
        report["backup_path"] = backup_path
        return report


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
