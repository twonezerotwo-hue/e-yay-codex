"use client";

import { useEffect, useRef, useState } from "react";
import type { LLMProvider } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ToolCall {
  tool: string;
  label: string;
}

interface ProviderInfo {
  provider: "groq" | "claude";
  status: "active" | "fallback";
  reason?: string;
}

// ---------------------------------------------------------------------------
// Örnek sorular — hızlı başlatıcılar
// ---------------------------------------------------------------------------

const STARTERS = [
  "Genel piyasa durumu nedir? Ne bekliyoruz?",
  "BTC için teknik seviyeler nerede?",
  "Sermaye şu an nereye akıyor?",
  "Önümüzdeki hafta hangi kritik olaylar var?",
  "Altın ile petrol korelasyonu ne diyor?",
  "Mevcut rejimde en güçlü sinyal hangisi?",
];

// ---------------------------------------------------------------------------
// Mesaj balonu
// ---------------------------------------------------------------------------

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  const paras  = msg.content.split(/\n\n+/).map(p => p.trim()).filter(Boolean);

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="shrink-0 w-6 h-6 rounded-full bg-eyay-blue/20 border border-eyay-blue/30 flex items-center justify-center mt-0.5">
          <span className="text-[9px] text-eyay-blue font-bold">AI</span>
        </div>
      )}

      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed space-y-2 ${
          isUser
            ? "bg-eyay-blue/15 border border-eyay-blue/30 text-eyay-text rounded-br-sm"
            : "bg-eyay-raised border border-eyay-border text-eyay-dim rounded-bl-sm"
        }`}
      >
        {paras.map((p, i) => {
          if (p.startsWith("•") || p.startsWith("-") || p.startsWith("*")) {
            const lines = p.split("\n").filter(Boolean);
            return (
              <ul key={i} className="space-y-1 pl-1">
                {lines.map((ln, j) => (
                  <li key={j} className="flex gap-1.5">
                    <span className="text-eyay-blue shrink-0">›</span>
                    <span>{ln.replace(/^[•\-*]\s*/, "")}</span>
                  </li>
                ))}
              </ul>
            );
          }
          if (/^\d+\./.test(p)) {
            const lines = p.split("\n").filter(Boolean);
            return (
              <ol key={i} className="space-y-1 pl-1 list-none">
                {lines.map((ln, j) => (
                  <li key={j} className="flex gap-1.5">
                    <span className="text-eyay-blue shrink-0 font-mono">{j + 1}.</span>
                    <span>{ln.replace(/^\d+\.\s*/, "")}</span>
                  </li>
                ))}
              </ol>
            );
          }
          return <p key={i}>{p}</p>;
        })}
      </div>

      {isUser && (
        <div className="shrink-0 w-6 h-6 rounded-full bg-eyay-raised border border-eyay-border flex items-center justify-center mt-0.5">
          <span className="text-[9px] text-eyay-faint">SEN</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Araç çağrısı rozeti
// ---------------------------------------------------------------------------

function ToolBadge({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-[9px] font-mono text-eyay-faint/70 italic py-0.5">
      <span className="inline-block w-1 h-1 rounded-full bg-eyay-blue/50 animate-pulse shrink-0" />
      {label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Streaming balonu (cevap gelirken)
// ---------------------------------------------------------------------------

function ProviderChip({ info }: { info: ProviderInfo }) {
  const isGroq = info.provider === "groq";
  const isFallback = info.status === "fallback";
  const label = isGroq ? "GROQ · llama-3.3-70b" : "CLAUDE · opus-4-7";
  const cls = isFallback
    ? "text-amber-300 border-amber-800/60 bg-amber-950/30"
    : isGroq
      ? "text-emerald-300 border-emerald-800/60 bg-emerald-950/30"
      : "text-eyay-blue border-eyay-blue/40 bg-eyay-blue/10";
  return (
    <div className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border font-mono text-[8px] font-bold ${cls}`}>
      {isFallback && <span>⤳</span>}
      {label}
    </div>
  );
}

function StreamingBubble({
  text,
  toolCalls,
  provider,
}: {
  text: string;
  toolCalls: ToolCall[];
  provider: ProviderInfo | null;
}) {
  const paras = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
  const hasText = text.trim().length > 0;

  return (
    <div className="flex gap-3 justify-start">
      <div className="shrink-0 w-6 h-6 rounded-full bg-eyay-blue/20 border border-eyay-blue/30 flex items-center justify-center mt-0.5">
        <span className="w-1.5 h-1.5 rounded-full bg-eyay-blue animate-pulse" />
      </div>

      <div className="max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-3 text-xs leading-relaxed bg-eyay-raised border border-eyay-border text-eyay-dim space-y-2">

        {/* Sağlayıcı + araç çağrıları */}
        {(provider || toolCalls.length > 0) && (
          <div className="space-y-1 pb-1 border-b border-eyay-border/50">
            {provider && <ProviderChip info={provider} />}
            {toolCalls.map((tc, i) => (
              <ToolBadge key={i} label={tc.label} />
            ))}
          </div>
        )}

        {/* Yanıt metni */}
        {hasText ? (
          <>
            {paras.map((p, i) => <p key={i}>{p}</p>)}
            <span className="inline-block w-1 h-3 bg-eyay-blue/70 animate-pulse ml-0.5 align-middle" />
          </>
        ) : (
          !toolCalls.length && !provider && (
            <span className="text-eyay-faint italic">Düşünüyor…</span>
          )
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ana bileşen
// ---------------------------------------------------------------------------

export default function AIChatPanel() {
  const [open,      setOpen]      = useState(false);
  const [messages,  setMessages]  = useState<Message[]>([]);
  const [input,     setInput]     = useState("");
  const [streaming, setStreaming] = useState("");
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [provider,  setProvider]  = useState<ProviderInfo | null>(null);
  // Kullanıcının manuel sağlayıcı seçimi — varsayılan "auto" (Groq → Claude öncelik sırası)
  const [modelChoice, setModelChoice] = useState<LLMProvider>("auto");
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);
  const abortRef  = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming, toolCalls]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  // ---------------------------------------------------------------------------
  // Gönder
  // ---------------------------------------------------------------------------
  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput("");
    const userMsg: Message = { role: "user", content: trimmed };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setStreaming("");
    setToolCalls([]);
    setProvider(null);
    setLoading(true);

    abortRef.current = new AbortController();

    try {
      const res = await fetch("/api/chat", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({
          messages: newHistory.map(m => ({ role: m.role, content: m.content })),
          provider: modelChoice,
        }),
        signal: abortRef.current.signal,
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = "";
      let   full    = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") break;
          try {
            const parsed = JSON.parse(raw);

            if (parsed.error) {
              setError(parsed.error);
              break;
            }

            if (parsed.tool) {
              setToolCalls(prev => [
                ...prev,
                { tool: parsed.tool, label: parsed.label ?? parsed.tool },
              ]);
            }

            if (parsed.provider) {
              setProvider({
                provider: parsed.provider,
                status:   parsed.status ?? "active",
                reason:   parsed.reason,
              });
            }

            if (parsed.text) {
              full += parsed.text;
              setStreaming(full);
            }
          } catch { /* parse hatası — atla */ }
        }
      }

      if (full) {
        setMessages(prev => [...prev, { role: "assistant", content: full }]);
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setError(err.message);
      }
    } finally {
      setStreaming("");
      setToolCalls([]);
      setProvider(null);
      setLoading(false);
      abortRef.current = null;
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function cancelStream() {
    abortRef.current?.abort();
  }

  function clearChat() {
    abortRef.current?.abort();
    setMessages([]);
    setStreaming("");
    setToolCalls([]);
    setProvider(null);
    setLoading(false);
    setError(null);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="bg-eyay-surface rounded-2xl border border-eyay-border shadow-card overflow-hidden">

      {/* ── Başlık çubuğu ── */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5 border-b border-eyay-border hover:bg-eyay-raised/30 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-eyay-blue text-sm">🧠</span>
          <div className="text-left">
            <p className="text-2xs text-eyay-faint uppercase tracking-widest font-semibold">
              Piyasa Stratejisti
            </p>
            <p className="text-sm font-semibold text-eyay-text mt-0.5">
              Canlı verilerle senaryo analizi
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {messages.length > 0 && (
            <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5 py-0.5">
              {messages.length} mesaj
            </span>
          )}
          {/* Manuel model seçimi — varsayılan "Otomatik" (Groq → Claude öncelik sırası) */}
          <select
            value={modelChoice}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => { e.stopPropagation(); setModelChoice(e.target.value as LLMProvider); }}
            disabled={loading}
            className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5 py-0.5 bg-eyay-surface focus:outline-none focus:border-eyay-blue/50 disabled:opacity-50"
          >
            <option value="auto">Otomatik (Groq → Claude)</option>
            <option value="groq">Groq</option>
            <option value="claude">Claude</option>
          </select>
          <span className="text-[9px] font-mono text-eyay-faint border border-eyay-border rounded px-1.5 py-0.5">
            PAPER_SAFE
          </span>
          <span className={`text-eyay-faint text-sm transition-transform duration-200 ${open ? "rotate-180" : ""}`}>
            ▾
          </span>
        </div>
      </button>

      {/* ── Panel içeriği ── */}
      {open && (
        <div className="flex flex-col" style={{ height: "520px" }}>

          {/* Mesaj alanı */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">

            {/* Boş durum — örnek sorular */}
            {messages.length === 0 && !streaming && !loading && (
              <div className="space-y-4">
                <p className="text-[10px] text-eyay-faint text-center font-mono py-2">
                  Stratejist canlı verilerle çalışır — sorduğun şeye göre ihtiyaç duyduğu veriyi kendisi çeker.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {STARTERS.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(s)}
                      className="text-left text-[10px] text-eyay-dim border border-eyay-border rounded-xl px-3 py-2.5 hover:border-eyay-blue/40 hover:text-eyay-text hover:bg-eyay-raised/30 transition-colors leading-relaxed"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Mesaj listesi */}
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}

            {/* Aktif streaming */}
            {(loading || streaming) && (
              <StreamingBubble text={streaming} toolCalls={toolCalls} provider={provider} />
            )}

            {/* Hata */}
            {error && (
              <div className="text-[10px] text-red-400 font-mono bg-red-950/20 border border-red-900/40 rounded-xl px-3 py-2">
                ⚠ {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* ── Input alanı ── */}
          <div className="border-t border-eyay-border p-3 space-y-2">

            {messages.length > 0 && (
              <div className="flex items-center gap-2 px-1">
                <button
                  onClick={clearChat}
                  className="text-[9px] font-mono text-eyay-faint hover:text-eyay-dim transition-colors"
                >
                  ✕ Sohbeti temizle
                </button>
                {loading && (
                  <button
                    onClick={cancelStream}
                    className="text-[9px] font-mono text-red-400/70 hover:text-red-400 transition-colors ml-auto"
                  >
                    ■ Durdur
                  </button>
                )}
              </div>
            )}

            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Soru sor veya senaryo anlat… (Enter göndermek için)"
                rows={2}
                disabled={loading}
                className={`
                  flex-1 resize-none rounded-xl border px-3 py-2.5 text-xs leading-relaxed
                  bg-eyay-raised text-eyay-text placeholder:text-eyay-faint/50
                  border-eyay-border focus:border-eyay-blue/50 focus:outline-none
                  transition-colors scrollbar-thin
                  ${loading ? "opacity-50 cursor-not-allowed" : ""}
                `}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={loading || !input.trim()}
                className={`
                  shrink-0 h-[58px] w-10 rounded-xl border flex items-center justify-center transition-all
                  ${loading || !input.trim()
                    ? "border-eyay-border text-eyay-faint/30 cursor-not-allowed"
                    : "border-eyay-blue/50 text-eyay-blue hover:bg-eyay-blue/10 hover:border-eyay-blue"}
                `}
              >
                {loading
                  ? <span className="w-2 h-2 rounded-full bg-eyay-blue animate-pulse" />
                  : <span className="text-sm">↑</span>
                }
              </button>
            </div>

            <p className="text-[8px] text-eyay-faint/40 font-mono px-1">
              groq (llama-3.3-70b) → claude (opus-4-7) fallback · 5 araç · PAPER_SAFE
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
