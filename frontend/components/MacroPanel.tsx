"use client";

import type { MacroLayer, RiskAppetiteLayer, RegimeCode, AppetiteCode } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

// ── Renk haritaları ──────────────────────────────────────────────────────────

const REGIME_BADGE: Record<RegimeCode, { bg: string; text: string; bar: string }> = {
  RISK_ON:      { bg: "bg-emerald-950 border-emerald-700", text: "text-emerald-300", bar: "bg-emerald-500" },
  TRANSITIONING:{ bg: "bg-amber-950   border-amber-700",   text: "text-amber-300",   bar: "bg-amber-500"   },
  DEFENSIVE:    { bg: "bg-orange-950  border-orange-700",  text: "text-orange-300",  bar: "bg-orange-500"  },
  CRISIS:       { bg: "bg-red-950     border-red-700",     text: "text-red-300",     bar: "bg-red-500"     },
};

const APPETITE_DOT: Record<AppetiteCode, { dot: string; text: string }> = {
  STRONG:   { dot: "bg-emerald-400", text: "text-emerald-300" },
  MODERATE: { dot: "bg-amber-400",   text: "text-amber-300"   },
  WEAK:     { dot: "bg-orange-400",  text: "text-orange-300"  },
  CRISIS:   { dot: "bg-red-400",     text: "text-red-300"     },
};

// ── Sinyal satırı renk çıkarıcı ──────────────────────────────────────────────

function signalColor(value: string, label: string): string {
  const v = value.toUpperCase();
  if (v.includes("YÜKSEK") || v.includes("İNVERSİYON") || v.includes("KIRIYOR") ||
      v.includes("KAÇIŞ")  || v.includes("DARALIYOR") || v.includes("BASKILI"))
    return "text-red-300";
  if (v.includes("ZAYIF") && label === "DXY") return "text-emerald-300";
  if (v.includes("NORMAL") || v.includes("SAĞLAM") || v.includes("GENİŞLİYOR") ||
      (v.includes("ZAYIF") && label !== "DXY"))
    return "text-emerald-300";
  if (v.includes("İZLE") || v.includes("NÖTR") || v.includes("GEÇIŞ"))
    return "text-amber-300";
  return "text-eyay-dim";
}

// ── Ana bileşen ──────────────────────────────────────────────────────────────

export default function MacroPanel({ macro, appetite }: {
  macro: MacroLayer;
  appetite: RiskAppetiteLayer;
}) {
  const { t } = useLanguage();
  const rb = REGIME_BADGE[macro.regime];
  const ad = APPETITE_DOT[appetite.status];
  const appetiteLabel = t.macro.appetiteLabels[appetite.status] ?? appetite.status;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

      {/* ── Katman 1 — Makro Rejim ─────────────────────────────────────── */}
      <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">
        <div className="px-5 py-4 border-b border-eyay-border flex items-center justify-between">
          <div>
            <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">{t.macro.layer1}</p>
            <p className="text-sm font-semibold text-eyay-text mt-0.5">{t.macro.macroRegime}</p>
          </div>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold ${rb.bg} ${rb.text}`}>
            {macro.regime.replace("_", " ")}
          </div>
        </div>

        <div className="px-5 pt-4 pb-2">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-eyay-faint">{t.macro.confidence}</span>
            <span className={`font-mono text-sm font-semibold ${rb.text}`}>%{macro.confidence_pct}</span>
          </div>
          <div className="h-1.5 bg-eyay-raised rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${rb.bar}`}
              style={{ width: `${macro.confidence_pct}%` }} />
          </div>
        </div>

        <div className="px-5 py-4 space-y-3">
          <MacroRow label="DXY"                    value={macro.dxy_signal} />
          <MacroRow label="Brent"                  value={macro.energy_signal} />
          <MacroRow label={t.macro.yieldCurve}     value={macro.yield_curve_signal} />
          <MacroRow label="M2"                     value={macro.m2_signal} />
        </div>

        <div className="px-5 pb-4">
          <p className="text-xs text-eyay-dim leading-relaxed bg-eyay-raised rounded-xl px-4 py-3 border border-eyay-border">
            {macro.summary}
          </p>
        </div>
      </div>

      {/* ── Katman 2 — Risk İştahı ─────────────────────────────────────── */}
      <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">
        <div className="px-5 py-4 border-b border-eyay-border flex items-center justify-between">
          <div>
            <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">{t.macro.layer2}</p>
            <p className="text-sm font-semibold text-eyay-text mt-0.5">{t.macro.riskAppetite}</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-eyay-raised border border-eyay-border">
            <span className={`w-2 h-2 rounded-full ${ad.dot}`} />
            <span className={`text-xs font-semibold ${ad.text}`}>{appetiteLabel}</span>
          </div>
        </div>

        <div className="px-5 py-4 space-y-3">
          <MacroRow label="Kredi (HYG)"  value={appetite.credit_signal} />
          <MacroRow label="BTC.D"        value={appetite.btc_dominance_signal} />
          <MacroRow label="USDT.D"       value={appetite.usdt_dominance_signal} />
          <MacroRow label={t.macro.gold} value={appetite.safe_haven_signal} />
        </div>

        <div className="px-5 pb-4">
          <p className="text-xs text-eyay-dim leading-relaxed bg-eyay-raised rounded-xl px-4 py-3 border border-eyay-border">
            {appetite.summary}
          </p>
        </div>
      </div>

    </div>
  );
}

function MacroRow({ label, value }: { label: string; value: string }) {
  const color = signalColor(value, label.toUpperCase());
  const [first, ...rest] = value.split(" — ");
  const hasDetail = rest.length > 0;

  return (
    <div className="flex items-start gap-3">
      <span className="text-xs text-eyay-faint w-24 shrink-0 pt-px font-medium">{label}</span>
      <div className="flex-1 min-w-0">
        {hasDetail ? (
          <>
            <span className={`text-xs font-semibold ${color}`}>{first}</span>
            <span className="text-xs text-eyay-dim"> — {rest.join(" — ")}</span>
          </>
        ) : (
          <span className={`text-xs ${color}`}>{value}</span>
        )}
      </div>
    </div>
  );
}
