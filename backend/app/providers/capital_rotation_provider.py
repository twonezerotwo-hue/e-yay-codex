"""
CapitalRotationProvider — Sermaye Rotasyonu ve Çapraz Varlık Korelasyon Analizi.

Para nereye gidiyor?
  DOLAR_GÜCÜ (DXY) ⇄ TAHVİL (TLT/SHY) ⇄ ALTIN/GÜMÜŞ (GLD/XAG) ⇄ PETROL (OIL) ⇄ BTC

Hesaplamalar:
  1. Bireysel 30g momentum (her varlık sınıfı için)
  2. Çapraz oran trendleri — GLD/TLT, BTC/GLD, TLT/SPY, HYG/LQD, BTC/DXY, GLD/DXY
  3. Rolling 30g korelasyon matrisi — 8 çift
  4. Tüm 7 sınıf için ağırlıklı skor — sıralı liste
  5. Özet + önemli sinyal tespiti
  6. AI-ready context string

Cache: 5 dakika TTL.
PAPER_SAFE / NO_EXECUTION — sadece gözlem ve analiz.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Çıktı dataclass'ları
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssetClassScore:
    """Tek bir varlık sınıfının para akış skoru."""
    name: str           # "ALTIN", "TAHVİL", "BTC", "HİSSE", "DOLAR_GÜCÜ", "PETROL", "GÜMÜŞ"
    score: float        # -1.5 → +1.5 arası normalize
    momentum_30d: float # O sınıfın ana varlığının 30g % değişimi (referans)
    direction: str      # "GİRİŞ" | "ÇIKIŞ" | "NÖTR"


@dataclass(frozen=True)
class KeyInsight:
    """Tek satırlık, sade dilde analiz cümlesi."""
    icon: str           # "🔴" | "🟡" | "🟢" | "⚠️"
    text: str           # "TLT/SPY -8.3% — hisse tahvilden 8 puan önde, risk-on devam ediyor"
    importance: int     # 1-3 (3 = en önemli)


@dataclass(frozen=True)
class RatioSignal:
    """İki varlık arasındaki oran sinyali."""
    pair: str
    value: float
    delta_30d_pct: float
    trend: str              # "RISING" | "FALLING" | "FLAT"
    meaning: str


@dataclass(frozen=True)
class CorrelationPair:
    """İki varlık arasındaki 30-günlük korelasyon."""
    pair: str
    corr_30d: float
    regime: str
    explanation: str = ""   # Pariteye özel 1 cümle anlamlandırma


@dataclass(frozen=True)
class CapitalRotation:
    """Sermaye rotasyon analizi çıktısı."""
    primary_flow: str               # En güçlü para akışı
    secondary_flow: str | None
    conviction: int                 # 0-100
    class_scores: tuple[AssetClassScore, ...]   # Tüm sınıflar sıralı (en yüksek → en düşük)
    key_insights: tuple[KeyInsight, ...]        # 3-5 sade analiz cümlesi
    synthesis: str                  # 1 cümlelik özet
    ratios: tuple[RatioSignal, ...]
    correlations: tuple[CorrelationPair, ...]
    rotation_context: str           # AI prompt'a direkt enjekte edilir
    error: str | None


# ---------------------------------------------------------------------------
# yfinance OHLCV konfigürasyonu
# ---------------------------------------------------------------------------

_ROTATION_TICKERS: dict[str, dict] = {
    "BTC":  {"ticker": "BTC-USD",  "period": "120d", "mult": 1.0},
    "GLD":  {"ticker": "GC=F",     "period": "120d", "mult": 1.0},
    "XAG":  {"ticker": "SI=F",     "period": "120d", "mult": 1.0},
    "TLT":  {"ticker": "TLT",      "period": "120d", "mult": 1.0},
    "SHY":  {"ticker": "SHY",      "period": "120d", "mult": 1.0},
    "SPY":  {"ticker": "SPY",      "period": "120d", "mult": 1.0},
    "HYG":  {"ticker": "HYG",      "period": "120d", "mult": 1.0},
    "LQD":  {"ticker": "LQD",      "period": "120d", "mult": 1.0},
    "DXY":  {"ticker": "DX-Y.NYB", "period": "120d", "mult": 1.0},
    "OIL":  {"ticker": "BZ=F",     "period": "120d", "mult": 1.0},
}

# Her varlık sınıfının "ana göstergesi" — momentum referansı için
_CLASS_MAIN_ASSET: dict[str, str] = {
    "ALTIN":      "GLD",
    "GÜMÜŞ":      "XAG",
    "TAHVİL":     "TLT",
    "BTC":        "BTC",
    "HİSSE":      "SPY",
    "DOLAR_GÜCÜ": "DXY",   # DXY artık "NAKİT" değil — dolar gücü ölçüsü
    "PETROL":     "OIL",
}

# ---------------------------------------------------------------------------
# Önbellek
# ---------------------------------------------------------------------------

_ROT_CACHE:    CapitalRotation | None = None
_ROT_CACHE_TS: float = 0.0
_ROT_CACHE_TTL = 180.0  # 3 dk — yfinance ile uyumlu (teknik provider ile aynı sıklık)


# ---------------------------------------------------------------------------
# Veri çekimi
# ---------------------------------------------------------------------------

def _fetch_close(name: str, cfg: dict) -> tuple[str, np.ndarray | None]:
    import yfinance as yf
    try:
        df = yf.download(
            cfg["ticker"], period=cfg["period"], interval="1d",
            auto_adjust=True, progress=False,
        )
        if df is None or df.empty or len(df) < 32:
            return name, None
        if hasattr(df.columns, "levels"):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        if "Close" not in df.columns:
            return name, None
        arr = df["Close"].dropna().to_numpy(dtype=float) * cfg["mult"]
        return name, arr
    except Exception as exc:
        logger.debug("CapitalRotation _fetch_close %s: %s", cfg["ticker"], exc)
        return name, None


# ---------------------------------------------------------------------------
# Matematik
# ---------------------------------------------------------------------------

def _momentum_30d(series: np.ndarray) -> float:
    if len(series) < 31:
        return 0.0
    old, new = series[-31], series[-1]
    if old <= 0:
        return 0.0
    return round((new - old) / old * 100, 2)


def _rolling_corr(a: np.ndarray, b: np.ndarray, window: int = 30) -> float | None:
    min_len = min(len(a), len(b))
    if min_len < window + 2:
        return None
    a_tail = a[-window - 1:]
    b_tail = b[-window - 1:]
    ra = np.diff(a_tail) / (a_tail[:-1] + 1e-12)
    rb = np.diff(b_tail) / (b_tail[:-1] + 1e-12)
    if np.std(ra) < 1e-10 or np.std(rb) < 1e-10:
        return 0.0
    corr = float(np.corrcoef(ra, rb)[0, 1])
    return round(corr, 3) if not np.isnan(corr) else 0.0


def _corr_regime(corr: float) -> str:
    if corr <= -0.60:   return "GÜÇLÜ_TERS"
    if corr <= -0.30:   return "ORTA_TERS"
    if corr <   0.30:   return "BAĞIMSIZ"
    if corr <   0.60:   return "ORTA_POZİTİF"
    return "GÜÇLÜ_POZİTİF"


def _trend(delta: float) -> str:
    if delta > 1.5:     return "RISING"
    if delta < -1.5:    return "FALLING"
    return "FLAT"


# ---------------------------------------------------------------------------
# Oran sinyalleri
# ---------------------------------------------------------------------------

_RATIO_DEFS: list[dict] = [
    {
        "pair": "GLD/TLT", "num": "GLD", "den": "TLT",
        "up":   "Altın tahvil üzerinde güçleniyor — enflasyon/güvensizlik baskısı",
        "down": "Tahvil altın üzerinde güçleniyor — deflasyon/güvenli liman talebi",
        "flat": "Altın–tahvil dengeli",
    },
    {
        "pair": "BTC/GLD", "num": "BTC", "den": "GLD",
        "up":   "Kripto altın üzerinde baskın — spekülatif risk iştahı yüksek",
        "down": "Altın kriptoya baskın — güvenli varlık tercihi güçlü",
        "flat": "BTC–altın dengeli",
    },
    {
        "pair": "TLT/SPY", "num": "TLT", "den": "SPY",
        "up":   "Tahvil hisse üzerinde güçleniyor — savunmacı rotasyon başladı",
        "down": "Hisse tahvil üzerinde baskın — risk-on ortam devam ediyor",
        "flat": "Tahvil–hisse dengeli",
    },
    {
        "pair": "HYG/LQD", "num": "HYG", "den": "LQD",
        "up":   "Yüksek getiri IG'yi geçiyor — kredi risk iştahı güçlü",
        "down": "IG yüksek getiriyi geçiyor — kaliteye kaçış başladı",
        "flat": "HY–IG kredi dengeli",
    },
    {
        "pair": "BTC/DXY", "num": "BTC", "den": "DXY",
        "up":   "BTC dolar üzerinde güçleniyor — dolar zayıflarken kripto canlanıyor",
        "down": "Dolar BTC'ye baskın — güçlü dolar kripto değer kaybettiriyor",
        "flat": "BTC–dolar dengeli",
    },
    {
        "pair": "GLD/DXY", "num": "GLD", "den": "DXY",
        "up":   "Altın dolar üzerinde baskın — dolar güçlü olsa da altın tutuyor",
        "down": "Dolar altına baskın — güçlü dolar altın değer kaybettiriyor",
        "flat": "Altın–dolar dengeli",
    },
]

_CORR_PAIRS: list[tuple[str, str]] = [
    ("BTC", "DXY"), ("BTC", "GLD"), ("BTC", "SPY"),
    ("GLD", "TLT"), ("GLD", "DXY"),
    ("HYG", "SPY"), ("TLT", "SPY"), ("OIL", "DXY"),
]

# Her parite için 1 cümle anlamlandırma — UI sadece valid matriste gösterir
_CORR_EXPLAIN: dict[str, str] = {
    "BTC/DXY": "Negatif ilişki klasik risk-on; pozitif ilişki normale göre dikkat gerektirir.",
    "BTC/GLD": "Birlikte hareket ediyorsa piyasa ikisini hedge/risk alternatifi gibi fiyatlıyor olabilir.",
    "BTC/SPY": "BTC hisseyle birlikte hareket ediyorsa kripto risk-on/risk-off davranışına bağlıdır.",
    "GLD/TLT": "Altın ve tahvil birlikteyse güvenli liman talebi ortak olabilir.",
    "GLD/DXY": "Altın dolar güçlenirken de yükseliyorsa hedge talebi güçlü olabilir.",
    "HYG/SPY": "Kredi ve hisse aynı yöndeyse risk iştahı daha sağlıklı görünür.",
    "TLT/SPY": "Ters hareket klasik risk-on/risk-off ayrımını gösterir.",
    "OIL/DXY": "Petrol-dolar ilişkisi arz/jeopolitik veya emtia-dolar etkisini gösterebilir.",
}

# ---------------------------------------------------------------------------
# Varlık sınıfı skorlaması
# ---------------------------------------------------------------------------
# Her sınıf için katkı sinyalleri: (sinyal_adı, katsayı)
# Pozitif katsayı → o sinyal güçlenince o sınıfa para giriyor demek
_FLOW_SIGNALS: dict[str, list[tuple[str, float]]] = {
    "ALTIN":      [("GLD", 1.5), ("GLD/TLT", 1.0), ("GLD/DXY", 1.0), ("BTC/GLD", -0.5)],
    "GÜMÜŞ":      [("XAG", 1.5), ("GLD/TLT", 0.5), ("GLD/DXY", 0.5)],
    "TAHVİL":     [("TLT", 1.5), ("SHY", 0.8), ("TLT/SPY", 1.0), ("GLD/TLT", -0.5)],
    "BTC":        [("BTC", 1.5), ("BTC/GLD", 0.8), ("BTC/DXY", 1.0)],
    "HİSSE":      [("SPY", 1.5), ("HYG/LQD", 0.5), ("TLT/SPY", -0.8)],
    # DXY = dolar gücü ölçüsü; "para nereye akıyor" değil, dolar momentum
    "DOLAR_GÜCÜ": [("DXY", 1.5), ("BTC/DXY", -0.5), ("GLD/DXY", -0.5)],
    "PETROL":     [("OIL", 2.0)],
}


def _score_class(class_name: str, momenta: dict[str, float]) -> float:
    """
    Verilen varlık sınıfı için normalize edilmiş para akış skoru hesaplar.
    Döner: -1.5 → +1.5 arası float
    """
    signals = _FLOW_SIGNALS.get(class_name, [])
    total_weight = sum(abs(w) for _, w in signals)
    if total_weight == 0:
        return 0.0

    score = 0.0
    for sig_key, weight in signals:
        if sig_key in momenta:
            # Normalize: 5% hareket = tam 1 puan
            m = max(-1.5, min(1.5, momenta[sig_key] / 5.0))
            score += m * weight

    return round(score / total_weight, 4)


def _direction(score: float) -> str:
    if score > 0.15:    return "GİRİŞ"
    if score < -0.15:   return "ÇIKIŞ"
    return "NÖTR"


# ---------------------------------------------------------------------------
# Veri kalitesi kontrolleri — sanity guard
# ---------------------------------------------------------------------------

def _check_return_quality(momenta: dict[str, float]) -> str | None:
    """5+ asset aynı momentum'a sahipse veri serileri güvenilir değil.

    yfinance race condition'ı veya cache contamination tipik bu pattern'i üretir.
    Tolerance 0.05% — gerçek piyasada bu kadar yakın oluşma ihtimali yok.
    """
    base_keys = {"BTC", "GLD", "XAG", "TLT", "SHY", "SPY", "HYG", "LQD", "DXY", "OIL"}
    base = {k: round(v, 2) for k, v in momenta.items() if k in base_keys}
    if len(base) < 5:
        return None
    # Aynı değere yakın olanları say
    counts: dict[float, int] = {}
    for v in base.values():
        # 0.05% tolerance ile bucket'le
        bucket = round(v * 20) / 20
        counts[bucket] = counts.get(bucket, 0) + 1
    max_same = max(counts.values()) if counts else 0
    if max_same >= 5:
        return "identical_returns_across_assets"
    return None


def _check_correlation_quality(corrs: list["CorrelationPair"]) -> str | None:
    """Korelasyonların çoğu |c|>=0.95 ise matris degenere.

    Gerçek piyasada 8 çapraz çiftin hepsi 1.00 olamaz — bu yfinance race veya
    aynı seri kullanılması demek.
    """
    if len(corrs) < 5:
        return None
    extreme = sum(1 for c in corrs if abs(c.corr_30d) >= 0.95)
    if extreme / len(corrs) >= 0.75:
        return "degenerate_correlation_matrix"
    return None


# ---------------------------------------------------------------------------
# Önemli sinyal tespiti
# ---------------------------------------------------------------------------

def _extract_key_insights(
    ratios: list[RatioSignal],
    corrs: list[CorrelationPair],
    momenta: dict[str, float],
) -> list[KeyInsight]:
    """
    Veriden en anlamlı 3-5 öngörüyü sade Türkçe cümleler olarak çıkarır.
    """
    insights: list[KeyInsight] = []

    # 1. TLT/SPY — risk-on / savunmacı sinyal
    tlt_spy = next((r for r in ratios if r.pair == "TLT/SPY"), None)
    if tlt_spy:
        if tlt_spy.delta_30d_pct < -5.0:
            insights.append(KeyInsight(
                icon="🟢",
                text=f"TLT/SPY {tlt_spy.delta_30d_pct:+.1f}% — hisse tahvilden {abs(tlt_spy.delta_30d_pct):.0f} puan önde, risk-on ortam net",
                importance=3,
            ))
        elif tlt_spy.delta_30d_pct > 5.0:
            insights.append(KeyInsight(
                icon="🔴",
                text=f"TLT/SPY {tlt_spy.delta_30d_pct:+.1f}% — tahvil hisseyi geçiyor, savunmacı rotasyon aktif",
                importance=3,
            ))

    # 2. GLD/DXY — dolar vs altın
    gld_dxy = next((r for r in ratios if r.pair == "GLD/DXY"), None)
    if gld_dxy:
        if gld_dxy.delta_30d_pct < -3.0:
            insights.append(KeyInsight(
                icon="🔴",
                text=f"GLD/DXY {gld_dxy.delta_30d_pct:+.1f}% — DXY 30g momentum altını baskıladı (spot seviye ≠ momentum; ikisini ayrı oku)",
                importance=2,
            ))
        elif gld_dxy.delta_30d_pct > 3.0:
            insights.append(KeyInsight(
                icon="🟢",
                text=f"GLD/DXY {gld_dxy.delta_30d_pct:+.1f}% — altın dolar karşısında da güçleniyor; güvenli liman talebi derin",
                importance=2,
            ))

    # 3. GLD/TLT — altın vs tahvil
    gld_tlt = next((r for r in ratios if r.pair == "GLD/TLT"), None)
    if gld_tlt:
        if gld_tlt.delta_30d_pct > 3.0:
            insights.append(KeyInsight(
                icon="🟡",
                text=f"GLD/TLT {gld_tlt.delta_30d_pct:+.1f}% — altın tahvile baskın; enflasyon koruması güvenli liman faizini geçiyor",
                importance=2,
            ))
        elif gld_tlt.delta_30d_pct < -3.0:
            insights.append(KeyInsight(
                icon="🟡",
                text=f"GLD/TLT {gld_tlt.delta_30d_pct:+.1f}% — tahvil altına baskın; real faiz talebi enflasyon korkusunu bastırıyor",
                importance=2,
            ))

    # 4. BTC/DXY — dolar baskısı altında kripto
    btc_dxy = next((r for r in ratios if r.pair == "BTC/DXY"), None)
    if btc_dxy and abs(btc_dxy.delta_30d_pct) > 3.0:
        if btc_dxy.delta_30d_pct < -3.0:
            insights.append(KeyInsight(
                icon="🔴",
                text=f"BTC/DXY {btc_dxy.delta_30d_pct:+.1f}% — dolar 30g momentumu kripto ve altını sıkıştırıyor (DXY spot düşük olsa da)",
                importance=2,
            ))
        else:
            insights.append(KeyInsight(
                icon="🟢",
                text=f"BTC/DXY {btc_dxy.delta_30d_pct:+.1f}% — dolar zayıflarken kripto ön plana geçiyor",
                importance=2,
            ))

    # 5. BTC/SPY korelasyonu — ayrışma var mı?
    btc_spy_corr = next((c for c in corrs if c.pair == "BTC/SPY"), None)
    if btc_spy_corr:
        if abs(btc_spy_corr.corr_30d) < 0.15:
            insights.append(KeyInsight(
                icon="⚠️",
                text=f"BTC/SPY korelasyon {btc_spy_corr.corr_30d:+.2f} — kripto hisseden bağımsız hareket ediyor; ayrı dinamik var",
                importance=2,
            ))
        elif btc_spy_corr.corr_30d > 0.7:
            insights.append(KeyInsight(
                icon="🟡",
                text=f"BTC/SPY korelasyon {btc_spy_corr.corr_30d:+.2f} — kripto hisse ile birlikte hareket ediyor; risk-on/off birleşik",
                importance=1,
            ))

    # 6. Altın + tahvil birlikte güçlüyse — hedge talebi
    gld_m = momenta.get("GLD", 0)
    tlt_m = momenta.get("TLT", 0)
    if gld_m > 3.0 and tlt_m > 1.0:
        insights.append(KeyInsight(
            icon="⚠️",
            text=f"Altın ({gld_m:+.1f}%) ve tahvil ({tlt_m:+.1f}%) aynı anda güçleniyor — risk-off hedge talebi belirgin",
            importance=3,
        ))

    # 7. BTC/GLD oranı — spekülatif iştah
    btc_gld = next((r for r in ratios if r.pair == "BTC/GLD"), None)
    if btc_gld and abs(btc_gld.delta_30d_pct) > 8.0:
        if btc_gld.delta_30d_pct > 8.0:
            insights.append(KeyInsight(
                icon="🟢",
                text=f"BTC/GLD {btc_gld.delta_30d_pct:+.1f}% — kripto altından belirgin kopuş; spekülatif sermaye risk-on yapıyor",
                importance=2,
            ))
        else:
            insights.append(KeyInsight(
                icon="🔴",
                text=f"BTC/GLD {btc_gld.delta_30d_pct:+.1f}% — altın kriptoyu ciddi geçiyor; güvenli varlık tercihi baskın",
                importance=2,
            ))

    # En önemliden en az önemliye sırala, max 5 tane
    insights.sort(key=lambda x: -x.importance)
    return insights[:5]


# ---------------------------------------------------------------------------
# Synthesis cümlesi
# ---------------------------------------------------------------------------

def _detect_rotation_pattern(class_scores: list[AssetClassScore]) -> str | None:
    """
    Tabloya bakarak klasik rotasyon kalıplarını tespit eder.
    primary tek başına net değilse bile, GİRİŞ + ÇIKIŞ kombinasyonundan hikaye çıkar.

    Dönen kalıp adları:
      "DEFENSIVE_RISK_ON"   — Hisse+Dolar gücü (DXY) giriyor, Altın/BTC çıkıyor (dolar güçlü)
      "PURE_RISK_ON"        — Hisse+BTC giriyor, Dolar gücü (DXY)/Tahvil çıkıyor
      "FLIGHT_TO_SAFETY"    — Altın+Tahvil+Dolar gücü (DXY) giriyor, Hisse/BTC çıkıyor
      "INFLATION_HEDGE"     — Altın+Emtia giriyor, Tahvil çıkıyor
      "CRYPTO_LEADERSHIP"   — BTC öncü, geri kalan karışık
      None                  — gerçekten karışık, hiç kalıp yok
    """
    enters = {cs.name for cs in class_scores if cs.direction == "GİRİŞ"}
    exits  = {cs.name for cs in class_scores if cs.direction == "ÇIKIŞ"}

    # Hisse + Dolar gücü giriş, Metal/Kripto çıkış → defansif risk-on
    if {"HİSSE", "DOLAR_GÜCÜ"} <= enters and {"ALTIN", "BTC"} <= exits:
        return "DEFENSIVE_RISK_ON"

    # Hisse + BTC giriş, Dolar gücü/Tahvil çıkış → saf risk-on
    if {"HİSSE", "BTC"} <= enters and ({"DOLAR_GÜCÜ"} <= exits or {"TAHVİL"} <= exits):
        return "PURE_RISK_ON"

    # Altın + Tahvil + Dolar gücü en az 2 tanesi giriş, Hisse/BTC çıkış → güvenli liman
    safe = enters & {"ALTIN", "TAHVİL", "DOLAR_GÜCÜ"}
    if len(safe) >= 2 and ({"HİSSE"} <= exits or {"BTC"} <= exits):
        return "FLIGHT_TO_SAFETY"

    # Altın+Emtia giriyor, Tahvil çıkıyor → enflasyon hedgesi
    if {"ALTIN"} <= enters and ({"PETROL"} <= enters or {"GÜMÜŞ"} <= enters) and {"TAHVİL"} <= exits:
        return "INFLATION_HEDGE"

    # BTC tek başına lider — diğerleri karışık
    btc = next((cs for cs in class_scores if cs.name == "BTC"), None)
    if btc and btc.score > 1.0 and len(enters) <= 2:
        return "CRYPTO_LEADERSHIP"

    return None


def _build_synthesis(
    primary: str,
    secondary: str | None,
    conviction: int,
    class_scores: list[AssetClassScore],
    momenta: dict[str, float],
) -> str:
    """Tüm tabloyu tek cümleyle özetler."""
    gld_m  = momenta.get("GLD", 0)
    btc_m  = momenta.get("BTC", 0)
    spy_m  = momenta.get("SPY", 0)
    dxy_m  = momenta.get("DXY", 0)
    tlt_m  = momenta.get("TLT", 0)

    # KARISIK durumunda bile kalıp tespiti dene — conviction düşük olabilir
    # ama GİRİŞ/ÇIKIŞ dağılımı net bir hikaye anlatıyor olabilir
    if primary == "KARISIK":
        pattern = _detect_rotation_pattern(class_scores)
        enters = [cs.name for cs in class_scores if cs.direction == "GİRİŞ"]
        exits  = [cs.name for cs in class_scores if cs.direction == "ÇIKIŞ"]

        if pattern == "DEFENSIVE_RISK_ON":
            return (
                f"Defansif risk-on: hisse ({spy_m:+.1f}%) ve nakit ({dxy_m:+.1f}%) birlikte giriş alıyor — "
                f"sermaye büyümeye gidiyor ama dolar güçlü kaldığı için altın ({gld_m:+.1f}%) ve "
                f"kripto ({btc_m:+.1f}%) baskılanıyor. Klasik 'güçlü-dolar-büyümesi'."
            )
        if pattern == "PURE_RISK_ON":
            return (
                f"Saf risk-on: hisse ({spy_m:+.1f}%) ve kripto ({btc_m:+.1f}%) önde, "
                f"nakit/tahvilden çıkış var. Spekülatif iştah aktif."
            )
        if pattern == "FLIGHT_TO_SAFETY":
            return (
                f"Güvenli liman akışı: altın/tahvil/nakitten en az ikisi giriş alıyor, "
                f"hisse ({spy_m:+.1f}%) veya kripto ({btc_m:+.1f}%) baskı altında — risk-off."
            )
        if pattern == "INFLATION_HEDGE":
            return (
                f"Enflasyon hedgesi: altın ({gld_m:+.1f}%) ve emtia giriş alıyor, "
                f"tahvil ({tlt_m:+.1f}%) çıkıyor — enflasyon beklentisi yükseliyor."
            )
        if pattern == "CRYPTO_LEADERSHIP":
            return (
                f"Kripto liderliği: BTC ({btc_m:+.1f}%) öne çıkıyor, "
                f"diğer sınıflar karışık — bu özel bir alt-sınıf hareketi."
            )

        # Gerçekten karışık — net bir kalıp yok
        if enters and exits:
            return (
                f"Karışık akış: {'/'.join(enters[:2])} giriş alırken {'/'.join(exits[:2])} çıkıyor; "
                f"belirgin tek-yön rotasyonu yok, sektörel ayrışma var."
            )
        return "Son 30 günde sermaye akışı net bir yön çizmedi — tüm varlık sınıfları karışık momentum sergiliyor."

    if primary == "HİSSE" and dxy_m > 0:
        return (f"Hisse senetleri ({spy_m:+.1f}%) öne çıkıyor; dolar 30g momentum: {dxy_m:+.1f}% (spot seviye ayrı değerlendir). "
                f"Altın ({gld_m:+.1f}%), kripto ({btc_m:+.1f}%) ve tahvil ({tlt_m:+.1f}%) dolar momentumu altında baskılı; "
                "risk-on ama büyüme odaklı, güvenli limanlara sınırlı sermaye akıyor.")

    if primary == "ALTIN":
        return (f"Altın ({gld_m:+.1f}%) belirgin şekilde öne çıkıyor; "
                "enflasyon / jeopolitik risk beklentisi güvenli liman talebini canlandırıyor.")

    if primary == "BTC":
        return (f"Bitcoin ({btc_m:+.1f}%) alternatif varlık sınıfına güçlü sermaye girişini gösteriyor; "
                "spekülatif risk iştahı yüksek.")

    if primary == "TAHVİL":
        return (f"Tahvil ({tlt_m:+.1f}%) güvenli liman olarak öne çıkıyor; "
                "resesyon veya risk-off endişesi sermayeyi devlet tahviline yönlendiriyor.")

    if primary == "DOLAR_GÜCÜ":
        return (f"Dolar ({dxy_m:+.1f}%) tüm varlıkları baskılıyor; "
                "sermaye en güvenli park yeri olarak dolara (DXY) sığınıyor.")

    conv_str = "net" if conviction >= 50 else "zayıf"
    return (f"{primary} {conv_str} sermaye çekiyor"
            + (f", ikincil olarak {secondary}" if secondary else "")
            + f" (conviction {conviction}/100).")


# ---------------------------------------------------------------------------
# AI prompt context
# ---------------------------------------------------------------------------

_ASSET_TR: dict[str, str] = {
    "BTC": "Bitcoin", "GLD": "Altın", "XAG": "Gümüş", "TLT": "20Y Tahvil",
    "SHY": "Kısa Tahvil", "SPY": "S&P 500", "HYG": "HY Bono",
    "LQD": "IG Bono", "DXY": "Dolar", "OIL": "Petrol",
}


def _build_rotation_context(
    primary: str,
    secondary: str | None,
    conviction: int,
    class_scores: list[AssetClassScore],
    ratios: list[RatioSignal],
    corrs: list[CorrelationPair],
    momenta: dict[str, float],
    synthesis: str,
    key_insights: list[KeyInsight],
) -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "SERMAYE ROTASYONU VE KORELASYONlar",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"ÖZET: {synthesis}",
        f"PARA AKIŞ YÖNܒ: {primary}" + (f" / {secondary} (ikincil)" if secondary else "") + f"  |  conviction: {conviction}/100",
        "",
    ]

    # Sınıf skor tablosu
    lines.append("VARLIK SINIFI SIRALAMASI (30g ağırlıklı skor):")
    for cs in class_scores:
        bar = "▓" * max(0, min(8, int((cs.score + 1.5) / 3.0 * 8)))
        lines.append(f"  {cs.name:8s} {bar:8s} skor={cs.score:+.2f} | {cs.direction} | ana={cs.momentum_30d:+.1f}%")

    lines.append("")

    # Önemli sinyaller
    if key_insights:
        lines.append("ÖNEMLİ SİNYALLER:")
        for ki in key_insights:
            lines.append(f"  {ki.icon} {ki.text}")
        lines.append("")

    # Çapraz oran trendleri
    lines.append("ÇAPRAZ VARLIK ORANLARI (30g trend):")
    for r in ratios:
        arrow = "↑" if r.trend == "RISING" else ("↓" if r.trend == "FALLING" else "→")
        lines.append(f"  {r.pair} {arrow} {r.delta_30d_pct:+.1f}%: {r.meaning}")

    lines.append("")

    # Korelasyonlar
    lines.append("KORELASYONlar (30g rolling log-getiri):")
    for c in corrs:
        lines.append(f"  {c.pair}: {c.corr_30d:+.2f} [{c.regime}]")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ana provider
# ---------------------------------------------------------------------------

class CapitalRotationProvider:
    """
    Çapraz varlık korelasyon ve sermaye rotasyon analizi.
    5 dakika TTL önbellek. PAPER_SAFE / NO_EXECUTION.
    """

    def compute(self, force_refresh: bool = False) -> CapitalRotation:
        global _ROT_CACHE, _ROT_CACHE_TS
        now = time.monotonic()
        if (not force_refresh and _ROT_CACHE is not None
                and (now - _ROT_CACHE_TS) < _ROT_CACHE_TTL):
            return _ROT_CACHE
        result = self._compute_impl()
        if result.error is None:
            _ROT_CACHE = result
            _ROT_CACHE_TS = now
        return result

    def _compute_impl(self) -> CapitalRotation:
        try:
            # 1. OHLCV çekimi — max_workers=1 ile sıralı (yfinance thread race fix)
            closes: dict[str, np.ndarray] = {}
            with ThreadPoolExecutor(max_workers=1) as pool:
                futures = {
                    pool.submit(_fetch_close, name, cfg): name
                    for name, cfg in _ROTATION_TICKERS.items()
                }
                for fut in as_completed(futures, timeout=60):
                    key = futures[fut]
                    try:
                        k, arr = fut.result()
                        if arr is not None:
                            closes[k] = arr
                    except Exception as exc:
                        logger.debug("CapitalRotation future %s: %s", key, exc)

            if len(closes) < 3:
                return _error_result("data_insufficient: 3+ varlık verisi alınamadı.")

            # 2. Bireysel 30g momentumlar
            momenta: dict[str, float] = {
                name: _momentum_30d(arr) for name, arr in closes.items()
            }

            # 2a. Sanity: aynı momentum'a sahip 5+ asset varsa veri kalitesi şüpheli
            #     (yfinance race veya genel piyasa felaketi/cache hit'i değil — degenerate veri)
            quality_reason = _check_return_quality(momenta)
            if quality_reason:
                return _error_result(quality_reason)

            # 3. Oran sinyalleri
            ratio_signals: list[RatioSignal] = []
            for rd in _RATIO_DEFS:
                num_k, den_k = rd["num"], rd["den"]
                if num_k not in closes or den_k not in closes:
                    continue
                num_arr, den_arr = closes[num_k], closes[den_k]
                min_len = min(len(num_arr), len(den_arr))
                if min_len < 32:
                    continue
                num_t = num_arr[-min_len:]
                den_t = den_arr[-min_len:]
                if np.any(den_t <= 0):
                    continue
                ratio_s = num_t / den_t
                cur = float(ratio_s[-1])
                lkb = min(31, len(ratio_s) - 1)
                old = float(ratio_s[-lkb - 1])
                delta = round((cur - old) / old * 100, 2) if old > 0 else 0.0
                t = _trend(delta)
                meaning = rd["up"] if t == "RISING" else (rd["down"] if t == "FALLING" else rd["flat"])
                ratio_signals.append(RatioSignal(rd["pair"], round(cur, 4), delta, t, meaning))
                momenta[rd["pair"]] = delta

            # 4. Korelasyonlar — min 20 ortak veri noktası gerekli
            corr_signals: list[CorrelationPair] = []
            for a_k, b_k in _CORR_PAIRS:
                if a_k not in closes or b_k not in closes:
                    continue
                if min(len(closes[a_k]), len(closes[b_k])) < 22:  # 20 valid + 2 buffer
                    continue
                c = _rolling_corr(closes[a_k], closes[b_k])
                if c is None:
                    continue
                pair_name = f"{a_k}/{b_k}"
                corr_signals.append(CorrelationPair(
                    pair_name, c, _corr_regime(c),
                    explanation=_CORR_EXPLAIN.get(pair_name, ""),
                ))

            # 4a. Sanity: korelasyonların çoğu |c|>=0.95 ise matris degenere
            corr_reason = _check_correlation_quality(corr_signals)
            if corr_reason:
                return _error_result(corr_reason)

            # 5. Her varlık sınıfı için skor
            raw_scores: dict[str, float] = {
                cls: _score_class(cls, momenta)
                for cls in _FLOW_SIGNALS
            }

            # Sınıf skoru + yön + ana varlık momentumu
            scored: list[AssetClassScore] = []
            for cls, score in raw_scores.items():
                main_asset = _CLASS_MAIN_ASSET.get(cls, "")
                main_m     = momenta.get(main_asset, 0.0)
                scored.append(AssetClassScore(cls, score, main_m, _direction(score)))
            scored.sort(key=lambda x: -x.score)

            # 6. Primary / secondary / conviction
            primary    = scored[0].name if scored else "KARISIK"
            secondary  = scored[1].name if len(scored) > 1 and scored[1].score > 0.10 else None
            gap        = (scored[0].score - scored[1].score) if len(scored) > 1 else scored[0].score if scored else 0.0
            conviction = max(0, min(100, int(gap * 70)))
            if conviction < 12:
                primary, secondary = "KARISIK", None

            # 7. Önemli sinyaller
            key_insights = _extract_key_insights(ratio_signals, corr_signals, momenta)

            # 8. Synthesis
            synthesis = _build_synthesis(primary, secondary, conviction, scored, momenta)

            # 9. AI context
            context = _build_rotation_context(
                primary, secondary, conviction, scored,
                ratio_signals, corr_signals, momenta, synthesis, key_insights,
            )

            logger.info(
                "CapitalRotationProvider: akış=%s (%d/100) | %d oran | %d korelasyon",
                primary, conviction, len(ratio_signals), len(corr_signals),
            )

            return CapitalRotation(
                primary_flow=primary,
                secondary_flow=secondary,
                conviction=conviction,
                class_scores=tuple(scored),
                key_insights=tuple(key_insights),
                synthesis=synthesis,
                ratios=tuple(ratio_signals),
                correlations=tuple(corr_signals),
                rotation_context=context,
                error=None,
            )

        except Exception as exc:
            logger.warning("CapitalRotationProvider hata: %s", exc, exc_info=True)
            return _error_result(str(exc))


_ERROR_SYNTHESIS: dict[str, str] = {
    "identical_returns_across_assets":
        "Sermaye rotasyonu yorumu durduruldu: getiriler birden çok varlıkta aynı görünüyor, veri serileri güvenilir değil.",
    "degenerate_correlation_matrix":
        "Sermaye rotasyonu yorumu durduruldu: korelasyon matrisi degenere (çoğu çift +1.00/-1.00), veri serileri güvenilir değil.",
    "data_insufficient":
        "Sermaye rotasyonu yorumu durduruldu: yeterli veri yok.",
}


def _error_result(msg: str) -> CapitalRotation:
    # msg "code: detail" veya sadece "code" olabilir; ilk segmenti tablo lookup için kullan
    code = msg.split(":", 1)[0].strip()
    synth = _ERROR_SYNTHESIS.get(
        code, "Sermaye rotasyonu yorumu durduruldu: veri kalitesi şüpheli.",
    )
    return CapitalRotation(
        primary_flow="KARISIK", secondary_flow=None, conviction=0,
        class_scores=(), key_insights=(), synthesis=synth,
        ratios=(), correlations=(),
        rotation_context=synth,
        error=msg,
    )


__all__ = [
    "CapitalRotationProvider", "CapitalRotation",
    "AssetClassScore", "KeyInsight", "RatioSignal", "CorrelationPair",
]
