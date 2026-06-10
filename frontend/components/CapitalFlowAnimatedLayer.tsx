"use client";

/**
 * FAZ 14 — Capital Flow Animated (3D-feel) Layer.
 *
 * Mevcut CapitalFlowWidget bozulmaz. Bu komponent ayrı bir visual layer'dır
 * ve crash ederse Shell legacy görünüme döner.
 *
 * Data source: GET /api/backend/capital-rotation/visual
 *   → CapitalRotationVisualAdapter
 *
 * Karar üretmez. Trade etmez. Auto tune etkilemez.
 */
import { useEffect, useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface VisualNode {
  id:          string;
  label:       string;
  asset_class: string;
  value_pct:   number;
  direction:   "in" | "out" | "neutral";
  strength:    number;
}

interface VisualFlow {
  from:     string;
  to:       string;
  strength: number;
  reason:   string;
}

interface VisualPayload {
  status:              "ok" | "degraded";
  schema_version:      string;
  source:              string;
  decision_permission: string;
  execution_mode:      string;
  visual_mode:         string;
  conviction:          number;
  primary_flow:        string;
  nodes:               VisualNode[];
  flows:               VisualFlow[];
  fallback_reason:     string | null;
}

interface Props {
  onDegraded?: (reason: string) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Style helpers
// ─────────────────────────────────────────────────────────────────────────────

const NODE_ORDER: string[] = ["DXY", "TLT", "GLD", "XAG", "OIL", "BTC", "SPY", "HYG"];

function nodeGlow(d: VisualNode["direction"]): string {
  if (d === "in")  return "border-emerald-500/70 bg-emerald-950/40 text-emerald-300 shadow-[0_0_24px_rgba(16,185,129,0.35)]";
  if (d === "out") return "border-red-700/60 bg-red-950/30 text-red-300 shadow-[0_0_24px_rgba(239,68,68,0.30)]";
  return "border-amber-700/40 bg-amber-950/20 text-amber-200/80 shadow-[0_0_18px_rgba(245,158,11,0.20)]";
}

function flowGradient(strength: number): string {
  // 0 → soluk, 1 → parlak
  const opacity = Math.max(0.25, Math.min(1, strength));
  return `linear-gradient(90deg, rgba(239,68,68,${opacity}) 0%, rgba(245,158,11,${opacity * 0.8}) 50%, rgba(16,185,129,${opacity}) 100%)`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function CapitalFlowAnimatedLayer({ onDegraded }: Props) {
  const [data, setData]       = useState<VisualPayload | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const [reduced, setReduced] = useState<boolean>(false);
  const [isMobile, setMobile] = useState<boolean>(false);

  // Reduced motion + mobile detection
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener?.("change", onChange);

    setMobile(window.innerWidth < 640);
    const onResize = () => setMobile(window.innerWidth < 640);
    window.addEventListener("resize", onResize);

    return () => {
      mq.removeEventListener?.("change", onChange);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  // Fetch
  useEffect(() => {
    let alive    = true;
    const ctrl   = new AbortController();
    const timer  = setTimeout(() => ctrl.abort(), 6000);

    const url = "/api/backend/capital-rotation/visual";
    fetch(url, { signal: ctrl.signal, cache: "no-store" })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((j: VisualPayload) => {
        if (!alive) return;
        if (j.status === "degraded") {
          const reason = j.fallback_reason || "degraded";
          setError(reason);
          onDegraded?.(reason);
          return;
        }
        setData(j);
      })
      .catch(e => {
        if (!alive) return;
        const reason = e?.name === "AbortError" ? "timeout" : (e?.message || "fetch_failed");
        setError(reason);
        onDegraded?.(reason);
      })
      .finally(() => clearTimeout(timer));

    return () => { alive = false; ctrl.abort(); clearTimeout(timer); };
  }, [onDegraded]);

  if (error || !data) {
    // ErrorBoundary fallback aktive olmayacak — sadece null döner; shell uyarıyı gösterir
    return null;
  }

  const sortedNodes = [...data.nodes].sort(
    (a, b) => NODE_ORDER.indexOf(a.id) - NODE_ORDER.indexOf(b.id),
  );

  const animatedClass = reduced || isMobile ? "" : "animate-pulse-slow";

  return (
    <div
      className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-4 space-y-3"
      data-testid="capital-flow-animated"
      data-reduced-motion={reduced ? "true" : "false"}
      data-mobile={isMobile ? "true" : "false"}
    >
      <div className="flex items-center justify-between">
        <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">
          🌐 Akış görünümü · {data.primary_flow || "—"}
        </p>
        <span className="text-[9px] font-mono text-eyay-faint/60">
          conviction {data.conviction}/5
        </span>
      </div>

      {/* Node grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {sortedNodes.map(n => (
          <div
            key={n.id}
            className={`rounded-xl border px-3 py-2 transition-all duration-500 ${nodeGlow(n.direction)} ${n.direction !== "neutral" ? animatedClass : ""}`}
            title={`${n.label}: ${n.value_pct.toFixed(1)}% 30g momentum`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] font-bold">{n.label}</span>
              <span className={`w-1.5 h-1.5 rounded-full ${
                n.direction === "in"  ? "bg-emerald-400" :
                n.direction === "out" ? "bg-red-400"     : "bg-amber-400"
              }`} />
            </div>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="font-mono text-[9px] opacity-70">{n.id}</span>
              <span className="font-mono text-[11px] font-semibold">
                {n.value_pct > 0 ? "+" : ""}{n.value_pct.toFixed(1)}%
              </span>
            </div>
            {/* Strength bar */}
            <div className="mt-1.5 h-0.5 w-full rounded bg-eyay-border/30">
              <div
                className={`h-full rounded transition-all duration-700 ${
                  n.direction === "in"  ? "bg-emerald-400" :
                  n.direction === "out" ? "bg-red-400"     : "bg-amber-400"
                }`}
                style={{ width: `${Math.round(n.strength * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Flows */}
      {data.flows.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-eyay-border/40">
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">
            Para akışları
          </p>
          {data.flows.slice(0, 4).map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
              <span className="text-red-300/80 min-w-[40px]">{f.from}</span>
              <div
                className="flex-1 h-[3px] rounded"
                style={{ background: flowGradient(f.strength) }}
              />
              <span className="text-emerald-300 min-w-[60px] text-right">{f.to}</span>
              <span className="text-eyay-faint/70 text-[9px] hidden sm:inline ml-1 truncate max-w-[180px]">
                {f.reason}
              </span>
            </div>
          ))}
        </div>
      )}

      <p className="text-[8px] font-mono text-eyay-faint/40 pt-1">
        {data.schema_version} · {data.execution_mode} · {data.decision_permission}
      </p>
    </div>
  );
}
