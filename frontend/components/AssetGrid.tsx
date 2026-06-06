"use client";

import { useState } from "react";
import type { AssetSignal, AssetActionType, SignalStatus, TechnicalInsight } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ---------------------------------------------------------------------------
// 8 Komut Sinyali — sadece kod + ikon (isimler çeviriden gelir)
// ---------------------------------------------------------------------------

const COMMAND_SIGNALS = [
  // Kripto / Risk-on pulse
  { code: "BTCUSD",    icon: "₿"  },
  // Kıymetli metaller — stratejik üçlü
  { code: "XAUUSD",    icon: "◆"  },
  { code: "XAGUSD",    icon: "🥈" },
  { code: "XAUXAG",    icon: "⚖️" },
  // Sanayi / büyüme
  { code: "XCUUSD",    icon: "🔧" },
  { code: "SP500",     icon: "📈" },
  // Makro baskı göstergeleri
  { code: "BRENT",     icon: "⚡" },
  { code: "DXY",       icon: "💵" },
  { code: "US10Y",     icon: "🏛" },
  // Risk göstergeleri
  { code: "VIX",       icon: "⚠" },
  { code: "HY_SPREAD", icon: "📊" },
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

function ActionChip({ action, trigger }: { action: AssetActionType; trigger?: string }) {
  if (action === "NEUTRAL") return null;
  const s = ACTION_STYLE[action];
  return (
    <div
      className={`flex items-center gap-1 px-1.5 py-0.5 rounded border font-mono text-[9px] font-bold shrink-0 leading-none ${s.classes}`}
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
  const base  = size === "sm" ? "text-[10px]" : "text-xs";
  return (
    <span className={`font-mono font-semibold ${base} ${isPos ? "text-emerald-400" : delta < 0 ? "text-red-400" : "text-eyay-faint"}`}>
      {isPos ? "▲" : delta < 0 ? "▼" : "≈"} {abs}%
    </span>
  );
}

// ---------------------------------------------------------------------------
// S/R Level display helpers
// ---------------------------------------------------------------------------

/** Fiyatın S-R aralığına göre konumu */
function pricePosition(price: number, support: number, resistance: number): "above_r" | "below_s" | "in_range" {
  if (price >= resistance) return "above_r";
  if (price <= support)    return "below_s";
  return "in_range";
}

function SRLevels({ ti, unit }: { ti: TechnicalInsight; unit: string }) {
  const { support, resistance } = ti.levels;
  const pos = pricePosition(ti.current_price, support, resistance);

  // Direnç satırı
  const rBroken = pos === "above_r";
  const sBroken = pos === "below_s";

  return (
    <div className="flex flex-col gap-0.5 my-0.5">
      {/* Direnç — fiyatın üstünde */}
      <div className={`flex items-center justify-between text-[9px] font-mono px-1.5 py-0.5 rounded ${
        rBroken
          ? "text-emerald-300 bg-emerald-950/40"
          : "text-eyay-faint/70 bg-white/3"
      }`}>
        <span className="opacity-60">R</span>
        <span>{formatPrice(resistance, unit)}</span>
        {rBroken && <span className="text-emerald-400">↑</span>}
      </div>

      {/* Destek — fiyatın altında */}
      <div className={`flex items-center justify-between text-[9px] font-mono px-1.5 py-0.5 rounded ${
        sBroken
          ? "text-red-300 bg-red-950/40"
          : "text-eyay-faint/70 bg-white/3"
      }`}>
        <span className="opacity-60">S</span>
        <span>{formatPrice(support, unit)}</span>
        {sBroken && <span className="text-red-400">↓</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Command Signal Card
// ---------------------------------------------------------------------------

function CommandCard({
  signal, icon, statusLabel, techInsight,
}: {
  signal: AssetSignal;
  icon: string;
  statusLabel: string;
  techInsight?: TechnicalInsight;
}) {
  const st = STATUS_STYLE[signal.status];
  return (
    <div className={`border ${st.cardBorder} ${st.cardBg} rounded-xl p-3.5 flex flex-col gap-2 transition-all duration-200 hover:brightness-110`}>
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
          {/* Direnç — fiyatın üstünde */}
          {techInsight && (() => {
            const broken = signal.value >= techInsight.levels.resistance;
            return (
              <p className={`text-[9px] font-mono whitespace-nowrap ${broken ? "text-emerald-400" : "text-eyay-faint/50"}`}>
                R {formatPrice(techInsight.levels.resistance, signal.unit)}{broken ? " ↑" : ""}
              </p>
            );
          })()}

          {/* Fiyat */}
          <div>
            <p className={`font-mono font-black text-xl leading-none ${st.priceColor}`}>
              {formatPrice(signal.value, signal.unit)}
            </p>
            <p className="text-[9px] font-mono text-eyay-faint mt-0.5">{signal.unit}</p>
          </div>

          {/* Destek — fiyatın altında */}
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
        {/* ATR tech suffix'i gizle — temiz görünüm için */}
        {signal.reason.replace(/\s*\[S:[^\]]+\]/g, "")}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compact detail row
// ---------------------------------------------------------------------------

function DetailRow({ signal, statusLabel }: { signal: AssetSignal; statusLabel: string }) {
  const st = STATUS_STYLE[signal.status];
  return (
    <div className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-white/3 transition-colors">
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${st.dot} ${st.dotAnim ?? ""}`} />
      <div className="flex-1 min-w-0">
        <span className="font-mono text-xs font-semibold text-eyay-text">{signal.asset_code}</span>
        <span className="text-[10px] text-eyay-faint ml-1.5 hidden sm:inline">{signal.asset_name}</span>
      </div>
      {signal.value !== null && (
        <span className={`font-mono text-xs font-semibold ${st.priceColor}`}>
          {formatPrice(signal.value, signal.unit)}
        </span>
      )}
      <DeltaBadge delta={signal.delta_7d_pct} size="sm" />
      {signal.asset_action && signal.asset_action !== "NEUTRAL" && (
        <ActionChip action={signal.asset_action} trigger={signal.action_trigger} />
      )}
      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border shrink-0 ${st.badge}`}>
        {statusLabel}
      </span>
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
  const [detailsOpen, setDetailsOpen] = useState(false);
  const { t } = useLanguage();

  const byCode    = Object.fromEntries(signals.map(s => [s.asset_code, s]));
  const techByCode = Object.fromEntries(techInsights.map(ti => [ti.asset_code, ti]));
  const commandCodes = new Set(COMMAND_SIGNALS.map(c => c.code));

  const commandItems = COMMAND_SIGNALS
    .map(c => ({ ...c, signal: byCode[c.code] }))
    .filter(c => c.signal != null) as Array<{ code: string; icon: string; signal: AssetSignal }>;

  const detailItems = signals.filter(s => !commandCodes.has(s.asset_code));

  const cmdBlocking  = commandItems.filter(c => c.signal.status === "BLOCKING").length;
  const cmdConfirmed = commandItems.filter(c => c.signal.status === "CONFIRMED").length;
  const cmdPending   = commandItems.filter(c => c.signal.status === "PENDING").length;
  const detBlocking  = detailItems.filter(s => s.status === "BLOCKING").length;
  const detConfirmed = detailItems.filter(s => s.status === "CONFIRMED").length;

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
            {cmdBlocking > 0 && (
              <span className="px-2 py-0.5 rounded border bg-red-950 text-red-400 border-red-900/60">
                {cmdBlocking} {t.assetGrid.block}
              </span>
            )}
            {cmdConfirmed > 0 && (
              <span className="px-2 py-0.5 rounded border bg-emerald-950 text-emerald-400 border-emerald-900/60">
                {cmdConfirmed} {t.assetGrid.confirm}
              </span>
            )}
            {cmdPending > 0 && (
              <span className="px-2 py-0.5 rounded border bg-amber-950 text-amber-400 border-amber-900/60">
                {cmdPending} {t.assetGrid.wait}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── 8 Komut Sinyali ── */}
      <div className="p-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-6 gap-3">
          {commandItems.map(c => (
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

      {/* ── Detay Sinyalleri ── */}
      {detailItems.length > 0 && (
        <div className="border-t border-eyay-border">
          <button
            onClick={() => setDetailsOpen(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3 text-xs font-mono text-eyay-dim hover:text-eyay-text hover:bg-white/2 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className={`transition-transform duration-200 ${detailsOpen ? "rotate-90" : ""}`}>▶</span>
              <span>{t.assetGrid.detailSignals(detailItems.length)}</span>
              <span className="text-eyay-faint text-[10px]">
                — {detailItems.map(s => s.asset_code).join(" · ")}
              </span>
            </div>
            <div className="flex items-center gap-2 text-[10px]">
              {detBlocking  > 0 && <span className="text-red-400">{detBlocking} {t.assetGrid.detBlock}</span>}
              {detConfirmed > 0 && <span className="text-emerald-400">{detConfirmed} {t.assetGrid.detConfirm}</span>}
            </div>
          </button>

          {detailsOpen && (
            <div className="px-3 pb-3 space-y-0.5">
              {detailItems.map(s => (
                <DetailRow
                  key={s.asset_code}
                  signal={s}
                  statusLabel={t.assetGrid.statusLabel[s.status] ?? s.status}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
