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

// FAZ 3: Add Plan / Manual Override / Opening Explanation tipleri
interface AddLevel {
  id: string;
  trigger_type: "price_pullback" | "breakout_confirm" | "pnl_drawdown" | "momentum_reclaim" | "manual";
  trigger_price?: number | null;
  trigger_pnl_pct?: number | null;
  add_size_usd: number;
  condition_text: string;
  status: "waiting" | "ready" | "filled" | "blocked" | "manual_required";
  requires_manual_confirmation?: boolean;
  created_at?: string;
  filled_at?: string | null;
}

interface AddPlanControl {
  allowed: boolean;
  status: "allowed" | "manual_required" | "blocked" | "risk_warning";
  reason: string;
  risk_checks?: Record<string, boolean>;
  warnings?: string[];
  before_add?: { size_usd: number; average_entry: number; stop_loss: number; take_profit: number; rr: number; max_loss_usd?: number | null };
  after_add_preview?: { size_usd: number; average_entry: number; stop_loss: number; take_profit: number; rr: number; max_loss_usd?: number | null };
  manual_risk_override_active?: boolean;
  evaluated_at?: string;
}

interface AddPlan {
  mode: "off" | "manual" | "paper_auto";
  current_size_usd: number;
  max_position_size_usd: number;
  remaining_add_capacity_usd: number;
  average_entry_price: number;
  add_levels: AddLevel[];
  last_control_result?: AddPlanControl | null;
  created_at?: string;
}

interface ManualRiskOverride {
  is_manual_override: boolean;
  previous_stop_loss: number;
  previous_take_profit: number;
  new_stop_loss: number;
  new_take_profit: number;
  previous_rr: number;
  new_rr: number;
  changed_at: string;
  changed_by: "user";
  reason: string;
  auto_plan_backup?: { stop_loss: number; take_profit: number; rr: number; atr_multiplier?: number | null };
  warnings?: string[];
}

interface OpeningExplanation {
  primary_reason: string;
  was_pattern_primary_reason: boolean;
  pattern_summary: string;
  pattern_notes: string[];
  supporting_layers: Record<string, string>;
  opposing_signals: string[];
  why_trade_opened_anyway: string;
  invalidation_summary: string[];
  generated_at?: string;
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
  // FAZ 3
  add_plan?: AddPlan;
  manual_risk_override?: ManualRiskOverride;
  opening_explanation?: OpeningExplanation;
  average_entry_price?: number;
  // Open signal — backend agent_decision_aggregator çıktısı (asdict ile serialize)
  open_signal?: {
    // Temel sinyal metrikleri
    primary_tf?: string;            // Sinyalin üretildiği TF (1h, 4h, 1d)
    final_score?: number;           // Confluence sonrası nihai skor
    final_direction?: string;       // bullish / bearish / neutral
    contradiction_score?: number;   // 0-100
    // Modül tabanlı consensus (base TF üzerinde hesaplandı)
    base?: {
      timeframe?: string;
      consensus_score?: number;
      direction?: string;
      module_scores?: Record<string, number>;
      contributions?: Record<string, {
        score: number;
        weight: number;
        weighted_score: number;
      }>;
    };
    // Çok-zaman-dilimi confluence
    confluence?: {
      original_score?: number;
      adjusted_score?: number;
      multiplier?: number;
      status?: string;        // "aligned" | "opposing" | "skipped"
      vote_count?: { aligned: number; opposing: number; neutral_ignored: number };
      tf_directions?: Record<string, string>;  // {"4h":"bullish","1d":"bullish"}
      warnings?: string[];
    };
    // Her TF için ayrı consensus signal
    tf_signals?: Record<string, {
      consensus_score?: number;
      direction?: string;
      module_scores?: Record<string, number>;
    }>;
    other_tf_scores?: Record<string, number>;  // {"4h": 64.1, "1d": 64.1}
    // Aggression / izleme TF kararı
    timeframe_decision?: {
      selected_timeframe?: string;    // monitoring TF (4h)
      reason?: string;
      max_holding_time?: string;
      recheck_interval_minutes?: number;
    };
    aggression_context?: {
      aggression_level?: string;
      aggression_score?: number;
      recommended_timeframe?: string;
      max_holding_time?: string;
      summary?: string;
    };
    // Diğer context
    news?: string[];
    agent_command?: string;
  };
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

interface StateAnomaly {
  active: boolean;
  reasons: string[];
  action: "OK" | "REPAIR_OR_RESET_REQUIRED";
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
  state_anomaly?: StateAnomaly;
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
  const anomalyActive = !!state.state_anomaly?.active;
  const equityPct = ((state.equity - state.starting_balance) / state.starting_balance) * 100;
  const dailyColor = state.daily_pnl_usd >= 0 ? "text-emerald-300" : "text-red-300";
  const equityColor = equityPct >= 0 ? "text-emerald-400" : "text-red-400";

  // Anomaly banner — açık pozisyon varsa kartların ALTINA, yoksa stats üstüne.
  // Tek satır kompakt; reset/repair butonları inline.
  const handleAnomalyReset = async () => {
    if (!window.confirm(
      "Paper trading state TAM SIFIRLANACAK. Önce backup alınır.\n\nDevam edilsin mi?",
    )) return;
    try {
      const r = await fetch("/api/backend/trading/state/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "ui_manual_reset" }),
        cache: "no-store",
      });
      if (r.ok) {
        const body = await r.json();
        window.alert(`Reset tamam.\nBackup: ${body.backup_path ?? "(yok)"}\nYeni equity: $${body.equity ?? 100000}`);
        await loadState();
      } else {
        window.alert(`Reset başarısız: HTTP ${r.status}`);
      }
    } catch (e) {
      window.alert(`Reset hatası: ${String(e).slice(0, 200)}`);
    }
  };
  const handleAnomalyRepair = async (dryRun: boolean) => {
    try {
      const r = await fetch("/api/backend/trading/state/repair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dry_run: dryRun }),
        cache: "no-store",
      });
      const body = await r.json();
      if (!r.ok) {
        window.alert(`Repair HTTP ${r.status}: ${JSON.stringify(body).slice(0, 200)}`);
        return;
      }
      if (body.status === "repair_not_safe") {
        window.alert("Repair güvenli değil (tüm trade kayıtları bozuk).\nReset gerekli.");
        return;
      }
      const summary = [
        `${dryRun ? "Dry-run" : "Apply"} sonucu:`,
        `  Eski realized: $${body.old_realized_pnl}`,
        `  Yeni realized: $${body.corrected_realized_pnl}`,
        `  Yeni equity:   $${body.new_equity}`,
        `  Sağlıklı trade: ${body.sane_trade_count}`,
        `  Anomalous trade: ${body.anomalous_trade_count}`,
        body.backup_path ? `  Backup: ${body.backup_path}` : "",
      ].filter(Boolean).join("\n");
      window.alert(summary);
      if (!dryRun) await loadState();
    } catch (e) {
      window.alert(`Repair hatası: ${String(e).slice(0, 200)}`);
    }
  };
  const anomalyBanner = anomalyActive && state.state_anomaly ? (
    <StateAnomalyBanner
      anomaly={state.state_anomaly}
      onReset={handleAnomalyReset}
      onRepair={handleAnomalyRepair}
    />
  ) : null;

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
              {anomalyActive ? (
                <div className="text-right">
                  <p className="text-[8px] font-mono text-red-300 uppercase tracking-wider font-bold">⚠ Anomaly</p>
                  <p className="font-mono font-black text-sm leading-tight text-red-400">
                    Reset / Repair
                  </p>
                </div>
              ) : (
                <>
                  <div className="text-right">
                    <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Equity</p>
                    <p className={`font-mono font-black text-sm leading-tight ${equityColor}`}>
                      ${state.equity.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </p>
                  </div>

                  <div className="w-px h-8 bg-eyay-border" />

                  <div className="text-right">
                    <p className="text-[8px] font-mono text-eyay-faint uppercase tracking-wider">Günlük</p>
                    <p className={`font-mono font-bold text-sm leading-tight ${dailyColor}`}>
                      {fmtUsd(state.daily_pnl_usd)}
                    </p>
                  </div>
                </>
              )}

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
              {anomalyActive && state.open_positions.length === 0 && anomalyBanner}
              <div className="grid grid-cols-3 gap-2 text-center pb-2 border-b border-eyay-border/40">
                <div>
                  <p className="text-[8px] font-mono text-eyay-faint">REALIZED</p>
                  {anomalyActive ? (
                    <p className="text-xs font-mono font-bold text-eyay-faint italic">— gizli —</p>
                  ) : (
                    <p className={`text-xs font-mono font-bold ${state.realized_pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {fmtUsd(state.realized_pnl_usd)}
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-[8px] font-mono text-eyay-faint">UNREALIZED</p>
                  {anomalyActive ? (
                    <p className="text-xs font-mono font-bold text-eyay-faint italic">— gizli —</p>
                  ) : (
                    <p className={`text-xs font-mono font-bold ${state.unrealized_pnl_usd >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {fmtUsd(state.unrealized_pnl_usd)}
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-[8px] font-mono text-eyay-faint">TRADES</p>
                  <p className="text-xs font-mono font-bold text-eyay-text">{state.trade_count}</p>
                </div>
              </div>

              {state.open_positions.length > 0 ? (
                <div>
                  <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1.5">
                    Açık Pozisyonlar
                  </p>
                  <div className="space-y-2">
                    {state.open_positions.map(p => (
                      <OpenPositionCard
                        key={p.pair}
                        position={p}
                        pattern={patterns[p.pair]}
                        isClosing={closing === p.pair}
                        onClose={() => handleManualClose(p.pair)}
                        onRefresh={async () => {
                          try {
                            const res = await fetch("/api/backend/trading/state", { cache: "no-store" });
                            if (res.ok) setState(await res.json());
                          } catch { /* sessiz */ }
                        }}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-[10px] font-mono text-eyay-faint italic py-1.5 text-center">
                  Açık pozisyon yok
                </p>
              )}

              {/* Anomaly banner — açık pozisyon varsa kartların ALTINA gelir
                  (öncelik açık pozisyondur). Açık pozisyon yokken zaten yukarıda
                  gösteriliyor (stats grid'in üstünde). */}
              {anomalyActive && state.open_positions.length > 0 && anomalyBanner}

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
// STATE ANOMALY BANNER
// Realized PnL / equity başlangıç bakiyenin kat kat üzerinde, ya da günlük PnL
// %50'yi aşıyorsa: paper trading state corrupt sayılır. UI burada banner basar,
// yeni trade açılışı backend tarafından engellenir; kullanıcı reset veya
// dry-run/apply repair seçebilir.
// ─────────────────────────────────────────────────────────────────────────────
function StateAnomalyBanner({
  anomaly,
  onReset,
  onRepair,
}: {
  anomaly: StateAnomaly;
  onReset: () => Promise<void>;
  onRepair: (dryRun: boolean) => Promise<void>;
}) {
  const [detailOpen, setDetailOpen] = useState(false);
  return (
    <div className="rounded border border-red-700/60 bg-red-950/30 px-2 py-1.5 text-[10px] font-mono">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-red-200 font-bold whitespace-nowrap">
          ⚠ Paper PnL paused
        </span>
        <span className="text-red-200/70 truncate">· State check required</span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={onReset}
            className="text-[9px] px-1.5 py-0.5 rounded border border-red-700/60 text-red-200 hover:bg-red-900/40"
          >
            Reset
          </button>
          <button
            onClick={() => onRepair(true)}
            className="text-[9px] px-1.5 py-0.5 rounded border border-amber-700/60 text-amber-200 hover:bg-amber-950/30"
          >
            Repair
          </button>
          <button
            onClick={() => setDetailOpen((v) => !v)}
            className="text-[9px] px-1.5 py-0.5 rounded border border-eyay-border text-eyay-faint hover:text-eyay-text"
          >
            Detay {detailOpen ? "▴" : "▾"}
          </button>
        </div>
      </div>
      {detailOpen && (
        <div className="mt-1.5 pt-1.5 border-t border-red-800/40 space-y-1">
          {anomaly.reasons.length > 0 && (
            <ul className="text-[9px] text-red-100/80 list-disc list-inside space-y-0.5">
              {anomaly.reasons.slice(0, 4).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-1">
            <button
              onClick={() => onRepair(true)}
              className="text-[9px] px-1.5 py-0.5 rounded border border-amber-700/60 text-amber-200 hover:bg-amber-950/30"
            >
              Dry-run Repair
            </button>
            <button
              onClick={() => onRepair(false)}
              className="text-[9px] px-1.5 py-0.5 rounded border border-emerald-700/60 text-emerald-200 hover:bg-emerald-950/30"
            >
              Apply Repair
            </button>
          </div>
        </div>
      )}
    </div>
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

// FAZ 3: Position management helpers — küçük ve odaklı (UI'da debug panel YOK)

function fmtUsdSigned(n: number): string {
  return `${n >= 0 ? "+" : ""}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function StatusBadge({ status }: { status: AddPlanControl["status"] | AddLevel["status"] }) {
  const map: Record<string, { cls: string; label: string }> = {
    allowed:         { cls: "border-emerald-700/60 bg-emerald-950/40 text-emerald-300", label: "Uygun" },
    ready:           { cls: "border-emerald-700/60 bg-emerald-950/40 text-emerald-300", label: "Hazır" },
    filled:          { cls: "border-sky-700/60 bg-sky-950/40 text-sky-300",             label: "Dolduruldu" },
    waiting:         { cls: "border-eyay-border bg-eyay-raised/60 text-eyay-faint",     label: "Bekliyor" },
    manual_required: { cls: "border-amber-700/60 bg-amber-950/40 text-amber-300",       label: "Manuel Onay" },
    risk_warning:    { cls: "border-amber-700/60 bg-amber-950/40 text-amber-300",       label: "Riskli" },
    blocked:         { cls: "border-red-700/60 bg-red-950/40 text-red-300",             label: "Bloklu" },
  };
  const m = map[status] ?? { cls: "border-eyay-border text-eyay-faint", label: status };
  return (
    <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${m.cls}`}>
      {m.label}
    </span>
  );
}

async function _readJSON(res: Response): Promise<any> {
  // İstek başarısız olsa bile JSON parse'a girip detail görmek istiyoruz
  try {
    return await res.json();
  } catch {
    return { __parse_error: true, status_code: res.status };
  }
}

async function _wrap(res: Response): Promise<any> {
  const body = await _readJSON(res);
  if (!res.ok) {
    // FastAPI 422 → body.detail (str | list[{msg, loc}]) · 404/500 → body.detail
    let msg: string;
    if (typeof body?.detail === "string") {
      msg = body.detail;
    } else if (Array.isArray(body?.detail) && body.detail.length > 0) {
      msg = body.detail.map((d: any) => d?.msg || JSON.stringify(d)).join(" · ");
    } else if (body?.__parse_error) {
      msg = "Sunucu yanıtı okunamadı";
    } else {
      msg = JSON.stringify(body).slice(0, 200);
    }
    // status: "http_error" + reason: HTTP code + msg — caller bu alanları gösterir
    return {
      status: "http_error",
      http_status: res.status,
      reason: `HTTP ${res.status}: ${msg}` + (
        res.status === 404
          ? " · Backend yeniden başlatılması gerekebilir (yeni endpoint)"
          : ""
      ),
    };
  }
  return body;
}

async function postJSON(url: string, body: unknown): Promise<any> {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    return await _wrap(res);
  } catch (e) {
    return { status: "network_error", reason: `Ağ hatası: ${String(e).slice(0, 140)}` };
  }
}

async function patchJSON(url: string, body: unknown): Promise<any> {
  try {
    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    return await _wrap(res);
  } catch (e) {
    return { status: "network_error", reason: `Ağ hatası: ${String(e).slice(0, 140)}` };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AddToPositionModal — manuel ekleme
// ─────────────────────────────────────────────────────────────────────────────

const ADD_PRESETS = [500, 1000, 2000, 5000];
const ADD_REASONS = [
  { value: "support_reaction",     label: "Destekten tepki" },
  { value: "average_down",         label: "Ortalama düşürme" },
  { value: "breakout_confirm",     label: "Kırılım teyidi" },
  { value: "momentum_reclaim",     label: "Momentum geri alımı" },
  { value: "manual_strategy",      label: "Manuel strateji" },
  { value: "other",                label: "Diğer" },
];

function AddToPositionModal({
  pair, position, onClose, onAdded,
}: {
  pair: string;
  position: Position;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [size, setSize] = useState<number>(500);
  const [customSize, setCustomSize] = useState<string>("");
  const [reason, setReason] = useState<string>(ADD_REASONS[0].value);
  const [preview, setPreview] = useState<AddPlanControl | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [err, setErr] = useState<string | null>(null);

  const effectiveSize = customSize ? Number(customSize) || 0 : size;

  // Preview her input değişikliğinde yeniden fetch et (debounce light)
  useEffect(() => {
    if (effectiveSize <= 0) { setPreview(null); return; }
    let cancel = false;
    const t = setTimeout(async () => {
      try {
        const r = await postJSON(
          `/api/backend/trading/positions/${pair}/add/preview`,
          { add_size_usd: effectiveSize, mode: "manual" },
        );
        if (!cancel && r?.control) setPreview(r.control);
      } catch { /* sessiz */ }
    }, 250);
    return () => { cancel = true; clearTimeout(t); };
  }, [effectiveSize, pair]);

  async function submit() {
    if (effectiveSize <= 0) { setErr("Geçerli bir miktar girin"); return; }
    setBusy(true); setErr(null);
    try {
      const r = await postJSON(
        `/api/backend/trading/positions/${pair}/add`,
        { add_size_usd: effectiveSize, reason, mode: "manual" },
      );
      if (r?.status === "added") {
        onAdded();
        onClose();
      } else if (r?.status === "rejected") {
        setErr(r?.control?.reason || "Risk gate engelledi");
      } else {
        setErr(r?.reason || r?.status || "Bilinmeyen hata");
      }
    } catch (e) {
      setErr(String(e).slice(0, 140));
    } finally {
      setBusy(false);
    }
  }

  const beforeRR = preview?.before_add?.rr;
  const afterRR = preview?.after_add_preview?.rr;
  const beforeAvg = preview?.before_add?.average_entry;
  const afterAvg = preview?.after_add_preview?.average_entry;
  const beforeSize = preview?.before_add?.size_usd;
  const afterSize = preview?.after_add_preview?.size_usd;
  const maxLossBefore = preview?.before_add?.max_loss_usd;
  const maxLossAfter = preview?.after_add_preview?.max_loss_usd;

  return (
    <div className="fixed inset-0 z-[300] bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-eyay-surface border border-eyay-border rounded-xl max-w-md w-full p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-mono font-bold text-eyay-text">
            Manuel Ekle · {position.side} {pair}
          </h3>
          <button onClick={onClose} className="text-eyay-faint hover:text-eyay-text text-xs">✕</button>
        </header>

        {/* Miktar preset */}
        <div>
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">Eklenecek miktar</p>
          <div className="flex flex-wrap gap-1.5">
            {ADD_PRESETS.map(v => (
              <button
                key={v}
                onClick={() => { setSize(v); setCustomSize(""); }}
                className={`text-[10px] font-mono px-2 py-1 rounded border ${
                  (!customSize && size === v)
                    ? "border-eyay-blue bg-eyay-blue/20 text-eyay-blue"
                    : "border-eyay-border text-eyay-faint hover:text-eyay-text"
                }`}
              >
                ${v}
              </button>
            ))}
            <input
              type="number"
              value={customSize}
              onChange={(e) => setCustomSize(e.target.value)}
              placeholder="Özel"
              className="text-[10px] font-mono px-2 py-1 rounded border border-eyay-border bg-eyay-raised text-eyay-text w-20"
            />
          </div>
        </div>

        {/* Sebep */}
        <div>
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">Ekleme nedeni</p>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full text-[11px] font-mono bg-eyay-raised border border-eyay-border rounded px-2 py-1 text-eyay-text"
          >
            {ADD_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>

        {/* Önizleme */}
        {preview && (
          <div className="rounded border border-eyay-border bg-eyay-raised/50 p-2 space-y-1 text-[10px] font-mono">
            <div className="flex items-center justify-between">
              <span className="text-eyay-faint">Durum</span>
              <StatusBadge status={preview.status} />
            </div>
            {beforeSize != null && afterSize != null && (
              <div className="flex justify-between">
                <span className="text-eyay-faint">Boyut</span>
                <span className="text-eyay-text">${beforeSize.toLocaleString()} → ${afterSize.toLocaleString()}</span>
              </div>
            )}
            {beforeAvg != null && afterAvg != null && (
              <div className="flex justify-between">
                <span className="text-eyay-faint">Ortalama entry</span>
                <span className="text-eyay-text">{beforeAvg.toFixed(4)} → {afterAvg.toFixed(4)}</span>
              </div>
            )}
            {beforeRR != null && afterRR != null && (
              <div className="flex justify-between">
                <span className="text-eyay-faint">R / R</span>
                <span className={`font-bold ${afterRR < 1 ? "text-red-300" : afterRR < beforeRR ? "text-amber-300" : "text-emerald-300"}`}>
                  1 : {beforeRR.toFixed(2)} → 1 : {afterRR.toFixed(2)}
                </span>
              </div>
            )}
            {maxLossBefore != null && maxLossAfter != null && (
              <div className="flex justify-between">
                <span className="text-eyay-faint">Max kayıp</span>
                <span className="text-red-300">{fmtUsdSigned(-maxLossBefore)} → {fmtUsdSigned(-maxLossAfter)}</span>
              </div>
            )}
            {preview.warnings && preview.warnings.length > 0 && (
              <div className="text-amber-300 pt-1 border-t border-eyay-border/40">
                ⚠ {preview.warnings.join(" · ")}
              </div>
            )}
            {preview.reason && (
              <p className="text-eyay-dim italic pt-1 border-t border-eyay-border/40">{preview.reason}</p>
            )}
          </div>
        )}

        {err && <p className="text-[10px] text-red-300">{err}</p>}

        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 text-[11px] font-mono py-1.5 rounded border border-eyay-border text-eyay-faint hover:text-eyay-text"
          >
            İptal
          </button>
          <button
            onClick={submit}
            disabled={busy || !preview?.allowed}
            className="flex-1 text-[11px] font-mono py-1.5 rounded border border-emerald-700 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/40 disabled:opacity-40"
          >
            {busy ? "Ekleniyor..." : "Onayla ve Ekle"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ManualRiskOverrideModal — SL/TP düzenleme
// ─────────────────────────────────────────────────────────────────────────────

const RISK_REASONS = [
  { value: "tighten_stop",      label: "Stop'u sıkılaştırmak istiyorum" },
  { value: "earlier_profit",    label: "Karı daha erken almak istiyorum" },
  { value: "structure_based",   label: "Teknik destek/direnç seviyesine göre ayarladım" },
  { value: "volatility_change", label: "Volatilite arttı" },
  { value: "manual_reduce_risk", label: "Manuel risk azaltma" },
  { value: "post_add_adjust",   label: "Parçalı alım sonrası planı güncelliyorum" },
  { value: "other",             label: "Diğer" },
];

function ManualRiskOverrideModal({
  pair, position, onClose, onSaved,
}: {
  pair: string;
  position: Position;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [sl, setSl] = useState<string>(String(position.stop_loss || ""));
  const [tp, setTp] = useState<string>(String(position.take_profit || ""));
  const [reason, setReason] = useState<string>(RISK_REASONS[0].value);
  const [busy, setBusy] = useState<boolean>(false);
  const [err, setErr] = useState<string | null>(null);

  // Türkçe locale comma desteği: "92,3282" → "92.3282"
  const _parseLocaleNum = (s: string) => Number(String(s).replace(",", "."));
  const slNum = _parseLocaleNum(sl) || 0;
  const tpNum = _parseLocaleNum(tp) || 0;
  const entry = position.average_entry_price || position.entry_price;
  const risk = Math.abs(entry - slNum);
  const reward = Math.abs(tpNum - entry);
  const newRR = risk > 0 ? reward / risk : 0;
  const slPct = entry > 0 ? Math.abs(((slNum - entry) / entry) * 100) : 0;
  const tpPct = entry > 0 ? Math.abs(((tpNum - entry) / entry) * 100) : 0;
  const dirOK = position.side === "LONG"
    ? (slNum < entry && entry < tpNum)
    : (tpNum < entry && entry < slNum);

  async function submit() {
    if (!dirOK) { setErr(`Yön hatalı: ${position.side} için SL/TP konumu yanlış`); return; }
    if (slNum <= 0 || tpNum <= 0) { setErr("SL ve TP pozitif olmalı"); return; }
    setBusy(true); setErr(null);
    try {
      const r = await patchJSON(
        `/api/backend/trading/positions/${pair}/risk-plan`,
        { new_stop_loss: slNum, new_take_profit: tpNum, reason },
      );
      if (r?.status === "overridden") {
        onSaved();
        onClose();
      } else {
        setErr(r?.reason || r?.status || "Bilinmeyen hata");
      }
    } catch (e) {
      setErr(String(e).slice(0, 140));
    } finally {
      setBusy(false);
    }
  }

  async function resetAuto() {
    setBusy(true); setErr(null);
    try {
      const r = await postJSON(
        `/api/backend/trading/positions/${pair}/risk-plan/reset`, {},
      );
      if (r?.status === "reset") {
        onSaved();
        onClose();
      } else if (r?.status === "no_override") {
        onClose();
      } else {
        setErr(r?.reason || r?.status || "Bilinmeyen hata");
      }
    } catch (e) {
      setErr(String(e).slice(0, 140));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[300] bg-black/70 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-eyay-surface border border-eyay-border rounded-xl max-w-md w-full p-4 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-mono font-bold text-eyay-text">
            SL/TP Düzenle · {position.side} {pair}
          </h3>
          <button onClick={onClose} className="text-eyay-faint hover:text-eyay-text text-xs">✕</button>
        </header>

        <div className="space-y-2 text-[11px] font-mono">
          <div className="flex justify-between text-eyay-faint">
            <span>Entry (ortalama)</span>
            <span className="text-eyay-text">{entry.toFixed(4)}</span>
          </div>
          <div className="flex justify-between text-eyay-faint">
            <span>Mevcut SL</span>
            <span className="text-red-300">{position.stop_loss.toFixed(4)}</span>
          </div>
          <div className="flex justify-between text-eyay-faint">
            <span>Mevcut TP</span>
            <span className="text-emerald-300">{position.take_profit.toFixed(4)}</span>
          </div>
        </div>

        <div>
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">Yeni SL</p>
          <input
            type="number"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            className="w-full text-[11px] font-mono bg-eyay-raised border border-eyay-border rounded px-2 py-1 text-eyay-text"
          />
        </div>
        <div>
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">Yeni TP</p>
          <input
            type="number"
            value={tp}
            onChange={(e) => setTp(e.target.value)}
            className="w-full text-[11px] font-mono bg-eyay-raised border border-eyay-border rounded px-2 py-1 text-eyay-text"
          />
        </div>

        <div className="rounded border border-eyay-border bg-eyay-raised/50 p-2 space-y-1 text-[10px] font-mono">
          <div className="flex justify-between">
            <span className="text-eyay-faint">Stop mesafesi</span>
            <span className={slPct < 0.5 ? "text-amber-300" : "text-eyay-text"}>
              {position.side === "LONG" ? "-" : "+"}{slPct.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-eyay-faint">Hedef mesafesi</span>
            <span className={tpPct < 0.5 ? "text-amber-300" : "text-eyay-text"}>
              {position.side === "LONG" ? "+" : "-"}{tpPct.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-eyay-faint">Yeni R/R</span>
            <span className={`font-bold ${newRR < 1 ? "text-red-300" : newRR < 1.5 ? "text-amber-300" : "text-emerald-300"}`}>
              1 : {newRR.toFixed(2)}
            </span>
          </div>
          {!dirOK && (
            <p className="text-red-300 pt-1 border-t border-eyay-border/40">
              ⚠ {position.side} pozisyonu için SL/TP yön sırası hatalı
            </p>
          )}
          {newRR < 1 && dirOK && (
            <p className="text-red-300 pt-1 border-t border-eyay-border/40">
              ⚠ R/R 1:1 altında — yüksek risk
            </p>
          )}
        </div>

        <div>
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">Değişiklik nedeni</p>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full text-[11px] font-mono bg-eyay-raised border border-eyay-border rounded px-2 py-1 text-eyay-text"
          >
            {RISK_REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>

        {err && <p className="text-[10px] text-red-300">{err}</p>}

        <div className="flex gap-2">
          {position.manual_risk_override?.is_manual_override && (
            <button
              onClick={resetAuto}
              disabled={busy}
              className="flex-1 text-[10px] font-mono py-1.5 rounded border border-sky-700 bg-sky-950/40 text-sky-300 hover:bg-sky-900/40 disabled:opacity-40"
            >
              Otomatik Plana Dön
            </button>
          )}
          <button
            onClick={onClose}
            className="flex-1 text-[11px] font-mono py-1.5 rounded border border-eyay-border text-eyay-faint hover:text-eyay-text"
          >
            İptal
          </button>
          <button
            onClick={submit}
            disabled={busy || !dirOK}
            className="flex-1 text-[11px] font-mono py-1.5 rounded border border-emerald-700 bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/40 disabled:opacity-40"
          >
            {busy ? "Kaydediliyor..." : "Onayla"}
          </button>
        </div>
      </div>
    </div>
  );
}

function OpenPositionCard({
  position: p,
  pattern,
  isClosing,
  onClose,
  onRefresh,
}: {
  position: Position;
  pattern?: ChartPatternSummary;
  isClosing: boolean;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [addOpen, setAddOpen]   = useState(false);
  const [riskOpen, setRiskOpen] = useState(false);
  const [explExpanded, setExplExpanded] = useState(false);
  // Hotfix accordion'ları — default kapalı. Kullanıcı talebi:
  //   ilk bakışta açık pozisyonun temel bilgileri görünür kalmalı;
  //   pozisyon boyutu/SL-TP düzenleme ve açılma sebebi ihtiyaç hâlinde açılır.
  const [addPlanOpen, setAddPlanOpen]   = useState(false);
  const [explanOpen, setExplanOpen]     = useState(false);
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
      <header className="flex items-start justify-between gap-2 px-3 py-2.5 bg-eyay-surface/40 border-b border-eyay-border/40">
        <div className="flex items-center gap-2 min-w-0 flex-wrap">
          <span className={`text-sm font-black ${sideTextClr}`}>
            {p.side === "LONG" ? "▲" : "▼"} {p.pair}
          </span>
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider border ${sideBadgeClr}`}>
            {p.side}
          </span>
          <span
            className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider border ${sourceBadgeClr}`}
            title={sourceTooltip}
          >
            {isManual ? "MANUEL" : "PAPER"}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div
            className={`text-right px-2 py-1 rounded border ${pnlBadgeClr}`}
            title="Açılış fiyatından bu yana gerçekleşmemiş kâr/zarar."
          >
            <span className="block text-sm font-black leading-tight">{fmtUsd(p.pnl_usd)}</span>
            <span className="block text-[10px] leading-tight opacity-90">
              {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct.toFixed(2)}%
            </span>
          </div>
          <button
            onClick={onClose}
            disabled={isClosing}
            title="Pozisyonu anlık fiyattan elle kapat"
            className="text-[9px] font-bold border border-red-800/50 text-red-300 hover:text-red-100 hover:bg-red-900/40 hover:border-red-600/60 px-2 py-1 rounded transition-colors disabled:opacity-40 leading-tight whitespace-nowrap"
          >
            {isClosing ? "···" : "Kapat"}
          </button>
        </div>
      </header>

      {/* ────────────── B + C : 2-col on desktop, 1-col on mobile ────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 p-2.5">
        {/* B) Pozisyon Özeti */}
        <section className="bg-eyay-surface/30 rounded-md p-2.5 border border-eyay-border/40">
          <h4 className="text-[9px] uppercase tracking-wider text-eyay-faint mb-2 font-semibold">
            Pozisyon Özeti
          </h4>
          <dl className="space-y-1.5 text-[11px]">
            <CardRow label="Entry" value={fmt2(p.entry_price)} valueClass="text-eyay-text font-semibold" />
            <CardRow
              label="Anlık Fiyat"
              value={p.current_price > 0 ? `$${fmt2(p.current_price)}` : "—"}
              valueClass="text-sky-300 font-semibold"
            />
            <CardRow
              label="Boyut"
              value={p.size_usd != null ? `$${fmt0(p.size_usd)}` : "—"}
              valueClass="text-eyay-text font-semibold"
            />
            <CardRow
              label="TF"
              labelTip="Sinyalin üretildiği ana zaman dilimi."
              value={tf}
              valueClass="text-eyay-text font-semibold"
            />
            <CardRow label="Hedeflenen Pozisyon Süresi" value={horizonText} valueClass="text-eyay-text font-semibold" />
          </dl>
        </section>

        {/* C) Risk Planı */}
        <section className="bg-eyay-surface/30 rounded-md p-2.5 border border-eyay-border/40">
          <h4 className="text-[9px] uppercase tracking-wider text-eyay-faint mb-2 font-semibold">
            Risk Planı
          </h4>
          <dl className="space-y-1.5 text-[11px]">
            <CardRow
              label="Stop Loss"
              labelTip="Fiyat buraya gelirse zarar sınırlamak için kapanır."
              value={p.stop_loss > 0 ? `${fmt2(p.stop_loss)} (${slPct!.toFixed(1)}%)` : "—"}
              valueClass="text-red-300 font-semibold"
            />
            <CardRow
              label="Take Profit"
              labelTip="Fiyat buraya gelirse hedef kâr alınır."
              value={p.take_profit > 0 ? `${fmt2(p.take_profit)} (+${tpPct!.toFixed(1)}%)` : "—"}
              valueClass="text-emerald-300 font-semibold"
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
              valueClass="text-sky-300 font-semibold"
            />
          </dl>
          {slBasis && (
            <p className="mt-2 pt-2 border-t border-eyay-border/30 text-[10px] text-eyay-faint">
              Stop mantığı: <span className="text-eyay-dim">{slBasis}</span>
            </p>
          )}
        </section>
      </div>

      {/* ────────────── Pozisyon Boyutu / SL-TP Düzenle (accordion) ────────────── */}
      {p.add_plan && (
        <section className="mx-2 mb-2 bg-eyay-surface/20 rounded border border-eyay-border/30">
          <button
            type="button"
            onClick={() => setAddPlanOpen((v) => !v)}
            className="w-full flex items-center justify-between gap-2 px-2.5 py-2 hover:bg-eyay-surface/30"
          >
            <h4 className="text-[11px] font-semibold text-eyay-text truncate">
              ⚙ Pozisyon Boyutu / SL-TP Düzenle
            </h4>
            <span className="flex items-center gap-2 shrink-0">
              <span className="text-[10px] font-mono text-eyay-faint">
                Mod: {p.add_plan.mode === "off" ? "Kapalı" : p.add_plan.mode === "manual" ? "Manuel" : "Paper Auto"}
                {" · Kalan ekleme: "}
                <span className={p.add_plan.remaining_add_capacity_usd > 0 ? "text-emerald-300" : "text-eyay-faint"}>
                  ${p.add_plan.remaining_add_capacity_usd.toLocaleString()}
                </span>
              </span>
              <span className="text-eyay-faint text-[10px]">{addPlanOpen ? "▴" : "▾"}</span>
            </span>
          </button>
          {addPlanOpen && (
            <div className="px-2 pb-2 border-t border-eyay-border/30 pt-2">
              <dl className="space-y-0.5 text-[10px]">
                <CardRow label="Mevcut boyut" value={`$${p.add_plan.current_size_usd.toLocaleString()}`} valueClass="text-eyay-text" />
                <CardRow label="Maksimum pozisyon" value={`$${p.add_plan.max_position_size_usd.toLocaleString()}`} valueClass="text-eyay-text" />
                <CardRow
                  label="Kalan ekleme hakkı"
                  value={`$${p.add_plan.remaining_add_capacity_usd.toLocaleString()}`}
                  valueClass={p.add_plan.remaining_add_capacity_usd > 0 ? "text-emerald-300" : "text-eyay-faint"}
                />
                <CardRow label="Ortalama entry" value={p.add_plan.average_entry_price.toFixed(4)} valueClass="text-eyay-text" />
              </dl>
              {p.add_plan.add_levels.length > 0 && (
                <div className="mt-2 pt-2 border-t border-eyay-border/30 space-y-1">
                  <p className="text-[8px] uppercase tracking-wider text-eyay-faint">Ekleme Seviyeleri</p>
                  {p.add_plan.add_levels.map((lv, i) => (
                    <div key={lv.id || i} className="flex items-center justify-between gap-2 text-[10px] font-mono">
                      <span className="text-eyay-text truncate">
                        {lv.trigger_price ? lv.trigger_price.toFixed(2) : "—"} → +${lv.add_size_usd.toLocaleString()}
                        {lv.condition_text && <span className="text-eyay-faint"> · {lv.condition_text}</span>}
                      </span>
                      <StatusBadge status={lv.status} />
                    </div>
                  ))}
                </div>
              )}
              {p.add_plan.last_control_result?.reason && (
                <p className="text-[9px] text-eyay-dim italic mt-1.5 leading-snug">
                  Son kontrol: {p.add_plan.last_control_result.reason}
                </p>
              )}
              <div className="flex gap-1.5 mt-2">
                <button
                  onClick={() => setAddOpen(true)}
                  disabled={p.add_plan.mode === "off" || p.add_plan.remaining_add_capacity_usd <= 0}
                  className="text-[9px] font-mono px-2 py-1 rounded border border-emerald-700/70 bg-emerald-950/30 text-emerald-300 hover:bg-emerald-900/40 disabled:opacity-40"
                >
                  Manuel Ekle
                </button>
                <button
                  onClick={() => setRiskOpen(true)}
                  className="text-[9px] font-mono px-2 py-1 rounded border border-eyay-border text-eyay-faint hover:text-eyay-text hover:border-eyay-blue/60"
                >
                  SL/TP Düzenle
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* ────────────── Manuel Risk Override notu (varsa ince satır) ────────────── */}
      {p.manual_risk_override?.is_manual_override && (
        <div className="mx-2 mb-2 px-2 py-1 rounded border border-violet-800/50 bg-violet-950/20 text-[10px] font-mono text-violet-300/90">
          Manuel Risk Planı · R/R {p.manual_risk_override.previous_rr.toFixed(2)}
          {" → "}{p.manual_risk_override.new_rr.toFixed(2)}
          {p.manual_risk_override.reason && (
            <span className="text-eyay-dim"> · {p.manual_risk_override.reason}</span>
          )}
          {p.manual_risk_override.warnings && p.manual_risk_override.warnings.length > 0 && (
            <span className="text-amber-300"> · ⚠ {p.manual_risk_override.warnings[0]}</span>
          )}
        </div>
      )}

      {/* ────────────── İşlem Açılma Sebebi (accordion) ────────────── */}
      {(p.opening_explanation || p.open_signal) && (
        <section className="mx-2 mb-2 bg-eyay-surface/20 rounded border border-eyay-border/30">
          <button
            type="button"
            onClick={() => setExplanOpen((v) => !v)}
            className="w-full flex items-center justify-between gap-2 px-2 py-1.5 hover:bg-eyay-surface/30"
          >
            <h4 className="text-[10px] font-mono text-eyay-text/90 truncate">
              📖 İşlem Açılma Sebebi
            </h4>
            <span className="flex items-center gap-1.5 shrink-0">
              {!explanOpen && (
                <span className="text-[9px] font-mono text-eyay-faint truncate max-w-xs">
                  {p.open_signal
                    ? (() => {
                        const tfEval = buildTimeframeEval(p.open_signal);
                        const hasNews = p.open_signal.news && p.open_signal.news.length > 0;
                        return `Teknik: ${tfEval.summary} · Haber: ${hasNews ? "var" : "kayıt yok"} · ${p.opening_explanation ? "Açıklama var" : "kayıt yok"}`;
                      })()
                    : "kayıt yok"}
                </span>
              )}
              <span className="text-eyay-faint text-[9px]">{explanOpen ? "▴" : "▾"}</span>
            </span>
          </button>
          {explanOpen && (
            <div className="px-2 pb-2 border-t border-eyay-border/30 pt-2 space-y-2.5 text-[11px]">
              {/* A) Consensus Skoru Nasıl Oluştu */}
              <div>
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">A) Consensus Skoru</p>
                {p.open_signal ? (
                  <>
                    <pre className="text-[10px] text-eyay-text/90 leading-snug whitespace-pre-wrap font-mono">
                      {buildConsensusExplanation(p.open_signal)}
                    </pre>
                    {/* Modül katkıları */}
                    {buildModuleScores(p.open_signal) && (
                      <p className="text-[9px] text-eyay-faint mt-1 leading-snug">
                        Modül katkıları: {buildModuleScores(p.open_signal)}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-[10px] text-eyay-faint">Kayıt yok.</p>
                )}
              </div>

              {/* B) Timeframe Değerlendirmesi */}
              <div>
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">B) Timeframe Değerlendirmesi</p>
                {p.open_signal ? (() => {
                  const tfEval = buildTimeframeEval(p.open_signal);
                  return (
                    <>
                      <table className="w-full text-[10px] font-mono border-collapse">
                        <thead>
                          <tr className="text-eyay-faint text-[8px] uppercase tracking-wider">
                            <th className="text-left pb-1 pr-2 w-8">TF</th>
                            <th className="text-left pb-1 pr-2 w-16">Yön</th>
                            <th className="text-left pb-1 pr-2 w-16">Skor</th>
                            <th className="text-left pb-1">Not</th>
                          </tr>
                        </thead>
                        <tbody className="space-y-0.5">
                          {tfEval.details.map(d => (
                            <tr key={d.tf} className={d.direction === "bullish" ? "text-emerald-300/90" : d.direction === "bearish" ? "text-red-300/90" : "text-eyay-faint"}>
                              <td className="pr-2 align-top">{d.tf}</td>
                              <td className="pr-2 align-top">{d.direction}</td>
                              <td className="pr-2 align-top">{d.score !== "—" ? `${d.score}/100` : "—"}</td>
                              <td className="text-eyay-faint text-[9px] align-top">{d.note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="text-[9px] text-eyay-dim italic mt-1.5">
                        💡 {
                          tfEval.details.filter(d => d.direction === "bullish").length >= 2 ? "Birden fazla TF bullish — confluence işlem yönünü destekledi." :
                          tfEval.details.filter(d => d.direction === "bearish").length >= 2 ? "Kısa vadeler karşı sinyal veriyor; risk kontrollü izlemeli." :
                          "TF uyumu zayıf; manuel karar için 4H ve 1H kapanışlarını izlemeli."
                        }
                      </p>
                      {/* TF anlamı — üç farklı TF kavramı */}
                      <div className="mt-1.5 pt-1.5 border-t border-eyay-border/30 text-[9px] text-eyay-faint space-y-0.5">
                        {p.open_signal?.primary_tf && (
                          <p>Sinyal TF: <span className="text-eyay-dim">{p.open_signal.primary_tf.toUpperCase()}</span> (agent bu TF'de sinyal üretti)</p>
                        )}
                        {p.open_signal?.timeframe_decision?.selected_timeframe && (
                          <p>İzleme TF: <span className="text-eyay-dim">{p.open_signal.timeframe_decision.selected_timeframe.toUpperCase()}</span> (aggression → monitoring)</p>
                        )}
                        {p.risk_plan?.timeframe && (
                          <p>Risk TF: <span className="text-eyay-dim">{p.risk_plan.timeframe.toUpperCase()}</span> (SL/TP/horizon hesabı için)</p>
                        )}
                      </div>
                    </>
                  );
                })() : (
                  <p className="text-[10px] text-eyay-faint">Kayıt yok.</p>
                )}
              </div>

              {/* C) Manuel Takip Notu */}
              <div>
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">C) Manuel Takip Notu</p>
                <p className="text-[10px] text-eyay-text/90 leading-snug">
                  {buildManualFollowNote(p.open_signal)}
                </p>
              </div>

              {/* D) Haber / Event Etkisi */}
              <div>
                <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-wider mb-1">D) Haber / Event Etkisi</p>
                <p className="text-[10px] text-eyay-text/90 leading-snug">
                  {buildNewsImpact(p.open_signal)}
                </p>
              </div>

              {/* E) Karar Özeti (açıklama varsa) */}
              {p.opening_explanation?.primary_reason && (
                <div>
                  <p className="text-[9px] font-mono text-emerald-300/80 uppercase tracking-wider mb-1">E) Karar Özeti</p>
                  <p className="text-[10px] text-eyay-text/90 leading-snug italic">
                    {p.opening_explanation.primary_reason}
                  </p>
                </div>
              )}
            </div>
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

      {/* ────────────── Modallar ────────────── */}
      {addOpen && (
        <AddToPositionModal
          pair={p.pair}
          position={p}
          onClose={() => setAddOpen(false)}
          onAdded={onRefresh}
        />
      )}
      {riskOpen && (
        <ManualRiskOverrideModal
          pair={p.pair}
          position={p}
          onClose={() => setRiskOpen(false)}
          onSaved={onRefresh}
        />
      )}
    </article>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// İşlem Açılma Sebebi — helper fonksiyonları
// ─────────────────────────────────────────────────────────────────────────────

// Timeframe eval — tf_signals + confluence.tf_directions okur
function buildTimeframeEval(openSignal: Position["open_signal"]): {
  summary: string;
  details: Array<{ tf: string; direction: string; score: string; note: string }>;
} {
  const tfSigs = openSignal?.tf_signals ?? {};
  const tfDirs = openSignal?.confluence?.tf_directions ?? {};
  const primaryTf = openSignal?.primary_tf ?? "";

  const details = ["15m", "1h", "4h", "1d"].map(tf => {
    const sig = tfSigs[tf];
    if (!sig) {
      const note = tf === "15m" ? "sistem 15m sinyal hesaplamıyor" : "kayıt yok";
      return { tf, direction: "—", score: "—", note };
    }
    const dir = sig.direction ?? tfDirs[tf] ?? "—";
    const score = sig.consensus_score != null ? sig.consensus_score.toFixed(1) : "—";
    const isPrimary = tf === primaryTf ? "sinyal TF" : "";
    const confDir = tfDirs[tf];
    const isConfluence = confDir && confDir !== "neutral" && tf !== primaryTf
      ? `confluence: ${confDir}` : "";
    const noteParts = [isPrimary, isConfluence].filter(Boolean);
    return { tf, direction: dir, score, note: noteParts.join(" · ") };
  });

  const bullish = details.filter(d => d.direction === "bullish").length;
  const bearish = details.filter(d => d.direction === "bearish").length;
  const summary = bullish >= 2 ? "Bullish uyum" : bearish >= 2 ? "Bearish uyum" : "Mixed/nötr";
  return { summary, details };
}

// Consensus skoru nasıl oluştu — base × confluence multiplier
function buildConsensusExplanation(openSignal: Position["open_signal"]): string {
  const conf = openSignal?.confluence;
  const base = openSignal?.base;
  if (!conf && !base) return "Kayıt yok.";

  const baseScore = conf?.original_score ?? base?.consensus_score;
  const finalScore = conf?.adjusted_score ?? openSignal?.final_score;
  const mult = conf?.multiplier ?? 1.0;
  const status = conf?.status ?? "unknown";
  const primaryTf = openSignal?.primary_tf ?? "?";

  const lines: string[] = [];
  lines.push(`Temel TF: ${primaryTf} → Base skor: ${baseScore?.toFixed(1) ?? "—"}`);

  if (status === "aligned") {
    const aligned = Object.entries(conf?.tf_directions ?? {})
      .filter(([, v]) => v !== "neutral")
      .map(([k, v]) => `${k}:${v}`)
      .join(" + ");
    lines.push(`Confluence: ${aligned} uyumu → ×${mult} → Final skor: ${finalScore?.toFixed(1) ?? "—"}`);
  } else if (status === "skipped") {
    lines.push(`Confluence skip (higher TF'ler nötr) → Çarpan uygulanmadı → Final skor: ${finalScore?.toFixed(1) ?? "—"}`);
  } else if (status === "opposing") {
    lines.push(`Confluence karşı sinyal (×${mult}) → Final skor: ${finalScore?.toFixed(1) ?? "—"}`);
  }

  const votes = conf?.vote_count;
  if (votes) {
    lines.push(`Oy: ${votes.aligned} uyumlu · ${votes.opposing} karşı · ${votes.neutral_ignored} nötr (sayılmadı)`);
  }

  const warnings = conf?.warnings ?? base?.["warnings" as keyof typeof base];
  if (Array.isArray(warnings) && warnings.length > 0) {
    lines.push(`⚠ ${(warnings as string[]).join(" · ")}`);
  }

  return lines.join("\n");
}

// Modül skorları — açıklayıcı satır
function buildModuleScores(openSignal: Position["open_signal"]): string | null {
  const scores = openSignal?.base?.module_scores;
  if (!scores || Object.keys(scores).length === 0) return null;
  const parts = Object.entries(scores).map(([mod, score]) =>
    `${mod}: ${typeof score === "number" ? score.toFixed(1) : score}`
  );
  return parts.join(" · ");
}

// Manuel takip notu — timeframe_decision + aggression
function buildManualFollowNote(openSignal: Position["open_signal"]): string {
  const td = openSignal?.timeframe_decision;
  const ac = openSignal?.aggression_context;

  if (!td && !ac) return "Kayıt yok.";

  const parts: string[] = [];
  if (td?.selected_timeframe) {
    parts.push(`İzleme TF: ${td.selected_timeframe.toUpperCase()}`);
    if (td.reason) parts.push(`(${td.reason})`);
    if (td.max_holding_time) parts.push(`Max tutuş: ${td.max_holding_time}`);
    if (td.recheck_interval_minutes) parts.push(`Recheck: ${td.recheck_interval_minutes} dk`);
  } else if (ac?.recommended_timeframe) {
    parts.push(`Önerilen TF: ${ac.recommended_timeframe.toUpperCase()}`);
    if (ac.max_holding_time) parts.push(`Max tutuş: ${ac.max_holding_time}`);
  }
  return parts.join(" · ");
}

// Haber/Event etkisi
function buildNewsImpact(openSignal: Position["open_signal"]): string {
  if (!openSignal?.news || openSignal.news.length === 0) {
    return "Bu pozisyonun açılış snapshot'ında trade'i doğrudan tetikleyen doğrulanmış haber kaydı yok. Karar teknik yapı ve timeframe uyumu üzerinden oluştu.";
  }
  return openSignal.news.join("\n");
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
        className="text-[10px] text-eyay-dim shrink-0 truncate"
        title={labelTip}
      >
        {labelTip ? <span className="border-b border-dotted border-eyay-faint/40">{label}</span> : label}
      </dt>
      <dd className={`text-right truncate font-mono ${valueClass}`}>{value}</dd>
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
