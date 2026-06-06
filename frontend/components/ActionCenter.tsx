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
  AÇIL:   { label: "AÇILIM",  accent: "text-emerald-300", accentBg: "bg-emerald-950/30", accentBorder: "border-emerald-900/60", stepNum: "bg-emerald-500/15 text-emerald-300 border-emerald-700/40" },
  BEKLE:  { label: "BEKLE",   accent: "text-amber-300",   accentBg: "bg-amber-950/20",   accentBorder: "border-amber-900/50",   stepNum: "bg-amber-500/15 text-amber-300 border-amber-700/40" },
  KÜÇÜLT: { label: "KÜÇÜLT",  accent: "text-orange-300",  accentBg: "bg-orange-950/20",  accentBorder: "border-orange-900/50",  stepNum: "bg-orange-500/15 text-orange-300 border-orange-700/40" },
  KAPAT:  { label: "KAPAT",   accent: "text-red-300",     accentBg: "bg-red-950/25",     accentBorder: "border-red-900/60",     stepNum: "bg-red-500/15 text-red-300 border-red-700/40" },
};

// Flip yön kartları için iki ana grup teması
const FLIP_GROUP: Record<"up" | "down" | "neutral", {
  title:     string;
  accent:    string;
  bg:        string;
  border:    string;
  icon:      string;
  bullet:    string;
}> = {
  up:      { title: "İyileşme Sinyalleri", accent: "text-emerald-300", bg: "bg-emerald-950/15", border: "border-emerald-900/40", icon: "↗", bullet: "bg-emerald-400" },
  down:    { title: "Kriz Tetikleyicileri", accent: "text-red-300",    bg: "bg-red-950/15",     border: "border-red-900/40",     icon: "↘", bullet: "bg-red-400" },
  neutral: { title: "Belirsizlik",         accent: "text-amber-300",   bg: "bg-amber-950/15",   border: "border-amber-900/40",   icon: "→", bullet: "bg-amber-400" },
};

// ---------------------------------------------------------------------------
// Koşul satırı: "metin (şu an X)" → metin + ayrı görsel mevcut-değer çipi
// ---------------------------------------------------------------------------

function splitCondition(raw: string): { main: string; current: string | null; threshold: string | null } {
  // "(şu an X)" parantezini ayıkla
  const curMatch = raw.match(/\(şu an[:\s]*([^)]+)\)/i);
  const current  = curMatch ? curMatch[1].trim() : null;
  const main     = curMatch ? raw.replace(curMatch[0], "").trim() : raw.trim();

  // Eşik değerini metinden tahmin et: ilk $XX,XXX veya XX,XX rakamı
  const thrMatch = main.match(/\$?[\d,]+(?:\.\d+)?/);
  const threshold = thrMatch ? thrMatch[0] : null;

  return { main, current, threshold };
}

function ConditionRow({ raw, group }: { raw: string; group: typeof FLIP_GROUP[keyof typeof FLIP_GROUP] }) {
  const { main, current } = splitCondition(raw);
  return (
    <div className="flex items-start gap-2.5 py-2 first:pt-0 last:pb-0">
      <span className={`shrink-0 mt-1.5 w-1 h-1 rounded-full ${group.bullet}`} />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] text-eyay-text leading-snug">{main}</p>
        {current && (
          <p className="text-[9px] font-mono text-eyay-faint mt-0.5">
            ŞU AN: <span className="text-eyay-dim">{current}</span>
          </p>
        )}
      </div>
    </div>
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">

      {/* ═══════════════════════════════════════════════════════════════════
          SOL — OPERASYONEL ADIMLAR
         ═══════════════════════════════════════════════════════════════════ */}
      {ownerActions?.length > 0 && (
        <div className={`rounded-2xl border ${theme.accentBorder} ${theme.accentBg} overflow-hidden`}>

          {/* Başlık */}
          <div className="px-5 py-3.5 border-b border-white/5 flex items-center justify-between">
            <div>
              <p className="text-[9px] text-eyay-faint uppercase tracking-[0.2em] font-bold">
                {t.actionCenter.operationalSteps}
              </p>
              <p className={`text-base font-bold mt-1 ${theme.accent}`}>
                Şimdi ne yapmalıyım?
              </p>
            </div>
            <span className={`text-[10px] font-mono font-bold px-2 py-1 rounded border ${theme.stepNum}`}>
              {theme.label} MODU
            </span>
          </div>

          {/* Adım listesi */}
          <ol className="px-5 py-4 space-y-3.5">
            {ownerActions.map((action, i) => (
              <li key={i} className="flex items-start gap-3">
                <span
                  className={`shrink-0 flex items-center justify-center w-6 h-6 rounded-md border font-mono text-[11px] font-black ${theme.stepNum}`}
                >
                  {i + 1}
                </span>
                <p className="text-xs text-eyay-text leading-relaxed pt-0.5">{action}</p>
              </li>
            ))}
          </ol>

          {/* Alt bilgi */}
          <div className="px-5 py-2 border-t border-white/5 bg-black/20">
            <p className="text-[9px] font-mono text-eyay-faint tracking-wider">
              PAPER_SAFE · NO_EXECUTION · tüm kararlar insana aittir
            </p>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          SAĞ — SENARYO TETİKLEYİCİLERİ (yön bazında 2 panel)
         ═══════════════════════════════════════════════════════════════════ */}
      {flipConditions?.length > 0 && (
        <div className="rounded-2xl border border-eyay-border bg-eyay-surface overflow-hidden flex flex-col">

          {/* Başlık */}
          <div className="px-5 py-3.5 border-b border-eyay-border">
            <p className="text-[9px] text-eyay-faint uppercase tracking-[0.2em] font-bold">
              {t.actionCenter.decisionChange}
            </p>
            <p className="text-base font-bold text-eyay-text mt-1">
              Kararı değiştirecek koşullar
            </p>
          </div>

          {/* İçerik — yön kartları (iyileşme + kriz yan yana) */}
          <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-px bg-eyay-border/50">
            {flipConditions.map((fc, fi) => {
              const group = FLIP_GROUP[fc.icon as keyof typeof FLIP_GROUP] ?? FLIP_GROUP.neutral;
              return (
                <div key={fi} className={`p-4 ${group.bg}`}>

                  {/* Yön başlığı */}
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/5">
                    <span className={`flex items-center justify-center w-6 h-6 rounded-full border-2 ${group.border} ${group.accent} font-bold text-sm leading-none`}>
                      {group.icon}
                    </span>
                    <span className={`text-[11px] font-bold tracking-wider uppercase ${group.accent}`}>
                      {group.title}
                    </span>
                  </div>

                  {/* Koşullar — divider'lı liste */}
                  <div className="divide-y divide-white/5">
                    {fc.conditions.map((cond, ci) => (
                      <ConditionRow key={ci} raw={cond} group={group} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Alt bilgi */}
          <div className="px-5 py-2 border-t border-eyay-border bg-black/20">
            <p className="text-[9px] font-mono text-eyay-faint tracking-wider">
              Bu koşullar gerçekleşirse karar otomatik güncellenir
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
