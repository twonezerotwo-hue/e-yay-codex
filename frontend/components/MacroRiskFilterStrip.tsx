"use client";

/**
 * Macro / Risk Filter compact strip.
 *
 * Katman 2 (Makro Zemin) + Katman 3 (Risk İştahı) verilerini Katman 1
 * "Durum Odası" üst bandında kompakt chip satırı olarak gösterir.
 *
 * Detay accordion açıldığında eski Katman 2/3 satırları MacroPanel
 * (showUnified=false) ile aynen render edilir — veri kaybı yok.
 *
 * Veri eksikse "Makro/Risk verisi bekleniyor" gösterir, crash yok.
 * Frontend-only görsel katman; backend/agent verisi mutate edilmez.
 */
import { useState } from "react";

import MacroPanel from "@/components/MacroPanel";
import type { MacroLayer, RiskAppetiteLayer } from "@/lib/types";

type ChipTone = "good" | "neutral" | "risk" | "hedge";

const TONE_CLS: Record<ChipTone, string> = {
  good:    "border-emerald-500/40 bg-emerald-950/40 text-emerald-200",
  neutral: "border-amber-500/40 bg-amber-950/30 text-amber-200",
  risk:    "border-red-500/40 bg-red-950/40 text-red-200",
  hedge:   "border-purple-500/40 bg-purple-950/30 text-purple-200",
};

function firstWord(v?: string): string {
  if (!v) return "";
  const head = v.split(" — ")[0]?.split("(")[0]?.trim() ?? "";
  return head.toLowerCase();
}

function classifyDxy(v?: string): ChipTone {
  const s = (v || "").toUpperCase();
  if (s.includes("ZAYIF")) return "good";
  if (s.includes("GÜÇL") || s.includes("YÜKSEK") || s.includes("KIRIYOR")) return "risk";
  return "neutral";
}
function classifyCredit(v?: string): ChipTone {
  const s = (v || "").toUpperCase();
  if (s.includes("SAĞL") || s.includes("NORMAL") || s.includes("GENİŞ")) return "good";
  if (s.includes("DARAL") || s.includes("ZAYIF") || s.includes("BASKILI")) return "risk";
  return "neutral";
}
function classifyBtcD(v?: string): ChipTone {
  const s = (v || "").toUpperCase();
  if (s.includes("LİDER") || s.includes("LIDER") || s.includes("YÜKSEL")) return "good";
  return "neutral";
}
function classifyUsdtD(v?: string): ChipTone {
  const s = (v || "").toUpperCase();
  if (s.includes("KAÇIŞ") || s.includes("YÜKSEL") || s.includes("ARTI")) return "risk";
  if (s.includes("DÜŞÜ") || s.includes("ZAYIF")) return "good";
  return "neutral";
}
function classifySafeHaven(v?: string): ChipTone {
  const s = (v || "").toUpperCase();
  if (s.includes("HEDGE") || s.includes("TALEP") || s.includes("YÜKSEK")) return "hedge";
  return "neutral";
}
function classifyM2(v?: string): ChipTone {
  const s = (v || "").toUpperCase();
  if (s.includes("GENİŞ") || s.includes("DESTEK") || s.includes("NORMAL")) return "good";
  if (s.includes("DARAL") || s.includes("ZAYIF")) return "risk";
  return "neutral";
}

function Chip({ label, value, tone }: { label: string; value: string; tone: ChipTone }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-mono whitespace-nowrap ${TONE_CLS[tone]}`}
    >
      <span className="opacity-70">{label}:</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

interface Props {
  macro?:    MacroLayer;
  appetite?: RiskAppetiteLayer;
}

export default function MacroRiskFilterStrip({ macro, appetite }: Props) {
  const [open, setOpen] = useState(false);
  const hasData = !!macro && !!appetite;

  return (
    <div
      className="w-full max-w-full min-w-0 overflow-hidden rounded-xl border border-eyay-border bg-eyay-surface/40"
      data-testid="macro-risk-filter-strip"
    >
      <div className="px-3 py-2 border-b border-eyay-border/60 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
          <span className="text-[10px] font-mono text-cyan-300 uppercase tracking-widest font-semibold whitespace-nowrap">
            Macro / Risk Filter
          </span>
          <span className="text-[11px] text-eyay-dim truncate">
            {hasData
              ? "Likidite destekli ama risk iştahı seçici — geniş risk-on değil, asset bazlı sinyal."
              : "Makro/Risk verisi bekleniyor"}
          </span>
        </div>
        {hasData && (
          <button
            type="button"
            onClick={() => setOpen(o => !o)}
            className="shrink-0 rounded-md border border-cyan-700/40 bg-cyan-950/30 px-2 py-0.5 text-[10px] font-mono text-cyan-200 hover:bg-cyan-900/40 transition"
            aria-expanded={open}
          >
            {open ? "▴ Detayı gizle" : "▾ Detayları göster"}
          </button>
        )}
      </div>

      {hasData && (
        <div className="px-3 py-2 flex flex-wrap gap-1.5">
          <Chip label="Likidite"    value={firstWord(macro!.m2_signal)            || "destekli"}    tone={classifyM2(macro!.m2_signal)} />
          <Chip label="DXY"         value={firstWord(macro!.dxy_signal)           || "nötr"}        tone={classifyDxy(macro!.dxy_signal)} />
          <Chip label="Kredi/HYG"   value={firstWord(appetite!.credit_signal)     || "sağlam"}      tone={classifyCredit(appetite!.credit_signal)} />
          <Chip label="BTC.D"       value={firstWord(appetite!.btc_dominance_signal)  || "BTC lider"}   tone={classifyBtcD(appetite!.btc_dominance_signal)} />
          <Chip label="USDT.D"      value={firstWord(appetite!.usdt_dominance_signal) || "kaçış"}       tone={classifyUsdtD(appetite!.usdt_dominance_signal)} />
          <Chip label="Altın/XAUUSD" value={firstWord(appetite!.safe_haven_signal)    || "hedge talebi"} tone={classifySafeHaven(appetite!.safe_haven_signal)} />
        </div>
      )}

      {open && hasData && (
        <div className="border-t border-eyay-border/60 p-2">
          <MacroPanel macro={macro!} appetite={appetite!} showUnified={false} />
        </div>
      )}
    </div>
  );
}
