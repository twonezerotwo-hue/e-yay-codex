"use client";

/**
 * FAZ 15 — Breaking News Panel Shell.
 *
 * Legacy "Son Dakika · Savaş Gündemi" liste paneli ana kaynak ve güvenli
 * fallback'tir. Kullanıcı "🌐 Radar" toggle'ına bastığında event radar
 * layer lazy yüklenir.
 *
 * Radar layer:
 *   - Crash ederse ErrorBoundary listeye döner.
 *   - Endpoint degraded/timeout dönerse listeye döner.
 *
 * Karar üretmez. Trade etmez.
 */
import { lazy, Suspense, useState } from "react";

import BreakingNewsErrorBoundary from "@/components/BreakingNewsErrorBoundary";
import type { NewsHeadline } from "@/lib/types";

const BreakingNewsRadarLayer = lazy(
  () => import("@/components/BreakingNewsRadarLayer"),
);

type ViewMode = "list" | "radar";

interface Props {
  headlines: NewsHeadline[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Legacy liste — AgentCommandCenter'daki orijinal markup, dokunulmadan
// ─────────────────────────────────────────────────────────────────────────────

function LegacyList({ headlines }: Props) {
  return (
    <div className="space-y-2">
      {headlines.map((h, i) => {
        const display = (h.title_tr && h.title_tr.trim()) || h.title;
        return (
          <a
            key={i}
            href={h.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-3 p-3 rounded-lg bg-black/30 border border-red-900/40 hover:border-red-700/60 transition-colors group"
          >
            <span className="shrink-0 mt-0.5 text-[9px] font-mono font-black text-red-300 border border-red-800/60 bg-red-950/40 rounded px-1.5 py-0.5 uppercase tracking-widest">
              Son Dakika
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-eyay-text leading-relaxed group-hover:text-white transition-colors">
                {display}
              </p>
              <p className="text-[10px] text-eyay-faint mt-1">{h.source}</p>
            </div>
          </a>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shell
// ─────────────────────────────────────────────────────────────────────────────

export default function BreakingNewsPanelShell({ headlines }: Props) {
  const [mode, setMode]               = useState<ViewMode>("list");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  if (headlines.length === 0) return null;

  const listView = <LegacyList headlines={headlines} />;

  const fallbackToList = (reason: string) => {
    setDegradedMsg(reason);
    setMode("list");
  };

  return (
    <section className="rounded-2xl border border-red-800/60 bg-red-950/20 p-5" data-testid="breaking-news-shell">
      {/* Başlık + toggle */}
      <div className="flex items-center gap-2 mb-3">
        <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
        <span className="text-base">🚨</span>
        <p className="text-[10px] font-mono text-red-300 uppercase tracking-widest font-black">
          Son Dakika · Savaş Gündemi
        </p>
        <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5">
          {headlines.length}
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setMode("list")}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "list"
                ? "bg-red-600/25 text-red-200 border border-red-600/50"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "list"}
            data-testid="bn-toggle-list"
          >
            Liste
          </button>
          <button
            type="button"
            onClick={() => {
              setDegradedMsg(null);
              setMode("radar");
            }}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "radar"
                ? "bg-cyan-600/25 text-cyan-200 border border-cyan-500/50 shadow-[0_0_14px_rgba(34,211,238,0.30)]"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "radar"}
            data-testid="bn-toggle-radar"
          >
            🌐 Radar
          </button>
        </div>
      </div>

      {/* Degraded uyarısı */}
      {degradedMsg && mode === "list" && (
        <div
          className="mb-3 text-[10px] font-mono text-amber-300/80 bg-amber-950/20 border border-amber-800/40 rounded-md px-3 py-1.5"
          data-testid="bn-degraded-warning"
        >
          Haber radarı yüklenemedi, klasik liste kullanılıyor. ({degradedMsg})
        </div>
      )}

      {/* View */}
      {mode === "list" && listView}

      {mode === "radar" && (
        <BreakingNewsErrorBoundary
          fallback={listView}
          onError={(err) => fallbackToList(err?.message || "render_error")}
        >
          <Suspense fallback={listView}>
            <BreakingNewsRadarLayer onDegraded={fallbackToList} />
          </Suspense>
        </BreakingNewsErrorBoundary>
      )}
    </section>
  );
}
