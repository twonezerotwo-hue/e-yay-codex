"use client";

/**
 * Otomatik sayfa yenileyici — Groq dostu.
 *
 * Önemli: sayfa yenileme Groq'a istek YAPMAZ — backend cache hit olur.
 * Groq tüketimi cache TTL'ine bağlı:
 *   • AI Yorumu : 2 saat cache → 12 çağrı/gün → ~41k token (70b limit 100k,
 *                 stratejist + agent ile paylaşılan kotanın ~%40'ı)
 *   • Haber çev.: 6 saat cache → 4 çağrı/gün  → ~18k token (8b limit 500k)
 * Yani 30s'lik yenileme bile Groq'a yük getirmez, sadece RSC re-render.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const PRESETS: Array<{ label: string; seconds: number }> = [
  { label: "30s",   seconds:  30  },
  { label: "60s",   seconds:  60  },
  { label: "2dk",   seconds: 120  },
  { label: "5dk",   seconds: 300  },
];

const STORAGE_KEY = "eyay.refresh.interval";

export default function AutoRefresh({
  intervalSeconds: defaultInterval = 60,
}: {
  intervalSeconds?: number;
}) {
  const router = useRouter();

  // LocalStorage'den son seçimi oku (varsa)
  const [interval, setIntervalSec] = useState(defaultInterval);
  const [secondsLeft, setSecondsLeft] = useState(defaultInterval);
  const [paused,     setPaused]       = useState(false);
  const [refreshing, setRefreshing]   = useState(false);
  const [menuOpen,   setMenuOpen]     = useState(false);
  const [agentOpen,  setAgentOpen]    = useState(false);  // agent modal açıksa gizle
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Agent modal açıkken kendini gizle
  useEffect(() => {
    const onAgent = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setAgentOpen(!!detail?.open);
    };
    window.addEventListener("eyay:agent-modal", onAgent as EventListener);
    return () => window.removeEventListener("eyay:agent-modal", onAgent as EventListener);
  }, []);

  // İlk render: localStorage oku
  useEffect(() => {
    const saved = typeof window !== "undefined"
      ? window.localStorage.getItem(STORAGE_KEY)
      : null;
    if (saved) {
      const n = parseInt(saved, 10);
      if (!isNaN(n) && n > 0) {
        setIntervalSec(n);
        setSecondsLeft(n);
      }
    }
  }, []);

  // Interval değişince LocalStorage'e yaz
  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, String(interval));
    }
  }, [interval]);

  // Geri sayım + auto-refresh
  useEffect(() => {
    if (paused) return;

    tickRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          setRefreshing(true);
          router.refresh();
          setTimeout(() => setRefreshing(false), 600);
          return interval;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [paused, interval, router]);

  function manualRefresh() {
    setRefreshing(true);
    router.refresh();
    setSecondsLeft(interval);
    setTimeout(() => setRefreshing(false), 600);
  }

  function pickInterval(sec: number) {
    setIntervalSec(sec);
    setSecondsLeft(sec);
    setMenuOpen(false);
  }

  if (agentOpen) return null;  // agent modal aktifken kendini gizle

  const stateClass = refreshing
    ? "border-emerald-500/60 text-emerald-300 bg-emerald-950/40"
    : paused
      ? "border-amber-700/60 text-amber-300 bg-amber-950/30"
      : "border-eyay-border text-eyay-faint bg-eyay-surface";

  const dotClass = refreshing
    ? "bg-emerald-400 motion-safe:animate-pulse-soft"
    : paused
      ? "bg-amber-400"
      : "bg-eyay-blue/60 motion-safe:animate-pulse-soft";

  // Saniye formatla — 60+ ise "1:23" gibi
  const fmt = (s: number) =>
    s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : `${s}s`;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex items-center gap-1 select-none">

      {/* Menü açıkken: preset seçenekleri */}
      {menuOpen && (
        <div className="flex flex-col gap-0.5 mr-1 bg-eyay-surface border border-eyay-border rounded-lg p-1 shadow-card">
          <div className="text-[8px] font-mono text-eyay-faint px-2 py-0.5 uppercase tracking-wider border-b border-eyay-border/50 mb-0.5">
            Yenileme sıklığı
          </div>
          {PRESETS.map((p) => (
            <button
              key={p.seconds}
              onClick={() => pickInterval(p.seconds)}
              className={`text-left text-[10px] font-mono px-2 py-1 rounded hover:bg-eyay-raised/50 transition-colors ${
                interval === p.seconds
                  ? "text-eyay-blue bg-eyay-blue/10"
                  : "text-eyay-dim"
              }`}
            >
              {interval === p.seconds && "✓ "}{p.label}
            </button>
          ))}
          <div className="text-[8px] font-mono text-eyay-faint/60 px-2 py-1 border-t border-eyay-border/50 mt-0.5 leading-tight">
            Sayfa yenileme Groq'a<br />istek yapmaz (cache hit).
          </div>
        </div>
      )}

      {/* Sayaç / durum */}
      <button
        onClick={() => setPaused((v) => !v)}
        title={paused ? "Devam ettir" : "Duraklat"}
        className={`flex items-center gap-1.5 px-2 py-1 rounded-l-lg border-l border-y font-mono text-[10px] transition-colors ${stateClass}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
        {paused ? "DURDURULDU" : refreshing ? "YENİLENDİ" : fmt(secondsLeft)}
      </button>

      {/* Interval seçici (≡) */}
      <button
        onClick={() => setMenuOpen((v) => !v)}
        title="Yenileme sıklığı"
        className={`px-2 py-1 border-y font-mono text-[10px] hover:text-eyay-blue hover:border-eyay-blue/40 transition-colors ${stateClass}`}
      >
        {fmt(interval)}
      </button>

      {/* Manuel yenile (↻) */}
      <button
        onClick={manualRefresh}
        title="Şimdi yenile"
        className={`px-2 py-1 rounded-r-lg border-r border-y font-mono text-[10px] hover:text-eyay-blue hover:border-eyay-blue/40 transition-colors ${stateClass}`}
      >
        ↻
      </button>
    </div>
  );
}
