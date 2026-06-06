"use client";

import type { CatalystEvent, ImportanceCode } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const importanceStyle: Record<ImportanceCode, string> = {
  CRITICAL: "border-red-700 text-red-400 bg-red-950/50",
  HIGH:     "border-amber-700 text-amber-400 bg-amber-950/40",
  MEDIUM:   "border-zinc-700 text-zinc-400 bg-zinc-900/40",
};

const importanceLabel: Record<ImportanceCode, string> = {
  CRITICAL: "KRİTİK",
  HIGH:     "YÜKSEK",
  MEDIUM:   "ORTA",
};

const categoryColor: Record<string, string> = {
  FED:          "text-purple-400",
  MACRO:        "text-blue-400",
  ENERGY:       "text-orange-400",
  CRYPTO:       "text-yellow-400",
  EQUITY:       "text-emerald-400",
  GEOPOLITICAL: "text-rose-400",
};

function DaysUntilBadge({ days }: { days: number }) {
  if (days === 0) return (
    <span className="text-[10px] font-bold font-mono text-red-400 animate-pulse">BUGÜN</span>
  );
  if (days === 1) return (
    <span className="text-[10px] font-bold font-mono text-red-400">YARIN</span>
  );
  return (
    <span className="text-[10px] font-mono text-eyay-faint">
      <span className="text-white font-bold">{days}</span>g
    </span>
  );
}

// ---------------------------------------------------------------------------
// Single event card
// ---------------------------------------------------------------------------

function CatalystCard({ event }: { event: CatalystEvent }) {
  const impStyle = importanceStyle[event.importance] ?? importanceStyle.MEDIUM;
  const catColor = categoryColor[event.category] ?? "text-eyay-dim";

  return (
    <div className={`
      flex-shrink-0 w-64 rounded-xl border p-3 space-y-2
      ${impStyle}
      transition-all duration-200 hover:brightness-110
    `}>
      {/* Top row: category + importance badge + days */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] font-bold font-mono tracking-wider ${catColor}`}>
            {event.category}
          </span>
          <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${impStyle}`}>
            {importanceLabel[event.importance]}
          </span>
        </div>
        <DaysUntilBadge days={event.days_until} />
      </div>

      {/* Event name */}
      <p className="text-xs font-semibold text-white leading-snug line-clamp-2">
        {event.name}
      </p>

      {/* Date */}
      <p className="text-[10px] font-mono text-eyay-faint">
        {new Date(event.date + "T12:00:00").toLocaleDateString("tr-TR", {
          day: "numeric",
          month: "long",
          year: "numeric",
        })}
      </p>

      {/* Expectation */}
      <div className="text-[10px] text-eyay-dim leading-snug border-t border-current/20 pt-1.5">
        <span className="text-eyay-faint">Beklenti: </span>
        {event.expectation}
      </div>

      {/* Market impact — truncated, shown on hover concept */}
      <div
        className="text-[9px] text-eyay-faint leading-snug line-clamp-2"
        title={event.market_impact}
      >
        {event.market_impact}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main strip
// ---------------------------------------------------------------------------

interface CatalystStripProps {
  catalysts: CatalystEvent[];
}

export default function CatalystStrip({ catalysts }: CatalystStripProps) {
  if (!catalysts || catalysts.length === 0) return null;

  // Split by importance for visual grouping
  const critical = catalysts.filter(c => c.importance === "CRITICAL");
  const other    = catalysts.filter(c => c.importance !== "CRITICAL");

  return (
    <div className="rounded-2xl border border-eyay-border bg-eyay-surface overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-eyay-border">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          <span className="text-xs font-mono font-semibold text-eyay-dim tracking-wider uppercase">
            Olay Takvimi
          </span>
          <span className="text-[10px] font-mono text-eyay-faint">
            — önümüzdeki 60 gün
          </span>
        </div>
        <span className="text-[10px] font-mono text-eyay-faint">
          {catalysts.length} etkinlik
        </span>
      </div>

      {/* Horizontal scroll strip */}
      <div className="p-3 overflow-x-auto scrollbar-thin scrollbar-thumb-eyay-border scrollbar-track-transparent">
        <div className="flex gap-3 min-w-max">
          {/* Critical events first with separator */}
          {critical.map(ev => (
            <CatalystCard key={ev.id} event={ev} />
          ))}
          {critical.length > 0 && other.length > 0 && (
            <div className="flex-shrink-0 w-px bg-eyay-border self-stretch mx-1" />
          )}
          {other.map(ev => (
            <CatalystCard key={ev.id} event={ev} />
          ))}
        </div>
      </div>

      {/* Footer hint */}
      <div className="px-4 py-2 border-t border-eyay-border/50 bg-eyay-bg/30">
        <p className="text-[9px] font-mono text-eyay-faint text-center tracking-wide">
          PAPER_SAFE · Sadece analiz — tarihler değişebilir, teyit ediniz
        </p>
      </div>
    </div>
  );
}
