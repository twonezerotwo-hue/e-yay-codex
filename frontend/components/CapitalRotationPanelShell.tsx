"use client";

/**
 * FAZ 14 — Capital Rotation Panel Shell.
 *
 * Legacy CapitalFlowWidget ana kaynak ve güvenli fallback'tir.
 * Kullanıcı "Akış" toggle'ına bastığında animated/3D layer lazy yüklenir.
 *
 * Animated layer:
 *   - Crash ederse ErrorBoundary legacy görünüme döner.
 *   - Endpoint degraded/timeout dönerse legacy görünüme döner.
 *   - prefers-reduced-motion ve mobile için sade görünüm.
 *
 * Karar üretmez. Trade etmez. Auto tune etkilemez.
 */
import { lazy, Suspense, useState } from "react";

import CapitalFlowWidget from "@/components/CapitalFlowWidget";
import CapitalFlowErrorBoundary from "@/components/CapitalFlowErrorBoundary";
import type { CapitalRotation } from "@/lib/types";

// Animated layer lazy yüklenir — Klasik mod kullanıcısına ek bundle yüklenmez
const CapitalFlowAnimatedLayer = lazy(
  () => import("@/components/CapitalFlowAnimatedLayer"),
);

type ViewMode = "classic" | "flow";

interface Props {
  rotation: CapitalRotation | null | undefined;
}

export default function CapitalRotationPanelShell({ rotation }: Props) {
  const [mode, setMode]               = useState<ViewMode>("classic");
  const [degradedMsg, setDegradedMsg] = useState<string | null>(null);

  const legacyView = <CapitalFlowWidget rotation={rotation} />;

  // Animated layer'ı kapatıp kalıcı olarak legacy'ye dön
  const fallbackToClassic = (reason: string) => {
    setDegradedMsg(reason);
    setMode("classic");
  };

  return (
    <div className="space-y-2">
      {/* Toggle */}
      <div className="flex items-center justify-end gap-1">
        <button
          type="button"
          onClick={() => setMode("classic")}
          className={`px-2.5 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
            mode === "classic"
              ? "bg-eyay-blue/20 text-eyay-blue border border-eyay-blue/40"
              : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
          }`}
          aria-pressed={mode === "classic"}
          data-testid="cap-toggle-classic"
        >
          Klasik
        </button>
        <button
          type="button"
          onClick={() => {
            setDegradedMsg(null);
            setMode("flow");
          }}
          className={`px-2.5 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider transition-colors ${
            mode === "flow"
              ? "bg-emerald-600/20 text-emerald-300 border border-emerald-600/40"
              : "bg-eyay-raised/40 text-eyay-faint border border-eyay-border/40 hover:text-eyay-dim"
          }`}
          aria-pressed={mode === "flow"}
          data-testid="cap-toggle-flow"
        >
          Akış
        </button>
      </div>

      {/* Degraded warning */}
      {degradedMsg && mode === "classic" && (
        <div
          className="text-[10px] font-mono text-amber-300/80 bg-amber-950/20 border border-amber-800/40 rounded-md px-3 py-1.5"
          data-testid="cap-degraded-warning"
        >
          3D akış yüklenemedi, klasik görünüm kullanılıyor. ({degradedMsg})
        </div>
      )}

      {/* View */}
      {mode === "classic" && legacyView}

      {mode === "flow" && (
        <CapitalFlowErrorBoundary
          fallback={legacyView}
          onError={(err) => fallbackToClassic(err?.message || "render_error")}
        >
          <Suspense fallback={legacyView}>
            <CapitalFlowAnimatedLayer onDegraded={fallbackToClassic} />
          </Suspense>
        </CapitalFlowErrorBoundary>
      )}
    </div>
  );
}
