"use client";

import { useState } from "react";
import type { Scenario } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

const COLOR = {
  green:  { label: "text-emerald-400", bar: "bg-emerald-500", border: "border-emerald-900/40", bg: "bg-emerald-950/15" },
  yellow: { label: "text-amber-400",   bar: "bg-amber-400",   border: "border-amber-900/30",   bg: "bg-amber-950/10"  },
  red:    { label: "text-red-400",     bar: "bg-red-500",     border: "border-red-900/40",      bg: "bg-red-950/15"   },
} as const;

const EMOJI: Record<string, string> = { bull: "🟢", base: "🟡", bear: "🔴" };

function confidenceLabel(pct: number, key: string): string {
  if (key === "base") return pct >= 50 ? "Orta" : "Düşük/Orta";
  return pct >= 35 ? "Düşük/Orta" : "Düşük";
}

interface ScenarioPanelProps {
  scenarios: Scenario[];
  decision: string;
}

export default function ScenarioPanel({ scenarios }: ScenarioPanelProps) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  if (!scenarios || scenarios.length === 0) return null;

  const ordered = (["bull", "base", "bear"] as const)
    .map(k => scenarios.find(s => s.key === k))
    .filter(Boolean) as Scenario[];

  const dominant = [...scenarios].sort((a, b) => b.probability_pct - a.probability_pct)[0];
  const dominantLabel = t.scenario.labelMap[dominant.label] ?? dominant.label;

  const probLine = ordered
    .map(sc => `${t.scenario.labelMap[sc.label] ?? sc.label} %${sc.probability_pct}`)
    .join(" · ");

  return (
    <div className="rounded-2xl border border-eyay-border bg-eyay-surface overflow-hidden">
      {/* ── Kompakt özet (her zaman görünür) ── */}
      <div className="flex items-start gap-3 px-4 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-mono font-semibold text-eyay-dim tracking-widest uppercase">
              {t.scenario.title}
            </span>
            <span
              className="text-[8px] font-mono text-eyay-faint/70 px-1.5 py-px rounded border border-eyay-border/60 bg-eyay-raised/30 cursor-help"
              title="Bu oran istatistiksel tahmin değildir; mevcut karar, makro rejim, risk iştahı ve sinyal durumundan türetilmiş deterministik senaryo ağırlığıdır."
            >
              Sinyal türetimi
            </span>
          </div>
          <p className="text-[11px] font-mono text-eyay-text mt-1.5 tracking-wide">
            {probLine}
          </p>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span className={`text-[10px] font-mono font-semibold ${COLOR[dominant.color].label}`}>
              {EMOJI[dominant.key]} {t.scenario.dominant} {dominantLabel}
            </span>
            <span className="text-[9px] text-eyay-faint">·</span>
            <span className="text-[9px] font-mono text-amber-400/70">
              senaryo ağırlıkları sinyal durumundan türetilir
            </span>
          </div>
        </div>
        <button
          onClick={() => setOpen(v => !v)}
          aria-expanded={open}
          className="shrink-0 text-[10px] font-mono text-eyay-blue hover:text-blue-300 transition-colors mt-0.5 whitespace-nowrap"
        >
          {open ? "Gizle ▲" : "Detaylar ▼"}
        </button>
      </div>

      {/* ── Detay accordion ── */}
      {open && (
        <>
          <div className="border-t border-eyay-border grid grid-cols-3 gap-0 divide-x divide-eyay-border">
            {ordered.map(sc => {
              const s = COLOR[sc.color];
              const scLabel = t.scenario.labelMap[sc.label] ?? sc.label;
              const conf = confidenceLabel(sc.probability_pct, sc.key);
              return (
                <div key={sc.key} className={`p-3 ${s.bg} flex flex-col gap-2`}>
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold font-mono ${s.label}`}>
                      {EMOJI[sc.key]} {scLabel}
                    </span>
                    <span className={`text-sm font-black font-mono ${s.label}`}>
                      %{sc.probability_pct}
                    </span>
                  </div>
                  <span className="text-[8px] font-mono text-eyay-faint/60">
                    Güven: {conf}
                  </span>
                  <div className="h-0.5 rounded-full bg-white/5">
                    <div
                      className={`h-full rounded-full ${s.bar}`}
                      style={{ width: `${sc.probability_pct}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-eyay-dim leading-snug line-clamp-2" title={sc.trigger}>
                    {sc.trigger}
                  </p>
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
        </>
      )}
    </div>
  );
}
