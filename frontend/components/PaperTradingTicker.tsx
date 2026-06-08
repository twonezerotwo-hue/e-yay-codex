"use client";

import { useEffect, useRef, useState } from "react";

interface TradeEvent {
  type: "OPEN" | "CLOSE";
  pair: string;
  side: "LONG" | "SHORT";
  price?: number;
  size_usd?: number;
  pnl_usd?: number;
  pnl_pct?: number;
}

interface RiskPlan {
  timeframe?: string;
  atr_period_bars?: number;
  atr_value?: number | null;
  sl_basis?: string;
  tp_basis?: string;
  risk_reward?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  expected_horizon_hours?: { low?: number; high?: number };
  explanation?: string;
}

interface Position {
  pair: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  current_price: number;
  pnl_usd: number;
  pnl_pct: number;
  stop_loss: number;
  take_profit: number;
  size_usd?: number;
  risk_plan?: RiskPlan;
  // Backend Position dataclass'taki opened_by alanı:
  //   "PAPER"  → otomatik pending → 60sn'lik onay penceresi sonunda açıldı
  //   "MANUAL" → 'Açılmaya Hazır' kuyruğundan kullanıcı elle açtı
  opened_by?: "PAPER" | "MANUAL";
}

interface ChartPatternSummary {
  bias: "BULLISH" | "BEARISH" | "NEUTRAL";
  consolidated_score: number;
  active_patterns: string[];
}

interface PendingOrder {
  pair: string;
  side: "LONG" | "SHORT";
  requested_at: string;
  execute_at: string;
  requested_price: number;
  size_usd: number;
  seconds_remaining: number;
  market_open: boolean;
  primary_tf?: string;
  is_recurring?: boolean;       // yinelenen sinyal (farklı TF/side ile tekrar gelen)
}

interface ManualReadyTrade {
  pair: string;
  side: "LONG" | "SHORT";
  requested_at: string;
  rejected_at: string;
  last_signal: string;
  size_usd: number;
  requested_price: number;             // her tick refresh edilen taze fiyat
  original_requested_price?: number;   // reddedildiği anki donmuş fiyat
  current_price?: number;              // last_tick_prices'tan
  last_refreshed_at?: string;
  market_open?: boolean;
  primary_tf?: string;
  fingerprint?: string;
}

interface TradingState {
  starting_balance: number;
  equity: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  daily_pnl_usd: number;
  open_positions: Position[];
  pending_orders: PendingOrder[];
  manual_ready_trades?: ManualReadyTrade[];
  trade_count: number;
  last_event: TradeEvent | null;
  last_event_at: string | null;
}

interface AlertEvent {
  id: number;
  uid: string;
  type: string;
  level: "CRITICAL" | "ACTION_REQUIRED" | "TRADE_EVENT" | "WARNING" | "INFO";
  title: string;
  message: string;
  created_at: string;
  mode: string;
  pair?: string;
  side?: string;
  size_usd?: number;
  price?: number;
  reason?: string;
  metadata: Record<string, unknown>;
  voice: boolean;
}

// Türkçe sesli uyarı metinleri
function alertVoiceText(alert: AlertEvent): string {
  const pair = alert.pair ?? "";
  const side = alert.side === "LONG" ? "alış" : alert.side === "SHORT" ? "satış" : "";
  switch (alert.type) {
    case "pending_trade_created":      return `Bekleyen işlem: ${side} ${pair}`;
    case "paper_trade_opened":         return `${pair} ${side} pozisyon açıldı`;
    case "paper_trade_closed":         return `${pair} pozisyon kapatıldı`;
    case "market_closed_trade_blocked":return `${pair} piyasa kapalı, işlem engellendi`;
    case "daily_loss_limit_warning":   return "Günlük zarar limitine ulaşıldı";
    case "agent_self_validation_failed":return "Agent doğrulama hatası";
    case "paper_live_boundary_violation":return "Kritik: paper sınırı ihlali";
    default:                           return alert.title;
  }
}

const POLL_MS = 15_000;

// Sesli uyarı aç/kapa tercihi — localStorage'da kalıcı
const VOICE_STORAGE_KEY = "eyay:voice-alerts-enabled";

// USD biçimleyici — module scope (PaperTradingTicker + OpenPositionCard ortak kullanır)
const fmtUsd = (value: number): string =>
  `${value >= 0 ? "+" : ""}$${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

export default function PaperTradingTicker() {
  const [state,     setState]    = useState<TradingState | null>(null);
  const [expanded,  setExpanded] = useState(false);
  const [banner,    setBanner]   = useState<TradeEvent | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [closing,   setClosing]  = useState<string | null>(null);
  const [patterns,  setPatterns] = useState<Record<string, ChartPatternSummary>>({});
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const voiceEnabledRef = useRef(true);
  const [nowMs,     setNowMs]    = useState(Date.now());
  const lastEventAtRef  = useRef<string | null>(null);
  const lastAlertIdRef  = useRef<number>(0);   // sesli uyarı dedup

  // Panel (Açık Pozisyonlar) açıkken arkadaki dashboard'un body-scroll'unu
  // kilitle — kullanıcı panel içinde scroll yaparken arka plan kaymasın.
  // Panel kapanınca/unmount olunca önceki overflow değeri geri yüklenir.
  useEffect(() => {
    if (!expanded) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [expanded]);

  const loadState = async () => {
    const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
    if (!res.ok) {
      return;
    }
    const nextState: TradingState = await res.json();
    setState(nextState);

    if (nextState.last_event_at && nextState.last_event_at !== lastEventAtRef.current) {
      lastEventAtRef.current = nextState.last_event_at;
      if (nextState.last_event) {
        setBanner(nextState.last_event);
        setTimeout(() => setBanner(null), 5000);
      }
    }
  };

  useEffect(() => {
    const onAgent = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      setAgentOpen(!!detail?.open);
    };
    window.addEventListener("eyay:agent-modal", onAgent as EventListener);
    return () => window.removeEventListener("eyay:agent-modal", onAgent as EventListener);
  }, []);

  // Sesli uyarı tercihini localStorage'dan oku (ilk render)
  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(VOICE_STORAGE_KEY) : null;
    if (saved !== null) {
      const enabled = saved === "1";
      setVoiceEnabled(enabled);
      voiceEnabledRef.current = enabled;
    }
  }, []);

  function toggleVoiceEnabled() {
    setVoiceEnabled((prev) => {
      const next = !prev;
      voiceEnabledRef.current = next;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(VOICE_STORAGE_KEY, next ? "1" : "0");
      }
      if (!next && typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      return next;
    });
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        await loadState();
      } catch {
        if (cancelled) {
          return;
        }
      }
    }

    async function loadPatterns() {
      try {
        const res = await fetch("/api/backend/chart-patterns", { cache: "no-store" });
        if (!res.ok) return;
        const d = await res.json();
        if (cancelled || !d.pairs) return;
        setPatterns(d.pairs);
      } catch { /* sessiz */ }
    }

    async function loadAlerts() {
      try {
        const res = await fetch("/api/backend/alerts/recent?limit=20", { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const d: { alerts: AlertEvent[] } = await res.json();
        const newAlerts = (d.alerts ?? []).filter(a => a.id > lastAlertIdRef.current);
        if (newAlerts.length === 0) return;
        // En yeninin ID'sini kaydet
        lastAlertIdRef.current = Math.max(...newAlerts.map(a => a.id));
        // Sesli uyarıları sıraya al (önce kritik) — kullanıcı kapattıysa atla
        if (voiceEnabledRef.current) {
          const voiceAlerts = newAlerts
            .filter(a => a.voice)
            .sort((a, b) => a.id - b.id);
          for (const alert of voiceAlerts) {
            speakAlert(alert);
          }
        }
      } catch { /* sessiz */ }
    }

    // İlk yükleme: alert ID'yi sessizce initialize et (eski alert'leri sesletme)
    async function initAlertBaseline() {
      try {
        const res = await fetch("/api/backend/alerts/recent?limit=1", { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const d: { alerts: AlertEvent[] } = await res.json();
        if (d.alerts?.length > 0) {
          lastAlertIdRef.current = d.alerts[0].id;
        }
      } catch { /* sessiz */ }
    }

    load(); loadPatterns(); initAlertBaseline();
    const i = setInterval(load, POLL_MS);
    const p = setInterval(loadPatterns, 60_000);
    const a = setInterval(loadAlerts, POLL_MS);
    return () => { cancelled = true; clearInterval(i); clearInterval(p); clearInterval(a); };
  }, []);

  useEffect(() => {
    const intervalId = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(intervalId);
  }, []);

  function speakAlert(alert: AlertEvent) {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const text = alertVoiceText(alert);
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = "tr-TR";
    utt.rate = 1.05;
    utt.volume = 1;
    // CRITICAL/ACTION_REQUIRED daha yavaş ve net
    if (alert.level === "CRITICAL" || alert.level === "ACTION_REQUIRED") {
      utt.rate = 0.9;
    }
    window.speechSynthesis.speak(utt);
  }

  async function handleManualClose(pair: string) {
    setClosing(pair);
    try {
      await fetch(`/api/backend/trading/close/${pair}`, { method: "POST", cache: "no-store" });
      const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
      if (res.ok) setState(await res.json());
    } catch { /* sessiz */ } finally {
      setClosing(null);
    }
  }

  if (!state) {
    return null;
  }

  const pendingOrders = state.pending_orders ?? [];
  const manualReadyTrades = state.manual_ready_trades ?? [];
  const showWidget = !agentOpen;
  const equityPct = ((state.equity - state.starting_balance) / state.starting_balance) * 100;
  const dailyColor = state.daily_pnl_usd >= 0 ? "text-emerald-300" : "text-red-300";
  const equityColor = equityPct >= 0 ? "text-emerald-400" : "text-red-400";

  const rejectPendingOrder = async (pair: string) => {
    try {
      await fetch(`/api/backend/trading/pending/${pair}/reject`, {
        method: "POST",
        cache: "no-store",
      });
      await loadState();
    } catch {
      // no-op
    }
  };

  const openManualReady = async (pair: string) => {
    try {
      await fetch(`/api/backend/trading/manual-ready/${pair}/open`, {
        method: "POST",
        cache: "no-store",
      });
      await loadState();
    } catch {
      // no-op
    }
  };

  const dismissManualReady = async (pair: string) => {
    try {
      await fetch(`/api/backend/trading/manual-ready/${pair}/dismiss`, {
        method: "POST",
        cache: "no-store",
      });
      await loadState();
    } catch {
      // no-op
    }
  };

  return (
    <>
      {pendingOrders.map((order) => (
        <PendingTradeBanner
          key={`${order.pair}-${order.execute_at}`}
          nowMs={nowMs}
          order={order}
          onReject={() => rejectPendingOrder(order.pair)}
        />
      ))}

      {banner && <TradeBanner event={banner} />}

      {showWidget && (
        <div className="fixed top-4 right-4 z-40 flex flex-col items-end gap-1">
          {/* Sesli uyarı toggle'ı artık panelin altında (footer) — bkz. aşağıdaki
              "expanded" bloğu içindeki sticky footer. Burada panel kapalıyken
              kullanıcı toggle'a erişemez; bu kasıtlı — toggle paneli açtığında görünür. */}
          <button
            onClick={() => setExpanded((value) => !value)}
            className="bg-eyay-surface border border-eyay-border rounded-xl shadow-card px-3 py-2 hover:border-eyay-blue/40 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Equity</p>
                <p className={`font-mono font-black text-sm leading-tight ${equityColor}`}>
                  ${state.equity.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </p>
              </div>

              <div className="w-px h-8 bg-eyay-border" />

              <div className="text-right">
                <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Gunluk</p>
                <p className={`font-mono font-bold text-sm leading-tight ${dailyColor}`}>
                  {fmtUsd(state.daily_pnl_usd)}
                </p>
              </div>

              {state.open_positions.length > 0 && (
                <>
                  <div className="w-px h-8 bg-eyay-border" />
                  <div className="text-right">
                    <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Acik</p>
                    <p className="font-mono font-bold text-sm leading-tight text-eyay-blue">
                      {state.open_positions.length}
                    </p>
                  </div>
                </>
              )}

              {pendingOrders.length > 0 && (
                <>
                  <div className="w-px h-8 bg-eyay-border" />
                  <div className="text-right">
                    <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Bekleyen</p>
                    <p className="font-mono font-bold text-sm leading-tight text-amber-300">
                      {pendingOrders.length}
                    </p>
                  </div>
                </>
              )}

              {manualReadyTrades.length > 0 && (
                <>
                  <div className="w-px h-8 bg-eyay-border" />
                  <div className="text-right">
                    <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Hazır</p>
                    <p className="font-mono font-bold text-sm leading-tight text-violet-300">
                      {manualReadyTrades.length}
                    </p>
                  </div>
                </>
              )}

              <span className={`text-eyay-faint text-xs transition-transform ${expanded ? "rotate-180" : ""}`}>
                ▾
              </span>
            </div>
          </button>

          {expanded && (
            <div
              className="bg-eyay-surface border border-eyay-border rounded-xl shadow-card w-[340px] sm:w-[520px] flex flex-col overflow-hidden"
              style={{ maxHeight: "calc(100vh - 80px)" }}
            >
              {/* Scroll edilebilir içerik alanı — açık pozisyon sayısı arttıkça
                  panel viewport dışına taşmasın diye burada overflow-y-auto var.
                  overscroll-contain: panel içeriği üst/alt sınıra ulaştığında
                  scroll arkadaki dashboard'a "zincirlenmesin" (scroll chaining). */}
              <div className="overflow-y-auto overscroll-contain p-3 space-y-2">
              <div className="grid grid-cols-3 gap-2 text-center pb-2 border-b border-eyay-border/40">
                <div>
                  <p className="text-[8px] font-mono text-eyay-faint">REALIZED</p>
                  <p className={`text-xs font-mono font-bold ${state.realized_pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {fmtUsd(state.realized_pnl_usd)}
                  </p>
                </div>
                <div>
                  <p className="text-[8px] font-mono text-eyay-faint">UNREALIZED</p>
                  <p className={`text-xs font-mono font-bold ${state.unrealized_pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {fmtUsd(state.unrealized_pnl_usd)}
                  </p>
                </div>
                <div>
                  <p className="text-[8px] font-mono text-eyay-faint">TRADES</p>
                  <p className="text-xs font-mono font-bold text-eyay-text">{state.trade_count}</p>
                </div>
              </div>

              {state.open_positions.length > 0 ? (
                <div>
                  <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1.5">
                    Acik Pozisyonlar
                  </p>
                  <div className="space-y-2">
                    {state.open_positions.map(p => (
                      <OpenPositionCard
                        key={p.pair}
                        position={p}
                        pattern={patterns[p.pair]}
                        isClosing={closing === p.pair}
                        onClose={() => handleManualClose(p.pair)}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-[10px] font-mono text-eyay-faint italic py-1.5 text-center">
                  Acik pozisyon yok
                </p>
              )}

              {pendingOrders.length > 0 && (
                <div className="pt-2 border-t border-eyay-border/40 space-y-1.5">
                  <p className="text-[9px] font-mono text-amber-300 uppercase tracking-wider">
                    Bekleyen Agent Islemleri ({pendingOrders.length})
                  </p>
                  {pendingOrders.map((order) => {
                    const secondsLeft = Math.max(
                      0,
                      Math.ceil((new Date(order.execute_at).getTime() - nowMs) / 1000),
                    );
                    const recurring = !!order.is_recurring;
                    return (
                      <div key={order.pair}
                           className={`flex items-center justify-between text-[10px] font-mono rounded px-2 py-1 border ${
                             recurring
                               ? "bg-fuchsia-950/30 border-fuchsia-700/50"
                               : "bg-amber-950/20 border-amber-900/40"
                           }`}>
                        <div className="min-w-0">
                          <p className={`font-bold ${recurring ? "text-fuchsia-300" : "text-amber-300"}`}>
                            {recurring && (
                              <span className="px-1 py-0.5 rounded text-[8px] mr-1.5 bg-fuchsia-500/20 border border-fuchsia-700/40">
                                YİNELENEN
                              </span>
                            )}
                            {order.side} {order.pair}
                            {order.primary_tf && (
                              <span className="text-eyay-faint ml-1 text-[9px]">· TF {order.primary_tf}</span>
                            )}
                          </p>
                          <p className="text-eyay-faint">
                            {secondsLeft}s sonra otomatik açılacak
                          </p>
                        </div>
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            void rejectPendingOrder(order.pair);
                          }}
                          className="px-2 py-1 rounded border border-red-700/60 text-red-300 hover:bg-red-950/30 shrink-0"
                        >
                          Reddet
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {manualReadyTrades.length > 0 && (
                <div className="pt-2 border-t border-eyay-border/40 space-y-1.5">
                  <p className="text-[9px] font-mono text-violet-300 uppercase tracking-wider">
                    Açılmaya Hazır İşlemler ({manualReadyTrades.length})
                  </p>
                  {manualReadyTrades.map((mr) => {
                    // Taze fiyat = current_price (last tick) > requested_price (silent-block refresh) > original
                    const livePrice = mr.current_price ?? mr.requested_price;
                    const orig      = mr.original_requested_price ?? mr.requested_price;
                    // Delta orijinal fiyata göre — kullanıcının reddettiği seviyeyle
                    // şimdiki seviye farkı; LONG için negatif delta = daha iyi giriş.
                    const delta     = livePrice - orig;
                    const deltaPct  = orig > 0 ? (delta / orig) * 100 : 0;
                    const better    = (mr.side === "LONG" && delta < 0) || (mr.side === "SHORT" && delta > 0);
                    const deltaCls  = better
                      ? "text-emerald-400"
                      : (Math.abs(deltaPct) < 0.05 ? "text-eyay-faint" : "text-amber-300");
                    const sign      = delta >= 0 ? "+" : "−";
                    return (
                      <div
                        key={`mr-${mr.pair}-${mr.rejected_at}`}
                        className="flex items-center justify-between text-[10px] font-mono bg-violet-950/20 border border-violet-900/40 rounded px-2 py-1 gap-2"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-violet-300 flex items-baseline gap-1.5 flex-wrap">
                            <span>{mr.side} {mr.pair}</span>
                            {mr.primary_tf && (
                              <span className="text-eyay-faint text-[9px] font-normal">TF {mr.primary_tf}</span>
                            )}
                            <span className="text-eyay-dim text-[9px] font-normal">· {mr.last_signal}</span>
                          </p>
                          <p className="flex items-baseline gap-1.5 mt-0.5">
                            <span className="text-eyay-faint text-[9px]">şu an</span>
                            <span className="text-violet-200 font-bold text-[11px]">
                              ${livePrice.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                            </span>
                            {Math.abs(deltaPct) >= 0.01 && (
                              <span className={`text-[9px] ${deltaCls}`}>
                                {sign}${Math.abs(delta).toLocaleString("en-US", { maximumFractionDigits: 2 })} ({sign}{Math.abs(deltaPct).toFixed(2)}%)
                              </span>
                            )}
                            <span className="text-eyay-faint/70 text-[9px]" title={`Referans fiyat (kuyruğa girdiği an): $${orig.toLocaleString("en-US", { maximumFractionDigits: 2 })}`}>
                              vs ${orig.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                            </span>
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              void openManualReady(mr.pair);
                            }}
                            className="px-2 py-1 rounded border border-emerald-700/60 text-emerald-300 hover:bg-emerald-950/30 disabled:opacity-40 disabled:cursor-not-allowed"
                            title={mr.market_open === false
                              ? "Piyasa kapalı"
                              : `Anlık fiyat $${livePrice.toLocaleString("en-US", { maximumFractionDigits: 2 })} ile aç`}
                            disabled={mr.market_open === false}
                          >
                            Aç @ ${livePrice.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                          </button>
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              void dismissManualReady(mr.pair);
                            }}
                            className="px-2 py-1 rounded border border-eyay-border text-eyay-dim hover:bg-eyay-raised/40"
                            title="Listeden çıkar"
                          >
                            Sil
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              <p className="text-[8px] font-mono text-eyay-faint/50 pt-1 border-t border-eyay-border/40">
                Agent sinyalleri · 4 parite (BTC/XAU/XAG/BRENT) · PAPER_SAFE
              </p>
              </div>

              {/* Footer — Sesli Uyarı toggle'ı. Panelin en altında, içerik
                  scroll edilse bile sticky ile her zaman görünür kalır;
                  açık pozisyon kartlarının üstüne binmemesi için kendi
                  satırında, ayrı arka planlı bir şerit olarak ayrıldı. */}
              <div className="shrink-0 sticky bottom-0 border-t border-eyay-border/60 bg-eyay-surface px-3 py-2">
                <button
                  onClick={toggleVoiceEnabled}
                  title={voiceEnabled ? "Sesli uyarılar açık — kapatmak için tıkla" : "Sesli uyarılar kapalı — açmak için tıkla"}
                  className={`w-full flex items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[9px] font-mono font-bold uppercase tracking-wider transition-colors ${
                    voiceEnabled
                      ? "border-emerald-800/60 bg-emerald-950/30 text-emerald-300 hover:border-emerald-600/60"
                      : "border-eyay-border bg-eyay-raised text-eyay-faint hover:border-eyay-muted"
                  }`}
                >
                  <span>{voiceEnabled ? "🔊" : "🔇"}</span>
                  <span>Sesli Uyarı {voiceEnabled ? "Açık" : "Kapalı"}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// OPEN POSITION CARD
// Açık pozisyon kartı — 4 bölüm:
//   A) Header  : asset, side, status badge (MANUEL/PAPER), PnL badge, Kapat
//   B) Pozisyon Özeti : entry, current PnL, position size, timeframe, beklenen tutuş
//   C) Risk Planı    : SL, TP, RR, ATR, stop mantığı
//   D) Pattern       : bias, score, aktif pattern'lar, kısa açıklama
// + karar cümlesi (en altta italic)
// Mobil: tek kolon. Desktop (sm+): B & C yan yana 2-col grid.
// ─────────────────────────────────────────────────────────────────────────────

function OpenPositionCard({
  position: p,
  pattern,
  isClosing,
  onClose,
}: {
  position: Position;
  pattern?: ChartPatternSummary;
  isClosing: boolean;
  onClose: () => void;
}) {
  const fmt2 = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  const fmt0 = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  const pctFromEntry = (level: number) =>
    p.entry_price > 0 ? ((level - p.entry_price) / p.entry_price * 100) : 0;

  const sideTextClr = p.side === "LONG" ? "text-emerald-400" : "text-red-400";
  const sideBadgeClr = p.side === "LONG"
    ? "bg-emerald-950/50 text-emerald-300 border-emerald-800/50"
    : "bg-red-950/50 text-red-300 border-red-800/50";

  // PnL state: pozitif / negatif / nötr (~0)
  const pnlState: "POS" | "NEG" | "NEUTRAL" =
    p.pnl_usd > 0.5 ? "POS" : p.pnl_usd < -0.5 ? "NEG" : "NEUTRAL";
  const pnlBadgeClr =
    pnlState === "POS" ? "bg-emerald-950/40 text-emerald-300 border-emerald-800/50" :
    pnlState === "NEG" ? "bg-red-950/40 text-red-300 border-red-800/50" :
    "bg-eyay-raised/60 text-eyay-faint border-eyay-border/50";
  const pnlPctClr =
    pnlState === "POS" ? "text-emerald-300" :
    pnlState === "NEG" ? "text-red-300" :
    "text-eyay-faint";

  // MANUEL / PAPER ENGINE badge
  const isManual = p.opened_by === "MANUAL";
  const sourceBadgeClr = isManual
    ? "bg-violet-950/60 text-violet-300 border-violet-800/50"
    : "bg-sky-950/60 text-sky-300 border-sky-800/50";
  const sourceTooltip = isManual
    ? "Bu pozisyon kullanıcı onayıyla açıldı; paper engine yalnızca risk yönetimini takip ediyor."
    : "Bu pozisyon paper trading sinyaliyle açıldı.";

  // Risk Plan değerleri
  const slPct = p.stop_loss > 0 ? pctFromEntry(p.stop_loss) : null;
  const tpPct = p.take_profit > 0 ? pctFromEntry(p.take_profit) : null;
  const rr = p.risk_plan?.risk_reward ?? null;
  // RR rengi: ≥1.5 yeşil (iyi), 1.0-1.5 sarı, <1.0 kırmızı
  const rrColor =
    rr == null ? "text-eyay-faint" :
    rr >= 1.5 ? "text-emerald-300" :
    rr >= 1.0 ? "text-amber-300" :
    "text-red-300";
  const atrVal = p.risk_plan?.atr_value;
  const atrBars = p.risk_plan?.atr_period_bars;
  const atrText = atrVal != null
    ? `${atrBars ? `(${atrBars}) ` : ""}${typeof atrVal === "number" ? atrVal.toFixed(4) : atrVal}`
    : "—";
  const tf = p.risk_plan?.timeframe || "—";
  const horizon = p.risk_plan?.expected_horizon_hours;
  const horizonText = horizon?.low != null
    ? `${horizon.low}–${horizon.high} saat`
    : "—";
  const slBasis = p.risk_plan?.sl_basis;

  // Pattern bias rengi (consensus skor 0-100 değil, pattern skor -100..+100 — açıklama tooltipte)
  const biasColor =
    pattern?.bias === "BULLISH" ? "text-emerald-300" :
    pattern?.bias === "BEARISH" ? "text-red-300" :
    "text-eyay-faint";
  const hasPattern = !!pattern;
  const activeP = pattern?.active_patterns ?? [];

  // Karar cümlesi — dinamik
  const intensity =
    Math.abs(p.pnl_pct) < 0.5 ? "hafif " :
    Math.abs(p.pnl_pct) > 2 ? "ciddi " : "";
  const pnlWord =
    pnlState === "POS" ? "kârda" :
    pnlState === "NEG" ? "zararda" :
    "başabaş seviyesinde";
  const slStr = slPct != null ? `${slPct.toFixed(1)}%` : "—";
  const tpStr = tpPct != null ? `+${tpPct.toFixed(1)}%` : "—";
  const patternHint = !hasPattern
    ? ""
    : pattern.bias === "NEUTRAL"
      ? " Pattern nötr olduğu için sistem pozisyonu teknik pattern yerine SL/TP planıyla yönetiyor."
      : pattern.bias === "BULLISH"
        ? " Pattern hâlâ bullish; SL/TP planı geçerli."
        : " Pattern bearish; SL/TP planı geçerli.";
  const decisionSentence =
    `Bu pozisyon şu an ${intensity}${pnlWord}. Stop mesafesi ${slStr}, hedef ${tpStr}.${patternHint}`;

  return (
    <article className="bg-eyay-raised/40 rounded-lg border border-eyay-border/50 overflow-hidden font-mono">
      {/* ────────────── A) HEADER ────────────── */}
      <header className="flex items-start justify-between gap-2 px-2.5 py-2 bg-eyay-surface/40 border-b border-eyay-border/40">
        <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
          <span className={`text-sm font-black ${sideTextClr}`}>
            {p.side === "LONG" ? "▲" : "▼"} {p.pair}
          </span>
          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider border ${sideBadgeClr}`}>
            {p.side}
          </span>
          <span
            className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider border ${sourceBadgeClr}`}
            title={sourceTooltip}
          >
            {isManual ? "MANUEL AÇILDI" : "PAPER ENGINE"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <div
            className={`text-right px-1.5 py-0.5 rounded border ${pnlBadgeClr}`}
            title="Açılış fiyatından bu yana gerçekleşmemiş kâr/zarar."
          >
            <span className="block text-[10px] font-bold leading-none">{fmtUsd(p.pnl_usd)}</span>
            <span className="block text-[8px] leading-none opacity-90">
              {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct.toFixed(2)}%
            </span>
          </div>
          <button
            onClick={onClose}
            disabled={isClosing}
            title="Pozisyonu anlık fiyattan elle kapat"
            className="text-[8px] font-bold border border-red-800/40 text-red-300/80 hover:text-red-100 hover:bg-red-900/40 hover:border-red-600/60 px-1.5 py-1 rounded transition-colors disabled:opacity-40 leading-tight whitespace-nowrap"
          >
            {isClosing ? "···" : (
              <span className="flex flex-col items-center gap-0.5">
                <span>Manuel</span>
                <span>Kapat</span>
              </span>
            )}
          </button>
        </div>
      </header>

      {/* ────────────── B + C : 2-col on desktop, 1-col on mobile ────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 p-2">
        {/* B) Pozisyon Özeti */}
        <section className="bg-eyay-surface/30 rounded p-2 border border-eyay-border/30">
          <h4 className="text-[8px] uppercase tracking-wider text-eyay-faint mb-1.5">
            Pozisyon Özeti
          </h4>
          <dl className="space-y-0.5 text-[10px]">
            <CardRow label="Entry" value={fmt2(p.entry_price)} valueClass="text-eyay-text" />
            <CardRow
              label="Current PnL"
              value={`${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(2)}%`}
              valueClass={pnlPctClr + " font-bold"}
            />
            <CardRow
              label="Boyut"
              value={p.size_usd != null ? `$${fmt0(p.size_usd)}` : "—"}
              valueClass="text-eyay-text"
            />
            <CardRow
              label="TF"
              labelTip="Sinyalin üretildiği ana zaman dilimi."
              value={tf}
              valueClass="text-eyay-text"
            />
            <CardRow label="Beklenen tutuş" value={horizonText} valueClass="text-eyay-text" />
          </dl>
        </section>

        {/* C) Risk Planı */}
        <section className="bg-eyay-surface/30 rounded p-2 border border-eyay-border/30">
          <h4 className="text-[8px] uppercase tracking-wider text-eyay-faint mb-1.5">
            Risk Planı
          </h4>
          <dl className="space-y-0.5 text-[10px]">
            <CardRow
              label="Stop Loss"
              labelTip="Fiyat buraya gelirse zarar sınırlamak için kapanır."
              value={p.stop_loss > 0 ? `${fmt2(p.stop_loss)} (${slPct!.toFixed(1)}%)` : "—"}
              valueClass="text-red-300"
            />
            <CardRow
              label="Take Profit"
              labelTip="Fiyat buraya gelirse hedef kâr alınır."
              value={p.take_profit > 0 ? `${fmt2(p.take_profit)} (+${tpPct!.toFixed(1)}%)` : "—"}
              valueClass="text-emerald-300"
            />
            <CardRow
              label="R / R"
              labelTip="Alınan riske karşı beklenen ödül oranı."
              value={rr != null ? `1 : ${rr}` : "—"}
              valueClass={rrColor + " font-bold"}
            />
            <CardRow
              label="ATR"
              labelTip="Ortalama fiyat oynaklığı; stop/target mesafesini ayarlamak için kullanılır."
              value={atrText}
              valueClass="text-sky-300/80"
            />
            {slBasis && (
              <CardRow label="Stop mantığı" value={slBasis} valueClass="text-eyay-faint text-[9px]" />
            )}
          </dl>
        </section>
      </div>

      {/* ────────────── D) Pattern / Teknik Okuma ────────────── */}
      {hasPattern && (
        <section className="mx-2 mb-2 bg-eyay-surface/20 rounded p-2 border border-eyay-border/30">
          <div className="flex items-center justify-between gap-2 mb-1">
            <h4
              className="text-[8px] uppercase tracking-wider text-eyay-faint"
              title="Mum formasyonu / teknik yapı yorumu."
            >
              📊 Pattern / Teknik Okuma
            </h4>
            <span
              className={`text-[9px] font-bold ${biasColor}`}
              title="Chart Pattern skoru -100..+100 aralığındadır. Consensus skoru (0-100) ile aynı değildir."
            >
              {pattern.bias}{" "}
              {pattern.consolidated_score >= 0 ? "+" : ""}
              {pattern.consolidated_score.toFixed(1)}
              <span className="text-eyay-faint font-normal">/100</span>
            </span>
          </div>
          {activeP.length > 0 ? (
            <PatternList items={activeP} />
          ) : (
            <p className="text-[9px] text-eyay-faint italic">Aktif pattern yok.</p>
          )}
          {pattern.bias === "NEUTRAL" && (
            <p className="text-[9px] text-eyay-faint/80 italic mt-1.5 leading-snug">
              Pattern yön teyidi vermiyor; pozisyon daha çok risk planına göre yönetiliyor.
            </p>
          )}
        </section>
      )}

      {/* ────────────── Karar cümlesi ────────────── */}
      <p className="px-2.5 pb-2 text-[9px] text-eyay-dim italic leading-snug">
        {decisionSentence}
        {isManual && (
          <span className="block text-violet-300/70 mt-0.5">
            ↳ Bu pozisyon kullanıcı onayıyla açıldı; paper engine yalnızca risk yönetimini takip ediyor.
          </span>
        )}
      </p>
    </article>
  );
}

// Tek satırlık etiket–değer rowu (Pozisyon Özeti / Risk Planı içinde)
function CardRow({
  label,
  labelTip,
  value,
  valueClass = "text-eyay-text",
}: {
  label: string;
  labelTip?: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt
        className="text-[9px] text-eyay-faint shrink-0 truncate"
        title={labelTip}
      >
        {labelTip ? <span className="border-b border-dotted border-eyay-faint/40">{label}</span> : label}
      </dt>
      <dd className={`text-right truncate ${valueClass}`}>{value}</dd>
    </div>
  );
}

// Pattern aktif liste — uzun olursa truncate + expand toggle
function PatternList({ items }: { items: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? items : items.slice(0, 3);
  const hasMore = items.length > 3;
  return (
    <div className="text-[9px] text-eyay-text/90 leading-snug">
      <span>{shown.join(" · ")}</span>
      {hasMore && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setExpanded((v) => !v);
          }}
          className="ml-1.5 text-eyay-faint hover:text-eyay-text underline underline-offset-2 decoration-dotted"
        >
          {expanded ? "daha az" : `+${items.length - 3} daha`}
        </button>
      )}
    </div>
  );
}

function PendingTradeBanner({
  order,
  nowMs,
  onReject,
}: {
  order: PendingOrder;
  nowMs: number;
  onReject: () => void;
}) {
  const secondsLeft = Math.max(0, Math.ceil((new Date(order.execute_at).getTime() - nowMs) / 1000));
  const recurring = !!order.is_recurring;

  return (
    <div className="fixed top-0 left-0 right-0 z-[260]">
      <div className={`shadow-2xl text-white ${
        recurring
          ? "bg-gradient-to-r from-fuchsia-700 to-fuchsia-900"
          : "bg-gradient-to-r from-amber-700 to-amber-900"
      }`}>
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black">{recurring ? "🔁" : "⏳"}</span>
            <div>
              <p className="text-[10px] font-mono font-bold tracking-widest opacity-80">
                {recurring
                  ? `YINELENEN SINYAL · TF ${order.primary_tf || "n/a"}`
                  : "AGENT ISLEM ACIYOR"}
              </p>
              <p className="text-base font-black tracking-tight">
                {order.side} {order.pair} {secondsLeft}s icinde acilacak
              </p>
              <p className="text-[11px] opacity-85">
                {recurring
                  ? `Hazırda bekleyen ${order.pair} için farklı TF/yönden yeni sinyal geldi. Reddetmezsen otomatik açılır.`
                  : `Reddetmezsen otomatik acilir. Planlanan boyut $${order.size_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
              </p>
            </div>
          </div>

          <button
            onClick={onReject}
            className="pointer-events-auto rounded-lg border border-red-300/40 bg-red-950/40 px-4 py-2 text-sm font-mono font-bold text-red-100 hover:bg-red-950/60"
          >
            REDDET
          </button>
        </div>
      </div>
    </div>
  );
}

function TradeBanner({ event }: { event: TradeEvent }) {
  const isOpen = event.type === "OPEN";
  const isLong = event.side === "LONG";
  const isProfit = (event.pnl_usd ?? 0) >= 0;

  const bg = isOpen
    ? (isLong ? "from-emerald-600 to-emerald-800" : "from-red-600 to-red-800")
    : (isProfit ? "from-emerald-700 to-emerald-900" : "from-red-700 to-red-900");
  const icon = isOpen ? (isLong ? "▲" : "▼") : (isProfit ? "✓" : "✕");
  const title = isOpen
    ? `${event.side} ${event.pair} ACILDI`
    : `${event.side} ${event.pair} KAPATILDI`;

  return (
    <div className="fixed top-0 left-0 right-0 z-[250] pointer-events-none">
      <div
        className={`bg-gradient-to-r ${bg} text-white shadow-2xl`}
        style={{
          animation: "tradeBanner 5s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        }}
      >
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black">{icon}</span>
            <div>
              <p className="text-[10px] font-mono font-bold tracking-widest opacity-80">
                {isOpen ? "POZISYON ACILDI" : "POZISYON KAPATILDI"}
              </p>
              <p className="text-base font-black tracking-tight">{title}</p>
            </div>
          </div>

          <div className="text-right">
            {isOpen ? (
              <>
                <p className="text-[10px] font-mono opacity-70">FIYAT · BUYUKLUK</p>
                <p className="text-base font-mono font-bold">
                  ${event.price?.toLocaleString("en-US", { maximumFractionDigits: 2 })} · $
                  {event.size_usd?.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                </p>
              </>
            ) : (
              <>
                <p className="text-[10px] font-mono opacity-70">PnL</p>
                <p className="text-base font-mono font-black">
                  {(event.pnl_usd ?? 0) >= 0 ? "+" : ""}$
                  {Math.abs(event.pnl_usd ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  <span className="text-sm opacity-80 ml-2">
                    ({(event.pnl_pct ?? 0) >= 0 ? "+" : ""}
                    {(event.pnl_pct ?? 0).toFixed(2)}%)
                  </span>
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes tradeBanner {
          0% {
            transform: translateY(-100%);
            opacity: 0;
          }
          8% {
            transform: translateY(0);
            opacity: 1;
          }
          85% {
            transform: translateY(0);
            opacity: 1;
          }
          100% {
            transform: translateY(-100%);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
