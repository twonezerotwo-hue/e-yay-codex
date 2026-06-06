"use client";

import type { TechnicalInsight } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ── Görüntü yardımcıları ────────────────────────────────────────────────────

const STRUCT_STYLE: Record<string, { label: string; color: string; dot: string }> = {
  BULLISH: { label: "BULLISH", color: "text-emerald-400", dot: "bg-emerald-400" },
  BEARISH: { label: "BEARISH", color: "text-red-400",     dot: "bg-red-400"     },
  NEUTRAL: { label: "NEUTRAL", color: "text-amber-400",   dot: "bg-amber-400"   },
};

const MACD_COLOR: Record<string, string> = {
  BULLISH: "text-emerald-400",
  BEARISH: "text-red-400",
  NEUTRAL: "text-eyay-faint",
};

/** Skoru renge çevirir (0-100). */
function scoreColor(score: number): string {
  if (score >= 70) return "bg-emerald-500";
  if (score >= 45) return "bg-amber-500";
  return "bg-red-500";
}

/** Fiyatı öz biçimde biçimlendirir. */
function fmt(v: number): string {
  if (v >= 10_000) return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (v >= 100)    return v.toLocaleString("en-US", { maximumFractionDigits: 1 });
  if (v >= 1)      return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return v.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

// ── Sabit görünen isimler ───────────────────────────────────────────────────

const ASSET_NAMES: Record<string, string> = {
  BTCUSD: "Bitcoin",
  XAUUSD: "Altın",
  XAGUSD: "Gümüş",
  XCUUSD: "Bakır",
  BRENT:  "Brent",
  DXY:    "DXY",
  VIX:    "VIX",
  SP500:  "S&P 500",
  HYG:    "HYG",
  QQQ:    "QQQ",
  IWM:    "IWM",
  LQD:    "LQD",
  SMH:    "SMH",
  XLF:    "XLF",
};

// ── Sıralama: teknik skora göre azalan ──────────────────────────────────────

function sorted(insights: TechnicalInsight[]): TechnicalInsight[] {
  return [...insights].sort((a, b) => b.technical_score - a.technical_score);
}

// ── Bileşenler ───────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-1.5 min-w-[80px]">
      <div className="flex-1 h-1 bg-eyay-border rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${scoreColor(score)} transition-all`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-[9px] font-mono text-eyay-faint w-7 text-right">{score}</span>
    </div>
  );
}

function InsightRow({ ti }: { ti: TechnicalInsight }) {
  const st = STRUCT_STYLE[ti.structure] ?? STRUCT_STYLE.NEUTRAL;
  const l  = ti.levels;

  return (
    <div className="flex items-center gap-3 px-3 py-2 hover:bg-eyay-raised/40 transition-colors rounded-lg group">

      {/* Asset name */}
      <div className="w-[76px] shrink-0">
        <p className="text-xs font-semibold text-eyay-text truncate">
          {ASSET_NAMES[ti.asset_code] ?? ti.asset_code}
        </p>
        <p className="text-[9px] font-mono text-eyay-faint">{ti.asset_code}</p>
      </div>

      {/* Structure dot + label */}
      <div className="flex items-center gap-1 w-[66px] shrink-0">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${st.dot}`} />
        <span className={`text-[9px] font-mono font-semibold ${st.color}`}>{st.label}</span>
      </div>

      {/* Support / Resistance */}
      <div className="flex gap-2 text-[9px] font-mono w-[140px] shrink-0">
        <span>
          <span className="text-eyay-faint">S </span>
          <span className="text-red-300">{fmt(l.support)}</span>
        </span>
        <span className="text-eyay-border">|</span>
        <span>
          <span className="text-eyay-faint">R </span>
          <span className="text-emerald-300">{fmt(l.resistance)}</span>
        </span>
      </div>

      {/* ATR % */}
      <div className="w-[44px] shrink-0 text-right">
        <span className="text-[9px] font-mono text-amber-400/80">
          ±{l.atr_pct.toFixed(1)}%
        </span>
      </div>

      {/* RSI */}
      <div className="w-[32px] shrink-0 text-right">
        {ti.rsi_14 !== null ? (
          <span className={`text-[9px] font-mono ${
            ti.rsi_14 > 70 ? "text-red-400" :
            ti.rsi_14 < 30 ? "text-emerald-400" :
            "text-eyay-faint"
          }`}>
            {ti.rsi_14.toFixed(0)}
          </span>
        ) : (
          <span className="text-[9px] text-eyay-faint/40">—</span>
        )}
      </div>

      {/* MACD */}
      <div className="w-[22px] shrink-0 text-center">
        <span className={`text-[9px] font-mono font-bold ${MACD_COLOR[ti.macd_signal]}`}>
          {ti.macd_signal === "BULLISH" ? "▲" : ti.macd_signal === "BEARISH" ? "▼" : "—"}
        </span>
      </div>

      {/* Score bar */}
      <div className="flex-1 min-w-0">
        <ScoreBar score={ti.technical_score} />
      </div>
    </div>
  );
}

// ── Ana bileşen ──────────────────────────────────────────────────────────────

export default function TechnicalPanel({ insights }: { insights: TechnicalInsight[] }) {
  const { t } = useLanguage();

  if (!insights || insights.length === 0) return null;

  const items = sorted(insights);

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">

      {/* Başlık */}
      <div className="px-5 py-3.5 border-b border-eyay-border flex items-center justify-between">
        <div>
          <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">
            {t.technical.sectionLabel}
          </p>
          <p className="text-sm font-semibold text-eyay-text mt-0.5">{t.technical.title}</p>
        </div>
        <span className="text-xs text-eyay-faint font-mono">
          {t.technical.assets(insights.length)}
        </span>
      </div>

      {/* Kolon başlıkları */}
      <div className="flex items-center gap-3 px-3 py-1.5 border-b border-eyay-border/50">
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider w-[76px] shrink-0">
          {t.technical.asset}
        </span>
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider w-[66px] shrink-0">
          {t.technical.structure}
        </span>
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider w-[140px] shrink-0">
          {t.technical.levels}
        </span>
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider w-[44px] shrink-0 text-right">
          ATR%
        </span>
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider w-[32px] shrink-0 text-right">
          RSI
        </span>
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider w-[22px] shrink-0 text-center">
          M
        </span>
        <span className="text-[8px] text-eyay-faint/60 uppercase tracking-wider flex-1">
          {t.technical.score}
        </span>
      </div>

      {/* Satırlar */}
      <div className="divide-y divide-eyay-border/30 px-2 py-1">
        {items.map(ti => <InsightRow key={ti.asset_code} ti={ti} />)}
      </div>

      {/* Alt not */}
      <div className="px-5 py-2 border-t border-eyay-border/50">
        <p className="text-[9px] text-eyay-faint/50 font-mono">{t.technical.footer}</p>
      </div>
    </div>
  );
}
