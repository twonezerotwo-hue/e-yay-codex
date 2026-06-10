/**
 * FAZ 23 — Asymmetry display smoothing.
 *
 * Backend canonical field: `report.asymmetry.ratio` (gain/loss oran, 0–∞).
 * UI'da gösterilen değer ani sıçramaları yumuşatmak için clamp'lenir.
 * Raw değer tooltip'te kalır; karar motoru ham veriyle çalışmaya devam eder.
 */

const STORAGE_KEY = "eyay.asymmetry.lastDisplayedRatio";
const DEFAULT_MAX_STEP = 1.5;
const SUSPECT_JUMP_RATIO = 2.5;

export interface SmoothResult {
  displayed:  number;
  raw:        number;
  delta:      number;
  prevRaw:    number | null;
  smoothed:   boolean;
  /** Raw değişim eşiği aştı mı — UI rozetinde kullanılır. */
  rawJump:    boolean;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Saklanan son displayed ratio'yu oku. localStorage yoksa null. */
export function loadPrevDisplayedRatio(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

/** Yeni displayed ratio'yu kaydet. */
export function savePrevDisplayedRatio(v: number): void {
  if (typeof window === "undefined") return;
  if (!isFinite(v) || v <= 0) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, String(v));
  } catch {
    /* quota / private mode → sessiz geç */
  }
}

/**
 * Raw ratio'yu önceki displayed ratio'ya göre yumuşat.
 *
 * - prev null → raw aynen gösterilir.
 * - |raw - prev| ≤ maxStep → raw aynen gösterilir.
 * - değil → prev ± maxStep yönüne clamp'lenir, smoothed=true.
 *
 * rawJump bayrağı: raw değişimi büyük (>= SUSPECT_JUMP_RATIO katı) olduğunda
 * UI küçük bir uyarı rozeti gösterir; karar motoru etkilenmez.
 */
export function smoothRatio(
  raw: number,
  prev: number | null,
  maxStep: number = DEFAULT_MAX_STEP,
): SmoothResult {
  const result: SmoothResult = {
    displayed: raw,
    raw,
    delta:     0,
    prevRaw:   prev,
    smoothed:  false,
    rawJump:   false,
  };
  if (!isFinite(raw) || raw <= 0) return result;
  if (prev === null || !isFinite(prev) || prev <= 0) return result;

  const diff = raw - prev;
  result.delta = diff;
  if (Math.abs(diff) <= maxStep) {
    return result;
  }
  const direction = diff > 0 ? 1 : -1;
  result.displayed = clamp(prev + direction * maxStep, 0.05, 15);
  result.smoothed  = true;

  // Raw sıçrama büyük mü?
  const factor = raw > prev ? raw / prev : prev / raw;
  if (factor >= SUSPECT_JUMP_RATIO) {
    result.rawJump = true;
  }
  return result;
}

/** Backend ratio alanından 0–10 normalized score üretir (UI rozetleri için).
 *  ratio 0.5 → 2 puan, ratio 5+ → 10 puan; lineer olmayan eğri. */
export function normalizeAsymmetryScore(ratio: number): number {
  if (!isFinite(ratio) || ratio <= 0) return 0;
  // log2 eğri: 1× → 5, 2× → 7, 4× → 9, 8× → 10
  const score = 5 + Math.log2(Math.max(0.25, Math.min(8, ratio))) * 2;
  return Math.round(clamp(score, 0, 10) * 10) / 10;
}
