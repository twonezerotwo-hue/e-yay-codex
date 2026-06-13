"use client";

/**
 * FAZ 30 — Agent Main Panel.
 *
 * Üst sticky AgentInsightBar kaldırıldı; banner'ın içindeki Agent ana ekranı
 * (Agent Core + komut merkezi görünümü) ana dashboard'un en üst ana paneli
 * olarak buraya taşındı. "Agent Detayı" butonu ve eyay:open-agent-modal
 * eventi mevcut AgentCommandCenter modalını açar (modal hosting burada).
 * Banner verisi yoksa klasik fallback: AgentBriefPanel.
 * Karar üretmez. PAPER_SAFE / NO_EXECUTION.
 */
import { useEffect, useRef, useState } from "react";

import AgentBriefPanel from "@/components/AgentBriefPanel";
import AgentCommandCenter from "@/components/AgentCommandCenter";
import AgentCoreVisual from "@/components/AgentCoreVisual";
import { useAgentVoice } from "@/lib/useAgentVoice";
import type {
  AsymmetrySignal, ConfirmationItem, Decision, FlipCondition, NewsHeadline, RegimeReport,
  SignalChainLevel, SignalChainNotification, SignalChainView,
} from "@/lib/types";

// ── Signal chain bildirim stil/sıra eşlemeleri (orb'dan çıkan balon) ─────────
// Önceliği yüksek olan önce gösterilir (conflict > triple > double > single > duplicate).
const CHAIN_LEVEL_RANK: Record<SignalChainLevel, number> = {
  timeframe_conflict: 5,
  triple_timeframe_confirmation: 4,
  double_timeframe_signal: 3,
  single_signal: 2,
  same_timeframe_duplicate: 1,
};

const CHAIN_LEVEL_LABEL: Record<SignalChainLevel, string> = {
  single_signal: "TEK SİNYAL",
  double_timeframe_signal: "ÇİFT TF",
  triple_timeframe_confirmation: "ÜÇLÜ TEYİT",
  same_timeframe_duplicate: "YİNELENEN",
  timeframe_conflict: "ÇELİŞKİ",
};

interface ChainTone {
  ring: string; border: string; bg: string; text: string; chip: string;
}
const CHAIN_TONES: Record<SignalChainNotification["tone"], ChainTone> = {
  amber:   { ring: "#fbbf24", border: "border-amber-500/60",   bg: "bg-amber-950/45",   text: "text-amber-200",   chip: "border-amber-500/50 text-amber-300" },
  cyan:    { ring: "#22d3ee", border: "border-cyan-500/60",    bg: "bg-cyan-950/45",    text: "text-cyan-200",    chip: "border-cyan-500/50 text-cyan-300" },
  emerald: { ring: "#34d399", border: "border-emerald-500/60", bg: "bg-emerald-950/45", text: "text-emerald-200", chip: "border-emerald-500/50 text-emerald-300" },
  slate:   { ring: "#94a3b8", border: "border-slate-500/50",   bg: "bg-slate-900/55",   text: "text-slate-200",   chip: "border-slate-500/50 text-slate-300" },
  red:     { ring: "#f87171", border: "border-red-500/60",     bg: "bg-red-950/45",     text: "text-red-200",     chip: "border-red-500/50 text-red-300" },
};

// ── Banner tipi (AgentInsightBar ile aynı endpoint kontratı) ─────────────────

type BannerMode = "waiting" | "managing_position" | "contradiction" | "risk_alert" | "learning";

interface AgentBanner {
  mode:           BannerMode;
  headline:       string;
  main_view:      string;
  top_signals:    string[];
  contradictions: string[];
  watch_next:     string[];
  position_note:  string | null;
  learning_note:  string | null;
  updated_at:     string;
}

const MODE_TONE: Record<BannerMode, {
  ring: string; soft: string; label: string;
  borderCls: string; bgCls: string; textCls: string;
}> = {
  risk_alert: {
    ring: "#f87171", soft: "rgba(248,113,113,0.18)", label: "RİSK UYARISI",
    borderCls: "border-red-600/50", bgCls: "bg-red-950/25", textCls: "text-red-300",
  },
  contradiction: {
    ring: "#fbbf24", soft: "rgba(251,191,36,0.18)", label: "ÇELİŞKİ",
    borderCls: "border-amber-600/50", bgCls: "bg-amber-950/25", textCls: "text-amber-300",
  },
  managing_position: {
    ring: "#34d399", soft: "rgba(52,211,153,0.18)", label: "POZİSYON",
    borderCls: "border-emerald-600/50", bgCls: "bg-emerald-950/25", textCls: "text-emerald-300",
  },
  learning: {
    ring: "#a78bfa", soft: "rgba(167,139,250,0.18)", label: "ÖĞRENME",
    borderCls: "border-violet-600/50", bgCls: "bg-violet-950/25", textCls: "text-violet-300",
  },
  waiting: {
    ring: "#22d3ee", soft: "rgba(34,211,238,0.16)", label: "BEKLİYOR",
    borderCls: "border-cyan-700/45", bgCls: "bg-slate-950/40", textCls: "text-cyan-300",
  },
};

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  report: RegimeReport;
  headlines?: NewsHeadline[];
  macro?: import("@/lib/types").MacroLayer;
  appetite?: import("@/lib/types").RiskAppetiteLayer;
  reportDecision?: Decision;
  ownerActions?: string[];
  flipConditions?: FlipCondition[];
  confirmationChecklist?: ConfirmationItem[];
  asymmetry?: AsymmetrySignal;
}

export default function AgentMainPanel({
  report, headlines = [], macro, appetite,
  reportDecision, ownerActions = [], flipConditions = [],
  confirmationChecklist = [], asymmetry,
}: Props) {
  const [banner,  setBanner]  = useState<AgentBanner | null>(null);
  const [open,    setOpen]    = useState(false);
  const [animate, setAnimate] = useState(false);

  // Son dakika haber → Agent Core yanında speech bubble + opsiyonel sesli okuma
  const voice = useAgentVoice();
  const newsKey = headlines[0]?.url || headlines[0]?.title || "";
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

  // Yeni bilgi sinyali → dolaşan orb ilgili panele uçar + "yeni sinyal" bubble
  const [orbSignal, setOrbSignal] = useState<{ n: number; target: string }>({ n: 0, target: "news-panel-shell" });
  const prevNewsRef   = useRef<string | null>(null);
  const prevBannerRef = useRef<string | null>(null);
  useEffect(() => {
    if (newsKey && prevNewsRef.current && newsKey !== prevNewsRef.current) {
      setOrbSignal(s => ({ n: s.n + 1, target: "news-panel-shell" }));
    }
    prevNewsRef.current = newsKey || prevNewsRef.current;
  }, [newsKey]);
  const bannerStamp = banner?.updated_at || "";
  useEffect(() => {
    if (bannerStamp && prevBannerRef.current && bannerStamp !== prevBannerRef.current) {
      setOrbSignal(s => ({ n: s.n + 1, target: "agent-main-panel" }));
    }
    prevBannerRef.current = bannerStamp || prevBannerRef.current;
  }, [bannerStamp]);

  // ── Paper signal chain bildirimi → orb'dan çıkan holografik balon ───────────
  // /trading/state'i 15sn'de bir yokla; signal_chain[] içinden YENİ ya da seviye
  // değiştiren chain'i bul, orb'u PaperTradingTicker'a uçur ve balonu aç.
  // İlk poll baseline'dır (sayfa açılışında 4 balon basmasın). Salt gözlem.
  const [chainNotif, setChainNotif] = useState<SignalChainNotification | null>(null);
  const seenChainRef     = useRef<Map<string, SignalChainLevel>>(new Map());
  const chainBaselineRef = useRef(false);
  const chainTimerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    let cancelled = false;
    async function loadChain() {
      try {
        const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const data = await res.json();
        const chains: SignalChainView[] = Array.isArray(data?.signal_chain) ? data.signal_chain : [];
        if (!chainBaselineRef.current) {
          for (const c of chains) seenChainRef.current.set(c.asset, c.signal_level);
          chainBaselineRef.current = true;
          return;
        }
        const fresh: SignalChainView[] = [];
        for (const c of chains) {
          if (seenChainRef.current.get(c.asset) !== c.signal_level) {
            fresh.push(c);
            seenChainRef.current.set(c.asset, c.signal_level);
          }
        }
        if (fresh.length === 0 || cancelled) return;
        fresh.sort((a, b) => CHAIN_LEVEL_RANK[b.signal_level] - CHAIN_LEVEL_RANK[a.signal_level]);
        const notif = fresh[0].last_notification;
        if (!notif || cancelled) return;
        setChainNotif(notif);
        setOrbSignal(s => ({ n: s.n + 1, target: "paper-trading-ticker" }));
        if (chainTimerRef.current) clearTimeout(chainTimerRef.current);
        chainTimerRef.current = setTimeout(() => setChainNotif(null), 11_000);
      } catch { /* sessiz */ }
    }
    loadChain();
    const id = setInterval(loadChain, 15_000);
    return () => {
      cancelled = true;
      clearInterval(id);
      if (chainTimerRef.current) clearTimeout(chainTimerRef.current);
    };
  }, []);

  // ESC ile chain balonunu kapat
  useEffect(() => {
    if (!chainNotif) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setChainNotif(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chainNotif]);

  async function cancelChain(asset: string) {
    try {
      await fetch(`/api/backend/trading/signal-chain/${asset}/cancel`, {
        method: "POST", cache: "no-store",
      });
    } catch { /* sessiz */ }
    setChainNotif(null);
  }
  function openChainDetail() {
    window.dispatchEvent(new CustomEvent("eyay:open-agent-modal"));
    setChainNotif(null);
  }

  // prefers-reduced-motion
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setAnimate(!mq.matches);
    const onMQ = () => setAnimate(!mq.matches);
    mq.addEventListener?.("change", onMQ);
    return () => mq.removeEventListener?.("change", onMQ);
  }, []);

  // Banner polling (30sn) — AgentInsightBar'dan devralındı
  useEffect(() => {
    let cancelled = false;
    async function loadBanner() {
      try {
        const res = await fetch("/api/backend/agent/banner", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: AgentBanner = await res.json();
        if (!cancelled) setBanner(data);
      } catch { /* banner null kalır → fallback brief */ }
    }
    loadBanner();
    const id = setInterval(loadBanner, 30_000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Dış event ile modal açma (diğer panellerdeki "Agent Detayı" butonları)
  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("eyay:open-agent-modal", onOpen);
    return () => window.removeEventListener("eyay:open-agent-modal", onOpen);
  }, []);

  // Modal açıkken: ESC + body scroll lock + global event
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

  const modal = open ? (
    <AgentCommandCenter
      onClose={() => setOpen(false)}
      headlines={headlines}
      macro={macro}
      appetite={appetite}
      reportDecision={reportDecision}
      ownerActions={ownerActions}
      flipConditions={flipConditions}
      confirmationChecklist={confirmationChecklist}
      asymmetry={asymmetry}
    />
  ) : null;

  // Orb'dan çıkan signal chain balonu — her iki render dalında da gösterilir
  // (banner olsun olmasın, reduced-motion/mobil dahil).
  const chainBubble = chainNotif ? (
    <SignalChainBubble
      notif={chainNotif}
      animate={animate}
      onCancel={cancelChain}
      onDetail={openChainDetail}
      onClose={() => setChainNotif(null)}
    />
  ) : null;

  // Banner yoksa klasik fallback: mevcut Agent Brief paneli
  if (!banner?.headline) {
    return (
      <>
        <AgentBriefPanel report={report} />
        {chainBubble}
        {modal}
      </>
    );
  }

  const t    = MODE_TONE[banner.mode] ?? MODE_TONE.waiting;
  const time = banner.updated_at
    ? new Date(banner.updated_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
    : "—";

  return (
    <>
      <style>{`
        @keyframes amp-flip   { 0%{transform:perspective(700px) rotateX(78deg);opacity:0} 100%{transform:none;opacity:1} }
        @keyframes amp-bubble { 0%{opacity:0;transform:translateY(8px) scale(.92)} 8%,88%{opacity:1;transform:none} 100%{opacity:0;transform:translateY(-6px)} }
        @keyframes amp-orb    { 0%,100%{filter:brightness(1)} 50%{filter:brightness(1.45)} }
        @keyframes amp-ping   { 0%{transform:scale(1);opacity:.8} 100%{transform:scale(2.6);opacity:0} }
        .amp-flip-kids > * { animation: amp-flip .55s ease both; }
        .amp-flip-kids > *:nth-child(2){animation-delay:.08s}
        .amp-flip-kids > *:nth-child(3){animation-delay:.16s}
      `}</style>
      <div
        data-testid="agent-main-panel"
        className={`relative w-full max-w-full min-w-0 overflow-hidden rounded-2xl border ${t.borderCls} ${t.bgCls}`}
        style={{ boxShadow: animate ? `0 0 18px ${t.soft}, inset 0 1px 0 ${t.ring}28` : `0 0 8px ${t.soft}` }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-cyan-500/20 bg-gradient-to-r from-black/40 via-cyan-950/15 to-black/40 gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span aria-hidden="true" className={t.textCls}>◈</span>
            <div className="min-w-0">
              <p className="text-[11px] font-mono font-black text-cyan-50 uppercase tracking-[0.24em] truncate">
                e-yAy <span className={t.textCls}>AGENT</span> · KOMUT MERKEZİ
              </p>
              <p className="text-[10px] font-mono text-cyan-400/65 truncate">
                Agent Layer · düşünen · yorumlayan · karar vermeyen
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`rounded-md border px-2 py-0.5 text-[10px] font-mono font-black uppercase tracking-widest ${t.borderCls}`}
                  style={{ color: t.ring, background: t.soft }}>
              {t.label}
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
                {voice.enabled ? "🔊" : "🔇"}
              </button>
            )}
            <span className="font-mono text-[10px] text-eyay-faint">{time}</span>
          </div>
        </div>

        {/* Body: Agent Core | ana görünüm | sinyal kolonları
            key=bannerStamp → banner güncellenince kolonlar flip ile döner */}
        <div key={bannerStamp || banner.headline}
             className={`grid grid-cols-1 sm:grid-cols-[180px_minmax(0,1fr)_240px] gap-3 p-3 ${animate ? "amp-flip-kids" : ""}`}>
          {/* Sol: Agent Core — modal'la birebir aynı görsel */}
          <div className="hidden sm:flex items-center justify-center min-w-0">
            <AgentCoreVisual ring={t.ring} soft={t.soft} animate={animate} size={180} />
          </div>

          {/* Orta: headline + ana görünüm */}
          <div className="flex flex-col gap-2 min-w-0 justify-center">
            <p className={`text-base font-semibold leading-snug ${t.textCls}`}>
              {banner.headline}
            </p>
            {banner.main_view && (
              <p className="text-[12px] font-mono text-slate-200/90 leading-snug line-clamp-4">
                {banner.main_view}
              </p>
            )}
            {banner.position_note && (
              <p className="text-[11px] font-mono text-emerald-300/85 leading-snug line-clamp-2">
                ▸ {banner.position_note}
              </p>
            )}
          </div>

          {/* Sağ: sinyal/izlem chip kolonları + Detay butonu */}
          <div className="flex flex-col gap-1.5 min-w-0">
            {banner.top_signals.length > 0 && (
              <ChipList label="Öne çıkan sinyaller" items={banner.top_signals} tone={t.ring} />
            )}
            {banner.contradictions.length > 0 && (
              <ChipList label="Çelişkiler" items={banner.contradictions} tone="#fbbf24" />
            )}
            {banner.watch_next.length > 0 && (
              <ChipList label="Sıradaki izlem" items={banner.watch_next} tone="#22d3ee" />
            )}
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="mt-auto w-full rounded-lg border border-cyan-500/45 bg-cyan-950/35 hover:bg-cyan-900/45 transition-colors px-3 py-2 text-[11px] font-mono font-bold text-cyan-100 uppercase tracking-wider focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              data-testid="agent-main-open-modal">
              ◇ Agent Detayı
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-3 py-1.5 border-t border-eyay-border/40 bg-black/30">
          <p className="text-[10px] font-mono text-eyay-faint/75 text-center leading-relaxed">
            PAPER_SAFE · NO_EXECUTION · tüm gerçek kararlar insana aittir
          </p>
        </div>

        {/* Son dakika speech bubble — Agent Core'un ağzından çıkıyormuş gibi */}
        {newsBubble && (
          <div className="pointer-events-none absolute z-20 left-3 top-14 sm:left-[150px] sm:top-12 max-w-[240px] min-w-0"
               style={animate ? { animation: "amp-bubble 10s ease both" } : undefined}>
            <div className="relative rounded-xl border border-red-400/60 bg-[#10060c]/90 backdrop-blur-sm px-2.5 py-2 shadow-[0_0_18px_rgba(248,113,113,0.25)]">
              <p className="text-[9px] font-mono font-black text-red-300 uppercase tracking-[0.2em] mb-0.5">
                🔴 Son Dakika
              </p>
              <p className="text-[10.5px] font-mono text-eyay-text leading-snug line-clamp-3">
                {newsBubble}
              </p>
              <span aria-hidden="true"
                    className="absolute top-1/2 -left-[6px] -translate-y-1/2 w-3 h-3 rotate-45 bg-[#10060c]/90 border-b border-l border-red-400/60" />
            </div>
          </div>
        )}
      </div>

      {/* Dolaşan holografik agent orb — panelden panele gezer (sadece UI) */}
      {!open && <RoamingAgentOrb ring={t.ring} animate={animate} signal={orbSignal} />}
      {!open && chainBubble}
      {modal}
    </>
  );
}

// ── Roaming holographic orb ──────────────────────────────────────────────────
// Dashboard panelleri arasında dolaşan küçük agent orb'u. Yeni sinyal gelince
// ilgili panele uçar, kısa pulse + "yeni sinyal" bubble gösterir.
// reduced-motion veya dar ekranda (<768px) hiç render edilmez.

const ORB_TARGETS = [
  "agent-main-panel",
  "command-signals-shell",
  "event-calendar-shell",
  "cap-rotation-shell",
  "scenario-panel-shell",
  "news-panel-shell",
] as const;

function RoamingAgentOrb({
  ring, animate, signal,
}: { ring: string; animate: boolean; signal: { n: number; target: string } }) {
  const [pos,     setPos]     = useState<{ x: number; y: number } | null>(null);
  const [bubble,  setBubble]  = useState(false);
  const [desktop, setDesktop] = useState(false);
  const idxRef = useRef(0);

  useEffect(() => {
    const check = () => setDesktop(window.innerWidth >= 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Hedef panelin sağ-üst köşesine konum (viewport sınırları içinde)
  const moveTo = (testid: string): boolean => {
    const el = document.querySelector(`[data-testid="${testid}"]`);
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.bottom < 0 || r.top > window.innerHeight) return false;
    const x = Math.max(20, Math.min(r.right - 16, window.innerWidth - 36));
    const y = Math.max(10, Math.min(r.top + 12, window.innerHeight - 60));
    setPos({ x, y });
    return true;
  };

  // Idle dolaşım — 9 sn'de bir görünür bir sonraki panele süzül
  useEffect(() => {
    if (!animate || !desktop) return;
    const hop = () => {
      for (let i = 0; i < ORB_TARGETS.length; i++) {
        idxRef.current = (idxRef.current + 1) % ORB_TARGETS.length;
        if (moveTo(ORB_TARGETS[idxRef.current])) return;
      }
    };
    hop();
    const t = setInterval(hop, 9_000);
    return () => clearInterval(t);
  }, [animate, desktop]);

  // Yeni sinyal → ilgili panele uç + pulse + bubble
  useEffect(() => {
    if (!animate || !desktop || signal.n === 0) return;
    moveTo(signal.target);
    setBubble(true);
    const t = setTimeout(() => setBubble(false), 4_500);
    return () => clearTimeout(t);
  }, [signal, animate, desktop]);

  if (!animate || !desktop || !pos) return null;

  return (
    <div aria-hidden="true"
         className="fixed left-0 top-0 z-40 pointer-events-none"
         style={{
           transform: `translate(${pos.x - 9}px, ${pos.y}px)`,
           transition: "transform 1.7s cubic-bezier(.45,.05,.25,1)",
         }}>
      <span className="relative block w-[18px] h-[18px] rounded-full"
            style={{
              background: `radial-gradient(circle at 35% 30%, #fff, ${ring} 45%, transparent 78%)`,
              boxShadow: `0 0 10px ${ring}, 0 0 24px ${ring}66`,
              animation: "amp-orb 2.2s ease-in-out infinite",
            }}>
        {bubble && (
          <span className="absolute inset-0 rounded-full"
                style={{ border: `1.5px solid ${ring}`, animation: "amp-ping 1.1s ease-out infinite" }} />
        )}
      </span>
      {bubble && (
        <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1.5 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[9px] font-mono font-bold"
              style={{ color: ring, borderColor: `${ring}66`, background: "rgba(2,8,18,0.92)" }}>
          ⚡ yeni sinyal
        </span>
      )}
    </div>
  );
}

// ── Chip list helper ─────────────────────────────────────────────────────────

function ChipList({ label, items, tone }: { label: string; items: string[]; tone: string }) {
  return (
    <div className="rounded-md border bg-black/40 px-2 py-1.5 min-w-0"
         style={{ borderColor: `${tone}44` }}>
      <p className="text-[10px] font-mono text-slate-400 uppercase tracking-widest leading-none mb-1">{label}</p>
      {items.slice(0, 3).map((it, i) => (
        <p key={i} className="text-[10px] font-mono leading-snug truncate" style={{ color: tone }}>
          › {it}
        </p>
      ))}
    </div>
  );
}

// ── Signal chain bildirim balonu (orb'dan çıkan holografik konuşma balonu) ────
// Kurumsal sci-fi; çizgi film değil. Seviye rengi + canlı countdown + aksiyonlar.
// PaperTradingTicker'ın hemen altına sabitlenir; orb da oraya uçtuğu için
// "orb'un içinden çıkıyormuş" hissi verir. Mobile'da genişlik clamp ile taşmaz.
function SignalChainBubble({
  notif, animate, onCancel, onDetail, onClose,
}: {
  notif: SignalChainNotification;
  animate: boolean;
  onCancel: (asset: string) => void;
  onDetail: () => void;
  onClose: () => void;
}) {
  const tone = CHAIN_TONES[notif.tone] ?? CHAIN_TONES.slate;
  const label = CHAIN_LEVEL_LABEL[notif.level] ?? notif.level;
  const isTriple = notif.level === "triple_timeframe_confirmation";
  const small = notif.level === "same_timeframe_duplicate" || notif.level === "timeframe_conflict";
  const canCancel = notif.level === "single_signal" || notif.level === "double_timeframe_signal";

  // Canlı countdown — yalnız single/double (countdown > 0).
  const [remaining, setRemaining] = useState(notif.countdown);
  useEffect(() => {
    setRemaining(notif.countdown);
    if (notif.countdown <= 0) return undefined;
    const started = Date.now();
    const id = setInterval(() => {
      const left = Math.max(0, notif.countdown - Math.floor((Date.now() - started) / 1000));
      setRemaining(left);
      if (left <= 0) clearInterval(id);
    }, 1000);
    return () => clearInterval(id);
  }, [notif.countdown, notif.at]);

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="signal-chain-bubble"
      className="fixed z-[130] top-[calc(4.75rem+env(safe-area-inset-top))] right-[calc(1rem+env(safe-area-inset-right))] w-80 max-w-[92vw]"
      style={animate ? { animation: "scn-emerge .42s cubic-bezier(.22,1,.36,1)" } : undefined}
    >
      <style>{`
        @keyframes scn-emerge { 0%{opacity:0;transform:translateY(-10px) scale(.82)} 100%{opacity:1;transform:none} }
        @keyframes scn-ring   { to { transform: rotate(360deg) } }
      `}</style>
      <div className={`relative rounded-2xl border ${tone.border} ${tone.bg} backdrop-blur-md px-3 ${small ? "py-2" : "py-2.5"}`}
           style={{ boxShadow: `0 0 22px ${tone.ring}33, 0 8px 30px rgba(0,0,0,.55)` }}>
        {/* Orb'a işaret eden ışıltı kuyruğu (sağ üst köşe) */}
        <span aria-hidden="true"
              className={`absolute -top-1.5 right-6 w-3 h-3 rotate-45 border-t border-l ${tone.border} ${tone.bg}`} />
        {/* Üst satır: mini orb + seviye + asset/side + countdown + kapat */}
        <div className="flex items-center gap-2 mb-1.5">
          <span aria-hidden="true" className="relative flex h-5 w-5 items-center justify-center shrink-0">
            <span className="absolute inset-0 rounded-full"
                  style={{ background: `radial-gradient(circle at 35% 30%, #fff, ${tone.ring} 50%, transparent 78%)`,
                           boxShadow: `0 0 8px ${tone.ring}` }} />
            {animate && (
              <span className="absolute -inset-1 rounded-full border"
                    style={{ borderColor: `${tone.ring}66`, animation: "scn-ring 3.2s linear infinite" }} />
            )}
          </span>
          <span className={`text-[10px] font-mono font-black uppercase tracking-[0.16em] ${tone.text}`}>{label}</span>
          <span className="text-[10px] font-mono font-bold text-eyay-text/90 truncate">{notif.asset} {notif.side}</span>
          {remaining > 0 && (
            <span className="ml-auto text-[12px] font-mono font-black tabular-nums" style={{ color: tone.ring }}>
              {remaining}s
            </span>
          )}
          <button type="button" onClick={onClose} aria-label="Kapat"
                  className={`${remaining > 0 ? "ml-1.5" : "ml-auto"} text-eyay-faint hover:text-eyay-text text-[11px] leading-none shrink-0`}>
            ✕
          </button>
        </div>
        {/* TF chipleri */}
        {notif.timeframes.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1.5">
            {notif.timeframes.map(tf => (
              <span key={tf} className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${tone.chip}`}>{tf}</span>
            ))}
          </div>
        )}
        {/* Metin — agent konuşuyormuş gibi */}
        <p className={`text-[11px] font-mono leading-snug ${tone.text} ${small ? "line-clamp-2" : "line-clamp-3"}`}>
          {notif.text}
        </p>
        {/* Aksiyonlar */}
        <div className="flex items-center gap-1.5 mt-2">
          {canCancel && (
            <button type="button" onClick={() => onCancel(notif.asset)}
                    data-testid="signal-chain-cancel"
                    className="flex-1 rounded-lg border border-red-600/60 bg-red-950/40 px-2 py-1 text-[10px] font-mono font-bold text-red-200 uppercase tracking-wider hover:bg-red-900/50 transition-colors">
              İptal Et
            </button>
          )}
          <button type="button" onClick={onDetail}
                  className={`${canCancel ? "flex-1" : "w-full"} rounded-lg border ${tone.border} ${tone.bg} px-2 py-1 text-[10px] font-mono font-bold ${tone.text} uppercase tracking-wider hover:brightness-125 transition`}>
            Detay
          </button>
        </div>
        {isTriple && (
          <p className="mt-1.5 text-[9px] font-mono text-emerald-300/80 leading-snug">
            ⚡ Üçlü teyit — paper trade mevcut akışta otomatik açıldı.
          </p>
        )}
      </div>
    </div>
  );
}
