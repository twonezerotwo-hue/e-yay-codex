"use client";

/**
 * FAZ 15 — News Panel Shell.
 *
 * Ana dashboard "Haber Akışı" paneline [Liste] / [🌐 Radar] toggle ekler.
 * - Liste modu : orijinal NewsPanel (dokunulmaz, legacy fallback).
 * - Radar modu : BreakingNewsRadarLayer (lazy, aynı endpoint).
 * Radar crash/timeout/degraded → otomatik liste fallback.
 * Karar üretmez. Trade etmez.
 */
import { lazy, Suspense, useState } from "react";

import BreakingNewsErrorBoundary from "@/components/BreakingNewsErrorBoundary";
import NewsPanel from "@/components/NewsPanel";
import type { NewsHeadline } from "@/lib/types";

const NewsMapRadarLayer = lazy(
  () => import("@/components/NewsMapRadarLayer"),
);

type ViewMode = "list" | "radar";

interface Props {
  headlines: NewsHeadline[];
}

export default function NewsPanelShell({ headlines }: Props) {
  const [mode, setMode]               = useState<ViewMode>("radar");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  const legacyView = <NewsPanel headlines={headlines} />;

  const fallbackToList = (reason: string) => {
    setDegradedMsg(reason);
    setMode("list");
  };

  return (
    <div id="news" data-section="news" data-testid="news-panel-shell" className="scroll-mt-20">
      {/* ── Toggle bar ── */}
      <div className="flex items-center justify-between px-3 py-2 mb-1.5 bg-eyay-raised/60 border border-eyay-border/60 rounded-xl">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-eyay-blue/70" />
          <span className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-semibold">
            Haber Akışı
          </span>
          <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5">
            {headlines.length}
          </span>
          {degradedMsg && mode === "list" && (
            <span className="text-[9px] font-mono text-amber-400/80 ml-1">
              · Radar yüklenemedi
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setMode("list")}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "list"
                ? "bg-eyay-blue/20 text-eyay-blue border border-eyay-blue/40"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "list"}
            data-testid="np-toggle-list"
          >
            Liste
          </button>
          <button
            type="button"
            onClick={() => { setDegradedMsg(null); setMode("radar"); }}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "radar"
                ? "bg-cyan-600/25 text-cyan-200 border border-cyan-500/50 shadow-[0_0_14px_rgba(34,211,238,0.30)]"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "radar"}
            data-testid="np-toggle-radar"
          >
            🌐 Radar
          </button>
        </div>
      </div>

      {/* ── Liste modu: orijinal NewsPanel (kendi border/rounded getiriyor) ── */}
      {mode === "list" && legacyView}

      {/* ── Radar modu: BreakingNewsRadarLayer ── */}
      {mode === "radar" && (
        <div
          className="min-h-[520px] relative overflow-visible bg-eyay-surface rounded-b-2xl border border-eyay-border border-t-0 p-4"
          data-testid="np-radar-container"
        >
          <BreakingNewsErrorBoundary
            fallback={legacyView}
            onError={(err) => fallbackToList(err?.message || "render_error")}
          >
            <Suspense fallback={legacyView}>
              <NewsMapRadarLayer headlines={headlines} onDegraded={fallbackToList} />
            </Suspense>
          </BreakingNewsErrorBoundary>
        </div>
      )}
    </div>
  );
}
