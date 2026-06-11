"use client";

/**
 * FAZ 29 — Agent Brief Panel.
 *
 * Ana dashboard'daki "Decision Launch Pad" / roket görselinin yerine geçer.
 * Sade premium kart: sol Agent Core mini görsel, orta aksiyon brief, sağ status
 * chipler + "Agent Detayı" butonu. Buton agent modalını açmak için custom event
 * dispatch eder; mevcut AgentInsightBar bunu dinler.
 * Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useState } from "react";

import type { Decision, RegimeReport } from "@/lib/types";

// ── Mode mapping ─────────────────────────────────────────────────────────────

type Mode = "ONAY" | "BEKLE" | "KÜÇÜLT" | "KAPAT" | "İZLE";

interface ModeMeta {
  label:     Mode;
  toneRing:  string;
  toneSoft:  string;
  borderCls: string;
  bgCls:     string;
  textCls:   string;
  action:    string;
  reason:    string;
  note:      string;
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
    borderCls: "border-emerald-600/50", bgCls: "bg-emerald-950/25",
    textCls: "text-emerald-300",
    action: "Planlı girişe izin var; risk limitini aşma.",
    reason: "Teknik teyit ve kredi desteği aynı yönde çalışıyor (HYG $78 üstü / VIX sakin).",
    note:   "Risk iştahı destekli; agresif fakat disiplinli kalmak gerekir.",
  },
  BEKLE: {
    label: "BEKLE", toneRing: "#fbbf24", toneSoft: "rgba(251,191,36,0.18)",
    borderCls: "border-amber-600/50", bgCls: "bg-amber-950/25",
    textCls: "text-amber-300",
    action: "Yeni pozisyon açma; teyit bekle.",
    reason: "BTC güçlü kapanış teyidi yok ($58,000 / $57,889); Brent hâlâ risk primi taşıyor ($85 altı rahatlama).",
    note:   "Kredi tarafı panik üretmiyor, fakat enerji/event riski agresif kararı engelliyor.",
  },
  KÜÇÜLT: {
    label: "KÜÇÜLT", toneRing: "#fb923c", toneSoft: "rgba(251,146,60,0.18)",
    borderCls: "border-orange-600/50", bgCls: "bg-orange-950/25",
    textCls: "text-orange-300",
    action: "Pozisyonu kademeli azalt; panik satış yapma.",
    reason: "Risk/ödül bozuldu; kritik destekler zayıflıyor (BTC $57,889 / HYG $78).",
    note:   "Riski azaltırken yapısal alım fırsatlarını kaybetmeden ölçülü hareket.",
  },
  KAPAT: {
    label: "KAPAT", toneRing: "#f87171", toneSoft: "rgba(248,113,113,0.18)",
    borderCls: "border-red-600/50", bgCls: "bg-red-950/25",
    textCls: "text-red-300",
    action: "Yeni risk alma; koruma moduna geç.",
    reason: "Kritik eşik kırıldı veya blok sinyali aktif (HYG $74 altı / VIX $25 üstü).",
    note:   "Sermaye koruma birinci öncelik; piyasa stabilize olana kadar gözlemleyici kal.",
  },
  "İZLE": {
    label: "İZLE", toneRing: "#60a5fa", toneSoft: "rgba(96,165,250,0.18)",
    borderCls: "border-blue-600/50", bgCls: "bg-slate-900/40",
    textCls: "text-blue-300",
    action: "Acele etme; net sinyal bekle.",
    reason: "Sinyaller karışık; belirgin yön üstünlüğü yok.",
    note:   "Trend netleşene kadar pozisyonel tercih yapmamak en sağlıklı tutum.",
  },
};

// ── Mini Agent Core SVG ──────────────────────────────────────────────────────

function MiniAgentCore({ tone, animate }: { tone: string; animate: boolean }) {
  return (
    <svg viewBox="0 0 100 100" className="w-full h-full max-w-[110px] max-h-[110px]"
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <radialGradient id="abp-core" cx="50%" cy="50%" r="60%">
          <stop offset="0%"  stopColor="#fff" stopOpacity="0.8" />
          <stop offset="30%" stopColor={tone} stopOpacity="0.7" />
          <stop offset="100%" stopColor="#020812" />
        </radialGradient>
      </defs>
      <g style={animate ? { transformOrigin: "50px 50px", animation: "abp-spin 30s linear infinite" } : undefined}>
        <circle cx="50" cy="50" r="42" fill="none" stroke={tone} strokeWidth="0.6" strokeDasharray="4 6" opacity="0.5" />
        {Array.from({ length: 6 }, (_, i) => {
          const a = (i / 6) * Math.PI * 2;
          const x = 50 + Math.cos(a) * 42;
          const y = 50 + Math.sin(a) * 42;
          return <circle key={i} cx={x} cy={y} r="1.6" fill={tone} opacity="0.8" />;
        })}
      </g>
      <g style={animate ? { transformOrigin: "50px 50px", animation: "abp-spin 20s linear infinite reverse" } : undefined}>
        <circle cx="50" cy="50" r="30" fill="none" stroke={tone} strokeWidth="0.5" strokeDasharray="2 4" opacity="0.55" />
      </g>
      <circle cx="50" cy="50" r="22" fill="none" stroke={tone} strokeWidth="0.8" opacity="0.55"
              style={animate ? { transformOrigin: "50px 50px", animation: "abp-pulse 2.6s ease-in-out infinite" } : undefined} />
      <circle cx="50" cy="50" r="17" fill="url(#abp-core)" />
      <circle cx="50" cy="50" r="17" fill="none" stroke={tone} strokeWidth="0.8" />
    </svg>
  );
}

// ── Component ────────────────────────────────────────────────────────────────

interface Props { report: RegimeReport; }

export default function AgentBriefPanel({ report }: Props) {
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

  const openAgentModal = () => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent("eyay:open-agent-modal", { detail: { source: "brief" } }));
  };

  return (
    <div
      data-testid="agent-brief-panel"
      className={`w-full max-w-full min-w-0 overflow-hidden rounded-2xl border ${m.borderCls} ${m.bgCls}`}
      style={{ boxShadow: animate ? `0 0 16px ${m.toneSoft}, inset 0 1px 0 ${m.toneRing}28` : `0 0 8px ${m.toneSoft}` }}
    >
      <style>{`
        @keyframes abp-spin  { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        @keyframes abp-pulse { 0%,100%{transform:scale(1);opacity:0.55} 50%{transform:scale(1.12);opacity:0.85} }
        @keyframes abp-fade  { from{opacity:0;transform:translateY(3px)} to{opacity:1;transform:none} }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-cyan-500/20 bg-gradient-to-r from-black/40 via-cyan-950/15 to-black/40 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span aria-hidden="true" className={m.textCls}>◈</span>
          <div className="min-w-0">
            <p className="text-[11px] font-mono font-black text-cyan-50 uppercase tracking-[0.24em] truncate">
              e-yAy <span className={m.textCls}>AGENT BRIEF</span>
            </p>
            <p className="text-[9px] font-mono text-cyan-400/65 truncate">
              Agent Layer · yorumlayan · açıklayan · karar vermeyen
            </p>
          </div>
        </div>
        <span className="font-mono text-[10px] text-eyay-faint shrink-0">{time}</span>
      </div>

      {/* Body: agent core | brief | status chips */}
      <div className="grid grid-cols-1 sm:grid-cols-[110px_minmax(0,1fr)_220px] gap-3 p-3"
           style={{ minHeight: 0 }}>
        {/* Sol: Mini Agent Core */}
        <div className="hidden sm:flex items-center justify-center min-w-0">
          <MiniAgentCore tone={m.toneRing} animate={animate} />
        </div>

        {/* Orta: Action brief */}
        <div className="flex flex-col gap-2 min-w-0" key={mode}
             style={animate ? { animation: "abp-fade 0.45s ease" } : undefined}>
          <div className="flex items-center gap-2">
            <span className={`rounded-md border px-2 py-0.5 text-[11px] font-mono font-black uppercase tracking-widest ${m.borderCls}`}
                  style={{ color: m.toneRing, background: m.toneSoft }}>
              {m.label}
            </span>
            <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">
              Tavsiye edilen aksiyon
            </p>
          </div>

          <div>
            <p className="text-[10px] font-mono text-slate-300/80 uppercase tracking-widest mb-0.5">Aksiyon</p>
            <p className={`text-sm font-semibold leading-snug ${m.textCls}`}>{m.action}</p>
          </div>

          <div>
            <p className="text-[10px] font-mono text-slate-300/80 uppercase tracking-widest mb-0.5">Neden</p>
            <p className="text-[12px] font-mono text-slate-200/90 leading-snug line-clamp-3">{m.reason}</p>
          </div>

          <div className="pt-1.5 border-t border-cyan-700/20">
            <p className="text-[10px] font-mono uppercase tracking-widest mb-0.5"
               style={{ color: m.toneRing, opacity: 0.85 }}>✦ Agent notu</p>
            <p className="text-[11px] font-mono text-slate-200/85 leading-snug line-clamp-2">{m.note}</p>
          </div>
        </div>

        {/* Sağ: chipler + Detay butonu */}
        <div className="flex flex-col gap-1.5 min-w-0">
          <div className="grid grid-cols-2 sm:grid-cols-1 gap-1.5">
            <Chip label="Mod"    value={m.label}    tone={m.toneRing} />
            <Chip label="Tarama" value={time}       tone="#22d3ee" />
            <Chip label="Mode"   value="PAPER_SAFE" tone="#34d399" />
            <Chip label="Exec"   value="NO_EXECUTION" tone="#94a3b8" />
          </div>
          <button
            type="button"
            onClick={openAgentModal}
            className="mt-1 w-full rounded-lg border border-cyan-500/45 bg-cyan-950/35 hover:bg-cyan-900/45 transition-colors px-3 py-2 text-[11px] font-mono font-bold text-cyan-100 uppercase tracking-wider focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            data-testid="agent-brief-open-modal">
            ◇ Agent Detayı
          </button>
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-eyay-border/40 bg-black/30">
        <p className="text-[9px] font-mono text-eyay-faint/75 text-center leading-relaxed">
          PAPER_SAFE · NO_EXECUTION · tüm gerçek kararlar insana aittir
        </p>
      </div>
    </div>
  );
}

// ── Chip helper ──────────────────────────────────────────────────────────────

function Chip({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-md border bg-black/40 px-2 py-1 min-w-0"
         style={{ borderColor: `${tone}44` }}>
      <p className="text-[8px] font-mono text-slate-400 uppercase tracking-widest leading-none">{label}</p>
      <p className="text-[10.5px] font-mono font-bold leading-tight truncate mt-0.5" style={{ color: tone }}>
        {value}
      </p>
    </div>
  );
}
