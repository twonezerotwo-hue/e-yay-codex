"use client";

/**
 * Paper Trading Ticker — sağ üstte küçük bakiye + günlük PnL widget'ı.
 *
 * Yan etki: trading state'te son event değiştiğinde (OPEN/CLOSE)
 * geçici bir banner gösterir. Banner state ana sayfaya
 * (PaperTradingBanner aracılığıyla) localStorage event üzerinden bildirilir.
 */
import { useEffect, useRef, useState } from "react";

interface TradeEvent {
  type:     "OPEN" | "CLOSE";
  pair:     string;
  side:     "LONG" | "SHORT";
  price?:   number;
  size_usd?: number;
  pnl_usd?:  number;
  pnl_pct?:  number;
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
}

interface TradingState {
  starting_balance: number;
  equity: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number;
  daily_pnl_usd: number;
  open_positions: Position[];
  trade_count: number;
  last_event: TradeEvent | null;
  last_event_at: string | null;
}

const POLL_MS = 15_000;  // 15 sn'de bir tick (cache backend'de 30 sn)

export default function PaperTradingTicker() {
  const [state,         setState]         = useState<TradingState | null>(null);
  const [expanded,      setExpanded]      = useState(false);
  const [banner,        setBanner]        = useState<TradeEvent | null>(null);
  const [agentOpen,     setAgentOpen]     = useState(false);  // agent modal açıksa gizle
  const [closing,       setClosing]       = useState<string | null>(null);
  const lastEventAtRef = useRef<string | null>(null);

  // Agent modal açıkken trading widget'ı sayfa görünümünden gizle
  useEffect(() => {
    const onAgent = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setAgentOpen(!!detail?.open);
    };
    window.addEventListener("eyay:agent-modal", onAgent as EventListener);
    return () => window.removeEventListener("eyay:agent-modal", onAgent as EventListener);
  }, []);

  // Polling
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
        if (!res.ok) return;
        const d = await res.json();
        if (cancelled) return;

        setState(d);

        // Yeni event geldi mi?
        if (d.last_event_at && d.last_event_at !== lastEventAtRef.current) {
          lastEventAtRef.current = d.last_event_at;
          if (d.last_event) {
            setBanner(d.last_event);
            // 5sn sonra banner'ı kapat
            setTimeout(() => setBanner(null), 5000);
          }
        }
      } catch { /* sessiz */ }
    }
    load();
    const i = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(i); };
  }, []);

  async function handleManualClose(pair: string) {
    setClosing(pair);
    try {
      await fetch(`/api/backend/trading/close/${pair}`, { method: "POST", cache: "no-store" });
      // Hemen yeni state'i çek
      const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
      if (res.ok) setState(await res.json());
    } catch { /* sessiz */ } finally {
      setClosing(null);
    }
  }

  if (!state) return null;
  if (agentOpen) return null;  // agent modal aktifken kendini gizle

  const equityPct  = ((state.equity - state.starting_balance) / state.starting_balance) * 100;
  const dailyColor = state.daily_pnl_usd >= 0 ? "text-emerald-300" : "text-red-300";
  const eqColor    = equityPct >= 0 ? "text-emerald-400" : "text-red-400";

  const fmtUsd = (n: number) =>
    `${n >= 0 ? "+" : ""}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

  return (
    <>
      {/* === Banner — sayfanın üstünde, 5 sn'lik animasyon === */}
      {banner && <TradeBanner event={banner} />}

      {/* === Sağ üst sticky widget === */}
      <div className="fixed top-4 right-4 z-40 flex flex-col items-end gap-1">

        {/* Üst bant — Equity + Günlük PnL */}
        <button
          onClick={() => setExpanded(v => !v)}
          className="bg-eyay-surface border border-eyay-border rounded-xl shadow-card px-3 py-2 hover:border-eyay-blue/40 transition-colors"
        >
          <div className="flex items-center gap-3">
            {/* Equity */}
            <div className="text-right">
              <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Equity</p>
              <p className={`font-mono font-black text-sm leading-tight ${eqColor}`}>
                ${state.equity.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </p>
            </div>

            {/* Divider */}
            <div className="w-px h-8 bg-eyay-border" />

            {/* Günlük PnL */}
            <div className="text-right">
              <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Günlük</p>
              <p className={`font-mono font-bold text-sm leading-tight ${dailyColor}`}>
                {fmtUsd(state.daily_pnl_usd)}
              </p>
            </div>

            {/* Açık pozisyon sayısı (var ise) */}
            {state.open_positions.length > 0 && (
              <>
                <div className="w-px h-8 bg-eyay-border" />
                <div className="text-right">
                  <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Açık</p>
                  <p className="font-mono font-bold text-sm leading-tight text-eyay-blue">
                    {state.open_positions.length}
                  </p>
                </div>
              </>
            )}

            <span className={`text-eyay-faint text-xs transition-transform ${expanded ? "rotate-180" : ""}`}>
              ▾
            </span>
          </div>
        </button>

        {/* Genişletilmiş — pozisyon + trade detayları */}
        {expanded && (
          <div className="bg-eyay-surface border border-eyay-border rounded-xl shadow-card p-3 w-[340px] space-y-2">

            {/* Özet */}
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

            {/* Açık pozisyonlar */}
            {state.open_positions.length > 0 ? (
              <div>
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1.5">
                  Açık Pozisyonlar
                </p>
                <div className="space-y-1.5">
                  {state.open_positions.map(p => {
                    const sideColor  = p.side === "LONG" ? "text-emerald-400" : "text-red-400";
                    const pnlColor   = p.pnl_usd >= 0 ? "text-emerald-400" : "text-red-400";
                    const isClosing  = closing === p.pair;
                    const fmt2       = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 2 });
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
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="text-[10px] font-mono text-eyay-faint italic py-1.5 text-center">
                Açık pozisyon yok — sinyal bekleniyor
              </p>
            )}

            <p className="text-[8px] font-mono text-eyay-faint/50 pt-1 border-t border-eyay-border/40">
              🤖 Agent sinyalleri · 4 parite (BTC/XAU/XAG/BRENT) · sabit $25k pos · PAPER_SAFE
            </p>
          </div>
        )}
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Banner — yeni trade olunca üstte 5sn'lik animasyon
// ─────────────────────────────────────────────────────────────────────────────

function TradeBanner({ event }: { event: TradeEvent }) {
  const isOpen  = event.type === "OPEN";
  const isLong  = event.side === "LONG";
  const isProfit = (event.pnl_usd ?? 0) >= 0;

  const bg   = isOpen
    ? (isLong ? "from-emerald-600 to-emerald-800" : "from-red-600 to-red-800")
    : (isProfit ? "from-emerald-700 to-emerald-900" : "from-red-700 to-red-900");
  const icon = isOpen ? (isLong ? "▲" : "▼") : (isProfit ? "✓" : "✗");
  const title = isOpen
    ? `${event.side} ${event.pair} AÇILDI`
    : `${event.side} ${event.pair} KAPATILDI`;

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] pointer-events-none">
      <div
        className={`bg-gradient-to-r ${bg} text-white shadow-2xl animate-trade-banner`}
        style={{
          animation: "tradeBanner 5s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        }}
      >
        <div className="max-w-4xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl font-black">{icon}</span>
            <div>
              <p className="text-[10px] font-mono font-bold tracking-widest opacity-80">
                {isOpen ? "POZİSYON AÇILDI" : "POZİSYON KAPATILDI"}
              </p>
              <p className="text-base font-black tracking-tight">{title}</p>
            </div>
          </div>

          <div className="text-right">
            {isOpen ? (
              <>
                <p className="text-[10px] font-mono opacity-70">FİYAT · BÜYÜKLÜK</p>
                <p className="text-base font-mono font-bold">
                  ${event.price?.toLocaleString("en-US", {maximumFractionDigits: 2})} · ${event.size_usd?.toLocaleString("en-US", {maximumFractionDigits: 0})}
                </p>
              </>
            ) : (
              <>
                <p className="text-[10px] font-mono opacity-70">PnL</p>
                <p className="text-base font-mono font-black">
                  {(event.pnl_usd ?? 0) >= 0 ? "+" : ""}${Math.abs(event.pnl_usd ?? 0).toLocaleString("en-US", {maximumFractionDigits: 0})}
                  <span className="text-sm opacity-80 ml-2">
                    ({(event.pnl_pct ?? 0) >= 0 ? "+" : ""}{(event.pnl_pct ?? 0).toFixed(2)}%)
                  </span>
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes tradeBanner {
          0%   { transform: translateY(-100%); opacity: 0; }
          8%   { transform: translateY(0);     opacity: 1; }
          85%  { transform: translateY(0);     opacity: 1; }
          100% { transform: translateY(-100%); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
