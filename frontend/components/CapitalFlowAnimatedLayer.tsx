"use client";

/**
 * FAZ 14 — Capital Flow Animated (3D-feel) Layer.
 *
 * Hub-and-spoke SVG: merkez "Capital Flow" node, çevrede 7 asset node.
 * SVG animated path'ler out→merkez ve merkez→in için akar.
 *
 * Data source: GET /api/backend/capital-rotation/visual
 * Karar üretmez. Trade etmez. Auto tune etkilemez.
 */
import { useEffect, useState } from "react";

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

// Sabit yerleşim sırası — saat 12'den başlayıp saat yönünde
const ORBIT_ORDER = ["DXY", "TLT", "GLD", "XAG", "OIL", "BTC", "SPY", "HYG"];

function colorFor(d: VisualNode["direction"]): { stroke: string; fill: string; glow: string } {
  if (d === "in")  return { stroke: "#34d399", fill: "rgba(16,185,129,0.18)", glow: "rgba(16,185,129,0.55)" };
  if (d === "out") return { stroke: "#f87171", fill: "rgba(239,68,68,0.16)",  glow: "rgba(239,68,68,0.55)"  };
  return                  { stroke: "#fbbf24", fill: "rgba(245,158,11,0.14)", glow: "rgba(245,158,11,0.45)" };
}

export default function CapitalFlowAnimatedLayer({ onDegraded }: Props) {
  const [data, setData]       = useState<VisualPayload | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const [reduced, setReduced] = useState<boolean>(false);
  const [isMobile, setMobile] = useState<boolean>(false);

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

  useEffect(() => {
    let alive   = true;
    const ctrl  = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 6000);
    fetch("/api/backend/capital-rotation/visual", { signal: ctrl.signal, cache: "no-store" })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
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

  if (error || !data) return null;

  // Layout — merkez + yörünge
  const W = 640, H = 360, CX = W / 2, CY = H / 2;
  const R = isMobile ? 110 : 140;
  const ordered = ORBIT_ORDER
    .map(id => data.nodes.find(n => n.id === id))
    .filter((n): n is VisualNode => !!n);
  const N = ordered.length || 1;

  const positions: Record<string, { x: number; y: number }> = {};
  ordered.forEach((n, i) => {
    const angle = -Math.PI / 2 + (i / N) * 2 * Math.PI;
    positions[n.id] = { x: CX + R * Math.cos(angle), y: CY + R * Math.sin(angle) };
  });

  const animate = !reduced;

  return (
    <div
      className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-4 space-y-2 min-h-[420px] relative"
      data-testid="capital-flow-animated"
      data-reduced-motion={reduced ? "true" : "false"}
      data-mobile={isMobile ? "true" : "false"}
    >
      <div className="flex items-center justify-between border-b border-eyay-border/40 pb-2 mb-1">
        <div className="flex flex-col">
          <span className="text-[10px] font-mono text-eyay-dim uppercase tracking-widest">
            Animasyonlu Sermaye Akışı
          </span>
          <span className="text-[9px] font-mono text-eyay-faint">
            {data.nodes.length} varlık · {data.flows.length} akış · {data.execution_mode}
          </span>
        </div>
        <span className="text-[9px] font-mono text-eyay-faint">
          conviction {data.conviction}/5 · {data.primary_flow}
        </span>
      </div>

      {/* SVG hub-and-spoke */}
      <div className="relative w-full" style={{ minHeight: 360 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="absolute inset-0 w-full h-full"
          style={{ overflow: "visible" }}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <radialGradient id="hubGrad" cx="50%" cy="50%" r="50%">
              <stop offset="0%"  stopColor="rgba(59,130,246,0.55)" />
              <stop offset="60%" stopColor="rgba(59,130,246,0.18)" />
              <stop offset="100%" stopColor="rgba(59,130,246,0)" />
            </radialGradient>
            <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="b" />
              <feMerge>
                <feMergeNode in="b" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Flows — out node → merkez, merkez → primary in node */}
          {data.flows.map((f, i) => {
            const src = positions[f.from];
            if (!src) return null;
            const dst = positions[f.to] || { x: CX, y: CY };
            const strokeW = 1 + f.strength * 3;
            const dur = animate ? `${Math.max(2, 5 - f.strength * 3)}s` : undefined;
            return (
              <g key={`flow-${i}`}>
                {/* base line */}
                <line
                  x1={src.x} y1={src.y} x2={CX} y2={CY}
                  stroke="rgba(239,68,68,0.35)"
                  strokeWidth={strokeW}
                  strokeDasharray="6 6"
                >
                  {animate && (
                    <animate
                      attributeName="stroke-dashoffset"
                      from="24" to="0" dur={dur} repeatCount="indefinite"
                    />
                  )}
                </line>
                {/* center → dst */}
                {dst !== positions[f.from] && (
                  <line
                    x1={CX} y1={CY} x2={dst.x} y2={dst.y}
                    stroke="rgba(16,185,129,0.40)"
                    strokeWidth={strokeW}
                    strokeDasharray="6 6"
                  >
                    {animate && (
                      <animate
                        attributeName="stroke-dashoffset"
                        from="0" to="-24" dur={dur} repeatCount="indefinite"
                      />
                    )}
                  </line>
                )}
              </g>
            );
          })}

          {/* Hub */}
          <circle cx={CX} cy={CY} r={62} fill="url(#hubGrad)" />
          <circle cx={CX} cy={CY} r={42} fill="rgba(15,23,42,0.85)" stroke="rgba(96,165,250,0.6)" strokeWidth={2} filter="url(#softGlow)" />
          <text x={CX} y={CY - 6} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="#93c5fd" letterSpacing="1">
            CAPITAL
          </text>
          <text x={CX} y={CY + 6} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="#93c5fd" letterSpacing="1">
            FLOW
          </text>
          <text x={CX} y={CY + 20} textAnchor="middle" fontSize="8" fontFamily="monospace" fill="rgba(148,163,184,0.7)">
            {data.flows.length} akış
          </text>

          {/* Asset nodes — orbit */}
          {ordered.map(n => {
            const p = positions[n.id];
            const c = colorFor(n.direction);
            const r = 26 + n.strength * 8;
            return (
              <g key={n.id}>
                {/* halo / glow */}
                <circle
                  cx={p.x} cy={p.y} r={r + 6}
                  fill="none"
                  stroke={c.glow}
                  strokeWidth={1}
                  opacity={0.6}
                  filter="url(#softGlow)"
                >
                  {animate && n.direction !== "neutral" && (
                    <animate attributeName="r" values={`${r + 4};${r + 10};${r + 4}`} dur="2.4s" repeatCount="indefinite" />
                  )}
                </circle>
                {/* main */}
                <circle cx={p.x} cy={p.y} r={r} fill={c.fill} stroke={c.stroke} strokeWidth={1.5}>
                  <title>{`${n.label}: ${n.value_pct.toFixed(1)}% 30g`}</title>
                </circle>
                <text x={p.x} y={p.y - 3} textAnchor="middle" fontSize="10" fontFamily="monospace" fontWeight="bold" fill={c.stroke}>
                  {n.id}
                </text>
                <text x={p.x} y={p.y + 10} textAnchor="middle" fontSize="9" fontFamily="monospace" fill={c.stroke}>
                  {n.value_pct > 0 ? "+" : ""}{n.value_pct.toFixed(1)}%
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Flow list */}
      {data.flows.length > 0 && (
        <div className="pt-2 border-t border-eyay-border/40 space-y-1">
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">
            Para akışları ({data.flows.length})
          </p>
          {data.flows.slice(0, 5).map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
              <span className="text-red-300/90 min-w-[36px]">{f.from}</span>
              <span className="text-eyay-faint">→</span>
              <span className="text-emerald-300 min-w-[60px]">{f.to}</span>
              <span className="text-eyay-faint/70 text-[9px] truncate flex-1">{f.reason}</span>
              <span className="text-eyay-dim text-[9px]">{Math.round(f.strength * 100)}%</span>
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
