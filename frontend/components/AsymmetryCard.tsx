"use client";

import type { AsymmetrySignal } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ---------------------------------------------------------------------------
// Style map
// ---------------------------------------------------------------------------

const STYLES = {
  green:  { ring: "border-emerald-700", label: "text-emerald-400", bar: "bg-emerald-500", glow: "shadow-emerald-900/40" },
  lime:   { ring: "border-lime-700",    label: "text-lime-400",    bar: "bg-lime-500",    glow: "shadow-lime-900/40"    },
  yellow: { ring: "border-amber-700",   label: "text-amber-400",   bar: "bg-amber-400",   glow: "shadow-amber-900/40"   },
  orange: { ring: "border-orange-700",  label: "text-orange-400",  bar: "bg-orange-500",  glow: "shadow-orange-900/40"  },
  red:    { ring: "border-red-700",     label: "text-red-400",     bar: "bg-red-500",     glow: "shadow-red-900/40"     },
} as const;

// ---------------------------------------------------------------------------

interface AsymmetryCardProps {
  asymmetry: AsymmetrySignal;
}

export default function AsymmetryCard({ asymmetry }: AsymmetryCardProps) {
  const { t } = useLanguage();
  if (!asymmetry) return null;

  const s = STYLES[asymmetry.color] ?? STYLES.yellow;
  const totalWidth = asymmetry.expected_gain_pct + asymmetry.expected_loss_pct;
  const gainWidth  = totalWidth > 0 ? (asymmetry.expected_gain_pct / totalWidth) * 100 : 50;
  const lossWidth  = 100 - gainWidth;

  return (
    <div className={`bg-eyay-surface rounded-2xl border ${s.ring} overflow-hidden shadow-lg ${s.glow} h-full flex flex-col`}>
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-eyay-border">
        <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">
          {t.asymmetry.sectionLabel}
        </p>
        <p className="text-sm font-semibold text-eyay-text mt-0.5">{t.asymmetry.title}</p>
      </div>

      <div className="p-4 space-y-4 flex-1">
        {/* Ratio — büyük sayı */}
        <div className="flex items-end justify-between gap-3">
          <div>
            <span className={`font-mono font-black text-4xl leading-none ${s.label}`}>
              {asymmetry.ratio.toFixed(1)}
              <span className="text-lg font-bold">×</span>
            </span>
            <p className={`text-xs font-semibold mt-1 ${s.label}`}>{asymmetry.label}</p>
          </div>

          {/* Gain vs Loss sayısal */}
          <div className="text-right space-y-1">
            <div className="text-[11px] font-mono">
              <span className="text-eyay-faint">{t.asymmetry.gain} </span>
              <span className="text-emerald-400 font-semibold">+{asymmetry.expected_gain_pct}%</span>
            </div>
            <div className="text-[11px] font-mono">
              <span className="text-eyay-faint">{t.asymmetry.loss}  </span>
              <span className="text-red-400 font-semibold">−{asymmetry.expected_loss_pct}%</span>
            </div>
          </div>
        </div>

        {/* Visual bar */}
        <div>
          <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
            <div
              className="bg-emerald-500 rounded-l-full transition-all duration-700"
              style={{ width: `${gainWidth}%` }}
            />
            <div
              className="bg-red-500 rounded-r-full transition-all duration-700"
              style={{ width: `${lossWidth}%` }}
            />
          </div>
          <div className="flex justify-between mt-1">
            <span className="text-[9px] font-mono text-emerald-400/60">{t.asymmetry.upside}</span>
            <span className="text-[9px] font-mono text-red-400/60">{t.asymmetry.downside}</span>
          </div>
        </div>

        {/* Brief */}
        <p className="text-xs text-eyay-dim leading-relaxed border-t border-eyay-border pt-3">
          {asymmetry.brief}
        </p>

        {/* Methodology note */}
        <p className="text-[9px] text-eyay-faint font-mono leading-snug">
          {t.asymmetry.methodology}
        </p>
      </div>
    </div>
  );
}
