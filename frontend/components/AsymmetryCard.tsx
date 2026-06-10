"use client";

/**
 * FAZ 23 — Asimetri Kartı (sade premium tasarım).
 *
 * Ana göstergede 0-100 canonical score. Ratio yalnızca küçük alt satırda.
 * report.asymmetry.score doluysa kullan; yoksa ratio'dan türet.
 * Display smoothing: tek poll'da maks 8 puan oynar. Karar motoru ham ratio
 * üzerinden çalışmaya devam eder.
 */
import { useEffect, useState } from "react";

import type { AsymmetrySignal } from "@/lib/types";
import {
  loadPrevDisplayedScore,
  ratioToScore100,
  savePrevDisplayedScore,
  smoothScore,
} from "@/lib/normalizeAsymmetry";

type Tone = "red" | "orange" | "amber" | "cyan" | "emerald";

const TONE: Record<Tone, { ring: string; bar: string; text: string; soft: string; border: string }> = {
  red:     { ring: "#f87171", bar: "bg-red-500",     text: "text-red-300",     soft: "rgba(248,113,113,0.15)", border: "border-red-700/50" },
  orange:  { ring: "#fb923c", bar: "bg-orange-500",  text: "text-orange-300",  soft: "rgba(251,146,60,0.15)",  border: "border-orange-700/50" },
  amber:   { ring: "#fbbf24", bar: "bg-amber-400",   text: "text-amber-300",   soft: "rgba(251,191,36,0.15)",  border: "border-amber-700/50" },
  cyan:    { ring: "#22d3ee", bar: "bg-cyan-500",    text: "text-cyan-300",    soft: "rgba(34,211,238,0.15)",  border: "border-cyan-700/50" },
  emerald: { ring: "#34d399", bar: "bg-emerald-500", text: "text-emerald-300", soft: "rgba(52,211,153,0.15)",  border: "border-emerald-700/50" },
};

function toneFor(score: number): Tone {
  if (score <= 30) return "red";
  if (score <= 45) return "orange";
  if (score <= 55) return "amber";
  if (score <= 70) return "cyan";
  return "emerald";
}

function labelFor(direction: string, score: number): string {
  if (direction === "negative" || score <= 30) return "Negatif";
  if (score <= 45) return "Temkinli";
  if (score <= 55) return "Nötr";
  if (score <= 70) return "Seçici pozitif";
  return "Pozitif";
}

function isSuspect(a: AsymmetrySignal): boolean {
  if (!a) return true;
  if (!isFinite(a.ratio) || a.ratio <= 0) return true;
  if (a.expected_gain_pct < 0 || a.expected_gain_pct > 100) return true;
  if (a.expected_loss_pct <= 0 || a.expected_loss_pct > 100) return true;
  return false;
}

export default function AsymmetryCard({ asymmetry }: { asymmetry: AsymmetrySignal | null | undefined }) {
  const [displayed, setDisplayed] = useState<number | null>(null);
  const [smoothed, setSmoothed]   = useState(false);

  // Canonical raw score: backend tercih, yoksa ratio fallback
  const rawScore = asymmetry && !isSuspect(asymmetry)
    ? (typeof asymmetry.score === "number" ? asymmetry.score : ratioToScore100(asymmetry.ratio))
    : null;

  useEffect(() => {
    if (rawScore === null) return;
    const prev = loadPrevDisplayedScore();
    const r = smoothScore(rawScore, prev);
    setDisplayed(r.displayed);
    setSmoothed(r.smoothed);
    savePrevDisplayedScore(r.displayed);
  }, [rawScore]);

  if (!asymmetry) {
    return (
      <div className="bg-eyay-surface rounded-2xl border border-eyay-border p-4">
        <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">Asimetri</p>
        <p className="text-[10px] font-mono text-eyay-faint italic mt-2">Asimetri verisi bekleniyor.</p>
      </div>
    );
  }

  if (isSuspect(asymmetry) || rawScore === null) {
    return (
      <div className="bg-eyay-surface rounded-2xl border border-eyay-border p-4 space-y-1">
        <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">Asimetri</p>
        <p className="text-[10px] font-mono text-amber-400">⚠ Hesaplanamadı — veri aralık dışı</p>
      </div>
    );
  }

  const shown      = Math.round(displayed ?? rawScore);
  const tone       = TONE[toneFor(shown)];
  const direction  = asymmetry.direction ?? (shown >= 56 ? "positive" : shown < 45 ? "negative" : "neutral");
  const label      = labelFor(direction, shown);
  const confidence = asymmetry.confidence ?? 60;
  const dataQ      = asymmetry.data_quality ?? "ok";
  const dqDot      = dataQ === "ok" ? "#34d399" : dataQ === "degraded" ? "#fbbf24" : "#f87171";

  return (
    <div
      className={`bg-eyay-surface rounded-2xl border ${tone.border} p-4 flex flex-col`}
      style={{ boxShadow: `0 0 14px ${tone.soft}` }}
      data-testid="asymmetry-card"
    >
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">Asimetri</p>
        <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded border ${tone.border}`}
              style={{ color: tone.ring, background: tone.soft }}>
          {label}
        </span>
      </div>

      {/* Ana skor */}
      <div className="flex items-baseline gap-1 mb-2">
        <span className={`font-mono font-black text-4xl leading-none ${tone.text}`}
              title={`Ham R/R: ${asymmetry.ratio.toFixed(2)}×${smoothed ? " (gösterim yumuşatıldı)" : ""}`}>
          {shown}
        </span>
        <span className="text-[12px] font-mono text-eyay-faint">/ 100</span>
        {smoothed && (
          <span className="ml-auto text-[8px] font-mono text-amber-400/70" title="Tek poll'da büyük değişim — yumuşatıldı">
            ⌛ stabilize
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-black/40 overflow-hidden mb-2">
        <div className={`h-full rounded-full ${tone.bar} transition-all duration-700`}
             style={{ width: `${shown}%` }} />
      </div>

      {/* Compact alt satır */}
      <div className="flex items-center gap-2 text-[9px] font-mono text-eyay-faint">
        <span>Ham R/R: <span className="text-eyay-dim">{asymmetry.ratio.toFixed(2)}×</span></span>
        <span>·</span>
        <span>Güven: <span className="text-eyay-dim">{confidence}</span></span>
        <span className="ml-auto flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: dqDot }} />
          <span className="text-eyay-dim">{dataQ}</span>
        </span>
      </div>
    </div>
  );
}
