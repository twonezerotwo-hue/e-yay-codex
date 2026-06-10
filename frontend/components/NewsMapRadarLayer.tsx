"use client";

/**
 * FAZ 15 — News Map Radar Layer v2 (global intelligence map).
 *
 * Dünya haritası üzerinde haberleri gerçek coğrafi konumda gösterir.
 * Döngü: her haber 10 sn "featured" → seri bitince 10 sn "all-pulse"
 * (tüm noktalar senkron yanıp söner) → başa sarar.
 *
 * Data source : GET /api/backend/breaking-news/visual
 * Region logic: lib/newsRegionMap.ts (ayrı helper)
 * Karar üretmez. Sadece görselleştirme. PAPER_SAFE.
 * Fail/degraded/timeout → onDegraded → Shell klasik listeye döner.
 */
import { useEffect, useState } from "react";

import {
  classifyHeadlineRegion,
  geoForRegion,
  type GeoPoint,
} from "@/lib/newsRegionMap";

// ── Types ─────────────────────────────────────────────────────────────────────

type Severity  = "critical" | "high" | "medium" | "low";
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

interface RadarPayload {
  status:              "ok" | "degraded";
  decision_permission: string;
  execution_mode:      string;
  risk_level:          RiskLevel;
  active_count:        number;
  nodes:               NewsNode[];
  asset_impacts:       AssetImpact[];
  fallback_reason:     string | null;
}

interface Props {
  onDegraded?: (reason: string) => void;
}

type EnrichedNode = NewsNode & { geo: GeoPoint };

/** Döngü durumu: sequence (haber i featured) | all_pulse (toplu görünüm) */
type CyclePhase =
  | { mode: "sequence"; idx: number }
  | { mode: "all_pulse" };

const PHASE_MS = 10_000;

// ── Style maps ────────────────────────────────────────────────────────────────

const SEV: Record<Severity, { dot: string; badge: string; text: string; label: string }> = {
  critical: { dot: "#f87171", badge: "bg-red-950/60 border-red-600/70 text-red-200",         text: "text-red-300",    label: "KRİTİK" },
  high:     { dot: "#fb923c", badge: "bg-orange-950/50 border-orange-600/60 text-orange-200", text: "text-orange-300", label: "YÜKSEK" },
  medium:   { dot: "#fbbf24", badge: "bg-amber-950/40 border-amber-600/50 text-amber-200",   text: "text-amber-300",  label: "ORTA" },
  low:      { dot: "#22d3ee", badge: "bg-cyan-950/40 border-cyan-700/50 text-cyan-200",      text: "text-cyan-300",   label: "DÜŞÜK" },
};

const RISK_BADGE: Record<RiskLevel, string> = {
  critical: "bg-red-950/70 border-red-600/70 text-red-200",
  high:     "bg-orange-950/60 border-orange-500/60 text-orange-200",
  medium:   "bg-amber-950/50 border-amber-500/50 text-amber-200",
  low:      "bg-cyan-950/40 border-cyan-600/40 text-cyan-200",
};

const ASSET_META: Record<string, { icon: string; color: string }> = {
  BRENT:  { icon: "🛢", color: "text-orange-300" },
  GOLD:   { icon: "Au", color: "text-amber-300" },
  SILVER: { icon: "Ag", color: "text-slate-300" },
  BTC:    { icon: "₿",  color: "text-purple-300" },
  DXY:    { icon: "$",  color: "text-cyan-300" },
  VIX:    { icon: "⚡", color: "text-red-300" },
  SPY:    { icon: "📊", color: "text-blue-300" },
  HYG:    { icon: "HY", color: "text-rose-300" },
};

// ── World map silhouettes ─────────────────────────────────────────────────────
// 1000×500 equirectangular; gerçek kıyı noktalarından (lat/lon → x,y) türetildi.

const LANDMASS: string[] = [
  // Kuzey Amerika (Alaska–Kanada–ABD–Meksika–Panama)
  "M 42,83 L 67,53 L 130,46 L 194,50 L 240,58 L 264,69 L 300,80 L 333,97 L 347,114 L 322,122 L 306,133 L 296,152 L 282,168 L 275,181 L 258,176 L 236,169 L 231,189 L 258,192 L 267,217 L 281,228 L 270,222 L 247,206 L 224,200 L 208,197 L 196,186 L 189,172 L 174,158 L 161,147 L 156,131 L 153,117 L 138,103 L 125,89 L 94,87 L 64,92 Z",
  // Grönland
  "M 297,33 L 360,22 L 420,20 L 444,28 L 439,56 L 410,72 L 381,83 L 358,74 L 347,64 L 322,50 Z",
  // Güney Amerika
  "M 286,228 L 300,217 L 330,224 L 356,236 L 381,250 L 403,269 L 397,292 L 389,311 L 367,330 L 344,347 L 330,361 L 319,375 L 314,392 L 311,403 L 303,392 L 300,375 L 297,342 L 306,306 L 292,283 L 275,267 L 278,250 Z",
  // Afrika
  "M 483,153 L 506,144 L 528,147 L 553,153 L 583,164 L 592,167 L 608,183 L 625,203 L 642,219 L 631,239 L 614,256 L 611,269 L 603,286 L 597,306 L 583,328 L 569,344 L 556,347 L 542,333 L 533,300 L 530,283 L 533,267 L 525,239 L 506,228 L 483,222 L 464,211 L 453,208 L 456,192 L 464,178 L 472,164 Z",
  // Avrasya (Avrupa + Rusya + Asya + Arabistan + Hindistan + Güneydoğu Asya)
  "M 569,53 L 611,67 L 656,50 L 700,42 L 778,36 L 830,38 L 869,42 L 910,47 L 944,53 L 994,67 L 975,80 L 958,89 L 944,106 L 925,97 L 894,100 L 875,117 L 867,131 L 853,153 L 836,164 L 819,181 L 806,194 L 797,222 L 778,236 L 789,247 L 775,242 L 769,231 L 758,206 L 753,189 L 742,194 L 728,211 L 714,228 L 706,211 L 700,194 L 683,181 L 658,178 L 664,192 L 647,206 L 625,214 L 608,192 L 597,169 L 594,156 L 583,150 L 572,142 L 561,139 L 550,133 L 542,136 L 525,128 L 511,131 L 508,133 L 500,139 L 483,150 L 475,144 L 475,131 L 497,122 L 486,117 L 503,108 L 522,94 L 536,94 L 517,86 L 514,78 L 536,64 Z",
  // İngiltere
  "M 486,111 L 503,106 L 500,97 L 494,89 L 483,97 L 481,106 Z",
  // İzlanda
  "M 442,72 L 456,67 L 458,75 L 444,78 Z",
  // Japonya
  "M 861,161 L 875,156 L 886,147 L 893,131 L 897,125 L 890,138 L 880,153 L 867,164 Z",
  // Endonezya / Malay takımadaları
  "M 772,250 L 794,267 L 786,272 L 767,256 Z",
  "M 797,269 L 819,272 L 819,277 L 797,275 Z",
  "M 803,236 L 825,239 L 822,256 L 800,253 Z",
  "M 836,200 L 842,194 L 844,211 L 837,217 Z",
  "M 869,261 L 906,253 L 911,264 L 872,272 Z",
  // Avustralya
  "M 817,308 L 842,292 L 864,283 L 894,281 L 911,300 L 925,325 L 922,342 L 917,353 L 897,353 L 878,347 L 850,350 L 819,344 L 811,328 Z",
  // Yeni Zelanda
  "M 968,389 L 978,381 L 981,397 L 970,403 Z",
  // Madagaskar
  "M 625,294 L 633,283 L 636,303 L 628,311 Z",
];

// ── Sub-components ────────────────────────────────────────────────────────────

function WorldMap({
  nodes, phase, animate,
}: { nodes: EnrichedNode[]; phase: CyclePhase; animate: boolean }) {
  const allPulse  = phase.mode === "all_pulse";
  const activeIdx = phase.mode === "sequence" ? phase.idx : -1;

  return (
    <div className="relative w-full" style={{ paddingBottom: "50%" }}>
      {/* Radar sweep (HTML overlay — SVG transform birim sorunlarından kaçınır) */}
      {animate && (
        <div
          className="absolute top-0 bottom-0 pointer-events-none z-10"
          style={{
            width: "90px",
            background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.06), rgba(34,211,238,0.10))",
            animation: "bnm-scan 9s linear infinite",
          }}
        />
      )}
      <svg
        viewBox="0 0 1000 500"
        className="absolute inset-0 w-full h-full"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        style={animate ? { animation: "bnm-breathe 14s ease-in-out infinite" } : undefined}
      >
        <defs>
          <radialGradient id="bnm-bg" cx="50%" cy="46%" r="68%">
            <stop offset="0%"   stopColor="#0a1c34" />
            <stop offset="60%"  stopColor="#051226" />
            <stop offset="100%" stopColor="#020812" />
          </radialGradient>
          <filter id="bnm-landglow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="1.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Zemin */}
        <rect width="1000" height="500" fill="url(#bnm-bg)" />

        {/* Grid */}
        {Array.from({ length: 17 }, (_, i) => (
          <line key={`v${i}`} x1={(i + 1) * 55.5} y1="0" x2={(i + 1) * 55.5} y2="500"
            stroke="#13335c" strokeWidth="0.4" opacity="0.5" />
        ))}
        {Array.from({ length: 8 }, (_, i) => (
          <line key={`h${i}`} x1="0" y1={(i + 1) * 55.5} x2="1000" y2={(i + 1) * 55.5}
            stroke="#13335c" strokeWidth="0.4" opacity="0.5" />
        ))}
        <line x1="0" y1="250" x2="1000" y2="250" stroke="#22d3ee" strokeWidth="0.6" opacity="0.18" />

        {/* Kıtalar */}
        <g filter="url(#bnm-landglow)">
          {LANDMASS.map((d, i) => (
            <path key={i} d={d}
              fill="#0e2a4e" stroke="#2563a8" strokeWidth="1"
              strokeLinejoin="round" opacity="0.92" />
          ))}
        </g>

        {/* All-pulse modunda aktivite ağı */}
        {allPulse && nodes.length > 1 && (
          <g opacity="0.35">
            {nodes.slice(0, -1).map((n, i) => {
              const next = nodes[i + 1];
              return (
                <line key={`net${i}`}
                  x1={n.geo.x} y1={n.geo.y} x2={next.geo.x} y2={next.geo.y}
                  stroke="#22d3ee" strokeWidth="0.8" strokeDasharray="3 5"
                  style={animate ? { animation: "bnm-dash 2.4s linear infinite" } : undefined}
                />
              );
            })}
          </g>
        )}

        {/* Haber noktaları */}
        {nodes.map((node, i) => {
          const { x, y, region } = node.geo;
          const sv       = SEV[node.severity] ?? SEV.low;
          const isActive = allPulse || i === activeIdx;
          const strong   = !allPulse && i === activeIdx;
          return (
            <g key={node.id} transform={`translate(${x},${y})`}
               style={{ transition: "opacity 0.6s ease" }} opacity={isActive ? 1 : 0.45}>
              {/* Dış pulse halkası */}
              {animate && isActive && (
                <circle r={strong ? 26 : 18} fill="none" stroke={sv.dot} strokeWidth="1"
                  opacity="0.30"
                  style={{ animation: `bnm-pulse ${allPulse ? "1.6s" : "2s"} ease-in-out infinite` }}
                />
              )}
              {/* Concentric ring (yalnızca featured) */}
              {animate && strong && (
                <circle r="15" fill="none" stroke={sv.dot} strokeWidth="0.8" opacity="0.45"
                  style={{ animation: "bnm-pulse 2s ease-in-out infinite", animationDelay: "0.6s" }}
                />
              )}
              <circle r={strong ? 9 : 5.5} fill="none" stroke={sv.dot}
                strokeWidth={strong ? 1.5 : 1} opacity="0.8" />
              <circle r={strong ? 5 : 3} fill={sv.dot}
                style={{ filter: `drop-shadow(0 0 ${strong ? 10 : 5}px ${sv.dot})` }}
              />
              {strong && (
                <text x="0" y="-19" textAnchor="middle" fontSize="9"
                  fill="#a5f3fc" fontFamily="monospace" fontWeight="700" letterSpacing="0.12em">
                  {region.toUpperCase()}
                </text>
              )}
            </g>
          );
        })}

        <rect width="1000" height="500" fill="none" stroke="#22d3ee" strokeWidth="1" opacity="0.10" />
      </svg>
    </div>
  );
}

function SideNewsCard({
  node, active, dimmed, onClick,
}: { node: EnrichedNode; active: boolean; dimmed: boolean; onClick: () => void }) {
  const sv = SEV[node.severity] ?? SEV.low;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left rounded-xl px-3 py-2.5 border transition-all duration-500 ${
        active
          ? `${sv.badge} shadow-[0_0_18px_rgba(0,0,0,0.45)] scale-[1.02]`
          : dimmed
            ? "bg-white/[0.02] border-eyay-border/30 opacity-60"
            : "bg-white/[0.03] border-eyay-border/40 hover:border-eyay-border/70"
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className={`rounded px-1 py-0.5 text-[7px] font-mono font-black uppercase tracking-widest border ${sv.badge}`}>
          {sv.label}
        </span>
        <span className="text-[8px] font-mono text-eyay-faint truncate max-w-[90px]">{node.source}</span>
        {node.age_minutes !== null && (
          <span className="text-[8px] font-mono text-eyay-faint/60 ml-auto shrink-0">{node.age_minutes}dk</span>
        )}
      </div>
      <p className="text-[9px] text-eyay-dim leading-snug line-clamp-2">{node.headline}</p>
      <p className="text-[8px] font-mono text-eyay-faint/70 mt-0.5">📍 {node.geo.region} · {node.category}</p>
    </button>
  );
}

function AssetCard({ a }: { a: AssetImpact }) {
  const meta = ASSET_META[a.asset] ?? { icon: a.asset.slice(0, 2), color: "text-slate-300" };
  const up   = a.impact === "up";
  return (
    <div className={`rounded-xl border px-3 py-2 bg-white/[0.04] backdrop-blur-sm ${
      up ? "border-red-600/40" : "border-cyan-700/40"
    }`}>
      <div className="flex items-center gap-2">
        <span className={`text-sm font-bold shrink-0 ${meta.color}`}>{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-[9px] font-mono font-bold text-eyay-dim">{a.asset}</p>
          <p className="text-[8px] font-mono text-eyay-faint truncate">{a.reason}</p>
        </div>
        <span className={`text-[10px] font-mono font-semibold shrink-0 ${up ? "text-red-300" : "text-cyan-300"}`}>
          {up ? "↑ risk" : "↓ baskı"}
        </span>
      </div>
      <div className="mt-1 h-1 rounded bg-white/10 overflow-hidden">
        <div className={`h-full rounded ${up ? "bg-red-400" : "bg-cyan-400"}`}
          style={{ width: `${Math.round(a.strength * 100)}%` }}
        />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function NewsMapRadarLayer({ onDegraded }: Props) {
  const [data,    setData]    = useState<RadarPayload | null>(null);
  const [error,   setError]   = useState<string | null>(null);
  const [phase,   setPhase]   = useState<CyclePhase>({ mode: "sequence", idx: 0 });
  const [animate, setAnimate] = useState(false);
  const [isMobile, setMobile] = useState(false);

  // Motion + mobile detection (client-only)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    setMobile(window.innerWidth < 640);
    const onResize = () => setMobile(window.innerWidth < 640);
    window.addEventListener("resize", onResize);
    return () => {
      mq.removeEventListener?.("change", onMQ);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  // Data fetch (6 s timeout)
  useEffect(() => {
    let alive = true;
    const ctrl  = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 6000);
    fetch("/api/backend/breaking-news/visual", { signal: ctrl.signal, cache: "no-store" })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: RadarPayload) => {
        if (!alive) return;
        // "degraded" (örn. no_news_data) bir hata değil, sadece veri yok demek —
        // radar'da kal, boş durum göster. Liste fallback'i sadece gerçek
        // fetch/render hatalarında (catch bloğu) tetiklenir.
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

  const nodeCount = Math.min(data?.nodes?.length ?? 0, 6);

  // Döngü makinesi: her faz 10 sn.
  // sequence i → sequence i+1 → ... → sequence n-1 → all_pulse → sequence 0
  // Manuel kart tıklaması phase'i değiştirir; bu effect yeniden kurulur → timer sıfırlanır.
  useEffect(() => {
    if (nodeCount === 0) return;
    const t = setTimeout(() => {
      setPhase(p => {
        if (p.mode === "all_pulse")    return { mode: "sequence", idx: 0 };
        if (p.idx >= nodeCount - 1)    return nodeCount > 1 ? { mode: "all_pulse" } : { mode: "sequence", idx: 0 };
        return { mode: "sequence", idx: p.idx + 1 };
      });
    }, PHASE_MS);
    return () => clearTimeout(t);
  }, [phase, nodeCount]);

  if (error || !data) return null;

  const enriched: EnrichedNode[] = data.nodes.slice(0, 6).map(n => ({
    ...n,
    geo: geoForRegion(classifyHeadlineRegion(`${n.headline} ${n.label}`, n.category)),
  }));

  if (enriched.length === 0) {
    return (
      <div className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-5"
           data-testid="news-map-radar">
        <p className="text-xs text-eyay-faint italic">Aktif son dakika haber kaydı yok.</p>
      </div>
    );
  }

  const allPulse   = phase.mode === "all_pulse";
  const safeIdx    = phase.mode === "sequence" ? phase.idx % enriched.length : 0;
  const activeNode = enriched[safeIdx];
  const impacts    = data.asset_impacts.slice(0, 5);
  const sv         = SEV[activeNode.severity]   ?? SEV.low;
  const riskBadge  = RISK_BADGE[data.risk_level] ?? RISK_BADGE.low;

  return (
    <div
      className="rounded-2xl border border-eyay-border bg-[#030e1c] overflow-hidden"
      data-testid="news-map-radar"
      data-cycle-mode={phase.mode}
      data-reduced-motion={!animate ? "true" : "false"}
    >
      <style>{`
        @keyframes bnm-pulse   { 0%,100%{opacity:.28;transform:scale(1)} 50%{opacity:.70;transform:scale(1.45)} }
        @keyframes bnm-scan    { from{left:-90px} to{left:100%} }
        @keyframes bnm-dash    { to{stroke-dashoffset:-16} }
        @keyframes bnm-breathe { 0%,100%{transform:scale(1)} 50%{transform:scale(1.012)} }
        @keyframes bnm-fadein  { from{opacity:0;transform:translateY(3px)} to{opacity:1;transform:none} }
      `}</style>

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-eyay-border/40 bg-black/30">
        <div>
          <p className="text-[11px] font-mono font-bold text-eyay-dim uppercase tracking-widest">
            Son Dakika Haber Radarı
          </p>
          <p className="text-[9px] font-mono text-eyay-faint mt-0.5">
            {data.active_count} aktif haber · {data.execution_mode} · sadece görselleştirme
          </p>
        </div>
        <div className="flex items-center gap-2">
          {allPulse && (
            <span className="text-[8px] font-mono text-cyan-300/80 uppercase tracking-widest"
                  style={animate ? { animation: "bnm-fadein 0.6s ease" } : undefined}>
              ◉ Global görünüm
            </span>
          )}
          <span className={`rounded-md border px-2 py-0.5 text-[8px] font-mono uppercase tracking-widest ${riskBadge}`}>
            Risk: {data.risk_level}
          </span>
        </div>
      </div>

      {/* ── Desktop layout ── */}
      {!isMobile && (
        <div className="grid grid-cols-[190px_1fr_175px] min-h-[320px]">

          {/* SOL: haber kartları */}
          <div className="border-r border-eyay-border/25 p-3 flex flex-col gap-2 bg-black/20 overflow-y-auto max-h-[460px]">
            <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest shrink-0">
              Haberler · {enriched.length}
            </p>
            {enriched.map((n, i) => (
              <SideNewsCard
                key={n.id} node={n}
                active={!allPulse && i === safeIdx}
                dimmed={allPulse}
                onClick={() => setPhase({ mode: "sequence", idx: i })}
              />
            ))}
          </div>

          {/* ORTA: harita + aktif bilgi şeridi */}
          <div className="flex flex-col bg-[#020a16]">
            <div className="flex-1 relative">
              <WorldMap nodes={enriched} phase={phase} animate={animate} />
            </div>
            <div className="px-4 py-2 border-t border-eyay-border/20 bg-black/40 text-center"
                 key={allPulse ? "all" : activeNode.id}
                 style={animate ? { animation: "bnm-fadein 0.5s ease" } : undefined}>
              {allPulse ? (
                <p className="text-[9px] font-mono text-cyan-300/90">
                  ◉ GLOBAL RİSK GÖRÜNÜMÜ · {enriched.length} aktif bölge
                </p>
              ) : (
                <>
                  <p className="text-[9px] font-mono">
                    <span className={`font-bold ${sv.text}`}>● {activeNode.geo.region}</span>
                    <span className="text-eyay-faint"> · {activeNode.source}</span>
                  </p>
                  <p className="text-[8px] text-eyay-faint/70 truncate mt-0.5 max-w-[420px] mx-auto">
                    {activeNode.headline.slice(0, 95)}{activeNode.headline.length > 95 ? "…" : ""}
                  </p>
                </>
              )}
            </div>
          </div>

          {/* SAĞ: etkilenen varlıklar */}
          <div className="border-l border-eyay-border/25 p-3 flex flex-col gap-2 bg-black/20">
            <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest shrink-0">
              Etkilenen Varlıklar
            </p>
            {impacts.map((a, i) => <AssetCard key={i} a={a} />)}
          </div>
        </div>
      )}

      {/* ── Mobile layout (static-lite) ── */}
      {isMobile && (
        <div className="space-y-3 p-3 bg-[#020a16]">
          <WorldMap nodes={enriched} phase={phase} animate={false} />
          <div className={`rounded-xl border p-3 ${sv.badge}`}>
            <p className="text-[8px] font-mono mb-0.5">
              {activeNode.source} · 📍 {activeNode.geo.region}
            </p>
            <p className="text-[10px] text-eyay-dim leading-snug">{activeNode.headline}</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {impacts.slice(0, 4).map((a, i) => <AssetCard key={i} a={a} />)}
          </div>
          <div className="flex gap-2 flex-wrap justify-center">
            {enriched.map((n, i) => (
              <button
                key={n.id} type="button"
                onClick={() => setPhase({ mode: "sequence", idx: i })}
                aria-label={n.geo.region}
                className={`w-2.5 h-2.5 rounded-full transition-all ${
                  !allPulse && i === safeIdx ? "ring-1 ring-white/60 scale-125" : "opacity-50"
                }`}
                style={{ background: (SEV[n.severity] ?? SEV.low).dot }}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Footer ── */}
      <div className="px-4 py-2 border-t border-eyay-border/30 bg-black/30">
        <p className="text-[8px] font-mono text-eyay-faint/55 text-center">
          Bu katman yalnızca haber akışının görsel sunumudur · işlem kararı üretmez · Veri alınamazsa klasik liste görünümüne dönülür
        </p>
      </div>
    </div>
  );
}
