"use client";

import { useEffect, useState } from "react";
import type { AssetSignal, AssetActionType, SignalStatus, TechnicalInsight } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";
import MiniChart, { type ChartTFView } from "./MiniChart";

// ---------------------------------------------------------------------------
// 5 Komut Sinyali — büyük kartlar
// ---------------------------------------------------------------------------

const PRIMARY_SIGNALS = [
  { code: "BTCUSD",    icon: "₿"  },
  { code: "XAUUSD",    icon: "◆"  },
  { code: "XAGUSD",    icon: "🥈" },
  { code: "XCUUSD",    icon: "🔧" },
  { code: "BRENT",     icon: "⚡" },
];

// ---------------------------------------------------------------------------
// 14 İkincil Sinyal — kompakt kartlar
// ---------------------------------------------------------------------------

const SECONDARY_SIGNALS = [
  { code: "XAUXAG",     icon: "⚖️" },
  { code: "SP500",      icon: "📈" },
  { code: "DXY",        icon: "💵" },
  { code: "VIX",        icon: "⚠"  },
  { code: "HY_SPREAD",  icon: "📊" },
  { code: "HYG",        icon: "🏦" },
  { code: "QQQ",        icon: "💻" },
  { code: "REAL_YIELD", icon: "📉" },
  { code: "ETHUSD",     icon: "Ξ"  },
  { code: "IWM",        icon: "🏭" },
  { code: "LQD",        icon: "📋" },
  { code: "SMH",        icon: "⚙️" },
  { code: "XLF",        icon: "🏛" },
  { code: "FXI",        icon: "🇨🇳" },
];

// ---------------------------------------------------------------------------
// Style maps
// ---------------------------------------------------------------------------

const STATUS_STYLE: Record<SignalStatus, {
  dot: string; dotAnim?: string;
  badge: string; cardBorder: string; cardBg: string; priceColor: string;
}> = {
  CONFIRMED: {
    dot: "bg-emerald-400",
    badge: "bg-emerald-950 text-emerald-300 border-emerald-800/60",
    cardBorder: "border-emerald-900/50", cardBg: "bg-emerald-950/10",
    priceColor: "text-emerald-300",
  },
  PENDING: {
    dot: "bg-amber-400",
    badge: "bg-amber-950 text-amber-300 border-amber-800/60",
    cardBorder: "border-eyay-border", cardBg: "bg-eyay-raised",
    priceColor: "text-amber-300",
  },
  BLOCKING: {
    dot: "bg-red-400", dotAnim: "animate-pulse",
    badge: "bg-red-950 text-red-300 border-red-800/60",
    cardBorder: "border-red-900/70", cardBg: "bg-red-950/20",
    priceColor: "text-red-300",
  },
  NEUTRAL: {
    dot: "bg-eyay-muted",
    badge: "bg-eyay-raised text-eyay-faint border-eyay-border",
    cardBorder: "border-eyay-border", cardBg: "bg-eyay-raised",
    priceColor: "text-eyay-dim",
  },
  "VERİ_YOK": {
    dot: "bg-eyay-border",
    badge: "bg-eyay-raised text-eyay-faint border-eyay-border",
    cardBorder: "border-eyay-border/50", cardBg: "bg-eyay-raised/50",
    priceColor: "text-eyay-faint",
  },
};

// ---------------------------------------------------------------------------
// Action chip styles
// ---------------------------------------------------------------------------

const ACTION_STYLE: Record<AssetActionType, {
  label: string;
  classes: string;
  dot?: string;
}> = {
  LONG:        { label: "LONG",       classes: "text-emerald-300 border-emerald-800/70 bg-emerald-950/50",  dot: "bg-emerald-400" },
  LONG_AWAIT:  { label: "LONG SETUP", classes: "text-amber-300   border-amber-800/70   bg-amber-950/40",    dot: "bg-amber-400" },
  SHORT:       { label: "SHORT",      classes: "text-red-300     border-red-800/70     bg-red-950/50",       dot: "bg-red-400" },
  SHORT_AWAIT: { label: "SHORT SETUP",classes: "text-orange-300  border-orange-800/70  bg-orange-950/40",   dot: "bg-orange-400" },
  HOLD:        { label: "KORU",       classes: "text-sky-300     border-sky-800/70     bg-sky-950/40",       dot: "bg-sky-400" },
  AVOID:       { label: "KAÇIN",      classes: "text-red-400     border-red-900/80     bg-red-950/60",       dot: "bg-red-500" },
  NEUTRAL:     { label: "NÖTR",       classes: "text-eyay-faint  border-eyay-border    bg-eyay-raised/50",   dot: undefined },
};

function ActionChip({ action, trigger, size = "md" }: { action: AssetActionType; trigger?: string; size?: "sm" | "md" }) {
  if (action === "NEUTRAL") return null;
  const s = ACTION_STYLE[action];
  const textSize = size === "sm" ? "text-[8px]" : "text-[9px]";
  return (
    <div
      className={`flex items-center gap-1 px-1.5 py-0.5 rounded border font-mono ${textSize} font-bold shrink-0 leading-none ${s.classes}`}
      title={trigger || undefined}
    >
      {s.dot && <span className={`w-1 h-1 rounded-full flex-shrink-0 ${s.dot}`} />}
      {s.label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatPrice(value: number, unit: string): string {
  if (unit.includes("%") || unit === "pct" || unit === "yield_percent" || unit === "spread_percent")
    return `%${value.toFixed(2)}`;
  if (value > 999_999) return `$${(value / 1_000_000).toFixed(2)}T`;
  if (value > 9_999)   return `$${value.toLocaleString("tr-TR", { maximumFractionDigits: 0 })}`;
  if (value > 999)     return `$${value.toFixed(0)}`;
  if (value < 0.01)    return `${value.toFixed(4)}`;
  return `${value.toFixed(2)}`;
}

function DeltaBadge({ delta, size = "md" }: { delta: number | null; size?: "sm" | "md" }) {
  if (delta === null || delta === undefined) return null;
  const isPos = delta > 0;
  const abs   = Math.abs(delta).toFixed(1);
  const base  = size === "sm" ? "text-[9px]" : "text-xs";
  return (
    <span className={`font-mono font-semibold ${base} ${isPos ? "text-emerald-400" : delta < 0 ? "text-red-400" : "text-eyay-faint"}`}>
      {isPos ? "▲" : delta < 0 ? "▼" : "≈"} {abs}%
    </span>
  );
}

// ---------------------------------------------------------------------------
// Primary Command Card — büyük
// ---------------------------------------------------------------------------

interface ChartReading {
  asset_code: string;
  ticker: string;
  primary_tf: string;
  alignment: string;
  alignment_pct: number;
  summary: string;
  timeframes: ChartTFView[];
  error?: string | null;
}

function CommandCard({
  signal, icon, statusLabel, techInsight,
}: {
  signal: AssetSignal;
  icon: string;
  statusLabel: string;
  techInsight?: TechnicalInsight;
}) {
  const st = STATUS_STYLE[signal.status];
  const [flipped, setFlipped] = useState(false);
  const [reading, setReading] = useState<ChartReading | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTf, setActiveTf] = useState<string>("1d");
  const [err, setErr] = useState<string | null>(null);

  // İlk flip'te chart fetch et
  useEffect(() => {
    if (!flipped || reading) return;
    let cancel = false;
    setLoading(true);
    setErr(null);
    fetch(`/api/backend/agent/chart/${signal.asset_code}?timeframes=1h,4h,1d`, { cache: "no-store" })
      .then(r => r.json())
      .then(d => {
        if (cancel) return;
        const r2 = d?.reading as ChartReading | undefined;
        if (!r2 || !r2.timeframes?.length) {
          setErr(d?.reading?.summary || "Veri yok");
          setLoading(false);
          return;
        }
        setReading(r2);
        setActiveTf(r2.primary_tf || r2.timeframes[0].timeframe);
        setLoading(false);
      })
      .catch(e => {
        if (cancel) return;
        setErr(String(e).slice(0, 140));
        setLoading(false);
      });
    return () => { cancel = true; };
  }, [flipped, reading, signal.asset_code]);

  const view = reading?.timeframes?.find(v => v.timeframe === activeTf) || reading?.timeframes?.[0];

  const cardBaseCls = `border ${st.cardBorder} ${st.cardBg} rounded-xl flex flex-col gap-2 absolute inset-0 backface-hidden`;

  return (
    <div className="relative" style={{ perspective: "1000px", minHeight: "260px" }}>
      <div
        className="relative w-full h-full transition-transform duration-500"
        style={{
          transformStyle: "preserve-3d",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
          minHeight: "260px",
        }}
      >
        {/* ── ÖN YÜZ ─────────────────────────────────────────────────────────── */}
        <div
          className={`${cardBaseCls} p-3.5 cursor-pointer transition-all duration-200 hover:brightness-110`}
          style={{ backfaceVisibility: "hidden" }}
          onClick={() => setFlipped(true)}
          role="button"
          tabIndex={0}
          aria-label={`${signal.asset_code} kartını çevir`}
          onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFlipped(true); } }}
        >
          <div className="flex items-start justify-between gap-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-sm leading-none">{icon}</span>
              <p className="font-mono font-bold text-xs text-eyay-text tracking-wide truncate">
                {signal.asset_code}
              </p>
            </div>
            <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-[9px] font-semibold shrink-0 ${st.badge}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${st.dot} ${st.dotAnim ?? ""}`} />
              {statusLabel}
            </div>
          </div>

          {signal.value !== null ? (
            <div className="flex flex-col gap-0.5">
              {techInsight && (() => {
                const broken = signal.value >= techInsight.levels.resistance;
                return (
                  <p className={`text-[9px] font-mono whitespace-nowrap ${broken ? "text-emerald-400" : "text-eyay-faint/50"}`}>
                    R {formatPrice(techInsight.levels.resistance, signal.unit)}{broken ? " ↑" : ""}
                  </p>
                );
              })()}
              <div>
                <p className={`font-mono font-black text-xl leading-none ${st.priceColor}`}>
                  {formatPrice(signal.value, signal.unit)}
                </p>
                <p className="text-[9px] font-mono text-eyay-faint mt-0.5">{signal.unit}</p>
              </div>
              {techInsight && (() => {
                const broken = signal.value <= techInsight.levels.support;
                return (
                  <p className={`text-[9px] font-mono whitespace-nowrap ${broken ? "text-red-400" : "text-eyay-faint/50"}`}>
                    S {formatPrice(techInsight.levels.support, signal.unit)}{broken ? " ↓" : ""}
                  </p>
                );
              })()}
            </div>
          ) : (
            <p className="text-xs text-eyay-faint font-mono">—</p>
          )}

          <div className="flex items-center justify-between gap-1">
            <DeltaBadge delta={signal.delta_7d_pct} size="md" />
            {signal.asset_action && signal.asset_action !== "NEUTRAL" && (
              <ActionChip action={signal.asset_action} trigger={signal.action_trigger} />
            )}
          </div>

          {signal.action_trigger && signal.asset_action && signal.asset_action !== "NEUTRAL" && (
            <p className="text-[9px] text-eyay-faint/70 font-mono leading-snug italic">
              {signal.action_trigger}
            </p>
          )}

          <p className="text-[10px] text-eyay-dim leading-snug line-clamp-2 border-t border-white/5 pt-2">
            {signal.reason.replace(/\s*\[S:[^\]]+\]/g, "")}
          </p>

          <p className="text-[9px] text-eyay-faint/60 italic text-center mt-auto">
            ⤺ grafiği görmek için tıkla
          </p>
        </div>

        {/* ── ARKA YÜZ ───────────────────────────────────────────────────────── */}
        <div
          className={`${cardBaseCls} p-2.5 cursor-pointer`}
          style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
          onClick={() => setFlipped(false)}
        >
          <div className="flex items-center justify-between gap-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-sm">{icon}</span>
              <p className="font-mono font-bold text-xs text-eyay-text">{signal.asset_code}</p>
            </div>
            <span className="text-[9px] text-eyay-faint/70">↺ kapat</span>
          </div>

          {/* TF seçici */}
          {reading?.timeframes?.length ? (
            <div className="flex items-center gap-1 text-[9px] font-mono">
              {reading.timeframes.map(v => (
                <button
                  key={v.timeframe}
                  onClick={(e) => { e.stopPropagation(); setActiveTf(v.timeframe); }}
                  className={`px-1.5 py-0.5 rounded border ${
                    activeTf === v.timeframe
                      ? "border-emerald-700/70 bg-emerald-950/40 text-emerald-200"
                      : "border-eyay-border/40 text-eyay-faint hover:text-eyay-text"
                  }`}
                >
                  {v.timeframe.toUpperCase()}
                </button>
              ))}
              {reading.primary_tf && (
                <span className="text-[8px] text-eyay-faint ml-auto">primary: {reading.primary_tf.toUpperCase()}</span>
              )}
            </div>
          ) : null}

          {/* Chart */}
          <div className="flex-1 flex items-center justify-center min-h-[110px]">
            {loading && <p className="text-[10px] text-eyay-faint animate-pulse">grafik yükleniyor…</p>}
            {err && !loading && <p className="text-[10px] text-red-400 text-center px-2">{err}</p>}
            {!loading && !err && view && (
              <MiniChart view={view} width={280} height={130} />
            )}
          </div>

          {/* Detay satırı */}
          {view && !loading && !err && (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[8px] font-mono text-eyay-faint">
              <span>trend <span className={
                view.trend === "BULLISH" ? "text-emerald-400 font-bold" :
                view.trend === "BEARISH" ? "text-red-400 font-bold" :
                "text-eyay-text"
              }>{view.trend}</span></span>
              <span>ATR <span className="text-eyay-text">{view.atr_pct.toFixed(2)}%</span></span>
              {view.rsi_14 != null && (
                <span>RSI <span className={
                  view.rsi_14 > 70 ? "text-orange-400" :
                  view.rsi_14 < 30 ? "text-sky-400" :
                  "text-eyay-text"
                }>{view.rsi_14.toFixed(1)}</span></span>
              )}
              {view.distance_to_support_pct != null && (
                <span>→ S {view.distance_to_support_pct.toFixed(2)}%</span>
              )}
              {view.distance_to_resistance_pct != null && (
                <span>→ R {view.distance_to_resistance_pct.toFixed(2)}%</span>
              )}
              <span>bars {view.bars_used}</span>
            </div>
          )}

          {reading && !loading && !err && (
            <p className="text-[9px] text-eyay-dim leading-tight border-t border-white/5 pt-1">
              {reading.summary}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Secondary Compact Card — küçük
// ---------------------------------------------------------------------------

function SecondaryCard({
  signal, icon, statusLabel,
}: {
  signal: AssetSignal;
  icon: string;
  statusLabel: string;
}) {
  const st = STATUS_STYLE[signal.status];
  return (
    <div className={`border ${st.cardBorder} ${st.cardBg} rounded-lg p-2 flex flex-col gap-1.5 transition-all duration-200 hover:brightness-110`}>
      {/* Başlık satırı */}
      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1 min-w-0">
          <span className="text-xs leading-none">{icon}</span>
          <span className="font-mono font-bold text-[10px] text-eyay-text truncate">
            {signal.asset_code}
          </span>
        </div>
        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${st.dot} ${st.dotAnim ?? ""}`} />
      </div>

      {/* Fiyat */}
      {signal.value !== null ? (
        <p className={`font-mono font-bold text-sm leading-none ${st.priceColor}`}>
          {formatPrice(signal.value, signal.unit)}
        </p>
      ) : (
        <p className="text-[10px] text-eyay-faint font-mono">—</p>
      )}

      {/* Delta + Aksiyon */}
      <div className="flex items-center justify-between gap-1 flex-wrap">
        <DeltaBadge delta={signal.delta_7d_pct} size="sm" />
        {signal.asset_action && signal.asset_action !== "NEUTRAL" && (
          <ActionChip action={signal.asset_action} size="sm" />
        )}
      </div>

      {/* Durum badge */}
      <div className={`text-[8px] font-mono px-1 py-0.5 rounded border text-center truncate ${st.badge}`}>
        {statusLabel}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ana bileşen
// ---------------------------------------------------------------------------

export default function AssetGrid({
  signals,
  techInsights = [],
}: {
  signals: AssetSignal[];
  techInsights?: TechnicalInsight[];
}) {
  const { t } = useLanguage();

  const byCode     = Object.fromEntries(signals.map(s => [s.asset_code, s]));
  const techByCode = Object.fromEntries(techInsights.map(ti => [ti.asset_code, ti]));

  const primaryCodes   = new Set(PRIMARY_SIGNALS.map(c => c.code));
  const secondaryCodes = new Set(SECONDARY_SIGNALS.map(c => c.code));
  const allKnownCodes  = new Set([...primaryCodes, ...secondaryCodes]);

  const primaryItems = PRIMARY_SIGNALS
    .map(c => ({ ...c, signal: byCode[c.code] }))
    .filter(c => c.signal != null) as Array<{ code: string; icon: string; signal: AssetSignal }>;

  const secondaryItems = SECONDARY_SIGNALS
    .map(c => ({ ...c, signal: byCode[c.code] }))
    .filter(c => c.signal != null) as Array<{ code: string; icon: string; signal: AssetSignal }>;

  // Hiçbir gruba girmeyen sinyaller (fallback)
  const otherItems = signals.filter(s => !allKnownCodes.has(s.asset_code));

  const priBlocking  = primaryItems.filter(c => c.signal.status === "BLOCKING").length;
  const priConfirmed = primaryItems.filter(c => c.signal.status === "CONFIRMED").length;
  const priPending   = primaryItems.filter(c => c.signal.status === "PENDING").length;
  const secBlocking  = secondaryItems.filter(c => c.signal.status === "BLOCKING").length;
  const secConfirmed = secondaryItems.filter(c => c.signal.status === "CONFIRMED").length;

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">

      {/* ── Header ── */}
      <div className="px-5 py-3.5 border-b border-eyay-border">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">
              {t.assetGrid.layer}
            </p>
            <p className="text-sm font-semibold text-eyay-text mt-0.5">{t.assetGrid.title}</p>
          </div>
          <div className="flex items-center gap-2 text-[10px] font-mono">
            {priBlocking > 0 && (
              <span className="px-2 py-0.5 rounded border bg-red-950 text-red-400 border-red-900/60">
                {priBlocking} {t.assetGrid.block}
              </span>
            )}
            {priConfirmed > 0 && (
              <span className="px-2 py-0.5 rounded border bg-emerald-950 text-emerald-400 border-emerald-900/60">
                {priConfirmed} {t.assetGrid.confirm}
              </span>
            )}
            {priPending > 0 && (
              <span className="px-2 py-0.5 rounded border bg-amber-950 text-amber-400 border-amber-900/60">
                {priPending} {t.assetGrid.wait}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── 5 Komut Sinyali — büyük kartlar ── */}
      <div className="p-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {primaryItems.map(c => (
            <CommandCard
              key={c.code}
              signal={c.signal}
              icon={c.icon}
              statusLabel={t.assetGrid.statusLabel[c.signal.status] ?? c.signal.status}
              techInsight={techByCode[c.code]}
            />
          ))}
        </div>
      </div>

      {/* ── İkincil Sinyaller — kompakt ── */}
      {secondaryItems.length > 0 && (
        <div className="px-4 pb-4 border-t border-eyay-border/40 pt-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest">
              Makro Göstergeler
            </p>
            <div className="flex items-center gap-2 text-[9px] font-mono">
              {secBlocking  > 0 && <span className="text-red-400">{secBlocking} blok</span>}
              {secConfirmed > 0 && <span className="text-emerald-400">{secConfirmed} onay</span>}
            </div>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-7 gap-2">
            {secondaryItems.map(c => (
              <SecondaryCard
                key={c.code}
                signal={c.signal}
                icon={c.icon}
                statusLabel={t.assetGrid.statusLabel[c.signal.status] ?? c.signal.status}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Geri kalan sinyaller (fallback) ── */}
      {otherItems.length > 0 && (
        <div className="border-t border-eyay-border px-3 pb-3 pt-2 space-y-0.5">
          {otherItems.map(s => (
            <div key={s.asset_code} className="flex items-center gap-3 py-1.5 px-2 rounded hover:bg-white/3 text-[10px] font-mono text-eyay-faint">
              <span className={`w-1.5 h-1.5 rounded-full ${STATUS_STYLE[s.status].dot}`} />
              <span className="text-eyay-text font-semibold">{s.asset_code}</span>
              {s.value !== null && <span>{formatPrice(s.value, s.unit)}</span>}
              <DeltaBadge delta={s.delta_7d_pct} size="sm" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
