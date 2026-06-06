"use client";

import type { ModuleHealth, HealthScore } from "@/lib/types";

// ─── Renk haritası ───────────────────────────────────────────────────────────

const SCORE_STYLE: Record<HealthScore, { dot: string; text: string; bg: string; border: string }> = {
  HIGH:   { dot: "bg-emerald-400", text: "text-emerald-400", bg: "bg-emerald-950/30", border: "border-emerald-900/50" },
  MEDIUM: { dot: "bg-amber-400",   text: "text-amber-400",   bg: "bg-amber-950/30",   border: "border-amber-900/50"   },
  LOW:    { dot: "bg-red-400",     text: "text-red-400",     bg: "bg-red-950/30",     border: "border-red-900/50"     },
};

const MODULE_LABELS: Record<string, string> = {
  calendar: "TAKVİM",
  price:    "FİYAT",
  news:     "HABER",
  signals:  "SİNYAL",
  rotation: "ROTASYON",
};

// ─── Monitoring Mode Banner ───────────────────────────────────────────────────

interface MonitoringBannerProps {
  aiError: boolean;  // true = AI raporu çalışmıyor
}

export function MonitoringBanner({ aiError }: MonitoringBannerProps) {
  if (!aiError) return null;
  return (
    <div className="w-full bg-amber-950/40 border-b border-amber-900/50 px-4 py-2 flex items-center gap-2.5">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
      <p className="text-xs font-mono text-amber-400 font-semibold tracking-wide">
        AI ANALİZİ KAPALI — İZLEME MODU
      </p>
      <span className="text-xs font-mono text-amber-600 ml-1">
        · Tüm kararlar manuel doğrulama gerektirir. Sistem veri izliyor, yorum üretmiyor.
      </span>
    </div>
  );
}

// ─── Modül Sağlık Çipleri ─────────────────────────────────────────────────────

interface SystemHealthBarProps {
  health: Record<string, ModuleHealth>;
}

export function SystemHealthBar({ health }: SystemHealthBarProps) {
  const entries = Object.entries(health);
  if (!entries.length) return null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {entries.map(([key, mod]) => {
        const s = SCORE_STYLE[mod.score] ?? SCORE_STYLE.LOW;
        return (
          <span
            key={key}
            title={mod.detail}
            className={`inline-flex items-center gap-1 text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${s.bg} ${s.border} ${s.text} cursor-default`}
          >
            <span className={`w-1 h-1 rounded-full flex-shrink-0 ${s.dot}`} />
            {MODULE_LABELS[key] ?? key.toUpperCase()}
          </span>
        );
      })}
    </div>
  );
}
