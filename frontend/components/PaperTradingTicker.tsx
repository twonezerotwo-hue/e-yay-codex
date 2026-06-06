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

interface Position {
  pair: string;
  side: "LONG" | "SHORT";
  entry_price: number;
  current_price: number;
  pnl_usd: number;
  pnl_pct: number;
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
}

interface TradingState {
  starting_balance: number;
  equity: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  daily_pnl_usd: number;
  open_positions: Position[];
  pending_orders: PendingOrder[];
  trade_count: number;
  last_event: TradeEvent | null;
  last_event_at: string | null;
}

const POLL_MS = 15_000;

export default function PaperTradingTicker() {
  const [state, setState] = useState<TradingState | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [banner, setBanner] = useState<TradeEvent | null>(null);
  const [agentOpen, setAgentOpen] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());
  const lastEventAtRef = useRef<string | null>(null);

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

    load();
    const intervalId = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    const intervalId = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(intervalId);
  }, []);

  if (!state) {
    return null;
  }

  const pendingOrders = state.pending_orders ?? [];
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
                    {state.open_positions.map((position) => {
                      const sideColor = position.side === "LONG" ? "text-emerald-400" : "text-red-400";
                      const pnlColor = position.pnl_usd >= 0 ? "text-emerald-400" : "text-red-400";
                      return (
                        <div key={position.pair} className="flex items-center justify-between text-[10px] font-mono bg-eyay-raised rounded px-2 py-1">
                          <div className="flex items-center gap-1.5">
                            <span className={`font-black ${sideColor}`}>
                              {position.side === "LONG" ? "▲" : "▼"} {position.pair}
                            </span>
                            <span className="text-eyay-faint">
                              @{position.entry_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}
                            </span>
                          </div>
                          <div className="text-right">
                            <p className={`font-bold ${pnlColor}`}>{fmtUsd(position.pnl_usd)}</p>
                            <p className={`text-[8px] ${pnlColor}`}>
                              {position.pnl_pct >= 0 ? "+" : ""}
                              {position.pnl_pct.toFixed(2)}%
                            </p>
                          </div>
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
                    Bekleyen Agent Islemleri
                  </p>
                  {pendingOrders.map((order) => {
                    const secondsLeft = Math.max(
                      0,
                      Math.ceil((new Date(order.execute_at).getTime() - nowMs) / 1000),
                    );
                    return (
                      <div key={order.pair} className="flex items-center justify-between text-[10px] font-mono bg-amber-950/20 border border-amber-900/40 rounded px-2 py-1">
                        <div>
                          <p className="font-bold text-amber-300">
                            {order.side} {order.pair}
                          </p>
                          <p className="text-eyay-faint">{secondsLeft}s sonra otomatik acilacak</p>
                        </div>
                        <button
                          onClick={(event) => {
                            event.stopPropagation();
                            void rejectPendingOrder(order.pair);
                          }}
                          className="px-2 py-1 rounded border border-red-700/60 text-red-300 hover:bg-red-950/30"
                        >
                          Reddet
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              <p className="text-[8px] font-mono text-eyay-faint/50 pt-1 border-t border-eyay-border/40">
                Agent sinyalleri · 4 parite (BTC/XAU/XAG/BRENT) · PAPER_SAFE
              </p>
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

  return (
    <div className="fixed top-0 left-0 right-0 z-[260]">
      <div className="bg-gradient-to-r from-amber-700 to-amber-900 text-white shadow-2xl">
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black">⏳</span>
            <div>
              <p className="text-[10px] font-mono font-bold tracking-widest opacity-80">
                AGENT ISLEM ACIYOR
              </p>
              <p className="text-base font-black tracking-tight">
                {order.side} {order.pair} {secondsLeft}s icinde acilacak
              </p>
              <p className="text-[11px] opacity-85">
                Reddetmezsen otomatik acilir. Planlanan boyut ${order.size_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}
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
