import type { MacroLayer, RiskAppetiteLayer, RegimeCode, AppetiteCode } from "@/lib/types";

const REGIME_COLOR: Record<RegimeCode, string> = {
  RISK_ON:      "text-emerald-400 border-emerald-700 bg-emerald-950",
  TRANSITIONING:"text-amber-400   border-amber-700   bg-amber-950",
  DEFENSIVE:    "text-orange-400  border-orange-700  bg-orange-950",
  CRISIS:       "text-red-400     border-red-700     bg-red-950",
};

const APPETITE_COLOR: Record<AppetiteCode, string> = {
  STRONG:   "text-emerald-400",
  MODERATE: "text-amber-400",
  WEAK:     "text-orange-400",
  CRISIS:   "text-red-400",
};

export default function MacroPanel({ macro, appetite }: { macro: MacroLayer; appetite: RiskAppetiteLayer }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Katman 1 */}
      <div className="bg-eyay-surface border border-eyay-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-eyay-dim">
            Katman 1 — Makro Rejim
          </h2>
          <span className={`font-mono text-xs font-bold border rounded px-2 py-0.5 ${REGIME_COLOR[macro.regime]}`}>
            {macro.regime}
          </span>
        </div>
        <div className="space-y-3">
          <SignalRow label="DXY"         value={macro.dxy_signal} />
          <SignalRow label="ENERJİ"      value={macro.energy_signal} />
          <SignalRow label="YİELD CURVE" value={macro.yield_curve_signal} />
          <SignalRow label="M2SL"        value={macro.m2_signal} />
        </div>
        <div className="mt-4 pt-3 border-t border-eyay-border">
          <p className="text-xs text-eyay-dim font-mono">{macro.summary}</p>
          <div className="mt-2 h-1.5 bg-eyay-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${macro.regime === "RISK_ON" ? "bg-emerald-500" : macro.regime === "TRANSITIONING" ? "bg-amber-500" : macro.regime === "DEFENSIVE" ? "bg-orange-500" : "bg-red-500"}`}
              style={{ width: `${macro.confidence_pct}%` }}
            />
          </div>
          <p className="text-xs text-eyay-dim font-mono mt-1">Güven: %{macro.confidence_pct}</p>
        </div>
      </div>

      {/* Katman 2 */}
      <div className="bg-eyay-surface border border-eyay-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-eyay-dim">
            Katman 2 — Risk İştahı
          </h2>
          <span className={`font-mono text-sm font-bold ${APPETITE_COLOR[appetite.status]}`}>
            {appetite.status}
          </span>
        </div>
        <div className="space-y-3">
          <SignalRow label="KREDİ"      value={appetite.credit_signal} />
          <SignalRow label="BTC.D"      value={appetite.btc_dominance_signal} />
          <SignalRow label="USDT.D"     value={appetite.usdt_dominance_signal} />
          <SignalRow label="GÜVENLI"    value={appetite.safe_haven_signal} />
        </div>
        <div className="mt-4 pt-3 border-t border-eyay-border">
          <p className="text-xs text-eyay-dim font-mono">{appetite.summary}</p>
        </div>
      </div>
    </div>
  );
}

function SignalRow({ label, value }: { label: string; value: string }) {
  const isNeg = value.includes("YÜKSEK") || value.includes("İNVERSİYON") || value.includes("KIRIYOR") || value.includes("KAÇIŞ") || value.includes("DARALIYOR");
  const isPos = value.includes("ZAYIF") && label === "DXY" || value.includes("NORMAL") || value.includes("SAĞLAM") || value.includes("GENİŞLİYOR");

  return (
    <div className="flex gap-3">
      <span className="font-mono text-xs text-eyay-dim w-24 shrink-0 pt-0.5">{label}</span>
      <span className={`font-mono text-xs leading-relaxed ${isNeg ? "text-orange-300" : isPos ? "text-emerald-300" : "text-eyay-text"}`}>
        {value}
      </span>
    </div>
  );
}
