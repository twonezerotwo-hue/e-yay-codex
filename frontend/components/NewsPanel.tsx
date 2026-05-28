import type { NewsHeadline, Sentiment } from "@/lib/types";

const SENTIMENT_STYLE: Record<Sentiment, string> = {
  BULLISH: "text-emerald-400 border-emerald-800",
  BEARISH: "text-red-400     border-red-800",
  NEUTRAL: "text-gray-400    border-gray-700",
};

const TAG_COLORS: Record<string, string> = {
  crypto:  "bg-blue-950  text-blue-400  border-blue-800",
  macro:   "bg-purple-950 text-purple-400 border-purple-800",
  energy:  "bg-orange-950 text-orange-400 border-orange-800",
  metals:  "bg-yellow-950 text-yellow-400 border-yellow-800",
  general: "bg-gray-900  text-gray-500  border-gray-700",
};

export default function NewsPanel({ headlines }: { headlines: NewsHeadline[] }) {
  if (headlines.length === 0) {
    return (
      <div className="bg-eyay-surface border border-eyay-border rounded-xl p-5">
        <h2 className="text-xs font-mono uppercase tracking-widest text-eyay-dim mb-3">Son Dakika Haberler</h2>
        <p className="text-xs text-eyay-dim font-mono">Haber verisi mevcut değil.</p>
      </div>
    );
  }

  const high   = headlines.filter(h => h.relevance === "HIGH");
  const others = headlines.filter(h => h.relevance !== "HIGH");

  return (
    <div className="bg-eyay-surface border border-eyay-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-mono uppercase tracking-widest text-eyay-dim">
          Son Dakika Haberler
        </h2>
        <span className="text-xs text-eyay-dim font-mono">{headlines.length} kaynak</span>
      </div>

      {high.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-mono text-red-400 uppercase tracking-wider mb-2">⚡ Yüksek Önem</p>
          <div className="space-y-2">
            {high.slice(0, 5).map((h, i) => <HeadlineRow key={i} h={h} />)}
          </div>
        </div>
      )}

      {others.length > 0 && (
        <div>
          {high.length > 0 && <div className="border-t border-eyay-border my-3" />}
          <div className="space-y-2">
            {others.slice(0, 8).map((h, i) => <HeadlineRow key={i} h={h} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function HeadlineRow({ h }: { h: NewsHeadline }) {
  return (
    <a
      href={h.url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className="block p-3 rounded-lg border border-eyay-border bg-eyay-bg hover:border-eyay-muted transition-colors"
    >
      <div className="flex items-start gap-2">
        <span className={`font-mono text-xs border rounded px-1.5 py-0.5 shrink-0 mt-0.5 ${SENTIMENT_STYLE[h.sentiment]}`}>
          {h.sentiment === "BULLISH" ? "▲" : h.sentiment === "BEARISH" ? "▼" : "—"}
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-mono text-xs text-eyay-text leading-relaxed line-clamp-2">{h.title}</p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className="text-xs text-eyay-dim font-mono">{h.source}</span>
            {h.tags.map(tag => (
              <span key={tag} className={`text-xs font-mono border rounded px-1.5 py-px ${TAG_COLORS[tag] ?? TAG_COLORS.general}`}>
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </a>
  );
}
