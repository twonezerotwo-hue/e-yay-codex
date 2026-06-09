"""
Regime Report Service — 4-katmanlı piyasa analiz motoru.

Katman 1: Makro Rejim      (DXY, M2SL, yield curve, Brent)
Katman 2: Risk İştahı      (HYG/JNK, BTC.D, USDT.D, Gold/equities)
Katman 3: Asset Sinyalleri (çapraz teyit, per-asset logic)
Katman 4: Tek karar        (AÇIL / BEKLE / KÜÇÜLT / KAPAT)

Çıktı: RegimeReport dataclass — hiçbir zaman trade execution içermez.
"""
from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.domain import AssetCode
from app.domain.market_snapshot import MarketSnapshot
from app.providers.news_provider import NewsHeadline
from app.providers.technical_provider import TechnicalInsight, _is_insight_sane
from app.services.event_calendar_service import CatalystEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML threshold loader — config/thresholds.yaml tek kaynak
# ---------------------------------------------------------------------------

def _load_thresholds() -> dict[str, Any]:
    """config/thresholds.yaml yükle; dosya yoksa boş dict döndür (fallback hardcoded)."""
    try:
        import yaml  # type: ignore[import]
        p = Path(__file__).resolve().parents[2] / "config" / "thresholds.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}

_THR = _load_thresholds()

# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

Decision = Literal["AÇIL", "BEKLE", "KÜÇÜLT", "KAPAT"]
RegimeCode = Literal["RISK_ON", "TRANSITIONING", "DEFENSIVE", "CRISIS"]
AppetiteCode = Literal["STRONG", "MODERATE", "WEAK", "CRISIS"]
SignalStatus = Literal["CONFIRMED", "PENDING", "BLOCKING", "NEUTRAL", "VERİ_YOK"]
AssetActionType = Literal["LONG", "LONG_AWAIT", "SHORT", "SHORT_AWAIT", "HOLD", "AVOID", "NEUTRAL"]


@dataclass(frozen=True)
class MacroLayer:
    regime: RegimeCode
    confidence_pct: int
    dxy_signal: str
    energy_signal: str
    yield_curve_signal: str
    m2_signal: str
    summary: str


@dataclass(frozen=True)
class RiskAppetiteLayer:
    status: AppetiteCode
    credit_signal: str
    btc_dominance_signal: str
    usdt_dominance_signal: str
    safe_haven_signal: str
    summary: str


@dataclass(frozen=True)
class AssetSignal:
    asset_code: str
    asset_name: str
    status: SignalStatus
    reason: str
    value: float | None
    unit: str
    delta_7d_pct: float | None = None   # 7 günlük % değişimi (≈10 iş günü)
    asset_action: AssetActionType = "NEUTRAL"   # per-asset eylem önerisi
    action_trigger: str = ""                     # eylem koşulu / beklenen tetikleyici
    # ── Controlled-Aggressive UI etiketleri ──
    # paper_trading_service'ten doldurulur (varsa); UI sadece dolu olduğunda
    # küçük badge render eder ("Normal" / "Taktik" / "Agresif" / "Çok Agresif").
    aggression_level: str = ""    # "" | "low" | "medium" | "high" | "extreme"
    agent_command: str = ""       # "" | "WAIT" | "TACTICAL_LONG_SETUP" | ...
    # FAZ 2: UI extension — timeframe + stop style + recheck (sade etiket için)
    recommended_timeframe: str = ""    # "" | "15m" | "30m" | "1h" | "4h" | "1d"
    stop_style: str = ""               # "" | "tight_atr" | "structure_based" | "hybrid_tight"
    recheck_interval_minutes: int = 0  # 0 = veri yok


@dataclass(frozen=True)
class ConfirmationItem:
    signal: str
    met: bool
    current_value: str
    threshold: str


@dataclass(frozen=True)
class AsymmetrySignal:
    """
    Risk/Ödül asimetrisi — mevcut sinyal durumundan türetilir.
    Olasılık-ağırlıklı beklenen kazanç vs beklenen kayıp oranı.
    """
    expected_gain_pct: float    # olasılık-ağırlıklı beklenen kazanç
    expected_loss_pct: float    # olasılık-ağırlıklı beklenen kayıp (pozitif değer)
    ratio: float                # expected_gain / expected_loss
    label: str                  # "Çok Olumlu" / "Olumlu" / "Dengeli" / "Olumsuz" / "Çok Olumsuz"
    color: str                  # "green" | "lime" | "yellow" | "orange" | "red"
    brief: str                  # 1 cümle yorum


@dataclass(frozen=True)
class Scenario:
    key: str              # "bull" | "base" | "bear"
    label: str            # "Boğa", "Baz", "Ayı"
    probability_pct: int  # 0–100 (3 senaryo toplamı 100)
    trigger: str          # "Tetikleyici: ..."
    brief: str            # 1–2 cümle beklenti özeti
    color: str            # "green" | "yellow" | "red"
    thresholds: tuple[str, ...] = ()  # 2-3 kısa eşik chip: "BTC >$80k", "VIX <20"


@dataclass(frozen=True)
class FlipCondition:
    """Kararı değiştirecek koşullar seti."""
    direction: str                 # "AL" | "KÜÇÜLT" | "KAPAT" | "BEKLE"
    label: str                     # "AL'a Geçiş Koşulları" vb.
    icon: str                      # "up" | "down" | "neutral"
    conditions: tuple[str, ...]    # 5 maddelik koşul listesi


@dataclass(frozen=True)
class RegimeReport:
    generated_at: str
    execution_mode: str

    # Katman 1
    macro_layer: MacroLayer

    # Katman 2
    appetite_layer: RiskAppetiteLayer

    # Katman 3
    asset_signals: tuple[AssetSignal, ...]
    confirmation_checklist: tuple[ConfirmationItem, ...]

    # Katman 4
    decision: Decision
    owner_action: str
    verdict: str

    # Senaryo motoru
    scenarios: tuple[Scenario, ...]

    # Asimetri göstergesi
    asymmetry: AsymmetrySignal

    # Operasyonel adımlar (5 madde, karara özel)
    owner_actions: tuple[str, ...]

    # Kararı değiştirecek koşullar (AL / KÜÇÜLT yönleri)
    flip_conditions: tuple[FlipCondition, ...]

    # Haberler
    news_headlines: tuple[NewsHeadline, ...]

    # Yaklaşan katalizörler
    upcoming_catalysts: tuple[CatalystEvent, ...]

    # Özet istatistik
    blocking_count: int
    confirmed_count: int
    pending_count: int

    # Teknik analiz (OHLCV bazlı dinamik seviyeler) — default = () yeni alanlar için
    tech_insights: tuple[TechnicalInsight, ...] = ()


# ---------------------------------------------------------------------------
# Thresholds — config/thresholds.yaml'dan yüklenir (fallback hardcoded)
# Değiştirmek için: config/thresholds.yaml düzenle, backend'i yeniden başlat.
# ---------------------------------------------------------------------------

def _t(section: str, key: str, default: float) -> float:
    """_THR dict'inden güvenli okuma; YAML yoksa fallback kullan."""
    return float((_THR.get(section) or {}).get(key, default))

_DXY_STRONG = _t("dxy", "strong", 104.0)
_DXY_WEAK   = _t("dxy", "weak",   99.0)

_BRENT_HIGH  = _t("brent", "high", 100.0)
_BRENT_WARN  = _t("brent", "warn",  85.0)

_YIELD_INVERSION = _t("yield_curve", "inversion", 0.0)
_YIELD_FLAT      = _t("yield_curve", "flat",       0.3)

_M2_EXPANDING = _t("m2", "expanding", 21_500.0)
_M2_SHRINKING = _t("m2", "shrinking", 20_500.0)

_HYG_HEALTHY  = _t("hyg", "healthy",  78.0)
_HYG_BREAKING = _t("hyg", "breaking", 74.0)

_BTCD_DOMINANT = _t("btc_dominance", "dominant", 52.0)
_BTCD_PANIC    = _t("btc_dominance", "panic",    40.0)

_USDTD_SAFE   = _t("usdt_dominance", "safe",   5.0)
_USDTD_FLIGHT = _t("usdt_dominance", "flight", 7.5)

_BTC_STRONG = _t("btc", "strong", 70_000.0)
_BTC_WATCH  = _t("btc", "watch",  58_000.0)
_BTC_WEAK   = _t("btc", "weak",   48_000.0)

_XAUUSD_BREAKOUT = _t("xauusd", "breakout", 3_800.0)
_XAGUSD_CONFIRM  = _t("xagusd", "confirm",     62.0)
_XAUXAG_HIGH     = _t("xauxag", "high",         68.0)
_XAUXAG_CRISIS   = _t("xauxag", "crisis",        90.0)

_XCUUSD_HEALTHY = _t("xcuusd", "healthy", 12_000.0)

_SP500_STRONG = _t("sp500", "strong", 6_800.0)
_SP500_WARN   = _t("sp500", "warn",   6_000.0)
_SP500_BLOCK  = _t("sp500", "block",  5_200.0)

_TOTAL_BULL  = _t("total",  "bull", 2_200.0)
_TOTAL_WARN  = _t("total",  "warn", 1_800.0)
_TOTAL2_BULL = _t("total2", "bull", 1_000.0)
_TOTAL2_WARN = _t("total2", "warn",   750.0)

_FXI_STRONG = _t("fxi", "strong", 35.0)
_FXI_WEAK   = _t("fxi", "weak",   29.0)

_VIX_CALM     = _t("vix", "calm",     20.0)
_VIX_ELEVATED = _t("vix", "elevated", 25.0)
_VIX_FEAR     = _t("vix", "fear",     30.0)
_VIX_PANIC    = _t("vix", "panic",    40.0)

_REAL_YIELD_DOVISH  = _t("real_yield", "dovish",  0.5)
_REAL_YIELD_NEUTRAL = _t("real_yield", "neutral", 1.5)
_REAL_YIELD_HAWKISH = _t("real_yield", "hawkish", 2.5)

_HY_SPREAD_HEALTHY = _t("hy_spread", "healthy",  4.0)
_HY_SPREAD_WARN    = _t("hy_spread", "warn",      5.5)
_HY_SPREAD_STRESS  = _t("hy_spread", "stress",    7.5)
_HY_SPREAD_CRISIS  = _t("hy_spread", "crisis",   10.0)

_ETH_STRONG = _t("eth", "strong", 2_500.0)
_ETH_WATCH  = _t("eth", "watch",  1_800.0)
_ETH_WEAK   = _t("eth", "weak",   1_200.0)

_IWM_HEALTHY  = _t("iwm", "healthy",  265.0)
_IWM_NARROW   = _t("iwm", "narrow",   240.0)
_IWM_BLOCKING = _t("iwm", "blocking", 210.0)

_LQD_HEALTHY = _t("lqd", "healthy", 108.0)
_LQD_STRESS  = _t("lqd", "stress",  103.0)
_LQD_CRISIS  = _t("lqd", "crisis",   97.0)

_SMH_STRONG = _t("smh", "strong", 520.0)
_SMH_WARN   = _t("smh", "warn",   430.0)
_SMH_WEAK   = _t("smh", "weak",   350.0)

_XLF_HEALTHY  = _t("xlf", "healthy",  50.0)
_XLF_STRESS   = _t("xlf", "stress",   44.0)
_XLF_BLOCKING = _t("xlf", "blocking", 38.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _val(snapshots: dict[AssetCode, MarketSnapshot], code: AssetCode) -> float | None:
    snap = snapshots.get(code)
    return snap.value if snap is not None else None


def _unit(snapshots: dict[AssetCode, MarketSnapshot], code: AssetCode) -> str:
    snap = snapshots.get(code)
    return snap.unit if snap is not None else "N/A"


def _fmt(v: float | None, decimals: int = 2) -> str:
    if v is None:
        return "N/A"
    if v > 10_000:
        return f"{v:,.0f}"
    return f"{v:,.{decimals}f}"


# ---------------------------------------------------------------------------
# Katman 1 — Makro Rejim
# ---------------------------------------------------------------------------

def _analyze_macro(snapshots: dict[AssetCode, MarketSnapshot]) -> MacroLayer:
    dxy        = _val(snapshots, AssetCode.DXY)
    brent      = _val(snapshots, AssetCode.BRENT)
    us10y      = _val(snapshots, AssetCode.US10Y)
    us02y      = _val(snapshots, AssetCode.US02Y)
    m2         = _val(snapshots, AssetCode.M2SL)
    real_yield = _val(snapshots, AssetCode.REAL_YIELD)
    uscpi      = _val(snapshots, AssetCode.USCPI)

    # DXY
    if dxy is None:
        dxy_signal = "VERİ YOK"
        dxy_score = 0
    elif dxy > _DXY_STRONG:
        dxy_signal = f"GÜÇLÜ ({_fmt(dxy)}) — global likidite sıkışıyor"
        dxy_score = -2
    elif dxy < _DXY_WEAK:
        dxy_signal = f"ZAYIF ({_fmt(dxy)}) — likidite açılıyor, risk varlıklarına olumlu"
        dxy_score = 2
    else:
        dxy_signal = f"NÖTR ({_fmt(dxy)}) — belirgin baskı yok"
        dxy_score = 0

    # Brent
    if brent is None:
        energy_signal = "VERİ YOK"
        energy_score = 0
    elif brent > _BRENT_HIGH:
        energy_signal = f"YÜKSEK ({_fmt(brent)} $) — jeopolitik prim aktif, rotasyon erken"
        energy_score = -2
    elif brent > _BRENT_WARN:
        energy_signal = f"İZLE ({_fmt(brent)} $) — prim devam ediyor, teyit bekle"
        energy_score = -1
    else:
        energy_signal = f"NORMAL ({_fmt(brent)} $) — enerji baskısı azaldı"
        energy_score = 1

    # Yield curve
    if us10y is None or us02y is None:
        yield_signal = "VERİ YOK"
        yield_score = 0
    else:
        spread = round(us10y - us02y, 2)
        if spread < _YIELD_INVERSION:
            yield_signal = f"İNVERSİYON (10Y-2Y={spread:+.2f}) — resesyon baskısı aktif"
            yield_score = -2
        elif spread < _YIELD_FLAT:
            yield_signal = f"DÜZLEŞME (10Y-2Y={spread:+.2f}) — dikkat gerekiyor"
            yield_score = -1
        else:
            yield_signal = f"NORMAL (10Y-2Y={spread:+.2f}) — eğri sağlıklı"
            yield_score = 1

    # M2
    if m2 is None:
        m2_signal = "VERİ YOK"
        m2_score = 0
    elif m2 > _M2_EXPANDING:
        m2_signal = f"GENİŞLİYOR ({_fmt(m2)} B$) — para sisteme giriyor"
        m2_score = 2
    elif m2 < _M2_SHRINKING:
        m2_signal = f"DARALIYOR ({_fmt(m2)} B$) — likidite çekilimi devam ediyor"
        m2_score = -1
    else:
        m2_signal = f"YATAY ({_fmt(m2)} B$) — belirgin yön yok"
        m2_score = 0

    # Real yield (±1 ağırlık — refinement, rewriting etmeden ekle)
    if real_yield is None:
        ry_score = 0
    elif real_yield < _REAL_YIELD_DOVISH:
        ry_score = 1   # ucuz para, risk-on
    elif real_yield > _REAL_YIELD_HAWKISH:
        ry_score = -1  # yüksek reel faiz, büyüme baskıda
    else:
        ry_score = 0

    # USCPI enflasyon baskısı (±1)
    if uscpi is None:
        cpi_score = 0
    elif uscpi > 4.5:
        cpi_score = -1  # fed agresif
    elif uscpi >= 1.5:
        cpi_score = 0   # nötr / hedef civarı
    else:
        cpi_score = 0

    total = dxy_score + energy_score + yield_score + m2_score + ry_score + cpi_score
    if total >= 5:
        regime: RegimeCode = "RISK_ON"
        conf = 85
        summary = "Makro koşullar risk almayı destekliyor."
    elif total >= 1:
        regime = "TRANSITIONING"
        conf = 60
        summary = "Makro geçiş halinde — bazı sinyaller olumlu, bazıları olumsuz."
    elif total >= -2:
        regime = "DEFENSIVE"
        conf = 65
        summary = "Makro koşullar savunmacı duruşu zorunlu kılıyor."
    else:
        regime = "CRISIS"
        conf = 80
        summary = "Birden fazla makro baskı aynı anda aktif — kriz uyarısı."

    return MacroLayer(
        regime=regime,
        confidence_pct=conf,
        dxy_signal=dxy_signal,
        energy_signal=energy_signal,
        yield_curve_signal=yield_signal,
        m2_signal=m2_signal,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Katman 2 — Risk İştahı
# ---------------------------------------------------------------------------

def _analyze_appetite(snapshots: dict[AssetCode, MarketSnapshot]) -> RiskAppetiteLayer:
    hyg       = _val(snapshots, AssetCode.HYG)
    jnk       = _val(snapshots, AssetCode.JNK)
    btcd      = _val(snapshots, AssetCode.BTC_DOMINANCE)
    usdtd     = _val(snapshots, AssetCode.USDT_DOMINANCE)
    gold      = _val(snapshots, AssetCode.XAUUSD)
    qqq       = _val(snapshots, AssetCode.QQQ)
    vix       = _val(snapshots, AssetCode.VIX)
    hy_spread = _val(snapshots, AssetCode.HY_SPREAD)
    lqd       = _val(snapshots, AssetCode.LQD)

    # Credit
    credit_val = hyg if hyg is not None else jnk
    if credit_val is None:
        credit_signal = "VERİ YOK"
        credit_score = 0
    elif credit_val > _HYG_HEALTHY:
        credit_signal = f"SAĞLAM ({_fmt(credit_val)}) — sistemik panik yok, kredi piyasası tutuyor"
        credit_score = 2
    elif credit_val > _HYG_BREAKING:
        credit_signal = f"GERİLİYOR ({_fmt(credit_val)}) — kredi baskısı başlıyor, izle"
        credit_score = -1
    else:
        credit_signal = f"KIRIYOR ({_fmt(credit_val)}) — kredi stresi ciddi"
        credit_score = -3

    # BTC Dominance
    if btcd is None:
        btcd_signal = "VERİ YOK"
        btcd_score = 0
    elif btcd > _BTCD_DOMINANT:
        btcd_signal = f"BTC LIDER (%{_fmt(btcd)}) — piyasa BTC'ye sığınıyor, altcoin'ler daha kötü"
        btcd_score = 0  # neutral — not necessarily good
    elif btcd < _BTCD_PANIC:
        btcd_signal = f"KRİTİK DÜŞÜK (%{_fmt(btcd)}) — altcoin sezonu veya piyasa kaçışı"
        btcd_score = -2
    else:
        btcd_signal = f"NÖTR (%{_fmt(btcd)}) — BTC piyasaya liderlik ediyor"
        btcd_score = 1

    # USDT Dominance
    if usdtd is None:
        usdt_signal = "VERİ YOK"
        usdt_score = 0
    elif usdtd > _USDTD_FLIGHT:
        usdt_signal = f"KAÇIŞ (%{_fmt(usdtd)}) — kripto'dan stablecoin'e geçiş güçlü"
        usdt_score = -2
    elif usdtd > _USDTD_SAFE:
        usdt_signal = f"İZLE (%{_fmt(usdtd)}) — hafif kaçış eğilimi"
        usdt_score = -1
    else:
        usdt_signal = f"NORMAL (%{_fmt(usdtd)}) — para kripto'ya akıyor"
        usdt_score = 2

    # Gold vs Equities correlation
    if gold is None or qqq is None:
        haven_signal = "VERİ YOK"
        haven_score = 0
    elif gold > _XAUUSD_BREAKOUT and qqq < 450:
        haven_signal = f"GÜVENLI LIMAN (XAUUSD={_fmt(gold)}, QQQ={_fmt(qqq)}) — kaçış talebi var"
        haven_score = -2
    elif gold > _XAUUSD_BREAKOUT:
        haven_signal = f"HEDGE TALEBİ (XAUUSD={_fmt(gold)}) — altın güçlü ama equities hâlâ tutuyor"
        haven_score = -1
    else:
        haven_signal = f"NÖTR (XAUUSD={_fmt(gold)}, QQQ={_fmt(qqq)}) — korelasyon anormal değil"
        haven_score = 1

    # VIX — volatilite / korku (±2)
    if vix is None:
        vix_score = 0
    elif vix < _VIX_CALM:
        vix_score = 2    # piyasa sakin
    elif vix < _VIX_ELEVATED:
        vix_score = 0    # hafif dikkat
    elif vix < _VIX_FEAR:
        vix_score = -1   # korku başlıyor
    elif vix < _VIX_PANIC:
        vix_score = -2   # korku aktif
    else:
        vix_score = -3   # panik

    # HY Credit Spread — kredi stresi (±2)
    if hy_spread is None:
        hys_score = 0
    elif hy_spread < _HY_SPREAD_HEALTHY:
        hys_score = 2    # kredi sağlıklı
    elif hy_spread < _HY_SPREAD_WARN:
        hys_score = 0    # dikkat
    elif hy_spread < _HY_SPREAD_STRESS:
        hys_score = -2   # stres
    else:
        hys_score = -3   # kriz

    # LQD — investment grade kredi (±1)
    if lqd is None:
        lqd_score = 0
    elif lqd > _LQD_HEALTHY:
        lqd_score = 1    # IG kredi sağlıklı
    elif lqd < _LQD_CRISIS:
        lqd_score = -2   # sistemik stres
    else:
        lqd_score = 0

    total = credit_score + btcd_score + usdt_score + haven_score + vix_score + hys_score + lqd_score
    if total >= 7:
        status: AppetiteCode = "STRONG"
        summary = "Risk iştahı güçlü — piyasa risk almaya hazır."
    elif total >= 2:
        status = "MODERATE"
        summary = "Risk iştahı orta — bazı sinyaller destekliyor, bazıları uyarıyor."
    elif total >= -3:
        status = "WEAK"
        summary = "Risk iştahı zayıf — piyasa dikkatli, teyit olmadan adım atma."
    else:
        status = "CRISIS"
        summary = "Risk iştahı çökmüş — VIX/HY spread/kredi baskısı aynı anda aktif."

    return RiskAppetiteLayer(
        status=status,
        credit_signal=credit_signal,
        btc_dominance_signal=btcd_signal,
        usdt_dominance_signal=usdt_signal,
        safe_haven_signal=haven_signal,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Katman 3 — Asset Sinyalleri
# ---------------------------------------------------------------------------

def _tech_suffix(ti: "TechnicalInsight | None") -> str:
    """Teknik analizden kısa bir ek özet üretir (sinyal reason'ına eklenir)."""
    if ti is None:
        return ""
    lvl = ti.levels
    # Fiyata göre uygun hassasiyetle biçimlendir
    p = ti.current_price
    decimals = 0 if p > 100 else (2 if p > 1 else 4)
    fmt = lambda v: f"{v:,.{decimals}f}"  # noqa: E731
    parts = [
        f"S:{fmt(lvl.support)}",
        f"R:{fmt(lvl.resistance)}",
        f"ATR:{fmt(lvl.atr)} ({lvl.atr_pct:.1f}%)",
        ti.structure,
    ]
    if ti.rsi_14 is not None:
        parts.append(f"RSI:{ti.rsi_14:.0f}")
    return " [" + " · ".join(parts) + "]"


def _build_asset_signals(
    snapshots: dict[AssetCode, MarketSnapshot],
    delta_map: dict[str, float] | None = None,
    tech_map: dict[str, "TechnicalInsight"] | None = None,
) -> tuple[AssetSignal, ...]:
    signals:  list[AssetSignal] = []
    tech_map = tech_map or {}

    # Defansif sanity guard: drift cross-check çalışmasa bile asset-bound dışı
    # insight'ları filtrele. tech_map'in kendisini in-place yeniden bağla ki
    # _tech_suffix(tech_map.get("XAUUSD")) gibi aşağı çağrılar da korunsun.
    tech_map = {
        code: ti for code, ti in tech_map.items()
        if _is_insight_sane(code, ti.current_price, ti.levels.support, ti.levels.resistance)
    }

    # ── ATR-adaptive eşikler — tech_map varsa canlı seviyeler, yoksa sabitler ──
    _btc_ti    = tech_map.get("BTCUSD")
    _brent_ti  = tech_map.get("BRENT")
    _gold_ti   = tech_map.get("XAUUSD")
    _silver_ti = tech_map.get("XAGUSD")
    _copper_ti = tech_map.get("XCUUSD")

    dyn_btc_strong   = _btc_ti.levels.resistance  if _btc_ti    else _BTC_STRONG
    dyn_btc_watch    = _btc_ti.levels.support      if _btc_ti    else _BTC_WATCH
    dyn_btc_weak     = _btc_ti.levels.stop_loss    if _btc_ti    else _BTC_WEAK
    dyn_brent_high   = _brent_ti.levels.resistance if _brent_ti  else _BRENT_HIGH
    dyn_brent_warn   = _brent_ti.levels.support    if _brent_ti  else _BRENT_WARN
    dyn_xau_breakout = _gold_ti.levels.resistance  if _gold_ti   else _XAUUSD_BREAKOUT
    dyn_xag_confirm  = _silver_ti.levels.support   if _silver_ti else _XAGUSD_CONFIRM
    dyn_xcu_healthy  = _copper_ti.levels.support   if _copper_ti else _XCUUSD_HEALTHY

    btc   = _val(snapshots, AssetCode.BTCUSD)
    btcd  = _val(snapshots, AssetCode.BTC_DOMINANCE)
    usdtd = _val(snapshots, AssetCode.USDT_DOMINANCE)
    total = _val(snapshots, AssetCode.TOTAL)
    total2= _val(snapshots, AssetCode.TOTAL2)
    hyg   = _val(snapshots, AssetCode.HYG)
    dxy   = _val(snapshots, AssetCode.DXY)
    brent = _val(snapshots, AssetCode.BRENT)
    gold  = _val(snapshots, AssetCode.XAUUSD)
    silver= _val(snapshots, AssetCode.XAGUSD)
    copper= _val(snapshots, AssetCode.XCUUSD)
    qqq   = _val(snapshots, AssetCode.QQQ)
    us10y = _val(snapshots, AssetCode.US10Y)
    us02y = _val(snapshots, AssetCode.US02Y)

    # --- BTC — fiyat + tüm kripto yapısı arka planda değerlendirilir ---
    if btc is None:
        btc_status: SignalStatus = "VERİ_YOK"
        btc_reason = "BTC verisi yok."
    else:
        confirmations = 0
        chk = 6  # toplam kontrol sayısı (sabit base)

        # 1. Fiyat — dinamik direnç/destek seviyeleri
        if btc > dyn_btc_strong:
            confirmations += 1
            price_note = f"${_fmt(btc, 0)} direnç üstünde"
        elif btc < dyn_btc_weak:
            price_note = f"${_fmt(btc, 0)} stop altında"
        elif btc < dyn_btc_watch:
            price_note = f"${_fmt(btc, 0)} destek kırıldı"
        else:
            price_note = f"${_fmt(btc, 0)} destek-direnç arası"

        # 2. BTC Dominance
        if btcd is not None and btcd > _BTCD_DOMINANT:
            confirmations += 1
            btcd_note = f"D.%{_fmt(btcd)} dominant"
        elif btcd is not None and btcd < _BTCD_PANIC:
            btcd_note = f"D.%{_fmt(btcd)}↓ kritik"
        elif btcd is not None:
            btcd_note = f"D.%{_fmt(btcd)} nötr"
        else:
            btcd_note = "D:?"

        # 3. USDT Dominance
        if usdtd is not None and usdtd < _USDTD_SAFE:
            confirmations += 1
            usdt_note = f"USDT.D%{_fmt(usdtd)}↓ para akıyor"
        elif usdtd is not None and usdtd > _USDTD_FLIGHT:
            usdt_note = f"USDT.D%{_fmt(usdtd)}↑ kaçış"
        elif usdtd is not None:
            usdt_note = f"USDT.D%{_fmt(usdtd)} izle"
        else:
            usdt_note = "USDT.D:?"

        # 4. TOTAL market cap
        if total is not None and total > _TOTAL_BULL:
            confirmations += 1
            total_note = f"TOTAL:{_fmt(total/1000, 1)}T✓"
        elif total is not None:
            total_note = f"TOTAL:{_fmt(total/1000, 1)}T↓"
        else:
            total_note = ""

        # 5. TOTAL2 (altcoin yapısı)
        if total2 is not None and total2 > _TOTAL2_BULL:
            confirmations += 1
            total2_note = f"T2:{_fmt(total2/1000, 1)}T↑"
        elif total2 is not None:
            total2_note = f"T2:{_fmt(total2/1000, 1)}T yatay"
        else:
            total2_note = ""

        # 6. Kredi / HYG
        if hyg is not None and hyg > _HYG_HEALTHY:
            confirmations += 1

        # Ekstra: DXY
        if dxy is not None and dxy < _DXY_STRONG:
            confirmations += 1
            chk += 1

        ratio = confirmations / chk
        if ratio >= 0.75:
            btc_status = "CONFIRMED"
        elif ratio >= 0.5:
            btc_status = "PENDING"
        elif btc < dyn_btc_weak:
            btc_status = "BLOCKING"
        elif btc < dyn_btc_watch:
            btc_status = "BLOCKING"   # destek kırıldı
        else:
            btc_status = "PENDING"

        # Kompakt özet: fiyat + kripto yapısı tek satırda
        structure = " · ".join(p for p in [btcd_note, usdt_note, total_note, total2_note] if p)
        btc_reason = f"{price_note} — {structure}" + _tech_suffix(tech_map.get("BTCUSD"))

    if btc is None or btc_status == "VERİ_YOK":
        _btc_act: AssetActionType = "NEUTRAL"; _btc_trig = ""
    elif btc_status == "CONFIRMED":
        _btc_act = "LONG"; _btc_trig = "Teyitler güçlü — pozisyon kurulabilir"
    elif btc_status == "PENDING":
        _btc_act = "LONG_AWAIT"; _btc_trig = f"${_fmt(dyn_btc_strong, 0)} üzeri kapanış + D.>%55"
    elif btc_status == "BLOCKING":
        _btc_act = "AVOID"; _btc_trig = f"${_fmt(dyn_btc_watch, 0)} desteğinin geri kazanımı"
    else:
        _btc_act = "NEUTRAL"; _btc_trig = ""

    signals.append(AssetSignal(
        asset_code="BTCUSD",
        asset_name="Bitcoin",
        status=btc_status,
        reason=btc_reason,
        value=btc,
        unit="usd",
        asset_action=_btc_act,
        action_trigger=_btc_trig,
    ))

    # --- BRENT ---
    if brent is None:
        brent_status: SignalStatus = "VERİ_YOK"
        brent_reason = "Brent verisi yok."
    elif brent > dyn_brent_high:
        brent_status = "BLOCKING"
        brent_reason = f"Direnç üstünde (${_fmt(brent)}) — jeopolitik prim / enerji krizi aktif (R:${_fmt(dyn_brent_high)})"
    elif brent > dyn_brent_warn:
        brent_status = "PENDING"
        brent_reason = f"İzleme bölgesi (${_fmt(brent)}) — destek-direnç arası, kalıcı yön bekle"
    else:
        brent_status = "CONFIRMED"
        brent_reason = f"Destek altında (${_fmt(brent)}) — enerji baskısı azaldı, risk rotasyonu açık (S:${_fmt(dyn_brent_warn)})"

    brent_reason += _tech_suffix(tech_map.get("BRENT"))

    if brent is None or brent_status == "VERİ_YOK":
        _brent_act: AssetActionType = "NEUTRAL"; _brent_trig = ""
    elif brent_status == "BLOCKING":
        _brent_act = "AVOID"; _brent_trig = f"${_fmt(dyn_brent_high)} altına kalıcı gerileme"
    elif brent_status == "PENDING":
        _brent_act = "LONG_AWAIT"; _brent_trig = f"${_fmt(dyn_brent_high)} direnç kırılımı için izle"
    else:  # CONFIRMED — enerji baskısı azaldı
        _brent_act = "LONG"; _brent_trig = f"${_fmt(dyn_brent_warn)} desteği koruyorsa"

    signals.append(AssetSignal(
        asset_code="BRENT",
        asset_name="Brent Ham Petrol",
        status=brent_status,
        reason=brent_reason,
        value=brent,
        unit="usd/bbl",
        asset_action=_brent_act,
        action_trigger=_brent_trig,
    ))

    # --- ALTIN ---
    if gold is None:
        gold_status: SignalStatus = "VERİ_YOK"
        gold_reason = "Altın verisi yok."
    elif gold > dyn_xau_breakout:
        if us10y is not None and us02y is not None and (us10y - us02y) < 0:
            gold_status = "BLOCKING"
            gold_reason = f"Altın direnç kırdı (${_fmt(gold)}, R:${_fmt(dyn_xau_breakout)}) + yield inversiyonu — kriz modu"
        else:
            gold_status = "PENDING"
            gold_reason = f"Altın direnç üstünde (${_fmt(gold)}, R:${_fmt(dyn_xau_breakout)}) — hedge talebi, yön belirsiz"
    else:
        gold_status = "NEUTRAL"
        gold_reason = f"Altın destek-direnç aralığında (${_fmt(gold)}) — S:${_fmt(dyn_xau_breakout if _gold_ti is None else _gold_ti.levels.support)}"

    gold_reason += _tech_suffix(tech_map.get("XAUUSD"))

    if gold is None or gold_status == "VERİ_YOK":
        _gold_act: AssetActionType = "NEUTRAL"; _gold_trig = ""
    elif gold_status == "BLOCKING":  # kriz hedge modu
        _gold_act = "HOLD"; _gold_trig = "Kriz modu devam ederse hedge'i koru"
    elif gold_status == "PENDING":
        _gold_act = "LONG_AWAIT"; _gold_trig = f"${_fmt(dyn_xau_breakout)} üzeri kalıcı kapanış"
    else:
        _gold_act = "NEUTRAL"; _gold_trig = ""

    signals.append(AssetSignal(
        asset_code="XAUUSD",
        asset_name="Altın",
        status=gold_status,
        reason=gold_reason,
        value=gold,
        unit="usd/oz",
        asset_action=_gold_act,
        action_trigger=_gold_trig,
    ))

    # --- GÜMÜŞ ---
    if silver is None or gold is None:
        silver_status: SignalStatus = "VERİ_YOK"
        silver_reason = "Gümüş/Altın verisi yok."
    else:
        xauxag = gold / silver if silver > 0 else 999
        if silver > dyn_xag_confirm and copper is not None and copper > dyn_xcu_healthy:
            silver_status = "CONFIRMED"
            silver_reason = f"Gümüş destek üstünde (${_fmt(silver)}, S:${_fmt(dyn_xag_confirm)}) + bakır güçlü — metal rotasyonu"
        elif xauxag > _XAUXAG_HIGH:
            silver_status = "PENDING"
            silver_reason = f"Oran yüksek (Au/Ag={_fmt(xauxag, 0)}) — gümüş ucuz ama S:${_fmt(dyn_xag_confirm)} teyidi gelmedi"
        else:
            silver_status = "NEUTRAL"
            silver_reason = f"Gümüş nötr (${_fmt(silver)}, Au/Ag={_fmt(xauxag, 0)}, S:${_fmt(dyn_xag_confirm)})"

    silver_reason += _tech_suffix(tech_map.get("XAGUSD"))

    if silver is None or gold is None or silver_status == "VERİ_YOK":
        _silver_act: AssetActionType = "NEUTRAL"; _silver_trig = ""
    elif silver_status == "CONFIRMED":
        _silver_act = "LONG"; _silver_trig = "Bakır güçlü + destek korunuyor"
    elif silver_status == "PENDING":
        _silver_act = "LONG_AWAIT"; _silver_trig = f"${_fmt(dyn_xag_confirm)} destek + bakır teyidi"
    else:
        _silver_act = "NEUTRAL"; _silver_trig = ""

    signals.append(AssetSignal(
        asset_code="XAGUSD",
        asset_name="Gümüş",
        status=silver_status,
        reason=silver_reason,
        value=silver,
        unit="usd/oz",
        asset_action=_silver_act,
        action_trigger=_silver_trig,
    ))

    # --- HYG/JNK Kredi ---
    if hyg is None:
        hyg_status: SignalStatus = "VERİ_YOK"
        hyg_reason = "HYG verisi yok."
    elif hyg > _HYG_HEALTHY:
        hyg_status = "CONFIRMED"
        hyg_reason = f"HYG sağlam ({_fmt(hyg)}) — sistemik panik yok, kredi piyasası tutuyor"
    elif hyg > _HYG_BREAKING:
        hyg_status = "PENDING"
        hyg_reason = f"HYG geriliyor ({_fmt(hyg)}) — kredi baskısı izleniyor"
    else:
        hyg_status = "BLOCKING"
        hyg_reason = f"HYG kırılıyor ({_fmt(hyg)}) — kredi stresi kritik seviyede"

    if hyg_status == "BLOCKING":
        _hyg_act: AssetActionType = "AVOID"; _hyg_trig = "Kredi stresi normalleşmesi bekle"
    else:
        _hyg_act = "NEUTRAL"; _hyg_trig = ""

    signals.append(AssetSignal(
        asset_code="HYG",
        asset_name="HYG / Yüksek Getirili Tahvil",
        status=hyg_status,
        reason=hyg_reason,
        value=hyg,
        unit="usd/share",
        asset_action=_hyg_act,
        action_trigger=_hyg_trig,
    ))

    # --- QQQ / Nasdaq ---
    if qqq is None:
        qqq_status: SignalStatus = "VERİ_YOK"
        qqq_reason = "QQQ verisi yok."
    elif qqq > 480:
        qqq_status = "CONFIRMED"
        qqq_reason = f"QQQ güçlü ({_fmt(qqq)}) — teknoloji tarafı canlı"
    elif qqq > 430:
        qqq_status = "NEUTRAL"
        qqq_reason = f"QQQ izleme bölgesinde ({_fmt(qqq)}) — seçici ama çökmüş değil"
    else:
        qqq_status = "BLOCKING"
        qqq_reason = f"QQQ zayıf ({_fmt(qqq)}) — risk iştahı düşük"

    if qqq_status == "CONFIRMED":
        _qqq_act: AssetActionType = "LONG"; _qqq_trig = "Teknoloji momentum korunuyor"
    elif qqq_status == "NEUTRAL":
        _qqq_act = "HOLD"; _qqq_trig = "Mevcut pozisyon koru, yeni giriş yok"
    elif qqq_status == "BLOCKING":
        _qqq_act = "AVOID"; _qqq_trig = "$480 üzeri kapanış bekle"
    else:
        _qqq_act = "NEUTRAL"; _qqq_trig = ""

    signals.append(AssetSignal(
        asset_code="QQQ",
        asset_name="QQQ / Nasdaq ETF",
        status=qqq_status,
        reason=qqq_reason,
        value=qqq,
        unit="usd/share",
        asset_action=_qqq_act,
        action_trigger=_qqq_trig,
    ))

    # --- ALTIN/GÜMÜŞ ORANI (XAUXAG) — risk-off vs risk-on barometre ---
    if gold is None or silver is None or silver == 0:
        xauxag_status: SignalStatus = "VERİ_YOK"
        xauxag_reason = "Altın veya gümüş verisi yok."
        xauxag_val: float | None = None
    else:
        xauxag_val = round(gold / silver, 2)
        if xauxag_val > _XAUXAG_CRISIS:
            xauxag_status = "BLOCKING"
            xauxag_reason = f"KRİZ SEVİYESİ (oran={_fmt(xauxag_val, 0)}) — deflasyon korkusu, güvenli limana kaçış maksimum"
        elif xauxag_val > _XAUXAG_HIGH:
            xauxag_status = "PENDING"
            xauxag_reason = f"Risk-off bölgesi (oran={_fmt(xauxag_val, 0)}) — altın gümüşü eziyor, sanayi endişesi var"
        elif xauxag_val < 65.0:
            xauxag_status = "CONFIRMED"
            xauxag_reason = f"Metal rotasyonu (oran={_fmt(xauxag_val, 0)}) — gümüş/altın yaklaşıyor; sanayi talebi aktif. Risk-on kanıtı değil, endüstriyel aktivite sinyali"
        else:
            xauxag_status = "NEUTRAL"
            xauxag_reason = f"Normal bölge (oran={_fmt(xauxag_val, 0)}) — belirgin yönlü sinyal yok"

    if xauxag_val is None or xauxag_status == "VERİ_YOK":
        _xauxag_act: AssetActionType = "NEUTRAL"; _xauxag_trig = ""
    elif xauxag_status == "BLOCKING":  # kriz seviyesi, oran çok yüksek
        _xauxag_act = "AVOID"; _xauxag_trig = "Oran 90 altına gerileme"
    elif xauxag_status == "CONFIRMED":  # oran düşük, metal rotasyonu aktif
        _xauxag_act = "LONG"; _xauxag_trig = "Metal rotasyonu aktif — gümüş/altın long"
    else:
        _xauxag_act = "NEUTRAL"; _xauxag_trig = ""

    signals.append(AssetSignal(
        asset_code="XAUXAG",
        asset_name="Altın/Gümüş Oranı",
        status=xauxag_status,
        reason=xauxag_reason,
        value=xauxag_val,
        unit="ratio",
        asset_action=_xauxag_act,
        action_trigger=_xauxag_trig,
    ))

    # --- SP500 — Geniş ABD piyasası ---
    sp500 = _val(snapshots, AssetCode.SP500)
    if sp500 is None:
        sp500_status: SignalStatus = "VERİ_YOK"
        sp500_reason = "SP500 verisi yok."
    elif sp500 > _SP500_STRONG:
        sp500_status = "CONFIRMED"
        sp500_reason = f"Geniş piyasa güçlü ({_fmt(sp500, 0)}) — bull market sürüyor, breadth geniş"
    elif sp500 > _SP500_WARN:
        sp500_status = "NEUTRAL"
        sp500_reason = f"İzleme bölgesinde ({_fmt(sp500, 0)}) — trend kırılmadı, ivme düşüyor"
    elif sp500 > _SP500_BLOCK:
        sp500_status = "PENDING"
        sp500_reason = f"Zayıflama sinyali ({_fmt(sp500, 0)}) — ana destek testinde, kayıp izle"
    else:
        sp500_status = "BLOCKING"
        sp500_reason = f"Bear piyasası ({_fmt(sp500, 0)}) — geniş satış baskısı aktif, giriş yapma"

    if sp500 is None or sp500_status == "VERİ_YOK":
        _sp500_act: AssetActionType = "NEUTRAL"; _sp500_trig = ""
    elif sp500_status == "CONFIRMED":
        _sp500_act = "LONG"; _sp500_trig = "Geniş piyasa güçlü — mevcut pozisyon koru"
    elif sp500_status == "NEUTRAL":
        _sp500_act = "HOLD"; _sp500_trig = "Trend kırılmadı, ivme izle"
    elif sp500_status == "PENDING":
        _sp500_act = "LONG_AWAIT"; _sp500_trig = f"${_fmt(_SP500_WARN, 0)} desteği korunması"
    else:  # BLOCKING
        _sp500_act = "AVOID"; _sp500_trig = "Bear piyasası — nakit koru"

    signals.append(AssetSignal(
        asset_code="SP500",
        asset_name="S&P 500",
        status=sp500_status,
        reason=sp500_reason,
        value=sp500,
        unit="index_points",
        asset_action=_sp500_act,
        action_trigger=_sp500_trig,
    ))

    # BTC.D, USDT.D, TOTAL, TOTAL2 — arka planda BTC sinyalini besler, standalone kart yok

    # --- DXY — Dolar Endeksi (standalone kart) ---
    if dxy is not None:
        if dxy > _DXY_STRONG:
            dxy_card_status: SignalStatus = "BLOCKING"
            dxy_card_reason = f"Dolar güçlü ({_fmt(dxy)}) — global likidite sıkışıyor, BTC/altın/gelişen piyasalar baskı altında"
        elif dxy < _DXY_WEAK:
            dxy_card_status = "CONFIRMED"
            dxy_card_reason = f"Dolar zayıf ({_fmt(dxy)}) — likidite açılıyor, risk varlıkları için uygun zemin"
        else:
            dxy_card_status = "NEUTRAL"
            dxy_card_reason = f"DXY nötr ({_fmt(dxy)}) — belirgin yönlü baskı yok"

        if dxy_card_status == "BLOCKING":  # dolar güçlü = risk-off baskısı
            _dxy_act: AssetActionType = "AVOID"; _dxy_trig = f"{_fmt(_DXY_STRONG)} altına gerileme"
        elif dxy_card_status == "CONFIRMED":  # dolar zayıf = risk varlıkları için zemin
            _dxy_act = "LONG"; _dxy_trig = "Risk varlıkları için zemin hazır"
        else:
            _dxy_act = "NEUTRAL"; _dxy_trig = ""

        signals.append(AssetSignal(
            asset_code="DXY",
            asset_name="Dolar Endeksi",
            status=dxy_card_status,
            reason=dxy_card_reason,
            value=dxy,
            unit="index_points",
            asset_action=_dxy_act,
            action_trigger=_dxy_trig,
        ))

    # --- XCUUSD — Bakır (standalone kart, endüstriyel talep barometresi) ---
    if copper is not None:
        # HG=F (COMEX) $/lb × 2204.623 = $/ton — birim: usd_per_tonne
        _cu_per_lb = copper / 2_204.623
        copper_threshold_low = dyn_xcu_healthy * 0.85
        if copper > dyn_xcu_healthy:
            copper_card_status: SignalStatus = "CONFIRMED"
            copper_card_reason = f"Bakır destek üstünde ({_fmt(copper, 0)}/ton ≈ ${_cu_per_lb:.2f}/lb COMEX, S:{_fmt(dyn_xcu_healthy, 0)}) — endüstriyel talep güçlü"
        elif copper > copper_threshold_low:
            copper_card_status = "NEUTRAL"
            copper_card_reason = f"Bakır destek bölgesinde ({_fmt(copper, 0)}/ton ≈ ${_cu_per_lb:.2f}/lb, S:{_fmt(dyn_xcu_healthy, 0)}) — izleme"
        else:
            copper_card_status = "PENDING"
            copper_card_reason = f"Bakır destek altında ({_fmt(copper, 0)}/ton ≈ ${_cu_per_lb:.2f}/lb, S:{_fmt(dyn_xcu_healthy, 0)}) — sanayi yavaşlama sinyali"

        copper_card_reason += _tech_suffix(tech_map.get("XCUUSD"))

        if copper_card_status == "CONFIRMED":
            _cu_act: AssetActionType = "LONG"; _cu_trig = "Endüstriyel talep güçlü"
        elif copper_card_status == "PENDING":
            _cu_act = "LONG_AWAIT"; _cu_trig = f"${_fmt(dyn_xcu_healthy, 0)}/ton destek korunması"
        else:
            _cu_act = "NEUTRAL"; _cu_trig = ""

        signals.append(AssetSignal(
            asset_code="XCUUSD",
            asset_name="Bakır",
            status=copper_card_status,
            reason=copper_card_reason,
            value=copper,
            unit="usd_per_tonne",
            asset_action=_cu_act,
            action_trigger=_cu_trig,
        ))

    # --- VIX — Korku / Volatilite ---
    vix = _val(snapshots, AssetCode.VIX)
    if vix is None:
        vix_card_status: SignalStatus = "VERİ_YOK"
        vix_card_reason = "VIX verisi yok."
    elif vix < _VIX_CALM:
        vix_card_status = "CONFIRMED"
        vix_card_reason = f"Piyasa sakin ({_fmt(vix)}) — korku düşük, risk-on ortam korunuyor"
    elif vix < _VIX_ELEVATED:
        vix_card_status = "NEUTRAL"
        vix_card_reason = f"Hafif dikkat ({_fmt(vix)}) — nötr bölge, belirgin panik yok"
    elif vix < _VIX_FEAR:
        vix_card_status = "PENDING"
        vix_card_reason = f"Korku başlıyor ({_fmt(vix)}) — piyasa tedirgin, pozisyon küçült"
    elif vix < _VIX_PANIC:
        vix_card_status = "BLOCKING"
        vix_card_reason = f"Korku aktif ({_fmt(vix)}) — risk iştahı çöküyor, yeni giriş yapma"
    else:
        vix_card_status = "BLOCKING"
        vix_card_reason = f"PANİK ({_fmt(vix)}) — kriz seviyesi, 2020/2008 benzeri dağılma riski"

    if vix_card_status == "CONFIRMED":
        _vix_act: AssetActionType = "LONG"; _vix_trig = "Korku düşük — risk-on devam ediyor"
    elif vix_card_status == "NEUTRAL":
        _vix_act = "NEUTRAL"; _vix_trig = ""
    elif vix_card_status == "PENDING":
        _vix_act = "LONG_AWAIT"; _vix_trig = f"VIX < {_VIX_CALM:.0f} kalıcı kapanış"
    else:  # BLOCKING
        _vix_act = "AVOID"; _vix_trig = "Korku seviyesi düşene kadar bekle"

    signals.append(AssetSignal(
        asset_code="VIX", asset_name="VIX / Korku Endeksi",
        status=vix_card_status, reason=vix_card_reason,
        value=vix, unit="index_points",
        asset_action=_vix_act, action_trigger=_vix_trig,
    ))

    # --- REAL_YIELD — Reel Faiz (10Y TIPS) ---
    real_yield = _val(snapshots, AssetCode.REAL_YIELD)
    if real_yield is None:
        ry_status: SignalStatus = "VERİ_YOK"
        ry_reason = "TIPS reel faiz verisi yok."
    elif real_yield < _REAL_YIELD_DOVISH:
        ry_status = "CONFIRMED"
        ry_reason = f"Reel faiz düşük (%{_fmt(real_yield)}) — para ucuz, büyüme/kripto/altın pozitif"
    elif real_yield > _REAL_YIELD_HAWKISH:
        ry_status = "BLOCKING"
        ry_reason = f"Reel faiz yüksek (%{_fmt(real_yield)}) — büyüme varlıkları baskıda, altın/kripto dezavantajlı"
    else:
        ry_status = "NEUTRAL"
        ry_reason = f"Reel faiz nötr bölge (%{_fmt(real_yield)}) — belirgin yönlü baskı yok"

    if ry_status == "CONFIRMED":
        _ry_act: AssetActionType = "LONG"; _ry_trig = "Para ucuz — büyüme varlıkları için pozitif"
    elif ry_status == "BLOCKING":
        _ry_act = "AVOID"; _ry_trig = f"Reel faiz < %{_REAL_YIELD_HAWKISH} gerileme"
    else:
        _ry_act = "NEUTRAL"; _ry_trig = ""

    signals.append(AssetSignal(
        asset_code="REAL_YIELD", asset_name="Reel Faiz (10Y TIPS)",
        status=ry_status, reason=ry_reason,
        value=real_yield, unit="yield_percent",
        asset_action=_ry_act, action_trigger=_ry_trig,
    ))

    # --- HY_SPREAD — HY Kredi Spreadi (ICE BofA OAS) ---
    hy_spread = _val(snapshots, AssetCode.HY_SPREAD)
    if hy_spread is None:
        hys_status: SignalStatus = "VERİ_YOK"
        hys_reason = "HY spread verisi yok."
    elif hy_spread < _HY_SPREAD_HEALTHY:
        hys_status = "CONFIRMED"
        hys_reason = f"Spread sıkı (%{_fmt(hy_spread)}) — piyasa şirket riskini fiyatlamıyor, kredi rahat"
    elif hy_spread < _HY_SPREAD_WARN:
        hys_status = "NEUTRAL"
        hys_reason = f"Spread normal (%{_fmt(hy_spread)}) — izleme bölgesi"
    elif hy_spread < _HY_SPREAD_STRESS:
        hys_status = "PENDING"
        hys_reason = f"Spread genişliyor (%{_fmt(hy_spread)}) — kredi koşulları sıkışıyor"
    elif hy_spread < _HY_SPREAD_CRISIS:
        hys_status = "BLOCKING"
        hys_reason = f"Kredi stresi (%{_fmt(hy_spread)}) — junk borçlanma pahalılaşıyor, yeni giriş yok"
    else:
        hys_status = "BLOCKING"
        hys_reason = f"KRİZ SPREAD (%{_fmt(hy_spread)}) — 2008/2020 seviyesi, sistemik risk"

    if hys_status == "CONFIRMED":
        _hys_act: AssetActionType = "LONG"; _hys_trig = "Kredi piyasası rahat"
    elif hys_status == "BLOCKING":
        _hys_act = "AVOID"; _hys_trig = "Kredi stresi normalleşmesi bekle"
    else:
        _hys_act = "NEUTRAL"; _hys_trig = ""

    signals.append(AssetSignal(
        asset_code="HY_SPREAD", asset_name="HY Kredi Spreadi",
        status=hys_status, reason=hys_reason,
        value=hy_spread, unit="spread_percent",
        asset_action=_hys_act, action_trigger=_hys_trig,
    ))

    # --- ETHUSD — Ethereum ---
    eth = _val(snapshots, AssetCode.ETHUSD)
    if eth is None:
        eth_status: SignalStatus = "VERİ_YOK"
        eth_reason = "ETH verisi yok."
    else:
        # ETH/BTC ratio için BTC kullan
        eth_btc_note = ""
        if btc is not None and btc > 0:
            eth_btc = round(eth / btc, 4)
            if eth_btc > 0.065:
                eth_btc_note = f" · ETH/BTC={eth_btc:.3f}↑ altcoin sezonu kapıda"
            elif eth_btc < 0.040:
                eth_btc_note = f" · ETH/BTC={eth_btc:.3f}↓ BTC dominant"
            else:
                eth_btc_note = f" · ETH/BTC={eth_btc:.3f}"

        if eth > _ETH_STRONG:
            eth_status = "CONFIRMED"
            eth_reason = f"ETH güçlü (${_fmt(eth, 0)}){eth_btc_note} — altcoin risk iştahı açık"
        elif eth > _ETH_WATCH:
            eth_status = "NEUTRAL"
            eth_reason = f"ETH izleme (${_fmt(eth, 0)}){eth_btc_note} — momentum nötr"
        elif eth > _ETH_WEAK:
            eth_status = "PENDING"
            eth_reason = f"ETH zayıf (${_fmt(eth, 0)}){eth_btc_note} — altcoin risk iştahı düşük"
        else:
            eth_status = "BLOCKING"
            eth_reason = f"ETH çöküyor (${_fmt(eth, 0)}){eth_btc_note} — kripto geneli risk-off"

    if eth is None or eth_status == "VERİ_YOK":
        _eth_act: AssetActionType = "NEUTRAL"; _eth_trig = ""
    elif eth_status == "CONFIRMED":
        _eth_act = "LONG"; _eth_trig = "Altcoin risk iştahı açık"
    elif eth_status == "NEUTRAL":
        _eth_act = "NEUTRAL"; _eth_trig = ""
    elif eth_status == "PENDING":
        _eth_act = "LONG_AWAIT"; _eth_trig = f"${_fmt(_ETH_WATCH, 0)} üzeri kalıcı kapanış"
    else:  # BLOCKING
        _eth_act = "AVOID"; _eth_trig = f"${_fmt(_ETH_WATCH, 0)} destek geri kazanımı"

    signals.append(AssetSignal(
        asset_code="ETHUSD", asset_name="Ethereum",
        status=eth_status, reason=eth_reason,
        value=eth, unit="usd_per_eth",
        asset_action=_eth_act, action_trigger=_eth_trig,
    ))

    # --- IWM — Russell 2000 (Piyasa Genişliği) ---
    iwm = _val(snapshots, AssetCode.IWM)
    if iwm is None:
        iwm_status: SignalStatus = "VERİ_YOK"
        iwm_reason = "IWM verisi yok."
    elif iwm > _IWM_HEALTHY:
        iwm_status = "CONFIRMED"
        iwm_reason = f"Small cap güçlü (${_fmt(iwm)}) — piyasa genişliği sağlıklı, rally kırılgan değil"
    elif iwm > _IWM_NARROW:
        iwm_status = "NEUTRAL"
        iwm_reason = f"Small cap yatay (${_fmt(iwm)}) — büyük-küçük şirket ayrışması başlıyor"
    elif iwm > _IWM_BLOCKING:
        iwm_status = "PENDING"
        iwm_reason = f"Breadth daralıyor (${_fmt(iwm)}) — rally mega-cap'e sıkıştı, kırılgan sinyal"
    else:
        iwm_status = "BLOCKING"
        iwm_reason = f"Small cap bear (${_fmt(iwm)}) — geniş piyasa katılımı çökmüş, sadece büyükler tutuyor"

    if iwm_status == "CONFIRMED":
        _iwm_act: AssetActionType = "LONG"; _iwm_trig = "Piyasa genişliği sağlıklı"
    elif iwm_status == "NEUTRAL":
        _iwm_act = "HOLD"; _iwm_trig = ""
    elif iwm_status == "PENDING":
        _iwm_act = "LONG_AWAIT"; _iwm_trig = f"${_fmt(_IWM_NARROW)} üzeri kapanış"
    else:  # BLOCKING
        _iwm_act = "AVOID"; _iwm_trig = "Bear piyasası — uzak dur"

    signals.append(AssetSignal(
        asset_code="IWM", asset_name="IWM / Russell 2000",
        status=iwm_status, reason=iwm_reason,
        value=iwm, unit="usd_per_share",
        asset_action=_iwm_act, action_trigger=_iwm_trig,
    ))

    # --- LQD — Investment Grade Tahvil ---
    lqd = _val(snapshots, AssetCode.LQD)
    if lqd is None:
        lqd_status: SignalStatus = "VERİ_YOK"
        lqd_reason = "LQD verisi yok."
    elif lqd > _LQD_HEALTHY:
        lqd_status = "CONFIRMED"
        lqd_reason = f"IG kredi sağlıklı (${_fmt(lqd)}) — investment grade tahvil tutuyor, HYG'yi teyit ediyor"
    elif lqd > _LQD_STRESS:
        lqd_status = "NEUTRAL"
        lqd_reason = f"IG izleme (${_fmt(lqd)}) — kredi koşulları yavaş sıkışıyor"
    elif lqd > _LQD_CRISIS:
        lqd_status = "PENDING"
        lqd_reason = f"IG baskı altında (${_fmt(lqd)}) — sadece junk değil, genel kredi sıkışıyor"
    else:
        lqd_status = "BLOCKING"
        lqd_reason = f"Sistemik kredi korkusu (${_fmt(lqd)}) — IG + HYG birlikte düşüyor, büyük stres"

    signals.append(AssetSignal(
        asset_code="LQD", asset_name="LQD / IG Tahvil ETF",
        status=lqd_status, reason=lqd_reason,
        value=lqd, unit="usd_per_share",
        asset_action="AVOID" if lqd_status == "BLOCKING" else "NEUTRAL",
        action_trigger="IG kredi stresi normalleşmesi" if lqd_status == "BLOCKING" else "",
    ))

    # --- SMH — Yarı İletkenler (Tech Cycle Leading Indicator) ---
    smh = _val(snapshots, AssetCode.SMH)
    if smh is None:
        smh_status: SignalStatus = "VERİ_YOK"
        smh_reason = "SMH verisi yok."
    elif smh > _SMH_STRONG:
        smh_status = "CONFIRMED"
        smh_reason = f"Chip sektörü güçlü (${_fmt(smh)}) — tech cycle canlı, Nasdaq rallisi destekleniyor"
    elif smh > _SMH_WARN:
        smh_status = "NEUTRAL"
        smh_reason = f"Chip sektörü yatay (${_fmt(smh)}) — momentum düşüyor, yakından izle"
    elif smh > _SMH_WEAK:
        smh_status = "PENDING"
        smh_reason = f"Chip talebi zayıflayor (${_fmt(smh)}) — tech cycle dönüşü başlamış olabilir"
    else:
        smh_status = "BLOCKING"
        smh_reason = f"Chip bear (${_fmt(smh)}) — tech resesyon bölgesi, Nasdaq için öncü uyarı"

    signals.append(AssetSignal(
        asset_code="SMH", asset_name="SMH / Yarı İletkenler",
        status=smh_status, reason=smh_reason,
        value=smh, unit="usd_per_share",
        asset_action="LONG" if smh_status == "CONFIRMED" else ("AVOID" if smh_status == "BLOCKING" else "NEUTRAL"),
        action_trigger="Chip sektörü güçlü" if smh_status == "CONFIRMED" else ("Tech resesyon riski" if smh_status == "BLOCKING" else ""),
    ))

    # --- XLF — Finansallar ---
    xlf = _val(snapshots, AssetCode.XLF)
    if xlf is None:
        xlf_status: SignalStatus = "VERİ_YOK"
        xlf_reason = "XLF verisi yok."
    elif xlf > _XLF_HEALTHY:
        xlf_status = "CONFIRMED"
        xlf_reason = f"Bankacılık sağlıklı (${_fmt(xlf)}) — kredi koşulları normal, sistem tutuyor"
    elif xlf > _XLF_STRESS:
        xlf_status = "NEUTRAL"
        xlf_reason = f"Finansallar yatay (${_fmt(xlf)}) — banka sektörü nötr"
    elif xlf > _XLF_BLOCKING:
        xlf_status = "PENDING"
        xlf_status = "PENDING"
        xlf_reason = f"Banka stresi başlıyor (${_fmt(xlf)}) — kredi koşulları sıkışıyor, öncü uyarı"
    else:
        xlf_status = "BLOCKING"
        xlf_reason = f"Finansal sistem baskıda (${_fmt(xlf)}) — banka kırılganlığı, kredi daralması riski"

    signals.append(AssetSignal(
        asset_code="XLF", asset_name="XLF / Finansal Sektör",
        status=xlf_status, reason=xlf_reason,
        value=xlf, unit="usd_per_share",
        asset_action="LONG" if xlf_status == "CONFIRMED" else ("AVOID" if xlf_status == "BLOCKING" else "NEUTRAL"),
        action_trigger="Bankacılık sağlıklı" if xlf_status == "CONFIRMED" else ("Finansal sistem baskıda" if xlf_status == "BLOCKING" else ""),
    ))

    # --- FXI — Çin Büyük Şirket ETF ---
    fxi = _val(snapshots, AssetCode.FXI)
    if fxi is None:
        fxi_status: SignalStatus = "VERİ_YOK"
        fxi_reason = "FXI verisi yok."
    elif fxi > _FXI_STRONG:
        fxi_status = "CONFIRMED"
        fxi_reason = f"Çin sermaye girişi güçlü (${_fmt(fxi)}) — Çin varlıklarına talep artıyor, bakır/sanayi metal pozitif"
    elif fxi > _FXI_WEAK:
        fxi_status = "NEUTRAL"
        fxi_reason = f"Çin piyasası yatay (${_fmt(fxi)}) — belirgin trend yok"
    else:
        fxi_status = "PENDING"
        fxi_reason = f"Çin yavaşlama sinyali (${_fmt(fxi)}) — bakır ve sanayi metal talebi baskı altında"

    signals.append(AssetSignal(
        asset_code="FXI",
        asset_name="FXI / Çin Büyük Şirket ETF",
        status=fxi_status,
        reason=fxi_reason,
        value=fxi,
        unit="usd/share",
        asset_action="LONG" if fxi_status == "CONFIRMED" else ("LONG_AWAIT" if fxi_status == "NEUTRAL" else "NEUTRAL"),
        action_trigger="Çin sermaye girişi güçlü" if fxi_status == "CONFIRMED" else "",
    ))

    # Delta zenginleştirmesi — tüm sinyallere tek noktadan eklenir
    if delta_map:
        signals = [
            dataclasses.replace(s, delta_7d_pct=delta_map.get(s.asset_code))
            for s in signals
        ]

    # ── Controlled-Aggressive: paper trading'ten aggression_level + command çek ──
    # Sadece o asset için aktif bir pozisyon/pending/manual_ready varsa dolar;
    # hiçbir hard bağımlılık değil — paper_trading import edilemese sessiz pas geç.
    try:
        agg_map = _pull_aggression_from_paper_trading()
        if agg_map:
            signals = [
                (
                    dataclasses.replace(s, **agg_map[s.asset_code])
                    if s.asset_code in agg_map else s
                )
                for s in signals
            ]
    except Exception:
        pass

    return tuple(signals)


def _pull_aggression_from_paper_trading() -> dict[str, dict[str, Any]]:
    """Aktif paper trading state'inden pair → {aggression_level, agent_command,
    recommended_timeframe, stop_style, recheck_interval_minutes}.

    Sıralama: Position > PendingOpenOrder > ManualReadyTrade. Her birinin
    open_signal["aggression_context"] alanını okur.
    Hiçbir asset için kayıt yoksa boş dict döner.
    """
    try:
        from app.services.paper_trading_service import get_snapshot
    except Exception:
        return {}
    try:
        snap = get_snapshot()
    except Exception:
        return {}

    out: dict[str, dict[str, Any]] = {}

    def _extract(open_signal: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(open_signal, dict):
            return None
        agg = open_signal.get("aggression_context") or {}
        level = str(agg.get("aggression_level") or "")
        command = str(open_signal.get("agent_command") or "")
        if not level and not command:
            return None
        recommended_tf = str(agg.get("recommended_timeframe") or "")
        stop_style = str(agg.get("stop_style") or "")
        try:
            recheck_min = int(agg.get("recheck_interval_minutes") or 0)
        except (TypeError, ValueError):
            recheck_min = 0
        return {
            "aggression_level":         level,
            "agent_command":            command,
            "recommended_timeframe":    recommended_tf,
            "stop_style":               stop_style,
            "recheck_interval_minutes": recheck_min,
        }

    for pos in snap.get("open_positions") or []:
        info = _extract(pos.get("open_signal"))
        if info:
            out[pos.get("pair", "")] = info
    for pend in snap.get("pending_orders") or []:
        pair = pend.get("pair", "")
        if pair and pair not in out:
            info = _extract(pend.get("open_signal"))
            if info:
                out[pair] = info
    for mr in snap.get("manual_ready_trades") or []:
        pair = mr.get("pair", "")
        if pair and pair not in out:
            info = _extract(mr.get("open_signal"))
            if info:
                out[pair] = info

    return out


# ---------------------------------------------------------------------------
# Katman 3 — Teyit Listesi
# ---------------------------------------------------------------------------

def _build_confirmation_checklist(
    snapshots: dict[AssetCode, MarketSnapshot],
    tech_map: dict[str, "TechnicalInsight"] | None = None,
) -> tuple[ConfirmationItem, ...]:
    brent  = _val(snapshots, AssetCode.BRENT)
    gold   = _val(snapshots, AssetCode.XAUUSD)
    silver = _val(snapshots, AssetCode.XAGUSD)
    copper = _val(snapshots, AssetCode.XCUUSD)
    btc    = _val(snapshots, AssetCode.BTCUSD)
    us10y  = _val(snapshots, AssetCode.US10Y)
    us02y  = _val(snapshots, AssetCode.US02Y)
    dxy    = _val(snapshots, AssetCode.DXY)

    tm = tech_map or {}

    # ATR-adaptive checklist eşikleri
    _btc_ti    = tm.get("BTCUSD")
    _brent_ti  = tm.get("BRENT")
    _silver_ti = tm.get("XAGUSD")
    _copper_ti = tm.get("XCUUSD")
    _dxy_ti    = tm.get("DXY")

    cl_brent_high   = _brent_ti.levels.resistance  if _brent_ti  else _BRENT_HIGH
    cl_btc_watch    = _btc_ti.levels.support        if _btc_ti    else _BTC_WATCH
    cl_silver_conf  = _silver_ti.levels.support     if _silver_ti else _XAGUSD_CONFIRM
    cl_copper_hlthy = _copper_ti.levels.support     if _copper_ti else _XCUUSD_HEALTHY

    items: list[ConfirmationItem] = []

    # 1. Brent baskı altında mı?
    brent_met = brent is not None and brent < cl_brent_high
    items.append(ConfirmationItem(
        signal=f"Brent direnç altında (${_fmt(cl_brent_high)} altında)",
        met=brent_met,
        current_value=f"${_fmt(brent)}" if brent else "N/A",
        threshold=f"< ${_fmt(cl_brent_high)}",
    ))

    # 2. DXY sıkılaşma yok
    dxy_met = dxy is not None and dxy < _DXY_STRONG
    items.append(ConfirmationItem(
        signal=f"DXY dolar sıkılaşması yok ({int(_DXY_STRONG)} altında)",
        met=dxy_met,
        current_value=_fmt(dxy) if dxy else "N/A",
        threshold=f"< {int(_DXY_STRONG)}",
    ))

    # 3. BTC destek üstünde (dinamik swing seviyesi)
    btc_met = btc is not None and btc > cl_btc_watch
    items.append(ConfirmationItem(
        signal=f"BTC destek üstünde (${_fmt(cl_btc_watch, 0)} üzerinde)",
        met=btc_met,
        current_value=f"${_fmt(btc, 0)}" if btc else "N/A",
        threshold=f"> ${_fmt(cl_btc_watch, 0)}",
    ))

    # 4. Gümüş momentumu koruyor (dinamik destek)
    xauxag = (gold / silver) if (gold and silver and silver > 0) else None
    silver_met = silver is not None and silver > cl_silver_conf
    items.append(ConfirmationItem(
        signal=f"Gümüş destek üstünde (${_fmt(cl_silver_conf)} üzerinde)",
        met=silver_met,
        current_value=f"${_fmt(silver)} (Au/Ag={_fmt(xauxag, 0)})" if silver else "N/A",
        threshold=f"> ${_fmt(cl_silver_conf)}",
    ))

    # 5. Bakır endüstriyel talep sağlıklı (dinamik destek)
    copper_met = copper is not None and copper > cl_copper_hlthy
    items.append(ConfirmationItem(
        signal=f"Bakır destek üstünde (${_fmt(cl_copper_hlthy, 0)}/ton üzerinde)",
        met=copper_met,
        current_value=f"${_fmt(copper, 0)}" if copper else "N/A",
        threshold=f"> ${_fmt(cl_copper_hlthy, 0)}",
    ))

    # 6. Yield curve inversiyonu çözüldü
    if us10y is not None and us02y is not None:
        spread = us10y - us02y
        yield_met = spread >= 0
        yield_current = f"10Y-2Y = {spread:+.2f}%"
    else:
        yield_met = False
        yield_current = "N/A"
    items.append(ConfirmationItem(
        signal="Yield curve inversiyonu çözülüyor (10Y > 2Y)",
        met=yield_met,
        current_value=yield_current,
        threshold=">= 0",
    ))

    return tuple(items)


# ---------------------------------------------------------------------------
# Katman 4 — Karar
# ---------------------------------------------------------------------------

def _build_asymmetry(
    macro: MacroLayer,
    appetite: RiskAppetiteLayer,
    signals: tuple[AssetSignal, ...],
    scenarios: tuple[Scenario, ...],
    tech_map: dict[str, "TechnicalInsight"] | None = None,
) -> AsymmetrySignal:
    """
    Olasılık-ağırlıklı beklenen kazanç / beklenen kayıp oranını hesaplar.
    tech_map varsa gerçek ATR/swing seviyelerinden türetilir.
    Execution yoktur — yalnızca analiz çerçevesi.
    """
    blocking  = sum(1 for s in signals if s.status == "BLOCKING")

    # ── Tahmini hareket büyüklüğü ────────────────────────────────────────────
    # Önce ATR/S-R bazlı gerçek hesap dene — olmadığında rejim sabitine dön

    # Key varlıklar ve portföy ağırlıkları
    _ASYM_WEIGHTS: list[tuple[str, float]] = [
        ("BTCUSD", 0.30),
        ("XAUUSD", 0.25),
        ("XAGUSD", 0.15),
        ("XCUUSD", 0.15),
        ("BRENT",  0.15),
    ]

    upside_sum   = 0.0
    downside_sum = 0.0
    atr_sum      = 0.0
    weight_sum   = 0.0

    if tech_map:
        for code, w in _ASYM_WEIGHTS:
            ti = tech_map.get(code)
            if ti and ti.current_price > 0:
                price = ti.current_price
                lvl   = ti.levels

                # Dirence kadar yükseliş potansiyeli
                up = max(0.0, (lvl.resistance - price) / price * 100.0)

                # Destege (veya stop'a) kadar düşüş riski
                # Destek zaten kırıldıysa stop_loss'u kullan — daha muhafazakâr
                down_ref = lvl.stop_loss if price < lvl.support else lvl.support
                down = max(0.0, (price - down_ref) / price * 100.0)

                upside_sum   += up   * w
                downside_sum += down * w
                atr_sum      += ti.levels.atr_pct * w
                weight_sum   += w

    if weight_sum >= 0.5:
        # ATR volatilite çarpanı — yüksek ATR = daha geniş hedef aralık
        avg_atr_pct = atr_sum / weight_sum
        vol_mult = max(0.75, min(1.40, 1.0 + (avg_atr_pct - 2.0) / 15.0))

        bull_target   = max(3.0, min(40.0, (upside_sum   / weight_sum) * vol_mult))
        bear_drawdown = max(3.0, min(45.0, (downside_sum / weight_sum) * vol_mult))
    else:
        # Fallback: rejim bazlı sabitler
        bull_target_map: dict[str, float] = {
            "RISK_ON":       22.0,
            "TRANSITIONING": 13.0,
            "DEFENSIVE":      7.0,
            "CRISIS":         4.0,
        }
        bull_target = bull_target_map.get(macro.regime, 13.0)

        if blocking == 0:
            bear_drawdown = 10.0
        elif blocking == 1:
            bear_drawdown = 18.0
        else:
            bear_drawdown = 30.0

    # ── Bloklama amplifikatörü — kriz anında riskin altını çiz ───────────────
    if blocking >= 2:
        bear_drawdown = max(bear_drawdown, bear_drawdown * 1.35)
    if macro.regime == "CRISIS" or appetite.status == "CRISIS":
        bear_drawdown = max(bear_drawdown, 35.0)

    # ── Risk iştahı düzeltmesi ────────────────────────────────────────────────
    if appetite.status == "STRONG":
        bull_target *= 1.12
    elif appetite.status == "WEAK":
        bull_target *= 0.82
    elif appetite.status == "CRISIS":
        bull_target *= 0.55

    # Baz senaryo: yarı kazanç / yarı kayıp (nötr)
    base_gain = bull_target * 0.30
    base_loss = bear_drawdown * 0.25

    # ── Olasılık-ağırlıklı beklenti ────────────────────────────────────────
    bull_prob = next((s.probability_pct for s in scenarios if s.key == "bull"), 30) / 100
    base_prob = next((s.probability_pct for s in scenarios if s.key == "base"), 40) / 100
    bear_prob = next((s.probability_pct for s in scenarios if s.key == "bear"), 30) / 100

    expected_gain = round(bull_prob * bull_target + base_prob * base_gain, 1)
    expected_loss = round(bear_prob * bear_drawdown + base_prob * base_loss, 1)

    ratio = round(expected_gain / max(expected_loss, 0.01), 2)

    # ── Değerlendirme ve renk ───────────────────────────────────────────────
    if ratio >= 2.5:
        label, color = "Çok Olumlu", "green"
        brief = f"Her %1 beklenen kayba karşı %{ratio:.1f} beklenen kazanç var — teyit sinyallerini bekle, asimetri güçlü."
    elif ratio >= 1.7:
        label, color = "Olumlu", "lime"
        brief = f"Kazanç/kayıp oranı {ratio:.1f}×. Risk-ödül dengesi olumlu — teyit sinyalleri netleşince değerlendir."
    elif ratio >= 1.1:
        label, color = "Dengeli", "yellow"
        brief = f"Oran {ratio:.1f}× — kazanç potansiyeli ve risk birbirine yakın. Katalizör netleşmeden izlemede kal."
    elif ratio >= 0.6:
        label, color = "Olumsuz", "orange"
        brief = f"Beklenen kayıp beklenen kazancı aşıyor ({ratio:.1f}×). Mevcut asimetri yeni giriş için elverişli değil — izleme modu."
    else:
        label, color = "Çok Olumsuz", "red"
        brief = f"Risk/Ödül oranı {ratio:.1f}× — olası kayıp kazancın çok üzerinde. Savunmacı kal, izlemede bekle."

    return AsymmetrySignal(
        expected_gain_pct=expected_gain,
        expected_loss_pct=expected_loss,
        ratio=ratio,
        label=label,
        color=color,
        brief=brief,
    )


def _build_owner_actions(
    decision: Decision,
    signals: tuple[AssetSignal, ...],
    checklist: tuple[ConfirmationItem, ...],
    macro: MacroLayer,
    appetite: RiskAppetiteLayer,
) -> tuple[str, ...]:
    """Karara özel 5 operasyonel adım üretir. PAPER_SAFE — execution içermez."""

    def _sig(code: str) -> float | None:
        s = next((x for x in signals if x.asset_code == code), None)
        return s.value if s and s.value is not None else None

    btc   = _sig("BTCUSD")
    brent = _sig("BRENT")
    hyg   = _sig("HYG")
    vix   = _sig("VIX")
    silver= _sig("XAGUSD")
    copper= _sig("XCUUSD")

    if decision == "BEKLE":
        step1 = "Yeni pozisyon açma — sistem teyit toplama modunda."
        step2 = (
            f"Brent ${_fmt(brent)} izle — ${int(_BRENT_WARN)} altında kalıcı kapanış gerekli."
            if brent else "Brent $85 altına kalıcı girmesini bekle."
        )
        step3 = (
            f"BTC ${_fmt(btc, 0)} — ${int(_BTC_WATCH):,} üstünde güçlü kapanış teyidi al."
            if btc else f"BTC ${int(_BTC_WATCH):,} üstünde kapanış teyidini bekle."
        )
        step4 = (
            f"Silver {_fmt(silver)} + Copper birlikte yukarı kırıyorsa stratejik metal rotasyonunu not et."
            if silver and copper
            else "Silver ve Copper momentumunu izle — birlikte güçleniyorsa metal rotasyonu yakın."
        )
        step5 = (
            f"HYG {_fmt(hyg)} — ${int(_HYG_HEALTHY)} üstünde kaldığı sürece kredi endişesi yok."
            if hyg else "HYG/JNK sağlığını saatlik takip et — bozulursa risk azalt."
        )
        return (step1, step2, step3, step4, step5)

    elif decision == "AÇIL":
        step1 = "Tüm teyit koşulları karşılandı — execution hâlâ tamamen insana ait."
        step2 = "Pozisyon büyüklüğünü risk bütçene göre planla; tek seferde tam giriş yapma."
        step3 = (
            f"BTC ${_fmt(btc, 0)} — ${int(_BTC_WATCH):,} stop-loss bölgesini belirle ve izle."
            if btc else "BTC stop-loss seviyesini belirle ve otomatik uyarı kur."
        )
        step4 = (
            f"Brent >${int(_BRENT_HIGH)} veya VIX >{int(_VIX_ELEVATED)} görürsen rotasyonu yavaşlat."
        )
        step5 = "AI rapor ve makro sinyal güncellemelerini 24 saatte bir kontrol et."
        return (step1, step2, step3, step4, step5)

    elif decision == "KÜÇÜLT":
        step1 = "Mevcut pozisyonları kademeli küçült — panikle tek seferde satma."
        step2 = "Nakit veya stablecoin oranını toplam portföyün ≥%40'ına çek."
        step3 = (
            f"BTC ${_fmt(btc, 0)} — ${int(_BTC_WEAK):,} altı kalıcı kapanış görürsen hızlan."
            if btc else f"BTC ${int(_BTC_WEAK):,} altı kapanışta küçültme hızını artır."
        )
        step4 = (
            f"HYG {_fmt(hyg)} — ${int(_HYG_BREAKING)} altına kırılırsa sistem KAPAT moduna geçer."
            if hyg else "HYG/JNK bozulmasını KAPAT sinyali olarak say."
        )
        step5 = "Altın / kısa vadeli tahvil / nakit ağırlığını artır, büyüme varlıklarını azalt."
        return (step1, step2, step3, step4, step5)

    else:  # KAPAT
        step1 = "Tüm riskli pozisyonları kapat veya hedge'i maksimuma çek — sistem kriz modunda."
        step2 = "Nakit, altın veya kısa vadeli devlet tahvili pozisyonuna geç."
        step3 = "Yeni giriş yok — piyasa kriz modunda."
        step4 = (
            f"VIX {_fmt(vix)} — {int(_VIX_ELEVATED)} altına kalıcı dönüş + HYG toparlanması olmadan pozisyon açma."
            if vix else f"VIX {int(_VIX_ELEVATED)} altına dönüş ve kredi toparlanması olmadan geri dönme."
        )
        step5 = "Bir sonraki güncellemede sinyal ortamını değerlendir; acele etme."
        return (step1, step2, step3, step4, step5)


def _build_flip_conditions(
    decision: Decision,
    signals: tuple[AssetSignal, ...],
    macro: MacroLayer,
    appetite: RiskAppetiteLayer,
    tech_map: dict | None = None,
) -> tuple[FlipCondition, ...]:
    """Kararı değiştirecek koşulları üretir — dinamik fiyat ve teknik seviye referansları kullanır."""
    _tm = tech_map or {}

    def _sig(code: str) -> float | None:
        s = next((x for x in signals if x.asset_code == code), None)
        return s.value if s and s.value is not None else None

    btc    = _sig("BTCUSD")
    brent  = _sig("BRENT")
    hyg    = _sig("HYG")
    dxy    = _sig("DXY")
    vix    = _sig("VIX")
    silver = _sig("XAGUSD")
    copper = _sig("XCUUSD")

    # Dinamik teknik seviyeler — statik sabitlerden daha güncel
    _btc_ti   = _tm.get("BTCUSD")
    _brent_ti = _tm.get("BRENT")
    flip_btc_support  = _btc_ti.levels.support      if _btc_ti   else _BTC_WATCH
    flip_btc_stoploss = _btc_ti.levels.stop_loss     if _btc_ti   else _BTC_WEAK
    flip_brent_high   = _brent_ti.levels.resistance  if _brent_ti else _BRENT_HIGH
    flip_brent_warn   = _brent_ti.levels.support     if _brent_ti else _BRENT_WARN

    def _p(val: float | None, prefix: str = "$", decimals: int = 0) -> str:
        if val is None:
            return ""
        fmt = f"{val:,.{decimals}f}"
        return f" (şu an {prefix}{fmt})"

    if decision == "BEKLE":
        to_open = FlipCondition(
            direction="AL",
            label="AL'a Geçiş Koşulları",
            icon="up",
            conditions=(
                f"BTC ${flip_btc_support:,.0f} desteği geri alımı + kapanış teyidi{_p(btc)}",
                f"Brent ${flip_brent_warn:,.0f} altında kalıcı kapanış{_p(brent)}",
                f"Silver ${int(_XAGUSD_CONFIRM)} üstünde momentum{_p(silver)}",
                f"Copper ${int(_XCUUSD_HEALTHY):,} üstünde sağlıklı{_p(copper)}",
                f"HYG ${int(_HYG_HEALTHY)} üstünde bozulmadan{_p(hyg)}",
            ),
        )
        to_reduce = FlipCondition(
            direction="KÜÇÜLT",
            label="Risk Azaltma Tetikleyicileri",
            icon="down",
            conditions=(
                f"BTC ${flip_btc_stoploss:,.0f} stop seviyesi altına kalıcı kırılış{_p(btc)}",
                f"HYG ${int(_HYG_BREAKING)} altına düşüş{_p(hyg)}",
                f"DXY {int(_DXY_STRONG)} üstüne çıkış{_p(dxy, prefix='')}",
                f"Brent ${flip_brent_high:,.0f} üstüne tekrar yükseliş{_p(brent)}",
                f"VIX {int(_VIX_ELEVATED)} üstünde kapanış{_p(vix, prefix='')}",
            ),
        )
        return (to_open, to_reduce)

    elif decision == "AÇIL":
        to_wait = FlipCondition(
            direction="BEKLE",
            label="BEKLE'ye Geri Dönüş Sinyalleri",
            icon="neutral",
            conditions=(
                f"BTC ${flip_btc_support:,.0f} desteği altına kırılış{_p(btc)}",
                f"Brent ${flip_brent_high:,.0f} üstüne yükseliş{_p(brent)}",
                f"VIX {int(_VIX_ELEVATED)} üstünde kapanış{_p(vix, prefix='')}",
                f"DXY {int(_DXY_STRONG)} üstüne çıkış{_p(dxy, prefix='')}",
                f"HYG ${int(_HYG_HEALTHY)} altına düşüş{_p(hyg)}",
            ),
        )
        to_reduce = FlipCondition(
            direction="KÜÇÜLT",
            label="Risk Azaltma Tetikleyicileri",
            icon="down",
            conditions=(
                f"BTC ${flip_btc_stoploss:,.0f} stop altına kalıcı kırılış{_p(btc)}",
                f"HYG ${int(_HYG_BREAKING)} altına düşüş{_p(hyg)}",
                "Makro DEFENSIVE'e dönüş (birden fazla bloklama)",
                f"Brent ${flip_brent_high:,.0f} üstünde kalıcı yerleşme{_p(brent)}",
                f"VIX {int(_VIX_FEAR)} üstünde kapanış{_p(vix, prefix='')}",
            ),
        )
        return (to_wait, to_reduce)

    elif decision == "KÜÇÜLT":
        to_bekle = FlipCondition(
            direction="BEKLE",
            label="İyileşme Sinyalleri",
            icon="up",
            conditions=(
                f"Bloklama sayısı 1'e düşmesi (şu an: {sum(1 for s in signals if s.status == 'BLOCKING')})",
                f"HYG ${int(_HYG_HEALTHY)} üstüne toparlanma{_p(hyg)}",
                f"VIX {int(_VIX_ELEVATED)} altına kalıcı düşüş{_p(vix, prefix='')}",
                f"Brent ${int(_BRENT_WARN)} altına geri çekilme{_p(brent)}",
                "Makro TRANSITIONING'e dönüş",
            ),
        )
        to_kapat = FlipCondition(
            direction="KAPAT",
            label="Kriz Tetikleyicileri",
            icon="down",
            conditions=(
                "3+ sinyal BLOCKING durumuna girmesi",
                f"HYG ${int(_HYG_BREAKING)} altına düşüş{_p(hyg)}",
                f"VIX {int(_VIX_PANIC)} üstüne çıkış{_p(vix, prefix='')}",
                f"BTC ${int(_BTC_WEAK):,} altına kalıcı kırılış{_p(btc)}",
                "Makro CRISIS'e geçiş",
            ),
        )
        return (to_bekle, to_kapat)

    else:  # KAPAT
        to_kucult = FlipCondition(
            direction="KÜÇÜLT",
            label="Toparlanma Sinyalleri",
            icon="up",
            conditions=(
                f"VIX {int(_VIX_ELEVATED)} altına kalıcı dönüş{_p(vix, prefix='')}",
                f"HYG ${int(_HYG_HEALTHY)} üstüne toparlanma{_p(hyg)}",
                "Bloklama sayısının 2'ye düşmesi",
                f"BTC ${int(_BTC_WATCH):,} üstünde tutunma{_p(btc)}",
                "Makro DEFENSIVE'e gerileme (CRISIS çözülüyor)",
            ),
        )
        stay = FlipCondition(
            direction="KAPAT",
            label="Kriz Devam Koşulları",
            icon="neutral",
            conditions=(
                f"VIX {int(_VIX_PANIC)} üstünde kalması{_p(vix, prefix='')}",
                f"HYG ${int(_HYG_BREAKING)} altında kalması{_p(hyg)}",
                f"BTC ${int(_BTC_WEAK):,} altında kalması{_p(btc)}",
                f"DXY {int(_DXY_STRONG)} üstünde güçlü kalması{_p(dxy, prefix='')}",
                "Kredi spread genişlemeye devam ediyorsa",
            ),
        )
        return (to_kucult, stay)


def _build_scenarios(
    macro: MacroLayer,
    appetite: RiskAppetiteLayer,
    signals: tuple[AssetSignal, ...],
    decision: Decision,
    tech_map: dict[str, "TechnicalInsight"] | None = None,
) -> tuple[Scenario, ...]:
    """
    Mevcut sinyal durumundan olasılık ağırlıklı 3 senaryo üretir.
    Olasılıklar sinyallere göre dinamik olarak hesaplanır ve 100'e normalize edilir.
    Hiçbir zaman trade tavsiyesi vermez — yalnızca analiz.
    """
    blocking  = sum(1 for s in signals if s.status == "BLOCKING")
    confirmed = sum(1 for s in signals if s.status == "CONFIRMED")

    # ── Temel olasılıklar (karar bazlı başlangıç noktası) ──────────────────
    base_map: dict[Decision, tuple[int, int, int]] = {
        #              bull  base  bear
        "AÇIL":       (55,   32,   13),
        "BEKLE":      (30,   45,   25),
        "KÜÇÜLT":     (18,   32,   50),
        "KAPAT":      ( 8,   20,   72),
    }
    bull, base, bear = base_map.get(decision, (30, 45, 25))

    # ── Sinyal düzeltmeleri ─────────────────────────────────────────────────
    # Bloklama sinyalleri ayı lehine baskı
    if blocking == 0:
        bull += 5;  bear -= 3
    elif blocking == 1:
        bull -= 5;  bear += 6
    elif blocking >= 2:
        bull -= 10; bear += 12

    # Teyit sinyalleri boğa lehine güç
    if confirmed >= 5:
        bull += 8;  bear -= 5
    elif confirmed >= 3:
        bull += 4;  bear -= 2

    # Makro rejim etkisi
    if macro.regime == "RISK_ON":
        bull += 5;  bear -= 3
    elif macro.regime == "DEFENSIVE":
        bull -= 7;  bear += 8
    elif macro.regime == "CRISIS":
        bull -= 12; bear += 15
    elif macro.regime == "TRANSITIONING":
        base += 3   # belirsizlik → baz senaryo güçlenir

    # Risk iştahı etkisi
    if appetite.status == "STRONG":
        bull += 5;  bear -= 3
    elif appetite.status == "WEAK":
        bull -= 5;  bear += 6
    elif appetite.status == "CRISIS":
        bull -= 10; bear += 14

    # Makro güven skoru etkisi
    if macro.confidence_pct >= 80:
        bull += 3;  bear -= 2
    elif macro.confidence_pct <= 40:
        base += 4   # belirsizlik artar

    # ── Normalize et (toplam = 100, minimum 5) ──────────────────────────────
    bull = max(5, bull)
    base = max(5, base)
    bear = max(5, bear)
    total = bull + base + bear
    bull = round(bull / total * 100)
    bear = round(bear / total * 100)
    base = 100 - bull - bear   # yuvarlamadan doğan hatayı baz senaryoya yükle
    base = max(5, base)

    # ── Dinamik fiyat referansları (sinyallerden) ────────────────────────────
    btc_sig   = next((s for s in signals if s.asset_code == "BTCUSD"),   None)
    brent_sig = next((s for s in signals if s.asset_code == "BRENT"),    None)
    dxy_sig   = next((s for s in signals if s.asset_code == "DXY"),      None)
    hyg_sig   = next((s for s in signals if s.asset_code == "HYG"),      None)

    btc_price   = btc_sig.value   if btc_sig   and btc_sig.value   is not None else None
    brent_price = brent_sig.value if brent_sig and brent_sig.value is not None else None
    dxy_price   = dxy_sig.value   if dxy_sig   and dxy_sig.value   is not None else None

    # Hedef fiyatlar: mevcut +20% (boğa) referansı
    btc_bull_lvl   = f"${int(btc_price * 1.20):,}"   if btc_price   else "+%20"
    brent_bear_lvl = f"${brent_price * 1.10:.0f}"    if brent_price else "$+10%"
    dxy_bull_lvl   = f"{dxy_price * 1.04:.1f}"       if dxy_price   else "+%4"

    # ── Narratif şablonları ─────────────────────────────────────────────────
    # BOĞA tetikleyicileri
    if macro.regime in ("RISK_ON", "TRANSITIONING") and appetite.status in ("STRONG", "MODERATE"):
        bull_trigger = (
            f"FOMC dovish sinyal / CPI beklenti altı + "
            f"BTC >{btc_bull_lvl} kapanış + USDT.D düşüşü"
        )
        bull_brief   = (
            "Risk iştahı açılır, sermaye kripto ve büyüme hisselerine döner. "
            "BTC dominant yapısı sürdürülürse altcoin rotasyonu da güçlenir."
        )
    elif macro.regime == "DEFENSIVE":
        bull_trigger = (
            f"Enerji baskısı azalır + Brent <$85 + DXY <{dxy_bull_lvl if dxy_price and dxy_price > 100 else '100'}"
        )
        bull_brief   = (
            "Makro baskı hafiflediğinde sıkışmış değerleme açılabilir. "
            "Güçlü bir VIX düşüşü ve HYG toparlanması ön koşul."
        )
    else:
        bull_trigger = (
            f"Kriz sinyalleri çözülür + USDT.D <5% + BTC >{btc_bull_lvl} kalıcı kapanış"
        )
        bull_brief   = (
            "Kriz geçerken toparlanma hızlı olabilir. "
            "Riskin azaldığının ilk onayı gelene kadar beklenmeli."
        )

    # BAZ tetikleyicileri
    if decision in ("BEKLE", "AÇIL"):
        base_trigger = "Mevcut sinyal yapısı korunur, büyük sürpriz yok, piyasa konsolide olur"
        base_brief   = (
            "Fiyatlar dar bir bant içinde seyreder. "
            "Katalizörler ve yeni veri akışı sinyal dengesini belirleyecek."
        )
    elif decision == "KÜÇÜLT":
        base_trigger = "Ek bloklama gelmez, makro yavaşça TRANSITIONING'e döner"
        base_brief   = (
            "Savunmacı pozisyon korunur ancak kriz derinleşmez. "
            "Tahvil ve altın görece güçlü kalır."
        )
    else:
        base_trigger = "Panik azalır ama toparlanma için katalizör gelmez"
        base_brief   = (
            "Piyasa stabilize olur, yön arayışı sürer. "
            "Bu aşamada riskli varlıklar zaten büyük ölçüde satılmış olmalı."
        )

    # AYI tetikleyicileri
    if blocking >= 2 or macro.regime in ("DEFENSIVE", "CRISIS"):
        bear_trigger = (
            f"Blok sinyalleri artar + VIX >30 + "
            f"{'HYG <76' if not hyg_sig or not hyg_sig.value else f'HYG <{hyg_sig.value * 0.95:.0f}'}"
        )
        bear_brief   = (
            "Makro baskı derinleşirse likit olmayan varlıklar sert satış görebilir. "
            "Hedge ve nakit pozisyonları koruyucu işlev görür."
        )
    elif appetite.status in ("WEAK", "CRISIS"):
        bear_trigger = (
            f"USDT.D >10% + DXY >{dxy_bull_lvl} + risk-off sermaye çıkışı"
        )
        bear_brief   = (
            "Sermaye güvenli limanlara kaçmaya devam eder. "
            "Dolar gücü tüm emtia ve kripto üzerinde baskı yaratır."
        )
    else:
        bear_trigger = (
            f"FOMC hawkish sürpriz + enflasyon tırmanışı + "
            f"{'Brent >' + brent_bear_lvl if brent_price else 'enerji şoku'}"
        )
        bear_brief   = (
            "Beklenmedik bir sıkılaşma sinyali tüm risk varlıklarını eş zamanlı vurur. "
            "Düşük olasılıklı ama yüksek etki — hedge pozisyonunu koru."
        )

    # ── Eşik chip'leri (kısa, taranabilir) ─────────────────────────────────────
    tech_map = tech_map or {}

    # Dinamik ATR-bazlı eşikler (yeterli teknik veri varsa statik sabitleri geçersiz kıl)
    _btc_ti = tech_map.get("BTCUSD")
    _brent_ti = tech_map.get("BRENT")
    _vix_ti = tech_map.get("VIX")
    _hyg_ti = tech_map.get("HYG")

    # BTC: direnç seviyesi veya mevcut +%20 (hangisi daha gerçekçiyse)
    if _btc_ti and btc_price:
        _btc_res = _btc_ti.levels.resistance
        # +%20 hedef vs ATR-bazlı direnç — ikisinden düşük olanı daha erişilebilir
        _btc_bull_target = min(btc_price * 1.20, _btc_res * 1.05)
        btc_bull_chip = f"BTC >${int(_btc_bull_target):,}"
    else:
        btc_bull_chip  = f"BTC >${int(btc_price * 1.20):,}"  if btc_price  else "BTC ↑ %20"

    # Brent: ATR-bazlı dinamik eşikler
    if _brent_ti:
        _brent_sup = _brent_ti.levels.support
        _brent_res = _brent_ti.levels.resistance
        brent_ok_chip   = f"Brent <${_brent_sup:.0f} (destek)"
        brent_risk_chip = f"Brent >${_brent_res:.0f} (direnç)"
    else:
        brent_ok_chip   = f"Brent <${int(_BRENT_WARN)}"
        brent_risk_chip = f"Brent >${int(_BRENT_HIGH)}"

    # VIX
    if _vix_ti:
        _vix_sup = _vix_ti.levels.support
        _vix_res = _vix_ti.levels.resistance
        vix_ok_chip   = f"VIX <{_vix_sup:.0f} (destek)"
        vix_fear_chip = f"VIX >{_vix_res:.0f} (direnç)"
    else:
        vix_ok_chip   = f"VIX <{int(_VIX_CALM)}"
        vix_fear_chip = f"VIX >{int(_VIX_FEAR)}"

    # HYG
    if _hyg_ti:
        _hyg_sup = _hyg_ti.levels.support
        hyg_ok_chip   = f"HYG >{int(_HYG_HEALTHY)}"
        hyg_risk_chip = f"HYG <{_hyg_sup:.1f} (destek)"
    else:
        hyg_ok_chip   = f"HYG >{int(_HYG_HEALTHY)}"
        hyg_risk_chip = f"HYG <{int(_HYG_BREAKING)}"

    dxy_ok_chip    = f"DXY <{int(_DXY_WEAK)}"
    usdtd_ok_chip  = f"USDT.D <{_USDTD_SAFE:.0f}%"
    usdtd_risk_chip= f"USDT.D >{_USDTD_FLIGHT:.0f}%"

    if macro.regime in ("RISK_ON", "TRANSITIONING") and appetite.status in ("STRONG", "MODERATE"):
        bull_thresholds = (btc_bull_chip, usdtd_ok_chip, "CPI ↓ sürpriz")
    elif macro.regime == "DEFENSIVE":
        bull_thresholds = (brent_ok_chip, dxy_ok_chip, vix_ok_chip)
    else:
        bull_thresholds = (btc_bull_chip, usdtd_ok_chip, "Kriz çözülür")

    base_thresholds = (vix_ok_chip, "Sinyal dengesi", hyg_ok_chip)

    if blocking >= 2 or macro.regime in ("DEFENSIVE", "CRISIS"):
        bear_thresholds = (vix_fear_chip, hyg_risk_chip, brent_risk_chip)
    elif appetite.status in ("WEAK", "CRISIS"):
        bear_thresholds = (usdtd_risk_chip, f"DXY >{int(_DXY_STRONG)}", vix_fear_chip)
    else:
        bear_thresholds = (brent_risk_chip, vix_fear_chip, "FOMC hawkish")

    return (
        Scenario(
            key="bull", label="Boğa", probability_pct=bull,
            trigger=bull_trigger, brief=bull_brief, color="green",
            thresholds=bull_thresholds,
        ),
        Scenario(
            key="base", label="Baz", probability_pct=base,
            trigger=base_trigger, brief=base_brief, color="yellow",
            thresholds=base_thresholds,
        ),
        Scenario(
            key="bear", label="Ayı", probability_pct=bear,
            trigger=bear_trigger, brief=bear_brief, color="red",
            thresholds=bear_thresholds,
        ),
    )


def _make_decision(
    macro: MacroLayer,
    appetite: RiskAppetiteLayer,
    signals: tuple[AssetSignal, ...],
    checklist: tuple[ConfirmationItem, ...],
) -> tuple[Decision, str, str]:
    """Returns (decision, owner_action, verdict)."""

    blocking = sum(1 for s in signals if s.status == "BLOCKING")
    confirmed = sum(1 for s in signals if s.status == "CONFIRMED")
    checklist_met = sum(1 for c in checklist if c.met)
    total_checks = len(checklist)

    # --- KAPAT ---
    # Kriz modu: makro kriz VEYA iştah tamamen çökmüş VEYA 3+ bloklama
    if macro.regime == "CRISIS" or appetite.status == "CRISIS" or blocking >= 3:
        decision: Decision = "KAPAT"
        owner = "Pozisyonları kapat veya hedge'i maksimuma çek. Sistem kriz modunda."
        verdict = "Birden fazla kritik sinyal aynı anda ateşlendi — güvenlik önce gelir."
        return decision, owner, verdict

    # --- KÜÇÜLT ---
    # Sert savunmacı: Defensive makro VEYA 2+ bloklama
    # VEYA: iştah zayıf VE bloklayan sinyal var
    if (
        macro.regime == "DEFENSIVE"
        or blocking >= 2
        or (appetite.status == "WEAK" and blocking >= 1)
    ):
        decision = "KÜÇÜLT"
        owner = "Mevcut pozisyonları küçült. Yeni giriş yapma. Teyit için bekle."
        verdict = "Makro baskı veya risk iştahı zayıflığı mevcut — defansif kalın."
        return decision, owner, verdict

    # --- AÇIL ---
    # Tam uyum: RISK_ON makro, güçlü/orta iştah, 4+ teyit, 5/6+ checklist, 0 bloklama
    if (
        macro.regime == "RISK_ON"
        and appetite.status in ("STRONG", "MODERATE")
        and confirmed >= 4
        and checklist_met >= int(total_checks * 0.8)
        and blocking == 0
    ):
        decision = "AÇIL"
        owner = "Teyit koşulları karşılandı. Kademeli giriş planlanabilir. Execution hâlâ OFF."
        verdict = "Tüm katmanlar aynı yönde — fırsat penceresi açılıyor, execution kararı insana ait."
        return decision, owner, verdict

    # --- BEKLE (default) ---
    # TRANSITIONING makro veya WEAK iştah ama bloklama yok → bekle, teyit topla
    unmet = [c.signal for c in checklist if not c.met]
    decision = "BEKLE"
    if unmet:
        # Kısa ve öz: ilk eksik teyiti anlaşılır biçimde yaz
        first_unmet = unmet[0]
        rest = len(unmet) - 1
        if rest > 0:
            owner = f"Eksik teyit: {first_unmet} (+{rest} daha). Pozisyon açma."
        else:
            owner = f"Eksik teyit: {first_unmet}. Bu sinyal gelene kadar bekle."
    elif appetite.status == "WEAK":
        owner = "Checklist tamam ama risk iştahı zayıf — altın ve USDT.D sinyallerini izle."
    else:
        owner = "Sinyaller henüz tam hizalı değil. Bir sonraki güncellemede tekrar değerlendir."

    # Verdict — engelleyen varlık yalnızca core macro sinyalse öne çıkar;
    # ETH/IWM/SMH gibi ikincil varlıklar tüm portföy kararını yönlendirmez.
    _CORE_BLOCKING = {"BTCUSD", "SP500", "DXY", "BRENT", "VIX", "HYG", "HY_SPREAD", "REAL_YIELD"}

    if blocking == 1:
        blocking_sig = next((s for s in signals if s.status == "BLOCKING"), None)
        if blocking_sig and blocking_sig.asset_code in _CORE_BLOCKING:
            verdict = f"Geçiş rejimi — {blocking_sig.asset_name} çözüme kavuşmadan pozisyon açma."
        elif confirmed >= 4 and checklist_met >= total_checks - 2:
            verdict = "Sinyaller büyük ölçüde olumlu — makro yön teyidini bekle, checklist tamamla."
        else:
            verdict = "Koşullar olgunlaşıyor — makro yön netleşene kadar bekle."
    elif macro.regime == "TRANSITIONING" and checklist_met >= total_checks - 1:
        verdict = "Koşullar olgunlaşıyor — makro yön netleşene kadar bekle."
    elif confirmed >= 3:
        verdict = "Çoğu sinyal olumlu, makro tam netleşmedi — acele etme."
    else:
        verdict = "Rejim belirsizliğini koruyor — bekle, teyit topla, sonra karar ver."

    return decision, owner, verdict


# ---------------------------------------------------------------------------
# Tech-insight × snapshot cross-validation
# ---------------------------------------------------------------------------

# yfinance bazen yanlış asset'in DataFrame'ini iade edebiliyor (BTC yerine XAG bar'ları gibi).
# Bu durumda tech_insight.current_price gerçek market snapshot fiyatından çok farklı çıkar.
# Burada eşik %5: bunun üstündeki fark "asset contamination" sinyali kabul edilir.
_TECH_SNAPSHOT_DRIFT_TOLERANCE = 0.05

# tech_map anahtarı (str) → snapshot AssetCode eşlemesi
# Not: XCUUSD dahil edilmedi çünkü technical_provider USD/lb → USD/MT dönüşümü
# (mult=2204.623) uyguluyor — snapshot ham USD/lb taşıyor, bu yüzden drift
# yapay olarak büyük çıkar. XCU sanity'si _is_insight_sane bound guard'ına bırakıldı.
_TECH_TO_SNAPSHOT_CODE: dict[str, AssetCode] = {
    "BTCUSD": AssetCode.BTCUSD,
    "XAUUSD": AssetCode.XAUUSD,
    "XAGUSD": AssetCode.XAGUSD,
    "BRENT":  AssetCode.BRENT,
    "DXY":    AssetCode.DXY,
    "VIX":    AssetCode.VIX,
    "SP500":  AssetCode.SP500,
    "HYG":    AssetCode.HYG,
}


def _validate_tech_map_against_snapshots(
    tech_map: dict[str, "TechnicalInsight"],
    snap_map: dict[AssetCode, "MarketSnapshot"],
) -> dict[str, "TechnicalInsight"]:
    """Her tech_insight.current_price'ı snapshot.value ile karşılaştır.

    Sapma %_TECH_SNAPSHOT_DRIFT_TOLERANCE'ı aşıyorsa insight discard edilir.
    Böylece BTC'ye sızmış XAG seviyeleri owner_actions, flip_conditions ve
    asset_signals tarafında fallback sabit eşiklere düşer; yanlış değer ile
    karar üretilmez.
    """
    if not tech_map:
        return tech_map

    validated: dict[str, "TechnicalInsight"] = {}
    for code, ti in tech_map.items():
        # 1) Asset-bound check — yfinance ticker bazen yanlış DF iade ediyor
        if not _is_insight_sane(code, ti.current_price, ti.levels.support, ti.levels.resistance):
            logger.warning(
                "tech_map[%s] discard: current=%.4f S=%.4f R=%.4f asset-bound dışı",
                code, ti.current_price, ti.levels.support, ti.levels.resistance,
            )
            continue

        # 2) Snapshot drift check — bound içinde olabilir ama yanlış asset olabilir
        snap_code = _TECH_TO_SNAPSHOT_CODE.get(code)
        if snap_code is None:
            validated[code] = ti
            continue
        snap = snap_map.get(snap_code)
        snap_value = getattr(snap, "value", None) if snap is not None else None
        if snap_value is None or snap_value <= 0:
            validated[code] = ti
            continue
        drift = abs(ti.current_price - snap_value) / snap_value
        if drift > _TECH_SNAPSHOT_DRIFT_TOLERANCE:
            logger.warning(
                "tech_map[%s] discard: tech.current=%.4f vs snapshot.value=%.4f drift=%.1f%%",
                code, ti.current_price, snap_value, drift * 100.0,
            )
            continue
        validated[code] = ti
    return validated


# ---------------------------------------------------------------------------
# Ana Servis
# ---------------------------------------------------------------------------

class RegimeReportService:
    """
    4-katmanlı piyasa analiz motoru.
    Hiçbir zaman trade execution üretmez — PAPER_SAFE / NO_EXECUTION.
    """

    def generate(
        self,
        snapshots: list[MarketSnapshot] | tuple[MarketSnapshot, ...],
        news_headlines: tuple[NewsHeadline, ...] = (),
        upcoming_catalysts: tuple[CatalystEvent, ...] = (),
        delta_map: dict[str, float] | None = None,
        tech_insights: dict[str, TechnicalInsight] | None = None,
    ) -> RegimeReport:
        snap_map: dict[AssetCode, MarketSnapshot] = {
            s.asset_symbol: s for s in snapshots
        }
        tech_map = _validate_tech_map_against_snapshots(tech_insights or {}, snap_map)

        macro    = _analyze_macro(snap_map)
        appetite = _analyze_appetite(snap_map)
        signals  = _build_asset_signals(snap_map, delta_map=delta_map, tech_map=tech_map)
        checklist = _build_confirmation_checklist(snap_map, tech_map=tech_map)
        decision, owner, verdict = _make_decision(macro, appetite, signals, checklist)
        scenarios       = _build_scenarios(macro, appetite, signals, decision, tech_map=tech_map)
        asymmetry       = _build_asymmetry(macro, appetite, signals, scenarios, tech_map=tech_map)
        owner_actions   = _build_owner_actions(decision, signals, checklist, macro, appetite)
        flip_conditions = _build_flip_conditions(decision, signals, macro, appetite, tech_map=tech_map)

        blocking  = sum(1 for s in signals if s.status == "BLOCKING")
        confirmed = sum(1 for s in signals if s.status == "CONFIRMED")
        pending   = sum(1 for s in signals if s.status == "PENDING")

        return RegimeReport(
            generated_at=datetime.now(UTC).isoformat(),
            execution_mode="OFF / NO_EXECUTION / PAPER_SAFE",
            macro_layer=macro,
            appetite_layer=appetite,
            asset_signals=signals,
            confirmation_checklist=checklist,
            decision=decision,
            owner_action=owner,
            verdict=verdict,
            scenarios=scenarios,
            asymmetry=asymmetry,
            owner_actions=owner_actions,
            flip_conditions=flip_conditions,
            news_headlines=news_headlines,
            upcoming_catalysts=upcoming_catalysts,
            tech_insights=tuple(tech_map.values()),
            blocking_count=blocking,
            confirmed_count=confirmed,
            pending_count=pending,
        )


__all__ = [name for name in globals() if not name.startswith("_")]
