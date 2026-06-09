"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export type Lang = "tr" | "en";

// ---------------------------------------------------------------------------
// Turkish translations (default)
// ---------------------------------------------------------------------------

const TR = {
  header: {
    assets:     (n: number) => `${n} varlık`,
    live:       "● CANLI",
    simulation: "● SİMÜLASYON",
  },
  decision: {
    actionLabel: "Tavsiye Edilen Aksiyon",
    displayMap:  { AÇIL: "AÇIL", BEKLE: "BEKLE", KÜÇÜLT: "KÜÇÜLT", KAPAT: "KAPAT" } as Record<string, string>,
    actionMap:   {
      AÇIL:   "Risk-on pozisyon al",
      BEKLE:  "Teyit bekle, bekle",
      KÜÇÜLT: "Maruziyeti azalt",
      KAPAT:  "Tüm pozisyonları kapat",
    } as Record<string, string>,
    chips: { block: "Blok", confirm: "Onay", wait: "Bekle" },
  },
  ai: {
    title:      "Piyasa Analisti",
    cached:     "önbellek",
    newsScanned:(n: number) => `${n} haber tarandı`,
    preparing:  "Rapor hazırlanıyor...",
    errorTitle: "AI Raporu Kullanılamıyor",
    // noKeyParts: [before_file_code,  between_codes,  after_key_code]
    noKeyParts: ["Aktifleştirmek için", "dosyasına", "ekleyin."] as [string, string, string],
    providerLabel:   "Model",
    providerAuto:    "Otomatik (Groq → Claude)",
    providerGroq:    "Groq",
    providerClaude:  "Claude",
    providerRefreshing: "Seçilen modelle yeniden üretiliyor…",
  },
  assetGrid: {
    layer:    "KATMAN 1 — Durum Odası",
    layerSub: "Asset bazlı komut sinyalleri: makro zemin, risk iştahı, teknik setup ve risk filtresi birlikte okunur.",
    title:    "Komut Sinyalleri",
    rawTitle: "Ham Göstergeler — Veri Doğrulama ve Piyasa Nabzı",
    rawSub:   "Bu göstergeler Durum Odası, Makro Zemin ve Risk İştahı katmanlarını besleyen ham sinyal kaynaklarıdır.",
    layerContribution: "Katman katkısı",
    paperTrading: {
      watch:   "Paper Trading: İzle",
      allowed: "Paper Trading: Uygun",
      blocked: "Paper Trading: Bloklu",
    },
    aggression: {
      low:     "Normal",
      medium:  "Taktik",
      high:    "Agresif",
      extreme: "Çok Agresif",
    } as Record<string, string>,
    block:   "BLOK",
    confirm: "ONAY",
    wait:    "BEKLE",
    detailSignals: (n: number) => `${n} detay sinyal`,
    detBlock:   "blok",
    detConfirm: "onay",
    statusLabel: {
      CONFIRMED: "Onaylı",
      PENDING:   "Bekliyor",
      BLOCKING:  "Blok",
      NEUTRAL:   "Nötr",
      "VERİ_YOK":"Veri Yok",
    } as Record<string, string>,
    commandNames: {
      BTCUSD:    "Bitcoin",
      XAUUSD:    "Altın",
      XAGUSD:    "Gümüş",
      XAUXAG:    "Altın/Gümüş",
      XCUUSD:    "Bakır",
      SP500:     "S&P 500",
      BRENT:     "Brent Ham Petrol",
      DXY:       "Dolar Endeksi",
      US10Y:     "10Y Hazine",
      VIX:       "VIX / Korku",
      HY_SPREAD: "HY Kredi Spreadi",
    } as Record<string, string>,
  },
  macro: {
    layer1:       "KATMAN 2 — Makro Zemin / Para Rejimi",
    layer1Sub:    "Dolar, faiz, likidite ve enerji koşullarını okur.",
    macroRegime:  "Makro Zemin / Para Rejimi",
    confidence:   "Güven",
    layer2:       "KATMAN 3 — Risk İştahı / Piyasa Davranışı",
    layer2Sub:    "Kredi, hisse, kripto ve hedge davranışını okur.",
    riskAppetite: "Risk İştahı / Piyasa Davranışı",
    yieldCurve:   "Yield Eğrisi",
    gold:         "Altın",
    appetiteLabels: {
      STRONG:   "Risk İştahı Güçlü",
      MODERATE: "Risk İştahı Orta",
      WEAK:     "Risk İştahı Zayıf",
      CRISIS:   "Risk İştahı Kriz",
    } as Record<string, string>,
  },
  unifiedReading: {
    title:    "Birleşik Okuma — Makro Zemin + Risk İştahı Sentezi",
    intro:    "Makro zemin risk almayı kısmen destekliyor; piyasa davranışı ise bunu geniş risk-on yerine seçici risk alma şeklinde fiyatlıyor. Bu nedenle Durum Odası'nda agresif tüm-varlık long değil, asset bazlı seçici komut sinyalleri üretiliyor.",
    regime:   "Birleşik Rejim",
    meaning:  "Anlamı",
    impact:   "Etkisi",
  },
  catalyst: {
    title:    "Olay Takvimi",
    events:   (n: number) => `${n} etkinlik`,
    footer:   "yakından uzağa · PAPER_SAFE",
    today:    "BUGÜN",
    tomorrow: "YARIN",
    importance: { CRITICAL: "KRİTİK", HIGH: "YÜKSEK", MEDIUM: "ORTA" } as Record<string, string>,
  },
  scenario: {
    title:    "Senaryo",
    dominant: "Baskın:",
    footer:   "PAPER_SAFE · olasılıklar sinyal durumundan türetilir",
    labelMap: { "Boğa": "Boğa", "Baz": "Baz", "Ayı": "Ayı" } as Record<string, string>,
  },
  confirmation: { title: "Teyit Listesi" },
  asymmetry: {
    sectionLabel: "Risk / Ödül",
    title:        "Asimetri Göstergesi",
    gain:         "Kazanç:",
    loss:         "Kayıp:",
    upside:       "▲ Yukarı",
    downside:     "Aşağı ▼",
    methodology:  "Senaryo olasılıkları × tahmini hareket büyüklüğü · beklenti analizi",
  },
  news: {
    sectionLabel: "Haber Akışı",
    title:        "Son Dakika",
    headlines:    (n: number) => `${n} başlık`,
    geo:          "🌍 Jeopolitik & Merkez Bankaları",
    high:         "Piyasa & Makro",
    medium:       "Emtia & Metaller",
    low:          "Genel",
    empty:        "Haber verisi mevcut değil.",
  },
  actionCenter: {
    operationalSteps: "Operasyonel Adımlar",
    ownerAction:      "Şimdi Ne Yapmalıyım?",
    analysisOnly:     "tüm kararlar insana aittir",
    decisionChange:   "Kararı Değiştirecek Koşullar",
    flipTitle:        "Senaryo Tetikleyicileri",
  },
  footer: { text: "Sadece analiz amaçlıdır — tüm yatırım kararları insana aittir." },
  technical: {
    sectionLabel: "Teknik Analiz",
    title:        "Dinamik Eşikler",
    assets:       (n: number) => `${n} varlık · OHLCV`,
    asset:        "Varlık",
    structure:    "Yapı",
    levels:       "Destek / Direnç",
    score:        "Skor",
    footer:       "Wilder ATR(14) · Swing H/L · RSI(14) · MACD · 1D zaman dilimi · PAPER_SAFE",
  },
};

// ---------------------------------------------------------------------------
// English translations
// ---------------------------------------------------------------------------

const EN: typeof TR = {
  header: {
    assets:     (n: number) => `${n} assets`,
    live:       "● LIVE",
    simulation: "● SIMULATION",
  },
  decision: {
    actionLabel: "Recommended Action",
    displayMap:  { AÇIL: "OPEN", BEKLE: "WAIT", KÜÇÜLT: "REDUCE", KAPAT: "CLOSE" },
    actionMap:   {
      AÇIL:   "Take risk-on position",
      BEKLE:  "Wait for confirmation",
      KÜÇÜLT: "Reduce exposure",
      KAPAT:  "Close all positions",
    },
    chips: { block: "Block", confirm: "Confirm", wait: "Wait" },
  },
  ai: {
    title:       "Market Analyst",
    cached:      "cached",
    newsScanned: (n: number) => `${n} news scanned`,
    preparing:   "Preparing report...",
    errorTitle:  "AI Report Unavailable",
    noKeyParts:  ["To activate, add", "to file", ""],
    providerLabel:   "Model",
    providerAuto:    "Automatic (Groq → Claude)",
    providerGroq:    "Groq",
    providerClaude:  "Claude",
    providerRefreshing: "Regenerating with selected model…",
  },
  assetGrid: {
    layer:    "LAYER 1 — Situation Room",
    layerSub: "Asset-level command signals: macro ground, risk appetite, technical setup and risk filter read together.",
    title:    "Command Signals",
    rawTitle: "Raw Indicators — Data Validation & Market Pulse",
    rawSub:   "These indicators are the raw signal sources feeding the Situation Room, Macro Ground and Risk Appetite layers.",
    layerContribution: "Layer contribution",
    paperTrading: {
      watch:   "Paper Trading: Watch",
      allowed: "Paper Trading: Eligible",
      blocked: "Paper Trading: Blocked",
    },
    aggression: {
      low:     "Normal",
      medium:  "Tactical",
      high:    "Aggressive",
      extreme: "Very Aggressive",
    },
    block:   "BLOCK",
    confirm: "CONFIRM",
    wait:    "WAIT",
    detailSignals: (n: number) => `${n} detail signals`,
    detBlock:   "block",
    detConfirm: "confirm",
    statusLabel: {
      CONFIRMED: "Confirmed",
      PENDING:   "Pending",
      BLOCKING:  "Block",
      NEUTRAL:   "Neutral",
      "VERİ_YOK":"No Data",
    },
    commandNames: {
      BTCUSD:    "Bitcoin",
      XAUUSD:    "Gold",
      XAGUSD:    "Silver",
      XAUXAG:    "Gold/Silver",
      XCUUSD:    "Copper",
      SP500:     "S&P 500",
      BRENT:     "Brent Crude",
      DXY:       "Dollar Index",
      US10Y:     "10Y Treasury",
      VIX:       "VIX / Fear",
      HY_SPREAD: "HY Credit Spread",
    },
  },
  macro: {
    layer1:       "LAYER 2 — Macro Ground / Money Regime",
    layer1Sub:    "Reads dollar, rates, liquidity and energy conditions.",
    macroRegime:  "Macro Ground / Money Regime",
    confidence:   "Confidence",
    layer2:       "LAYER 3 — Risk Appetite / Market Behavior",
    layer2Sub:    "Reads credit, equities, crypto and hedge behavior.",
    riskAppetite: "Risk Appetite / Market Behavior",
    yieldCurve:   "Yield Curve",
    gold:         "Gold",
    appetiteLabels: {
      STRONG:   "Strong Risk Appetite",
      MODERATE: "Moderate Risk Appetite",
      WEAK:     "Weak Risk Appetite",
      CRISIS:   "Crisis Risk Appetite",
    },
  },
  unifiedReading: {
    title:    "Unified Reading — Macro Ground + Risk Appetite Synthesis",
    intro:    "The macro ground partially supports risk-taking; market behavior is pricing this as selective risk-taking rather than broad risk-on. That's why the Situation Room produces asset-level selective command signals instead of an aggressive all-asset long.",
    regime:   "Combined Regime",
    meaning:  "Meaning",
    impact:   "Impact",
  },
  catalyst: {
    title:    "Event Calendar",
    events:   (n: number) => `${n} events`,
    footer:   "near to far · PAPER_SAFE",
    today:    "TODAY",
    tomorrow: "TOMORROW",
    importance: { CRITICAL: "CRITICAL", HIGH: "HIGH", MEDIUM: "MEDIUM" },
  },
  scenario: {
    title:    "Scenario",
    dominant: "Dominant:",
    footer:   "PAPER_SAFE · probabilities derived from signal state",
    labelMap: { "Boğa": "Bull", "Baz": "Base", "Ayı": "Bear" },
  },
  confirmation: { title: "Confirmation List" },
  asymmetry: {
    sectionLabel: "Risk / Reward",
    title:        "Asymmetry Indicator",
    gain:         "Gain:",
    loss:         "Loss:",
    upside:       "▲ Upside",
    downside:     "Downside ▼",
    methodology:  "Scenario probabilities × estimated move magnitude · expectation analysis",
  },
  news: {
    sectionLabel: "News Feed",
    title:        "Breaking News",
    headlines:    (n: number) => `${n} headlines`,
    geo:          "🌍 Geopolitical & Central Banks",
    high:         "Market & Macro",
    medium:       "Commodities & Metals",
    low:          "General",
    empty:        "No news data available.",
  },
  actionCenter: {
    operationalSteps: "Operational Steps",
    ownerAction:      "What Should I Do Now?",
    analysisOnly:     "all decisions belong to humans",
    decisionChange:   "Decision-Changing Conditions",
    flipTitle:        "Scenario Triggers",
  },
  footer: { text: "For analysis purposes only — all investment decisions belong to humans." },
  technical: {
    sectionLabel: "Technical Analysis",
    title:        "Dynamic Thresholds",
    assets:       (n: number) => `${n} assets · OHLCV`,
    asset:        "Asset",
    structure:    "Structure",
    levels:       "Support / Resistance",
    score:        "Score",
    footer:       "Wilder ATR(14) · Swing H/L · RSI(14) · MACD · 1D timeframe · PAPER_SAFE",
  },
};

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export type Translations = typeof TR;

export const T: Record<Lang, Translations> = { tr: TR, en: EN };

interface LanguageCtx {
  lang: Lang;
  t:    Translations;
  toggle: () => void;
}

const LanguageContext = createContext<LanguageCtx>({
  lang: "tr",
  t:    TR,
  toggle: () => {},
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("tr");
  const toggle = () => setLang(l => (l === "tr" ? "en" : "tr"));
  return (
    <LanguageContext.Provider value={{ lang, t: T[lang], toggle }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
