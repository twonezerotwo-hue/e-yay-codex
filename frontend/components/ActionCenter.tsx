"use client";

import type { Decision, FlipCondition } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ---------------------------------------------------------------------------
// Karar rengine göre tema
// ---------------------------------------------------------------------------

const THEME: Record<Decision, {
  label: string;
  accent: string; accentBg: string; accentBorder: string;
  stepNum: string;
  glow: string;
}> = {
  AÇIL:   { label: "AÇILIM",  accent: "text-emerald-300", accentBg: "bg-emerald-950/40",  accentBorder: "border-emerald-700/70", stepNum: "bg-emerald-500/20 text-emerald-300 border-emerald-600/60", glow: "shadow-[0_0_24px_rgba(52,211,153,0.15)]" },
  BEKLE:  { label: "BEKLE",   accent: "text-amber-300",   accentBg: "bg-amber-950/30",    accentBorder: "border-amber-700/60",   stepNum: "bg-amber-500/20 text-amber-300 border-amber-600/50",    glow: "shadow-[0_0_24px_rgba(251,191,36,0.12)]" },
  KÜÇÜLT: { label: "KÜÇÜLT",  accent: "text-orange-300",  accentBg: "bg-orange-950/30",   accentBorder: "border-orange-700/60",  stepNum: "bg-orange-500/20 text-orange-300 border-orange-600/50", glow: "shadow-[0_0_24px_rgba(251,146,60,0.12)]" },
  KAPAT:  { label: "KAPAT",   accent: "text-red-300",     accentBg: "bg-red-950/35",      accentBorder: "border-red-700/70",     stepNum: "bg-red-500/20 text-red-300 border-red-600/60",          glow: "shadow-[0_0_24px_rgba(248,113,113,0.15)]" },
};

// Flip yön kartları için tema
const FLIP_GROUP: Record<"up" | "down" | "neutral", {
  title:       string;
  accent:      string;
  accentDim:   string;
  bg:          string;
  bgHover:     string;
  border:      string;
  borderGlow:  string;
  icon:        string;
  bullet:      string;
  badge:       string;
  dotPulse:    string;
}> = {
  up: {
    title:      "İyileşme Sinyalleri",
    accent:     "text-emerald-300",
    accentDim:  "text-emerald-400/70",
    bg:         "bg-emerald-950/20",
    bgHover:    "hover:bg-emerald-950/30",
    border:     "border-emerald-800/50",
    borderGlow: "shadow-[inset_0_0_20px_rgba(52,211,153,0.05),0_0_20px_rgba(52,211,153,0.10)]",
    icon:       "↗",
    bullet:     "bg-emerald-400",
    badge:      "bg-emerald-500/15 text-emerald-300 border-emerald-700/40",
    dotPulse:   "bg-emerald-400",
  },
  down: {
    title:      "Kriz Tetikleyicileri",
    accent:     "text-red-300",
    accentDim:  "text-red-400/70",
    bg:         "bg-red-950/20",
    bgHover:    "hover:bg-red-950/30",
    border:     "border-red-800/50",
    borderGlow: "shadow-[inset_0_0_20px_rgba(248,113,113,0.05),0_0_20px_rgba(248,113,113,0.10)]",
    icon:       "↘",
    bullet:     "bg-red-400",
    badge:      "bg-red-500/15 text-red-300 border-red-700/40",
    dotPulse:   "bg-red-400",
  },
  neutral: {
    title:      "Belirsizlik",
    accent:     "text-amber-300",
    accentDim:  "text-amber-400/70",
    bg:         "bg-amber-950/15",
    bgHover:    "hover:bg-amber-950/25",
    border:     "border-amber-800/40",
    borderGlow: "shadow-[inset_0_0_20px_rgba(251,191,36,0.04),0_0_16px_rgba(251,191,36,0.08)]",
    icon:       "→",
    bullet:     "bg-amber-400",
    badge:      "bg-amber-500/15 text-amber-300 border-amber-700/40",
    dotPulse:   "bg-amber-400",
  },
};

// ---------------------------------------------------------------------------
// Koşul satırı — büyütülmüş, değer çipli
// ---------------------------------------------------------------------------

function splitCondition(raw: string): { main: string; current: string | null } {
  const curMatch = raw.match(/\(şu an[:\s]*([^)]+)\)/i);
  const current  = curMatch ? curMatch[1].trim() : null;
  const main     = curMatch ? raw.replace(curMatch[0], "").trim() : raw.trim();
  return { main, current };
}

function ConditionRow({ raw, group, index }: {
  raw:   string;
  group: typeof FLIP_GROUP[keyof typeof FLIP_GROUP];
  index: number;
}) {
  const { main, current } = splitCondition(raw);
  return (
    <div className={`
      flex items-start gap-3 rounded-xl px-4 py-3.5
      border ${group.border} ${group.bg} ${group.bgHover}
      transition-colors duration-200
    `}>
      {/* Numara rozeti */}
      <span className={`
        shrink-0 flex items-center justify-center
        w-6 h-6 rounded-md border font-mono text-[11px] font-black
        ${group.badge}
      `}>
        {index + 1}
      </span>

      <div className="flex-1 min-w-0">
        <p className={`text-[13px] font-medium leading-snug ${group.accent}`}>{main}</p>
        {current && (
          <div className="mt-1.5 inline-flex items-center gap-1.5">
            <span className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider">Şu an:</span>
            <span className={`font-mono text-[11px] font-bold ${group.accent} bg-black/30 px-2 py-0.5 rounded-md border ${group.border}`}>
              {current}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ActionCenterProps {
  decision:        Decision;
  ownerActions:    string[];
  flipConditions:  FlipCondition[];
}

export default function ActionCenter({ decision, ownerActions, flipConditions }: ActionCenterProps) {
  const { t } = useLanguage();
  const theme = THEME[decision] ?? THEME.BEKLE;

  if (!ownerActions?.length && !flipConditions?.length) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">

      {/* ═══════════════════════════════════════════════════════════════════
          SOL — OPERASYONEL ADIMLAR
         ═══════════════════════════════════════════════════════════════════ */}
      {ownerActions?.length > 0 && (
        <div className={`
          rounded-2xl border ${theme.accentBorder} ${theme.accentBg} ${theme.glow}
          overflow-hidden flex flex-col
        `}>

          {/* Başlık */}
          <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
            <div>
              <p className="text-[9px] text-eyay-faint uppercase tracking-[0.2em] font-bold">
                {t.actionCenter.operationalSteps}
              </p>
              <p className={`text-lg font-bold mt-1 ${theme.accent}`}>
                Şimdi ne yapmalıyım?
              </p>
            </div>
            <div className="flex items-center gap-2">
              {/* Canlı göstergesi */}
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                decision === "AÇIL" ? "bg-emerald-400" :
                decision === "BEKLE" ? "bg-amber-400" :
                decision === "KÜÇÜLT" ? "bg-orange-400" : "bg-red-400"
              }`} />
              <span className={`text-[10px] font-mono font-bold px-2.5 py-1 rounded-md border ${theme.stepNum}`}>
                {theme.label} MODU
              </span>
            </div>
          </div>

          {/* Adım listesi */}
          <ol className="px-6 py-5 space-y-3 flex-1">
            {ownerActions.map((action, i) => (
              <li key={i} className="flex items-start gap-3.5">
                <span className={`
                  shrink-0 flex items-center justify-center
                  w-7 h-7 rounded-lg border font-mono text-[12px] font-black
                  ${theme.stepNum}
                `}>
                  {i + 1}
                </span>
                <p className={`text-[13px] leading-relaxed pt-0.5 ${theme.accent} opacity-90`}>{action}</p>
              </li>
            ))}
          </ol>

          {/* Alt bilgi */}
          <div className="px-6 py-2.5 border-t border-white/5 bg-black/25">
            <p className="text-[9px] font-mono text-eyay-faint tracking-wider">
              PAPER_SAFE · NO_EXECUTION · tüm kararlar insana aittir
            </p>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          SAĞ — KARARAYI DEĞİŞTİRECEK KOŞULLAR
         ═══════════════════════════════════════════════════════════════════ */}
      {flipConditions?.length > 0 && (
        <div className={`
          rounded-2xl border-2 border-eyay-border
          bg-eyay-surface overflow-hidden flex flex-col
          shadow-[0_0_30px_rgba(99,179,237,0.06)]
        `}>

          {/* Başlık — vurgulu */}
          <div className="px-6 py-4 border-b border-eyay-border bg-eyay-raised/40">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[9px] text-eyay-faint uppercase tracking-[0.2em] font-bold">
                  {t.actionCenter.decisionChange}
                </p>
                <p className="text-xl font-extrabold text-eyay-text mt-1 tracking-tight">
                  Kararı değiştirecek koşullar
                </p>
              </div>
              {/* Aktif izleme rozeti */}
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-eyay-border bg-eyay-raised/60">
                <span className="w-1.5 h-1.5 rounded-full bg-eyay-blue animate-pulse" />
                <span className="text-[9px] font-mono font-bold text-eyay-blue tracking-widest uppercase">Aktif İzleme</span>
              </div>
            </div>
          </div>

          {/* İçerik — yön blokları (dikey sıralı her biri tam genişlik) */}
          <div className="flex-1 flex flex-col gap-3 p-4">
            {flipConditions.map((fc, fi) => {
              const group = FLIP_GROUP[fc.icon as keyof typeof FLIP_GROUP] ?? FLIP_GROUP.neutral;
              return (
                <div key={fi} className={`
                  rounded-xl border ${group.border} overflow-hidden
                  ${group.borderGlow}
                `}>

                  {/* Yön başlık bandı */}
                  <div className={`px-4 py-2.5 ${group.bg} border-b ${group.border} flex items-center gap-3`}>
                    <span className={`
                      flex items-center justify-center
                      w-8 h-8 rounded-full border-2 ${group.border}
                      ${group.accent} font-bold text-lg leading-none
                      ${group.bg}
                    `}>
                      {group.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <span className={`text-sm font-extrabold tracking-wide uppercase ${group.accent}`}>
                        {group.title}
                      </span>
                    </div>
                    {/* Koşul sayacı */}
                    <span className={`
                      text-[10px] font-mono font-bold px-2 py-0.5
                      rounded border ${group.badge}
                    `}>
                      {fc.conditions.length} koşul
                    </span>
                  </div>

                  {/* Koşul satırları */}
                  <div className={`p-3 space-y-2 ${group.bg}`}>
                    {fc.conditions.map((cond, ci) => (
                      <ConditionRow key={ci} raw={cond} group={group} index={ci} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Alt bilgi */}
          <div className="px-6 py-2.5 border-t border-eyay-border bg-black/20">
            <p className="text-[9px] font-mono text-eyay-faint tracking-wider">
              Bu koşullar gerçekleşirse karar otomatik güncellenir
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
