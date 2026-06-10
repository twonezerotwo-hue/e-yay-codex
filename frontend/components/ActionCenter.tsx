"use client";

/**
 * Launch Control Dock — Decision Launch Pad altındaki
 * operasyonel adımlar, iyileşme sinyalleri ve kriz tetikleyicileri için
 * roket kalkış kontrol paneli görünümü.
 *
 * Veri kaynakları (mevcut backend payload'u — aynen kullanılır):
 *   • ownerActions     → Görev Kontrol checklist (T-minus checklist)
 *   • flipConditions[up]   → Clearance Signals (launch clearance lamps)
 *   • flipConditions[down] → Abort Triggers (abort lamps)
 *
 * Frontend-only visual layer. PAPER_SAFE / NO_EXECUTION korunur.
 */
import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";

import type { Decision, FlipCondition } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ── Open state context (paylaşılan "tam metin göster" durumu) ────────────────

const DockOpenContext = createContext(false);
const useDockOpen = () => useContext(DockOpenContext);

// ── Karar teması ─────────────────────────────────────────────────────────────

type DeckMode = "clearance" | "hold" | "throttle_down" | "abort";

const DECK_BY_DECISION: Record<Decision, {
  mode:        DeckMode;
  label:       string;
  badge:       string;     // tailwind classes
  countdown:   string;     // countdown caption
  accent:      string;
  accentBg:    string;
  accentBorder:string;
  stepNum:     string;
}> = {
  AÇIL:   { mode: "clearance",     label: "LAUNCH CLEARANCE", countdown: "T-0 · clearance verildi",
            badge: "bg-emerald-500/15 text-emerald-200 border-emerald-500/60",
            accent: "text-emerald-300", accentBg: "bg-emerald-950/25",
            accentBorder: "border-emerald-900/50",
            stepNum: "bg-emerald-500/15 text-emerald-300 border-emerald-700/40" },
  BEKLE:  { mode: "hold",          label: "HOLD",             countdown: "T-− · geri sayım duraklatıldı",
            badge: "bg-amber-500/15 text-amber-200 border-amber-500/60",
            accent: "text-amber-300", accentBg: "bg-amber-950/20",
            accentBorder: "border-amber-900/45",
            stepNum: "bg-amber-500/15 text-amber-300 border-amber-700/40" },
  KÜÇÜLT: { mode: "throttle_down", label: "THROTTLE DOWN",    countdown: "Itki azaltılıyor · abort riski",
            badge: "bg-orange-500/15 text-orange-200 border-orange-500/60",
            accent: "text-orange-300", accentBg: "bg-orange-950/20",
            accentBorder: "border-orange-900/45",
            stepNum: "bg-orange-500/15 text-orange-300 border-orange-700/40" },
  KAPAT:  { mode: "abort",         label: "ABORT LOCK",       countdown: "Abort sistemi devrede",
            badge: "bg-red-500/15 text-red-200 border-red-500/60",
            accent: "text-red-300", accentBg: "bg-red-950/25",
            accentBorder: "border-red-900/55",
            stepNum: "bg-red-500/15 text-red-300 border-red-700/40" },
};

// ── Helpers: mevcut metinden kısa başlık + alt satır türet ───────────────────

function splitCurrent(raw: string): { rest: string; current: string | null } {
  const m = raw.match(/\(şu an[:\s]*([^)]+)\)/i);
  if (!m) return { rest: raw.trim(), current: null };
  return { rest: raw.replace(m[0], "").trim(), current: m[1].trim() };
}

function splitTitleSub(raw: string): { title: string; sub: string | null; current: string | null } {
  const { rest, current } = splitCurrent(raw);
  // Önce belirgin ayraçları dene
  const sep = [" — ", "—", " · ", " - ", ": "];
  for (const s of sep) {
    const idx = rest.indexOf(s);
    if (idx > 4 && idx < 60) {
      return {
        title: rest.slice(0, idx).trim(),
        sub:   rest.slice(idx + s.length).trim() || null,
        current,
      };
    }
  }
  // Ayraç yoksa: kısa başlık + line-clamp (sub aynı metin değil → null)
  if (rest.length <= 56) return { title: rest, sub: null, current };
  // Uzun cümle: ilk virgüle kadar başlık, kalan subtext
  const ci = rest.indexOf(", ");
  if (ci > 6 && ci < 60) {
    return { title: rest.slice(0, ci).trim(), sub: rest.slice(ci + 2).trim(), current };
  }
  // Son çare: ilk 7 kelime başlık, kalan subtext
  const words = rest.split(" ");
  return { title: words.slice(0, 7).join(" "), sub: words.slice(7).join(" ") || null, current };
}

const formatChecklistItem = splitTitleSub;
const formatSignalCondition = splitTitleSub;
const formatTriggerCondition = splitTitleSub;

// ── Mini lamp ────────────────────────────────────────────────────────────────

function Lamp({ tone, animate }: { tone: "green" | "red" | "amber" | "blue"; animate: boolean }) {
  const c =
    tone === "green" ? "#34d399" :
    tone === "red"   ? "#f87171" :
    tone === "amber" ? "#fbbf24" : "#60a5fa";
  return (
    <span
      aria-hidden="true"
      className="inline-block shrink-0 rounded-full"
      style={{
        width: 8, height: 8,
        background: `radial-gradient(circle, ${c} 0%, ${c}55 70%, transparent 100%)`,
        boxShadow: `0 0 6px ${c}aa`,
        animation: animate
          ? (tone === "red" ? "lcd-blink 1.8s ease-in-out infinite"
                            : "lcd-glow 2.6s ease-in-out infinite")
          : undefined,
      }}
    />
  );
}

// ── Dock column header ───────────────────────────────────────────────────────

function ColumnHeader({
  tag, title, sub, accent, lampTone, badge, animate,
}: {
  tag: string; title: string; sub: string; accent: string;
  lampTone: "green" | "red" | "amber" | "blue";
  badge?: { text: string; cls: string };
  animate: boolean;
}) {
  return (
    <div className="px-3 py-2 border-b border-white/5 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 min-w-0">
        <Lamp tone={lampTone} animate={animate} />
        <div className="min-w-0">
          <p className={`text-[8px] font-mono uppercase tracking-[0.18em] ${accent} opacity-80`}>{tag}</p>
          <p className={`text-[11.5px] font-bold leading-tight ${accent}`}>{title}</p>
          <p className="text-[9px] text-eyay-faint truncate">{sub}</p>
        </div>
      </div>
      {badge && (
        <span className={`shrink-0 text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${badge.cls}`}>
          {badge.text}
        </span>
      )}
    </div>
  );
}

// ── Detail toggle row wrapper ────────────────────────────────────────────────

function DetailToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="w-full text-[8.5px] font-mono uppercase tracking-widest text-eyay-faint hover:text-eyay-dim border-t border-white/5 bg-black/20 py-1 transition-colors"
      aria-expanded={open}
    >
      {open ? "▴ Tam metni gizle" : "▾ Tam metni göster"}
    </button>
  );
}

// ── Operational checklist row ────────────────────────────────────────────────

function ChecklistRow({
  index, raw, stepNum, accent, open,
}: {
  index: number; raw: string; stepNum: string; accent: string; open: boolean;
}) {
  const { title, sub } = formatChecklistItem(raw);
  return (
    <li className="flex items-start gap-2 py-1 group hover:bg-white/[0.025] rounded-md px-1 -mx-1 transition-colors">
      <span className={`shrink-0 mt-0.5 flex items-center justify-center w-5 h-5 rounded-md border font-mono text-[9px] font-black ${stepNum}`}>
        T{index + 1}
      </span>
      <div className="flex-1 min-w-0">
        <p className={`text-[10.5px] font-semibold leading-snug ${accent}`}>{title}</p>
        {sub && (
          <p
            className="text-[9.5px] text-eyay-dim leading-snug mt-0.5"
            style={open ? undefined : { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
            title={!open ? sub : undefined}
          >
            {sub}
          </p>
        )}
        {open && !sub && (
          <p className="text-[9.5px] text-eyay-dim leading-snug mt-0.5">{raw}</p>
        )}
      </div>
    </li>
  );
}

// ── Clearance / Abort condition row ──────────────────────────────────────────

function ConditionRow({
  raw, tone, accent, open,
}: {
  raw: string; tone: "green" | "red" | "amber"; accent: string; open: boolean;
}) {
  const { title, sub, current } = formatSignalCondition(raw);
  return (
    <li className="flex items-start gap-2 py-1 group hover:bg-white/[0.025] rounded-md px-1 -mx-1 transition-colors">
      <span className="shrink-0 mt-1"><Lamp tone={tone} animate={false} /></span>
      <div className="flex-1 min-w-0">
        <p className={`text-[10.5px] font-semibold leading-snug ${accent}`}>{title}</p>
        {sub && (
          <p
            className="text-[9.5px] text-eyay-dim leading-snug mt-0.5"
            style={open ? undefined : { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
            title={!open ? sub : undefined}
          >
            {sub}
          </p>
        )}
        {current && (
          <p className="text-[9px] mt-0.5">
            <span className="text-eyay-faint">şu an: </span>
            <span className={`font-mono font-semibold ${accent}`}>{current}</span>
          </p>
        )}
      </div>
    </li>
  );
}

// ── Dock column (Checklist / Clearance / Abort) ──────────────────────────────

interface ColumnProps {
  tag:        string;
  title:      string;
  sub:        string;
  accent:     string;
  border:     string;
  bg:         string;
  lampTone:   "green" | "red" | "amber" | "blue";
  badge?:     { text: string; cls: string };
  footerNote: string;
  animate:    boolean;
  children:   ReactNode;
}

function DockColumn({
  tag, title, sub, accent, border, bg, lampTone, badge, footerNote, animate, children,
}: ColumnProps) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`relative w-full max-w-full min-w-0 overflow-hidden rounded-xl border ${border} ${bg} flex flex-col`}>
      {/* Connector line bağlantısı (üstte gradient ışık) */}
      <div
        aria-hidden="true"
        className="absolute inset-x-2 top-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, currentColor, transparent)`, opacity: 0.35 }}
      />
      <ColumnHeader tag={tag} title={title} sub={sub} accent={accent} lampTone={lampTone} badge={badge} animate={animate} />
      <ol className="px-3 py-2 flex-1 min-h-0 overflow-hidden max-h-[260px] overflow-y-auto">
        {/* clone children with `open` prop injected via context substitute */}
        <DockOpenContext.Provider value={open}>{children}</DockOpenContext.Provider>
      </ol>
      <div className="px-3 py-1 border-t border-white/5 bg-black/20 flex items-center justify-between gap-2">
        <p className="text-[8px] font-mono text-eyay-faint tracking-wider truncate">{footerNote}</p>
      </div>
      <DetailToggle open={open} onToggle={() => setOpen(o => !o)} />
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

interface ActionCenterProps {
  decision:        Decision;
  ownerActions:    string[];
  flipConditions:  FlipCondition[];
}

export default function ActionCenter({ decision, ownerActions, flipConditions }: ActionCenterProps) {
  const { t } = useLanguage();
  const deck = DECK_BY_DECISION[decision] ?? DECK_BY_DECISION.BEKLE;

  const animate =
    typeof window !== "undefined"
      ? !window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : true;

  const upGroup   = flipConditions?.find(fc => fc.icon === "up");
  const downGroup = flipConditions?.find(fc => fc.icon === "down");

  const hasChecklist = (ownerActions?.length ?? 0) > 0;
  const hasClearance = (upGroup?.conditions?.length ?? 0) > 0;
  const hasAbort     = (downGroup?.conditions?.length ?? 0) > 0;

  if (!hasChecklist && !hasClearance && !hasAbort) return null;

  return (
    <div className="w-full max-w-full min-w-0 overflow-hidden rounded-2xl border border-eyay-border bg-eyay-surface/40">
      <style>{`
        @keyframes lcd-glow { 0%,100%{filter:brightness(1);opacity:0.82} 50%{filter:brightness(1.25);opacity:1} }
        @keyframes lcd-blink { 0%,100%{filter:brightness(0.9);opacity:0.6} 50%{filter:brightness(1.4);opacity:1} }
      `}</style>

      {/* Dock header — roket kontrol bandı */}
      <div className="relative px-3 py-2 border-b border-eyay-border/60 bg-gradient-to-r from-black/40 via-cyan-950/15 to-black/40 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" style={animate ? { boxShadow: "0 0 6px #22d3ee" } : undefined} />
          <p className="text-[10px] font-mono text-cyan-300 uppercase tracking-[0.22em] font-semibold whitespace-nowrap">
            Launch Control Dock
          </p>
          <p className="text-[10.5px] text-eyay-dim truncate">
            {deck.countdown}
          </p>
        </div>
        <span className={`shrink-0 rounded-md border px-2 py-0.5 text-[9px] font-mono font-bold tracking-widest ${deck.badge}`}>
          {deck.label}
        </span>
      </div>

      {/* Dock 3 columns */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-2 p-2">

        {hasChecklist && (
          <DockColumn
            tag="T-MINUS"
            title="Launch Checklist"
            sub="Şimdi ne yapılmalı?"
            accent={deck.accent}
            border={deck.accentBorder}
            bg={deck.accentBg}
            lampTone={deck.mode === "abort" || deck.mode === "throttle_down" ? "amber" : "blue"}
            badge={{ text: deck.label, cls: deck.badge }}
            footerNote={`${t.actionCenter.operationalSteps} · PAPER_SAFE · NO_EXECUTION`}
            animate={animate}
          >
            <ChecklistList items={ownerActions} stepNum={deck.stepNum} accent={deck.accent} />
          </DockColumn>
        )}

        {hasClearance && upGroup && (
          <DockColumn
            tag="GREEN LAMPS"
            title="Clearance Signals"
            sub="Yeşil ışık için gerekenler"
            accent="text-emerald-300"
            border="border-emerald-900/40"
            bg="bg-emerald-950/15"
            lampTone="green"
            badge={{ text: `${upGroup.conditions.length} lamp`, cls: "bg-emerald-500/15 text-emerald-300 border-emerald-700/40" }}
            footerNote="hepsi yeşil olduğunda kalkış izni açılır"
            animate={animate}
          >
            <ConditionList items={upGroup.conditions} tone="green" accent="text-emerald-300" />
          </DockColumn>
        )}

        {hasAbort && downGroup && (
          <DockColumn
            tag="ABORT LAMPS"
            title="Abort Triggers"
            sub="Risk artarsa iptal şartları"
            accent="text-red-300"
            border="border-red-900/40"
            bg="bg-red-950/15"
            lampTone="red"
            badge={{ text: `${downGroup.conditions.length} lamp`, cls: "bg-red-500/15 text-red-300 border-red-700/40" }}
            footerNote="gerçekleşirse karar güncellenir · abort sistemi devreye girer"
            animate={animate}
          >
            <ConditionList items={downGroup.conditions} tone="red" accent="text-red-300" />
          </DockColumn>
        )}
      </div>
    </div>
  );
}

// ── Inner list renderers (consume DockOpenContext) ──────────────────────────

function ChecklistList({ items, stepNum, accent }: {
  items: string[]; stepNum: string; accent: string;
}) {
  const open = useDockOpen();
  return (
    <>
      {items.map((raw, i) => (
        <ChecklistRow key={i} index={i} raw={raw} stepNum={stepNum} accent={accent} open={open} />
      ))}
    </>
  );
}

function ConditionList({ items, tone, accent }: {
  items: string[]; tone: "green" | "red" | "amber"; accent: string;
}) {
  const open = useDockOpen();
  return (
    <>
      {items.map((raw, i) => (
        <ConditionRow key={i} raw={raw} tone={tone} accent={accent} open={open} />
      ))}
    </>
  );
}

export { formatChecklistItem, formatSignalCondition, formatTriggerCondition };
