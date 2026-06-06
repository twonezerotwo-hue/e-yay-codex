"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import RefreshButton from "@/components/RefreshButton";

interface HeaderProps {
  totalSnapshots?: number;
  dataMode?: string;
}

export default function Header({ totalSnapshots, dataMode }: HeaderProps) {
  const { t, lang, toggle } = useLanguage();

  return (
    <header className="sticky top-0 z-20 border-b border-eyay-border bg-eyay-bg/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">

        {/* Sol: Logo */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-mono font-bold text-base tracking-[0.2em] text-white">E-YAY</span>
            <span className="text-eyay-faint font-mono text-xs">BrainChain</span>
          </div>
          <span className="hidden sm:inline-flex text-2xs font-mono border border-red-900 text-red-500 bg-red-950/40 rounded px-2 py-0.5 tracking-wider">
            NO EXECUTION
          </span>
        </div>

        {/* Sağ: varlık sayısı + mod + dil toggle */}
        <div className="flex items-center gap-3 text-xs text-eyay-faint font-mono">
          {totalSnapshots != null && (
            <span className="hidden sm:inline">{t.header.assets(totalSnapshots)}</span>
          )}
          {dataMode != null && (
            <span className={`px-2 py-0.5 rounded border text-2xs font-semibold ${
              dataMode === "live"
                ? "border-emerald-900 text-emerald-400 bg-emerald-950/40"
                : "border-amber-900 text-amber-400 bg-amber-950/40"
            }`}>
              {dataMode === "live" ? t.header.live : t.header.simulation}
            </span>
          )}

          {/* Yenile */}
          <RefreshButton />

          {/* Dil Toggle */}
          <button
            onClick={toggle}
            className={`
              px-2.5 py-0.5 rounded border text-2xs font-mono font-bold
              transition-all duration-200 cursor-pointer select-none
              ${lang === "tr"
                ? "border-eyay-border text-eyay-dim bg-eyay-raised hover:border-blue-700 hover:text-blue-400 hover:bg-blue-950/30"
                : "border-blue-700 text-blue-400 bg-blue-950/30 hover:border-eyay-border hover:text-eyay-dim hover:bg-eyay-raised"
              }
            `}
            title={lang === "tr" ? "Switch to English" : "Türkçeye geç"}
          >
            {lang === "tr" ? "EN" : "TR"}
          </button>
        </div>

      </div>
    </header>
  );
}
