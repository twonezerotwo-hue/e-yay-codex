"use client";

/**
 * FAZ 15 — Breaking News Radar Layer (globe-centered event radar).
 *
 * Ortada "GLOBAL EVENT RADAR" dijital dünya; solda haber node'ları,
 * sağda etkilenen asset kartları, arada neon alarm hatları.
 *
 * Data source: GET /api/backend/breaking-news/visual
 * Karar üretmez. Trade etmez. Yalnızca sunum katmanı.
 * Fail/degraded → onDegraded ile Shell klasik listeye döner.
 */
import { useEffect, useState } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type Severity = "critical" | "high" | "medium" | "low";
type RiskLevel = "critical" | "high" | "medium" | "low";

interface NewsNode {
  id:              string;
  label:           string;
  category:        string;
  severity:        Severity;
  source:          string;
  headline:        string;
  affected_assets: string[];
  age_minutes:     number | null;
}

interface AssetImpact {
  asset:    string;
  impact:   "up" | "down";
  strength: number;
  reason:   string;
}

interface RadarLink {
  from:      string;
  to:        string;
  strength:  number;
  direction: "risk_up" | "risk_down";
}

interface RadarPayload {
  status:              "ok" | "degraded";
  schema_version:      string;
  decision_permission: string;
  execution_mode:      string;
  visual_mode:         string;
  risk_level:          RiskLevel;
  active_count:        number;
  nodes:               NewsNode[];
  asset_impacts:       AssetImpact[];
  links:               RadarLink[];
  fallback_reason:     string | null;
}

interface Props {
  onDegraded?: (reason: string) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Style maps
// ─────────────────────────────────────────────────────────────────────────────

const SEV_STYLE: Record<Severity, { badge: string; line: string; label: string }> = {
  critical: { badge: "bg-red-950/60 border-red-600/70 text-red-200",       line: "#f87171", label: "KRİTİK" },
  high:     { badge: "bg-orange-950/50 border-orange-600/60 text-orange-200", line: "#fb923c", label: "YÜKSEK" },
  medium:   { badge: "bg-amber-950/40 border-amber-600/50 text-amber-200", line: "#fbbf24", label: "ORTA" },
  low:      { badge: "bg-cyan-950/40 border-cyan-700/50 text-cyan-200",    line: "#22d3ee", label: "DÜŞÜK" },
};

// Kategori → çizgi rengi (spec: war kırmızı/turuncu, macro mavi/sarı,
// crypto mor/cyan, metals altın)
const CAT_LINE: Record<string, string> = {
  war: "#f87171", us_policy: "#fb923c", macro: "#60a5fa",
  energy: "#fb923c", crypto: "#c084fc", metals: "#fbbf24", risk_market: "#22d3ee",
};

const ASSET_META: Record<string, { icon: string; accent: string }> = {
  BRENT:  { icon: "🛢", accent: "bg-orange-600/25 text-orange-200" },
  GOLD:   { icon: "Au", accent: "bg-amber-500/25 text-amber-200" },
  SILVER: { icon: "Ag", accent: "bg-slate-400/25 text-slate-100" },
  BTC:    { icon: "₿",  accent: "bg-purple-500/25 text-purple-200" },
  DXY:    { icon: "$",  accent: "bg-cyan-500/25 text-cyan-200" },
  VIX:    { icon: "⚡", accent: "bg-red-500/25 text-red-200" },
  SPY:    { icon: "📊", accent: "bg-blue-500/25 text-blue-200" },
  HYG:    { icon: "HY", accent: "bg-rose-500/25 text-rose-200" },
};

const RISK_HALO: Record<RiskLevel, { glow: string; ring: string; pulse: string }> = {
  critical: { glow: "rgba(239,68,68,0.55)",  ring: "border-red-500/40",    pulse: "rgba(239,68,68,0.35)" },
  high:     { glow: "rgba(251,146,60,0.50)", ring: "border-orange-500/40", pulse: "rgba(251,146,60,0.30)" },
  medium:   { glow: "rgba(245,158,11,0.45)", ring: "border-amber-500/35",  pulse: "rgba(245,158,11,0.25)" },
  low:      { glow: "rgba(34,211,238,0.40)", ring: "border-cyan-500/35",   pulse: "rgba(34,211,238,0.22)" },
};

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function NewsCard({ n }: { n: NewsNode }) {
  const sv = SEV_STYLE[n.severity] ?? SEV_STYLE.low;
  return (
    <div className={`rounded-xl border bg-white/[0.04] backdrop-blur-sm px-3 py-2 ${sv.badge.split(" ")[1]} shadow-[0_0_16px_rgba(0,0,0,0.3)]`}>
      <div className="flex items-center gap-1.5 mb-1">
        <span className={`rounded px-1.5 py-0.5 text-[7px] font-mono font-black uppercase tracking-widest border ${sv.badge}`}>
          {sv.label}
        </span>
        <span className="text-[8px] font-mono text-eyay-faint truncate">{n.source}</span>
        {n.age_minutes !== null && (
          <span className="text-[8px] font-mono text-eyay-faint/60 ml-auto shrink-0">{n.age_minutes}dk</span>
        )}
      </div>
      <p className="text-[9px] text-eyay-dim leading-snug line-clamp-2">{n.headline}</p>
      <p className="text-[8px] font-mono text-eyay-faint/70 mt-0.5">{n.label}</p>
    </div>
  );
}

function AssetImpactCard({ a }: { a: AssetImpact }) {
  const meta = ASSET_META[a.asset] ?? { icon: a.asset.slice(0, 2), accent: "bg-slate-500/25 text-slate-200" };
  const up = a.impact === "up";
  return (
    <div className={`rounded-xl border bg-white/[0.04] backdrop-blur-sm px-3 py-2 ${
      up ? "border-red-500/40 shadow-[0_0_16px_rgba(239,68,68,0.20)]"
         : "border-cyan-700/40 shadow-[0_0_16px_rgba(34,211,238,0.15)]"
    }`}>
      <div className="flex items-center gap-2">
        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${meta.accent}`}>
          {meta.icon}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[9px] font-mono font-bold text-eyay-dim leading-tight">{a.asset}</p>
          <p className="text-[8px] font-mono text-eyay-faint leading-tight truncate">{a.reason}</p>
        </div>
        <span className={`text-[10px] font-mono font-semibold shrink-0 ${up ? "text-red-300" : "text-cyan-300"}`}>
          {up ? "↑ risk" : "↓ baskı"}
        </span>
      </div>
      <div className="mt-1.5 h-1 rounded bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded ${up ? "bg-red-400" : "bg-cyan-400"}`}
          style={{ width: `${Math.round(a.strength * 100)}%` }}
        />
      </div>
    </div>
  );
}

function RadarGlobe({ animate, riskLevel, activeCount, small }: {
  animate: boolean; riskLevel: RiskLevel; activeCount: number; small?: boolean;
}) {
  const halo = RISK_HALO[riskLevel] ?? RISK_HALO.low;
  const size = small ? "w-28 h-28" : "w-40 h-40";
  return (
    <div className={`relative ${size}`}>
      <div
        className={`absolute -inset-4 rounded-full border ${halo.ring}`}
        style={animate ? { animation: "bnr-pulse 2.4s ease-in-out infinite" } : undefined}
      />
      <div
        className={`absolute -inset-2 rounded-full border-2 border-dashed ${halo.ring}`}
        style={animate ? { animation: "bnr-spin 22s linear infinite" } : undefined}
      />
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: "radial-gradient(circle at 35% 30%, #7dd3fc 0%, #1d4ed8 45%, #0a1733 85%)",
          boxShadow: `0 0 56px ${halo.glow}, inset 0 0 36px ${halo.pulse}`,
        }}
      />
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full opacity-35">
        <circle  cx="50" cy="50" r="48"          fill="none" stroke="#a5f3fc" strokeWidth="0.6" />
        <ellipse cx="50" cy="50" rx="48" ry="18" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="48" ry="34" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="18" ry="48" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
        <ellipse cx="50" cy="50" rx="34" ry="48" fill="none" stroke="#a5f3fc" strokeWidth="0.5" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-[8px] font-bold tracking-[0.18em] text-cyan-100 drop-shadow">GLOBAL</span>
        <span className="font-mono text-[8px] font-bold tracking-[0.18em] text-cyan-100 drop-shadow">EVENT RADAR</span>
        <span className="font-mono text-[7px] text-cyan-200/70 mt-1">
          {activeCount} aktif · {riskLevel.toUpperCase()}
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function BreakingNewsRadarLayer({ onDegraded }: Props) {
  const [data, setData]       = useState<RadarPayload | null>(null);
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
    fetch("/api/backend/breaking-news/visual", { signal: ctrl.signal, cache: "no-store" })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: RadarPayload) => {
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

  const animate    = !reduced && !isMobile;
  const newsNodes  = data.nodes.slice(0, 4);
  const impacts    = data.asset_impacts.slice(0, 5);

  // Boş veri — crash etme, sade mesaj
  if (newsNodes.length === 0) {
    return (
      <div className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-5"
           data-testid="breaking-news-radar" data-reduced-motion={reduced ? "true" : "false"}>
        <p className="text-xs text-eyay-faint italic">Aktif son dakika haber kaydı yok.</p>
      </div>
    );
  }

  // Çizgi koordinatları (viewBox 0-100)
  const slotY = (i: number, n: number) => 8 + ((i + 0.5) / Math.max(n, 1)) * 76;
  const nodeIndex: Record<string, number> = Object.fromEntries(newsNodes.map((n, i) => [n.id, i]));
  const assetIndex: Record<string, number> = Object.fromEntries(impacts.map((a, i) => [a.asset, i]));
  const visibleLinks = data.links.filter(
    l => l.from in nodeIndex && l.to in assetIndex,
  ).slice(0, 14);

  return (
    <div
      className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-4 space-y-3 min-h-[420px] relative overflow-visible"
      data-testid="breaking-news-radar"
      data-reduced-motion={reduced ? "true" : "false"}
      data-mobile={isMobile ? "true" : "false"}
    >
      <style>{`
        @keyframes bnr-dash  { to { stroke-dashoffset: -24; } }
        @keyframes bnr-spin  { to { transform: rotate(360deg); } }
        @keyframes bnr-pulse { 0%,100% { opacity: .4; transform: scale(1); } 50% { opacity: 1; transform: scale(1.06); } }
      `}</style>

      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b border-eyay-border/40 pb-2">
        <div className="flex flex-col">
          <span className="text-[10px] font-mono text-eyay-dim uppercase tracking-widest">
            Son Dakika Haber Radarı
          </span>
          <span className="text-[9px] font-mono text-eyay-faint">
            {data.active_count} aktif haber · {data.execution_mode} · karar üretmez
          </span>
        </div>
        <span className={`rounded-md border px-2 py-0.5 text-[8px] font-mono uppercase ${
          (SEV_STYLE[data.risk_level as Severity] ?? SEV_STYLE.low).badge
        }`}>
          Risk: {data.risk_level}
        </span>
      </div>

      {/* ── Desktop: haberler | globe | assetler ── */}
      <div className="hidden sm:block relative h-[380px]">
        {/* Neon alarm hatları */}
        <svg viewBox="0 0 100 100" preserveAspectRatio="none"
             className="absolute inset-0 w-full h-full pointer-events-none z-0">
          {visibleLinks.map((l, i) => {
            const node = newsNodes[nodeIndex[l.from]];
            const yFrom = slotY(nodeIndex[l.from], newsNodes.length);
            const yTo   = slotY(assetIndex[l.to], impacts.length);
            const color = CAT_LINE[node.category] ?? "#22d3ee";
            const dur   = Math.max(1, 3 - l.strength * 2);
            return (
              <line
                key={`lnk-${i}`}
                x1={30} y1={yFrom} x2={70} y2={yTo}
                stroke={color}
                strokeWidth={0.8 + l.strength * 2.2}
                strokeDasharray="3 3"
                opacity={0.55}
                vectorEffect="non-scaling-stroke"
                style={animate ? { animation: `bnr-dash ${dur}s linear infinite` } : undefined}
              />
            );
          })}
        </svg>

        {/* Sol — haber node'ları */}
        {newsNodes.map((n, i) => (
          <div key={n.id} className="absolute left-0 w-[29%] z-10"
               style={{ top: `${slotY(i, newsNodes.length)}%`, transform: "translateY(-50%)" }}>
            <NewsCard n={n} />
          </div>
        ))}

        {/* Sağ — etkilenen asset kartları */}
        {impacts.map((a, i) => (
          <div key={a.asset} className="absolute right-0 w-[27%] z-10"
               style={{ top: `${slotY(i, impacts.length)}%`, transform: "translateY(-50%)" }}>
            <AssetImpactCard a={a} />
          </div>
        ))}

        {/* Globe — merkez */}
        <div className="absolute z-10" style={{ left: "50%", top: "46%", transform: "translate(-50%,-50%)" }}>
          <RadarGlobe animate={animate} riskLevel={data.risk_level} activeCount={data.active_count} />
        </div>
      </div>

      {/* ── Mobile: static-lite ── */}
      <div className="sm:hidden space-y-3">
        <div className="flex justify-center">
          <RadarGlobe animate={false} riskLevel={data.risk_level} activeCount={data.active_count} small />
        </div>
        <div className="space-y-2">
          {newsNodes.map(n => <NewsCard key={n.id} n={n} />)}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {impacts.map(a => <AssetImpactCard key={a.asset} a={a} />)}
        </div>
      </div>

      {/* Disclaimer */}
      <p className="text-[8px] font-mono text-eyay-faint/40 pt-1">
        Haber radarı yalnızca sunum amaçlıdır; trade kararı üretmez ve risk gate&apos;i etkilemez.
        · {data.schema_version} · {data.execution_mode} · {data.decision_permission}
      </p>
    </div>
  );
}
