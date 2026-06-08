"use client";

/**
 * GlobalEventPanel — Harita + haber akışı + seçili haber detayı.
 *
 * Mevcut `NewsPanel` kendi başına da çalışmaya devam eder (eski sayfa yapısını
 * bozmaz). Bu yeni panel ek bir dashboard bölümü olarak monte edilir ve haber
 * listesini "piyasa terminali" formatında gösterir + harita ile iki yönlü
 * bağlantılıdır.
 *
 * Veri: sayfa zaten /regime-report/current çekiyor, news_headlines (enriched)
 * alanını prop olarak alır.
 *
 * Bağımlılık eklenmedi (no react-simple-maps); SVG harita inline.
 */
import { useMemo, useState } from "react";
import type {
  ClaimStatus, NewsHeadline, NewsSeverity,
} from "@/lib/types";
import GlobalEventMap from "./GlobalEventMap";

interface Props {
  headlines: NewsHeadline[];
}

// ── Severity stil paleti ────────────────────────────────────────────────────
const SEV_STYLE: Record<NewsSeverity, {
  label:        string;
  badgeBg:      string;
  badgeText:    string;
  borderCls:    string;       // kart border + animasyon
  dotCls:       string;
}> = {
  RED: {
    label:     "YÜKSEK",
    badgeBg:   "bg-red-950/60",
    badgeText: "text-red-300 border-red-700",
    borderCls: "border-red-900/60 news-critical-border",
    dotCls:    "bg-red-400",
  },
  ORANGE: {
    label:     "YÜKSEK",
    badgeBg:   "bg-orange-950/55",
    badgeText: "text-orange-300 border-orange-700",
    borderCls: "border-orange-900/50 news-high-border",
    dotCls:    "bg-orange-400",
  },
  YELLOW: {
    label:     "ORTA",
    badgeBg:   "bg-yellow-950/40",
    badgeText: "text-yellow-300 border-yellow-800",
    borderCls: "border-yellow-900/40",
    dotCls:    "bg-yellow-400",
  },
  BLUE: {
    label:     "DÜŞÜK",
    badgeBg:   "bg-blue-950/30",
    badgeText: "text-blue-300 border-blue-800",
    borderCls: "border-blue-900/30",
    dotCls:    "bg-blue-400",
  },
};

// ── Claim status stil ───────────────────────────────────────────────────────
const CLAIM_STYLE: Record<ClaimStatus, { label: string; cls: string }> = {
  VERIFIED:     { label: "TEYİTLİ",       cls: "text-emerald-300 border-emerald-800/60 bg-emerald-950/30" },
  PARTIAL:      { label: "KISMİ",         cls: "text-amber-300   border-amber-800/60   bg-amber-950/30"   },
  UNVERIFIED:   { label: "TEYİTSİZ",      cls: "text-rose-300    border-rose-800/60    bg-rose-950/30"    },
  CONTEXT_ONLY: { label: "BAĞLAM",        cls: "text-slate-300   border-slate-700/60   bg-slate-950/30"   },
};

// ── Asset direction → renkli ok ─────────────────────────────────────────────
function ImpactChip({ code, direction, note }: { code: string; direction: string; note?: string }) {
  const cls =
    direction === "positive" ? "text-emerald-300 border-emerald-800/60 bg-emerald-950/30" :
    direction === "negative" ? "text-red-300     border-red-800/60     bg-red-950/30"     :
                                "text-amber-300   border-amber-800/40   bg-amber-950/20";
  const arrow = direction === "positive" ? "↑" : direction === "negative" ? "↓" : "↔";
  return (
    <span
      title={note}
      className={`inline-flex items-center gap-0.5 text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${cls}`}
    >
      <span>{arrow}</span>
      <span>{code}</span>
    </span>
  );
}

// ── Yardımcı: severity'i NewsHeadline'dan türet (geriye uyumlu) ─────────────
function severityOf(h: NewsHeadline): NewsSeverity {
  if (h.severity) return h.severity;
  // Backend enrichment çalışmamışsa fallback
  if (h.relevance === "HIGH") return "ORANGE";
  if (h.relevance === "MEDIUM") return "YELLOW";
  return "BLUE";
}

// ── Zaman ago ───────────────────────────────────────────────────────────────
function relTime(iso: string): string {
  try {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60)    return `${Math.floor(diff)}sn`;
    if (diff < 3600)  return `${Math.floor(diff / 60)}dk`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}sa`;
    return `${Math.floor(diff / 86400)}g`;
  } catch { return ""; }
}

// ── Ana panel ───────────────────────────────────────────────────────────────

export default function GlobalEventPanel({ headlines }: Props) {
  // Lokasyonlu ve lokasyonsuz tüm haberler — UI'da tümünü göster, haritada sadece lokasyonlu olanlar
  const sortedHeadlines = useMemo(() => {
    const sevRank: Record<NewsSeverity, number> = { RED: 0, ORANGE: 1, YELLOW: 2, BLUE: 3 };
    return [...headlines].sort((a, b) => {
      const sa = sevRank[severityOf(a)];
      const sb = sevRank[severityOf(b)];
      if (sa !== sb) return sa - sb;
      // Aynı severity → daha taze önce
      try {
        return new Date(b.published_at).getTime() - new Date(a.published_at).getTime();
      } catch { return 0; }
    });
  }, [headlines]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(
    () => sortedHeadlines.find(h => h.event_id === selectedId) ?? null,
    [sortedHeadlines, selectedId],
  );

  const counts = useMemo(() => {
    const out = { RED: 0, ORANGE: 0, YELLOW: 0, BLUE: 0, withLocation: 0 };
    for (const h of sortedHeadlines) {
      out[severityOf(h)]++;
      if (h.location) out.withLocation++;
    }
    return out;
  }, [sortedHeadlines]);

  if (sortedHeadlines.length === 0) return null;

  return (
    <section className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="px-5 py-4 border-b border-eyay-border flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-base">🌐</span>
          <div>
            <p className="text-[10px] font-mono text-eyay-faint uppercase tracking-widest font-semibold">
              Global Event Map · Son Dakika
            </p>
            <p className="text-sm font-semibold text-eyay-text mt-0.5">
              Coğrafi haber haritası + piyasa karar etkisi
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono">
          {counts.RED > 0 && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-red-800/60 bg-red-950/40 text-red-300 severity-badge-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> {counts.RED} RED
            </span>
          )}
          {counts.ORANGE > 0 && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-orange-800/60 bg-orange-950/40 text-orange-300">
              <span className="w-1.5 h-1.5 rounded-full bg-orange-400" /> {counts.ORANGE} ORANGE
            </span>
          )}
          {counts.YELLOW > 0 && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-yellow-900/60 bg-yellow-950/30 text-yellow-300">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" /> {counts.YELLOW} YELLOW
            </span>
          )}
          {counts.BLUE > 0 && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-blue-900/60 bg-blue-950/30 text-blue-300">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400" /> {counts.BLUE} BLUE
            </span>
          )}
          <span className="text-eyay-faint">
            {counts.withLocation}/{sortedHeadlines.length} haritada
          </span>
        </div>
      </header>

      {/* ── Grid: harita | liste | seçili detay ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr_0.9fr] gap-0 divide-x divide-eyay-border">

        {/* SOL — Harita */}
        <div className="p-3 min-h-[280px]">
          <GlobalEventMap
            headlines={sortedHeadlines}
            selectedEventId={selectedId}
            onSelect={setSelectedId}
          />
        </div>

        {/* ORTA — Haber listesi */}
        <div className="p-3 max-h-[560px] overflow-y-auto space-y-2">
          {sortedHeadlines.slice(0, 14).map(h => {
            const sev = severityOf(h);
            const st  = SEV_STYLE[sev];
            const isSelected = h.event_id === selectedId;
            const display = (h.title_tr && h.title_tr.trim()) || h.title;
            return (
              <button
                key={h.event_id ?? h.title}
                onClick={() => setSelectedId(h.event_id ?? null)}
                className={`w-full text-left rounded-lg border bg-eyay-raised/50 p-3 transition-all
                  ${st.borderCls}
                  ${isSelected ? "ring-2 ring-eyay-blue/60 bg-eyay-raised" : "hover:bg-eyay-raised"}`}
              >
                {/* Üst: severity + claim + kaynak + zaman */}
                <div className="flex items-center gap-2 flex-wrap mb-1.5">
                  <span className={`inline-flex items-center gap-1 text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${st.badgeBg} ${st.badgeText}`}>
                    <span className={`w-1 h-1 rounded-full ${st.dotCls}`} />
                    {st.label}
                  </span>
                  {h.claim_status && (
                    <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${CLAIM_STYLE[h.claim_status].cls}`}>
                      {CLAIM_STYLE[h.claim_status].label}
                    </span>
                  )}
                  {h.location && (
                    <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5 py-0.5">
                      📍 {h.location.name}
                    </span>
                  )}
                  <span className="text-[9px] font-mono text-eyay-faint ml-auto">
                    {h.source} · {relTime(h.published_at)}
                  </span>
                </div>

                {/* Başlık */}
                <p className="text-xs text-eyay-text leading-snug line-clamp-2">
                  {display}
                </p>

                {/* Asset impacts */}
                {h.asset_impact && h.asset_impact.length > 0 && (
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    {h.asset_impact.slice(0, 5).map((imp, i) => (
                      <ImpactChip
                        key={i}
                        code={imp.asset_code}
                        direction={imp.direction}
                        note={imp.note}
                      />
                    ))}
                  </div>
                )}
              </button>
            );
          })}
          {sortedHeadlines.length > 14 && (
            <p className="text-[10px] font-mono text-eyay-faint text-center py-2">
              +{sortedHeadlines.length - 14} ek haber alt panelde
            </p>
          )}
        </div>

        {/* SAĞ — Seçili haber detayı */}
        <div className="p-4">
          {!selected ? (
            <div className="h-full flex items-center justify-center text-center">
              <div className="space-y-2">
                <p className="text-xs font-mono text-eyay-faint">
                  Haritada bir marker'a veya listede bir habere<br />tıklayın
                </p>
                <p className="text-[10px] text-eyay-faint/60">
                  Detay · etki · karar yansıması burada görünür
                </p>
              </div>
            </div>
          ) : (
            <SelectedDetail h={selected} />
          )}
        </div>
      </div>

      {/* Footer — Ticker (en kritik 8 haber) */}
      {sortedHeadlines.length > 0 && (
        <div className="border-t border-eyay-border bg-eyay-bg/30 overflow-hidden">
          <div className="flex items-center">
            <span className="shrink-0 px-3 py-1.5 text-[9px] font-mono font-bold text-amber-300 border-r border-eyay-border bg-amber-950/20 tracking-widest">
              CANLI AKIŞ
            </span>
            <div className="overflow-hidden relative flex-1">
              <div className="news-ticker-track flex items-center gap-6 whitespace-nowrap py-1.5 px-4">
                {[...sortedHeadlines.slice(0, 10), ...sortedHeadlines.slice(0, 10)].map((h, i) => {
                  const st = SEV_STYLE[severityOf(h)];
                  const display = (h.title_tr && h.title_tr.trim()) || h.title;
                  return (
                    <span key={i} className="flex items-center gap-1.5 text-[10px] font-mono">
                      <span className={`w-1.5 h-1.5 rounded-full ${st.dotCls} shrink-0`} />
                      <span className="text-eyay-faint">{h.source}</span>
                      <span className="text-eyay-text">{display.length > 80 ? display.slice(0, 80) + "…" : display}</span>
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Seçili haber detay paneli ───────────────────────────────────────────────
function SelectedDetail({ h }: { h: NewsHeadline }) {
  const sev   = severityOf(h);
  const st    = SEV_STYLE[sev];
  const claim = h.claim_status ? CLAIM_STYLE[h.claim_status] : null;
  const display = (h.title_tr && h.title_tr.trim()) || h.title;

  return (
    <article className="space-y-3 text-xs">
      {/* Üst rozetler */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`inline-flex items-center gap-1 text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${st.badgeBg} ${st.badgeText} severity-badge-pulse`}>
          <span className={`w-1 h-1 rounded-full ${st.dotCls}`} />
          {st.label} ({sev})
        </span>
        {claim && (
          <span className={`text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border ${claim.cls}`}>
            {claim.label}
          </span>
        )}
        {h.location && (
          <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5 py-0.5">
            📍 {h.location.name}
          </span>
        )}
      </div>

      {/* Başlık */}
      <h3 className="text-sm font-semibold text-eyay-text leading-snug">
        {display}
      </h3>

      {/* Kaynak + zaman + url */}
      <div className="flex items-center justify-between text-[10px] font-mono text-eyay-faint">
        <span>{h.source} · {relTime(h.published_at)} önce</span>
        {h.url && (
          <a href={h.url} target="_blank" rel="noopener noreferrer"
             className="text-eyay-blue hover:text-blue-300 transition-colors">
            kaynak ↗
          </a>
        )}
      </div>

      {/* Asset impact bölümü */}
      {h.asset_impact && h.asset_impact.length > 0 && (
        <div className="rounded-lg border border-eyay-border bg-eyay-raised/30 p-2.5 space-y-1.5">
          <p className="text-[9px] font-mono text-eyay-faint uppercase tracking-widest font-bold">
            Etkilenen varlıklar
          </p>
          <div className="flex flex-wrap gap-1.5">
            {h.asset_impact.map((imp, i) => (
              <ImpactChip
                key={i}
                code={imp.asset_code}
                direction={imp.direction}
                note={imp.note}
              />
            ))}
          </div>
        </div>
      )}

      {/* Decision impact */}
      {h.decision_impact && (
        <div className="rounded-lg border border-eyay-blue/30 bg-eyay-blue/5 p-3 space-y-1">
          <p className="text-[9px] font-mono text-eyay-blue uppercase tracking-widest font-bold flex items-center gap-1.5">
            <span>⚑</span>
            Karar Etkisi
          </p>
          <p className="text-[11px] text-eyay-text leading-relaxed">
            {h.decision_impact}
          </p>
        </div>
      )}

      {/* Etiketler */}
      {h.tags && h.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {h.tags.map(tag => (
            <span key={tag}
                  className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5 py-px">
              #{tag}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
