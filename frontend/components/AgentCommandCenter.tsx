"use client";

/**
 * Agent Komut Merkezi — modal içeriği.
 *
 * Veri kaynakları:
 *   /api/backend/agent/banner    → dinamik mod/headline/signals/learning (FAZ 10.1)
 *   /api/backend/agent/insight   → pipeline insights (yaklaşan tetikleyiciler + gözlemler)
 *   /api/backend/trading/state   → açık pozisyonlar + trade history + PnL
 *
 * PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useMemo, useState } from "react";
import BreakingNewsPanelShell from "@/components/BreakingNewsPanelShell";
import LearningPanel from "@/components/LearningPanel";
import SystemHealthPanel from "@/components/SystemHealthPanel";
import MacroPanel from "@/components/MacroPanel";
import type { NewsHeadline } from "@/lib/types";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface AgentInsight {
  severity:     "CRITICAL" | "WARNING" | "OPPORTUNITY" | "OBSERVATION";
  headline:     string;
  detail:       string;
  asset_code:   string;
  icon:         string;
  generated_at: string;
}

interface InsightResponse {
  status: string;
  decision: string;
  paper_decision_label?: string;
  generated_at: string;
  insights: AgentInsight[];
}

interface Position {
  pair: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  current_price: number;
  entry_at: string;
  size_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  last_signal: string;
}

interface Trade {
  id: number;
  pair: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  exit_price: number;
  entry_at: string;
  exit_at: string;
  pnl_usd: number;
  pnl_pct: number;
  duration_min: number;
}

interface TradingState {
  starting_balance: number;
  equity: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  daily_pnl_usd: number;
  open_positions: Position[];
  trades: Trade[];
  trade_count: number;
  traded_pairs: string[];
  state_anomaly?: { active: boolean; reasons: string[] };
}

type BannerMode = "waiting" | "managing_position" | "contradiction" | "risk_alert" | "learning";

// AI Trade Opinion (ai_trade_opinion_v1) — net fikir katmanı
interface AssetOpinion {
  asset: string;
  opinion: string;
  conviction: string;
  score: number;
  why: string[];
  against: string[];
  trigger_needed: string;
  invalidation: string;
  suggested_action: string;
}

interface PositionOpinion {
  pair: string;
  side: string;
  opinion: string;
  conviction: string;
  reason: string;
  what_to_watch: string[];
  invalidation: string;
}

interface TradeOpinion {
  schema_version: string;
  generated_at: string;
  overall_view: string;
  market_opinion: string;
  asset_opinions: AssetOpinion[];
  open_position_opinions: PositionOpinion[];
  best_candidate: { asset: string; bias: string; reason: string; trigger: string; risk: string };
  no_trade_reason: string;
  next_3_triggers: string[];
  what_would_change_my_mind: string[];
  owner_brief: string;
}

const OPINION_STYLE: Record<string, string> = {
  LONG_BIAS:   "text-emerald-300 border-emerald-700/50 bg-emerald-950/30",
  HOLD:        "text-emerald-300 border-emerald-700/50 bg-emerald-950/30",
  SHORT_BIAS:  "text-red-300 border-red-700/50 bg-red-950/30",
  AVOID:       "text-red-300 border-red-700/50 bg-red-950/30",
  CLOSE_WATCH: "text-red-300 border-red-700/50 bg-red-950/30",
  REDUCE:      "text-amber-300 border-amber-700/50 bg-amber-950/30",
  WAIT:        "text-eyay-dim border-eyay-border bg-eyay-raised/40",
  WAIT_EVENT_CONFIRMATION: "text-amber-300 border-amber-700/50 bg-amber-950/20",
  MANUAL_REVIEW: "text-eyay-blue border-blue-800/50 bg-blue-950/20",
  ADD_ONLY_IF: "text-eyay-blue border-blue-800/50 bg-blue-950/20",
};

interface AgentBanner {
  mode:                BannerMode;
  headline:            string;
  main_view:           string;
  top_signals:         string[];
  contradictions:      string[];
  watch_next:          string[];
  position_note:       string | null;
  learning_note:       string | null;
  updated_at:          string;
  // FAZ 13 — piyasa fikri alanları
  market_thought?:      string;
  price_story?:         string;
  event_story?:         string;
  event_calendar_note?: string;
  market_pricing_note?: string;
  next_trigger?:        string;
  // FAZ 14 — haber farkındalığı
  news_story?:          string;
  source_news_titles?:  string[];
  generated_at?:        string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Styling
// ─────────────────────────────────────────────────────────────────────────────

const SEV: Record<AgentInsight["severity"], {
  dot: string; text: string; bg: string; border: string; label: string
}> = {
  CRITICAL:    { dot: "bg-red-400",     text: "text-red-300",     bg: "bg-red-950/30",     border: "border-red-800/50",     label: "KRİTİK"  },
  WARNING:     { dot: "bg-amber-400",   text: "text-amber-300",   bg: "bg-amber-950/30",   border: "border-amber-800/50",   label: "DİKKAT"  },
  OPPORTUNITY: { dot: "bg-emerald-400", text: "text-emerald-300", bg: "bg-emerald-950/30", border: "border-emerald-800/50", label: "FIRSAT"  },
  OBSERVATION: { dot: "bg-eyay-blue",   text: "text-eyay-dim",    bg: "bg-eyay-raised/40", border: "border-eyay-border",    label: "GÖZLEM"  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Narrative — banner endpoint'ten gelen veriye dayanır
// ─────────────────────────────────────────────────────────────────────────────

function buildNarrative(
  banner: AgentBanner | null,
  insights: AgentInsight[],
  trading: TradingState | null,
  decision: string,
): string {
  // ── Banner yüklendiyse: dinamik, moda özgü anlatı ─────────────────────────
  if (banner) {
    const parts: string[] = [];

    if (banner.mode === "risk_alert") {
      parts.push(banner.headline);
      if (banner.main_view) parts.push(banner.main_view);
      return parts.join(" · ");
    }

    if (banner.mode === "contradiction") {
      parts.push(banner.headline);
      if (banner.main_view) parts.push(banner.main_view);
      return parts.join(" · ");
    }

    if (banner.mode === "managing_position") {
      if (banner.main_view) parts.push(banner.main_view);
      if (trading && trading.open_positions.length > 0) {
        const pnl = trading.unrealized_pnl_usd;
        const dir = pnl >= 0 ? "kâr" : "zarar";
        parts.push(`Toplam açık PnL: ${dir} ${Math.abs(pnl).toFixed(0)} USD`);
      }
      return parts.join(". ") || banner.headline;
    }

    if (banner.mode === "learning") {
      parts.push(banner.headline);
      if (banner.main_view) parts.push(banner.main_view);
      return parts.join(". ");
    }

    // waiting — pozisyon yok, gerçek neden
    const isPlaceholder = !banner.main_view
      || banner.main_view.startsWith("Henüz")
      || banner.main_view === "Yeni trade için sinyal ve uygun market koşulları bekleniyor.";

    if (!isPlaceholder) {
      parts.push(`Pozisyon yok · ${banner.main_view}`);
    } else {
      parts.push("Pozisyon yok — aktif sinyal bekleniyor");
    }
    return parts.join(". ");
  }

  // ── Fallback: banner henüz yüklenmediyse minimal metin ────────────────────
  const crit = insights.filter(i => i.severity === "CRITICAL");
  const warn = insights.filter(i => i.severity === "WARNING");
  const opp  = insights.filter(i => i.severity === "OPPORTUNITY");
  const parts: string[] = [];

  if (crit.length > 0) {
    parts.push(`${crit.length} kritik sinyal: ${crit[0].headline.split("—")[0].trim()}`);
  } else if (warn.length > 0) {
    parts.push(warn[0].headline.split("—")[0].trim());
  } else if (opp.length > 0) {
    parts.push(`${opp.length} fırsat sinyali izleniyor`);
  } else if (decision) {
    parts.push(`Aktif karar: ${decision}`);
  }

  if (trading && trading.open_positions.length > 0) {
    const pnl = trading.unrealized_pnl_usd;
    const dir = pnl >= 0 ? "kâr" : "zarar";
    parts.push(`${trading.open_positions.length} pozisyon açık, ${dir} ${Math.abs(pnl).toFixed(0)} USD`);
  }

  return parts.join(" · ") || "Sistem stabil";
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60)    return `${Math.floor(diff)}s önce`;
    if (diff < 3600)  return `${Math.floor(diff / 60)}dk önce`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}sa önce`;
    return `${Math.floor(diff / 86400)}g önce`;
  } catch { return ""; }
}

function fmtUsd(n: number): string {
  return `${n >= 0 ? "+" : "−"}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

// ── SON DAKİKA — savaş haberleri filtresi ────────────────────────────────────
const WAR_COUNTRY_PATTERNS: RegExp[] = [
  /\b(ABD|USA?|United States|America[n]?)\b/i,
  /\b(İran|Iran)\b/i,
  /\b(İsrail|Israel)\b/i,
  /\b(Rusya|Russia[n]?)\b/i,
  /\b(Çin|China|Chinese)\b/i,
];
const WAR_KEYWORD_PATTERNS: RegExp[] = [
  /sava[şs]/i, /\bwar\b/i, /sald[ıi]r[ıi]/i, /\battack/i, /\bstrike/i,
  /çat[ıi][şs]ma/i, /\bconflict/i, /asker[îi]?/i, /\bmilitary\b/i,
  /\bf[üu]ze\b/i, /\bmissile\b/i, /bombal/i, /\bbomb/i, /i[şs]gal/i,
  /\binvasion\b/i, /ate[şs]kes/i, /\bceasefire\b/i, /cephe/i, /\bfront\b/i,
  /nükleer/i, /\bnuclear\b/i, /tırman/i, /\bescalat/i,
];
function isWarHeadline(h: NewsHeadline): boolean {
  const text = `${h.title ?? ""} ${h.title_tr ?? ""}`;
  return WAR_COUNTRY_PATTERNS.some(p => p.test(text)) && WAR_KEYWORD_PATTERNS.some(p => p.test(text));
}

// Banner mode → bant rengi
function modeColor(mode: BannerMode): string {
  switch (mode) {
    case "risk_alert":         return "text-red-300";
    case "contradiction":      return "text-amber-300";
    case "managing_position":  return "text-emerald-300";
    case "learning":           return "text-emerald-300";
    default:                   return "text-eyay-blue";
  }
}
function modeBorder(mode: BannerMode): string {
  switch (mode) {
    case "risk_alert":         return "border-red-800/50 bg-gradient-to-br from-red-950/20 to-transparent";
    case "contradiction":      return "border-amber-800/40 bg-gradient-to-br from-amber-950/15 to-transparent";
    case "managing_position":  return "border-emerald-800/40 bg-gradient-to-br from-emerald-950/15 to-transparent";
    case "learning":           return "border-emerald-900/30 bg-gradient-to-br from-emerald-950/10 to-transparent";
    default:                   return "border-eyay-blue/30 bg-gradient-to-br from-eyay-blue/10 to-eyay-blue/0";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function AgentCommandCenter({ onClose, headlines = [], macro, appetite }: {
  onClose: () => void;
  headlines?: NewsHeadline[];
  /** FAZ 21 — Sistem Kontrolleri accordion için ek prop'lar; opsiyonel. */
  macro?: import("@/lib/types").MacroLayer;
  appetite?: import("@/lib/types").RiskAppetiteLayer;
}) {
  const [diagOpen, setDiagOpen] = useState(false);
  // ── State ──────────────────────────────────────────────────────────────────
  const [banner,    setBanner]    = useState<AgentBanner | null>(null);
  const [opinion,   setOpinion]   = useState<TradeOpinion | null>(null);
  const [insights,  setInsights]  = useState<AgentInsight[]>([]);
  const [decision,  setDecision]  = useState("");
  const [insightAt, setInsightAt] = useState<string>("");
  const [trading,   setTrading]   = useState<TradingState | null>(null);
  const [now,       setNow]       = useState(Date.now());

  // ── Banner polling (FAZ 10.1 — birincil, 30sn)
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/backend/agent/banner", { cache: "no-store" });
        if (!res.ok) return;
        const data: AgentBanner = await res.json();
        if (!cancelled) setBanner(data);
      } catch { /* silent */ }
    }
    load();
    const id = setInterval(load, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ── AI Trade Opinion polling (60sn — backend cache ile uyumlu)
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/backend/agent/trade-opinion", { cache: "no-store" });
        if (!res.ok) return;
        const data: TradeOpinion = await res.json();
        if (!cancelled) setOpinion(data);
      } catch { /* silent */ }
    }
    load();
    const id = setInterval(load, 60_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // ── Insight + trading state polling (modal açıkken 15sn)
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [iRes, tRes] = await Promise.all([
          fetch("/api/backend/agent/insight", { cache: "no-store" }),
          fetch("/api/backend/trading/state",  { cache: "no-store" }),
        ]);
        const iData: InsightResponse = await iRes.json();
        const tData: TradingState    = await tRes.json();
        if (!cancelled) {
          setInsights(iData.insights || []);
          setDecision(iData.paper_decision_label || iData.decision || "");
          setInsightAt(iData.generated_at || "");
          setTrading(tData);
        }
      } catch { /* sessiz */ }
    }
    load();
    const i = setInterval(load, 15_000);
    return () => { cancelled = true; clearInterval(i); };
  }, []);

  // Anlık saat tic-toc
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 5_000);
    return () => clearInterval(t);
  }, []);

  // ── Türetilen veri ─────────────────────────────────────────────────────────
  const narrative = useMemo(
    () => buildNarrative(banner, insights, trading, decision),
    [banner, insights, trading, decision],
  );

  const activeDecisions = useMemo(() => {
    if (!trading) return [];
    return trading.open_positions.map(p => ({
      type: "POSITION" as const,
      pair: p.pair, side: p.side,
      pnl_usd: p.pnl_usd, pnl_pct: p.pnl_pct,
      entry_price: p.entry_price, current_price: p.current_price,
      entry_at: p.entry_at, last_signal: p.last_signal,
    }));
  }, [trading]);

  const triggers = useMemo(() => {
    return insights.filter(
      i => (i.severity === "WARNING" && /yakın|eşiğinde/.test(i.headline))
        || i.severity === "OPPORTUNITY"
    ).slice(0, 5);
  }, [insights]);

  const warHeadlines = useMemo(
    () => headlines.filter(isWarHeadline).slice(0, 4),
    [headlines],
  );

  const observations = useMemo(() => {
    const used = new Set(triggers.map(t => t.headline));
    return insights.filter(i => !used.has(i.headline));
  }, [insights, triggers]);

  const accuracy = useMemo(() => {
    if (!trading || trading.trades.length === 0) {
      return { winRate: null as number | null, wins: 0, losses: 0, totalRealized: 0 };
    }
    const wins   = trading.trades.filter(t => t.pnl_usd > 0).length;
    const losses = trading.trades.filter(t => t.pnl_usd < 0).length;
    const total  = wins + losses;
    return {
      winRate: total > 0 ? (wins / total) * 100 : null,
      wins, losses,
      totalRealized: trading.realized_pnl_usd,
    };
  }, [trading]);

  // Boş pozisyon mesajı — banner'dan gerçek neden
  const noPositionReason: string = useMemo(() => {
    if (banner?.mode === "waiting" && banner.main_view
        && !banner.main_view.startsWith("Henüz")
        && banner.main_view !== "Yeni trade için sinyal ve uygun market koşulları bekleniyor."
        && banner.main_view !== "Pozisyon yok — aktif sinyal bekleniyor") {
      return banner.main_view;
    }
    return "Şu an açık pozisyon yok — aktif sinyal bekliyorum";
  }, [banner]);

  // Banner'dan filtreli top_signals (kayıt yok olanları çıkar)
  const topSignals = useMemo(
    () => (banner?.top_signals ?? []).filter(s => s !== "kayıt yok").slice(0, 3),
    [banner],
  );

  const contradictions = useMemo(
    () => banner?.contradictions ?? [],
    [banner],
  );

  const watchNext = useMemo(
    () => (banner?.watch_next ?? []).slice(0, 3),
    [banner],
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  const bannerMode: BannerMode = banner?.mode ?? "waiting";
  const narrativeBorderCls = modeBorder(bannerMode);
  const narrativeTextCls   = modeColor(bannerMode);

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col"
      style={{ backgroundColor: "#0a0a0f" }}
      onClick={onClose}
    >
      <div
        className="flex-1 overflow-y-auto"
        style={{ backgroundColor: "#0a0a0f" }}
        onClick={e => e.stopPropagation()}
      >

        {/* ════════════════════════════════════════════════════════════════
            ÜST BAŞLIK
           ════════════════════════════════════════════════════════════════ */}
        <header
          className="sticky top-0 z-10 border-b border-eyay-border"
          style={{ backgroundColor: "#15151c" }}
        >
          <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-2xl bg-eyay-raised border border-eyay-border flex items-center justify-center text-2xl">
                  🤖
                </div>
                <span className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-eyay-bg animate-pulse" />
              </div>
              <div>
                <p className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  e-yAy AGENT
                </p>
                <h2 className="text-lg font-bold text-eyay-text mt-0.5 leading-tight">
                  Komut Merkezi
                </h2>
                {(insightAt || banner?.updated_at) && (
                  <p className="text-[10px] font-mono text-eyay-faint mt-0.5">
                    Son tarama {timeAgo(banner?.updated_at ?? insightAt)}
                    {banner && (
                      <span className={`ml-2 uppercase font-bold ${narrativeTextCls}`}>
                        · {banner.mode.replace("_", " ")}
                      </span>
                    )}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-9 h-9 rounded-lg border border-eyay-border bg-eyay-surface hover:border-eyay-blue/50 hover:text-eyay-blue text-eyay-dim flex items-center justify-center transition-colors"
              title="Kapat (ESC)"
            >
              ✕
            </button>
          </div>
        </header>

        {/* ════════════════════════════════════════════════════════════════
            RISK ALERT — paper anomaly veya contradiction modu (bant)
           ════════════════════════════════════════════════════════════════ */}
        {banner && (banner.mode === "risk_alert" || banner.mode === "contradiction") && (
          <div className={`border-b px-6 py-3 ${
            banner.mode === "risk_alert"
              ? "border-red-800/60 bg-red-950/20"
              : "border-amber-800/40 bg-amber-950/15"
          }`}>
            <div className="max-w-5xl mx-auto flex items-center gap-3">
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                banner.mode === "risk_alert" ? "bg-red-400" : "bg-amber-400"
              }`} />
              <span className={`text-xs font-mono font-bold ${
                banner.mode === "risk_alert" ? "text-red-300" : "text-amber-300"
              }`}>
                {banner.headline}
              </span>
            </div>
          </div>
        )}

        <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">

          {/* ════════════════════════════════════════════════════════════
              ŞU AN NE DÜŞÜNÜYORUM — banner'dan dinamik içerik
             ════════════════════════════════════════════════════════════ */}
          <section className={`rounded-2xl border p-5 ${narrativeBorderCls}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">🧠</span>
              <p className={`text-[10px] font-mono uppercase tracking-widest font-bold ${narrativeTextCls}`}>
                Şu an ne düşünüyorum
              </p>
            </div>

            {/* Narrative */}
            <p className="text-sm text-eyay-text leading-relaxed">{narrative}</p>

            {/* Top signals */}
            {topSignals.length > 0 && (
              <div className="mt-3 space-y-1">
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-1">
                  Öne çıkan sinyaller
                </p>
                {topSignals.map((sig, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs font-mono text-eyay-dim">
                    <span className={`shrink-0 mt-0.5 ${narrativeTextCls}`}>›</span>
                    <span>{sig}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Contradictions */}
            {contradictions.length > 0 && (
              <div className="mt-3 space-y-1">
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-1">
                  Çelişkiler
                </p>
                {contradictions.map((c, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs font-mono text-amber-400/80">
                    <span className="shrink-0 mt-0.5">⚡</span>
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Watch next */}
            {watchNext.length > 0 && (
              <div className="mt-3 space-y-1">
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-1">
                  İzlenecekler
                </p>
                {watchNext.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs font-mono text-eyay-dim">
                    <span className="shrink-0 mt-0.5 text-eyay-blue">📌</span>
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Learning note */}
            {banner?.learning_note && (
              <div className="mt-3 p-2.5 rounded-lg bg-eyay-raised/60 border border-eyay-border/40">
                <p className="text-[10px] font-mono text-sky-300 leading-relaxed">
                  🧠 {banner.learning_note}
                </p>
              </div>
            )}

            {/* FAZ 13 — Piyasa fikri satırları (market_thought önce) */}
            {banner?.market_thought && (
              <div className="mt-3 p-3 rounded-lg bg-eyay-raised/50 border border-eyay-border/40 space-y-2">
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">
                  Piyasa fikri
                </p>
                <p className="text-xs text-eyay-text leading-relaxed">{banner.market_thought}</p>
              </div>
            )}

            {/* Portföy kararı */}
            <div className="mt-3 pt-3 border-t border-white/10 flex items-center gap-3 flex-wrap">
              <span className="text-[10px] font-mono text-eyay-faint">PORTFÖY KARARI</span>
              <span className={`text-xs font-mono font-black px-2 py-0.5 rounded border ${
                decision === "AÇIL"                    ? "border-emerald-700 text-emerald-300 bg-emerald-950/30"
                : decision === "KORU"                  ? "border-emerald-700 text-emerald-300 bg-emerald-950/30"
                : decision === "KAPAT"                 ? "border-red-700    text-red-300    bg-red-950/30"
                : decision === "İŞLEM YOK / SİSTEM DURDU" ? "border-red-700 text-red-300  bg-red-950/40"
                : decision === "KÜÇÜLT"                ? "border-orange-700 text-orange-300 bg-orange-950/30"
                : decision === "POZİSYON ARTIRMA"      ? "border-yellow-700 text-yellow-300 bg-yellow-950/25"
                : decision === "İZLE"                  ? "border-blue-700   text-blue-300   bg-blue-950/25"
                : decision === "YENİ RİSK AÇMA / BEKLE"? "border-amber-700 text-amber-300  bg-amber-950/30"
                : decision === "POZİSYON YOK · NÖTR İZLEME" ? "border-slate-700 text-slate-300 bg-slate-950/30"
                : "border-amber-700 text-amber-300 bg-amber-950/30"
              }`}>
                {decision || "—"}
              </span>
            </div>
          </section>

          {/* ════════════════════════════════════════════════════════════
              AI TRADE OPINION — net fikir katmanı (PAPER_SAFE, emir yok)
             ════════════════════════════════════════════════════════════ */}
          {opinion && (
            <section className="rounded-2xl border border-cyan-900/40 bg-cyan-950/10 p-5" data-testid="ai-trade-opinion">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[9px] font-mono text-cyan-300/80 uppercase tracking-widest">
                  🎯 AI Trade Fikrim
                </p>
                <span className="text-[8px] font-mono text-eyay-faint border border-eyay-border/60 rounded px-1.5 py-0.5">
                  {opinion.overall_view} · PAPER_SAFE · emir yok
                </span>
              </div>
              <p className="text-xs text-eyay-text leading-relaxed mb-4">{opinion.market_opinion}</p>

              {/* Açık Pozisyon Görüşüm */}
              {opinion.open_position_opinions.length > 0 && (
                <div className="mb-4">
                  <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-2">
                    Açık Pozisyon Görüşüm
                  </p>
                  <div className="flex flex-col gap-2">
                    {opinion.open_position_opinions.map(po => (
                      <div key={po.pair} className="rounded-xl border border-eyay-border/60 bg-eyay-raised/30 px-3 py-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[11px] font-mono font-bold text-eyay-text">{po.pair} {po.side}</span>
                          <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${OPINION_STYLE[po.opinion] ?? OPINION_STYLE.WAIT}`}>
                            {po.opinion}
                          </span>
                          <span className="text-[8px] font-mono text-eyay-faint">conviction: {po.conviction}</span>
                        </div>
                        <p className="text-[10px] text-eyay-dim mt-1 leading-snug">{po.reason}</p>
                        <p className="text-[9px] font-mono text-amber-400/70 mt-1">⚠ {po.invalidation}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Asset fikirleri — kompakt çip satırı */}
              <div className="mb-4">
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-2">
                  Varlık Görüşleri
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {opinion.asset_opinions.map(ao => (
                    <span
                      key={ao.asset}
                      title={`${ao.suggested_action} · skor ${ao.score} · ${ao.trigger_needed}`}
                      className={`text-[9px] font-mono font-semibold px-2 py-1 rounded-lg border ${OPINION_STYLE[ao.opinion] ?? OPINION_STYLE.WAIT}`}
                    >
                      {ao.asset} · {ao.opinion} ({ao.conviction})
                    </span>
                  ))}
                </div>
              </div>

              {/* En İyi Yeni Aday */}
              <div className="mb-4">
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-1.5">
                  En İyi Yeni Aday
                </p>
                {opinion.best_candidate.asset !== "NONE" ? (
                  <p className="text-[11px] text-eyay-text leading-snug">
                    <span className="font-mono font-bold text-cyan-300">{opinion.best_candidate.asset}</span>
                    <span className="text-eyay-dim"> ({opinion.best_candidate.bias})</span>
                    {" — "}{opinion.best_candidate.reason}
                    <span className="text-eyay-faint"> · Tetik: {opinion.best_candidate.trigger}</span>
                  </p>
                ) : (
                  <p className="text-[10px] text-eyay-dim leading-snug">
                    Aday yok — {opinion.no_trade_reason}
                  </p>
                )}
              </div>

              {/* Neyi Bekliyorum / Fikrimi Ne Bozar */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {opinion.next_3_triggers.length > 0 && (
                  <div>
                    <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-1.5">
                      Neyi Bekliyorum?
                    </p>
                    <ul className="flex flex-col gap-1">
                      {opinion.next_3_triggers.map((t, i) => (
                        <li key={i} className="text-[10px] text-eyay-dim leading-snug">→ {t}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {opinion.what_would_change_my_mind.length > 0 && (
                  <div>
                    <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-1.5">
                      Fikrimi Ne Bozar?
                    </p>
                    <ul className="flex flex-col gap-1">
                      {opinion.what_would_change_my_mind.map((t, i) => (
                        <li key={i} className="text-[10px] text-eyay-dim leading-snug">✕ {t}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* ════════════════════════════════════════════════════════════
              FAZ 13 — PIYASA BAĞLAMI: fiyat / takvim / tetikleyici
             ════════════════════════════════════════════════════════════ */}
          {banner && (banner.news_story || banner.price_story || banner.event_calendar_note || banner.market_pricing_note || banner.next_trigger) && (
            <section className="rounded-2xl border border-eyay-border bg-eyay-surface/40 p-5">
              <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest mb-3">
                Piyasa bağlamı
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

                {/* Haber hikayesi */}
                {banner.news_story && (
                  <div className="rounded-xl border border-orange-800/40 bg-orange-950/10 p-3 space-y-1">
                    <p className="text-[9px] font-mono text-orange-300 uppercase tracking-widest">📰 Haber hikayesi</p>
                    <p className="text-[11px] text-eyay-dim leading-relaxed">{banner.news_story}</p>
                  </div>
                )}

                {/* Fiyat tepkisi */}
                {banner.price_story && (
                  <div className="rounded-xl border border-eyay-border/60 bg-eyay-raised/40 p-3 space-y-1">
                    <p className="text-[9px] font-mono text-eyay-blue uppercase tracking-widest">📈 Fiyat tepkisi</p>
                    <p className="text-[11px] text-eyay-dim leading-relaxed">{banner.price_story}</p>
                  </div>
                )}

                {/* Olay takvimi */}
                {banner.event_calendar_note && (
                  <div className="rounded-xl border border-amber-800/40 bg-amber-950/10 p-3 space-y-1">
                    <p className="text-[9px] font-mono text-amber-300 uppercase tracking-widest">📅 Olay takvimi</p>
                    <p className="text-[11px] text-eyay-dim leading-relaxed">{banner.event_calendar_note}</p>
                  </div>
                )}

                {/* Piyasa neyi fiyatlıyor */}
                {banner.market_pricing_note && (
                  <div className="rounded-xl border border-eyay-border/60 bg-eyay-raised/40 p-3 space-y-1">
                    <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest">📊 Piyasa neyi fiyatlıyor?</p>
                    <p className="text-[11px] text-eyay-dim leading-relaxed">{banner.market_pricing_note}</p>
                  </div>
                )}

                {/* Beklenen tetikleyici */}
                {banner.next_trigger && (
                  <div className="rounded-xl border border-emerald-800/40 bg-emerald-950/10 p-3 space-y-1">
                    <p className="text-[9px] font-mono text-emerald-400 uppercase tracking-widest">🎯 Beklenen tetikleyici</p>
                    <p className="text-[11px] text-eyay-dim leading-relaxed">{banner.next_trigger}</p>
                  </div>
                )}

              </div>

              {/* Jeopolitik hikaye ayrı satır (varsa) */}
              {banner.event_story && !banner.event_story.startsWith("Jeopolitik başlık yok") && (
                <div className="mt-3 rounded-xl border border-red-800/40 bg-red-950/10 p-3 space-y-1">
                  <p className="text-[9px] font-mono text-red-300 uppercase tracking-widest">🌐 Jeopolitik / savaş gündemi</p>
                  <p className="text-[11px] text-eyay-dim leading-relaxed">{banner.event_story}</p>
                </div>
              )}
            </section>
          )}

          {/* ════════════════════════════════════════════════════════════
              SON DAKİKA — FAZ 15: Liste/Radar shell (legacy liste fallback)
             ════════════════════════════════════════════════════════════ */}
          <BreakingNewsPanelShell headlines={warHeadlines} />

          {/* ════════════════════════════════════════════════════════════
              AKTİF KARARLARIM (paper trading açık pozisyonlar)
             ════════════════════════════════════════════════════════════ */}
          <section className="rounded-2xl border border-eyay-border bg-eyay-surface p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-base">📊</span>
                <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-bold">
                  Aktif Kararlarım
                </p>
                <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5">
                  {activeDecisions.length} pozisyon
                </span>
              </div>
              {trading && (
                <div className="text-right">
                  <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider">Toplam Unreal.</p>
                  <p className={`text-sm font-mono font-bold ${trading.unrealized_pnl_usd >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                    {fmtUsd(trading.unrealized_pnl_usd)}
                  </p>
                </div>
              )}
            </div>

            {activeDecisions.length === 0 ? (
              <div className="py-6 text-center space-y-1.5">
                <p className="text-xs text-eyay-faint italic">
                  {noPositionReason}
                </p>
                {/* Eğer banner'dan watch_next varsa burada da göster */}
                {watchNext.length > 0 && (
                  <div className="flex flex-wrap justify-center gap-2 mt-2">
                    {watchNext.map((w, i) => (
                      <span key={i} className="text-[9px] font-mono border border-eyay-border rounded px-2 py-0.5 text-eyay-dim">
                        {w}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {activeDecisions.map((d, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded-lg bg-eyay-raised border border-eyay-border"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`text-lg ${d.side === "LONG" ? "text-emerald-400" : "text-red-400"}`}>
                        {d.side === "LONG" ? "▲" : "▼"}
                      </span>
                      <div>
                        <p className="text-sm font-mono font-bold text-eyay-text">
                          {d.side} {d.pair}
                        </p>
                        <p className="text-[10px] font-mono text-eyay-faint">
                          @{d.entry_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                          {" · "}{timeAgo(d.entry_at)}
                          {" · "}sinyal: {d.last_signal}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={`text-sm font-mono font-black ${d.pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {fmtUsd(d.pnl_usd)}
                      </p>
                      <p className={`text-[10px] font-mono ${d.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {d.pnl_pct >= 0 ? "+" : ""}{d.pnl_pct.toFixed(2)}%
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ════════════════════════════════════════════════════════════
              YAKLAŞAN TETİKLEYİCİLER
             ════════════════════════════════════════════════════════════ */}
          {triggers.length > 0 && (
            <section className="rounded-2xl border border-amber-900/40 bg-amber-950/10 p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-base">🎯</span>
                <p className="text-[10px] font-mono text-amber-300 uppercase tracking-widest font-bold">
                  Yaklaşan Tetikleyiciler
                </p>
                <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5">
                  {triggers.length} aktif
                </span>
              </div>
              <div className="space-y-2">
                {triggers.map((t, i) => {
                  const s = SEV[t.severity];
                  return (
                    <div key={i} className={`p-3 rounded-lg border ${s.border} ${s.bg}`}>
                      <div className="flex items-start gap-3">
                        <span className="text-lg shrink-0">{t.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            {t.asset_code && (
                              <span className="text-[9px] font-mono text-eyay-text border border-white/10 bg-black/30 rounded px-1.5 py-0.5">
                                {t.asset_code}
                              </span>
                            )}
                            <p className={`text-xs font-bold ${s.text}`}>{t.headline}</p>
                          </div>
                          {t.detail && (
                            <p className="text-[10px] text-eyay-dim mt-1 leading-relaxed">{t.detail}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* ════════════════════════════════════════════════════════════
              GENEL GÖZLEMLER
             ════════════════════════════════════════════════════════════ */}
          {observations.length > 0 && (
            <section className="rounded-2xl border border-eyay-border bg-eyay-surface p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-base">👁</span>
                <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-bold">
                  Diğer Gözlemler
                </p>
                <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5">
                  {observations.length}
                </span>
              </div>
              <div className="space-y-2">
                {observations.map((o, i) => {
                  const s = SEV[o.severity];
                  return (
                    <div key={i} className={`p-3 rounded-lg border ${s.border} ${s.bg}`}>
                      <div className="flex items-start gap-2.5">
                        <span className="text-base shrink-0">{o.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className={`text-[9px] font-mono font-black ${s.text}`}>{s.label}</span>
                            {o.asset_code && (
                              <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5">
                                {o.asset_code}
                              </span>
                            )}
                          </div>
                          <p className={`text-xs font-medium ${s.text}`}>{o.headline}</p>
                          {o.detail && (
                            <p className="text-[10px] text-eyay-dim mt-1 leading-relaxed">{o.detail}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* ════════════════════════════════════════════════════════════
              DOĞRULUK SKORU
             ════════════════════════════════════════════════════════════ */}
          {trading && trading.trade_count > 0 && (
            <section className="rounded-2xl border border-eyay-border bg-eyay-surface p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-base">📈</span>
                <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-bold">
                  Sinyal Doğruluğum
                </p>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Stat
                  label="WIN RATE"
                  value={accuracy.winRate !== null ? `${accuracy.winRate.toFixed(0)}%` : "—"}
                  color={accuracy.winRate !== null && accuracy.winRate >= 50 ? "text-emerald-300" : "text-amber-300"}
                />
                <Stat label="KAZANAN"  value={String(accuracy.wins)}   color="text-emerald-300" />
                <Stat label="KAYBEDEN" value={String(accuracy.losses)} color="text-red-300" />
                <Stat
                  label="REALIZED PNL"
                  value={fmtUsd(accuracy.totalRealized)}
                  color={accuracy.totalRealized >= 0 ? "text-emerald-300" : "text-red-300"}
                />
              </div>
              {trading.trades.length > 0 && (
                <div className="mt-4 pt-4 border-t border-eyay-border/40">
                  <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-2">
                    SON KAPANANLAR
                  </p>
                  <div className="space-y-1.5">
                    {trading.trades.slice(-5).reverse().map(t => (
                      <div key={t.id} className="flex items-center justify-between text-[10px] font-mono bg-eyay-raised rounded px-2 py-1.5">
                        <div className="flex items-center gap-2">
                          <span className={t.side === "LONG" ? "text-emerald-400" : "text-red-400"}>
                            {t.side === "LONG" ? "▲" : "▼"}
                          </span>
                          <span className="text-eyay-text">{t.pair}</span>
                          <span className="text-eyay-faint">{timeAgo(t.exit_at)}</span>
                          <span className="text-eyay-faint">{t.duration_min}dk</span>
                        </div>
                        <span className={`font-bold ${t.pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {fmtUsd(t.pnl_usd)} ({t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* FAZ 21 — Sistem Kontrolleri (diagnostic accordion, default kapalı) */}
          <section className="rounded-2xl border border-eyay-border bg-eyay-surface/60 overflow-hidden"
                   data-testid="agent-diagnostic-accordion">
            <button
              type="button"
              onClick={() => setDiagOpen(o => !o)}
              aria-expanded={diagOpen}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-white/[0.02] transition-colors"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-cyan-400/80 text-xs">⚙</span>
                <p className="text-[11px] font-mono font-bold text-eyay-dim uppercase tracking-[0.2em]">
                  Sistem Kontrolleri
                </p>
                <span className="text-[9px] font-mono text-eyay-faint truncate">
                  · Makro+Risk · Öğrenme · Sistem Sağlığı
                </span>
              </div>
              <span className="text-[10px] font-mono text-eyay-faint shrink-0">
                {diagOpen ? "▾ kapat" : "▸ aç"}
              </span>
            </button>
            {diagOpen && (
              <div className="border-t border-eyay-border/40 p-4 space-y-3 bg-black/20">
                {macro && appetite ? (
                  <MacroPanel macro={macro} appetite={appetite} showUnified={true} />
                ) : (
                  <p className="text-[10px] font-mono text-eyay-faint italic">
                    Makro/Risk sentezi: veri yok.
                  </p>
                )}
                <LearningPanel />
                <SystemHealthPanel />
              </div>
            )}
          </section>

          {/* Footer */}
          <div className="pt-2 border-t border-eyay-border/40">
            <p className="text-[10px] font-mono text-eyay-faint text-center leading-relaxed">
              🤖 Agent canlı izleme · banner 30sn · insight 15sn · saf analiz (Groq yok)<br />
              PAPER_SAFE · NO_EXECUTION · tüm gerçek kararlar insana aittir
            </p>
          </div>
        </div>

        {/* Alt sabit kapat çubuğu */}
        <div className="sticky bottom-0 border-t border-eyay-border" style={{ backgroundColor: "#15151c" }}>
          <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
            <span className="text-[10px] font-mono text-eyay-faint">
              ESC veya backdrop tıkla → kapat
            </span>
            <button
              onClick={onClose}
              className="px-4 py-1.5 rounded-lg border border-eyay-blue/40 text-eyay-blue text-xs font-mono font-bold hover:bg-eyay-blue/10 transition-colors"
            >
              DASHBOARD'A DÖN
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Mini stat card
function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="text-center p-3 rounded-lg bg-eyay-raised border border-eyay-border/50">
      <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-widest">{label}</p>
      <p className={`text-lg font-mono font-black mt-1 ${color}`}>{value}</p>
    </div>
  );
}
