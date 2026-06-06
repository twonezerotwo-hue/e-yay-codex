"use client";

import type { Scenario } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ---------------------------------------------------------------------------

const COLOR = {
  green:  { label: "text-emerald-400", bar: "bg-emerald-500", border: "border-emerald-900/40", bg: "bg-emerald-950/15" },
  yellow: { label: "text-amber-400",   bar: "bg-amber-400",   border: "border-amber-900/30",   bg: "bg-amber-950/10"  },
  red:    { label: "text-red-400",     bar: "bg-red-500",     border: "border-red-900/40",      bg: "bg-red-950/15"   },
} as const;

const EMOJI: Record<string, string> = { bull: "🟢", base: "🟡", bear: "🔴" };

// ---------------------------------------------------------------------------

interface ScenarioPanelProps {
  scenarios: Scenario[];
  decision: string;
}

export default function ScenarioPanel({ scenarios, decision }: ScenarioPanelProps) {
  const { t } = useLanguage();

  if (!scenarios || scenarios.length === 0) return null;

  const ordered = (["bull", "base", "bear"] as const)
    .map(k => scenarios.find(s => s.key === k))
    .filter(Boolean) as Scenario[];

  const dominant = [...scenarios].sort((a, b) => b.probability_pct - a.probability_pct)[0];
  const dominantLabel = t.scenario.labelMap[dominant.label] ?? dominant.label;

  return (
    <div className="rounded-2xl border border-eyay-border bg-eyay-surface overflow-hidden h-full flex flex-col">
      {/* Header tek satır */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-eyay-border">
        <span className="text-[10px] font-mono font-semibold text-eyay-dim tracking-widest uppercase shrink-0">
          {t.scenario.title}
        </span>
        <span className="text-[9px] font-mono text-eyay-faint shrink-0">{t.scenario.dominant}</span>
        <span className={`text-[10px] font-mono font-bold shrink-0 ${COLOR[dominant.color].label}`}>
          {EMOJI[dominant.key]} {dominantLabel} %{dominant.probability_pct}
        </span>
        <div className="flex-1 flex items-center gap-1.5 min-w-0 justify-end">
          {ordered.map(sc => (
            <span key={sc.key} className="text-[9px] font-mono text-eyay-faint whitespace-nowrap">
              {EMOJI[sc.key]} %{sc.probability_pct}
            </span>
          ))}
        </div>
      </div>

      {/* 3 kompakt kart */}
      <div className="grid grid-cols-3 gap-0 divide-x divide-eyay-border flex-1">
        {ordered.map(sc => {
          const s = COLOR[sc.color];
          const scLabel = t.scenario.labelMap[sc.label] ?? sc.label;
          return (
            <div key={sc.key} className={`p-3 ${s.bg} flex flex-col gap-2`}>
              {/* Başlık + % */}
              <div className="flex items-center justify-between">
                <span className={`text-xs font-bold font-mono ${s.label}`}>
                  {EMOJI[sc.key]} {scLabel}
                </span>
                <span className={`text-sm font-black font-mono ${s.label}`}>
                  %{sc.probability_pct}
                </span>
              </div>

              {/* Bar */}
              <div className="h-0.5 rounded-full bg-white/5">
                <div
                  className={`h-full rounded-full ${s.bar}`}
                  style={{ width: `${sc.probability_pct}%` }}
                />
              </div>

              {/* Tetikleyici */}
              <p className="text-[10px] text-eyay-dim leading-snug line-clamp-2" title={sc.trigger}>
                {sc.trigger}
              </p>

              {/* Eşik chip'leri */}
              {sc.thresholds && sc.thresholds.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-auto pt-1 border-t border-white/5">
                  {sc.thresholds.map((thr, i) => (
                    <span
                      key={i}
                      className={`text-[8px] font-mono font-semibold px-1.5 py-0.5 rounded border ${s.bg} ${s.border} ${s.label} opacity-80`}
                    >
                      {thr}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="px-4 py-1.5 border-t border-eyay-border/50 bg-eyay-bg/30">
        <p className="text-[8px] font-mono text-eyay-faint text-center">
          {t.scenario.footer}
        </p>
      </div>
    </div>
  );
}
