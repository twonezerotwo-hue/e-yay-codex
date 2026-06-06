import type { ConfirmationItem } from "@/lib/types";

export default function ConfirmationChecklist({ items }: { items: ConfirmationItem[] }) {
  const met   = items.filter(i => i.met).length;
  const total = items.length;
  const pct   = total > 0 ? Math.round((met / total) * 100) : 0;

  const barColor = pct === 100 ? "bg-emerald-500"
    : pct >= 60 ? "bg-amber-500"
    : "bg-orange-500";

  const countColor = pct === 100 ? "text-emerald-300"
    : pct >= 60 ? "text-amber-300"
    : "text-orange-300";

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden h-full">

      {/* Başlık */}
      <div className="px-5 py-4 border-b border-eyay-border">
        <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">Katman 4</p>
        <p className="text-sm font-semibold text-eyay-text mt-0.5">Teyit Listesi</p>
      </div>

      {/* İlerleme */}
      <div className="px-5 pt-4 pb-3">
        <div className="flex items-end justify-between mb-2">
          <span className="text-xs text-eyay-dim">
            Karşılanan koşullar
          </span>
          <span className={`font-mono font-bold text-2xl leading-none ${countColor}`}>
            {met}
            <span className="text-sm text-eyay-faint font-normal">/{total}</span>
          </span>
        </div>
        <div className="h-2 bg-eyay-raised rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-eyay-faint mt-1.5 text-right font-mono">%{pct}</p>
      </div>

      {/* Koşul listesi */}
      <div className="px-4 pb-4 space-y-2">
        {items.map((item, i) => (
          <CheckRow key={i} item={item} />
        ))}
      </div>
    </div>
  );
}

function CheckRow({ item }: { item: ConfirmationItem }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${
      item.met
        ? "border-emerald-900/50 bg-emerald-950/30"
        : "border-eyay-border bg-eyay-raised"
    }`}>
      {/* Sinyal adı */}
      <div className="flex items-start gap-2.5">
        <span className={`font-mono font-bold text-base leading-none mt-0.5 shrink-0 ${
          item.met ? "text-emerald-400" : "text-eyay-faint"
        }`}>
          {item.met ? "✓" : "✗"}
        </span>
        <p className={`text-xs font-medium leading-snug ${
          item.met ? "text-emerald-200" : "text-eyay-dim"
        }`}>
          {item.signal}
        </p>
      </div>

      {/* Değerler */}
      <div className="flex items-center gap-1.5 mt-2 ml-6 flex-wrap">
        <span className={`font-mono text-xs font-semibold ${item.met ? "text-emerald-400" : "text-eyay-blue"}`}>
          {item.current_value}
        </span>
        <span className="text-eyay-faint text-xs">→</span>
        <span className="text-xs text-eyay-faint">{item.threshold}</span>
      </div>
    </div>
  );
}
