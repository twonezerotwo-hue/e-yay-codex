"use client";

import type { Decision, RegimeReport } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

const STYLES: Record<Decision, {
  bg: string; border: string; titleColor: string;
  glow: string; dot: string;
}> = {
  AÇIL:   {
    bg: "bg-emerald-950/60", border: "border-emerald-600/40",
    titleColor: "text-emerald-300", glow: "shadow-glow-green",
    dot: "bg-emerald-400",
  },
  BEKLE:  {
    bg: "bg-amber-950/50",   border: "border-amber-600/40",
    titleColor: "text-amber-300",   glow: "shadow-glow-amber",
    dot: "bg-amber-400",
  },
  KÜÇÜLT: {
    bg: "bg-orange-950/50",  border: "border-orange-600/40",
    titleColor: "text-orange-300",  glow: "shadow-glow-orange",
    dot: "bg-orange-400",
  },
  KAPAT:  {
    bg: "bg-red-950/60",     border: "border-red-600/40",
    titleColor: "text-red-300",     glow: "shadow-glow-red",
    dot: "bg-red-400",
  },
};

export default function DecisionBanner({ report }: { report: RegimeReport }) {
  const { t, lang } = useLanguage();
  const s = STYLES[report.decision];

  const time = new Date(report.generated_at).toLocaleTimeString(
    lang === "tr" ? "tr-TR" : "en-US",
    { hour: "2-digit", minute: "2-digit" },
  );

  const displayDecision = t.decision.displayMap[report.decision] ?? report.decision;
  const actionLabel     = t.decision.actionMap[report.decision]  ?? "";

  return (
    <div className={`rounded-2xl border ${s.border} ${s.bg} ${s.glow} overflow-hidden`}>

      {/* Ana karar satırı */}
      <div className="px-5 sm:px-7 py-5 flex flex-col sm:flex-row sm:items-center gap-4">

        {/* Sol: Karar + Aksiyon */}
        <div className="flex items-center gap-4 flex-1">
          <div className="flex items-center gap-3">
            <span className={`w-3 h-3 rounded-full shrink-0 ${s.dot}`} />
            <span className={`font-mono font-bold text-4xl sm:text-5xl tracking-widest ${s.titleColor}`}>
              {displayDecision}
            </span>
          </div>
          <div className="hidden sm:block h-10 w-px bg-white/10" />
          <div className="hidden sm:block">
            <p className="text-xs text-eyay-dim uppercase tracking-widest">{t.decision.actionLabel}</p>
            <p className="text-sm font-semibold text-eyay-text mt-0.5">{actionLabel}</p>
          </div>
        </div>

        {/* Sağ: Sinyaller + Zaman */}
        <div className="flex items-center gap-3 flex-wrap">
          <SignalChip count={report.blocking_count}  label={t.decision.chips.block}   color="red" />
          <SignalChip count={report.confirmed_count} label={t.decision.chips.confirm} color="green" />
          <SignalChip count={report.pending_count}   label={t.decision.chips.wait}    color="amber" />
          <span className="font-mono text-xs text-eyay-faint ml-1">{time}</span>
        </div>
      </div>

      {/* Verdict şeridi */}
      <div className="border-t border-white/5 bg-black/20 px-5 sm:px-7 py-3">
        <p className="text-sm text-eyay-dim leading-relaxed">
          {report.verdict}
        </p>
      </div>

    </div>
  );
}

function SignalChip({ count, label, color }: { count: number; label: string; color: string }) {
  const styles: Record<string, string> = {
    red:   "bg-red-950/80   text-red-400   border-red-800/50",
    green: "bg-emerald-950/80 text-emerald-400 border-emerald-800/50",
    amber: "bg-amber-950/80 text-amber-400  border-amber-800/50",
  };
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${styles[color]}`}>
      <span className="font-mono font-bold text-sm">{count}</span>
      <span className="opacity-75">{label}</span>
    </div>
  );
}
