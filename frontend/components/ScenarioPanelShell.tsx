"use client";

/**
 * Scenario Panel Shell.
 *
 * SENARYO paneline [⚔ Battle] / [Liste] toggle ekler.
 * - Battle modu : ScenarioBattleLayer (lazy, sadece görsel katman).
 * - Liste modu  : orijinal ScenarioPanel (dokunulmaz, legacy fallback).
 * Battle crash/veri eksik → otomatik liste fallback + küçük uyarı.
 * Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 */
import { lazy, Suspense, useCallback, useState } from "react";

import ScenarioBattleErrorBoundary from "@/components/ScenarioBattleErrorBoundary";
import ScenarioPanel from "@/components/ScenarioPanel";
import type { Scenario } from "@/lib/types";

const ScenarioBattleLayer = lazy(
  () => import("@/components/ScenarioBattleLayer"),
);

type ViewMode = "battle" | "list";

interface Props {
  scenarios: Scenario[];
  decision: string;
}

export default function ScenarioPanelShell({ scenarios, decision }: Props) {
  const [mode, setMode]               = useState<ViewMode>("battle");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  const legacyView = <ScenarioPanel scenarios={scenarios} decision={decision} />;

  const fallbackToList = useCallback((reason: string) => {
    setDegradedMsg(reason);
    setMode("list");
  }, []);

  if (!scenarios || scenarios.length === 0) return legacyView;

  return (
    <div data-testid="scenario-panel-shell">
      {/* ── Toggle bar ── */}
      <div className="flex items-center justify-between px-3 py-2 mb-1.5 bg-eyay-raised/60 border border-eyay-border/60 rounded-xl">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400/70" />
          <span className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-semibold">
            Senaryo
          </span>
          {degradedMsg && mode === "list" && (
            <span className="text-[9px] font-mono text-amber-400/80 ml-1">
              · Battle görünümü yüklenemedi, klasik senaryo kullanılıyor.
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => { setDegradedMsg(null); setMode("battle"); }}
            className={`px-3 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
              mode === "battle"
                ? "bg-amber-600/25 text-amber-200 border border-amber-500/50 shadow-[0_0_14px_rgba(251,191,36,0.30)]"
                : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
            }`}
            aria-pressed={mode === "battle"}
            data-testid="sp-toggle-battle"
          >
            ⚔ Battle
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
            data-testid="sp-toggle-list"
          >
            Liste
          </button>
        </div>
      </div>

      {/* ── Liste modu: orijinal ScenarioPanel ── */}
      {mode === "list" && legacyView}

      {/* ── Battle modu ── */}
      {mode === "battle" && (
        <ScenarioBattleErrorBoundary
          fallback={legacyView}
          onError={(err) => fallbackToList(err?.message || "render_error")}
        >
          <Suspense fallback={legacyView}>
            <ScenarioBattleLayer scenarios={scenarios} onDegraded={fallbackToList} />
          </Suspense>
        </ScenarioBattleErrorBoundary>
      )}
    </div>
  );
}
