import type { AssetSignal, SignalStatus } from "@/lib/types";

const STATUS_STYLE: Record<SignalStatus, { dot: string; badge: string; border: string }> = {
  CONFIRMED:  { dot: "bg-emerald-400", badge: "text-emerald-400 bg-emerald-950 border-emerald-800", border: "border-eyay-border" },
  PENDING:    { dot: "bg-amber-400",   badge: "text-amber-400   bg-amber-950   border-amber-800",   border: "border-eyay-border" },
  BLOCKING:   { dot: "bg-red-400 animate-pulse", badge: "text-red-400 bg-red-950 border-red-800", border: "border-red-900" },
  NEUTRAL:    { dot: "bg-gray-500",    badge: "text-gray-400    bg-gray-900    border-gray-700",    border: "border-eyay-border" },
  VERİ_YOK:  { dot: "bg-gray-700",    badge: "text-gray-600    bg-gray-900    border-gray-800",    border: "border-eyay-border" },
};

export default function AssetGrid({ signals }: { signals: AssetSignal[] }) {
  return (
    <div className="bg-eyay-surface border border-eyay-border rounded-xl p-5">
      <h2 className="text-xs font-mono uppercase tracking-widest text-eyay-dim mb-4">
        Katman 3 — Asset Sinyalleri
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {signals.map((s) => (
          <AssetCard key={s.asset_code} signal={s} />
        ))}
      </div>
    </div>
  );
}

function AssetCard({ signal }: { signal: AssetSignal }) {
  const st = STATUS_STYLE[signal.status];
  return (
    <div className={`border ${st.border} bg-eyay-bg rounded-lg p-4`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="font-mono font-bold text-sm text-eyay-text">{signal.asset_code}</span>
          <p className="text-xs text-eyay-dim font-mono">{signal.asset_name}</p>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${st.dot}`} />
          <span className={`font-mono text-xs border rounded px-1.5 py-0.5 ${st.badge}`}>
            {signal.status}
          </span>
        </div>
      </div>
      {signal.value !== null && (
        <p className="font-mono text-xs text-eyay-blue mb-2">
          {signal.value > 1000
            ? `$${signal.value.toLocaleString("tr-TR", { maximumFractionDigits: 0 })}`
            : signal.value < 1
            ? `${signal.value.toFixed(4)}`
            : `${signal.value.toFixed(2)}`}
          {" "}<span className="text-eyay-dim">{signal.unit}</span>
        </p>
      )}
      <p className="text-xs text-eyay-dim font-mono leading-relaxed line-clamp-2">{signal.reason}</p>
    </div>
  );
}
