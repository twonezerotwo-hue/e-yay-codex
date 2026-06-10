"use client";

/**
 * FAZ 14 — Capital Flow Animated Layer (globe-centered).
 *
 * Ortada parlak dijital dünya/globe; sermaye akışı merkez ile asset
 * kartları arasında neon çizgilerle gösterilir.
 *   Sol: güvenli liman / dolar / metaller (DXY, GLD, XAG)
 *   Sağ: tahvil / emtia / kripto (TLT, OIL, BTC, HYG)
 *   Alt: ana giriş node'u (SPY)
 *
 * Data source: GET /api/backend/capital-rotation/visual
 * Karar üretmez. Trade etmez. Yalnızca sunum katmanı.
 * Fail/degraded → onDegraded ile Shell klasik görünüme döner.
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
// Layout + style maps
// ─────────────────────────────────────────────────────────────────────────────

const LEFT_IDS   = ["DXY", "GLD", "XAG"];
const RIGHT_IDS  = ["TLT", "OIL", "BTC", "HYG"];
const BOTTOM_IDS = ["SPY"];

const ASSET_META: Record<string, { icon: string; accent: string }> = {
  DXY: { icon: "$",  accent: "bg-cyan-500/25 text-cyan-200" },
  GLD: { icon: "Au", accent: "bg-amber-500/25 text-amber-200" },
  XAG: { icon: "Ag", accent: "bg-slate-400/25 text-slate-100" },
  OIL: { icon: "🛢", accent: "bg-orange-600/25 text-orange-200" },
  BTC: { icon: "₿",  accent: "bg-purple-500/25 text-purple-200" },
  SPY: { icon: "📊", accent: "bg-blue-500/25 text-blue-200" },
  TLT: { icon: "🏛", accent: "bg-indigo-500/25 text-indigo-200" },
  HYG: { icon: "HY", accent: "bg-rose-500/25 text-rose-200" },
};

function dirStyle(d: VisualNode["direction"]): {
  border: string; shadow: string; text: string; bar: string; line: string; lineAnim: string;
} {
  if (d === "in")
    return {
      border: "border-emerald-400/50",
      shadow: "shadow-[0_0_22px_rgba(34,211,238,0.30)]",
      text:   "text-emerald-300",
      bar:    "bg-cyan-400",
      line:   "#22d3ee",
      lineAnim: "cfal-dash",
    };
  if (d === "out")
    return {
      border: "border-red-500/50",
      shadow: "shadow-[0_0_22px_rgba(239,68,68,0.30)]",
      text:   "text-red-300",
      bar:    "bg-red-400",
      line:   "#f87171",
      lineAnim: "cfal-dash-rev",
    };
  return {
    border: "border-amber-500/40",
    shadow: "shadow-[0_0_16px_rgba(245,158,11,0.22)]",
    text:   "text-amber-200",
    bar:    "bg-amber-400",
    line:   "#fbbf24",
    lineAnim: "cfal-dash",
  };
}

const DIR_TR: Record<VisualNode["direction"], string> = {
  in: "GİRİŞ", out: "ÇIKIŞ", neutral: "NÖTR",
};

function fmtPct(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Asset kartı — glassmorphism + direction glow
// ─────────────────────────────────────────────────────────────────────────────

function AssetCard({ n }: { n: VisualNode }) {
  const ds   = dirStyle(n.direction);
  const meta = ASSET_META[n.id] ?? { icon: n.id.slice(0, 2), accent: "bg-slate-500/25 text-slate-200" };
  return (
    <div className={`rounded-xl border bg-white/[0.04] backdrop-blur-sm px-3 py-2 ${ds.border} ${ds.shadow}`}>
      <div className="flex items-center gap-2">
        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${meta.accent}`}>
          {meta.icon}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[9px] font-mono font-bold text-eyay-dim leading-tight truncate">{n.label}</p>
          <p className="text-[8px] font-mono text-eyay-faint leading-tight">{n.id} · 30g</p>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-[11px] font-mono font-semibold leading-tight ${ds.text}`}>{fmtPct(n.value_pct)}</p>
          <p className={`text-[8px] font-mono leading-tight ${ds.text}`}>{DIR_TR[n.direction]}</p>
        </div>
      </div>
      <div className="mt-1.5 h-1 rounded bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded transition-all duration-700 ${ds.bar}`}
          style={{ width: `${Math.round(n.strength * 100)}%` }}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Globe — CSS radial gradient + grid overlay + halo
// ─────────────────────────────────────────────────────────────────────────────

function Globe({ animate, primaryFlow, conviction, small }: {
  animate: boolean; primaryFlow: string; conviction: number; small?: boolean;
}) {
  const size = small ? "w-28 h-28" : "w-44 h-44";
  return (
    <div className={`relative ${size}`}>
      {/* dış halo */}
      <div
        className="absolute -inset-4 rounded-full border border-cyan-400/20"
        style={animate ? { animation: "cfal-pulse 3.2s ease-in-out infinite" } : undefined}
      />
      {/* dönen dashed ring */}
      <div
        className="absolute -inset-2 rounded-full border-2 border-dashed border-cyan-400/25"
        style={animate ? { animation: "cfal-spin 26s linear infinite" } : undefined}
      />
      {/* küre */}
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: "radial-gradient(circle at 35% 30%, #7dd3fc 0%, #2563eb 45%, #0b1d40 85%)",
          boxShadow: "0 0 60px rgba(56,189,248,0.40), inset 0 0 40px rgba(125,211,252,0.22)",
        }}
      />
      {/* grid overlay */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full opacity-35">
        <circle  cx="50" cy="50" r="48"          fill="none" stroke="#a5f3fc" strokeWidth="0.6" />
        <ellipse cx="50" cy="50" rx="48" ry="18" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="48" ry="34" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="18" ry="48" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="34" ry="48" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
      </svg>
      {/* merkez yazı */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-[10px] font-bold tracking-[0.2em] text-cyan-100 drop-shadow">CAPITAL</span>
        <span className="font-mono text-[10px] font-bold tracking-[0.2em] text-cyan-100 drop-shadow">FLOW</span>
        <span className="font-mono text-[7px] text-cyan-200/70 mt-1">
          {primaryFlow || "—"} · {conviction}/5
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

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

  const byId: Record<string, VisualNode> = Object.fromEntries(data.nodes.map(n => [n.id, n]));
  const leftNodes   = LEFT_IDS.map(id => byId[id]).filter((n): n is VisualNode => !!n);
  const rightNodes  = RIGHT_IDS.map(id => byId[id]).filter((n): n is VisualNode => !!n);
  const bottomNodes = BOTTOM_IDS.map(id => byId[id]).filter((n): n is VisualNode => !!n);
  const animate = !reduced && !isMobile;

  // Üst metrikler
  const inCount  = data.nodes.filter(n => n.direction === "in").length;
  const outCount = data.nodes.filter(n => n.direction === "out").length;
  const netDir   = outCount > inCount ? "ÇIKIŞ baskın" : inCount > outCount ? "GİRİŞ baskın" : "DENGELİ";
  const topFlow  = data.flows.length > 0
    ? [...data.flows].sort((a, b) => b.strength - a.strength)[0]
    : null;

  // Desktop çizgi uç noktaları (viewBox 0-100, percent koordinat)
  const CXp = 50, CYp = 44;
  const slotY = (i: number, n: number) => 8 + ((i + 0.5) / Math.max(n, 1)) * 70;
  const lineDefs: { x: number; y: number; node: VisualNode }[] = [
    ...leftNodes.map((node, i)  => ({ x: 28, y: slotY(i, leftNodes.length),  node })),
    ...rightNodes.map((node, i) => ({ x: 72, y: slotY(i, rightNodes.length), node })),
    ...bottomNodes.map(node     => ({ x: 50, y: 86, node })),
  ];

  return (
    <div
      className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-4 space-y-3 min-h-[420px] relative overflow-visible"
      data-testid="capital-flow-animated"
      data-reduced-motion={reduced ? "true" : "false"}
      data-mobile={isMobile ? "true" : "false"}
    >
      <style>{`
        @keyframes cfal-dash     { to { stroke-dashoffset: -24; } }
        @keyframes cfal-dash-rev { to { stroke-dashoffset: 24; } }
        @keyframes cfal-spin     { to { transform: rotate(360deg); } }
        @keyframes cfal-pulse    { 0%,100% { opacity: .45; transform: scale(1); } 50% { opacity: 1; transform: scale(1.05); } }
      `}</style>

      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-eyay-border/40 pb-2">
        <div className="flex flex-col">
          <span className="text-[10px] font-mono text-eyay-dim uppercase tracking-widest">
            Animasyonlu Sermaye Akışı
          </span>
          <span className="text-[9px] font-mono text-eyay-faint">
            {data.nodes.length} varlık · {data.flows.length} akış · {data.execution_mode}
          </span>
        </div>
        {/* Metrikler */}
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <span className="rounded-md border border-eyay-border/50 bg-eyay-raised/40 px-2 py-0.5 text-[8px] font-mono text-eyay-dim">
            Aktif Akış: {data.flows.length}
          </span>
          <span className={`rounded-md border px-2 py-0.5 text-[8px] font-mono ${
            netDir === "ÇIKIŞ baskın" ? "border-red-800/50 bg-red-950/20 text-red-300"
            : netDir === "GİRİŞ baskın" ? "border-emerald-800/50 bg-emerald-950/20 text-emerald-300"
            : "border-amber-800/50 bg-amber-950/20 text-amber-200"
          }`}>
            Net Yön: {netDir}
          </span>
          {topFlow && (
            <span className="rounded-md border border-cyan-800/50 bg-cyan-950/20 px-2 py-0.5 text-[8px] font-mono text-cyan-200">
              En Güçlü: {topFlow.from}→{topFlow.to}
            </span>
          )}
          <span className="rounded-md border border-eyay-border/50 bg-eyay-raised/40 px-2 py-0.5 text-[8px] font-mono text-eyay-dim">
            Conviction: {data.conviction}/5
          </span>
        </div>
      </div>

      {/* ── Desktop: globe + yanlarda kartlar ── */}
      <div className="hidden sm:block relative h-[400px]">
        {/* Neon flow çizgileri — kartların altında */}
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 w-full h-full pointer-events-none z-0"
        >
          {lineDefs.map(({ x, y, node }, i) => {
            const ds  = dirStyle(node.direction);
            const dur = Math.max(0.9, 3 - node.strength * 2.2);
            return (
              <line
                key={`l-${node.id}-${i}`}
                x1={x} y1={y} x2={CXp} y2={CYp}
                stroke={ds.line}
                strokeWidth={1 + node.strength * 2.5}
                strokeDasharray="3 3"
                opacity={0.7}
                vectorEffect="non-scaling-stroke"
                style={animate ? { animation: `${ds.lineAnim} ${dur}s linear infinite` } : undefined}
              />
            );
          })}
        </svg>

        {/* Sol kartlar — güvenli liman / dolar / metaller */}
        {leftNodes.map((n, i) => (
          <div
            key={n.id}
            className="absolute left-0 w-[27%] z-10"
            style={{ top: `${slotY(i, leftNodes.length)}%`, transform: "translateY(-50%)" }}
          >
            <AssetCard n={n} />
          </div>
        ))}

        {/* Sağ kartlar — tahvil / emtia / kripto */}
        {rightNodes.map((n, i) => (
          <div
            key={n.id}
            className="absolute right-0 w-[27%] z-10"
            style={{ top: `${slotY(i, rightNodes.length)}%`, transform: "translateY(-50%)" }}
          >
            <AssetCard n={n} />
          </div>
        ))}

        {/* Alt kart — ana giriş node'u */}
        {bottomNodes.map(n => (
          <div
            key={n.id}
            className="absolute left-1/2 w-[30%] z-10"
            style={{ top: "86%", transform: "translate(-50%,-50%)" }}
          >
            <AssetCard n={n} />
          </div>
        ))}

        {/* Globe — merkez */}
        <div
          className="absolute z-10"
          style={{ left: "50%", top: `${CYp}%`, transform: "translate(-50%,-50%)" }}
        >
          <Globe animate={animate} primaryFlow={data.primary_flow} conviction={data.conviction} />
        </div>
      </div>

      {/* ── Mobile: hafif static görünüm ── */}
      <div className="sm:hidden space-y-3">
        <div className="flex justify-center">
          <Globe animate={false} primaryFlow={data.primary_flow} conviction={data.conviction} small />
        </div>
        <div className="grid grid-cols-2 gap-2">
          {data.nodes.map(n => <AssetCard key={n.id} n={n} />)}
        </div>
      </div>

      {/* Flow listesi */}
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

      {/* Disclaimer */}
      <p className="text-[8px] font-mono text-eyay-faint/40 pt-1">
        Akış gücü 30 günlük referans getiriye göre normalize edilir. Görsel katman yalnızca sunum amaçlıdır.
        · {data.schema_version} · {data.execution_mode} · {data.decision_permission}
      </p>
    </div>
  );
}
