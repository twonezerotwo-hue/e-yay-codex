/**
 * Katman (layer) human-label haritalama yardımcıları — Dashboard redesign.
 *
 * ÖNEMLİ: Bu dosya SADECE kullanıcıya gösterilen Türkçe açıklama metinlerini
 * üretir. Backend'den gelen internal enum değerleri (RegimeCode, AppetiteCode
 * vb.) HİÇBİR ŞEKİLDE değiştirilmez/parse edilmez — agent/paper-trading karar
 * zinciri bu enum'ları okumaya devam eder; "human_label" yalnızca UI
 * açıklaması amaçlıdır (bkz. AssetGrid/MacroPanel kullanım yerleri).
 *
 * Eşleme tabloları, mevcut backend enum kümesini
 *   RegimeCode:   RISK_ON | TRANSITIONING | DEFENSIVE | CRISIS
 *   AppetiteCode: STRONG | MODERATE | WEAK | CRISIS
 * VE talepte belirtilen genişletilmiş etiketleri
 *   (CONTROLLED_RISK_ON, AGGRESSIVE_RISK_ON, NEUTRAL, RISK_OFF, MEDIUM,
 *    DEFENSIVE, PANIC)
 * birlikte kapsar — geriye+ileriye dönük uyumluluk için. Tabloda olmayan bir
 * değer ham haliyle gösterilir (asla "undefined" göstermez).
 */

// ── Makro Zemin / Para Rejimi (KATMAN 2) — internal_label → human_label ─────

const REGIME_HUMAN_LABELS: Record<string, string> = {
  // Mevcut backend enum'ları (RegimeCode) — DEĞİŞMEDEN okunur
  RISK_ON:            "Güçlü risk-on zemini",
  TRANSITIONING:      "Likidite destekli geçiş",
  DEFENSIVE:          "Savunmacı piyasa",
  CRISIS:             "Sermaye koruma / kriz",
  // Talepte belirtilen genişletilmiş etiketler (ileriye dönük uyum)
  CONTROLLED_RISK_ON: "Kontrollü risk-on",
  AGGRESSIVE_RISK_ON: "Güçlü risk-on zemini",
  NEUTRAL:            "Bekle-gör makro zemin",
  RISK_OFF:           "Savunmacı piyasa",
};

export function mapRegimeToHumanLabel(regime: string): string {
  return REGIME_HUMAN_LABELS[regime] ?? regime;
}

// ── Risk İştahı / Piyasa Davranışı (KATMAN 3) — internal_label → human_label ─

const RISK_APPETITE_HUMAN_LABELS: Record<string, string> = {
  // Mevcut backend enum'ları (AppetiteCode) — DEĞİŞMEDEN okunur
  STRONG:    "Geniş risk alma",
  MODERATE:  "Seçici risk alma",
  WEAK:      "Risk iştahı zayıf",
  CRISIS:    "Panik / sermaye kaçışı",
  // Talepte belirtilen genişletilmiş etiketler (ileriye dönük uyum)
  MEDIUM:    "Seçici risk alma",
  DEFENSIVE: "Savunmacı davranış",
  PANIC:     "Panik / sermaye kaçışı",
};

export function mapRiskAppetiteToHumanLabel(appetite: string): string {
  return RISK_APPETITE_HUMAN_LABELS[appetite] ?? appetite;
}

// ── Ham Gösterge → Katman katkısı eşlemesi ───────────────────────────────────

export interface IndicatorLayerMapping {
  /** Katkı sağladığı katman numarası/numaraları — örn. [1, 3] */
  layers: number[];
  /** UI'da "Katman katkısı" rozetinde gösterilecek kısa metin */
  label: string;
}

const INDICATOR_LAYER_MAP: Record<string, IndicatorLayerMapping> = {
  DXY:         { layers: [2],    label: "Katman 2 / Dolar Baskısı" },
  REAL_YIELD:  { layers: [2],    label: "Katman 2 / Finansal Sıkılık" },
  US10Y:       { layers: [2],    label: "Katman 2 / Faiz ve Büyüme Zemini" },
  YIELD_CURVE: { layers: [2],    label: "Katman 2 / Faiz ve Büyüme Zemini" },
  M2:          { layers: [2],    label: "Katman 2 / Likidite" },
  BRENT:       { layers: [1, 2], label: "Katman 1 + Katman 2 / Enerji Riski" },
  XLE:         { layers: [1, 2], label: "Katman 1 + Katman 2 / Enerji Sektörü" },
  HYG:         { layers: [3],    label: "Katman 3 / Kredi Sağlığı" },
  JNK:         { layers: [3],    label: "Katman 3 / Kredi Sağlığı" },
  HY_SPREAD:   { layers: [3],    label: "Katman 3 / Kredi Stresi" },
  LQD:         { layers: [3],    label: "Katman 3 / Investment Grade Kredi" },
  VIX:         { layers: [3],    label: "Katman 3 / Volatilite Stresi" },
  SP500:       { layers: [3],    label: "Katman 3 / Ana Hisse Risk İştahı" },
  QQQ:         { layers: [3],    label: "Katman 3 / Growth-Tech Risk İştahı" },
  IWM:         { layers: [3],    label: "Katman 3 / Piyasa Genişliği / Small Caps" },
  SMH:         { layers: [1, 3], label: "Katman 1 + Katman 3 / Semiconductor-AI Risk İştahı" },
  "BTC.D":     { layers: [1, 3], label: "Katman 1 + Katman 3 / Kripto İç Rotasyon" },
  BTC_D:       { layers: [1, 3], label: "Katman 1 + Katman 3 / Kripto İç Rotasyon" },
  "USDT.D":    { layers: [1, 3], label: "Katman 1 + Katman 3 / Stablecoin'e Kaçış" },
  USDT_D:      { layers: [1, 3], label: "Katman 1 + Katman 3 / Stablecoin'e Kaçış" },
  ETHUSD:      { layers: [1, 3], label: "Katman 1 + Katman 3 / Kripto Risk Davranışı" },
  XAUUSD:      { layers: [1, 3], label: "Katman 1 + Katman 3 / Hedge Talebi" },
  XAGUSD:      { layers: [1, 3], label: "Katman 1 + Katman 3 / Metal Rotasyonu" },
  XAUXAG:      { layers: [1],    label: "Katman 1 / Gold-Silver Rotation" },
  XCUUSD:      { layers: [1],    label: "Katman 1 / Sanayi Metal Sinyali" },
  FXI:         { layers: [1, 3], label: "Katman 1 + Katman 3 / Çin Risk İştahı" },
};

export function mapIndicatorToLayer(indicator: string): IndicatorLayerMapping | null {
  return INDICATOR_LAYER_MAP[indicator.toUpperCase()] ?? null;
}

// ── Birleşik Okuma sentezi (Katman 2 + Katman 3) ─────────────────────────────

export interface UnifiedReadingSynthesis {
  combinedRegime: string;
  meaning: string;
  impact: string;
}

/**
 * Makro Zemin (regime) ve Risk İştahı (appetite) internal kodlarını birleştirip
 * "Birleşik Okuma" kutusu için 3 satırlık sentez üretir. Girdi olarak SADECE
 * mevcut internal enum'ları kullanır — yeni bir backend alanı/endpoint
 * gerektirmez; agent/paper-trading zincirine dokunmaz.
 */
export function buildUnifiedReading(regime: string, appetite: string): UnifiedReadingSynthesis {
  const supportiveRegime  = regime === "RISK_ON" || regime === "AGGRESSIVE_RISK_ON" || regime === "CONTROLLED_RISK_ON";
  const transitioning     = regime === "TRANSITIONING";
  const defensiveRegime   = regime === "DEFENSIVE" || regime === "RISK_OFF";
  const crisisRegime      = regime === "CRISIS";

  const wideAppetite      = appetite === "STRONG";
  const selectiveAppetite = appetite === "MODERATE" || appetite === "MEDIUM";
  const weakAppetite      = appetite === "WEAK" || appetite === "DEFENSIVE";
  const panicAppetite     = appetite === "CRISIS" || appetite === "PANIC";

  if (crisisRegime || panicAppetite) {
    return {
      combinedRegime: "Sermaye koruma önceliğinde, savunmacı geçiş rejimi",
      meaning: "Hem makro zemin hem piyasa davranışı risk almaktan kaçıyor; sermaye korunması ön planda.",
      impact:  "Durum Odası savunmacı/izleme ağırlıklı sinyal üretir; yeni risk-on komutları kısıtlanır.",
    };
  }

  if (defensiveRegime || weakAppetite) {
    return {
      combinedRegime: "Temkinli zeminde seçici/zayıf risk alma rejimi",
      meaning: "Makro zemin risk almayı net desteklemiyor; piyasa davranışı da temkinli/seçici kalmayı tercih ediyor.",
      impact:  "Durum Odası asset bazlı, küçük ölçekli sinyaller üretir; agresif tüm-varlık long üretmez.",
    };
  }

  if (transitioning && (selectiveAppetite || wideAppetite)) {
    return {
      combinedRegime: "Likidite destekli ama hedge talebi süren geçiş rejimi",
      meaning: "Makro zemin risk almayı kısmen destekliyor; piyasa bunu geniş risk-on yerine seçici risk alma olarak fiyatlıyor.",
      impact:  "Durum Odası asset bazlı seçici sinyal üretir; agresif tüm-varlık long üretmez.",
    };
  }

  if (supportiveRegime && wideAppetite) {
    return {
      combinedRegime: "Geniş tabanlı risk-on zemini",
      meaning: "Makro zemin ve piyasa davranışı aynı yönde; risk alma geniş tabana yayılıyor.",
      impact:  "Durum Odası daha geniş kapsamlı onaylı sinyaller üretebilir; teyit/risk filtreleri yine de korunur.",
    };
  }

  return {
    combinedRegime: "Karışık sinyalli, bekle-gör rejimi",
    meaning: "Makro zemin ve piyasa davranışı net bir yönde hizalanmıyor; teyit eksikliği sürüyor.",
    impact:  "Durum Odası teyit gelene kadar izleme ağırlıklı, asset bazlı sinyal üretmeye devam eder.",
  };
}
