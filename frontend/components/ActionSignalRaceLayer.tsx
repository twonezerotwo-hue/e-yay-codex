"use client";

/**
 * FAZ 20 — AI Decision Race Track Layer.
 *
 * "Tavsiye Edilen Aksiyon" alanını yarış pisti + atlet metaforu ile gösterir.
 * Atletin pozu kararı (AÇIL/BEKLE/KÜÇÜLT/KAPAT), pist üstü pozisyonu
 * Onay/Bekle/Blok sayaçlarından türetilir.
 * Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useState } from "react";

import type { Decision, RegimeReport } from "@/lib/types";

// ── Mode tanımları ───────────────────────────────────────────────────────────

type Pose = "run" | "crouch" | "brake" | "block" | "stand";

interface ModeMeta {
  pose:        Pose;
  toneRing:    string;
  toneSoft:    string;
  borderCls:   string;
  bgCls:       string;
  textCls:     string;
  label:       string;
  shortLabel:  string;
  description: string;
}

const MODE: Record<Decision, ModeMeta> = {
  AÇIL:   {
    pose: "run", toneRing: "#34d399", toneSoft: "rgba(52,211,153,0.18)",
    borderCls: "border-emerald-600/50", bgCls: "bg-emerald-950/40",
    textCls: "text-emerald-300", label: "ONAY · AÇIL", shortLabel: "ONAY",
    description: "Pistte ilerideyiz — koşu hızı yüksek.",
  },
  BEKLE:  {
    pose: "crouch", toneRing: "#fbbf24", toneSoft: "rgba(251,191,36,0.18)",
    borderCls: "border-amber-600/50", bgCls: "bg-amber-950/40",
    textCls: "text-amber-300", label: "BEKLE", shortLabel: "BEKLE",
    description: "Start çizgisinde teyit bekliyoruz.",
  },
  KÜÇÜLT: {
    pose: "brake", toneRing: "#fb923c", toneSoft: "rgba(251,146,60,0.18)",
    borderCls: "border-orange-600/50", bgCls: "bg-orange-950/40",
    textCls: "text-orange-300", label: "KÜÇÜLT", shortLabel: "KÜÇÜLT",
    description: "Pist ortasında kontrollü yavaşlama.",
  },
  KAPAT:  {
    pose: "block", toneRing: "#f87171", toneSoft: "rgba(248,113,113,0.18)",
    borderCls: "border-red-600/50", bgCls: "bg-red-950/40",
    textCls: "text-red-300", label: "BLOK · KAPAT", shortLabel: "BLOK",
    description: "Bariyer indirildi — risk bölgesi.",
  },
};

function metaFor(d: Decision): ModeMeta { return MODE[d] ?? MODE.BEKLE; }

// ── Athlete SVG ──────────────────────────────────────────────────────────────

function Athlete({ pose, color, animate }: { pose: Pose; color: string; animate: boolean }) {
  const glow = { filter: `drop-shadow(0 0 6px ${color}aa)` } as const;
  // Vücut özellikleri her poz için minimal stylized geometri
  switch (pose) {
    case "run":
      return (
        <g style={glow}>
          {/* baş */}
          <circle cx="0" cy="-44" r="7" fill={color} />
          {/* gövde (ileri eğik) */}
          <line x1="-4" y1="-37" x2="6" y2="-12" stroke={color} strokeWidth="5" strokeLinecap="round" />
          {/* kollar — ileri/geri swing */}
          <line x1="6" y1="-30" x2="22" y2="-36" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="-4" y1="-26" x2="-18" y2="-18" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          {/* bacaklar — koşu adımı */}
          <line x1="6" y1="-12" x2="20" y2="2"  stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          <line x1="6" y1="-12" x2="-12" y2="2" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          {animate && (
            <circle cx="22" cy="-36" r="3" fill={color} opacity="0.7">
              <animate attributeName="r" values="3;6;3" dur="1.4s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.7;0;0.7" dur="1.4s" repeatCount="indefinite" />
            </circle>
          )}
        </g>
      );
    case "crouch":
      return (
        <g style={glow}>
          <circle cx="-2" cy="-32" r="6.5" fill={color} />
          {/* gövde — çömelmiş, paralel zemin */}
          <line x1="-6" y1="-26" x2="14" y2="-22" stroke={color} strokeWidth="5" strokeLinecap="round" />
          {/* kollar — start blocks */}
          <line x1="-4" y1="-24" x2="-4" y2="0" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="14" y1="-22" x2="22" y2="-2" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          {/* bacak — geride */}
          <line x1="14" y1="-22" x2="-2" y2="0" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          <line x1="14" y1="-22" x2="6" y2="2" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          {/* starting block */}
          <rect x="-12" y="0" width="14" height="4" rx="1" fill={color} opacity="0.5" />
        </g>
      );
    case "brake":
      return (
        <g style={glow}>
          <circle cx="0" cy="-44" r="7" fill={color} />
          {/* gövde — geriye kaykılmış */}
          <line x1="2" y1="-37" x2="-6" y2="-12" stroke={color} strokeWidth="5" strokeLinecap="round" />
          {/* kollar — denge */}
          <line x1="-2" y1="-30" x2="-20" y2="-26" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="2" y1="-28" x2="18" y2="-32" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          {/* bacaklar — fren */}
          <line x1="-6" y1="-12" x2="-18" y2="2" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          <line x1="-6" y1="-12" x2="8" y2="2"  stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          {/* lastik izi / sürtünme */}
          <line x1="-18" y1="3.5" x2="-30" y2="3.5" stroke={color} strokeWidth="2" strokeDasharray="2 2" opacity="0.6" />
        </g>
      );
    case "block":
      return (
        <g style={glow}>
          {/* atlet dik durmuş, bariyer önünde */}
          <circle cx="-10" cy="-44" r="7" fill={color} />
          <line x1="-10" y1="-37" x2="-10" y2="-12" stroke={color} strokeWidth="5" strokeLinecap="round" />
          <line x1="-10" y1="-30" x2="-20" y2="-22" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="-10" y1="-30" x2="0"   y2="-22" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="-10" y1="-12" x2="-16" y2="2" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          <line x1="-10" y1="-12" x2="-4"  y2="2" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          {/* bariyer — kırmızı şerit */}
          <rect x="14" y="-44" width="6" height="48" rx="2" fill={color} />
          <line x1="14" y1="-32" x2="20" y2="-32" stroke="#0a0a0a" strokeWidth="2" />
          <line x1="14" y1="-16" x2="20" y2="-16" stroke="#0a0a0a" strokeWidth="2" />
          <text x="17" y="-50" textAnchor="middle" fontSize="9" fill={color}
                fontFamily="monospace" fontWeight="bold">STOP</text>
        </g>
      );
    case "stand":
    default:
      return (
        <g style={glow}>
          <circle cx="0" cy="-44" r="7" fill={color} />
          <line x1="0" y1="-37" x2="0" y2="-10" stroke={color} strokeWidth="5" strokeLinecap="round" />
          <line x1="0" y1="-30" x2="-12" y2="-22" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="0" y1="-30" x2="12"  y2="-22" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
          <line x1="0" y1="-10" x2="-8" y2="4" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
          <line x1="0" y1="-10" x2="8"  y2="4" stroke={color} strokeWidth="4.5" strokeLinecap="round" />
        </g>
      );
  }
}

// ── Race track SVG ───────────────────────────────────────────────────────────

const TRACK_W = 800;
const TRACK_H = 220;

function clampPct(v: number): number { return Math.max(6, Math.min(94, v)); }

// ── Component ────────────────────────────────────────────────────────────────

interface Props { report: RegimeReport; }

export default function ActionSignalRaceLayer({ report }: Props) {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    return () => mq.removeEventListener?.("change", onMQ);
  }, []);

  const decision   = report.decision ?? "BEKLE";
  const meta       = metaFor(decision);
  const confirmed  = report.confirmed_count ?? 0;
  const pending    = report.pending_count   ?? 0;
  const blocking   = report.blocking_count  ?? 0;
  const total      = confirmed + pending + blocking;

  // Atlet x pozisyonu (track yüzdesi). Dominant kararın tabanı + sayaç oranı.
  const baseByDecision: Record<Decision, number> = {
    AÇIL: 70, BEKLE: 18, KÜÇÜLT: 50, KAPAT: 85,
  };
  const ratioBoost = total > 0 ? (confirmed / total) * 20 - (blocking / total) * 14 : 0;
  const xPct = clampPct((baseByDecision[decision] ?? 30) + ratioBoost);

  const time = report.generated_at
    ? new Date(report.generated_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
    : "—";

  // Verdict kısa özet — ilk cümle
  const briefVerdict = (report.verdict || "")
    .split(/[.!?]\s+/)[0]
    .slice(0, 140);

  // Athlete merkez koordinatı (SVG)
  const athleteX = (xPct / 100) * TRACK_W;
  const athleteY = 150;

  return (
    <div
      data-testid="action-signal-race"
      className={`w-full max-w-full min-w-0 overflow-hidden rounded-2xl border ${meta.borderCls} ${meta.bgCls}`}
      style={{
        boxShadow: animate
          ? `0 0 28px ${meta.toneSoft}, inset 0 1px 0 ${meta.toneRing}55`
          : `0 0 12px ${meta.toneSoft}`,
      }}
    >
      <style>{`
        @keyframes asr-bob     { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-3px)} }
        @keyframes asr-glide   { 0%{transform:translateX(0)} 50%{transform:translateX(8px)} 100%{transform:translateX(0)} }
        @keyframes asr-lights  { 0%{background-position:0 0} 100%{background-position:120px 0} }
        @keyframes asr-breathe { 0%,100%{opacity:0.75} 50%{opacity:1} }
        @keyframes asr-fade    { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-cyan-500/15 bg-gradient-to-r from-black/40 via-cyan-950/15 to-black/40">
        <div className="flex items-center gap-2 min-w-0">
          <span aria-hidden="true" className={meta.textCls}
                style={animate ? { animation: "asr-breathe 2.5s ease-in-out infinite" } : undefined}>
            ◈
          </span>
          <div className="min-w-0">
            <p className="text-[10px] font-mono font-bold text-cyan-100 uppercase tracking-[0.22em] truncate">
              Decision Race Track
            </p>
            <p className="text-[8px] font-mono text-cyan-400/60 truncate">
              AI visual layer · PAPER_SAFE
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-1.5 min-w-0 shrink">
          <Chip n={blocking}  label="Blok"  color="#f87171" />
          <Chip n={confirmed} label="Onay"  color="#34d399" />
          <Chip n={pending}   label="Bekle" color="#fbbf24" />
          <span className="font-mono text-[10px] text-eyay-faint ml-1">{time}</span>
        </div>
      </div>

      {/* Body: track + detail */}
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_220px] gap-0">
        {/* Track */}
        <div className="relative px-4 py-4 overflow-hidden">
          {/* Pist arka plan ışıkları */}
          <div aria-hidden="true" className="absolute inset-x-4 top-1/2 -translate-y-1/2 h-[120px] rounded-2xl pointer-events-none"
               style={{
                 background:
                   "linear-gradient(180deg, rgba(34,211,238,0.06), rgba(34,211,238,0.02) 50%, rgba(34,211,238,0.06))",
                 boxShadow: "inset 0 0 30px rgba(34,211,238,0.08)",
                 border: "1px solid rgba(34,211,238,0.10)",
               }} />

          <svg
            viewBox={`0 0 ${TRACK_W} ${TRACK_H}`}
            className="relative w-full h-[200px] sm:h-[220px]"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="asr-track-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"  stopColor="#0a1c34" />
                <stop offset="100%" stopColor="#031020" />
              </linearGradient>
              <linearGradient id="asr-tone-grad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%"   stopColor={meta.toneRing} stopOpacity="0" />
                <stop offset={`${xPct - 5}%`} stopColor={meta.toneRing} stopOpacity="0.25" />
                <stop offset={`${xPct}%`}     stopColor={meta.toneRing} stopOpacity="0.7" />
                <stop offset={`${xPct + 5}%`} stopColor={meta.toneRing} stopOpacity="0.25" />
                <stop offset="100%" stopColor={meta.toneRing} stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Pist gövdesi (trapez perspective) */}
            <path d={`M 40 ${TRACK_H - 30} L ${TRACK_W - 40} ${TRACK_H - 30} L ${TRACK_W - 80} 80 L 80 80 Z`}
                  fill="url(#asr-track-grad)" stroke="rgba(34,211,238,0.25)" strokeWidth="1" />

            {/* Lane çizgileri */}
            {[0.25, 0.5, 0.75].map((y, i) => (
              <line key={i}
                    x1={40 + (40) * y}  y1={TRACK_H - 30 - (TRACK_H - 110) * y}
                    x2={TRACK_W - 40 - 40 * y} y2={TRACK_H - 30 - (TRACK_H - 110) * y}
                    stroke="rgba(34,211,238,0.18)" strokeWidth="0.6" strokeDasharray="6 6" />
            ))}

            {/* Start çizgisi */}
            <line x1="80" y1="80" x2="40" y2={TRACK_H - 30}
                  stroke="rgba(251,191,36,0.55)" strokeWidth="2" strokeDasharray="4 4" />
            <text x="50" y="74" fontSize="9" fill="rgba(251,191,36,0.85)" fontFamily="monospace" fontWeight="bold">START</text>

            {/* Bitiş / risk bölgesi */}
            <line x1={TRACK_W - 80} y1="80" x2={TRACK_W - 40} y2={TRACK_H - 30}
                  stroke="rgba(248,113,113,0.55)" strokeWidth="2" strokeDasharray="4 4" />
            <text x={TRACK_W - 60} y="74" textAnchor="middle" fontSize="9"
                  fill="rgba(248,113,113,0.85)" fontFamily="monospace" fontWeight="bold">BARİYER</text>

            {/* Tone-renkli pozisyon highlight şerit */}
            <rect x="40" y={TRACK_H - 50} width={TRACK_W - 80} height="6" fill="url(#asr-tone-grad)" />

            {/* Pist üzeri yürüyen ışıklar (CSS animated overlay yerine SVG dashed line) */}
            <line x1="60" y1={TRACK_H - 18} x2={TRACK_W - 60} y2={TRACK_H - 18}
                  stroke={meta.toneRing} strokeOpacity="0.35" strokeWidth="1.5" strokeDasharray="14 18">
              {animate && (
                <animate attributeName="stroke-dashoffset" from="0" to="-64" dur="2.4s" repeatCount="indefinite" />
              )}
            </line>

            {/* Mesafe işaretleri */}
            {[25, 50, 75].map(p => {
              const x = (p / 100) * TRACK_W;
              return (
                <g key={p}>
                  <line x1={x} y1={TRACK_H - 38} x2={x} y2={TRACK_H - 26}
                        stroke="rgba(34,211,238,0.35)" strokeWidth="1" />
                  <text x={x} y={TRACK_H - 14} textAnchor="middle" fontSize="8"
                        fill="rgba(34,211,238,0.5)" fontFamily="monospace">{p}%</text>
                </g>
              );
            })}

            {/* Spotlight altında atlet */}
            <ellipse cx={athleteX} cy={athleteY + 6} rx="34" ry="6"
                     fill={meta.toneRing} opacity="0.22"
                     style={animate ? { animation: "asr-breathe 2.4s ease-in-out infinite" } : undefined} />
            <g transform={`translate(${athleteX}, ${athleteY})`}
               style={animate ? {
                 animation: meta.pose === "run"
                   ? "asr-glide 1.6s ease-in-out infinite, asr-bob 1.1s ease-in-out infinite"
                   : "asr-bob 2.6s ease-in-out infinite",
               } : undefined}>
              <Athlete pose={meta.pose} color={meta.toneRing} animate={animate} />
            </g>

            {/* Pozisyon yüzde rozeti */}
            <g transform={`translate(${athleteX}, ${athleteY - 70})`} style={animate ? { animation: "asr-fade 0.6s ease" } : undefined}>
              <rect x="-22" y="-12" width="44" height="16" rx="3"
                    fill="rgba(2,10,22,0.85)" stroke={meta.toneRing} strokeOpacity="0.6" />
              <text x="0" y="-1" textAnchor="middle" fontSize="9"
                    fill={meta.toneRing} fontFamily="monospace" fontWeight="bold">
                {Math.round(xPct)}%
              </text>
            </g>
          </svg>
        </div>

        {/* Detail panel */}
        <div className="border-t lg:border-t-0 lg:border-l border-cyan-500/15 p-3 bg-black/20">
          <p className="text-[8px] font-mono text-cyan-400/60 uppercase tracking-[0.22em] mb-1">
            Aksiyon
          </p>
          <p className={`text-[20px] font-mono font-black tracking-widest ${meta.textCls}`}
             style={animate ? { textShadow: `0 0 10px ${meta.toneRing}66` } : undefined}>
            {meta.shortLabel}
          </p>
          <p className="text-[10px] font-mono text-eyay-dim mt-1 leading-snug line-clamp-2">
            {meta.description}
          </p>

          {/* Verdict brief */}
          {briefVerdict && (
            <div className="mt-2 pt-2 border-t border-cyan-700/20">
              <p className="text-[7.5px] font-mono uppercase tracking-[0.22em] mb-0.5"
                 style={{ color: meta.toneRing }}>
                Verdict
              </p>
              <p className="text-[9px] font-mono text-eyay-dim leading-snug line-clamp-4">
                {briefVerdict}
              </p>
            </div>
          )}

          {/* Dominant mode */}
          <div className="mt-2 pt-2 border-t border-cyan-700/20">
            <p className="text-[7.5px] font-mono uppercase tracking-[0.22em] mb-1"
               style={{ color: meta.toneRing }}>
              Pist Konumu
            </p>
            <div className="flex items-center gap-1 text-[9px] font-mono text-eyay-dim">
              <span className="rounded px-1 border" style={{ borderColor: `${meta.toneRing}66`, color: meta.toneRing }}>
                {Math.round(xPct)}%
              </span>
              <span className="text-eyay-faint">·</span>
              <span className="truncate min-w-0">{meta.label}</span>
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

// ── Chip ─────────────────────────────────────────────────────────────────────

function Chip({ n, label, color }: { n: number; label: string; color: string }) {
  return (
    <span className="flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-mono bg-black/40"
          style={{ borderColor: `${color}55`, color }}>
      <span className="font-bold">{n}</span>
      <span className="opacity-70">{label}</span>
    </span>
  );
}
