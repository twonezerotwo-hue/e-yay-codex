"use client";

import type { CatalystEvent, ImportanceCode } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ---------------------------------------------------------------------------
// Style maps — renklere dokunma (kullanıcı istedi)
// ---------------------------------------------------------------------------

const DOT: Record<ImportanceCode, string> = {
  CRITICAL: "bg-red-500",
  HIGH:     "bg-amber-400",
  MEDIUM:   "bg-zinc-500",
};

const LABEL_COLOR: Record<ImportanceCode, string> = {
  CRITICAL: "text-red-400",
  HIGH:     "text-amber-400",
  MEDIUM:   "text-zinc-400",
};

const BORDER: Record<ImportanceCode, string> = {
  CRITICAL: "border-red-900/50",
  HIGH:     "border-amber-900/40",
  MEDIUM:   "border-zinc-800/60",
};

const BG: Record<ImportanceCode, string> = {
  CRITICAL: "bg-red-950/20",
  HIGH:     "bg-amber-950/15",
  MEDIUM:   "bg-zinc-900/20",
};

const CAT_COLOR: Record<string, string> = {
  FED:          "text-purple-400",
  MACRO:        "text-blue-400",
  ENERGY:       "text-orange-400",
  CRYPTO:       "text-yellow-400",
  EQUITY:       "text-emerald-400",
  GEOPOLITICAL: "text-rose-400",
};

// ---------------------------------------------------------------------------

interface CatalystSidebarProps {
  catalysts: CatalystEvent[];
}

export default function CatalystSidebar({ catalysts }: CatalystSidebarProps) {
  const { t, lang } = useLanguage();

  if (!catalysts || catalysts.length === 0) return null;

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border overflow-hidden flex flex-col max-h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-eyay-border flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-[10px] font-mono font-semibold text-eyay-dim tracking-widest uppercase">
            {t.catalyst.title}
          </span>
        </div>
        <span className="text-[9px] font-mono text-eyay-faint">{t.catalyst.events(catalysts.length)}</span>
      </div>

      {/* Dikey liste */}
      <div className="flex-1 divide-y divide-eyay-border/50 overflow-y-auto">
        {catalysts.map(ev => (
          <div
            key={ev.id}
            className={`px-3 py-2.5 border-l-2 ${BORDER[ev.importance]} ${BG[ev.importance]} transition-all duration-150 hover:brightness-110`}
          >
            {/* Üst: kategori + önem + gün */}
            <div className="flex items-center justify-between gap-1.5 mb-1">
              <div className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${DOT[ev.importance]}`} />
                <span className={`text-[9px] font-mono font-bold tracking-wide ${CAT_COLOR[ev.category] ?? "text-eyay-faint"}`}>
                  {ev.category}
                </span>
                <span className={`text-[8px] font-mono ${LABEL_COLOR[ev.importance]}`}>
                  {t.catalyst.importance[ev.importance] ?? ev.importance}
                </span>
              </div>
              <DaysChip days={ev.days_until} today={t.catalyst.today} tomorrow={t.catalyst.tomorrow} />
            </div>

            {/* Etkinlik adı */}
            <p className="text-[11px] font-semibold text-eyay-text leading-snug">
              {ev.name}
            </p>

            {/* Tarih */}
            <p className="text-[9px] font-mono text-eyay-faint mt-0.5">
              {new Date(ev.date + "T12:00:00").toLocaleDateString(
                lang === "tr" ? "tr-TR" : "en-US",
                { day: "numeric", month: "short" }
              )}
            </p>

            {/* Beklenti */}
            <p className="text-[9px] text-eyay-dim mt-1 leading-snug line-clamp-1" title={ev.expectation}>
              {ev.expectation}
            </p>
          </div>
        ))}
      </div>

      <div className="px-3 py-1.5 border-t border-eyay-border/50 bg-eyay-bg/30">
        <p className="text-[8px] font-mono text-eyay-faint text-center tracking-wide">
          {t.catalyst.footer}
        </p>
      </div>
    </div>
  );
}

function DaysChip({ days, today, tomorrow }: { days: number; today: string; tomorrow: string }) {
  if (days === 0) return (
    <span className="text-[10px] font-mono font-bold text-red-400 animate-pulse">{today}</span>
  );
  if (days === 1) return (
    <span className="text-[10px] font-mono font-bold text-red-400">{tomorrow}</span>
  );
  if (days <= 3) return (
    <span className="text-[10px] font-mono font-bold text-amber-400">{days}g</span>
  );
  return (
    <span className="text-[10px] font-mono text-eyay-faint">
      <span className="text-eyay-dim font-semibold">{days}</span>g
    </span>
  );
}
