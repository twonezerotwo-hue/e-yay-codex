"use client";

/**
 * FAZ 28 — Agent Holographic Layer (Neural Command Center).
 *
 * AgentCommandCenter modal'ının yeni varsayılan görünümü:
 *   - merkezde holografik Agent Core (SVG)
 *   - etrafında orbit eden sinyal kartları (Top Signals / Contradictions /
 *     Watch Next / Market Stance)
 *   - sağda "AI Trade Fikrim" holografik analiz kartı (confidence ring)
 *   - 5 piyasa bağlamı mini modülü (haber / fiyat / takvim / fiyatlama / jeopol)
 *   - aşağıda haber radarı (BreakingNewsPanelShell — Radar default)
 *   - "Aktif Kararlar" özet bandı
 *   - default kapalı accordion'lar: Karar Detayları, Sistem Kontrolleri
 *
 * Sadece görselleştirme — karar üretmez, broker emri yok. PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import ActionCenter from "@/components/ActionCenter";
import AgentCoreVisual from "@/components/AgentCoreVisual";
import AsymmetryCard from "@/components/AsymmetryCard";
import BreakingNewsPanelShell from "@/components/BreakingNewsPanelShell";
import ConfirmationStrip from "@/components/ConfirmationStrip";
import LearningPanel from "@/components/LearningPanel";
import SystemHealthPanel from "@/components/SystemHealthPanel";
import MacroPanel from "@/components/MacroPanel";
import { useAgentVoice } from "@/lib/useAgentVoice";
import type {
  AsymmetrySignal, ConfirmationItem, Decision, FlipCondition, MacroLayer, NewsHeadline, RiskAppetiteLayer,
} from "@/lib/types";

// ── Types (AgentCommandCenter'daki ile aynı, prop drilling için kopya) ───────

type BannerMode = "waiting" | "managing_position" | "contradiction" | "risk_alert" | "learning";

export interface AgentBanner {
  mode:               BannerMode;
  headline:           string;
  main_view:          string;
  top_signals:        string[];
  contradictions:     string[];
  watch_next:         string[];
  position_note:      string | null;
  learning_note:      string | null;
  updated_at:         string;
  market_thought?:    string;
  price_story?:       string;
  event_story?:       string;
  event_calendar_note?: string;
  market_pricing_note?: string;
  next_trigger?:      string;
  news_story?:        string;
  source_news_titles?: string[];
  generated_at?:      string;
  agent_orchestration?: AgentOrchestration;
}

export interface AgentOrchestration {
  status?:        "degraded";
  reason?:        string;
  generated_at?:  string;
  data_sources?:  Record<"price" | "news" | "macro" | "event" | "paper_state", string>;
  paper_observer?: {
    experiment_mode?:    boolean;
    mode?:               string;
    recent_labels?:      { pair: string; side: string; labels: string[]; at: string }[];
    active_adjustments?: Record<string, { label: string; threshold_delta: number; size_multiplier: number; wins: number; losses: number; net: number }>;
    open_positions?:     number;
    manual_ready?:       number;
    last_event?:         unknown;
  };
  validator?: { stale_inputs?: string[]; missing_inputs?: string[]; conflicts?: string[] };
  strategist_context?: { market_stance?: string; last_decision?: string; best_candidate?: string };
  risk_explainer?: string;
}

export interface AgentInsight {
  severity:   "CRITICAL" | "WARNING" | "OPPORTUNITY" | "OBSERVATION";
  headline:   string;
  detail:     string;
  asset_code: string;
  icon:       string;
  generated_at: string;
}

export interface AssetOpinion {
  asset: string; opinion: string; conviction: string; score: number;
  why: string[]; against: string[]; trigger_needed: string; invalidation: string;
  suggested_action: string;
}

export interface PositionOpinion {
  pair: string; side: string; opinion: string; conviction: string;
  reason: string; what_to_watch: string[]; invalidation: string;
}

export interface TradeOpinion {
  schema_version?: string; generated_at?: string; overall_view?: string;
  market_opinion?: string; asset_opinions?: AssetOpinion[];
  open_position_opinions?: PositionOpinion[];
  best_candidate?: { asset: string; bias: string; reason: string; trigger: string; risk: string };
  no_trade_reason?: string;
  next_3_triggers?: string[];
  what_would_change_my_mind?: string[];
  owner_brief?: string;
}

export interface Position {
  pair: string; side: "LONG" | "SHORT"; entry_price: number;
  current_price: number; size_usd: number; pnl_usd: number; pnl_pct: number;
}

export interface TradingState {
  starting_balance: number; equity: number; realized_pnl_usd: number;
  unrealized_pnl_usd: number; daily_pnl_usd: number;
  open_positions: Position[]; trade_count: number;
  traded_pairs: string[];
  state_anomaly?: { active: boolean; reasons: string[] };
}

// ── Mode → tone ──────────────────────────────────────────────────────────────

interface Tone { ring: string; soft: string; text: string; label: string; border: string; }
const TONES: Record<BannerMode, Tone> = {
  waiting:           { ring: "#22d3ee", soft: "rgba(34,211,238,0.18)",  text: "text-cyan-300",    label: "BEKLİYOR",    border: "border-cyan-700/40" },
  managing_position: { ring: "#34d399", soft: "rgba(52,211,153,0.18)",  text: "text-emerald-300", label: "POZİSYONDA",  border: "border-emerald-700/40" },
  contradiction:     { ring: "#fbbf24", soft: "rgba(251,191,36,0.18)",  text: "text-amber-300",   label: "ÇELİŞKİ",     border: "border-amber-700/40" },
  risk_alert:        { ring: "#f87171", soft: "rgba(248,113,113,0.18)", text: "text-red-300",     label: "RİSK UYARISI", border: "border-red-700/40" },
  learning:          { ring: "#a78bfa", soft: "rgba(167,139,250,0.18)", text: "text-violet-300",  label: "ÖĞRENİYOR",   border: "border-violet-700/40" },
};

const OPINION_TONE: Record<string, string> = {
  LONG_BIAS:               "#34d399",
  HOLD:                    "#34d399",
  SHORT_BIAS:              "#f87171",
  AVOID:                   "#f87171",
  CLOSE_WATCH:             "#f87171",
  REDUCE:                  "#fb923c",
  WAIT:                    "#94a3b8",
  WAIT_EVENT_CONFIRMATION: "#fbbf24",
  MANUAL_REVIEW:           "#60a5fa",
  ADD_ONLY_IF:             "#60a5fa",
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(iso: string | undefined): string {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" }); }
  catch { return "—"; }
}

// 0-100 confidence türetir — best candidate varsa
function confidenceFromOpinion(o: TradeOpinion | null): number {
  if (!o) return 0;
  const best = o.asset_opinions?.find(a => a.asset === o.best_candidate?.asset);
  if (best && typeof best.score === "number") return Math.max(0, Math.min(100, best.score));
  if (o.best_candidate?.asset && o.best_candidate.asset !== "NONE") return 60;
  return 30;
}

// ── Agent Core SVG (legacy; artık shared AgentCoreVisual kullanılıyor) ──────
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function _LegacyAgentCore({ tone, animate }: { tone: Tone; animate: boolean }) {
  return (
    <svg viewBox="0 0 280 280" className="w-full h-full max-w-[340px] max-h-[340px]"
         xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="ac-bg" cx="50%" cy="50%" r="60%">
          <stop offset="0%"  stopColor={tone.ring} stopOpacity="0.18" />
          <stop offset="55%" stopColor={tone.ring} stopOpacity="0.06" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <radialGradient id="ac-core" cx="50%" cy="50%" r="60%">
          <stop offset="0%"  stopColor="#fff" stopOpacity="0.85" />
          <stop offset="30%" stopColor={tone.ring} stopOpacity="0.75" />
          <stop offset="100%" stopColor="#020812" />
        </radialGradient>
        <linearGradient id="ac-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"  stopColor={tone.ring} stopOpacity="0" />
          <stop offset="50%" stopColor={tone.ring} stopOpacity="0.65" />
          <stop offset="100%" stopColor={tone.ring} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Aura */}
      <circle cx="140" cy="140" r="135" fill="url(#ac-bg)" />

      {/* Outer rotating ring */}
      <g style={animate ? { transformOrigin: "140px 140px", animation: "agc-spin 40s linear infinite" } : undefined}>
        <circle cx="140" cy="140" r="118" fill="none" stroke={tone.ring} strokeWidth="0.8" strokeDasharray="6 8" opacity="0.5" />
        {/* Sensör noktaları */}
        {Array.from({ length: 8 }, (_, i) => {
          const a = (i / 8) * Math.PI * 2;
          const x = 140 + Math.cos(a) * 118;
          const y = 140 + Math.sin(a) * 118;
          return <circle key={i} cx={x} cy={y} r="2.4" fill={tone.ring} opacity="0.85" />;
        })}
      </g>

      {/* Middle counter-ring */}
      <g style={animate ? { transformOrigin: "140px 140px", animation: "agc-spin 28s linear infinite reverse" } : undefined}>
        <circle cx="140" cy="140" r="92" fill="none" stroke={tone.ring} strokeWidth="0.6" opacity="0.35" />
        <circle cx="140" cy="140" r="92" fill="none" stroke={tone.ring} strokeWidth="0.5" strokeDasharray="2 10" opacity="0.7" />
      </g>

      {/* Hexagonal grid mesh (static) */}
      <g opacity="0.35">
        {[0, 60, 120].map(rot => (
          <line key={rot} x1="140" y1="55" x2="140" y2="225" stroke={tone.ring} strokeWidth="0.4"
                transform={`rotate(${rot} 140 140)`} />
        ))}
        <polygon points="140,55 215,97 215,183 140,225 65,183 65,97" fill="none" stroke={tone.ring} strokeWidth="0.5" opacity="0.6" />
        <polygon points="140,85 188,113 188,167 140,195 92,167 92,113" fill="none" stroke={tone.ring} strokeWidth="0.4" opacity="0.45" />
      </g>

      {/* Data flow lines (animated dashed lines) */}
      {animate && Array.from({ length: 6 }, (_, i) => {
        const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
        const x1 = 140 + Math.cos(a) * 50;
        const y1 = 140 + Math.sin(a) * 50;
        const x2 = 140 + Math.cos(a) * 110;
        const y2 = 140 + Math.sin(a) * 110;
        return (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="url(#ac-line)"
                strokeWidth="1.2" strokeDasharray="3 6">
            <animate attributeName="stroke-dashoffset" from="0" to="-36"
                     dur={`${2 + i * 0.4}s`} repeatCount="indefinite" />
          </line>
        );
      })}

      {/* Pulse halka */}
      <circle cx="140" cy="140" r="56" fill="none" stroke={tone.ring} strokeWidth="1.2" opacity="0.7"
              style={animate ? { transformOrigin: "140px 140px", animation: "agc-pulse 3s ease-in-out infinite" } : undefined} />

      {/* Core */}
      <circle cx="140" cy="140" r="44" fill="url(#ac-core)" />
      <circle cx="140" cy="140" r="44" fill="none" stroke={tone.ring} strokeWidth="1.2" />

      {/* Core text */}
      <text x="140" y="138" textAnchor="middle" fontSize="10" fontFamily="monospace"
            fontWeight="bold" fill="#fff" letterSpacing="2">AGENT</text>
      <text x="140" y="152" textAnchor="middle" fontSize="8" fontFamily="monospace"
            fill={tone.ring} letterSpacing="3" opacity="0.9">CORE</text>
    </svg>
  );
}

// ── Confidence ring ──────────────────────────────────────────────────────────

function ConfidenceRing({ value, color, size = 96 }: { value: number; color: string; size?: number }) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(148,163,184,0.18)" strokeWidth="3.5" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3.5"
              strokeLinecap="round" strokeDasharray={`${(pct / 100) * c} ${c}`}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: "stroke-dasharray 0.7s ease" }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
            fontSize={size * 0.3} fontFamily="monospace" fontWeight="700" fill={color}>
        {Math.round(pct)}
      </text>
    </svg>
  );
}

// ── Sidebar icons ────────────────────────────────────────────────────────────

interface NavItem { icon: string; label: string; description: string; id: string; opensAccordion?: "detail" | "system"; }
const NAV_ITEMS: readonly NavItem[] = [
  { icon: "◈", label: "Komut Merkezi",     description: "Agent'ın anlık düşünce katmanı",      id: "agent-core-section" },
  { icon: "◇", label: "Piyasa Zekası",     description: "Haber, fiyat ve makro bağlam",       id: "market-context-section" },
  { icon: "△", label: "AI Trade Fikrim",   description: "Deterministik trade opinion",        id: "trade-opinion-section" },
  { icon: "⊙", label: "Haber Radarı",      description: "Son dakika risk taraması",           id: "news-radar-section" },
  { icon: "▤", label: "Aktif Kararlar",    description: "Paper pozisyon ve PnL izleme",       id: "positions-section" },
  { icon: "≡", label: "Karar Detayları",   description: "Uzun karar koşulları",               id: "decision-details-section", opensAccordion: "detail" },
  { icon: "⚙", label: "Sistem Kontrolleri", description: "Health, learning, auto-tune",       id: "system-controls-section", opensAccordion: "system" },
] as const;

// ── Main ─────────────────────────────────────────────────────────────────────

interface Props {
  banner:   AgentBanner | null;
  opinion:  TradeOpinion | null;
  insights: AgentInsight[];
  trading:  TradingState | null;
  headlines?: NewsHeadline[];

  /** Karar Detayları accordion'u için (opsiyonel). */
  decision?:       Decision;
  confirmationChecklist?: ConfirmationItem[];
  asymmetry?:      AsymmetrySignal;
  ownerActions?:   string[];
  flipConditions?: FlipCondition[];

  /** Sistem Kontrolleri accordion'u için (opsiyonel). */
  macro?:    MacroLayer;
  appetite?: RiskAppetiteLayer;

  onClose: () => void;
}

export default function AgentHolographicLayer({
  banner, opinion, insights, trading, headlines = [],
  decision, ownerActions = [], flipConditions = [],
  confirmationChecklist = [], asymmetry,
  macro, appetite, onClose,
}: Props) {
  const [animate,       setAnimate]       = useState(false);
  const [activeId,      setActiveId]      = useState<string>("agent-core-section");
  // Canlı feed: banner/insight/news güncellenince kartlar dönsün (flip)
  const [pulseKey, setPulseKey] = useState(0);
  const [now,      setNow]      = useState(() => Date.now());
  const bannerStamp  = banner?.updated_at || banner?.generated_at || "";
  const insightStamp = insights[0]?.generated_at || "";
  const newsKey      = headlines[0]?.url || headlines[0]?.title || "";
  useEffect(() => {
    if (bannerStamp || banner?.headline || insightStamp || newsKey) setPulseKey(k => k + 1);
  }, [bannerStamp, banner?.headline, insightStamp, newsKey]);

  // Son dakika haber → Agent Core yanında speech bubble + opsiyonel sesli okuma
  const voice = useAgentVoice();
  const [newsBubble, setNewsBubble] = useState<string | null>(null);
  const speakRef = useRef(voice.speak);
  useEffect(() => { speakRef.current = voice.speak; }, [voice.speak]);
  useEffect(() => {
    if (!newsKey) return;
    const h = headlines[0];
    const text = h?.title_tr || h?.title || "";
    if (!text) return;
    setNewsBubble(text);
    speakRef.current(`Son dakika. ${text}`);
    const t = setTimeout(() => setNewsBubble(null), 10_000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newsKey]);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(t);
  }, []);
  const stampMs = bannerStamp ? new Date(bannerStamp).getTime() : NaN;
  const isStale = !isNaN(stampMs) && now - stampMs > 300_000;
  const [detailOpen,    setDetailOpen]    = useState(false);
  const [systemOpen,    setSystemOpen]    = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    return () => mq.removeEventListener?.("change", onMQ);
  }, []);

  // ── Tab navigation: sadece aktif tab içeriği render edilir, scroll yok ─────
  const handleNavClick = (item: NavItem) => {
    setActiveId(item.id);
    // İçindeki accordion'ları otomatik açabilir
    if (item.opensAccordion === "detail") setDetailOpen(true);
    if (item.opensAccordion === "system") setSystemOpen(true);
    // İçeriğin üst kısmına in-place reset
    if (typeof window !== "undefined") {
      requestAnimationFrame(() => {
        const main = document.getElementById("agent-tab-content");
        main?.scrollTo({ top: 0, behavior: animate ? "smooth" : "auto" });
      });
    }
  };

  const activeTab = useMemo(
    () => NAV_ITEMS.find(i => i.id === activeId) ?? NAV_ITEMS[0],
    [activeId],
  );

  const mode: BannerMode = banner?.mode ?? "waiting";
  const tone = TONES[mode];

  // Top signals / contradictions / watch — kısa chip
  const topSignals     = useMemo(() => (banner?.top_signals     ?? []).slice(0, 3), [banner]);
  const contradictions = useMemo(() => (banner?.contradictions  ?? []).slice(0, 3), [banner]);
  const watchNext      = useMemo(() => (banner?.watch_next      ?? []).slice(0, 3), [banner]);

  // 3 thought card
  const thoughts = useMemo(() => {
    const t: { label: string; text: string; tone: string }[] = [];
    if (banner?.market_thought)      t.push({ label: "Makro / Rejim",      text: banner.market_thought,      tone: tone.ring });
    if (banner?.event_story)         t.push({ label: "Risk / Event",       text: banner.event_story,         tone: TONES.contradiction.ring });
    else if (banner?.price_story)    t.push({ label: "Fiyat Hareketi",     text: banner.price_story,         tone: TONES.contradiction.ring });
    if (banner?.next_trigger)        t.push({ label: "Sonraki İzlem",      text: banner.next_trigger,        tone: TONES.waiting.ring });
    return t.slice(0, 3);
  }, [banner, tone.ring]);

  // 5 piyasa bağlamı modülü
  const ctxModules = useMemo(() => ([
    { key: "news",   label: "Haber Hikayesi",   text: banner?.news_story          ?? "",  icon: "📰" },
    { key: "price",  label: "Fiyat Tepkisi",    text: banner?.price_story         ?? "",  icon: "📈" },
    { key: "cal",    label: "Olay Takvimi",     text: banner?.event_calendar_note ?? "",  icon: "🗓" },
    { key: "pricing",label: "Piyasa Fiyatlaması", text: banner?.market_pricing_note ?? "", icon: "⚖" },
    { key: "geo",    label: "Jeopolitik",       text: banner?.event_story         ?? "",  icon: "🌐" },
  ]), [banner]);

  // AI trade opinion
  const best         = opinion?.best_candidate;
  const confidence   = confidenceFromOpinion(opinion);
  const opinionColor = best && best.asset !== "NONE"
    ? (OPINION_TONE[(best.bias?.toUpperCase() === "LONG" ? "LONG_BIAS" : "WAIT")] ?? "#94a3b8")
    : "#94a3b8";

  // Aktif kararlar
  const openCount   = trading?.open_positions?.length ?? 0;
  const dailyPnl    = trading?.daily_pnl_usd ?? 0;
  const tradedPairs = trading?.traded_pairs?.length ?? 0;
  const anomaly     = trading?.state_anomaly?.active ?? false;

  // Insight severity counts (risk_alert vb için)
  const insightCounts = useMemo(() => {
    const c = { CRITICAL: 0, WARNING: 0, OPPORTUNITY: 0, OBSERVATION: 0 };
    for (const i of insights) c[i.severity] = (c[i.severity] ?? 0) + 1;
    return c;
  }, [insights]);

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col"
      style={{ backgroundColor: "#02060f" }}
      onClick={onClose}
    >
      <style>{`
        @keyframes agc-spin   { from{transform:rotate(0)} to{transform:rotate(360deg)} }
        @keyframes agc-pulse  { 0%,100%{transform:scale(1);opacity:0.7} 50%{transform:scale(1.12);opacity:0.35} }
        @keyframes agc-float  { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
        @keyframes agc-breathe{ 0%,100%{opacity:0.78} 50%{opacity:1} }
        @keyframes agc-scan   { 0%{transform:translateY(-100%)} 100%{transform:translateY(100%)} }
        @keyframes agc-flow   { to{stroke-dashoffset:-32} }
        @keyframes agc-fade   { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }
        @keyframes agc-flash  { 0%{box-shadow:0 0 0 rgba(34,211,238,0)} 30%{box-shadow:0 0 18px rgba(34,211,238,0.35)} 100%{box-shadow:0 0 0 rgba(34,211,238,0)} }
        @keyframes agc-flip   { 0%{transform:perspective(700px) rotateX(78deg);opacity:0} 100%{transform:none;opacity:1} }
        @keyframes agc-bubble { 0%{opacity:0;transform:translateY(8px) scale(.92)} 8%,88%{opacity:1;transform:none} 100%{opacity:0;transform:translateY(-6px)} }
        .agc-flip-kids > * { animation: agc-flip .55s ease both; }
        .agc-flip-kids > *:nth-child(2){animation-delay:.07s}
        .agc-flip-kids > *:nth-child(3){animation-delay:.14s}
        .agc-flip-kids > *:nth-child(4){animation-delay:.21s}
        .agc-flip-kids > *:nth-child(5){animation-delay:.28s}
      `}</style>

      <div
        className="flex-1 overflow-y-auto w-full max-w-full min-w-0"
        style={{ backgroundColor: "#02060f" }}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <header className="sticky top-0 z-10 border-b border-cyan-500/15"
                style={{ background: "linear-gradient(180deg, #050d1a, #02060f)" }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-4 min-w-0">
            <div className="flex items-center gap-3 min-w-0">
              <span aria-hidden="true" className={tone.text}
                    style={animate ? { animation: "agc-breathe 2.6s ease-in-out infinite" } : undefined}>
                ◈
              </span>
              <div className="min-w-0">
                <p className="text-[12px] font-mono font-black uppercase tracking-[0.28em] text-cyan-100 truncate">
                  e-yAy <span className={tone.text}>AGENT</span>
                </p>
                <p className="text-[10px] font-mono text-cyan-400/65 truncate">
                  Agent Layer · Düşünen · Yorumlayan · Karar vermeyen
                </p>
              </div>
            </div>

            <div className="hidden md:flex items-center gap-1 ml-2">
              <span className="text-[10px] font-mono text-cyan-400/55 uppercase tracking-[0.22em]">
                Komut Merkezi · Canlı Analiz
              </span>
            </div>

            <div className="ml-auto flex items-center gap-1.5 flex-wrap justify-end shrink-0">
              <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest ${tone.border}`}
                    style={{ color: tone.ring, background: tone.soft }}>
                {tone.label}
              </span>
              <span className="rounded-md border border-cyan-700/40 bg-cyan-950/30 px-2 py-0.5 text-[10px] font-mono text-cyan-300">
                {fmtTime(banner?.updated_at)}
              </span>
              <span className="rounded-md border border-emerald-700/40 bg-emerald-950/30 px-2 py-0.5 text-[10px] font-mono text-emerald-300">
                PAPER_SAFE
              </span>
              <span className="rounded-md border border-eyay-border bg-black/30 px-2 py-0.5 text-[10px] font-mono text-eyay-dim">
                {openCount} pozisyon
              </span>
              {voice.supported && (
                <button
                  type="button"
                  onClick={voice.toggle}
                  aria-pressed={voice.enabled}
                  title="Son dakika haberleri sesli oku (tr-TR)"
                  className={`rounded-md border px-2 py-0.5 text-[10px] font-mono font-bold transition-colors ${
                    voice.enabled
                      ? "border-emerald-600/60 bg-emerald-950/40 text-emerald-300"
                      : "border-eyay-border bg-black/30 text-eyay-faint hover:text-eyay-dim"
                  }`}>
                  {voice.enabled ? "🔊 SES" : "🔇 SES"}
                </button>
              )}
              <button
                onClick={onClose}
                className="ml-1 rounded-md border border-cyan-700/40 bg-cyan-950/30 px-2 py-0.5 text-[10px] font-mono text-cyan-200 hover:bg-cyan-900/40 transition-colors">
                ESC
              </button>
            </div>
          </div>
        </header>

        {/* ── Body grid ── */}
        <div className="max-w-7xl mx-auto px-3 sm:px-5 py-5 grid grid-cols-1 sm:grid-cols-[64px_minmax(0,1fr)] gap-3 min-w-0">
          {/* Sidebar */}
          <nav className="sm:sticky sm:top-[60px] sm:self-start flex sm:flex-col flex-row gap-1 bg-black/30 border border-cyan-500/15 rounded-2xl p-1.5 overflow-x-auto sm:overflow-visible"
               aria-label="Agent komut merkezi gezinme">
            {NAV_ITEMS.map(item => {
              const isActive = activeId === item.id;
              return (
                <button key={item.id}
                        type="button"
                        onClick={() => handleNavClick(item)}
                        aria-pressed={isActive}
                        aria-label={item.label}
                        title={item.label}
                        className={`group relative shrink-0 w-12 h-12 sm:w-full sm:aspect-square rounded-lg flex items-center justify-center text-lg transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                          isActive
                            ? "border border-cyan-500/60 bg-cyan-950/50 text-cyan-100 shadow-[0_0_12px_rgba(34,211,238,0.30)]"
                            : "border border-white/5 text-slate-400 hover:text-cyan-200 hover:bg-white/[0.04] hover:border-cyan-700/30"
                        }`}>
                  <span aria-hidden="true">{item.icon}</span>
                  {/* Tooltip label — hover'da yan çıkar */}
                  <span aria-hidden="true"
                        className="hidden sm:block absolute left-full ml-2 px-2.5 py-1 rounded-md border border-cyan-500/50 bg-[#0f1118] text-cyan-100 text-[10.5px] font-semibold whitespace-nowrap opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 pointer-events-none transition-opacity z-30 shadow-lg shadow-black/40">
                    {item.label}
                  </span>
                </button>
              );
            })}
          </nav>

          {/* Main — tab-bazlı içerik */}
          <div id="agent-tab-content" className="min-w-0 flex flex-col gap-4">

            {/* Tab başlığı — açıklamalı, sağda safety chipler */}
            <div className="flex items-start justify-between gap-3 pb-3 border-b border-cyan-500/20 bg-[#0f1118]/60 backdrop-blur-sm rounded-t-lg px-3 pt-2.5 -mx-1">
              <div className="flex items-start gap-3 min-w-0">
                <span aria-hidden="true" className="text-cyan-300 text-2xl leading-none mt-0.5 shrink-0"
                      style={animate ? { textShadow: "0 0 12px rgba(34,211,238,0.55)" } : undefined}>
                  {activeTab.icon}
                </span>
                <div className="min-w-0">
                  <p className="text-base font-bold text-cyan-50 leading-tight tracking-tight">
                    {activeTab.label}
                  </p>
                  <p className="text-[11px] text-slate-300/85 leading-relaxed mt-0.5">
                    {activeTab.description}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap justify-end shrink-0">
                <span className="rounded-md border border-emerald-700/50 bg-emerald-950/50 px-2 py-0.5 text-[10px] font-mono font-bold text-emerald-200 uppercase tracking-wider">
                  PAPER_SAFE
                </span>
                <span className="hidden sm:inline-block rounded-md border border-cyan-700/40 bg-cyan-950/40 px-2 py-0.5 text-[10px] font-mono text-cyan-200 uppercase tracking-wider">
                  NO_EXECUTION
                </span>
              </div>
            </div>

            {/* ◈ KOMUT MERKEZİ — agent core + thoughts + orbit + insight kısa */}
            {activeId === "agent-core-section" && (
            <>
            {/* ── CANLI AGENT FEED — banner/insight polling ile anlık güncellenir ── */}
            <div key={pulseKey}
                 className="rounded-xl border border-cyan-500/20 bg-black/30 p-3"
                 style={animate ? { animation: "agc-flash 0.9s ease" } : undefined}
                 data-testid="agent-live-feed">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-[10px] font-mono text-cyan-400/70 uppercase tracking-[0.22em]">
                  ⟳ Canlı Agent Feed
                </p>
                <div className="flex items-center gap-1.5">
                  {isStale && (
                    <span className="rounded border border-amber-600/50 bg-amber-950/40 px-1.5 py-0.5 text-[10px] font-mono text-amber-300 uppercase">
                      stale
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-eyay-faint">
                    Son güncelleme: {fmtTime(bannerStamp || undefined)}
                  </span>
                </div>
              </div>
              <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2 ${animate ? "agc-flip-kids" : ""}`}>
                <FeedCell label="Anlık Özet"        tone={tone.ring}
                          text={banner?.headline || banner?.main_view || ""} />
                <FeedCell label="Öne Çıkan Sinyal"  tone={TONES.managing_position.ring}
                          text={topSignals[0] ?? ""} />
                <FeedCell label="Ana Çelişki"       tone={TONES.contradiction.ring}
                          text={contradictions[0] ?? ""} />
                <FeedCell label="İzlenecek Varlık"  tone={TONES.waiting.ring}
                          text={watchNext[0] ?? ""} />
                <FeedCell label="Son Karar / Duruş" tone={tone.ring}
                          text={[tone.label, opinion?.overall_view || banner?.position_note || ""].filter(Boolean).join(" · ")} />
              </div>
            </div>

            {/* ── Agent Orchestration — "Agent şu an neyi kontrol ediyor?" ── */}
            {banner?.agent_orchestration && (
              <OrchestrationPanel orch={banner.agent_orchestration} />
            )}

            {/* ── Üst grid: thoughts | core | opinion ── */}
            <div className="grid grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)_320px] gap-4 items-stretch">

              {/* Thoughts (sol) */}
              <div className="flex flex-col gap-2">
                <p className="text-[10px] font-mono text-cyan-400/65 uppercase tracking-[0.22em]">
                  ✦ Şu an ne düşünüyorum
                </p>
                {thoughts.length > 0 ? (
                  thoughts.map((t, i) => (
                    <div key={i} className="rounded-xl border bg-black/40 px-3 py-2.5"
                         style={{
                           borderColor: `${t.tone}55`,
                           boxShadow: animate ? `0 0 12px ${t.tone}18` : undefined,
                           animation: animate ? `agc-fade 0.5s ease ${i * 0.1}s both` : undefined,
                         }}>
                      <p className="text-[10px] font-mono uppercase tracking-widest mb-1"
                         style={{ color: t.tone, opacity: 0.85 }}>{t.label}</p>
                      <p className="text-[10.5px] font-mono text-eyay-dim leading-snug line-clamp-3">
                        {t.text}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-[10px] font-mono text-eyay-faint italic">Düşünce verisi bekleniyor.</p>
                )}
              </div>

              {/* Agent Core (orta) */}
              <div id="agent-core-section" data-section="agent-core" className="scroll-mt-[80px] relative flex items-center justify-center bg-black/30 border border-cyan-500/15 rounded-2xl p-3 min-h-[340px] overflow-hidden">
                {/* Köşe brackets */}
                <span aria-hidden="true" className="absolute top-2 left-2 w-3 h-3 border-t border-l border-cyan-400/40" />
                <span aria-hidden="true" className="absolute top-2 right-2 w-3 h-3 border-t border-r border-cyan-400/40" />
                <span aria-hidden="true" className="absolute bottom-2 left-2 w-3 h-3 border-b border-l border-cyan-400/40" />
                <span aria-hidden="true" className="absolute bottom-2 right-2 w-3 h-3 border-b border-r border-cyan-400/40" />
                <AgentCoreVisual ring={tone.ring} soft={tone.soft} animate={animate} size={280} />

                {/* 4 floating orbit cards — veri güncellenince flip (pulseKey remount) */}
                <div key={`o1-${pulseKey}`} className="absolute top-3 left-3"
                     style={animate ? { animation: "agc-flip .55s ease both" } : undefined}>
                  <OrbitCard label="Top Sinyal" n={topSignals.length} tone={TONES.managing_position.ring} animate={animate} />
                </div>
                <div key={`o2-${pulseKey}`} className="absolute top-3 right-3"
                     style={animate ? { animation: "agc-flip .55s ease .07s both" } : undefined}>
                  <OrbitCard label="Çelişki" n={contradictions.length} tone={TONES.contradiction.ring} animate={animate} />
                </div>
                <div key={`o3-${pulseKey}`} className="absolute bottom-3 left-3"
                     style={animate ? { animation: "agc-flip .55s ease .14s both" } : undefined}>
                  <OrbitCard label="İzlem" n={watchNext.length} tone={TONES.waiting.ring} animate={animate} />
                </div>
                <div key={`o4-${pulseKey}`} className="absolute bottom-3 right-3"
                     style={animate ? { animation: "agc-flip .55s ease .21s both" } : undefined}>
                  <OrbitCard
                    label="Mod"
                    value={tone.label}
                    tone={tone.ring}
                    animate={animate}
                  />
                </div>

                {/* Son dakika speech bubble — agent ağzından çıkıyormuş gibi */}
                {newsBubble && (
                  <div className="pointer-events-none absolute z-10 left-1/2 -translate-x-1/2 top-10 sm:top-8 max-w-[250px] min-w-0"
                       style={animate ? { animation: "agc-bubble 10s ease both" } : undefined}>
                    <div className="relative rounded-xl border border-red-400/60 bg-[#10060c]/90 backdrop-blur-sm px-2.5 py-2 shadow-[0_0_18px_rgba(248,113,113,0.25)]">
                      <p className="text-[9px] font-mono font-black text-red-300 uppercase tracking-[0.2em] mb-0.5">
                        🔴 Son Dakika
                      </p>
                      <p className="text-[10.5px] font-mono text-eyay-text leading-snug line-clamp-3">
                        {newsBubble}
                      </p>
                      <span aria-hidden="true"
                            className="absolute -bottom-[6px] left-1/2 -translate-x-1/2 w-3 h-3 rotate-45 bg-[#10060c]/90 border-b border-r border-red-400/60" />
                    </div>
                  </div>
                )}
              </div>

              {/* AI Trade Fikrim (sağ) */}
              <div id="trade-opinion-section" data-section="trade-opinion" className="scroll-mt-[80px] rounded-2xl border border-cyan-500/20 bg-gradient-to-b from-black/40 via-cyan-950/15 to-black/40 p-3 flex flex-col gap-2 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-mono text-cyan-300/70 uppercase tracking-[0.22em]">
                    ✦ AI Trade Fikrim
                  </p>
                  <span className="text-[10px] font-mono text-eyay-faint">v{(opinion?.schema_version || "—").replace("ai_trade_opinion_", "")}</span>
                </div>

                <div className="flex items-center gap-3">
                  <ConfidenceRing value={confidence} color={opinionColor} size={88} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">Ana Fikir</p>
                    <p className="text-[14px] font-mono font-black tracking-wider truncate" style={{ color: opinionColor }}>
                      {best?.asset && best.asset !== "NONE"
                        ? `${best.asset} ${best.bias?.toUpperCase() === "LONG" ? "LONG" : best.bias?.toUpperCase() === "SHORT" ? "SHORT" : "WAIT"}`
                        : "NONE"}
                    </p>
                    {best?.trigger && (
                      <p className="text-[10px] font-mono text-eyay-dim leading-snug mt-1 line-clamp-2">⚡ {best.trigger}</p>
                    )}
                  </div>
                </div>

                {best?.risk && (
                  <div className="border-t border-cyan-700/20 pt-2">
                    <p className="text-[10px] font-mono text-cyan-400/65 uppercase tracking-widest mb-0.5">Invalidation</p>
                    <p className="text-[10px] font-mono text-eyay-dim leading-snug line-clamp-2">{best.risk}</p>
                  </div>
                )}

                {/* Asset opinion chips */}
                {(opinion?.asset_opinions?.length ?? 0) > 0 && (
                  <div className="border-t border-cyan-700/20 pt-2">
                    <p className="text-[10px] font-mono text-cyan-400/65 uppercase tracking-widest mb-1">Varlık Görüşleri</p>
                    <div className="flex flex-wrap gap-1">
                      {opinion!.asset_opinions!.slice(0, 5).map(a => {
                        const c = OPINION_TONE[a.opinion?.toUpperCase()] ?? "#94a3b8";
                        return (
                          <span key={a.asset}
                                className="text-[10px] font-mono px-1.5 py-0.5 rounded border"
                                style={{ color: c, borderColor: `${c}55`, background: `${c}11` }}>
                            {a.asset} · {a.opinion}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            </>
            )}

            {/* ◇ PİYASA ZEKASI — 5 modül */}
            {activeId === "market-context-section" && (
            <div id="market-context-section" data-section="market-context" className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
              {ctxModules.map(c => (
                <details key={c.key} className="group rounded-xl border border-cyan-500/15 bg-black/30 p-2 min-w-0">
                  <summary className="flex items-center gap-1.5 cursor-pointer list-none">
                    <span aria-hidden="true" className="text-cyan-300/80">{c.icon}</span>
                    <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-300/75 truncate">
                      {c.label}
                    </span>
                    <span className="ml-auto text-[10px] font-mono text-eyay-faint group-open:hidden">▸</span>
                    <span className="ml-auto text-[10px] font-mono text-eyay-faint hidden group-open:inline">▾</span>
                  </summary>
                  <p className="text-[10px] font-mono text-eyay-dim leading-snug mt-1.5 line-clamp-1 group-open:line-clamp-none">
                    {c.text || "Veri bekleniyor."}
                  </p>
                </details>
              ))}
            </div>
            )}

            {/* △ AI TRADE FİKRİM — opinion genişletilmiş */}
            {activeId === "trade-opinion-section" && (
            <div className="flex flex-col gap-3">
              {best && best.asset !== "NONE" ? (
                <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-b from-black/40 via-cyan-950/15 to-black/40 p-4 grid grid-cols-1 md:grid-cols-[140px_minmax(0,1fr)] gap-4 items-start">
                  <ConfidenceRing value={confidence} color={opinionColor} size={132} />
                  <div className="min-w-0">
                    <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">Ana Fikir</p>
                    <p className="text-[20px] font-mono font-black tracking-wider" style={{ color: opinionColor }}>
                      {best.asset} {best.bias?.toUpperCase() === "LONG" ? "LONG" : best.bias?.toUpperCase() === "SHORT" ? "SHORT" : "WAIT"}
                    </p>
                    {best.reason && <p className="text-[10px] font-mono text-eyay-dim mt-1 leading-snug">{best.reason}</p>}
                    {best.trigger && <p className="text-[10px] font-mono text-cyan-300/80 mt-2 leading-snug">⚡ Tetikleyici: {best.trigger}</p>}
                    {best.risk && <p className="text-[10px] font-mono text-amber-300/80 mt-1 leading-snug">⚠ Invalidation: {best.risk}</p>}
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-eyay-border bg-black/30 p-4">
                  <p className="text-[10px] font-mono text-eyay-faint italic">AI Trade fikri bekleniyor.</p>
                  {opinion?.no_trade_reason && (
                    <p className="text-[10px] font-mono text-eyay-dim mt-1.5 leading-snug">{opinion.no_trade_reason}</p>
                  )}
                </div>
              )}

              {opinion?.market_opinion && (
                <div className="rounded-xl border border-cyan-500/15 bg-black/30 p-3">
                  <p className="text-[10px] font-mono text-cyan-400/70 uppercase tracking-widest mb-1">Piyasa Görüşü</p>
                  <p className="text-[10.5px] font-mono text-eyay-dim leading-snug">{opinion.market_opinion}</p>
                </div>
              )}

              {(opinion?.asset_opinions?.length ?? 0) > 0 && (
                <div className="rounded-xl border border-cyan-500/15 bg-black/30 p-3">
                  <p className="text-[10px] font-mono text-cyan-400/70 uppercase tracking-widest mb-2">Varlık Görüşleri</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {opinion!.asset_opinions!.map(a => {
                      const c = OPINION_TONE[a.opinion?.toUpperCase()] ?? "#94a3b8";
                      return (
                        <div key={a.asset} className="rounded-lg border bg-black/40 px-2 py-1.5"
                             style={{ borderColor: `${c}44` }}>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-mono font-bold" style={{ color: c }}>{a.asset}</span>
                            <span className="text-[10px] font-mono px-1 rounded border"
                                  style={{ color: c, borderColor: `${c}55` }}>{a.opinion}</span>
                            <span className="ml-auto text-[10px] font-mono text-eyay-faint">{a.conviction}</span>
                          </div>
                          {a.trigger_needed && (
                            <p className="text-[10px] font-mono text-eyay-dim mt-1 leading-snug line-clamp-2">⚡ {a.trigger_needed}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {(opinion?.open_position_opinions?.length ?? 0) > 0 && (
                <div className="rounded-xl border border-cyan-500/15 bg-black/30 p-3">
                  <p className="text-[10px] font-mono text-cyan-400/70 uppercase tracking-widest mb-2">Açık Pozisyon Görüşleri</p>
                  <div className="space-y-1.5">
                    {opinion!.open_position_opinions!.map(p => {
                      const c = OPINION_TONE[p.opinion?.toUpperCase()] ?? "#94a3b8";
                      return (
                        <div key={`${p.pair}-${p.side}`} className="rounded-lg border bg-black/40 px-2 py-1.5"
                             style={{ borderColor: `${c}44` }}>
                          <p className="text-[10px] font-mono font-bold" style={{ color: c }}>{p.pair} {p.side} · {p.opinion}</p>
                          {p.reason && <p className="text-[10px] font-mono text-eyay-dim mt-0.5 leading-snug">{p.reason}</p>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {(opinion?.next_3_triggers?.length ?? 0) > 0 && (
                <div className="rounded-xl border border-cyan-500/15 bg-black/30 p-3">
                  <p className="text-[10px] font-mono text-cyan-400/70 uppercase tracking-widest mb-1.5">Sonraki Tetikleyiciler</p>
                  <ul className="space-y-0.5 text-[10px] font-mono text-eyay-dim">
                    {opinion!.next_3_triggers!.map((t, i) => <li key={i}>› {t}</li>)}
                  </ul>
                </div>
              )}
            </div>
            )}

            {/* ⊙ HABER RADARI */}
            {activeId === "news-radar-section" && (
            <div id="news-radar-section" className="rounded-xl border border-red-700/30 bg-black/30 p-2">
              <p className="text-[10px] font-mono text-red-300/70 uppercase tracking-widest mb-1.5 px-1">
                🚨 Son Dakika Haber Radarı
              </p>
              <BreakingNewsPanelShell headlines={headlines} />

              {insights.length > 0 && (
                <div className="mt-3 rounded-xl border border-cyan-500/15 bg-black/30 px-3 py-2">
                  <p className="text-[10px] font-mono text-cyan-400/65 uppercase tracking-widest mb-1.5">
                    Ajan Günlüğü ({insights.length})
                  </p>
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {insights.slice(0, 8).map((ins, i) => {
                      const sevColor = ins.severity === "CRITICAL" ? "#f87171"
                                    : ins.severity === "WARNING"  ? "#fbbf24"
                                    : ins.severity === "OPPORTUNITY" ? "#34d399"
                                    : "#94a3b8";
                      return (
                        <div key={i} className="shrink-0 max-w-[260px] rounded-lg border px-2 py-1"
                             style={{ borderColor: `${sevColor}55`, background: `${sevColor}11` }}>
                          <p className="text-[10px] font-mono font-black uppercase tracking-widest" style={{ color: sevColor }}>
                            {ins.severity} · {ins.asset_code}
                          </p>
                          <p className="text-[10px] font-mono text-eyay-dim leading-snug truncate">{ins.headline}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            )}

            {/* ▤ AKTİF KARARLAR */}
            {activeId === "positions-section" && (
            <>
            <div id="positions-section" data-section="positions" className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Stat label="Açık Pozisyon" value={String(openCount)} tone={openCount > 0 ? "#34d399" : "#94a3b8"} />
              <Stat label="Günlük PnL"    value={`${dailyPnl >= 0 ? "+" : "−"}${Math.abs(dailyPnl).toFixed(0)} USD`}
                    tone={dailyPnl >= 0 ? "#34d399" : "#f87171"} />
              <Stat label="İşlenen Pair"  value={String(tradedPairs)} tone="#22d3ee" />
              <Stat label="Risk Durumu"   value={anomaly ? "ANOMALİ" : "OK"} tone={anomaly ? "#f87171" : "#34d399"} />
            </div>

              {/* Açık pozisyon listesi — pozisyon varsa */}
              {(trading?.open_positions?.length ?? 0) > 0 && (
                <div className="col-span-2 md:col-span-4 rounded-xl border border-cyan-500/15 bg-black/30 p-3 mt-1">
                  <p className="text-[10px] font-mono text-cyan-400/65 uppercase tracking-widest mb-2">
                    Açık Pozisyonlar
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {trading!.open_positions.map(p => {
                      const c = p.pnl_usd >= 0 ? "#34d399" : "#f87171";
                      return (
                        <div key={`${p.pair}-${p.side}`} className="rounded-lg border bg-black/40 px-2.5 py-1.5"
                             style={{ borderColor: `${c}44` }}>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-mono font-bold text-eyay-text">{p.pair}</span>
                            <span className="text-[10px] font-mono px-1 rounded border" style={{ color: c, borderColor: `${c}55` }}>{p.side}</span>
                            <span className="ml-auto text-[10px] font-mono font-bold" style={{ color: c }}>
                              {p.pnl_usd >= 0 ? "+" : "−"}{Math.abs(p.pnl_usd).toFixed(0)} USD
                            </span>
                          </div>
                          <p className="text-[10px] font-mono text-eyay-faint mt-0.5">
                            Giriş {p.entry_price.toFixed(2)} · Şimdi {p.current_price.toFixed(2)} · {p.pnl_pct.toFixed(2)}%
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
            )}

            {/* (Insight ticker artık ◊ Komut Merkezi yerine Haber Radarı tab'ında) */}
            {false && insights.length > 0 && (
              <div className="rounded-xl border border-cyan-500/15 bg-black/30 px-3 py-2">
                <p className="text-[10px] font-mono text-cyan-400/65 uppercase tracking-widest mb-1.5">
                  Ajan Günlüğü ({insights.length})
                </p>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {insights.slice(0, 6).map((ins, i) => {
                    const sevColor = ins.severity === "CRITICAL" ? "#f87171"
                                  : ins.severity === "WARNING"  ? "#fbbf24"
                                  : ins.severity === "OPPORTUNITY" ? "#34d399"
                                  : "#94a3b8";
                    return (
                      <div key={i} className="shrink-0 max-w-[260px] rounded-lg border px-2 py-1"
                           style={{ borderColor: `${sevColor}55`, background: `${sevColor}11` }}>
                        <p className="text-[10px] font-mono font-black uppercase tracking-widest" style={{ color: sevColor }}>
                          {ins.severity} · {ins.asset_code}
                        </p>
                        <p className="text-[10px] font-mono text-eyay-dim leading-snug truncate">{ins.headline}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* (Eski sürekli render Breaking News bloğu — tab'a taşındı) */}
            {false && (
            <div className="rounded-xl border border-red-700/30 bg-black/30 p-2">
              <p className="text-[10px] font-mono text-red-300/70 uppercase tracking-widest mb-1.5 px-1">
                🚨 Son Dakika Haber Radarı
              </p>
              <BreakingNewsPanelShell headlines={headlines} />
            </div>
            )}

            {/* ≡ KARAR DETAYLARI — sadece bu tab seçili iken */}
            {activeId === "decision-details-section" &&
             (confirmationChecklist.length > 0 || asymmetry) && (
              <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,260px)] gap-3 items-start">
                {confirmationChecklist.length > 0 && (
                  <ConfirmationStrip items={confirmationChecklist} />
                )}
                {asymmetry && <AsymmetryCard asymmetry={asymmetry} />}
              </div>
            )}
            {activeId === "decision-details-section" && decision && (
              <section id="decision-details-section" data-section="decision-details"
                       className="rounded-xl border border-cyan-500/15 bg-black/30 overflow-hidden">
                <button
                  type="button"
                  onClick={() => setDetailOpen(o => !o)}
                  aria-expanded={detailOpen}
                  className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/[0.02]">
                  <div className="flex items-center gap-2">
                    <span className="text-cyan-300/70 text-xs">🎯</span>
                    <p className="text-[10px] font-mono font-bold text-eyay-dim uppercase tracking-[0.2em]">
                      Karar Detayları
                    </p>
                    <span className="text-[10px] font-mono text-eyay-faint">
                      · Aksiyon · İyileşme · Risk
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-eyay-faint">{detailOpen ? "▾ kapat" : "▸ aç"}</span>
                </button>
                {detailOpen && (
                  <div className="border-t border-cyan-500/15 p-3 bg-black/20 max-h-[500px] overflow-y-auto" style={{ scrollbarWidth: "thin" }}>
                    <ActionCenter decision={decision} ownerActions={ownerActions} flipConditions={flipConditions} />
                  </div>
                )}
              </section>
            )}

            {/* ⚙ SİSTEM KONTROLLERİ — sadece bu tab seçili iken */}
            {activeId === "system-controls-section" && (
            <section id="system-controls-section" data-section="system-controls"
                     className="rounded-xl border border-cyan-500/15 bg-black/30 overflow-hidden">
              <button
                type="button"
                onClick={() => setSystemOpen(o => !o)}
                aria-expanded={systemOpen}
                className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/[0.02]">
                <div className="flex items-center gap-2">
                  <span className="text-cyan-300/70 text-xs">⚙</span>
                  <p className="text-[10px] font-mono font-bold text-eyay-dim uppercase tracking-[0.2em]">
                    Sistem Kontrolleri
                  </p>
                  <span className="text-[10px] font-mono text-eyay-faint">
                    · Makro+Risk · Öğrenme · System Health
                  </span>
                </div>
                <span className="text-[10px] font-mono text-eyay-faint">{systemOpen ? "▾ kapat" : "▸ aç"}</span>
              </button>
              {systemOpen && (
                <div className="border-t border-cyan-500/15 p-3 bg-black/20 space-y-3">
                  {macro && appetite ? (
                    <MacroPanel macro={macro} appetite={appetite} showUnified={true} />
                  ) : (
                    <p className="text-[10px] font-mono text-eyay-faint italic">Makro/Risk sentezi: veri yok.</p>
                  )}
                  <LearningPanel />
                  <SystemHealthPanel />
                </div>
              )}
            </section>
            )}

            {/* ── Footer ── */}
            <div className="pt-2 border-t border-cyan-500/15">
              <p className="text-[10px] font-mono text-eyay-faint text-center leading-relaxed">
                Agent canlı izleme · banner 30sn · insight 15sn · saf analiz<br />
                <span className="text-cyan-300/70">PAPER_SAFE · NO_EXECUTION · tüm gerçek kararlar insana aittir</span>
              </p>
            </div>
          </div>
        </div>

        {/* Alt sabit kapat çubuğu */}
        <div className="sticky bottom-0 border-t border-cyan-500/20"
             style={{ background: "linear-gradient(180deg, #050d1a, #02060f)" }}>
          <div className="max-w-7xl mx-auto px-6 py-2.5 flex items-center justify-between">
            <span className="text-[10px] font-mono text-cyan-400/60">
              ESC veya backdrop → kapat
            </span>
            <span className="text-[10px] font-mono text-cyan-400/50">
              insight critical: {insightCounts.CRITICAL} · warning: {insightCounts.WARNING} · obs: {insightCounts.OBSERVATION}
            </span>
            <button
              onClick={onClose}
              className="px-3 py-1 rounded-lg border border-cyan-500/40 text-cyan-200 text-[10px] font-mono font-bold hover:bg-cyan-900/30 transition-colors">
              DASHBOARD'A DÖN
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Mini stat ────────────────────────────────────────────────────────────────

// Canlı feed hücresi — veri yoksa "veri bekleniyor"
// ── Agent Orchestration panel ────────────────────────────────────────────────
const SRC_STATUS: Record<string, { tr: string; cls: string }> = {
  ok:       { tr: "ok",       cls: "border-emerald-600/50 bg-emerald-950/40 text-emerald-300" },
  stale:    { tr: "bayat",    cls: "border-amber-600/50 bg-amber-950/40 text-amber-300" },
  degraded: { tr: "bozuk",    cls: "border-red-600/50 bg-red-950/40 text-red-300" },
  missing:  { tr: "yok",      cls: "border-red-600/50 bg-red-950/40 text-red-300" },
  unknown:  { tr: "—",        cls: "border-slate-600/50 bg-slate-900/50 text-slate-400" },
};
const SRC_LABEL: Record<string, string> = {
  price: "Fiyat", news: "Haber", macro: "Makro", event: "Olay", paper_state: "Paper",
};

function OrchestrationPanel({ orch }: { orch: AgentOrchestration }) {
  if (orch.status === "degraded") {
    return (
      <div data-testid="agent-orchestration" className="rounded-xl border border-amber-700/40 bg-amber-950/15 px-3 py-2">
        <p className="text-[10px] font-mono text-amber-300/80">⟳ Orchestration durumu geçici olarak yok ({orch.reason}).</p>
      </div>
    );
  }
  const ds: Record<string, string> = orch.data_sources ?? {};
  const po = orch.paper_observer ?? {};
  const val = orch.validator ?? {};
  const adj = po.active_adjustments ?? {};
  const adjEntries = Object.entries(adj).slice(0, 3);
  const hasDivergence = (val.conflicts ?? []).length > 0;
  const staleList = val.stale_inputs ?? [];
  return (
    <div data-testid="agent-orchestration"
         className="rounded-xl border border-cyan-500/20 bg-black/30 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-mono text-cyan-300/80 uppercase tracking-[0.22em]">
          ⟳ Agent şu an neyi kontrol ediyor?
        </p>
        <span className="text-[10px] font-mono text-eyay-faint">
          {po.experiment_mode ? "🧪 experiment" : "standard"} · {po.open_positions ?? 0} açık · {po.manual_ready ?? 0} hazır
        </span>
      </div>

      {/* Data source status chips */}
      <div className="flex flex-wrap items-center gap-1.5">
        {(["price", "news", "macro", "event", "paper_state"] as const).map(k => {
          const st = SRC_STATUS[ds[k] ?? "unknown"] ?? SRC_STATUS.unknown;
          return (
            <span key={k} className={`rounded border px-1.5 py-0.5 text-[10px] font-mono ${st.cls}`}>
              {SRC_LABEL[k]} · {st.tr}
            </span>
          );
        })}
      </div>

      {/* Learning + warning chips */}
      {(adjEntries.length > 0 || staleList.length > 0 || hasDivergence) && (
        <div className="flex flex-wrap items-center gap-1.5">
          {adjEntries.map(([key, a]) => {
            const boost = a.label === "learning_boost";
            return (
              <span key={key}
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-mono font-bold ${
                      boost ? "border-emerald-600/60 bg-emerald-950/40 text-emerald-300"
                            : "border-red-600/60 bg-red-950/40 text-red-300"}`}
                    title={`${key} · ${a.wins}W/${a.losses}L · size x${a.size_multiplier} · threshold ${a.threshold_delta >= 0 ? "+" : ""}${a.threshold_delta}`}>
              {key.split("|")[0]} {boost ? "BOOST" : "PENALTY"} x{a.size_multiplier}
            </span>
            );
          })}
          {staleList.length > 0 && (
            <span className="rounded border border-amber-600/60 bg-amber-950/40 text-amber-300 px-1.5 py-0.5 text-[10px] font-mono">
              ⚠ stale: {staleList.join(", ")}
            </span>
          )}
          {hasDivergence && (
            <span className="rounded border border-fuchsia-600/60 bg-fuchsia-950/40 text-fuchsia-300 px-1.5 py-0.5 text-[10px] font-mono">
              ⚠ divergence
            </span>
          )}
        </div>
      )}

      {/* Kısa canlı anlatım */}
      {orch.risk_explainer && (
        <p className="text-[10px] font-mono text-eyay-dim leading-snug border-t border-cyan-700/20 pt-1.5">
          ◇ {orch.risk_explainer}
        </p>
      )}
    </div>
  );
}

function FeedCell({ label, text, tone }: { label: string; text: string; tone: string }) {
  return (
    <div className="rounded-lg border bg-black/40 px-2.5 py-2 min-w-0"
         style={{ borderColor: `${tone}44` }}>
      <p className="text-[10px] font-mono uppercase tracking-widest leading-none mb-1"
         style={{ color: tone, opacity: 0.85 }}>{label}</p>
      {text ? (
        <p className="text-[11px] font-mono text-eyay-dim leading-snug line-clamp-3">{text}</p>
      ) : (
        <p className="text-[10px] font-mono text-eyay-faint italic">veri bekleniyor</p>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-xl border bg-black/30 px-3 py-2"
         style={{ borderColor: `${tone}44`, boxShadow: `0 0 10px ${tone}14` }}>
      <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">{label}</p>
      <p className="text-[14px] font-mono font-black mt-0.5" style={{ color: tone }}>{value}</p>
    </div>
  );
}

// ── Orbit floating card ──────────────────────────────────────────────────────

function OrbitCard({
  label, n, value, tone, animate,
}: { label: string; n?: number; value?: string; tone: string; animate: boolean }) {
  return (
    <div
      className="rounded-lg border bg-black/55 backdrop-blur-sm px-2 py-1 min-w-[80px]"
      style={{
        borderColor: `${tone}55`,
        boxShadow: animate ? `0 0 10px ${tone}22` : undefined,
        animation: animate ? "agc-float 6s ease-in-out infinite" : undefined,
      }}>
      <p className="text-[10px] font-mono uppercase tracking-widest"
         style={{ color: tone, opacity: 0.85 }}>{label}</p>
      <p className="text-[14px] font-mono font-black leading-none mt-0.5"
         style={{ color: tone }}>
        {value ?? (n ?? 0)}
      </p>
    </div>
  );
}
