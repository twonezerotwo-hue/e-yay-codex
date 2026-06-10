"use client";

/**
 * FAZ 19 — Holographic Event Calendar Layer v3 (calendar-first).
 *
 * Konsept: alt katmanda **geniş holografik takvim zemini** (gün hücreleri),
 * aktif gün hücresinden yukarı yükselen **takvim yaprağı / event sheet**.
 * 220px sticky sidebar uyumlu. Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 * Crash → EventCalendarErrorBoundary → legacy CatalystSidebar.
 */
import { useEffect, useMemo, useState } from "react";

import type { CatalystEvent } from "@/lib/types";

// ── Tone map ──────────────────────────────────────────────────────────────────

type Importance = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

const TONE: Record<string, { ring: string; soft: string; label: string; text: string; weight: number }> = {
  CRITICAL: { ring: "#f87171", soft: "rgba(248,113,113,0.22)", label: "KRİTİK", text: "text-red-300",    weight: 4 },
  HIGH:     { ring: "#fb923c", soft: "rgba(251,146,60,0.22)",  label: "YÜKSEK", text: "text-orange-300", weight: 3 },
  MEDIUM:   { ring: "#22d3ee", soft: "rgba(34,211,238,0.20)",  label: "ORTA",   text: "text-cyan-300",   weight: 2 },
  LOW:      { ring: "#94a3b8", soft: "rgba(148,163,184,0.18)", label: "DÜŞÜK",  text: "text-slate-300",  weight: 1 },
};

function toneOf(imp: string): typeof TONE["LOW"] {
  const k = (imp || "").toUpperCase() as Importance;
  return TONE[k] ?? TONE.LOW;
}

function ymd(d: Date | string): string {
  const dt = typeof d === "string" ? new Date(d) : d;
  if (isNaN(dt.getTime())) return "";
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const day = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function fmtDateLong(iso: string): { day: string; month: string; weekday: string } {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return { day: "—", month: "", weekday: "" };
  return {
    day:     String(d.getDate()).padStart(2, "0"),
    month:   d.toLocaleDateString("tr-TR", { month: "short" }).toUpperCase(),
    weekday: d.toLocaleDateString("tr-TR", { weekday: "long" }),
  };
}

// ── Impact narrative helper (deterministik; uydurma veri yok) ────────────────

export function buildCatalystImpactNarrative(ev: CatalystEvent): string[] {
  const name = (ev.name || "").toLowerCase();
  const imp  = (ev.importance || "").toUpperCase();

  if (/fomc|fed (faiz|karar)|federal reserve|faiz karar/.test(name)) {
    return [
      "Şahin ton → DXY ve tahvil faizleri güçlenebilir; hisse ve altın baskılanabilir.",
      "Güvercin ton → risk iştahı toparlanabilir; teknoloji hisseleri ve altın destek bulabilir.",
      "Karar metni ve dot plot tonu asıl fiyatlamayı belirler.",
    ];
  }
  if (/cpi|tüfe|enflasyon\b|inflation/.test(name)) {
    return [
      "Beklenti üstü enflasyon → Fed indirimi ötelenir; DXY güçlenebilir.",
      "Beklenti altı veri → risk-on tepki görülebilir; tahvil ve hisse rahatlayabilir.",
      "İlk reaksiyonda DXY, US10Y ve Nasdaq yakından izlenmeli.",
    ];
  }
  if (/ppi|üretici fiyat|producer price/.test(name)) {
    return [
      "Üretici fiyat baskısı sonraki CPI beklentilerini etkileyebilir.",
      "DXY ve faiz tarafında ikinci kademe fiyatlama yaratabilir.",
    ];
  }
  if (/nfp|tarım dışı|nonfarm|payroll|işsizlik|unemployment/.test(name)) {
    return [
      "Güçlü istihdam → Fed'in sıkı duruşu desteklenebilir.",
      "Zayıf veri → faiz indirimi beklentisini öne çekebilir.",
      "İlk tepki DXY ve US10Y tahvil faizlerinde görülmeli.",
    ];
  }
  if (/ecb|avrupa merkez|european central/.test(name)) {
    return [
      "Şahin ECB → EUR güçlenebilir; DXY baskılanabilir.",
      "Güvercin ECB → euro bölgesi tahvilleri destek bulabilir.",
    ];
  }
  if (/boe|bank of england|ingiltere merkez/.test(name)) {
    return [
      "Şahin BoE → GBP güçlenebilir; FTSE baskılanabilir.",
      "Güvercin BoE → İngiliz tahvilleri destek bulabilir.",
    ];
  }
  if (/boj|japon merkez|bank of japan/.test(name)) {
    return [
      "YCC/faiz adımı USDJPY ve Japon tahvillerinde sert reaksiyon üretebilir.",
      "Yen carry trade etkileri global tahvil getirilerini hareketlendirebilir.",
    ];
  }
  if (/opec|petrol|brent|crude|oil/.test(name)) {
    return [
      "Üretim kesintisi → Brent yukarı yönlü tepki verebilir.",
      "Beklenti üzeri arz → enerji hisseleri ve Brent baskılanabilir.",
      "Risk priminin DXY ve enerji hisselerine yansıması izlenmeli.",
    ];
  }
  if (/jeopol|war|savaş|attack|saldırı|conflict|gaza|israel|iran|ukraine|russia|hormuz/.test(name)) {
    return [
      "Risk-off reaksiyon → altın ve DXY destek bulabilir; hisseler baskılanabilir.",
      "Enerji tarafında ani yukarı boşluk olasılığı izlenmeli.",
      "VIX yükselişi ve high-yield spread genişlemesi öncü sinyal olabilir.",
    ];
  }
  if (/earnings|bilanço|kar açıklama|kazanç/.test(name)) {
    return [
      "Beklenti üzeri sonuç → ilgili sektörde momentum hızlanabilir.",
      "Beklenti altı sonuç → sektörel rotasyon ve volatilite üretebilir.",
    ];
  }
  if (/gdp|büyüme|growth/.test(name)) {
    return [
      "Beklenti üstü büyüme → risk-on; DXY ve tahvil faizleri yukarı kıpırdayabilir.",
      "Beklenti altı veri → resesyon endişesi, altın ve uzun vadeli tahviller destek bulabilir.",
    ];
  }
  if (/retail|perakende/.test(name)) {
    return [
      "Güçlü tüketici harcamaları → Fed'in sıkı duruşunu destekler.",
      "Zayıf veri → resesyon temasını öne çıkarabilir; defansif sektörler öne çıkabilir.",
    ];
  }
  if (/pmi|imalat|manufacturing/.test(name)) {
    return [
      "50 üzeri PMI → genişleme; hisse senedi pozitif.",
      "50 altı PMI → daralma sinyali; defansif rotasyon görülebilir.",
    ];
  }

  if (imp === "LOW") return ["Düşük etki beklentisi; ana yön değişimi olası değil."];
  if (!ev.expectation && !ev.market_impact) {
    return [
      "Beklenti kaydı yok; fiyatlama daha çok açıklama tonu üzerinden okunmalı.",
      "İlk reaksiyon DXY, tahvil ve hisse endeksleri tarafında izlenmeli.",
    ];
  }
  return [
    "Volatilite artışı beklenebilir.",
    "İlk reaksiyon DXY, US10Y, hisse endeksleri ve altın tarafında izlenmeli.",
  ];
}

// ── Calendar grid hesabı ─────────────────────────────────────────────────────

const GRID_COLS = 5;
const GRID_ROWS = 4;
const GRID_DAYS = GRID_COLS * GRID_ROWS;

function buildGridDays(events: CatalystEvent[]): Date[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // İlk event ile bugün arası en küçük günü baz al — bugün geçmişteki event'i de gösterelim
  let start = today;
  for (const ev of events) {
    const d = new Date(ev.date);
    if (!isNaN(d.getTime())) {
      d.setHours(0, 0, 0, 0);
      if (d < start) start = d;
    }
  }
  // Bugünden çok geride başlamayalım — max 2 gün geriye git
  const minStart = new Date(today);
  minStart.setDate(today.getDate() - 2);
  if (start < minStart) start = minStart;

  return Array.from({ length: GRID_DAYS }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

// ── Component ────────────────────────────────────────────────────────────────

const ROTATE_MS = 5000;

interface Props {
  catalysts: CatalystEvent[];
}

export default function EventCalendar3DLayer({ catalysts }: Props) {
  const events = catalysts.slice(0, 12);
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

  const gridDays = useMemo(() => buildGridDays(events), [events]);

  // YMD → highest tone weight (öncelikli importance göster)
  const eventByDate = useMemo(() => {
    const m = new Map<string, { events: CatalystEvent[]; tone: typeof TONE["LOW"] }>();
    for (const ev of events) {
      const key = ymd(ev.date);
      if (!key) continue;
      const t = toneOf(ev.importance);
      const prev = m.get(key);
      if (!prev || t.weight > prev.tone.weight) {
        m.set(key, { events: [ev, ...(prev?.events ?? []).filter(e => e !== ev)], tone: t });
      } else {
        prev.events.push(ev);
      }
    }
    return m;
  }, [events]);

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

  const safeSel       = Math.min(selected, events.length - 1);
  const active        = events[safeSel];
  const tone          = toneOf(active.importance);
  const narrative     = buildCatalystImpactNarrative(active);
  const activeYMD     = ymd(active.date);
  const activeCellIdx = gridDays.findIndex(d => ymd(d) === activeYMD);
  const beamCol       = activeCellIdx >= 0 ? activeCellIdx % GRID_COLS : -1;

  const longDate = fmtDateLong(active.date);
  const dayNames = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

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
        @keyframes ec-pulse  { 0%,100%{opacity:.35;transform:scale(1)} 50%{opacity:.9;transform:scale(1.4)} }
        @keyframes ec-rise   { from{opacity:0;transform:translateY(10px) scale(0.96)} to{opacity:1;transform:none} }
        @keyframes ec-breathe{ 0%,100%{opacity:0.78;filter:brightness(1)} 50%{opacity:1;filter:brightness(1.25)} }
        @keyframes ec-beam   { 0%,100%{opacity:0.55} 50%{opacity:1} }
        @keyframes ec-cellpulse { 0%,100%{box-shadow:0 0 6px var(--c)} 50%{box-shadow:0 0 14px var(--c)} }
      `}</style>

      {/* Header */}
      <div className="relative flex items-center gap-1.5 px-3 py-1.5 border-b border-cyan-500/20 bg-gradient-to-r from-black/50 via-cyan-950/20 to-black/50">
        <span aria-hidden="true" className="text-cyan-400/80 text-[10px]"
              style={animate ? { animation: "ec-breathe 3s ease-in-out infinite" } : undefined}>◈</span>
        <div className="min-w-0">
          <p className="text-[9.5px] font-mono font-bold text-cyan-100 uppercase tracking-[0.22em] truncate">
            Holographic Event Calendar
          </p>
          <p className="text-[7.5px] font-mono text-cyan-400/60 truncate">
            takvim bazlı makro katalizörler
          </p>
        </div>
        <span className="ml-auto text-[8px] font-mono text-cyan-400/70 border border-cyan-700/40 rounded px-1 shrink-0">
          {events.length}
        </span>
      </div>

      {/* HERO — Rising event sheet */}
      <div className="relative px-3 pt-3 pb-2 overflow-hidden">
        {/* Köşe brackets */}
        <span aria-hidden="true" className="absolute top-1.5 left-1.5 w-2.5 h-2.5 border-t border-l border-cyan-400/40" />
        <span aria-hidden="true" className="absolute top-1.5 right-1.5 w-2.5 h-2.5 border-t border-r border-cyan-400/40" />

        <div
          key={active.id}
          className="relative rounded-xl border backdrop-blur-md px-2.5 py-2"
          style={{
            background: `linear-gradient(165deg, rgba(8,28,52,0.92), rgba(3,12,26,0.96)), radial-gradient(circle at 50% 0%, ${tone.ring}44, transparent 65%)`,
            borderColor: `${tone.ring}77`,
            boxShadow: animate
              ? `0 18px 28px -10px ${tone.ring}aa, 0 0 26px ${tone.soft}, inset 0 1px 0 ${tone.ring}66`
              : `0 0 12px ${tone.soft}, inset 0 1px 0 ${tone.ring}44`,
            animation: animate ? "ec-rise 0.55s ease" : undefined,
          }}
        >
          {/* Yaprak üst kenarı (sheen) */}
          <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px rounded-t-xl"
               style={{ background: `linear-gradient(90deg, transparent, ${tone.ring}, transparent)` }} />

          {/* Tarih bandı (büyük gün + ay + weekday) */}
          <div className="flex items-start gap-2 pb-1.5 mb-1.5 border-b border-cyan-700/25">
            <div className="flex flex-col items-center justify-center rounded-lg border px-1.5 py-1 shrink-0"
                 style={{ borderColor: `${tone.ring}66`, background: tone.soft }}>
              <p className="text-[7px] font-mono text-eyay-faint leading-none">{longDate.month}</p>
              <p className="text-[18px] font-mono font-bold leading-none mt-0.5" style={{ color: tone.ring }}>
                {longDate.day}
              </p>
              <p className="text-[7px] font-mono text-eyay-faint leading-none mt-0.5">{longDate.weekday}</p>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 mb-0.5">
                <span className="rounded px-1 py-0.5 text-[7.5px] font-mono font-black border"
                      style={{ color: tone.ring, borderColor: `${tone.ring}77`, background: tone.soft }}>
                  {tone.label}
                </span>
                <span className="text-[7.5px] font-mono text-eyay-faint truncate min-w-0">
                  {active.category}
                </span>
                <span className="ml-auto text-[7.5px] font-mono font-bold shrink-0 rounded px-1 border"
                      style={{ color: tone.ring, borderColor: `${tone.ring}55` }}>
                  {active.days_until >= 0 ? `+${active.days_until}g` : `${active.days_until}g`}
                </span>
              </div>
              <p className="text-[10.5px] font-mono font-bold text-eyay-text leading-snug line-clamp-2">
                {active.name}
              </p>
            </div>
          </div>

          {/* Expectation / market impact */}
          {active.expectation && (
            <p className="text-[8.5px] font-mono text-eyay-dim leading-snug line-clamp-2">
              ◇ {active.expectation}
            </p>
          )}
          {active.market_impact && (
            <p className="text-[8.5px] font-mono text-eyay-faint leading-snug line-clamp-2 mt-0.5">
              ↪ {active.market_impact}
            </p>
          )}

          {/* Tahmin / Olası Etki */}
          <div className="mt-1.5 pt-1.5 border-t border-cyan-700/25">
            <p className="text-[7.5px] font-mono uppercase tracking-[0.22em] mb-1"
               style={{ color: tone.ring, opacity: 0.85 }}>
              ✦ Tahmin / Olası Etki
            </p>
            <ul className="space-y-0.5">
              {narrative.map((line, i) => (
                <li key={i} className="text-[8.5px] font-mono text-eyay-dim leading-snug flex gap-1">
                  <span style={{ color: tone.ring }}>›</span>
                  <span className="min-w-0">{line}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Beam — sheet'in altından grid'e */}
        {beamCol >= 0 && (
          <div aria-hidden="true" className="relative h-3 pointer-events-none">
            <div
              className="absolute top-0 bottom-0"
              style={{
                left: `calc(${(beamCol + 0.5) * (100 / GRID_COLS)}% )`,
                width: "12px",
                marginLeft: "-6px",
                background: `linear-gradient(180deg, ${tone.ring}aa, ${tone.ring}55, transparent)`,
                clipPath: "polygon(36% 0, 64% 0, 100% 100%, 0 100%)",
                filter: animate ? `drop-shadow(0 0 6px ${tone.ring})` : undefined,
                animation: animate ? "ec-beam 1.6s ease-in-out infinite" : undefined,
              }}
            />
          </div>
        )}
      </div>

      {/* CALENDAR BOARD — gün hücreleri */}
      <div className="relative px-3 pb-2"
           style={{
             background:
               "radial-gradient(ellipse 90% 70% at 50% 100%, rgba(34,211,238,0.10), transparent 70%)",
           }}>
        {/* Weekday header (compact) */}
        <div className="grid grid-cols-5 gap-0.5 mb-1">
          {Array.from({ length: GRID_COLS }, (_, i) => (
            <div key={i} className="text-center text-[6.5px] font-mono text-cyan-500/50 uppercase tracking-widest">
              {dayNames[(gridDays[i]?.getDay() + 6) % 7]}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-5 gap-0.5">
          {gridDays.map((d, i) => {
            const key  = ymd(d);
            const hit  = eventByDate.get(key);
            const isActive = key === activeYMD;
            const t = hit?.tone;
            const dayNum = d.getDate();

            const handleClick = () => {
              if (!hit) return;
              const idx = events.indexOf(hit.events[0]);
              if (idx >= 0) setSelected(idx);
            };

            return (
              <button
                key={i}
                type="button"
                onClick={handleClick}
                disabled={!hit}
                aria-label={`${dayNum}`}
                className="relative rounded-md aspect-square flex items-center justify-center transition-all"
                style={{
                  background: isActive && t
                    ? `linear-gradient(160deg, ${t.soft}, rgba(3,12,26,0.7))`
                    : "rgba(34,211,238,0.04)",
                  border: isActive && t
                    ? `1px solid ${t.ring}aa`
                    : "1px solid rgba(34,211,238,0.15)",
                  cursor: hit ? "pointer" : "default",
                  // @ts-expect-error css custom property
                  "--c": t ? `${t.ring}99` : "rgba(34,211,238,0.25)",
                  animation: isActive && animate ? "ec-cellpulse 2.2s ease-in-out infinite" : undefined,
                }}
              >
                <span className="text-[8.5px] font-mono font-bold leading-none"
                      style={{ color: isActive && t ? t.ring : "rgba(148,163,184,0.55)" }}>
                  {dayNum}
                </span>
                {hit && !isActive && (
                  <span aria-hidden="true" className="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full"
                        style={{ background: hit.tone.ring, boxShadow: animate ? `0 0 4px ${hit.tone.ring}` : undefined }} />
                )}
                {isActive && t && animate && (
                  <span aria-hidden="true" className="absolute inset-0 rounded-md pointer-events-none"
                        style={{ background: `radial-gradient(circle at center, ${t.ring}33, transparent 70%)`,
                                 animation: "ec-pulse 2s ease-in-out infinite" }} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Mini timeline */}
      <div className="px-3 pb-2 space-y-0.5 max-h-[120px] overflow-y-auto"
           style={{ scrollbarWidth: "thin" }}>
        <div className="flex items-center gap-1 mb-1">
          <span aria-hidden="true" className="h-px flex-1 bg-cyan-700/25" />
          <span className="text-[7px] font-mono text-cyan-400/60 uppercase tracking-[0.25em]">
            Yaklaşan
          </span>
          <span aria-hidden="true" className="h-px flex-1 bg-cyan-700/25" />
        </div>
        {events.slice(0, 6).map((e, i) => {
          const tt = toneOf(e.importance);
          const isAct = i === safeSel;
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => setSelected(i)}
              className="w-full flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-left transition-all"
              style={{
                background: isAct ? `linear-gradient(90deg, ${tt.soft}, transparent)` : "transparent",
                borderLeft: `2px solid ${isAct ? tt.ring : "transparent"}`,
              }}
            >
              <span className="shrink-0 w-1 h-1 rounded-full"
                    style={{ background: tt.ring, boxShadow: animate && isAct ? `0 0 5px ${tt.ring}` : undefined }} />
              <span className="text-[7.5px] font-mono font-bold shrink-0" style={{ color: tt.ring }}>
                {String(new Date(e.date).getDate()).padStart(2, "0")}/{String(new Date(e.date).getMonth() + 1).padStart(2, "0")}
              </span>
              <span className="text-[8px] font-mono text-eyay-dim truncate min-w-0 flex-1">
                {e.name}
              </span>
              <span className="text-[7px] font-mono text-eyay-faint shrink-0">
                +{e.days_until}g
              </span>
            </button>
          );
        })}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-eyay-border/30 bg-black/30">
        <p className="text-[7px] font-mono text-eyay-faint/55 text-center">
          PAPER_SAFE · NO_EXECUTION · sadece görselleştirme
        </p>
      </div>
    </div>
  );
}
