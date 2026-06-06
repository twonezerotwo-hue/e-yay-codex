"use client";

/**
 * Agent Insight Bar — sayfanın üstünde sticky bant.
 *
 * Kapalıyken: tek satırlık bant, rotation ile 5sn'de bir farklı insight.
 * Tıklayınca: TÜM SAYFAYI kaplayan dark overlay (modal) açılır,
 *             tüm insights net listelenir, arka plandaki dashboard gizlenir.
 *             ESC veya backdrop tıklayınca kapanır.
 *
 * Groq'a istek YAPMAZ — saf analiz katmanı (eşik kıyaslamaları).
 */
import { useEffect, useState } from "react";
import AgentCommandCenter from "./AgentCommandCenter";

interface AgentInsight {
  severity:  "CRITICAL" | "WARNING" | "OPPORTUNITY" | "OBSERVATION";
  headline:  string;
  detail:    string;
  asset_code: string;
  icon:      string;
  generated_at: string;
}

const SEVERITY_STYLE: Record<AgentInsight["severity"], {
  bg:        string;
  border:    string;
  text:      string;
  dot:       string;
  label:     string;
  modalAccent: string;
}> = {
  CRITICAL:    {
    bg: "bg-red-950/60",     border: "border-red-800/70",     text: "text-red-200",     dot: "bg-red-400",
    label: "KRİTİK",  modalAccent: "from-red-900/40 to-red-950/20",
  },
  WARNING:     {
    bg: "bg-amber-950/50",   border: "border-amber-800/60",   text: "text-amber-200",   dot: "bg-amber-400",
    label: "DİKKAT",  modalAccent: "from-amber-900/30 to-amber-950/10",
  },
  OPPORTUNITY: {
    bg: "bg-emerald-950/40", border: "border-emerald-800/60", text: "text-emerald-200", dot: "bg-emerald-400",
    label: "FIRSAT",  modalAccent: "from-emerald-900/30 to-emerald-950/10",
  },
  OBSERVATION: {
    bg: "bg-eyay-raised",    border: "border-eyay-border",    text: "text-eyay-dim",    dot: "bg-eyay-blue/60",
    label: "GÖZLEM",  modalAccent: "from-slate-900/40 to-slate-950/20",
  },
};

export default function AgentInsightBar() {
  const [insights, setInsights] = useState<AgentInsight[]>([]);
  const [idx,      setIdx]      = useState(0);
  const [open,     setOpen]     = useState(false);   // modal mı açık?
  const [loading,  setLoading]  = useState(true);

  // ── Backend polling
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/backend/agent/insight", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setInsights(data.insights || []);
          setLoading(false);
          setIdx(0);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 60_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // ── Modal kapalıyken: insight rotation
  useEffect(() => {
    if (open || insights.length <= 1) return;
    const r = setInterval(() => {
      setIdx(prev => (prev + 1) % insights.length);
    }, 5000);
    return () => clearInterval(r);
  }, [open, insights.length]);

  // ── Modal açıkken: ESC ile kapat + body scroll lock + global event yayını
  // (TradingTicker ve AutoRefresh modal açıkken gizlenir — sayfada agent dışında bir şey görünmez)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    document.body.dataset.agentModalOpen = "true";
    window.dispatchEvent(new CustomEvent("eyay:agent-modal", { detail: { open: true } }));
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      delete document.body.dataset.agentModalOpen;
      window.dispatchEvent(new CustomEvent("eyay:agent-modal", { detail: { open: false } }));
    };
  }, [open]);

  if (loading) {
    return (
      <div className="sticky top-0 z-40 bg-eyay-surface/95 backdrop-blur border-b border-eyay-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 flex items-center gap-3">
          <span className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">🤖 Agent</span>
          <span className="text-xs text-eyay-faint italic">Veriler taranıyor…</span>
        </div>
      </div>
    );
  }

  if (insights.length === 0) return null;

  const cur = insights[idx];
  const st  = SEVERITY_STYLE[cur.severity];

  return (
    <>
      {/* ═══════════════════════════════════════════════════════════════════
          KAPALI HAL — tek satır sticky bant
         ═══════════════════════════════════════════════════════════════════ */}
      <div className={`sticky top-0 z-40 backdrop-blur border-b ${st.border} ${st.bg}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2">
          <button
            onClick={() => setOpen(true)}
            className="w-full flex items-center gap-3 group"
          >
            <span className="shrink-0 inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-white/10 bg-black/30">
              <span className={`w-1.5 h-1.5 rounded-full ${st.dot} animate-pulse`} />
              <span className="text-[9px] font-mono font-bold text-eyay-text uppercase tracking-widest">
                🤖 AGENT
              </span>
            </span>

            <span className={`shrink-0 text-[9px] font-mono font-black tracking-widest ${st.text}`}>
              {st.label}{cur.icon && <span className="ml-1">{cur.icon}</span>}
            </span>

            <span className={`flex-1 text-left text-xs font-medium truncate ${st.text}`}>
              {cur.headline}
            </span>

            {insights.length > 1 && (
              <span className="shrink-0 text-[9px] font-mono text-eyay-faint">
                {idx + 1}/{insights.length}
              </span>
            )}

            <span className="shrink-0 text-[9px] font-mono text-eyay-faint group-hover:text-eyay-blue transition-colors">
              tümünü gör ›
            </span>
          </button>
        </div>
      </div>

      {/* AÇIK HAL — Agent Komut Merkezi */}
      {open && <AgentCommandCenter onClose={() => setOpen(false)} />}
    </>
  );
}
