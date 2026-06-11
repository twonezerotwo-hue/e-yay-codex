"use client";

/**
 * FAZ 27 — Decision Launch Pad.
 *
 * "Tavsiye Edilen Aksiyon" alanının yeni 3D-hissiyatlı görsel katmanı.
 * Sol: SVG roket + launch pad. Sağ: TAVSİYE EDİLEN AKSİYON kartı (Aksiyon + Neden).
 * Karar üretmez. PAPER_SAFE / NO_EXECUTION. Crash → ErrorBoundary → DecisionBanner.
 */
import { useEffect, useState } from "react";

import type { Decision, RegimeReport } from "@/lib/types";

// ── Mode mapping ──────────────────────────────────────────────────────────────

type Mode = "ONAY" | "BEKLE" | "KÜÇÜLT" | "KAPAT" | "İZLE";

interface ModeMeta {
  label:     Mode;
  toneRing:  string;
  toneSoft:  string;
  borderCls: string;
  bgCls:     string;
  textCls:   string;
  thrust:    string;
  thrustOff: boolean;
  bodyTint:  string;
  action:    string;
  reason:    string;
}

function decisionToMode(d: Decision | undefined): Mode {
  switch (d) {
    case "AÇIL":   return "ONAY";
    case "BEKLE":  return "BEKLE";
    case "KÜÇÜLT": return "KÜÇÜLT";
    case "KAPAT":  return "KAPAT";
    default:       return "İZLE";
  }
}

const MODE_META: Record<Mode, ModeMeta> = {
  ONAY: {
    label: "ONAY", toneRing: "#34d399", toneSoft: "rgba(52,211,153,0.18)",
    borderCls: "border-emerald-600/50", bgCls: "bg-emerald-950/30",
    textCls: "text-emerald-300", thrust: "#34d399", thrustOff: false,
    bodyTint: "#34d399",
    action: "Planlı girişe izin var; risk limitini aşma.",
    reason: "Teknik teyit ve kredi desteği aynı yönde çalışıyor (HYG $78 üstü / VIX sakin).",
  },
  BEKLE: {
    label: "BEKLE", toneRing: "#fbbf24", toneSoft: "rgba(251,191,36,0.18)",
    borderCls: "border-amber-600/50", bgCls: "bg-amber-950/30",
    textCls: "text-amber-300", thrust: "#fbbf24", thrustOff: false,
    bodyTint: "#fbbf24",
    action: "Yeni pozisyon açma; teyit bekle.",
    reason: "BTC güçlü kapanış teyidi yok ($58,000 / $57,889); Brent hâlâ risk primi taşıyor ($85 altı rahatlama).",
  },
  KÜÇÜLT: {
    label: "KÜÇÜLT", toneRing: "#fb923c", toneSoft: "rgba(251,146,60,0.18)",
    borderCls: "border-orange-600/50", bgCls: "bg-orange-950/30",
    textCls: "text-orange-300", thrust: "#fb923c", thrustOff: false,
    bodyTint: "#fb923c",
    action: "Pozisyonu kademeli azalt; panik satış yapma.",
    reason: "Risk/ödül bozuldu; kritik destekler zayıflıyor (BTC $57,889 / HYG $78).",
  },
  KAPAT: {
    label: "KAPAT", toneRing: "#f87171", toneSoft: "rgba(248,113,113,0.18)",
    borderCls: "border-red-600/50", bgCls: "bg-red-950/30",
    textCls: "text-red-300", thrust: "#f87171", thrustOff: true,
    bodyTint: "#f87171",
    action: "Yeni risk alma; koruma moduna geç.",
    reason: "Kritik eşik kırıldı veya blok sinyali aktif (HYG $74 altı / VIX $25 üstü).",
  },
  "İZLE": {
    label: "İZLE", toneRing: "#60a5fa", toneSoft: "rgba(96,165,250,0.18)",
    borderCls: "border-blue-600/50", bgCls: "bg-slate-900/40",
    textCls: "text-blue-300", thrust: "#60a5fa", thrustOff: true,
    bodyTint: "#60a5fa",
    action: "Acele etme; net sinyal bekle.",
    reason: "Sinyaller karışık; belirgin yön üstünlüğü yok.",
  },
};

// ── Rocket SVG ────────────────────────────────────────────────────────────────

function Rocket({ mode, animate }: { mode: Mode; animate: boolean }) {
  const m = MODE_META[mode];
  const isLaunching = mode === "ONAY";
  const isLocked    = mode === "KAPAT";
  const showSmoke   = mode === "BEKLE" || isLaunching;

  return (
    <svg viewBox="0 0 320 320" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* Brushed-metal body — multi-stop highlight */}
        <linearGradient id="rk-body" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor="#0a1626" />
          <stop offset="20%"  stopColor="#475569" />
          <stop offset="42%"  stopColor="#cbd5e1" />
          <stop offset="50%"  stopColor="#e2e8f0" />
          <stop offset="58%"  stopColor="#cbd5e1" />
          <stop offset="80%"  stopColor="#475569" />
          <stop offset="100%" stopColor="#0a1626" />
        </linearGradient>
        <linearGradient id="rk-nose" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor={m.bodyTint} stopOpacity="1" />
          <stop offset="55%" stopColor={m.bodyTint} stopOpacity="0.55" />
          <stop offset="100%" stopColor="#0a1626" />
        </linearGradient>
        <linearGradient id="rk-fin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#1e293b" />
          <stop offset="100%" stopColor={m.bodyTint} stopOpacity="0.85" />
        </linearGradient>
        <linearGradient id="rk-booster" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor="#0e1726" />
          <stop offset="50%"  stopColor="#94a3b8" />
          <stop offset="100%" stopColor="#0e1726" />
        </linearGradient>
        <radialGradient id="rk-flame" cx="50%" cy="0%" r="80%">
          <stop offset="0%"   stopColor="#ffffff" />
          <stop offset="25%"  stopColor={m.thrust} stopOpacity="0.95" />
          <stop offset="70%"  stopColor={m.thrust} stopOpacity="0.35" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <radialGradient id="rk-pad-glow" cx="50%" cy="100%" r="80%">
          <stop offset="0%"   stopColor={m.toneSoft} />
          <stop offset="55%"  stopColor={m.toneSoft} stopOpacity="0.35" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <radialGradient id="rk-smoke" cx="50%" cy="50%" r="60%">
          <stop offset="0%"  stopColor="#94a3b8" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#475569" stopOpacity="0" />
        </radialGradient>
        <filter id="rk-blur" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="2.6" />
        </filter>
        <filter id="rk-soft" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" />
        </filter>
      </defs>

      {/* Pad radial glow */}
      <ellipse cx="160" cy="294" rx="140" ry="28" fill="url(#rk-pad-glow)" />

      {/* Multi-layer launch platform rings */}
      <g style={animate ? { animation: "lp-breathe 3.5s ease-in-out infinite" } : undefined}>
        <ellipse cx="160" cy="262" rx="98" ry="13" fill="none" stroke={m.toneRing}
                 strokeWidth="1" opacity={isLaunching ? 0.85 : 0.45} />
        <ellipse cx="160" cy="262" rx="76" ry="10" fill="none" stroke={m.toneRing}
                 strokeWidth="0.7" strokeDasharray="5 3" opacity="0.55" />
        <ellipse cx="160" cy="262" rx="54" ry="7.5" fill="none" stroke={m.toneRing}
                 strokeWidth="0.6" opacity="0.42" />
      </g>

      {/* Projection beams from pad up — yalnız aktif modlarda */}
      {(isLaunching || mode === "BEKLE") && (
        <g opacity={isLaunching ? 0.55 : 0.28}>
          <line x1="100" y1="262" x2="124" y2="218" stroke={m.toneRing} strokeWidth="0.7" />
          <line x1="220" y1="262" x2="196" y2="218" stroke={m.toneRing} strokeWidth="0.7" />
        </g>
      )}

      {/* Roket — lift animation */}
      <g
        style={animate && isLaunching ? { animation: "lp-lift 2.4s ease-in-out infinite" } : undefined}
        transform={isLaunching ? "translate(0,-8)" : "translate(0,0)"}
      >
        {/* Thrust — multi-layer flame */}
        {!m.thrustOff && (
          <g>
            <path d="M 140 234 Q 160 304 180 234 Z" fill="url(#rk-flame)"
                  opacity={isLaunching ? 0.95 : 0.65} filter="url(#rk-blur)"
                  style={animate ? { animation: `lp-flame ${isLaunching ? "0.16s" : "0.42s"} ease-in-out infinite alternate` } : undefined} />
            <path d="M 148 234 Q 160 282 172 234 Z" fill={m.thrust}
                  opacity={isLaunching ? 0.9 : 0.6} />
            <path d="M 154 234 Q 160 262 166 234 Z" fill="#fff"
                  opacity={isLaunching ? 0.95 : 0.55} />
          </g>
        )}

        {/* Yan booster (sol) */}
        <g>
          <rect x="116" y="150" width="13" height="82" rx="2.5" fill="url(#rk-booster)"
                stroke={m.toneRing} strokeWidth="0.6" opacity="0.95" />
          <rect x="118" y="160" width="9" height="1.8" fill={m.toneRing} opacity="0.35" />
          <rect x="118" y="180" width="9" height="1.8" fill={m.toneRing} opacity="0.35" />
          <path d="M 116 232 L 129 232 L 127 240 L 118 240 Z" fill="#020812" stroke={m.toneRing} strokeWidth="0.6" />
          {!m.thrustOff && (
            <path d="M 117 240 Q 122.5 268 128 240 Z" fill={m.thrust}
                  opacity={isLaunching ? 0.78 : 0.45} filter="url(#rk-blur)" />
          )}
        </g>

        {/* Yan booster (sağ) */}
        <g>
          <rect x="191" y="150" width="13" height="82" rx="2.5" fill="url(#rk-booster)"
                stroke={m.toneRing} strokeWidth="0.6" opacity="0.95" />
          <rect x="193" y="160" width="9" height="1.8" fill={m.toneRing} opacity="0.35" />
          <rect x="193" y="180" width="9" height="1.8" fill={m.toneRing} opacity="0.35" />
          <path d="M 191 232 L 204 232 L 202 240 L 193 240 Z" fill="#020812" stroke={m.toneRing} strokeWidth="0.6" />
          {!m.thrustOff && (
            <path d="M 192 240 Q 197.5 268 203 240 Z" fill={m.thrust}
                  opacity={isLaunching ? 0.78 : 0.45} filter="url(#rk-blur)" />
          )}
        </g>

        {/* Burun — sharp tip + highlight */}
        <path d="M 160 38 L 178 78 L 142 78 Z" fill="url(#rk-nose)" stroke={m.toneRing} strokeWidth="0.8" />
        <line x1="160" y1="40" x2="160" y2="76" stroke="#fff" strokeWidth="0.5" opacity="0.32" />

        {/* Ana gövde */}
        <rect x="142" y="78" width="36" height="128" rx="3" fill="url(#rk-body)"
              stroke={m.toneRing} strokeWidth="0.7" />
        {/* Body inner highlight stripe */}
        <line x1="160" y1="80" x2="160" y2="204" stroke="#fff" strokeWidth="0.35" opacity="0.18" />

        {/* Pencere — detaylı bolts */}
        <circle cx="160" cy="104" r="7.5" fill="#020812" stroke={m.toneRing} strokeWidth="1.4" />
        <circle cx="160" cy="104" r="5.2" fill={m.bodyTint} opacity="0.42" />
        <circle cx="161" cy="102" r="2" fill="#fff" opacity="0.85" />
        {[0, 60, 120, 180, 240, 300].map(a => {
          const rad = (a * Math.PI) / 180;
          const cx = 160 + Math.cos(rad) * 7.5;
          const cy = 104 + Math.sin(rad) * 7.5;
          return <circle key={a} cx={cx} cy={cy} r="0.55" fill={m.toneRing} opacity="0.7" />;
        })}

        {/* Şerit detaylar + logo bandı */}
        <rect x="142" y="130" width="36" height="3" fill={m.toneRing} opacity="0.5" />
        <rect x="142" y="160" width="36" height="1.6" fill="#94a3b8" opacity="0.4" />
        <rect x="142" y="188" width="36" height="3" fill={m.toneRing} opacity="0.5" />
        <ellipse cx="160" cy="146" rx="9" ry="3" fill="none" stroke={m.toneRing} strokeWidth="0.6" opacity="0.55" />
        <text x="160" y="148" textAnchor="middle" fontSize="3.8" fill={m.toneRing}
              fontFamily="monospace" fontWeight="bold" opacity="0.78">E·YAY</text>

        {/* Kanatlar — fin + trailing edge highlight */}
        <path d="M 142 186 L 116 232 L 142 218 Z" fill="url(#rk-fin)" stroke={m.toneRing} strokeWidth="0.8" />
        <path d="M 178 186 L 204 232 L 178 218 Z" fill="url(#rk-fin)" stroke={m.toneRing} strokeWidth="0.8" />
        <line x1="142" y1="186" x2="116" y2="232" stroke={m.toneRing} strokeWidth="0.5" opacity="0.65" />
        <line x1="178" y1="186" x2="204" y2="232" stroke={m.toneRing} strokeWidth="0.5" opacity="0.65" />

        {/* Motor + nozzle */}
        <path d="M 144 206 L 176 206 L 172 236 L 148 236 Z" fill="#0a0f1a"
              stroke={m.toneRing} strokeWidth="0.9" />
        <path d="M 150 210 L 170 210 L 167 232 L 153 232 Z" fill="#000" />
        {!m.thrustOff && (
          <ellipse cx="160" cy="232" rx="9" ry="2.4" fill={m.thrust}
                   opacity={isLaunching ? 0.9 : 0.55} filter="url(#rk-blur)" />
        )}

        {/* Lock overlay (KAPAT) */}
        {isLocked && (
          <g style={animate ? { animation: "lp-blink 1.2s ease-in-out infinite" } : undefined}>
            <rect x="132" y="118" width="56" height="48" rx="3"
                  fill="rgba(248,113,113,0.20)" stroke={m.toneRing} strokeWidth="1.6" />
            <text x="160" y="148" textAnchor="middle" fontSize="14"
                  fill={m.toneRing} fontFamily="monospace" fontWeight="bold">LOCK</text>
            {/* Hazard stripes */}
            <line x1="132" y1="170" x2="188" y2="170" stroke={m.toneRing}
                  strokeWidth="2" strokeDasharray="6 4" opacity="0.65" />
          </g>
        )}
      </g>

      {/* Duman — multi-layer blurred */}
      {showSmoke && (
        <g filter="url(#rk-soft)"
           style={animate ? { animation: "lp-smoke 4.5s ease-in-out infinite" } : undefined}>
          <ellipse cx="160" cy="278" rx="48" ry="14" fill="url(#rk-smoke)" opacity="0.85" />
          <ellipse cx="118" cy="284" rx="32" ry="11" fill="url(#rk-smoke)" />
          <ellipse cx="202" cy="286" rx="34" ry="12" fill="url(#rk-smoke)" />
          <ellipse cx="92"  cy="292" rx="22" ry="8"  fill="url(#rk-smoke)" opacity="0.55" />
          <ellipse cx="228" cy="294" rx="24" ry="9"  fill="url(#rk-smoke)" opacity="0.55" />
        </g>
      )}

      {/* Pad — çok katmanlı zemin */}
      <rect x="50" y="266" width="220" height="6"  rx="2" fill="#1e293b" stroke={m.toneRing} strokeWidth="0.5" />
      <rect x="50" y="272" width="220" height="8"  rx="1" fill="#0a1220" />
      <rect x="50" y="280" width="220" height="3"  rx="1" fill="#020812" />

      {/* Pad surface grid */}
      {[80, 110, 160, 210, 240].map((x) => (
        <line key={x} x1={x} y1="266" x2={x} y2="272" stroke={m.toneRing} strokeWidth="0.4" opacity="0.5" />
      ))}

      {/* Launch clamp arms — detaylı */}
      <g opacity="0.72">
        <line x1="106" y1="266" x2="106" y2="206" stroke={m.toneRing} strokeWidth="2.1" />
        <line x1="106" y1="206" x2="124" y2="206" stroke={m.toneRing} strokeWidth="2.1" />
        <rect x="98"  y="262" width="16" height="6" rx="1" fill="#1e293b" stroke={m.toneRing} strokeWidth="0.6" />
        <line x1="214" y1="266" x2="214" y2="206" stroke={m.toneRing} strokeWidth="2.1" />
        <line x1="214" y1="206" x2="196" y2="206" stroke={m.toneRing} strokeWidth="2.1" />
        <rect x="206" y="262" width="16" height="6" rx="1" fill="#1e293b" stroke={m.toneRing} strokeWidth="0.6" />
        {/* Cable joints */}
        <line x1="106" y1="228" x2="116" y2="228" stroke={m.toneRing} strokeWidth="1" opacity="0.5" />
        <line x1="214" y1="228" x2="204" y2="228" stroke={m.toneRing} strokeWidth="1" opacity="0.5" />
      </g>

      {/* Pad ışıkları — küçük blinking ledler + halo */}
      {[64, 92, 228, 256].map((x, i) => (
        <g key={i}>
          <circle cx={x} cy="266" r="4.4" fill="none" stroke={m.toneRing} strokeWidth="0.45" opacity="0.32" />
          <circle cx={x} cy="266" r="2.6" fill={m.toneRing}
                  opacity={animate ? 0.9 : 0.5}
                  style={animate ? { animation: `lp-blink ${1.4 + i * 0.25}s ease-in-out infinite` } : undefined} />
        </g>
      ))}
    </svg>
  );
}

// ── Component ────────────────────────────────────────────────────────────────

interface Props { report: RegimeReport; }

export default function ActionSignalLaunchLayer({ report }: Props) {
  const [animate, setAnimate] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    return () => mq.removeEventListener?.("change", onMQ);
  }, []);

  const mode = decisionToMode(report?.decision);
  const m    = MODE_META[mode];
  const time = report?.generated_at
    ? new Date(report.generated_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
    : "—";

  return (
    <div
      data-testid="action-signal-launch"
      className={`w-full max-w-full min-w-0 overflow-hidden rounded-2xl border ${m.borderCls} ${m.bgCls}`}
      style={{ boxShadow: animate ? `0 0 26px ${m.toneSoft}, inset 0 1px 0 ${m.toneRing}44` : `0 0 10px ${m.toneSoft}` }}
    >
      <style>{`
        @keyframes lp-lift    { 0%,100%{transform:translateY(-6px)} 50%{transform:translateY(-12px)} }
        @keyframes lp-flame   { from{transform:scaleY(0.85);opacity:0.85} to{transform:scaleY(1.18);opacity:1} }
        @keyframes lp-blink   { 0%,100%{opacity:0.45} 50%{opacity:1} }
        @keyframes lp-smoke   { 0%,100%{opacity:0.35;transform:translateY(0)} 50%{opacity:0.6;transform:translateY(-3px)} }
        @keyframes lp-fade    { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
        @keyframes lp-breathe { 0%,100%{opacity:0.55;transform:scaleX(1)} 50%{opacity:0.9;transform:scaleX(1.04)} }
        @keyframes lp-scan    { 0%{transform:translateY(-100%)} 100%{transform:translateY(100%)} }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-cyan-500/15 bg-gradient-to-r from-black/40 via-cyan-950/15 to-black/40">
        <div className="flex items-center gap-2 min-w-0">
          <span aria-hidden="true" className={m.textCls}
                style={animate ? { animation: "lp-fade 0.6s ease" } : undefined}>🚀</span>
          <div className="min-w-0">
            <p className="text-[10px] font-mono font-bold text-cyan-100 uppercase tracking-[0.22em] truncate">
              Decision Launch Pad
            </p>
            <p className="text-[8px] font-mono text-cyan-400/60 truncate">
              AI visual layer · PAPER_SAFE
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono font-black uppercase tracking-widest ${m.borderCls}`}
                style={{ color: m.toneRing, background: m.toneSoft }}>
            {m.label}
          </span>
          <span className="font-mono text-[10px] text-eyay-faint">{time}</span>
        </div>
      </div>

      {/* Body */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_340px] gap-0">
        {/* Sol: Rocket scene */}
        <div className="relative p-3 overflow-hidden h-[340px]"
             style={{ background: "radial-gradient(ellipse 85% 60% at 50% 95%, rgba(34,211,238,0.06), transparent 65%)" }}>
          {/* Mission control yıldız izleri */}
          <div aria-hidden="true" className="absolute inset-0 pointer-events-none opacity-40"
               style={{
                 backgroundImage:
                   "radial-gradient(1px 1px at 20% 30%, #94a3b8 50%, transparent), " +
                   "radial-gradient(1px 1px at 70% 20%, #cbd5e1 50%, transparent), " +
                   "radial-gradient(1px 1px at 40% 70%, #94a3b8 50%, transparent), " +
                   "radial-gradient(1px 1px at 85% 60%, #cbd5e1 50%, transparent)",
               }}
          />
          {/* Hafif grid */}
          <div aria-hidden="true" className="absolute inset-0 pointer-events-none opacity-20"
               style={{
                 backgroundImage:
                   "linear-gradient(rgba(34,211,238,0.10) 1px, transparent 1px), " +
                   "linear-gradient(90deg, rgba(34,211,238,0.10) 1px, transparent 1px)",
                 backgroundSize: "30px 30px",
                 maskImage: "radial-gradient(ellipse at 50% 70%, black 30%, transparent 80%)",
                 WebkitMaskImage: "radial-gradient(ellipse at 50% 70%, black 30%, transparent 80%)",
               }}
          />
          {/* Köşe brackets — institutional terminal */}
          <span aria-hidden="true" className="absolute top-2 left-2 w-3 h-3 border-t border-l border-cyan-400/40" />
          <span aria-hidden="true" className="absolute top-2 right-2 w-3 h-3 border-t border-r border-cyan-400/40" />
          <span aria-hidden="true" className="absolute bottom-2 left-2 w-3 h-3 border-b border-l border-cyan-400/40" />
          <span aria-hidden="true" className="absolute bottom-2 right-2 w-3 h-3 border-b border-r border-cyan-400/40" />

          {/* Scanline */}
          {animate && (
            <div aria-hidden="true" className="absolute inset-x-0 top-0 h-12 pointer-events-none"
                 style={{
                   background: "linear-gradient(180deg, transparent, rgba(34,211,238,0.05) 50%, transparent)",
                   animation: "lp-scan 8s linear infinite",
                 }}
            />
          )}
          <Rocket mode={mode} animate={animate} />
        </div>

        {/* Sağ: Tavsiye Edilen Aksiyon kartı */}
        <div className="border-t lg:border-t-0 lg:border-l border-cyan-500/15 p-4 bg-black/30 flex flex-col"
             key={mode}
             style={animate ? { animation: "lp-fade 0.5s ease" } : undefined}>
          <p className="text-[9px] font-mono font-bold text-cyan-300/80 uppercase tracking-[0.24em] mb-2">
            ✦ Tavsiye Edilen Aksiyon
          </p>

          {/* Büyük durum */}
          <p className={`font-mono font-black text-3xl leading-none tracking-widest ${m.textCls} mb-3`}
             style={animate ? { textShadow: `0 0 12px ${m.toneRing}55` } : undefined}>
            {m.label}
          </p>

          <div className="space-y-3">
            <div>
              <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest mb-1">
                Aksiyon
              </p>
              <p className={`text-[12px] font-mono font-semibold leading-snug ${m.textCls}`}>
                {m.action}
              </p>
            </div>

            <div>
              <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest mb-1">
                Neden
              </p>
              <p className="text-[10px] font-mono text-eyay-dim leading-snug">
                {m.reason}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-eyay-border/30 bg-black/30">
        <p className="text-[8px] font-mono text-eyay-faint/55 text-center">
          PAPER_SAFE · NO_EXECUTION · sadece görselleştirme
        </p>
      </div>
    </div>
  );
}
