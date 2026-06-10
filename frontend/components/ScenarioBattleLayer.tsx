"use client";

/**
 * Scenario Battle Layer — "Boğa vs Ayı 3D Battle" (low-poly neon stil).
 *
 * SENARYO panelindeki bull/base/bear olasılıklarını wireframe/constellation
 * tarzı savaş sahnesi olarak görselleştirir. KARAR ÜRETMEZ — sadece görsel
 * katman. Hesaplama logic'i değişmez; olasılıklar props'tan okunur.
 * Veri eksik/parse edilemez → onDegraded → Shell legacy listeye döner.
 * PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useState } from "react";

import type { Scenario } from "@/lib/types";

type Dominance = "bull-dominant" | "base-dominant" | "bear-dominant";

interface Props {
  scenarios: Scenario[];
  onDegraded?: (reason: string) => void;
}

interface BattleData {
  bull: Scenario;
  base: Scenario;
  bear: Scenario;
  dominance: Dominance;
  clash: number;      // 0..1 — boğa/ayı yakınlığı (yüksek = yoğun çatışma)
  bullPower: number;  // 0..1
  bearPower: number;  // 0..1
  basePower: number;  // 0..1
}

function parseBattle(scenarios: Scenario[]): BattleData | null {
  const bull = scenarios.find(s => s.key === "bull");
  const base = scenarios.find(s => s.key === "base");
  const bear = scenarios.find(s => s.key === "bear");
  if (!bull || !base || !bear) return null;
  const p = (s: Scenario) => Number(s.probability_pct);
  if (![p(bull), p(base), p(bear)].every(n => Number.isFinite(n) && n >= 0)) return null;

  const dominance: Dominance =
    p(base) >= p(bull) && p(base) >= p(bear) ? "base-dominant"
    : p(bull) >= p(bear)                     ? "bull-dominant"
    :                                          "bear-dominant";

  const diff  = Math.abs(p(bull) - p(bear));
  const clash = Math.max(0.2, 1 - diff / 30);

  const power = (n: number) => Math.min(1, Math.max(0.25, n / 60));
  return {
    bull, base, bear, dominance, clash,
    bullPower: power(p(bull)),
    bearPower: power(p(bear)),
    basePower: power(p(base)),
  };
}

// ── Low-poly wireframe figürler ───────────────────────────────────────────────
// Stil: koyu gövde + neon kenar glow + iç mesh çizgileri + vertex noktaları.

const BULL_VERTS: Array<[number, number]> = [
  [30, 70], [60, 52], [95, 40], [125, 48], [150, 55], [185, 95],
  [160, 105], [140, 125], [135, 142], [100, 128], [70, 132], [25, 95],
  [138, 72],
];
const BULL_MESH: Array<[number, number, number, number]> = [
  [25, 95, 60, 52], [25, 95, 100, 128], [60, 52, 100, 128],
  [95, 40, 100, 128], [95, 40, 140, 125], [125, 48, 140, 125],
  [125, 48, 160, 105], [150, 55, 160, 105], [140, 125, 100, 128],
  [160, 105, 140, 125], [150, 55, 185, 95], [70, 132, 100, 128],
  [30, 70, 60, 52], [30, 70, 25, 95], [135, 142, 140, 125],
];

function BullFigure({ power, dominant, animate }: { power: number; dominant: boolean; animate: boolean }) {
  const glow = dominant ? 0.9 : 0.45;
  return (
    <svg
      viewBox="0 0 200 160"
      className="w-full h-full"
      style={{
        opacity: 0.6 + power * 0.4,
        filter: `drop-shadow(0 0 ${dominant ? 22 : 10}px rgba(52,211,153,${glow}))`,
        animation: animate ? "sb-bull-breathe 3.4s ease-in-out infinite" : undefined,
      }}
      aria-hidden
    >
      <defs>
        <linearGradient id="sb-bull-body" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#064e3b" />
          <stop offset="50%" stopColor="#022c22" />
          <stop offset="100%" stopColor="#042f2e" />
        </linearGradient>
        <linearGradient id="sb-bull-edge" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
        <clipPath id="sb-bull-clip">
          <path d="M35 140 L25 95 L18 86 L30 70 L60 52 L95 40 L125 48 L150 55 L185 95 L175 108 L160 105 L140 125 L150 145 L135 142 L100 128 L70 132 L60 148 L45 145 Z" />
        </clipPath>
      </defs>

      {/* gövde — koyu dolgu */}
      <path
        fill="url(#sb-bull-body)"
        d="M35 140 L25 95 L18 86 L30 70 L60 52 L95 40 L125 48 L150 55 L185 95 L175 108 L160 105 L140 125 L150 145 L135 142 L100 128 L70 132 L60 148 L45 145 Z"
      />
      {/* iç mesh — üçgenleme çizgileri */}
      <g clipPath="url(#sb-bull-clip)" stroke="#34d399" strokeWidth="0.6" opacity={0.4 + power * 0.3}>
        {BULL_MESH.map(([x1, y1, x2, y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />
        ))}
      </g>
      {/* facet highlight'lar */}
      <g clipPath="url(#sb-bull-clip)" opacity={0.25 + power * 0.2}>
        <polygon points="95,40 125,48 100,128" fill="rgba(52,211,153,0.30)" />
        <polygon points="125,48 160,105 140,125" fill="rgba(34,211,238,0.22)" />
        <polygon points="25,95 60,52 100,128" fill="rgba(16,185,129,0.15)" />
      </g>
      {/* neon dış kontur */}
      <path
        fill="none" stroke="url(#sb-bull-edge)" strokeWidth="1.4" strokeLinejoin="round"
        opacity={0.55 + power * 0.45}
        d="M35 140 L25 95 L18 86 L30 70 L60 52 L95 40 L125 48 L150 55 L185 95 L175 108 L160 105 L140 125 L150 145 L135 142 L100 128 L70 132 L60 148 L45 145 Z"
      />
      {/* boynuzlar — öne kıvrılan kısa hilaller */}
      <path fill="#d1fae5" opacity="0.9"
        d="M147 57 Q156 47 169 42 Q174 40 170 45 Q162 52 153 61 Z" />
      <path fill="#d1fae5" opacity="0.85"
        d="M136 58 Q129 48 118 45 Q113 44 117 48 Q124 54 130 62 Z" />
      {/* baş faseti — kafayı belirginleştir */}
      <polygon points="150,55 185,95 160,105 138,72" fill="rgba(110,231,183,0.18)" />
      <path fill="none" stroke="#34d399" strokeWidth="0.7" opacity="0.6"
        d="M138 72 L160 105 M138 72 L185 95" />
      {/* vertex noktaları — constellation */}
      <g fill="#6ee7b7" opacity={0.7 + power * 0.3}>
        {BULL_VERTS.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="1.4" />)}
      </g>
      {/* göz */}
      <circle cx="162" cy="74" r="2.2" fill="#a7f3d0" opacity="0.95" />
      {/* burun deliği buhar çizgisi */}
      <path fill="none" stroke="#34d399" strokeWidth="0.8" opacity="0.5"
        d="M183 100 q6 -2 9 -7 M180 105 q7 0 11 -3" />
    </svg>
  );
}

const BEAR_VERTS: Array<[number, number]> = [
  [45, 52], [58, 40], [100, 42], [140, 50], [165, 62], [180, 100],
  [160, 142], [115, 130], [95, 135], [60, 115], [40, 100], [38, 80],
];
const BEAR_MESH: Array<[number, number, number, number]> = [
  [45, 52, 38, 80], [38, 80, 60, 115], [45, 52, 60, 115],
  [58, 40, 60, 115], [100, 42, 60, 115], [100, 42, 115, 130],
  [140, 50, 115, 130], [165, 62, 115, 130], [165, 62, 180, 100],
  [180, 100, 115, 130], [60, 115, 95, 135], [115, 130, 95, 135],
  [140, 50, 165, 62], [40, 100, 60, 115], [160, 142, 115, 130],
];

function BearFigure({ power, dominant, animate }: { power: number; dominant: boolean; animate: boolean }) {
  const glow = dominant ? 0.9 : 0.45;
  return (
    <svg
      viewBox="0 0 200 160"
      className="w-full h-full"
      style={{
        opacity: 0.6 + power * 0.4,
        filter: `drop-shadow(0 0 ${dominant ? 22 : 10}px rgba(248,113,113,${glow}))`,
        animation: animate ? "sb-bear-claw 3.8s ease-in-out infinite" : undefined,
      }}
      aria-hidden
    >
      <defs>
        <linearGradient id="sb-bear-body" x1="1" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7f1d1d" />
          <stop offset="50%" stopColor="#450a0a" />
          <stop offset="100%" stopColor="#431407" />
        </linearGradient>
        <linearGradient id="sb-bear-edge" x1="1" y1="0" x2="0" y2="0">
          <stop offset="0%" stopColor="#f87171" />
          <stop offset="100%" stopColor="#fb923c" />
        </linearGradient>
        <clipPath id="sb-bear-clip">
          <path d="M18 62 L45 52 L58 40 L70 48 L100 42 L140 50 L165 62 L180 100 L175 145 L160 142 L115 130 L95 135 L90 148 L75 145 L60 115 L40 100 L22 92 L38 80 Z" />
        </clipPath>
      </defs>

      {/* gövde */}
      <path
        fill="url(#sb-bear-body)"
        d="M18 62 L45 52 L58 40 L70 48 L100 42 L140 50 L165 62 L180 100 L175 145 L160 142 L115 130 L95 135 L90 148 L75 145 L60 115 L40 100 L22 92 L38 80 Z"
      />
      {/* iç mesh */}
      <g clipPath="url(#sb-bear-clip)" stroke="#f87171" strokeWidth="0.6" opacity={0.4 + power * 0.3}>
        {BEAR_MESH.map(([x1, y1, x2, y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} />
        ))}
      </g>
      {/* facet highlight'lar */}
      <g clipPath="url(#sb-bear-clip)" opacity={0.25 + power * 0.2}>
        <polygon points="100,42 140,50 115,130" fill="rgba(248,113,113,0.28)" />
        <polygon points="45,52 70,48 60,115" fill="rgba(251,146,60,0.22)" />
        <polygon points="165,62 180,100 115,130" fill="rgba(239,68,68,0.15)" />
      </g>
      {/* neon dış kontur */}
      <path
        fill="none" stroke="url(#sb-bear-edge)" strokeWidth="1.4" strokeLinejoin="round"
        opacity={0.55 + power * 0.45}
        d="M18 62 L45 52 L58 40 L70 48 L100 42 L140 50 L165 62 L180 100 L175 145 L160 142 L115 130 L95 135 L90 148 L75 145 L60 115 L40 100 L22 92 L38 80 Z"
      />
      {/* açık ağız — dişler */}
      <path fill="#fecaca" opacity="0.9" d="M20 64 L28 68 L24 72 Z M26 88 L34 84 L32 92 Z" />
      {/* vertex noktaları */}
      <g fill="#fca5a5" opacity={0.7 + power * 0.3}>
        {BEAR_VERTS.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="1.4" />)}
      </g>
      {/* göz */}
      <circle cx="48" cy="60" r="2.2" fill="#f87171" opacity="0.95" />
      {/* pençe izi çizgileri */}
      <path fill="none" stroke="#fb923c" strokeWidth="0.8" opacity="0.5"
        d="M58 112 l-8 9 M64 116 l-8 9 M70 120 l-8 9" />
    </svg>
  );
}

// ── Parçacıklar + enkaz ───────────────────────────────────────────────────────

function Particles({ side }: { side: "bull" | "bear" }) {
  const items = [0, 1, 2, 3, 4, 5];
  const color = side === "bull" ? "rgba(52,211,153," : "rgba(248,113,113,";
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden>
      {items.map(i => (
        <span
          key={i}
          className="absolute rounded-full"
          style={{
            width: i % 2 ? 2 : 3, height: i % 2 ? 2 : 3,
            left: side === "bull" ? `${6 + i * 6.5}%` : undefined,
            right: side === "bear" ? `${6 + i * 6.5}%` : undefined,
            bottom: "12%",
            background: `${color}0.85)`,
            boxShadow: `0 0 8px ${color}0.9)`,
            animation: `${side === "bull" ? "sb-rise" : "sb-fall"} ${2.2 + i * 0.5}s linear infinite`,
            animationDelay: `${i * 0.4}s`,
          }}
        />
      ))}
    </div>
  );
}

function Debris() {
  // zemindeki kaya/enkaz silüeti — statik
  return (
    <svg className="absolute bottom-0 left-0 w-full h-[26%] pointer-events-none" viewBox="0 0 700 60" preserveAspectRatio="none" aria-hidden>
      <path
        d="M0 60 L0 38 L40 30 L80 40 L130 26 L180 38 L240 30 L300 42 L350 34 L410 44 L470 28 L530 40 L580 30 L630 42 L700 32 L700 60 Z"
        fill="#020a14" opacity="0.9"
      />
      <path
        d="M0 60 L0 46 L60 40 L120 48 L200 38 L280 50 L350 44 L430 52 L510 40 L600 50 L700 42 L700 60 Z"
        fill="#01060d"
      />
      {/* küçük enkaz üçgenleri */}
      <g opacity="0.6">
        <polygon points="95,38 102,28 110,38" fill="#0d9488" opacity="0.5" />
        <polygon points="170,42 176,34 184,42" fill="#115e59" opacity="0.5" />
        <polygon points="540,40 547,31 555,40" fill="#9a3412" opacity="0.5" />
        <polygon points="610,46 616,38 624,46" fill="#7f1d1d" opacity="0.5" />
      </g>
    </svg>
  );
}

// ── Mini kart ─────────────────────────────────────────────────────────────────

const CARD_STYLE = {
  bull: { label: "text-emerald-300", ring: "border-emerald-500/60", border: "border-emerald-800/40", bg: "bg-emerald-950/25", chip: "border-emerald-700/50 text-emerald-300 bg-emerald-950/40", icon: "🐂" },
  base: { label: "text-amber-300",   ring: "border-amber-500/60",   border: "border-amber-800/40",   bg: "bg-amber-950/20",   chip: "border-amber-700/50 text-amber-300 bg-amber-950/40",     icon: "⚖️" },
  bear: { label: "text-red-300",     ring: "border-red-500/60",     border: "border-red-800/40",     bg: "bg-red-950/25",     chip: "border-red-700/50 text-red-300 bg-red-950/40",           icon: "🐻" },
} as const;

function confidenceLabel(pct: number, key: string): string {
  if (key === "base") return pct >= 50 ? "Orta" : "Düşük/Orta";
  return pct >= 35 ? "Düşük/Orta" : "Düşük";
}

function MiniCard({ sc, kind }: { sc: Scenario; kind: keyof typeof CARD_STYLE }) {
  const s = CARD_STYLE[kind];
  return (
    <div className={`rounded-xl border px-3 py-2.5 ${s.border} ${s.bg} backdrop-blur-sm`}>
      <div className="flex items-center gap-2">
        <span className={`w-8 h-8 rounded-full border-2 ${s.ring} flex items-center justify-center text-sm shrink-0 bg-black/40`}>
          {s.icon}
        </span>
        <span className={`text-xs font-mono font-bold ${s.label}`}>{sc.label}</span>
        <span className={`ml-auto text-base font-black font-mono ${s.label}`}>%{sc.probability_pct}</span>
      </div>
      <p className="text-[8px] font-mono text-eyay-faint mt-1.5">
        Güven: {confidenceLabel(sc.probability_pct, sc.key)}
      </p>
      <p className="text-[9px] text-eyay-dim leading-snug line-clamp-2 mt-1" title={sc.trigger}>
        {sc.trigger}
      </p>
      {sc.thresholds && sc.thresholds.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {sc.thresholds.slice(0, 3).map((thr, i) => (
            <span key={i} className={`text-[8px] font-mono font-semibold px-1.5 py-0.5 rounded border ${s.chip}`}>
              {thr}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Ana bileşen ───────────────────────────────────────────────────────────────

export default function ScenarioBattleLayer({ scenarios, onDegraded }: Props) {
  const [animate, setAnimate] = useState(false);
  const [isMobile, setMobile] = useState(false);

  const battle = parseBattle(scenarios ?? []);

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

  useEffect(() => {
    if (battle === null) onDegraded?.("scenario_data_missing");
  }, [battle, onDegraded]);

  if (battle === null) return null;

  const { bull, base, bear, dominance, clash, bullPower, bearPower, basePower } = battle;
  const anim = animate && !isMobile;

  const domSc =
    dominance === "base-dominant" ? base :
    dominance === "bull-dominant" ? bull : bear;
  const domColor =
    dominance === "base-dominant" ? "#fbbf24" :
    dominance === "bull-dominant" ? "#34d399" : "#f87171";
  const domRgba =
    dominance === "base-dominant" ? "rgba(251,191,36," :
    dominance === "bull-dominant" ? "rgba(52,211,153," : "rgba(248,113,113,";

  return (
    <div
      className="rounded-2xl border border-eyay-border overflow-hidden relative"
      style={{ background: "radial-gradient(120% 90% at 50% 30%, #071426 0%, #030b16 55%, #01060d 100%)" }}
      data-testid="scenario-battle"
      data-dominance={dominance}
      data-reduced-motion={!anim ? "true" : "false"}
    >
      <style>{`
        @keyframes sb-bull-breathe { 0%,100%{transform:translateX(0) scale(1)} 50%{transform:translateX(5px) scale(1.015)} }
        @keyframes sb-bear-claw    { 0%,100%{transform:rotate(0deg) scale(1)} 50%{transform:rotate(-2deg) scale(1.015)} }
        @keyframes sb-clash        { 0%,100%{opacity:.5;transform:translate(-50%,-50%) scale(1)} 50%{opacity:.95;transform:translate(-50%,-50%) scale(1.15)} }
        @keyframes sb-rise         { from{transform:translateY(0);opacity:.9} to{transform:translateY(-140px);opacity:0} }
        @keyframes sb-fall         { from{transform:translate(0,0);opacity:.9} to{transform:translate(-45px,45px);opacity:0} }
        @keyframes sb-badge-pulse  { 0%,100%{transform:translate(-50%,-50%) scale(1)} 50%{transform:translate(-50%,-50%) scale(1.06)} }
      `}</style>

      {/* arka plan: grid + mum çubukları + chart çizgileri */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.14]" aria-hidden>
        <defs>
          <pattern id="sb-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M40 0H0V40" fill="none" stroke="#1d4ed8" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#sb-grid)" />
        {/* mum çubukları */}
        <g opacity="0.7">
          {[40, 90, 140, 190, 240, 290, 340, 390, 440, 490, 540, 590, 640].map((x, i) => {
            const up = i % 3 !== 1;
            const h = 14 + ((i * 7) % 22);
            const y = 30 + ((i * 13) % 40);
            return (
              <g key={x}>
                <line x1={x} y1={y - 6} x2={x} y2={y + h + 6} stroke={up ? "#10b981" : "#ef4444"} strokeWidth="1" />
                <rect x={x - 3} y={y} width="6" height={h} fill={up ? "#10b981" : "#ef4444"} />
              </g>
            );
          })}
        </g>
        <polyline points="0,140 70,115 140,130 220,85 300,105 380,65 470,90 570,50 700,75"
          fill="none" stroke="#22d3ee" strokeWidth="1.2" opacity="0.6" />
      </svg>

      {/* üst başlık */}
      <div className="relative px-4 pt-3 flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono font-bold text-eyay-text tracking-widest uppercase">Senaryo</span>
            <span className="text-[8px] font-mono text-eyay-faint/70 px-1.5 py-px rounded border border-eyay-border/60 bg-eyay-raised/30">
              Sinyal üretimi
            </span>
          </div>
          <p className="text-[11px] font-mono text-eyay-text mt-1 tracking-wide">
            {bull.label} %{bull.probability_pct} · {base.label} %{base.probability_pct} · {bear.label} %{bear.probability_pct}
          </p>
          <p className="text-[9px] font-mono mt-0.5">
            <span style={{ color: domColor }}>● Baskın: {domSc.label}</span>
            <span className="text-eyay-faint"> · olasılıklar sinyal durumundan türetilir</span>
          </p>
        </div>
      </div>

      {/* battle sahnesi */}
      <div className="relative h-[240px] sm:h-[290px] mt-1">
        <Debris />

        {/* merkez enerji patlaması — iki taraf karışımı */}
        <div
          className="absolute left-1/2 top-1/2 pointer-events-none"
          style={{
            width: `${140 + clash * 110}px`,
            height: `${140 + clash * 110}px`,
            transform: "translate(-50%,-50%)",
            background: `radial-gradient(circle, rgba(255,255,255,${0.16 + clash * 0.14}) 0%, ${domRgba}${0.32 + clash * 0.22}) 28%, rgba(34,211,238,0.10) 55%, transparent 72%)`,
            borderRadius: "50%",
            animation: anim ? `sb-clash ${2.8 - clash}s ease-in-out infinite` : undefined,
          }}
          aria-hidden
        />
        {/* çapraz ışık hüzmeleri */}
        <div className="absolute left-1/2 top-1/2 pointer-events-none" aria-hidden
          style={{
            width: "200px", height: "3px",
            transform: "translate(-50%,-50%) rotate(-18deg)",
            background: `linear-gradient(to right, rgba(52,211,153,0.55), rgba(255,255,255,0.7), rgba(248,113,113,0.55))`,
            filter: "blur(2px)",
            opacity: 0.4 + clash * 0.5,
          }} />
        <div className="absolute left-1/2 top-1/2 pointer-events-none" aria-hidden
          style={{
            width: "150px", height: "2px",
            transform: "translate(-50%,-50%) rotate(14deg)",
            background: `linear-gradient(to right, rgba(34,211,238,0.5), rgba(255,255,255,0.6), rgba(251,146,60,0.5))`,
            filter: "blur(2px)",
            opacity: 0.35 + clash * 0.4,
          }} />

        {anim && <Particles side="bull" />}
        {anim && <Particles side="bear" />}

        {/* boğa — sol */}
        <div
          className="absolute left-[-2%] bottom-[6%] w-[48%] h-[84%]"
          style={{ transform: `scale(${0.86 + bullPower * 0.22})`, transformOrigin: "bottom left" }}
        >
          <BullFigure power={bullPower} dominant={dominance === "bull-dominant"} animate={anim} />
        </div>
        {/* ayı — sağ */}
        <div
          className="absolute right-[-2%] bottom-[6%] w-[48%] h-[84%]"
          style={{ transform: `scale(${0.86 + bearPower * 0.22})`, transformOrigin: "bottom right" }}
        >
          <BearFigure power={bearPower} dominant={dominance === "bear-dominant"} animate={anim} />
        </div>

        {/* zemin glow — her figürün altı */}
        <div className="absolute left-[6%] bottom-[8%] w-[34%] h-3 rounded-full pointer-events-none" aria-hidden
          style={{ background: `radial-gradient(ellipse, rgba(52,211,153,${0.18 + bullPower * 0.2}), transparent 70%)`, filter: "blur(4px)" }} />
        <div className="absolute right-[6%] bottom-[8%] w-[34%] h-3 rounded-full pointer-events-none" aria-hidden
          style={{ background: `radial-gradient(ellipse, rgba(248,113,113,${0.18 + bearPower * 0.2}), transparent 70%)`, filter: "blur(4px)" }} />

        {/* merkez baskın senaryo rozeti */}
        <div
          className="absolute left-1/2 top-[58%] pointer-events-none text-center"
          style={{
            transform: "translate(-50%,-50%)",
            animation: anim ? "sb-badge-pulse 2.6s ease-in-out infinite" : undefined,
          }}
        >
          <p
            className="text-sm font-black font-mono uppercase tracking-widest"
            style={{ color: domColor, textShadow: `0 0 14px ${domRgba}0.95), 0 0 34px ${domRgba}0.5)` }}
          >
            {domSc.label}
          </p>
          <p
            className="text-xl font-black font-mono leading-none"
            style={{ color: domColor, textShadow: `0 0 16px ${domRgba}0.95), 0 0 40px ${domRgba}0.55)` }}
          >
            %{domSc.probability_pct}
          </p>
        </div>

        {/* baz denge sütunu — base gücüne göre */}
        <div
          className="absolute left-1/2 top-[12%] bottom-[26%] w-px pointer-events-none"
          style={{
            transform: "translateX(-50%)",
            background: `linear-gradient(to bottom, transparent, rgba(251,191,36,${0.2 + basePower * 0.5}), transparent)`,
          }}
          aria-hidden
        />
      </div>

      {/* alt mini kartlar */}
      <div className="relative grid grid-cols-1 sm:grid-cols-3 gap-2 px-3 pb-2 -mt-2">
        <MiniCard sc={bull} kind="bull" />
        <MiniCard sc={base} kind="base" />
        <MiniCard sc={bear} kind="bear" />
      </div>

      <p className="relative text-[8px] font-mono text-eyay-faint/70 text-center pb-2.5 pt-0.5 border-t border-eyay-border/30 mx-3 mt-1">
        PAPER_SAFE · olasılıklar sinyal durumundan türetilir
      </p>
    </div>
  );
}
