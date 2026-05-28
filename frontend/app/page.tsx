import { fetchRegimeReport } from "@/lib/api";
import DecisionBanner from "@/components/DecisionBanner";
import MacroPanel from "@/components/MacroPanel";
import AssetGrid from "@/components/AssetGrid";
import ConfirmationChecklist from "@/components/ConfirmationChecklist";
import NewsPanel from "@/components/NewsPanel";

export const revalidate = 60; // ISR — her 60 saniyede yenile

export default async function HomePage() {
  let data = null;
  let error: string | null = null;

  try {
    data = await fetchRegimeReport(true);
  } catch (e) {
    error = e instanceof Error ? e.message : "Backend bağlantısı kurulamadı.";
  }

  return (
    <main className="min-h-screen bg-eyay-bg">
      {/* Top bar */}
      <header className="border-b border-eyay-border bg-eyay-surface/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-mono font-bold text-eyay-text tracking-widest">E-YAY</span>
            <span className="text-eyay-dim font-mono text-xs">BrainChain</span>
            <span className="text-xs font-mono border border-red-800 text-red-400 bg-red-950 rounded px-2 py-0.5">
              NO EXECUTION
            </span>
          </div>
          {data && (
            <span className="text-xs font-mono text-eyay-dim">
              {data.meta.total_snapshots} asset · {data.data_mode}
            </span>
          )}
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Error state */}
        {error && (
          <div className="border border-red-800 bg-red-950/50 rounded-xl p-6 text-center">
            <p className="font-mono text-red-400 text-sm mb-2">Backend bağlantısı yok</p>
            <p className="font-mono text-eyay-dim text-xs">{error}</p>
            <p className="font-mono text-eyay-dim text-xs mt-3">
              Backend başlatmak için: <code className="text-eyay-blue">cd backend && uvicorn app.main:app --reload</code>
            </p>
          </div>
        )}

        {data && (
          <>
            {/* Katman 4 — Karar */}
            <DecisionBanner report={data.report} />

            {/* Katman 1 + 2 */}
            <MacroPanel
              macro={data.report.macro_layer}
              appetite={data.report.appetite_layer}
            />

            {/* Alt grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Katman 3 — Asset sinyalleri (2 col) */}
              <div className="lg:col-span-2">
                <AssetGrid signals={data.report.asset_signals} />
              </div>

              {/* Teyit listesi (1 col) */}
              <div>
                <ConfirmationChecklist items={data.report.confirmation_checklist} />
              </div>
            </div>

            {/* Haberler */}
            <NewsPanel headlines={data.report.news_headlines} />

            {/* Footer */}
            <footer className="text-center py-4 border-t border-eyay-border">
              <p className="font-mono text-xs text-eyay-dim">
                E-YAY BrainChain · PAPER_SAFE · NO_EXECUTION · Sadece analiz — trade kararı insana aittir.
              </p>
            </footer>
          </>
        )}
      </div>
    </main>
  );
}
