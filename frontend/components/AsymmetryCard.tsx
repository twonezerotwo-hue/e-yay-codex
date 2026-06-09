"use client";

import { useEffect, useRef, useState } from "react";
import type { AsymmetrySignal } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

const STYLES = {
  green:  { ring: "border-emerald-700", label: "text-emerald-400", bar: "bg-emerald-500", glow: "shadow-emerald-900/40" },
  lime:   { ring: "border-lime-700",    label: "text-lime-400",    bar: "bg-lime-500",    glow: "shadow-lime-900/40"    },
  yellow: { ring: "border-amber-700",   label: "text-amber-400",   bar: "bg-amber-400",   glow: "shadow-amber-900/40"   },
  orange: { ring: "border-orange-700",  label: "text-orange-400",  bar: "bg-orange-500",  glow: "shadow-orange-900/40"  },
  red:    { ring: "border-red-700",     label: "text-red-400",     bar: "bg-red-500",     glow: "shadow-red-900/40"     },
} as const;

function isSuspect(a: AsymmetrySignal): boolean {
  return (
    a.ratio < 0.05 ||
    a.ratio > 15 ||
    a.expected_gain_pct < 0 ||
    a.expected_gain_pct > 100 ||
    a.expected_loss_pct <= 0 ||
    a.expected_loss_pct > 100
  );
}

export default function AsymmetryCard({ asymmetry }: { asymmetry: AsymmetrySignal }) {
  const { t } = useLanguage();
  const [showFormula, setShowFormula] = useState(false);
  const prevRatioRef = useRef<number | null>(null);

  const suspect   = !asymmetry || isSuspect(asymmetry);
  const prevRatio = prevRatioRef.current;
  const bigJump   =
    !suspect &&
    asymmetry != null &&
    prevRatio !== null &&
    (asymmetry.ratio / prevRatio > 2.5 || prevRatio / asymmetry.ratio > 2.5);

  // Effect runs after every render to track the last valid ratio.
  // No deps array is intentional — we always want the latest confirmed value.
  useEffect(() => {
    if (asymmetry && !isSuspect(asymmetry)) {
      prevRatioRef.current = asymmetry.ratio;
    }
  });

  if (!asymmetry) return null;

  const s      = STYLES[asymmetry.color] ?? STYLES.yellow;
  const totalW = asymmetry.expected_gain_pct + asymmetry.expected_loss_pct;
  const gainW  = totalW > 0 ? (asymmetry.expected_gain_pct / totalW) * 100 : 50;
  const lossW  = 100 - gainW;
  const computed = asymmetry.expected_loss_pct > 0
    ? (asymmetry.expected_gain_pct / asymmetry.expected_loss_pct).toFixed(2)
    : "—";

  return (
    <div
      className={`bg-eyay-surface rounded-2xl border ${
        suspect ? "border-eyay-border" : `${s.ring} shadow-lg ${s.glow}`
      } overflow-hidden flex flex-col`}
    >
      {/* ── Header ── */}
      <div className="px-4 py-2.5 border-b border-eyay-border flex items-center justify-between">
        <div>
          <p className="text-[9px] text-eyay-faint uppercase tracking-widest font-semibold">
            {t.asymmetry.sectionLabel}
          </p>
          <p className="text-xs font-semibold text-eyay-text mt-0.5">{t.asymmetry.title}</p>
        </div>
        {!suspect && (
          <button
            onClick={() => setShowFormula(v => !v)}
            className="text-[9px] font-mono text-eyay-blue hover:text-blue-300 transition-colors"
          >
            {showFormula ? "▲" : "Formül ▼"}
          </button>
        )}
      </div>

      <div className="p-4 flex-1">
        {suspect ? (
          /* ── Şüpheli / hesaplanamadı görünümü ── */
          <div className="space-y-2">
            <p className="text-[10px] font-mono text-amber-400 font-semibold">
              ⚠ Asimetri hesaplanamadı
            </p>
            <p className="text-[9px] text-eyay-faint leading-snug">
              Giriş değerleri sanity kontrolünden geçmedi. Güvenilir hesaplama için veri doğrulaması gerekiyor.
            </p>
            <div className="text-[9px] font-mono text-eyay-faint/50 space-y-0.5 pt-1 border-t border-eyay-border/40">
              <div>
                Oran: {asymmetry.ratio.toFixed(2)}×
                {(asymmetry.ratio < 0.05 || asymmetry.ratio > 15) ? " ← aralık dışı" : ""}
              </div>
              <div>
                Kazanç %{asymmetry.expected_gain_pct} · Kayıp %{asymmetry.expected_loss_pct}
              </div>
            </div>
          </div>
        ) : (
          /* ── Normal görünüm ── */
          <div className="space-y-3">
            {bigJump && prevRatio !== null && (
              <div className="text-[9px] font-mono text-amber-400/80 border border-amber-900/40 bg-amber-950/20 rounded px-2 py-1 leading-snug">
                ⚠ Asimetri değişimi yüksek: {prevRatio.toFixed(1)}× → {asymmetry.ratio.toFixed(1)}×
              </div>
            )}

            {/* Büyük oran */}
            <div className="flex items-end justify-between gap-3">
              <div>
                <span className={`font-mono font-black text-3xl leading-none ${s.label}`}>
                  {asymmetry.ratio.toFixed(1)}
                  <span className="text-base font-bold">×</span>
                </span>
                <p className={`text-[10px] font-semibold mt-1 ${s.label}`}>{asymmetry.label}</p>
              </div>
              <div className="text-right space-y-0.5">
                <div className="text-[10px] font-mono">
                  <span className="text-eyay-faint">{t.asymmetry.gain} </span>
                  <span className="text-emerald-400 font-semibold">+{asymmetry.expected_gain_pct}%</span>
                </div>
                <div className="text-[10px] font-mono">
                  <span className="text-eyay-faint">{t.asymmetry.loss} </span>
                  <span className="text-red-400 font-semibold">−{asymmetry.expected_loss_pct}%</span>
                </div>
              </div>
            </div>

            {/* Görsel çubuk */}
            <div>
              <div className="flex h-2.5 rounded-full overflow-hidden gap-0.5">
                <div
                  className="bg-emerald-500 rounded-l-full transition-all duration-700"
                  style={{ width: `${gainW}%` }}
                />
                <div
                  className="bg-red-500 rounded-r-full transition-all duration-700"
                  style={{ width: `${lossW}%` }}
                />
              </div>
              <div className="flex justify-between mt-0.5">
                <span className="text-[8px] font-mono text-emerald-400/60">{t.asymmetry.upside}</span>
                <span className="text-[8px] font-mono text-red-400/60">{t.asymmetry.downside}</span>
              </div>
            </div>

            {/* Kısa açıklama */}
            <p className="text-[10px] text-eyay-dim leading-relaxed border-t border-eyay-border pt-2">
              {asymmetry.brief}
            </p>

            {/* Formül detayı */}
            {showFormula && (
              <div className="border-t border-eyay-border/50 pt-2 space-y-1.5">
                <p className="text-[9px] font-mono text-eyay-faint/80 font-semibold uppercase tracking-wide">
                  Formül
                </p>
                <p className="text-[9px] font-mono text-eyay-faint">
                  Asimetri = beklenen yukarı hareket / beklenen aşağı hareket
                </p>
                <div className="text-[9px] font-mono text-eyay-faint/70 space-y-0.5">
                  <div>Yukarı: +{asymmetry.expected_gain_pct}%</div>
                  <div>Aşağı: −{asymmetry.expected_loss_pct}%</div>
                  <div>Hesaplanan: {computed}×</div>
                </div>
                <p className="text-[8px] font-mono text-eyay-faint/40 pt-0.5">
                  {t.asymmetry.methodology}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
