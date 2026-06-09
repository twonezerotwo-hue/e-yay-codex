"use client";

/**
 * Büyük "Breaking War Alert" overlay'i.
 *
 * Headlines listesi içinde aktör (ABD/İsrail/İran/...) + askeri kelime
 * eşleşmesi varsa, en yüksek öncelikli alert için ekranın üstünde
 * profesyonel bir banner gösterir.
 *
 * - Aynı alert (id) son 30 dakikada gösterildiyse tekrar açılmaz.
 * - 10 saniye sonra otomatik kapanır.
 * - "Kapat" butonu manuel kapatır.
 * - "Detayları Gör" sayfanın haber bölümüne kaydırır.
 * - prefers-reduced-motion altında pulse animasyonu kapanır.
 */
import { useEffect, useMemo, useState } from "react";
import type { NewsHeadline } from "@/lib/types";
import {
  detectWarAlert,
  isAlertRecentlyShown,
  markAlertShown,
  pickTopWarAlert,
  type WarAlert,
} from "@/lib/warAlert";

const AUTO_DISMISS_MS = 10_000;

function timeAgo(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60)    return `${Math.floor(diff)} sn önce`;
    if (diff < 3600)  return `${Math.floor(diff / 60)} dk önce`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} sa önce`;
    return `${Math.floor(diff / 86400)} g önce`;
  } catch { return ""; }
}

function severityStyle(s: WarAlert["severity"]) {
  if (s === "critical") {
    return {
      border: "border-red-700/70",
      bg: "bg-red-950/60",
      ringClass: "ring-1 ring-red-800/40",
      dotClass: "bg-red-400",
      titleClass: "text-red-200",
      badgeClass: "bg-red-900/70 text-red-100 border-red-700/70",
      pulseClass: "motion-safe:animate-pulse-soft",
      label: "SON DAKİKA · SAVAŞ GÜNDEMİ",
      icon: "🚨",
    };
  }
  if (s === "high") {
    return {
      border: "border-amber-700/70",
      bg: "bg-amber-950/50",
      ringClass: "ring-1 ring-amber-800/30",
      dotClass: "bg-amber-300",
      titleClass: "text-amber-100",
      badgeClass: "bg-amber-900/60 text-amber-100 border-amber-700/60",
      pulseClass: "",
      label: "SON DAKİKA",
      icon: "🟠",
    };
  }
  return {
    border: "border-sky-800/70",
    bg: "bg-sky-950/40",
    ringClass: "ring-1 ring-sky-800/30",
    dotClass: "bg-sky-300",
    titleClass: "text-sky-100",
    badgeClass: "bg-sky-900/60 text-sky-100 border-sky-700/60",
    pulseClass: "",
    label: "GÜNDEMDE",
    icon: "ℹ",
  };
}

export default function WarBreakingAlert({
  headlines = [],
}: {
  headlines?: NewsHeadline[];
}) {
  const [activeAlert, setActiveAlert] = useState<WarAlert | null>(null);

  // Headlines listesinden ilk uygun alert'i seç (CRITICAL > HIGH).
  const candidate = useMemo<WarAlert | null>(
    () => pickTopWarAlert(headlines),
    [headlines],
  );

  // candidate değişince: dedup kontrolü → göster + dismiss timer kur.
  useEffect(() => {
    if (!candidate) return;
    if (isAlertRecentlyShown(candidate.id)) return;
    setActiveAlert(candidate);
    markAlertShown(candidate.id);
    const t = window.setTimeout(() => setActiveAlert(null), AUTO_DISMISS_MS);
    return () => window.clearTimeout(t);
  }, [candidate]);

  if (!activeAlert) return null;
  const s = severityStyle(activeAlert.severity);

  const scrollToNews = () => {
    if (typeof document === "undefined") return;
    // NewsPanel'ı veya en yakın "news" data-section'ı bul ve scroll et.
    const el =
      document.querySelector('[data-section="news"]') ||
      document.querySelector('#news') ||
      document.querySelector('main h2, main h3');
    if (el && "scrollIntoView" in el) {
      (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (activeAlert.url) {
      // Yeni sekmede aç — kullanıcı haberi okumak isteyebilir.
      window.open(activeAlert.url, "_blank", "noopener,noreferrer");
    }
    setActiveAlert(null);
  };

  return (
    <div
      className="fixed top-3 left-1/2 -translate-x-1/2 z-[250] w-[min(680px,calc(100vw-1.5rem))] pointer-events-none"
      role="alert"
      aria-live="assertive"
    >
      <div
        className={`pointer-events-auto rounded-xl border ${s.border} ${s.bg} ${s.ringClass} ${s.pulseClass} backdrop-blur-md shadow-lg p-3 sm:p-4`}
      >
        <div className="flex items-start gap-3">
          <div className="shrink-0 flex items-center gap-2 mt-0.5">
            <span className={`inline-block w-2 h-2 rounded-full ${s.dotClass} motion-safe:animate-pulse-soft`} />
            <span className="text-lg leading-none">{s.icon}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-[10px] font-mono font-black uppercase tracking-widest px-1.5 py-0.5 rounded border ${s.badgeClass}`}>
                {s.label}
              </span>
              <span className="text-[10px] font-mono text-eyay-dim">
                {activeAlert.source} · {timeAgo(activeAlert.timestamp)}
              </span>
            </div>
            <p className={`mt-1.5 text-sm sm:text-[15px] font-semibold leading-snug ${s.titleClass}`}>
              {activeAlert.title}
            </p>
            <div className="mt-2 flex flex-wrap items-baseline gap-1.5 text-[11px] font-mono">
              <span className="text-eyay-faint">Etkilenen:</span>
              {activeAlert.affected_assets.map((a) => (
                <span key={a} className="px-1.5 py-0.5 rounded border border-eyay-border bg-eyay-raised/50 text-eyay-text">
                  {a}
                </span>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-eyay-dim leading-snug">
              {activeAlert.market_impact}
            </p>
            <div className="mt-2.5 flex items-center gap-2">
              <button
                onClick={scrollToNews}
                className="text-[11px] font-mono font-semibold px-2.5 py-1 rounded border border-eyay-blue/40 text-eyay-blue hover:bg-eyay-blue/10 transition-colors"
              >
                Detayları Gör
              </button>
              <button
                onClick={() => setActiveAlert(null)}
                className="text-[11px] font-mono px-2.5 py-1 rounded border border-eyay-border text-eyay-faint hover:text-eyay-text hover:border-eyay-blue/40 transition-colors"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// İhraç edilmeyen — runtime referans dummy: detectWarAlert ileride başka yerde
// tek-haber test'inde kullanılabilir. Build-time tree-shake kalmamasın diye
// noqa: bundler ölü kodu otomatik atar.
void detectWarAlert;
