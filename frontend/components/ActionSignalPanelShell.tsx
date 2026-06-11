"use client";

/**
 * FAZ 20 — Action Signal Panel Shell.
 *
 * "Tavsiye Edilen Aksiyon" alanına [Launch] / [Klasik] toggle ekler.
 * - Launch modu : ActionSignalLaunchLayer (lazy, default).
 * - Klasik modu : legacy DecisionBanner (dokunulmaz, güvenli fallback).
 * Crash/error → DecisionBanner'a düşer. Karar üretmez.
 */
import { lazy, Suspense, useState } from "react";

import ActionSignalErrorBoundary from "@/components/ActionSignalErrorBoundary";
import DecisionBanner from "@/components/DecisionBanner";
import type { RegimeReport } from "@/lib/types";

const ActionSignalLaunchLayer = lazy(
  () => import("@/components/ActionSignalLaunchLayer"),
);

type ViewMode = "launch" | "classic";

interface Props {
  report: RegimeReport;
}

export default function ActionSignalPanelShell({ report }: Props) {
  const [mode, setMode]               = useState<ViewMode>("launch");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  const legacyView = <DecisionBanner report={report} />;

  const fallbackToClassic = (reason: string) => {
    setDegradedMsg(reason);
    setMode("classic");
  };

  return (
    <div data-testid="action-signal-shell" className="w-full max-w-full min-w-0 overflow-hidden">
      {/* Toggle bar */}
      <div className="flex items-center justify-between px-3 py-1.5 mb-1.5 bg-eyay-raised/60 border border-eyay-border/60 rounded-xl">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/70 shrink-0" />
          <span className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-semibold truncate">
            Tavsiye Edilen Aksiyon
          </span>
          {degradedMsg && mode === "classic" && (
            <span className="text-[9px] font-mono text-amber-400/80 ml-1 truncate">
              · Launch görünümü yüklenemedi
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => { setDegradedMsg(null); setMode("launch"); }}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "launch"
                ? "bg-cyan-600/25 text-cyan-200 border border-cyan-500/50 shadow-[0_0_14px_rgba(34,211,238,0.30)]"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "launch"}
            data-testid="as-toggle-race"
          >
            🚀 Launch
          </button>
          <button
            type="button"
            onClick={() => setMode("classic")}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "classic"
                ? "bg-eyay-blue/20 text-eyay-blue border border-eyay-blue/40"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "classic"}
            data-testid="as-toggle-classic"
          >
            Klasik
          </button>
        </div>
      </div>

      {/* Klasik mode: legacy DecisionBanner */}
      {mode === "classic" && legacyView}

      {/* Launch mode */}
      {mode === "launch" && (
        <ActionSignalErrorBoundary
          fallback={legacyView}
          onError={(err) => fallbackToClassic(err?.message || "render_error")}
        >
          <Suspense fallback={legacyView}>
            <ActionSignalLaunchLayer report={report} />
          </Suspense>
        </ActionSignalErrorBoundary>
      )}
    </div>
  );
}
