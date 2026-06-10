"use client";

/**
 * FAZ 19 — Event Calendar Panel Shell.
 *
 * Sağ kolon "Olay Takvimi" paneline [Takvim 3D] / [Liste] toggle.
 * - 3D modu : EventCalendar3DLayer (lazy, default).
 * - Liste modu : legacy CatalystSidebar (dokunulmaz, güvenli fallback).
 * Crash/error → CatalystSidebar listesine düşer. Karar üretmez.
 */
import { lazy, Suspense, useState } from "react";

import CatalystSidebar from "@/components/CatalystSidebar";
import EventCalendarErrorBoundary from "@/components/EventCalendarErrorBoundary";
import type { CatalystEvent } from "@/lib/types";

const EventCalendar3DLayer = lazy(
  () => import("@/components/EventCalendar3DLayer"),
);

type ViewMode = "cal3d" | "list";

interface Props {
  catalysts: CatalystEvent[];
}

export default function EventCalendarPanelShell({ catalysts }: Props) {
  const [mode, setMode]               = useState<ViewMode>("cal3d");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  const legacyView = <CatalystSidebar catalysts={catalysts} />;

  const fallbackToList = (reason: string) => {
    setDegradedMsg(reason);
    setMode("list");
  };

  return (
    <div data-testid="event-calendar-shell" className="w-full max-w-full min-w-0 overflow-hidden">
      {/* Toggle bar */}
      <div className="flex items-center justify-between px-2 py-1.5 mb-1 bg-eyay-raised/60 border border-eyay-border/60 rounded-lg">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="w-1 h-1 rounded-full bg-cyan-400/70 shrink-0" />
          <span className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest font-semibold truncate">
            Olay Takvimi
          </span>
          {degradedMsg && mode === "list" && (
            <span className="text-[8px] font-mono text-amber-400/80 truncate">· radar yok</span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => { setDegradedMsg(null); setMode("cal3d"); }}
            className={`px-2 py-0.5 rounded-md text-[9px] font-mono uppercase tracking-wider transition-colors ${
              mode === "cal3d"
                ? "bg-cyan-600/25 text-cyan-200 border border-cyan-500/50 shadow-[0_0_10px_rgba(34,211,238,0.30)]"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "cal3d"}
            data-testid="ec-toggle-3d"
          >
            🗓 Takvim 3D
          </button>
          <button
            type="button"
            onClick={() => setMode("list")}
            className={`px-2 py-0.5 rounded-md text-[9px] font-mono uppercase tracking-wider transition-colors ${
              mode === "list"
                ? "bg-eyay-blue/20 text-eyay-blue border border-eyay-blue/40"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "list"}
            data-testid="ec-toggle-list"
          >
            Liste
          </button>
        </div>
      </div>

      {/* Liste modu: legacy CatalystSidebar */}
      {mode === "list" && legacyView}

      {/* 3D modu */}
      {mode === "cal3d" && (
        <EventCalendarErrorBoundary
          fallback={legacyView}
          onError={(err) => fallbackToList(err?.message || "render_error")}
        >
          <Suspense fallback={legacyView}>
            <EventCalendar3DLayer catalysts={catalysts} />
          </Suspense>
        </EventCalendarErrorBoundary>
      )}
    </div>
  );
}
