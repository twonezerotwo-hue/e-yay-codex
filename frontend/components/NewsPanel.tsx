"use client";

import { useEffect, useState } from "react";
import type { AssetImpact, NewsHeadline, Sentiment } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

const SENTIMENT: Record<Sentiment, { icon: string; color: string; bg: string }> = {
  BULLISH: { icon: "▲", color: "text-emerald-400", bg: "bg-emerald-950/60 border-emerald-900/50" },
  BEARISH: { icon: "▼", color: "text-red-400",     bg: "bg-red-950/60     border-red-900/50"     },
  NEUTRAL: { icon: "—", color: "text-eyay-faint",  bg: "bg-eyay-raised    border-eyay-border"    },
};

const TAG_STYLE: Record<string, string> = {
  geo:     "bg-rose-950/60   text-rose-400   border-rose-900/50",
  crypto:  "bg-blue-950/60   text-blue-400   border-blue-900/50",
  macro:   "bg-purple-950/60 text-purple-400 border-purple-900/50",
  energy:  "bg-orange-950/60 text-orange-400 border-orange-900/50",
  metals:  "bg-yellow-950/60 text-yellow-400 border-yellow-900/50",
  general: "bg-eyay-raised   text-eyay-faint border-eyay-border",
};

// Jeopolitik kaynaklar — bu kaynaklardan gelen haberler her zaman GEO bölümünde gösterilir
const GEO_SOURCES = new Set([
  "Jerusalem Post", "BBC World", "Anadolu Agency", "Xinhua", "TASS",
  "Al Jazeera", "Fed Reserve",
]);

// Öncelik sırası: askeri/siyasi haberler Fed açıklamalarından önce
const GEO_PRIORITY: Record<string, number> = {
  "Jerusalem Post":  0,   // İsrail/İran/Orta Doğu — en acil
  "Anadolu Agency":  1,   // Türkiye/Orta Doğu/Küresel
  "TASS":            2,   // Rusya resmi
  "Xinhua":          3,   // Çin resmi
  "Al Jazeera":      4,   // Orta Doğu/Küresel
  "BBC World":       5,   // Küresel/Batı perspektifi
  "Fed Reserve":     6,   // Merkez bankası açıklamaları
};

export default function NewsPanel({ headlines }: { headlines: NewsHeadline[] }) {
  const { t } = useLanguage();
  // Mount sonrası "TAZE" sayacı — SSR hidrasyon mismatch'i için boş gösterilir.
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  if (headlines.length === 0) {
    return (
      <div className="bg-eyay-surface rounded-2xl border border-eyay-border p-5">
        <SectionHeader sectionLabel={t.news.sectionLabel} title={t.news.title} />
        <p className="text-sm text-eyay-faint mt-3">{t.news.empty}</p>
      </div>
    );
  }

  // GEO bölümü: jeopolitik kaynaklardan gelen haberler, aciliyet sırasına göre — max 6
  const geo = headlines
    .filter(h => GEO_SOURCES.has(h.source))
    .sort((a, b) => (GEO_PRIORITY[a.source] ?? 99) - (GEO_PRIORITY[b.source] ?? 99))
    .slice(0, 6);

  // Kalan haberler (GEO bölümünde gösterilenler hariç)
  const geoTitles = new Set(geo.map(h => h.title));
  const rest = headlines.filter(h => !geoTitles.has(h.title));

  const high   = rest.filter(h => h.relevance === "HIGH").slice(0, 4);
  const medium = rest.filter(h => h.relevance === "MEDIUM").slice(0, 3);
  const low    = rest.filter(h => h.relevance === "LOW").slice(0, 2);

  return (
    <div
      id="news"
      data-section="news"
      className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden scroll-mt-20"
    >
      <div className="px-5 py-4 border-b border-eyay-border flex items-center justify-between">
        <div>
          <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">{t.news.sectionLabel}</p>
          <p className="text-sm font-semibold text-eyay-text mt-0.5">{t.news.title}</p>
        </div>
        <div className="flex items-center gap-2">
          {mounted && (() => {
            const oneHourAgo = Date.now() - 3_600_000;
            const fresh = headlines.filter(h => {
              try { return new Date(h.published_at).getTime() > oneHourAgo; }
              catch { return false; }
            }).length;
            return fresh > 0 && (
              <span className="inline-flex items-center gap-1 text-[9px] font-mono font-bold text-emerald-300 border border-emerald-800/60 bg-emerald-950/40 rounded px-1.5 py-0.5">
                <span className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
                {fresh} TAZE
              </span>
            );
          })()}
          <span className="text-xs text-eyay-faint font-mono">{t.news.headlines(headlines.length)}</span>
        </div>
      </div>

      <div className="divide-y divide-eyay-border">

        {/* ── GEO: Jeopolitik & Merkez Bankaları ── */}
        {geo.length > 0 && (
          <div className="p-4 bg-rose-950/5">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse" />
              <span className="text-2xs text-rose-400 font-semibold tracking-widest">{t.news.geo}</span>
            </div>
            <div className="space-y-2">
              {geo.map((h, i) => <HeadlineRow key={i} h={h} />)}
            </div>
          </div>
        )}

        {/* ── Yüksek önem: Piyasa & Makro ── */}
        {high.length > 0 && (
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
              <span className="text-2xs text-red-400 font-semibold uppercase tracking-widest">{t.news.high}</span>
            </div>
            <div className="space-y-2">
              {high.map((h, i) => <HeadlineRow key={i} h={h} />)}
            </div>
          </div>
        )}

        {/* ── Orta önem: Emtia & Metaller ── */}
        {medium.length > 0 && (
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              <span className="text-2xs text-amber-400 font-semibold uppercase tracking-widest">{t.news.medium}</span>
            </div>
            <div className="space-y-2">
              {medium.map((h, i) => <HeadlineRow key={i} h={h} />)}
            </div>
          </div>
        )}

        {/* ── Genel ── */}
        {low.length > 0 && (
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-1.5 h-1.5 rounded-full bg-eyay-muted" />
              <span className="text-2xs text-eyay-faint font-semibold uppercase tracking-widest">{t.news.low}</span>
            </div>
            <div className="space-y-2">
              {low.map((h, i) => <HeadlineRow key={i} h={h} />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionHeader({ sectionLabel, title }: { sectionLabel: string; title: string }) {
  return (
    <div>
      <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">{sectionLabel}</p>
      <p className="text-sm font-semibold text-eyay-text mt-0.5">{title}</p>
    </div>
  );
}

const IMPACT_STYLE: Record<AssetImpact["direction"], { arrow: string; color: string; bg: string; border: string }> = {
  positive: { arrow: "▲", color: "text-emerald-400", bg: "bg-emerald-950/50", border: "border-emerald-900/50" },
  negative: { arrow: "▼", color: "text-red-400",     bg: "bg-red-950/50",     border: "border-red-900/50"     },
  neutral:  { arrow: "→", color: "text-amber-400",   bg: "bg-amber-950/30",   border: "border-amber-900/40"   },
};

function AssetImpactChips({ impacts }: { impacts: AssetImpact[] }) {
  if (!impacts || impacts.length === 0) return null;
  return (
    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
      {impacts.map((imp, i) => {
        const st = IMPACT_STYLE[imp.direction];
        return (
          <span
            key={i}
            title={imp.note}
            className={`inline-flex items-center gap-0.5 text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${st.bg} ${st.border} ${st.color}`}
          >
            <span>{st.arrow}</span>
            <span>{imp.asset_code}</span>
          </span>
        );
      })}
    </div>
  );
}

function relativeTime(iso: string, nowMs: number = Date.now()): string {
  try {
    const diffMs  = nowMs - new Date(iso).getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin <  2)  return "şimdi";
    if (diffMin < 60)  return `${diffMin}dk`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH   < 24)  return `${diffH}s`;
    return `${Math.floor(diffH / 24)}g`;
  } catch {
    return "";
  }
}

function ageColor(iso: string, nowMs: number = Date.now()): string {
  try {
    const h = (nowMs - new Date(iso).getTime()) / 3_600_000;
    if (h < 1)  return "text-emerald-400";
    if (h < 6)  return "text-eyay-dim";
    if (h < 24) return "text-eyay-faint";
    return "text-eyay-faint/40";
  } catch {
    return "text-eyay-faint";
  }
}

function HeadlineRow({ h }: { h: NewsHeadline }) {
  const s   = SENTIMENT[h.sentiment];
  // SSR ile client time'ı eşleşmediği için hidrasyon mismatch oluyordu
  // ("18dk" vs "19dk"). Mount sonrası hesapla; SSR çıktısı boş → mismatch yok.
  const [mounted, setMounted] = useState(false);
  const [now,     setNow]     = useState(0);
  useEffect(() => {
    setMounted(true);
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  const age    = mounted ? relativeTime(h.published_at, now) : "";
  const ageCls = mounted ? ageColor(h.published_at, now) : "text-eyay-faint";
  const display = (h.title_tr && h.title_tr.trim()) || h.title;
  const isTranslated = display !== h.title;

  return (
    <a
      href={h.url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-start gap-3 p-3 rounded-xl bg-eyay-raised border border-eyay-border hover:border-eyay-muted transition-colors group"
    >
      <span className={`font-mono font-bold text-xs mt-0.5 shrink-0 w-5 text-center ${s.color}`}>
        {s.icon}
      </span>

      <div className="flex-1 min-w-0">
        <p
          className="text-xs text-eyay-text leading-relaxed line-clamp-2 group-hover:text-white transition-colors"
          title={isTranslated ? h.title : undefined}
        >
          {display}
        </p>
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          <span className="text-2xs text-eyay-faint">{h.source}</span>
          {age && (
            <span className={`font-mono text-[9px] ${ageCls}`}>{age}</span>
          )}
          {h.tags.slice(0, 2).map(tag => (
            <span
              key={tag}
              className={`text-2xs border rounded px-1.5 py-px font-mono ${TAG_STYLE[tag] ?? TAG_STYLE.general}`}
            >
              {tag}
            </span>
          ))}
        </div>
        {h.asset_impact && h.asset_impact.length > 0 && (
          <AssetImpactChips impacts={h.asset_impact} />
        )}
      </div>
    </a>
  );
}
