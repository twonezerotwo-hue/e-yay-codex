"use client";

/**
 * Agent Insight Bar — sayfanın üstünde sticky bant.
 *
 * Bant içeriği: yeni /agent/banner endpoint'inden dinamik, durum odaklı banner.
 *   • mode=risk_alert       → kırmızı bant + anomali detayı
 *   • mode=contradiction    → turuncu bant + thesis sanity uyarısı
 *   • mode=managing_position→ yeşil bant + açık pozisyon özeti
 *   • mode=learning         → yeşil bant + öğrenme adayı
 *   • mode=waiting          → mavi/slate bant + son karar
 *
 * Tıklayınca: AgentCommandCenter (pipeline analizi) açılır.
 * ESC veya backdrop tıklayınca kapanır.
 *
 * Groq'a istek YAPMAZ — saf analiz katmanı.
 * FAZ 10.1: /agent/banner (stored-data banner) birincil kaynak.
 *           /agent/insight (pipeline insights) sadece modal için.
 */
import { useEffect, useState } from "react";
import AgentCommandCenter from "./AgentCommandCenter";
import type { NewsHeadline } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentInsight {
  severity:   "CRITICAL" | "WARNING" | "OPPORTUNITY" | "OBSERVATION";
  headline:   string;
  detail:     string;
  asset_code: string;
  icon:       string;
  generated_at: string;
}

type BannerMode = "waiting" | "managing_position" | "contradiction" | "risk_alert" | "learning";

interface AgentBanner {
  mode:          BannerMode;
  headline:      string;
  main_view:     string;
  top_signals:   string[];
  contradictions: string[];
  watch_next:    string[];
  position_note: string | null;
  learning_note: string | null;
  updated_at:    string;
}

// ── Mode → stil eşlemesi ──────────────────────────────────────────────────────

const MODE_STYLE: Record<BannerMode, {
  bg:    string;
  border: string;
  text:  string;
  dot:   string;
  label: string;
}> = {
  risk_alert: {
    bg:     "bg-red-950/60",
    border: "border-red-800/70",
    text:   "text-red-200",
    dot:    "bg-red-400",
    label:  "RİSK UYARISI",
  },
  contradiction: {
    bg:     "bg-amber-950/50",
    border: "border-amber-800/60",
    text:   "text-amber-200",
    dot:    "bg-amber-400",
    label:  "ÇELİŞKİ",
  },
  managing_position: {
    bg:     "bg-emerald-950/40",
    border: "border-emerald-800/60",
    text:   "text-emerald-200",
    dot:    "bg-emerald-400",
    label:  "POZİSYON",
  },
  learning: {
    bg:     "bg-emerald-950/30",
    border: "border-emerald-900/50",
    text:   "text-emerald-300",
    dot:    "bg-emerald-500",
    label:  "ÖĞRENME",
  },
  waiting: {
    bg:     "bg-eyay-raised",
    border: "border-eyay-border",
    text:   "text-eyay-dim",
    dot:    "bg-eyay-blue/60",
    label:  "BEKLİYOR",
  },
};

// Fallback: eski insight'lardan severity → mode eşlemesi
const SEVERITY_TO_MODE: Record<AgentInsight["severity"], BannerMode> = {
  CRITICAL:    "risk_alert",
  WARNING:     "contradiction",
  OPPORTUNITY: "managing_position",
  OBSERVATION: "waiting",
};

// ── Bileşen ───────────────────────────────────────────────────────────────────

export default function AgentInsightBar({ headlines = [] }: { headlines?: NewsHeadline[] }) {
  // Banner endpoint (FAZ 10.1 — birincil)
  const [banner,   setBanner]   = useState<AgentBanner | null>(null);
  // Insight endpoint (sadece modal için)
  const [insights, setInsights] = useState<AgentInsight[]>([]);
  const [insIdx,   setInsIdx]   = useState(0);

  const [open,    setOpen]    = useState(false);
  const [loading, setLoading] = useState(true);

  // ── Banner polling (birincil, 30sn)
  useEffect(() => {
    let cancelled = false;
    async function loadBanner() {
      try {
        const res = await fetch("/api/backend/agent/banner", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: AgentBanner = await res.json();
        if (!cancelled) {
          setBanner(data);
          setLoading(false);
        }
      } catch {
        // Banner endpoint başarısızsa loading'i kaldır ama banner null kalır
        if (!cancelled) setLoading(false);
      }
    }
    loadBanner();
    const id = setInterval(loadBanner, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ── Insight polling (modal için, 60sn)
  useEffect(() => {
    let cancelled = false;
    async function loadInsights() {
      try {
        const res = await fetch("/api/backend/agent/insight", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) setInsights(data.insights || []);
      } catch { /* silent */ }
    }
    loadInsights();
    const id = setInterval(loadInsights, 60_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ── Insight rotation (insight array'i varsa, modal kapalıyken)
  useEffect(() => {
    if (open || insights.length <= 1) return;
    const r = setInterval(() => {
      setInsIdx(prev => (prev + 1) % insights.length);
    }, 5000);
    return () => clearInterval(r);
  }, [open, insights.length]);

  // ── Modal açıkken: ESC + body scroll lock + global event
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

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="sticky top-0 z-40 bg-eyay-surface/95 backdrop-blur-md border-b border-eyay-border shadow-lg shadow-black/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-4">
          <span className="text-sm font-mono text-eyay-faint uppercase tracking-widest">🤖 Agent</span>
          <span className="text-base text-eyay-faint italic">Veriler taranıyor…</span>
        </div>
      </div>
    );
  }

  // Banner yoksa insight'lardan fallback; ikisi de yoksa null
  const stripMode: BannerMode = banner?.mode
    ?? (insights[insIdx] ? SEVERITY_TO_MODE[insights[insIdx].severity] : null)
    ?? "waiting";
  const stripHeadline: string = banner?.headline
    ?? insights[insIdx]?.headline
    ?? "";

  if (!stripHeadline) return null;

  const st = MODE_STYLE[stripMode];

  return (
    <>
      {/* ═══════════════════════════════════════════════════════════════════
          KAPALI HAL — tek satır sticky bant
         ═══════════════════════════════════════════════════════════════════ */}
      <div className={`sticky top-0 z-40 backdrop-blur-md border-b ${st.border} ${st.bg} shadow-xl shadow-black/40 relative`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 sm:py-5">
          <button
            onClick={() => setOpen(true)}
            className="w-full flex items-center gap-4 group"
          >
            {/* Agent badge */}
            <span className="shrink-0 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/10 bg-black/30">
              <span className={`w-3 h-3 rounded-full ${st.dot} animate-pulse`} />
              <span className="text-base font-mono font-bold text-eyay-text uppercase tracking-widest">
                🤖 AGENT
              </span>
            </span>

            {/* Mode label */}
            <span className={`shrink-0 text-base font-mono font-black tracking-widest ${st.text}`}>
              {st.label}
            </span>

            {/* Headline */}
            <span className={`flex-1 text-left text-lg font-medium truncate ${st.text}`}>
              {stripHeadline}
            </span>

            {/* Banner'dan gelen extra context: watch_next veya top signal */}
            {banner?.watch_next?.length ? (
              <span className={`shrink-0 hidden sm:block text-sm font-mono max-w-[280px] truncate ${st.text} opacity-70`}>
                {banner.watch_next[0]}
              </span>
            ) : null}

            <span className="shrink-0 text-sm font-mono text-eyay-faint group-hover:text-eyay-blue transition-colors">
              detay ›
            </span>
          </button>
        </div>
        {/* Alt fade */}
        <div className="pointer-events-none absolute -bottom-6 left-0 right-0 h-6 bg-gradient-to-b from-black/30 to-transparent" />
      </div>

      {/* AÇIK HAL — Agent Komut Merkezi (pipeline insights modalı) */}
      {open && <AgentCommandCenter onClose={() => setOpen(false)} headlines={headlines} />}
    </>
  );
}
