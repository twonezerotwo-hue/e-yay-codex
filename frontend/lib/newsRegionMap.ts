/**
 * FAZ 15 — News region mapping helper.
 *
 * Haber başlığından coğrafi bölge çıkarır ve 1000×500 equirectangular
 * harita koordinatına eşler (x = (lon+180)/360*1000, y = (90-lat)/180*500).
 *
 * Saf fonksiyon — UI'dan bağımsız, genişletilebilir. Karar üretmez.
 */

export type RegionKey =
  | "iran" | "hormuz" | "israel" | "lebanon" | "gaza" | "turkey"
  | "saudi" | "usa" | "russia" | "ukraine" | "crimea" | "china"
  | "taiwan" | "japan" | "india" | "europe" | "uk" | "global";

export interface GeoPoint {
  x: number;
  y: number;
  region: string; // görünen Türkçe etiket
}

// Gerçek lat/lon'dan hesaplanmış koordinatlar
const REGION_COORDS: Record<RegionKey, GeoPoint> = {
  iran:    { x: 643, y: 151, region: "İran" },          // Tahran 35.7N 51.4E
  hormuz:  { x: 656, y: 176, region: "Hürmüz Boğazı" }, // 26.6N 56.3E
  israel:  { x: 598, y: 162, region: "İsrail" },        // 31.8N 35.2E
  lebanon: { x: 599, y: 156, region: "Lübnan" },        // 33.9N 35.5E
  gaza:    { x: 596, y: 163, region: "Gazze" },         // 31.5N 34.5E
  turkey:  { x: 591, y: 139, region: "Türkiye" },       // 39.9N 32.9E
  saudi:   { x: 630, y: 181, region: "Suudi Arabistan" }, // 24.7N 46.7E
  usa:     { x: 286, y: 142, region: "ABD" },           // Washington 38.9N 77W
  russia:  { x: 604, y: 95,  region: "Rusya" },         // Moskova 55.8N 37.6E
  ukraine: { x: 585, y: 110, region: "Ukrayna" },       // Kiev 50.5N 30.5E
  crimea:  { x: 594, y: 125, region: "Kırım" },         // 45N 34E
  china:   { x: 823, y: 139, region: "Çin" },           // Pekin 39.9N 116.4E
  taiwan:  { x: 836, y: 184, region: "Tayvan" },        // 23.7N 121E
  japan:   { x: 888, y: 151, region: "Japonya" },       // Tokyo 35.7N 139.7E
  india:   { x: 714, y: 171, region: "Hindistan" },     // Delhi 28.6N 77.2E
  europe:  { x: 524, y: 111, region: "Avrupa" },        // Frankfurt 50.1N 8.7E
  uk:      { x: 500, y: 107, region: "İngiltere" },     // Londra 51.5N 0W
  global:  { x: 389, y: 167, region: "Küresel" },       // Orta Atlantik
};

// Öncelik sıralı pattern listesi — spesifik lokasyon genel ülkeden önce
const REGION_PATTERNS: Array<[RegExp, RegionKey]> = [
  [/hormuz|strait of hormuz|persian gulf|basra/i,            "hormuz"],
  [/gaza|rafah|khan younis/i,                                "gaza"],
  [/lebanon|beirut|hezbollah|tyre/i,                         "lebanon"],
  [/israel|tel aviv|jerusalem|idf|netanyahu/i,               "israel"],
  [/iran|tehran|irgc|khamenei/i,                             "iran"],
  [/crimea|sevastopol|kerch/i,                               "crimea"],
  [/ukraine|kyiv|kiev|kharkiv|odesa|donbas|zelensk/i,        "ukraine"],
  [/russia|moscow|kremlin|putin/i,                           "russia"],
  [/taiwan|taipei/i,                                         "taiwan"],
  [/china|beijing|shanghai|xi jinping|pboc/i,                "china"],
  [/japan|tokyo|boj|yen\b/i,                                 "japan"],
  [/india|delhi|mumbai|rbi\b/i,                              "india"],
  [/turkey|türkiye|ankara|istanbul|erdogan/i,                "turkey"],
  [/saudi|riyadh|opec|aramco/i,                              "saudi"],
  [/\buk\b|britain|london|boe\b|sterling/i,                  "uk"],
  [/europe|\becb\b|germany|france|berlin|paris|brussels|eurozone/i, "europe"],
  [/trump|white house|pentagon|washington|congress|\bfed\b|fomc|treasury|nato|\bus\b|u\.s\./i, "usa"],
];

// Kategori bazlı fallback — keyword eşleşmezse
const CATEGORY_FALLBACK: Record<string, RegionKey> = {
  war:         "israel",
  energy:      "saudi",
  us_policy:   "usa",
  macro:       "usa",
  crypto:      "usa",
  metals:      "global",
  risk_market: "usa",
};

export function classifyHeadlineRegion(headline: string, category?: string): RegionKey {
  for (const [pattern, key] of REGION_PATTERNS) {
    if (pattern.test(headline)) return key;
  }
  if (category && category in CATEGORY_FALLBACK) return CATEGORY_FALLBACK[category];
  return "global";
}

export function geoForRegion(key: RegionKey): GeoPoint {
  return REGION_COORDS[key];
}
