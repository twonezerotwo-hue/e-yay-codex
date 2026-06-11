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

  return (
    <svg viewBox="0 0 320 320" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="lp-body" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor="#0e2a4e" />
          <stop offset="45%"  stopColor="#cfd8e8" />
          <stop offset="55%"  stopColor="#e2e8f0" />
          <stop offset="100%" stopColor="#0e2a4e" />
        </linearGradient>
        <linearGradient id="lp-nose" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor={m.bodyTint} />
          <stop offset="100%" stopColor="#0e2a4e" />
        </linearGradient>
        <radialGradient id="lp-flame" cx="50%" cy="0%" r="70%">
          <stop offset="0%"  stopColor="#ffffff" />
          <stop offset="35%" stopColor={m.thrust} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <radialGradient id="lp-pad-glow" cx="50%" cy="100%" r="65%">
          <stop offset="0%"   stopColor={m.toneSoft} />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <filter id="lp-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3.5" />
        </filter>
      </defs>

      {/* Pad glow */}
      <ellipse cx="160" cy="276" rx="120" ry="22" fill="url(#lp-pad-glow)" />

      {/* Launch ring */}
      <ellipse cx="160" cy="240" rx="84" ry="12" fill="none" stroke={m.toneRing}
               strokeWidth="1" opacity={isLaunching ? 0.7 : 0.35}
               style={animate ? { animation: "lp-breathe 3.5s ease-in-out infinite" } : undefined} />
      <ellipse cx="160" cy="240" rx="62" ry="8" fill="none" stroke={m.toneRing}
               strokeWidth="0.8" opacity="0.45" strokeDasharray="4 4" />

      {/* Roket — lift sırasında yukarı */}
      <g
        style={animate && isLaunching ? { animation: "lp-lift 2s ease-in-out infinite" } : undefined}
        transform={isLaunching ? "translate(0,-6)" : "translate(0,0)"}
      >
        {/* Thrust alevi */}
        {!m.thrustOff && (
          <>
            <path
              d="M 148 226 Q 160 280 172 226 Z"
              fill="url(#lp-flame)"
              opacity={isLaunching ? 1 : 0.85}
              style={animate ? { animation: `lp-flame ${isLaunching ? "0.18s" : "0.45s"} ease-in-out infinite alternate` } : undefined}
            />
            <path
              d="M 152 226 Q 160 260 168 226 Z"
              fill="#fff"
              opacity={isLaunching ? 0.9 : 0.55}
            />
          </>
        )}

        {/* Burun */}
        <path d="M 160 66 L 178 106 L 142 106 Z" fill="url(#lp-nose)" stroke={m.toneRing} strokeWidth="1" />

        {/* Gövde */}
        <rect x="142" y="106" width="36" height="100" rx="3" fill="url(#lp-body)" stroke={m.toneRing} strokeWidth="0.8" />

        {/* Pencere */}
        <circle cx="160" cy="130" r="6.5" fill="#0a1c34" stroke={m.toneRing} strokeWidth="1.5" />
        <circle cx="160" cy="130" r="3" fill={m.bodyTint} opacity="0.6" />
        <circle cx="161" cy="128" r="1.5" fill="#fff" opacity="0.85" />

        {/* Şerit detay */}
        <rect x="142" y="156" width="36" height="3" fill={m.toneRing} opacity="0.35" />
        <rect x="142" y="188" width="36" height="3" fill={m.toneRing} opacity="0.35" />

        {/* Kanatlar */}
        <path d="M 142 186 L 122 226 L 142 216 Z" fill={m.bodyTint} stroke={m.toneRing} strokeWidth="1" opacity="0.92" />
        <path d="M 178 186 L 198 226 L 178 216 Z" fill={m.bodyTint} stroke={m.toneRing} strokeWidth="1" opacity="0.92" />

        {/* Motor */}
        <rect x="148" y="206" width="24" height="20" rx="2" fill="#1a2233" stroke={m.toneRing} strokeWidth="1" />
        <rect x="152" y="210" width="16" height="14" rx="1" fill="#000" />

        {/* Lock overlay (KAPAT) */}
        {isLocked && (
          <g style={animate ? { animation: "lp-blink 1.2s ease-in-out infinite" } : undefined}>
            <rect x="138" y="146" width="44" height="40" rx="3" fill="rgba(248,113,113,0.18)" stroke={m.toneRing} strokeWidth="1.5" />
            <text x="160" y="171" textAnchor="middle" fontSize="11" fill={m.toneRing} fontFamily="monospace" fontWeight="bold">LOCK</text>
          </g>
        )}
      </g>

      {/* BEKLE — duman bulutu */}
      {mode === "BEKLE" && (
        <g opacity="0.5" filter="url(#lp-glow)" style={animate ? { animation: "lp-smoke 4s ease-in-out infinite" } : undefined}>
          <ellipse cx="130" cy="270" rx="22" ry="8" fill="#475569" />
          <ellipse cx="190" cy="272" rx="26" ry="9" fill="#475569" />
          <ellipse cx="160" cy="262" rx="32" ry="10" fill="#64748b" />
        </g>
      )}

      {/* Launch pad zemini */}
      <rect x="60" y="276" width="200" height="6" rx="2" fill="#1a2233" stroke={m.toneRing} strokeWidth="0.5" />
      <rect x="60" y="282" width="200" height="6" rx="1" fill="#0a1220" />

      {/* Tutucu kollar */}
      <line x1="118" y1="276" x2="118" y2="225" stroke={m.toneRing} strokeWidth="2" opacity="0.5" />
      <line x1="202" y1="276" x2="202" y2="225" stroke={m.toneRing} strokeWidth="2" opacity="0.5" />
      <line x1="118" y1="225" x2="130" y2="225" stroke={m.toneRing} strokeWidth="2" opacity="0.5" />
      <line x1="190" y1="225" x2="202" y2="225" stroke={m.toneRing} strokeWidth="2" opacity="0.5" />

      {/* Pad ışıkları */}
      {[78, 110, 210, 242].map((x, i) => (
        <circle key={i} cx={x} cy="276" r="2.4" fill={m.toneRing}
                opacity={animate ? 0.85 : 0.5}
                style={animate ? { animation: `lp-blink ${1.5 + i * 0.2}s ease-in-out infinite` } : undefined} />
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
