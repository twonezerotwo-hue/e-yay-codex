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
}> = {
  AÇIL:   { label: "AÇILIM",  accent: "text-emerald-300", accentBg: "bg-emerald-950/25", accentBorder: "border-emerald-900/50", stepNum: "bg-emerald-500/15 text-emerald-300 border-emerald-700/40" },
  BEKLE:  { label: "BEKLE",   accent: "text-amber-300",   accentBg: "bg-amber-950/20",   accentBorder: "border-amber-900/45",   stepNum: "bg-amber-500/15 text-amber-300 border-amber-700/40" },
  KÜÇÜLT: { label: "KÜÇÜLT",  accent: "text-orange-300",  accentBg: "bg-orange-950/20",  accentBorder: "border-orange-900/45",  stepNum: "bg-orange-500/15 text-orange-300 border-orange-700/40" },
  KAPAT:  { label: "KAPAT",   accent: "text-red-300",     accentBg: "bg-red-950/25",     accentBorder: "border-red-900/55",     stepNum: "bg-red-500/15 text-red-300 border-red-700/40" },
};

// Yön kartları için kompakt tema
const FLIP_GROUP: Record<"up" | "down" | "neutral", {
  title:  string;
  accent: string;
  bg:     string;
  border: string;
  icon:   string;
  badge:  string;
}> = {
  up: {
    title:  "İYİLEŞME SİNYALLERİ",
    accent: "text-emerald-300",
    bg:     "bg-emerald-950/15",
    border: "border-emerald-900/40",
    icon:   "↗",
    badge:  "bg-emerald-500/15 text-emerald-300 border-emerald-700/40",
  },
  down: {
    title:  "KRİZ TETİKLEYİCİLERİ",
    accent: "text-red-300",
    bg:     "bg-red-950/15",
    border: "border-red-900/40",
    icon:   "↘",
    badge:  "bg-red-500/15 text-red-300 border-red-700/40",
  },
  neutral: {
    title:  "BELİRSİZLİK",
    accent: "text-amber-300",
    bg:     "bg-amber-950/15",
    border: "border-amber-900/40",
    icon:   "→",
    badge:  "bg-amber-500/15 text-amber-300 border-amber-700/40",
  },
};

// ---------------------------------------------------------------------------
// Koşul satırı — kompakt: tek satırda metin + opsiyonel "şu an" chip
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
    <li className="flex items-start gap-2 py-1.5 first:pt-0 last:pb-0">
      <span className={`shrink-0 mt-0.5 text-[9px] font-mono font-bold ${group.accent} opacity-70`}>
        {index + 1}.
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[10.5px] text-eyay-text leading-snug">{main}</p>
        {current && (
          <p className="text-[9px] mt-0.5">
            <span className="text-eyay-faint">şu an: </span>
            <span className={`font-mono font-semibold ${group.accent}`}>{current}</span>
          </p>
        )}
      </div>
    </li>
  );
}

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

  // flip_conditions içinden up/down/neutral'a göre ayır — 3 sütun layout
  const upGroup      = flipConditions.find(fc => fc.icon === "up");
  const downGroup    = flipConditions.find(fc => fc.icon === "down");
  const neutralGroup = flipConditions.find(fc => fc.icon === "neutral");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">

      {/* ─── Sütun 1: Operasyonel Adımlar ──────────────────────────────── */}
      {ownerActions?.length > 0 && (
        <div className={`rounded-xl border ${theme.accentBorder} ${theme.accentBg} overflow-hidden flex flex-col`}>
          <div className="px-3 py-2 border-b border-white/5 flex items-center justify-between">
            <div>
              <p className="text-[8px] text-eyay-faint uppercase tracking-widest font-bold">
                {t.actionCenter.operationalSteps}
              </p>
              <p className={`text-[12px] font-bold leading-tight mt-0.5 ${theme.accent}`}>
                Şimdi ne yapmalıyım?
              </p>
            </div>
            <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border ${theme.stepNum}`}>
              {theme.label}
            </span>
          </div>

          <ol className="px-3 py-2.5 space-y-2 flex-1">
            {ownerActions.map((action, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className={`shrink-0 flex items-center justify-center w-4 h-4 rounded-md border font-mono text-[9px] font-black ${theme.stepNum}`}>
                  {i + 1}
                </span>
                <p className="text-[10.5px] text-eyay-text leading-snug pt-0.5">{action}</p>
              </li>
            ))}
          </ol>

          <div className="px-3 py-1 border-t border-white/5 bg-black/20">
            <p className="text-[8px] font-mono text-eyay-faint tracking-wider">
              Analiz modu · Canlı emir gönderimi kapalı
            </p>
          </div>
        </div>
      )}

      {/* ─── Sütun 2: İyileşme Sinyalleri (UP) ─────────────────────────── */}
      {upGroup && (
        <FlipColumn group={FLIP_GROUP.up} conditions={upGroup.conditions} />
      )}

      {/* ─── Sütun 3: Kriz Tetikleyicileri (DOWN) ──────────────────────── */}
      {downGroup && (
        <FlipColumn group={FLIP_GROUP.down} conditions={downGroup.conditions} />
      )}

      {/* Neutral varsa, ek bilgi olarak alta tam genişlik */}
      {neutralGroup && !downGroup && (
        <FlipColumn group={FLIP_GROUP.neutral} conditions={neutralGroup.conditions} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function FlipColumn({
  group, conditions,
}: {
  group:      typeof FLIP_GROUP[keyof typeof FLIP_GROUP];
  conditions: string[];
}) {
  return (
    <div className={`rounded-xl border ${group.border} ${group.bg} overflow-hidden flex flex-col`}>
      <div className="px-3 py-2 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`flex items-center justify-center w-5 h-5 rounded-full border ${group.border} ${group.accent} font-bold text-xs leading-none shrink-0`}>
            {group.icon}
          </span>
          <p className={`text-[11px] font-bold tracking-wide uppercase truncate ${group.accent}`}>
            {group.title}
          </p>
        </div>
        <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border ${group.badge} shrink-0`}>
          {conditions.length} koşul
        </span>
      </div>

      <ol className="px-3 py-2 flex-1">
        {conditions.map((cond, ci) => (
          <ConditionRow key={ci} raw={cond} group={group} index={ci} />
        ))}
      </ol>

      <div className="px-3 py-1 border-t border-white/5 bg-black/20">
        <p className="text-[8px] font-mono text-eyay-faint tracking-wider">
          gerçekleşirse karar güncellenir
        </p>
      </div>
    </div>
  );
}
