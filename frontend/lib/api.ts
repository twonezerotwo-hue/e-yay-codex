import type { AIReportResponse, ApiResponse } from "./types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function fetchRegimeReport(includeNews = true): Promise<ApiResponse> {
  const url = `${BACKEND}/api/v1/regime-report/current?include_news=${includeNews}`;
  // no-store — backend'in kendi 5dk cache'i var; Next.js hatayı dondurmasın
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return res.json();
}

// "auto" → Groq önce, Claude yedek (varsayılan öncelik sırası).
// Kullanıcı "groq" veya "claude" seçerse o sağlayıcı zorunlu kılınır (önbellek atlanır).
export type LLMProvider = "auto" | "groq" | "claude";

export async function fetchAIReport(provider?: LLMProvider): Promise<AIReportResponse> {
  const params = new URLSearchParams();
  if (provider && provider !== "auto") {
    params.set("provider", provider);
    params.set("force_refresh", "true");
  }
  const qs = params.toString();
  const url = `${BACKEND}/api/v1/ai-report/current${qs ? `?${qs}` : ""}`;
  // no-store — ai_analyst_service.py 15dk TTL cache yönetiyor; Next.js hata yanıtını dondurmasın
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`AI report backend error: ${res.status}`);
  return res.json();
}
