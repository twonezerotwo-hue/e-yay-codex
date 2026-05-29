"""
Regime Report Service — 4-katmanlı piyasa analiz motoru.

Katman 1: Makro Rejim      (DXY, M2SL, yield curve, Brent)
Katman 2: Risk İştahı      (HYG/JNK, BTC.D, USDT.D, Gold/equities)
Katman 3: Asset Sinyalleri (çapraz teyit, per-asset logic)
Katman 4: Tek karar        (AÇIL / BEKLE / KÜÇÜLT / KAPAT)

Çıktı: RegimeReport dataclass — hiçbir zaman trade execution içermez.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.domain import AssetCode
from app.domain.market_snapshot import MarketSnapshot
from app.providers.news_provider import NewsHeadline

# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

Decision = Literal["AÇIL", "BEKLE", "KÜÇÜLT", "KAPAT"]
RegimeCode = Literal["RISK_ON", "TRANSITIONING", "DEFENSIVE", "CRISIS"]
AppetiteCode = Literal["STRONG", "MODERATE", "WEAK", "CRISIS"]
SignalStatus = Literal["CONFIRMED", "PENDING", "BLOCKING", "NEUTRAL", "VERİ_YOK"]


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


@dataclass(frozen=True)
class ConfirmationItem:
    signal: str
    met: bool
    current_value: str
    threshold: str


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

    # Haberler
    news_headlines: tuple[NewsHeadline, ...]

    # Özet istatistik
    blocking_count: int
    confirmed_count: int
    pending_count: int


# ---------------------------------------------------------------------------
# Thresholds — Mayıs 2026 piyasa gerçeklerine göre kalibrate edildi
# ---------------------------------------------------------------------------

_DXY_STRONG = 104.0       # above = dolar sıkılaşması, risk-off baskısı
_DXY_WEAK   = 100.0       # below = dolar zayıf, likidite açılıyor   [anlık: ~99]

_BRENT_HIGH  = 95.0       # above = enerji baskısı kritik seviye      [anlık: ~93]
_BRENT_WARN  = 85.0       # 85–95 = izleme bölgesi

_YIELD_INVERSION  = 0.0   # 10Y - 2Y < 0 = resesyon sinyali
_YIELD_FLAT       = 0.3   # < 0.3 = eğri düzleşiyor                   [anlık: +0.87]

_M2_EXPANDING = 21_500.0  # > 21.5T = para arzı genişliyor
_M2_SHRINKING = 20_500.0  # < 20.5T = sıkılaşma devam ediyor

_HYG_HEALTHY  = 78.0      # above = kredi piyasası sağlıklı            [anlık: ~80]
_HYG_BREAKING = 74.0      # below = kredi stresi

_BTCD_DOMINANT   = 52.0   # BTC.D above = BTC lider                   [anlık: ~54]
_BTCD_PANIC      = 40.0   # BTC.D below = piyasa paniği veya altseason

_USDTD_SAFE   = 5.0       # USDT.D below = para kripto içinde
_USDTD_FLIGHT = 7.5       # USDT.D above = stablecoin'e kaçış

_BTC_STRONG = 80_000.0    # above = güçlü momentum                    [anlık: ~73K]
_BTC_WATCH  = 70_000.0    # below = dikkat bölgesi
_BTC_WEAK   = 65_000.0    # below = zayıflama sinyali

_XAUUSD_BREAKOUT = 3_800.0  # below = altın güç kaybediyor            [anlık: ~4,542]
_XAGUSD_CONFIRM  = 60.0     # below = gümüş momentumu kırılıyor       [anlık: ~75]
_XAUXAG_HIGH     = 75.0     # ratio > 75 = gümüş ucuz, altına göre    [anlık: ~60]

_XCUUSD_HEALTHY  = 10_000.0  # above = endüstriyel talep sağlıklı     [anlık: ~14K]


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
    dxy   = _val(snapshots, AssetCode.DXY)
    brent = _val(snapshots, AssetCode.BRENT)
    us10y = _val(snapshots, AssetCode.US10Y)
    us02y = _val(snapshots, AssetCode.US02Y)
    m2    = _val(snapshots, AssetCode.M2SL)

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

    total = dxy_score + energy_score + yield_score + m2_score
    if total >= 4:
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
    hyg   = _val(snapshots, AssetCode.HYG)
    jnk   = _val(snapshots, AssetCode.JNK)
    btcd  = _val(snapshots, AssetCode.BTC_DOMINANCE)
    usdtd = _val(snapshots, AssetCode.USDT_DOMINANCE)
    gold  = _val(snapshots, AssetCode.XAUUSD)
    qqq   = _val(snapshots, AssetCode.QQQ)

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

    total = credit_score + btcd_score + usdt_score + haven_score
    if total >= 4:
        status: AppetiteCode = "STRONG"
        summary = "Risk iştahı güçlü — piyasa risk almaya hazır."
    elif total >= 1:
        status = "MODERATE"
        summary = "Risk iştahı orta — bazı sinyaller destekliyor, bazıları uyarıyor."
    elif total >= -2:
        status = "WEAK"
        summary = "Risk iştahı zayıf — piyasa dikkatli, teyit olmadan adım atma."
    else:
        status = "CRISIS"
        summary = "Risk iştahı çökmüş — kredi ve kripto aynı anda baskı altında."

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

def _build_asset_signals(snapshots: dict[AssetCode, MarketSnapshot]) -> tuple[AssetSignal, ...]:
    signals: list[AssetSignal] = []

    btc   = _val(snapshots, AssetCode.BTCUSD)
    btcd  = _val(snapshots, AssetCode.BTC_DOMINANCE)
    usdtd = _val(snapshots, AssetCode.USDT_DOMINANCE)
    hyg   = _val(snapshots, AssetCode.HYG)
    dxy   = _val(snapshots, AssetCode.DXY)
    brent = _val(snapshots, AssetCode.BRENT)
    gold  = _val(snapshots, AssetCode.XAUUSD)
    silver= _val(snapshots, AssetCode.XAGUSD)
    copper= _val(snapshots, AssetCode.XCUUSD)
    qqq   = _val(snapshots, AssetCode.QQQ)
    us10y = _val(snapshots, AssetCode.US10Y)
    us02y = _val(snapshots, AssetCode.US02Y)

    # --- BTC ---
    if btc is None:
        btc_status: SignalStatus = "VERİ_YOK"
        btc_reason = "BTC verisi yok."
    else:
        confirmations = 0
        total_checks = 4
        reasons: list[str] = []
        if btc > _BTC_STRONG:
            confirmations += 1
            reasons.append(f"fiyat güçlü (${_fmt(btc)})")
        elif btc < _BTC_WEAK:
            reasons.append(f"fiyat zayıf (${_fmt(btc)}) — destek testinde")
        else:
            reasons.append(f"fiyat izleme bölgesinde (${_fmt(btc)})")

        if btcd is not None and btcd > _BTCD_DOMINANT:
            confirmations += 1
            reasons.append("BTC.D dominant")
        elif btcd is not None:
            reasons.append(f"BTC.D zayıf (%{_fmt(btcd)})")

        if usdtd is not None and usdtd < _USDTD_SAFE:
            confirmations += 1
            reasons.append("USDT.D normal (para akıyor)")
        elif usdtd is not None:
            reasons.append(f"USDT.D yüksek (%{_fmt(usdtd)}) — kaçış var")

        if hyg is not None and hyg > _HYG_HEALTHY:
            confirmations += 1
            reasons.append("kredi sağlam")
        elif hyg is not None:
            reasons.append(f"kredi baskılı ({_fmt(hyg)})")

        if dxy is not None and dxy < _DXY_STRONG:
            confirmations += 1
            total_checks += 1
            reasons.append("DXY baskılı değil")

        ratio = confirmations / total_checks
        if ratio >= 0.75:
            btc_status = "CONFIRMED"
        elif ratio >= 0.5:
            btc_status = "PENDING"
        elif btc < _BTC_WEAK:
            btc_status = "BLOCKING"
        else:
            btc_status = "PENDING"

        btc_reason = " / ".join(reasons[:3])

    signals.append(AssetSignal(
        asset_code="BTCUSD",
        asset_name="Bitcoin",
        status=btc_status,
        reason=btc_reason,
        value=btc,
        unit="usd",
    ))

    # --- BRENT ---
    if brent is None:
        brent_status: SignalStatus = "VERİ_YOK"
        brent_reason = "Brent verisi yok."
    elif brent > _BRENT_HIGH:
        brent_status = "BLOCKING"
        brent_reason = f"Jeopolitik prim hâlâ aktif (${_fmt(brent)}) — enerji/savaş riski çözülmedi"
    elif brent > _BRENT_WARN:
        brent_status = "PENDING"
        brent_reason = f"İzleme bölgesinde (${_fmt(brent)}) — kalıcı düşüş teyidi gerekli"
    else:
        brent_status = "CONFIRMED"
        brent_reason = f"Enerji baskısı azaldı (${_fmt(brent)}) — risk rotasyonu için yeşil ışık"

    signals.append(AssetSignal(
        asset_code="BRENT",
        asset_name="Brent Ham Petrol",
        status=brent_status,
        reason=brent_reason,
        value=brent,
        unit="usd/bbl",
    ))

    # --- ALTIN ---
    if gold is None:
        gold_status: SignalStatus = "VERİ_YOK"
        gold_reason = "Altın verisi yok."
    elif gold > _XAUUSD_BREAKOUT:
        if us10y is not None and us02y is not None and (us10y - us02y) < 0:
            gold_status = "BLOCKING"
            gold_reason = f"Altın güçlü (${_fmt(gold)}) + yield inversiyonu — savunmacı kalın"
        else:
            gold_status = "PENDING"
            gold_reason = f"Altın güçlü (${_fmt(gold)}) — hedge talebi artıyor, yön belirsiz"
    else:
        gold_status = "NEUTRAL"
        gold_reason = f"Altın nötr bölgede (${_fmt(gold)}) — belirgin baskı yok"

    signals.append(AssetSignal(
        asset_code="XAUUSD",
        asset_name="Altın",
        status=gold_status,
        reason=gold_reason,
        value=gold,
        unit="usd/oz",
    ))

    # --- GÜMÜŞ ---
    if silver is None or gold is None:
        silver_status: SignalStatus = "VERİ_YOK"
        silver_reason = "Gümüş/Altın verisi yok."
    else:
        xauxag = gold / silver if silver > 0 else 999
        if silver > _XAGUSD_CONFIRM and copper is not None and copper > _XCUUSD_HEALTHY:
            silver_status = "CONFIRMED"
            silver_reason = f"Gümüş ayrışıyor (${_fmt(silver)}) + bakır destekliyor — stratejik metal rotasyonu"
        elif xauxag > _XAUXAG_HIGH:
            silver_status = "PENDING"
            silver_reason = f"Oran yüksek (Au/Ag={_fmt(xauxag, 0)}) — gümüş ucuz ama tetik gelmedi"
        else:
            silver_status = "NEUTRAL"
            silver_reason = f"Gümüş nötr (${_fmt(silver)}, Au/Ag={_fmt(xauxag, 0)})"

    signals.append(AssetSignal(
        asset_code="XAGUSD",
        asset_name="Gümüş",
        status=silver_status,
        reason=silver_reason,
        value=silver,
        unit="usd/oz",
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

    signals.append(AssetSignal(
        asset_code="HYG",
        asset_name="HYG / Yüksek Getirili Tahvil",
        status=hyg_status,
        reason=hyg_reason,
        value=hyg,
        unit="usd/share",
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

    signals.append(AssetSignal(
        asset_code="QQQ",
        asset_name="QQQ / Nasdaq ETF",
        status=qqq_status,
        reason=qqq_reason,
        value=qqq,
        unit="usd/share",
    ))

    return tuple(signals)


# ---------------------------------------------------------------------------
# Katman 3 — Teyit Listesi
# ---------------------------------------------------------------------------

def _build_confirmation_checklist(
    snapshots: dict[AssetCode, MarketSnapshot],
) -> tuple[ConfirmationItem, ...]:
    brent  = _val(snapshots, AssetCode.BRENT)
    gold   = _val(snapshots, AssetCode.XAUUSD)
    silver = _val(snapshots, AssetCode.XAGUSD)
    copper = _val(snapshots, AssetCode.XCUUSD)
    btc    = _val(snapshots, AssetCode.BTCUSD)
    us10y  = _val(snapshots, AssetCode.US10Y)
    us02y  = _val(snapshots, AssetCode.US02Y)
    dxy    = _val(snapshots, AssetCode.DXY)

    items: list[ConfirmationItem] = []

    # 1. Brent baskı altında mı?
    brent_met = brent is not None and brent < _BRENT_HIGH
    items.append(ConfirmationItem(
        signal=f"Brent enerji baskısı yok (${int(_BRENT_HIGH)} altında)",
        met=brent_met,
        current_value=f"${_fmt(brent)}" if brent else "N/A",
        threshold=f"< ${int(_BRENT_HIGH)}",
    ))

    # 2. DXY sıkılaşma yok
    dxy_met = dxy is not None and dxy < _DXY_STRONG
    items.append(ConfirmationItem(
        signal=f"DXY dolar sıkılaşması yok ({int(_DXY_STRONG)} altında)",
        met=dxy_met,
        current_value=_fmt(dxy) if dxy else "N/A",
        threshold=f"< {int(_DXY_STRONG)}",
    ))

    # 3. BTC risk iştahı pozitif
    btc_met = btc is not None and btc > _BTC_WATCH
    items.append(ConfirmationItem(
        signal=f"BTC risk iştahı pozitif (${int(_BTC_WATCH/1000)}K üzerinde)",
        met=btc_met,
        current_value=f"${_fmt(btc, 0)}" if btc else "N/A",
        threshold=f"> ${int(_BTC_WATCH):,}",
    ))

    # 4. Gümüş momentumu koruyor
    xauxag = (gold / silver) if (gold and silver and silver > 0) else None
    silver_met = silver is not None and silver > _XAGUSD_CONFIRM
    items.append(ConfirmationItem(
        signal=f"Gümüş momentumu koruyor (${int(_XAGUSD_CONFIRM)} üzerinde)",
        met=silver_met,
        current_value=f"${_fmt(silver)} (Au/Ag={_fmt(xauxag, 0)})" if silver else "N/A",
        threshold=f"> ${int(_XAGUSD_CONFIRM)}",
    ))

    # 5. Bakır endüstriyel talep sağlıklı
    copper_met = copper is not None and copper > _XCUUSD_HEALTHY
    items.append(ConfirmationItem(
        signal=f"Bakır endüstriyel talep sağlıklı (${int(_XCUUSD_HEALTHY):,}/ton üzerinde)",
        met=copper_met,
        current_value=f"${_fmt(copper, 0)}" if copper else "N/A",
        threshold=f"> ${int(_XCUUSD_HEALTHY):,}",
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
        missing_str = " · ".join(unmet[:2])
        owner = f"Eksik teyit: {missing_str}. Bu sinyalleri bekle."
    elif appetite.status == "WEAK":
        owner = "Checklist tamam ama risk iştahı zayıf — altın ve USDT.D sinyallerini izle."
    else:
        owner = "Sinyaller henüz tam hizalı değil. Bir sonraki güncellemede tekrar değerlendir."

    if blocking == 1:
        blocking_asset = next((s.asset_name for s in signals if s.status == "BLOCKING"), "bilinmeyen")
        verdict = f"Geçiş rejimi — {blocking_asset} çözüme kavuşmadan pozisyon açma."
    elif macro.regime == "TRANSITIONING" and checklist_met >= total_checks - 1:
        verdict = "Koşullar olgunlaşıyor — makro yön netleşene kadar bekle."
    elif confirmed >= 3:
        verdict = "Çoğu sinyal olumlu, makro tam netleşmedi — acele etme."
    else:
        verdict = "Rejim belirsizliğini koruyor — bekle, teyit topla, sonra karar ver."

    return decision, owner, verdict


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
    ) -> RegimeReport:
        snap_map: dict[AssetCode, MarketSnapshot] = {
            s.asset_symbol: s for s in snapshots
        }

        macro    = _analyze_macro(snap_map)
        appetite = _analyze_appetite(snap_map)
        signals  = _build_asset_signals(snap_map)
        checklist = _build_confirmation_checklist(snap_map)
        decision, owner, verdict = _make_decision(macro, appetite, signals, checklist)

        blocking = sum(1 for s in signals if s.status == "BLOCKING")
        confirmed = sum(1 for s in signals if s.status == "CONFIRMED")
        pending  = sum(1 for s in signals if s.status == "PENDING")

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
            news_headlines=news_headlines,
            blocking_count=blocking,
            confirmed_count=confirmed,
            pending_count=pending,
        )


__all__ = [name for name in globals() if not name.startswith("_")]
