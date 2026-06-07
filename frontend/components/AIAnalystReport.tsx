"use client";

import type { AIAnalystReport } from "@/lib/types";
import { useLanguage } from "@/contexts/LanguageContext";

interface Props {
  report: AIAnalystReport | null;
  error?: string | null;
  geoNewsCount?: number;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="rounded-xl border border-eyay-border bg-eyay-surface/30 p-6 space-y-3 animate-pulse">
      <div className="flex items-center gap-2 mb-5">
        <div className="h-4 w-4 rounded-full bg-eyay-border" />
        <div className="h-3 w-36 rounded bg-eyay-border" />
        <div className="h-3 w-24 rounded bg-eyay-border ml-auto" />
      </div>
      {[95, 88, 72, 80, 65, 90, 55].map((w, i) => (
        <div key={i} className="h-2.5 rounded bg-eyay-border" style={{ width: `${w}%` }} />
      ))}
    </div>
  );
}

// ─── Hata ────────────────────────────────────────────────────────────────────

/**
 * AI rapor hata kutusu — her zaman tek, profesyonel mesaj.
 *
 * Ham backend hatası (örn. "invalid x-api-key", "ANTHROPIC_API_KEY") kullanıcıya
 * gösterilmez; backend bunu zaten generic mesaja sanitize ediyor, ama frontend
 * de ikinci kapı olarak savunma yapar — gelecekte başka kanaldan ham mesaj
 * sızarsa burada da yakalanır.
 */
function ErrorBox({ message }: { message: string }) {
  const { lang } = useLanguage();
  const isRawTechnical =
    /api[\s_-]?key|x-api-key|401|403|unauthorized|invalid|forbidden/i.test(message);
  const display = isRawTechnical
    ? (lang === "tr"
        ? "AI analiz katmanı geçici olarak kullanılamıyor. Veri ve risk motoru çalışmaya devam ediyor."
        : "AI analysis layer is temporarily unavailable. Data and risk engine continue to operate.")
    : message;

  return (
    <div className="rounded-xl border border-amber-800/40 bg-amber-950/15 px-5 py-4 flex items-start gap-3">
      <span className="text-amber-400 text-base mt-0.5 shrink-0">ℹ</span>
      <div className="space-y-1">
        <p className="font-mono text-xs text-amber-300 font-semibold tracking-wider">
          {lang === "tr" ? "AI YORUMU GEÇİCİ OLARAK YOK" : "AI ANALYSIS TEMPORARILY OFFLINE"}
        </p>
        <p className="font-mono text-xs text-eyay-dim leading-relaxed">{display}</p>
      </div>
    </div>
  );
}

// ─── Narratif ─────────────────────────────────────────────────────────────────

function NarrativeText({ text }: { text: string }) {
  const paragraphs = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
  return (
    <div className="space-y-4">
      {paragraphs.map((para, i) => (
        <p key={i} className="font-mono text-sm text-eyay-text leading-relaxed">{para}</p>
      ))}
    </div>
  );
}

// ─── Ana bileşen ─────────────────────────────────────────────────────────────

export default function AIAnalystReportPanel({ report, error, geoNewsCount }: Props) {
  const { t, lang } = useLanguage();

  if (!report && !error) return <Skeleton />;
  if (error) return <ErrorBox message={error} />;
  if (!report) return null;
  if (report.error) return <ErrorBox message={report.error} />;

  const generatedAt = new Date(report.generated_at).toLocaleString(
    lang === "tr" ? "tr-TR" : "en-US",
    { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" },
  );

  return (
    <div className="rounded-xl border border-eyay-border bg-eyay-surface/20 overflow-hidden">

      {/* ── Başlık çubuğu ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-eyay-border bg-eyay-surface/40">
        <div className="flex items-center gap-2.5">
          <span className="text-eyay-blue text-base">🤖</span>
          <span className="font-mono text-xs font-semibold text-eyay-text tracking-widest uppercase">
            {t.ai.title}
          </span>
          <span className="font-mono text-[10px] text-eyay-dim">
            {report.model} · {generatedAt}
            {report.cached && (
              <span className="ml-2 border border-eyay-border rounded px-1">{t.ai.cached}</span>
            )}
            {geoNewsCount !== undefined && geoNewsCount > 0 && (
              <span className="ml-2">· {t.ai.newsScanned(geoNewsCount)}</span>
            )}
          </span>
        </div>
        <span className="font-mono text-[10px] border border-eyay-blue/40 text-eyay-blue bg-eyay-blue/10 rounded px-2 py-0.5">
          Analiz modu · Canlı emir gönderimi kapalı
        </span>
      </div>

      {/* ── Sinyal tickers ────────────────────────────────────────────── */}
      {report.key_signals.length > 0 && (
        <div className="flex flex-wrap gap-2 px-5 py-2.5 border-b border-eyay-border bg-eyay-surface/20">
          {report.key_signals.map((sig, i) => (
            <span
              key={i}
              className="font-mono text-[10px] text-eyay-dim border border-eyay-border rounded px-2 py-0.5 whitespace-nowrap"
            >
              {sig}
            </span>
          ))}
        </div>
      )}

      {/* ── Narratif ──────────────────────────────────────────────────── */}
      <div className="px-5 py-5">
        {report.narrative ? (
          <NarrativeText text={report.narrative} />
        ) : (
          <p className="font-mono text-xs text-eyay-dim italic">{t.ai.preparing}</p>
        )}
      </div>

      {/* ── Sonuç + uyarı ─────────────────────────────────────────────── */}
      {(report.verdict || report.confidence_note) && (
        <div className="px-5 py-3 border-t border-eyay-border bg-eyay-surface/30 space-y-1.5">
          {report.verdict && (
            <p className="font-mono text-xs font-semibold text-eyay-text">
              <span className="text-eyay-dim mr-1.5">⚑</span>
              {report.verdict}
            </p>
          )}
          {report.confidence_note && (
            <p className="font-mono text-[10px] text-eyay-dim italic">{report.confidence_note}</p>
          )}
        </div>
      )}
    </div>
  );
}
