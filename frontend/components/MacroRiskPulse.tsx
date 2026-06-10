"use client";

/**
 * FAZ 22 — Macro / Risk Pulse rotating banner.
 *
 * Mevcut macro_layer + appetite_layer verisinden deterministik mesajlar
 * üretir; 5 saniyede bir döner. Hover/focus pause, reduced-motion statik.
 * Karar üretmez. Sadece görselleştirme.
 */
import { useEffect, useMemo, useState } from "react";

import type { MacroLayer, RiskAppetiteLayer } from "@/lib/types";

type Tone = "emerald" | "cyan" | "amber" | "red" | "blue" | "slate";

const TONE: Record<Tone, { ring: string; text: string; soft: string }> = {
  emerald: { ring: "#34d399", text: "text-emerald-300", soft: "rgba(52,211,153,0.15)" },
  cyan:    { ring: "#22d3ee", text: "text-cyan-300",    soft: "rgba(34,211,238,0.15)" },
  amber:   { ring: "#fbbf24", text: "text-amber-300",   soft: "rgba(251,191,36,0.15)" },
  red:     { ring: "#f87171", text: "text-red-300",     soft: "rgba(248,113,113,0.15)" },
  blue:    { ring: "#60a5fa", text: "text-blue-300",    soft: "rgba(96,165,250,0.15)" },
  slate:   { ring: "#94a3b8", text: "text-slate-300",   soft: "rgba(148,163,184,0.15)" },
};

interface PulseMsg { text: string; tone: Tone; tag: string; }

function toneFromText(text: string): Tone {
  const v = text.toUpperCase();
  if (v.includes("KAÇIŞ") || v.includes("KIRIYOR") || v.includes("BASKILI") || v.includes("İNVERSİYON")) return "red";
  if (v.includes("NORMAL") || v.includes("SAĞLAM") || v.includes("GENİŞLİYOR") || v.includes("ZAYIF") && v.includes("DXY")) return "emerald";
  if (v.includes("İZLE") || v.includes("GEÇIŞ") || v.includes("DARALIYOR")) return "amber";
  if (v.includes("NÖTR")) return "slate";
  return "cyan";
}

function buildPulseMessages(macro?: MacroLayer, appetite?: RiskAppetiteLayer): PulseMsg[] {
  const msgs: PulseMsg[] = [];
  if (macro) {
    if (macro.regime) {
      const rx: Record<string, [string, Tone]> = {
        RISK_ON:       ["Makro rejim risk-on — likidite destekli ortam.", "emerald"],
        TRANSITIONING: ["Makro rejim geçişte — pozisyonlama seçici.", "amber"],
        DEFENSIVE:     ["Makro rejim defansif — riski azalt.", "red"],
        CRISIS:        ["Makro rejim kriz — yüksek koruma modu.", "red"],
      };
      const m = rx[macro.regime];
      if (m) msgs.push({ text: m[0], tone: m[1], tag: "Rejim" });
    }
    if (macro.dxy_signal) msgs.push({ text: `DXY ${macro.dxy_signal.toLowerCase()} — dolar tarafı.`, tone: toneFromText(macro.dxy_signal), tag: "DXY" });
    if (macro.yield_curve_signal) msgs.push({ text: `Verim eğrisi ${macro.yield_curve_signal.toLowerCase()}.`, tone: toneFromText(macro.yield_curve_signal), tag: "Yield" });
    if (macro.m2_signal) msgs.push({ text: `M2 likidite ${macro.m2_signal.toLowerCase()}.`, tone: toneFromText(macro.m2_signal), tag: "M2" });
    if (macro.energy_signal) msgs.push({ text: `Enerji / Brent ${macro.energy_signal.toLowerCase()}.`, tone: toneFromText(macro.energy_signal), tag: "Brent" });
  }
  if (appetite) {
    if (appetite.status) {
      const ax: Record<string, [string, Tone]> = {
        STRONG:   ["Risk iştahı güçlü — piyasa atılgan.", "emerald"],
        MODERATE: ["Risk iştahı ölçülü — seçici alım.", "cyan"],
        WEAK:     ["Risk iştahı zayıf — defansif rotasyon.", "amber"],
        CRISIS:   ["Risk iştahı krizde — kaçış modu.", "red"],
      };
      const a = ax[appetite.status];
      if (a) msgs.push({ text: a[0], tone: a[1], tag: "İştah" });
    }
    if (appetite.credit_signal) msgs.push({ text: `Kredi (HYG) ${appetite.credit_signal.toLowerCase()} — kredi piyasası.`, tone: toneFromText(appetite.credit_signal), tag: "HYG" });
    if (appetite.btc_dominance_signal) msgs.push({ text: `BTC.D ${appetite.btc_dominance_signal.toLowerCase()} — kripto rotasyon.`, tone: toneFromText(appetite.btc_dominance_signal), tag: "BTC.D" });
    if (appetite.usdt_dominance_signal) {
      const t = toneFromText(appetite.usdt_dominance_signal);
      msgs.push({ text: `USDT.D ${appetite.usdt_dominance_signal.toLowerCase()} — stablecoin sığınma.`, tone: t === "emerald" ? "red" : t, tag: "USDT.D" });
    }
    if (appetite.safe_haven_signal) msgs.push({ text: `Altın ${appetite.safe_haven_signal.toLowerCase()} — güvenli liman.`, tone: "blue", tag: "Altın" });
  }
  if (msgs.length === 0) {
    msgs.push({ text: "Makro/Risk verisi bekleniyor.", tone: "slate", tag: "—" });
  }
  return msgs;
}

const ROTATE_MS = 5000;

interface Props {
  macro?: MacroLayer;
  appetite?: RiskAppetiteLayer;
}

export default function MacroRiskPulse({ macro, appetite }: Props) {
  const messages = useMemo(() => buildPulseMessages(macro, appetite), [macro, appetite]);
  const [idx,     setIdx]     = useState(0);
  const [animate, setAnimate] = useState(false);
  const [paused,  setPaused]  = useState(false);
  const [open,    setOpen]    = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    return () => mq.removeEventListener?.("change", onMQ);
  }, []);

  useEffect(() => {
    if (!animate || paused || messages.length <= 1) return;
    const t = setInterval(() => setIdx(i => (i + 1) % messages.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [animate, paused, messages.length]);

  const safeIdx = Math.min(idx, messages.length - 1);
  const cur     = messages[safeIdx];
  const tone    = TONE[cur.tone];

  return (
    <div
      data-testid="macro-risk-pulse"
      className="w-full max-w-full min-w-0 overflow-hidden rounded-xl border bg-black/30"
      style={{ borderColor: `${tone.ring}55` }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      <style>{`
        @keyframes mrp-fade { from{opacity:0;transform:translateY(3px)} to{opacity:1;transform:none} }
      `}</style>
      {/* Banner satırı */}
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="flex items-center gap-1 shrink-0">
          <span className="w-1 h-1 rounded-full" style={{ background: tone.ring, boxShadow: animate ? `0 0 5px ${tone.ring}` : undefined }} />
          <p className="text-[8px] font-mono uppercase tracking-[0.2em] text-cyan-300/70">
            Macro / Risk Pulse
          </p>
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <p key={cur.text} className={`text-[10px] font-mono leading-snug truncate ${tone.text}`}
             style={animate ? { animation: "mrp-fade 0.45s ease" } : undefined}>
            {cur.text}
          </p>
        </div>
        <span className="text-[8px] font-mono shrink-0 rounded border px-1 py-0.5"
              style={{ color: tone.ring, borderColor: `${tone.ring}55`, background: tone.soft }}>
          {cur.tag}
        </span>
        {/* dot indicators */}
        <div className="flex items-center gap-1 shrink-0">
          <button type="button" aria-label="Önceki"
                  onClick={() => setIdx(i => (i - 1 + messages.length) % messages.length)}
                  className="text-cyan-300/60 text-[10px] hover:text-cyan-200 px-0.5">‹</button>
          {messages.map((_, i) => (
            <span key={i} className="w-1 h-1 rounded-full"
                  style={{ background: i === safeIdx ? tone.ring : "rgba(148,163,184,0.35)" }} />
          ))}
          <button type="button" aria-label="Sonraki"
                  onClick={() => setIdx(i => (i + 1) % messages.length)}
                  className="text-cyan-300/60 text-[10px] hover:text-cyan-200 px-0.5">›</button>
        </div>
        <button type="button"
                onClick={() => setOpen(o => !o)}
                aria-expanded={open}
                className="ml-1 shrink-0 text-[8.5px] font-mono text-cyan-300/70 hover:text-cyan-200 border border-cyan-700/40 rounded px-1.5 py-0.5">
          {open ? "▾ Detay" : "▸ Detay"}
        </button>
      </div>

      {/* Detay accordion — Katman 2 + Katman 3 kompakt */}
      {open && (
        <div className="border-t border-cyan-700/20 bg-black/40 px-3 py-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <p className="text-[8px] font-mono text-cyan-400/60 uppercase tracking-widest mb-1">
              Makro Detay
            </p>
            {macro ? (
              <ul className="space-y-0.5 text-[9px] font-mono text-eyay-dim">
                {macro.regime && <li>Rejim: <span className="text-eyay-text">{macro.regime}</span></li>}
                {macro.dxy_signal && <li>DXY: {macro.dxy_signal}</li>}
                {macro.yield_curve_signal && <li>Yield: {macro.yield_curve_signal}</li>}
                {macro.m2_signal && <li>M2: {macro.m2_signal}</li>}
                {macro.energy_signal && <li>Brent: {macro.energy_signal}</li>}
                {macro.summary && <li className="pt-1 text-eyay-faint italic">{macro.summary}</li>}
              </ul>
            ) : <p className="text-[9px] font-mono text-eyay-faint italic">veri yok</p>}
          </div>
          <div>
            <p className="text-[8px] font-mono text-cyan-400/60 uppercase tracking-widest mb-1">
              Risk İştahı Detay
            </p>
            {appetite ? (
              <ul className="space-y-0.5 text-[9px] font-mono text-eyay-dim">
                {appetite.status && <li>Durum: <span className="text-eyay-text">{appetite.status}</span></li>}
                {appetite.credit_signal && <li>Kredi (HYG): {appetite.credit_signal}</li>}
                {appetite.btc_dominance_signal && <li>BTC.D: {appetite.btc_dominance_signal}</li>}
                {appetite.usdt_dominance_signal && <li>USDT.D: {appetite.usdt_dominance_signal}</li>}
                {appetite.safe_haven_signal && <li>Altın: {appetite.safe_haven_signal}</li>}
                {appetite.summary && <li className="pt-1 text-eyay-faint italic">{appetite.summary}</li>}
              </ul>
            ) : <p className="text-[9px] font-mono text-eyay-faint italic">veri yok</p>}
          </div>
        </div>
      )}
    </div>
  );
}
