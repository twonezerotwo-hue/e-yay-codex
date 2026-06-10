"use client";

/**
 * FAZ 17 — Command Signal Cards Layer (Holographic War Room).
 *
 * Katman 1 komut sinyallerini 3D/holografik kart görünümünde sunar.
 * Veri kaynağı: parent'tan gelen signals + techInsights propları (AssetGrid
 * ile birebir aynı). Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 * Crash → CommandSignalsErrorBoundary → legacy AssetGrid.
 */
import { useEffect, useState } from "react";

import MacroRiskPulse from "@/components/MacroRiskPulse";
import type { AssetSignal, MacroLayer, RiskAppetiteLayer, TechnicalInsight } from "@/lib/types";

// ── Config ────────────────────────────────────────────────────────────────────

const PRIMARY: Array<{ code: string; icon: string; name: string }> = [
  { code: "BTCUSD", icon: "₿",  name: "Bitcoin" },
  { code: "XAUUSD", icon: "◆",  name: "Altın" },
  { code: "XAGUSD", icon: "Ag", name: "Gümüş" },
  { code: "XCUUSD", icon: "Cu", name: "Bakır" },
  { code: "BRENT",  icon: "🛢", name: "Brent" },
];

const SUPPORT_CODES = ["DXY", "VIX", "SP500", "QQQ", "HYG", "ETHUSD", "REAL_YIELD"];

type Tone = "approved" | "waiting" | "neutral" | "risk";

const TONE: Record<Tone, {
  ring: string; border: string; glow: string; badge: string; text: string; label: string;
}> = {
  approved: { ring: "#34d399", border: "border-emerald-500/60", glow: "0 0 26px rgba(52,211,153,0.30)",  badge: "bg-emerald-950/60 border-emerald-600/60 text-emerald-200", text: "text-emerald-300", label: "ONAYLI" },
  waiting:  { ring: "#fbbf24", border: "border-amber-500/50",   glow: "0 0 22px rgba(251,191,36,0.22)",  badge: "bg-amber-950/50 border-amber-600/50 text-amber-200",      text: "text-amber-300",   label: "BEKLİYOR" },
  neutral:  { ring: "#60a5fa", border: "border-cyan-700/40",    glow: "0 0 16px rgba(34,211,238,0.14)",  badge: "bg-slate-900/60 border-slate-600/50 text-slate-300",      text: "text-slate-300",   label: "NÖTR" },
  risk:     { ring: "#f87171", border: "border-red-600/60",     glow: "0 0 24px rgba(248,113,113,0.28)", badge: "bg-red-950/60 border-red-600/60 text-red-200",            text: "text-red-300",     label: "BLOKLU" },
};

function toneOf(s: AssetSignal): Tone {
  if (s.status === "BLOCKING") return "risk";
  if (s.status === "CONFIRMED") return "approved";
  if (s.status === "PENDING") return "waiting";
  return "neutral";
}

function dirOf(s: AssetSignal): { label: string; cls: string } {
  const a = s.asset_action;
  if (a === "LONG")        return { label: "▲ LONG",       cls: "bg-emerald-600/25 text-emerald-200 border-emerald-500/50" };
  if (a === "LONG_AWAIT")  return { label: "▲ LONG SETUP", cls: "bg-cyan-600/20 text-cyan-200 border-cyan-500/40" };
  if (a === "SHORT")       return { label: "▼ SHORT",      cls: "bg-red-600/25 text-red-200 border-red-500/50" };
  if (a === "SHORT_AWAIT") return { label: "▼ SHORT SETUP", cls: "bg-rose-600/20 text-rose-200 border-rose-500/40" };
  if (a === "AVOID")       return { label: "✕ KAÇIN",      cls: "bg-red-950/50 text-red-300 border-red-700/40" };
  return { label: "◎ WATCH", cls: "bg-slate-800/60 text-slate-300 border-slate-600/40" };
}

function fmtVal(v: number | null, unit: string): string {
  if (v == null) return "—";
  const s = v >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toFixed(2);
  return unit === "USD" || unit === "$" ? `$${s}` : `${s}${unit ? ` ${unit}` : ""}`;
}

// ── Confidence ring ───────────────────────────────────────────────────────────

function ScoreRing({ score, color, size }: { score: number | null; color: string; size: number }) {
  const r = size / 2 - 4;
  const c = 2 * Math.PI * r;
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth="3" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3"
        strokeLinecap="round" strokeDasharray={`${(pct / 100) * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: "stroke-dasharray 0.8s ease" }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
        fontSize={size * 0.3} fontFamily="monospace" fontWeight="700" fill={color}>
        {score == null ? "—" : Math.round(pct)}
      </text>
    </svg>
  );
}

// ── Holo card ─────────────────────────────────────────────────────────────────

function HoloCard({
  signal, tech, icon, selected, animate, onClick,
}: {
  signal: AssetSignal; tech?: TechnicalInsight; icon: string; name: string;
  selected: boolean; animate: boolean; onClick: () => void;
}) {
  const tone = TONE[toneOf(signal)];
  const dir  = dirOf(signal);
  const delta = signal.delta_7d_pct;
  return (
    <div className="relative" style={{ perspective: "1100px" }}>
      {/* Radial halo behind card */}
      <div
        aria-hidden="true"
        className="absolute -inset-3 pointer-events-none rounded-3xl"
        style={{
          background: `radial-gradient(ellipse at 50% 60%, ${tone.ring}${selected ? "33" : "14"}, transparent 70%)`,
          filter: "blur(6px)",
          opacity: selected ? 1 : 0.55,
          transition: "all 0.5s ease",
        }}
      />
      <button
        type="button"
        onClick={onClick}
        data-testid={`cs-card-${signal.asset_code}`}
        className={`relative w-full text-left rounded-xl border backdrop-blur-md px-2.5 pt-2 pb-2 transition-all duration-500 h-[150px] ${tone.border} ${
          selected ? "z-20" : "opacity-90 hover:opacity-100"
        }`}
        style={{
          background: selected
            ? `linear-gradient(160deg, rgba(8,32,58,0.95), rgba(3,12,26,0.95)), radial-gradient(circle at 50% 0%, ${tone.ring}22, transparent 60%)`
            : "linear-gradient(165deg, rgba(8,24,46,0.78), rgba(3,12,26,0.92))",
          boxShadow: selected
            ? `${tone.glow}, 0 18px 30px -10px ${tone.ring}55, inset 0 1px 0 ${tone.ring}33`
            : `0 0 10px rgba(34,211,238,0.10), inset 0 1px 0 rgba(255,255,255,0.04)`,
          transform: selected
            ? "translateY(-5px) translateZ(18px) rotateX(-5deg) scale(1.04)"
            : "translateZ(0) rotateX(2deg) scale(0.96)",
          transformStyle: "preserve-3d",
          animation: animate ? `cs-float ${selected ? "5s" : "7s"} ease-in-out infinite${selected ? ", cs-breathe 3s ease-in-out infinite" : ""}` : undefined,
        }}
      >
        {/* Top reflection sheen */}
        <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px rounded-t-2xl"
             style={{ background: `linear-gradient(90deg, transparent, ${tone.ring}, transparent)` }} />

        {/* Header: icon + code + status dot */}
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-sm leading-none">{icon}</span>
          <p className="text-[11px] font-mono font-bold text-cyan-50 tracking-wider leading-none">
            {signal.asset_code}
          </p>
          <span aria-hidden="true" className="ml-auto w-1.5 h-1.5 rounded-full shrink-0"
                style={{ background: tone.ring, boxShadow: animate ? `0 0 6px ${tone.ring}` : undefined }} />
        </div>

        {/* Price */}
        <p className="text-[15px] font-mono font-bold leading-tight tracking-tight" style={{ color: tone.ring, textShadow: `0 0 8px ${tone.ring}44` }}>
          {fmtVal(signal.value, signal.unit)}
        </p>

        {/* Delta + status label */}
        <div className="flex items-center justify-between mt-0.5">
          {delta != null ? (
            <p className={`text-[9px] font-mono font-semibold ${delta >= 0 ? "text-emerald-300" : "text-red-300"}`}>
              {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}%
            </p>
          ) : <span />}
          <span className={`rounded px-1 py-0.5 text-[7px] font-mono font-black border ${tone.badge}`}>
            {tone.label}
          </span>
        </div>

        {/* Confidence ring + dir badge */}
        <div className="flex items-center justify-between mt-1.5">
          <ScoreRing score={tech?.technical_score ?? null} color={tone.ring} size={selected ? 40 : 36} />
          <span className={`rounded-md border px-1.5 py-0.5 text-[8px] font-mono font-bold ${dir.cls}`}>
            {dir.label}
          </span>
        </div>
      </button>

      {/* Hologram beam — kart zemine bağlanır */}
      <div
        aria-hidden="true"
        className="absolute left-1/2 top-full -translate-x-1/2 pointer-events-none hidden sm:block"
        style={{
          width: selected ? "48px" : "22px",
          height: selected ? "38px" : "28px",
          background: `linear-gradient(180deg, ${tone.ring}${selected ? "66" : "33"}, ${tone.ring}11, transparent)`,
          clipPath: "polygon(34% 0, 66% 0, 100% 100%, 0 100%)",
          filter: selected ? `drop-shadow(0 0 12px ${tone.ring})` : undefined,
          opacity: selected ? 1 : 0.45,
          transition: "all 0.5s ease",
        }}
      />
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function Row({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div className="flex justify-between gap-2 text-[9px] font-mono py-0.5 border-b border-white/5">
      <span className="text-eyay-faint">{k}</span>
      <span className={cls ?? "text-eyay-dim"}>{v}</span>
    </div>
  );
}

function DetailPanel({ signal, tech }: { signal: AssetSignal; tech?: TechnicalInsight }) {
  const tone = TONE[toneOf(signal)];
  const dir  = dirOf(signal);
  return (
    <div className="rounded-2xl border border-eyay-border/40 bg-black/30 p-3 space-y-2 overflow-y-auto max-h-full" data-testid="cs-detail-panel" style={{ scrollbarWidth: "thin" }}>
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-mono font-bold text-eyay-text">{signal.asset_code}</p>
        <span className={`rounded-md border px-1.5 py-0.5 text-[8px] font-mono font-bold ${dir.cls}`}>{dir.label}</span>
      </div>
      <p className={`text-lg font-mono font-bold ${tone.text}`}>{fmtVal(signal.value, signal.unit)}</p>
      <p className="text-[9px] text-eyay-faint leading-snug line-clamp-4">{signal.reason}</p>
      {tech && (
        <div className="pt-1">
          <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest mb-1">Teknik · {tech.timeframe}</p>
          <Row k="Direnç"  v={tech.levels.resistance.toLocaleString("en-US")} />
          <Row k="Destek"  v={tech.levels.support.toLocaleString("en-US")} />
          <Row k="Yapı"    v={tech.structure} cls={tech.structure === "BULLISH" ? "text-emerald-300" : tech.structure === "BEARISH" ? "text-red-300" : "text-slate-300"} />
          {tech.rsi_14 != null && <Row k="RSI 14" v={tech.rsi_14.toFixed(0)} />}
          {tech.vwap_position && tech.vwap_position !== "unavailable" && (
            <Row k="VWAP" v={tech.vwap_position === "above" ? "Üstünde" : tech.vwap_position === "below" ? "Altında" : "Üzerinde"} />
          )}
          {tech.ema_stack && tech.ema_stack !== "unavailable" && <Row k="EMA Dizilim" v={tech.ema_stack} />}
          <Row k="Teknik Skor" v={`${tech.technical_score}/100`} cls={tone.text} />
        </div>
      )}
      {signal.action_trigger && (
        <p className="text-[8px] font-mono text-cyan-300/70 border border-cyan-800/30 bg-cyan-950/20 rounded-md px-2 py-1">
          ⚡ {signal.action_trigger}
        </p>
      )}
      {signal.recommended_timeframe && (
        <p className="text-[8px] font-mono text-eyay-faint">
          Plan: {signal.recommended_timeframe.toUpperCase()}
          {signal.recheck_interval_minutes ? ` · kontrol ${signal.recheck_interval_minutes}dk` : ""}
        </p>
      )}
    </div>
  );
}

// ── Support strip ─────────────────────────────────────────────────────────────

function SupportBar({ s }: { s: AssetSignal }) {
  const tone  = TONE[toneOf(s)];
  const delta = s.delta_7d_pct;
  return (
    <div className={`rounded-lg border px-2 py-1 bg-black/40 backdrop-blur-sm ${tone.border} shrink-0 flex items-center gap-2`}>
      <span aria-hidden="true" className="w-1 h-1 rounded-full" style={{ background: tone.ring, boxShadow: `0 0 4px ${tone.ring}` }} />
      <p className="text-[9px] font-mono font-bold text-eyay-dim">{s.asset_code}</p>
      <p className="text-[9px] font-mono" style={{ color: tone.ring }}>{fmtVal(s.value, s.unit)}</p>
      {delta != null && (
        <p className={`text-[8px] font-mono ${delta >= 0 ? "text-emerald-300" : "text-red-300"}`}>
          {delta >= 0 ? "▲" : "▼"}{Math.abs(delta).toFixed(1)}%
        </p>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

interface Props {
  signals:      AssetSignal[];
  techInsights?: TechnicalInsight[];
  /** FAZ 22 — Macro/Risk Pulse banner için opsiyonel. */
  macro?:       MacroLayer;
  appetite?:    RiskAppetiteLayer;
}

export default function CommandSignalCardsLayer({ signals, techInsights = [], macro, appetite }: Props) {
  const [selected, setSelected] = useState(0);
  const [animate,  setAnimate]  = useState(false);
  const [isMobile, setMobile]   = useState(false);
  const [paused,   setPaused]   = useState(false);

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

  const byCode   = Object.fromEntries(signals.map(s => [s.asset_code, s]));
  const techBy   = Object.fromEntries(techInsights.map(t => [t.asset_code, t]));
  const primary  = PRIMARY.filter(p => byCode[p.code] != null);
  const supports = SUPPORT_CODES.map(c => byCode[c]).filter((s): s is AssetSignal => s != null);

  // Auto-rotate selected card every 4s (desktop, animate on, not paused).
  useEffect(() => {
    if (!animate || isMobile || paused || primary.length <= 1) return;
    const t = setInterval(() => {
      setSelected(s => (s + 1) % primary.length);
    }, 4000);
    return () => clearInterval(t);
  }, [animate, isMobile, paused, primary.length]);

  if (primary.length === 0) {
    return (
      <div className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-5" data-testid="cs-cards-layer">
        <p className="text-xs text-eyay-faint italic">Komut sinyali kaydı yok.</p>
      </div>
    );
  }

  const safeSel  = Math.min(selected, primary.length - 1);
  const selCode  = primary[safeSel].code;
  const selSig   = byCode[selCode];

  return (
    <div
      className="w-full max-w-full min-w-0 h-full rounded-2xl border border-eyay-border bg-[#030c1a] overflow-hidden flex flex-col"
      data-testid="cs-cards-layer"
    >
      <style>{`
        @keyframes cs-float   { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
        @keyframes cs-breathe { 0%,100%{filter:brightness(1);opacity:0.85} 50%{filter:brightness(1.25);opacity:1} }
        @keyframes cs-spin    { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        @keyframes cs-scan    { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
        @keyframes cs-pulsering { 0%{transform:scale(0.95);opacity:0.6} 100%{transform:scale(1.4);opacity:0} }
        @keyframes cs-ticker  { from{transform:translateX(0)} to{transform:translateX(-50%)} }
      `}</style>

      {/* Header */}
      <div className="relative flex items-center justify-between px-3 py-2 border-b border-cyan-500/20 bg-gradient-to-r from-black/50 via-cyan-950/20 to-black/50">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400/80" style={animate ? { animation: "cs-breathe 3s ease-in-out infinite" } : undefined}>◈</span>
          <div>
            <p className="text-[11px] font-mono font-bold text-cyan-100 uppercase tracking-[0.22em]">
              Holographic Command Signals
            </p>
            <p className="text-[9px] font-mono text-cyan-400/70 mt-0.5">
              {primary.length} ana asset · destek göstergeleri · PAPER_SAFE
            </p>
          </div>
        </div>
        <span className="rounded-md border border-cyan-500/40 bg-cyan-950/40 px-2 py-0.5 text-[8px] font-mono text-cyan-200 uppercase tracking-widest"
              style={animate ? { boxShadow: "0 0 12px rgba(34,211,238,0.25)" } : undefined}>
          NO_EXECUTION
        </span>
      </div>

      <div className={isMobile ? "p-3 space-y-3" : "grid grid-cols-[minmax(0,1fr)_210px] gap-0 items-stretch"}>
        {/* Sol: holo sahne */}
        <div className="relative px-3 pt-3 pb-2 overflow-hidden"
             style={{
               background:
                 "radial-gradient(ellipse 90% 70% at 50% 110%, rgba(34,211,238,0.10), transparent 65%), " +
                 "linear-gradient(180deg, rgba(3,12,26,0) 0%, rgba(34,211,238,0.025) 100%)",
             }}>
          {/* Grid katmanı */}
          <div aria-hidden="true" className="absolute inset-0 pointer-events-none opacity-50"
               style={{
                 backgroundImage:
                   "linear-gradient(rgba(34,211,238,0.06) 1px, transparent 1px), " +
                   "linear-gradient(90deg, rgba(34,211,238,0.06) 1px, transparent 1px)",
                 backgroundSize: "44px 44px",
                 maskImage: "radial-gradient(ellipse at 50% 60%, black 30%, transparent 80%)",
                 WebkitMaskImage: "radial-gradient(ellipse at 50% 60%, black 30%, transparent 80%)",
               }}
          />
          {/* Scan beam */}
          {animate && !isMobile && (
            <div aria-hidden="true" className="absolute inset-y-0 left-0 w-[40%] pointer-events-none"
                 style={{
                   background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.07), transparent)",
                   animation: "cs-scan 8s ease-in-out infinite",
                 }}
            />
          )}
          {/* Corner brackets */}
          {!isMobile && (
            <>
              <span aria-hidden="true" className="absolute top-2 left-2 w-3 h-3 border-t border-l border-cyan-400/40" />
              <span aria-hidden="true" className="absolute top-2 right-2 w-3 h-3 border-t border-r border-cyan-400/40" />
              <span aria-hidden="true" className="absolute bottom-2 left-2 w-3 h-3 border-b border-l border-cyan-400/40" />
              <span aria-hidden="true" className="absolute bottom-2 right-2 w-3 h-3 border-b border-r border-cyan-400/40" />
            </>
          )}

          {/* Kartlar — Desktop: 3D carousel; Mobile: prev/next + scroll */}
          {!isMobile ? (
            <div
              className="relative z-10 h-[240px] overflow-hidden"
              style={{ perspective: "1500px", perspectiveOrigin: "50% 38%" }}
              onMouseEnter={() => setPaused(true)}
              onMouseLeave={() => setPaused(false)}
              onFocusCapture={() => setPaused(true)}
              onBlurCapture={() => setPaused(false)}
            >
              {primary.map((p, i) => {
                const n = primary.length;
                let offset = i - safeSel;
                if (offset > n / 2) offset -= n;
                if (offset < -n / 2) offset += n;
                const abs = Math.abs(offset);
                // Pixel-tabanlı fan-out — container'a göre güvenli
                const txPx = offset === 0 ? 0 : offset > 0
                  ? (abs === 1 ? 220 : 400)
                  : -(abs === 1 ? 220 : 400);
                const tz   = -abs * 110;
                const ry   = offset * -10;
                const sc   = abs === 0 ? 1.03 : abs === 1 ? 0.88 : 0.76;
                const op   = abs === 0 ? 1 : abs === 1 ? 0.88 : 0.62;
                return (
                  <div
                    key={p.code}
                    className="absolute top-2 left-1/2 transition-all duration-700 ease-out"
                    style={{
                      width: "210px",
                      marginLeft: "-105px",
                      transform: `translateX(${txPx}px) translateZ(${tz}px) rotateY(${ry}deg) scale(${sc})`,
                      opacity: op,
                      zIndex: 100 - abs,
                      transformStyle: "preserve-3d",
                      pointerEvents: abs > 2 ? "none" : "auto",
                    }}
                  >
                    <HoloCard
                      signal={byCode[p.code]}
                      tech={techBy[p.code]}
                      icon={p.icon}
                      name={p.name}
                      selected={i === safeSel}
                      animate={animate}
                      onClick={() => setSelected(i)}
                    />
                  </div>
                );
              })}
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-2 px-1">
                <button
                  type="button"
                  onClick={() => setSelected((safeSel - 1 + primary.length) % primary.length)}
                  className="rounded-md border border-cyan-700/40 bg-cyan-950/30 px-2 py-0.5 text-cyan-200 text-[11px] font-mono"
                  aria-label="Previous"
                >‹</button>
                <span className="text-[9px] font-mono text-cyan-300/70">
                  {safeSel + 1}/{primary.length}
                </span>
                <button
                  type="button"
                  onClick={() => setSelected((safeSel + 1) % primary.length)}
                  className="rounded-md border border-cyan-700/40 bg-cyan-950/30 px-2 py-0.5 text-cyan-200 text-[11px] font-mono"
                  aria-label="Next"
                >›</button>
              </div>
              <div className="flex gap-3 overflow-x-auto pb-6 -mx-1 px-1 relative z-10 snap-x snap-mandatory">
                {primary.map((p, i) => (
                  <div key={p.code} className="w-[180px] shrink-0 snap-center">
                    <HoloCard
                      signal={byCode[p.code]}
                      tech={techBy[p.code]}
                      icon={p.icon}
                      name={p.name}
                      selected={i === safeSel}
                      animate={false}
                      onClick={() => setSelected(i)}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Holografik AI Trading Operations platformu — premium katmanlı */}
          {!isMobile && (
            <div aria-hidden="true" className="relative h-[58px] mt-1 overflow-hidden">
              {/* Dış halka — soft bloom */}
              <div
                className="absolute left-1/2 top-0 -translate-x-1/2 rounded-[50%]"
                style={{
                  width: "88%", height: "92px",
                  background: "radial-gradient(ellipse at center, rgba(34,211,238,0.18), rgba(34,211,238,0.05) 55%, transparent 78%)",
                  filter: "blur(0.4px)",
                  animation: animate ? "cs-breathe 4.5s ease-in-out infinite" : undefined,
                }}
              />
              {/* Orta ana platform halkası */}
              <div
                className="absolute left-1/2 top-2 -translate-x-1/2 rounded-[50%]"
                style={{
                  width: "70%", height: "76px",
                  background: "radial-gradient(ellipse at center, rgba(34,211,238,0.28), rgba(34,211,238,0.08) 55%, transparent 80%)",
                  border: "1px solid rgba(34,211,238,0.45)",
                  boxShadow: "0 0 32px rgba(34,211,238,0.22), inset 0 0 44px rgba(34,211,238,0.12)",
                }}
              />
              {/* Dönen dashed ring */}
              <div
                className="absolute left-1/2 top-3.5 -translate-x-1/2 rounded-[50%] border border-cyan-400/30"
                style={{
                  width: "54%", height: "60px",
                  animation: animate ? "cs-spin 32s linear infinite" : undefined,
                  borderStyle: "dashed",
                }}
              />
              {/* İç dönen ters yön */}
              <div
                className="absolute left-1/2 top-5 -translate-x-1/2 rounded-[50%] border border-cyan-300/20"
                style={{
                  width: "40%", height: "42px",
                  animation: animate ? "cs-spin 22s linear infinite reverse" : undefined,
                }}
              />
              {/* Enerji çekirdeği */}
              <div
                className="absolute left-1/2 top-[26px] -translate-x-1/2 rounded-full"
                style={{
                  width: "10px", height: "10px",
                  background: "radial-gradient(circle, #67e8f9, rgba(34,211,238,0.4) 60%, transparent)",
                  boxShadow: "0 0 10px rgba(34,211,238,0.8), 0 0 18px rgba(34,211,238,0.4)",
                  animation: animate ? "cs-breathe 2s ease-in-out infinite" : undefined,
                }}
              />
              {/* Scanline */}
              {animate && (
                <div
                  className="absolute left-0 top-2 h-[76px] w-[60px] pointer-events-none"
                  style={{
                    background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.10), transparent)",
                    animation: "cs-scan 7s linear infinite",
                  }}
                />
              )}
              <p className="absolute left-1/2 bottom-1.5 -translate-x-1/2 text-[7px] font-mono text-cyan-300/65 uppercase tracking-[0.35em] whitespace-nowrap">
                ◇ AI TRADING OPERATIONS ◇
              </p>
            </div>
          )}
        </div>

        {/* Sağ: detay paneli */}
        <div className={isMobile
          ? ""
          : "relative border-l border-cyan-500/20 p-3 bg-gradient-to-b from-black/30 via-cyan-950/10 to-black/40 overflow-hidden flex flex-col min-h-0"
        }>
          {!isMobile && (
            <>
              <span aria-hidden="true" className="absolute top-2 right-2 w-3 h-3 border-t border-r border-cyan-400/40" />
              <span aria-hidden="true" className="absolute bottom-2 right-2 w-3 h-3 border-b border-r border-cyan-400/40" />
            </>
          )}
          <p className="text-[8px] font-mono text-cyan-300/70 uppercase tracking-[0.22em] mb-2 flex items-center gap-1.5">
            <span className="w-1 h-1 rounded-full bg-cyan-400" style={animate ? { boxShadow: "0 0 6px #22d3ee" } : undefined} />
            Sinyal Detayı
          </p>
          <DetailPanel signal={selSig} tech={techBy[selCode]} />
        </div>
      </div>

      {/* Destek göstergeleri — auto-scrolling ticker */}
      {supports.length > 0 && (
        <div className="px-3 py-2 border-t border-eyay-border/30 bg-black/20">
          <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest mb-2">
            Piyasa Göstergeleri
          </p>
          {animate ? (
            <div className="relative overflow-hidden"
                 style={{
                   maskImage: "linear-gradient(90deg, transparent, black 6%, black 94%, transparent)",
                   WebkitMaskImage: "linear-gradient(90deg, transparent, black 6%, black 94%, transparent)",
                 }}>
              <div
                className="flex gap-2 w-max will-change-transform"
                style={{
                  animation: `cs-ticker ${Math.max(18, supports.length * 4)}s linear infinite`,
                  animationPlayState: paused ? "paused" : "running",
                }}
                onMouseEnter={() => setPaused(true)}
                onMouseLeave={() => setPaused(false)}
              >
                {[...supports, ...supports].map((s, i) => (
                  <SupportBar key={`${s.asset_code}-${i}`} s={s} />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {supports.map(s => <SupportBar key={s.asset_code} s={s} />)}
            </div>
          )}
        </div>
      )}

      {/* FAZ 22 — Macro / Risk Pulse rotating banner */}
      <div className="px-3 pt-2 pb-2 border-t border-eyay-border/30 bg-black/20">
        <MacroRiskPulse macro={macro} appetite={appetite} />
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-eyay-border/30 bg-black/30">
        <p className="text-[8px] font-mono text-eyay-faint/55 text-center">
          Cards görünümü yalnızca sinyal görselleştirmesidir · karar üretmez · hata durumunda klasik listeye dönülür
        </p>
      </div>
    </div>
  );
}
