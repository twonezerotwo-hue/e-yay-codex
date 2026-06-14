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
import { useEffect, useRef, useState } from "react";

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
  timeframe?:          "1d" | "7d" | "30d";
  timeframe_available?: boolean;
}

interface Props {
  onDegraded?: (reason: string) => void;
  /** Shell'deki [1D][7D][30D] toggle'ı. Endpoint'e ?timeframe=... olarak gider;
      backend aynı günlük serilerden pencere-bazlı momentum üretir. */
  timeframe?: "1d" | "7d" | "30d";
}

const TF_META: Record<NonNullable<Props["timeframe"]>, { title: string; short: string; speed: number }> = {
  "1d":  { title: "Günlük Göreli Momentum Rotasyonu",   short: "1g",  speed: 0.55 },
  "7d":  { title: "Haftalık Göreli Momentum Rotasyonu", short: "7g",  speed: 0.8 },
  "30d": { title: "30 Günlük Göreli Momentum Rotasyonu", short: "30g", speed: 1 },
};

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
    border: "border-slate-500/40",
    shadow: "shadow-[0_0_12px_rgba(148,163,184,0.16)]",
    text:   "text-slate-300",
    bar:    "bg-slate-400",
    line:   "#94a3b8",
    lineAnim: "cfal-dash",
  };
}

// Akış ikonu — çizgi üzerinde hareket eden varlık sembolü
function FlowIcon({ id }: { id: string }) {
  switch (id) {
    case "DXY": return <span className="text-[11px] font-mono font-black text-cyan-200">$</span>;
    case "GLD": return <span className="inline-block w-3 h-1.5 rounded-[2px]" style={{ background: "linear-gradient(180deg,#fde68a,#b45309)" }} />;
    case "XAG": return <span className="inline-block w-3 h-1.5 rounded-[2px]" style={{ background: "linear-gradient(180deg,#f1f5f9,#64748b)" }} />;
    case "TLT": return <span className="inline-block w-2.5 h-3 rounded-[2px] border border-indigo-300/80 bg-indigo-200/20 text-[10px] leading-3 text-center font-mono text-indigo-200">%</span>;
    case "BTC": return <span className="text-[11px] font-mono font-black text-purple-200">₿</span>;
    case "SPY": case "HYG": return (
      <span className="inline-flex items-end gap-px">
        <span className="inline-block w-1 h-2 bg-emerald-400 rounded-[1px]" />
        <span className="inline-block w-1 h-3 bg-red-400 rounded-[1px]" />
        <span className="inline-block w-1 h-1.5 bg-emerald-400 rounded-[1px]" />
      </span>
    );
    case "OIL": return <span className="text-[10px]">🛢</span>;
    default:    return <span className="inline-block w-1.5 h-1.5 rounded-full bg-slate-300/80" />;
  }
}

// Mini conviction ring (strength 0-1)
function MiniRing({ v, color }: { v: number; color: string }) {
  const r = 7, c = 2 * Math.PI * r;
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" className="shrink-0">
      <circle cx="9" cy="9" r={r} fill="none" stroke="rgba(148,163,184,0.25)" strokeWidth="2" />
      <circle cx="9" cy="9" r={r} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round"
              strokeDasharray={`${Math.max(0, Math.min(1, v)) * c} ${c}`}
              transform="rotate(-90 9 9)" />
    </svg>
  );
}

// NOT: Bu panel gerçek fon/ETF akışı değil; 30g fiyat momentumu + oran/korelasyon
// türevidir. Bu yüzden "GİRİŞ/ÇIKIŞ" yerine göreli güçlenme/zayıflama dili kullanılır.
const DIR_TR: Record<VisualNode["direction"], string> = {
  in: "GÜÇLENME", out: "ZAYIFLAMA", neutral: "NÖTR",
};

function fmtPct(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Asset kartı — glassmorphism + direction glow
// ─────────────────────────────────────────────────────────────────────────────

function AssetCard({ n, tf = "30g" }: { n: VisualNode; tf?: string }) {
  const ds   = dirStyle(n.direction);
  const meta = ASSET_META[n.id] ?? { icon: n.id.slice(0, 2), accent: "bg-slate-500/25 text-slate-200" };
  return (
    <div className={`rounded-xl border bg-white/[0.04] backdrop-blur-sm px-3 py-2 ${ds.border} ${ds.shadow}`}>
      <div className="flex items-center gap-2">
        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${meta.accent}`}>
          {meta.icon}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-mono font-bold text-eyay-dim leading-tight truncate">{n.label}</p>
          <p className="text-[10px] font-mono text-eyay-faint leading-tight">{n.id} · {tf}</p>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-[11px] font-mono font-semibold leading-tight ${ds.text}`}>{fmtPct(n.value_pct)}</p>
          <p className={`text-[10px] font-mono leading-tight ${ds.text}`}>{DIR_TR[n.direction]}</p>
        </div>
        <MiniRing v={n.strength} color={ds.line} />
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
      {/* küre — koyu holografik zemin */}
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: "radial-gradient(circle at 35% 30%, rgba(125,211,252,0.35) 0%, rgba(13,46,99,0.9) 48%, #060f24 85%)",
          boxShadow: "0 0 50px rgba(34,211,238,0.30), inset 0 0 36px rgba(34,211,238,0.18)",
        }}
      />
      {/* graticule + kıta konturları — yavaş hologram dönüşü */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full">
        <defs>
          <clipPath id="cfal-globe-clip"><circle cx="50" cy="50" r="48" /></clipPath>
        </defs>
        {/* meridyen/paralel */}
        <g opacity="0.4">
          <circle  cx="50" cy="50" r="48"          fill="none" stroke="#67e8f9" strokeWidth="0.6" />
          <ellipse cx="50" cy="50" rx="48" ry="18" fill="none" stroke="#67e8f9" strokeWidth="0.4" />
          <ellipse cx="50" cy="50" rx="48" ry="34" fill="none" stroke="#67e8f9" strokeWidth="0.4" />
          <ellipse cx="50" cy="50" rx="18" ry="48" fill="none" stroke="#67e8f9" strokeWidth="0.4" />
          <ellipse cx="50" cy="50" rx="34" ry="48" fill="none" stroke="#67e8f9" strokeWidth="0.4" />
          <line x1="2" y1="50" x2="98" y2="50" stroke="#67e8f9" strokeWidth="0.5" />
        </g>
        {/* basitleştirilmiş kıtalar — cam dolgu + cyan kontur */}
        <g clipPath="url(#cfal-globe-clip)"
           fill="rgba(103,232,249,0.13)" stroke="#7dd3fc" strokeWidth="0.55" strokeLinejoin="round"
           style={animate ? { animation: "cfal-spin 48s linear infinite", transformOrigin: "50% 50%" } : undefined}>
          {/* Kuzey Amerika */}
          <path d="M16 24 Q24 18 33 21 Q38 24 36 30 Q31 36 27 41 Q23 38 19 33 Q14 29 16 24 Z" />
          {/* Güney Amerika */}
          <path d="M30 48 Q35 45 38 50 Q39 57 35 64 Q31 68 29 62 Q27 54 30 48 Z" />
          {/* Avrupa */}
          <path d="M48 20 Q54 17 59 20 Q58 25 54 27 Q49 26 48 20 Z" />
          {/* Afrika */}
          <path d="M47 32 Q54 28 60 33 Q62 41 58 49 Q53 55 49 49 Q45 40 47 32 Z" />
          {/* Asya */}
          <path d="M62 18 Q74 15 83 22 Q86 30 80 36 Q72 40 65 35 Q60 26 62 18 Z" />
          {/* Avustralya */}
          <path d="M74 56 Q80 53 84 57 Q84 62 79 64 Q74 62 74 56 Z" />
        </g>
        {/* scan çizgisi */}
        {animate && (
          <line x1="2" y1="50" x2="98" y2="50" stroke="#22d3ee" strokeWidth="0.8" opacity="0.5"
                clipPath="url(#cfal-globe-clip)"
                style={{ animation: "cfal-scanline 5.5s ease-in-out infinite", transformOrigin: "50% 50%" }} />
        )}
      </svg>
      {/* merkez yazı */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-[10px] font-bold tracking-[0.2em] text-cyan-100 drop-shadow">CAPITAL</span>
        <span className="font-mono text-[10px] font-bold tracking-[0.2em] text-cyan-100 drop-shadow">FLOW</span>
        <span className="font-mono text-[10px] text-cyan-200/70 mt-1">
          {primaryFlow || "—"} · {conviction}/5
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function CapitalFlowAnimatedLayer({ onDegraded, timeframe = "30d" }: Props) {
  const tf = TF_META[timeframe] ?? TF_META["30d"];
  const [data, setData]       = useState<VisualPayload | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [tfUnavailable, setTfUnavailable] = useState<string | null>(null);
  const [reduced, setReduced] = useState<boolean>(false);
  const [isMobile, setMobile] = useState<boolean>(false);

  // onDegraded'ı ref'te tut → fetch effect yalnızca timeframe değişince yeniden koşsun
  const onDegradedRef = useRef(onDegraded);
  useEffect(() => { onDegradedRef.current = onDegraded; }, [onDegraded]);

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
    // Timeframe değişince net loading: eski veriyi temizle, hata/mesajı sıfırla.
    setLoading(true);
    setError(null);
    setTfUnavailable(null);
    setData(null);
    fetch(`/api/backend/capital-rotation/visual?timeframe=${timeframe}`, { signal: ctrl.signal, cache: "no-store" })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: VisualPayload) => {
        if (!alive) return;
        if (j.status === "degraded") {
          // Sağlayıcı tamamen erişilemez → Shell klasik görünüme döner.
          const reason = j.fallback_reason || "degraded";
          setError(reason);
          onDegradedRef.current?.(reason);
          return;
        }
        if (j.timeframe_available === false) {
          // Bu pencere için veri yok → klasik görünüme DÜŞME, inline mesaj göster.
          setTfUnavailable(j.fallback_reason || "insufficient_history");
          return;
        }
        setData(j);
      })
      .catch(e => {
        if (!alive) return;
        const reason = e?.name === "AbortError" ? "timeout" : (e?.message || "fetch_failed");
        setError(reason);
        onDegradedRef.current?.(reason);
      })
      .finally(() => { if (alive) setLoading(false); clearTimeout(timer); });
    return () => { alive = false; ctrl.abort(); clearTimeout(timer); };
  }, [timeframe]);

  // Sağlayıcı hatası → Shell zaten klasik görünüme döndü, burada bir şey çizme.
  if (error) return null;

  // Bu timeframe için veri hesaplanamadı → inline "veri yok" (akış modunda kal).
  if (tfUnavailable) {
    return (
      <TimeframeUnavailable label={tf.title} short={timeframe.toUpperCase()} reason={tfUnavailable} />
    );
  }

  // İlk yükleme veya timeframe değişimi → loading kutusu.
  if (loading || !data) {
    return <CapitalFlowLoading label={tf.title} />;
  }

  const byId: Record<string, VisualNode> = Object.fromEntries(data.nodes.map(n => [n.id, n]));
  const leftNodes   = LEFT_IDS.map(id => byId[id]).filter((n): n is VisualNode => !!n);
  const rightNodes  = RIGHT_IDS.map(id => byId[id]).filter((n): n is VisualNode => !!n);
  const bottomNodes = BOTTOM_IDS.map(id => byId[id]).filter((n): n is VisualNode => !!n);
  const animate = !reduced && !isMobile;

  // Üst metrikler
  const inCount  = data.nodes.filter(n => n.direction === "in").length;
  const outCount = data.nodes.filter(n => n.direction === "out").length;
  const netDir   = outCount > inCount ? "ZAYIFLAMA baskın" : inCount > outCount ? "GÜÇLENME baskın" : "DENGELİ";
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
      className="w-full max-w-full min-w-0 rounded-xl border border-eyay-border bg-eyay-surface/40 p-4 space-y-3 min-h-[420px] relative overflow-hidden"
      data-testid="capital-flow-animated"
      data-reduced-motion={reduced ? "true" : "false"}
      data-mobile={isMobile ? "true" : "false"}
    >
      <style>{`
        @keyframes cfal-dash     { to { stroke-dashoffset: -24; } }
        @keyframes cfal-dash-rev { to { stroke-dashoffset: 24; } }
        @keyframes cfal-spin     { to { transform: rotate(360deg); } }
        @keyframes cfal-pulse    { 0%,100% { opacity: .45; transform: scale(1); } 50% { opacity: 1; transform: scale(1.05); } }
        @keyframes cfal-scanline { 0%,100% { transform: translateY(-30px); } 50% { transform: translateY(30px); } }
        @keyframes cfal-travel {
          0%   { transform: translate(calc(var(--x0) * 1cqw - 50%), calc(var(--y0) * 1cqh - 50%)); opacity: 0; }
          12%  { opacity: 1; }
          88%  { opacity: 1; }
          100% { transform: translate(calc(var(--x1) * 1cqw - 50%), calc(var(--y1) * 1cqh - 50%)); opacity: 0; }
        }
      `}</style>

      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-eyay-border/40 pb-2">
        <div className="flex flex-col">
          <span
            className="text-[10px] font-mono text-eyay-dim uppercase tracking-widest cursor-help"
            title="Bu panel gerçek fon/ETF akışı değildir; fiyat momentumu, çapraz oran trendleri ve korelasyonlardan türetilmiş rotasyon proxy'sidir."
          >
            {tf.title}
          </span>
          <span className="text-[10px] font-mono text-eyay-faint">
            {data.nodes.length} varlık · {data.flows.length} akış · proxy · {data.execution_mode}
          </span>
        </div>
        {/* Metrikler */}
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <span className="rounded-md border border-eyay-border/50 bg-eyay-raised/40 px-2 py-0.5 text-[10px] font-mono text-eyay-dim">
            Aktif Akış: {data.flows.length}
          </span>
          <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono ${
            netDir === "ZAYIFLAMA baskın" ? "border-red-800/50 bg-red-950/20 text-red-300"
            : netDir === "GÜÇLENME baskın" ? "border-emerald-800/50 bg-emerald-950/20 text-emerald-300"
            : "border-amber-800/50 bg-amber-950/20 text-amber-200"
          }`}>
            Net Yön: {netDir}
          </span>
          {topFlow && (
            <span className="rounded-md border border-cyan-800/50 bg-cyan-950/20 px-2 py-0.5 text-[10px] font-mono text-cyan-200">
              En Güçlü: {topFlow.from}→{topFlow.to}
            </span>
          )}
          <span className="rounded-md border border-eyay-border/50 bg-eyay-raised/40 px-2 py-0.5 text-[10px] font-mono text-eyay-dim">
            Conviction: {data.conviction}/5
          </span>
        </div>
      </div>

      {/* ── Desktop: globe + yanlarda kartlar ── */}
      <div className="hidden sm:block relative h-[400px] [container-type:size]">
        {/* Neon flow çizgileri — kartların altında */}
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 w-full h-full pointer-events-none z-0"
        >
          {lineDefs.map(({ x, y, node }, i) => {
            const ds  = dirStyle(node.direction);
            const dur = Math.max(0.9, 3 - node.strength * 2.2) * tf.speed;
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

        {/* Akış ikonları — GİRİŞ: dünya→asset, ÇIKIŞ: asset→dünya, NÖTR: statik dot */}
        {lineDefs.map(({ x, y, node }, i) => {
          const midX = (x + CXp) / 2, midY = (y + CYp) / 2;
          if (node.direction === "neutral" || !animate) {
            return (
              <span key={`fi-${node.id}-${i}`} aria-hidden="true"
                    className="absolute left-0 top-0 z-[5] pointer-events-none opacity-40"
                    style={{ transform: `translate(${midX}cqw, ${midY}cqh) translate(-50%,-50%)` } as React.CSSProperties}>
                {node.direction === "neutral"
                  ? <span className="inline-block w-1.5 h-1.5 rounded-full bg-slate-400/70" />
                  : <FlowIcon id={node.id} />}
              </span>
            );
          }
          const from = node.direction === "in" ? { x: CXp, y: CYp } : { x, y };
          const to   = node.direction === "in" ? { x, y }           : { x: CXp, y: CYp };
          const dur  = Math.max(2.2, 5 - node.strength * 2.5) * tf.speed;
          return (
            <span key={`fi-${node.id}-${i}`} aria-hidden="true"
                  className="absolute left-0 top-0 z-[5] pointer-events-none drop-shadow-[0_0_4px_rgba(34,211,238,0.6)]"
                  style={{
                    "--x0": from.x, "--y0": from.y, "--x1": to.x, "--y1": to.y,
                    animation: `cfal-travel ${dur}s linear ${(i * 0.45).toFixed(2)}s infinite`,
                    opacity: 0,
                  } as React.CSSProperties}>
              <FlowIcon id={node.id} />
            </span>
          );
        })}

        {/* Sol kartlar — güvenli liman / dolar / metaller */}
        {leftNodes.map((n, i) => (
          <div
            key={n.id}
            className="absolute left-0 w-[27%] z-10"
            style={{ top: `${slotY(i, leftNodes.length)}%`, transform: "translateY(-50%)" }}
          >
            <AssetCard n={n} tf={tf.short} />
          </div>
        ))}

        {/* Sağ kartlar — tahvil / emtia / kripto */}
        {rightNodes.map((n, i) => (
          <div
            key={n.id}
            className="absolute right-0 w-[27%] z-10"
            style={{ top: `${slotY(i, rightNodes.length)}%`, transform: "translateY(-50%)" }}
          >
            <AssetCard n={n} tf={tf.short} />
          </div>
        ))}

        {/* Alt kart — ana giriş node'u */}
        {bottomNodes.map(n => (
          <div
            key={n.id}
            className="absolute left-1/2 w-[30%] z-10"
            style={{ top: "86%", transform: "translate(-50%,-50%)" }}
          >
            <AssetCard n={n} tf={tf.short} />
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
          {data.nodes.map(n => <AssetCard key={n.id} n={n} tf={tf.short} />)}
        </div>
      </div>

      {/* Flow listesi */}
      {data.flows.length > 0 && (
        <div className="pt-2 border-t border-eyay-border/40 space-y-1">
          <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">
            Göreli momentum akışları ({data.flows.length})
          </p>
          {data.flows.slice(0, 5).map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
              <span className="text-red-300/90 min-w-[36px]">{f.from}</span>
              <span className="text-eyay-faint">→</span>
              <span className="text-emerald-300 min-w-[60px]">{f.to}</span>
              <span className="text-eyay-faint/70 text-[10px] truncate flex-1">{f.reason}</span>
              <span className="text-eyay-dim text-[10px]">{Math.round(f.strength * 100)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <p className="text-[10px] font-mono text-eyay-faint/40 pt-1">
        Akış gücü 30 günlük referans getiriye göre normalize edilir. Görsel katman yalnızca sunum amaçlıdır.
        · {data.schema_version} · {data.execution_mode} · {data.decision_permission}
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Yükleniyor / veri yok durumları — mobil güvenli, panel çökmez
// ─────────────────────────────────────────────────────────────────────────────

function CapitalFlowLoading({ label }: { label: string }) {
  return (
    <div
      className="w-full max-w-full min-w-0 rounded-xl border border-eyay-border bg-eyay-surface/40 p-4 min-h-[200px] flex flex-col items-center justify-center gap-3"
      data-testid="capital-flow-loading"
    >
      <div className="w-8 h-8 rounded-full border-2 border-cyan-500/30 border-t-cyan-400 animate-spin" />
      <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest text-center">{label}</p>
      <p className="text-[10px] font-mono text-eyay-faint/70">akış verisi yükleniyor…</p>
    </div>
  );
}

function TimeframeUnavailable({ label, short, reason }: { label: string; short: string; reason: string }) {
  return (
    <div
      className="w-full max-w-full min-w-0 rounded-xl border border-amber-700/40 bg-amber-950/15 p-4 min-h-[160px] flex flex-col items-center justify-center gap-2 text-center"
      data-testid="capital-flow-tf-unavailable"
    >
      <span className="text-2xl" aria-hidden="true">📭</span>
      <p className="text-[11px] font-mono font-bold text-amber-200">
        {short} için veri yok / hesaplanamıyor
      </p>
      <p className="text-[10px] font-mono text-amber-300/70">{label}</p>
      <p className="text-[10px] font-mono text-eyay-faint/70">
        Başka bir zaman aralığı seçebilirsin · ({reason})
      </p>
    </div>
  );
}
