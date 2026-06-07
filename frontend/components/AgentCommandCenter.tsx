"use client";

/**
 * Agent Komut Merkezi — modal içeriği.
 *
 * Insight + trading state + asset signals'i birleştirip aktif bir agent
 * görünümü verir: "ne düşünüyorum / ne yaptım / ne bekliyorum / ne kadar haklıydım".
 *
 * Veri kaynakları:
 *   /api/backend/agent/insight   → 8 proaktif gözlem
 *   /api/backend/trading/state   → açık pozisyonlar + trade history + PnL
 */
import { useEffect, useMemo, useState } from "react";

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
  paper_decision_label?: string;  // disiplinli karar dili (0 pozisyon → KÜÇÜLT yok)
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Styling
// ─────────────────────────────────────────────────────────────────────────────

const SEV: Record<AgentInsight["severity"], { dot: string; text: string; bg: string; border: string; label: string }> = {
  CRITICAL:    { dot: "bg-red-400",     text: "text-red-300",     bg: "bg-red-950/30",     border: "border-red-800/50",     label: "KRİTİK"  },
  WARNING:     { dot: "bg-amber-400",   text: "text-amber-300",   bg: "bg-amber-950/30",   border: "border-amber-800/50",   label: "DİKKAT"  },
  OPPORTUNITY: { dot: "bg-emerald-400", text: "text-emerald-300", bg: "bg-emerald-950/30", border: "border-emerald-800/50", label: "FIRSAT"  },
  OBSERVATION: { dot: "bg-eyay-blue",   text: "text-eyay-dim",    bg: "bg-eyay-raised/40", border: "border-eyay-border",    label: "GÖZLEM"  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Narrative — agent'ın "şu an ne düşünüyorum" cümlesi (Groq'a istek YOK)
// ─────────────────────────────────────────────────────────────────────────────

function buildNarrative(insights: AgentInsight[], trading: TradingState | null, decision: string): string {
  const crit = insights.filter(i => i.severity === "CRITICAL");
  const warn = insights.filter(i => i.severity === "WARNING");
  const opp  = insights.filter(i => i.severity === "OPPORTUNITY");

  const parts: string[] = [];

  if (crit.length > 0) {
    parts.push(`Şu an ${crit.length} kritik sinyal görüyorum; en kritik olanı: ${crit[0].headline.split("—")[0].trim()}`);
  } else if (warn.length >= 3) {
    parts.push(`Birden fazla dikkat sinyali var (${warn.length}); piyasa rejimi geçişte olabilir`);
  } else if (warn.length > 0) {
    parts.push(`Genel piyasa yapısı ${decision} kararına uygun; ${warn[0].headline.split("—")[0].trim()}`);
  } else if (opp.length > 0) {
    parts.push(`Aktif kritik sinyal yok; ${opp.length} fırsat izleme listemde`);
  } else {
    parts.push(`Sistem stabil — mevcut ${decision} rejimi devam ediyor`);
  }

  if (trading && trading.open_positions.length > 0) {
    const totalPnl = trading.unrealized_pnl_usd;
    const direction = totalPnl >= 0 ? "kâr" : "zarar";
    parts.push(`Şu an ${trading.open_positions.length} açık pozisyonum var, toplam ${direction} ${Math.abs(totalPnl).toFixed(0)} USD`);
  } else if (trading) {
    parts.push(`Hiç pozisyon açmadım — uygun sinyal bekliyorum`);
  }

  return parts.join(". ") + ".";
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

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export default function AgentCommandCenter({ onClose }: { onClose: () => void }) {
  const [insights, setInsights]   = useState<AgentInsight[]>([]);
  const [decision, setDecision]   = useState("");
  const [insightAt, setInsightAt] = useState<string>("");
  const [trading, setTrading]     = useState<TradingState | null>(null);
  const [now, setNow]             = useState(Date.now());

  // Polling — modal açıkken 15sn'de bir
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [iRes, tRes] = await Promise.all([
          fetch("/api/backend/agent/insight", { cache: "no-store" }),
          fetch("/api/backend/trading/state",  { cache: "no-store" }),
        ]);
        const iData: InsightResponse = await iRes.json();
        const tData: TradingState     = await tRes.json();
        if (!cancelled) {
          setInsights(iData.insights || []);
          // Disiplinli karar dili önce; yoksa regime report kararına düş
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

  // Anlık saat tic-toc (timeAgo için)
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 5_000);
    return () => clearInterval(t);
  }, []);

  // ── Türetilen veri
  const narrative = useMemo(
    () => buildNarrative(insights, trading, decision),
    [insights, trading, decision]
  );

  const activeDecisions = useMemo(() => {
    if (!trading) return [];
    return trading.open_positions.map(p => ({
      type: "POSITION" as const,
      pair: p.pair,
      side: p.side,
      pnl_usd: p.pnl_usd,
      pnl_pct: p.pnl_pct,
      entry_price: p.entry_price,
      current_price: p.current_price,
      entry_at: p.entry_at,
      last_signal: p.last_signal,
    }));
  }, [trading]);

  // YAKLAŞAN TETİKLEYİCİLER — level proximity insight'ları + OPPORTUNITY'ler
  const triggers = useMemo(() => {
    return insights.filter(
      i => i.severity === "WARNING" && /yakın|eşiğinde/.test(i.headline)
        || i.severity === "OPPORTUNITY"
    ).slice(0, 5);
  }, [insights]);

  // GÖZLEMLER — geriye kalan (cluster, news, rotation, vs.)
  const observations = useMemo(() => {
    const usedHeadlines = new Set(triggers.map(t => t.headline));
    return insights.filter(i => !usedHeadlines.has(i.headline));
  }, [insights, triggers]);

  // DOĞRULUK skoru
  const accuracy = useMemo(() => {
    if (!trading || trading.trades.length === 0) {
      return { winRate: null as number | null, wins: 0, losses: 0, totalRealized: 0 };
    }
    const wins = trading.trades.filter(t => t.pnl_usd > 0).length;
    const losses = trading.trades.filter(t => t.pnl_usd < 0).length;
    const total = wins + losses;
    return {
      winRate: total > 0 ? (wins / total) * 100 : null,
      wins,
      losses,
      totalRealized: trading.realized_pnl_usd,
    };
  }, [trading]);

  // ── Render
  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col"
      style={{ backgroundColor: "#0a0a0f" }}
      onClick={onClose}
    >
      <div
        className="flex-1 overflow-y-auto"
        style={{ backgroundColor: "#0a0a0f" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ════════════════════════════════════════════════════════════════
            ÜST BAŞLIK — AGENT STATÜSÜ
           ════════════════════════════════════════════════════════════════ */}
        <header
          className="sticky top-0 z-10 border-b border-eyay-border"
          style={{ backgroundColor: "#15151c" }}
        >
          <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              {/* Canlı agent indicator */}
              <div className="relative">
                <div className="w-12 h-12 rounded-2xl bg-eyay-raised border border-eyay-border flex items-center justify-center text-2xl">
                  🤖
                </div>
                <span className="absolute -bottom-1 -right-1 w-3 h-3 rounded-full bg-emerald-400 border-2 border-eyay-bg animate-pulse" />
              </div>

              <div>
                <p className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  AGENT · CANLI
                </p>
                <h2 className="text-lg font-bold text-eyay-text mt-0.5 leading-tight">
                  Komut Merkezi
                </h2>
                {insightAt && (
                  <p className="text-[10px] font-mono text-eyay-faint mt-0.5">
                    Son tarama {timeAgo(insightAt)} · piyasa izleniyor
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

        <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">

          {/* ════════════════════════════════════════════════════════════
              ŞU AN NE DÜŞÜNÜYORUM (canlı narrative)
             ════════════════════════════════════════════════════════════ */}
          <section className="rounded-2xl border border-eyay-blue/30 bg-gradient-to-br from-eyay-blue/10 to-eyay-blue/0 p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">🧠</span>
              <p className="text-[10px] font-mono text-eyay-blue uppercase tracking-widest font-bold">
                Şu an ne düşünüyorum
              </p>
            </div>
            <p className="text-sm text-eyay-text leading-relaxed">{narrative}</p>
            <div className="mt-3 pt-3 border-t border-eyay-blue/15 flex items-center gap-3 flex-wrap">
              <span className="text-[10px] font-mono text-eyay-faint">PORTFÖY KARARI</span>
              <span className={`text-xs font-mono font-black px-2 py-0.5 rounded border ${
                decision === "AÇIL" ? "border-emerald-700 text-emerald-300 bg-emerald-950/30"
                : decision === "KORU" ? "border-emerald-700 text-emerald-300 bg-emerald-950/30"
                : decision === "KAPAT" ? "border-red-700 text-red-300 bg-red-950/30"
                : decision === "İŞLEM YOK / SİSTEM DURDU" ? "border-red-700 text-red-300 bg-red-950/40"
                : decision === "KÜÇÜLT" ? "border-orange-700 text-orange-300 bg-orange-950/30"
                : decision === "POZİSYON ARTIRMA" ? "border-yellow-700 text-yellow-300 bg-yellow-950/25"
                : decision === "İZLE" ? "border-blue-700 text-blue-300 bg-blue-950/25"
                : decision === "YENİ RİSK AÇMA / BEKLE" ? "border-amber-700 text-amber-300 bg-amber-950/30"
                : decision === "POZİSYON YOK · NÖTR İZLEME" ? "border-slate-700 text-slate-300 bg-slate-950/30"
                : "border-amber-700 text-amber-300 bg-amber-950/30"
              }`}>
                {decision || "—"}
              </span>
            </div>
          </section>

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
              <p className="text-xs text-eyay-faint italic text-center py-6">
                Şu an açık pozisyon yok — uygun sinyal bekliyorum
              </p>
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
              GENEL GÖZLEMLER (cluster, news, rotation)
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
              DOĞRULUK SKORU — geçmiş trade'ler
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
                <Stat
                  label="KAZANAN"
                  value={String(accuracy.wins)}
                  color="text-emerald-300"
                />
                <Stat
                  label="KAYBEDEN"
                  value={String(accuracy.losses)}
                  color="text-red-300"
                />
                <Stat
                  label="REALIZED PNL"
                  value={fmtUsd(accuracy.totalRealized)}
                  color={accuracy.totalRealized >= 0 ? "text-emerald-300" : "text-red-300"}
                />
              </div>

              {/* Son kapanan trade'ler */}
              {trading.trades.length > 0 && (
                <div className="mt-4 pt-4 border-t border-eyay-border/40">
                  <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-2">
                    SON KAPANANLAR
                  </p>
                  <div className="space-y-1.5">
                    {trading.trades.slice(-5).reverse().map((t) => (
                      <div key={t.id} className="flex items-center justify-between text-[10px] font-mono bg-eyay-raised rounded px-2 py-1.5">
                        <div className="flex items-center gap-2">
                          <span className={`${t.side === "LONG" ? "text-emerald-400" : "text-red-400"}`}>
                            {t.side === "LONG" ? "▲" : "▼"}
                          </span>
                          <span className="text-eyay-text">{t.pair}</span>
                          <span className="text-eyay-faint">{timeAgo(t.exit_at)}</span>
                          <span className="text-eyay-faint">{t.duration_min}dk</span>
                        </div>
                        <div className="text-right">
                          <span className={`font-bold ${t.pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {fmtUsd(t.pnl_usd)} ({t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(2)}%)
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* Footer */}
          <div className="pt-2 border-t border-eyay-border/40">
            <p className="text-[10px] font-mono text-eyay-faint text-center leading-relaxed">
              🤖 Agent canlı izleme · 15 sn'de bir tazelenir · saf analiz (Groq'a istek yok)<br />
              PAPER_SAFE · NO_EXECUTION · tüm gerçek kararlar insana aittir
            </p>
          </div>
        </div>

        {/* Alt sabit kapat çubuğu */}
        <div
          className="sticky bottom-0 border-t border-eyay-border"
          style={{ backgroundColor: "#15151c" }}
        >
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
