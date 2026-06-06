"use client";

import type { ConfirmationItem } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

export default function ConfirmationStrip({ items }: { items: ConfirmationItem[] }) {
  const { t } = useLanguage();
  const met   = items.filter(i => i.met).length;
  const total = items.length;
  const pct   = total > 0 ? Math.round((met / total) * 100) : 0;

  const barColor = pct === 100 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-500" : "bg-orange-500";
  const pctColor = pct === 100 ? "text-emerald-400" : pct >= 60 ? "text-amber-400" : "text-orange-400";

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-eyay-border">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono font-semibold text-eyay-dim tracking-widest uppercase">
            {t.confirmation.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-24 h-1.5 bg-eyay-raised rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
          <span className={`text-xs font-mono font-bold ${pctColor}`}>
            {met}<span className="text-eyay-faint font-normal">/{total}</span>
          </span>
        </div>
      </div>

      {/* Kompakt chip listesi */}
      <div className="px-3 py-2.5 flex flex-wrap gap-1.5 flex-1 content-start">
        {items.map((item, i) => (
          <span
            key={i}
            title={`${item.current_value} → ${item.threshold}`}
            className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-md border ${
              item.met
                ? "bg-emerald-950/40 border-emerald-900/50 text-emerald-300"
                : "bg-eyay-raised border-eyay-border text-eyay-dim"
            }`}
          >
            <span className={item.met ? "text-emerald-400" : "text-eyay-faint"}>
              {item.met ? "✓" : "✗"}
            </span>
            {item.signal}
          </span>
        ))}
      </div>
    </div>
  );
}
