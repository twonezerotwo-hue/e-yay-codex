/**
 * War / breaking-news alert detection.
 *
 * Mevcut news/event akışında ABD / İsrail / İran ekseninde ASKERİ-SİYASİ
 * gerilim haberi varsa büyük "Breaking War Alert" üretmek için tek noktadan
 * keyword + severity sınıflaması. Yeni backend endpoint EKLEMEZ — sadece
 * frontend tarafında mevcut `NewsHeadline[]` üzerinde çalışır.
 */
import type { NewsHeadline } from "@/lib/types";

export type WarAlertSeverity = "info" | "high" | "critical";

export type WarAlertCategory =
  | "war"
  | "ceasefire"
  | "attack"
  | "oil_risk"
  | "military"
  | "nuclear";

export interface WarAlert {
  id: string;             // başlığın deterministik hash'i — dedup için
  title: string;          // TR varsa onun, yoksa orijinal
  source: string;
  timestamp: string;      // published_at
  severity: WarAlertSeverity;
  category: WarAlertCategory;
  affected_assets: string[];
  market_impact: string;
  url?: string;
}

// ── Aktör / ülke / coğrafya patterns ──────────────────────────────────────
const ACTOR_PATTERNS: RegExp[] = [
  /\bABD\b/i,
  /\bUSA?\b/i,
  /\bUnited States\b/i,
  /\bAmerica[n]?\b/i,
  /\bİsrail\b/i, /\bIsrael\b/i,
  /\bİran\b/i,  /\bIran\b/i,
  /\bTehran\b/i, /\bTahran\b/i,
  /\bTel Aviv\b/i,
  /\bMiddle East\b/i, /\bOrtado[ğg]u\b/i,
  /\bGulf\b/i, /\bK[öo]rfez\b/i,
  /\bHormuz\b/i, /\bH[üu]rm[üu]z\b/i,
  /\bLebanon\b/i, /\bL[üu]bnan\b/i,
  /\bHezbollah\b/i, /\bHizbullah\b/i,
];

// ── Kritik askeri / saldırı kelimeleri (CRITICAL severity) ────────────────
const CRITICAL_PATTERNS: RegExp[] = [
  /\bmissile/i, /\bf[üu]ze\b/i,
  /\bairstrike/i, /\bhava sald[ıi]r[ıi]/i,
  /\bbombing\b/i, /\bbomb\b/i, /bombal[ıi]/i, /bomba\b/i,
  /\bexplosion\b/i, /patlama/i,
  /\bretaliation\b/i, /misilleme/i,
  /\battack\b/i, /\bstrike\b/i, /sald[ıi]r[ıi]/i,
  /breach/i, /ihlal\b/i,
  /\bnuclear\b/i, /n[üu]kleer/i,
  /\bdrone\b/i, /\binsans[ıi]z/i,
  /closure/i, /kapan[ıi][şs]/i,
];

// ── Yumuşak askeri / siyasi kelimeler (HIGH severity) ────────────────────
const HIGH_PATTERNS: RegExp[] = [
  /\bcease.?fire\b/i, /ate[şs]kes/i,
  /\bwar\b/i, /sava[şs]/i,
  /\bmilitary\b/i, /asker[îi]?/i,
  /\bsanctions?\b/i, /yapt[ıi]r[ıi]m/i,
  /\bthreat\b/i, /tehdit/i,
  /\bproxy\b/i, /vekil sava[şs]/i,
  /\boil shock\b/i, /petrol [şs]oku/i,
];

// ── Düşük öncelik (INFO) — sadece aktör + tehlike yokken ──────────────────
// (Aktör yoksa zaten alert üretilmiyor; bu pattern'ler aktör ile aynı anda
// gelirse ve CRITICAL/HIGH yoksa "info" sayılır.)

// ── False positive azaltıcı ────────────────────────────────────────────────
// "cyber attack", "stock attack", "DDoS attack" gibi finansal/teknoloji
// bağlamı CRITICAL severity'i düşürür.
const TECH_CONTEXT: RegExp[] = [
  /\bcyber/i, /siber/i,
  /\bphishing\b/i, /oltalama/i,
  /\bDDoS\b/i, /\bhack/i, /hack(?:le|liyor|lendi)/i,
  /\bransomware\b/i, /fidye yaz[ıi]l[ıi]m/i,
];

function hasMatch(text: string, patterns: RegExp[]): boolean {
  return patterns.some(p => p.test(text));
}

// ── Etkilenen varlık tahmini — keyword bazlı, kısa ────────────────────────
function inferAssets(text: string): string[] {
  const assets: string[] = [];
  if (/\b(oil|petrol|brent|crude|hormuz|h[üu]rm[üu]z)\b/i.test(text)) assets.push("Brent");
  if (/\b(gold|alt[ıi]n|xau|haven|g[üu]venli liman)\b/i.test(text))   assets.push("Gold");
  if (/\b(vix|volatility|volatilite|fear)\b/i.test(text))             assets.push("VIX");
  if (/\b(bitcoin|btc|crypto|kripto)\b/i.test(text))                  assets.push("BTC");
  if (/\b(silver|g[üu]m[üu][şs]|xag)\b/i.test(text))                  assets.push("Silver");
  if (/\b(qqq|tech|teknoloji|nasdaq)\b/i.test(text))                  assets.push("QQQ");
  // Default — savaş haberi her zaman enerji + güvenli liman etkiler
  if (assets.length === 0) return ["Brent", "Gold", "VIX"];
  return assets;
}

// ── Piyasa etkisi cümlesi — TR, kısa, profesyonel ─────────────────────────
function buildMarketImpact(
  category: WarAlertCategory,
  severity: WarAlertSeverity,
): string {
  if (category === "ceasefire") {
    return "Enerji primi düşebilir; risk iştahı kısa vadede toparlanabilir.";
  }
  if (category === "nuclear") {
    return "Güvenli liman talebi sert artabilir; risk varlıkları satışa gelebilir.";
  }
  if (category === "oil_risk") {
    return "Brent'te yukarı şok riski; enerji-bağımlı para birimleri zayıflayabilir.";
  }
  if (category === "attack" || category === "war") {
    return severity === "critical"
      ? "Enerji riski ve güvenli liman talebi artabilir; risk varlıklarında volatilite yükselebilir."
      : "Jeopolitik prim artabilir; gelişmeler izlenmeli.";
  }
  return "Gelişmeler izlenmeli; oynaklık artabilir.";
}

// ── Kategori karar ────────────────────────────────────────────────────────
function decideCategory(text: string): WarAlertCategory {
  if (/cease.?fire|ate[şs]kes/i.test(text)) return "ceasefire";
  if (/nuclear|n[üu]kleer/i.test(text))     return "nuclear";
  if (/hormuz|h[üu]rm[üu]z|oil shock|petrol [şs]oku/i.test(text)) return "oil_risk";
  if (/missile|f[üu]ze|airstrike|hava sald|bombing|bomba|explosion|patlama|attack|sald[ıi]r/i.test(text)) {
    return "attack";
  }
  if (/military|asker[îi]?|sanctions|yapt[ıi]r[ıi]m/i.test(text)) return "military";
  return "war";
}

// ── Deterministik kısa hash (id için) ─────────────────────────────────────
// FNV-1a-ish — crypto'ya gerek yok, dedup için yeterli.
function hashKey(s: string): string {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(36);
}

/**
 * Tek bir haber için WarAlert üret — match yoksa null döner.
 *
 * Kurallar:
 *   - Aktör (ABD/İsrail/İran/...) yoksa: null. (Cyber attack vs. spam'i eler.)
 *   - Aktör + CRITICAL pattern + tech context YOK → severity = "critical"
 *   - Aktör + CRITICAL pattern + tech context VAR → severity = "high" (cyber attack vs.)
 *   - Aktör + HIGH pattern → severity = "high"
 *   - Aktör + (sadece info-tier kelimeler) → severity = "info"
 *   - Aktör yok → null (alert tetiklenmez)
 */
export function detectWarAlert(news: NewsHeadline): WarAlert | null {
  const titleSrc = news.title ?? "";
  const titleTr  = news.title_tr ?? "";
  const text = `${titleSrc} ${titleTr}`.trim();
  if (!text) return null;

  if (!hasMatch(text, ACTOR_PATTERNS)) {
    return null;
  }

  const hasCritical = hasMatch(text, CRITICAL_PATTERNS);
  const hasHigh     = hasMatch(text, HIGH_PATTERNS);
  const hasTech     = hasMatch(text, TECH_CONTEXT);

  let severity: WarAlertSeverity;
  if (hasCritical && !hasTech) {
    severity = "critical";
  } else if (hasHigh || (hasCritical && hasTech)) {
    severity = "high";
  } else {
    severity = "info";
  }

  const category = decideCategory(text);
  // "ceasefire" varsa severity "high" tercih edilir (ateşkes critical değildir)
  if (category === "ceasefire" && severity === "critical") {
    severity = "high";
  }

  const display = (titleTr && titleTr.trim()) || titleSrc;
  return {
    id: hashKey(display + "|" + news.source + "|" + news.published_at),
    title: display,
    source: news.source,
    timestamp: news.published_at,
    severity,
    category,
    affected_assets: inferAssets(text),
    market_impact: buildMarketImpact(category, severity),
    url: news.url,
  };
}

/**
 * Bir liste için en yüksek öncelikli alert'i bul (CRITICAL > HIGH > INFO,
 * eşitlikte en yeni published_at). INFO seviyeleri büyük overlay tetiklemez,
 * yalnızca CRITICAL ve HIGH return edilir.
 */
export function pickTopWarAlert(
  headlines: NewsHeadline[],
): WarAlert | null {
  const alerts: WarAlert[] = [];
  for (const h of headlines) {
    const a = detectWarAlert(h);
    if (a && a.severity !== "info") alerts.push(a);
  }
  if (alerts.length === 0) return null;
  alerts.sort((a, b) => {
    const rank = (s: WarAlertSeverity) => (s === "critical" ? 0 : s === "high" ? 1 : 2);
    if (rank(a.severity) !== rank(b.severity)) {
      return rank(a.severity) - rank(b.severity);
    }
    return (b.timestamp || "").localeCompare(a.timestamp || "");
  });
  return alerts[0];
}

// ── Recent-shown dedup (30 dakika) ────────────────────────────────────────
const RECENT_TTL_MS = 30 * 60 * 1000;
const STORAGE_KEY = "eyay:war-alert-shown";

interface ShownEntry {
  id: string;
  at: number;
}

function loadShown(): ShownEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ShownEntry[];
    const now = Date.now();
    return parsed.filter(e => now - e.at < RECENT_TTL_MS);
  } catch { return []; }
}

function saveShown(entries: ShownEntry[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(-50)));
  } catch { /* quota — sessiz */ }
}

export function isAlertRecentlyShown(id: string): boolean {
  return loadShown().some(e => e.id === id);
}

export function markAlertShown(id: string): void {
  const entries = loadShown();
  entries.push({ id, at: Date.now() });
  saveShown(entries);
}
