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
  risk_plan?: RiskPlan;
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

export default function PaperTradingTicker() {
  const [state,        setState]       = useState<TradingState | null>(null);
  const [expanded,     setExpanded]    = useState(false);
  const [banner,       setBanner]      = useState<TradeEvent | null>(null);
  const [agentOpen,    setAgentOpen]   = useState(false);
  const [closing,      setClosing]     = useState<string | null>(null);
  const [patterns,     setPatterns]    = useState<Record<string, ChartPatternSummary>>({});
  const [nowMs,        setNowMs]       = useState(Date.now());
  const [soundEnabled, setSoundEnabled] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("eyay-sound") !== "off";
  });
  const [resetConfirm, setResetConfirm] = useState(false);
  const lastEventAtRef  = useRef<string | null>(null);
  const lastAlertIdRef  = useRef<number>(0);   // sesli uyarı dedup

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
        // Sesli uyarıları sıraya al (önce kritik)
        const voiceAlerts = newAlerts
          .filter(a => a.voice)
          .sort((a, b) => a.id - b.id);
        for (const alert of voiceAlerts) {
          speakAlert(alert);
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
    if (!soundEnabled) return;                             // ses kapalıysa çıkış
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

  function toggleSound() {
    setSoundEnabled(prev => {
      const next = !prev;
      localStorage.setItem("eyay-sound", next ? "on" : "off");
      if (!next && typeof window !== "undefined") {
        window.speechSynthesis?.cancel();   // devam eden konuşmayı kes
      }
      return next;
    });
  }

  async function resetTrades() {
    try {
      await fetch("/api/backend/trading/reset-trades", { method: "POST", cache: "no-store" });
      const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
      if (res.ok) setState(await res.json());
    } catch { /* sessiz */ } finally {
      setResetConfirm(false);
    }
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

  const fmtUsd = (value: number) =>
    `${value >= 0 ? "+" : ""}$${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

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
            <div className="bg-eyay-surface border border-eyay-border rounded-xl shadow-card p-3 w-[340px] space-y-2">
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
                  <div className="space-y-1.5">
                    {state.open_positions.map(p => {
                      const sideColor    = p.side === "LONG" ? "text-emerald-400" : "text-red-400";
                      const pnlColor     = p.pnl_usd >= 0 ? "text-emerald-400" : "text-red-400";
                      const isClosing    = closing === p.pair;
                      const fmt2         = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 2 });
                      const pctFromEntry = (level: number) =>
                        ((level - p.entry_price) / p.entry_price * 100).toFixed(1);
                      return (
                        <div key={p.pair} className="bg-eyay-raised rounded px-2 py-1.5 space-y-1 text-[10px] font-mono">
                          {/* Row 1: pair + PnL + Kapat */}
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              <span className={`font-black ${sideColor}`}>
                                {p.side === "LONG" ? "▲" : "▼"} {p.pair}
                              </span>
                              <span className="text-eyay-faint">@{fmt2(p.entry_price)}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="text-right">
                                <p className={`font-bold ${pnlColor}`}>{fmtUsd(p.pnl_usd)}</p>
                                <p className={`text-[8px] ${pnlColor}`}>{p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct.toFixed(2)}%</p>
                              </div>
                              <button
                                onClick={() => handleManualClose(p.pair)}
                                disabled={isClosing}
                                className="text-[8px] font-bold bg-red-950/60 hover:bg-red-700/50 border border-red-700/40 text-red-400 hover:text-red-200 px-1.5 py-1 rounded transition-colors disabled:opacity-40 whitespace-nowrap leading-tight"
                              >
                                {isClosing ? "···" : <span className="flex flex-col items-center"><span>Manuel</span><span>Kapat</span></span>}
                              </button>
                            </div>
                          </div>
                          {/* Row 2: SL / TP seviyeleri */}
                          {(p.stop_loss > 0 || p.take_profit > 0) && (
                            <div className="flex items-center gap-3 text-[8px]">
                              {p.stop_loss > 0 && (
                                <span className="text-red-400">
                                  SL {fmt2(p.stop_loss)}
                                  <span className="opacity-70 ml-0.5">({pctFromEntry(p.stop_loss)}%)</span>
                                </span>
                              )}
                              {p.take_profit > 0 && (
                                <span className="text-emerald-400">
                                  TP {fmt2(p.take_profit)}
                                  <span className="opacity-70 ml-0.5">(+{pctFromEntry(p.take_profit)}%)</span>
                                </span>
                              )}
                            </div>
                          )}
                          {/* Row 2b: Risk plan — timeframe + ATR + horizon */}
                          {p.risk_plan && (p.risk_plan.timeframe || p.risk_plan.atr_value) && (
                            <div
                              className="flex flex-wrap items-center gap-2 text-[8px] text-eyay-faint border-t border-eyay-border/20 pt-1"
                              title={p.risk_plan.explanation || ""}
                            >
                              {p.risk_plan.timeframe && (
                                <span className="px-1 py-[1px] rounded bg-eyay-raised/60 border border-eyay-border/40">
                                  TF: <span className="text-eyay-text font-bold">{p.risk_plan.timeframe}</span>
                                </span>
                              )}
                              {p.risk_plan.atr_period_bars && (
                                <span>
                                  ATR({p.risk_plan.atr_period_bars})
                                  {p.risk_plan.atr_value != null && (
                                    <span className="opacity-70 ml-0.5">
                                      ={typeof p.risk_plan.atr_value === "number" ? p.risk_plan.atr_value.toFixed(4) : p.risk_plan.atr_value}
                                    </span>
                                  )}
                                </span>
                              )}
                              {p.risk_plan.risk_reward && (
                                <span>RR <span className="text-eyay-text">1:{p.risk_plan.risk_reward}</span></span>
                              )}
                              {p.risk_plan.expected_horizon_hours?.low != null && (
                                <span>
                                  ⏱ Beklenen tutuş:
                                  <span className="text-eyay-text ml-0.5">
                                    {p.risk_plan.expected_horizon_hours.low}-{p.risk_plan.expected_horizon_hours.high} saat
                                  </span>
                                </span>
                              )}
                              {p.risk_plan.sl_basis && (
                                <span className="opacity-70">· {p.risk_plan.sl_basis}</span>
                              )}
                            </div>
                          )}
                          {/* Row 3: Chart Pattern göstergesi (pattern_score: -100..+100, ≠ consensus) */}
                          {patterns[p.pair] && (
                            <div
                              className="flex items-center gap-1.5 text-[8px] pt-0.5 border-t border-eyay-border/30"
                              title="Chart Pattern skoru -100..+100 aralığındadır. Consensus skoru (0-100) ile aynı değildir."
                            >
                              <span className="text-eyay-faint">📊 Pattern</span>
                              <span className={
                                patterns[p.pair].bias === "BULLISH" ? "text-emerald-400 font-bold" :
                                patterns[p.pair].bias === "BEARISH" ? "text-red-400 font-bold" :
                                "text-eyay-faint"
                              }>
                                {patterns[p.pair].bias} {patterns[p.pair].consolidated_score >= 0 ? "+" : ""}
                                {patterns[p.pair].consolidated_score.toFixed(1)}
                                <span className="text-eyay-faint font-normal">/100</span>
                              </span>
                              {patterns[p.pair].active_patterns?.length > 0 && (
                                <span className="text-eyay-faint truncate">
                                  · {patterns[p.pair].active_patterns.slice(0, 2).join(", ")}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
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
                            <span className="text-eyay-faint/70 text-[9px]" title={`Reddedildiği fiyat: $${orig.toLocaleString("en-US", { maximumFractionDigits: 2 })}`}>
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

              <div className="flex items-center justify-between pt-1 border-t border-eyay-border/40">
                <p className="text-[8px] font-mono text-eyay-faint/50">
                  Agent · 4 parite · Analiz modu
                </p>
                <div className="flex items-center gap-1.5">
                  {/* Ses toggle */}
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleSound(); }}
                    title={soundEnabled ? "Sesli uyarıyı kapat" : "Sesli uyarıyı aç"}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-colors ${
                      soundEnabled
                        ? "border-eyay-blue/40 text-eyay-blue hover:bg-eyay-blue/10"
                        : "border-eyay-border text-eyay-faint hover:bg-eyay-raised/40"
                    }`}
                  >
                    {soundEnabled ? "🔔 Ses Açık" : "🔕 Ses Kapalı"}
                  </button>

                  {/* Log temizle (çift tıklama onay) */}
                  {resetConfirm ? (
                    <div className="flex items-center gap-1">
                      <span className="text-[9px] font-mono text-amber-400">Emin misin?</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); void resetTrades(); }}
                        className="px-2 py-0.5 rounded text-[10px] font-mono border border-red-600/60 text-red-400 hover:bg-red-950/30"
                      >
                        Evet, Temizle
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setResetConfirm(false); }}
                        className="px-2 py-0.5 rounded text-[10px] font-mono border border-eyay-border text-eyay-dim hover:bg-eyay-raised/40"
                      >
                        İptal
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => { e.stopPropagation(); setResetConfirm(true); }}
                      title="İşlem geçmişini sıfırla (öğrenmeler korunur)"
                      className="px-2 py-0.5 rounded text-[10px] font-mono border border-eyay-border text-eyay-faint hover:border-red-600/40 hover:text-red-400 transition-colors"
                    >
                      Log Temizle
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
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
