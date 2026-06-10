import type { AIReportResponse, ApiResponse } from "./types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function fetchRegimeReport(includeNews = true): Promise<ApiResponse> {
  const url = `${BACKEND}/api/v1/regime-report/current?include_news=${includeNews}`;
  // no-store — backend'in kendi 5dk cache'i var; Next.js hatayı dondurmasın
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Backend error: ${res.status}`);
  return res.json();
}

// ── Canonical Dashboard State ────────────────────────────────────────────────
// Tüm paneller için ortak veri kaynağı. Backend tek snapshot_id ile risk_gate,
// agent_votes, position_checks ViewModel'leri döner. PAPER_SAFE / NO_EXECUTION.

export type RiskGateStatus = "PASS" | "CAUTION" | "BLOCK";
export type AgentVote      = "ALLOW" | "CAUTION" | "BLOCK" | "ABSTAIN";

export interface RiskGateView {
  status:               RiskGateStatus;
  source_risk_action:   string;
  reason:               string;
  hard_blockers:        string[];
  soft_warnings:        string[];
  dqs_score:            number | null;
  dqs_passed:           boolean | null;
  kill_switch_active:   boolean;
  no_position_increase: boolean;
  risk_reduce:          boolean;
  evidence:             Record<string, unknown>[];
}

export interface AgentVoteView {
  agent_name:   string;
  vote:         AgentVote;
  confidence:   number | null;
  direction:    string | null;
  reason:       string;
  evidence:     Record<string, unknown>[];
  invalidation: string | null;
}

export interface DashboardStateResponse {
  status:                   string;
  paper_safe:               boolean;
  execution_side_effects:   string;
  snapshot_id:              string;
  generated_at:             string;
  cached:                   boolean;
  state: {
    snapshot_id:    string;
    generated_at:   string;
    data_mode:      string;
    execution_mode: string;
    risk_gate:      RiskGateView | null;
    agent_votes:    AgentVoteView[];
    position_checks: Record<string, unknown>[];
    module_health:   Record<string, { score: string; detail: string }>;
    data_quality:    { score: number; passed: boolean; per_module: Record<string, number> };
    warnings:        string[];
    [key: string]: unknown;
  };
  warnings: string[];
}

export async function fetchDashboardState(forceRefresh = false): Promise<DashboardStateResponse> {
  const qs = forceRefresh ? "?force_refresh=true" : "";
  const url = `${BACKEND}/api/v1/dashboard/state${qs}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Dashboard state backend error: ${res.status}`);
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
