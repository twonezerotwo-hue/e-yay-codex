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

interface LiveStatus {
  tickAtMs:   number | null;   // tick zamanı (lokal ms)
  openCount:  number;
  pendingCount: number;
  unrealized: number;
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
  const [live,     setLive]     = useState<LiveStatus | null>(null);
  const [nowMs,    setNowMs]    = useState(Date.now());

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

  // ── Canlı durum (paper trading state) — 10sn'de bir
  useEffect(() => {
    let cancelled = false;
    async function loadLive() {
      try {
        const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const d = await res.json();
        const ageSec = typeof d.tick_age_seconds === "number" ? d.tick_age_seconds : null;
        setLive({
          tickAtMs:     ageSec !== null ? Date.now() - ageSec * 1000 : null,
          openCount:    Array.isArray(d.open_positions) ? d.open_positions.length : 0,
          pendingCount: Array.isArray(d.pending_orders) ? d.pending_orders.length : 0,
          unrealized:   typeof d.unrealized_pnl_usd === "number" ? d.unrealized_pnl_usd : 0,
        });
      } catch { /* sessiz */ }
    }
    loadLive();
    const t = setInterval(loadLive, 10_000);
    return () => { cancelled = true; clearInterval(t); };
  }, []);

  // Saniye sayacı tic-toc (tarama yaşı için)
  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(t);
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

  // tick yaşı — her saniye canlı (nowMs bağımlı)
  const liveTickAge = (() => {
    if (!live || live.tickAtMs === null) return null;
    return Math.max(0, (nowMs - live.tickAtMs) / 1000);
  })();

  if (loading) {
    return (
      <div className="sticky top-0 z-40 bg-eyay-surface/95 backdrop-blur border-b border-eyay-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-3">
          <span className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">🤖 Agent</span>
          <span className="text-xs text-eyay-faint italic">Veriler taranıyor…</span>
        </div>
      </div>
    );
  }

  if (insights.length === 0) return null;

  const cur = insights[idx];
  const st  = SEVERITY_STYLE[cur.severity];
  const tickStr = liveTickAge === null
    ? "—"
    : liveTickAge < 60
      ? `${Math.floor(liveTickAge)}s`
      : `${Math.floor(liveTickAge / 60)}dk`;
  const tickFresh = liveTickAge !== null && liveTickAge < 45;

  return (
    <>
      {/* ═══════════════════════════════════════════════════════════════════
          KAPALI HAL — sticky bant (büyütülmüş, canlı agent durum şeridi)
         ═══════════════════════════════════════════════════════════════════ */}
      <div className={`sticky top-0 z-40 backdrop-blur border-b ${st.border} ${st.bg}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3">
          <button
            onClick={() => setOpen(true)}
            className="w-full flex items-center gap-3 group"
          >
            {/* Agent rozet — canlı dot + etiket */}
            <span className="shrink-0 inline-flex items-center gap-2 px-2.5 py-1 rounded-md border border-white/10 bg-black/40">
              <span className="relative flex items-center justify-center">
                <span className={`absolute w-2.5 h-2.5 rounded-full ${st.dot} opacity-40 animate-ping`} />
                <span className={`relative w-2 h-2 rounded-full ${st.dot}`} />
              </span>
              <span className="text-[10px] font-mono font-bold text-eyay-text uppercase tracking-widest">
                AGENT
              </span>
              <span className={`text-[9px] font-mono ${tickFresh ? "text-emerald-300" : "text-eyay-faint"}`}>
                · {tickStr}
              </span>
            </span>

            {/* Severity etiketi */}
            <span className={`shrink-0 hidden sm:inline-flex items-center gap-1 text-[10px] font-mono font-black tracking-widest ${st.text}`}>
              {cur.icon && <span>{cur.icon}</span>}
              {st.label}
            </span>

            {/* Insight cümlesi */}
            <span className={`flex-1 text-left text-sm font-medium truncate ${st.text}`}>
              {cur.headline}
            </span>

            {/* Canlı metrikler — pozisyon / pending / unrealized */}
            {live && (
              <span className="shrink-0 hidden md:flex items-center gap-3 pl-3 border-l border-white/10">
                <span className="text-[10px] font-mono">
                  <span className="text-eyay-faint">Açık </span>
                  <span className="text-eyay-text font-bold">{live.openCount}</span>
                </span>
                {live.pendingCount > 0 && (
                  <span className="text-[10px] font-mono">
                    <span className="text-eyay-faint">Bekleyen </span>
                    <span className="text-amber-300 font-bold">{live.pendingCount}</span>
                  </span>
                )}
                {live.openCount > 0 && (
                  <span className="text-[10px] font-mono">
                    <span className="text-eyay-faint">PnL </span>
                    <span className={`font-bold ${live.unrealized >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                      {live.unrealized >= 0 ? "+" : "−"}${Math.abs(live.unrealized).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  </span>
                )}
              </span>
            )}

            {insights.length > 1 && (
              <span className="shrink-0 text-[10px] font-mono text-eyay-faint border border-white/10 rounded px-1.5 py-0.5">
                {idx + 1}/{insights.length}
              </span>
            )}

            <span className="shrink-0 text-[10px] font-mono text-eyay-faint group-hover:text-eyay-blue transition-colors">
              detay ›
            </span>
          </button>
        </div>
      </div>

      {/* AÇIK HAL — Agent Komut Merkezi */}
      {open && <AgentCommandCenter onClose={() => setOpen(false)} />}
    </>
  );
}
