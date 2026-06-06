import { fetchAIReport, fetchRegimeReport } from "@/lib/api";
import AIAnalystReportPanel from "@/components/AIAnalystReport";
import DecisionBanner from "@/components/DecisionBanner";
import ScenarioPanel from "@/components/ScenarioPanel";
import MacroPanel from "@/components/MacroPanel";
import AssetGrid from "@/components/AssetGrid";
import AsymmetryCard from "@/components/AsymmetryCard";
import CatalystSidebar from "@/components/CatalystSidebar";
import ConfirmationStrip from "@/components/ConfirmationStrip";
import NewsPanel from "@/components/NewsPanel";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ActionCenter from "@/components/ActionCenter";
import CapitalFlowWidget from "@/components/CapitalFlowWidget"
import AIChatPanel from "@/components/AIChatPanel";
import AgentInsightBar from "@/components/AgentInsightBar";
import AutoRefresh from "@/components/AutoRefresh";
import PaperTradingTicker from "@/components/PaperTradingTicker";
import { MonitoringBanner, SystemHealthBar } from "@/components/SystemHealthBar";

// Cache'i kapat — backend kendi 5dk/15dk cache'lerini yönetiyor.
// Önemli: önceki "revalidate = 60" sayfayı dondurup eski 401 hatasını saplıyordu.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function HomePage() {
  let data = null;
  let error: string | null = null;
  let aiReport = null;
  let aiError: string | null = null;
  let geoNewsCount = 0;

  const [regimeResult, aiResult] = await Promise.allSettled([
    fetchRegimeReport(true),
    fetchAIReport(),
  ]);

  if (regimeResult.status === "fulfilled") {
    data = regimeResult.value;
  } else {
    error = regimeResult.reason instanceof Error
      ? regimeResult.reason.message
      : "Backend bağlantısı kurulamadı.";
  }

  if (aiResult.status === "fulfilled") {
    aiReport = aiResult.value.ai_report;
    geoNewsCount = aiResult.value.geo_news_count;
  } else {
    aiError = aiResult.reason instanceof Error
      ? aiResult.reason.message
      : "AI raporu alınamadı.";
  }

  return (
    <div className="min-h-screen bg-eyay-bg">

      {/* 🤖 AGENT — proaktif gözlem bandı (en üstte sticky) */}
      <AgentInsightBar />

      <Header
        totalSnapshots={data?.meta.total_snapshots}
        dataMode={data?.data_mode}
      />

      <MonitoringBanner aiError={!!(aiError || aiReport?.error)} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-2">

        {data?.module_health && (
          <div className="flex items-center gap-2 px-1 pb-1">
            <SystemHealthBar health={data.module_health} />
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-900/60 bg-red-950/30 p-6 text-center space-y-2">
            <p className="font-semibold text-red-400">Backend bağlantısı yok</p>
            <p className="text-sm text-eyay-dim">{error}</p>
            <p className="text-xs text-eyay-faint mt-2">
              <code className="font-mono text-eyay-blue bg-eyay-raised px-2 py-0.5 rounded">
                cd backend && uvicorn app.main:app --reload
              </code>
            </p>
          </div>
        )}

        {data && (
          <>
            {/* 1 ── Karar */}
            <DecisionBanner report={data.report} />

            {/* 2 ── Operasyonel Merkez */}
            <ActionCenter
              decision={data.report.decision}
              ownerActions={data.report.owner_actions ?? []}
              flipConditions={data.report.flip_conditions ?? []}
            />

            {/* 3 ── AI Yorumu  +  AI Sohbet (yan yana) */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-2 items-start">
              <AIAnalystReportPanel
                report={aiReport}
                error={aiError}
                geoNewsCount={geoNewsCount}
              />
              <div className="lg:sticky lg:top-16">
                <AIChatPanel />
              </div>
            </div>

            {/* 3 ── Durum Odası + Makro  |  Takvim */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-2 items-start">
              <div className="flex flex-col gap-2">
                <AssetGrid
                  signals={data.report.asset_signals}
                  techInsights={data.report.tech_insights ?? []}
                />
                <MacroPanel
                  macro={data.report.macro_layer}
                  appetite={data.report.appetite_layer}
                />
              </div>
              <div className="sticky top-16 self-start">
                <CatalystSidebar catalysts={data.report.upcoming_catalysts ?? []} />
              </div>
            </div>

            {/* 4 ── Sermaye Rotasyonu */}
            <CapitalFlowWidget rotation={data.capital_rotation} />

            {/* 5 ── Senaryo  |  Teyit  |  Asimetri */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px_200px] gap-2 items-stretch">
              <ScenarioPanel
                scenarios={data.report.scenarios ?? []}
                decision={data.report.decision}
              />
              <ConfirmationStrip items={data.report.confirmation_checklist} />
              <AsymmetryCard asymmetry={data.report.asymmetry} />
            </div>

            {/* 5 ── Haberler */}
            <NewsPanel headlines={data.report.news_headlines} />

            <Footer />
          </>
        )}
      </main>

      {/* 30 saniyede bir RSC tabanlı yenileme — Groq dostu (cache hit)
          Fiyatlar 3dk'da tazelenir, haberler 60sn'de, AI Yorumu 50dk'da. */}
      <AutoRefresh intervalSeconds={30} />

      {/* Paper Trading — 100k bakiye, agent sinyalleriyle otomatik long/short */}
      <PaperTradingTicker />
    </div>
  );
}
