"use client";

/**
 * FAZ 15 — News Map Radar Layer v3.
 *
 * Veri kaynağı: parent'tan gelen `headlines` prop (NewsPanelShell).
 * Liste ve Radar aynı veri setini kullanır — ayrı fetch yok.
 *
 * Döngü: her haber 10 sn featured → seri bitince 10 sn all-pulse → başa.
 * Aktif nokta yanında floating ticker (bölge · kaynak · başlık).
 * Karar üretmez. PAPER_SAFE. Fail/degraded → onDegraded → Shell listeye döner.
 */
import { useEffect, useState } from "react";

import {
  classifyHeadlineRegion,
  geoForRegion,
  type GeoPoint,
} from "@/lib/newsRegionMap";
import { WORLD_LAND_PATHS } from "@/lib/worldMapPath";
import type { NewsHeadline } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

type Severity = "critical" | "high" | "medium" | "low";

interface EnrichedNode {
  id:       string;
  headline: string;
  source:   string;
  severity: Severity;
  category: string;
  age_min:  number | null;
  assets:   { asset: string; up: boolean; note: string }[];
  geo:      GeoPoint;
  actor:    { name: string; short: string; img?: string } | null;
}

// Tanıdık aktör tespiti — headline metninden deterministik; fotoğraf uydurmaz.
const KNOWN_ACTORS: { re: RegExp; name: string; short: string }[] = [
  { re: /\btrump\b/i,                       name: "Trump",   short: "DT" },
  { re: /\bpowell\b/i,                      name: "Powell",  short: "JP" },
  { re: /\bfed\b|federal reserve|fomc/i,    name: "Fed",     short: "FED" },
  { re: /\becb\b|avrupa merkez|lagarde/i,   name: "ECB",     short: "ECB" },
  { re: /\bopec\b/i,                        name: "OPEC",    short: "OPC" },
  { re: /\bputin\b/i,                       name: "Putin",   short: "VP" },
  { re: /\bxi\b|jinping/i,                  name: "Xi",      short: "XI" },
  { re: /\bboj\b|bank of japan|ueda/i,      name: "BoJ",     short: "BOJ" },
  { re: /\bbiden\b/i,                       name: "Biden",   short: "JB" },
  { re: /\bnetanyahu\b/i,                   name: "Netanyahu", short: "BN" },
  { re: /\berdoğan\b|\berdogan\b/i,         name: "Erdoğan", short: "RTE" },
];

function detectActor(h: NewsHeadline, text: string): EnrichedNode["actor"] {
  // Veride güvenli speaker/author/thumbnail alanı varsa onu kullan
  const x = h as NewsHeadline & { speaker?: string; author?: string; thumbnail?: string };
  const explicit = x.speaker || x.author;
  if (explicit) {
    return { name: explicit, short: explicit.slice(0, 3).toUpperCase(), img: x.thumbnail };
  }
  for (const a of KNOWN_ACTORS) if (a.re.test(text)) return { name: a.name, short: a.short };
  return null;
}

type CyclePhase =
  | { mode: "sequence"; idx: number }
  | { mode: "all_pulse" };

const PHASE_MS = 10_000;

// ── Conversion helpers ────────────────────────────────────────────────────────

function toSeverity(relevance: string): Severity {
  if (relevance === "HIGH")   return "critical";
  if (relevance === "MEDIUM") return "high";
  return "medium";
}

function toAgeMin(published_at: string): number | null {
  if (!published_at) return null;
  const ms = Date.now() - new Date(published_at).getTime();
  if (isNaN(ms)) return null;
  return Math.max(0, Math.round(ms / 60_000));
}

function deriveRisk(nodes: EnrichedNode[]): string {
  if (nodes.some(n => n.severity === "critical")) return "critical";
  if (nodes.some(n => n.severity === "high"))     return "high";
  if (nodes.some(n => n.severity === "medium"))   return "medium";
  return "low";
}

function enrichHeadlines(headlines: NewsHeadline[]): EnrichedNode[] {
  return headlines.slice(0, 8).map((h, i) => {
    const text = (h.title_tr?.trim()) || h.title;
    const sev  = toSeverity(h.relevance);
    const cat  = h.tags?.[0] ?? "news";
    const assets = (h.asset_impact ?? []).map(a => ({
      asset: a.asset_code,
      up:    a.direction === "negative",
      note:  a.note,
    }));
    return {
      id:       `n${i}`,
      headline: text,
      source:   h.source,
      severity: sev,
      category: cat,
      age_min:  toAgeMin(h.published_at),
      assets,
      geo:      geoForRegion(classifyHeadlineRegion(text, cat)),
      actor:    detectActor(h, text),
    };
  });
}

// Haber başına süre: headline okunmadan geçilmez (uzunluğa göre 9–20sn)
function durForNode(n: EnrichedNode | null): number {
  if (!n) return PHASE_MS;
  return Math.min(20_000, Math.max(9_000, 4_000 + n.headline.length * 85));
}

// ── Style maps ────────────────────────────────────────────────────────────────

const SEV: Record<Severity, { dot: string; badge: string; text: string; label: string }> = {
  critical: { dot: "#f87171", badge: "bg-red-950/60 border-red-600/70 text-red-200",         text: "text-red-300",    label: "KRİTİK" },
  high:     { dot: "#fb923c", badge: "bg-orange-950/50 border-orange-600/60 text-orange-200", text: "text-orange-300", label: "YÜKSEK" },
  medium:   { dot: "#fbbf24", badge: "bg-amber-950/40 border-amber-600/50 text-amber-200",   text: "text-amber-300",  label: "ORTA" },
  low:      { dot: "#22d3ee", badge: "bg-cyan-950/40 border-cyan-700/50 text-cyan-200",      text: "text-cyan-300",   label: "DÜŞÜK" },
};

const RISK_BADGE: Record<string, string> = {
  critical: "bg-red-950/70 border-red-600/70 text-red-200",
  high:     "bg-orange-950/60 border-orange-500/60 text-orange-200",
  medium:   "bg-amber-950/50 border-amber-500/50 text-amber-200",
  low:      "bg-cyan-950/40 border-cyan-600/40 text-cyan-200",
};

// ── World map (local/static, equirectangular 1000×500) ───────────────────────
// x=(lon+180)/360*1000, y=(90-lat)/180*500 — gerçek kıyı koordinatlarından
// sadeleştirilmiş low-poly path'ler; runtime fetch yok.

const LANDMASS: string[] = WORLD_LAND_PATHS;

// ── Sub-components ────────────────────────────────────────────────────────────

function WorldMap({
  nodes, phase, animate, activeNode, activeSv, fill = false, durationMs = PHASE_MS,
}: {
  nodes:     EnrichedNode[];
  phase:     CyclePhase;
  animate:   boolean;
  activeNode: EnrichedNode | null;
  activeSv:  typeof SEV["low"] | null;
  /** true → modülün tamamını kaplayan arka plan modu */
  fill?:     boolean;
  /** Aktif haberin toplam süresi — zoom/marquee bununla senkron */
  durationMs?: number;
}) {
  const allPulse  = phase.mode === "all_pulse";
  const activeIdx = phase.mode === "sequence" ? phase.idx : -1;

  // Zoom haber süresiyle senkron: haber başında zoom-in, headline bitene
  // kadar bölgede kal, bitişten ~1.6sn önce zoom-out. Reduced-motion → zoom yok.
  const [zoomed, setZoomed] = useState(false);
  const activeId = activeNode?.id ?? null;
  useEffect(() => {
    if (!animate || !activeId) { setZoomed(false); return; }
    setZoomed(true);
    const t = setTimeout(() => setZoomed(false), Math.max(2_500, durationMs - 1_600));
    return () => clearTimeout(t);
  }, [activeId, animate, durationMs]);

  const ZK = 2.1;
  const zcx = activeNode ? Math.min(762, Math.max(238, activeNode.geo.x)) : 500;
  const zcy = activeNode ? Math.min(381, Math.max(119, activeNode.geo.y)) : 250;
  const mapTransform = zoomed
    ? `translate(500px,250px) scale(${ZK}) translate(${-zcx}px,${-zcy}px)`
    : "translate(0px,0px) scale(1)";

  // Ticker position: zoom'da merkez; değilse nokta yanı (kenarlarda taraf değiştir)
  const tickerAnchorLeft = activeNode ? activeNode.geo.x > 620 : false;
  const tickerAnchorLow  = activeNode ? activeNode.geo.y < 130 : false;
  const tickerTransformX = zoomed ? "-50%" : tickerAnchorLeft ? "calc(-100% - 14px)" : "14px";
  const tickerTransformY = zoomed ? "20px" : tickerAnchorLow ? "4px" : "-50%";
  const tickerLeftPct = zoomed ? 50 : activeNode ? (activeNode.geo.x / 1000) * 100 : 50;
  const tickerTopPct  = zoomed ? 50 : activeNode ? (activeNode.geo.y / 500)  * 100 : 50;

  return (
    <div className={fill ? "absolute inset-0 w-full h-full" : "relative w-full"}
         style={fill ? undefined : { paddingBottom: "50%" }}>
      {/* Radar sweep HTML overlay */}
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

      {/* Floating headline ticker */}
      {!allPulse && activeNode && activeSv && (
        <div
          className="absolute pointer-events-none z-20"
          style={{
            left:      `${tickerLeftPct}%`,
            top:       `${tickerTopPct}%`,
            transform: `translate(${tickerTransformX}, ${tickerTransformY})`,
            maxWidth:  zoomed ? "60%" : "42%",
            minWidth:  "160px",
            transition: animate ? "left 1.3s cubic-bezier(.4,0,.2,1), top 1.3s cubic-bezier(.4,0,.2,1)" : undefined,
          }}
          key={activeNode.id}
        >
          <div className="flex items-end gap-2">
            {/* Speaker/aktör avatar bubble — sadece tespit edilen aktörde */}
            {activeNode.actor && (
              <div className="flex flex-col items-center shrink-0 pb-0.5">
                <span
                  className="flex h-9 w-9 items-center justify-center rounded-full border-2 overflow-hidden font-mono font-black text-[10px] text-white"
                  style={{
                    borderColor: activeSv.dot,
                    background: activeNode.actor.img
                      ? undefined
                      : `radial-gradient(circle at 35% 30%, ${activeSv.dot}55, rgba(2,10,22,0.95))`,
                    boxShadow: `0 0 12px ${activeSv.dot}55`,
                  }}
                >
                  {activeNode.actor.img
                    // eslint-disable-next-line @next/next/no-img-element
                    ? <img src={activeNode.actor.img} alt={activeNode.actor.name} className="h-full w-full object-cover" />
                    : activeNode.actor.short}
                </span>
                <span className="mt-0.5 text-[10px] font-mono leading-none" style={{ color: activeSv.dot }}>
                  {activeNode.actor.name}
                </span>
              </div>
            )}

            {/* Glass speech-pill */}
            <div
              className="relative rounded-xl border backdrop-blur-md px-3 py-2"
              style={{
                background:   "rgba(2,10,22,0.92)",
                borderColor:  activeSv.dot + "66",
                boxShadow:    `0 0 18px ${activeSv.dot}33, inset 0 1px 0 ${activeSv.dot}33`,
              }}
            >
              {/* Speech beam — avatar'dan çıkıyormuş hissi */}
              {activeNode.actor && (
                <span aria-hidden="true" className="absolute -left-1.5 bottom-3 w-3 h-3 rotate-45 border-l border-b"
                      style={{ background: "rgba(2,10,22,0.92)", borderColor: activeSv.dot + "66" }} />
              )}
              <p className="text-[10px] font-mono truncate whitespace-nowrap"
                 style={{ color: activeSv.dot, opacity: 0.85 }}>
                {activeNode.geo.region} · {activeNode.source}
                {activeNode.age_min !== null ? ` · ${activeNode.age_min}dk` : ""}
              </p>
              <div className="overflow-hidden" style={{ maxWidth: "100%" }}>
                <span
                  className="inline-block text-sm sm:text-base font-semibold whitespace-nowrap"
                  style={{
                    color:     activeSv.dot,
                    textShadow: `0 0 10px ${activeSv.dot}44`,
                    animation: animate && activeNode.headline.length > 36
                      ? `bnm-ticker ${((durationMs - 1_200) / 1000).toFixed(1)}s ease-in-out infinite`
                      : undefined,
                  }}
                >
                  {activeNode.headline}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      <svg
        viewBox="0 0 1000 500"
        preserveAspectRatio={fill ? "none" : "xMidYMid meet"}
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

        <rect width="1000" height="500" fill="url(#bnm-bg)" />

        {/* Zoom grubu — aktif haberin bölgesine smooth yakınlaşma */}
        <g style={{
          transform: mapTransform,
          transition: animate ? "transform 1.3s cubic-bezier(.4,0,.2,1)" : undefined,
          transformOrigin: "0 0",
        }}>

        {Array.from({ length: 17 }, (_, i) => (
          <line key={`v${i}`} x1={(i + 1) * 55.5} y1="0" x2={(i + 1) * 55.5} y2="500"
            stroke="#13335c" strokeWidth="0.4" opacity="0.5" />
        ))}
        {Array.from({ length: 8 }, (_, i) => (
          <line key={`h${i}`} x1="0" y1={(i + 1) * 55.5} x2="1000" y2={(i + 1) * 55.5}
            stroke="#13335c" strokeWidth="0.4" opacity="0.5" />
        ))}
        <line x1="0" y1="250" x2="1000" y2="250" stroke="#22d3ee" strokeWidth="0.6" opacity="0.18" />

        <g filter="url(#bnm-landglow)">
          {LANDMASS.map((d, i) => (
            <path key={i} d={d}
              fill="#0e2a4e" stroke="#2563a8" strokeWidth="1"
              strokeLinejoin="round" opacity="0.92" />
          ))}
        </g>

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

        {nodes.map((node, i) => {
          const { x, y, region } = node.geo;
          const sv       = SEV[node.severity] ?? SEV.low;
          const isActive = allPulse || i === activeIdx;
          const strong   = !allPulse && i === activeIdx;
          return (
            <g key={node.id} transform={`translate(${x},${y})`}
               style={{ transition: "opacity 0.6s ease" }} opacity={isActive ? 1 : 0.45}>
              {animate && isActive && (
                <circle r={strong ? 26 : 18} fill="none" stroke={sv.dot} strokeWidth="1"
                  opacity="0.30"
                  style={{ animation: `bnm-pulse ${allPulse ? "1.6s" : "2s"} ease-in-out infinite` }}
                />
              )}
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
              {/* Region label (small, above dot — visible when NOT the active node) */}
              {!strong && isActive && (
                <text x="0" y="-11" textAnchor="middle" fontSize="7"
                  fill="#94a3b8" fontFamily="monospace" opacity="0.55">
                  {region.toUpperCase()}
                </text>
              )}
            </g>
          );
        })}

        </g>

        <rect width="1000" height="500" fill="none" stroke="#22d3ee" strokeWidth="1" opacity="0.10" />
      </svg>
    </div>
  );
}

function SideNewsCard({
  node, active, dimmed, onClick,
}: { node: EnrichedNode; active: boolean; dimmed: boolean; onClick: () => void }) {
  const sv = SEV[node.severity] ?? SEV.low;
  // age_min Date.now() ile hesaplanır → SSR ve client farklı dakika üretip
  // hydration mismatch yapar. İlk render'da (server + client) deterministik
  // placeholder göster; mount sonrası gerçek dakikayı ver.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
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
        <span className={`rounded px-1 py-0.5 text-[10px] font-mono font-black uppercase tracking-widest border ${sv.badge}`}>
          {sv.label}
        </span>
        <span className="text-[10px] font-mono text-eyay-faint truncate max-w-[90px]">{node.source}</span>
        {node.age_min !== null && (
          <span className="text-[10px] font-mono text-eyay-faint/60 ml-auto shrink-0">
            {mounted ? `${node.age_min}dk` : "—"}
          </span>
        )}
      </div>
      <p className="text-[10px] text-eyay-dim leading-snug line-clamp-2">{node.headline}</p>
      <p className="text-[10px] font-mono text-eyay-faint/70 mt-0.5">📍 {node.geo.region} · {node.category}</p>
    </button>
  );
}

function AssetCard({ a }: { a: { asset: string; up: boolean; note: string } }) {
  const ICONS: Record<string, { icon: string; color: string }> = {
    BRENT:  { icon: "🛢", color: "text-orange-300" },
    GOLD:   { icon: "Au", color: "text-amber-300" },
    SILVER: { icon: "Ag", color: "text-slate-300" },
    BTC:    { icon: "₿",  color: "text-purple-300" },
    DXY:    { icon: "$",  color: "text-cyan-300" },
    VIX:    { icon: "⚡", color: "text-red-300" },
    SPY:    { icon: "📊", color: "text-blue-300" },
    HYG:    { icon: "HY", color: "text-rose-300" },
  };
  const meta = ICONS[a.asset] ?? { icon: a.asset.slice(0, 2), color: "text-slate-300" };
  return (
    <div className={`rounded-xl border px-3 py-2 bg-white/[0.04] backdrop-blur-sm ${
      a.up ? "border-red-600/40" : "border-cyan-700/40"
    }`}>
      <div className="flex items-center gap-2">
        <span className={`text-sm font-bold shrink-0 ${meta.color}`}>{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-mono font-bold text-eyay-dim">{a.asset}</p>
          <p className="text-[10px] font-mono text-eyay-faint truncate">{a.note}</p>
        </div>
        <span className={`text-[10px] font-mono font-semibold shrink-0 ${a.up ? "text-red-300" : "text-cyan-300"}`}>
          {a.up ? "↑ risk" : "↓ baskı"}
        </span>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  headlines:   NewsHeadline[];
  onDegraded?: (reason: string) => void;
}

export default function NewsMapRadarLayer({ headlines, onDegraded: _onDegraded }: Props) {
  const [phase,    setPhase]   = useState<CyclePhase>({ mode: "sequence", idx: 0 });
  const [animate,  setAnimate] = useState(false);
  const [isMobile, setMobile]  = useState(false);

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

  const enriched  = enrichHeadlines(headlines);
  const nodeCount = enriched.length;

  // Haber okunmadan geçilmez — süre headline uzunluğuna göre
  const phaseDur = phase.mode === "sequence"
    ? durForNode(enriched[phase.idx % Math.max(nodeCount, 1)] ?? null)
    : PHASE_MS;

  useEffect(() => {
    if (nodeCount === 0) return;
    const t = setTimeout(() => {
      setPhase(p => {
        if (p.mode === "all_pulse")    return { mode: "sequence", idx: 0 };
        if (p.idx >= nodeCount - 1)    return nodeCount > 1 ? { mode: "all_pulse" } : { mode: "sequence", idx: 0 };
        return { mode: "sequence", idx: p.idx + 1 };
      });
    }, phaseDur);
    return () => clearTimeout(t);
  }, [phase, nodeCount, phaseDur]);

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
  const sv         = SEV[activeNode.severity] ?? SEV.low;
  const riskLevel  = deriveRisk(enriched);
  const riskBadge  = RISK_BADGE[riskLevel] ?? RISK_BADGE.low;

  const impacts = allPulse
    ? enriched.flatMap(n => n.assets).slice(0, 5)
    : activeNode.assets.slice(0, 5);

  return (
    <div
      className="w-full max-w-full min-w-0 rounded-xl border border-eyay-border bg-[#030e1c] overflow-hidden"
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
        @keyframes bnm-ticker  { 0%,12%{transform:translateX(0)} 78%,100%{transform:translateX(-55%)} }
      `}</style>

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-eyay-border/40 bg-black/30">
        <div>
          <p className="text-[11px] font-mono font-bold text-eyay-dim uppercase tracking-widest">
            Son Dakika Haber Radarı
          </p>
          <p className="text-[10px] font-mono text-eyay-faint mt-0.5">
            {enriched.length} haber · PAPER_SAFE · sadece görselleştirme
          </p>
        </div>
        <div className="flex items-center gap-2">
          {allPulse && (
            <span className="text-[10px] font-mono text-cyan-300/80 uppercase tracking-widest"
                  style={animate ? { animation: "bnm-fadein 0.6s ease" } : undefined}>
              ◉ Global görünüm
            </span>
          )}
          <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest ${riskBadge}`}>
            Risk: {riskLevel}
          </span>
        </div>
      </div>

      {/* ── Desktop layout — harita tüm modülün arka planı ── */}
      {!isMobile && (
        <div className="relative min-h-[440px]">
          {/* ARKA PLAN: tam genişlik dünya haritası */}
          <WorldMap
            fill
            nodes={enriched}
            phase={phase}
            animate={animate}
            activeNode={!allPulse ? activeNode : null}
            activeSv={!allPulse ? sv : null}
            durationMs={phaseDur}
          />

          {/* ÖN KATMAN: yan kolonlar + alt bilgi şeridi */}
          <div className="relative z-10 grid grid-cols-[190px_minmax(0,1fr)_175px] min-h-[440px] pointer-events-none">

          {/* SOL: haber kartları */}
          <div className="pointer-events-auto border-r border-eyay-border/25 p-3 flex flex-col gap-2 bg-black/45 backdrop-blur-[2px] overflow-y-auto max-h-[460px]">
            <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest shrink-0">
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

          {/* ORTA: harita görünür kalsın — sadece alt bilgi şeridi */}
          <div className="flex flex-col justify-end min-w-0">
            <div className="pointer-events-auto px-4 py-2 border-t border-eyay-border/20 bg-black/55 backdrop-blur-[2px] text-center"
                 key={allPulse ? "all" : activeNode.id}
                 style={animate ? { animation: "bnm-fadein 0.5s ease" } : undefined}>
              {allPulse ? (
                <p className="text-[10px] font-mono text-cyan-300/90">
                  ◉ GLOBAL RİSK GÖRÜNÜMÜ · {enriched.length} aktif bölge
                </p>
              ) : (
                <>
                  <p className="text-[10px] font-mono">
                    <span className={`font-bold ${sv.text}`}>● {activeNode.geo.region}</span>
                    <span className="text-eyay-faint"> · {activeNode.source}</span>
                  </p>
                  <p className="text-xs text-eyay-faint/80 truncate mt-0.5 max-w-[460px] mx-auto">
                    {activeNode.headline.slice(0, 95)}{activeNode.headline.length > 95 ? "…" : ""}
                  </p>
                </>
              )}
            </div>
          </div>

          {/* SAĞ: etkilenen varlıklar */}
          <div className="pointer-events-auto border-l border-eyay-border/25 p-3 flex flex-col gap-2 bg-black/45 backdrop-blur-[2px]">
            <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest shrink-0">
              Etkilenen Varlıklar
            </p>
            {impacts.length > 0
              ? impacts.map((a, i) => <AssetCard key={i} a={a} />)
              : <p className="text-[10px] font-mono text-eyay-faint/50 italic">Varlık etkisi yok.</p>
            }
          </div>
          </div>
        </div>
      )}

      {/* ── Mobile layout ── */}
      {isMobile && (
        <div className="space-y-3 p-3 bg-[#020a16]">
          <WorldMap
            nodes={enriched} phase={phase} animate={false}
            activeNode={null} activeSv={null}
          />
          <div className={`rounded-xl border p-3 ${sv.badge}`}>
            <p className="text-[10px] font-mono mb-0.5">
              {activeNode.source} · 📍 {activeNode.geo.region}
            </p>
            <p className="text-xs text-eyay-dim leading-snug">{activeNode.headline}</p>
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
        <p className="text-[10px] font-mono text-eyay-faint/55 text-center">
          Radar yalnızca haber görselleştirmesidir · karar üretmez · veri alınamazsa klasik liste görünümüne dönülür
        </p>
      </div>
    </div>
  );
}
