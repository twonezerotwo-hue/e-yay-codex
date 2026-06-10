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

/** Backend ratio'sundan 0-100 canonical asimetri skoru üretir (log eğri).
 *  Backend `report.asymmetry.score` doluysa o tercih edilmeli; bu helper
 *  geriye uyum için fallback yoludur.
 *  Eğri: 0.25× → 0, 1× → 50, 2× → 67, 4× → 83, 8× → 100 */
export function ratioToScore100(ratio: number): number {
  if (!isFinite(ratio) || ratio <= 0) return 50;
  const clamped = Math.max(0.25, Math.min(8, ratio));
  const s = 50 + Math.log2(clamped) * (50 / 3);
  return Math.round(clamp(s, 0, 100));
}

/** Geriye uyum: eski 0-10 skala. */
export function normalizeAsymmetryScore(ratio: number): number {
  return Math.round(ratioToScore100(ratio) / 10 * 10) / 10;
}

/** Display smoothing for 0-100 score; en fazla maxStep puan oynar. */
const SCORE_KEY = "eyay.asymmetry.lastDisplayedScore";

export function loadPrevDisplayedScore(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SCORE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    return isFinite(n) && n >= 0 && n <= 100 ? n : null;
  } catch { return null; }
}

export function savePrevDisplayedScore(v: number): void {
  if (typeof window === "undefined") return;
  if (!isFinite(v)) return;
  try { window.localStorage.setItem(SCORE_KEY, String(v)); } catch { /* */ }
}

export function smoothScore(
  raw: number,
  prev: number | null,
  maxStep: number = 8,
): { displayed: number; raw: number; delta: number; smoothed: boolean } {
  if (!isFinite(raw)) raw = 50;
  raw = clamp(raw, 0, 100);
  if (prev === null || !isFinite(prev)) {
    return { displayed: raw, raw, delta: 0, smoothed: false };
  }
  const diff = raw - prev;
  if (Math.abs(diff) <= maxStep) {
    return { displayed: raw, raw, delta: diff, smoothed: false };
  }
  const direction = diff > 0 ? 1 : -1;
  const displayed = clamp(prev + direction * maxStep, 0, 100);
  return { displayed, raw, delta: diff, smoothed: true };
}
