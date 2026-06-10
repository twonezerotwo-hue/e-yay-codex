"use client";

/**
 * FAZ 19 — Holographic Event Calendar Layer.
 *
 * Kompakt dikey timeline. 220px sticky sidebar uyumlu.
 * Aktif olay 5s'de bir döner; hover/focus → pause.
 * Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useState } from "react";

import type { CatalystEvent } from "@/lib/types";

type Importance = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

const TONE: Record<string, { ring: string; badge: string; text: string; label: string }> = {
  CRITICAL: { ring: "#f87171", badge: "bg-red-950/60 border-red-600/70 text-red-200",         text: "text-red-300",    label: "KRİTİK" },
  HIGH:     { ring: "#fb923c", badge: "bg-orange-950/50 border-orange-600/60 text-orange-200", text: "text-orange-300", label: "YÜKSEK" },
  MEDIUM:   { ring: "#22d3ee", badge: "bg-cyan-950/40 border-cyan-700/50 text-cyan-200",       text: "text-cyan-300",   label: "ORTA" },
  LOW:      { ring: "#94a3b8", badge: "bg-slate-900/60 border-slate-600/50 text-slate-300",    text: "text-slate-300",  label: "DÜŞÜK" },
};

function toneOf(imp: string): typeof TONE["LOW"] {
  const k = (imp || "").toUpperCase() as Importance;
  return TONE[k] ?? TONE.LOW;
}

function fmtDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function dayLabel(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("tr-TR", { weekday: "short" });
}

const ROTATE_MS = 5000;

interface Props {
  catalysts: CatalystEvent[];
}

export default function EventCalendar3DLayer({ catalysts }: Props) {
  const events = catalysts.slice(0, 8);
  const [selected, setSelected] = useState(0);
  const [animate,  setAnimate]  = useState(false);
  const [paused,   setPaused]   = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    return () => mq.removeEventListener?.("change", onMQ);
  }, []);

  useEffect(() => {
    if (!animate || paused || events.length <= 1) return;
    const t = setInterval(() => {
      setSelected(s => (s + 1) % events.length);
    }, ROTATE_MS);
    return () => clearInterval(t);
  }, [animate, paused, events.length]);

  if (events.length === 0) {
    return (
      <div
        data-testid="event-calendar-3d"
        className="w-full min-w-0 overflow-hidden rounded-2xl border border-eyay-border bg-[#030c1a] p-3"
      >
        <p className="text-[11px] font-mono text-eyay-faint uppercase tracking-widest mb-2">
          Holographic Event Calendar
        </p>
        <p className="text-[10px] font-mono text-eyay-faint italic">Yaklaşan etkinlik yok.</p>
      </div>
    );
  }

  const safeSel = Math.min(selected, events.length - 1);
  const active  = events[safeSel];
  const tone    = toneOf(active.importance);

  return (
    <div
      data-testid="event-calendar-3d"
      className="w-full min-w-0 overflow-hidden rounded-2xl border border-eyay-border bg-[#030c1a]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      <style>{`
        @keyframes ec-pulse  { 0%,100%{opacity:.35;transform:scale(1)} 50%{opacity:.85;transform:scale(1.18)} }
        @keyframes ec-rise   { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:none} }
        @keyframes ec-breathe{ 0%,100%{filter:brightness(1)} 50%{filter:brightness(1.22)} }
        @keyframes ec-scan   { from{transform:translateY(-100%)} to{transform:translateY(100%)} }
      `}</style>

      {/* Header */}
      <div className="relative flex items-center gap-1.5 px-3 py-2 border-b border-cyan-500/20 bg-gradient-to-r from-black/50 via-cyan-950/20 to-black/50">
        <span aria-hidden="true" className="text-cyan-400/80 text-[10px]"
              style={animate ? { animation: "ec-breathe 3s ease-in-out infinite" } : undefined}>
          ◈
        </span>
        <p className="text-[10px] font-mono font-bold text-cyan-100 uppercase tracking-[0.2em]">
          Holographic Event Calendar
        </p>
        <span className="ml-auto text-[8px] font-mono text-cyan-400/70">{events.length}</span>
      </div>

      {/* Active event card — yükselen hologram */}
      <div className="relative px-3 pt-3 pb-2 overflow-hidden">
        {/* Background scan */}
        {animate && (
          <div aria-hidden="true" className="absolute inset-x-0 top-0 h-full pointer-events-none opacity-50"
               style={{
                 background: "linear-gradient(180deg, transparent, rgba(34,211,238,0.05), transparent)",
                 animation: "ec-scan 6s linear infinite",
               }}
          />
        )}
        <div
          key={active.id}
          className={`relative rounded-xl border backdrop-blur-md px-2.5 py-2 ${tone.badge}`}
          style={{
            background: `linear-gradient(160deg, rgba(8,28,52,0.85), rgba(3,12,26,0.92)), radial-gradient(circle at 50% 0%, ${tone.ring}22, transparent 60%)`,
            boxShadow: animate ? `0 12px 22px -10px ${tone.ring}66, 0 0 18px ${tone.ring}33, inset 0 1px 0 ${tone.ring}33` : undefined,
            animation: animate ? "ec-rise 0.5s ease" : undefined,
          }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <span className="rounded px-1 py-0.5 text-[7px] font-mono font-black border ${tone.badge}"
                  style={{ color: tone.ring, borderColor: `${tone.ring}55` }}>
              {tone.label}
            </span>
            <span className="text-[8px] font-mono text-eyay-faint truncate">{active.category}</span>
            <span className="ml-auto text-[8px] font-mono text-eyay-faint shrink-0">
              {active.days_until >= 0 ? `+${active.days_until}g` : `${active.days_until}g`}
            </span>
          </div>
          <p className="text-[10px] font-mono font-bold text-eyay-text leading-tight line-clamp-2">
            {active.name}
          </p>
          <p className="text-[9px] font-mono mt-0.5" style={{ color: tone.ring }}>
            {fmtDate(active.date)} · {dayLabel(active.date)}
          </p>
          {active.expectation && (
            <p className="text-[8.5px] font-mono text-eyay-dim mt-1 line-clamp-2">
              ◇ {active.expectation}
            </p>
          )}
          {active.market_impact && (
            <p className="text-[8.5px] font-mono text-eyay-faint mt-0.5 line-clamp-2">
              ↪ {active.market_impact}
            </p>
          )}
        </div>
      </div>

      {/* Mini vertical timeline */}
      <div className="px-3 pb-2 space-y-1 max-h-[260px] overflow-y-auto">
        <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest mb-1">
          Takvim
        </p>
        {events.map((e, i) => {
          const t = toneOf(e.importance);
          const active = i === safeSel;
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => setSelected(i)}
              className={`w-full flex items-center gap-2 rounded-md border px-2 py-1 text-left transition-all ${
                active ? `${t.badge} scale-[1.02]` : "bg-white/[0.02] border-eyay-border/30 hover:border-eyay-border/60"
              }`}
              style={active && animate ? { boxShadow: `0 0 12px ${t.ring}44` } : undefined}
            >
              {/* Dot + pulse */}
              <span className="relative shrink-0 w-2 h-2 rounded-full"
                    style={{ background: t.ring, boxShadow: animate ? `0 0 6px ${t.ring}` : undefined }}>
                {active && animate && (
                  <span aria-hidden="true" className="absolute inset-0 rounded-full"
                        style={{ background: t.ring, animation: "ec-pulse 1.8s ease-in-out infinite" }} />
                )}
              </span>
              <span className="text-[8.5px] font-mono font-bold shrink-0" style={{ color: t.ring }}>
                {fmtDate(e.date)}
              </span>
              <span className="text-[9px] font-mono text-eyay-dim truncate min-w-0 flex-1">
                {e.name}
              </span>
              <span className="text-[7.5px] font-mono text-eyay-faint shrink-0">
                {e.days_until >= 0 ? `+${e.days_until}` : e.days_until}g
              </span>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-eyay-border/30 bg-black/30">
        <p className="text-[7.5px] font-mono text-eyay-faint/55 text-center">
          PAPER_SAFE · NO_EXECUTION · sadece görselleştirme
        </p>
      </div>
    </div>
  );
}
