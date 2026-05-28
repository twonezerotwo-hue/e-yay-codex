import type { ConfirmationItem } from "@/lib/types";

export default function ConfirmationChecklist({ items }: { items: ConfirmationItem[] }) {
  const met    = items.filter(i => i.met).length;
  const total  = items.length;
  const pct    = total > 0 ? Math.round((met / total) * 100) : 0;

  return (
    <div className="bg-eyay-surface border border-eyay-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-mono uppercase tracking-widest text-eyay-dim">
          Teyit Listesi
        </h2>
        <span className="font-mono text-xs text-eyay-dim">
          <span className={pct === 100 ? "text-emerald-400" : pct >= 60 ? "text-amber-400" : "text-orange-400"}>
            {met}/{total}
          </span>
          {" "}karşılandı
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-eyay-muted rounded-full overflow-hidden mb-5">
        <div
          className={`h-full rounded-full transition-all ${pct === 100 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-500" : "bg-orange-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <div className="space-y-3">
        {items.map((item, i) => (
          <CheckRow key={i} item={item} />
        ))}
      </div>
    </div>
  );
}

function CheckRow({ item }: { item: ConfirmationItem }) {
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${item.met ? "border-emerald-900 bg-emerald-950/30" : "border-eyay-border bg-eyay-bg"}`}>
      <span className={`font-mono font-bold text-base shrink-0 mt-0.5 ${item.met ? "text-emerald-400" : "text-red-500"}`}>
        {item.met ? "✓" : "✗"}
      </span>
      <div className="flex-1 min-w-0">
        <p className={`font-mono text-sm ${item.met ? "text-emerald-300" : "text-eyay-dim"}`}>
          {item.signal}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="font-mono text-xs text-eyay-blue">{item.current_value}</span>
          <span className="text-eyay-muted font-mono text-xs">→ hedef:</span>
          <span className="font-mono text-xs text-eyay-dim">{item.threshold}</span>
        </div>
      </div>
    </div>
  );
}
