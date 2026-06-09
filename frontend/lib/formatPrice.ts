// Merkezi fiyat formatlama ve sanity check — gösterge başına min/max + birim kuralları.

export type SanityReason = "out_of_range" | "unit_unknown" | "missing";
export type FinalStatus  = "ok" | "current_invalid" | "threshold_invalid" | "unit_uncertain" | "unknown";

export interface SanityResult {
  ok: boolean;
  reason?: SanityReason;
  displayValue?: string;
}

export interface ConfirmationSanity {
  current:      SanityResult;
  threshold:    SanityResult;
  final_status: FinalStatus;
}

const RULES: Record<string, { min: number; max: number; fmt: (v: number) => string }> = {
  btcusd:       { min: 10_000, max: 1_000_000, fmt: v => `$${Math.round(v).toLocaleString("en-US")}` },
  ethusd:       { min: 100,    max: 50_000,    fmt: v => `$${Math.round(v).toLocaleString("en-US")}` },
  xauusd:       { min: 1_000,  max: 10_000,    fmt: v => `$${Math.round(v).toLocaleString("en-US")}` },
  xagusd:       { min: 5,      max: 300,       fmt: v => `$${v.toFixed(2)}` },
  brent:        { min: 10,     max: 250,       fmt: v => `$${v.toFixed(2)}` },
  vix:          { min: 5,      max: 150,       fmt: v => v.toFixed(1) },
  dxy:          { min: 50,     max: 200,       fmt: v => v.toFixed(1) },
  hyg:          { min: 20,     max: 200,       fmt: v => `$${v.toFixed(2)}` },
  copper_lb:    { min: 1,      max: 20,        fmt: v => `$${v.toFixed(2)}/lb` },
  copper_ton:   { min: 1_000,  max: 20_000,    fmt: v => `$${Math.round(v).toLocaleString("en-US")}/ton` },
  yield:        { min: -5,     max: 30,        fmt: v => `${v.toFixed(2)}%` },
  yield_spread: { min: -5,     max: 5,         fmt: v => `${v > 0 ? "+" : ""}${v.toFixed(2)}%` },
  usdt_d:       { min: 0,      max: 100,       fmt: v => `${v.toFixed(1)}%` },
  btc_d:        { min: 0,      max: 100,       fmt: v => `${v.toFixed(1)}%` },
};

function detectKey(signal: string): string | null {
  const s = signal.toUpperCase();

  // Yield curve spread — önce kontrol et; "10Y > 2Y" içeren ifadeler spread bekler
  if (
    s.includes("CURVE") ||
    (s.includes("10Y") && s.includes("2Y")) ||
    s.includes("İNVERSİYON") ||
    s.includes("INVERSION")
  ) return "yield_spread";

  // BTC.D — BTC'den önce
  if (/BTC\.?D(OMINAN[TC]?E?)?/.test(s) || s.includes("BTC DOM")) return "btc_d";
  if (s.includes("BTC") || s.includes("BITCOIN"))                   return "btcusd";
  if (s.includes("ETH") || s.includes("ETHEREUM"))                  return "ethusd";

  // ALTIN: \bALTIN\b (word boundary) — "altında" (=below) kelimesini eşleştirmez!
  // "ALTINDA" içinde 'N' ile 'D' arasında word-boundary YOK → eşleşmez. ✓
  if (s.includes("XAU") || /\bALTIN\b/.test(s) || s.includes("GOLD")) return "xauusd";
  if (s.includes("XAG") || s.includes("GÜMÜŞ") || s.includes("SILVER")) return "xagusd";
  if (s.includes("BRENT") || s.includes("WTI") || s.includes("PETROL") || s.includes("OIL")) return "brent";
  if (s.includes("VIX"))  return "vix";
  if (s.includes("DXY") || s.includes("DOLAR ENDEKSİ") || s.includes("USD INDEX")) return "dxy";
  if (s.includes("HYG"))  return "hyg";
  if (s.includes("BAKIR") || s.includes("COPPER")) return "__copper__";
  if (s.includes("YIELD") || s.includes("FAİZ") || s.includes("TREASURY") || /\d+Y\b/.test(s)) return "yield";
  if (s.includes("USDT.D") || s.includes("USDT_D") || s.includes("USDT DOM")) return "usdt_d";
  return null;
}

/** Sayısal değeri ham strinden çıkar — "$61,000", "4.32%", "134,680/ton" gibi. */
export function parseNumeric(raw: string): number | null {
  if (!raw || raw.trim() === "" || raw === "—" || raw === "-") return null;
  const cleaned = raw.replace(/[$%,]/g, "").replace(/\/\w+$/, "").trim();
  const n = parseFloat(cleaned);
  return isNaN(n) ? null : n;
}

function checkFieldSanity(signal: string, rawValue: string): SanityResult {
  const n = parseNumeric(rawValue);
  if (n === null) return { ok: false, reason: "missing" };

  let key = detectKey(signal);

  if (key === "__copper__") {
    // 1. Explicit unit suffix
    if (/\/lb\b/i.test(rawValue))       key = "copper_lb";
    else if (/\/ton\b/i.test(rawValue)) key = "copper_ton";
    // 2. Magnitude-based inference (no suffix in the value)
    else if (n >= 1 && n <= 20)         key = "copper_lb";
    else if (n >= 1_000 && n <= 20_000) key = "copper_ton";
    // 3. Unrecognized scale (e.g. 130_000_000)
    else return { ok: false, reason: "out_of_range" };
  }

  if (!key) return { ok: true, displayValue: rawValue };

  const rule = RULES[key];
  if (!rule) return { ok: true, displayValue: rawValue };

  if (n < rule.min || n > rule.max) return { ok: false, reason: "out_of_range" };
  return { ok: true, displayValue: rule.fmt(n) };
}

/**
 * Current value VE threshold'u AYRI AYRI sanity kontrolünden geçirir.
 *
 * - ok              → ikisi geçerli; `item.met` güvenle ✓/✗ olarak gösterilebilir
 * - threshold_invalid → eşik bu gösterge için aralık dışı; current değil threshold sorunlu
 * - current_invalid  → mevcut değer bu gösterge için aralık dışı
 * - unit_uncertain   → birim çözümlenemedi
 */
export function checkConfirmationSanity(
  signal: string,
  currentValue: string,
  thresholdValue: string,
): ConfirmationSanity {
  const current   = checkFieldSanity(signal, currentValue);
  const threshold = checkFieldSanity(signal, thresholdValue);

  let final_status: FinalStatus;
  if (!current.ok && current.reason === "unit_unknown") {
    final_status = "unit_uncertain";
  } else if (!current.ok) {
    final_status = "current_invalid";
  } else if (!threshold.ok) {
    final_status = "threshold_invalid";
  } else {
    final_status = "ok";
  }

  return { current, threshold, final_status };
}

/** Tek-alan sanity kontrolü (AsymmetryCard veya başka yerlerde kullanım için). */
export function checkSanity(signal: string, rawValue: string): SanityResult {
  return checkFieldSanity(signal, rawValue);
}
