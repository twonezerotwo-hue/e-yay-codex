"use client";

import { useState } from "react";
import type { ConfirmationItem } from "@/lib/types";
import { checkConfirmationSanity, type FinalStatus } from "@/lib/formatPrice";
import { useLanguage } from "@/contexts/LanguageContext";

function extractTF(signal: string): string | null {
  const m = /\b(15[mM]|30[mM]|1[hH]|4[hH]|1[dD]|[dD]1|[wW]1)\b/.exec(signal);
  return m ? m[1].toUpperCase() : null;
}

function statusIcon(met: boolean, status: FinalStatus): string {
  return status !== "ok" ? "?" : met ? "✓" : "✗";
}

function statusColor(met: boolean, status: FinalStatus): string {
  if (status !== "ok") return "text-amber-400";
  return met ? "text-emerald-400" : "text-red-400";
}

function chipCls(met: boolean, status: FinalStatus): string {
  if (status !== "ok") return "bg-amber-950/30 border-amber-900/50 text-amber-300";
  if (met)             return "bg-emerald-950/40 border-emerald-900/50 text-emerald-300";
  return "bg-eyay-raised border-eyay-border text-eyay-dim";
}

export default function ConfirmationStrip({ items }: { items: ConfirmationItem[] }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  const checked = items.map(item => ({
    ...item,
    sanity: checkConfirmationSanity(item.signal, item.current_value, item.threshold),
    tf:     extractTF(item.signal),
  }));

  // "met" sadece sanity=ok olanlar için geçerli
  const metOk   = checked.filter(i => i.met && i.sanity.final_status === "ok").length;
  const total   = checked.length;
  const suspect = checked.filter(i => i.sanity.final_status !== "ok").length;
  const pct     = total > 0 ? Math.round((metOk / total) * 100) : 0;

  const barColor = pct === 100 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-500" : "bg-orange-500";
  const pctColor = pct === 100 ? "text-emerald-400" : pct >= 60 ? "text-amber-400" : "text-orange-400";

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border overflow-hidden">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-eyay-border">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="text-[10px] font-mono font-semibold text-eyay-dim tracking-widest uppercase shrink-0">
            {t.confirmation.title}
          </span>
          {suspect > 0 && (
            <span className="text-[9px] font-mono text-amber-400/80 px-1.5 py-px rounded border border-amber-900/40 bg-amber-950/20 shrink-0">
              {suspect} şüpheli
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-20 h-1.5 bg-eyay-raised rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className={`text-xs font-mono font-bold ${pctColor}`}>
            {metOk}<span className="text-eyay-faint font-normal">/{total}</span>
          </span>
          <button
            onClick={() => setOpen(v => !v)}
            aria-expanded={open}
            className="text-[10px] font-mono text-eyay-blue hover:text-blue-300 transition-colors"
          >
            {open ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {!open ? (
        /* ── Kompakt chip görünümü (varsayılan) ── */
        <div className="px-3 py-2 flex flex-wrap gap-1.5">
          {checked.slice(0, 5).map((item, i) => {
            const icon = statusIcon(item.met, item.sanity.final_status);
            const cls  = chipCls(item.met, item.sanity.final_status);
            return (
              <span
                key={i}
                title={`Mevcut: ${item.current_value} | Eşik: ${item.threshold}`}
                className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-md border ${cls}`}
              >
                <span>{icon}</span>
                {item.signal}
              </span>
            );
          })}
          {checked.length > 5 && (
            <button
              onClick={() => setOpen(true)}
              className="text-[10px] font-mono text-eyay-blue/70 hover:text-eyay-blue px-1.5 py-0.5 transition-colors"
            >
              +{checked.length - 5} daha ▼
            </button>
          )}
        </div>
      ) : (
        /* ── Genişletilmiş liste ── */
        <div className="px-3 py-2.5 space-y-1.5">
          {checked.map((item, i) => {
            const { sanity } = item;
            const icon   = statusIcon(item.met, sanity.final_status);
            const icolor = statusColor(item.met, sanity.final_status);

            return (
              <div key={i} className="flex items-start gap-2 text-[10px] font-mono">
                <span className={`shrink-0 w-4 text-center font-bold ${icolor}`}>{icon}</span>
                <div className="flex-1 min-w-0 leading-snug">
                  <span className="text-eyay-text">{item.signal}</span>

                  {sanity.final_status === "ok" && (
                    /* ✓/✗ — her iki alan geçerli; met sonucu göster */
                    <span className="text-eyay-faint ml-1.5">
                      {sanity.current.displayValue ?? item.current_value}
                      {item.threshold
                        ? ` → ${sanity.threshold.displayValue ?? item.threshold}`
                        : ""}
                    </span>
                  )}

                  {sanity.final_status === "threshold_invalid" && (
                    /* Current geçerli; threshold sorunlu — current'ı suçlama */
                    <span className="ml-1.5">
                      <span className="text-eyay-faint">
                        {sanity.current.displayValue ?? item.current_value}
                      </span>
                      <span className="text-amber-400/70 ml-1.5">
                        Eşik şüpheli: {item.threshold}
                      </span>
                    </span>
                  )}

                  {sanity.final_status === "unit_uncertain" && (
                    <span className="text-amber-400/70 ml-1.5">
                      {item.current_value} (birim belirsiz)
                    </span>
                  )}

                  {(sanity.final_status === "current_invalid" ||
                    sanity.final_status === "unknown") && (
                    <span className="text-amber-400/70 ml-1.5">
                      {item.current_value} (değer aralık dışı)
                    </span>
                  )}

                  {item.tf && (
                    <span className="text-eyay-faint/50 ml-1.5">TF:{item.tf}</span>
                  )}
                </div>
              </div>
            );
          })}
          <p className="text-[8px] font-mono text-eyay-faint pt-1.5 border-t border-eyay-border/40">
            Teyit listesi · kaynak: sinyal motoru · PAPER_SAFE
          </p>
        </div>
      )}
    </div>
  );
}
