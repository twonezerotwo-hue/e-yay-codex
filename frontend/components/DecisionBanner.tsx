import type { Decision, RegimeReport } from "@/lib/types";

const DECISION_STYLES: Record<Decision, { bg: string; border: string; text: string; glow: string }> = {
  AÇIL:   { bg: "bg-emerald-950",  border: "border-emerald-500",  text: "text-emerald-400", glow: "shadow-emerald-900" },
  BEKLE:  { bg: "bg-amber-950",    border: "border-amber-500",    text: "text-amber-400",   glow: "shadow-amber-900" },
  KÜÇÜLT: { bg: "bg-orange-950",   border: "border-orange-500",   text: "text-orange-400",  glow: "shadow-orange-900" },
  KAPAT:  { bg: "bg-red-950",      border: "border-red-500",      text: "text-red-400",     glow: "shadow-red-900" },
};

export default function DecisionBanner({ report }: { report: RegimeReport }) {
  const s = DECISION_STYLES[report.decision];
  const ts = new Date(report.generated_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`${s.bg} border-2 ${s.border} rounded-xl p-6 shadow-lg ${s.glow}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={`font-mono font-bold text-3xl tracking-widest ${s.text}`}>
            {report.decision}
          </span>
          <span className="text-xs font-mono text-eyay-dim border border-eyay-border rounded px-2 py-0.5">
            {report.execution_mode}
          </span>
        </div>
        <span className="text-xs text-eyay-dim font-mono">{ts}</span>
      </div>

      {/* Verdict */}
      <p className="text-eyay-text font-mono text-sm leading-relaxed mb-4 border-l-2 border-eyay-muted pl-4">
        {report.verdict}
      </p>

      {/* Owner action */}
      <div className="bg-eyay-surface rounded-lg p-3">
        <span className="text-xs text-eyay-dim font-mono uppercase tracking-wider">Owner Action → </span>
        <span className="text-eyay-text font-mono text-sm">{report.owner_action}</span>
      </div>

      {/* Signal summary chips */}
      <div className="flex gap-3 mt-4">
        <Chip color="red"    label="BLOCKING"  count={report.blocking_count} />
        <Chip color="green"  label="CONFIRMED" count={report.confirmed_count} />
        <Chip color="yellow" label="PENDING"   count={report.pending_count} />
      </div>
    </div>
  );
}

function Chip({ color, label, count }: { color: string; label: string; count: number }) {
  const colors: Record<string, string> = {
    red:    "bg-red-950 border-red-800 text-red-400",
    green:  "bg-emerald-950 border-emerald-800 text-emerald-400",
    yellow: "bg-amber-950 border-amber-800 text-amber-400",
  };
  return (
    <div className={`border rounded px-3 py-1 font-mono text-xs flex items-center gap-2 ${colors[color]}`}>
      <span className="font-bold text-base">{count}</span>
      <span className="opacity-70">{label}</span>
    </div>
  );
}
