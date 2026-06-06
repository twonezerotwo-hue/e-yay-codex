"use client";

import { useState } from "react";
import type { CapitalRotation, AssetClassScore, KeyInsight, CorrelationPair } from "@/lib/types";

// ---------------------------------------------------------------------------
// Döngü sırası — soldan sağa risk-off → risk-on
// ---------------------------------------------------------------------------
const CYCLE_ORDER = ["NAKİT", "TAHVİL", "ALTIN", "GÜMÜŞ", "PETROL", "BTC", "HİSSE"] as const;

const AXIS_LABELS = {
  left:  "← Güvenli Liman",
  right: "Risk-On →",
};

// Her sınıfın hangi göstergeyle ölçüldüğü — kullanıcının "neye göre?" sorusunu yanıtlar
const CLASS_PROXY: Record<string, { ticker: string; label: string }> = {
  NAKİT:  { ticker: "DXY", label: "Dolar Endeksi (DXY) 30g getirisi" },
  TAHVİL: { ticker: "TLT", label: "20Y Treasury ETF (TLT) 30g getirisi" },
  ALTIN:  { ticker: "GLD", label: "Altın ETF (GLD) 30g getirisi" },
  GÜMÜŞ:  { ticker: "XAG", label: "Gümüş futures (XAG) 30g getirisi" },
  PETROL: { ticker: "OIL", label: "Ham Petrol (OIL/WTI) 30g getirisi" },
  BTC:    { ticker: "BTC", label: "Bitcoin spot 30g getirisi" },
  HİSSE:  { ticker: "SPY", label: "S&P 500 ETF (SPY) 30g getirisi" },
};

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

function nodeStyle(cs: AssetClassScore | undefined): {
  border: string; bg: string; text: string; dot: string;
} {
  if (!cs) return { border: "border-eyay-border/40", bg: "bg-eyay-raised/30", text: "text-eyay-faint", dot: "bg-eyay-muted" };
  if (cs.direction === "GİRİŞ")
    return { border: "border-emerald-700/60", bg: "bg-emerald-950/40", text: "text-emerald-300", dot: "bg-emerald-400" };
  if (cs.direction === "ÇIKIŞ")
    return { border: "border-red-900/40", bg: "bg-red-950/20", text: "text-red-300/70", dot: "bg-red-700/60" };
  return { border: "border-eyay-border/40", bg: "bg-eyay-raised/30", text: "text-eyay-dim", dot: "bg-eyay-muted" };
}

function momentumColor(m: number): string {
  if (m > 2.0)  return "text-emerald-400";
  if (m > 0.5)  return "text-emerald-400/70";
  if (m < -2.0) return "text-red-400";
  if (m < -0.5) return "text-red-400/70";
  return "text-eyay-faint";
}

// ---------------------------------------------------------------------------
// Döngü düğümleri arası ok yönü
// "->" soldan sağa, "<-" sağdan sola, "·" nötr
// ---------------------------------------------------------------------------
function arrowBetween(left: AssetClassScore | undefined, right: AssetClassScore | undefined): string {
  if (!left || !right) return "·";
  const diff = right.score - left.score;
  if (diff > 0.20) return "→";
  if (diff < -0.20) return "←";
  return "·";
}

// ---------------------------------------------------------------------------
// Cycle Chain Visualization
// ---------------------------------------------------------------------------
function CycleChain({ scores }: { scores: AssetClassScore[] }) {
  const byName = Object.fromEntries(scores.map(s => [s.name, s]));

  return (
    <div className="space-y-2">
      {/* Eksen etiketleri */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[8px] text-eyay-faint/60 font-mono">{AXIS_LABELS.left}</span>
        <span className="text-[8px] text-eyay-faint/60 font-mono">{AXIS_LABELS.right}</span>
      </div>

      {/* Düğüm + ok zinciri */}
      <div className="flex items-stretch gap-0 overflow-x-auto pb-1">
        {CYCLE_ORDER.map((name, i) => {
          const cs    = byName[name];
          const st    = nodeStyle(cs);
          const mColor = cs ? momentumColor(cs.momentum_30d) : "text-eyay-faint";
          const arrow = i < CYCLE_ORDER.length - 1
            ? arrowBetween(cs, byName[CYCLE_ORDER[i + 1]])
            : null;

          const proxy = CLASS_PROXY[name];

          return (
            <div key={name} className="flex items-stretch shrink-0">
              {/* Düğüm kutusu — title ile hover tooltip (neye göre ölçüldüğü) */}
              <div
                title={proxy ? `${name}: ${proxy.label}` : name}
                className={`flex flex-col items-center justify-between rounded-lg border px-2 py-2 min-w-[64px] gap-1 ${st.border} ${st.bg}`}
              >
                {/* Durum noktası */}
                <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />

                {/* İsim */}
                <span className={`font-mono text-[9px] font-bold leading-none text-center ${st.text}`}>
                  {name}
                </span>

                {/* Referans gösterge — "neye göre" sorusunu yanıtlar */}
                {proxy && (
                  <span className="font-mono text-[7px] text-eyay-faint/60 leading-none uppercase tracking-wider">
                    {proxy.ticker}
                  </span>
                )}

                {/* Momentum */}
                {cs ? (
                  <span className={`font-mono text-[8px] leading-none ${mColor}`}>
                    {cs.momentum_30d > 0 ? "+" : ""}{cs.momentum_30d.toFixed(1)}%
                  </span>
                ) : (
                  <span className="text-[8px] text-eyay-faint/30">—</span>
                )}

                {/* Yön etiketi */}
                {cs && (
                  <span className={`text-[7px] font-semibold leading-none ${
                    cs.direction === "GİRİŞ" ? "text-emerald-400"
                    : cs.direction === "ÇIKIŞ" ? "text-red-400/60"
                    : "text-eyay-faint/50"
                  }`}>
                    {cs.direction}
                  </span>
                )}
              </div>

              {/* Ok bağlantısı */}
              {arrow !== null && (
                <div className="flex items-center px-0.5 shrink-0">
                  <span className={`text-[10px] font-bold leading-none ${
                    arrow === "→" ? "text-emerald-500/70"
                    : arrow === "←" ? "text-red-500/50"
                    : "text-eyay-border"
                  }`}>
                    {arrow === "→" ? "›" : arrow === "←" ? "‹" : "·"}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Akış özeti — sınıf sayıları + yüzde açıklaması */}
      <div className="flex items-center gap-3 px-1 flex-wrap pt-1 border-t border-eyay-border/30">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
          <span className="text-[9px] text-eyay-dim font-mono">
            {scores.filter(s => s.direction === "GİRİŞ").length} GİRİŞ
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-red-700/60 shrink-0" />
          <span className="text-[9px] text-eyay-dim font-mono">
            {scores.filter(s => s.direction === "ÇIKIŞ").length} ÇIKIŞ
          </span>
        </div>
        <span className="text-[8px] text-eyay-faint/60 italic">
          % = referans varlığın 30 günlük getirisi (NAKİT=DXY, HİSSE=SPY vs.)
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Key Insights
// ---------------------------------------------------------------------------
function InsightList({ insights }: { insights: KeyInsight[] }) {
  if (!insights.length) return null;
  return (
    <div className="space-y-1.5">
      {insights.map((ki, i) => (
        <div key={i} className="flex items-start gap-2 text-[10px] leading-snug">
          <span className="shrink-0 mt-px">{ki.icon}</span>
          <span className="text-eyay-dim">{ki.text}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Correlations (collapsible)
// ---------------------------------------------------------------------------
const CORR_COLOR: Record<string, string> = {
  GÜÇLÜ_TERS:    "text-red-400",
  ORTA_TERS:     "text-orange-400",
  BAĞIMSIZ:      "text-eyay-faint",
  ORTA_POZİTİF:  "text-emerald-400/70",
  GÜÇLÜ_POZİTİF: "text-emerald-400",
};

function CorrTable({ corrs }: { corrs: CorrelationPair[] }) {
  const [open, setOpen] = useState(false);
  if (!corrs.length) return null;
  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-[9px] font-mono text-eyay-faint hover:text-eyay-dim transition-colors"
      >
        <span className={`transition-transform duration-150 text-[8px] ${open ? "rotate-90" : ""}`}>▶</span>
        Korelasyon tablosu — {corrs.length} çift
      </button>
      {open && (
        <div className="mt-1.5 grid grid-cols-2 gap-x-4 gap-y-0.5">
          {corrs.map(c => (
            <div key={c.pair} className="flex items-center gap-1.5">
              <span className="font-mono text-[9px] text-eyay-dim w-[58px] shrink-0">{c.pair}</span>
              <span className={`font-mono text-[9px] font-semibold ${CORR_COLOR[c.regime] ?? "text-eyay-faint"}`}>
                {c.corr_30d > 0 ? "+" : ""}{c.corr_30d.toFixed(2)}
              </span>
              <span className={`text-[8px] font-mono ${CORR_COLOR[c.regime] ?? "text-eyay-faint"}`}>
                [{c.regime.replace(/_/g, " ")}]
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Conviction bar
// ---------------------------------------------------------------------------
function convictionColor(c: number) {
  if (c >= 55) return { bar: "bg-emerald-500", text: "text-emerald-300" };
  if (c >= 30) return { bar: "bg-amber-500",   text: "text-amber-300"   };
  return           { bar: "bg-eyay-muted",      text: "text-eyay-dim"   };
}

// ---------------------------------------------------------------------------
// Ana bileşen
// ---------------------------------------------------------------------------

export default function CapitalFlowWidget({
  rotation,
}: {
  rotation: CapitalRotation | null | undefined;
}) {
  if (!rotation) return null;
  if (rotation.error && rotation.class_scores.length === 0) return null;

  const cv = convictionColor(rotation.conviction);

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">

      {/* Header */}
      <div className="px-5 py-3.5 border-b border-eyay-border flex items-center justify-between">
        <div>
          <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">
            Sermaye Rotasyonu · 30 Gün
          </p>
          <p className="text-sm font-semibold text-eyay-text mt-0.5">Para Nereye Akıyor?</p>
        </div>
        {/* Conviction */}
        <div className="flex items-center gap-2.5">
          <div className="text-right">
            <p className="text-[8px] text-eyay-faint uppercase tracking-wider">Conviction</p>
            <p className={`font-mono font-black text-lg leading-none ${cv.text}`}>
              {rotation.conviction}
              <span className="text-[9px] font-normal text-eyay-faint">/100</span>
            </p>
          </div>
          <div className="w-1.5 h-10 rounded-full bg-eyay-border overflow-hidden flex flex-col justify-end">
            <div
              className={`w-full rounded-full transition-all ${cv.bar}`}
              style={{ height: `${rotation.conviction}%` }}
            />
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">

        {/* ── Döngü zinciri ── */}
        <CycleChain scores={[...rotation.class_scores]} />

        <div className="border-t border-eyay-border/40" />

        {/* ── Synthesis ── */}
        {rotation.synthesis && (
          <p className="text-[11px] text-eyay-dim leading-relaxed border-l-2 border-eyay-border pl-3 italic">
            {rotation.synthesis}
          </p>
        )}

        {/* ── Önemli sinyaller ── */}
        {rotation.key_insights.length > 0 && (
          <div>
            <p className="text-[9px] font-semibold text-eyay-faint uppercase tracking-wider mb-2">
              Ne Söylüyor?
            </p>
            <InsightList insights={rotation.key_insights} />
          </div>
        )}

        {/* ── Korelasyonlar (collapse) ── */}
        <div className="border-t border-eyay-border/40 pt-2.5">
          <CorrTable corrs={rotation.correlations} />
        </div>

        <p className="text-[8px] text-eyay-faint/40 font-mono">
          yfinance OHLCV 30g · çapraz oran trendleri · log-getiri korelasyonu · PAPER_SAFE
        </p>
      </div>
    </div>
  );
}
