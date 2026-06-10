"use client";

/**
 * FAZ 17 — Command Signals Panel Shell.
 *
 * Katman 1 "Durum Odası / Komut Sinyalleri" bölümüne [Cards] / [Liste]
 * toggle ekler. Cards = holografik görünüm (default), Liste = legacy
 * AssetGrid (dokunulmaz, güvenli fallback).
 * Cards crash/boş veri → otomatik Liste. Karar üretmez.
 */
import { lazy, Suspense, useState } from "react";

import AssetGrid from "@/components/AssetGrid";
import CommandSignalsErrorBoundary from "@/components/CommandSignalsErrorBoundary";
import type { AssetSignal, TechnicalInsight } from "@/lib/types";

const CommandSignalCardsLayer = lazy(
  () => import("@/components/CommandSignalCardsLayer"),
);

type ViewMode = "cards" | "list";

interface Props {
  signals:       AssetSignal[];
  techInsights?: TechnicalInsight[];
}

export default function CommandSignalsPanelShell({ signals, techInsights = [] }: Props) {
  const [mode, setMode]               = useState<ViewMode>("cards");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  const legacyView = <AssetGrid signals={signals} techInsights={techInsights} />;

  const fallbackToList = (reason: string) => {
    setDegradedMsg(reason);
    setMode("list");
  };

  return (
    <div data-testid="command-signals-shell" className="w-full max-w-full min-w-0 overflow-hidden">
      {/* ── Toggle bar ── */}
      <div className="flex items-center justify-between px-3 py-2 mb-1.5 bg-eyay-raised/60 border border-eyay-border/60 rounded-xl">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/70" />
          <span className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-semibold">
            Katman 1 — Durum Odası
          </span>
          {degradedMsg && mode === "list" && (
            <span className="text-[9px] font-mono text-amber-400/80 ml-1">
              · Cards görünümü yüklenemedi, klasik liste kullanılıyor
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => { setDegradedMsg(null); setMode("cards"); }}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "cards"
                ? "bg-cyan-600/25 text-cyan-200 border border-cyan-500/50 shadow-[0_0_14px_rgba(34,211,238,0.30)]"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "cards"}
            data-testid="cs-toggle-cards"
          >
            🃏 Cards
          </button>
          <button
            type="button"
            onClick={() => setMode("list")}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "list"
                ? "bg-eyay-blue/20 text-eyay-blue border border-eyay-blue/40"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "list"}
            data-testid="cs-toggle-list"
          >
            Liste
          </button>
        </div>
      </div>

      {/* ── Liste modu: legacy AssetGrid ── */}
      {mode === "list" && legacyView}

      {/* ── Cards modu ── */}
      {mode === "cards" && (
        <CommandSignalsErrorBoundary
          fallback={legacyView}
          onError={(err) => fallbackToList(err?.message || "render_error")}
        >
          <Suspense fallback={legacyView}>
            <CommandSignalCardsLayer signals={signals} techInsights={techInsights} />
          </Suspense>
        </CommandSignalsErrorBoundary>
      )}
    </div>
  );
}
